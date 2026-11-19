[CmdletBinding()]
param(
    [string]$Manifest = "references/private/dji_mini_baseline/manifest.json",
    [ValidateRange(1, 20)]
    [int]$Repetitions = 3,
    [string[]]$Engines,
    [switch]$SkipSetup,
    [switch]$SkipNearLive,
    [switch]$Quick
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Requirements = Join-Path $ProjectRoot "requirements.txt"
$ConfigPath = Join-Path $ProjectRoot "config\models.json"
Set-Location -LiteralPath $ProjectRoot

function Invoke-Python {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python-opdracht is mislukt: $($Arguments -join ' ')"
    }
}

if (-not (Test-Path -LiteralPath $Python)) {
    Write-Host "Python 3.11-omgeving maken..." -ForegroundColor Cyan
    & py -3.11 -m venv (Join-Path $ProjectRoot ".venv")
    if ($LASTEXITCODE -ne 0) {
        throw "Python 3.11 is niet gevonden. Installeer Python 3.11 en probeer opnieuw."
    }
}

if (-not $SkipSetup) {
    Write-Host "Afhankelijkheden en modellen controleren..." -ForegroundColor Cyan
    Invoke-Python -Arguments @("-m", "pip", "install", "-r", $Requirements)
    & (Join-Path $PSScriptRoot "setup-models.ps1")
    if ($LASTEXITCODE -ne 0) {
        throw "Modelinstallatie is mislukt."
    }
}

Invoke-Python -Arguments @("-m", "src.verify")

$ManifestPath = (Resolve-Path -LiteralPath $Manifest).Path
$Session = Split-Path -Leaf (Split-Path -Parent $ManifestPath)
$Config = Get-Content -Raw -LiteralPath $ConfigPath | ConvertFrom-Json
if (-not $Engines -or $Engines.Count -eq 0) {
    $Engines = @($Config.engines.PSObject.Properties.Name)
}

$ConcurrencyLevels = if ($Quick) { @(1) } else { @(1, 2, 4) }
if ($Quick) {
    $Repetitions = 1
    $SkipNearLive = $true
    Write-Host "Snelle controle: één offline run per model." -ForegroundColor Yellow
} else {
    Write-Host "Volledige matrix: $($Engines.Count) modellen, 1/2/4 streams en $Repetitions herhalingen." -ForegroundColor Cyan
    if (-not $SkipNearLive) {
        Write-Host "Daarna volgt ook de bijna-live test; die speelt de audiolengte in realtime af." -ForegroundColor Yellow
    }
}

foreach ($Concurrency in $ConcurrencyLevels) {
    foreach ($Engine in $Engines) {
        Write-Host "`nOffline: $Engine, $Concurrency stream(s)" -ForegroundColor Green
        Invoke-Python -Arguments @(
            "-m", "src.benchmark",
            "--manifest", $ManifestPath,
            "--engines", $Engine,
            "--mode", "offline",
            "--concurrency", "$Concurrency",
            "--repetitions", "$Repetitions"
        )
    }
}

if (-not $SkipNearLive) {
    foreach ($Engine in $Engines) {
        Write-Host "`nBijna-live: $Engine" -ForegroundColor Green
        Invoke-Python -Arguments @(
            "-m", "src.benchmark",
            "--manifest", $ManifestPath,
            "--engines", $Engine,
            "--mode", "near-live",
            "--concurrency", "1",
            "--repetitions", "$Repetitions"
        )
    }
}

$ReportName = "ALL_MODELS_{0}_REPORT.md" -f $Session.ToUpperInvariant()
$ReportPath = Join-Path "results" $ReportName
Invoke-Python -Arguments @(
    "-m", "src.report",
    "--session", $Session,
    "--output", $ReportPath
)

Write-Host "`nBenchmark voltooid." -ForegroundColor Green
Write-Host "Rapport: $ReportPath"
Write-Host "Ruwe resultaten: results\raw"
