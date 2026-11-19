# Nederlands STT-benchmarkrapport

## Laptopconfiguratie

- OS: Windows 10 (AMD64)
- CPU: AMD Ryzen 9 7940HX with Radeon Graphics; 16 fysiek / 32 logisch
- RAM: 31.21 GB
- GPU: NVIDIA GeForce RTX 4060 Laptop GPU; AMD Radeon(TM) 610M; standaard CPU-build gebruikt
- Voeding/energieprofiel: {'plugged_in': True, 'percent': 100} / 27fa6203-3987-4dcc-918d-748559d549ec  (Performance)
- Python: 3.11.9 (tags/v3.11.9:de54cf5, Apr  2 2024, 10:12:12) [MSC v.1938 64 bit (AMD64)]
- Pakketten: numpy=2.3.5, sounddevice=0.5.6, soundfile=0.14.0, vosk=0.3.45, psutil=7.2.2, jiwer=4.0.0
- whisper.cpp: whisper.cpp version: 1.9.5

## Modelconfiguraties

| Engine | Exact model | Licentie | Commercieel | Lokaal formaat |
| --- | --- | --- | --- | ---: |
| vosk-small | vosk-model-small-nl-0.22 | Apache-2.0 | ja | 65.6 MB |
| vosk-lgraph | vosk-model-nl-spraakherkenning-0.6-lgraph | CC-BY-NC-SA | nee | 182.3 MB |
| whisper-base-q5 | ggml-base-q5_1.bin | MIT | ja | 56.9 MB |

## Kwaliteit en één-streamdoorvoer

| Engine | WER | CER | Weggelaten | Kritieke recall | Stiltewoorden | Engelse insluipsels | Laadtijd gem. | RTF gem. |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| vosk-small | 22.8% | 13.2% | 8.8% | 79.0% | 0 | 0 | 0.27 s | 0.200 |
| vosk-lgraph | 25.2% | 13.5% | 5.9% | 85.2% | 3 | 0 | 0.30 s | 0.193 |
| whisper-base-q5 | 34.2% | 14.5% | 2.0% | 66.7% | 3 | 0 | 0.06 s | 0.047 |

### Leesbaarheid buiten WER/CER

| Engine | Clips met beginhoofdletter | Clips met zinsinterpunctie | Zinsgrenzen per spraakclip |
| --- | ---: | ---: | ---: |
| vosk-small | 0.0% | 0.0% | 0.00 |
| vosk-lgraph | 0.0% | 0.0% | 0.00 |
| whisper-base-q5 | 100.0% | 100.0% | 2.38 |

## Belasting bij 1, 2 en 4 streams

| Engine | Streams | Totale tijd | Proc. gem. | Proc. p95 | RTF gem. | RTF max | Realtime | Cluster CPU gem. | Cluster CPU piek | Cluster RSS piek | Mislukt |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| vosk-small | 1 | 72.80 s | 2.49 s | 4.17 s | 0.200 | 0.313 | ja | 132.5% | 225.3% | 286.9 MB | 0 |
| vosk-small | 2 | 45.09 s | 3.01 s | 5.19 s | 0.242 | 0.384 | ja | 244.6% | 401.1% | 514.1 MB | 0 |
| vosk-small | 4 | 24.15 s | 2.91 s | 4.89 s | 0.236 | 0.368 | ja | 438.6% | 694.7% | 884.2 MB | 0 |
| vosk-lgraph | 1 | 77.70 s | 2.37 s | 4.17 s | 0.193 | 0.300 | ja | 130.8% | 219.2% | 463.2 MB | 0 |
| vosk-lgraph | 2 | 47.36 s | 2.80 s | 4.87 s | 0.229 | 0.355 | ja | 239.1% | 466.8% | 841.0 MB | 0 |
| vosk-lgraph | 4 | 26.80 s | 2.79 s | 4.72 s | 0.232 | 0.356 | ja | 425.1% | 1138.3% | 1529.5 MB | 0 |
| whisper-base-q5 | 1 | 15.75 s | 0.55 s | 0.81 s | 0.047 | 0.086 | ja | 2051.8% | 3882.4% | 280.7 MB | 0 |
| whisper-base-q5 | 2 | 11.03 s | 0.73 s | 1.06 s | 0.064 | 0.123 | ja | 1972.8% | 3631.1% | 519.5 MB | 0 |
| whisper-base-q5 | 4 | 11.47 s | 1.44 s | 2.21 s | 0.128 | 0.272 | ja | 2085.0% | 3982.8% | 982.9 MB | 0 |

## Bijna-live latency

Vosk gebruikt 200-ms PCM-blokken. Whisper gebruikt de ongetunede baseline van niet-overlappende vensters van vijf seconden; daardoor kunnen geen dubbele overlapwoorden ontstaan.

| Engine | Eerste leesbare tekst gem. | Definitieve tekst gem. |
| --- | ---: | ---: |
| vosk-small | 2.54 s | 17.44 s |
| vosk-lgraph | 2.56 s | 17.44 s |
| whisper-base-q5 | 5.47 s | 16.36 s |

## Resultaten per categorie

### vosk-small

| Categorie | WER | CER | Weggelaten | Kritieke recall |
| --- | ---: | ---: | ---: | ---: |
| care-medical | 45.5% | 19.1% | 0.0% | 50.0% |
| hesitation-correction | 0.0% | 0.0% | 0.0% | 100.0% |
| household-conversation | 22.9% | 15.5% | 14.6% | 100.0% |
| light-noise | 10.5% | 5.6% | 1.8% | 100.0% |
| names-places | 14.0% | 9.5% | 5.3% | 86.7% |
| numbers | 6.7% | 3.4% | 0.0% | 80.0% |
| short-answer | 80.0% | 85.7% | 80.0% | 100.0% |
| silence | — | — | — | — |
| soft-fast-speech | 36.4% | 20.5% | 9.1% | 66.7% |

### vosk-lgraph

| Categorie | WER | CER | Weggelaten | Kritieke recall |
| --- | ---: | ---: | ---: | ---: |
| care-medical | 33.3% | 10.5% | 0.0% | 66.7% |
| hesitation-correction | 0.0% | 0.0% | 0.0% | 100.0% |
| household-conversation | 13.9% | 7.9% | 7.6% | 100.0% |
| light-noise | 33.3% | 17.9% | 0.0% | 100.0% |
| names-places | 22.8% | 13.3% | 5.3% | 80.0% |
| numbers | 20.0% | 13.6% | 0.0% | 100.0% |
| short-answer | 46.7% | 45.2% | 33.3% | 100.0% |
| silence | — | — | — | — |
| soft-fast-speech | 66.7% | 33.3% | 24.2% | 66.7% |

### whisper-base-q5

| Categorie | WER | CER | Weggelaten | Kritieke recall |
| --- | ---: | ---: | ---: | ---: |
| care-medical | 45.5% | 18.4% | 0.0% | 16.7% |
| hesitation-correction | 15.4% | 8.3% | 0.0% | 100.0% |
| household-conversation | 31.2% | 16.7% | 4.2% | 33.3% |
| light-noise | 42.1% | 10.5% | 5.3% | 0.0% |
| names-places | 21.1% | 8.2% | 0.0% | 100.0% |
| numbers | 20.0% | 6.8% | 0.0% | 100.0% |
| short-answer | 20.0% | 21.4% | 0.0% | 100.0% |
| silence | — | — | — | — |
| soft-fast-speech | 72.7% | 19.2% | 0.0% | 66.7% |

## Resultaten per spreker

### vosk-small

| Sprekeralias | WER | CER | Weggelaten | Kritieke recall |
| --- | ---: | ---: | ---: | ---: |
| adult-a | 22.8% | 13.2% | 8.8% | 79.0% |

### vosk-lgraph

| Sprekeralias | WER | CER | Weggelaten | Kritieke recall |
| --- | ---: | ---: | ---: | ---: |
| adult-a | 25.2% | 13.5% | 5.9% | 85.2% |

### whisper-base-q5

| Sprekeralias | WER | CER | Weggelaten | Kritieke recall |
| --- | ---: | ---: | ---: | ---: |
| adult-a | 34.2% | 14.5% | 2.0% | 66.7% |

## Beslissing

- **vosk-small: afgekeurd** — score 69.6/100; kritieke-woordenrecall 79.0% is te laag.
- **vosk-lgraph: afgekeurd; niet geschikt voor commercieel productgebruik** — score 70.0/100; 3 woorden gehallucineerd in stilte.
- **whisper-base-q5: afgekeurd** — score 65.6/100; kritieke-woordenrecall 66.7% is te laag, 3 woorden gehallucineerd in stilte.

**Geen model haalt op deze laptop tegelijk de ingestelde kwaliteitsgrenzen en vier-stream-realtime.** Onderzoek een snellere CPU/mini-pc of een andere architectuur.

## Beperkingen

- De vier-streamtest meet rekenkracht met vier workerprocessen, niet de betrouwbaarheid van een toekomstige USB-audio-interface.
- De meting geldt alleen voor deze laptop, energie-instelling, testset en modelversies.
- De Engelse-insluipselmeting gebruikt een kleine lijst ondubbelzinnige Engelse woorden en blijft een heuristiek.
- Leesbaarheid (interpunctie en hoofdletters) is vastgelegd in de ruwe records maar telt niet mee voor WER/CER.
- Vosk LGraph heeft een CC-BY-NC-SA-licentie en wordt niet als commerciële productkeuze aanbevolen zonder licentieoplossing.

## Ruwe gegevens

- `20261104T163942+0100_vosk-lgraph_near-live_c1.json` (vosk-lgraph, near-live, concurrency 1)
- `20261104T162706+0100_vosk-lgraph_offline_c1.json` (vosk-lgraph, offline, concurrency 1)
- `20261104T162931+0100_vosk-lgraph_offline_c2.json` (vosk-lgraph, offline, concurrency 2)
- `20261104T163101+0100_vosk-lgraph_offline_c4.json` (vosk-lgraph, offline, concurrency 4)
- `20261104T163144+0100_vosk-small_near-live_c1.json` (vosk-small, near-live, concurrency 1)
- `20261104T162551+0100_vosk-small_offline_c1.json` (vosk-small, offline, concurrency 1)
- `20261104T162844+0100_vosk-small_offline_c2.json` (vosk-small, offline, concurrency 2)
- `20261104T163035+0100_vosk-small_offline_c4.json` (vosk-small, offline, concurrency 4)
- `20261104T164748+0100_whisper-base-q5_near-live_c1.json` (whisper-base-q5, near-live, concurrency 1)
- `20261104T162825+0100_whisper-base-q5_offline_c1.json` (whisper-base-q5, offline, concurrency 1)
- `20261104T163020+0100_whisper-base-q5_offline_c2.json` (whisper-base-q5, offline, concurrency 2)
- `20261104T163129+0100_whisper-base-q5_offline_c4.json` (whisper-base-q5, offline, concurrency 4)
