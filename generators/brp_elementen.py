"""
BRP Elementen - Loads BRP category/group/element data from CSV files.

All data lives in ../data/*.csv. This module provides lookup functions
for converting rubrieken to meaningful URI names, labels, etc.
"""

import csv
import os

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def _load_csv(filename):
    path = os.path.join(_DATA_DIR, filename)
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

def _load_categories():
    cats = {}
    hist_to_actual = {}
    suffix_map = {}
    for row in _load_csv("categories.csv"):
        nr = int(row["nr"])
        hist = int(row["historic_nr"]) if row["historic_nr"] else None
        cats[nr] = (row["label"], hist, row["uri_name"])
        suffix_map[nr] = row["suffix"]
        if hist:
            hist_to_actual[hist] = nr
    return cats, hist_to_actual, suffix_map


def _load_groups():
    groups = {}
    for row in _load_csv("groups.csv"):
        groups[row["code"]] = (row["label"], row["uri_fragment"])
    return groups


def _load_elements():
    elements = {}
    value_types = {}
    comments = {}
    for row in _load_csv("elements.csv"):
        gg_ee = row["gg_ee"]
        elements[gg_ee] = (row["label"], row["uri_name"])
        if row["value_type"]:
            value_types[gg_ee] = row["value_type"]
        if row["comment"]:
            comments[gg_ee] = row["comment"]
    return elements, value_types, comments


def _load_category_elements():
    cat_elms = {}
    for row in _load_csv("category_elements.csv"):
        nr = int(row["cat_nr"])
        cat_elms.setdefault(nr, []).append(row["gg_ee"])
    return cat_elms


CATEGORIES, _HISTORIC_TO_ACTUAL, _CATEGORY_SUFFIX = _load_categories()
GROUPS = _load_groups()
ELEMENTS, ELEMENT_VALUE_TYPES, ELEMENT_COMMENTS = _load_elements()
CATEGORY_ELEMENTS = _load_category_elements()

_ACTUAL_TO_HISTORIC = {v: k for k, v in _HISTORIC_TO_ACTUAL.items()}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def categorie_to_uri(cat_nr):
    return CATEGORIES[cat_nr][2]


def groep_to_uri(cat_nr, grp_code):
    cat_uri = categorie_to_uri(cat_nr)
    grp_uri = GROUPS[grp_code][1]
    return f"{cat_uri}-{grp_uri}"


def element_value_type(rubrieknummer):
    base = rubrieknummer.split("@")[0] if "@" in rubrieknummer else rubrieknummer
    gg_ee = base[3:] if len(base) > 5 else base
    return ELEMENT_VALUE_TYPES.get(gg_ee)


def _is_historic(cat_nr):
    return cat_nr in _HISTORIC_TO_ACTUAL


def _actual_category(cat_nr):
    return _HISTORIC_TO_ACTUAL.get(cat_nr, cat_nr)


def _category_suffix(cat_nr):
    actual = _actual_category(cat_nr)
    suffix = _CATEGORY_SUFFIX.get(actual, "")
    if _is_historic(cat_nr):
        suffix += "Hist"
    return suffix


def rubriek_to_uri(rubrieknummer):
    parts = rubrieknummer.split(".")
    if len(parts) != 3:
        raise ValueError(f"Invalid rubrieknummer: {rubrieknummer}")
    cat_nr = int(parts[0])
    gg_ee = f"{parts[1]}.{parts[2]}"
    if gg_ee not in ELEMENTS:
        raise KeyError(f"Unknown element: {gg_ee}")
    _, base_name = ELEMENTS[gg_ee]
    return base_name + _category_suffix(cat_nr)


def rubriek_to_label(rubrieknummer):
    parts = rubrieknummer.split(".")
    if len(parts) != 3:
        raise ValueError(f"Invalid rubrieknummer: {rubrieknummer}")
    cat_nr = int(parts[0])
    gg_ee = f"{parts[1]}.{parts[2]}"
    if gg_ee not in ELEMENTS:
        raise KeyError(f"Unknown element: {gg_ee}")
    label, _ = ELEMENTS[gg_ee]
    actual = _actual_category(cat_nr)
    cat_label = CATEGORIES[actual][0] if actual in CATEGORIES else f"Categorie {actual}"
    if _is_historic(cat_nr):
        return f"{label} ({cat_label}, historisch)"
    return f"{label} ({cat_label})"


def all_rubrieken():
    result = []
    for cat_nr, elements in CATEGORY_ELEMENTS.items():
        cat_str = f"{cat_nr:02d}"
        for gg_ee in elements:
            result.append(f"{cat_str}.{gg_ee}")
        if cat_nr in _ACTUAL_TO_HISTORIC:
            hist_str = f"{_ACTUAL_TO_HISTORIC[cat_nr]:02d}"
            for gg_ee in elements:
                result.append(f"{hist_str}.{gg_ee}")
    return sorted(result)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    rubrieken = all_rubrieken()
    print(f"Total rubrieken: {len(rubrieken)}")
    errors = []
    for r in rubrieken:
        try:
            rubriek_to_uri(r)
            rubriek_to_label(r)
        except (KeyError, ValueError) as e:
            errors.append((r, str(e)))
    if errors:
        print(f"Errors: {len(errors)}")
        for r, e in errors:
            print(f"  {r}: {e}")
    else:
        print("All rubrieken convert successfully.")
    print(f"Categories: {len(CATEGORIES)}")
    print(f"Groups: {len(GROUPS)}")
    print(f"Elements: {len(ELEMENTS)}")
    print(f"Value types: {len(ELEMENT_VALUE_TYPES)}")
    print(f"Comments: {len(ELEMENT_COMMENTS)}")
