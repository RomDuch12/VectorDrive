"""Coins réglables : les angles d'un tracé, droits ou courbes de chaque côté,
coupés en arrondi, arrondi inversé ou chanfrein, et la forme d'avant gardée pour
y revenir. Calculs d'après VectorCraft (`crates/geom/src/corners.rs`, MIT) ; les
coupes sont ici de vrais arcs (`Conic`), que la FAO reconnaît comme tels.

extra['corners'] = {'base': tracé d'avant, 'radii': {'contour:noeud': rayon},
'kinds': {…}, 'result': empreinte du tracé obtenu}. Un tracé retouché autrement
ne correspond plus à l'empreinte : il redevient une forme ordinaire.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

from .geom import Conic, Contour, Cubic, Line, Path, dist

KEY = 'corners'
ROUND, INVERTED, CHAMFER = 'round', 'inverted', 'chamfer'
KINDS = (ROUND, INVERTED, CHAMFER)

#: Sous ce changement de direction (degrés), deux segments se suivent : pas de coin.
MIN_TURN_DEG = 1.0
EPS = 1e-9
_TABLE = 64                 # points de la table des longueurs le long d'une courbe


def _leaving(seg) -> tuple | None:
    """La direction unitaire de départ d'un segment ; None : il n'a pas de longueur."""
    p = seg.start
    for q in seg.controls()[1:]:
        dx, dy = q[0] - p[0], q[1] - p[1]
        d = math.hypot(dx, dy)
        if d > EPS:
            return dx / d, dy / d
    return None


def _conic_split(c: Conic, t: float) -> tuple:
    """Une conique coupée à `t`, l'arc restant exact (de Casteljau en coordonnées homogènes)."""
    w = c.w
    a = (c.p0[0], c.p0[1], 1.0)
    b = (c.p1[0] * w, c.p1[1] * w, w)
    d = (c.p2[0], c.p2[1], 1.0)
    q0 = tuple(u + (v - u) * t for u, v in zip(a, b))
    q1 = tuple(u + (v - u) * t for u, v in zip(b, d))
    m = tuple(u + (v - u) * t for u, v in zip(q0, q1))
    mid = (m[0] / m[2], m[1] / m[2])
    root = math.sqrt(m[2])
    return (Conic(c.p0, (q0[0] / q0[2], q0[1] / q0[2]), mid, q0[2] / root),
            Conic(mid, (q1[0] / q1[2], q1[1] / q1[2]), c.p2, q1[2] / root))


def _at_length(seg, s: float) -> float:
    """Le paramètre à la longueur `s` depuis le début du segment."""
    pts = [seg.point(i / _TABLE) for i in range(_TABLE + 1)]
    done = 0.0
    for i in range(_TABLE):
        step = dist(pts[i], pts[i + 1])
        if done + step >= s:
            return (i + (s - done) / step) / _TABLE if step > EPS else i / _TABLE
        done += step
    return 1.0


def _after(seg, s: float):
    """Ce qui reste du segment après la longueur `s` depuis son début."""
    if s <= EPS:
        return seg
    if isinstance(seg, Line):
        u = _leaving(seg)
        return Line((seg.p0[0] + u[0] * s, seg.p0[1] + u[1] * s), seg.p1)
    t = _at_length(seg, s)
    if isinstance(seg, Cubic):
        return seg.split(t)[1]
    return _conic_split(seg, t)[1]


def _trimmed(seg, s_start: float, s_end: float):
    """Le segment sans ses longueurs `s_start` et `s_end` à ses bouts ; None : il n'en reste rien."""
    left = seg.length() - s_start - s_end
    if left <= 1e-7:
        return None
    out = _after(seg, s_start)
    if s_end > EPS:
        out = _after(out.reversed(), s_end).reversed()
    return out


def _from(seg, p: tuple):
    """Le segment, partant exactement de `p`."""
    if isinstance(seg, Line):
        return Line(p, seg.p1)
    if isinstance(seg, Cubic):
        return Cubic(p, seg.p1, seg.p2, seg.p3)
    return Conic(p, seg.p1, seg.p2, seg.w)


def _joined(segs: list, closed: bool) -> list:
    """Chaque segment part exactement d'où finit le précédent : les longueurs le long d'une
    courbe sont approchées, et un côté disparu laisse deux coupes bout à bout."""
    out = list(segs)
    for k in range(1, len(out)):
        if out[k].start != out[k - 1].end:
            out[k] = _from(out[k], out[k - 1].end)
    if closed and len(out) > 1 and out[0].start != out[-1].end:
        out[0] = _from(out[0], out[-1].end)
    return out


@dataclass(frozen=True)
class Corner:
    """Un coin : là où le segment `index - 1` et le segment `index` d'un contour se
    rencontrent. `u` et `v` : les directions unitaires qui quittent le coin, vers le
    nœud d'avant et vers le suivant ; `lu`, `lv` : les longueurs de ces côtés."""
    contour: int
    index: int
    at: tuple
    u: tuple
    v: tuple
    lu: float
    lv: float
    side_u: object
    side_v: object

    @property
    def key(self) -> str:
        return f'{self.contour}:{self.index}'

    @property
    def cos(self) -> float:
        return self.u[0] * self.v[0] + self.u[1] * self.v[1]

    @property
    def sin(self) -> float:
        return abs(self.u[0] * self.v[1] - self.u[1] * self.v[0])

    def angle_deg(self) -> float:
        return math.degrees(math.atan2(self.sin, self.cos))

    def setback(self, r: float) -> float:
        """À quelle distance du coin un arrondi de rayon `r` rejoint chaque côté."""
        return r * (1.0 + self.cos) / self.sin

    def max_radius(self) -> float:
        """Le plus grand rayon : la coupe atteint la moitié du côté le plus court."""
        return min(self.lu, self.lv) / 2.0 * self.sin / (1.0 + self.cos)

    def fitted(self, r: float) -> float:
        if not isinstance(r, (int, float)) or r != r:
            return 0.0
        return max(0.0, min(float(r), self.max_radius()))

    def on_bisector(self, k: float) -> tuple:
        return self.at[0] + (self.u[0] + self.v[0]) * k, self.at[1] + (self.u[1] + self.v[1]) * k

    def radius_change(self, dx: float, dy: float) -> float:
        """De combien le rayon change quand le centre de l'arrondi bouge de (dx, dy)."""
        return (dx * (self.u[0] + self.v[0]) + dy * (self.u[1] + self.v[1])) * self.sin / (2.0 + 2.0 * self.cos)

    def cut(self, radius: float, kind: str = ROUND):
        """(segment de coupe, longueur retirée à chaque côté) pour un rayon déjà ajusté."""
        s = self.setback(radius)
        rest_u, rest_v = _after(self.side_u, s), _after(self.side_v, s)
        a, b = rest_u.start, rest_v.start
        if kind == CHAMFER:
            return Line(a, b), s
        if kind == INVERTED:                         # un arc centré sur le coin
            half = math.acos(max(-1.0, min(1.0, self.cos))) / 2.0
            bx, by = self.u[0] + self.v[0], self.u[1] + self.v[1]
            n = math.hypot(bx, by)
            far = (dist(self.at, a) + dist(self.at, b)) / 2.0 / math.cos(half)
            return Conic(a, (self.at[0] + bx / n * far, self.at[1] + by / n * far), b, math.cos(half)), s
        if isinstance(self.side_u, Line) and isinstance(self.side_v, Line):
            return Conic(a, self.at, b, math.sqrt(max(0.0, (1.0 - self.cos) / 2.0))), s
        du, dv = _leaving(rest_u), _leaving(rest_v)
        if du is None or dv is None:
            return Line(a, b), s
        # le croisement des tangentes aux bouts de la coupe : a - du·p = b - dv·q
        cross = du[0] * dv[1] - du[1] * dv[0]
        wx, wy = a[0] - b[0], a[1] - b[1]
        if abs(cross) > 1e-6:
            p = (wx * dv[1] - wy * dv[0]) / cross
            q = (wx * du[1] - wy * du[0]) / cross
            if p > EPS and q > EPS:
                c = du[0] * dv[0] + du[1] * dv[1]
                return Conic(a, (a[0] - du[0] * p, a[1] - du[1] * p), b, math.sqrt(max(0.0, (1.0 - c) / 2.0))), s
        third = dist(a, b) / 3.0
        return Cubic(a, (a[0] - du[0] * third, a[1] - du[1] * third), (b[0] - dv[0] * third, b[1] - dv[1] * third), b), s


def contour_corners(contour: Contour, ci: int = 0) -> list:
    """Les coins d'un contour, dans l'ordre de ses nœuds."""
    segs = contour.segments
    n = len(segs)
    if n < 2 and not (n == 1 and contour.closed):
        return []
    limit = math.sin(math.radians(MIN_TURN_DEG))
    out = []
    for i in range(0 if contour.closed else 1, n):
        side_u, side_v = segs[i - 1].reversed(), segs[i]
        u, v = _leaving(side_u), _leaving(side_v)
        if u is None or v is None:
            continue
        cos = u[0] * v[0] + u[1] * v[1]
        sin = abs(u[0] * v[1] - u[1] * v[0])
        if sin <= limit:                            # dans le prolongement, ou repli sur lui-même
            continue
        lu, lv = side_u.length(), side_v.length()
        if lu <= EPS or lv <= EPS or cos != cos:
            continue
        out.append(Corner(ci, i, side_v.start, u, v, lu, lv, side_u, side_v))
    return out


def path_corners(path: Path) -> list:
    return [c for ci, contour in enumerate(path.contours) for c in contour_corners(contour, ci)]


def cut_contour(contour: Contour, ci: int, radii: dict, kinds: dict) -> Contour:
    segs = contour.segments
    n = len(segs)
    cuts = {}
    for c in contour_corners(contour, ci):
        r = c.fitted(radii.get(c.key, 0.0))
        if r > EPS:
            cuts[c.index] = c.cut(r, kinds.get(c.key, ROUND))
    if not cuts:
        return contour
    out = []
    for i, seg in enumerate(segs):
        if i in cuts and (i or not contour.closed):
            out.append(cuts[i][0])
        nxt = (i + 1) % n if contour.closed else i + 1
        part = _trimmed(seg, cuts[i][1] if i in cuts else 0.0, cuts[nxt][1] if nxt in cuts else 0.0)
        if part is not None:
            out.append(part)
    if contour.closed and 0 in cuts:                # la coupe du premier nœud referme le contour
        out.append(cuts[0][0])
    return Contour(_joined(out, contour.closed), contour.closed)


def cut(path: Path, radii: dict, kinds: dict | None = None) -> Path:
    """`path` avec ses coins coupés selon `radii` et `kinds` ({'contour:noeud': …}) ; un rayon
    trop grand est ramené à ce qui tient."""
    kinds = kinds or {}
    return Path([cut_contour(c, i, radii, kinds) for i, c in enumerate(path.contours)])


def signature(path: Path) -> str:
    """L'empreinte d'un tracé : la même une fois enregistré et relu."""
    from ..io.native import _path_out
    return hashlib.sha1(json.dumps(_path_out(path)).encode('ascii')).hexdigest()


def live_of(shape) -> tuple:
    """(tracé d'avant, rayons, sortes) d'une forme ; une forme sans coins réglables,
    ou retouchée autrement depuis, est son propre tracé d'avant."""
    d = shape.extra.get(KEY) if isinstance(shape.extra, dict) else None
    if isinstance(d, dict) and d.get('result') == signature(shape.path):
        from ..io.native import _path_in
        base = _path_in(d.get('base'))
        if base is not None:
            return base, dict(d.get('radii') or {}), dict(d.get('kinds') or {})
    return shape.path, {}, {}


def settings(base: Path, radii: dict, kinds: dict) -> tuple:
    """(tracé obtenu, données à garder ; None : plus aucun coin coupé)."""
    from ..io.native import _path_out
    radii = {k: float(r) for k, r in radii.items() if r > EPS}
    kinds = {k: v for k, v in kinds.items() if k in radii and v != ROUND}
    path = cut(base, radii, kinds)
    if not radii:
        return path, None
    return path, {'base': _path_out(base), 'radii': radii, 'kinds': kinds, 'result': signature(path)}


def transformed(d: dict, m, new_path: Path) -> dict | None:
    """Les données après la transformation `m` ; None : un étirement, la forme garde son
    tracé et ses coins ne sont plus réglables."""
    from ..io.native import _path_in, _path_out
    from .forms import _similarity
    sim = _similarity(m)
    base = _path_in(d.get('base')) if isinstance(d, dict) else None
    if sim is None or base is None:
        return None
    return {'base': _path_out(base.transformed(m)), 'radii': {k: r * sim[0] for k, r in d.get('radii', {}).items()},
            'kinds': dict(d.get('kinds') or {}), 'result': signature(new_path)}
