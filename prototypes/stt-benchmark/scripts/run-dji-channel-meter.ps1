[CmdletBinding()]
param(
    [int]$Port = 8766,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python-omgeving ontbreekt."
}

Set-Location -LiteralPath $ProjectRoot
$MeterSource = Join-Path $ProjectRoot "native\wasapi-raw-meter\WasapiRawMeter.cs"
$MeterExe = Join-Path $ProjectRoot "native\wasapi-raw-meter\WasapiRawMeter.exe"
if (-not (Test-Path -LiteralPath $MeterExe) -or
    (Get-Item -LiteralPath $MeterSource).LastWriteTimeUtc -gt (Get-Item -LiteralPath $MeterExe).LastWriteTimeUtc) {
    & (Join-Path $PSScriptRoot "build-wasapi-meter.ps1")
}
$Arguments = @("-m", "src.channel_meter_app", "--port", "$Port")
if ($NoBrowser) { $Arguments += "--no-browser" }

Write-Host "DJI 4-kanaalsmeter starten..." -ForegroundColor Cyan
Write-Host "Deze app neemt niets op en voert geen transcriptie uit." -ForegroundColor Yellow
& $Python @Arguments
exit $LASTEXITCODE
