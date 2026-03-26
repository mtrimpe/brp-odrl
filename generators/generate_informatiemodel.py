#!/usr/bin/env python3
"""Generate informatiemodel.ttl from brp_elementen module.

Produces a complete Turtle file with all BRP categories, groups, and elements
using meaningful URI names from brp_elementen.rubriek_to_uri().
"""

import os
from collections import OrderedDict

from rdflib import Literal, URIRef
from rdflib.namespace import XSD

from namespaces import (
    new_graph, save,
    BRP, BRPCAT, BRPGRP, BRPELM, BRPRUB,
    RDF, RDFS, SKOS, ODRL,
)
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
    "gemeente": BRP.Gemeente,
    "nationaliteit": BRP.Nationaliteit,
    "land": BRP.Land,
    "verblijfstitel": BRP.VerblijfstitelType,
    "afnemer": BRP.Afnemer,
}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_FILE = os.path.join(BASE_DIR, "ttl", "informatiemodel.ttl")

# Category comments (from LO-BRP paragraph 4.4)
CAT_COMMENTS = {
    "1": "Gegevens over de ingeschrevene.",
    "2": "Gegevens over de ouder1 van de ingeschrevene.",
    "3": "Gegevens over de ouder2 van de ingeschrevene.",
    "4": "Gegevens over een nationaliteit van de ingeschrevene.",
    "5": "Gegevens over een gesloten of ontbonden huwelijk of geregistreerd partnerschap van de ingeschrevene.",
    "6": "Gegevens over het overlijden van de ingeschrevene.",
    "7": "Gegevens over de opneming en de status van de persoonslijst.",
    "8": "Gegevens over het verblijf en adres van de ingeschrevene.",
    "9": "Gegevens over een kind van de ingeschrevene.",
    "10": "Gegevens over de verblijfsrechtelijke status van de ingeschrevene.",
    "11": "Gegevens betreffende het gezag over de ingeschrevene.",
    "12": "Gegevens over een reisdocument van de ingeschrevene.",
    "13": "Gegevens over het kiesrecht van de ingeschrevene.",
    "14": "Geeft aan of de persoonslijst onderdeel is van de doelgroep van een afnemer.",
    "15": "Aanwijzing op de persoonslijst.",
    "16": "Adres waar betrokkene tijdelijk woont tijdens diens verblijf in Nederland.",
    "17": "Telefoonnummer en/of e-mailadres waarop betrokkene bereikbaar is.",
    "19": "Systeemrubrieken voor peildatums in voorwaarderegels.",
    "21": "Gegevens over de eerste of volgende gemeente van inschrijving of de RNI van de ingeschrevene.",
    "PA": "Actuele persoonsgegevens als afgeleide informatieproducten via de BRP API (LO-BRP §5.3.12).",
    "PH": "Historische persoonsgegevens als afgeleide informatieproducten via de BRP API.",
    "PX": "Persoonsgegevens (actueel en historisch) als informatieproducten via de BRP API, waaronder verblijfplaatshistorie (LO-BRP §5.3.14).",
    "AX": "Adresgegevens over een periode als informatieproducten via de BRP API (LO-BRP §5.3.11).",
}


def _grp_label(grp_code):
    """Return the Dutch label for a group code."""
    entry = GROUPS.get(grp_code)
    return entry[0] if entry else f"Groep {grp_code}"


def _sorted_actual_categories():
    """Return actual (non-historic) category numbers in sorted order."""
    return sorted(cat for cat in CATEGORY_ELEMENTS.keys())


def _cat_str(cat_nr):
    """Format a category key. Numeric cats get zero-padded."""
    s = str(cat_nr)
    return s.zfill(2) if s.isdigit() else s


def _ensure_abstract_element(g, gg_ee):
    """Add the abstract Element (GG.EE) if not already present."""
    label_text, base_name = ELEMENTS[gg_ee]
    subj = BRPELM[base_name]
    # Only add once (rdflib handles duplicates, but this is cleaner)
    if (subj, RDF.type, BRP.Element) not in g:
        g.add((subj, RDF.type, BRP.Element))
        g.add((subj, RDFS.label, Literal(label_text, lang="nl")))
        comment = ELEMENT_COMMENTS.get(gg_ee)
        if comment:
            g.add((subj, RDFS.comment, Literal(comment, lang="nl")))
        vt = ELEMENT_VALUE_TYPES.get(gg_ee)
        if vt and vt in VALUE_TYPE_RANGES:
            g.add((subj, RDFS.range, VALUE_TYPE_RANGES[vt]))
    return subj


def _add_rubriek(g, cat_nr, gg_ee, hist_nr=None):
    """Add a Rubriek (CC.GG.EE) linking to its abstract Element."""
    is_historic = hist_nr is not None
    use_nr = hist_nr if is_historic else cat_nr
    rubrieknummer = f"{_cat_str(use_nr)}.{gg_ee}"
    rub_name = rubriek_to_uri(rubrieknummer)
    label = rubriek_to_label(rubrieknummer)
    grp_code = gg_ee.split(".")[0]
    g_uri = groep_to_uri(use_nr, grp_code)

    # The abstract element
    elm_subj = _ensure_abstract_element(g, gg_ee)

    # The concrete rubriek (also an ODRL Asset via partOf)
    rub_subj = BRPRUB[rub_name]
    g.add((rub_subj, RDF.type, BRP.Rubriek))
    g.add((rub_subj, RDFS.label, Literal(label, lang="nl")))
    g.add((rub_subj, BRP.rubrieknummer, Literal(rubrieknummer)))
    g.add((rub_subj, BRP.element, elm_subj))
    g.add((rub_subj, BRP.behoortTotGroep, BRPGRP[g_uri]))
    g.add((rub_subj, ODRL.partOf, BRPGRP[g_uri]))

    if is_historic:
        actual_rub = rubriek_to_uri(f"{_cat_str(cat_nr)}.{gg_ee}")
        g.add((rub_subj, BRP.historischeVariantVan, BRPRUB[actual_rub]))


def generate():
    """Generate the complete informatiemodel graph."""
    g = new_graph()
    actual_cats = _sorted_actual_categories()

    for cat_nr in actual_cats:
        cat_s = _cat_str(cat_nr)
        cat_label, hist_nr, cat_uri = CATEGORIES[cat_nr]

        # Actual category (also an AssetCollection for ODRL targets)
        cat_subj = BRPCAT[cat_uri]
        g.add((cat_subj, RDF.type, BRP.Categorie))
        g.add((cat_subj, RDF.type, ODRL.AssetCollection))
        g.add((cat_subj, RDFS.label, Literal(cat_label, lang="nl")))
        cat_comment = CAT_COMMENTS.get(cat_nr)
        if cat_comment:
            g.add((cat_subj, RDFS.comment, Literal(cat_comment, lang="nl")))
        g.add((cat_subj, SKOS.notation, Literal(cat_s)))

        # Historic category
        if hist_nr:
            hist_s = _cat_str(hist_nr)
            hist_uri = categorie_to_uri(hist_nr)
            hist_label = CATEGORIES[hist_nr][0]
            hist_subj = BRPCAT[hist_uri]
            g.add((hist_subj, RDF.type, BRP.Categorie))
            g.add((hist_subj, RDF.type, ODRL.AssetCollection))
            g.add((hist_subj, RDFS.label, Literal(hist_label, lang="nl")))
            if cat_comment:
                g.add((hist_subj, RDFS.comment, Literal(f"Historische variant: {cat_comment.lower()}", lang="nl")))
            g.add((hist_subj, SKOS.notation, Literal(hist_s)))
            g.add((hist_subj, BRP.historischeVariantVan, cat_subj))

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
            g_notation = f"{cat_s}.{grp_code}"
            g_label = _grp_label(grp_code)
            grp_subj = BRPGRP[g_uri]
            g.add((grp_subj, RDF.type, BRP.Groep))
            g.add((grp_subj, RDF.type, ODRL.AssetCollection))
            g.add((grp_subj, RDFS.label, Literal(g_label, lang="nl")))
            g.add((grp_subj, SKOS.notation, Literal(g_notation)))
            g.add((grp_subj, BRP.behoortTotCategorie, cat_subj))
            g.add((grp_subj, ODRL.partOf, cat_subj))

        # Historic groups
        if hist_nr:
            hist_s = _cat_str(hist_nr)
            hist_cat_subj = BRPCAT[categorie_to_uri(hist_nr)]
            for grp_code in groups_in_cat:
                g_uri = groep_to_uri(hist_nr, grp_code)
                g_notation = f"{hist_s}.{grp_code}"
                g_label = _grp_label(grp_code)
                actual_g_uri = groep_to_uri(cat_nr, grp_code)
                grp_subj = BRPGRP[g_uri]
                g.add((grp_subj, RDF.type, BRP.Groep))
                g.add((grp_subj, RDF.type, ODRL.AssetCollection))
                g.add((grp_subj, RDFS.label, Literal(f"{g_label} (historisch)", lang="nl")))
                g.add((grp_subj, SKOS.notation, Literal(g_notation)))
                g.add((grp_subj, BRP.behoortTotCategorie, hist_cat_subj))
                g.add((grp_subj, ODRL.partOf, hist_cat_subj))
                g.add((grp_subj, BRP.historischeVariantVan, BRPGRP[actual_g_uri]))

        # Elements (actual)
        for gg_ee in elements_in_cat:
            _add_rubriek(g, cat_nr, gg_ee)

        # Rubrieken (historic)
        if hist_nr:
            for gg_ee in elements_in_cat:
                _add_rubriek(g, cat_nr, gg_ee, hist_nr)

    return g


def _serialize_structured(g, path):
    """Write informatiemodel as structured Turtle with section comments."""
    from rdflib import Graph
    from rdflib.plugins.serializers.turtle import TurtleSerializer
    import io

    # Collect subjects by type for ordering
    categories = {}  # cat_uri -> cat_subj
    groups_by_cat = {}  # cat_subj -> [(grp_uri, grp_subj)]
    elements_by_grp = {}  # grp_subj -> [elm_subj]
    api_products = []

    for subj in g.subjects(predicate=RDF.type, object=BRP.Categorie):
        uri_name = str(subj).split("/")[-1]
        categories[uri_name] = subj

    for subj in g.subjects(predicate=RDF.type, object=BRP.Groep):
        cat = g.value(subj, BRP.behoortTotCategorie)
        if cat:
            groups_by_cat.setdefault(cat, []).append(subj)

    for subj in g.subjects(predicate=RDF.type, object=BRP.Rubriek):
        grp = g.value(subj, BRP.behoortTotGroep)
        if grp:
            elements_by_grp.setdefault(grp, []).append(subj)

    # Abstract elements (not rubrieken) for a separate section
    abstract_elements = []
    for subj in g.subjects(predicate=RDF.type, object=BRP.Element):
        if (subj, RDF.type, BRP.Rubriek) not in g:
            abstract_elements.append(subj)

    # Helper: serialize one subject's triples as Turtle fragment
    def _subject_turtle(subj):
        """Extract all triples for a subject and serialize as Turtle."""
        mini = Graph()
        for ns, uri in g.namespaces():
            mini.bind(ns, uri)
        for p, o in g.predicate_objects(subj):
            mini.add((subj, p, o))
        buf = io.BytesIO()
        mini.serialize(buf, format="turtle")
        text = buf.getvalue().decode("utf-8")
        # Strip prefix declarations (we'll write them once at the top)
        lines = []
        for line in text.split("\n"):
            if line.startswith("@prefix") or not line.strip():
                continue
            lines.append(line)
        return "\n".join(lines).strip()

    # Write the file
    with open(path, "w", encoding="utf-8") as f:
        # Prefixes
        buf = io.BytesIO()
        g.serialize(buf, format="turtle")
        full = buf.getvalue().decode("utf-8")
        for line in full.split("\n"):
            if line.startswith("@prefix"):
                f.write(line + "\n")
        f.write("\n")

        # Header
        f.write("# " + "=" * 77 + "\n")
        f.write("# BRP Informatiemodel\n")
        f.write("#\n")
        f.write("# Categorieën, groepen en elementen van de Basisregistratie Personen.\n")
        f.write("# Gebaseerd op het Logisch Ontwerp BRP 2024.Q2, Deel 4.\n")
        f.write("# " + "=" * 77 + "\n\n")

        # Sort categories: actual first, then historic
        actual_cats = _sorted_actual_categories()

        for cat_nr in actual_cats:
            cat_label, hist_nr, cat_uri_name = CATEGORIES[cat_nr]
            cat_subj = BRPCAT[cat_uri_name]
            if cat_subj not in categories.values():
                continue

            # Category section header
            hist_str = f"/{_cat_str(hist_nr)}" if hist_nr else ""
            f.write("\n# " + "=" * 77 + "\n")
            f.write(f"# Categorie {_cat_str(cat_nr)}{hist_str} — {cat_label}\n")
            cat_comment = CAT_COMMENTS.get(cat_nr, "")
            if cat_comment:
                f.write(f"#\n# {cat_comment}\n")
            f.write("# " + "=" * 77 + "\n\n")

            # Category definition
            f.write(_subject_turtle(cat_subj) + "\n\n")

            # Historic category
            if hist_nr:
                hist_uri_name = categorie_to_uri(hist_nr)
                hist_subj = BRPCAT[hist_uri_name]
                if hist_subj in categories.values():
                    f.write(_subject_turtle(hist_subj) + "\n\n")

            # Groups and their elements
            cat_groups = groups_by_cat.get(cat_subj, [])
            # Sort groups by notation
            cat_groups.sort(key=lambda s: str(g.value(s, SKOS.notation) or ""))

            for grp_subj in cat_groups:
                grp_label = str(g.value(grp_subj, RDFS.label) or "")
                grp_notation = str(g.value(grp_subj, SKOS.notation) or "")

                f.write(f"# --- Groep {grp_notation}: {grp_label} ---\n\n")
                f.write(_subject_turtle(grp_subj) + "\n\n")

                # Elements in this group
                elms = elements_by_grp.get(grp_subj, [])
                elms.sort(key=lambda s: str(g.value(s, BRP.rubrieknummer) or ""))
                for elm_subj in elms:
                    f.write(_subject_turtle(elm_subj) + "\n\n")

            # Historic groups and elements
            if hist_nr:
                hist_uri_name = categorie_to_uri(hist_nr)
                hist_subj = BRPCAT[hist_uri_name]
                hist_groups = groups_by_cat.get(hist_subj, [])
                hist_groups.sort(key=lambda s: str(g.value(s, SKOS.notation) or ""))

                if hist_groups:
                    f.write(f"# --- Historische groepen (categorie {_cat_str(hist_nr)}) ---\n\n")
                    for grp_subj in hist_groups:
                        f.write(_subject_turtle(grp_subj) + "\n\n")
                        elms = elements_by_grp.get(grp_subj, [])
                        elms.sort(key=lambda s: str(g.value(s, BRP.rubrieknummer) or ""))
                        for elm_subj in elms:
                            f.write(_subject_turtle(elm_subj) + "\n\n")

        # Abstracte elementen (de GG.EE concepten)
        if abstract_elements:
            f.write("\n# " + "=" * 77 + "\n")
            f.write("# Abstracte elementen\n")
            f.write("#\n")
            f.write("# De elementdefinities (GG.EE) waarvan de rubrieken (CC.GG.EE)\n")
            f.write("# categorie-specifieke instanties zijn.\n")
            f.write("# " + "=" * 77 + "\n\n")
            abstract_elements.sort(key=lambda s: str(g.value(s, RDFS.label) or ""))
            for elm_subj in abstract_elements:
                f.write(_subject_turtle(elm_subj) + "\n\n")

    print(f"  {path}: {len(g)} triples")


def main():
    g = generate()
    _serialize_structured(g, OUTPUT_FILE)
    print(f"Generated {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
