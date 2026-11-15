"""Accrochage (F3 dans TypeEdit) : nœuds, intersections, milieux de
segments, centres (arcs, cercles, objets), point le plus proche sur un
contour et grille.

Le moteur ne dépend pas de Qt : `Snap.query(x, y, tol, leaves)` renvoie le
point accroché le plus proche ou None. Les points de chaque objet sont mis
en cache par identité de chemin (un objet modifié reçoit un nouveau chemin,
donc le cache se renouvelle de lui-même).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .document import Group, Image, Item, Shape, Text

#: Ordre de priorité à distance égale (un nœud l'emporte sur un milieu…).
#: « Sur le contour » et la grille ne servent que si rien d'autre n'est proche.
KINDS = ('node', 'intersection', 'middle', 'center', 'centroid', 'quadrant', 'perpendicular', 'tangent', 'extension',
         'parallel', 'guide', 'nearest', 'grid')
LABELS = {'node': 'Nœud', 'intersection': 'Intersection', 'middle': 'Milieu', 'center': 'Centre',
          'centroid': 'Centre de gravité', 'perpendicular': 'Perpendiculaire', 'tangent': 'Tangente',
          'extension': 'Prolongement', 'parallel': 'Parallèle',
          'quadrant': 'Quadrant', 'guide': 'Guide', 'nearest': 'Sur le contour', 'grid': 'Grille',
          'tracking': 'Repérage'}
#: points acquis par le repérage (les plus récents)
TRACK_MAX = 4
#: natures de points qu'acquiert le repérage
TRACK_KINDS = ('node', 'intersection', 'middle', 'center', 'centroid', 'quadrant')
#: précision de l'aplatissement pour les intersections et le point le plus proche (mm)
FLAT_TOL = 2e-4
#: au-delà, on ne cherche pas d'intersections (curseur sur une zone trop dense)
MAX_CANDIDATES = 80


@dataclass
class SnapHit:
    x: float
    y: float
    kind: str


def track(x: float, y: float, tol: float, pts) -> tuple[SnapHit | None, list]:
    """Repérage : (x, y) accroché sur la verticale ou l'horizontale d'un
    point acquis, ou à la croisée de deux ; rend le point et les lignes de
    repérage [(px, py, qx, qy)] (du point acquis au point accroché)."""
    vx = min(((abs(x - p[0]), p) for p in pts if abs(x - p[0]) <= tol), default=None)
    hy = min(((abs(y - p[1]), p) for p in pts if abs(y - p[1]) <= tol), default=None)
    if vx is None and hy is None:
        return None, []
    qx = vx[1][0] if vx else x
    qy = hy[1][1] if hy else y
    lines = [(p[0], p[1], qx, qy) for p in ((vx or (0, None))[1], (hy or (0, None))[1]) if p is not None]
    return SnapHit(qx, qy, 'tracking'), lines


def extension(x: float, y: float, tol: float, ends) -> tuple[SnapHit | None, tuple | None]:
    """Prolongement : (x, y) ramené sur le prolongement d'un des bouts
    retenus (au-delà du bout, à moins de `tol` de la droite)."""
    best, bd, line = None, tol, None
    for px, py, ux, uy in ends:
        t = (x - px) * ux + (y - py) * uy
        if t <= tol:
            continue
        d = abs((x - px) * uy - (y - py) * ux)
        if d < bd:
            qx, qy = px + t * ux, py + t * uy
            best, bd, line = SnapHit(qx, qy, 'extension'), d, (px, py, qx, qy)
    return best, line


def polar(x: float, y: float, tol: float, anchor, step_deg: float) -> tuple[SnapHit | None, list]:
    """Repérage polaire : (x, y) ramené sur le rayon issu de `anchor` à
    l'angle multiple de `step_deg` le plus proche, s'il en est à moins de
    `tol` ; rend le point et la ligne de repérage."""
    if anchor is None or step_deg <= 0:
        return None, []
    dx, dy = x - anchor[0], y - anchor[1]
    d = math.hypot(dx, dy)
    if d < tol:
        return None, []
    a = math.degrees(math.atan2(dy, dx))
    k = round(a / step_deg) * step_deg
    t = math.radians(k)
    ux, uy = math.cos(t), math.sin(t)
    along = dx * ux + dy * uy
    if along <= 0 or abs(dx * uy - dy * ux) > tol:
        return None, []
    qx, qy = anchor[0] + along * ux, anchor[1] + along * uy
    return SnapHit(qx, qy, 'tracking'), [(anchor[0], anchor[1], qx, qy)]


@dataclass
class _Pts:
    ref: object                   # garde l'objet source vivant (id stable)
    bbox: tuple
    arrays: dict                  # kind → ndarray (n, 2)
    segs: list = field(default_factory=list)          # [(contour, rang, segment)]
    segboxes: np.ndarray | None = None                 # (n, 4) boîtes des segments


def _bbox_pts(bb) -> list:
    x0, y0, x1, y1 = bb
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def item_points(it: Item) -> dict[str, list]:
    """Points accrochables d'un objet feuille, par nature."""
    out = {'node': [], 'middle': [], 'center': [], 'centroid': [], 'quadrant': []}
    bb = it.bbox()
    if isinstance(it, Shape) and it.path:
        if any(c.closed and c.segments for c in it.path.contours):
            g = centroid(it.path)
            if g is not None:
                out['centroid'].append(g)
        for c in it.path.contours:
            if not c.segments:
                continue
            for s in c.segments:
                out['node'].append(s.start)
                out['middle'].append(s.point(0.5))
                cp = getattr(s, 'circle_params', None)
                if cp is not None:
                    r = cp()
                    if r is not None:
                        out['center'].append(r[0])
                        out['quadrant'].extend(_quadrants(*r))
            if not c.closed:
                out['node'].append(c.segments[-1].end)
    elif isinstance(it, (Text, Image)) and bb:
        out['node'].extend(_bbox_pts(bb))
    if bb:
        out['center'].append(((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2))
    return out


def centroid(path) -> tuple[float, float] | None:
    """Centre de gravité de la surface des contours fermés (trous retranchés)."""
    from .cadtools import mass_properties
    try:
        m = mass_properties(path)
    except Exception:                                   # contour dégénéré
        return None
    return m['centroid'] if m and m.get('area', 0) > 1e-12 else None


def _quadrants(c, r: float, a0: float, sweep: float) -> list:
    """Points à 0°, 90°, 180°, 270° d'un arc (centre, rayon, départ,
    balayage signé en degrés) qui sont sur l'arc."""
    out = []
    for q in (0.0, 90.0, 180.0, 270.0):
        d = (q - a0) % 360.0 if sweep >= 0 else (a0 - q) % 360.0
        if d <= abs(sweep) + 1e-9:
            t = math.radians(q)
            out.append((c[0] + r * math.cos(t), c[1] + r * math.sin(t)))
    return out


def _polyline_crossings(P: np.ndarray, Q: np.ndarray) -> list[tuple[float, float]]:
    """Points de croisement de deux polylignes (tous les couples de
    morceaux, en numpy)."""
    if len(P) < 2 or len(Q) < 2:
        return []
    a, b = P[:-1], P[1:]
    c, d = Q[:-1], Q[1:]
    # élimination rapide par boîtes
    ax0, ax1 = np.minimum(a[:, 0], b[:, 0]), np.maximum(a[:, 0], b[:, 0])
    ay0, ay1 = np.minimum(a[:, 1], b[:, 1]), np.maximum(a[:, 1], b[:, 1])
    cx0, cx1 = np.minimum(c[:, 0], d[:, 0]), np.maximum(c[:, 0], d[:, 0])
    cy0, cy1 = np.minimum(c[:, 1], d[:, 1]), np.maximum(c[:, 1], d[:, 1])
    m = ((ax0[:, None] <= cx1[None]) & (cx0[None] <= ax1[:, None])
         & (ay0[:, None] <= cy1[None]) & (cy0[None] <= ay1[:, None]))
    I, J = np.nonzero(m)
    if not len(I):
        return []
    r = b[I] - a[I]
    s = d[J] - c[J]
    den = r[:, 0] * s[:, 1] - r[:, 1] * s[:, 0]
    ok = np.abs(den) > 1e-18
    w = c[J] - a[I]
    with np.errstate(divide='ignore', invalid='ignore'):
        t = (w[:, 0] * s[:, 1] - w[:, 1] * s[:, 0]) / den
        u = (w[:, 0] * r[:, 1] - w[:, 1] * r[:, 0]) / den
    ok &= (t >= -1e-9) & (t <= 1 + 1e-9) & (u >= -1e-9) & (u <= 1 + 1e-9)
    pts = a[I][ok] + t[ok][:, None] * r[ok]
    return [(float(px), float(py)) for px, py in pts]


def _param_near(s, p, n: int = 64) -> float:
    """Paramètre du point de `s` le plus proche de `p` (échantillons puis
    resserrement)."""
    ts = np.linspace(0.0, 1.0, n + 1)
    pts = np.asarray([s.point(float(t)) for t in ts])
    k = int(np.argmin(np.hypot(pts[:, 0] - p[0], pts[:, 1] - p[1])))
    lo, hi = ts[max(0, k - 1)], ts[min(n, k + 1)]
    for _ in range(30):
        m1, m2 = lo + (hi - lo) / 3, hi - (hi - lo) / 3
        d1 = math.dist(s.point(m1), p)
        d2 = math.dist(s.point(m2), p)
        if d1 < d2:
            hi = m2
        else:
            lo = m1
    return (lo + hi) / 2


def refine_crossing(sa, sb, p) -> tuple[float, float]:
    """Intersection exacte de deux segments près de `p` (Newton sur les
    paramètres) ; `p` si la méthode ne converge pas."""
    ta, tb = _param_near(sa, p), _param_near(sb, p)
    h = 1e-7
    for _ in range(12):
        A, B = sa.point(ta), sb.point(tb)
        fx, fy = A[0] - B[0], A[1] - B[1]
        if math.hypot(fx, fy) < 1e-13:
            break
        a1, a0 = sa.point(min(1.0, ta + h)), sa.point(max(0.0, ta - h))
        b1, b0 = sb.point(min(1.0, tb + h)), sb.point(max(0.0, tb - h))
        da = ((a1[0] - a0[0]) / (min(1.0, ta + h) - max(0.0, ta - h)),
              (a1[1] - a0[1]) / (min(1.0, ta + h) - max(0.0, ta - h)))
        db = ((b1[0] - b0[0]) / (min(1.0, tb + h) - max(0.0, tb - h)),
              (b1[1] - b0[1]) / (min(1.0, tb + h) - max(0.0, tb - h)))
        det = da[0] * -db[1] - da[1] * -db[0]
        if abs(det) < 1e-18:
            return p
        dta = (-fx * -db[1] + fy * -db[0]) / det
        dtb = (-da[0] * fy + da[1] * fx) / det
        ta = min(1.0, max(0.0, ta + dta))
        tb = min(1.0, max(0.0, tb + dtb))
    A, B = sa.point(ta), sb.point(tb)
    if math.dist(A, B) > 1e-7 or math.dist(A, p) > 10 * FLAT_TOL + 1e-6:
        return p
    return (float(A[0] + B[0]) / 2, float(A[1] + B[1]) / 2)


def _leaves(items):
    for it in items:
        if not it.visible:
            continue
        if isinstance(it, Group):
            yield from _leaves(it.children)
        else:
            yield it


@dataclass
class Snap:
    enabled: bool = False
    modes: set = field(default_factory=lambda: {'node', 'intersection', 'middle', 'center', 'guide', 'grid'})
    grid_step: float = 1.0
    #: guides du document : [('h', y) | ('v', x)] (mis à jour par le canevas)
    guides: list = field(default_factory=list)
    #: lignes de construction (guides obliques) : [(x, y, angle°)] (mises à jour par le canevas)
    obliques: list = field(default_factory=list)
    #: repérage (F11) : verticales et horizontales des points survolés
    tracking: bool = False
    tracked: list = field(default_factory=list)
    track_lines: list = field(default_factory=list)
    #: repérage polaire : angles multiples de `polar_step` depuis `anchor` (dernier point cliqué)
    polar: bool = False
    polar_step: float = 15.0
    anchor: tuple | None = None
    #: prolongement : bouts de traits droits survolés [(x, y, ux, uy)] (direction vers l'extérieur)
    ext_ends: list = field(default_factory=list)
    #: parallèle : direction du dernier trait droit survolé (ux, uy)
    par_dir: tuple | None = None
    _cache: dict = field(default_factory=dict)

    def _points(self, it: Item) -> _Pts | None:
        key = id(getattr(it, 'path', None) or getattr(it, 'outline', None) or it)
        p = self._cache.get(key)
        if p is not None:
            return p
        bb = it.bbox()
        if not bb:
            return None
        pts = item_points(it)
        p = _Pts(getattr(it, 'path', None) or getattr(it, 'outline', None) or it, bb,
                 {k: np.asarray(v, dtype=float).reshape(-1, 2) for k, v in pts.items() if v})
        if isinstance(it, Shape) and it.path:
            for ci, c in enumerate(it.path.contours):
                for si, s in enumerate(c.segments):
                    p.segs.append((ci, si, len(c.segments), c.closed, s))
            if p.segs:
                p.segboxes = np.asarray([s.bbox() for *_x, s in p.segs], float)
        self._cache[key] = p
        return p

    def _flat(self, s) -> np.ndarray:
        key = ('flat', id(s))
        f = self._cache.get(key)
        if f is None or f[0] is not s:
            f = (s, np.asarray([s.start] + list(s.flatten(FLAT_TOL)), float))
            self._cache[key] = f
        return f[1]

    def _candidates(self, x: float, y: float, tol: float, items, excl) -> list:
        """Segments dont la boîte passe à moins de `tol` du curseur :
        [(feuille, contour, rang, nb, fermé, segment)]."""
        out = []
        for top in items:
            if id(top) in excl:
                continue
            tb = top.bbox()
            if not tb or not (tb[0] - tol <= x <= tb[2] + tol and tb[1] - tol <= y <= tb[3] + tol):
                continue
            for leaf in _leaves([top]):
                b = leaf.bbox()
                if not b or not (b[0] - tol <= x <= b[2] + tol and b[1] - tol <= y <= b[3] + tol):
                    continue
                p = self._points(leaf)
                if p is None or p.segboxes is None:
                    continue
                sb = p.segboxes
                near = np.nonzero((sb[:, 0] - tol <= x) & (x <= sb[:, 2] + tol)
                                  & (sb[:, 1] - tol <= y) & (y <= sb[:, 3] + tol))[0]
                for k in near.tolist():
                    out.append((id(leaf),) + p.segs[k])
        return out

    def _intersection(self, x, y, tol, cands):
        """Intersection la plus proche du curseur entre deux segments candidats."""
        best, best_d, pair = None, tol, None
        flats: dict[int, np.ndarray] = {}

        def flat(k):                                     # aplatis seulement s'il le faut
            if k not in flats:
                flats[k] = self._flat(cands[k][-1])
            return flats[k]
        for i in range(len(cands)):
            for j in range(i + 1, len(cands)):
                a, b = cands[i], cands[j]
                if a[0] == b[0] and a[1] == b[1]:
                    n = a[3]
                    if abs(a[2] - b[2]) == 1 or (a[4] and abs(a[2] - b[2]) == n - 1):
                        continue                         # segments voisins : leur point commun est un nœud
                for px, py in _polyline_crossings(flat(i), flat(j)):
                    d = math.hypot(px - x, py - y)
                    if d < best_d:
                        best, best_d, pair = (px, py), d, (a[-1], b[-1])
        if best is not None:
            best = refine_crossing(pair[0], pair[1], best)
            best_d = math.hypot(best[0] - x, best[1] - y)
        return best, best_d

    def _guide(self, x, y, tol) -> SnapHit | None:
        """Point sur le guide le plus proche, ou croisement de deux guides
        (lignes de construction obliques comprises)."""
        vs = [(abs(x - g), g) for a, g in self.guides if a == 'v' and abs(x - g) <= tol]
        hs = [(abs(y - g), g) for a, g in self.guides if a == 'h' and abs(y - g) <= tol]
        near = []
        for gx, gy, a in self.obliques:
            t = math.radians(a)
            ux, uy = math.cos(t), math.sin(t)
            d = abs(-(x - gx) * uy + (y - gy) * ux)
            if d <= tol:
                near.append((d, (gx, gy), (ux, uy)))
        if near:
            lines = near + [(d, (g, 0.0), (0.0, 1.0)) for d, g in vs] + [(d, (0.0, g), (1.0, 0.0)) for d, g in hs]
            best = None
            for i in range(len(lines)):
                for j in range(i + 1, len(lines)):
                    (_d, p, u), (_e, q, v) = lines[i], lines[j]
                    den = u[0] * v[1] - u[1] * v[0]
                    if abs(den) < 1e-12:
                        continue
                    s = ((q[0] - p[0]) * v[1] - (q[1] - p[1]) * v[0]) / den
                    c = (p[0] + s * u[0], p[1] + s * u[1])
                    dc = math.hypot(c[0] - x, c[1] - y)
                    if dc <= 2 * tol and (best is None or dc < best[0]):
                        best = (dc, c)
            if best is not None:
                return SnapHit(best[1][0], best[1][1], 'guide')
            _d, (gx, gy), (ux, uy) = min(lines, key=lambda l: l[0])
            k = (x - gx) * ux + (y - gy) * uy
            return SnapHit(gx + k * ux, gy + k * uy, 'guide')
        if vs and hs:
            return SnapHit(float(min(vs)[1]), float(min(hs)[1]), 'guide')
        if vs and (not hs):
            return SnapHit(float(min(vs)[1]), y, 'guide')
        if hs:
            return SnapHit(x, float(min(hs)[1]), 'guide')
        return None

    def _relative(self, x, y, tol, cands):
        """Accrochages relatifs au dernier point cliqué (`anchor`) : pied de la
        perpendiculaire sur un trait droit ou un cercle, point de tangence sur
        un cercle ou un arc — le plus proche du curseur, à moins de `tol`."""
        from .geom import Line
        A = self.anchor
        best, best_d = None, tol
        for c in cands:
            s = c[-1]
            pts = []
            if 'perpendicular' in self.modes and isinstance(s, Line):
                (ax, ay), (bx, by) = s.start, s.end
                dx, dy = bx - ax, by - ay
                L2 = dx * dx + dy * dy
                if L2 > 1e-18:
                    t = ((A[0] - ax) * dx + (A[1] - ay) * dy) / L2
                    if -1e-9 <= t <= 1 + 1e-9:
                        pts.append(((ax + t * dx, ay + t * dy), 'perpendicular'))
            cp = getattr(s, 'circle_params', None)
            r = cp() if cp is not None else None
            if r is not None:
                (cx, cy), rad = r[0], r[1]
                d = math.hypot(A[0] - cx, A[1] - cy)
                if d > 1e-9 and 'perpendicular' in self.modes:
                    ux, uy = (A[0] - cx) / d, (A[1] - cy) / d
                    pts += [((cx + ux * rad, cy + uy * rad), 'perpendicular'),
                            ((cx - ux * rad, cy - uy * rad), 'perpendicular')]
                if d > rad + 1e-9 and 'tangent' in self.modes:
                    base = math.atan2(A[1] - cy, A[0] - cx)
                    phi = math.acos(rad / d)
                    pts += [((cx + rad * math.cos(base + sg * phi), cy + rad * math.sin(base + sg * phi)), 'tangent')
                            for sg in (1, -1)]
            for (px, py), kind in pts:
                dd = math.hypot(px - x, py - y)
                if dd < best_d:
                    best, best_d = SnapHit(px, py, kind), dd
        return best, best_d

    def _nearest(self, x, y, tol, cands):
        best, best_d = None, tol
        for c in cands:
            q = self._flat(c[-1])
            a, b = q[:-1], q[1:]
            ab = b - a
            L2 = (ab ** 2).sum(1)
            L2[L2 == 0] = 1e-30
            t = np.clip(((x - a[:, 0]) * ab[:, 0] + (y - a[:, 1]) * ab[:, 1]) / L2, 0, 1)
            proj = a + t[:, None] * ab
            d = np.hypot(proj[:, 0] - x, proj[:, 1] - y)
            k = int(np.argmin(d))
            if d[k] < best_d:
                best, best_d = (float(proj[k, 0]), float(proj[k, 1])), float(d[k])
        return best, best_d

    def prune(self, keep: int = 20000) -> None:
        if len(self._cache) > keep:
            self._cache.clear()

    def query(self, x: float, y: float, tol: float, items, *, exclude=()) -> SnapHit | None:
        """Point accroché le plus proche de (x, y) à moins de `tol` (mm),
        parmi les objets `items` (premier niveau, groupes dépliés)."""
        if not self.enabled:
            return None
        excl = {id(e) for e in exclude}
        best: SnapHit | None = None
        best_d = tol
        object_modes = [k for k in ('node', 'middle', 'center', 'centroid', 'quadrant') if k in self.modes]
        if object_modes:
            for top in items:
                if id(top) in excl:
                    continue
                tb = top.bbox()                  # boîtes en cache sur les tracés
                if not tb or not (tb[0] - tol <= x <= tb[2] + tol and tb[1] - tol <= y <= tb[3] + tol):
                    continue
                for leaf in _leaves([top]):
                    b = leaf.bbox()
                    if not b or not (b[0] - tol <= x <= b[2] + tol and b[1] - tol <= y <= b[3] + tol):
                        continue
                    p = self._points(leaf)      # points calculés seulement près du curseur
                    if p is None:
                        continue
                    for k in object_modes:
                        a = p.arrays.get(k)
                        if a is None:
                            continue
                        d = np.hypot(a[:, 0] - x, a[:, 1] - y)
                        i = int(np.argmin(d))
                        # à distance quasi égale, la nature prioritaire l'emporte
                        if d[i] < best_d - 1e-9 or (best is not None and abs(d[i] - best_d) <= 1e-9
                                                    and KINDS.index(k) < KINDS.index(best.kind)):
                            best_d = float(d[i])
                            best = SnapHit(float(a[i, 0]), float(a[i, 1]), k)
        if 'intersection' in self.modes:
            cands = self._candidates(x, y, tol, items, excl)
            if 1 < len(cands) <= MAX_CANDIDATES:
                pt, d = self._intersection(x, y, tol, cands)
                if pt is not None and (best is None or d < best_d - 1e-9
                                       or (abs(d - best_d) <= 1e-9 and best.kind != 'node')):
                    best, best_d = SnapHit(pt[0], pt[1], 'intersection'), d
        if self.anchor is not None and ('perpendicular' in self.modes or 'tangent' in self.modes):
            cands = self._candidates(x, y, tol, items, excl)
            if cands and len(cands) <= MAX_CANDIDATES:
                hit, d = self._relative(x, y, tol, cands)
                if hit is not None and (best is None or d < best_d - 1e-9):
                    best, best_d = hit, d
        ext_line = None
        if 'parallel' in self.modes:
            from .geom import Line
            near = self._candidates(x, y, tol, items, excl)
            for c in near:                                   # survol d'un trait droit : sa direction retenue
                s = c[-1]
                if isinstance(s, Line):
                    (ax, ay), (bx, by) = s.start, s.end
                    dx, dy = bx - ax, by - ay
                    L = math.hypot(dx, dy)
                    if L > 1e-9 and abs((x - ax) * dy - (y - ay) * dx) / L < tol:
                        self.par_dir = (dx / L, dy / L)
                        break
            if self.anchor is not None and self.par_dir is not None and (best is None or best.kind in ('grid',
                                                                                                       'nearest')):
                ax, ay = self.anchor
                ux, uy = self.par_dir
                t = (x - ax) * ux + (y - ay) * uy
                if abs((x - ax) * uy - (y - ay) * ux) < tol and abs(t) > tol:
                    best = SnapHit(ax + t * ux, ay + t * uy, 'parallel')
                    ext_line = (ax, ay, best.x, best.y)
        if 'extension' in self.modes:
            if best is not None and best.kind == 'node':
                self._acquire_ends(best.x, best.y, tol, items, excl)
            elif best is None or best.kind in ('grid', 'nearest'):
                hit, ext_line = extension(x, y, tol, self.ext_ends)
                if hit is not None:
                    best = hit
        if best is None and 'guide' in self.modes and (self.guides or self.obliques):
            best = self._guide(x, y, tol)
        if best is None and 'nearest' in self.modes:
            cands = self._candidates(x, y, tol, items, excl)
            if cands:
                pt, d = self._nearest(x, y, tol, cands)
                if pt is not None:
                    best = SnapHit(pt[0], pt[1], 'nearest')
        self.track_lines = [ext_line] if ext_line is not None and best is not None and \
            best.kind in ('extension', 'parallel') else []
        if self.tracking:
            if best is not None and best.kind in TRACK_KINDS:
                self.acquire(best.x, best.y)
            elif best is None or best.kind in ('grid', 'nearest'):
                hit, lines = track(x, y, tol, self.tracked)
                if hit is not None:
                    best, self.track_lines = hit, lines
        if self.polar and (best is None or best.kind in ('grid', 'nearest')):
            hit, lines = polar(x, y, tol, self.anchor, self.polar_step)
            if hit is not None:
                best, self.track_lines = hit, lines
        if best is None and 'grid' in self.modes and self.grid_step > 0:
            g = self.grid_step
            gx, gy = round(x / g) * g, round(y / g) * g
            if math.hypot(gx - x, gy - y) <= tol:
                best = SnapHit(gx, gy, 'grid')
        return best

    def query_all(self, x: float, y: float, tol: float, items, *, exclude=()) -> list:
        """Tous les points accrochables à moins de `tol` (TypeEdit : multi-accrochage) : d'abord celui que rend `query`, puis
        les autres du plus proche au plus loin ; un même point n'y est qu'une fois, sous sa nature prioritaire."""
        if not self.enabled:
            return []
        first = self.query(x, y, tol, items, exclude=exclude)
        excl = {id(e) for e in exclude}
        found = []
        object_modes = [k for k in ('node', 'middle', 'center', 'centroid', 'quadrant') if k in self.modes]
        for top in items:
            if not object_modes or id(top) in excl:
                continue
            tb = top.bbox()
            if not tb or not (tb[0] - tol <= x <= tb[2] + tol and tb[1] - tol <= y <= tb[3] + tol):
                continue
            for leaf in _leaves([top]):
                b = leaf.bbox()
                if not b or not (b[0] - tol <= x <= b[2] + tol and b[1] - tol <= y <= b[3] + tol):
                    continue
                p = self._points(leaf)
                if p is None:
                    continue
                for k in object_modes:
                    a = p.arrays.get(k)
                    if a is None:
                        continue
                    d = np.hypot(a[:, 0] - x, a[:, 1] - y)
                    for i in np.nonzero(d <= tol)[0]:
                        found.append((float(d[i]), KINDS.index(k), SnapHit(float(a[i, 0]), float(a[i, 1]), k)))
        if 'intersection' in self.modes:
            cands = self._candidates(x, y, tol, items, excl)
            if 1 < len(cands) <= MAX_CANDIDATES:
                pt, d = self._intersection(x, y, tol, cands)
                if pt is not None:
                    found.append((float(d), KINDS.index('intersection'), SnapHit(pt[0], pt[1], 'intersection')))
        found.sort(key=lambda f: (f[0], f[1]))
        out = [] if first is None else [first]
        for _d, _k, hit in found:
            if not any(math.hypot(hit.x - h.x, hit.y - h.y) < 1e-6 for h in out):
                out.append(hit)
        return out

    def _acquire_ends(self, x: float, y: float, tol: float, items, excl) -> None:
        """Bout de trait droit sous le nœud accroché : sa direction vers
        l'extérieur retenue pour le prolongement (4 au plus, le dernier en tête)."""
        from .geom import Line
        for c in self._candidates(x, y, tol, items, excl):
            s = c[-1]
            if not isinstance(s, Line):
                continue
            for p, q in ((s.end, s.start), (s.start, s.end)):
                if math.hypot(p[0] - x, p[1] - y) < 1e-9:
                    d = math.hypot(p[0] - q[0], p[1] - q[1])
                    if d > 1e-9:
                        e = (p[0], p[1], (p[0] - q[0]) / d, (p[1] - q[1]) / d)
                        self.ext_ends = [e] + [o for o in self.ext_ends if o[:2] != e[:2] or o[2:] != e[2:]]
                        del self.ext_ends[4:]

    def acquire(self, x: float, y: float) -> None:
        """Point acquis par le repérage (le plus récent en tête)."""
        self.tracked = [(x, y)] + [p for p in self.tracked if math.hypot(p[0] - x, p[1] - y) > 1e-9]
        del self.tracked[TRACK_MAX:]

    def clear_tracking(self) -> None:
        self.tracked, self.track_lines, self.anchor, self.ext_ends, self.par_dir = [], [], None, [], None
