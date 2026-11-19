[CmdletBinding()]
param(
    [string]$Device,
    [int]$Port = 8765,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python-omgeving ontbreekt. Voer eerst scripts\run-all-benchmarks.ps1 -Quick uit."
}

Set-Location -LiteralPath $ProjectRoot
$MeterSource = Join-Path $ProjectRoot "native\wasapi-raw-meter\WasapiRawMeter.cs"
$MeterExe = Join-Path $ProjectRoot "native\wasapi-raw-meter\WasapiRawMeter.exe"
if (-not (Test-Path -LiteralPath $MeterExe) -or
    (Get-Item -LiteralPath $MeterSource).LastWriteTimeUtc -gt (Get-Item -LiteralPath $MeterExe).LastWriteTimeUtc) {
    & (Join-Path $PSScriptRoot "build-wasapi-meter.ps1")
}
$Arguments = @("-m", "src.live_app", "--port", "$Port")
if ($Device) { $Arguments += @("--device", $Device) }
if ($NoBrowser) { $Arguments += "--no-browser" }

Write-Host "DJI Mic 3-prototype starten..." -ForegroundColor Cyan
Write-Host "Audio-invoer: native RAW WASAPI (afzonderlijke transmitters)." -ForegroundColor Green
Write-Host "De app ondersteunt S (2 USB-kanalen) en Q (4 afzonderlijke USB-kanalen)." -ForegroundColor Yellow
Write-Host "Gebruik bij dubbele kanalen Q en klik daarna in de app op Microfoon opnieuw verbinden." -ForegroundColor Yellow
Write-Host "Stoppen kan later met Ctrl+C in dit venster."
& $Python @Arguments
exit $LASTEXITCODE
