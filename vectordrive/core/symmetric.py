"""Dessin symétrique (les « courbes symétriques » de TypeEdit) : chaque
forme dessinée reçoit son reflet par rapport à un axe vertical.

Un trait ouvert dont un bout touche l'axe est prolongé par son reflet en
un seul trait ; si ses deux bouts touchent l'axe, trait et reflet forment
un contour fermé (profil de vase, d'écusson…). Les bouts proches de l'axe
y sont posés exactement.
"""
from __future__ import annotations

from .geom import Affine, Conic, Contour, Cubic, Line, Path


def _moved_end(s, p, at_end: bool):
    if isinstance(s, Line):
        return Line(s.p0, p) if at_end else Line(p, s.p1)
    if isinstance(s, Cubic):
        return Cubic(s.p0, s.p1, s.p2, p) if at_end else Cubic(p, s.p1, s.p2, s.p3)
    return Conic(s.p0, s.p1, p, s.w) if at_end else Conic(p, s.p1, s.p2, s.w)


def _snap(c: Contour, axis_x: float, tol: float) -> tuple[Contour, bool, bool]:
    """Bouts proches de l'axe posés dessus ; (contour, départ sur l'axe, fin
    sur l'axe)."""
    segs = list(c.segments)
    on_start = abs(c.start[0] - axis_x) <= tol
    on_end = abs(c.end[0] - axis_x) <= tol
    if on_start:
        segs[0] = _moved_end(segs[0], (axis_x, c.start[1]), False)
    if on_end:
        segs[-1] = _moved_end(segs[-1], (axis_x, segs[-1].end[1]), True)
    return Contour(segs, c.closed), on_start, on_end


def revolution(contour, n: int, center, clockwise: bool = True):
    """Courbe de révolution (TypeEdit) : `n` copies d'une courbe ouverte,
    tournées autour de `center`, mises bout à bout en une courbe fermée
    (un segment droit relie deux copies qui ne se touchent pas)."""
    import math

    from .geom import Affine, Contour, Line
    if n < 1 or not contour.segments:
        return contour
    step = (-360.0 if clockwise else 360.0) / n
    segs = []
    for k in range(n):
        part = contour.transformed(Affine.rotation(step * k, center))
        if segs and math.dist(segs[-1].end, part.segments[0].start) > 1e-9:
            segs.append(Line(segs[-1].end, part.segments[0].start))
        segs.extend(part.segments)
    if math.dist(segs[-1].end, segs[0].start) > 1e-9:
        segs.append(Line(segs[-1].end, segs[0].start))
    return Contour(segs, True)


#: les courbes symétriques de TypeEdit : par rapport à l'axe horizontal, à l'axe vertical, aux deux axes, à l'origine
SYM_MODES = ('ox', 'oy', 'both', 'origin')


def _on_axes(p, mode: str, center, tol: float):
    """Un point presque sur un axe y est posé exactement : le reflet se confond alors avec lui."""
    x, y = float(p[0]), float(p[1])
    cx, cy = center
    if mode == 'origin':
        return (cx, cy) if abs(x - cx) <= tol and abs(y - cy) <= tol else (x, y)
    if mode in ('oy', 'both') and abs(x - cx) <= tol:
        x = cx
    if mode in ('ox', 'both') and abs(y - cy) <= tol:
        y = cy
    return x, y


def _copies(points: list, mode: str, center) -> list:
    """Les copies du tracé, chacune avec son sens de parcours, dans l'ordre où la courbe les enchaîne."""
    cx, cy = center
    mx, my, half = Affine.mirror_x(cy), Affine.mirror_y(cx), Affine.rotation(180.0, (cx, cy))
    if mode == 'ox':
        return [(None, False), (mx, True)]
    if mode == 'oy':
        return [(None, False), (my, True)]
    if mode == 'origin':
        return [(None, False), (half, False)]
    # aux deux axes : la courbe passe d'abord l'axe dont le tracé finit le plus près, sinon elle se croise
    ex, ey = points[-1]
    first, second = (my, mx) if abs(ex - cx) < abs(ey - cy) else (mx, my)
    return [(None, False), (first, True), (half, False), (second, True)]


def sym_points(points: list, mode: str, center, corners=(), tol: float = 0.0) -> list:
    """Tous les points de la courbe, (x, y, angle ?), sans doublon entre deux points qui se suivent."""
    base = [_on_axes(p, mode, center, tol) for p in points]
    if not base:
        return []
    out = []
    for m, back in _copies(base, mode, center):
        part = [((m.apply(p) if m is not None else p), i in corners) for i, p in enumerate(base)]
        for q, angle in (reversed(part) if back else part):
            if out and abs(out[-1][0] - q[0]) < 1e-9 and abs(out[-1][1] - q[1]) < 1e-9:
                out[-1] = (out[-1][0], out[-1][1], out[-1][2] or angle)
            else:
                out.append((q[0], q[1], angle))
    return out


def _smooth(pts: list, closed: bool = False) -> Contour:
    """Courbe lisse par les points, poignées à la mesure de chaque corde : ni boucle ni pointe entre deux points
    rapprochés, comme un point et son reflet de part et d'autre d'un axe."""
    from .geom import dist
    n = len(pts)
    if n < 2:
        return Contour([], closed)
    if n == 2:
        return Contour([Line(pts[0], pts[1])], False)

    def tangent(i):
        if not closed and i in (0, n - 1):
            a, b = (pts[0], pts[1]) if i == 0 else (pts[-2], pts[-1])
            d = dist(a, b)
            return (b[0] - a[0]) / d, (b[1] - a[1]) / d
        a, q, b = pts[(i - 1) % n], pts[i], pts[(i + 1) % n]
        d1, d2 = dist(a, q), dist(q, b)
        k1, k2 = d2 / (d1 * (d1 + d2)), d1 / (d2 * (d1 + d2))
        return (q[0] - a[0]) * k1 + (b[0] - q[0]) * k2, (q[1] - a[1]) * k1 + (b[1] - q[1]) * k2
    segs = []
    for i in range(n if closed else n - 1):
        j = (i + 1) % n
        p0, p3 = pts[i], pts[j]
        d = dist(p0, p3) / 3.0
        t0, t1 = tangent(i), tangent(j)
        segs.append(Cubic(p0, (p0[0] + t0[0] * d, p0[1] + t0[1] * d), (p3[0] - t1[0] * d, p3[1] - t1[1] * d), p3))
    return Contour(segs, closed)


def sym_curve(points: list, mode: str, center, closed: bool = True, corners=(), tol: float = 0.0) -> Contour:
    """La courbe symétrique d'un seul tenant : lisse, sauf aux points d'angle (`corners`, indices de `points`)."""
    full = sym_points(points, mode, center, corners, tol)
    if closed and len(full) > 1 and abs(full[0][0] - full[-1][0]) < 1e-9 and abs(full[0][1] - full[-1][1]) < 1e-9:
        full[0] = (full[0][0], full[0][1], full[0][2] or full[-1][2])
        full.pop()
    if len(full) < 2:
        return Contour([], closed)
    closed = closed and len(full) > 2
    if not any(q[2] for q in full):
        return _smooth([q[:2] for q in full], closed)
    if closed:                                         # une courbe fermée part d'un angle et y revient
        k = next(i for i, q in enumerate(full) if q[2])
        full = full[k:] + full[:k] + [full[k]]
    segs, run = [], [full[0][:2]]
    for q in full[1:]:
        run.append(q[:2])
        if q[2]:
            segs += _smooth(run).segments
            run = [q[:2]]
    if len(run) > 1:
        segs += _smooth(run).segments
    return Contour(segs, closed)


def mirror_join(path: Path, axis_x: float, tol: float = 1e-6) -> Path:
    m = Affine.mirror_y(axis_x)
    out = []
    for c in path.contours:
        if not c.segments:
            continue
        if c.closed:
            out += [c, c.transformed(m)]
            continue
        c, on_start, on_end = _snap(c, axis_x, tol)
        back = c.transformed(m).reversed()                 # reflet parcouru en sens inverse
        if on_start and on_end and len(c.segments) >= 1 and abs(c.start[1] - c.end[1]) > tol:
            out.append(Contour(c.segments + back.segments, True))
        elif on_end:
            out.append(Contour(c.segments + back.segments, False))
        elif on_start:
            out.append(Contour(back.segments + c.segments, False))
        else:
            out += [c, c.transformed(m)]
    return Path(out)
