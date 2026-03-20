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
import brp_elementen as be

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, "csv", "tabel35_autorisatietabel.csv")
OUTPUT_PATH = os.path.join(BASE_DIR, "ttl", "autorisatiebesluiten.ttl")

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


# Operator mapping: BRP operator -> (brp: ODRL Operator, Dutch description)
OPERATOR_MAP = {
    "GA1": ("brp:ga1", "gelijk aan"),
    "GAA": ("brp:gaa", "gelijk aan (alle voorkomens)"),
    "OGA1": ("brp:oga1", "ongelijk aan"),
    "OGAA": ("brp:ogaa", "ongelijk aan (alle voorkomens)"),
    "GD1": ("brp:gd1", "groter dan"),
    "KD1": ("brp:kd1", "kleiner dan"),
    "KDA": ("brp:kda", "kleiner dan (alle voorkomens)"),
    "KDOG1": ("brp:kdog1", "kleiner dan of gelijk aan"),
    "KDOGA": ("brp:kdoga", "kleiner dan of gelijk aan (alle voorkomens)"),
    "GDOG1": ("brp:gdog1", "groter dan of gelijk aan"),
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
                odrl_op = "odrl:and" if logical_op == "ENVWD" else "odrl:or"
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
                "operator": "brp:kv",
                "comment": f"KV {rub[1]}",
            }
        elif tok[0] == TOK_KNV:
            self.consume(TOK_KNV)
            rub = self.consume(TOK_RUBRIEK)
            return {
                "type": "constraint",
                "leftOperand": rub[1],
                "operator": "brp:knv",
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
                result["operator"] = OPERATOR_MAP[op[1]][0]
                result["rightOperand"] = values[0]
            else:
                if vgl_type == "OFVGL":
                    result["operator"] = "odrl:isAnyOf"
                else:  # ENVGL
                    result["operator"] = "odrl:isAllOf"
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
            "operator": "brp:lijst",
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


def constraint_to_turtle(node, indent="        "):
    """Convert a parsed constraint tree to Turtle string."""
    lines = []
    _constraint_to_lines(node, indent, lines)
    return "\n".join(lines)


def _elm_label(rub):
    """Get a readable Dutch label for a rubrieknummer."""
    rub_base = rub.split("@")[0] if "@" in rub else rub
    try:
        return be.ELEMENTS[rub_base[3:]][0]  # strip CC. prefix
    except (KeyError, IndexError):
        try:
            return be.rubriek_to_label(rub_base)
        except (KeyError, ValueError):
            return rub_base


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
    # geboortedatum KDOG1 vandaag-3j = geboren <= vandaag-3j = minimaal 3j oud
    # geboortedatum GD1 vandaag-23j = geboren > vandaag-23j = maximaal 23j oud
    # geboortedatum GA1 vandaag-18j = geboren op vandaag-18j = precies 18j
    # geboortedatum KD1 vandaag-65j = geboren < vandaag-65j = ouder dan 65j
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
        sign = "+" if right.get("sign") == "+" else "−"
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
    if operator == "brp:kv":
        return f"{left_label} is aanwezig"
    if operator == "brp:knv":
        return f"{left_label} is niet aanwezig"
    if operator == "brp:lijst":
        return f"{left_label} komt voor in selectielijst"

    # isAnyOf / isAllOf
    if operator == "odrl:isAnyOf":
        right_desc = _describe_right(right, vtype)
        return f"{left_label} is een van: {right_desc}"
    if operator == "odrl:isAllOf":
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
        base = f"{left_label} {op_desc} {ref_label} − {dur_dutch}"
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


def _constraint_to_lines(node, indent, lines):
    """Recursively convert constraint tree to Turtle lines."""
    if node["type"] == "logical":
        lines.append(f"{indent}[")
        lines.append(f"{indent}    a odrl:LogicalConstraint ;")
        op = node["operator"]
        lines.append(f"{indent}    {op} (")
        for operand in node["operands"]:
            _constraint_to_lines(operand, indent + "        ", lines)
        lines.append(f"{indent}    )")
        lines.append(f"{indent}]")
    elif node["type"] == "constraint":
        left_rub = node["leftOperand"]
        left_rub_base = left_rub.split("@")[0] if "@" in left_rub else left_rub
        operator = node["operator"]

        lines.append(f"{indent}[")
        lines.append(f"{indent}    a odrl:Constraint ;")
        lines.append(f"{indent}    odrl:leftOperand {elm_uri(left_rub_base)} ;")

        if "@" in left_rub:
            scope = left_rub.split("@")[1]
            lines.append(f'{indent}    brp:scope "{scope}" ;')

        lines.append(f"{indent}    odrl:operator {operator} ;")

        vtype = _value_type_for_rub(left_rub)
        right = node.get("rightOperand")
        if right is not None:
            if isinstance(right, list):
                formatted = [_format_value(v, value_type=vtype) for v in right]
                lines.append(
                    f"{indent}    odrl:rightOperand ( {' '.join(formatted)} ) ;"
                )
            elif isinstance(right, dict) and right.get("type") == "dateCalc":
                ref = right["reference"]
                ref_base = ref.split("@")[0] if "@" in ref else ref
                duration = _format_offset_duration(
                    right["offset"], right.get("sign", "-")
                )
                is_raw = right.get("rawDate", False)
                is_rubriek = re.match(r"\d{2}\.\d{2}\.\d{2}", ref_base)

                lines.append(
                    f'{indent}    odrl:rightOperand "{duration}"^^xsd:duration ;'
                )
                if is_rubriek:
                    lines.append(
                        f"{indent}    odrl:rightOperandReference {elm_uri(ref_base)} ;"
                    )
                elif is_raw:
                    lines.append(
                        f'{indent}    brp:peilDatum "{ref_base}" ;'
                    )
                if right.get("sign") == "+":
                    lines.append(
                        f'{indent}    brp:dateCalcSign "+" ;'
                    )
            elif isinstance(right, str) and re.match(
                r"\d{2}\.\d{2}\.\d{2}", right
            ):
                right_base = right.split("@")[0]
                lines.append(
                    f"{indent}    odrl:rightOperandReference {elm_uri(right_base)} ;"
                )
            else:
                lines.append(
                    f"{indent}    odrl:rightOperand {_format_value(right, value_type=vtype)} ;"
                )

        comment = _build_comment(node)
        if comment:
            lines.append(f'{indent}    rdfs:comment "{_escape(comment)}"@nl')
        lines.append(f"{indent}]")


def _value_type_for_rub(left_rub):
    """Determine the value type for a rubriek, using brp_elementen."""
    if not left_rub:
        return None
    return be.element_value_type(left_rub)


def _format_value(v, value_type=None):
    """Format a value for Turtle output."""
    if isinstance(v, dict) and v.get("type") == "dateCalc":
        duration = _format_offset_duration(v["offset"], v.get("sign", "-"))
        return f'"{duration}"^^xsd:duration'
    if isinstance(v, str) and re.match(r"\d{2}\.\d{2}\.\d{2}", v):
        return elm_uri(v.split("@")[0])
    if isinstance(v, str) and re.match(r"\d+$", v):
        if value_type == "gemeente" and len(v) == 4:
            return f"gem:gm{v}"
        if value_type == "nationaliteit" and len(v) == 4:
            return f"brpnat:{v}"
        if value_type == "land" and len(v) == 4:
            return f"brpland:{v}"
        if value_type == "verblijfstitel" and len(v) <= 2:
            return f"brpvbt:{v}"
        if value_type == "afnemer":
            return f"brpafn:{v.strip()}"
    return f'"{v}"'


def _escape(s):
    return str(s).replace("\\", "\\\\").replace('"', '\\"')


# =============================================================================
# TTL Generation helpers
# =============================================================================


def elm_uri(rubrieknummer):
    """Convert a rubrieknummer to brpelm: URI using meaningful names."""
    rub = rubrieknummer.split("@")[0]  # strip scope
    try:
        return f"brpelm:{be.rubriek_to_uri(rub)}"
    except (KeyError, ValueError):
        return f"brpelm:{rub}"


def format_date(d):
    s = str(d)
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}T00:00:00"


def format_date_short(d):
    s = str(d)
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}"


def format_afn(afn_ind):
    return str(afn_ind).strip()


def rubrieken_to_targets(rub_str):
    if not rub_str or str(rub_str).strip() == "":
        return []
    return [r.strip() for r in str(rub_str).split("#") if r.strip()]


def escape_ttl(s):
    return str(s).replace("\\", "\\\\").replace('"', '\\"')


def write_rubrieken_block(f, rubrieken, indent="        "):
    if not rubrieken:
        return
    elms = [elm_uri(r) for r in rubrieken]
    f.write(f"{indent}odrl:target ")
    for i, elm in enumerate(elms):
        suffix = " ;" if i == len(elms) - 1 else ","
        if i == 0:
            f.write(elm + suffix)
        elif i % 6 == 0:
            f.write(f"\n{indent}            {elm}{suffix}")
        else:
            f.write(f" {elm}{suffix}")
    f.write("\n")


def write_constraint_block(f, vwr_expr, indent="        "):
    """Parse a voorwaarderegel and write the ODRL constraint block."""
    if not vwr_expr or not str(vwr_expr).strip():
        return False
    vwr_str = str(vwr_expr).strip()
    try:
        tree = parse_voorwaarderegel(vwr_str)
        turtle = constraint_to_turtle(tree, indent + "    ")
        f.write(
            f'\n{indent}brp:voorwaarderegel """{escape_ttl(vwr_str)}""" ;\n'
        )
        f.write(f"\n{indent}odrl:constraint\n")
        f.write(turtle)
        f.write(" ;\n")
        return True
    except Exception as e:
        print(f"  WARNING: Could not parse: {e}", file=sys.stderr)
        print(f"  Expression: {vwr_str[:100]}", file=sys.stderr)
        f.write(
            f'\n{indent}brp:voorwaarderegel """{escape_ttl(vwr_str)}""" ;\n'
        )
        return False


def generate_autorisatiebesluiten(all_afnemers):
    """Generate the main autorisatiebesluiten TTL file."""
    parse_ok = 0
    parse_fail = 0

    with open(OUTPUT_PATH, "w") as f:
        f.write("""@prefix rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs:   <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl:    <http://www.w3.org/2002/07/owl#> .
@prefix xsd:    <http://www.w3.org/2001/XMLSchema#> .
@prefix dct:    <http://purl.org/dc/terms/> .
@prefix odrl:   <http://www.w3.org/ns/odrl/2/> .
@prefix tpl:    <http://www.w3.org/ns/odrl/2/temporal/> .
@prefix prov:   <http://www.w3.org/ns/prov#> .
@prefix brp:    <https://data.rijksoverheid.nl/brp/def#> .
@prefix brpelm: <https://data.rijksoverheid.nl/brp/element/> .
@prefix brpafn: <https://data.rijksoverheid.nl/brp/afnemer/> .
@prefix brpaut: <https://data.rijksoverheid.nl/brp/autorisatie/> .
@prefix gem:    <https://identifier.overheid.nl/tooi/id/gemeente/> .
@prefix brpnat: <https://data.rijksoverheid.nl/brp/nationaliteit/> .
@prefix brpland: <https://data.rijksoverheid.nl/brp/land/> .
@prefix brpvbt: <https://data.rijksoverheid.nl/brp/verblijfstitel/> .

# =============================================================================
# BRP Autorisatiebesluiten met ODRL Temporal Profile
#
# Alle versies (historisch en actief) van alle autorisatiebesluiten uit
# Tabel 35 (Autorisatietabel BRP), gemodelleerd met het ODRL Temporal Profile.
#
# Elke afnemer heeft een tpl:TemporalSet als duurzame container, met per
# versie een odrl:Set die de geldigheidsperiode vastlegt via
# tpl:effectiveFrom / tpl:effectiveTo.
#
# Voorwaarderegels uit de BRP-syntax (LO-BRP §3.1.3) zijn automatisch
# geparsed en vertaald naar ODRL 2.2 Constraints en LogicalConstraints.
#
# URI-patroon: brpaut:{afnemersindicatie}-v{versie}
#
# Bronnen:
# - Tabel35_Autorisatietabel.xlsx
# - ODRL Temporal Profile: https://w3c.github.io/odrl/profile-temporal/
# - Logisch Ontwerp BRP 2024.Q2, Hoofdstuk 3
# =============================================================================

""")

        # Sort afnemers by indicatie
        sorted_afnemers = sorted(all_afnemers.keys())

        # Afnemers staan in brp-afnemers.ttl (generate_afnemers.py)

        # Write temporal containers + versions per afnemer
        for afn_idx, afn in enumerate(sorted_afnemers):
            rows = all_afnemers[afn]
            afn_str = format_afn(afn)
            latest_naam = rows[-1][COL_AFN_NAAM]
            n_versions = len(rows)

            if afn_idx % 200 == 0:
                print(
                    f"  Processing afnemer {afn_idx + 1}/{len(sorted_afnemers)}"
                    f" ({afn_str})..."
                )

            f.write(
                f"\n# --- {escape_ttl(latest_naam)}"
                f" ({afn_str}, {n_versions} versies) ---\n\n"
            )

            # Temporal container
            version_uris = [
                f"brpaut:{afn_str}-v{row[COL_VERSIE]}" for row in rows
            ]
            f.write(f"brpaut:{afn_str} a tpl:TemporalSet ;\n")
            f.write(f"    odrl:uid brpaut:{afn_str} ;\n")
            f.write(
                "    odrl:profile <https://data.rijksoverheid.nl/brp/def> ;\n"
            )
            f.write(
                f'    dct:title "Autorisatiebesluit'
                f" {escape_ttl(latest_naam)}\"@nl ;\n"
            )
            f.write("    dct:hasPart\n")
            for i, uri in enumerate(version_uris):
                suffix = " ." if i == len(version_uris) - 1 else " ,"
                f.write(f"        {uri}{suffix}\n")

            # Each version
            for row in rows:
                versie = row[COL_VERSIE]
                naam = row[COL_AFN_NAAM]
                ingang = row[COL_INGANG]
                einde = row[COL_EINDE]
                geheim = row[COL_GEHEIM]
                verstr_bep = row[COL_VERSTR_BEP]
                bijz_kind = row[COL_BIJZ_KIND]

                is_active = einde is None or str(einde).strip() == ""
                uri = f"brpaut:{afn_str}-v{versie}"

                f.write(f"\n{uri} a odrl:Set, brp:Autorisatiebesluit ;\n")
                f.write(f"    prov:specializationOf brpaut:{afn_str} ;\n")
                f.write(
                    f'    dct:title "Autorisatiebesluit'
                    f" {escape_ttl(naam)} (versie {versie})\"@nl ;\n"
                )
                f.write(f"    brp:versie {versie} ;\n")
                f.write(
                    f'    tpl:effectiveFrom'
                    f' "{format_date(ingang)}"^^xsd:dateTime ;\n'
                )
                if not is_active:
                    f.write(
                        f'    tpl:effectiveTo'
                        f' "{format_date(einde)}"^^xsd:dateTime ;\n'
                    )

                # Boolean indicaties: alleen schrijven als true
                if geheim:
                    f.write(
                        "    brp:indicatieGeheimhoudingAfnemer true ;\n"
                    )
                if bijz_kind:
                    f.write(
                        "    brp:bijzondereBetrekkingKindVerstrekken true ;\n"
                    )

                # Verstrekkingsbeperking: alleen schrijven als niet "Geen" (0)
                vb = int(verstr_bep) if verstr_bep else 0
                if vb == 1:
                    f.write(
                        "    brp:verstrekkingsbeperking"
                        " brp:VerstrekkingsbeperkingBeperkt ;\n"
                    )
                elif vb == 2:
                    f.write(
                        "    brp:verstrekkingsbeperking"
                        " brp:VerstrekkingsbeperkingVerborgen ;\n"
                    )

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
                    ))

                if not permissions:
                    f.write(
                        '    rdfs:comment "Geen koppelvlakken'
                        ' gedefinieerd in deze versie."@nl .\n'
                    )
                    continue

                for pi, perm in enumerate(permissions):
                    is_last_perm = pi == len(permissions) - 1
                    ptype = perm[0]

                    f.write("\n    odrl:permission [\n")
                    f.write("        a odrl:Permission ;\n")
                    f.write(f"        odrl:assignee brpafn:{afn_str} ;\n")
                    f.write(
                        "        odrl:assigner"
                        " <https://data.rijksoverheid.nl/brp/org/RvIG> ;\n"
                    )

                    if ptype == "spontaan":
                        rub, vwr, med, sleutel, cond = perm[1:]
                        f.write(
                            "        odrl:action"
                            " brp:spontaneVerstrekking ;\n"
                        )
                        rubrieken = rubrieken_to_targets(rub)
                        write_rubrieken_block(f, rubrieken)
                        if med and str(med).strip():
                            med_uri = "brp:MediumNetwerk" if str(med).strip() == "N" else "brp:MediumAnders"
                            f.write(f'        brp:medium {med_uri} ;\n')
                        if sleutel and str(sleutel).strip():
                            sleutels = [
                                s.strip()
                                for s in str(sleutel).split("#")
                                if s.strip()
                            ]
                            sleutel_elms = ", ".join(
                                [elm_uri(s) for s in sleutels]
                            )
                            f.write(
                                f"        brp:sleutelrubriek"
                                f" {sleutel_elms} ;\n"
                            )
                        if cond is not None and str(cond).strip() != "":
                            cond_uri = (
                                "brp:SpontaanConditioneelBericht"
                                if str(cond).strip() == "1"
                                else "brp:SpontaanPlaatsingAfnemersindicatie"
                            )
                            f.write(
                                f"        brp:conditioneleVerstrekking"
                                f" {cond_uri} ;\n"
                            )
                        if vwr and str(vwr).strip():
                            ok = write_constraint_block(f, vwr)
                            if ok:
                                parse_ok += 1
                            else:
                                parse_fail += 1

                    elif ptype == "selectie":
                        rub, vwr, med, sel_soort, sel_periode = perm[1:]
                        f.write(
                            "        odrl:action"
                            " brp:selectieVerstrekking ;\n"
                        )
                        rubrieken = rubrieken_to_targets(rub)
                        if rubrieken:
                            write_rubrieken_block(f, rubrieken)
                        if med and str(med).strip():
                            med_uri = "brp:MediumNetwerk" if str(med).strip() == "N" else "brp:MediumAnders"
                            f.write(f'        brp:medium {med_uri} ;\n')
                        if sel_soort is not None and str(sel_soort).strip() != "":
                            ss_map = {
                                "0": "brp:SelectiesoortVerstrekking",
                                "1": "brp:SelectiesoortPlaatsing",
                                "2": "brp:SelectiesoortLogischVerwijderen",
                                "3": "brp:SelectiesoortVoorwaardelijkVerwijderen",
                                "4": "brp:SelectiesoortOnvoorwaardelijkVerwijderen",
                            }
                            ss_uri = ss_map.get(
                                str(sel_soort).strip(),
                                f'"{sel_soort}"',
                            )
                            f.write(
                                f"        brp:selectiesoort {ss_uri} ;\n"
                            )
                        if sel_periode is not None and str(sel_periode).strip() != "":
                            maanden = int(str(sel_periode).strip())
                            if maanden == 0:
                                f.write(
                                    '        brp:selectieperiode'
                                    ' "P0M"^^xsd:duration ;\n'
                                )
                                f.write(
                                    "        rdfs:comment"
                                    ' "Eenmalige selectie"@nl ;\n'
                                )
                            else:
                                f.write(
                                    f'        brp:selectieperiode'
                                    f' "P{maanden}M"^^xsd:duration ;\n'
                                )
                        if vwr and str(vwr).strip():
                            ok = write_constraint_block(f, vwr)
                            if ok:
                                parse_ok += 1
                            else:
                                parse_fail += 1

                    elif ptype == "adhoc":
                        rub, vwr, med, plaatsing, adresvraag = perm[1:]
                        f.write(
                            "        odrl:action brp:adHocVerstrekking ;\n"
                        )
                        rubrieken = rubrieken_to_targets(rub)
                        write_rubrieken_block(f, rubrieken)
                        if med and str(med).strip():
                            med_uri = "brp:MediumNetwerk" if str(med).strip() == "N" else "brp:MediumAnders"
                            f.write(f'        brp:medium {med_uri} ;\n')
                        if plaatsing and int(plaatsing):
                            f.write(
                                "        odrl:action brp:adHocPlaatsing ;\n"
                            )
                        if adresvraag and int(adresvraag):
                            f.write(
                                "        odrl:action brp:adresVraag ;\n"
                            )
                        if vwr and str(vwr).strip():
                            ok = write_constraint_block(f, vwr)
                            if ok:
                                parse_ok += 1
                            else:
                                parse_fail += 1

                    if is_last_perm:
                        f.write("    ] .\n")
                    else:
                        f.write("    ] ;\n")

        # Bundle
        f.write("""
# =============================================================================
# Bundel: alle temporale autorisatiebesluiten
# =============================================================================

brpaut:autorisatiebesluiten
    a tpl:TemporalSet ;
    odrl:uid brpaut:autorisatiebesluiten ;
    odrl:profile <https://data.rijksoverheid.nl/brp/def> ;
    dct:title "BRP Autorisatiebesluiten (Temporaal)"@nl ;
    dct:description \"\"\"Alle versies (historisch en actief) van alle
autorisatiebesluiten uit Tabel 35, gemodelleerd met het ODRL Temporal Profile.
Elke afnemer is een tpl:TemporalSet met dct:hasPart verwijzingen naar de
individuele versies (odrl:Set) met tpl:effectiveFrom/tpl:effectiveTo.
Voorwaarderegels zijn vertaald naar ODRL Constraints.\"\"\"@nl ;
    dct:issued "2024-04-22"^^xsd:date ;
    odrl:assigner <https://data.rijksoverheid.nl/brp/org/RvIG> ;
    dct:hasPart
""")
        for i, afn in enumerate(sorted_afnemers):
            suffix = " ." if i == len(sorted_afnemers) - 1 else " ,"
            f.write(f"        brpaut:{format_afn(afn)}{suffix}\n")

        f.write("""
# =============================================================================
# Provenance: Tabel 35 als bron
# =============================================================================

brpaut:tabel35
    a prov:Entity ;
    dct:title "Tabel 35 - Autorisatietabel BRP"@nl ;
    dct:source <https://publicaties.rvig.nl/Landelijke_tabellen> .
""")

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
            for i in [COL_VERSIE, COL_AFN_IND, COL_INGANG, COL_EINDE,
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

    print(f"\nGenerating {OUTPUT_PATH}...")
    parse_ok, parse_fail = generate_autorisatiebesluiten(all_afnemers)

    print(f"\nVoorwaarderegels parsed: {parse_ok} OK, {parse_fail} failed")


if __name__ == "__main__":
    main()
