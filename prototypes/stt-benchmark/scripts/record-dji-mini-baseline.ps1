[CmdletBinding()]
param(
    [Parameter()]
    [ValidateRange(0, 999)]
    [int]$Device = 1,

    [Parameter()]
    [ValidatePattern('^[a-zA-Z0-9_-]+$')]
    [string]$Session = 'dji_mini_baseline',

    [Parameter()]
    [ValidatePattern('^[a-zA-Z0-9_-]+$')]
    [string]$Speaker = 'adult-a'
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python-omgeving ontbreekt: $Python"
}

Set-Location -LiteralPath $ProjectRoot

& $Python -c "import sounddevice as sd; d=sd.query_devices($Device); assert int(d['max_input_channels']) > 0, 'Dit apparaat heeft geen invoerkanalen'; print('Geselecteerd:', d['name'], '- invoerkanalen:', int(d['max_input_channels']))"
if ($LASTEXITCODE -ne 0) {
    throw "Microfoonapparaat $Device kon niet als invoer worden geopend. Voer eerst 'python -m src.capture --list-devices' uit."
}

$Clips = @(
    [PSCustomObject]@{
        Name = 'short_yes_01'
        Duration = 5
        Category = 'short-answer'
        Noise = 'quiet room'
        Style = 'normal'
        Instruction = 'Zeg exact vijf keer ja, met korte pauzes.'
        Reference = 'ja ja ja ja ja'
        Critical = @('ja')
    },
    [PSCustomObject]@{
        Name = 'household_conversation_01'
        Duration = 20
        Category = 'household-conversation'
        Noise = 'quiet room'
        Style = 'normal'
        Instruction = 'Lees de getoonde tekst normaal voor.'
        Reference = 'Weet jij al wat we vanavond eten Ik dacht aan spaghetti We hebben alles nog in huis toch Volgens mij wel behalve geraspte kaas Zal ik zo nog heel snel even naar de Super Fijn Neem dan meteen even een pak melk mee Is goed ben zo terug'
        Critical = @('spaghetti', 'geraspte kaas', 'melk')
    },
    [PSCustomObject]@{
        Name = 'names_places_01'
        Duration = 10
        Category = 'names-places'
        Noise = 'quiet room'
        Style = 'normal'
        Instruction = 'Lees de getoonde tekst normaal voor.'
        Reference = 'Hoi Anna waar ga jij naartoe op vakantie in de zomer naar Spanje met Mark en Sophie naar Barcelona'
        Critical = @('Anna', 'Spanje', 'Mark', 'Sophie', 'Barcelona')
    },
    [PSCustomObject]@{
        Name = 'numbers_times_amounts_01'
        Duration = 10
        Category = 'numbers'
        Noise = 'quiet room'
        Style = 'normal'
        Instruction = 'Lees de getoonde tekst normaal voor.'
        Reference = 'afspraak om twaalf uur dertig voor vijftig euro met veertig personen in Amsterdam is dat'
        Critical = @('twaalf', 'dertig', 'vijftig', 'veertig', 'Amsterdam')
    },
    [PSCustomObject]@{
        Name = 'care_medical_01'
        Duration = 10
        Category = 'care-medical'
        Noise = 'quiet room'
        Style = 'normal'
        Instruction = 'Lees de medische zin exact voor.'
        Reference = 'de chirurg heeft vandaag om half drie een spoedoperatie op de intensive care uitgevoerd voor de ernstige griep van patient jan pietersen'
        Critical = @('chirurg', 'half drie', 'spoedoperatie', 'intensive care', 'griep', 'Jan Pietersen')
    },
    [PSCustomObject]@{
        Name = 'soft_fast_speech_01'
        Duration = 10
        Category = 'soft-fast-speech'
        Noise = 'quiet room'
        Style = 'soft and fast'
        Instruction = 'Spreek deze zin zacht en relatief snel.'
        Reference = 'voorzichtig fluisterend snel naar de overkant rennen voordat de deur dichtvalt'
        Critical = @('voorzichtig', 'overkant', 'deur')
    },
    [PSCustomObject]@{
        Name = 'hesitation_correction_01'
        Duration = 10
        Category = 'hesitation-correction'
        Noise = 'quiet room'
        Style = 'hesitation and self-correction'
        Instruction = 'Spreek de aarzelingen en correctie letterlijk uit.'
        Reference = 'ik wil graag ik bedoel wij willen graag twee nee drie broodjes bestellen'
        Critical = @('twee', 'drie', 'broodjes')
    },
    [PSCustomObject]@{
        Name = 'silence_30s_01'
        Duration = 30
        Category = 'silence'
        Noise = 'quiet room'
        Style = 'silence'
        Instruction = 'Blijf dertig seconden volledig stil.'
        Reference = ' '
        Critical = @()
    },
    [PSCustomObject]@{
        Name = 'light_noise_radio_01'
        Duration = 30
        Category = 'light-noise'
        Noise = 'radio in background'
        Style = 'normal'
        Instruction = 'Zet de radio zacht aan en lees de zin een keer normaal voor.'
        Reference = 'hallo mijn naam is Pieter Jansen en ik ben dus de echte Pieter Jansen de for real Pieter Jansen'
        Critical = @('Pieter Jansen')
    }
)

foreach ($Clip in $Clips) {
    $Accepted = $false
    while (-not $Accepted) {
        Write-Host ''
        Write-Host '==================================================' -ForegroundColor Cyan
        Write-Host "VOLGENDE OPNAME: $($Clip.Name)" -ForegroundColor Yellow
        Write-Host "Duur: $($Clip.Duration) seconden"
        Write-Host $Clip.Instruction -ForegroundColor Green

        if ($Clip.Category -ne 'silence') {
            Write-Host ''
            Write-Host 'TEKST:' -ForegroundColor Cyan
            Write-Host $Clip.Reference -ForegroundColor White
        }

        [void](Read-Host 'Druk op Enter wanneer je klaar bent')

        $CaptureArgs = @(
            '-m', 'src.capture',
            '--session', $Session,
            '--name', $Clip.Name,
            '--duration', [string]$Clip.Duration,
            '--device', [string]$Device,
            '--speaker', $Speaker,
            '--category', $Clip.Category,
            '--distance-cm', '20',
            '--noise', $Clip.Noise,
            '--speaking-style', $Clip.Style,
            '--reference', $Clip.Reference,
            '--consent'
        )

        foreach ($Word in $Clip.Critical) {
            $CaptureArgs += @('--critical-word', $Word)
        }

        & $Python @CaptureArgs
        if ($LASTEXITCODE -ne 0) {
            throw "De opname $($Clip.Name) is mislukt. Er zijn geen volgende clips gestart."
        }

        $Answer = Read-Host 'Was de tekst exact en zag het volumeniveau er goed uit? (j/n)'
        $Accepted = $Answer -match '^(j|ja)$'
        if (-not $Accepted) {
            Write-Host 'Deze clip wordt opnieuw opgenomen en veilig overschreven.' -ForegroundColor Yellow
        }
    }
}

Write-Host ''
Write-Host 'Alle DJI Mic Mini-opnamen zijn voltooid.' -ForegroundColor Green
Write-Host "Manifest: references\private\$Session\manifest.json"
Write-Host "Audio: recordings\$Session"
