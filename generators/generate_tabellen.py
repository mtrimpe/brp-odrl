#!/usr/bin/env python3
"""
Generate TTL files from RvIG Landelijke Tabellen CSV's.

Produces:
- brp-tabel32-nationaliteit.ttl  (Tabel 32: Nationaliteitentabel)
- brp-tabel33-gemeente.ttl       (Tabel 33: Gemeententabel)
- brp-tabel34-land.ttl           (Tabel 34: Landentabel, with EU Pub Office links)
- brp-tabel56-verblijfstitel.ttl (Tabel 56: Verblijfstiteltabel)

Source: https://publicaties.rvig.nl/Landelijke_tabellen
"""

import csv
import os

from rdflib import Literal, Namespace
from rdflib.namespace import XSD

from namespaces import new_graph, save, BRP, BRPNAT, BRPLAND, BRPVBT, GEM, RDF, RDFS, SKOS, DCTERMS

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

EU_COUNTRY = Namespace("http://publications.europa.eu/resource/authority/country/")


def _read_csv(path):
    """Read a CSV, auto-detecting encoding."""
    with open(path, "rb") as f:
        raw = f.read(4)

    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        enc = "utf-16"
    elif raw[:3] == b"\xef\xbb\xbf":
        enc = "utf-8-sig"
    else:
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
    """Convert YYYYMMDD to xsd:date string, or return None."""
    d = d.strip()
    if not d or len(d) < 8:
        return None
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"


def generate_tabel32():
    """Generate nationaliteit TTL from Tabel 32."""
    rows = _read_csv(CSV_T32)
    data = rows[1:]

    print(f"Tabel 32: {len(data)} nationaliteiten")

    g = new_graph()
    for row in data:
        code = row[0].strip()
        naam = row[1].strip()
        ingang = row[2].strip() if len(row) > 2 else ""
        einde = row[3].strip() if len(row) > 3 else ""

        if not code:
            continue

        subj = BRPNAT[code]
        g.add((subj, RDF.type, BRP.Nationaliteit))
        g.add((subj, RDFS.label, Literal(naam, lang="nl")))
        g.add((subj, SKOS.notation, Literal(code)))

        ingang_d = _format_date(ingang)
        einde_d = _format_date(einde)
        if ingang_d:
            g.add((subj, DCTERMS.valid, Literal(ingang_d, datatype=XSD.date)))
        if einde_d:
            g.add((subj, BRP.datumEinde, Literal(einde_d, datatype=XSD.date)))

        g.add((subj, BRP.tabel, Literal("32")))

    save(g, OUT_T32)


def generate_tabel34():
    """Generate land TTL from Tabel 34, with EU Publications Office links."""
    rows = _read_csv(CSV_T34)
    data = rows[1:]

    print(f"Tabel 34: {len(data)} landen")

    g = new_graph()
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

        subj = BRPLAND[code]
        g.add((subj, RDF.type, BRP.Land))
        g.add((subj, RDFS.label, Literal(naam, lang="nl")))
        if iso_eng:
            g.add((subj, RDFS.label, Literal(iso_eng, lang="en")))
        g.add((subj, SKOS.notation, Literal(code)))

        if iso_a2:
            g.add((subj, BRP.isoAlpha2, Literal(iso_a2)))
        if iso_a3:
            g.add((subj, BRP.isoAlpha3, Literal(iso_a3)))
            if iso_a3 != "XXX":
                g.add((subj, SKOS.exactMatch, EU_COUNTRY[iso_a3]))
        if iso_num:
            g.add((subj, BRP.isoNumeric, Literal(iso_num)))

        ingang_d = _format_date(ingang)
        einde_d = _format_date(einde)
        if ingang_d:
            g.add((subj, DCTERMS.valid, Literal(ingang_d, datatype=XSD.date)))
        if einde_d:
            g.add((subj, BRP.datumEinde, Literal(einde_d, datatype=XSD.date)))

        g.add((subj, BRP.tabel, Literal("34")))

    save(g, OUT_T34)


def generate_tabel56():
    """Generate verblijfstitel TTL from Tabel 56."""
    rows = _read_csv(CSV_T56)
    data = rows[1:]

    print(f"Tabel 56: {len(data)} verblijfstitels")

    g = new_graph()
    for row in data:
        code = row[0].strip()
        naam = row[1].strip()
        ingang = row[2].strip() if len(row) > 2 else ""
        einde = row[3].strip() if len(row) > 3 else ""

        if not code:
            continue

        subj = BRPVBT[code]
        g.add((subj, RDF.type, BRP.VerblijfstitelType))
        g.add((subj, RDFS.label, Literal(naam, lang="nl")))
        g.add((subj, SKOS.notation, Literal(code)))

        ingang_d = _format_date(ingang)
        einde_d = _format_date(einde)
        if ingang_d:
            g.add((subj, DCTERMS.valid, Literal(ingang_d, datatype=XSD.date)))
        if einde_d:
            g.add((subj, BRP.datumEinde, Literal(einde_d, datatype=XSD.date)))

        g.add((subj, BRP.tabel, Literal("56")))

    save(g, OUT_T56)


def generate_tabel33():
    """Generate gemeente TTL from Tabel 33, with TOOI links."""
    rows = _read_csv(CSV_T33)
    data = rows[1:]

    print(f"Tabel 33: {len(data)} gemeenten")

    g = new_graph()
    for row in data:
        code = row[0].strip()
        naam = row[1].strip()
        nieuwe_code = row[2].strip() if len(row) > 2 else ""
        ingang = row[3].strip() if len(row) > 3 else ""
        einde = row[4].strip() if len(row) > 4 else ""

        if not code:
            continue

        subj = GEM[f"gm{code}"]
        g.add((subj, RDF.type, BRP.Gemeente))
        g.add((subj, RDFS.label, Literal(naam, lang="nl")))
        g.add((subj, SKOS.notation, Literal(code)))

        if nieuwe_code:
            g.add((subj, BRP.nieuwGemeentecode, GEM[f"gm{nieuwe_code}"]))

        ingang_d = _format_date(ingang)
        einde_d = _format_date(einde)
        if ingang_d:
            g.add((subj, DCTERMS.valid, Literal(ingang_d, datatype=XSD.date)))
        if einde_d:
            g.add((subj, BRP.datumEinde, Literal(einde_d, datatype=XSD.date)))

        g.add((subj, BRP.tabel, Literal("33")))

    save(g, OUT_T33)


def main():
    generate_tabel32()
    generate_tabel33()
    generate_tabel34()
    generate_tabel56()


if __name__ == "__main__":
    main()
