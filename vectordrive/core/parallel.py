"""Courbes parallèles précises, trait double et gomme à boucles.

`parallel(contour, d)` : courbe(s) à distance d (d > 0 : à gauche du sens
de parcours) —

* droites décalées exactement ;
* arcs de cercle (coniques) : arcs concentriques **exacts** ;
* Bézier et arcs d'ellipse : Bézier d'Hermite ajustées sur la courbe
  parallèle exacte, coupées tant que l'écart dépasse `tol` (0,1 µm) ;
* raccords : arc de cercle exact côté extérieur d'un angle, coupe à
  l'intersection côté intérieur ;
* nettoyage : la courbe brute est coupée à ses auto-intersections et
  seuls les morceaux réellement à distance |d| du tracé sont gardés
  (boucles des courbures plus fortes que 1/d, U trop étroits…).

`remove_loops` est aussi la commande « Gomme à boucles ».

`offset_open(contour, d, join)` : Décaler (A) un contour ouvert, comme TypeEdit — un seul contour ouvert parallèle,
d > 0 à droite du sens de tracé, raccords arrondis, vifs ou chanfreinés (round 1170).
"""
from __future__ import annotations

import math

import numpy as np

from .geom import Conic, Contour, Cubic, Line, Path, arc_conics, dist
from .trim import piece, segment_crossings, self_crossings, split_at

TOL = 1e-4


def _left(v):
    n = math.hypot(*v)
    return (-v[1] / n, v[0] / n) if n > 1e-15 else (0.0, 0.0)


def _start_tangent(seg):
    pts = seg.controls()
    for q in pts[1:]:
        v = (q[0] - pts[0][0], q[1] - pts[0][1])
        if math.hypot(*v) > 1e-12:
            return v
    return (0.0, 0.0)


def _end_tangent(seg):
    pts = seg.controls()
    for q in reversed(pts[:-1]):
        v = (pts[-1][0] - q[0], pts[-1][1] - q[1])
        if math.hypot(*v) > 1e-12:
            return v
    return (0.0, 0.0)


# --- un segment --------------------------------------------------------------------

def _cubic_d(c: Cubic, t: float):
    """B'(t), B''(t)."""
    p0, p1, p2, p3 = c.p0, c.p1, c.p2, c.p3
    u = 1 - t
    d1 = tuple(3 * (u * u * (p1[k] - p0[k]) + 2 * u * t * (p2[k] - p1[k]) + t * t * (p3[k] - p2[k])) for k in (0, 1))
    d2 = tuple(6 * (u * (p2[k] - 2 * p1[k] + p0[k]) + t * (p3[k] - 2 * p2[k] + p1[k])) for k in (0, 1))
    return d1, d2


def _offset_point(c: Cubic, t: float, d: float):
    """Point et dérivée de la courbe parallèle O(t) = B(t) + d·n(t)."""
    b = c.point(t)
    (dx, dy), (ex, ey) = _cubic_d(c, t)
    s2 = dx * dx + dy * dy
    if s2 < 1e-24:                                  # point de rebroussement : on s'écarte un peu
        tt = min(1.0, t + 1e-6) if t < 0.5 else max(0.0, t - 1e-6)
        b2, _ = _offset_point(c, tt, d)
        (dx, dy), (ex, ey) = _cubic_d(c, tt)
        s2 = dx * dx + dy * dy
        if s2 < 1e-24:
            return b, (0.0, 0.0)
    s = math.sqrt(s2)
    n = (-dy / s, dx / s)
    # n' = J·(B''·|B'|² − B'·(B'·B'')) / |B'|³
    k = dx * ex + dy * ey
    nx = -(ey * s2 - dy * k) / (s2 * s)
    ny = (ex * s2 - dx * k) / (s2 * s)
    return (b[0] + d * n[0], b[1] + d * n[1]), (dx + d * nx, dy + d * ny)


def _offset_cubic(c: Cubic, d: float, tol: float, t0=0.0, t1=1.0, depth=0) -> list:
    a, da = _offset_point(c, t0, d)
    b, db = _offset_point(c, t1, d)
    h = t1 - t0
    seg = Cubic(a, (a[0] + da[0] * h / 3, a[1] + da[1] * h / 3), (b[0] - db[0] * h / 3, b[1] - db[1] * h / 3), b)
    err = max(dist(seg.point(u), _offset_point(c, t0 + u * h, d)[0]) for u in (0.2, 0.4, 0.5, 0.6, 0.8))
    if err > tol and depth < 18:
        m = (t0 + t1) / 2
        return _offset_cubic(c, d, tol, t0, m, depth + 1) + _offset_cubic(c, d, tol, m, t1, depth + 1)
    return [seg]


def offset_segment(seg, d: float, tol: float = TOL) -> list:
    """Segment(s) parallèle(s) à distance d (à gauche) ; [] si dégénéré."""
    if isinstance(seg, Line):
        n = _left((seg.p1[0] - seg.p0[0], seg.p1[1] - seg.p0[1]))
        if n == (0.0, 0.0):
            return []
        return [Line((seg.p0[0] + d * n[0], seg.p0[1] + d * n[1]), (seg.p1[0] + d * n[0], seg.p1[1] + d * n[1]))]
    if isinstance(seg, Conic):
        cp = seg.circle_params()
        if cp is not None:
            c, r = cp[0], cp[1]
            n = _left(_start_tangent(seg))
            out = 1.0 if (seg.p0[0] - c[0]) * n[0] + (seg.p0[1] - c[1]) * n[1] > 0 else -1.0
            nr = r + d * out
            if nr <= 1e-9:
                return []
            k = nr / r
            sc = [(c[0] + (q[0] - c[0]) * k, c[1] + (q[1] - c[1]) * k) for q in (seg.p0, seg.p1, seg.p2)]
            return [Conic(sc[0], sc[1], sc[2], seg.w)]
        out = []
        for cb in seg.to_cubics(tol / 10):
            out += _offset_cubic(cb, d, tol)
        return out
    return _offset_cubic(seg, d, tol)


# --- un contour --------------------------------------------------------------------

#: angle vif (`join='miter'`) : au-delà de MITER_LIMIT·|d| du sommet, l'angle est chanfreiné (la limite de
#: `pathops.offset`)
MITER_LIMIT = 4.0


class _Corner(Line):
    """Raccord vif ou chanfreiné d'un angle extérieur (round 1170) ; `vertex` : le sommet d'origine ; `near` : sa
    plus courte distance à ce sommet, seuil du nettoyage pour lui (un chanfrein passe plus près du tracé que |d|).
    Jamais rendu tel quel : `_clean` le change en droite."""


def _corner(p, q, vertex) -> _Corner:
    seg = _Corner(p, q)
    dx, dy = q[0] - p[0], q[1] - p[1]
    n2 = dx * dx + dy * dy
    t = 0.0 if n2 < 1e-30 else max(0.0, min(1.0, ((vertex[0] - p[0]) * dx + (vertex[1] - p[1]) * dy) / n2))
    object.__setattr__(seg, 'vertex', vertex)
    object.__setattr__(seg, 'near', dist(vertex, (p[0] + t * dx, p[1] + t * dy)))
    return seg


def _keep_corner(old, new):
    """`new`, morceau coupé de `old` (`split_at` rend une droite ordinaire) : raccord vif ou chanfreiné s'il l'était,
    avec son sommet et le seuil du raccord entier (deux chanfreins voisins alignés, recoupés, restent d'un tenant)."""
    if not isinstance(old, _Corner):
        return new
    seg = _corner(new.p0, new.p1, old.vertex)
    object.__setattr__(seg, 'near', old.near)
    return seg


def _sharp(acc: list, a, b, vertex, d: float, theta: float, t_in, join: str) -> None:
    """Angle extérieur vif (`miter` : prolongement des deux tangentes jusqu'à leur rencontre, chanfrein au-delà de
    MITER_LIMIT) ou chanfreiné (`bevel` : droite de a à b)."""
    if join == 'miter':
        half = math.radians(abs(theta)) / 2
        n = math.hypot(*t_in)
        if n > 1e-15 and math.cos(half) * MITER_LIMIT >= 1.0:
            s = abs(d) * math.tan(half)                  # de a à la pointe, le long de la tangente d'arrivée
            m = (a[0] + t_in[0] / n * s, a[1] + t_in[1] / n * s)
            acc.append(_corner(a, m, vertex))
            acc.append(_corner(m, b, vertex))
            return
    acc.append(_corner(a, b, vertex))


def _join(acc: list, nxt: list, vertex, d: float, t_in, t_out, join: str = 'round') -> None:
    """Raccorde `nxt` à la fin de `acc` (modifie les deux listes) ; `join` : angle extérieur arrondi (d'office),
    vif (`miter`) ou chanfreiné (`bevel`) — un demi-tour reste arrondi."""
    if not acc or not nxt:
        return
    a, b = acc[-1].end, nxt[0].start
    if dist(a, b) < 1e-9:
        nxt[0] = _with_start(nxt[0], a)
        return
    # angle de virage signé ; un demi-tour (pic aller-retour) compte comme
    # un angle extérieur des deux côtés : l'arc passe devant le sommet
    theta = math.degrees(math.atan2(t_in[0] * t_out[1] - t_in[1] * t_out[0],
                                    t_in[0] * t_out[0] + t_in[1] * t_out[1]))
    if theta * d < 0 or abs(theta) > 179.9:             # côté extérieur : arc autour du sommet
        if join in ('miter', 'bevel') and abs(theta) <= 179.9:
            _sharp(acc, a, b, vertex, d, theta, t_in, join)
            return
        va = (a[0] - vertex[0], a[1] - vertex[1])
        sweep = -math.copysign(abs(theta), d)
        arc = arc_conics(vertex, abs(d), abs(d), math.degrees(math.atan2(va[1], va[0])), sweep)
        if arc:
            arc[0] = _with_start(arc[0], a)
            arc[-1] = _with_end(arc[-1], b)
            acc.extend(arc)
            return
    # côté intérieur : les deux parallèles se recoupent, on coupe à l'intersection
    for i in range(len(acc) - 1, max(-1, len(acc) - 4), -1):
        for j in range(min(3, len(nxt))):
            hits = segment_crossings(acc[i], nxt[j])
            if hits:
                ta, tb = max(hits, key=lambda h: (h[0], -h[1]))
                left = _keep_corner(acc[i], split_at(acc[i], ta)[0]) if ta < 1 - 1e-12 else acc[i]
                right = split_at(nxt[j], tb)[1] if tb > 1e-12 else nxt[j]
                del acc[i:]
                acc.append(left)
                del nxt[:j + 1]
                nxt.insert(0, _with_start(right, left.end))
                return
    if dist(a, b) < 0.05 * abs(d):                      # quasi tangent : simple raccord
        acc.append(Line(a, b))
        return
    # repli : passage par le sommet d'origine ; ce pont est à distance < |d|
    # du tracé, le nettoyage l'écarte toujours et raccorde les parallèles là
    # où elles se croisent plus loin
    acc.append(_Bridge(a, vertex))
    acc.append(_Bridge(vertex, b))


class _Bridge(Line):
    """Pont provisoire par le sommet d'origine (jamais gardé)."""


def _with_start(seg, p):
    if isinstance(seg, Line):
        return Line(p, seg.p1)
    if isinstance(seg, Cubic):
        return Cubic(p, seg.p1, seg.p2, seg.p3)
    return Conic(p, seg.p1, seg.p2, seg.w)


def _with_end(seg, p):
    if isinstance(seg, Line):
        return Line(seg.p0, p)
    if isinstance(seg, Cubic):
        return Cubic(seg.p0, seg.p1, seg.p2, p)
    return Conic(seg.p0, seg.p1, p, seg.w)


def _without_specks(c: Contour, eps: float) -> Contour:
    """Retire les micro-segments (jonctions de splines DXF : droites de
    0,1 µm à la direction arbitraire) en recollant leurs voisins."""
    segs = []
    for s in c.segments:
        if max(dist(s.start, q) for q in s.controls()) <= eps:
            continue
        if segs and dist(segs[-1].end, s.start) > 0:
            s = _with_start(s, segs[-1].end)
        segs.append(s)
    if c.closed and len(segs) > 1 and dist(segs[-1].end, segs[0].start) > 0:
        segs[-1] = _with_end(segs[-1], segs[0].start)
    if not segs and c.segments:
        return Contour([], c.closed)
    if not c.closed and segs:
        if dist(segs[0].start, c.start) > 0:
            segs[0] = _with_start(segs[0], c.start)
        if dist(segs[-1].end, c.end) > 0:
            segs[-1] = _with_end(segs[-1], c.end)
    return Contour(segs, c.closed)


def parallel_raw(contour: Contour, d: float, tol: float = TOL, join: str = 'round') -> Contour:
    c = contour.close() if contour.closed else contour
    c = _without_specks(c, min(1e-3, abs(d) / 100))
    segs = c.segments
    if not segs:
        return Contour([], contour.closed)
    pieces = [offset_segment(s, d, tol) for s in segs]
    idx = [i for i, p in enumerate(pieces) if p]
    if not idx:
        return Contour([], contour.closed)
    acc = list(pieces[idx[0]])
    for a, b in zip(idx, idx[1:]):
        nxt = list(pieces[b])
        _join(acc, nxt, segs[b].start, d, _end_tangent(segs[a]), _start_tangent(segs[b]), join)
        acc.extend(nxt)
    if c.closed:
        first = acc[:len(pieces[idx[0]])]
        tail = acc
        nxt = list(first)
        _join(tail, nxt, segs[idx[0]].start, d, _end_tangent(segs[idx[-1]]), _start_tangent(segs[idx[0]]), join)
        # `nxt` est le début modifié : on le remet en tête
        k = len(first)
        acc = nxt + tail[k:] if len(tail) >= k else nxt
        if acc and dist(acc[-1].end, acc[0].start) > 1e-9:
            acc[-1] = _with_end(acc[-1], acc[0].start) if dist(acc[-1].end, acc[0].start) < 1e-6 else acc[-1]
    return Contour(acc, c.closed)


def _loop_size(loop: Contour, by: str) -> float:
    if by == 'encombrement':                          # diagonale de la boîte de la boucle (TypeEdit)
        b = loop.bbox()
        return math.hypot(b[2] - b[0], b[3] - b[1]) if b else 0.0
    return loop.length()


def remove_loops(contour: Contour, max_len: float = math.inf, by: str = 'longueur', removed: list | None = None) -> Contour:
    """Gomme les boucles d'auto-intersection (la plus courte d'abord) dont la
    longueur — ou l'encombrement (`by='encombrement'` : diagonale de leur
    boîte) — ne dépasse pas `max_len`. `removed` : y sont ajoutées les
    boucles ôtées, refermées (pour les séparer du contour au lieu de les
    supprimer)."""
    c = contour.close() if contour.closed else contour
    for _ in range(2000):
        pairs = self_crossings(c)
        if not pairs:
            break
        n = len(c.segments)
        best = None
        for ga, gb in pairs:
            loop = piece(c, ga, gb)
            L = _loop_size(loop, by)
            if c.closed:
                other = piece(c, gb, ga)
                if _loop_size(other, by) < L:
                    L, ga, gb = _loop_size(other, by), gb, ga
            if best is None or L < best[0]:
                best = (L, ga, gb)
        L, ga, gb = best
        if L > max_len:
            break
        if removed is not None:
            lp = piece(c, ga, gb)
            if lp.segments:
                removed.append(Contour(lp.segments, True))
        if c.closed:
            rest = piece(c, gb, ga)
            c = Contour(rest.segments, True)
        else:
            a = piece(c, 0.0, ga).segments if ga > 1e-12 else []
            b = piece(c, gb, float(n)).segments if gb < n - 1e-12 else []
            if a and b:
                b[0] = _with_start(b[0], a[-1].end)
            c = Contour(a + b, False)
    return c


#: bases de Bernstein par nombre de pas (t, u, u³, 3u²t, 3ut², t³, u², t²)
_BASES: dict[int, tuple] = {}


def _bases(k: int) -> tuple:
    b = _BASES.get(k)
    if b is None:
        t = np.linspace(0.0, 1.0, k + 1)[1:, None]
        u = 1 - t
        b = _BASES[k] = (t, u, u ** 3, 3 * u * u * t, 3 * u * t * t, t ** 3, u * u, t * t)
    return b


def _polyline(c: Contour, tol: float = 1e-4):
    """Polyligne du contour à `tol` près, évaluée en numpy : nombre de pas
    tiré de la borne de la dérivée seconde (erreur de corde ≤ |B''|·h²/8).
    Suites de droites d'un bloc, bases de Bernstein en cache."""
    out = []
    run = [c.start]                                  # suite de sommets de droites
    hyp, sqrt, ceil = math.hypot, math.sqrt, math.ceil
    for sg in c.segments:
        ty = type(sg)
        if ty is Line:
            run.append(sg.p1)
            continue
        if ty is Cubic:
            (x0, y0), (x1, y1), (x2, y2), (x3, y3) = sg.p0, sg.p1, sg.p2, sg.p3
            acc = 6 * max(hyp(x0 - 2 * x1 + x2, y0 - 2 * y1 + y2), hyp(x1 - 2 * x2 + x3, y1 - 2 * y2 + y3))
        elif ty is Conic:
            (x0, y0), (x1, y1), (x2, y2) = sg.p0, sg.p1, sg.p2
            acc = 2 * hyp(x0 - 2 * x1 + x2, y0 - 2 * y1 + y2) * max(1.0, 1 / max(sg.w, 1e-3) ** 2)
        else:
            run.append(sg.end)
            continue
        if run:
            out.append(np.asarray(run, float))
            run = []
        k = int(min(4000, max(2, ceil(sqrt(acc / (8 * tol))))))
        t, u, c3, c2, c1, c0, uu, tt = _bases(k)
        P = np.asarray(sg.controls(), float)
        if ty is Cubic:
            pts = c3 * P[0] + c2 * P[1] + c1 * P[2] + c0 * P[3]
        else:
            a1 = 2 * sg.w * u * t
            pts = (uu * P[0] + a1 * P[1] + tt * P[2]) / (uu + a1 + tt)
        out.append(pts)
    if run:
        out.append(np.asarray(run, float))
    q = np.concatenate(out)
    if c.closed and np.hypot(*(q[0] - q[-1])) > 1e-12:
        q = np.vstack([q, q[:1]])
    return q


def _line_of(orig: Contour):
    import shapely
    q = _polyline(orig)
    if len(q) < 2:
        q = np.vstack([q, q]) if len(q) else np.zeros((2, 2))
    return shapely.LineString(q)


def _distances(orig: Contour, pts, line=None):
    """Distances de points au tracé d'origine (polyligne à 10⁻⁴ mm, bien en
    deçà de la marge de validité de 10⁻³ ; shapely)."""
    import shapely
    line = line if line is not None else _line_of(orig)
    P = np.asarray(pts, float)
    return shapely.distance(line, shapely.points(P[:, 0], P[:, 1]))


def _far_runs(raw: Contour, orig: Contour, g0: float, g1: float, r: float, lim: float, line,
              per: int = 8) -> list[tuple[float, float]]:
    """Parties à r du tracé d'un morceau [g0, g1] de la parallèle brute
    dont les sondes ne s'accordent pas : il garde une boucle que la
    recherche des croisements n'a pas vue. Relevé : à la pointe d'une
    Bézier plus serrée que r, la parallèle fait un aller-retour presque
    confondu avec le raccord rond qui suit, et leur croisement, presque
    tangent, échappe aux polylignes d'échantillonnage ; une sonde tombée
    dans la boucle faisait jeter tout le côté extérieur de la bande.
    Échantillonne le morceau (`per` points par segment), coupe par
    dichotomie là où la distance passe la limite ; les bouts de moins de
    0,05·r tombent (l'écart est refermé par un segment)."""
    n = len(raw.segments)

    def at(g):
        i = int(math.floor(g))
        if not raw.closed and i >= n:
            i = n - 1
        return raw.segments[i % n].point(g - i)

    m = max(16, int(math.ceil((g1 - g0) * per)))
    gs = np.linspace(g0, g1, m + 1).tolist()
    good = (_distances(orig, [at(g) for g in gs], line) >= lim).tolist()
    runs, start = [], (g0 if good[0] else None)
    for a in range(m):
        if good[a] == good[a + 1]:
            continue
        lo, hi = gs[a], gs[a + 1]                    # lo du côté de good[a]
        for _ in range(40):
            mid = (lo + hi) / 2
            if bool(_distances(orig, [at(mid)], line)[0] >= lim) == good[a]:
                lo = mid
            else:
                hi = mid
        if good[a]:
            runs.append((start, lo))
            start = None
        else:
            start = hi
    if start is not None:
        runs.append((start, g1))
    return [(a, b) for a, b in runs
            if b - a > 1e-9 and sum(sg.length() for sg in piece(raw, a, b).segments) >= 0.05 * r]


def _clean(raw: Contour, orig: Contour, d: float, tol: float = TOL, line=None) -> list[Contour]:
    """Morceaux de la parallèle brute réellement à distance |d| du tracé
    d'origine : coupe aux auto-intersections, test du milieu de chaque
    morceau, puis rechaînage par les extrémités communes."""
    n = len(raw.segments)
    bridges = {k for k, sg in enumerate(raw.segments) if isinstance(sg, _Bridge)}
    corners = {k: sg.near for k, sg in enumerate(raw.segments) if isinstance(sg, _Corner)}
    cuts = sorted({round(g, 12) for pair in self_crossings(raw) for g in pair}
                  | {float(k) for k in bridges} | {float((k + 1) % n if raw.closed else k + 1) for k in bridges}
                  | {float(k) for k in corners} | {float((k + 1) % n if raw.closed else k + 1) for k in corners})
    if raw.closed:
        spans = list(zip(cuts, cuts[1:] + [cuts[0] + n])) if cuts else [(0.0, float(n))]
    else:
        b = [0.0] + cuts + [float(n)]
        spans = list(zip(b, b[1:]))
    # les morceaux valables sont à |d| (à la tolérance d'ajustement près) ;
    # les autres passent nettement plus près du tracé (3 points par morceau)
    lim = abs(d) - max(10 * tol, 1e-6)
    spans = [(g0, g1) for g0, g1 in spans if g1 - g0 >= 1e-12]
    probes = []
    for g0, g1 in spans:
        for f in (0.25, 0.5, 0.75):
            gm = g0 + (g1 - g0) * f
            i = int(math.floor(gm))
            probes.append(raw.segments[i % n].point(gm - i))

    # seuil de chaque morceau : |d|, ou la distance au sommet d'un raccord vif ou chanfreiné (round 1170)
    def span_lim(g0, g1):
        k = int(math.floor((g0 + g1) / 2)) % n
        return min(lim, corners[k] - max(10 * tol, 1e-6)) if k in corners else lim
    lims = [span_lim(g0, g1) for g0, g1 in spans]
    ok3 = (_distances(orig, probes, line).reshape(-1, 3) >= np.asarray(lims)[:, None]).tolist() if probes else []
    far = [all(row) for row in ok3]
    if bridges:
        far = [ok and int(math.floor((g0 + g1) / 2)) % n not in bridges for (g0, g1), ok in zip(spans, far)]
    # sondes en désaccord : le morceau garde une boucle que la recherche des
    # croisements n'a pas vue ; on n'en garde que les parties à |d|
    mixed = {i for i, ((g0, g1), row) in enumerate(zip(spans, ok3))
             if any(row) and not all(row) and int(math.floor((g0 + g1) / 2)) % n not in bridges}
    whole = raw.closed and not cuts and not mixed
    if mixed:
        line = line if line is not None else _line_of(orig)
        spans2, far2 = [], []
        for i, (sp, ok) in enumerate(zip(spans, far)):
            if i in mixed:
                runs = _far_runs(raw, orig, sp[0], sp[1], abs(d), lims[i], line)
                spans2 += runs
                far2 += [True] * len(runs)
            else:
                spans2.append(sp)
                far2.append(ok)
        spans, far = spans2, far2
    kept = [raw if whole else piece(raw, g0, g1) for (g0, g1), ok in zip(spans, far) if ok]
    if whole:
        return [raw] if kept else []
    out = _chain([pc.segments for pc in kept if pc.segments])
    if raw.closed:
        out = _close_gaps(out, abs(d))
    res = []
    out = [sg for sg in out if sum(x.length() for x in sg) > 1e-9]
    for segs in out:
        segs = [Line(sg.p0, sg.p1) if isinstance(sg, _Corner) else sg for sg in segs]
        closed = raw.closed and dist(segs[-1].end, segs[0].start) < 1e-6
        if closed:
            segs[-1] = _with_end(segs[-1], segs[0].start)
        res.append(Contour(segs, closed))
    return res


def _chain(pieces: list[list]) -> list[list]:
    """Rechaîne des morceaux par leurs extrémités communes (à 10⁻⁶ près),
    le suivant dans l'ordre d'abord."""
    left = [list(pc) for pc in pieces]
    out = []
    while left:
        cur = left.pop(0)
        while True:
            end = cur[-1].end
            k = next((i for i, pc in enumerate(left) if dist(pc[0].start, end) < 1e-6), None)
            if k is None or dist(cur[0].start, end) < 1e-6:
                break
            pc = left.pop(k)
            cur += [_with_start(pc[0], end)] + pc[1:]
        out.append(cur)
    # un morceau qui finit au début d'un autre déjà sorti (fermeture)
    changed = True
    while changed and len(out) > 1:
        changed = False
        for i, a in enumerate(out):
            for j, b in enumerate(out):
                if i != j and dist(a[-1].end, b[0].start) < 1e-6 and dist(a[0].start, a[-1].end) >= 1e-6:
                    out[i] = a + [_with_start(b[0], a[-1].end)] + b[1:]
                    del out[j]
                    changed = True
                    break
            if changed:
                break
    return out


def _close_gaps(chains: list[list], limit: float) -> list[list]:
    """Dernier recours pour un contour fermé : relie le bout d'une chaîne au
    début le plus proche (elle-même comprise) par un segment si l'écart est
    inférieur à `limit` (détails plus petits que le décalage, où les
    parallèles ne se croisent pas)."""
    chains = [c for c in chains if c]
    done = []
    while chains:
        cur = chains.pop(0)
        while dist(cur[-1].end, cur[0].start) >= 1e-6:
            end = cur[-1].end
            best = min(range(len(chains)), key=lambda i: dist(chains[i][0].start, end), default=None)
            own = dist(cur[0].start, end)
            if best is not None and dist(chains[best][0].start, end) < min(own, limit):
                nxt = chains.pop(best)
                cur = cur + [Line(end, nxt[0].start)] + nxt
            elif own < limit:
                cur = cur + [Line(end, cur[0].start)]
            else:
                break
        done.append(cur)
    return done


def parallel(contour: Contour, d: float, tol: float = TOL, line=None, join: str = 'round') -> list[Contour]:
    """Courbe(s) parallèle(s) propres à distance d (à gauche si d > 0) ;
    `line` : polyligne shapely du contour, si déjà calculée ; `join` : angles extérieurs arrondis (d'office), vifs
    (`miter`) ou chanfreinés (`bevel`)."""
    raw = parallel_raw(contour, d, tol, join)
    if not raw.segments:
        return []
    orig = contour.close() if contour.closed else contour
    return _clean(raw, orig, d, tol, line)


def double_line(path: Path, width: float, ends: str = 'open', tol: float = TOL) -> Path:
    """Trait double : les deux parallèles à ±width/2 de chaque contour.
    `ends` (contours ouverts) : 'open' (deux traits), 'butt' (bouts fermés
    par un segment), 'round' (bouts en demi-cercle)."""
    h = width / 2
    out = []
    for c in path.contours:
        if not c.segments:
            continue
        lefts, rights = parallel(c, h, tol), parallel(c, -h, tol)
        if c.closed or ends == 'open' or len(lefts) != 1 or len(rights) != 1:
            out += lefts + rights
            continue
        left, back = lefts[0], rights[0].reversed()
        segs = list(left.segments)
        for p_from, p_to, center, tangent in ((left.end, back.start, c.end, _end_tangent(c.segments[-1])),
                                             (back.end, left.start, c.start, None)):
            if p_from == back.end:
                segs += back.segments
            if ends == 'round':
                va = (p_from[0] - center[0], p_from[1] - center[1])
                a0 = math.degrees(math.atan2(va[1], va[0]))
                arc = arc_conics(center, h, h, a0, -180.0)
                arc[0] = _with_start(arc[0], p_from)
                arc[-1] = _with_end(arc[-1], p_to)
                segs += arc
            else:
                segs.append(Line(p_from, p_to))
        out.append(Contour(segs, True))
    return Path(out)


def _union_tree(paths: list[Path]) -> Path:
    from . import pathops
    paths = [x for x in paths if x.contours]
    while len(paths) > 1:
        nxt = [pathops.boolean(paths[i], paths[i + 1], 'union') for i in range(0, len(paths) - 1, 2)]
        if len(paths) % 2:
            nxt.append(paths[-1])
        paths = nxt
    return paths[0] if paths else Path()


def band(c: Contour, r: float, tol: float = TOL) -> Path:
    """Bande de demi-largeur r autour d'un contour (somme de Minkowski du
    trait et d'un disque) : parallèles à ±r d'un contour fermé (région
    pair-impair), trait double à bouts ronds d'un contour ouvert."""
    if c.closed:
        line = _line_of(c.close())
        return Path(parallel(c, r, tol, line) + parallel(c, -r, tol, line))
    return double_line(Path([c]), 2 * r, 'round', tol)


def offset_region(path: Path, d: float, tol: float = TOL) -> Path:
    """Décalage d'une région (règle pair-impair) avec raccords ronds :
    d > 0 l'élargit (région ∪ bandes), d < 0 l'amincit (région − bandes).
    Les contours ouverts deviennent le contour de leur trait. Exact sur les
    arcs et à 0,1 µm sur les Bézier avant les booléens (qui travaillent
    eux-mêmes à 0,1 µm)."""
    from . import pathops
    closed = Path([c for c in path.contours if c.closed and c.segments])
    r = abs(d)
    if r < 1e-12:
        return closed
    bands = _union_tree([band(c, r, tol) for c in path.contours if c.segments])
    if d > 0:
        return pathops.boolean(closed, bands, 'union') if closed.contours else bands
    return pathops.boolean(closed, bands, 'difference') if closed.contours else Path()


#: Au-delà (segments), le décalage et le contour de trait restent sur le
#: calcul natif (9 µm) : photos vectorisées et logos de dizaines de milliers
#: de segments, où le calcul exact prendrait une minute.
EXACT_LIMIT = 4000

#: aplatissement des tracés pour contrôler les distances (mm)
CHECK_FLAT = 0.002


def misses(res: Path, path: Path, r: float) -> bool:
    """Un sommet de `res` (décalage ou contour de trait de `path` à la distance r) est plus près de `path` que r, à 1 % et 5 µm près :
    une bande n'a pas couvert tout son contour et le résultat garde un morceau collé au tracé. Relevé sur de vrais dessins : la parallèle
    d'une Bézier qui se recoupe laisse un trou dans sa bande (règle pair-impair) ; un retrait de 1 mm gardait jusqu'à 1,9 mm² de
    matière sur le tracé, sous l'écart permis des aires. Tout sommet d'un résultat juste est à r au moins du tracé."""
    import shapely
    if r < 1e-9 or not res.contours:
        return False
    src = [np.asarray(p, dtype=float)[:, :2] for p in path.flatten(CHECK_FLAT) if len(p) >= 2]
    pts = [np.asarray(p, dtype=float)[:, :2] for p in res.flatten(CHECK_FLAT) if len(p)]
    if not src or not pts:
        return False
    segs = np.concatenate([np.stack([p[:-1], p[1:]], axis=1) for p in src])
    tree = shapely.STRtree(shapely.linestrings(segs))
    _i, near = tree.query_nearest(shapely.points(np.concatenate(pts)), return_distance=True, all_matches=False)
    return bool((near < r - (0.01 * r + 0.005)).any())


def offset_checked(path: Path, d: float, tol: float = TOL) -> tuple[Path, bool]:
    """Décalage à raccords ronds : version exacte si elle est cohérente avec
    le décalage par polygones de `pathops` (aires égales à 1,2 % du
    périmètre près, ou au quart de l'aire de la bande), sinon ce dernier (formes dégénérées : pics d'aire
    nulle, allers-retours). Renvoie (tracé, exact ?)."""
    from . import pathops
    ref = pathops.offset(path, d)
    if path.segment_count() > EXACT_LIMIT:
        return ref, False
    try:
        new = offset_region(path, d, tol)
    except Exception:                                   # filet de sécurité
        return ref, False
    per = path.length()
    # écart permis : celui du décalage par polygones (≈ 1 % du périmètre),
    # borné par le quart de l'aire de la bande (petits décalages) ; et aucun
    # sommet trop près du tracé (`misses`)
    if abs(pathops.area(new) - pathops.area(ref)) <= min(0.012, 0.25 * abs(d)) * per + 1e-6 and not misses(new, path, abs(d)):
        return new, True
    return ref, False


def stroke_checked(path: Path, width: float, tol: float = TOL) -> tuple[Path, bool]:
    """Contour d'un trait d'épaisseur `width` (bouts et raccords ronds) :
    réunion des bandes exactes de chaque contour, contrôlée contre le
    contour de trait natif (repli sur lui si les aires divergent).
    Renvoie (tracé, exact ?)."""
    from . import pathops
    ref = pathops.outline_stroke(path, width)
    r = abs(width) / 2
    if r < 1e-12 or path.segment_count() > EXACT_LIMIT:
        return ref, False
    try:
        new = _union_tree([band(c, r, tol) for c in path.contours if c.segments])
    except Exception:
        return ref, False
    per = path.length()
    if abs(pathops.area(new) - pathops.area(ref)) <= min(0.012, 0.25 * r) * per + 1e-6 and not misses(new, path, r):
        return new, True
    return ref, False


#: un contour ouvert dont les bouts sont plus près que cela (mm) est décalé comme un fermé (round 1170)
LOOP_GAP = 1e-6


def _open_polyline(c: Contour, d: float, join: str) -> list[Contour]:
    """Repli de `offset_open` (contour de plus de EXACT_LIMIT segments, ou erreur du calcul exact) : la parallèle
    de sa polyligne (aplatie à `pathops.FLATTEN`) par shapely (`offset_curve`, qui garde le sens de tracé ; d > 0 à
    droite), même limite de vif ; [] si elle échoue aussi (la forme reste alors telle quelle)."""
    try:
        import shapely

        from . import pathops
        from .geom import polyline
        pts = c.flatten(pathops.FLATTEN)
        if len(pts) < 2:
            return []
        style = {'miter': 'mitre', 'bevel': 'bevel'}.get(join, 'round')
        g = shapely.LineString(pts).offset_curve(-d, quad_segs=16, join_style=style, mitre_limit=MITER_LIMIT)
        parts = getattr(g, 'geoms', [g])
        out = [polyline([(float(x), float(y)) for x, y, *_z in ln.coords]) for ln in parts
               if not ln.is_empty and len(ln.coords) >= 2]
        return [k for k in out if k.segments]
    except Exception:                                    # filet de sécurité : la commande n'échoue jamais
        return []


def offset_open(c: Contour, d: float, join: str = 'round', tol: float = TOL) -> list[Contour]:
    """Décaler (A) un contour ouvert, comme TypeEdit (round 1170) : un contour ouvert parallèle à |d| partout,
    d'un seul côté — d > 0 à droite du sens de tracé (l'extérieur d'un contour fermé tracé dans le sens
    anti-horaire), d < 0 à gauche —, bouts décalés perpendiculairement (pas de bouchon), angles extérieurs selon
    `join` (arrondis exacts, vifs, chanfreinés), arcs exacts, Bézier à `tol` ; une boucle locale (rayon plus petit
    que |d| du côté du décalage) est ôtée et les deux côtés rejoints à leur croisement. Plusieurs morceaux seulement
    là où la parallèle disparaît vraiment ; [] si rien ne reste. Au-delà de EXACT_LIMIT segments, ou sur une erreur
    du calcul exact : `_open_polyline`."""
    if c.closed or not c.segments or abs(d) < 1e-12:
        return []
    if len(c.segments) > EXACT_LIMIT:
        return _open_polyline(c, d, join)
    try:
        res = parallel(c, -d, tol, join=join if join in ('miter', 'bevel') else 'round')
    except Exception:
        return _open_polyline(c, d, join)
    return [Contour(r.segments, False) for r in res if r.segments]


def offset_job(path: Path, distances: list, join: str = 'round') -> tuple[list, int, int]:
    """Décalages d'un tracé aux `distances` (commande Décaler) : (tracés non
    vides, exacts, approchés). Fonction du module : calculable dans un autre
    processus (core.workers.adaptive_map). Les contours ouverts donnent chacun un contour ouvert parallèle
    (`offset_open`, round 1170 ; avant : le contour fermé de leur trait) ; ceux dont les bouts se rejoignent (à
    LOOP_GAP près) sont décalés comme des fermés ; les fermés, comme avant."""
    from . import pathops
    looped = [c for c in path.contours if not c.closed and c.segments and dist(c.start, c.end) < LOOP_GAP]
    opened = [c for c in path.contours if not c.closed and c.segments and dist(c.start, c.end) >= LOOP_GAP]
    if opened or looped:                                 # les fermés seuls passent par le décalage de région
        path = Path([c for c in path.contours if c.closed and c.segments]
                    + [Contour(c.segments, True) for c in looped])
    out, exact, approx = [], 0, 0
    for d in distances:
        res = None
        if path.contours:
            if join == 'round':
                res, ok = offset_checked(path, d)            # exact (arcs concentriques), contrôlé
                exact += ok
                approx += not ok
            else:
                res = pathops.offset(path, d, join)
        if opened:
            lines = [r for c in opened for r in offset_open(c, d, join)]
            if lines:
                exact += not path.contours                   # exacts (arcs concentriques, Bézier à 0,1 µm)
                res = Path((res.contours if res else []) + lines)
        if res:
            out.append(res)
    return out, exact, approx
