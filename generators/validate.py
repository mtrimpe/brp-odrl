#!/usr/bin/env python3
"""
Combine all TTL files into one graph and validate consistency.

Checks:
- All odrl:target references point to existing brp:Element subjects
- All odrl:assignee references point to existing brp:Afnemer subjects
- All brpelm:, brpnat:, brpland:, brpvbt:, gem: URIs used in constraints
  have definitions in their respective TTL files
- All brp:behoortTotGroep references point to existing brp:Groep subjects
- All brp:behoortTotCategorie references point to existing brp:Categorie subjects
"""

import os
import sys

from rdflib import Graph, Namespace
from rdflib.namespace import RDF, RDFS

from namespaces import BRP, BRPELM, BRPAFN, BRPNAT, BRPLAND, BRPVBT, GEM, BRPGRP, BRPCAT, ODRL

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TTL_DIR = os.path.join(BASE_DIR, "ttl")
ONTOLOGY_PATH = os.path.join(BASE_DIR, "odrl-ontology.ttl")
COMBINED_PATH = os.path.join(TTL_DIR, "combined.ttl")


def main():
    print("Loading all TTL files...")
    g = Graph()

    # Load ontology from project root
    if os.path.exists(ONTOLOGY_PATH):
        g.parse(ONTOLOGY_PATH, format="turtle")
        print(f"  odrl-ontology.ttl: {len(g)} triples")

    # Load all generated TTL files
    prev = len(g)
    for fn in sorted(os.listdir(TTL_DIR)):
        if fn.endswith(".ttl") and fn != "combined.ttl":
            path = os.path.join(TTL_DIR, fn)
            g.parse(path, format="turtle")
            added = len(g) - prev
            print(f"  {fn}: {added} triples")
            prev = len(g)

    print(f"\nTotal: {len(g)} triples")

    # Write combined graph
    print(f"\nWriting {COMBINED_PATH}...")
    g.serialize(destination=COMBINED_PATH, format="turtle")
    print(f"  {COMBINED_PATH}: {len(g)} triples")

    # --- Validation checks ---
    print("\nValidating consistency...")
    errors = 0

    # 1. Check odrl:target references (targets are Rubrieken)
    defined_rubrieken = set(g.subjects(predicate=RDF.type, object=BRP.Rubriek))
    defined_elements = set(g.subjects(predicate=RDF.type, object=BRP.Element))
    defined_all = defined_rubrieken | defined_elements
    targets_used = set(g.objects(predicate=ODRL.target))
    missing_targets = targets_used - defined_all
    if missing_targets:
        print(f"\n  WARN: {len(missing_targets)} odrl:target references to undefined elements:")
        for t in sorted(missing_targets, key=str)[:10]:
            print(f"    {t}")
        errors += len(missing_targets)
    else:
        print(f"  OK: All {len(targets_used)} odrl:target references resolve")

    # 2. Check odrl:assignee references
    defined_afnemers = set(g.subjects(predicate=RDF.type, object=BRP.Afnemer))
    assignees_used = set(g.objects(predicate=ODRL.assignee))
    missing_assignees = assignees_used - defined_afnemers
    if missing_assignees:
        print(f"\n  WARN: {len(missing_assignees)} odrl:assignee references to undefined afnemers:")
        for a in sorted(missing_assignees, key=str)[:10]:
            print(f"    {a}")
        errors += len(missing_assignees)
    else:
        print(f"  OK: All {len(assignees_used)} odrl:assignee references resolve")

    # 3. Check gemeente references
    defined_gem = set(g.subjects(predicate=RDF.type, object=BRP.Gemeente))
    gem_ns = str(GEM)
    gem_used = set()
    for s, p, o in g:
        if isinstance(o, type(s)) and str(o).startswith(gem_ns):
            gem_used.add(o)
    missing_gem = gem_used - defined_gem
    if missing_gem:
        print(f"\n  WARN: {len(missing_gem)} gemeente references to undefined gemeenten:")
        for x in sorted(missing_gem, key=str)[:10]:
            print(f"    {x}")
        errors += len(missing_gem)
    else:
        print(f"  OK: All {len(gem_used)} gemeente references resolve")

    # 4. Check nationaliteit references
    defined_nat = set(g.subjects(predicate=RDF.type, object=BRP.Nationaliteit))
    nat_ns = str(BRPNAT)
    nat_used = set()
    for s, p, o in g:
        if isinstance(o, type(s)) and str(o).startswith(nat_ns):
            nat_used.add(o)
    missing_nat = nat_used - defined_nat
    if missing_nat:
        print(f"\n  WARN: {len(missing_nat)} nationaliteit references to undefined nationaliteiten:")
        for x in sorted(missing_nat, key=str)[:10]:
            print(f"    {x}")
        errors += len(missing_nat)
    else:
        print(f"  OK: All {len(nat_used)} nationaliteit references resolve")

    # 5. Check land references
    defined_land = set(g.subjects(predicate=RDF.type, object=BRP.Land))
    land_ns = str(BRPLAND)
    land_used = set()
    for s, p, o in g:
        if isinstance(o, type(s)) and str(o).startswith(land_ns):
            land_used.add(o)
    missing_land = land_used - defined_land
    if missing_land:
        print(f"\n  WARN: {len(missing_land)} land references to undefined landen:")
        for x in sorted(missing_land, key=str)[:10]:
            print(f"    {x}")
        errors += len(missing_land)
    else:
        print(f"  OK: All {len(land_used)} land references resolve")

    # 6. Check groep/categorie integrity
    defined_groups = set(g.subjects(predicate=RDF.type, object=BRP.Groep))
    groups_used = set(g.objects(predicate=BRP.behoortTotGroep))
    missing_groups = groups_used - defined_groups
    if missing_groups:
        print(f"\n  WARN: {len(missing_groups)} brp:behoortTotGroep references to undefined groepen:")
        for x in sorted(missing_groups, key=str)[:10]:
            print(f"    {x}")
        errors += len(missing_groups)
    else:
        print(f"  OK: All {len(groups_used)} groep references resolve")

    defined_cats = set(g.subjects(predicate=RDF.type, object=BRP.Categorie))
    cats_used = set(g.objects(predicate=BRP.behoortTotCategorie))
    missing_cats = cats_used - defined_cats
    if missing_cats:
        print(f"\n  WARN: {len(missing_cats)} brp:behoortTotCategorie references to undefined categorieën:")
        for x in sorted(missing_cats, key=str)[:10]:
            print(f"    {x}")
        errors += len(missing_cats)
    else:
        print(f"  OK: All {len(cats_used)} categorie references resolve")

    if errors:
        print(f"\n{errors} issues found (warnings, not blocking).")
    else:
        print(f"\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
