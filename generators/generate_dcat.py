#!/usr/bin/env python3
"""
Generate dcat-entry.ttl — DCAT-AP-NL 3.0 catalogus entry for the BRP.

Describes the BRP as a DCAT dataset with distribution, data services,
and a link to the ODRL autorisatiebesluiten.
"""

import csv
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, "csv", "tabel35_autorisatietabel.csv")
OUTPUT_PATH = os.path.join(BASE_DIR, "ttl", "dcat-entry.ttl")

COL_EINDE = 4


def _read_csv(path):
    with open(path, "rb") as f:
        raw = f.read(4)
    enc = "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8"
    try:
        open(path, encoding=enc).read()
    except UnicodeDecodeError:
        enc = "latin-1"
    with open(path, encoding=enc, newline="") as f:
        return [r for r in csv.reader(f) if any(c.strip() for c in r)]


def main():
    print("Reading Tabel 35 for statistics...")
    rows = _read_csv(CSV_PATH)
    data = rows[1:]

    afnemers = set()
    n_active = 0
    for row in data:
        if len(row) > 1 and row[1].strip():
            afnemers.add(row[1].strip())
        if len(row) > COL_EINDE and not row[COL_EINDE].strip():
            n_active += 1

    n_afnemers = len(afnemers)
    n_versions = len(data)

    print(f"  {n_afnemers} afnemers, {n_versions} tabelregels, {n_active} actief")

    print(f"Generating {OUTPUT_PATH}...")
    with open(OUTPUT_PATH, "w") as f:
        f.write(f"""@prefix rdfs:   <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:    <http://www.w3.org/2001/XMLSchema#> .
@prefix dcat:   <http://www.w3.org/ns/dcat#> .
@prefix dct:    <http://purl.org/dc/terms/> .
@prefix dcatap: <http://data.europa.eu/r5r/> .
@prefix foaf:   <http://xmlns.com/foaf/0.1/> .
@prefix vcard:  <http://www.w3.org/2006/vcard/ns#> .
@prefix odrl:   <http://www.w3.org/ns/odrl/2/> .
@prefix adms:   <http://www.w3.org/ns/adms#> .
@prefix eli:    <http://data.europa.eu/eli/ontology#> .
@prefix brp:    <https://data.rijksoverheid.nl/brp/def#> .
@prefix brpaut: <https://data.rijksoverheid.nl/brp/autorisatie/> .
@prefix brpds:  <https://data.rijksoverheid.nl/brp/distributie/> .
@prefix brpsvc: <https://data.rijksoverheid.nl/brp/service/> .

# =============================================================================
# BRP DCAT-AP-NL 3.0 Catalogus Entry
#
# Beschrijft de Basisregistratie Personen (BRP) als DCAT dataset met:
# - De BRP als dcat:Dataset
# - De verstrekkingsvoorziening (GBA-V) als dcat:Distribution
# - Autorisatiebesluiten als odrl:hasPolicy
# - Koppelvlakken als dcat:DataService
#
# Conform: DCAT-AP-NL 3.0 (https://docs.geostandaarden.nl/dcat/dcat-ap-nl30/)
#
# Statistieken Tabel 35:
#   {n_afnemers} afnemers, {n_versions} tabelregels, {n_active} actief
# =============================================================================

# =============================================================================
# Catalogus
# =============================================================================

<https://data.rijksoverheid.nl/brp/catalogus>
    a dcat:Catalog ;
    dct:title "BRP Autorisatiecatalogus"@nl ;
    dct:description \"\"\"Catalogus van de Basisregistratie Personen (BRP) met
autorisatiebesluiten als ODRL policies conform DCAT-AP-NL 3.0.\"\"\"@nl ;
    dct:publisher <https://data.rijksoverheid.nl/brp/org/RvIG> ;
    dct:language <http://publications.europa.eu/resource/authority/language/NLD> ;
    dcat:dataset <https://data.rijksoverheid.nl/brp/dataset/brp> ;
    dcat:service brpsvc:adhoc, brpsvc:spontaan, brpsvc:selectie .

# =============================================================================
# Organisaties
# =============================================================================

<https://data.rijksoverheid.nl/brp/org/RvIG>
    a foaf:Organization ;
    foaf:name "Rijksdienst voor Identiteitsgegevens"@nl ;
    foaf:homepage <https://www.rvig.nl> .

# =============================================================================
# Contactpunt
# =============================================================================

<https://data.rijksoverheid.nl/brp/contact/rvig>
    a vcard:Organization ;
    vcard:fn "Rijksdienst voor Identiteitsgegevens"@nl ;
    vcard:hasURL <https://www.rvig.nl/brp> .

# =============================================================================
# Dataset: Basisregistratie Personen (BRP)
# =============================================================================

<https://data.rijksoverheid.nl/brp/dataset/brp>
    a dcat:Dataset ;
    dct:title "Basisregistratie Personen (BRP)"@nl ;
    dct:description \"\"\"De Nederlandse overheid registreert persoonsgegevens in de
Basisregistratie Personen (BRP). Alle overheidsinstellingen en bestuursorganen
zijn verplicht voor hun taken gebruik te maken van deze gegevens.\"\"\"@nl ;
    dct:identifier "basisregistratie-personen-brp" ;
    dct:publisher <https://data.rijksoverheid.nl/brp/org/RvIG> ;
    dct:creator <https://data.rijksoverheid.nl/brp/org/RvIG> ;
    dcat:contactPoint <https://data.rijksoverheid.nl/brp/contact/rvig> ;
    dcat:theme <http://standaarden.overheid.nl/owms/terms/Bestuur> ;
    dct:accessRights <http://publications.europa.eu/resource/authority/access-right/NON_PUBLIC> ;
    dcat:keyword "Persoonsgegevens"@nl, "Basisregistratie"@nl,
                 "Autorisatie"@nl, "BRP"@nl ;
    dct:language <http://publications.europa.eu/resource/authority/language/NLD> ;
    dct:spatial <http://publications.europa.eu/resource/authority/country/NLD> ;
    dct:temporal [
        a dct:PeriodOfTime ;
        dcat:startDate "2014-01-06"^^xsd:date
    ] ;
    dct:accrualPeriodicity <http://publications.europa.eu/resource/authority/frequency/DAILY> ;
    dcat:landingPage <https://www.rvig.nl/basisregistratie-personen> ;
    dct:conformsTo <https://data.rijksoverheid.nl/brp/def> ;
    dcatap:applicableLegislation <http://data.europa.eu/eli/wet/2013/brp> ;
    dct:issued "2014-01-06"^^xsd:date ;
    adms:status <http://purl.org/adms/status/Completed> ;
    dct:provenance [
        a dct:ProvenanceStatement ;
        rdfs:label \"\"\"De BRP is de opvolger van de Gemeentelijke Basisadministratie
persoonsgegevens (GBA). Op 6 januari 2014 is de Wet BRP in werking getreden.\"\"\"@nl
    ] ;
    dcat:distribution brpds:gbav .

# =============================================================================
# Wet BRP als ELI LegalResource
# =============================================================================

<http://data.europa.eu/eli/wet/2013/brp>
    a eli:LegalResource ;
    dct:title "Wet basisregistratie personen"@nl ;
    rdfs:seeAlso <https://wetten.overheid.nl/BWBR0033715> .

# =============================================================================
# DataServices (koppelvlakken)
# =============================================================================

brpsvc:adhoc
    a dcat:DataService ;
    dct:title "BRP Ad hoc gegevensverstrekking"@nl ;
    dct:description \"\"\"Zoekvraag-gebaseerde verstrekking op verzoek van een
geautoriseerde afnemer (HaalCentraal BRP Bevragen API).\"\"\"@nl ;
    dcat:endpointURL <https://brp.basisregistraties.overheid.nl/haalcentraal/api/brp> ;
    dcat:servesDataset <https://data.rijksoverheid.nl/brp/dataset/brp> ;
    dct:conformsTo <https://brp-api.github.io/Haal-Centraal-BRP-bevragen/> .

brpsvc:spontaan
    a dcat:DataService ;
    dct:title "BRP Spontane gegevensverstrekking"@nl ;
    dct:description \"\"\"Push-gebaseerde verstrekking: bij wijziging van een
sleutelrubriek op een PL worden gegevens automatisch aan de afnemer verstrekt.\"\"\"@nl ;
    dcat:servesDataset <https://data.rijksoverheid.nl/brp/dataset/brp> .

brpsvc:selectie
    a dcat:DataService ;
    dct:title "BRP Selectieverstrekking"@nl ;
    dct:description \"\"\"Periodieke of eenmalige selectie van persoonslijsten
die aan de voorwaarderegel voldoen.\"\"\"@nl ;
    dcat:servesDataset <https://data.rijksoverheid.nl/brp/dataset/brp> .

# =============================================================================
# Distributie: BRP Verstrekkingsvoorziening (GBA-V)
# =============================================================================

brpds:gbav
    a dcat:Distribution ;
    dct:title "BRP Verstrekkingsvoorziening (GBA-V)"@nl ;
    dct:description \"\"\"De centrale verstrekkingsvoorziening van de BRP (GBA-V).
Alle gegevensverstrekking loopt via deze voorziening. Toegang is uitsluitend
voor geautoriseerde afnemers op basis van een autorisatiebesluit conform
de Wet BRP.\"\"\"@nl ;
    dcat:accessURL <https://www.rvig.nl/brp> ;
    dcat:accessService brpsvc:adhoc, brpsvc:spontaan, brpsvc:selectie ;
    dct:license <http://standaarden.overheid.nl/owms/terms/geslotenlicentie> ;
    dcatap:applicableLegislation <http://data.europa.eu/eli/wet/2013/brp> ;
    dct:conformsTo <https://data.rijksoverheid.nl/brp/def> ;
    dct:rights [
        a dct:RightsStatement ;
        rdfs:label \"\"\"Toegang uitsluitend voor geautoriseerde afnemers op basis
van een autorisatiebesluit conform de Wet BRP.\"\"\"@nl
    ] ;
    odrl:hasPolicy brpaut:autorisatiebesluiten .
""")

    print(f"Generated {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
