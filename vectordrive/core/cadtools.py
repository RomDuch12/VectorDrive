"""Outils de dessin technique (comme les commandes DIVISER, MESURER,
MODIFLONG et REPÈRE DE CENTRE des logiciels de DAO) :

* **diviser** une courbe en n parts égales, **mesurer** une courbe tous les
  d mm : des points (repères) le long du tracé, avec l'angle de la
  tangente pour les orienter ;
* **allonger** un contour ouvert : de Δ, jusqu'à une longueur totale, ou
  d'un pourcentage — prolongé en droite dans la tangente du bout, raccourci
  en coupant le tracé ;
* **repères de centre** des cercles et arcs : une croix au centre, avec
  ou sans traits débordant du cercle ;
* **propriétés de masse** d'un ensemble de contours fermés : aire,
  périmètre, centre de gravité, moments d'inertie, rayons de giration.
"""
from __future__ import annotations

import math

from .geom import Contour, Line, Path, Point, dist
from . import nodes


# --- points le long d'une courbe ---------------------------------------------------------------
def _polyline(c: Contour, tol: float = 0.005) -> list[Point]:
    return c.flatten(tol)


def _at_lengths(c: Contour, lengths: list[float], tol: float = 0.005) -> list[tuple[float, float, float]]:
    """(x, y, angle° de la tangente) aux abscisses curvilignes données (dans
    leur ordre)."""
    P = _polyline(c, tol)
    cum = [0.0]
    for a, b in zip(P, P[1:]):
        cum.append(cum[-1] + dist(a, b))
    k = cum[-1] / max(1e-12, contour_length(c))         # abscisses exactes → abscisses de la polyligne
    order = sorted(range(len(lengths)), key=lambda j: lengths[j])
    out = [None] * len(lengths)
    i = 0
    for j in order:
        s = lengths[j] * k
        while i < len(cum) - 2 and cum[i + 1] < s:
            i += 1
        a, b = P[i], P[min(i + 1, len(P) - 1)]
        seg = cum[min(i + 1, len(cum) - 1)] - cum[i]
        f = (s - cum[i]) / seg if seg > 1e-12 else 0.0
        x, y = a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1])
        out[j] = (x, y, math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])))
    return out


def contour_length(c: Contour) -> float:
    return sum(s.length() for s in c.segments)


def divide(c: Contour, n: int) -> list[tuple[float, float, float]]:
    """n parts égales : n − 1 points sur un contour ouvert (les bouts exclus),
    n points sur un contour fermé (départ compris)."""
    n = max(2, int(n))
    L = contour_length(c)
    ks = range(n) if c.closed else range(1, n)
    return _at_lengths(c, [L * k / n for k in ks])


def measure(c: Contour, step: float, from_end: bool = False) -> list[tuple[float, float, float]]:
    """Un point tous les `step` mm depuis le départ (ou la fin), le départ
    exclu, comme MESURER."""
    L = contour_length(c)
    if step <= 0 or L <= 0:
        return []
    k = int(math.floor(L / step + 1e-9))
    ss = [step * i for i in range(1, k + 1) if step * i < L - 1e-9 or not c.closed]
    ss = [s for s in ss if s <= L + 1e-9]
    if from_end:
        ss = [L - s for s in ss]
    return _at_lengths(c, ss)


# --- allonger -----------------------------------------------------------------------------------
def _cut_start(c: Contour, d: float) -> Contour:
    """Le contour ouvert sans ses `d` premiers mm."""
    segs = list(c.segments)
    while segs and d > 1e-12:
        s = segs[0]
        L = s.length()
        if L <= d + 1e-12:
            d -= L
            segs.pop(0)
            continue
        lo, hi = 0.0, 1.0
        for _ in range(50):
            mid = (lo + hi) / 2
            if nodes.split_segment(s, mid)[0].length() < d:
                lo = mid
            else:
                hi = mid
        segs[0] = nodes.split_segment(s, (lo + hi) / 2)[1]
        d = 0.0
    return Contour(segs, False)


def _reverse(c: Contour) -> Contour:
    return Contour([s.reversed() for s in reversed(c.segments)], c.closed)


def _extend_start(c: Contour, d: float) -> Contour:
    s = c.segments[0]
    a = s.start
    q = next((p for p in s.controls()[1:] if dist(p, a) > 1e-12), s.end)
    ux, uy = a[0] - q[0], a[1] - q[1]
    n = math.hypot(ux, uy)
    if n < 1e-12:
        return c
    if isinstance(s, Line):
        return Contour([Line((a[0] + ux / n * d, a[1] + uy / n * d), s.end)] + list(c.segments[1:]), False)
    return Contour([Line((a[0] + ux / n * d, a[1] + uy / n * d), a)] + list(c.segments), False)


def lengthen(c: Contour, mode: str, value: float, end: str = 'fin') -> Contour:
    """Allonger (ou raccourcir) un contour ouvert. `mode` : 'delta' (mm, négatif :
    raccourcir), 'total' (longueur voulue), 'pourcent' (de la longueur) ;
    `end` : 'debut', 'fin' ou 'les_deux' (le changement partagé en deux)."""
    if c.closed or not c.segments:
        return c
    L = contour_length(c)
    delta = {'total': value - L, 'pourcent': L * (value / 100.0 - 1.0)}.get(mode, value)
    if L + delta <= 1e-6:
        raise ValueError('longueur nulle ou négative')
    parts = {'debut': (delta, 0.0), 'fin': (0.0, delta), 'les_deux': (delta / 2, delta / 2)}.get(end, (0.0, delta))

    def change_start(cc, d):
        if abs(d) < 1e-12:
            return cc
        return _extend_start(cc, d) if d > 0 else _cut_start(cc, -d)
    out = change_start(c, parts[0])
    out = _reverse(change_start(_reverse(out), parts[1]))
    return out


# --- repères de centre ----------------------------------------------------------------------------
def circle_of(c: Contour, tol: float = 0.01) -> tuple[Point, float] | None:
    """(centre, rayon) si le contour est un cercle ou un arc de cercle (les
    points aplatis à `tol` du cercle de leur ajustement)."""
    P = _polyline(c, tol / 4)
    if len(P) < 4:
        return None
    a, b, d = P[0], P[len(P) // 3], P[2 * len(P) // 3]
    ax, ay = a
    bx, by = b
    cx, cy = d
    den = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(den) < 1e-12:
        return None
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / den
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / den
    r = dist(a, (ux, uy))
    mids = [sg.point(0.5) for sg in c.segments]               # le milieu des segments aussi (un carré a ses coins sur un cercle)
    if r <= 0 or any(abs(dist(p, (ux, uy)) - r) > tol for p in P + mids):
        return None
    return (ux, uy), r


def change_point(c: Contour, p: Point) -> Contour | None:
    """Changer par un point (CHANGE, d'après CADCraft
    `crates/engine/src/cmd/props/change.rs`) : un contour ouvert dont le bout
    le plus proche de `p` est un trait droit voit ce bout amené en `p` ; un
    cercle garde son centre et passe par `p` ; None pour le reste (ou si
    rien ne bouge, ou si le trait s'annulerait)."""
    if not c.segments:
        return None
    if c.closed:
        got = circle_of(c)
        if got is None or dist(got[0], p) < 1e-9 or abs(dist(got[0], p) - got[1]) < 1e-9:
            return None
        from .geom import circle
        new = circle(got[0], dist(got[0], p))
        return new if (new.signed_area() > 0) == (c.signed_area() > 0) else new.reversed()
    first = dist(c.start, p) <= dist(c.end, p)
    s = c.segments[0] if first else c.segments[-1]
    if not isinstance(s, Line) or dist(c.start if first else c.end, p) < 1e-9:
        return None
    s2 = Line(p, s.p1) if first else Line(s.p0, p)
    if dist(s2.p0, s2.p1) < 1e-9:
        return None
    segs = list(c.segments)
    segs[0 if first else -1] = s2
    return Contour(segs, False)


def center_mark(center: Point, r: float, size: float = 2.0, extend: float = 2.0, lines: bool = True) -> Path:
    """Repère de centre : petite croix de `size` mm ; avec `lines`, traits
    jusqu'à `extend` mm au-delà du cercle, séparés de la croix."""
    x, y = center
    h = size / 2
    cs = [Contour([Line((x - h, y), (x + h, y))], False), Contour([Line((x, y - h), (x, y + h))], False)]
    if lines and r + extend > size:
        g = size * 0.5                                    # écart entre la croix et les traits
        a, b = h + g, r + extend
        for sx, sy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            cs.append(Contour([Line((x + sx * a, y + sy * a), (x + sx * b, y + sy * b))], False))
    return Path(cs)


def center_line(l1, l2, extend: float = 2.0) -> tuple[Point, Point] | None:
    """Ligne d'axe de deux traits droits (comme CENTERLINE en DAO, d'après
    CADCraft) : du milieu de leurs débuts au milieu de leurs fins, les traits
    remis dans le même sens, prolongée de `extend` mm à chaque bout ;
    (début, fin), ou None si elle n'a pas de longueur."""
    (a1, b1), (a2, b2) = l1, l2
    if (b1[0] - a1[0]) * (b2[0] - a2[0]) + (b1[1] - a1[1]) * (b2[1] - a2[1]) < 0:
        a2, b2 = b2, a2
    st = ((a1[0] + a2[0]) / 2, (a1[1] + a2[1]) / 2)
    en = ((b1[0] + b2[0]) / 2, (b1[1] + b2[1]) / 2)
    n = dist(st, en)
    if n < 1e-9:
        return None
    ux, uy = (en[0] - st[0]) / n, (en[1] - st[1]) / n
    return (st[0] - ux * extend, st[1] - uy * extend), (en[0] + ux * extend, en[1] + uy * extend)


def axis_path(a: Point, b: Point, dashed: bool = False, scale: float = 0.25) -> Path:
    """Trait d'axe de a à b ; `dashed` : en trait mixte (motif CENTER à
    l'échelle `scale`, ajustée pour finir sur un tiret long aux deux bouts)."""
    path = Path([Contour([Line(a, b)], False)])
    length = dist(a, b)
    if not dashed or length < 1e-9:
        return path
    from . import linetypes as LT
    pat = next(lt.pattern for lt in LT.standard() if lt.name == 'CENTER')
    period, first = sum(abs(d) for d in pat), pat[0]
    n = max(0, round((length / max(scale, 1e-6) - first) / period))
    return LT.dash_path(path, pat, length / (n * period + first))


# --- propriétés de masse ----------------------------------------------------------------------------
def mass_properties(path: Path, tol: float = 0.005) -> dict:
    """Aire, périmètre, centre de gravité, moments d'inertie (au centre de
    gravité, axes x et y, polaire) et rayons de giration ; les trous (sens
    opposé, règle pair-impair) sont retranchés."""
    import shapely
    from shapely.geometry import Polygon
    polys = []
    per = 0.0
    for c in path.contours:
        P = _polyline(c, tol)
        per += sum(dist(a, b) for a, b in zip(P, P[1:]))
        if c.closed and len(P) >= 3:
            polys.append(Polygon(P))
    if not polys:
        return {'area': 0.0, 'perimeter': per}
    level = polys                                    # pair-impair : trous retranchés ; deux à deux en arbre (le
    while len(level) > 1:                            # pli coûtait le carré : 1 500 formes, 13 s)
        nxt = [shapely.symmetric_difference(level[k], level[k + 1]) for k in range(0, len(level) - 1, 2)]
        level = nxt + ([level[-1]] if len(level) % 2 else [])
    region = level[0]
    A = cx = cy = Ixx = Iyy = Ixy = 0.0
    geoms = getattr(region, 'geoms', [region])
    for g in geoms:
        for ring, sign in [(g.exterior, 1.0)] + [(h, -1.0) for h in g.interiors]:
            pts = list(ring.coords)
            a = cxs = cys = ixx = iyy = ixy = 0.0
            for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                k = x0 * y1 - x1 * y0
                a += k
                cxs += (x0 + x1) * k
                cys += (y0 + y1) * k
                ixx += (y0 * y0 + y0 * y1 + y1 * y1) * k
                iyy += (x0 * x0 + x0 * x1 + x1 * x1) * k
                ixy += (x0 * y1 + 2 * x0 * y0 + 2 * x1 * y1 + x1 * y0) * k
            s = sign * (1.0 if a >= 0 else -1.0)                 # chaque anneau compté avec son signe
            A += s * a / 2
            cx += s * cxs / 6
            cy += s * cys / 6
            Ixx += s * ixx / 12
            Iyy += s * iyy / 12
            Ixy += s * ixy / 24
    if abs(A) < 1e-12:
        return {'area': 0.0, 'perimeter': per}
    gx, gy = cx / A, cy / A
    ixx_c = Ixx - A * gy * gy                                     # moments au centre de gravité
    iyy_c = Iyy - A * gx * gx
    ixy_c = Ixy - A * gx * gy
    return {'area': A, 'perimeter': per, 'centroid': (gx, gy), 'Ixx': ixx_c, 'Iyy': iyy_c, 'Ixy': ixy_c,
            'J': ixx_c + iyy_c, 'kx': math.sqrt(max(0.0, ixx_c / A)), 'ky': math.sqrt(max(0.0, iyy_c / A)),
            'bbox': region.bounds}


def break_line(a, b, size: float = 0.0, extension: float = 0.0):
    """Ligne de coupure (symbole de rupture des dessins techniques) : trait
    de a à b avec un zigzag au milieu — `size` : hauteur du zigzag (0 : un
    sixième de la longueur) ; `extension` : trait prolongé au-delà des deux
    points. Contour ouvert ; None si a et b sont confondus."""
    import math
    from .geom import polyline
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy)
    if L < 1e-9:
        return None
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    h = size if size > 0 else L / 6
    s = min(h, L * 0.8)                             # largeur du zigzag le long du trait
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    e = max(0.0, extension)

    def at(t, n=0.0):
        return (mx + ux * t + nx * n, my + uy * t + ny * n)
    pts = [(a[0] - ux * e, a[1] - uy * e), at(-s / 2), at(-s / 4, h / 2), at(s / 4, -h / 2), at(s / 2),
           (b[0] + ux * e, b[1] + uy * e)]
    return polyline(pts)
