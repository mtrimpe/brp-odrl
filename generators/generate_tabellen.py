#!/usr/bin/env python3
"""
Generate TTL files from RvIG Landelijke Tabellen CSV's.

Produces:
- brp-tabel32-nationaliteit.ttl  (Tabel 32: Nationaliteitentabel)
- brp-tabel34-land.ttl           (Tabel 34: Landentabel, with EU Pub Office links)
- brp-tabel56-verblijfstitel.ttl (Tabel 56: Verblijfstiteltabel)

Source: https://publicaties.rvig.nl/Landelijke_tabellen
"""

import csv
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# CSV paths
CSV_T32 = f"{BASE_DIR}/csv/tabel32_nationaliteit.csv"
CSV_T33 = f"{BASE_DIR}/csv/tabel33_gemeente.csv"
CSV_T34 = f"{BASE_DIR}/csv/tabel34_land.csv"
CSV_T56 = f"{BASE_DIR}/csv/tabel56_verblijfstitel.csv"

# Output paths
OUT_T32 = f"{BASE_DIR}/ttl/tabel32-nationaliteit.ttl"
OUT_T33 = f"{BASE_DIR}/ttl/tabel33-gemeente.ttl"
OUT_T34 = f"{BASE_DIR}/ttl/tabel34-land.ttl"
OUT_T56 = f"{BASE_DIR}/ttl/tabel56-verblijfstitel.ttl"


def _escape(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _read_csv(path):
    """Read a CSV, auto-detecting encoding."""
    # Detect encoding from BOM
    with open(path, "rb") as f:
        raw = f.read(4)

    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        enc = "utf-16"
    elif raw[:3] == b"\xef\xbb\xbf":
        enc = "utf-8-sig"
    else:
        # Try utf-8, fall back to latin-1
        enc = "utf-8"
        try:
            open(path, encoding="utf-8").read()
        except UnicodeDecodeError:
            enc = "latin-1"

    with open(path, encoding=enc, newline="") as f:
        reader = csv.reader(f)
        rows = [r for r in reader if any(c.strip() for c in r)]
    return rows


def _format_date(d):
    """Convert YYYYMMDD to xsd:date, or return None."""
    d = d.strip()
    if not d or len(d) < 8:
        return None
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"


def generate_tabel32():
    """Generate nationaliteit TTL from Tabel 32."""
    rows = _read_csv(CSV_T32)
    header = rows[0]
    data = rows[1:]

    print(f"Tabel 32: {len(data)} nationaliteiten")

    with open(OUT_T32, "w") as f:
        f.write("""@prefix rdfs:   <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:    <http://www.w3.org/2001/XMLSchema#> .
@prefix skos:   <http://www.w3.org/2004/02/skos/core#> .
@prefix dct:    <http://purl.org/dc/terms/> .
@prefix brp:    <https://data.rijksoverheid.nl/brp/def#> .
@prefix brpnat: <https://data.rijksoverheid.nl/brp/nationaliteit/> .

# =============================================================================
# BRP Tabel 32 - Nationaliteitentabel
#
# Gegenereerd uit de RvIG Landelijke Tabel 32 (Nationaliteitentabel).
# Bron: https://publicaties.rvig.nl/Landelijke_tabellen
# =============================================================================

""")
        for row in data:
            code = row[0].strip()
            naam = row[1].strip()
            ingang = row[2].strip() if len(row) > 2 else ""
            einde = row[3].strip() if len(row) > 3 else ""

            if not code:
                continue

            f.write(f"brpnat:{code} a brp:Nationaliteit ;\n")
            f.write(f'    rdfs:label "{_escape(naam)}"@nl ;\n')
            f.write(f'    skos:notation "{code}" ;\n')

            ingang_d = _format_date(ingang)
            einde_d = _format_date(einde)
            if ingang_d:
                f.write(f'    dct:valid "{ingang_d}"^^xsd:date ;\n')
            if einde_d:
                f.write(f'    brp:datumEinde "{einde_d}"^^xsd:date ;\n')

            f.write(f'    brp:tabel "32" .\n\n')

    print(f"  Generated {OUT_T32}")


def generate_tabel34():
    """Generate land TTL from Tabel 34, with EU Publications Office links."""
    rows = _read_csv(CSV_T34)
    header = rows[0]
    data = rows[1:]

    print(f"Tabel 34: {len(data)} landen")

    EU_COUNTRY = "http://publications.europa.eu/resource/authority/country/"

    with open(OUT_T34, "w") as f:
        f.write("""@prefix rdfs:   <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:    <http://www.w3.org/2001/XMLSchema#> .
@prefix skos:   <http://www.w3.org/2004/02/skos/core#> .
@prefix dct:    <http://purl.org/dc/terms/> .
@prefix brp:    <https://data.rijksoverheid.nl/brp/def#> .
@prefix brpland: <https://data.rijksoverheid.nl/brp/land/> .

# =============================================================================
# BRP Tabel 34 - Landentabel
#
# Gegenereerd uit de RvIG Landelijke Tabel 34 (Landentabel).
# Bevat links naar EU Publications Office country authority waar beschikbaar.
# Bron: https://publicaties.rvig.nl/Landelijke_tabellen
# =============================================================================

""")
        for row in data:
            code = row[0].strip()
            naam = row[1].strip()
            iso_a2 = row[2].strip() if len(row) > 2 else ""
            iso_a3 = row[3].strip() if len(row) > 3 else ""
            iso_num = row[4].strip() if len(row) > 4 else ""
            iso_eng = row[6].strip() if len(row) > 6 else ""
            ingang = row[8].strip() if len(row) > 8 else ""
            einde = row[9].strip() if len(row) > 9 else ""

            if not code:
                continue

            f.write(f"brpland:{code} a brp:Land ;\n")
            f.write(f'    rdfs:label "{_escape(naam)}"@nl ;\n')
            if iso_eng:
                f.write(f'    rdfs:label "{_escape(iso_eng)}"@en ;\n')
            f.write(f'    skos:notation "{code}" ;\n')

            if iso_a2:
                f.write(f'    brp:isoAlpha2 "{iso_a2}" ;\n')
            if iso_a3:
                f.write(f'    brp:isoAlpha3 "{iso_a3}" ;\n')
                # Link to EU Publications Office country authority
                if iso_a3 != "XXX":
                    f.write(
                        f"    skos:exactMatch"
                        f" <{EU_COUNTRY}{iso_a3}> ;\n"
                    )
            if iso_num:
                f.write(f'    brp:isoNumeric "{iso_num}" ;\n')

            ingang_d = _format_date(ingang)
            einde_d = _format_date(einde)
            if ingang_d:
                f.write(f'    dct:valid "{ingang_d}"^^xsd:date ;\n')
            if einde_d:
                f.write(f'    brp:datumEinde "{einde_d}"^^xsd:date ;\n')

            f.write(f'    brp:tabel "34" .\n\n')

    print(f"  Generated {OUT_T34}")


def generate_tabel56():
    """Generate verblijfstitel TTL from Tabel 56."""
    rows = _read_csv(CSV_T56)
    header = rows[0]
    data = rows[1:]

    print(f"Tabel 56: {len(data)} verblijfstitels")

    with open(OUT_T56, "w") as f:
        f.write("""@prefix rdfs:   <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:    <http://www.w3.org/2001/XMLSchema#> .
@prefix skos:   <http://www.w3.org/2004/02/skos/core#> .
@prefix dct:    <http://purl.org/dc/terms/> .
@prefix brp:    <https://data.rijksoverheid.nl/brp/def#> .
@prefix brpvbt: <https://data.rijksoverheid.nl/brp/verblijfstitel/> .

# =============================================================================
# BRP Tabel 56 - Verblijfstiteltabel
#
# Gegenereerd uit de RvIG Landelijke Tabel 56 (Verblijfstiteltabel).
# Bron: https://publicaties.rvig.nl/Landelijke_tabellen
# =============================================================================

""")
        for row in data:
            code = row[0].strip()
            naam = row[1].strip()
            ingang = row[2].strip() if len(row) > 2 else ""
            einde = row[3].strip() if len(row) > 3 else ""

            if not code:
                continue

            f.write(f"brpvbt:{code} a brp:VerblijfstitelType ;\n")
            f.write(f'    rdfs:label "{_escape(naam)}"@nl ;\n')
            f.write(f'    skos:notation "{code}" ;\n')

            ingang_d = _format_date(ingang)
            einde_d = _format_date(einde)
            if ingang_d:
                f.write(f'    dct:valid "{ingang_d}"^^xsd:date ;\n')
            if einde_d:
                f.write(f'    brp:datumEinde "{einde_d}"^^xsd:date ;\n')

            f.write(f'    brp:tabel "56" .\n\n')

    print(f"  Generated {OUT_T56}")


def generate_tabel33():
    """Generate gemeente TTL from Tabel 33, with TOOI links."""
    rows = _read_csv(CSV_T33)
    header = rows[0]
    data = rows[1:]

    print(f"Tabel 33: {len(data)} gemeenten")

    TOOI = "https://identifier.overheid.nl/tooi/id/gemeente/"

    with open(OUT_T33, "w") as f:
        f.write("""@prefix rdfs:   <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:    <http://www.w3.org/2001/XMLSchema#> .
@prefix skos:   <http://www.w3.org/2004/02/skos/core#> .
@prefix dct:    <http://purl.org/dc/terms/> .
@prefix brp:    <https://data.rijksoverheid.nl/brp/def#> .
@prefix gem:    <https://identifier.overheid.nl/tooi/id/gemeente/> .

# =============================================================================
# BRP Tabel 33 - Gemeententabel
#
# Gegenereerd uit de RvIG Landelijke Tabel 33 (Gemeententabel).
# URI's verwijzen naar TOOI (Thesaurus en Ontologie Overheidsinformatie).
# Bron: https://publicaties.rvig.nl/Landelijke_tabellen
# =============================================================================

""")
        for row in data:
            code = row[0].strip()
            naam = row[1].strip()
            nieuwe_code = row[2].strip() if len(row) > 2 else ""
            ingang = row[3].strip() if len(row) > 3 else ""
            einde = row[4].strip() if len(row) > 4 else ""

            if not code:
                continue

            f.write(f"gem:gm{code} a brp:Gemeente ;\n")
            f.write(f'    rdfs:label "{_escape(naam)}"@nl ;\n')
            f.write(f'    skos:notation "{code}" ;\n')

            if nieuwe_code:
                f.write(f"    brp:nieuwGemeentecode gem:gm{nieuwe_code} ;\n")

            ingang_d = _format_date(ingang)
            einde_d = _format_date(einde)
            if ingang_d:
                f.write(f'    dct:valid "{ingang_d}"^^xsd:date ;\n')
            if einde_d:
                f.write(f'    brp:datumEinde "{einde_d}"^^xsd:date ;\n')

            f.write(f'    brp:tabel "33" .\n\n')

    print(f"  Generated {OUT_T33}")


def main():
    generate_tabel32()
    generate_tabel33()
    generate_tabel34()
    generate_tabel56()

    # Validate
    try:
        import rdflib
        for path in [OUT_T32, OUT_T33, OUT_T34, OUT_T56]:
            g = rdflib.Graph()
            g.parse(path, format="turtle")
            print(f"  {path}: {len(g)} triples - OK")
    except ImportError:
        print("WARNING: rdflib not installed, skipping validation")


if __name__ == "__main__":
    main()
