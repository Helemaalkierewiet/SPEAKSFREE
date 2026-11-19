# Opnameprotocol voor de lokale testset

Neem alle clips één keer op en laat daarna elk model exact deze bestanden verwerken.
Gebruik alleen volwassen deelnemers die aantoonbaar toestemming hebben gegeven. Kies
niet-herleidbare aliassen (`adult-a`, `adult-b`) en commit de map `references/private`
of `recordings` niet.

Streef naar 15–25 minuten verdeeld over minstens twee volwassenen en circa 24 clips:

| Categorie | Richtaantal | Voorbeeldinhoud |
| --- | ---: | --- |
| `short-answer` | 4 | ja; nee; weet ik niet; een ogenblikje |
| `household-conversation` | 3 | eten, bezoek, weer, dagelijkse planning |
| `long-sentence` | 2 | langere zin met één of twee bijzinnen |
| `numbers` | 3 | tijd, bedrag, datum, telefoonnummer |
| `names-places` | 2 | Nederlandse plaats- en persoonsnamen |
| `care-medical` | 3 | huisarts, medicatie, klachten, afspraak |
| `soft-speech` | 2 | zacht uitgesproken maar verstaanbare tekst |
| `fast-speech` | 2 | relatief snel en natuurlijk gesproken tekst |
| `hesitation-correction` | 2 | aarzelingen, herhaling en zelfcorrectie |
| `light-noise` | 2 | dezelfde soort spraak met lichte achtergrondruis |
| `silence` | 1 | minimaal 30 seconden echte stilte; lege referentietekst |

Markeer per clip namen, tijden, bedragen en zorgtermen met herhaalde
`--critical-word`-opties. Typ de referentie letterlijk, inclusief aarzelingen en
zelfcorrecties. Corrigeer geen woorden om ze beter bij een modeluitvoer te laten
passen.

Voorbeeld:

```powershell
python -m src.capture --session baseline --name care_01 --duration 45 `
  --speaker adult-a --category care-medical --distance-cm 50 `
  --critical-word huisarts --critical-word amoxicilline --consent
```

Controleer elke opname met een hoofdtelefoon. Neem clips met clipping, afgebroken
spraak of een verkeerde handmatige referentie opnieuw op voordat de eerste
benchmark start.

