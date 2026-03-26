"""
Load informatiemodel.ttl as rdflib Graph and provide lookup functions.

This replaces brp_elementen.py — the informatiemodel TTL is now the
single source of truth for element URIs, labels, and value types.
"""

import os

from rdflib import Graph, Literal, URIRef
from namespaces import BRP, BRPELM, BRPRUB, BRPNAT, BRPLAND, BRPVBT, BRPAFN, GEM, RDFS, ODRL

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INFORMATIEMODEL_PATH = os.path.join(BASE_DIR, "ttl", "informatiemodel.ttl")

_graph = None
_uri_cache = {}    # rubrieknummer -> URIRef
_label_cache = {}  # rubrieknummer -> str
_range_cache = {}  # rubrieknummer -> value_type str


# Map rdfs:range classes to value type strings (used by autorisatiebesluiten generator)
_RANGE_TO_VALUE_TYPE = {
    BRP.Gemeente: "gemeente",
    BRP.Nationaliteit: "nationaliteit",
    BRP.Land: "land",
    BRP.VerblijfstitelType: "verblijfstitel",
    BRP.Afnemer: "afnemer",
}


def _ensure_loaded():
    global _graph
    if _graph is not None:
        return

    if not os.path.exists(INFORMATIEMODEL_PATH):
        raise FileNotFoundError(
            f"{INFORMATIEMODEL_PATH} not found. Run generate_informatiemodel.py first."
        )

    _graph = Graph()
    _graph.parse(INFORMATIEMODEL_PATH, format="turtle")

    # Build caches from the graph — iterate all (subject, rubrieknummer) pairs
    # since multiple rubrieken can share the same element URI
    for subj, rub_lit in _graph.subject_objects(predicate=BRP.rubrieknummer):
        rub = str(rub_lit)
        _uri_cache[rub] = subj

        label = _graph.value(subject=subj, predicate=RDFS.label)
        if label:
            _label_cache[rub] = str(label)

        range_cls = _graph.value(subject=subj, predicate=RDFS.range)
        if range_cls and range_cls in _RANGE_TO_VALUE_TYPE:
            _range_cache[rub] = _RANGE_TO_VALUE_TYPE[range_cls]


def elm_ref(rubrieknummer):
    """Get the Rubriek URIRef for a rubrieknummer. Falls back to BRPRUB[rub] if not found."""
    rub = rubrieknummer.split("@")[0] if "@" in rubrieknummer else rubrieknummer
    _ensure_loaded()
    uri = _uri_cache.get(rub)
    if uri:
        return uri
    # Fallback: use raw rubrieknummer as URI
    return BRPRUB[rub]


def elm_label(rubrieknummer):
    """Get the Dutch label for a rubrieknummer."""
    rub = rubrieknummer.split("@")[0] if "@" in rubrieknummer else rubrieknummer
    _ensure_loaded()
    # Try full rubrieknummer first
    label = _label_cache.get(rub)
    if label:
        # Strip category context "(Persoon)" etc. for cleaner constraint comments
        if " (" in label:
            return label[:label.rindex(" (")]
        return label
    return rub


def element_value_type(rubrieknummer):
    """Get the coded value type for a rubrieknummer, or None.

    Returns one of: 'gemeente', 'nationaliteit', 'land', 'verblijfstitel', 'afnemer', or None.
    """
    rub = rubrieknummer.split("@")[0] if "@" in rubrieknummer else rubrieknummer
    _ensure_loaded()

    # Try exact match first
    vt = _range_cache.get(rub)
    if vt:
        return vt

    # Try matching on group.element (GG.EE) part — handles historic categories
    # e.g. "58.09.10" should match same as "08.09.10"
    if len(rub) >= 8 and rub[2] == ".":
        gg_ee = rub[3:]  # strip CC.
        for cached_rub, cached_vt in _range_cache.items():
            if cached_rub.endswith(gg_ee):
                return cached_vt

    return None
