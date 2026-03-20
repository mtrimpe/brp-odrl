#!/usr/bin/env python3
"""
Generate afnemers.ttl from Tabel 35 CSV.

Extracts all unique afnemers (organisaties) with their afnemersindicatie
and naam. Uses the latest version's naam for each afnemer.
"""

import csv
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, "csv", "tabel35_autorisatietabel.csv")
OUTPUT_PATH = os.path.join(BASE_DIR, "ttl", "afnemers.ttl")

COL_AFN_IND = 1
COL_AFN_NAAM = 2


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


def format_afn(afn_ind):
    return str(afn_ind).strip()


def escape_ttl(s):
    return str(s).replace("\\", "\\\\").replace('"', '\\"')


def main():
    print("Reading Tabel 35...")
    rows = _read_csv(CSV_PATH)
    data = rows[1:]  # skip header

    afnemers = {}
    for row in data:
        afn = row[COL_AFN_IND].strip()
        if afn:
            afnemers[afn] = row[COL_AFN_NAAM].strip()

    sorted_afnemers = sorted(afnemers.keys(), key=lambda x: int(x))
    print(f"  {len(sorted_afnemers)} afnemers")

    print(f"Generating {OUTPUT_PATH}...")
    with open(OUTPUT_PATH, "w") as f:
        f.write("""@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix brp:  <https://data.rijksoverheid.nl/brp/def#> .
@prefix brpafn: <https://data.rijksoverheid.nl/brp/afnemer/> .

# =============================================================================
# BRP Afnemers
#
# Alle afnemers uit Tabel 35 (Autorisatietabel BRP).
# Bron: https://publicaties.rvig.nl/Landelijke_tabellen
# =============================================================================

""")
        for afn in sorted_afnemers:
            naam = afnemers[afn]
            afn_str = format_afn(afn)
            f.write(f"brpafn:{afn_str} a brp:Afnemer ;\n")
            f.write(f'    brp:afnemersindicatie "{afn_str}" ;\n')
            f.write(f'    rdfs:label "{escape_ttl(naam)}"@nl .\n\n')

    print(f"Generated {OUTPUT_PATH} ({len(sorted_afnemers)} afnemers)")


if __name__ == "__main__":
    main()
