#!/usr/bin/env python3
"""
Generate autorisatiebesluiten-compact.ttl — compact variant.

Same as autorisatiebesluiten.ttl but replaces odrl:target lists with
brpgrp: or brpcat: references when ALL elements in a group or category
are present. This makes the output much shorter but creates a dependency
on the informatiemodel definitions.

NOTE: This is a variant for discussion with the werkgroep. Changes to
group/category definitions in the informatiemodel would silently change
what elements are authorized.
"""

import os
import sys

from rdflib import Graph, URIRef

from namespaces import BRP, BRPELM, BRPGRP, BRPCAT, ODRL, RDF

# Import the main generator — we reuse everything except target writing
import generate_autorisatiebesluiten as gen

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH = os.path.join(BASE_DIR, "ttl", "autorisatiebesluiten-compact.ttl")
INFORMATIEMODEL_PATH = os.path.join(BASE_DIR, "ttl", "informatiemodel.ttl")


def _build_group_index():
    """Build index using odrl:partOf: group -> rubrieken, category -> rubrieken."""
    im = Graph()
    im.parse(INFORMATIEMODEL_PATH, format="turtle")

    # group -> rubrieken (via odrl:partOf)
    grp_elements = {}
    for rub in im.subjects(predicate=RDF.type, object=BRP.Rubriek):
        grp = im.value(subject=rub, predicate=ODRL.partOf)
        if grp:
            grp_elements.setdefault(grp, set()).add(rub)

    # category -> groups (via odrl:partOf on groups)
    cat_groups = {}
    for grp in im.subjects(predicate=RDF.type, object=BRP.Groep):
        cat = im.value(subject=grp, predicate=ODRL.partOf)
        if cat:
            cat_groups.setdefault(cat, set()).add(grp)

    # category -> all rubrieken (union of all groups)
    cat_elements = {}
    for cat, groups in cat_groups.items():
        elms = set()
        for grp in groups:
            elms.update(grp_elements.get(grp, set()))
        cat_elements[cat] = elms

    return grp_elements, cat_elements, cat_groups


def _compact_targets(targets, grp_elements, cat_elements, cat_groups):
    """Replace target element sets with group/category URIs where possible.

    Returns a new set of target URIs (mix of elements, groups, categories).
    """
    remaining = set(targets)
    result = set()

    # First try categories (biggest reduction)
    for cat, cat_elms in sorted(cat_elements.items(), key=lambda x: -len(x[1])):
        if cat_elms and cat_elms.issubset(remaining):
            result.add(cat)
            remaining -= cat_elms

    # Then try groups
    for grp, grp_elms in sorted(grp_elements.items(), key=lambda x: -len(x[1])):
        if grp_elms and grp_elms.issubset(remaining):
            result.add(grp)
            remaining -= grp_elms

    # Keep remaining individual elements
    result.update(remaining)
    return result


def main():
    print("Building group/category index from informatiemodel...")
    grp_elements, cat_elements, cat_groups = _build_group_index()
    print(f"  {len(grp_elements)} groups, {len(cat_elements)} categories indexed")

    # Generate the normal autorisatiebesluiten graph
    print("\nReading Tabel 35...")
    data = gen._read_tabel35()

    all_afnemers = {}
    for row in data:
        afn = row[gen.COL_AFN_IND]
        if afn is not None:
            all_afnemers.setdefault(afn, []).append(row)

    print(f"  {len(all_afnemers)} afnemers, {sum(len(r) for r in all_afnemers.values())} tabelregels")

    print(f"\nGenerating {OUTPUT_PATH}...")
    parse_ok, parse_fail = gen.generate_autorisatiebesluiten(all_afnemers)
    print(f"  Voorwaarderegels parsed: {parse_ok} OK, {parse_fail} failed")

    # Load the generated graph and ensure all namespace bindings
    print("\nLoading generated graph for compaction...")
    from namespaces import new_graph, save
    g = new_graph()
    g.parse(os.path.join(BASE_DIR, "ttl", "autorisatiebesluiten-actueel.ttl"), format="turtle")
    original_triples = len(g)

    # Find all permissions and compact their targets
    compacted = 0
    removed = 0
    added = 0

    for perm in g.subjects(predicate=RDF.type, object=ODRL.Permission):
        targets = set(g.objects(subject=perm, predicate=ODRL.target))
        if not targets:
            continue

        compact = _compact_targets(targets, grp_elements, cat_elements, cat_groups)

        if compact != targets:
            # Remove old targets
            for t in targets:
                g.remove((perm, ODRL.target, t))
                removed += 1
            # Add compacted targets
            for t in compact:
                g.add((perm, ODRL.target, t))
                added += 1
            compacted += 1

    print(f"  Compacted {compacted} permissions")
    print(f"  Removed {removed} element targets, added {added} group/category targets")
    print(f"  {original_triples} -> {len(g)} triples ({original_triples - len(g)} fewer)")

    from namespaces import save
    save(g, OUTPUT_PATH)
    print(f"Generated {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
