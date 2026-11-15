"""Tronquer et prolonger (outils de DAO de TypeEdit).

- `trim` : le morceau de contour cliqué, compris entre deux intersections
  (avec les autres objets, les autres contours de l'objet ou lui-même),
  est supprimé ; le reste devient un ou deux contours ouverts.
- `extend` : le bout d'un contour ouvert le plus proche du clic est
  prolongé, dans la direction de sa tangente, jusqu'au premier objet
  rencontré.

Les intersections sont exactes (approche par polylignes puis Newton sur
les segments eux-mêmes) et les courbes sont coupées à leur paramètre
exact (droites, Bézier, arcs rationnels).
"""
from __future__ import annotations

import math

import numpy as np

from .geom import Conic, Contour, Cubic, Line, Path

EPS_T = 1e-9


# --- découpe des segments ----------------------------------------------------------

def split_at(seg, t: float):
    """Coupe exacte d'un segment au paramètre t."""
    if isinstance(seg, Line):
        m = seg.point(t)
        return Line(seg.p0, m), Line(m, seg.p1)
    if isinstance(seg, Cubic):
        return seg.split(t)
    if isinstance(seg, Conic):
        w = seg.w
        # coordonnées homogènes (x·w, y·w, w) puis de Casteljau
        h0 = (seg.p0[0], seg.p0[1], 1.0)
        h1 = (seg.p1[0] * w, seg.p1[1] * w, w)
        h2 = (seg.p2[0], seg.p2[1], 1.0)
        a = tuple(h0[i] + (h1[i] - h0[i]) * t for i in range(3))
        b = tuple(h1[i] + (h2[i] - h1[i]) * t for i in range(3))
        m = tuple(a[i] + (b[i] - a[i]) * t for i in range(3))
        pm = (m[0] / m[2], m[1] / m[2])
        left = Conic(seg.p0, (a[0] / a[2], a[1] / a[2]), pm, a[2] / math.sqrt(m[2]))
        right = Conic(pm, (b[0] / b[2], b[1] / b[2]), seg.p2, b[2] / math.sqrt(m[2]))
        return left, right
    raise TypeError(type(seg))


def _conic_sub(seg: Conic, t0: float, t1: float) -> Conic:
    """Sous-arc exact [t0, t1] d'une conique : forme homogène et blossom
    (le paramètre d'un morceau découpé n'est pas linéaire en t)."""
    w = seg.w
    h = ((seg.p0[0], seg.p0[1], 1.0), (seg.p1[0] * w, seg.p1[1] * w, w), (seg.p2[0], seg.p2[1], 1.0))

    def blossom(a, b):
        c0, c1, c2 = (1 - a) * (1 - b), (1 - a) * b + a * (1 - b), a * b
        return tuple(c0 * h[0][k] + c1 * h[1][k] + c2 * h[2][k] for k in range(3))
    q0, q1, q2 = blossom(t0, t0), blossom(t0, t1), blossom(t1, t1)
    return Conic((q0[0] / q0[2], q0[1] / q0[2]), (q1[0] / q1[2], q1[1] / q1[2]), (q2[0] / q2[2], q2[1] / q2[2]),
                 q1[2] / math.sqrt(q0[2] * q2[2]))


def sub_segment(seg, t0: float, t1: float):
    """Portion [t0, t1] d'un segment (t0 < t1)."""
    if t0 <= EPS_T and t1 >= 1 - EPS_T:
        return seg
    if isinstance(seg, Conic):
        return _conic_sub(seg, max(0.0, t0), min(1.0, t1))
    s = seg
    if t1 < 1 - EPS_T:
        s = split_at(s, t1)[0]
    if t0 > EPS_T:
        s = split_at(s, t0 / t1)[1]
    return s


# --- intersections -----------------------------------------------------------------

_TS_CACHE: dict[int, np.ndarray] = {}


def _ts(k: int) -> np.ndarray:
    t = _TS_CACHE.get(k)
    if t is None:
        t = _TS_CACHE[k] = np.linspace(0.0, 1.0, k)
    return t


def _samples(seg) -> tuple[np.ndarray, np.ndarray]:
    """(paramètres, points) : 2 pour une droite ; pour une courbe, de 5 à
    33 selon sa taille (un point tous les 0,25 mm du polygone de contrôle),
    évaluation vectorisée."""
    if isinstance(seg, Line):
        return np.array([0.0, 1.0]), np.array([seg.p0, seg.p1], float)
    cp = seg.controls()
    L = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(cp, cp[1:]))
    _TS = _ts(min(33, max(5, int(math.ceil(L / 0.25)) + 1)))
    t = _TS[:, None]
    u = 1.0 - t
    if isinstance(seg, Cubic):
        p0, p1, p2, p3 = (np.asarray(q, float) for q in (seg.p0, seg.p1, seg.p2, seg.p3))
        return _TS, u ** 3 * p0 + 3 * u * u * t * p1 + 3 * u * t * t * p2 + t ** 3 * p3
    if isinstance(seg, Conic):
        p0, p1, p2 = (np.asarray(q, float) for q in (seg.p0, seg.p1, seg.p2))
        a, b, c = u * u, 2 * seg.w * u * t, t * t
        return _TS, (a * p0 + b * p1 + c * p2) / (a + b + c)
    return _TS, np.array([seg.point(float(x)) for x in _TS])


def _deriv(seg, t: float, h: float = 1e-7):
    a, b = max(0.0, t - h), min(1.0, t + h)
    p, q = seg.point(a), seg.point(b)
    return ((q[0] - p[0]) / (b - a), (q[1] - p[1]) / (b - a))


def _newton(sa, sb, ta: float, tb: float):
    for _ in range(30):
        A, B = sa.point(ta), sb.point(tb)
        fx, fy = A[0] - B[0], A[1] - B[1]
        if math.hypot(fx, fy) < 1e-12:
            break
        da, db = _deriv(sa, ta), _deriv(sb, tb)
        det = -da[0] * db[1] + da[1] * db[0]
        if abs(det) < 1e-18:
            break
        dta = (-fx * -db[1] + fy * -db[0]) / det
        dtb = (-da[0] * fy + da[1] * fx) / det
        ta = min(1.0, max(0.0, ta + dta))
        tb = min(1.0, max(0.0, tb + dtb))
    A, B = sa.point(ta), sb.point(tb)
    return ta, tb, math.hypot(A[0] - B[0], A[1] - B[1])


def _bbox(P):
    return P[:, 0].min(), P[:, 1].min(), P[:, 0].max(), P[:, 1].max()


def segment_crossings(sa, sb, A=None, B=None) -> list[tuple[float, float]]:
    """Paramètres (ta, tb) des intersections de deux segments ; A, B :
    échantillons (t, points) déjà calculés."""
    ta_s, P = A if A is not None else _samples(sa)
    tb_s, Q = B if B is not None else _samples(sb)
    a0, r = P[:-1], P[1:] - P[:-1]
    b0, s = Q[:-1], Q[1:] - Q[:-1]
    den = r[:, None, 0] * s[None, :, 1] - r[:, None, 1] * s[None, :, 0]
    w = b0[None, :, :] - a0[:, None, :]
    with np.errstate(divide='ignore', invalid='ignore'):
        t = (w[..., 0] * s[None, :, 1] - w[..., 1] * s[None, :, 0]) / den
        u = (w[..., 0] * r[:, None, 1] - w[..., 1] * r[:, None, 0]) / den
    ok = (np.abs(den) > 1e-18) & (t >= -1e-6) & (t <= 1 + 1e-6) & (u >= -1e-6) & (u <= 1 + 1e-6)
    out = []
    both_lines = isinstance(sa, Line) and isinstance(sb, Line)
    for i, j in zip(*np.nonzero(ok)):
        ta = float(ta_s[i] + (ta_s[i + 1] - ta_s[i]) * min(1.0, max(0.0, float(t[i, j]))))
        tb = float(tb_s[j] + (tb_s[j + 1] - tb_s[j]) * min(1.0, max(0.0, float(u[i, j]))))
        if not both_lines:
            ta, tb, err = _newton(sa, sb, ta, tb)
            if err > 1e-7:
                continue
        out.append((ta, tb))
    # doublons (croisement sur un sommet de polyligne)
    out.sort()
    uniq = []
    for ta, tb in out:
        if not uniq or abs(ta - uniq[-1][0]) > 1e-7 or abs(tb - uniq[-1][1]) > 1e-7:
            uniq.append((ta, tb))
    return uniq


def cut_params(contour: Contour, cutters: list, *, self_cut: bool = True) -> list[float]:
    """Paramètres globaux (indice du segment + t) où `contour` est coupé par
    les segments `cutters` (et par lui-même si `self_cut`)."""
    segs = contour.segments
    n = len(segs)
    smp = [_samples(x) for x in segs]
    if cutters:                                     # tri grossier : boîte du contour entier
        X0, Y0, X1, Y1 = (min(_bbox(P)[0] for _, P in smp), min(_bbox(P)[1] for _, P in smp),
                          max(_bbox(P)[2] for _, P in smp), max(_bbox(P)[3] for _, P in smp))
        keep = []
        for c in cutters:
            b = c.bbox()
            if b[0] <= X1 + 1e-6 and b[2] >= X0 - 1e-6 and b[1] <= Y1 + 1e-6 and b[3] >= Y0 - 1e-6:
                keep.append(c)
        cutters = keep
    csmp = [_samples(c) for c in cutters]
    bx = np.array([_bbox(P) for _, P in smp]).reshape(-1, 4)
    cb = np.array([_bbox(P) for _, P in csmp]).reshape(-1, 4)
    out = []
    for i, s in enumerate(segs):
        x0, y0, x1, y1 = bx[i]
        if len(cb):
            hit = np.nonzero((cb[:, 0] <= x1 + 1e-9) & (cb[:, 2] >= x0 - 1e-9)
                             & (cb[:, 1] <= y1 + 1e-9) & (cb[:, 3] >= y0 - 1e-9))[0]
            for k in hit:
                out += [i + ta for ta, _ in segment_crossings(s, cutters[k], smp[i], csmp[k])]
        if self_cut and i + 2 < n:
            js = np.arange(i + 2, n)
            m = ((bx[js, 0] <= x1 + 1e-9) & (bx[js, 2] >= x0 - 1e-9)
                 & (bx[js, 1] <= y1 + 1e-9) & (bx[js, 3] >= y0 - 1e-9))
            for j in js[m]:
                if contour.closed and i == 0 and j == n - 1:
                    continue                                     # voisins par la fermeture
                for ta, tb in segment_crossings(s, segs[j], smp[i], smp[j]):
                    out += [i + ta, int(j) + tb]
    out.sort()
    uniq = []
    for g in out:
        if not uniq or g - uniq[-1] > 1e-7:
            uniq.append(g)
    if not contour.closed:
        uniq = [g for g in uniq if 1e-7 < g < n - 1e-7]         # les bouts ne coupent rien
    elif uniq and uniq[-1] > n - 1e-7:              # n ≡ 0 sur un contour fermé
        uniq = uniq[:-1] if uniq[0] < 1e-7 else [0.0] + uniq[:-1]
    return [float(g) for g in uniq]


def _overlapping_pairs(bx: np.ndarray, gap: int = 2):
    """Couples (i, j), j ≥ i + gap, de boîtes qui se touchent (index
    spatial de shapely, en C)."""
    import shapely
    if len(bx) < gap + 1:
        return np.zeros(0, int), np.zeros(0, int)
    boxes = shapely.box(bx[:, 0] - 1e-9, bx[:, 1] - 1e-9, bx[:, 2] + 1e-9, bx[:, 3] + 1e-9)
    a, b = shapely.STRtree(boxes).query(boxes, predicate='intersects')
    m = b >= a + gap
    return a[m], b[m]


def _edges(segs, smp=None):
    """Arêtes des polylignes d'échantillonnage : (départs, arrivées, n° de
    segment, t de départ, t d'arrivée)."""
    smp = smp or [_samples(x) for x in segs]
    A, B, K, T0, T1 = [], [], [], [], []
    for k, (ts, P) in enumerate(smp):
        A.append(P[:-1])
        B.append(P[1:])
        K.append(np.full(len(P) - 1, k))
        T0.append(ts[:-1])
        T1.append(ts[1:])
    if not A:
        z = np.zeros((0, 2))
        return z, z, np.zeros(0, int), np.zeros(0), np.zeros(0)
    return np.concatenate(A), np.concatenate(B), np.concatenate(K), np.concatenate(T0), np.concatenate(T1)


def _edge_hits(ea, eb, same: bool):
    """Croisements d'arêtes (index spatial shapely puis calcul vectorisé) :
    (ia, ib, u, v) avec u, v les fractions le long des arêtes."""
    import shapely
    A0, A1 = ea[0], ea[1]
    B0, B1 = eb[0], eb[1]
    if not len(A0) or not len(B0):
        return (np.zeros(0, int),) * 2 + (np.zeros(0),) * 2
    la = shapely.linestrings(np.stack([A0, A1], 1))
    lb = la if same else shapely.linestrings(np.stack([B0, B1], 1))
    ib, ia = shapely.STRtree(lb).query(la, predicate='intersects')
    if not len(ia):
        return (np.zeros(0, int),) * 2 + (np.zeros(0),) * 2
    r, q = A1[ia] - A0[ia], B1[ib] - B0[ib]
    w = B0[ib] - A0[ia]
    den = r[:, 0] * q[:, 1] - r[:, 1] * q[:, 0]
    ok = np.abs(den) > 1e-18
    with np.errstate(divide='ignore', invalid='ignore'):
        u = (w[:, 0] * q[:, 1] - w[:, 1] * q[:, 0]) / den
        v = (w[:, 0] * r[:, 1] - w[:, 1] * r[:, 0]) / den
    return ia[ok], ib[ok], np.clip(u[ok], 0, 1), np.clip(v[ok], 0, 1)


def _refined(sa, sb, ta: float, tb: float):
    if isinstance(sa, Line) and isinstance(sb, Line):
        return ta, tb
    ta, tb, err = _newton(sa, sb, ta, tb)
    return (ta, tb) if err <= 1e-7 else None


def self_crossings(contour: Contour) -> list[tuple[float, float]]:
    """Couples (ga, gb), ga < gb, de paramètres globaux où le contour se
    recoupe lui-même (segments voisins exclus)."""
    segs = contour.segments
    n = len(segs)
    if n < 3:
        return []
    A0, A1, K, T0, T1 = _edges(segs)
    ia, ib, u, v = _edge_hits((A0, A1), (A0, A1), True)
    m = K[ib] >= K[ia] + 2
    if contour.closed:
        m &= ~((K[ia] == 0) & (K[ib] == n - 1))
    out = []
    seen = set()
    for a, b, uu, vv in zip(ia[m].tolist(), ib[m].tolist(), u[m].tolist(), v[m].tolist()):
        i, j = int(K[a]), int(K[b])
        ta = T0[a] + (T1[a] - T0[a]) * uu
        tb = T0[b] + (T1[b] - T0[b]) * vv
        r = _refined(segs[i], segs[j], float(ta), float(tb))
        if r is None:
            continue
        ga, gb = i + r[0], j + r[1]
        key = (round(ga, 7), round(gb, 7))
        if key in seen or gb - ga <= 1e-7 or (contour.closed and ga < 1e-7 and gb > n - 1e-7):
            continue
        seen.add(key)
        out.append((float(ga), float(gb)))
    out.sort()
    return out


def piece(contour: Contour, g0: float, g1: float) -> Contour:
    """Morceau ouvert du contour entre les paramètres globaux g0 et g1
    (g1 < g0 : on passe par la fermeture d'un contour fermé)."""
    segs = contour.segments
    n = len(segs)
    if g1 <= g0 + 1e-12:
        g1 += n
    out = []
    g = g0
    while g < g1 - 1e-12:
        i = int(math.floor(g + 1e-12))
        t0 = g - i
        end = min(g1, i + 1)
        t1 = end - i
        seg = segs[i % n]
        if t1 - t0 > 1e-12:
            out.append(sub_segment(seg, max(0.0, t0), min(1.0, t1)))
        g = end
    return Contour(out, False)


def _refine(s, p, lo: float, hi: float) -> float:
    for _ in range(40):
        m1, m2 = lo + (hi - lo) / 3, hi - (hi - lo) / 3
        if math.dist(s.point(m1), p) < math.dist(s.point(m2), p):
            hi = m2
        else:
            lo = m1
    return float((lo + hi) / 2)


def nearest_param(contour: Contour, p) -> tuple[float, float]:
    """(paramètre global, distance) du point du contour le plus proche de p :
    droites projetées exactement, courbes échantillonnées puis seules les
    plus proches resserrées."""
    best = (0.0, math.inf)
    coarse = []
    for i, s in enumerate(contour.segments):
        if isinstance(s, Line):
            a, b = s.p0, s.p1
            ab = (b[0] - a[0], b[1] - a[1])
            L2 = ab[0] ** 2 + ab[1] ** 2
            t = 0.0 if L2 < 1e-24 else min(1.0, max(0.0, ((p[0] - a[0]) * ab[0] + (p[1] - a[1]) * ab[1]) / L2))
            d = math.dist(s.point(t), p)
            if d < best[1]:
                best = (i + t, d)
        else:
            ts, P = _samples(s)
            dd = np.hypot(P[:, 0] - p[0], P[:, 1] - p[1])
            k = int(np.argmin(dd))
            # borne : la courbe ne s'écarte pas de plus d'un pas d'échantillon
            step = float(np.max(np.hypot(*np.diff(P, axis=0).T)))
            coarse.append((float(dd[k]) - step, float(dd[k]), i, k, ts))
    coarse.sort()
    for low, _, i, k, ts in coarse:
        if low > best[1]:
            break
        s = contour.segments[i]
        t = _refine(s, p, ts[max(0, k - 1)], ts[min(len(ts) - 1, k + 1)])
        d = math.dist(s.point(t), p)
        if d < best[1]:
            best = (i + t, d)
    return best


def trim_contour(contour: Contour, cutters: list, p, g: float | None = None) -> list[Contour] | None:
    """Contours restants après suppression du morceau cliqué en p ; None si
    rien à couper (aucune intersection : on ne supprime pas tout)."""
    cuts = cut_params(contour, cutters)
    if not cuts:
        return None
    n = len(contour.segments)
    if g is None:
        g, _ = nearest_param(contour, p)
    if contour.closed:
        if len(cuts) == 1:
            return []
        k = next((i for i, c in enumerate(cuts) if c > g), 0)
        a, b = cuts[k - 1], cuts[k]                 # morceau cliqué : de a à b (k = 0 : par la fermeture)
        return [piece(contour, b, a)]
    bounds = [0.0] + cuts + [float(n)]
    k = next(i for i in range(1, len(bounds)) if bounds[i] >= g)
    out = []
    if k - 1 > 0:
        out.append(piece(contour, 0.0, bounds[k - 1]))
    if k < len(bounds) - 1:
        out.append(piece(contour, bounds[k], float(n)))
    return [c for c in out if c.segments]


def trim(path: Path, others: list, p) -> Path | None:
    """Tronque le contour de `path` le plus proche de p ; `others` : segments
    des autres objets. None si rien n'a été coupé."""
    if not path.contours:
        return None
    near = [nearest_param(c, p) if c.segments else (0.0, math.inf) for c in path.contours]
    ci = min(range(len(near)), key=lambda i: near[i][1])
    target = path.contours[ci]
    if target.closed:
        target = target.close()                     # fermeture implicite → droite explicite
    cutters = list(others)
    for j, c in enumerate(path.contours):
        if j != ci:
            cutters += c.segments
    res = trim_contour(target, cutters, p, near[ci][0])
    if res is None:
        return None
    return Path(path.contours[:ci] + res + path.contours[ci + 1:])


# --- prolonger ----------------------------------------------------------------------

def _end_direction(seg, at_end: bool):
    """Direction exacte de sortie au bout d'un segment (vers l'extérieur) :
    le long du polygone de contrôle, sans dérivée numérique."""
    pts = list(seg.controls())
    if not at_end:
        pts = pts[::-1]
    q = pts[-1]
    for c in reversed(pts[:-1]):
        d = (q[0] - c[0], q[1] - c[1])
        if math.hypot(*d) > 1e-12:
            return d
    return (0.0, 0.0)


def extend(path: Path, others: list, p, reach: float = 1e4) -> Path | None:
    """Prolonge le bout (d'un contour ouvert) le plus proche de p jusqu'au
    premier segment rencontré dans `others` ou dans l'objet lui-même."""
    best = None
    for ci, c in enumerate(path.contours):
        if c.closed or not c.segments:
            continue
        for at_end in (False, True):
            q = c.end if at_end else c.start
            d = math.dist(q, p)
            if best is None or d < best[0]:
                best = (d, ci, at_end)
    if best is None:
        return None
    _, ci, at_end = best
    c = path.contours[ci]
    seg = c.segments[-1] if at_end else c.segments[0]
    q = seg.end if at_end else seg.start
    d = _end_direction(seg, at_end)
    L = math.hypot(*d)
    if L < 1e-15:
        return None
    u = (d[0] / L, d[1] / L)
    ray = Line(q, (q[0] + u[0] * reach, q[1] + u[1] * reach))
    cutters = list(others)
    for j, cc in enumerate(path.contours):
        cutters += [s for k, s in enumerate(cc.segments)
                    if not (j == ci and k == (len(cc.segments) - 1 if at_end else 0))]
    hits = []
    A = _samples(ray)
    lo = (min(ray.p0[0], ray.p1[0]), min(ray.p0[1], ray.p1[1]))
    hi = (max(ray.p0[0], ray.p1[0]), max(ray.p0[1], ray.p1[1]))
    for s in cutters:
        b = s.bbox()
        if b[0] > hi[0] + 1e-9 or b[2] < lo[0] - 1e-9 or b[1] > hi[1] + 1e-9 or b[3] < lo[1] - 1e-9:
            continue
        for tr_, _ in segment_crossings(ray, s, A):
            dist = tr_ * reach
            if dist > 1e-6:
                hits.append(dist)
    if not hits:
        return None
    dist = min(hits)
    target = (q[0] + u[0] * dist, q[1] + u[1] * dist)
    segs = list(c.segments)
    if isinstance(seg, Line):
        segs[-1 if at_end else 0] = Line(seg.p0, target) if at_end else Line(target, seg.p1)
    elif at_end:
        segs.append(Line(q, target))
    else:
        segs.insert(0, Line(target, q))
    out = list(path.contours)
    out[ci] = Contour(segs, False)
    return Path(out)


def _wrap(deg: float) -> float:
    return (deg + 180.0) % 360.0 - 180.0


def segment_circle(seg) -> tuple | None:
    """(centre, rayon, balayage signé en degrés) d'un segment qui est un arc de cercle : une conique, ou une cubique qui
    en suit un (un arc de fichier importé). Sinon None."""
    if isinstance(seg, Conic):
        cp = seg.circle_params()
        return None if cp is None else (cp[0], cp[1], cp[3])
    if not isinstance(seg, Cubic):
        return None
    (ax, ay), (bx, by), (cx, cy) = seg.start, seg.point(0.5), seg.end
    d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-9:
        return None
    sa, sb, sc = ax * ax + ay * ay, bx * bx + by * by, cx * cx + cy * cy
    ux = (sa * (by - cy) + sb * (cy - ay) + sc * (ay - by)) / d
    uy = (sa * (cx - bx) + sb * (ax - cx) + sc * (bx - ax)) / d
    r = math.hypot(ax - ux, ay - uy)
    tol = max(1e-3, r * 1e-3)                              # une cubique suit un quart de cercle à 0,03 % du rayon
    if any(abs(math.dist(seg.point(t), (ux, uy)) - r) > tol for t in (0.125, 0.25, 0.375, 0.625, 0.75, 0.875)):
        return None
    a0, a1, a2 = (math.degrees(math.atan2(q[1] - uy, q[0] - ux)) for q in ((ax, ay), (bx, by), (cx, cy)))
    return (ux, uy), r, _wrap(a1 - a0) + _wrap(a2 - a1)


class ArcReach:
    """Le bout d'arc à étendre, et tous les points que son cercle atteint, du plus proche au plus loin en le parcourant."""

    def __init__(self, ci: int, at_end: bool, center, r: float, sgn: float, q, room: float, skip: set):
        self.ci, self.at_end, self.center, self.r, self.sgn = ci, at_end, center, r, sgn
        self.q, self.room, self.skip = q, room, skip
        self.targets: list = []                            # (degrés depuis le bout, point sur le cercle)

    def extension(self, k: int) -> Contour | None:
        """L'arc ajouté pour atteindre la cible `k`, parcouru à partir du bout."""
        from .geom import arc_3points
        total, target = self.targets[k]
        cx, cy = self.center
        qa = math.degrees(math.atan2(self.q[1] - cy, self.q[0] - cx))
        mid_a = math.radians(qa + self.sgn * total / 2)
        return arc_3points(self.q, (cx + self.r * math.cos(mid_a), cy + self.r * math.sin(mid_a)), target)

    def extended(self, path: Path, k: int) -> Path | None:
        """Le tracé, l'arc étendu jusqu'à la cible `k`."""
        ext = self.extension(k)
        if ext is None or not ext.segments:
            return None
        c = path.contours[self.ci]
        segs = list(c.segments) + list(ext.segments) if self.at_end else list(ext.reversed().segments) + list(c.segments)
        out = list(path.contours)
        out[self.ci] = Contour(segs, False)
        return Path(out)


def _arc_end(path: Path, p) -> ArcReach | None:
    """Le bout de contour ouvert le plus proche de p, s'il finit par un arc de cercle (sinon None)."""
    best = None
    for ci, c in enumerate(path.contours):
        if c.closed or not c.segments:
            continue
        for at_end in (False, True):
            d = math.dist(c.end if at_end else c.start, p)
            if best is None or d < best[0]:
                best = (d, ci, at_end)
    if best is None:
        return None
    _, ci, at_end = best
    segs = path.contours[ci].segments
    order = list(range(len(segs) - 1, -1, -1)) if at_end else list(range(len(segs)))
    first = segment_circle(segs[order[0]])
    if first is None:
        return None
    center, r, sweep = first
    tol = max(1e-3, r * 1e-3)
    skip, total = {order[0]}, abs(sweep)
    for k in order[1:]:                                    # l'arc peut tenir en plusieurs segments du même cercle
        sc = segment_circle(segs[k])
        if sc is None or math.dist(sc[0], center) > tol or abs(sc[1] - r) > tol or sc[2] * sweep < 0:
            break
        skip.add(k)
        total += abs(sc[2])
    sgn = (1.0 if sweep > 0 else -1.0) * (1.0 if at_end else -1.0)     # au départ : on remonte le cercle
    return ArcReach(ci, at_end, center, r, sgn, segs[order[0]].end if at_end else segs[order[0]].start,
                    360.0 - total - 1e-6, skip)


def arc_targets(path: Path, others: list, p, step_deg: float = 1.0, first_only: bool = False) -> ArcReach | None:
    """Étendre en arc (TypeEdit) : le bout d'arc le plus proche de p et les points que son cercle atteint, sur un tour au
    plus, sur `others` ou sur le reste de l'objet. None : pas d'arc au bout."""
    a = _arc_end(path, p)
    if a is None:
        return None
    cutters = list(others)
    for j, cc in enumerate(path.contours):
        cutters += [s for k, s in enumerate(cc.segments) if not (j == a.ci and k in a.skip)]
    (cx, cy), r = a.center, a.r
    boxes = np.array([s.bbox() for s in cutters], dtype=float).reshape(-1, 4)
    near = (boxes[:, 0] <= cx + r + 1e-9) & (boxes[:, 2] >= cx - r - 1e-9) & (boxes[:, 1] <= cy + r + 1e-9) & (boxes[:, 3] >= cy - r - 1e-9)
    cutters = [s for s, on in zip(cutters, near) if on]
    boxes = boxes[near]
    qa = math.degrees(math.atan2(a.q[1] - cy, a.q[0] - cx))
    found = []
    done, prev = 0.0, a.q
    while done < a.room:
        step = min(step_deg, a.room - done)
        ang = math.radians(qa + a.sgn * (done + step))
        pt = (cx + r * math.cos(ang), cy + r * math.sin(ang))
        x0, x1 = min(prev[0], pt[0]) - 1e-9, max(prev[0], pt[0]) + 1e-9
        y0, y1 = min(prev[1], pt[1]) - 1e-9, max(prev[1], pt[1]) + 1e-9
        hit = (boxes[:, 0] <= x1) & (boxes[:, 2] >= x0) & (boxes[:, 1] <= y1) & (boxes[:, 3] >= y0)
        piece = Line(prev, pt)
        for j in np.nonzero(hit)[0]:
            for t, _ in segment_crossings(piece, cutters[int(j)]):
                if done + t * step > 1e-6:
                    hx, hy = prev[0] + (pt[0] - prev[0]) * t, prev[1] + (pt[1] - prev[1]) * t
                    ha = math.atan2(hy - cy, hx - cx)      # ramené sur le cercle
                    found.append((done + t * step, (cx + r * math.cos(ha), cy + r * math.sin(ha))))
        done += step
        prev = pt
        if first_only and found:
            break
    found.sort(key=lambda f: f[0])
    for f in found:
        if not a.targets or f[0] - a.targets[-1][0] > 1e-6:
            a.targets.append(f)
    return a


def extend_arc(path: Path, others: list, p, step_deg: float = 1.0) -> Path | None:
    """Le bout d'arc le plus proche de p, prolongé sur son cercle jusqu'au premier point atteint. None : pas d'arc au
    bout, ou rien sur le cercle."""
    a = arc_targets(path, others, p, step_deg, first_only=True)
    if a is None or not a.targets:
        return None
    return a.extended(path, 0)
