# Lokaal Nederlands STT-benchmarkprototype

Dit prototype neemt één vaste Nederlandse testset op en vergelijkt die lokaal met
acht routes: Vosk Small, LGraph en Full NL; Whisper Base Q5, Small Q5 en Large v3
Turbo Q5; NVIDIA Dutch FastConformer; en NVIDIA Parakeet TDT 0.6B v3 INT8.
De Whisper-routes gebruiken Silero VAD 6.2. De NVIDIA-modellen draaien via ONNX
Runtime op de CPU, zodat dezelfde 1/2/4-streamtest mogelijk blijft.

## Live DJI Mic 3-prototype

### Eerst: vier kanalen afzonderlijk controleren

Start de losse browsermeter zonder transcriptie:

```powershell
.\scripts\run-dji-channel-meter.ps1
```

Open `http://127.0.0.1:8766` en klik op **Start meting**. Een kleine lokale helper
opent **Wireless Mic Rx** via RAW WASAPI, vóór de Windows- en browser-
audioverbeteringen. De pagina toont alleen RMS-volume, piek en kanaalovereenkomst.
Audio wordt niet opgenomen, opgeslagen of verstuurd. Deze meter is de geïsoleerde
basis voor de latere transcriptieroute.

Verbind de DJI Mic 3-ontvanger via USB. De app ondersteunt **S (Stereo)** met twee
USB-kanalen en **Q (Quadraphonic)** met vier USB-kanalen. Gebruik bij een Windows-
endpoint dat Stereo als dubbel mono aanbiedt de Q-modus; TX1 en TX2 worden dan uit
de eerste twee afzonderlijke USB-kanalen verwerkt. Klik na iedere moduswijziging op
**Microfoon opnieuw verbinden**. Start vervolgens:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\run-dji-live.ps1
```

Het lokale gespreksscherm opent op `http://127.0.0.1:8765`. Whisper Small Q5
wordt met `language=nl` en zonder vertaalmodus gestart; daardoor kan de automatische
taaldetectie niet onbedoeld naar Engels omschakelen. De invoer gebruikt dezelfde
native RAW WASAPI-route als de vierkanaalsmeter, zodat Windows TX1 en TX2 niet meer
naar dubbel mono samenvoegt. Korte spraakfragmenten van beide kanalen gaan via één
inferencewachtrij. De audio wordt alleen tijdelijk in
`results/tmp/live` geplaatst en direct na transcriptie verwijderd. Namen, kleuren,
microfoonniveaus, stilteduur, start/pauze en een mono/stereo-waarschuwing staan in
de interface.

Bij het starten meet ieder zenderkanaal eerst drie seconden zelfstandig de
kamerruis. Blijf in die periode stil. De adaptieve spraakgrens wordt daarna per
zender op 12 dB boven die ruis gezet. Spraak moet 120 ms
boven de grens blijven voordat transcriptie start. Een lagere stopgrens voorkomt
flapperen en na standaard 450 ms stilte wordt het fragment verwerkt. De app
behoudt 250 ms audio van vóór de start, zodat de eerste klank niet wordt
afgekapt. Via **Instellingen → Opnieuw kalibreren** kan de meting opnieuw worden
uitgevoerd wanneer de kamer of microfoonpositie verandert.

Daarnaast heeft het instellingenscherm een vaste **minimale spraaksterkte** in
dBFS. Een fragment wordt alleen gestart wanneer het zowel boven de automatisch
gemeten ruisgrens als boven deze vaste grens komt. De standaardwaarde is
`-35 dBFS`; richting `-20 dBFS` is strenger. Bekende copyrightregels die Whisper
uit bijna-stilte kan verzinnen, zoals `(C) TV GELDERLAND 2021`, worden niet meer
in het gesprek getoond.

Het wijzigt geen mobiele app en uploadt geen audio. Whisper staat in de configuratie
en adapter hard op Nederlands (`-l nl`), en de vertaaloptie `-tr` wordt nooit
meegegeven. Vier toekomstige microfoonkanalen worden gesimuleerd met afzonderlijke
workerprocessen en dus met een eigen modelcontext per worker.

## Wat er al staat

- microfoonlijst, toestemmingscontrole, niveaumeter en clippingwaarschuwing;
- opname als 16-kHz mono 16-bit PCM-WAV;
- één gedeelde Vosk-codepad voor Small en LGraph;
- `whisper.cpp` Base Q5-adapter met Nederlands/transcriptiemodus;
- ongewijzigde offline benchmarkinput, warm-up en drie meetruns;
- concurrency 1, 2 en 4 met clusterbrede CPU/RSS-meting;
- aparte bijna-live baseline: Vosk in 200-ms-blokken, Whisper in niet-overlappende
  vensters van 5 seconden;
- WER, CER, weglatingen, kritieke-woordenrecall, stiltehallucinaties, Engelse
  insluipsels en eenvoudige leesbaarheidsvelden;
- JSON en CSV per run plus een gegenereerd Markdownrapport;
- unit-tests voor audioformaat, normalisatie, foutmeting en aggregatie.

## Alles met één script uitvoeren

Vanuit deze map voert dit commando installatie, modelcontrole, de offline
1/2/4-streammatrix, de bijna-live test en het rapport uit:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\run-all-benchmarks.ps1
```

Een korte technische controle zonder de lange bijna-live test:

```powershell
.\scripts\run-all-benchmarks.ps1 -Quick
```

Na een succesvolle installatie kun je downloads overslaan met `-SkipSetup`. Met
`-SkipNearLive` voer je wel alle kwaliteit- en vier-streamtests uit, maar niet de
realtime afgespeelde latencytest.

## 1. Python 3.11 installeren

Gebruik 64-bit Python 3.11. Controleer daarna:

```powershell
py -3.11 --version
```

Maak vanuit deze map de geïsoleerde omgeving:

```powershell
py -3.11 -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Alle Python-afhankelijkheden zijn exact vastgezet in `requirements.txt`. De
benchmark meldt een waarschuwing als een andere Python-minorversie actief is.

## 2. Exacte modellen en runtime eenmalig ophalen

```powershell
.\scripts\setup-models.ps1
python -m src.verify --hashes
```

Het script hergebruikt bestaande downloads en schrijft na afloop
`models/manifest.local.json` met uiteindelijke bron-URL, upstreamversie/commit,
bestandsgrootte, lokale locatie en zelf berekende SHA-256. Dit lokale manifest,
de downloads en uitgepakte modellen worden niet gecommit.

Vastgezette bronnen:

- Vosk Small en LGraph: het officiële [Vosk-modeloverzicht](https://alphacephei.com/vosk/models);
- Vosk API 0.3.45: [officiële Vosk-repository](https://github.com/alphacep/vosk-api);
- `whisper.cpp` runtime `b5454`, commit `d1be6fd`: [officiële releases](https://github.com/ggml-org/whisper.cpp/releases);
- meertalig `ggml-base-q5_1.bin`: de in het plan vastgezette [Hugging Face-commit](https://huggingface.co/ggerganov/whisper.cpp/blob/f281eb45af861ab5e5297d23694b7d46e090c02c/ggml-base-q5_1.bin).

LGraph is `CC-BY-NC-SA` en mag niet automatisch als commerciële productkeuze
worden behandeld. Het rapport past die licentiebeperking toe na de technische
vergelijking.

## 3. Microfoon controleren en testset opnemen

```powershell
python -m src.capture --list-devices
python -m src.capture --session baseline --name short_yes_01 --duration 5 `
  --speaker adult-a --category short-answer --critical-word ja --consent
```

Zonder `--consent` start geen opname. Zonder `--reference` vraagt de CLI na de
opname om de letterlijk uitgesproken tekst. Privé-audio en referenties komen in
genegeerde mappen:

```text
recordings/baseline/*.wav
references/private/baseline/*.txt
references/private/baseline/manifest.json
```

Volg [references/TESTSET.md](references/TESTSET.md) voor de categorieën, stilteclip,
kritieke woorden, twee sprekers en de gewenste 15–25 minuten. Luister alle clips
na en corrigeer de handmatige referenties vóór de benchmark. Gebruik per bestand
één spreker.

## 4. Rooktest

Deze stap laat alle routes exact dezelfde eerste WAV verwerken:

```powershell
python -m src.smoke --manifest references/private/baseline/manifest.json
```

Een lege stilteclip is geen geschikte rooktest; kies desnoods expliciet een
spraakclip met `--clip care_01`.

## 5. Eerlijke offline benchmark

Voer de hoofdmeting aan netvoeding uit met hetzelfde energieprofiel en zonder zware
achtergrondtaken:

```powershell
python -m src.benchmark --manifest references/private/baseline/manifest.json --concurrency 1 --repetitions 3
python -m src.benchmark --manifest references/private/baseline/manifest.json --concurrency 2 --repetitions 3
python -m src.benchmark --manifest references/private/baseline/manifest.json --concurrency 4 --repetitions 3
```

Iedere worker laadt een eigen model en voert eerst één ongemeten warm-up uit. Bij
Whisper wordt het aantal threads per worker automatisch begrensd tot ongeveer het
aantal logische cores gedeeld door de concurrency. De gemeten transcripties
bevatten koude model-laadtijd waar de runtime die rapporteert; Vosk-laadtijd wordt
apart rond de modelconstructie gemeten.

## 6. Aparte bijna-live baseline

```powershell
python -m src.benchmark --manifest references/private/baseline/manifest.json `
  --mode near-live --concurrency 1 --repetitions 3
```

Deze cijfers blijven gescheiden van offline throughput. Vosk registreert de eerste
gewijzigde partial en de uiteindelijke tekst. Whisper wacht per venster op vijf
seconden audio, transcribeert het venster en publiceert dat als definitief. De
vensters overlappen niet, zodat de baseline geen dubbele overlapwoorden kan maken.
Een later getunede vensterstrategie hoort in nieuwe resultaten en mag deze baseline
niet overschrijven.

## 7. Rapport genereren

```powershell
python -m src.report
```

Het rapport gebruikt per opnamesessie en per engine/mode/concurrency de nieuwste
run. Kies een sessie om te voorkomen dat laptop- en DJI-opnamen worden gemengd:

```powershell
python -m src.report --session dji_mini_baseline `
  --output results/ALL_MODELS_DJI_MINI_BASELINE_REPORT.md
```

Het schrijft:

- `results/BENCHMARK_REPORT.md`;
- `results/benchmark-results.csv`;
- ongewijzigde JSON/CSV per run in `results/raw/`.

De beslissing past eerst harde grenzen uit `config/benchmark.json` toe. Alleen
daarna wordt de richtweging 50% kwaliteit, 25% vier-streamdoorvoer, 15% bijna-live
latency en 10% resources gebruikt. Ruwe cijfers blijven altijd zichtbaar.

## Tests en schone installatiecontrole

De kern-tests hebben geen modeldownload of microfoon nodig:

```powershell
python -m unittest discover -s tests -v
python -m src.system_info
python -m src.verify --hashes
```

Voor een schone controle verwijder je alleen de lokale `.venv`, maak je die opnieuw
met de commando’s uit stap 1 en voer je tests, `src.verify` en `src.smoke` opnieuw
uit. Modellen hoeven niet opnieuw te worden gedownload.

## Meetdefinities en aandachtspunten

- `RTF = verwerkingstijd / audiolengte`; elke langdurige stream moet `< 1,0` zijn.
- CPU kan boven 100% uitkomen omdat het verbruik over alle logische cores wordt
  opgeteld; fysieke en logische core-aantallen staan in elk resultaat.
- Getallen worden voor WER/CER naar Nederlandse woorden genormaliseerd;
  interpunctie en hoofdletters tellen niet mee in de kern-WER.
- CPU/RSS van Whisper omvat het gestarte `whisper-cli`-proces; clusterwaarden bij
  concurrency omvatten parent en alle workers/afstammelingen.
- De vier-workerproef test compute, niet de opnamebetrouwbaarheid van een echte
  vierkanaals ontvanger.
- Energieverbruik wordt niet verzonnen wanneer Windows geen betrouwbare meting
  biedt; netvoeding en het actieve energieprofiel worden waar mogelijk vastgelegd.

