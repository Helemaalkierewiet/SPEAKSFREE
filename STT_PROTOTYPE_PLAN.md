# Agentbriefing: lokaal Nederlands STT-benchmarkprototype

## 1. Opdracht in één zin

Bouw op deze Windows-laptop een losstaand, reproduceerbaar prototype dat dezelfde
Nederlandse microfoonopnamen vergelijkt met **Vosk Small**, **Vosk LGraph** en
**Whisper Base Q5**, zodat we kunnen bepalen welk model de beste verhouding biedt
tussen transcriptiekwaliteit en benodigde rekenkracht — ook met het oog op vier
gelijktijdige, afzonderlijke microfoonkanalen.

## 2. Waarom dit prototype nodig is

De uiteindelijke toepassing moet gesprekken leesbaar maken voor oma. De eerdere
mobiele proef probeerde zowel spraak te herkennen als sprekers op basis van één
microfoon te onderscheiden. Dat bleek op de telefoon te traag en te onzeker:
woorden werden gemist, transcripties liepen achter en twee echte sprekers werden
soms als vier sprekers gezien.

De nieuwe productrichting is eenvoudiger en betrouwbaarder: iedere deelnemer krijgt
later een eigen zender/microfoon en ieder audiokanaal staat daardoor al voor een
bekende spreker en kleur. Diarization of stemclustering is dan niet nodig. Het nog
openstaande technische risico is de spraakherkenning zelf: welk lokaal Nederlands
model is nauwkeurig genoeg en kan uiteindelijk vier audiostreams tegelijk verwerken?

Dit benchmarkprototype beantwoordt eerst die vraag op de beschikbare laptop. Het is
geen nieuwe versie van de telefoonapp.

> Met “vertaling” wordt in deze opdracht **Nederlandse spraak naar Nederlandse
> tekst** bedoeld. Er mag niet naar Engels worden vertaald. Stel Whisper daarom
> expliciet in op `language=nl` en `translate=false`.

## 3. Onderzoeksvragen

Het prototype moet met meetgegevens antwoord geven op de volgende vragen:

1. Welk model maakt op onze eigen Nederlandse testspraak de minste fouten?
2. Welk model mist de minste volledige woorden of zinsdelen?
3. Hoe snel verschijnt een bruikbaar eindresultaat ten opzichte van de audiolengte?
4. Hoeveel CPU en werkgeheugen vraagt elk model bij één stream?
5. Kan deze laptop vier onafhankelijke herkenners tegelijk op realtime-tempo draaien?
6. Welk model is op basis van kwaliteit, snelheid, geheugen en licentie de beste
   kandidaat voor een prototype met vier afzonderlijke microfoonkanalen?

De winnaar staat vooraf **niet** vast. Modelgrootte en gepubliceerde foutpercentages
zijn alleen achtergrondinformatie; de beslissing volgt uit dezelfde lokale testset
en dezelfde meetmethode.

## 4. Afbakening

### Wel binnen scope

- Windows-laptop als enige uitvoerapparaat;
- ingebouwde laptopmicrofoon als enige opnamebron;
- Nederlandse spraak naar Nederlandse tekst;
- volledig lokale verwerking nadat de modellen zijn gedownload;
- drie herkenningsroutes:
  - `vosk-model-small-nl-0.22`;
  - `vosk-model-nl-spraakherkenning-0.6-lgraph`;
  - `ggml-base-q5_1.bin` via `whisper.cpp`;
- een eerlijke één-streamtest;
- een vier-stream-belastingstest door vier vooraf opgenomen audiobestanden tegelijk
  te verwerken;
- ruwe en samengevatte meetresultaten opslaan in JSON/CSV en Markdown.

### Niet binnen scope

- de Android- of React Native-app aanpassen;
- telefoon- of browserondersteuning;
- DJI-ontvangers of echte vierkanaals-audio aansluiten;
- sprekers herkennen of clusteren;
- kleuren aan stemmen toewijzen;
- cloudtranscriptie;
- audio naar een externe dienst uploaden;
- Vosk-woordenschat of prompts per testzin optimaliseren;
- een definitieve productinterface bouwen.

De vier-streamtest bewijst alleen of vier herkenningsprocessen qua rekenkracht
haalbaar lijken. Hij bewijst nog niet dat een toekomstige audio-interface vier
kanalen correct kan opnemen. Dat wordt een aparte hardwaretest zodra de ontvanger
en vier zenders beschikbaar zijn.

## 5. Te vergelijken modellen

| Route | Exact model | Indicatieve download | Verwachting die moet worden getoetst | Belangrijke beperking |
| --- | --- | ---: | --- | --- |
| Vosk Small | `vosk-model-small-nl-0.22` | 39 MB | Zeer licht en geschikt voor streaming, maar mogelijk meer woordfouten | Apache-2.0 |
| Vosk LGraph | `vosk-model-nl-spraakherkenning-0.6-lgraph` | 100 MB | Groter Nederlands taalmodel en dynamische graph; kwaliteit kan per soort spraak verschillen | `CC-BY-NC-SA`; niet zonder meer geschikt voor een commercieel product |
| Whisper Base Q5 | `ggml-base-q5_1.bin` | circa 57 MiB | Waarschijnlijk robuuster voor vrije Nederlandse spraak en interpunctie, maar zwaarder en meer blokgericht | Gebruik het meertalige `base`-model, dus **niet** `base.en` |

De WER-cijfers op de Vosk-modelpagina zijn tussen datasets zichtbaar verschillend.
Ook is LGraph daar niet op iedere dataset beter dan Small. Trek daarom geen conclusie
uit de upstream-cijfers; meet alle drie op exact dezelfde eigen audio.

### Bronnen die de agent moet vastzetten

- Vosk-modeloverzicht en licenties:
  <https://alphacephei.com/vosk/models>
- Vosk API:
  <https://github.com/alphacep/vosk-api>
- `whisper.cpp`:
  <https://github.com/ggml-org/whisper.cpp>
- Officieel geconverteerd `ggml-base-q5_1.bin`:
  <https://huggingface.co/ggerganov/whisper.cpp/blob/f281eb45af861ab5e5297d23694b7d46e090c02c/ggml-base-q5_1.bin>

Leg na iedere download de uiteindelijke URL, upstream-versie/commit, bestandsgrootte
en lokaal berekende SHA-256 vast in een manifest. Vertrouw niet alleen op een
veranderlijke `latest`-link.

## 6. Belangrijkste principe: eerst één vaste testset opnemen

Laat de drie modellen **niet** ieder een eigen live microfoonmoment horen. Uitspraak,
afstand en achtergrondgeluid zouden dan verschillen en de vergelijking ongeldig
maken.

De correcte werkwijze is:

1. neem de Nederlandse testset één keer op met de laptopmicrofoon;
2. bewaar ieder fragment als 16-kHz, mono, 16-bit PCM-WAV;
3. schrijf per fragment handmatig de werkelijk uitgesproken tekst uit;
4. voer vervolgens exact dezelfde WAV-bestanden door alle drie modellen;
5. herhaal iedere gemeten run minimaal drie keer na één ongemeten warm-up;
6. voer daarna dezelfde corpusbestanden in vier parallelle workers uit.

Zo scheiden we transcriptiekwaliteit van toevallige verschillen in microfoonopname.

## 7. Testset

Maak een kleine maar gevarieerde testset van ongeveer 15 tot 25 minuten. Gebruik
meerdere losse WAV-bestanden, zodat fouten per categorie zichtbaar blijven.

### Verplichte categorieën

- korte antwoorden: “ja”, “nee”, “weet ik niet”, “een ogenblikje”;
- gewone gesprekken in huis;
- langere zinnen met bijzinnen;
- getallen, tijden, bedragen, datums en telefoonnummers;
- Nederlandse plaats- en persoonsnamen;
- woorden die bij zorg of een doktersgesprek voorkomen;
- zacht uitgesproken spraak en normale spreeksterkte;
- langzaam, normaal en relatief snel spreken;
- aarzelingen, herhalingen en zelfcorrecties;
- enkele opnamen met lichte achtergrondruis;
- minimaal 30 seconden echte stilte voor een hallucinatietest.

Neem bij voorkeur spraak van minstens twee volwassenen op, maar wel één persoon per
bestand. Vraag toestemming voordat iemands stem wordt opgenomen. Commit geen echte
privé-opnamen aan Git.

Voor ieder bestand komt een UTF-8-referentietekst met dezelfde basisnaam. Leg ook
metadata vast: sprekeralias, categorie, duur, microfoon, afstand en eventuele ruis.

### Normalisatie voor foutmeting

Bewaar zowel de ruwe modeltekst als een genormaliseerde variant. Gebruik voor WER en
CER één gezamenlijke normalisatieregel, bijvoorbeeld:

- alles in kleine letters;
- interpunctie verwijderen;
- herhaalde witruimte samenvoegen;
- getallen consequent naar woorden of consequent naar cijfers omzetten;
- geen model-specifieke woorden handmatig corrigeren.

Documenteer de exacte regels. Interpunctie en hoofdletters mogen daarnaast als
aparte gebruikskwaliteit worden beoordeeld, maar mogen de kern-WER niet oneerlijk
beïnvloeden.

## 8. Technische vorm

Maak het prototype los van `apps/mobile`, bijvoorbeeld in:

```text
prototypes/stt-benchmark/
├── README.md
├── requirements.txt
├── .gitignore
├── config/
│   └── models.json
├── models/                 # niet committen
├── recordings/             # privé-audio niet committen
├── references/             # referentietekst en niet-gevoelige metadata
├── results/                # JSON/CSV en gegenereerd rapport
├── scripts/
│   └── setup-whisper.ps1
└── src/
    ├── __init__.py
    ├── capture.py
    ├── audio.py
    ├── engines/
    │   ├── base.py
    │   ├── vosk_engine.py
    │   └── whisper_cpp_engine.py
    ├── benchmark.py
    ├── metrics.py
    ├── monitor.py
    └── report.py
```

Gebruik bij voorkeur Python 3.11 voor de benchmarkbesturing. Verwachte pakketten:

- `sounddevice` voor microfoonopname;
- `soundfile` en `numpy` voor WAV-verwerking;
- `vosk` voor beide Vosk-modellen;
- `psutil` voor CPU- en geheugengebruik;
- `jiwer` voor WER en CER;
- standaard `subprocess` om de vastgezette `whisper.cpp`-CLI aan te roepen.

Gebruik voor Whisper daadwerkelijk `whisper.cpp` met `ggml-base-q5_1.bin`. Vervang
dit niet stilzwijgend door OpenAI Whisper, faster-whisper of een ander model/runtime;
dan zou de belastingstest niet meer meten wat is gevraagd.

De adapters moeten één gemeenschappelijk resultaatformaat teruggeven, bijvoorbeeld:

```json
{
  "engine": "vosk-small",
  "audio_file": "normal_01.wav",
  "audio_seconds": 8.42,
  "transcript_raw": "...",
  "transcript_normalized": "...",
  "processing_seconds": 1.13,
  "realtime_factor": 0.134,
  "model_load_seconds": 0.81,
  "peak_rss_mb": 312.4,
  "cpu_average_percent": 146.0,
  "cpu_peak_percent": 287.0,
  "exit_status": "ok"
}
```

CPU-percentages boven 100% zijn toegestaan wanneer ze het verbruik over meerdere
cores weergeven. Noteer daarnaast het aantal fysieke en logische cores, zodat dit
juist kan worden geïnterpreteerd.

## 9. Twee afzonderlijke benchmarkmodi

### A. Gelijke kwaliteit- en throughputtest

Iedere engine verwerkt volledige, vooraf opgenomen bestanden. Dit is de primaire,
eerlijke vergelijking.

- zelfde audiobestanden;
- zelfde 16-kHz mono-invoer;
- Vosk zonder aangepaste grammar of woordenlijst;
- Whisper met Nederlands geforceerd en vertaling uit;
- model één keer opwarmen;
- drie meetruns uitvoeren;
- model-laadtijd zowel apart als inclusief koude start rapporteren.

### B. Bijna-live gebruikstest

Meet daarna hoe een transcript tijdens een echt gesprek beschikbaar komt. Houd deze
resultaten apart van benchmark A, omdat Vosk native streamingresultaten geeft en
Whisper in audiovensters werkt.

- Vosk: voer PCM in kleine vaste blokken toe en registreer eerste partial en final;
- Whisper: gebruik één vooraf gedocumenteerde vensterstrategie voor alle tests;
- registreer de tijd tot eerste leesbare tekst en de tijd tot definitieve tekst;
- voorkom dubbele woorden door overlap aantoonbaar te verwerken;
- toon duidelijk welke tekst voorlopig en welke definitief is.

Optimaliseer de vensterlengte pas nadat de baseline is gemeten. Een getunede tweede
ronde mag, maar overschrijf de baselineresultaten niet.

## 10. Vier gelijktijdige streams simuleren

Er is nu maar één microfoon. Simuleer vier toekomstige kanalen daarom met vier
vooraf opgenomen bestanden die gelijktijdig starten.

Gebruik vier afzonderlijke workerprocessen, zodat CPU- en geheugendruk op een
realistische manier ontstaan. Verwerk liefst vier verschillende bestanden van
vergelijkbare duur. Herhaal desnoods met vier kopieën van hetzelfde bestand voor een
volledig identieke belastingstest.

Meet bij concurrency `1`, `2` en `4`:

- totale doorlooptijd;
- real-time factor per stream;
- gemiddelde en p95-verwerkingstijd per fragment;
- totale gemiddelde en piek-CPU;
- totale piek-RSS van parent plus alle workers;
- mislukte of vastgelopen taken;
- groeiende achterstand wanneer audio sneller binnenkomt dan transcriptie klaar is.

Laad per worker een eigen modelcontext als de runtime dat vereist. Als een model
veilig tussen workers kan worden gedeeld, rapporteer beide varianten in plaats van
geheugengebruik mooier voor te stellen dan het in de uiteindelijke architectuur is.

Een stream houdt realtime bij als:

```text
RTF = verwerkingstijd / audiolengte
RTF < 1,0  => sneller dan realtime
RTF = 1,0  => precies realtime
RTF > 1,0  => de achterstand groeit
```

Voor vier streams is de harde ondergrens dat **iedere** stream bij langdurige
belasting een RTF kleiner dan 1,0 houdt. Streef daarnaast naar minimaal 15% vrije
CPU-capaciteit en voldoende vrij geheugen voor audio-opname en de gebruikersinterface.

## 11. Te meten kwaliteit

Rapporteer niet alleen één gemiddeld cijfer. Minimaal vereist:

- **WER (Word Error Rate):** vervangen, verwijderen en toevoegen van woorden;
- **CER (Character Error Rate):** nuttig bij Nederlandse samenstellingen en namen;
- **weggelaten-woordenpercentage:** extra belangrijk omdat eerder halve zinnen
  verdwenen;
- **kritieke-woordenrecall:** handmatig gemarkeerde namen, tijden, bedragen en
  zorgtermen;
- **hallucinaties in stilte:** aantal woorden dat wordt geproduceerd zonder spraak;
- **Engelse insluipsels:** Engelse woorden terwijl de bron volledig Nederlands is;
- **leesbaarheid:** interpunctie, zinsgrenzen en hoofdletters als aparte beoordeling.

Splits de resultaten uit per categorie en spreker. Een gemiddeld goede WER mag niet
verbergen dat korte antwoorden of medische termen systematisch verdwijnen.

## 12. Te meten belasting en latency

Leg per model en per concurrency vast:

- modelbestand op schijf;
- laadtijd bij koude en warme start;
- gemiddelde en piek-CPU;
- piekwerkgeheugen van het complete procescluster;
- verwerkingstijd en RTF;
- tijd tot eerste voorlopige tekst;
- tijd tot definitieve tekst;
- energieverbruik alleen als Windows dit betrouwbaar beschikbaar maakt;
- eventuele GPU-versnelling en gebruikte instructieset.

Noteer vóór de test automatisch:

- Windows-versie;
- CPU-model;
- fysieke en logische cores;
- totaal RAM;
- GPU en of die werkelijk door de engine wordt gebruikt;
- Python-, Vosk- en `whisper.cpp`-versies;
- energieprofiel en of de laptop aan netvoeding hangt.

Voer de hoofdvergelijking aan netvoeding uit, met hetzelfde energieprofiel en zonder
zware achtergrondtaken. Een CPU- en GPU-build van Whisper mogen als twee aparte
configuraties worden getest, maar mogen niet tot één resultaat worden samengevoegd.

## 13. Beslisregel

Gebruik eerst harde afkeurcriteria:

1. vier gelijktijdige streams halen niet allemaal `RTF < 1,0`;
2. relevante woorden of korte antwoorden verdwijnen onaanvaardbaar vaak;
3. het model hallucineert regelmatig tekst tijdens stilte;
4. het geheugengebruik laat geen veilige marge voor de rest van de applicatie;
5. de licentie past niet bij het beoogde gebruik.

Rangschik de overgebleven opties vervolgens met deze richtweging:

| Onderdeel | Gewicht |
| --- | ---: |
| Transcriptiekwaliteit, inclusief kritieke woorden | 50% |
| Vier-stream-throughput | 25% |
| Bijna-live latency | 15% |
| Geheugen, laadtijd en modelgrootte | 10% |

Laat naast de totaalscore altijd de ruwe cijfers zien. Een gewogen score is een
hulpmiddel en geen vervanging voor productbeoordeling.

De eindconclusie moet één van deze vormen aannemen:

- model X is op deze laptop geschikt voor vier streams;
- model X lijkt geschikt, maar moet nog met echte vierkanaals-hardware worden getest;
- geen model haalt kwaliteit én vier-stream-realtime; adviseer welke CPU/mini-pc-klasse
  of welke andere architectuur als volgende proef nodig is;
- Vosk LGraph wint technisch, maar valt af voor productgebruik totdat de licentie is
  opgelost.

## 14. Uit te voeren stappen voor de implementatieagent

1. Lees `APP_CONCEPT.md`, `MODEL_MANIFEST.md` en dit document voor context.
2. Inspecteer en noteer de hardware van de laptop.
3. Maak `prototypes/stt-benchmark` zonder `apps/mobile` te wijzigen.
4. Maak een reproduceerbare Python 3.11-omgeving en pin afhankelijkheden.
5. Implementeer een microfoonlijst en een opnamecontrole vóór de echte test.
6. Implementeer WAV-opname op 16 kHz mono PCM met zichtbare niveaumeter en clipping-
   waarschuwing.
7. Voeg download-/installatie-instructies en een modelmanifest toe. Download modellen
   niet bij iedere run opnieuw.
8. Implementeer de twee Vosk-adapters met exact dezelfde codepad en alleen een ander
   modelpad.
9. Bouw of installeer een vastgezette `whisper.cpp`-CLI en implementeer de Base-Q5-
   adapter.
10. Leg met een kleine rooktest vast dat alle drie routes Nederlands transcriberen.
11. Maak of neem de testset op en controleer de referentieteksten handmatig.
12. Draai de één-streambaseline, daarna concurrency 2 en 4.
13. Genereer tabellen, per-categorie-resultaten en een korte conclusie in
    `results/BENCHMARK_REPORT.md`.
14. Voer een schone installatietest uit vanaf de beschreven commando’s.
15. Pas pas na de baseline model-specifieke tuning toe en label die resultaten als
    aparte experimenten.

Beoogde bediening mag ongeveer zo zijn:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m src.capture --session baseline
python -m src.benchmark --concurrency 1 --repetitions 3
python -m src.benchmark --concurrency 2 --repetitions 3
python -m src.benchmark --concurrency 4 --repetitions 3
python -m src.report
```

De exacte commando’s mogen technisch anders zijn, maar de README moet een nieuwe
agent of ontwikkelaar zonder verborgen handelingen van installatie tot rapport
brengen.

## 15. Op te leveren bestanden

Minimaal vereist:

- werkende lokale CLI voor opnemen en benchmarken;
- gepinde dependency- en runtimeversies;
- modelmanifest met bron, licentie, grootte en hash;
- testsetmanifest en referentieteksten;
- ruwe resultaten per run in JSON of CSV;
- `results/BENCHMARK_REPORT.md` met:
  - laptopconfiguratie;
  - modelconfiguraties;
  - WER/CER en foutcategorieën;
  - CPU, RAM, laadtijd, latency en RTF;
  - resultaten bij 1, 2 en 4 streams;
  - beperkingen van de proef;
  - één gemotiveerd advies voor de volgende stap;
- tests voor normalisatie, WER-berekening en resultaataggregatie;
- `.gitignore` voor modellen, virtuele omgeving, privé-audio en tijdelijke output.

## 16. Definition of Done

De opdracht is pas klaar als:

- de drie exact genoemde modellen aantoonbaar draaien;
- alle drie exact dezelfde opgenomen audio hebben verwerkt;
- Nederlands expliciet is ingesteld en Whisper niet naar Engels vertaalt;
- minimaal één warm-up en drie meetruns per relevante configuratie zijn uitgevoerd;
- één-, twee- en vier-streamresultaten aanwezig zijn;
- kwaliteit, latency, CPU, RAM en RTF meetbaar en reproduceerbaar zijn;
- het rapport fouten per testcategorie toont, niet alleen één gemiddelde;
- de winnaar of het ontbreken van een winnaar met ruwe cijfers wordt onderbouwd;
- licentiebeperkingen duidelijk in de conclusie staan;
- de mobiele app niet is aangepast;
- geen privé-audio of gedownloade modellen in Git terecht zijn gekomen;
- een tweede ontwikkelaar het prototype via de README kan uitvoeren.

## 17. Bekende valkuilen

- **Geen eerlijke input:** ieder model apart live inspreken maakt de vergelijking
  waardeloos. Hergebruik dezelfde WAV-bestanden.
- **Whisper vertaalt naar Engels:** forceer `nl` en transcriptiemodus.
- **Verkeerd Whisper-model:** `base.en` ondersteunt alleen Engels; gebruik
  `ggml-base-q5_1.bin`.
- **Alleen modelgrootte vergelijken:** runtimegeheugen en vier parallelle contexten
  zijn belangrijker dan alleen de downloadgrootte.
- **Laadtijd mengen met inferentie:** rapporteer koude start en warme verwerking
  apart.
- **CPU-percentages verkeerd lezen:** leg de schaal over meerdere cores vast.
- **Streaminglatency en offline snelheid mengen:** rapporteer die als twee
  experimenten.
- **Vosk bevoordelen met een aangepaste woordenlijst:** de baseline gebruikt geen
  model-specifieke vocabulary tuning.
- **Laptopmicrofoon als eindbewijs zien:** een toekomstige hals-/clipmicrofoon kan
  een betere signaal-ruisverhouding geven; herhaal de winnaar later met echte
  hardware.
- **Vier kopieën verwarren met vier audiokanalen:** deze proef meet compute, niet de
  betrouwbaarheid van een USB-ontvanger of audiostuurprogramma.
- **Licentie vergeten:** LGraph is `CC-BY-NC-SA` en mag niet automatisch als
  commerciële productkeuze worden behandeld.

## 18. Verwachte maar nog onbewezen hypothese

Vosk Small zal waarschijnlijk het lichtst en het snelst zijn. Vosk LGraph kan op
sommige Nederlandse spraak beter zijn, maar dat is niet gegarandeerd en de licentie
is beperkter. Whisper Base Q5 zal mogelijk natuurlijkere vrije spraak en
interpunctie leveren, maar kan meer rekentijd en bloklatency vragen. Deze uitspraken
zijn uitsluitend hypotheses; het doel van dit prototype is ze met lokale metingen te
bevestigen of te verwerpen.

