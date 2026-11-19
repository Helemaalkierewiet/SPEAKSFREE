[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Source = Join-Path $ProjectRoot "native\wasapi-raw-meter\WasapiRawMeter.cs"
$Output = Join-Path $ProjectRoot "native\wasapi-raw-meter\WasapiRawMeter.exe"
$Compiler = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"

if (-not (Test-Path -LiteralPath $Compiler)) {
    throw "De lokale C#-compiler ontbreekt: $Compiler"
}

& $Compiler /nologo /optimize+ /target:exe "/out:$Output" $Source
if ($LASTEXITCODE -ne 0) {
    throw "De RAW WASAPI-meter kon niet worden gebouwd."
}
Write-Host "Gebouwd: $Output" -ForegroundColor Green
