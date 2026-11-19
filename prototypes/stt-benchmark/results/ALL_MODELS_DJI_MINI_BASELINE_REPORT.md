# Nederlands STT-benchmarkrapport

Testset: `dji_mini_baseline`

## Laptopconfiguratie

- OS: Windows 10 (AMD64)
- CPU: AMD Ryzen 9 7940HX with Radeon Graphics; 16 fysiek / 32 logisch
- RAM: 31.21 GB
- GPU: NVIDIA GeForce RTX 4060 Laptop GPU; AMD Radeon(TM) 610M; standaard CPU-build gebruikt
- Voeding/energieprofiel: {'plugged_in': True, 'percent': 100} / 27fa6203-3987-4dcc-918d-748559d549ec  (Performance)
- Python: 3.11.9 (tags/v3.11.9:de54cf5, Apr  2 2024, 10:12:12) [MSC v.1938 64 bit (AMD64)]
- Pakketten: numpy=2.3.5, sounddevice=0.5.6, soundfile=0.14.0, vosk=0.3.45, onnx-asr=0.12.0, onnxruntime=1.31.1, psutil=7.2.2, jiwer=4.0.0
- whisper.cpp: whisper.cpp version: 1.9.5

## Modelconfiguraties

| Engine | Exact model | Licentie | Commercieel | Lokaal formaat |
| --- | --- | --- | --- | ---: |
| vosk-small | vosk-model-small-nl-0.22 | Apache-2.0 | ja | 65.6 MB |
| vosk-lgraph | vosk-model-nl-spraakherkenning-0.6-lgraph | CC-BY-NC-SA | nee | 182.3 MB |
| vosk-full | vosk-model-nl-spraakherkenning-0.6 | CC-BY-NC-SA | nee | 1636.7 MB |
| whisper-base-q5 | ggml-base-q5_1.bin | MIT | ja | 56.9 MB |
| whisper-small-q5 | ggml-small-q5_1.bin | MIT | ja | 181.3 MB |
| whisper-large-v3-turbo-q5 | ggml-large-v3-turbo-q5_0.bin | MIT | ja | 547.4 MB |
| nvidia-fastconformer-nl | OpenVoiceOS/stt_nl_fastconformer_hybrid_large_pc_onnx | CC-BY-4.0 | ja | 436.9 MB |
| nvidia-parakeet-tdt-v3-int8 | nemo-parakeet-tdt-0.6b-v3/int8 | CC-BY-4.0 | ja | 639.4 MB |

## Kwaliteit en één-streamdoorvoer

| Engine | WER | CER | Weggelaten | Kritieke recall | Stiltewoorden | Engelse insluipsels | Laadtijd gem. | RTF gem. |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| vosk-small | 22.8% | 13.2% | 8.8% | 79.0% | 0 | 0 | 0.22 s | 0.200 |
| vosk-lgraph | 25.2% | 13.5% | 5.9% | 85.2% | 3 | 0 | 0.31 s | 0.200 |
| vosk-full | 19.5% | 10.7% | 4.6% | 85.2% | 3 | 0 | 1.71 s | 0.064 |
| whisper-base-q5 | 30.3% | 15.0% | 2.6% | 70.4% | 0 | 0 | 0.06 s | 0.050 |
| whisper-small-q5 | 13.2% | 4.3% | 1.3% | 81.5% | 0 | 3 | 0.14 s | 0.120 |
| whisper-large-v3-turbo-q5 | 0.7% | 0.1% | 0.0% | 100.0% | 0 | 0 | 0.40 s | 0.428 |
| nvidia-fastconformer-nl | 36.8% | 22.0% | 10.5% | 66.7% | 3 | 0 | 1.80 s | 0.015 |
| nvidia-parakeet-tdt-v3-int8 | 17.1% | 6.5% | 0.7% | 74.1% | 0 | 3 | 2.48 s | 0.036 |

### Leesbaarheid buiten WER/CER

| Engine | Clips met beginhoofdletter | Clips met zinsinterpunctie | Zinsgrenzen per spraakclip |
| --- | ---: | ---: | ---: |
| vosk-small | 0.0% | 0.0% | 0.00 |
| vosk-lgraph | 0.0% | 0.0% | 0.00 |
| vosk-full | 0.0% | 0.0% | 0.00 |
| whisper-base-q5 | 100.0% | 100.0% | 2.62 |
| whisper-small-q5 | 100.0% | 100.0% | 3.00 |
| whisper-large-v3-turbo-q5 | 100.0% | 100.0% | 2.50 |
| nvidia-fastconformer-nl | 50.0% | 62.5% | 1.62 |
| nvidia-parakeet-tdt-v3-int8 | 100.0% | 100.0% | 2.00 |

## Belasting bij 1, 2 en 4 streams

| Engine | Streams | Totale tijd | Proc. gem. | Proc. p95 | RTF gem. | RTF max | Realtime | Cluster CPU gem. | Cluster CPU piek | Cluster RSS piek | Mislukt |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| vosk-small | 1 | 72.44 s | 2.48 s | 4.35 s | 0.200 | 0.313 | ja | 132.0% | 224.3% | 285.7 MB | 0 |
| vosk-small | 2 | 44.98 s | 2.98 s | 4.98 s | 0.241 | 0.389 | ja | 241.1% | 399.1% | 521.9 MB | 0 |
| vosk-small | 4 | 26.82 s | 3.27 s | 5.53 s | 0.264 | 0.420 | ja | 437.6% | 647.7% | 893.4 MB | 0 |
| vosk-lgraph | 1 | 80.59 s | 2.47 s | 4.28 s | 0.200 | 0.295 | ja | 129.5% | 202.5% | 462.6 MB | 0 |
| vosk-lgraph | 2 | 47.11 s | 2.77 s | 4.95 s | 0.226 | 0.338 | ja | 237.7% | 456.4% | 835.3 MB | 0 |
| vosk-lgraph | 4 | 30.61 s | 3.28 s | 5.51 s | 0.269 | 0.418 | ja | 427.7% | 677.3% | 1554.7 MB | 0 |
| vosk-full | 1 | 26.54 s | 0.87 s | 1.63 s | 0.064 | 0.108 | ja | 126.2% | 224.8% | 1860.1 MB | 0 |
| vosk-full | 2 | 17.81 s | 1.05 s | 2.08 s | 0.077 | 0.119 | ja | 226.8% | 420.2% | 3679.2 MB | 0 |
| vosk-full | 4 | 13.02 s | 1.21 s | 2.05 s | 0.092 | 0.143 | ja | 405.8% | 648.9% | 7260.7 MB | 0 |
| whisper-base-q5 | 1 | 16.17 s | 0.56 s | 0.90 s | 0.050 | 0.106 | ja | 2077.6% | 3879.4% | 284.3 MB | 0 |
| whisper-base-q5 | 2 | 10.83 s | 0.71 s | 1.11 s | 0.065 | 0.124 | ja | 1963.7% | 3762.1% | 532.7 MB | 0 |
| whisper-base-q5 | 4 | 9.44 s | 1.14 s | 1.89 s | 0.103 | 0.214 | ja | 2035.5% | 3724.1% | 963.5 MB | 0 |
| whisper-small-q5 | 1 | 36.67 s | 1.30 s | 1.86 s | 0.120 | 0.256 | ja | 2407.7% | 4325.1% | 550.3 MB | 0 |
| whisper-small-q5 | 2 | 36.12 s | 2.39 s | 3.94 s | 0.223 | 0.460 | ja | 2439.8% | 4180.3% | 1068.4 MB | 0 |
| whisper-small-q5 | 4 | 29.54 s | 3.65 s | 5.85 s | 0.339 | 0.759 | ja | 2547.3% | 3826.1% | 2070.8 MB | 0 |
| whisper-large-v3-turbo-q5 | 1 | 126.27 s | 4.48 s | 5.49 s | 0.428 | 0.962 | ja | 2683.8% | 4791.3% | 877.5 MB | 0 |
| whisper-large-v3-turbo-q5 | 2 | 138.05 s | 9.27 s | 12.95 s | 0.899 | 2.105 | nee | 2702.4% | 4982.0% | 1709.9 MB | 0 |
| whisper-large-v3-turbo-q5 | 4 | 124.17 s | 15.77 s | 18.51 s | 1.536 | 3.581 | nee | 2919.8% | 5195.9% | 3394.6 MB | 0 |
| nvidia-fastconformer-nl | 1 | 8.78 s | 0.21 s | 0.45 s | 0.015 | 0.021 | ja | 2208.6% | 4117.1% | 1034.9 MB | 0 |
| nvidia-fastconformer-nl | 2 | 8.06 s | 0.33 s | 0.69 s | 0.022 | 0.041 | ja | 1891.4% | 4229.7% | 2006.3 MB | 0 |
| nvidia-fastconformer-nl | 4 | 5.61 s | 0.35 s | 0.69 s | 0.024 | 0.033 | ja | 1679.8% | 4124.4% | 3492.6 MB | 0 |
| nvidia-parakeet-tdt-v3-int8 | 1 | 17.96 s | 0.51 s | 1.04 s | 0.036 | 0.062 | ja | 2487.5% | 4342.9% | 1310.5 MB | 0 |
| nvidia-parakeet-tdt-v3-int8 | 2 | 13.20 s | 0.66 s | 1.48 s | 0.045 | 0.062 | ja | 2282.0% | 4055.2% | 2507.4 MB | 0 |
| nvidia-parakeet-tdt-v3-int8 | 4 | 11.30 s | 0.90 s | 1.77 s | 0.063 | 0.076 | ja | 1996.6% | 4111.8% | 4649.5 MB | 0 |

## Bijna-live latency

Vosk gebruikt 200-ms PCM-blokken. Whisper en ONNX gebruiken niet-overlappende vensters van vijf seconden; daardoor kunnen geen dubbele overlapwoorden ontstaan. Whisper gebruikt daarnaast Silero VAD om stilte uit te filteren.

| Engine | Eerste leesbare tekst gem. | Definitieve tekst gem. |
| --- | ---: | ---: |
| vosk-small | 2.60 s | 17.68 s |
| vosk-lgraph | 2.54 s | 17.35 s |
| vosk-full | 2.05 s | 16.01 s |
| whisper-base-q5 | 5.47 s | 15.93 s |
| whisper-small-q5 | 6.17 s | 17.31 s |
| whisper-large-v3-turbo-q5 | 9.19 s | 22.99 s |
| nvidia-fastconformer-nl | 5.09 s | 15.24 s |
| nvidia-parakeet-tdt-v3-int8 | 5.24 s | 15.65 s |

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

### vosk-full

| Categorie | WER | CER | Weggelaten | Kritieke recall |
| --- | ---: | ---: | ---: | ---: |
| care-medical | 27.3% | 8.1% | 0.0% | 66.7% |
| hesitation-correction | 0.0% | 0.0% | 0.0% | 100.0% |
| household-conversation | 6.2% | 3.0% | 4.2% | 100.0% |
| light-noise | 33.3% | 17.2% | 0.0% | 100.0% |
| names-places | 26.3% | 15.3% | 5.3% | 80.0% |
| numbers | 20.0% | 13.6% | 0.0% | 100.0% |
| short-answer | 20.0% | 21.4% | 20.0% | 100.0% |
| silence | — | — | — | — |
| soft-fast-speech | 39.4% | 25.6% | 27.3% | 66.7% |

### whisper-base-q5

| Categorie | WER | CER | Weggelaten | Kritieke recall |
| --- | ---: | ---: | ---: | ---: |
| care-medical | 31.8% | 19.1% | 4.5% | 33.3% |
| hesitation-correction | 15.4% | 8.3% | 0.0% | 100.0% |
| household-conversation | 25.0% | 16.3% | 4.2% | 33.3% |
| light-noise | 42.1% | 10.5% | 5.3% | 0.0% |
| names-places | 21.1% | 10.2% | 0.0% | 100.0% |
| numbers | 20.0% | 5.7% | 0.0% | 100.0% |
| short-answer | 40.0% | 42.9% | 0.0% | 100.0% |
| silence | — | — | — | — |
| soft-fast-speech | 72.7% | 26.9% | 0.0% | 66.7% |

### whisper-small-q5

| Categorie | WER | CER | Weggelaten | Kritieke recall |
| --- | ---: | ---: | ---: | ---: |
| care-medical | 27.3% | 7.4% | 4.5% | 33.3% |
| hesitation-correction | 0.0% | 0.0% | 0.0% | 100.0% |
| household-conversation | 6.2% | 2.6% | 2.1% | 66.7% |
| light-noise | 5.3% | 2.1% | 0.0% | 100.0% |
| names-places | 0.0% | 0.0% | 0.0% | 100.0% |
| numbers | 20.0% | 5.7% | 0.0% | 100.0% |
| short-answer | 0.0% | 0.0% | 0.0% | 100.0% |
| silence | — | — | — | — |
| soft-fast-speech | 63.6% | 15.4% | 0.0% | 100.0% |

### whisper-large-v3-turbo-q5

| Categorie | WER | CER | Weggelaten | Kritieke recall |
| --- | ---: | ---: | ---: | ---: |
| care-medical | 4.5% | 0.7% | 0.0% | 100.0% |
| hesitation-correction | 0.0% | 0.0% | 0.0% | 100.0% |
| household-conversation | 0.0% | 0.0% | 0.0% | 100.0% |
| light-noise | 0.0% | 0.0% | 0.0% | 100.0% |
| names-places | 0.0% | 0.0% | 0.0% | 100.0% |
| numbers | 0.0% | 0.0% | 0.0% | 100.0% |
| short-answer | 0.0% | 0.0% | 0.0% | 100.0% |
| silence | — | — | — | — |
| soft-fast-speech | 0.0% | 0.0% | 0.0% | 100.0% |

### nvidia-fastconformer-nl

| Categorie | WER | CER | Weggelaten | Kritieke recall |
| --- | ---: | ---: | ---: | ---: |
| care-medical | 31.8% | 14.7% | 0.0% | 33.3% |
| hesitation-correction | 30.8% | 20.8% | 7.7% | 100.0% |
| household-conversation | 33.3% | 13.7% | 2.1% | 66.7% |
| light-noise | 73.7% | 77.9% | 68.4% | 0.0% |
| names-places | 47.4% | 24.5% | 5.3% | 60.0% |
| numbers | 0.0% | 0.0% | 0.0% | 100.0% |
| short-answer | 0.0% | 0.0% | 0.0% | 100.0% |
| silence | — | — | — | — |
| soft-fast-speech | 45.5% | 15.4% | 0.0% | 66.7% |

### nvidia-parakeet-tdt-v3-int8

| Categorie | WER | CER | Weggelaten | Kritieke recall |
| --- | ---: | ---: | ---: | ---: |
| care-medical | 18.2% | 4.4% | 0.0% | 50.0% |
| hesitation-correction | 0.0% | 0.0% | 0.0% | 100.0% |
| household-conversation | 8.3% | 3.9% | 2.1% | 66.7% |
| light-noise | 36.8% | 13.7% | 0.0% | 100.0% |
| names-places | 5.3% | 2.0% | 0.0% | 80.0% |
| numbers | 0.0% | 0.0% | 0.0% | 100.0% |
| short-answer | 100.0% | 107.1% | 0.0% | 0.0% |
| silence | — | — | — | — |
| soft-fast-speech | 45.5% | 10.3% | 0.0% | 66.7% |

## Resultaten per spreker

### vosk-small

| Sprekeralias | WER | CER | Weggelaten | Kritieke recall |
| --- | ---: | ---: | ---: | ---: |
| adult-a | 22.8% | 13.2% | 8.8% | 79.0% |

### vosk-lgraph

| Sprekeralias | WER | CER | Weggelaten | Kritieke recall |
| --- | ---: | ---: | ---: | ---: |
| adult-a | 25.2% | 13.5% | 5.9% | 85.2% |

### vosk-full

| Sprekeralias | WER | CER | Weggelaten | Kritieke recall |
| --- | ---: | ---: | ---: | ---: |
| adult-a | 19.5% | 10.7% | 4.6% | 85.2% |

### whisper-base-q5

| Sprekeralias | WER | CER | Weggelaten | Kritieke recall |
| --- | ---: | ---: | ---: | ---: |
| adult-a | 30.3% | 15.0% | 2.6% | 70.4% |

### whisper-small-q5

| Sprekeralias | WER | CER | Weggelaten | Kritieke recall |
| --- | ---: | ---: | ---: | ---: |
| adult-a | 13.2% | 4.3% | 1.3% | 81.5% |

### whisper-large-v3-turbo-q5

| Sprekeralias | WER | CER | Weggelaten | Kritieke recall |
| --- | ---: | ---: | ---: | ---: |
| adult-a | 0.7% | 0.1% | 0.0% | 100.0% |

### nvidia-fastconformer-nl

| Sprekeralias | WER | CER | Weggelaten | Kritieke recall |
| --- | ---: | ---: | ---: | ---: |
| adult-a | 36.8% | 22.0% | 10.5% | 66.7% |

### nvidia-parakeet-tdt-v3-int8

| Sprekeralias | WER | CER | Weggelaten | Kritieke recall |
| --- | ---: | ---: | ---: | ---: |
| adult-a | 17.1% | 6.5% | 0.7% | 74.1% |

## Beslissing

- **vosk-small: afgekeurd** — score 68.3/100; kritieke-woordenrecall 79.0% is te laag.
- **vosk-lgraph: afgekeurd; niet geschikt voor commercieel productgebruik** — score 68.4/100; 3 woorden gehallucineerd in stilte.
- **vosk-full: afgekeurd; niet geschikt voor commercieel productgebruik** — score 76.0/100; 3 woorden gehallucineerd in stilte.
- **whisper-base-q5: afgekeurd** — score 68.7/100; kritieke-woordenrecall 70.4% is te laag.
- **whisper-small-q5: afgekeurd** — score 61.1/100; kritieke-woordenrecall 81.5% is te laag.
- **whisper-large-v3-turbo-q5: afgekeurd** — score 60.2/100; vier-stream-RTF max 3.581 is niet < 1,0, minder dan 15% gemiddelde CPU-marge.
- **nvidia-fastconformer-nl: afgekeurd** — score 69.5/100; WER 36.8% overschrijdt de grens, kritieke-woordenrecall 66.7% is te laag, 3 woorden gehallucineerd in stilte.
- **nvidia-parakeet-tdt-v3-int8: afgekeurd** — score 75.6/100; kritieke-woordenrecall 74.1% is te laag.

**Geen model haalt op deze laptop tegelijk de ingestelde kwaliteitsgrenzen en vier-stream-realtime.** Vergelijk de foutredenen voordat hardware of architectuur wordt aangepast.

## Beperkingen

- De vier-streamtest meet rekenkracht met vier workerprocessen, niet de betrouwbaarheid van een toekomstige USB-audio-interface.
- De meting geldt alleen voor deze laptop, energie-instelling, testset en modelversies.
- De Engelse-insluipselmeting gebruikt een kleine lijst ondubbelzinnige Engelse woorden en blijft een heuristiek.
- Leesbaarheid (interpunctie en hoofdletters) is vastgelegd in de ruwe records maar telt niet mee voor WER/CER.
- Vosk LGraph heeft een CC-BY-NC-SA-licentie en wordt niet als commerciële productkeuze aanbevolen zonder licentieoplossing.

## Ruwe gegevens

- `20261104T190256+0100_dji_mini_baseline_nvidia-fastconformer-nl_near-live_c1.json` (nvidia-fastconformer-nl, near-live, concurrency 1)
- `20261104T180253+0100_dji_mini_baseline_nvidia-fastconformer-nl_offline_c1.json` (nvidia-fastconformer-nl, offline, concurrency 1)
- `20261104T180843+0100_dji_mini_baseline_nvidia-fastconformer-nl_offline_c2.json` (nvidia-fastconformer-nl, offline, concurrency 2)
- `20261104T181326+0100_dji_mini_baseline_nvidia-fastconformer-nl_offline_c4.json` (nvidia-fastconformer-nl, offline, concurrency 4)
- `20261104T190954+0100_dji_mini_baseline_nvidia-parakeet-tdt-v3-int8_near-live_c1.json` (nvidia-parakeet-tdt-v3-int8, near-live, concurrency 1)
- `20261104T180306+0100_dji_mini_baseline_nvidia-parakeet-tdt-v3-int8_offline_c1.json` (nvidia-parakeet-tdt-v3-int8, offline, concurrency 1)
- `20261104T180855+0100_dji_mini_baseline_nvidia-parakeet-tdt-v3-int8_offline_c2.json` (nvidia-parakeet-tdt-v3-int8, offline, concurrency 2)
- `20261104T181335+0100_dji_mini_baseline_nvidia-parakeet-tdt-v3-int8_offline_c4.json` (nvidia-parakeet-tdt-v3-int8, offline, concurrency 4)
- `20261104T183002+0100_dji_mini_baseline_vosk-full_near-live_c1.json` (vosk-full, near-live, concurrency 1)
- `20261104T175913+0100_dji_mini_baseline_vosk-full_offline_c1.json` (vosk-full, offline, concurrency 1)
- `20261104T180506+0100_dji_mini_baseline_vosk-full_offline_c2.json` (vosk-full, offline, concurrency 2)
- `20261104T181016+0100_dji_mini_baseline_vosk-full_offline_c4.json` (vosk-full, offline, concurrency 4)
- `20261104T182156+0100_dji_mini_baseline_vosk-lgraph_near-live_c1.json` (vosk-lgraph, near-live, concurrency 1)
- `20261104T175749+0100_dji_mini_baseline_vosk-lgraph_offline_c1.json` (vosk-lgraph, offline, concurrency 1)
- `20261104T180415+0100_dji_mini_baseline_vosk-lgraph_offline_c2.json` (vosk-lgraph, offline, concurrency 2)
- `20261104T180942+0100_dji_mini_baseline_vosk-lgraph_offline_c4.json` (vosk-lgraph, offline, concurrency 4)
- `20261104T181350+0100_dji_mini_baseline_vosk-small_near-live_c1.json` (vosk-small, near-live, concurrency 1)
- `20261104T175633+0100_dji_mini_baseline_vosk-small_offline_c1.json` (vosk-small, offline, concurrency 1)
- `20261104T180327+0100_dji_mini_baseline_vosk-small_offline_c2.json` (vosk-small, offline, concurrency 2)
- `20261104T180911+0100_dji_mini_baseline_vosk-small_offline_c4.json` (vosk-small, offline, concurrency 4)
- `20261104T183720+0100_dji_mini_baseline_whisper-base-q5_near-live_c1.json` (whisper-base-q5, near-live, concurrency 1)
- `20261104T175943+0100_dji_mini_baseline_whisper-base-q5_offline_c1.json` (whisper-base-q5, offline, concurrency 1)
- `20261104T180527+0100_dji_mini_baseline_whisper-base-q5_offline_c2.json` (whisper-base-q5, offline, concurrency 2)
- `20261104T181032+0100_dji_mini_baseline_whisper-base-q5_offline_c4.json` (whisper-base-q5, offline, concurrency 4)
- `20261104T185227+0100_dji_mini_baseline_whisper-large-v3-turbo-q5_near-live_c1.json` (whisper-large-v3-turbo-q5, near-live, concurrency 1)
- `20261104T180043+0100_dji_mini_baseline_whisper-large-v3-turbo-q5_offline_c1.json` (whisper-large-v3-turbo-q5, offline, concurrency 1)
- `20261104T180621+0100_dji_mini_baseline_whisper-large-v3-turbo-q5_offline_c2.json` (whisper-large-v3-turbo-q5, offline, concurrency 2)
- `20261104T181118+0100_dji_mini_baseline_whisper-large-v3-turbo-q5_offline_c4.json` (whisper-large-v3-turbo-q5, offline, concurrency 4)
- `20261104T184435+0100_dji_mini_baseline_whisper-small-q5_near-live_c1.json` (whisper-small-q5, near-live, concurrency 1)
- `20261104T180003+0100_dji_mini_baseline_whisper-small-q5_offline_c1.json` (whisper-small-q5, offline, concurrency 1)
- `20261104T180542+0100_dji_mini_baseline_whisper-small-q5_offline_c2.json` (whisper-small-q5, offline, concurrency 2)
- `20261104T181045+0100_dji_mini_baseline_whisper-small-q5_offline_c4.json` (whisper-small-q5, offline, concurrency 4)
