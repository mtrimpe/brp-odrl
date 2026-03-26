#!/usr/bin/env python3
"""
Generate brp-autorisatiebesluiten.ttl from Tabel 35 Excel.

Uses the ODRL Temporal Profile (tpl:) for versioning of autorisatiebesluiten.
Includes a full parser for BRP voorwaarderegel syntax (LO-BRP §3.1.3) that
generates ODRL 2.2 constraints (Constraint and LogicalConstraint).

Covers ALL 12,270 rows / 2,617 afnemers in Tabel 35.
Also generates a DCAT-AP-NL catalogus entry.

URI pattern: brpaut:{afnemersindicatie}-v{versie}
"""

import csv
import os
import re
import sys

from rdflib import BNode, Literal, URIRef
from rdflib.collection import Collection

import informatiemodel_graph as im
from namespaces import (
    new_graph, save,
    BRP, BRPAFN, BRPAUT, BRPNAT, BRPLAND, BRPVBT,
    GEM, ODRL, TPL, RDF, RDFS, XSD, DCTERMS, PROV,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, "csv", "tabel35_autorisatietabel.csv")
OUTPUT_PATH_ACTUEEL = os.path.join(BASE_DIR, "ttl", "autorisatiebesluiten-actueel.ttl")
OUTPUT_PATH_HISTORISCH = os.path.join(BASE_DIR, "ttl", "autorisatiebesluiten-historisch.ttl")

# Column indices (0-based) from the Excel headers
COL_VERSIE = 0
COL_AFN_IND = 1
COL_AFN_NAAM = 2
COL_INGANG = 3
COL_EINDE = 4
COL_AANTEKENING = 5
COL_GEHEIM = 6
COL_VERSTR_BEP = 7
COL_BIJZ_KIND = 8
COL_RUB_SPONT = 9
COL_VWR_SPONT = 10
COL_SLEUTEL = 11
COL_COND_VERSTR = 12
COL_MED_SPONT = 13
COL_RUB_SEL = 14
COL_VWR_SEL = 15
COL_SEL_SOORT = 16
COL_BER_AAND = 17
COL_EERSTE_SEL = 18
COL_SEL_PERIODE = 19
COL_MED_SEL = 20
COL_RUB_ADHOC = 21
COL_VWR_ADHOC = 22
COL_PLAATSING = 23
COL_AFN_VERSTR = 24
COL_ADRESVRAAG = 25
COL_MED_ADHOC = 26


# =============================================================================
# Lookup tabellen voor leesbare labels bij coded values
# =============================================================================

_LABEL_CACHE = {}


def _load_labels():
    """Load label lookup tables from CSV files and Excel."""
    if _LABEL_CACHE:
        return

    import csv

    def read_csv(path):
        with open(path, "rb") as f:
            raw = f.read(4)
        enc = "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8"
        try:
            open(path, encoding=enc).read()
        except UnicodeDecodeError:
            enc = "latin-1"
        with open(path, encoding=enc, newline="") as f:
            return [r for r in csv.reader(f) if any(c.strip() for c in r)]

    csv_dir = f"{BASE_DIR}/csv"

    # Tabel 32: Nationaliteit
    nat = {}
    for row in read_csv(f"{csv_dir}/tabel32_nationaliteit.csv")[1:]:
        if len(row) >= 2 and row[0].strip():
            nat[row[0].strip()] = row[1].strip()
    _LABEL_CACHE["nationaliteit"] = nat

    # Tabel 34: Land
    land = {}
    for row in read_csv(f"{csv_dir}/tabel34_land.csv")[1:]:
        if len(row) >= 2 and row[0].strip():
            land[row[0].strip()] = row[1].strip()
    _LABEL_CACHE["land"] = land

    # Tabel 56: Verblijfstitel
    vbt = {}
    for row in read_csv(f"{csv_dir}/tabel56_verblijfstitel.csv")[1:]:
        if len(row) >= 2 and row[0].strip():
            vbt[row[0].strip()] = row[1].strip()
    _LABEL_CACHE["verblijfstitel"] = vbt

    # Afnemers uit Tabel 35 CSV
    afn = {}
    for row in read_csv(f"{csv_dir}/tabel35_autorisatietabel.csv")[1:]:
        if len(row) > COL_AFN_NAAM and row[COL_AFN_IND].strip():
            afn[row[COL_AFN_IND].strip()] = row[COL_AFN_NAAM].strip()
    _LABEL_CACHE["afnemer"] = afn

    # Tabel 33: Gemeente
    gem = {}
    for row in read_csv(f"{csv_dir}/tabel33_gemeente.csv")[1:]:
        if len(row) >= 2 and row[0].strip():
            gem[row[0].strip()] = row[1].strip()
    _LABEL_CACHE["gemeente"] = gem


def _lookup_label(value, value_type):
    """Look up a human-readable label for a coded value."""
    _load_labels()
    table = _LABEL_CACHE.get(value_type, {})
    label = table.get(str(value).strip())
    if label:
        return f"{value} ({label})"
    return str(value)


# Operator mapping: BRP operator -> (brp: ODRL Operator URIRef, Dutch description)
OPERATOR_MAP = {
    "GA1": (BRP.ga1, "gelijk aan"),
    "GAA": (BRP.gaa, "gelijk aan (alle voorkomens)"),
    "OGA1": (BRP.oga1, "ongelijk aan"),
    "OGAA": (BRP.ogaa, "ongelijk aan (alle voorkomens)"),
    "GD1": (BRP.gd1, "groter dan"),
    "KD1": (BRP.kd1, "kleiner dan"),
    "KDA": (BRP.kda, "kleiner dan (alle voorkomens)"),
    "KDOG1": (BRP.kdog1, "kleiner dan of gelijk aan"),
    "KDOGA": (BRP.kdoga, "kleiner dan of gelijk aan (alle voorkomens)"),
    "GDOG1": (BRP.gdog1, "groter dan of gelijk aan"),
}


# =============================================================================
# BRP Voorwaarderegel Parser
#
# Grammar (LO-BRP §3.1.3):
#   voorwaarderegel = term ((ENVWD | OFVWD) term)*
#   term = '(' voorwaarderegel ')' | constraint
#   constraint = rubriek operator operand
#              | KV rubriek
#              | KNV rubriek
#   operand = value ((OFVGL | ENVGL) value)*
#   value = quoted_string | rubriek (('-'|'+') number)? | number
#   rubriek = \d{2}\.\d{2}\.\d{2} ('@' scope)?
# =============================================================================

TOK_LPAREN = 'LPAREN'
TOK_RPAREN = 'RPAREN'
TOK_RUBRIEK = 'RUBRIEK'
TOK_OPERATOR = 'OPERATOR'
TOK_LOGICAL = 'LOGICAL'
TOK_OFVGL = 'OFVGL'
TOK_ENVGL = 'ENVGL'
TOK_KV = 'KV'
TOK_KNV = 'KNV'
TOK_MINUS = 'MINUS'
TOK_PLUS = 'PLUS'
TOK_NUMBER = 'NUMBER'
TOK_STRING = 'STRING'
TOK_LIJST = 'LIJST'
TOK_KOLOM = 'KOLOM'
TOK_KLOPT1 = 'KLOPT1'
TOK_COLON = 'COLON'
TOK_EOF = 'EOF'

# Ordered by length (longest first) to avoid partial matches
OPERATOR_TOKENS = [
    ('KDOG1', TOK_OPERATOR),
    ('KDOGA', TOK_OPERATOR),
    ('GDOG1', TOK_OPERATOR),
    ('KLOPT1', TOK_KLOPT1),
    ('ENVWD', TOK_LOGICAL),
    ('OFVWD', TOK_LOGICAL),
    ('OFVGL', TOK_OFVGL),
    ('ENVGL', TOK_ENVGL),
    ('OGAA', TOK_OPERATOR),
    ('OGA1', TOK_OPERATOR),
    ('GA1', TOK_OPERATOR),
    ('GAA', TOK_OPERATOR),
    ('GD1', TOK_OPERATOR),
    ('KD1', TOK_OPERATOR),
    ('KDA', TOK_OPERATOR),
    ('KNV', TOK_KNV),
    ('KV', TOK_KV),
    ('LIJST', TOK_LIJST),
]


def tokenize(expr):
    """Tokenize a BRP voorwaarderegel expression."""
    tokens = []
    i = 0
    s = expr.strip()
    while i < len(s):
        if s[i] in ' \t\n\r':
            i += 1
            continue
        if s[i] == '(':
            tokens.append((TOK_LPAREN, '('))
            i += 1
        elif s[i] == ')':
            tokens.append((TOK_RPAREN, ')'))
            i += 1
        elif s[i] == '-':
            tokens.append((TOK_MINUS, '-'))
            i += 1
        elif s[i] == '+':
            tokens.append((TOK_PLUS, '+'))
            i += 1
        elif s[i] == ':':
            tokens.append((TOK_COLON, ':'))
            i += 1
        elif s[i] == '/':
            # Regex-like value /.../ -> treat as quoted string
            j = i + 1
            while j < len(s) and s[j] != '/':
                j += 1
            tokens.append((TOK_STRING, s[i + 1:j]))
            i = j + 1
        elif s[i] == '"':
            j = i + 1
            while j < len(s) and s[j] != '"':
                j += 1
            tokens.append((TOK_STRING, s[i + 1:j]))
            i = j + 1
        elif s[i] == '*':
            # Wildcard, skip
            i += 1
        elif re.match(r'\d{2}\.\d{2}\.\d{2}', s[i:]):
            rub = s[i:i + 8]
            i += 8
            # Check for @scope suffix
            if i < len(s) and s[i] == '@':
                j = i + 1
                while j < len(s) and s[j].isalpha():
                    j += 1
                rub += s[i:j]
                i = j
            tokens.append((TOK_RUBRIEK, rub))
        elif s[i:i + 6].startswith('kolom'):
            m = re.match(r'kolom\d+', s[i:])
            if m:
                tokens.append((TOK_KOLOM, m.group()))
                i += len(m.group())
            else:
                tokens.append((TOK_KOLOM, 'kolom'))
                i += 5
        else:
            # Try operator tokens (longest first)
            matched = False
            for keyword, tok_type in OPERATOR_TOKENS:
                if s[i:].startswith(keyword):
                    end = i + len(keyword)
                    if end < len(s) and s[end].isalpha():
                        continue
                    tokens.append((tok_type, keyword))
                    i = end
                    matched = True
                    break
            if not matched:
                if re.match(r'\d+', s[i:]):
                    m = re.match(r'\d+', s[i:])
                    tokens.append((TOK_NUMBER, m.group()))
                    i += len(m.group())
                else:
                    raise ValueError(
                        f"Unexpected char at pos {i}: '{s[i:i + 20]}'"
                    )
    tokens.append((TOK_EOF, None))
    return tokens


class Parser:
    """Recursive descent parser for BRP voorwaarderegel syntax."""

    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos]

    def consume(self, expected_type=None):
        tok = self.tokens[self.pos]
        if expected_type and tok[0] != expected_type:
            raise ValueError(f"Expected {expected_type}, got {tok}")
        self.pos += 1
        return tok

    def parse(self):
        # Handle KLOPT1: prefix
        if self.peek()[0] == TOK_KLOPT1:
            self.consume(TOK_KLOPT1)
            if self.peek()[0] == TOK_COLON:
                self.consume(TOK_COLON)
        result = self.parse_voorwaarderegel()
        if self.peek()[0] != TOK_EOF:
            raise ValueError(
                f"Trailing tokens at pos {self.pos}: {self.tokens[self.pos:]}"
            )
        return result

    def parse_voorwaarderegel(self):
        """voorwaarderegel = term ((ENVWD | OFVWD) term)*"""
        left = self.parse_term()

        while self.peek()[0] == TOK_LOGICAL:
            logical_op = self.peek()[1]
            terms = [left]
            while self.peek()[0] == TOK_LOGICAL and self.peek()[1] == logical_op:
                self.consume(TOK_LOGICAL)
                terms.append(self.parse_term())
            if len(terms) == 1:
                left = terms[0]
            else:
                odrl_op = "and" if logical_op == "ENVWD" else "or"
                left = {
                    "type": "logical",
                    "operator": odrl_op,
                    "operands": terms,
                }
        return left

    def parse_term(self):
        """term = '(' voorwaarderegel ')' | constraint"""
        if self.peek()[0] == TOK_LPAREN:
            self.consume(TOK_LPAREN)
            result = self.parse_voorwaarderegel()
            self.consume(TOK_RPAREN)
            return result
        return self.parse_constraint()

    def parse_constraint(self):
        """constraint = KV rubriek | KNV rubriek | LIJST (...) | rubriek operator operand"""
        tok = self.peek()

        if tok[0] == TOK_KV:
            self.consume(TOK_KV)
            rub = self.consume(TOK_RUBRIEK)
            return {
                "type": "constraint",
                "leftOperand": rub[1],
                "operator": "kv",
                "comment": f"KV {rub[1]}",
            }
        elif tok[0] == TOK_KNV:
            self.consume(TOK_KNV)
            rub = self.consume(TOK_RUBRIEK)
            return {
                "type": "constraint",
                "leftOperand": rub[1],
                "operator": "knv",
                "comment": f"KNV {rub[1]}",
            }
        elif tok[0] == TOK_LIJST:
            return self.parse_lijst()
        elif tok[0] == TOK_RUBRIEK:
            rub = self.consume(TOK_RUBRIEK)
            op = self.consume(TOK_OPERATOR)
            values, vgl_type = self.parse_operand()
            result = {
                "type": "constraint",
                "leftOperand": rub[1],
                "brpOperator": op[1],
            }
            if len(values) == 1:
                result["operator"] = op[1]  # store raw BRP op name
                result["rightOperand"] = values[0]
            else:
                if vgl_type == "OFVGL":
                    result["operator"] = "isAnyOf"
                else:  # ENVGL
                    result["operator"] = "isAllOf"
                result["rightOperand"] = values
            return result
        else:
            raise ValueError(f"Unexpected token in constraint: {tok}")

    def parse_lijst(self):
        """LIJST (kolom1 GA1 rubriek) -> special constraint"""
        self.consume(TOK_LIJST)
        self.consume(TOK_LPAREN)
        kolom = self.consume(TOK_KOLOM)
        op = self.consume(TOK_OPERATOR)
        rub = self.consume(TOK_RUBRIEK)
        self.consume(TOK_RPAREN)
        return {
            "type": "constraint",
            "leftOperand": rub[1],
            "operator": "lijst",
            "brpOperator": op[1],
            "comment": f"LIJST ({kolom[1]} {op[1]} {rub[1]})",
            "kolom": kolom[1],
        }

    def parse_operand(self):
        """operand = value ((OFVGL | ENVGL) value)*"""
        values = [self.parse_value()]
        vgl_type = None
        while self.peek()[0] in (TOK_OFVGL, TOK_ENVGL):
            vgl_type = self.peek()[1]
            self.consume()
            # Skip duplicate OFVGL/ENVGL (typos in source data)
            while self.peek()[0] in (TOK_OFVGL, TOK_ENVGL):
                self.consume()
            values.append(self.parse_value())
        return values, vgl_type or "OFVGL"

    def parse_value(self):
        """value = quoted_string
               | '(' rubriek ('-'|'+') number ')'
               | rubriek (('-'|'+') number)?
               | number (('-'|'+') number)?
        """
        tok = self.peek()
        if tok[0] == TOK_STRING:
            self.consume(TOK_STRING)
            return tok[1]
        elif tok[0] == TOK_LPAREN:
            # Parenthesized date calc: (19.89.30 - 0063)
            self.consume(TOK_LPAREN)
            inner = self.parse_value()
            self.consume(TOK_RPAREN)
            return inner
        elif tok[0] == TOK_RUBRIEK:
            rub = self.consume(TOK_RUBRIEK)
            if self.peek()[0] in (TOK_MINUS, TOK_PLUS):
                sign_tok = self.consume()
                num = self.consume(TOK_NUMBER)
                return {
                    "type": "dateCalc",
                    "reference": rub[1],
                    "offset": num[1],
                    "sign": sign_tok[1],
                }
            return rub[1]
        elif tok[0] == TOK_NUMBER:
            num = self.consume(TOK_NUMBER)
            # Handle raw date calculations: NUMBER ('-'|'+') NUMBER
            if self.peek()[0] in (TOK_MINUS, TOK_PLUS):
                sign_tok = self.consume()
                num2 = self.consume(TOK_NUMBER)
                return {
                    "type": "dateCalc",
                    "reference": num[1],
                    "offset": num2[1],
                    "sign": sign_tok[1],
                    "rawDate": True,
                }
            return num[1]
        else:
            raise ValueError(f"Unexpected token in value: {tok}")


def parse_voorwaarderegel(expr):
    """Parse a BRP voorwaarderegel expression and return a tree."""
    tokens = tokenize(expr)
    parser = Parser(tokens)
    return parser.parse()


# =============================================================================
# Constraint tree -> rdflib subgraph
# =============================================================================


def _format_offset_duration(offset_str, sign="-"):
    """Convert a BRP date offset to xsd:duration.

    4-digit: YYYY -> PNY
    5-digit: YYYYY -> PNY (rare, treat as years)
    6-digit: YYYYMM -> PNY[NM]
    8-digit: YYYYMMDD -> PNY[NM][ND]
    """
    n = len(offset_str)
    if n <= 4:
        years = int(offset_str)
        return f"P{years}Y"
    elif n <= 5:
        years = int(offset_str)
        return f"P{years}Y"
    elif n == 6:
        years = int(offset_str[:4])
        months = int(offset_str[4:6])
        parts = []
        if years:
            parts.append(f"{years}Y")
        if months:
            parts.append(f"{months}M")
        if not parts:
            parts.append("0D")
        return "P" + "".join(parts)
    else:
        # 7-8+ digit YYYYMMDD (pad right with zeros if needed)
        padded = offset_str.ljust(8, "0")
        years = int(padded[:4])
        months = int(padded[4:6])
        days = int(padded[6:8])
        parts = []
        if years:
            parts.append(f"{years}Y")
        if months:
            parts.append(f"{months}M")
        if days:
            parts.append(f"{days}D")
        if not parts:
            parts.append("0D")
        return "P" + "".join(parts)


def _elm_ref(rubrieknummer):
    """Convert a rubrieknummer to a URIRef, using informatiemodel.ttl."""
    return im.elm_ref(rubrieknummer)


def _elm_label(rub):
    """Get a readable Dutch label for a rubrieknummer."""
    return im.elm_label(rub)


def _duration_to_dutch(duration_str):
    """Convert an ISO 8601 duration like P3Y or P2M6D to readable Dutch."""
    m = re.match(r"P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)D)?", duration_str)
    if not m:
        return duration_str
    years = int(m.group(1) or 0)
    months = int(m.group(2) or 0)
    days = int(m.group(3) or 0)
    parts = []
    if years:
        parts.append(f"{years} jaar")
    if months:
        parts.append(f"{months} {'maand' if months == 1 else 'maanden'}")
    if days:
        parts.append(f"{days} {'dag' if days == 1 else 'dagen'}")
    if not parts:
        return "0 dagen"
    return " en ".join(parts)


def _is_age_constraint(left_rub, right):
    """Check if this is a geboortedatum vs peildatum constraint (= leeftijd)."""
    if not isinstance(right, dict) or right.get("type") != "dateCalc":
        return False
    left_base = left_rub.split("@")[0] if "@" in left_rub else left_rub
    gg_ee = left_base[3:] if len(left_base) > 5 else left_base
    ref = right["reference"].split("@")[0]
    ref_gg_ee = ref[3:] if len(ref) > 5 else ref
    # geboortedatum (03.10) vergeleken met vandaag/selectiedatum (89.20/89.30)
    return gg_ee == "03.10" and ref_gg_ee in ("89.20", "89.30")


def _age_meaning(brp_op, duration_str):
    """Describe what a geboortedatum comparison means in age terms."""
    dur = _duration_to_dutch(duration_str)
    age_map = {
        "KDOG1": f"minimaal {dur} oud",
        "KDOGA": f"minimaal {dur} oud",
        "KD1": f"ouder dan {dur}",
        "KDA": f"ouder dan {dur}",
        "GD1": f"maximaal {dur} oud",
        "GDOG1": f"maximaal {dur} oud",
        "GA1": f"precies {dur} oud",
        "GAA": f"precies {dur} oud",
    }
    return age_map.get(brp_op)


def _describe_right(right, value_type=None):
    """Generate a readable Dutch description of a right operand."""
    if isinstance(right, dict) and right.get("type") == "dateCalc":
        ref = right["reference"]
        ref_base = ref.split("@")[0] if "@" in ref else ref
        duration = _format_offset_duration(
            right["offset"], right.get("sign", "-")
        )
        dur_dutch = _duration_to_dutch(duration)
        is_rubriek = re.match(r"\d{2}\.\d{2}\.\d{2}", ref_base)
        sign = "+" if right.get("sign") == "+" else "\u2212"
        if is_rubriek:
            return f"{_elm_label(ref_base)} {sign} {dur_dutch}"
        else:
            return f"{ref_base} {sign} {dur_dutch}"
    elif isinstance(right, str) and re.match(r"\d{2}\.\d{2}\.\d{2}", right):
        return _elm_label(right)
    elif isinstance(right, list):
        vals = [_describe_right(v, value_type) for v in right]
        if len(vals) <= 5:
            return ", ".join(vals)
        return f"{', '.join(vals[:3])}, ... ({len(vals)} waarden)"
    elif value_type and isinstance(right, str):
        return _lookup_label(right, value_type)
    else:
        return str(right)


def _build_comment(node):
    """Build a meaningful Dutch comment for a constraint node."""
    if node["type"] == "logical":
        return None
    left_rub = node["leftOperand"]
    left_label = _elm_label(left_rub)
    operator = node.get("operator", "")
    brp_op = node.get("brpOperator", "")
    right = node.get("rightOperand")
    vtype = _value_type_for_rub(left_rub)

    # KV / KNV
    if operator == "kv":
        return f"{left_label} is aanwezig"
    if operator == "knv":
        return f"{left_label} is niet aanwezig"
    if operator == "lijst":
        return f"{left_label} komt voor in selectielijst"

    # isAnyOf / isAllOf
    if operator == "isAnyOf":
        right_desc = _describe_right(right, vtype)
        return f"{left_label} is een van: {right_desc}"
    if operator == "isAllOf":
        right_desc = _describe_right(right, vtype)
        return f"{left_label} is alle van: {right_desc}"

    # Date/age comparison: add human-readable meaning
    if _is_age_constraint(left_rub, right):
        duration = _format_offset_duration(
            right["offset"], right.get("sign", "-")
        )
        age = _age_meaning(brp_op, duration)
        dur_dutch = _duration_to_dutch(duration)
        ref_label = _elm_label(right["reference"])
        op_desc = OPERATOR_MAP.get(brp_op, (None, brp_op))[1]
        base = f"{left_label} {op_desc} {ref_label} \u2212 {dur_dutch}"
        if age:
            return f"{base} ({age})"
        return base

    # Other date calculation
    if isinstance(right, dict) and right.get("type") == "dateCalc":
        op_desc = OPERATOR_MAP.get(brp_op, (None, brp_op))[1] if brp_op else operator
        right_desc = _describe_right(right, vtype)
        return f"{left_label} {op_desc} {right_desc}"

    # Regular comparison
    op_desc = OPERATOR_MAP.get(brp_op, (None, brp_op))[1] if brp_op else operator
    right_desc = _describe_right(right, vtype) if right else ""
    return f"{left_label} {op_desc} {right_desc}"


def _value_type_for_rub(left_rub):
    """Determine the value type for a rubriek, using informatiemodel.ttl."""
    if not left_rub:
        return None
    return im.element_value_type(left_rub)


def _value_to_rdf(v, value_type=None):
    """Convert a parsed value to an rdflib URIRef or Literal."""
    if isinstance(v, dict) and v.get("type") == "dateCalc":
        duration = _format_offset_duration(v["offset"], v.get("sign", "-"))
        return Literal(duration, datatype=XSD.duration)
    if isinstance(v, str) and re.match(r"\d{2}\.\d{2}\.\d{2}", v):
        return _elm_ref(v.split("@")[0])
    if isinstance(v, str) and re.match(r"\d+$", v):
        if value_type == "gemeente" and len(v) == 4:
            return GEM[f"gm{v}"]
        if value_type == "nationaliteit" and len(v) == 4:
            return BRPNAT[v]
        if value_type == "land" and len(v) == 4:
            return BRPLAND[v]
        if value_type == "verblijfstitel" and len(v) <= 2:
            return BRPVBT[v]
        if value_type == "afnemer":
            return BRPAFN[v.strip()]
    return Literal(v)


def _operator_ref(op_name):
    """Resolve a parsed operator name to an rdflib URIRef.

    op_name is a short key like "kv", "knv", "lijst", "isAnyOf", "isAllOf",
    or a BRP operator name like "GA1" that maps via OPERATOR_MAP.
    """
    if op_name in ("kv", "knv", "lijst"):
        return BRP[op_name]
    if op_name in ("isAnyOf", "isAllOf"):
        return ODRL[op_name]
    # BRP comparison operator (GA1, GD1, etc.)
    entry = OPERATOR_MAP.get(op_name)
    if entry:
        return entry[0]
    return BRP[op_name]


def _add_constraint(g, node):
    """Recursively add a constraint tree to graph g. Returns the BNode."""
    if node["type"] == "logical":
        bnode = BNode()
        g.add((bnode, RDF.type, ODRL.LogicalConstraint))
        operand_nodes = [_add_constraint(g, op) for op in node["operands"]]
        list_head = BNode()
        Collection(g, list_head, operand_nodes)
        op_name = node["operator"]  # "and" or "or"
        g.add((bnode, ODRL[op_name], list_head))
        return bnode

    elif node["type"] == "constraint":
        bnode = BNode()
        g.add((bnode, RDF.type, ODRL.Constraint))

        left_rub = node["leftOperand"]
        left_rub_base = left_rub.split("@")[0] if "@" in left_rub else left_rub
        g.add((bnode, ODRL.leftOperand, _elm_ref(left_rub_base)))

        if "@" in left_rub:
            scope = left_rub.split("@")[1]
            g.add((bnode, BRP.scope, Literal(scope)))

        operator = node["operator"]
        g.add((bnode, ODRL.operator, _operator_ref(operator)))

        vtype = _value_type_for_rub(left_rub)
        right = node.get("rightOperand")

        if right is not None:
            if isinstance(right, list):
                # Multiple values (OFVGL / ENVGL) -> rdf:List via Collection
                rdf_values = [_value_to_rdf(v, value_type=vtype) for v in right]
                list_head = BNode()
                Collection(g, list_head, rdf_values)
                g.add((bnode, ODRL.rightOperand, list_head))
            elif isinstance(right, dict) and right.get("type") == "dateCalc":
                ref = right["reference"]
                ref_base = ref.split("@")[0] if "@" in ref else ref
                duration = _format_offset_duration(
                    right["offset"], right.get("sign", "-")
                )
                g.add((bnode, ODRL.rightOperand,
                       Literal(duration, datatype=XSD.duration)))
                is_raw = right.get("rawDate", False)
                is_rubriek = re.match(r"\d{2}\.\d{2}\.\d{2}", ref_base)
                if is_rubriek:
                    g.add((bnode, ODRL.rightOperandReference,
                           _elm_ref(ref_base)))
                elif is_raw:
                    g.add((bnode, BRP.peilDatum, Literal(ref_base)))
                if right.get("sign") == "+":
                    g.add((bnode, BRP.dateCalcSign, Literal("+")))
            elif isinstance(right, str) and re.match(
                r"\d{2}\.\d{2}\.\d{2}", right
            ):
                right_base = right.split("@")[0]
                g.add((bnode, ODRL.rightOperandReference,
                       _elm_ref(right_base)))
            else:
                g.add((bnode, ODRL.rightOperand,
                       _value_to_rdf(right, value_type=vtype)))

        comment = _build_comment(node)
        if comment:
            g.add((bnode, RDFS.comment, Literal(comment, lang="nl")))

        return bnode

    raise ValueError(f"Unknown node type: {node['type']}")


# =============================================================================
# TTL Generation helpers
# =============================================================================


def format_date(d):
    s = str(d)
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}T00:00:00"


def format_afn(afn_ind):
    return str(afn_ind).strip()


def rubrieken_to_targets(rub_str):
    if not rub_str or str(rub_str).strip() == "":
        return []
    return [r.strip() for r in str(rub_str).split("#") if r.strip()]


def _add_constraint_block(g, perm_node, vwr_expr):
    """Parse a voorwaarderegel and add the ODRL constraint to the graph.

    Returns True if parsing succeeded, False otherwise.
    """
    if not vwr_expr or not str(vwr_expr).strip():
        return None  # no expression -> no constraint attempted
    vwr_str = str(vwr_expr).strip()
    g.add((perm_node, BRP.voorwaarderegel, Literal(vwr_str)))
    try:
        tree = parse_voorwaarderegel(vwr_str)
        constraint_node = _add_constraint(g, tree)
        g.add((perm_node, ODRL.constraint, constraint_node))
        return True
    except Exception as e:
        print(f"  WARNING: Could not parse: {e}", file=sys.stderr)
        print(f"  Expression: {vwr_str[:100]}", file=sys.stderr)
        return False


RVIG = URIRef("https://identifier.overheid.nl/tooi/id/oorg/oorg10103")
BRP_PROFILE = URIRef("https://data.rijksoverheid.nl/brp/def")


def generate_autorisatiebesluiten(all_afnemers):
    """Generate autorisatiebesluiten TTL files (actueel + historisch)."""
    parse_ok = 0
    parse_fail = 0

    g_act = new_graph()
    g_hist = new_graph()

    def g_for(is_active):
        return g_act if is_active else g_hist

    # Helper: add to both graphs (for shared resources like containers)
    def g_both(triple):
        g_act.add(triple)
        g_hist.add(triple)

    sorted_afnemers = sorted(all_afnemers.keys())

    for afn_idx, afn in enumerate(sorted_afnemers):
        rows = all_afnemers[afn]
        afn_str = format_afn(afn)
        latest_naam = rows[-1][COL_AFN_NAAM]

        if afn_idx % 200 == 0:
            print(
                f"  Processing afnemer {afn_idx + 1}/{len(sorted_afnemers)}"
                f" ({afn_str})..."
            )

        # Temporal container (in both graphs)
        container = BRPAUT[afn_str]
        g_both((container, RDF.type, TPL.TemporalSet))
        g_both((container, ODRL.uid, container))
        g_both((container, ODRL.profile, BRP_PROFILE))
        g_both((container, DCTERMS.title,
               Literal(f"Autorisatiebesluit {latest_naam}", lang="nl")))

        for row in rows:
            version_uri = BRPAUT[f"{afn_str}-v{row[COL_VERSIE]}"]
            is_act = row[COL_EINDE] is None or str(row[COL_EINDE]).strip() == ""
            g_for(is_act).add((container, DCTERMS.hasPart, version_uri))

        # Each version
        prev_uri = None
        for row in rows:
            versie = row[COL_VERSIE]
            naam = row[COL_AFN_NAAM]
            ingang = row[COL_INGANG]
            einde = row[COL_EINDE]
            geheim = row[COL_GEHEIM]
            verstr_bep = row[COL_VERSTR_BEP]
            bijz_kind = row[COL_BIJZ_KIND]

            is_active = einde is None or str(einde).strip() == ""
            uri = BRPAUT[f"{afn_str}-v{versie}"]
            g = g_for(is_active)

            g.add((uri, RDF.type, ODRL.Set))
            g.add((uri, RDF.type, BRP.Autorisatiebesluit))
            g.add((uri, PROV.specializationOf, container))
            g.add((uri, DCTERMS.title,
                   Literal(f"Autorisatiebesluit {naam} (versie {versie})",
                           lang="nl")))
            if prev_uri:
                g.add((uri, PROV.wasRevisionOf, prev_uri))
            prev_uri = uri
            g.add((uri, TPL.effectiveFrom,
                   Literal(format_date(ingang), datatype=XSD.dateTime)))
            if not is_active:
                g.add((uri, TPL.effectiveTo,
                       Literal(format_date(einde), datatype=XSD.dateTime)))

            # Boolean indicaties
            if geheim:
                g.add((uri, BRP.indicatieGeheimhoudingAfnemer,
                       Literal(True)))
            if bijz_kind:
                g.add((uri, BRP.bijzondereBetrekkingKindVerstrekken,
                       Literal(True)))

            # Verstrekkingsbeperking
            vb = int(verstr_bep) if verstr_bep else 0
            if vb == 1:
                g.add((uri, BRP.verstrekkingsbeperking,
                       BRP.VerstrekkingsbeperkingBeperkt))
            elif vb == 2:
                g.add((uri, BRP.verstrekkingsbeperking,
                       BRP.VerstrekkingsbeperkingVerborgen))

            # Collect permissions
            permissions = []

            rub_spont = row[COL_RUB_SPONT]
            if rub_spont and str(rub_spont).strip():
                permissions.append((
                    "spontaan",
                    rub_spont,
                    row[COL_VWR_SPONT],
                    row[COL_MED_SPONT],
                    row[COL_SLEUTEL],
                    row[COL_COND_VERSTR],
                ))

            rub_sel = row[COL_RUB_SEL]
            vwr_sel = row[COL_VWR_SEL]
            if (rub_sel and str(rub_sel).strip()) or (
                vwr_sel and str(vwr_sel).strip()
            ):
                permissions.append((
                    "selectie",
                    rub_sel,
                    vwr_sel,
                    row[COL_MED_SEL],
                    row[COL_SEL_SOORT],
                    row[COL_SEL_PERIODE],
                    row[COL_BER_AAND],
                    row[COL_EERSTE_SEL],
                ))

            rub_adhoc = row[COL_RUB_ADHOC]
            if rub_adhoc and str(rub_adhoc).strip():
                permissions.append((
                    "adhoc",
                    rub_adhoc,
                    row[COL_VWR_ADHOC],
                    row[COL_MED_ADHOC],
                    row[COL_PLAATSING],
                    row[COL_ADRESVRAAG],
                    row[COL_AFN_VERSTR],
                ))

            if not permissions:
                g.add((uri, RDFS.comment,
                       Literal("Geen koppelvlakken gedefinieerd in deze versie.",
                               lang="nl")))
                continue

            for perm in permissions:
                ptype = perm[0]
                perm_node = BNode()
                g.add((uri, ODRL.permission, perm_node))
                g.add((perm_node, RDF.type, ODRL.Permission))
                g.add((perm_node, ODRL.assignee, BRPAFN[afn_str]))
                g.add((perm_node, ODRL.assigner, RVIG))

                if ptype == "spontaan":
                    rub, vwr, med, sleutel, cond = perm[1:]
                    g.add((perm_node, ODRL.action, BRP.spontaneVerstrekking))

                    for r in rubrieken_to_targets(rub):
                        g.add((perm_node, ODRL.target, _elm_ref(r)))

                    if med and str(med).strip():
                        med_uri = BRP.MediumNetwerk if str(med).strip() == "N" else BRP.MediumAnders
                        g.add((perm_node, BRP.medium, med_uri))

                    if sleutel and str(sleutel).strip():
                        for s in str(sleutel).split("#"):
                            if s.strip():
                                g.add((perm_node, BRP.sleutelrubriek,
                                       _elm_ref(s.strip())))

                    if cond is not None and str(cond).strip() != "":
                        cond_uri = (
                            BRP.SpontaanConditioneelBericht
                            if str(cond).strip() == "1"
                            else BRP.SpontaanPlaatsingAfnemersindicatie
                        )
                        g.add((perm_node, BRP.conditioneleVerstrekking,
                               cond_uri))

                    if vwr and str(vwr).strip():
                        ok = _add_constraint_block(g, perm_node, vwr)
                        if ok is True:
                            parse_ok += 1
                        elif ok is False:
                            parse_fail += 1

                elif ptype == "selectie":
                    rub, vwr, med, sel_soort, sel_periode, ber_aand, eerste_sel = perm[1:]

                    # Determine sub-action based on selectiesoort
                    ss_action_map = {
                        "0": BRP.selectieGegevensVerstrekking,
                        "1": BRP.selectiePlaatsingIndicatie,
                        "2": BRP.selectieLogischVerwijderen,
                        "3": BRP.selectieVoorwaardelijkVerwijderen,
                        "4": BRP.selectieOnvoorwaardelijkVerwijderen,
                    }
                    ss_str = str(sel_soort).strip() if sel_soort is not None else ""
                    action_uri = ss_action_map.get(ss_str, BRP.selectieVerstrekking)

                    # Build action with temporal refinements
                    action_node = BNode()
                    g.add((action_node, RDF.value, action_uri))

                    # Eerste selectiedatum als refinement
                    has_eerste = eerste_sel is not None and str(eerste_sel).strip()
                    has_periode = sel_periode is not None and str(sel_periode).strip()
                    maanden = int(str(sel_periode).strip()) if has_periode else 0

                    if has_eerste:
                        d = str(eerste_sel).strip()
                        if len(d) >= 8:
                            datum_ref = BNode()
                            g.add((datum_ref, RDF.type, ODRL.Constraint))
                            g.add((datum_ref, ODRL.leftOperand, ODRL.dateTime))
                            # Eenmalig (P0M) = exact op deze datum; periodiek = vanaf deze datum
                            if maanden == 0:
                                g.add((datum_ref, ODRL.operator, ODRL.eq))
                                g.add((datum_ref, RDFS.comment,
                                       Literal("Eenmalige selectie op deze datum", lang="nl")))
                            else:
                                g.add((datum_ref, ODRL.operator, ODRL.gteq))
                                g.add((datum_ref, RDFS.comment,
                                       Literal("Selectie mag pas vanaf deze datum", lang="nl")))
                            g.add((datum_ref, ODRL.rightOperand,
                                   Literal(f"{d[:4]}-{d[4:6]}-{d[6:8]}",
                                           datatype=XSD.date)))
                            g.add((action_node, ODRL.refinement, datum_ref))

                    # Selectieperiode als refinement (alleen als > 0)
                    if has_periode and maanden > 0:
                        interval_ref = BNode()
                        g.add((interval_ref, RDF.type, ODRL.Constraint))
                        g.add((interval_ref, ODRL.leftOperand, ODRL.timeInterval))
                        g.add((interval_ref, ODRL.operator, ODRL.eq))
                        g.add((interval_ref, ODRL.rightOperand,
                               Literal(f"P{maanden}M", datatype=XSD.duration)))
                        g.add((interval_ref, RDFS.comment,
                               Literal(f"Selectie wordt elke {maanden} maanden herhaald",
                                       lang="nl")))
                        g.add((action_node, ODRL.refinement, interval_ref))

                    g.add((perm_node, ODRL.action, action_node))

                    for r in rubrieken_to_targets(rub):
                        g.add((perm_node, ODRL.target, _elm_ref(r)))

                    if med and str(med).strip():
                        med_uri = BRP.MediumNetwerk if str(med).strip() == "N" else BRP.MediumAnders
                        g.add((perm_node, BRP.medium, med_uri))


                    if ber_aand is not None and str(ber_aand).strip() != "":
                        ba = str(ber_aand).strip()
                        if ba == "1":
                            g.add((perm_node, BRP.berichtaanduiding,
                                   BRP.BerichtaanduidingVulbericht))
                        elif ba == "0":
                            g.add((perm_node, BRP.berichtaanduiding,
                                   BRP.BerichtaanduidingGeen))

                    if vwr and str(vwr).strip():
                        ok = _add_constraint_block(g, perm_node, vwr)
                        if ok is True:
                            parse_ok += 1
                        elif ok is False:
                            parse_fail += 1

                elif ptype == "adhoc":
                    rub, vwr, med, plaatsing, adresvraag, afn_verstr = perm[1:]
                    g.add((perm_node, ODRL.action, BRP.adHocVerstrekking))

                    for r in rubrieken_to_targets(rub):
                        g.add((perm_node, ODRL.target, _elm_ref(r)))

                    if med and str(med).strip():
                        med_uri = BRP.MediumNetwerk if str(med).strip() == "N" else BRP.MediumAnders
                        g.add((perm_node, BRP.medium, med_uri))

                    if plaatsing and int(plaatsing):
                        g.add((perm_node, ODRL.action, BRP.adHocPlaatsing))

                    if adresvraag and int(adresvraag):
                        g.add((perm_node, ODRL.action, BRP.adresVraag))

                    # Afnemersverstrekkingen: andere afnemers wiens indicaties
                    # deze afnemer mag opvragen
                    if afn_verstr and str(afn_verstr).strip():
                        for a in str(afn_verstr).split("#"):
                            a = a.strip()
                            if a:
                                g.add((perm_node, BRP.afnemersverstrekkingen,
                                       BRPAFN[a]))

                    if vwr and str(vwr).strip():
                        ok = _add_constraint_block(g, perm_node, vwr)
                        if ok is True:
                            parse_ok += 1
                        elif ok is False:
                            parse_fail += 1

    # Bundle in both graphs
    bundle = BRPAUT.autorisatiebesluiten
    for gb in (g_act, g_hist):
        gb.add((bundle, RDF.type, TPL.TemporalSet))
        gb.add((bundle, ODRL.uid, bundle))
        gb.add((bundle, ODRL.profile, BRP_PROFILE))
        gb.add((bundle, ODRL.assigner, RVIG))
        for afn in sorted_afnemers:
            gb.add((bundle, DCTERMS.hasPart, BRPAUT[format_afn(afn)]))

    save(g_act, OUTPUT_PATH_ACTUEEL)
    save(g_hist, OUTPUT_PATH_HISTORISCH)
    return parse_ok, parse_fail


def _read_tabel35():
    """Read Tabel 35 CSV, returning rows as tuples with typed values."""
    csv_dir = os.path.join(BASE_DIR, "csv")
    with open(os.path.join(csv_dir, "tabel35_autorisatietabel.csv"), "rb") as f:
        raw = f.read(4)
    enc = "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8"
    try:
        open(os.path.join(csv_dir, "tabel35_autorisatietabel.csv"), encoding=enc).read()
    except UnicodeDecodeError:
        enc = "latin-1"

    with open(os.path.join(csv_dir, "tabel35_autorisatietabel.csv"),
              encoding=enc, newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = []
        for r in reader:
            if not any(c.strip() for c in r):
                continue
            # Convert numeric columns to int where expected
            typed = list(r)
            # COL_AFN_IND stays as string to preserve leading zeros
            for i in [COL_VERSIE, COL_INGANG, COL_EINDE,
                       COL_GEHEIM, COL_VERSTR_BEP, COL_BIJZ_KIND,
                       COL_PLAATSING, COL_ADRESVRAAG]:
                if i < len(typed) and typed[i].strip():
                    try:
                        typed[i] = int(typed[i].strip())
                    except ValueError:
                        pass
                elif i < len(typed):
                    typed[i] = None
            # Pad to expected length
            while len(typed) < 30:
                typed.append("")
            rows.append(tuple(typed))
    return rows


def main():
    print("Reading Tabel 35...")
    data = _read_tabel35()

    # Collect all rows per afnemer
    all_afnemers = {}
    for row in data:
        afn = row[COL_AFN_IND]
        if afn is not None:
            all_afnemers.setdefault(afn, []).append(row)

    n_afnemers = len(all_afnemers)
    n_rows = sum(len(rows) for rows in all_afnemers.values())
    print(f"  {n_afnemers} afnemers, {n_rows} tabelregels")

    print(f"\nGenerating autorisatiebesluiten...")
    parse_ok, parse_fail = generate_autorisatiebesluiten(all_afnemers)

    print(f"\nVoorwaarderegels parsed: {parse_ok} OK, {parse_fail} failed")


if __name__ == "__main__":
    main()
