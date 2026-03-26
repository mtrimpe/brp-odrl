# BRP Autorisatiebesluiten als ODRL Linked Data

Alle autorisatiebesluiten uit de [BRP autorisatietabel (Tabel 35)](https://publicaties.rvig.nl/Landelijke_tabellen/Landelijke_tabellen_32_tot_en_met_61/Tabel_35_Autorisatietabel) als [ODRL 2.2](https://www.w3.org/TR/odrl-model/) Linked Data.

## Wat zit erin?

| Bestand | Beschrijving |
|---------|-------------|
| `odrl-ontology.ttl` | OWL ontologie + ODRL profiel voor het BRP autorisatiedomein |
| `ttl/informatiemodel.ttl` | BRP categorieën, groepen en elementen (rubrieken) |
| `ttl/autorisatiebesluiten-actueel.ttl` | Alle ~1.400 actuele autorisatiebesluiten als ODRL policies |
| `ttl/autorisatiebesluiten-compact.ttl` | Idem, compact: één policy per afnemer met temporele versies |
| `ttl/afnemers.ttl` | Alle ~2.600 afnemers met metadata |
| `ttl/dcat-entry.ttl` | DCAT-AP-NL 3.0 catalogus |
| `ttl/tabel*.ttl` | RvIG referentietabellen (nationaliteit, gemeente, land, verblijfstitel) |

De historische autorisatiebesluiten (~108 MB) en het gecombineerde bestand (~121 MB) worden niet meegeleverd vanwege de GitHub bestandslimiet. Ze kunnen gegenereerd worden (zie onder).

## Brondata

De generators downloaden automatisch de volgende RvIG Landelijke Tabellen:

- Tabel 32 – Nationaliteit
- Tabel 33 – Gemeente
- Tabel 34 – Land
- Tabel 35 – Autorisatietabel
- Tabel 56 – Verblijfstitel

## Namespace-ontwerp

| Prefix | Namespace | Bevat |
|--------|-----------|-------|
| `brp:` | `https://data.rijksoverheid.nl/brp/def#` | Ontologie (klassen, properties, acties, operatoren) |
| `brpcat:` | `https://data.rijksoverheid.nl/brp/categorie/` | BRP categorieën (01–17 actueel, 51–66 historisch) |
| `brpgrp:` | `https://data.rijksoverheid.nl/brp/groep/` | BRP groepen |
| `brprub:` | `https://data.rijksoverheid.nl/brp/rubriek/` | BRP elementen/rubrieken (CC.GG.EE) |
| `brpafn:` | `https://data.rijksoverheid.nl/brp/afnemer/` | Afnemers (op afnemersindicatie) |
| `brpaut:` | `https://data.rijksoverheid.nl/brp/autorisatie/` | Autorisatiebesluiten (policies) |

## Zelf genereren

Vereist Python 3.10+.

```bash
make generate
```

Dit doet:
1. Maakt een virtualenv aan en installeert dependencies (`rdflib`, `openpyxl`, `pyparsing`)
2. Downloadt de RvIG brontabellen (eenmalig, ~5 MB)
3. Genereert alle TTL-bestanden in `ttl/`
4. Valideert referentiële integriteit

Of handmatig:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install rdflib openpyxl pyparsing
python generators/generate_all.py
```

Met `--clean` worden de gedownloade bronbestanden eerst verwijderd en opnieuw opgehaald:

```bash
python generators/generate_all.py --clean
```

## BRP → ODRL mapping

| BRP concept | ODRL concept |
|-------------|-------------|
| Autorisatiebesluit | `odrl:Set` |
| Afnemer | `odrl:assignee` |
| Koppelvlak (spontaan, selectie, ad hoc) | `odrl:Action` |
| Personen API query type | `odrl:Action` (sub-actie via `odrl:includedIn`) |
| Geautoriseerde rubrieken | `odrl:target` |
| Voorwaarderegel | `odrl:Constraint` / `odrl:LogicalConstraint` |
| ENVWD | `odrl:and` |
| OFVWD | `odrl:or` |
| OFVGL | `odrl:isAnyOf` |
| GA1/GD1/KD1 etc. | Custom operatoren (`brp:ga1`, `brp:gd1`, ...) |
| KV/KNV | `brp:kv` / `brp:knv` (bestaans-operatoren) |
| Datum ingang/einde tabelregel | ODRL Temporal Profile |

## Gerelateerde projecten

- [W3C ODRL Information Model 2.2](https://www.w3.org/TR/odrl-model/)
- [ODRL Formal Semantics](https://w3c.github.io/odrl/formal-semantics/)
- [FORCE ODRL Evaluator](https://github.com/SolidLabResearch/ODRL-Evaluator)
- [Logisch Ontwerp BRP 2025.Q1](https://www.rvig.nl/sites/default/files/2024-12/Logisch%20Ontwerp%20BRP%202025.Q1.pdf)

## Licentie

De brondata (Tabel 35 en overige Landelijke Tabellen) is afkomstig van de Rijksdienst voor Identiteitsgegevens (RvIG) en valt onder de voorwaarden van het [Besluit BRP](https://wetten.overheid.nl/BWBR0033715).
