"""Édition point par point d'un contour (Mode Point de TypeEdit).

Un contour est une suite de segments ; le **nœud k** est l'extrémité du
segment k (pour un contour ouvert, le nœud −1 est le départ du segment 0).
Les fonctions renvoient un nouveau contour ; elles ne modifient rien.
"""
from __future__ import annotations

import math

from .geom import Conic, Contour, Cubic, Line, Point, Segment, dist, lerp


def node_count(c: Contour) -> int:
    return len(c.segments) if c.closed else len(c.segments) + 1


def node_point(c: Contour, k: int) -> Point:
    """Position du nœud k (0 ≤ k < node_count). Ouvert : nœud 0 = départ."""
    if c.closed:
        return c.segments[k].end
    return c.segments[0].start if k == 0 else c.segments[k - 1].end


def _seg_in_out(c: Contour, k: int) -> tuple[int | None, int | None]:
    """Indices du segment qui arrive au nœud k et de celui qui en part."""
    n = len(c.segments)
    if c.closed:
        return k, (k + 1) % n
    return (k - 1 if k > 0 else None), (k if k < n else None)


def _with_start(s: Segment, p: Point, move_handle: bool) -> Segment:
    if isinstance(s, Line):
        return Line(p, s.p1)
    if isinstance(s, Cubic):
        h = s.p1
        if move_handle:
            h = (h[0] + p[0] - s.p0[0], h[1] + p[1] - s.p0[1])
        return Cubic(p, h, s.p2, s.p3)
    return Conic(p, s.p1, s.p2, s.w)


def _with_end(s: Segment, p: Point, move_handle: bool) -> Segment:
    if isinstance(s, Line):
        return Line(s.p0, p)
    if isinstance(s, Cubic):
        h = s.p2
        if move_handle:
            h = (h[0] + p[0] - s.p3[0], h[1] + p[1] - s.p3[1])
        return Cubic(s.p0, s.p1, h, p)
    return Conic(s.p0, s.p1, p, s.w)


def move_node(c: Contour, k: int, p: Point) -> Contour:
    """Déplace le nœud k ; les poignées attachées suivent."""
    segs = list(c.segments)
    i_in, i_out = _seg_in_out(c, k)
    if i_in is not None:
        segs[i_in] = _with_end(segs[i_in], p, True)
    if i_out is not None:
        segs[i_out] = _with_start(segs[i_out], p, True)
    return Contour(segs, c.closed)


def handles(c: Contour) -> list[tuple[int, int, Point]]:
    """Poignées éditables : (segment, numéro 1 ou 2, position)."""
    out = []
    for i, s in enumerate(c.segments):
        if isinstance(s, Cubic):
            out += [(i, 1, s.p1), (i, 2, s.p2)]
        elif isinstance(s, Conic):
            out.append((i, 1, s.p1))
    return out


def move_handle(c: Contour, seg: int, which: int, p: Point) -> Contour:
    segs = list(c.segments)
    s = segs[seg]
    if isinstance(s, Cubic):
        segs[seg] = Cubic(s.p0, p, s.p2, s.p3) if which == 1 else Cubic(s.p0, s.p1, p, s.p3)
    elif isinstance(s, Conic):
        segs[seg] = Conic(s.p0, p, s.p2, s.w)
    return Contour(segs, c.closed)


# --- points hors courbe (poignées) -----------------------------------------------------------
def handle_node(c: Contour, seg: int, which: int) -> int | None:
    """Nœud auquel une poignée de cubique est attachée (celui qu'elle suit
    quand il bouge) ; None pour le contrôle d'une conique (au milieu)."""
    s = c.segments[seg]
    if not isinstance(s, Cubic):
        return None
    a, b = segment_nodes(c, seg)
    return a if which == 1 else b


def handle_point(c: Contour, seg: int, which: int) -> Point:
    s = c.segments[seg]
    return s.p1 if which == 1 else s.p2


def is_smooth(c: Contour, k: int, tol_deg: float = 2.0) -> bool:
    """Point continu (tangentes alignées) ; False aux bouts d'un contour ouvert."""
    i_in, i_out = _seg_in_out(c, k)
    if i_in is None or i_out is None:
        return False
    a, b = _end_dir(c.segments[i_in]), _start_dir(c.segments[i_out])
    na, nb = math.hypot(*a), math.hypot(*b)
    if na < 1e-12 or nb < 1e-12:
        return False
    cos = (a[0] * b[0] + a[1] * b[1]) / (na * nb)
    return cos >= math.cos(math.radians(tol_deg))


def node_to_off(c: Contour, k: int) -> Contour:
    """Point en courbe → hors courbe (TypeEdit : attribut « Hors courbe ») :
    les deux segments autour du nœud n'en font plus qu'un, qui ne passe plus
    par lui ; deux droites donnent une courbe dont il est le point de
    contrôle. Sans effet aux bouts d'un contour ouvert."""
    i_in, i_out = _seg_in_out(c, k)
    if i_in is None or i_out is None or len(c.segments) < 2:
        return c
    a, b = c.segments[i_in], c.segments[i_out]
    p = node_point(c, k)
    if isinstance(a, Line) and isinstance(b, Line):
        new = Conic(a.p0, p, b.p1, 1.0)
    else:
        ha = a.p1 if isinstance(a, (Cubic, Conic)) else p
        hb = b.p2 if isinstance(b, Cubic) else (b.p1 if isinstance(b, Conic) else p)
        new = Cubic(a.start, ha, hb, b.end)
    segs = list(c.segments)
    if i_out == i_in + 1:
        segs[i_in:i_out + 1] = [new]
        return Contour(segs, c.closed)
    return Contour(segs[1:len(segs) - 1] + [new], c.closed)          # à cheval sur le départ


def handle_to_on(c: Contour, seg: int, which: int) -> Contour:
    """Point hors courbe → en courbe : le tracé passe par lui (le segment est
    coupé en deux à cet endroit)."""
    s = c.segments[seg]
    if isinstance(s, Conic):
        parts = [Line(s.p0, s.p1), Line(s.p1, s.p2)]
    elif isinstance(s, Cubic):
        parts = ([Line(s.p0, s.p1), Conic(s.p1, s.p2, s.p3, 1.0)] if which == 1 else
                 [Conic(s.p0, s.p1, s.p2, 1.0), Line(s.p2, s.p3)])
    else:
        return c
    segs = list(c.segments)
    segs[seg:seg + 1] = parts
    return Contour(segs, c.closed)


def remove_handles(c: Contour, hs) -> Contour:
    """Supprime des points hors courbe : une conique devient droite ; une
    cubique perd la poignée (conique), ou les deux (droite)."""
    by_seg: dict[int, set[int]] = {}
    for seg, which in hs:
        by_seg.setdefault(seg, set()).add(which)
    segs = list(c.segments)
    for i, ws in by_seg.items():
        s = segs[i]
        if isinstance(s, Conic) or (isinstance(s, Cubic) and ws >= {1, 2}):
            segs[i] = Line(s.start, s.end)
        elif isinstance(s, Cubic):
            segs[i] = Conic(s.p0, s.p2, s.p3, 1.0) if 1 in ws else Conic(s.p0, s.p1, s.p3, 1.0)
    return Contour(segs, c.closed)


def split_segment(s: Segment, t: float) -> tuple[Segment, Segment]:
    """Coupe un segment au paramètre t (exact pour les trois sortes)."""
    if isinstance(s, Line):
        m = lerp(s.p0, s.p1, t)
        return Line(s.p0, m), Line(m, s.p1)
    if isinstance(s, Cubic):
        p01 = lerp(s.p0, s.p1, t)
        p12 = lerp(s.p1, s.p2, t)
        p23 = lerp(s.p2, s.p3, t)
        a = lerp(p01, p12, t)
        b = lerp(p12, p23, t)
        m = lerp(a, b, t)
        return Cubic(s.p0, p01, a, m), Cubic(m, b, p23, s.p3)
    # conique : de Casteljau en coordonnées homogènes
    w = s.w
    P0 = (s.p0[0], s.p0[1], 1.0)
    P1 = (s.p1[0] * w, s.p1[1] * w, w)
    P2 = (s.p2[0], s.p2[1], 1.0)
    L = lambda a, b: tuple(a[i] + (b[i] - a[i]) * t for i in range(3))
    A = L(P0, P1)
    B = L(P1, P2)
    M = L(A, B)
    cart = lambda q: (q[0] / q[2], q[1] / q[2])
    # renormalisation : poids extrêmes ramenés à 1
    wa = A[2] / math.sqrt(P0[2] * M[2])
    wb = B[2] / math.sqrt(M[2] * P2[2])
    m = cart(M)
    return Conic(s.p0, cart(A), m, wa), Conic(m, cart(B), s.p2, wb)


def insert_node(c: Contour, seg: int, t: float) -> Contour:
    segs = list(c.segments)
    a, b = split_segment(segs[seg], t)
    segs[seg:seg + 1] = [a, b]
    return Contour(segs, c.closed)


def delete_node(c: Contour, k: int) -> Contour:
    """Supprime le nœud k : les deux segments voisins n'en font plus qu'un
    (droite si les deux étaient droits, Bézier sinon)."""
    segs = list(c.segments)
    n = len(segs)
    if c.closed:
        if n <= 2:
            return c
        i_in, i_out = k, (k + 1) % n
    else:
        if n <= 1:
            return c
        if k == 0:
            return Contour(segs[1:], False)
        if k == n:
            return Contour(segs[:-1], False)
        i_in, i_out = k - 1, k
    a, b = segs[i_in], segs[i_out]
    if isinstance(a, Line) and isinstance(b, Line):
        merged: Segment = Line(a.start, b.end)
    else:
        h1 = a.p1 if not isinstance(a, Line) else lerp(a.start, a.end, 1 / 3)
        h2 = (b.p2 if isinstance(b, Cubic) else b.p1) if not isinstance(b, Line) else lerp(b.start, b.end, 2 / 3)
        merged = Cubic(a.start, h1, h2, b.end)
    if c.closed and i_out == 0:
        segs = [merged] + segs[1:-1]
    else:
        segs[i_in:i_in + 2] = [merged]
    return Contour(segs, c.closed)


def break_at(c: Contour, k: int) -> list[Contour]:
    """Coupe au nœud k : un contour fermé devient ouvert (départ en k),
    un contour ouvert devient deux contours."""
    segs = list(c.segments)
    if c.closed:
        start = (k + 1) % len(segs)
        return [Contour(segs[start:] + segs[:start], False)]
    if k <= 0 or k >= len(segs):
        return [c]
    return [Contour(segs[:k], False), Contour(segs[k:], False)]


def break_many(c: Contour, ks) -> list[Contour]:
    """Coupe à plusieurs nœuds : le contour s'ouvre à chacun."""
    ks = sorted(set(ks))
    if not ks:
        return [c]
    if c.closed:                                        # ouvert d'abord au premier nœud ; les autres se renumérotent
        c = break_at(c, ks[0])[0]
        ks = [k - ks[0] for k in ks[1:]]
    segs = list(c.segments)
    out, prev = [], 0
    for k in ks:
        if 0 < k < len(segs):
            out.append(Contour(segs[prev:k], False))
            prev = k
    out.append(Contour(segs[prev:], False))
    return out


def set_start(c: Contour, k: int) -> Contour:
    """Contour fermé dont le départ passe au nœud k (même forme, même
    sens). Un écart de fermeture est d'abord comblé par une droite."""
    if not c.closed or not c.segments:
        return c
    segs = list(c.segments)
    if dist(segs[-1].end, segs[0].start) > 1e-9:
        segs.append(Line(segs[-1].end, segs[0].start))
    start = (k + 1) % len(segs)
    return Contour(segs[start:] + segs[:start], True)


def join(a: Contour, b: Contour, tol: float = 1e-6) -> Contour | None:
    """Raccorde deux contours ouverts par leurs extrémités les plus proches
    (une droite est ajoutée si elles ne se touchent pas)."""
    if a.closed or b.closed or not a.segments or not b.segments:
        return None
    from .geom import Contour as C
    options = [
        (dist(a.end, b.start), a, b),
        (dist(a.end, b.end), a, b.reversed()),
        (dist(a.start, b.end), b, a),
        (dist(a.start, b.start), a.reversed(), b),
    ]
    d, x, y = min(options, key=lambda o: o[0])
    segs = list(x.segments)
    if d > tol:
        segs.append(Line(x.end, y.start))
    segs += list(y.segments)
    return C(segs, False)


def nearest_on_segment(s: Segment, p: Point, steps: int = 64) -> tuple[float, float]:
    """(t, distance) du point de `s` le plus proche de p (recherche puis
    raffinement)."""
    best_t, best_d = 0.0, float('inf')
    for i in range(steps + 1):
        t = i / steps
        d = dist(s.point(t), p)
        if d < best_d:
            best_t, best_d = t, d
    lo, hi = max(0.0, best_t - 1 / steps), min(1.0, best_t + 1 / steps)
    for _ in range(40):
        m1, m2 = lo + (hi - lo) / 3, hi - (hi - lo) / 3
        if dist(s.point(m1), p) < dist(s.point(m2), p):
            hi = m2
        else:
            lo = m1
    t = (lo + hi) / 2
    return t, dist(s.point(t), p)


# --- transformation des segments, nature des nœuds, alignements -------------------

def segment_nodes(c: Contour, i: int) -> tuple[int, int]:
    """Nœuds de départ et d'arrivée du segment i."""
    n = len(c.segments)
    return ((i - 1) % n, i) if c.closed else (i, i + 1)


def segments_between(c: Contour, ks: set[int]) -> list[int]:
    """Segments concernés par une sélection de nœuds : ceux dont les deux
    nœuds sont sélectionnés ; avec un seul nœud, le segment qui en part
    (ou, au bout d'un contour ouvert, celui qui y arrive)."""
    both = [i for i in range(len(c.segments)) if set(segment_nodes(c, i)) <= ks]
    if both or len(ks) != 1:
        return both
    k = next(iter(ks))
    i_in, i_out = _seg_in_out(c, k)
    return [i_out] if i_out is not None else ([i_in] if i_in is not None else [])


def _as_cubic(s: Segment) -> Cubic:
    if isinstance(s, Cubic):
        return s
    if isinstance(s, Line):
        a, b = s.p0, s.p1
        return Cubic(a, lerp(a, b, 1 / 3), lerp(a, b, 2 / 3), b)
    if abs(s.w - 1) < 1e-12:                      # quadratique : élévation de degré exacte
        return Cubic(s.p0, lerp(s.p0, s.p1, 2 / 3), lerp(s.p2, s.p1, 2 / 3), s.p2)
    return s._cubic_guess()                      # arc : poignées le long des tangentes


def to_lines(c: Contour, segs: list[int]) -> Contour:
    """Segments → droites (mêmes extrémités)."""
    out = list(c.segments)
    for i in segs:
        out[i] = Line(out[i].start, out[i].end)
    return Contour(out, c.closed)


def to_curves(c: Contour, segs: list[int]) -> Contour:
    """Segments → courbes de Bézier modifiables (droites : poignées au tiers ;
    arcs : cubique la plus proche)."""
    out = list(c.segments)
    for i in segs:
        out[i] = _as_cubic(out[i])
    return Contour(out, c.closed)


def smooth_node(c: Contour, k: int, symmetric: bool = False) -> Contour:
    """Nœud lisse (poignées alignées) ou symétrique (alignées et de même
    longueur) ; les segments voisins deviennent des courbes au besoin."""
    i_in, i_out = _seg_in_out(c, k)
    if i_in is None or i_out is None:
        return c
    segs = list(c.segments)
    a, b = _as_cubic(segs[i_in]), _as_cubic(segs[i_out])
    p = node_point(c, k)
    u = (p[0] - a.p2[0], p[1] - a.p2[1])
    v = (b.p1[0] - p[0], b.p1[1] - p[1])
    lu, lv = math.hypot(*u), math.hypot(*v)
    if lu < 1e-12:
        lu = dist(a.p0, p) / 3
        u = (p[0] - a.p0[0], p[1] - a.p0[1])
    if lv < 1e-12:
        lv = dist(p, b.p3) / 3
        v = (b.p3[0] - p[0], b.p3[1] - p[1])
    nu, nv = math.hypot(*u) or 1.0, math.hypot(*v) or 1.0
    dx, dy = u[0] / nu + v[0] / nv, u[1] / nu + v[1] / nv
    nd = math.hypot(dx, dy)
    if nd < 1e-12:                                 # demi-tour : perpendiculaire
        dx, dy, nd = -u[1] / nu, u[0] / nu, 1.0
    dx, dy = dx / nd, dy / nd
    if symmetric:
        lu = lv = (lu + lv) / 2
    segs[i_in] = Cubic(a.p0, a.p1, (p[0] - dx * lu, p[1] - dy * lu), p)
    segs[i_out] = Cubic(p, (p[0] + dx * lv, p[1] + dy * lv), b.p2, b.p3)
    return Contour(segs, c.closed)


def align_nodes(contours: list[Contour], sel: set[tuple[int, int]], axis: str,
                first: tuple[int, int] | None = None) -> list[Contour]:
    """Aligne les nœuds sélectionnés (contour, nœud) : axis 'h' → même y
    (alignés horizontalement), 'v' → même x ; 'both' → tous au même point
    (moyenne, comme Average). La valeur est celle du nœud `first` s'il est de
    la sélection (TypeEdit : le premier sélectionné), sinon leur moyenne."""
    pts = [node_point(contours[ci], k) for ci, k in sel]
    if len(pts) < 2:
        return list(contours)
    if first is not None and first in sel and axis != 'both':
        mx, my = node_point(contours[first[0]], first[1])
    else:
        mx = sum(q[0] for q in pts) / len(pts)
        my = sum(q[1] for q in pts) / len(pts)
    out = list(contours)
    for ci, k in sorted(sel):
        q = node_point(out[ci], k)
        out[ci] = move_node(out[ci], k, (q[0], my) if axis == 'h' else (mx, q[1]) if axis == 'v' else (mx, my))
    return out


# --- commandes du Mode Point de TypeEdit 13 -------------------------------------------
def refine(c: Contour) -> Contour:
    """« Affiner la courbe » : un nouveau point au milieu de chaque segment
    (coupe exacte : le tracé ne change pas)."""
    out: list[Segment] = []
    for s in c.segments:
        out.extend(split_segment(s, 0.5))
    return Contour(out, c.closed)


def portion(c: Contour, a: int, b: int, other: bool = False) -> list[int]:
    """Segments entre les nœuds a et b, dans l'ordre du contour. Ouvert :
    ceux qui les séparent. Fermé : la portion la plus courte (`other` :
    l'autre, comme la touche Tab de TypeEdit)."""
    n = len(c.segments)
    if a == b or not n:
        return []
    if not c.closed:
        a, b = min(a, b), max(a, b)
        return list(range(a, b))
    fwd = [(a + 1 + i) % n for i in range((b - a) % n)]          # de a vers b
    back = [(b + 1 + i) % n for i in range((a - b) % n)]         # de b vers a
    la = sum(c.segments[i].length() for i in fwd)
    lb = sum(c.segments[i].length() for i in back)
    short, long_ = (fwd, back) if la <= lb else (back, fwd)
    return long_ if other else short


def _replace(c: Contour, idx: list[int], new: list[Segment]) -> Contour:
    """Remplace la suite de segments `idx` (consécutifs, éventuellement à
    cheval sur le départ d'un contour fermé) par `new`."""
    segs = list(c.segments)
    if idx == list(range(idx[0], idx[0] + len(idx))):
        segs[idx[0]:idx[0] + len(idx)] = new
        return Contour(segs, c.closed)
    # à cheval sur le départ : le contour repart de la fin de la portion
    keep = [segs[i] for i in range(idx[-1] + 1, idx[0])]
    return Contour(keep + new, c.closed)


def _start_dir(s: Segment) -> tuple[float, float]:
    for q in s.controls()[1:]:
        d = (q[0] - s.start[0], q[1] - s.start[1])
        if math.hypot(*d) > 1e-12:
            return d
    return (0.0, 0.0)


def _end_dir(s: Segment) -> tuple[float, float]:
    for q in reversed(s.controls()[:-1]):
        d = (s.end[0] - q[0], s.end[1] - q[1])
        if math.hypot(*d) > 1e-12:
            return d
    return (0.0, 0.0)


def to_segment(c: Contour, a: int, b: int, other: bool = False) -> Contour:
    """« Transformer en segment » : la portion entre les nœuds a et b
    devient une seule droite."""
    idx = portion(c, a, b, other)
    if not idx:
        return c
    p, q = c.segments[idx[0]].start, c.segments[idx[-1]].end
    return _replace(c, idx, [Line(p, q)])


def to_arc(c: Contour, a: int, b: int, other: bool = False) -> Contour:
    """« Transformer en arc » : la portion entre les nœuds a et b devient
    l'arc de cercle qui passe par ses deux bouts et par son milieu (à mi-
    longueur) ; portion droite (milieu sur la corde) : une droite."""
    from .geom import arc_3points
    idx = portion(c, a, b, other)
    if not idx:
        return c
    pts = []
    for i in idx:
        f = c.segments[i].flatten(0.001) if hasattr(c.segments[i], 'flatten') else [c.segments[i].start,
                                                                                  c.segments[i].end]
        pts.extend(f if not pts else f[1:])
    p, q = c.segments[idx[0]].start, c.segments[idx[-1]].end
    L = sum(math.dist(pts[k], pts[k + 1]) for k in range(len(pts) - 1))
    mid, run = pts[0], 0.0
    for k in range(len(pts) - 1):
        d = math.dist(pts[k], pts[k + 1])
        if run + d >= L / 2 and d > 0:
            t = (L / 2 - run) / d
            mid = (pts[k][0] + (pts[k + 1][0] - pts[k][0]) * t, pts[k][1] + (pts[k + 1][1] - pts[k][1]) * t)
            break
        run += d
    arc = arc_3points(p, mid, q)
    if arc is None or not arc.segments:
        return _replace(c, idx, [Line(p, q)])
    return _replace(c, idx, list(arc.segments))


def to_angle(c: Contour, a: int, b: int, other: bool = False) -> Contour:
    """« Transformer en angle » : la portion entre les nœuds a et b devient
    deux droites qui se rejoignent à l'intersection des tangentes aux deux
    extrémités ; à défaut (tangentes parallèles, divergentes ou sommet trop
    loin), au point de la portion le plus éloigné de la corde. Le sommet
    reste un point modifiable."""
    idx = portion(c, a, b, other)
    if not idx:
        return c
    first, last = c.segments[idx[0]], c.segments[idx[-1]]
    p, q = first.start, last.end
    chord = dist(p, q)
    if chord < 1e-9:
        return c
    (ux, uy), (vx, vy) = _start_dir(first), _end_dir(last)
    apex = None
    det = ux * vy - uy * vx
    if abs(det) > 1e-12 * (math.hypot(ux, uy) * math.hypot(vx, vy) or 1.0):
        # p + s·u = q − t·v  ⇔  s·u + t·v = q − p (Cramer)
        rx, ry = q[0] - p[0], q[1] - p[1]
        s_ = (rx * vy - ry * vx) / det
        t_ = (ux * ry - uy * rx) / det
        nu, nv = math.hypot(ux, uy), math.hypot(vx, vy)
        if s_ > 0 and t_ > 0 and s_ * nu < 4 * chord and t_ * nv < 4 * chord:
            apex = (p[0] + s_ * ux, p[1] + s_ * uy)
    if apex is None:
        best = 0.0
        ex, ey = (q[0] - p[0]) / chord, (q[1] - p[1]) / chord
        for i in idx:
            sg = c.segments[i]
            for k in range(1, 16):
                m = sg.point(k / 16)
                d = abs((m[0] - p[0]) * ey - (m[1] - p[1]) * ex)
                if d > best:
                    best, apex = d, m
            if i != idx[-1]:
                m = sg.end
                d = abs((m[0] - p[0]) * ey - (m[1] - p[1]) * ex)
                if d > best:
                    best, apex = d, m
        if apex is None or best < 1e-9:
            return c                                   # portion droite : déjà un angle plat
    return _replace(c, idx, [Line(p, apex), Line(apex, q)])


# --- projections de points (Mode Point de TypeEdit) -----------------------------------
def _all_segments(c: Contour) -> list[Segment]:
    """Segments du contour, fermeture implicite comprise."""
    segs = list(c.segments)
    if c.closed and segs and dist(segs[-1].end, segs[0].start) > 1e-12:
        segs.append(Line(segs[-1].end, segs[0].start))
    return segs


def _axis_hits(s: Segment, axis: int, target: float, steps: int = 64) -> list[float]:
    """Paramètres t où la coordonnée `axis` du segment vaut `target`
    (droites : exact ; courbes : changements de signe puis dichotomie)."""
    if isinstance(s, Line):
        a, b = s.p0[axis], s.p1[axis]
        if a == b:
            return [] if a != target else [0.0, 1.0]       # segment sur la droite : ses bouts
        t = (target - a) / (b - a)
        return [t] if -1e-12 <= t <= 1 + 1e-12 else []
    f = lambda t: s.point(t)[axis] - target
    out = []
    t0, f0 = 0.0, f(0.0)
    if f0 == 0:
        out.append(0.0)
    for i in range(1, steps + 1):
        t1 = i / steps
        f1 = f(t1)
        if f1 == 0:
            out.append(t1)
        elif f0 * f1 < 0:
            lo, hi, flo = t0, t1, f0
            for _ in range(60):
                m = (lo + hi) / 2
                fm = f(m)
                if (fm < 0) == (flo < 0):
                    lo, flo = m, fm
                else:
                    hi = m
            out.append((lo + hi) / 2)
        t0, f0 = t1, f1
    return out


def project_point(ref: Contour, p: Point, kind: str) -> Point | None:
    """Projection du point p sur le contour `ref` : 'v' verticale (même x),
    'h' horizontale (même y), 'perp' orthogonale (point le plus proche). Pour
    'v' / 'h', l'intersection la plus proche de p ; None s'il n'y en a pas."""
    segs = _all_segments(ref)
    if not segs:
        return None
    if kind == 'perp':
        best = None
        for s in segs:
            t, d = nearest_on_segment(s, p)
            if best is None or d < best[0]:
                best = (d, s.point(t))
        return best[1]
    axis = 0 if kind == 'v' else 1
    other = 1 - axis
    best = None
    for s in segs:
        if isinstance(s, Line) and s.p0[axis] == s.p1[axis] == p[axis]:
            lo, hi = sorted((s.p0[other], s.p1[other]))
            v = min(max(p[other], lo), hi)                 # segment sur la droite : point le plus proche
            q = [0.0, 0.0]
            q[axis], q[other] = p[axis], v
            cands = [tuple(q)]
        else:
            cands = []
            for t in _axis_hits(s, axis, p[axis]):
                q = list(s.point(min(max(t, 0.0), 1.0)))
                q[axis] = p[axis]                          # exactement sur la droite de projection
                cands.append(tuple(q))
        for q in cands:
            d = abs(q[other] - p[other])
            if best is None or d < best[0]:
                best = (d, q)
    return best[1] if best else None


def project_on_guide(axis: str, value: float, p: Point, kind: str) -> Point | None:
    """Projection sur un guide ('h' : y = value ; 'v' : x = value). Une
    projection parallèle au guide n'existe pas (None)."""
    if axis == 'h':
        return None if kind == 'h' else (p[0], value)
    return None if kind == 'v' else (value, p[1])


def project_nodes(contours: list[Contour], sel, fn) -> tuple[list[Contour], int]:
    """Nœuds sélectionnés (contour, nœud) déplacés sur fn(point) (None :
    laissé en place). Rend (contours, nombre de nœuds projetés)."""
    cs = list(contours)
    n = 0
    for ci, k in sorted(sel):
        if ci >= len(cs) or k >= node_count(cs[ci]):
            continue
        p = node_point(cs[ci], k)
        q = fn(p)
        if q is None:
            continue
        if dist(p, q) > 0:
            cs[ci] = move_node(cs[ci], k, q)
        n += 1
    return cs, n
