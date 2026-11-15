"""Calculs tapés dans les champs de valeur (comme la calculatrice rapide des
logiciels de DAO) : « 25.4*3/2 », « (120-2*5)/7 », « sqrt(2)*10 »,
« 50*tan(30) » — opérations + − × ÷, puissance ** ou ^, modulo %,
parenthèses, virgule ou point décimal ; fonctions sqrt, abs, round, min,
max, sin, cos, tan (degrés), asin, acos, atan (en degrés), hypot ; pi ;
ans, le dernier résultat s'il est donné.

Unités (le résultat est en mm) : un nombre suivi de mm, cm, dm, m, in ou ",
ft ou ', pt — « 1in », « 2,5cm », « 10pt » ; fractions et pieds-pouces comme
en DAO : « 3/4" », « 6 1/2in », « 1'6" », « 1'-6 1/2" » (lecture d'après
CADCraft, voir THIRD_PARTY_NOTICES.md). Avec « ° », degrés minutes
secondes : « 30°15'36" » → 30,26.

Relèvements de géomètre (d'après CADCraft) : « N45°E », « S30d15'W »,
« N12.5W » ou un point cardinal seul « N », « E », « S », « W » donnent leur
direction en degrés depuis l'est, sens trigonométrique (Y vers le haut) :
N → 90, N45°E → 45, S30°W → 240.

Rien n'est exécuté : l'expression est lue par `ast` et seuls ces éléments
sont acceptés.
"""
from __future__ import annotations

import ast
import math
import operator
import re

_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.Mod: operator.mod, ast.FloorDiv: operator.floordiv}
_UN = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUN = {'sqrt': math.sqrt, 'abs': abs, 'round': round, 'min': min, 'max': max, 'hypot': math.hypot,
        'sin': lambda d: math.sin(math.radians(d)), 'cos': lambda d: math.cos(math.radians(d)),
        'tan': lambda d: math.tan(math.radians(d)), 'asin': lambda v: math.degrees(math.asin(v)),
        'acos': lambda v: math.degrees(math.acos(v)), 'atan': lambda v: math.degrees(math.atan(v))}
_CONST = {'pi': math.pi}


def evaluate(text: str, ans: float | None = None) -> float:
    """Valeur de l'expression (`ans` : le dernier résultat) ; ValueError si
    elle n'est pas un calcul permis."""
    b = bearing(text)
    if b is not None:
        return b
    expr = text.strip().replace('×', '*').replace('÷', '/').replace('^', '**')
    if not expr:
        raise ValueError('expression vide')
    expr = _units(_decimal_commas(expr))
    try:
        tree = ast.parse(expr, mode='eval')
    except SyntaxError as ex:
        raise ValueError(f'calcul illisible : {text}') from ex

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
            return float(n.value)
        if isinstance(n, ast.BinOp) and type(n.op) in _BIN:
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Pow) and abs(b) > 64:
                raise ValueError('puissance trop grande')
            return float(_BIN[type(n.op)](a, b))
        if isinstance(n, ast.UnaryOp) and type(n.op) in _UN:
            return float(_UN[type(n.op)](ev(n.operand)))
        if isinstance(n, ast.Name) and n.id in _CONST:
            return _CONST[n.id]
        if isinstance(n, ast.Name) and n.id.lower() == 'ans':
            if ans is None:
                raise ValueError('pas encore de dernier résultat (ans)')
            return float(ans)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _FUN and not n.keywords:
            return float(_FUN[n.func.id](*[ev(a) for a in n.args]))
        raise ValueError(f'élément refusé dans le calcul : {ast.dump(n)[:40]}')
    try:
        v = ev(tree)
    except (ZeroDivisionError, OverflowError, TypeError) as ex:
        raise ValueError(str(ex)) from ex
    if math.isnan(v) or math.isinf(v):
        raise ValueError('résultat non fini')
    return v


_BEARING = re.compile(r'([NS])\s*(\d+(?:[.,]\d*)?)\s*(?:[d°]\s*(?:(\d+(?:[.,]\d*)?)\s*[\'′]\s*)?'
                      r'(?:(\d+(?:[.,]\d*)?)\s*["″]\s*)?)?([EW])', re.I)
_CARDINAL = {'E': 0.0, 'N': 90.0, 'W': 180.0, 'S': 270.0}


def bearing(text: str) -> float | None:
    """Direction d'un relèvement (« N45°E », « S30d15'W ») ou d'un point
    cardinal seul (« N », « e »…), en degrés depuis l'est, sens
    trigonométrique, dans [0, 360) ; None si le texte n'en est pas un, et
    ValueError si l'angle passe 90°."""
    t = text.strip()
    if t.upper() in _CARDINAL:
        return _CARDINAL[t.upper()]
    m = _BEARING.fullmatch(t)
    if m is None:
        return None
    ns, d, mi, se, ew = m.groups()
    a = sum(float((v or '0').replace(',', '.')) / k for v, k in ((d, 1), (mi, 60), (se, 3600)))
    if a > 90:
        raise ValueError(f'relèvement au-delà de 90° : {text}')
    base = _CARDINAL[ns.upper()]
    turn = -1 if (ns.upper() == 'N') == (ew.upper() == 'E') else 1        # N…E et S…W tournent en sens horaire
    return (base + turn * a) % 360.0


#: unités de longueur après un nombre → mm
UNITS = {'mm': 1.0, 'cm': 10.0, 'dm': 100.0, 'm': 1000.0, 'in': 25.4, '"': 25.4, 'ft': 304.8, "'": 304.8,
         'pt': 25.4 / 72}
_NUM = r'(?<![\w.])(?:(\d+)\s+(\d+)/(\d+)|(\d+)/(\d+)|(\d+(?:\.\d*)?(?:e[+-]?\d+)?|\.\d+(?:e[+-]?\d+)?))'
_PART = re.compile(_NUM + r'\s*(mm|cm|dm|m|in|ft|pt|"|\')(?![a-z])', re.I)
_DMS = re.compile(r'(\d+(?:\.\d*)?)\s*°(?:\s*(\d+(?:\.\d*)?)\s*\')?(?:\s*(\d+(?:\.\d*)?)\s*")?')
_JOIN = re.compile(r'\s*-?\s*')


def _part_value(m) -> float:
    """Longueur d'un nombre suivi de son unité, en mm."""
    a, b, c, n, d, x, unit = m.groups()
    if a is not None:
        if int(c) == 0:
            raise ValueError('fraction par zéro')
        v = int(a) + int(b) / int(c)
    elif n is not None:
        if int(d) == 0:
            raise ValueError('fraction par zéro')
        v = int(n) / int(d)
    else:
        v = float(x)
    return v * UNITS[unit.lower()]


def _units(expr: str) -> str:
    """Nombres suivis d'une unité → leur valeur en mm ; pieds puis pouces
    (« 1'6" », « 1'-6 1/2" ») additionnés ; degrés minutes secondes si
    l'expression a un « ° »."""
    expr = expr.replace('′', "'").replace('″', '"')
    if '°' in expr:
        expr = _DMS.sub(lambda m: '({0!r})'.format(float(m.group(1)) + float(m.group(2) or 0) / 60
                                                  + float(m.group(3) or 0) / 3600), expr)
    out, pos, prev = [], 0, None                  # prev : (valeur, unité) du dernier nombre lu
    for m in _PART.finditer(expr):
        v, unit = _part_value(m), m.group(7).lower()
        gap = expr[pos:m.start()]
        if prev is not None and prev[1] == "'" and unit == '"' and _JOIN.fullmatch(gap):   # 2'-6" : 2 pieds 6 pouces
            v += prev[0]
            out[-1] = '({0!r})'.format(v)
        else:
            out += [gap, '({0!r})'.format(v)]
        pos, prev = m.end(), (v, unit)
    out.append(expr[pos:])
    return ''.join(out)


def _decimal_commas(expr: str) -> str:
    """Virgule décimale (« 2,5 ») changée en point ; une virgule entre deux
    arguments de fonction (« min(2, 5) », suivie d'une espace) reste."""
    out = []
    for i, ch in enumerate(expr):
        if ch == ',' and 0 < i < len(expr) - 1 and expr[i - 1].isdigit() and expr[i + 1].isdigit():
            out.append('.')
        else:
            out.append(ch)
    return ''.join(out)
