[CmdletBinding()]
param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ModelsDir = Join-Path $ProjectRoot "models"
$DownloadsDir = Join-Path $ModelsDir "downloads"
$ManifestPath = Join-Path $ModelsDir "manifest.local.json"
$ConfigPath = Join-Path $ProjectRoot "config\models.json"
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

New-Item -ItemType Directory -Force -Path $ModelsDir, $DownloadsDir | Out-Null
$Config = Get-Content -Raw -LiteralPath $ConfigPath | ConvertFrom-Json
$Artifacts = @()
Add-Type -AssemblyName System.IO.Compression.FileSystem

function Get-OrDownload {
    param([string]$Url, [string]$Destination, [string]$ExpectedSha256 = "")
    $NeedsDownload = $Force -or -not (Test-Path -LiteralPath $Destination)
    if (-not $NeedsDownload -and [IO.Path]::GetExtension($Destination) -eq ".zip") {
        try {
            $Archive = [IO.Compression.ZipFile]::OpenRead($Destination)
            $Archive.Dispose()
        } catch {
            Write-Host "Onvolledige download gevonden; wordt opnieuw opgehaald: $Destination" -ForegroundColor Yellow
            $NeedsDownload = $true
        }
    }
    if ($NeedsDownload) {
        Write-Host "Downloaden: $Url"
        $PartialPath = $Destination + ".partial"
        if (Test-Path -LiteralPath $PartialPath) {
            Remove-Item -Force -LiteralPath $PartialPath
        }
        Invoke-WebRequest -Uri $Url -OutFile $PartialPath -UseBasicParsing
        Move-Item -Force -LiteralPath $PartialPath -Destination $Destination
    } else {
        Write-Host "Bestaat al: $Destination"
    }
    if ($ExpectedSha256) {
        $Actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $Destination).Hash.ToLowerInvariant()
        if ($Actual -ne $ExpectedSha256.ToLowerInvariant()) {
            throw "SHA-256 wijkt af voor $Destination. Verwacht $ExpectedSha256, kreeg $Actual"
        }
    }
}

function Add-ArtifactRecord {
    param(
        [string]$Name,
        [string]$Url,
        [string]$Path,
        [string]$Version,
        [string]$License,
        [string]$UpstreamCommit = ""
    )
    $File = Get-Item -LiteralPath $Path
    $Hash = Get-FileHash -Algorithm SHA256 -LiteralPath $Path
    $script:Artifacts += [ordered]@{
        name = $Name
        source_url = $Url
        upstream_version = $Version
        upstream_commit = $UpstreamCommit
        local_path = $File.FullName
        bytes = $File.Length
        sha256 = $Hash.Hash.ToLowerInvariant()
        license = $License
        recorded_at = (Get-Date).ToString("o")
    }
}

foreach ($EngineName in @("vosk-small", "vosk-lgraph", "vosk-full")) {
    $Engine = $Config.engines.$EngineName
    $ArchivePath = Join-Path $DownloadsDir ($Engine.model_version + ".zip")
    $InstallPath = Join-Path $ProjectRoot $Engine.model_path
    $ExpectedHash = if ($Engine.archive_sha256) { $Engine.archive_sha256 } else { "" }
    Get-OrDownload -Url $Engine.source_url -Destination $ArchivePath -ExpectedSha256 $ExpectedHash
    if ($Force -or -not (Test-Path -LiteralPath $InstallPath)) {
        Write-Host "Uitpakken: $($Engine.model_version)"
        Expand-Archive -LiteralPath $ArchivePath -DestinationPath $ModelsDir -Force
    }
    if (-not (Test-Path -LiteralPath $InstallPath)) {
        throw "Modelmap ontbreekt na uitpakken: $InstallPath"
    }
    Add-ArtifactRecord -Name $EngineName -Url $Engine.source_url -Path $ArchivePath -Version $Engine.model_version -License $Engine.license
}

foreach ($EngineName in @("whisper-base-q5", "whisper-small-q5", "whisper-large-v3-turbo-q5")) {
    $Engine = $Config.engines.$EngineName
    $ModelPath = Join-Path $ProjectRoot $Engine.model_path
    Get-OrDownload -Url $Engine.source_url -Destination $ModelPath -ExpectedSha256 $Engine.sha256
    Add-ArtifactRecord -Name ($EngineName + "-model") -Url $Engine.source_url -Path $ModelPath -Version $Engine.model_version -License $Engine.license -UpstreamCommit $Engine.upstream_commit
}

$Vad = $Config.vad_models.'silero-v6.2'
$VadPath = Join-Path $ProjectRoot $Vad.model_path
Get-OrDownload -Url $Vad.source_url -Destination $VadPath -ExpectedSha256 $Vad.sha256
Add-ArtifactRecord -Name "silero-vad-v6.2" -Url $Vad.source_url -Path $VadPath -Version $Vad.model_version -License $Vad.license

$Runtime = $Config.engines.'whisper-base-q5'
$RuntimeArchive = Join-Path $DownloadsDir ("whisper.cpp-" + $Runtime.runtime_release + "-x64.zip")
$RuntimeRoot = Join-Path $ModelsDir "whisper.cpp"
$RuntimeTemp = Join-Path $DownloadsDir "whisper-runtime-extracted"
Get-OrDownload -Url $Runtime.runtime_url -Destination $RuntimeArchive -ExpectedSha256 $Runtime.runtime_sha256
if ($Force -or -not (Test-Path -LiteralPath (Join-Path $RuntimeRoot "bin\whisper-cli.exe"))) {
    if (Test-Path -LiteralPath $RuntimeTemp) {
        Remove-Item -Recurse -Force -LiteralPath $RuntimeTemp
    }
    New-Item -ItemType Directory -Force -Path $RuntimeTemp | Out-Null
    Expand-Archive -LiteralPath $RuntimeArchive -DestinationPath $RuntimeTemp -Force
    New-Item -ItemType Directory -Force -Path (Join-Path $RuntimeRoot "bin") | Out-Null
    $Cli = Get-ChildItem -Path $RuntimeTemp -Recurse -Filter "whisper-cli.exe" | Select-Object -First 1
    if (-not $Cli) {
        throw "whisper-cli.exe is niet aangetroffen in $RuntimeArchive"
    }
    Copy-Item -LiteralPath $Cli.FullName -Destination (Join-Path $RuntimeRoot "bin\whisper-cli.exe") -Force
    Get-ChildItem -Path $Cli.DirectoryName -Filter "*.dll" | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $RuntimeRoot "bin\$($_.Name)") -Force
    }
}
if (Test-Path -LiteralPath $RuntimeTemp) {
    Remove-Item -Recurse -Force -LiteralPath $RuntimeTemp
}
Add-ArtifactRecord -Name "whisper.cpp-runtime" -Url $Runtime.runtime_url -Path $RuntimeArchive -Version $Runtime.runtime_release -License "MIT" -UpstreamCommit $Runtime.runtime_commit

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python-omgeving ontbreekt. Maak eerst .venv en installeer requirements.txt."
}
Write-Host "ONNX-modellen ophalen en valideren..."
& $Python (Join-Path $PSScriptRoot "setup-onnx-models.py")
if ($LASTEXITCODE -ne 0) {
    throw "Het downloaden of laden van een ONNX-model is mislukt."
}

[ordered]@{
    schema_version = 2
    generated_at = (Get-Date).ToString("o")
    artifacts = $Artifacts
} | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 -LiteralPath $ManifestPath

Write-Host "Klaar. Lokaal manifest: $ManifestPath"
