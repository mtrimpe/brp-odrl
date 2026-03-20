#!/usr/bin/env python3
"""Generate brp-informatiemodel.ttl from brp_elementen module.

Produces a complete Turtle file with all BRP categories, groups, and elements
using meaningful URI names from brp_elementen.rubriek_to_uri().
"""

import os
import sys
from collections import OrderedDict

from brp_elementen import (
    CATEGORIES,
    CATEGORY_ELEMENTS,
    ELEMENT_COMMENTS,
    ELEMENT_VALUE_TYPES,
    ELEMENTS,
    GROUPS,
    _HISTORIC_TO_ACTUAL,
    all_rubrieken,
    categorie_to_uri,
    groep_to_uri,
    rubriek_to_label,
    rubriek_to_uri,
)

# Map value types to rdfs:range classes
VALUE_TYPE_RANGES = {
    "gemeente": "brp:Gemeente",
    "nationaliteit": "brp:Nationaliteit",
    "land": "brp:Land",
    "verblijfstitel": "brp:VerblijfstitelType",
    "afnemer": "brp:Afnemer",
}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_FILE = os.path.join(BASE_DIR, "ttl", "informatiemodel.ttl")

PREFIXES = """\
@prefix rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs:   <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:    <http://www.w3.org/2001/XMLSchema#> .
@prefix skos:   <http://www.w3.org/2004/02/skos/core#> .
@prefix brp:    <https://data.rijksoverheid.nl/brp/def#> .
@prefix brpcat: <https://data.rijksoverheid.nl/brp/categorie/> .
@prefix brpgrp: <https://data.rijksoverheid.nl/brp/groep/> .
@prefix brpelm: <https://data.rijksoverheid.nl/brp/element/> .
"""

HEADER = """\
# =============================================================================
# BRP Informatiemodel - Categorieën, Groepen en Elementen
#
# Gegenereerd door generate_informatiemodel.py uit brp_elementen.py
# Gebaseerd op het Logisch Ontwerp BRP 2024.Q2, Deel 4: Gegevenswoordenboek
# Categorieën 01-17 = actueel, 51-66 = historisch
# =============================================================================
"""


def _escape_ttl_string(s: str) -> str:
    """Escape special characters for Turtle string literals."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _grp_label(grp_code: str) -> str:
    """Return the Dutch label for a group code."""
    entry = GROUPS.get(grp_code)
    return entry[0] if entry else f"Groep {grp_code}"


def _sorted_actual_categories() -> list[int]:
    """Return actual (non-historic) category numbers in sorted order."""
    return sorted(cat for cat in CATEGORY_ELEMENTS.keys())


def generate() -> str:
    """Generate the complete TTL content."""
    lines = []
    lines.append(PREFIXES)
    lines.append(HEADER)

    actual_cats = _sorted_actual_categories()

    # Category comments (from LO-BRP §4.4)
    cat_comments = {
        1: "Gegevens over de ingeschrevene.",
        2: "Gegevens over de ouder1 van de ingeschrevene.",
        3: "Gegevens over de ouder2 van de ingeschrevene.",
        4: "Gegevens over een nationaliteit van de ingeschrevene.",
        5: "Gegevens over een gesloten of ontbonden huwelijk of geregistreerd partnerschap van de ingeschrevene.",
        6: "Gegevens over het overlijden van de ingeschrevene.",
        7: "Gegevens over de opneming en de status van de persoonslijst.",
        8: "Gegevens over het verblijf en adres van de ingeschrevene.",
        9: "Gegevens over een kind van de ingeschrevene.",
        10: "Gegevens over de verblijfsrechtelijke status van de ingeschrevene.",
        11: "Gegevens betreffende het gezag over de ingeschrevene.",
        12: "Gegevens over een reisdocument van de ingeschrevene.",
        13: "Gegevens over het kiesrecht van de ingeschrevene.",
        14: "Geeft aan of de persoonslijst onderdeel is van de doelgroep van een afnemer.",
        15: "Aanwijzing op de persoonslijst.",
        16: "Adres waar betrokkene tijdelijk woont tijdens diens verblijf in Nederland.",
        17: "Telefoonnummer en/of e-mailadres waarop betrokkene bereikbaar is.",
        19: "Systeemrubrieken voor peildatums in voorwaarderegels.",
        21: "Gegevens over de eerste of volgende gemeente van inschrijving of de RNI van de ingeschrevene.",
    }

    for cat_nr in actual_cats:
        cat_str = f"{cat_nr:02d}"
        cat_label, hist_nr, cat_uri = CATEGORIES[cat_nr]

        # Section header
        hist_str = f"{hist_nr:02d}" if hist_nr else None
        header = f"Categorie {cat_str}/{hist_str} - {cat_label}" if hist_nr else f"Categorie {cat_str} - {cat_label}"
        lines.append(f"# {'=' * 77}")
        lines.append(f"# {header}")
        lines.append(f"# {'=' * 77}")
        lines.append("")

        # Actual category
        lines.append(f'brpcat:{cat_uri} a brp:Categorie ;')
        lines.append(f'    rdfs:label "{_escape_ttl_string(cat_label)}"@nl ;')
        cat_comment = cat_comments.get(cat_nr)
        if cat_comment:
            lines.append(f'    rdfs:comment "{_escape_ttl_string(cat_comment)}"@nl ;')
        lines.append(f'    skos:notation "{cat_str}" .')
        lines.append("")

        # Historic category
        if hist_nr:
            hist_uri = categorie_to_uri(hist_nr)
            hist_label = CATEGORIES[hist_nr][0]
            lines.append(f'brpcat:{hist_uri} a brp:Categorie ;')
            lines.append(f'    rdfs:label "{_escape_ttl_string(hist_label)}"@nl ;')
            if cat_comment:
                lines.append(f'    rdfs:comment "Historische variant: {_escape_ttl_string(cat_comment.lower())}"@nl ;')
            lines.append(f'    skos:notation "{hist_str}" ;')
            lines.append(f'    brp:historischeVariantVan brpcat:{cat_uri} .')
            lines.append("")

        # Collect groups used in this category
        elements_in_cat = CATEGORY_ELEMENTS[cat_nr]
        groups_in_cat = OrderedDict()
        for gg_ee in elements_in_cat:
            grp_code = gg_ee.split(".")[0]
            if grp_code not in groups_in_cat:
                groups_in_cat[grp_code] = []
            groups_in_cat[grp_code].append(gg_ee)

        # Groups (actual)
        for grp_code in groups_in_cat:
            g_uri = groep_to_uri(cat_nr, grp_code)
            g_notation = f"{cat_str}.{grp_code}"
            g_label = _grp_label(grp_code)
            lines.append(f'brpgrp:{g_uri} a brp:Groep ;')
            lines.append(f'    rdfs:label "{_escape_ttl_string(g_label)}"@nl ;')
            lines.append(f'    skos:notation "{g_notation}" ;')
            lines.append(f'    brp:behoortTotCategorie brpcat:{cat_uri} .')
            lines.append("")

        # Historic groups
        if hist_nr:
            hist_uri = categorie_to_uri(hist_nr)
            for grp_code in groups_in_cat:
                g_uri = groep_to_uri(hist_nr, grp_code)
                g_notation = f"{hist_str}.{grp_code}"
                g_label = _grp_label(grp_code)
                actual_g_uri = groep_to_uri(cat_nr, grp_code)
                lines.append(f'brpgrp:{g_uri} a brp:Groep ;')
                lines.append(f'    rdfs:label "{_escape_ttl_string(g_label)} (historisch)"@nl ;')
                lines.append(f'    skos:notation "{g_notation}" ;')
                lines.append(f'    brp:behoortTotCategorie brpcat:{hist_uri} ;')
                lines.append(f'    brp:historischeVariantVan brpgrp:{actual_g_uri} .')
                lines.append("")

        # Elements (actual)
        lines.append(f"# Elementen {cat_label}")
        lines.append("")
        for gg_ee in elements_in_cat:
            rubrieknummer = f"{cat_str}.{gg_ee}"
            elm_name = rubriek_to_uri(rubrieknummer)
            label = rubriek_to_label(rubrieknummer)
            grp_code = gg_ee.split(".")[0]
            g_uri = groep_to_uri(cat_nr, grp_code)

            lines.append(f'brpelm:{elm_name} a brp:Element ;')
            lines.append(f'    rdfs:label "{_escape_ttl_string(label)}"@nl ;')
            comment = ELEMENT_COMMENTS.get(gg_ee)
            if comment:
                lines.append(f'    rdfs:comment "{_escape_ttl_string(comment)}"@nl ;')
            vt = ELEMENT_VALUE_TYPES.get(gg_ee)
            if vt and vt in VALUE_TYPE_RANGES:
                lines.append(f'    rdfs:range {VALUE_TYPE_RANGES[vt]} ;')
            lines.append(f'    brp:rubrieknummer "{rubrieknummer}" ;')
            lines.append(f'    brp:behoortTotGroep brpgrp:{g_uri} .')
            lines.append("")

        # Elements (historic)
        if hist_nr:
            hist_label = CATEGORIES[hist_nr][0]
            lines.append(f"# Elementen {hist_label}")
            lines.append("")
            for gg_ee in elements_in_cat:
                rubrieknummer = f"{hist_str}.{gg_ee}"
                elm_name = rubriek_to_uri(rubrieknummer)
                label = rubriek_to_label(rubrieknummer)
                grp_code = gg_ee.split(".")[0]
                g_uri = groep_to_uri(hist_nr, grp_code)
                actual_elm = rubriek_to_uri(f"{cat_str}.{gg_ee}")

                lines.append(f'brpelm:{elm_name} a brp:Element ;')
                lines.append(f'    rdfs:label "{_escape_ttl_string(label)}"@nl ;')
                comment = ELEMENT_COMMENTS.get(gg_ee)
                if comment:
                    lines.append(f'    rdfs:comment "{_escape_ttl_string(comment)}"@nl ;')
                vt = ELEMENT_VALUE_TYPES.get(gg_ee)
                if vt and vt in VALUE_TYPE_RANGES:
                    lines.append(f'    rdfs:range {VALUE_TYPE_RANGES[vt]} ;')
                lines.append(f'    brp:rubrieknummer "{rubrieknummer}" ;')
                lines.append(f'    brp:behoortTotGroep brpgrp:{g_uri} ;')
                lines.append(f'    brp:historischeVariantVan brpelm:{actual_elm} .')
                lines.append("")

    return "\n".join(lines)


def main():
    ttl_content = generate()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(ttl_content)

    print(f"Generated {OUTPUT_FILE}")

    # Validate with rdflib
    try:
        import rdflib

        g = rdflib.Graph()
        g.parse(OUTPUT_FILE, format="turtle")
        print(f"Validation OK: {len(g)} triples parsed successfully.")
    except ImportError:
        print("WARNING: rdflib not installed, skipping validation.")
        print("Install with: pip install rdflib")
    except Exception as e:
        print(f"Validation FAILED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
