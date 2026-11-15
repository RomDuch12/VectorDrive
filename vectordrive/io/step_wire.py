"""STEP : les courbes libres d'un « fil de fer » (GEOMETRIC_CURVE_SET, GEOMETRIC_SET), hors de toute face — ce
qu'un logiciel de dessin exporte pour de simples courbes (TypeEdit : un jeu de B-splines, sans une face).

B-splines (rationnelles ou non), polylignes, courbes composites, droites bornées, cercles entiers ou bornés : en
courbes exactes, vues de dessus, en millimètres. Les autres courbes sont comptées, pas approchées.

Écrit d'après ISO 10303-42 ; les entités viennent de `neostep.stepread`, les morceaux de Bézier de `io.iges`.
"""
from __future__ import annotations

import math
import re

import numpy as np

from ..core.geom import Contour
from . import iges
from .neostep import stepread

#: le fichier porte un jeu de courbes : il vaut d'être relu pour elles
_HAS_WIRE = re.compile(r'GEOMETRIC_(?:CURVE_)?SET\s*\(')
_SETS = ('GEOMETRIC_CURVE_SET', 'GEOMETRIC_SET')
_WRAPPERS = ('SURFACE_CURVE', 'SEAM_CURVE', 'INTERSECTION_CURVE')
MAX_DEPTH = 16


def contours(path, matrix=None) -> tuple[list[Contour], int]:
    """(contours vus de dessus ; nombre de courbes d'un type non lu). `matrix` (3×3) : la pièce tournée d'abord."""
    try:
        with open(path, 'r', encoding='latin-1') as fh:
            text = fh.read()
    except OSError:
        return [], 0
    if not _HAS_WIRE.search(text):
        return [], 0
    try:
        ents = stepread.lire_entites(text)
    except stepread.StepError:
        return [], 0
    mod = stepread._Modele(ents)
    mod.f = mod.unite()
    turn = None
    if matrix is not None:
        turn = np.eye(4)
        turn[:3, :3] = np.asarray(matrix, dtype=float)
    out: list[Contour] = []
    skipped = 0
    seen: set[int] = set()
    for name, args in list(ents.values()):
        if name not in _SETS or len(args) < 2:
            continue
        for ref in args[1] or ():
            if not isinstance(ref, stepread.Ref) or int(ref) in seen:
                continue
            seen.add(int(ref))
            if mod.type_de(ref) == 'CARTESIAN_POINT':    # un point du jeu : pas une courbe
                continue
            try:
                pieces = _pieces(mod, ref, 0)
            except (ValueError, IndexError, TypeError, KeyError, ZeroDivisionError):
                pieces = None
            if not pieces:
                skipped += 1
                continue
            if turn is not None:
                pieces = [p.moved(turn) for p in pieces]
            out += iges._contours_of(pieces)
    return out, skipped


def _pieces(mod, ref, depth: int):
    """Les morceaux de Bézier d'une courbe, ou None : type non lu."""
    ent = mod.e.get(int(ref))
    if not ent or depth > MAX_DEPTH:
        return None
    name, a = ent
    if name == 'B_SPLINE_CURVE_WITH_KNOTS' or (name == '*' and 'B_SPLINE_CURVE' in a):
        return _spline(mod, ent)
    if name == 'POLYLINE':
        pts = [mod.point(r) for r in a[1]]
        return [iges._Piece([p, q]) for p, q in zip(pts, pts[1:])]
    if name == 'CIRCLE':
        return _arc(mod, a, 0.0, 2 * math.pi)
    if name == 'TRIMMED_CURVE':
        return _trimmed(mod, a)
    if name == 'COMPOSITE_CURVE':
        out = []
        for seg in a[1]:
            s = mod.e.get(int(seg))
            if not s or s[0] != 'COMPOSITE_CURVE_SEGMENT':
                return None
            part = _pieces(mod, s[1][2], depth + 1)
            if not part:
                return None
            out += part if s[1][1] == 'T' else [p.reversed() for p in reversed(part)]
        return out
    if name in _WRAPPERS:
        return _pieces(mod, a[1], depth + 1)
    return None


def _spline(mod, ent, t0=None, t1=None):
    """Une B-spline, simple ou entité complexe (rationnelle) ; `t0`, `t1` : la part bornée, sinon toute la courbe."""
    name, a = ent
    if name == 'B_SPLINE_CURVE_WITH_KNOTS':
        return _bspline(mod, a[1], a[2], a[6], a[7], None, t0, t1)
    bs, kn = a['B_SPLINE_CURVE'], a.get('B_SPLINE_CURVE_WITH_KNOTS')
    weights = (a.get('RATIONAL_B_SPLINE_CURVE') or [None])[0]
    if kn:
        return _bspline(mod, bs[0], bs[1], kn[0], kn[1], weights, t0, t1)
    if 'BEZIER_CURVE' in a:                              # un seul morceau : ses points sont ceux de la Bézier
        pts = [mod.point(r) for r in bs[1]]
        return [iges._Piece(pts, [float(w) for w in weights] if weights else None)]
    return None


def _bspline(mod, degree, refs, mults, knots, weights, t0=None, t1=None):
    p = int(degree)
    pts = np.array([mod.point(r) for r in refs], dtype=float)
    u = [float(k) for m, k in zip(mults, knots) for _ in range(int(m))]
    w = [float(x) for x in weights] if weights else [1.0] * len(pts)
    lo, hi = u[p], u[len(pts)]
    a = lo if t0 is None else min(max(float(t0), lo), hi)
    b = hi if t1 is None else min(max(float(t1), lo), hi)
    return iges._bezier_pieces(p, u, pts, w, a, b)


def _frame(mod, ref) -> np.ndarray:
    """Repère 4×4 d'un AXIS2_PLACEMENT (3D, ou 2D dans le plan XY)."""
    a = mod.args(ref)
    if mod.type_de(ref) == 'AXIS2_PLACEMENT_2D':
        loc, z = mod.point(a[1]), (0.0, 0.0, 1.0)
        x = mod.direction(a[2] if len(a) > 2 else None, (1.0, 0.0, 0.0))
    else:
        loc, z, x = mod.repere(ref)
    z = np.asarray(z, dtype=float)
    x = np.asarray(x, dtype=float)
    x = x - z * float(x @ z)                             # la direction de référence, ramenée dans le plan
    n = float(np.linalg.norm(x))
    if n < 1e-12:
        raise ValueError('repère dégénéré')
    x /= n
    m = np.eye(4)
    m[:3, 0], m[:3, 1], m[:3, 2], m[:3, 3] = x, np.cross(z, x), z, loc
    return m


def _arc(mod, circle_args, a0: float, sweep: float):
    m = _frame(mod, circle_args[1])
    r = float(circle_args[2]) * mod.f
    if r <= 0:
        raise ValueError('rayon nul')
    return [p.moved(m) for p in iges._arc_pieces((0.0, 0.0), r, a0, sweep, 0.0)]


def _trim(mod, values):
    """(paramètre ou None, point ou None) d'une borne de TRIMMED_CURVE."""
    t = pt = None
    for v in values or ():
        if isinstance(v, stepread.Ref) and mod.type_de(v) == 'CARTESIAN_POINT':
            pt = mod.point(v)
        elif isinstance(v, tuple) and v[0] == 'PARAMETER_VALUE' and v[1]:
            t = float(v[1][0])
        elif isinstance(v, float):
            t = v
    return t, pt


def _trimmed(mod, a):
    basis = mod.e.get(int(a[1]))
    if not basis:
        return None
    (t1, p1), (t2, p2) = _trim(mod, a[2]), _trim(mod, a[3])
    same = a[4] == 'T'
    if basis[0] == 'LINE':
        origin = np.asarray(mod.point(basis[1][1]), dtype=float)
        vec = mod.args(basis[1][2])                      # VECTOR : direction, longueur
        step = np.asarray(mod.direction(vec[1]), dtype=float) * float(vec[2]) * mod.f
        ends = [np.asarray(p, dtype=float) if p is not None else (origin + t * step if t is not None else None)
                for t, p in ((t1, p1), (t2, p2))]
        if ends[0] is None or ends[1] is None:
            return None
        return [iges._Piece([ends[0], ends[1]])]
    if basis[0] == 'CIRCLE':
        from .neostep import step3d
        m = _frame(mod, basis[1][1])
        inv = np.linalg.inv(m)
        unit = step3d._unite_angle(mod)

        def angle(t, p):
            if t is not None:
                return t * unit
            if p is None:
                raise ValueError('borne absente')
            q = inv @ np.array([p[0], p[1], p[2], 1.0])
            return math.atan2(q[1], q[0])
        s, e = angle(t1, p1), angle(t2, p2)
        sweep = (e - s) % (2 * math.pi) if same else -((s - e) % (2 * math.pi))
        if abs(sweep) < 1e-9:
            sweep = 2 * math.pi if same else -2 * math.pi
        return _arc(mod, basis[1], s, sweep)
    if basis[0] == 'B_SPLINE_CURVE_WITH_KNOTS' or (basis[0] == '*' and 'B_SPLINE_CURVE' in basis[1]):
        if t1 is not None and t2 is not None:            # bornée par ses paramètres, dans un sens ou dans l'autre
            part = _spline(mod, basis, min(t1, t2), max(t1, t2))
            return part if t1 <= t2 else [p.reversed() for p in reversed(part)] if part else None
        return _spline(mod, basis)                       # bornée par des points : ceux de ses bouts, d'ordinaire
    if basis[0] == 'POLYLINE' and t1 is None and t2 is None:
        return _pieces(mod, a[1], 1)
    return None
