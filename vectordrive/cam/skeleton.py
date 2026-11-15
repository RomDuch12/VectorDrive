"""Squelette droit d'une forme : ce que tracent ses sommets quand tous ses côtés avancent vers l'intérieur à la même vitesse. C'est le toit que
donne la pente d'un outil conique sur une lettre : les arêtes vives d'une lettre prismatique sont sur ce squelette.

Calcul par événements, sur le front d'avance : un côté qui disparaît (événement de côté), un sommet rentrant qui atteint un côté en face
(événement de partage). Les cas dégénérés sont courants sur des lettres (côtés parallèles, sommets qui se rencontrent) : on déplace très peu les
points (un centième de micron) pour qu'ils n'arrivent plus."""
from __future__ import annotations

import heapq
import math
import random

import numpy as np
import shapely


class SkeletonError(Exception):
    """Le calcul n'a pas abouti sur cette forme."""


def _clean_ring(coords, ccw: bool, min_len: float = 3e-4) -> list:
    """L'anneau dans le sens voulu, sans ses côtés trop courts pour survivre au déplacement des points, ni ses sommets alignés."""
    pts = []
    for c in coords:
        p = (float(c[0]), float(c[1]))
        if not pts or math.dist(p, pts[-1]) > min_len:
            pts.append(p)
    while len(pts) > 1 and math.dist(pts[0], pts[-1]) <= min_len:
        pts.pop()
    area = sum(pts[i - 1][0] * pts[i][1] - pts[i][0] * pts[i - 1][1] for i in range(len(pts))) if len(pts) > 2 else 0.0
    if (area > 0) != ccw:
        pts.reverse()
    out = []                                              # sans les sommets alignés : ils ne font pas d'arête
    n = len(pts)
    for i in range(n):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        ux, uy, vx, vy = b[0] - a[0], b[1] - a[1], c[0] - b[0], c[1] - b[1]
        cross = ux * vy - uy * vx
        if abs(cross) > 1e-10 * math.hypot(ux, uy) * math.hypot(vx, vy) or ux * vx + uy * vy < 0:
            out.append(b)
    return out


def straight_skeleton(poly, jitter: float = 1e-5, seed: int = 1, reach: float = 3.0) -> list:
    """Les arcs du squelette de ce polygone (avec trous) : (x0, y0, t0, x1, y1, t1, tournant en degrés au sommet qui l'a tracé, anneau, sommet).
    t : la distance parcourue par les côtés. Anneau 0 : l'extérieur, parcouru dans le sens direct ; les suivants : les trous, en sens horaire
    (la matière à gauche) ; anneau et sommet valent −1 pour un arc né à l'intérieur. `reach` : un sommet rentrant ne cherche que les côtés dont
    il atteint la droite à moins de `reach` fois le temps écoulé au-delà de leurs bouts : un côté ne s'allonge plus vite que près d'un coin
    rentrant très aigu (3 : un coin à 37° d'ouverture). C'est ce qui rend le calcul rapide sur une forme à centaines de trous."""
    rng = random.Random(seed)
    AX: list = []
    AY: list = []
    UX: list = []
    UY: list = []
    LEN: list = []
    X: list = []
    Y: list = []
    T: list = []
    VX: list = []
    VY: list = []
    PREV: list = []
    NEXT: list = []
    EL: list = []
    ER: list = []
    ALIVE: list = []
    TURN: list = []
    REFLEX: list = []
    SRC: list = []
    SEG: list = []
    arcs: list = []
    heap: list = []
    seq = [0]
    now = [0.0]

    def new(x, y, t, el, er, prev, nxt, src=(-1, -1, 0.0, 0.0)) -> int:
        sx, sy = -UY[el] - UY[er], UX[el] + UX[er]
        s2 = sx * sx + sy * sy
        if s2 < 1e-22:
            raise SkeletonError('côtés opposés')
        cross = UX[el] * UY[er] - UY[el] * UX[er]
        dot = UX[el] * UX[er] + UY[el] * UY[er]
        i = len(X)
        X.append(x)
        Y.append(y)
        T.append(t)
        VX.append(2 * sx / s2)
        VY.append(2 * sy / s2)
        PREV.append(prev)
        NEXT.append(nxt)
        EL.append(el)
        ER.append(er)
        ALIVE.append(True)
        TURN.append(abs(math.degrees(math.atan2(cross, dot))))
        REFLEX.append(cross < -1e-12)
        SRC.append(src)
        SEG[er].add(i)
        return i

    rings = [poly.exterior, *poly.interiors]
    firsts = []
    for r, ring in enumerate(rings):
        pts = _clean_ring(ring.coords, r == 0)
        if len(pts) < 3:
            continue
        moved = [(p[0] + rng.uniform(-jitter, jitter), p[1] + rng.uniform(-jitter, jitter)) for p in pts]
        e0, n = len(AX), len(pts)
        for i in range(n):
            a, b = moved[i], moved[(i + 1) % n]
            L = math.dist(a, b)
            LEN.append(L)
            AX.append(a[0])
            AY.append(a[1])
            UX.append((b[0] - a[0]) / L)
            UY.append((b[1] - a[1]) / L)
            SEG.append(set())
        v0 = len(X)
        for i in range(n):
            new(moved[i][0], moved[i][1], 0.0, e0 + (i - 1) % n, e0 + i, v0 + (i - 1) % n, v0 + (i + 1) % n, (r, i, pts[i][0], pts[i][1]))
        firsts.append((v0, n))
    if not X:
        return []
    ax, ay = np.array(AX), np.array(AY)
    ux, uy = np.array(UX), np.array(UY)
    nx, ny = -uy, ux
    lengths = np.array(LEN)
    CAND: dict = {}
    SLICE: dict = {}
    use_tree = math.isfinite(reach) and len(AX) > 3000
    edge_tree = shapely.STRtree(shapely.linestrings(np.stack([np.stack([ax, ay], axis=1), np.stack([ax + ux * lengths, ay + uy * lengths], axis=1)], axis=1))) if use_tree else None
    xmin, ymin, xmax, ymax = poly.bounds
    last_time = math.hypot(xmax - xmin, ymax - ymin) + 1.0

    def at(i, t):
        return X[i] + VX[i] * (t - T[i]), Y[i] + VY[i] * (t - T[i])

    def kill(i, qx, qy, t) -> None:
        ALIVE[i] = False
        SEG[ER[i]].discard(i)
        r, v, sx, sy = SRC[i]
        x0, y0 = (sx, sy) if r >= 0 else (X[i], Y[i])
        arcs.append((x0, y0, T[i], qx, qy, t, TURN[i], r, v))

    def push_edge(i) -> None:
        j, e = NEXT[i], ER[i]
        wi, wj = VX[i] * UX[e] + VY[i] * UY[e], VX[j] * UX[e] + VY[j] * UY[e]
        si = (X[i] - AX[e]) * UX[e] + (Y[i] - AY[e]) * UY[e] - wi * T[i]
        sj = (X[j] - AX[e]) * UX[e] + (Y[j] - AY[e]) * UY[e] - wj * T[j]
        rate = wi - wj
        if rate > 1e-12:
            t = (sj - si) / rate
        elif (sj + wj * now[0]) - (si + wi * now[0]) < 1e-9:
            t = now[0]
        else:
            return
        seq[0] += 1
        heapq.heappush(heap, (max(t, now[0]), 0, seq[0], i, j))

    def fill_candidates(i, after) -> None:
        """Les côtés que ce sommet rentrant peut atteindre dans la prochaine tranche de temps, les plus tôt d'abord : il meurt en général très vite.
        Sur une grande forme, on ne regarde que près de lui ; la tranche quadruple à chaque fois."""
        t0 = T[i]
        x0, y0 = X[i] - VX[i] * t0, Y[i] - VY[i] * t0
        if use_tree:
            begin = max(t0, after)
            width = SLICE.get(i, 1.0)
            SLICE[i] = 4 * width
            end = begin + width
            x1, y1, x2, y2 = x0 + VX[i] * begin, y0 + VY[i] * begin, x0 + VX[i] * end, y0 + VY[i] * end
            pad = (reach + 1) * end + 1e-3
            box = shapely.box(min(x1, x2) - pad, min(y1, y2) - pad, max(x1, x2) + pad, max(y1, y2) + pad)
            idx = edge_tree.query(box)
        else:
            end = math.inf
            idx = np.arange(len(AX))
        idx = idx[(idx != EL[i]) & (idx != ER[i])]
        ex, ey, fx, fy = ax[idx], ay[idx], nx[idx], ny[idx]
        d0 = (x0 - ex) * fx + (y0 - ey) * fy
        rate = VX[i] * fx + VY[i] * fy - 1.0
        with np.errstate(divide='ignore', invalid='ignore'):
            ts = -d0 / rate
        front = d0 + t0 * rate                            # sa distance à la droite du côté, à sa naissance
        ok = (rate < -1e-12) & (front > -1e-9) & (ts >= t0 - 1e-12) & (ts > after) & (ts <= end)
        if math.isfinite(reach):
            with np.errstate(invalid='ignore'):
                along = (x0 + VX[i] * ts - ex) * ux[idx] + (y0 + VY[i] * ts - ey) * uy[idx]
                ok &= (along >= -reach * ts - 1e-6) & (along <= lengths[idx] + reach * ts + 1e-6)
        ts, idx = ts[ok], idx[ok]
        order = np.argsort(ts)
        CAND[i] = [ts[order].tolist(), idx[order].tolist(), 0, end]

    def push_split(i) -> None:
        c = CAND.get(i)
        if c is None:
            fill_candidates(i, -math.inf)
            c = CAND[i]
        seq[0] += 1
        if c[2] >= len(c[0]):
            if c[3] < last_time:                          # la tranche est épuisée : la suivante, à son heure
                heapq.heappush(heap, (max(c[3], now[0]), 2, seq[0], i, -1))
            return
        heapq.heappush(heap, (max(c[0][c[2]], now[0]), 1, seq[0], i, c[1][c[2]]))
        c[2] += 1

    def close_two(a, b, t) -> None:
        ax_, ay_ = at(a, t)
        bx_, by_ = at(b, t)
        kill(a, ax_, ay_, t)
        kill(b, bx_, by_, t)
        if math.hypot(ax_ - bx_, ay_ - by_) > 1e-9:
            arcs.append((ax_, ay_, t, bx_, by_, t, 180.0, -1, -1))

    def start_vertex(i) -> None:
        """Le sommet vient de naître ou de changer de voisins : ses événements."""
        push_edge(PREV[i])
        push_edge(i)
        if REFLEX[i]:
            push_split(i)

    for v0, n in firsts:
        for i in range(v0, v0 + n):
            push_edge(i)
            if REFLEX[i]:
                push_split(i)

    budget = 40 * len(X) + 1000
    pops = 2000 * len(X) + 100000
    stall = 0                                             # des événements qui se suivent sans que le temps avance : un sommet posé sur un côté
    stall_max = len(AX) + 200
    while heap:
        pops -= 1
        if pops < 0:
            raise SkeletonError('trop d\'événements écartés')
        t, kind, _s, i, other = heapq.heappop(heap)
        if not ALIVE[i]:
            continue
        if kind == 2:
            fill_candidates(i, t)
            push_split(i)
            continue
        if kind == 0:
            j = other
            if not ALIVE[j] or NEXT[i] != j:
                continue
            budget -= 1
            if budget < 0:
                raise SkeletonError('trop d\'événements')
            stall = stall + 1 if t - now[0] < 1e-10 else 0
            if stall > stall_max:
                raise SkeletonError('le temps n\'avance plus')
            now[0] = max(now[0], t)
            t = now[0]
            xi, yi = at(i, t)
            xj, yj = at(j, t)
            qx, qy = (xi + xj) / 2, (yi + yj) / 2
            k, l = PREV[i], NEXT[j]
            kill(i, qx, qy, t)
            kill(j, qx, qy, t)
            if k == j:
                continue
            if k == l:
                px, py = at(k, t)
                kill(k, px, py, t)
                if math.hypot(px - qx, py - qy) > 1e-9:
                    arcs.append((px, py, t, qx, qy, t, 180.0, -1, -1))
                continue
            m = new(qx, qy, t, EL[i], ER[j], k, l)
            NEXT[k] = m
            PREV[l] = m
            start_vertex(m)
        else:
            e = other
            qx, qy = at(i, t)
            sq = (qx - AX[e]) * UX[e] + (qy - AY[e]) * UY[e]
            hit = None
            for m in SEG[e]:
                j = NEXT[m]
                if m == i or j == i:
                    continue
                xm, ym = at(m, t)
                xj, yj = at(j, t)
                sm = (xm - AX[e]) * UX[e] + (ym - AY[e]) * UY[e]
                sj = (xj - AX[e]) * UX[e] + (yj - AY[e]) * UY[e]
                if sm - 1e-7 <= sq <= sj + 1e-7:
                    hit = (m, j)
                    break
            if hit is None:
                push_split(i)                             # pas de côté à cet endroit à cet instant : le suivant
                continue
            budget -= 1
            if budget < 0:
                raise SkeletonError('trop d\'événements')
            stall = stall + 1 if t - now[0] < 1e-10 else 0
            if stall > stall_max:
                raise SkeletonError('le temps n\'avance plus')
            now[0] = max(now[0], t)
            t = now[0]
            m, j = hit
            pi, ni, el, er = PREV[i], NEXT[i], EL[i], ER[i]
            kill(i, qx, qy, t)
            a = new(qx, qy, t, el, e, pi, j)
            b = new(qx, qy, t, e, er, m, ni)
            NEXT[pi] = a
            PREV[j] = a
            NEXT[m] = b
            PREV[ni] = b
            for v in (a, b):
                if not ALIVE[v]:
                    continue
                w = NEXT[v]
                if NEXT[w] == v:
                    close_two(v, w, t)
                else:
                    start_vertex(v)
    if any(ALIVE):
        raise SkeletonError('front non refermé')
    return arcs


def _try_arcs(poly, tries: tuple) -> list | None:
    xmin, ymin, xmax, ymax = poly.bounds
    limit = math.hypot(xmax - xmin, ymax - ymin)
    grown = None
    for k, (amp, reach) in enumerate(tries):
        try:
            arcs = straight_skeleton(poly, amp, k + 1, reach)
        except (SkeletonError, ZeroDivisionError):
            continue
        if not arcs:
            return arcs
        a = np.array([(r[3], r[4], r[5]) for r in arcs], dtype=float)
        if grown is None:
            grown = poly.buffer(2e-3, quad_segs=1)
            shapely.prepare(grown)
        if shapely.covers(grown, shapely.points(a[:, 0], a[:, 1])).all() and (a[:, 2] <= limit).all():
            return arcs
    return None


def checked_arcs(poly) -> list | None:
    """Le squelette vérifié : chaque bout d'arc est dans la forme (t peut dépasser la distance au bord : le toit n'est pas la distance).
    Sinon on referme les fentes et on retire les voiles de moins de 2 microns de large (sur un dessin réel, plus fins que le déplacement des points),
    et on déplace autrement les points. None : le calcul n'aboutit pas sur cette forme."""
    arcs = _try_arcs(poly, ((1e-5, 3.0),))
    if arcs is not None:
        return arcs
    opened = poly.buffer(1e-3, join_style='mitre', mitre_limit=20.0).buffer(-2e-3, join_style='mitre', mitre_limit=20.0).buffer(1e-3, join_style='mitre', mitre_limit=20.0)
    out: list = []
    for p in getattr(opened, 'geoms', [opened]):
        if p.geom_type != 'Polygon' or p.is_empty:
            continue
        big = shapely.get_num_coordinates(p) > 3000       # sans le filtre de portée, une grande forme prendrait des dizaines de minutes
        arcs = _try_arcs(p, ((1e-5, 3.0), (3e-5, 12.0)) if big else ((1e-5, 3.0), (3e-5, 12.0), (3e-5, math.inf), (1e-4, math.inf)))
        if arcs is None:
            return None
        out += arcs
    return out


def roof_tours(arcs: list, top: float, min_turn: float, snap: float = 2e-3) -> list:
    """Le trajet qui reprend les arêtes du toit jusqu'à la hauteur `top` (en t) : [[(x, y, t)…]…]. Les arcs d'un tournant de moins de `min_turn`
    ne marquent pas d'arête (les petits côtés d'une courbe). Pour chaque sommet de contour, dans l'ordre : on part du haut de son arête si elle
    va jusqu'au plat, sinon de son pied, et on parcourt tout ce qui y est relié ; un arbre est parcouru aller et retour, comme dans TypeEdit ; ce
    qui contient une boucle s'arrête quand tout est fait."""
    cells: dict = {}
    pos: list = []

    def node(x, y, t) -> int:
        cx, cy = int(math.floor(x / snap)), int(math.floor(y / snap))
        for i in range(cx - 1, cx + 2):
            for j in range(cy - 1, cy + 2):
                for n in cells.get((i, j), ()):
                    if math.hypot(pos[n][0] - x, pos[n][1] - y) <= snap:
                        return n
        pos.append((x, y, t))
        cells.setdefault((cx, cy), []).append(len(pos) - 1)
        return len(pos) - 1

    edges: list = []
    out: dict = {}
    heads: list = []
    for x0, y0, t0, x1, y1, t1, turn, ring, vertex in arcs:
        if turn < min_turn or t0 >= top - 1e-9:
            continue
        if t1 > top:
            f = (top - t0) / (t1 - t0)
            x1, y1, t1 = x0 + (x1 - x0) * f, y0 + (y1 - y0) * f, top
        a, b = node(x0, y0, t0), node(x1, y1, t1)
        if a == b:
            continue
        k = len(edges)
        edges.append((a, b))
        out.setdefault(a, []).append(k)
        out.setdefault(b, []).append(k)
        if ring >= 0:
            heads.append((ring, vertex, a, b))
    heads.sort(key=lambda h: (h[0] == 0, h[0], h[1]))
    done = [False] * len(edges)

    def component(start) -> tuple:
        seen, stack, count, nodes = {start}, [start], set(), 0
        while stack:
            n = stack.pop()
            nodes += 1
            for k in out.get(n, ()):
                if k in count:
                    continue
                count.add(k)
                o = edges[k][1] if edges[k][0] == n else edges[k][0]
                if o not in seen:
                    seen.add(o)
                    stack.append(o)
        return count, nodes

    def tour(start) -> list:
        ks, nodes = component(start)
        tree = len(ks) == nodes - 1
        left = sum(1 for k in ks if not done[k])
        path = [start]
        back: list = []
        cur = start
        while True:
            here = pos[cur]
            came = pos[back[-1]] if back else None
            choices = [k for k in out.get(cur, ()) if not done[k]]
            if choices:
                def rank(k):                               # à droite d'abord, comme un tour de face
                    o = pos[edges[k][1] if edges[k][0] == cur else edges[k][0]]
                    a = math.atan2(o[1] - here[1], o[0] - here[0])
                    ref = math.atan2(came[1] - here[1], came[0] - here[0]) if came else 0.0
                    return (a - ref) % (2 * math.pi)
                k = min(choices, key=rank)
                done[k] = True
                left -= 1
                back.append(cur)
                cur = edges[k][1] if edges[k][0] == cur else edges[k][0]
                path.append(cur)
                if left == 0 and not tree:
                    break
            elif back:
                cur = back.pop()
                path.append(cur)
            else:
                break
        return [pos[n] for n in path]

    tours = []
    for _r, _v, a, b in heads:
        k = next((k for k in out.get(a, ()) if edges[k] == (a, b) or edges[k] == (b, a)), None)
        if k is None or done[k]:
            continue
        start = b if pos[b][2] >= top - 1e-9 else a
        tours.append(tour(start))
    for k, (a, b) in enumerate(edges):
        if not done[k]:
            leaf = a if len(out[a]) == 1 else b
            tours.append(tour(leaf))
    return [t for t in tours if len(t) > 1]
