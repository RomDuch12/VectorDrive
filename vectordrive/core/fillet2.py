"""Raccord entre deux traits (comme RACCORD / FILLET entre deux objets en
DAO) : deux segments droits de traits ouverts différents, cliqués du côté
à garder, sont prolongés ou raccourcis jusqu'à se rejoindre — par un arc
tangent de rayon r, ou en coin vif (r = 0). Les morceaux au-delà du coin
sont retirés.
"""
from __future__ import annotations

import math

from .geom import Contour, Line, arc_conics


def nearest_segment(c: Contour, p) -> int | None:
    """Indice du segment le plus proche de p."""
    best, k = None, None
    for i, s in enumerate(c.segments):
        a, b = s.start, s.end
        dx, dy = b[0] - a[0], b[1] - a[1]
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 < 1e-18 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
        d = math.dist((a[0] + t * dx, a[1] + t * dy), p)
        if best is None or d < best:
            best, k = d, i
    return k


def _cut(c: Contour, k: int, keep_start: bool, new_end) -> Contour:
    """Le contour coupé au segment k : on garde le côté du départ (segments
    0…k, le segment k finissant en `new_end`) ou de l'arrivée (k…fin,
    commençant en `new_end`)."""
    segs = list(c.segments)
    s = segs[k]
    if keep_start:
        return Contour(segs[:k] + [Line(s.start, new_end)], False)
    return Contour([Line(new_end, s.end)] + segs[k + 1:], False)


def fillet(ca: Contour, pa, cb: Contour, pb, r: float, chamfer: bool = False):
    """(nouveau contour A, nouveau contour B, arc ou None) — ou None si les
    segments cliqués ne sont pas droits, sont parallèles, ou si le rayon
    ne tient pas. `chamfer` : un chanfrein à `r` du coin sur chaque trait
    (segment droit) au lieu de l'arc."""
    ka, kb = nearest_segment(ca, pa), nearest_segment(cb, pb)
    if ka is None or kb is None:
        return None
    sa, sb = ca.segments[ka], cb.segments[kb]
    if not (isinstance(sa, Line) and isinstance(sb, Line)):
        return None
    (ax, ay), (bx, by) = sa.start, sa.end
    (cx, cy), (dx, dy) = sb.start, sb.end
    d1, d2 = (bx - ax, by - ay), (dx - cx, dy - cy)
    den = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(den) < 1e-12:
        return None
    t = ((cx - ax) * d2[1] - (cy - ay) * d2[0]) / den
    X = (ax + t * d1[0], ay + t * d1[1])
    # côté gardé : vers le clic depuis le coin
    def keep_dir(p, s, d):
        n = math.hypot(*d)
        u = (d[0] / n, d[1] / n)
        sg = 1.0 if (p[0] - X[0]) * u[0] + (p[1] - X[1]) * u[1] >= 0 else -1.0
        return (u[0] * sg, u[1] * sg), sg < 0       # vers le départ du segment : on garde le départ
    ua, keep_a_start = keep_dir(pa, sa, d1)
    ub, keep_b_start = keep_dir(pb, sb, d2)
    cos = max(-1.0, min(1.0, ua[0] * ub[0] + ua[1] * ub[1]))
    theta = math.acos(cos)
    if theta < 1e-6 or abs(theta - math.pi) < 1e-6:
        return None
    if r <= 1e-12:
        return _cut(ca, ka, keep_a_start, X), _cut(cb, kb, keep_b_start, X), None
    dist = r if chamfer else r / math.tan(theta / 2)
    Ta = (X[0] + ua[0] * dist, X[1] + ua[1] * dist)
    Tb = (X[0] + ub[0] * dist, X[1] + ub[1] * dist)
    # les tangentes doivent rester sur ce qu'on garde (sinon le rayon est trop grand)
    for s, keep_start in ((sa, keep_a_start), (sb, keep_b_start)):
        far = s.start if keep_start else s.end
        if dist > math.dist(X, far) + 1e-9:
            return None
    if chamfer:
        return _cut(ca, ka, keep_a_start, Ta), _cut(cb, kb, keep_b_start, Tb), Contour([Line(Ta, Tb)], False)
    bis = (ua[0] + ub[0], ua[1] + ub[1])
    bn = math.hypot(*bis)
    C = (X[0] + bis[0] / bn * r / math.sin(theta / 2), X[1] + bis[1] / bn * r / math.sin(theta / 2))
    a0 = math.degrees(math.atan2(Ta[1] - C[1], Ta[0] - C[0]))
    a1 = math.degrees(math.atan2(Tb[1] - C[1], Tb[0] - C[0]))
    sweep = (a1 - a0 + 180.0) % 360.0 - 180.0
    arc = Contour(arc_conics(C, r, r, a0, sweep), False)
    return _cut(ca, ka, keep_a_start, Ta), _cut(cb, kb, keep_b_start, Tb), arc
