"""Esquisse contrainte : points, traits, cercles et arcs tenus par des contraintes et des cotes.

L'idée vient de SolidCraft : on dit ce qui doit rester vrai (horizontal, tangent, égal, 40 mm…) et un solveur place la
géométrie. Le solveur est écrit ici, en numpy, sur le principe de Gauss-Newton : à chaque pas, la plus petite retouche
qui réduit les écarts (moindre mouvement : ce qui n'est pas contraint bouge le moins possible). Sous la souris, le point
tiré suit tant que les contraintes le permettent : elles passent d'abord, le geste dans ce qu'elles laissent libre.

Un rapport dit ce qui reste libre (degrés de liberté), ce qui est de trop, ce qui se contredit. Un solveur qui échoue
laisse la géométrie comme elle était.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .geom import Contour, Line, Path, Conic, arc_conics, circle as geom_circle

#: écart admis sur une contrainte (mm)
TOLERANCE = 1e-7
_STEP = 1e-6
_RANK = 1e-8
_MAX_ITER = 80
#: pas de suite sans progrès : on abandonne
_STALL = 8
#: secousses essayées à tour de rôle (part de la taille de la figure)
_TRIES = (0.0, 0.01, 0.1)
#: contraintes passées une à une pour trouver celles qui se contredisent ; au-delà, seule la dernière est soupçonnée
_MAX_SUSPECTS = 60

#: nom → (nature des références, a une valeur)
KINDS = {
    'coincident': ('pp', False), 'on_line': ('pl', False), 'on_circle': ('pc', False),
    'horizontal': ('l', False), 'vertical': ('l', False), 'h_points': ('pp', False), 'v_points': ('pp', False),
    'parallel': ('ll', False), 'perpendicular': ('ll', False), 'collinear': ('ll', False),
    'tangent_lc': ('lc', False), 'tangent_cc': ('cc', False), 'equal_ll': ('ll', False), 'equal_cc': ('cc', False),
    'concentric': ('cc', False), 'midpoint': ('pl', False), 'symmetric': ('ppl', False), 'fix': ('p', True),
    'distance': ('pp', True), 'distance_x': ('pp', True), 'distance_y': ('pp', True), 'point_line': ('pl', True),
    'length': ('l', True), 'radius': ('c', True), 'diameter': ('c', True), 'angle': ('ll', True),
}


@dataclass
class Constraint:
    id: int
    kind: str
    refs: tuple
    value: object = None

    def to_dict(self) -> dict:
        v = list(self.value) if isinstance(self.value, (list, tuple)) else self.value
        return {'id': self.id, 'kind': self.kind, 'refs': list(self.refs), 'value': v}


@dataclass
class Report:
    ok: bool = True
    dof: int = 0
    conflicts: list = field(default_factory=list)      # ids : l'une de ces contraintes en moins, ça se résout
    redundant: list = field(default_factory=list)      # ids : déjà dites par les autres
    free_points: set = field(default_factory=set)
    free_radii: set = field(default_factory=set)

    @property
    def complete(self) -> bool:
        return self.ok and self.dof == 0


def _hypot(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _cross(ax, ay, bx, by) -> float:
    return ax * by - ay * bx


def _wrap(a: float) -> float:
    return (a + math.pi) % (2 * math.pi) - math.pi


class Sketch:
    def __init__(self):
        self.points: dict[int, list] = {}
        self.lines: dict[int, dict] = {}
        self.circles: dict[int, dict] = {}
        self.constraints: list[Constraint] = []
        self._next = 1

    # --- construction ---------------------------------------------------------------------------------------------
    def _id(self) -> int:
        n = self._next
        self._next += 1
        return n

    def add_point(self, x: float, y: float) -> int:
        n = self._id()
        self.points[n] = [float(x), float(y)]
        return n

    def add_line(self, p: int, q: int, construction: bool = False) -> int:
        n = self._id()
        self.lines[n] = {'p': p, 'q': q, 'construction': bool(construction)}
        return n

    def add_circle(self, c: int, r: float, construction: bool = False) -> int:
        n = self._id()
        self.circles[n] = {'c': c, 'r': float(r), 'a': None, 'b': None, 'ccw': True, 'construction': bool(construction)}
        return n

    def add_arc(self, c: int, a: int, b: int, ccw: bool = True, construction: bool = False) -> int:
        """Arc de `a` à `b` autour de `c` ; ses bouts restent sur le cercle."""
        n = self._id()
        self.circles[n] = {'c': c, 'r': _hypot(self.points[a], self.points[c]), 'a': a, 'b': b, 'ccw': bool(ccw),
                           'construction': bool(construction)}
        return n

    def add_constraint(self, kind: str, *refs, value=None) -> Constraint:
        spec = KINDS.get(kind)
        if spec is None or len(spec[0]) != len(refs):
            raise ValueError(kind)
        for r, t in zip(refs, spec[0]):
            if r not in {'p': self.points, 'l': self.lines, 'c': self.circles}[t]:
                raise ValueError(f'{kind} : référence {r}')
        if kind == 'fix' and value is None:
            value = tuple(self.points[refs[0]])
        c = Constraint(self._id(), kind, tuple(refs), value)
        self.constraints.append(c)
        return c

    def add_rect(self, x0: float, y0: float, x1: float, y1: float) -> list[int]:
        """Quatre traits qui se suivent, tenus horizontaux et verticaux."""
        pts = [self.add_point(x, y) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
        out = [self.add_line(pts[i], pts[(i + 1) % 4]) for i in range(4)]
        for k, ln in enumerate(out):
            self.add_constraint('horizontal' if k % 2 == 0 else 'vertical', ln)
        return out

    def remove(self, n: int) -> None:
        """Retire un point, un trait, un cercle ou une contrainte ; avec eux ce qui en dépend et les points devenus seuls."""
        self.constraints = [c for c in self.constraints if c.id != n and n not in c.refs]
        if n in self.points:
            for k, v in list(self.lines.items()):
                if n in (v['p'], v['q']):
                    self.remove(k)
            for k, v in list(self.circles.items()):
                if n in (v['c'], v['a'], v['b']):
                    self.remove(k)
            self.points.pop(n, None)
            self.constraints = [c for c in self.constraints if n not in c.refs]
            return
        gone = self.lines.pop(n, None) or self.circles.pop(n, None)
        if gone:
            for key in ('p', 'q', 'c', 'a', 'b'):
                pid = gone.get(key)
                if pid is not None and pid in self.points and not self._point_used(pid):
                    self.points.pop(pid)
                    self.constraints = [c for c in self.constraints if pid not in c.refs]

    def _point_used(self, p: int) -> bool:
        return any(p in (v['p'], v['q']) for v in self.lines.values()) or \
            any(p in (v['c'], v['a'], v['b']) for v in self.circles.values())

    # --- enregistrement -------------------------------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {'points': [[k, *v] for k, v in self.points.items()],
                'lines': [{'id': k, **v} for k, v in self.lines.items()],
                'circles': [{'id': k, **v} for k, v in self.circles.items()],
                'constraints': [c.to_dict() for c in self.constraints], 'next': self._next}

    @classmethod
    def from_dict(cls, d: dict) -> 'Sketch':
        s = cls()
        for k, x, y in d.get('points', ()):
            s.points[int(k)] = [float(x), float(y)]
        for v in d.get('lines', ()):
            s.lines[int(v['id'])] = {'p': int(v['p']), 'q': int(v['q']), 'construction': bool(v.get('construction'))}
        for v in d.get('circles', ()):
            s.circles[int(v['id'])] = {'c': int(v['c']), 'r': float(v['r']),
                                       'a': None if v.get('a') is None else int(v['a']),
                                       'b': None if v.get('b') is None else int(v['b']), 'ccw': bool(v.get('ccw', True)),
                                       'construction': bool(v.get('construction'))}
        for c in d.get('constraints', ()):
            val = c.get('value')
            s.constraints.append(Constraint(int(c['id']), c['kind'], tuple(int(r) for r in c['refs']),
                                            tuple(val) if isinstance(val, list) else val))
        known = [*s.points, *s.lines, *s.circles, *(c.id for c in s.constraints)]
        s._next = max([int(d.get('next', 1)), *(n + 1 for n in known)])
        return s

    def copy(self) -> 'Sketch':
        return Sketch.from_dict(self.to_dict())

    # --- variables ------------------------------------------------------------------------------------------------
    def _vector(self) -> tuple[dict, np.ndarray]:
        """{point : indice de x} (y le suit), {cercle : indice du rayon} dans le même dictionnaire ; les valeurs."""
        index: dict = {}
        vals: list = []
        for k, v in self.points.items():
            index[k] = len(vals)
            vals.extend(v)
        for k, v in self.circles.items():
            index[k] = len(vals)
            vals.append(v['r'])
        return index, np.array(vals, dtype=float)

    def _store(self, index: dict, x: np.ndarray) -> None:
        for k in self.points:
            i = index[k]
            self.points[k] = [float(x[i]), float(x[i + 1])]
        for k in self.circles:
            self.circles[k]['r'] = float(x[index[k]])

    def _variables(self, c: Constraint, index: dict) -> list[int]:
        """Les inconnues que touche une contrainte."""
        out: list[int] = []

        def add_point(p: int) -> None:
            out.extend((index[p], index[p] + 1))
        for r, t in zip(c.refs, KINDS[c.kind][0]):
            if t == 'p':
                add_point(r)
            elif t == 'l':
                add_point(self.lines[r]['p'])
                add_point(self.lines[r]['q'])
            else:
                add_point(self.circles[r]['c'])
                out.append(index[r])
        return out

    def _implicit(self) -> list[Constraint]:
        """Les bouts d'un arc restent sur son cercle."""
        out = []
        for k, v in self.circles.items():
            if v['a'] is not None:
                out.append(Constraint(-k * 2, 'on_circle', (v['a'], k)))
                out.append(Constraint(-k * 2 - 1, 'on_circle', (v['b'], k)))
        return out

    # --- écarts ---------------------------------------------------------------------------------------------------
    def _freeze(self, c: Constraint, index: dict, x) -> float:
        """Le côté, gardé pendant la résolution : une cote n'inverse pas la figure."""
        g = _Reader(self, index, x)
        if c.kind == 'distance_x':
            return -1.0 if g.pt(c.refs[1])[0] < g.pt(c.refs[0])[0] else 1.0
        if c.kind == 'distance_y':
            return -1.0 if g.pt(c.refs[1])[1] < g.pt(c.refs[0])[1] else 1.0
        if c.kind == 'point_line':
            return -1.0 if g.side(c.refs[0], c.refs[1]) < 0 else 1.0
        if c.kind == 'tangent_lc':
            return -1.0 if g.side(self.circles[c.refs[1]]['c'], c.refs[0]) < 0 else 1.0
        if c.kind == 'tangent_cc':
            a, b = c.refs
            d = _hypot(g.pt(self.circles[a]['c']), g.pt(self.circles[b]['c']))
            ra, rb = g.rad(a), g.rad(b)
            if d >= max(ra, rb):
                return 0.0                               # extérieurs
            return 1.0 if ra >= rb else -1.0             # l'un dans l'autre
        if c.kind == 'angle':
            return -1.0 if g.angle(*c.refs) < 0 else 1.0
        return 1.0

    def _residual(self, c: Constraint, g: '_Reader', side: float) -> tuple:
        k, r = c.kind, c.refs
        if k == 'coincident':
            a, b = g.pt(r[0]), g.pt(r[1])
            return a[0] - b[0], a[1] - b[1]
        if k == 'on_line':
            return (g.side(r[0], r[1]),)
        if k == 'on_circle':
            return (_hypot(g.pt(r[0]), g.pt(self.circles[r[1]]['c'])) - g.rad(r[1]),)
        if k == 'horizontal':
            a, b = g.ends(r[0])
            return (a[1] - b[1],)
        if k == 'vertical':
            a, b = g.ends(r[0])
            return (a[0] - b[0],)
        if k == 'h_points':
            return (g.pt(r[0])[1] - g.pt(r[1])[1],)
        if k == 'v_points':
            return (g.pt(r[0])[0] - g.pt(r[1])[0],)
        if k in ('parallel', 'perpendicular'):
            (ax, ay), la = g.unit(r[0])
            (bx, by), lb = g.unit(r[1])
            scale = (la + lb) / 2
            return ((_cross(ax, ay, bx, by) if k == 'parallel' else ax * bx + ay * by) * scale,)
        if k == 'collinear':
            ln = self.lines[r[1]]
            return g.side(ln['p'], r[0]), g.side(ln['q'], r[0])
        if k == 'tangent_lc':
            return (side * g.side(self.circles[r[1]]['c'], r[0]) - g.rad(r[1]),)
        if k == 'tangent_cc':
            d = _hypot(g.pt(self.circles[r[0]]['c']), g.pt(self.circles[r[1]]['c']))
            ra, rb = g.rad(r[0]), g.rad(r[1])
            return (d - (ra + rb) if side == 0.0 else d - side * (ra - rb),)
        if k == 'equal_ll':
            return (g.length(r[0]) - g.length(r[1]),)
        if k == 'equal_cc':
            return (g.rad(r[0]) - g.rad(r[1]),)
        if k == 'concentric':
            a, b = g.pt(self.circles[r[0]]['c']), g.pt(self.circles[r[1]]['c'])
            return a[0] - b[0], a[1] - b[1]
        if k == 'midpoint':
            p = g.pt(r[0])
            a, b = g.ends(r[1])
            return p[0] - (a[0] + b[0]) / 2, p[1] - (a[1] + b[1]) / 2
        if k == 'symmetric':
            p, q = g.pt(r[0]), g.pt(r[1])
            a, b = g.ends(r[2])
            (ux, uy), _ln = g.unit(r[2])
            mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
            return _cross(ux, uy, mx - a[0], my - a[1]), (q[0] - p[0]) * ux + (q[1] - p[1]) * uy
        if k == 'fix':
            p = g.pt(r[0])
            return p[0] - float(c.value[0]), p[1] - float(c.value[1])
        if k == 'distance':
            return (_hypot(g.pt(r[0]), g.pt(r[1])) - float(c.value),)
        if k == 'distance_x':
            return (side * (g.pt(r[1])[0] - g.pt(r[0])[0]) - float(c.value),)
        if k == 'distance_y':
            return (side * (g.pt(r[1])[1] - g.pt(r[0])[1]) - float(c.value),)
        if k == 'point_line':
            return (side * g.side(r[0], r[1]) - float(c.value),)
        if k == 'length':
            return (g.length(r[0]) - float(c.value),)
        if k == 'radius':
            return (g.rad(r[0]) - float(c.value),)
        if k == 'diameter':
            return (2 * g.rad(r[0]) - float(c.value),)
        if k == 'angle':
            scale = (g.length(r[0]) + g.length(r[1])) / 2
            return (_wrap(side * g.angle(r[0], r[1]) - math.radians(float(c.value))) * scale,)
        raise ValueError(k)

    def solve(self, hold: dict | None = None, skip=(), analyse: bool = True) -> Report:
        """Place la géométrie. `hold` : {point : (x, y), cercle : rayon}, ce qu'on tire à la souris : suivi autant que les
        contraintes le permettent. `skip` : ids de contraintes ignorées. `analyse` : compter ce qui reste libre et ce qui est de trop
        (sous la souris, on s'en passe). Échec : la géométrie ne bouge pas."""
        index, x0 = self._vector()
        items = [c for c in self.constraints if c.id not in skip] + self._implicit()
        got = _solve(self, items, index, x0, hold or {})
        report = _analyse(self, items, index, got if got is not None else x0) if analyse else Report()
        report.ok = got is not None
        if got is not None:
            self._store(index, got)
        elif analyse:
            report.conflicts = self._conflicts(items, index, x0)
        return report

    def _conflicts(self, items: list, index: dict, x0) -> list[int]:
        """Les contraintes dont le retrait suffit à résoudre."""
        mine = [c for c in items if c.id > 0]
        suspects = mine if len(mine) <= _MAX_SUSPECTS else mine[-1:]
        tries = _TRIES if len(suspects) <= 20 else _TRIES[:1]
        out = []
        for c in suspects:
            if _solve(self, [o for o in items if o.id != c.id], index, x0, {}, tries) is not None:
                out.append(c.id)
        return out

    def value_of(self, c: Constraint) -> float:
        """La cote telle que la géométrie la donne, sans la contrainte."""
        index, x = self._vector()
        g = _Reader(self, index, x)
        side = self._freeze(c, index, x)
        probe = Constraint(c.id, c.kind, c.refs, 0.0)
        got = self._residual(probe, g, side)[0]
        if c.kind == 'angle':
            return math.degrees(side * g.angle(*c.refs))
        return got

    # --- tracés ---------------------------------------------------------------------------------------------------
    def _merged(self) -> dict:
        """Points confondus par une contrainte de coïncidence : leur représentant."""
        parent = {k: k for k in self.points}

        def find(a: int) -> int:
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a
        for c in self.constraints:
            if c.kind == 'coincident':
                parent[find(c.refs[0])] = find(c.refs[1])
        return {k: find(k) for k in parent}

    def _arc_angles(self, v: dict, reverse: bool = False) -> tuple:
        c = self.points[v['c']]
        a, b = self.points[v['a']], self.points[v['b']]
        start = math.atan2(a[1] - c[1], a[0] - c[0])
        end = math.atan2(b[1] - c[1], b[0] - c[0])
        sweep = (end - start) % (2 * math.pi) if v['ccw'] else -((start - end) % (2 * math.pi))
        if abs(sweep) < 1e-12:
            sweep = 2 * math.pi if v['ccw'] else -2 * math.pi
        if reverse:
            return math.degrees(end), -math.degrees(sweep)
        return math.degrees(start), math.degrees(sweep)

    def _pieces(self, eid: int, reverse: bool) -> list:
        if eid in self.lines:
            v = self.lines[eid]
            a, b = (v['q'], v['p']) if reverse else (v['p'], v['q'])
            return [Line(tuple(self.points[a]), tuple(self.points[b]))]
        v = self.circles[eid]
        start, sweep = self._arc_angles(v, reverse)
        return list(arc_conics(tuple(self.points[v['c']]), v['r'], v['r'], start, sweep))

    def to_path(self) -> Path:
        """Le tracé : cercles entiers, et traits et arcs enchaînés par leurs points communs. La construction n'en est pas."""
        contours = [geom_circle(tuple(self.points[v['c']]), v['r']) for v in self.circles.values()
                    if v['a'] is None and not v['construction']]
        merged = self._merged()
        ends = {}
        for k, v in self.lines.items():
            if not v['construction']:
                ends[k] = (merged[v['p']], merged[v['q']])
        for k, v in self.circles.items():
            if v['a'] is not None and not v['construction']:
                ends[k] = (merged[v['a']], merged[v['b']])
        at: dict = {}
        for k, (a, b) in ends.items():
            at.setdefault(a, []).append(k)
            at.setdefault(b, []).append(k)
        used: set = set()

        def walk(start_node: int, first: int) -> tuple[list, int]:
            chain, node, eid = [], start_node, first
            while True:
                used.add(eid)
                a, b = ends[eid]
                reverse = a != node
                chain.extend(self._pieces(eid, reverse))
                node = a if reverse else b
                nxt = next((e for e in at[node] if e not in used), None)
                if nxt is None or len(at[node]) > 2 and node != start_node:
                    return chain, node
                eid = nxt

        for node in sorted(at, key=lambda nd: (len(at[nd]) == 2,)):   # bouts libres et carrefours d'abord
            for eid in at[node]:
                if eid in used:
                    continue
                chain, last = walk(node, eid)
                contours.append(Contour(chain, last == node))
        return Path(contours)


class _Reader:
    """Lecture de la géométrie dans le vecteur des inconnues."""
    __slots__ = ('sk', 'index', 'x')

    def __init__(self, sk: Sketch, index: dict, x):
        self.sk, self.index, self.x = sk, index, x

    def pt(self, p: int) -> tuple:
        i = self.index[p]
        return self.x[i], self.x[i + 1]

    def rad(self, c: int) -> float:
        return self.x[self.index[c]]

    def ends(self, ln: int) -> tuple:
        v = self.sk.lines[ln]
        return self.pt(v['p']), self.pt(v['q'])

    def length(self, ln: int) -> float:
        a, b = self.ends(ln)
        return _hypot(a, b)

    def unit(self, ln: int) -> tuple:
        a, b = self.ends(ln)
        d = _hypot(a, b)
        if d < 1e-12:
            return (1.0, 0.0), 0.0
        return ((b[0] - a[0]) / d, (b[1] - a[1]) / d), d

    def side(self, p: int, ln: int) -> float:
        """Distance signée du point au trait."""
        a, b = self.ends(ln)
        q = self.pt(p)
        d = _hypot(a, b)
        if d < 1e-12:
            return _hypot(q, a)
        return _cross(b[0] - a[0], b[1] - a[1], q[0] - a[0], q[1] - a[1]) / d

    def angle(self, a: int, b: int) -> float:
        (ax, ay), _la = self.unit(a)
        (bx, by), _lb = self.unit(b)
        return math.atan2(_cross(ax, ay, bx, by), ax * bx + ay * by)


def _rows(sk: Sketch, items: list, index: dict, sides: dict, x) -> tuple[np.ndarray, np.ndarray]:
    """Écarts et jacobienne, dérivée par différences, contrainte par contrainte : elle ne touche que ses inconnues."""
    g = _Reader(sk, index, x)
    res, entries = [], []
    row = 0
    y = x.copy()
    gy = _Reader(sk, index, y)
    for c in items:
        base = sk._residual(c, g, sides[c.id])
        m = len(base)
        res.extend(base)
        for v in dict.fromkeys(sk._variables(c, index)):
            keep = y[v]
            y[v] = keep + _STEP
            up = sk._residual(c, gy, sides[c.id])
            y[v] = keep - _STEP
            down = sk._residual(c, gy, sides[c.id])
            y[v] = keep
            for k in range(m):
                d = (up[k] - down[k]) / (2 * _STEP)
                if d:
                    entries.append((row + k, v, d))
        row += m
    J = np.zeros((row, len(x)))
    for i, j, d in entries:
        J[i, j] = d
    return np.array(res, dtype=float), J


def _solve(sk: Sketch, items: list, index: dict, x0, hold: dict, tries: tuple = _TRIES):
    """Le vecteur résolu, None si les contraintes ne se tiennent pas. Un trait à angle droit de ce qu'on lui demande,
    un trait réduit à un point ne donnent aucune direction : on repart alors d'une position un peu secouée, puis on
    revient au plus près de la position d'origine."""
    if not len(x0):
        return x0
    sides = {c.id: sk._freeze(c, index, x0) for c in items}
    size = max(1.0, float(np.ptp(x0)))
    rng = np.random.default_rng(1)
    for noise in tries:
        start = x0 + rng.normal(0.0, noise * size, len(x0)) if noise else x0
        got = _descend(sk, items, index, sides, start, hold, size)
        if got is None:
            continue
        if noise:
            got = _back_toward(sk, items, index, sides, got, x0, size)
        if all(got[index[k]] > 0 for k in sk.circles):
            return got
    return None


def _back_toward(sk: Sketch, items: list, index: dict, sides: dict, x, x0, size: float):
    """Ce que les contraintes laissent libre revient vers la position d'origine."""
    res, J = _rows(sk, items, index, sides, x)
    if not len(res):
        return x0
    free = np.eye(len(x)) - np.linalg.pinv(J, rcond=_RANK) @ J
    near = _descend(sk, items, index, sides, x + free @ (x0 - x), {}, size)
    return near if near is not None else x


def _descend(sk: Sketch, items: list, index: dict, sides: dict, start, hold: dict, size: float):
    """Gauss-Newton au moindre mouvement. Avec `hold`, le geste suit dans ce que les contraintes laissent libre, puis les
    contraintes seules finissent le travail."""
    x = start.copy()
    n = len(x)
    wanted: list = []
    for k, q in hold.items():                          # un point : (x, y) ; un cercle : son rayon
        if k in sk.points:
            wanted += [(index[k], float(q[0])), (index[k] + 1, float(q[1]))]
        else:
            wanted.append((index[k], float(q)))
    for phase in ((wanted, []) if wanted else ([],)):
        last, stalled = math.inf, 0
        for _it in range(_MAX_ITER):
            res, J = _rows(sk, items, index, sides, x)
            if not np.isfinite(res).all() or not np.isfinite(J).all():
                return None
            norm = float(np.linalg.norm(res)) if len(res) else 0.0
            try:
                pinv = np.linalg.pinv(J, rcond=_RANK) if len(res) else None
            except np.linalg.LinAlgError:
                return None
            dx = -pinv @ res if pinv is not None else np.zeros(n)
            if phase:
                idx = [i for i, _v in phase]
                gap = np.array([v - x[i] for i, v in phase]) - dx[idx]
                free = np.eye(n) - (pinv @ J if pinv is not None else 0.0)
                dx = dx + free @ (np.linalg.pinv(free[idx, :], rcond=_RANK) @ gap)
            step = float(np.linalg.norm(dx))
            if norm < TOLERANCE and step < 1e-9:
                break
            limit = max(size, 2.0 * norm)
            if step > limit:                             # pas de saut hors de la figure
                dx *= limit / step
            allowed = max(norm, 0.05 * size) if phase else max(norm, TOLERANCE)
            t, moved = 1.0, False
            while t > 1 / 128:
                y = x + t * dx
                if float(np.linalg.norm(_rows_only(sk, items, index, sides, y))) <= allowed:
                    x, moved = y, True
                    break
                t /= 2
            if not moved:
                if phase:
                    break
                x = _damped(sk, items, index, sides, x, res, J)
                if x is None:
                    return None
            if not phase:
                stalled = stalled + 1 if norm > 0.99 * last and norm > TOLERANCE else 0
                if stalled >= _STALL:
                    return None
                last = norm
    final = _rows_only(sk, items, index, sides, x)
    if len(final) and float(np.max(np.abs(final))) > 1e-6:
        return None
    return x


def _rows_only(sk: Sketch, items: list, index: dict, sides: dict, x) -> np.ndarray:
    g = _Reader(sk, index, x)
    out: list = []
    for c in items:
        out.extend(sk._residual(c, g, sides[c.id]))
    return np.array(out, dtype=float)


def _damped(sk: Sketch, items: list, index: dict, sides: dict, x, res, J):
    """Levenberg-Marquardt : un pas plus court, quand le pas plein n'améliore rien ; None si plus rien ne descend."""
    A = J.T @ J
    b = -J.T @ res
    norm = float(np.linalg.norm(res))
    for lam in (1e-6, 1e-4, 1e-2, 1.0, 100.0):
        try:
            dx = np.linalg.solve(A + lam * np.eye(len(x)), b)
        except np.linalg.LinAlgError:
            continue
        y = x + dx
        if float(np.linalg.norm(_rows_only(sk, items, index, sides, y))) < norm:
            return y
    return None


def _analyse(sk: Sketch, items: list, index: dict, x) -> Report:
    """Ce qui reste libre, ce qui est de trop."""
    n = len(x)
    rep = Report()
    if not n:
        return rep
    sides = {c.id: sk._freeze(c, index, x) for c in items}
    groups = []
    res, J = _rows(sk, items, index, sides, x)
    row = 0
    g = _Reader(sk, index, x)
    for c in items:
        m = len(sk._residual(c, g, sides[c.id]))
        groups.append((c, row, m))
        row += m
    if len(res):
        scale = np.linalg.svd(J, compute_uv=True, full_matrices=True)
        rank = int(np.sum(scale[1] > _RANK * max(1.0, float(scale[1][0]) if len(scale[1]) else 1.0)))
        null = scale[2][rank:]
    else:
        rank, null = 0, np.eye(n)
    rep.dof = n - rank
    size = np.sqrt((null ** 2).sum(axis=0)) if len(null) else np.zeros(n)
    for k in sk.points:
        i = index[k]
        if size[i] > 1e-6 or size[i + 1] > 1e-6:
            rep.free_points.add(k)
    for k in sk.circles:
        if size[index[k]] > 1e-6:
            rep.free_radii.add(k)
    if len(res) > rank and len(groups) <= 300:           # une contrainte qui n'ajoute rien aux précédentes
        have = np.zeros((0, n))
        known = 0
        for c, r0, m in groups:
            have = np.vstack([have, J[r0:r0 + m]])
            now = int(np.linalg.matrix_rank(have, tol=_RANK * max(1.0, float(np.abs(J).max()))))
            if now == known and c.id > 0:
                rep.redundant.append(c.id)
            known = now
    return rep


# --- depuis un dessin -------------------------------------------------------------------------------------------------
def _conic_circle(seg) -> tuple | None:
    """(centre, rayon, sens direct, ouverture en degrés) d'un arc de conique circulaire, None sinon."""
    a, m, b, w = seg.p0, seg.p1, seg.p2, seg.w
    ta, tb = (m[0] - a[0], m[1] - a[1]), (b[0] - m[0], b[1] - m[1])
    la, lb = math.hypot(*ta), math.hypot(*tb)
    if la < 1e-9 or abs(la - lb) > 1e-6 * max(la, 1.0) or not 0.0 < w <= 1.0:
        return None
    turn = _cross(*ta, *tb)
    half = math.acos(min(1.0, w))
    if half < 1e-9 or abs(turn) < 1e-12:
        return None
    r = la / math.tan(half)
    sign = 1.0 if turn > 0 else -1.0
    c = (a[0] - sign * ta[1] / la * r, a[1] + sign * ta[0] / la * r)
    if abs(_hypot(c, b) - r) > 1e-5 * max(r, 1.0):
        return None
    return c, r, turn > 0, math.degrees(2 * half)


def from_path(path: Path, tol: float = 1e-4) -> tuple[Sketch, int]:
    """Une esquisse des traits et des arcs d'un dessin, points communs partagés, sans contraintes ; et le nombre de
    morceaux qu'elle ne sait pas reprendre (courbes de Bézier, arcs d'ellipse)."""
    sk = Sketch()
    ignored = 0
    pts: list = []

    def point(q) -> int:
        for k, r in pts:
            if abs(r[0] - q[0]) < tol and abs(r[1] - q[1]) < tol:
                return k
        k = sk.add_point(q[0], q[1])
        pts.append((k, (q[0], q[1])))
        return k

    for contour in path.contours:
        segs = list(contour.segments)
        i = 0
        while i < len(segs):
            s = segs[i]
            if isinstance(s, Line):
                if _hypot(s.start, s.end) > tol:
                    sk.add_line(point(s.start), point(s.end))
                i += 1
                continue
            got = _conic_circle(s) if isinstance(s, Conic) else None
            if got is None:
                ignored += 1
                i += 1
                continue
            c, r, ccw, angle = got
            j = i + 1
            while j < len(segs) and isinstance(segs[j], Conic):  # les quarts d'un même cercle n'en font qu'un
                o = _conic_circle(segs[j])
                if o is None or o[2] != ccw or _hypot(o[0], c) > tol or abs(o[1] - r) > tol:
                    break
                angle += o[3]
                j += 1
            end = segs[j - 1].end
            if angle >= 360.0 - 1e-6:
                sk.add_circle(point(c), r)
            else:
                sk.add_arc(point(c), point(s.start), point(end), ccw)
            i = j
        if contour.closed and segs and _hypot(segs[-1].end, segs[0].start) > tol:
            sk.add_line(point(segs[-1].end), point(segs[0].start))
    return sk, ignored
