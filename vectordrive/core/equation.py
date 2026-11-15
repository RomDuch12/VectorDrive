"""Courbes par équation et guilloché : des formules aux contours, à une tolérance donnée.

Formules : x(t) et y(t), y = f(x) ou, en polaire, r = f(a). Angles en radians, comme en mathématiques. Rien n'est exécuté :
la formule est lue par `ast`, seuls les calculs permis sont gardés, et chaque valeur reste un nombre à virgule (un entier géant
ne peut pas bloquer le logiciel).
"""
from __future__ import annotations

import ast
import math
import operator
from dataclasses import dataclass

from . import fitcurve
from .calc import _decimal_commas
from .geom import Contour, Path, dist, polyline

#: écart admis aux formules (mm)
TOL = 0.01
#: points de départ sur l'intervalle, profondeur et nombre de calculs au plus ; au-delà, la courbe n'est plus affinée
START_POINTS = 400
MAX_DEPTH = 14
MAX_EVALS = 300_000
MAX_LINES, MAX_LOBES = 500, 500
MAX_SPIRO_TURNS = 500
#: au-delà (mm), une valeur est hors domaine : 1/x près de 0 ne donne pas une courbe de 200 km
MAX_COORD = 100_000.0

_FUN = {'sin': math.sin, 'cos': math.cos, 'tan': math.tan, 'asin': math.asin, 'acos': math.acos, 'atan': math.atan,
        'atan2': math.atan2, 'sinh': math.sinh, 'cosh': math.cosh, 'tanh': math.tanh, 'sqrt': math.sqrt, 'abs': abs,
        'exp': math.exp, 'log': math.log, 'ln': math.log, 'log10': math.log10, 'floor': math.floor, 'ceil': math.ceil,
        'round': round, 'min': min, 'max': max, 'hypot': math.hypot, 'deg': math.degrees, 'rad': math.radians,
        'sign': lambda v: (v > 0) - (v < 0)}
_CONST = {'pi': math.pi, 'tau': math.tau, 'e': math.e}
_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: math.pow, ast.Mod: operator.mod, ast.FloorDiv: operator.floordiv}
_UN = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_MATH_ERRORS = (ValueError, ZeroDivisionError, OverflowError)


def compile_expr(text: str, var: str = 't'):
    """La formule en fonction d'une variable. ValueError si elle est illisible ou contient autre chose qu'un calcul."""
    expr = text.strip().replace('×', '*').replace('÷', '/').replace('^', '**').replace('π', 'pi')
    if not expr:
        raise ValueError('formule vide')
    try:
        tree = ast.parse(_decimal_commas(expr), mode='eval')
    except (SyntaxError, ValueError, RecursionError, MemoryError) as ex:
        raise ValueError(f'formule illisible : {text}') from ex

    def build(n):
        if isinstance(n, ast.Expression):
            return build(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
            v = float(n.value)
            return lambda _x: v
        if isinstance(n, ast.BinOp) and type(n.op) in _BIN:
            a, b, op = build(n.left), build(n.right), _BIN[type(n.op)]
            return lambda x: op(a(x), b(x))
        if isinstance(n, ast.UnaryOp) and type(n.op) in _UN:
            a, op = build(n.operand), _UN[type(n.op)]
            return lambda x: op(a(x))
        if isinstance(n, ast.Name):
            if n.id == var:
                return lambda x: x
            if n.id in _CONST:
                v = _CONST[n.id]
                return lambda _x: v
            raise ValueError(f'inconnu dans la formule : {n.id}')
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _FUN and not n.keywords:
            fn, args = _FUN[n.func.id], [build(a) for a in n.args]
            if len(args) == 1:
                a = args[0]
                return lambda x: fn(a(x))
            return lambda x: fn(*[f(x) for f in args])
        raise ValueError('seuls les calculs sont permis dans une formule')
    try:
        f = build(tree)
    except RecursionError as ex:
        raise ValueError(f'formule illisible : {text}') from ex
    try:
        f(1.0)                                           # nombre d'arguments d'une fonction
    except TypeError as ex:
        raise ValueError(f'formule illisible : {text}') from ex
    except (*_MATH_ERRORS, RecursionError):
        pass                                             # hors du domaine en ce point : pas une faute de frappe
    return f


def value_of(text: str) -> float:
    """Une borne : un nombre ou un calcul sans variable (« 2*pi »)."""
    try:
        v = float(compile_expr(text, '')(0.0))
    except (*_MATH_ERRORS[1:], TypeError) as ex:
        raise ValueError(f'valeur illisible : {text}') from ex
    if not math.isfinite(v):
        raise ValueError(f'valeur illisible : {text}')
    return v


def _point(fn, t: float):
    """(x, y) en t, None hors du domaine ou non fini."""
    try:
        x, y = fn(t)
        x, y = float(x), float(y)
    except _MATH_ERRORS:
        return None
    return (x, y) if abs(x) <= MAX_COORD and abs(y) <= MAX_COORD else None         # NaN et infini ne passent pas non plus


def _chord_gap(p, a, b) -> float:
    """Écart du point p à la corde a-b."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy)
    if L < 1e-12:
        return dist(p, a)
    return abs((p[0] - a[0]) * dy - (p[1] - a[1]) * dx) / L


def sample(fn, t0: float, t1: float, tol: float = TOL, start: int = START_POINTS, jumps: bool = True) -> list[list[tuple]]:
    """Morceaux continus de la courbe t -> fn(t) : une coupure hors du domaine ou à un saut. Plus de points où elle tourne.
    `jumps` : chercher les sauts. Un saut ressemble à un trait droit : seul un intervalle affiné jusqu'au bout sans que la
    corde raccourcisse le trahit. Inutile, et bien plus long, sur une courbe qu'on sait continue."""
    if t0 == t1:
        raise ValueError('intervalle vide')
    jump = max(10.0 * tol, 0.1)
    evals = [0]
    runs: list[list] = []
    cur: list = []

    def at(t):
        evals[0] += 1
        return _point(fn, t)

    def cut():
        nonlocal cur
        if len(cur) > 1:
            runs.append(cur)
        cur = []

    def between(ta, pa, tb, pb, depth):
        if evals[0] < MAX_EVALS and depth < MAX_DEPTH:
            tm = (ta + tb) / 2
            pm = at(tm)
            if pm is None:
                edge(ta, pa, tm, True)
                cut()
                edge(tm, None, tb, False)
                between_from_edge(tb, pb)
                return
            if _chord_gap(pm, pa, pb) > tol or dist(pm, pa) + dist(pm, pb) > 1.5 * dist(pa, pb) + tol                     or (jumps and dist(pa, pb) > jump):
                between(ta, pa, tm, pm, depth + 1)
                between(tm, pm, tb, pb, depth + 1)
                return
        elif jumps and depth >= MAX_DEPTH and dist(pa, pb) > jump:
            cut()                                        # saut : pas de trait entre les deux
        cur.append(pb)

    def between_from_edge(tb, pb):
        cur.append(pb)

    def edge(ta, pa, tb, after_a: bool):
        """La limite du domaine : le dernier point valable après a, ou le premier avant b."""
        lo, hi = ta, tb
        best = None
        for _ in range(24):
            mid = (lo + hi) / 2
            p = at(mid)
            if p is not None:
                best = p
                if after_a:
                    lo = mid
                else:
                    hi = mid
            elif after_a:
                hi = mid
            else:
                lo = mid
        if best is not None:
            cur.append(best)

    ts = [t0 + (t1 - t0) * i / start for i in range(start + 1)]
    prev_t, prev = ts[0], at(ts[0])
    if prev is not None:
        cur.append(prev)
    for t in ts[1:]:
        p = at(t)
        if prev is not None and p is not None:
            between(prev_t, prev, t, p, 0)
        elif prev is not None:
            edge(prev_t, prev, t, True)
            cut()
        elif p is not None:
            edge(prev_t, None, t, False)
            cur.append(p)
        prev_t, prev = t, p
    cut()
    return runs


def _contour(pts: list, tol: float, fit: bool) -> Contour | None:
    closed = len(pts) > 3 and dist(pts[0], pts[-1]) < max(tol / 5.0, 1e-6)
    c = polyline(pts[:-1] if closed else pts, closed)
    if not c.segments:
        return None
    if fit:
        c = fitcurve.approximate_contour(c, tol)
    return c if c.segments else None


def to_path(runs: list, tol: float = TOL, fit: bool = True) -> Path:
    return Path([c for c in (_contour(r, tol, fit) for r in runs) if c is not None])


def equation_path(kind: str, first: str, second: str, start: str, end: str, tol: float = TOL, fit: bool = True) -> Path:
    """kind 'xy' : x(t) = first, y(t) = second ; 'y' : y = first(x) ; 'polar' : r = first(a). ValueError si c'est illisible."""
    t0, t1 = value_of(start), value_of(end)
    if kind == 'xy':
        fx, fy = compile_expr(first, 't'), compile_expr(second, 't')
        fn = lambda t: (fx(t), fy(t))
    elif kind == 'y':
        f = compile_expr(first, 'x')
        fn = lambda x: (x, f(x))
    elif kind == 'polar':
        f = compile_expr(first, 'a')

        def fn(a):
            r = f(a)
            return r * math.cos(a), r * math.sin(a)
    else:
        raise ValueError(f'genre de courbe inconnu : {kind}')
    return to_path(sample(fn, t0, t1, tol / 2.0), tol, fit)


#: Courbes toutes prêtes : nom, genre, première formule, seconde, début, fin
PRESETS = (('Rose', 'polar', '30*cos(5*a)', '', '0', 'pi'),
           ('Cardioïde', 'polar', '20*(1-cos(a))', '', '0', '2*pi'),
           ('Lemniscate', 'xy', '40*cos(t)/(1+sin(t)^2)', '40*sin(t)*cos(t)/(1+sin(t)^2)', '0', '2*pi'),
           ('Spirale d\'Archimède', 'polar', '2*a', '', '0', '12*pi'),
           ('Spirale logarithmique', 'polar', 'exp(0.15*a)', '', '0', '8*pi'),
           ('Cœur', 'xy', '2*16*sin(t)^3', '2*(13*cos(t)-5*cos(2*t)-2*cos(3*t)-cos(4*t))', '0', '2*pi'),
           ('Lissajous', 'xy', '40*sin(3*t+pi/2)', '30*sin(2*t)', '0', '2*pi'),
           ('Sinusoïde', 'y', '10*sin(x/5)', '', '0', '100'))


@dataclass
class GuillocheSpec:
    """Motifs de traits entrelacés. rosette : courbes fermées autour d'un centre ; band : bande droite ; spiro : spirographe."""
    kind: str = 'rosette'
    lines: int = 24                                      # nombre de traits, décalés régulièrement
    radius: float = 40.0                                 # rosette : rayon moyen
    amplitude: float = 8.0                               # rosette et bande : hauteur de la vague
    lobes: int = 12                                      # rosette : vagues sur un tour
    amplitude2: float = 0.0                              # seconde vague, plus lente : le motif ondule
    lobes2: int = 0
    length: float = 120.0                                # bande : longueur
    wavelength: float = 20.0                             # bande : longueur d'une vague
    wavelength2: float = 0.0
    big: float = 50.0                                    # spirographe : rayon du cercle fixe
    small: float = 17.0                                  # spirographe : rayon du cercle qui roule
    pen: float = 30.0                                    # spirographe : distance du stylo au centre du cercle qui roule
    outside: bool = False                                # spirographe : le petit cercle roule au-dehors


def _in_range(v, lo, hi, name) -> None:
    if not lo <= v <= hi:
        raise ValueError(f'{name} : entre {lo} et {hi}')


def _rosette(s: GuillocheSpec, tol: float) -> list:
    _in_range(s.lobes, 1, MAX_LOBES, 'vagues')
    _in_range(s.lobes2, 0, MAX_LOBES, 'vagues')
    if s.radius <= 0:
        raise ValueError('le rayon doit être positif')
    out = []
    start = max(START_POINTS, 32 * max(s.lobes, s.lobes2))
    for i in range(s.lines):
        ph = math.tau * i / s.lines

        def fn(a, ph=ph):
            r = s.radius + s.amplitude * math.sin(s.lobes * a + ph) + s.amplitude2 * math.sin(s.lobes2 * a)
            return r * math.cos(a), r * math.sin(a)
        out.extend(sample(fn, 0.0, math.tau, tol, start, jumps=False))
    return out


def _band(s: GuillocheSpec, tol: float) -> list:
    if s.length <= 0 or s.wavelength <= 0:
        raise ValueError('longueur et longueur de vague doivent être positives')
    if s.length / s.wavelength > MAX_LOBES:
        raise ValueError(f'vagues : au plus {MAX_LOBES}')
    out = []
    start = max(START_POINTS, int(32 * s.length / s.wavelength))
    w2 = s.wavelength2
    for i in range(s.lines):
        ph = math.tau * i / s.lines

        def fn(x, ph=ph):
            y = s.amplitude * math.sin(math.tau * x / s.wavelength + ph)
            return x, y + (s.amplitude2 * math.sin(math.tau * x / w2) if w2 > 0 else 0.0)
        out.extend(sample(fn, 0.0, s.length, tol, start, jumps=False))
    return out


def _spiro(s: GuillocheSpec, tol: float) -> list:
    if s.big <= 0 or s.small <= 0:
        raise ValueError('les rayons doivent être positifs')
    R, r, d = s.big, s.small, s.pen
    turns = round(r * 1000) // math.gcd(round(R * 1000), round(r * 1000))    # tours pour revenir au départ
    if not 1 <= turns <= MAX_SPIRO_TURNS:
        raise ValueError(f'trop de tours pour refermer la courbe ({turns}) : prendre des rayons plus ronds')
    sign = 1.0 if s.outside else -1.0
    k = (R + sign * r) / r

    def base(t):
        return (R + sign * r) * math.cos(t) - sign * d * math.cos(k * t), (R + sign * r) * math.sin(t) - d * math.sin(k * t)
    first = sample(base, 0.0, math.tau * turns, tol, max(START_POINTS, 64 * turns), jumps=False)
    out = []
    for i in range(s.lines):
        a = math.tau * i / s.lines
        ca, sa = math.cos(a), math.sin(a)
        out.extend([[(x * ca - y * sa, x * sa + y * ca) for x, y in run] for run in first])
    return out


def guilloche(s: GuillocheSpec, tol: float = TOL, fit: bool = True) -> Path:
    """Les traits du motif ; ValueError si les réglages sont impossibles."""
    _in_range(s.lines, 1, MAX_LINES, 'traits')
    fn = {'rosette': _rosette, 'band': _band, 'spiro': _spiro}.get(s.kind)
    if fn is None:
        raise ValueError(f'motif inconnu : {s.kind}')
    return to_path(fn(s, tol / 2.0), tol, fit)
