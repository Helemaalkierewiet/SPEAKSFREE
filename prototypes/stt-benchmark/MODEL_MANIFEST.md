# Vastgezet model- en runtimemanifest

Gecontroleerd op 4 november 2026. `scripts/setup-models.ps1` vergelijkt iedere
download met deze SHA-256 voordat een archief wordt uitgepakt of gebruikt. Na de
installatie schrijft het daarnaast `models/manifest.local.json` met de werkelijk
gedownloade grootte, hash, tijd en lokale locatie.

| Onderdeel | Upstreamversie / commit | Bron | Grootte download | SHA-256 | Licentie |
| --- | --- | --- | ---: | --- | --- |
| Vosk Small NL | `vosk-model-small-nl-0.22` | [Vosk](https://alphacephei.com/vosk/models/vosk-model-small-nl-0.22.zip) | 40,441,176 bytes | `039811c3b829de64e4f123a9f684a53784005b212a346ac0b899dc7efce2ed0a` | Apache-2.0 |
| Vosk NL LGraph | `vosk-model-nl-spraakherkenning-0.6-lgraph` | [Vosk](https://alphacephei.com/vosk/models/vosk-model-nl-spraakherkenning-0.6-lgraph.zip) | 105,951,663 bytes | `ad3bdd17d19c99b6b9235669346fe79e871ecf0163b0b1efbe6d6b1ea88d9b5d` | CC-BY-NC-SA |
| Whisper Base Q5_1 meertalig | `f281eb45af861ab5e5297d23694b7d46e090c02c` | [Hugging Face](https://huggingface.co/ggerganov/whisper.cpp/blob/f281eb45af861ab5e5297d23694b7d46e090c02c/ggml-base-q5_1.bin) | 59,707,625 bytes | `422f1ae452ade6f30a004d7e5c6a43195e4433bc370bf23fac9cc591f01a8898` | MIT (runtime); modelvoorwaarden volgens upstream |
| whisper.cpp CPU x64 | `v1.9.5`, build `b5454`, commit `d1be6fd` | [GitHub](https://github.com/ggml-org/whisper.cpp/releases/tag/b5454) | 8,928,640 bytes | `6ba69e3482d7826214f90a6a9c84ca07782aec1e1d0c6a7c30c994fd5d816ccb` | MIT |

De LGraph-licentie bevat een niet-commercieel beding. Het model mag daarom niet als
productkeuze worden behandeld totdat de voorgenomen toepassing juridisch en met de
rechthebbende is opgelost.

