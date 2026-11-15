"""La Finition telle que relevée dans TE13 (cônes, bords et tirés d'angle).

À chaque passe, l'outil suit chaque contour du dessin à la distance où le cône touche la surface. Là où il n'y a pas la place, il passe sur
l'axe médian de la forme, à la profondeur que la largeur permet, puis revient. Dans chaque angle saillant de la forme, il monte au sommet
le long de la bissectrice et redescend. Le tout fait un seul trajet par contour : l'outil garde la paroi du même côté et prend la première
branche qu'il rencontre de ce côté, comme on suit un mur de la main. Le trajet du contour est le tour d'une face du graphe plan que font
les anneaux décalés, les axes et les tirés d'angle.
"""
from __future__ import annotations

import math

from . import strategies as S
from ..core import progress
from .model import Move


def _rdp3(pts: list, eps: float) -> list:
    """Polyligne 3D allégée (Douglas-Peucker), bouts conservés. Une boucle est d'abord coupée en son point le plus loin du départ."""
    if len(pts) < 3:
        return list(pts)
    if math.dist(pts[0], pts[-1]) < 1e-12:
        far = max(range(len(pts)), key=lambda i: math.dist(pts[i], pts[0]))
        return _rdp3(pts[:far + 1], eps)[:-1] + _rdp3(pts[far:], eps)
    keep = {0, len(pts) - 1}
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        if b <= a + 1:
            continue
        ax, ay, az = pts[a]
        ux, uy, uz = pts[b][0] - ax, pts[b][1] - ay, pts[b][2] - az
        uu = ux * ux + uy * uy + uz * uz
        best, at = -1.0, None
        for i in range(a + 1, b):
            vx, vy, vz = pts[i][0] - ax, pts[i][1] - ay, pts[i][2] - az
            t = (vx * ux + vy * uy + vz * uz) / uu if uu > 1e-18 else 0.0
            t = max(0.0, min(1.0, t))
            d = math.dist((vx, vy, vz), (t * ux, t * uy, t * uz))
            if d > best:
                best, at = d, i
        if best > eps:
            keep.add(at)
            stack += [(a, at), (at, b)]
    return [pts[i] for i in sorted(keep)]


class _Graph:
    """Graphe plan des chemins d'une passe. Chaque arête donne deux demi-arêtes : [départ, arrivée, chemin 3D, jumelle, sorte]. La sorte vaut
    'anneau' (le sens de l'anneau décalé : la paroi est du bon côté), 'dos' (l'autre sens : pas de paroi de ce côté), 'axe' ou 'tire'."""

    def __init__(self, wall_right: bool, snap: float):
        self.wall_right = wall_right
        self.cell = max(snap, 1e-3)
        self.pos: list = []
        self.cells: dict = {}
        self.he: list = []
        self.out: dict = {}

    def near(self, p, radius: float):
        """Le nœud le plus près de `p`, à moins de `radius` (au plus la taille d'une case de la grille)."""
        cx, cy = int(math.floor(p[0] / self.cell)), int(math.floor(p[1] / self.cell))
        best, bd = None, radius
        for i in range(cx - 1, cx + 2):
            for j in range(cy - 1, cy + 2):
                for n in self.cells.get((i, j), ()):
                    d = math.dist(self.pos[n][:2], p[:2])
                    if d <= bd:
                        best, bd = n, d
        return best

    def node(self, p, radius: float = 1e-4) -> int:
        n = self.near(p, radius)
        if n is None:
            n = len(self.pos)
            self.pos.append(tuple(p))
            self.cells.setdefault((int(math.floor(p[0] / self.cell)), int(math.floor(p[1] / self.cell))), []).append(n)
        return n

    def edge(self, path: list, kind: str, radius: float = 1e-4, radius_start=None) -> bool:
        u, v = self.node(path[0], radius if radius_start is None else radius_start), self.node(path[-1], radius)
        mid = path[1:-1]
        if u == v and not mid:
            return False
        fwd = [self.pos[u], *mid, self.pos[v]]
        k = len(self.he)
        back_kind = 'dos' if kind == 'anneau' else kind
        self.he.append([u, v, fwd, k + 1, kind])
        self.he.append([v, u, fwd[::-1], k, back_kind])
        self.out.setdefault(u, []).append(k)
        self.out.setdefault(v, []).append(k + 1)
        return True

    def chain(self, path: list, kind: str, radius: float = 1e-4) -> None:
        """Chaque segment de `path` en arête, comme `edge` sur chaque paire de points qui se suivent, mais chaque sommet n'est cherché
        qu'une fois (même graphe : entre deux recherches du même point, aucun nœud n'est créé)."""
        ids = [self.node(p, radius) for p in path]
        back_kind = 'dos' if kind == 'anneau' else kind
        for u, v in zip(ids, ids[1:]):
            if u == v:
                continue
            k = len(self.he)
            fwd = [self.pos[u], self.pos[v]]
            self.he.append([u, v, fwd, k + 1, kind])
            self.he.append([v, u, fwd[::-1], k, back_kind])
            self.out.setdefault(u, []).append(k)
            self.out.setdefault(v, []).append(k + 1)

    def move(self, n: int, p) -> None:
        """Le nœud n, un bout d'axe approché, va au point exact p."""
        self.pos[n] = tuple(p)
        for h in self.out.get(n, ()):
            e = self.he[h]
            e[2][0] = self.pos[n]
            self.he[e[3]][2][-1] = self.pos[n]

    @staticmethod
    def _heading(path: list) -> float:
        for p in path[1:]:
            dx, dy = p[0] - path[0][0], p[1] - path[0][1]
            if dx * dx + dy * dy > 1e-16:
                return math.atan2(dy, dx)
        return 0.0

    def faces(self) -> list:
        """Les tours de face (listes de demi-arêtes) qui longent une paroi."""
        rank: dict = {}
        turn: dict = {}
        for n, hs in self.out.items():
            turn[n] = sorted(hs, key=lambda h: self._heading(self.he[h][2]))
            for i, h in enumerate(turn[n]):
                rank[h] = i
        seen: set = set()
        out = []
        for h0, e in enumerate(self.he):
            if h0 in seen or e[4] == 'dos':
                continue
            cycle = []
            h = h0
            while h not in seen:
                seen.add(h)
                cycle.append(h)
                v, twin = self.he[h][1], self.he[h][3]
                ring = turn[v]
                h = ring[(rank[twin] + (1 if self.wall_right else -1)) % len(ring)]
            out.append(cycle)
        return out

    def flat(self, cycle: list) -> list:
        """Le chemin 3D d'un tour : le dernier point rejoint le premier."""
        path = [self.he[cycle[0]][2][0]]
        for h in cycle:
            path += self.he[h][2][1:]
        return path


def _walls_index(reg):
    """Index des segments de parois de la région (STRtree) : la distance à une paroi ne parcourt plus tout le dessin."""
    import numpy as np
    import shapely
    segs = []
    for poly in getattr(reg, 'geoms', [reg]):
        if poly.geom_type != 'Polygon' or poly.is_empty:
            continue
        for ring in [poly.exterior] + list(poly.interiors):
            c = np.asarray(ring.coords)[:, :2]
            segs.append(np.stack([c[:-1], c[1:]], axis=1))
    return shapely.STRtree(shapely.linestrings(np.concatenate(segs))) if segs else None


def _overlay(fn: str, a, b):
    """`a.difference(b)` ou `a.intersection(b)`, sans lever d'exception sur une géométrie douteuse : un décalage de contours réels peut rendre
    une géométrie que GEOS refuse (« side location conflict »). On la répare et on repasse sur une grille très fine (1/1000 de micron près,
    sans effet sur le parcours)."""
    import shapely
    try:
        return getattr(a, fn)(b)
    except shapely.errors.GEOSException:
        return getattr(shapely, fn)(shapely.make_valid(a), shapely.make_valid(b), grid_size=1e-6)


def _axis_chains(reg, d: float, rt: float, tan_h: float, depth: float, step: float, qs: int, pulls: list, walls=None) -> list:
    """L'axe médian là où la forme est trop étroite pour l'anneau à la distance d : [(x, y, z)…], la pointe descend selon la demi-largeur
    locale. Il va jusqu'au point où l'anneau se referme, pour s'y raccorder. Les seuls recoins d'angle n'en demandent pas : les tirés d'angle
    (`pulls`) les font."""
    import numpy as np
    import shapely
    from .advanced import medial_axis
    if d <= rt + 1e-6:
        return []
    from shapely.geometry import LineString, Point
    from shapely.ops import unary_union
    forms = shapely.get_parts(reg)                        # forme par forme : les formes d'une région valide sont disjointes
    forms = forms[(shapely.get_type_id(forms) == 3) & ~shapely.is_empty(forms)]
    if not len(forms):
        return []
    def retrait(x):                                       # les formes à nombreux trous par le calcul qui leur convient (S._erode_one)
        heavy = shapely.get_num_interior_rings(forms) >= S.HOLES_SPLIT if x >= S.HOLES_SPLIT_D else np.zeros(len(forms), dtype=bool)
        out = np.empty(len(forms), dtype=object)
        out[~heavy] = shapely.buffer(forms[~heavy], -x, quad_segs=qs)
        for i in np.nonzero(heavy)[0].tolist():
            out[i] = S._erode_one(forms[i], x, qs)
        return out

    fit = retrait(rt + 1e-3)
    opened = shapely.buffer(retrait(d), d, quad_segs=qs)
    try:
        rest = shapely.difference(fit, opened)
    except shapely.errors.GEOSException:
        rest = np.array([_overlay('difference', a, b) for a, b in zip(fit, opened)], dtype=object)
    rest = shapely.buffer(shapely.buffer(rest, -1e-4), 1e-4)
    parts = shapely.get_parts(rest)
    parts = parts[(shapely.get_type_id(parts) == 3) & ~shapely.is_empty(parts)]
    if not len(parts) or float(shapely.area(parts).sum()) < 1e-8:
        return []
    full = [LineString([v, (v[0] + b[0] * reach / s, v[1] + b[1] * reach / s)]) for v, b, s, reach in pulls if reach >= d - 1e-4]
    feet = [Point(v[0] + b[0] * reach / s, v[1] + b[1] * reach / s) for v, b, s, reach in pulls if rt < reach < d - 1e-4]
    keep = np.ones(len(parts), dtype=bool)
    if full:
        tubes = shapely.buffer(np.array(full, dtype=object), d)
        # couverte par un seul tube, le cas courant ; par plusieurs (un recoin à cheval), par leur réunion
        q, t = shapely.STRtree(tubes).query(parts, predicate='intersects')
        groups: dict = {}
        for i, j in zip(q.tolist(), t.tolist()):
            groups.setdefault(i, []).append(j)
        for i, js in groups.items():
            if unary_union([tubes[j] for j in js]).covers(parts[i]):
                keep[i] = False
        if feet:
            near_foot, _t = shapely.STRtree(feet).query(parts, predicate='dwithin', distance=2 * d)
            keep[near_foot] = True
    kept = parts[keep]
    if not len(kept):
        return []
    uncut = unary_union(list(kept))
    # l'axe calculé près d'elles seulement
    grown = shapely.buffer(kept, 3 * d + 3 * step, quad_segs=qs)
    q, t = shapely.STRtree(forms).query(grown, predicate='intersects')
    groups = {}
    for i, j in zip(q.tolist(), t.tolist()):
        groups.setdefault(j, []).append(i)
    pieces = [_overlay('intersection', forms[j], unary_union([grown[i] for i in ids])) for j, ids in groups.items()]
    bits = shapely.get_parts(np.array(pieces, dtype=object))
    bits = bits[(shapely.get_type_id(bits) == 3) & ~shapely.is_empty(bits)]
    if not len(bits):
        return []
    ax_step = max(0.02, min(step, d / 2))
    from ..core import workers
    chains = [c for found in workers.pmap(lambda q: medial_axis(q, ax_step, min_dist=max(ax_step / 2, rt)), list(bits)) for c in found]
    if not chains:
        return []
    tree = walls if walls is not None else _walls_index(reg)
    from .advanced import prune_hairs
    chains = prune_hairs(chains, reg, 135.0, walls=tree)  # une courbe en petits segments donne une branche par sommet
    if not chains:
        return []
    near = uncut.buffer(d + step)                         # plus loin : l'effet du bord artificiel de la zone
    shapely.prepare(near)
    dense = [shapely.get_coordinates(shapely.segmentize(shapely.LineString(c), ax_step)) for c in chains]
    allp = np.concatenate(dense)
    _i, dist = tree.query_nearest(shapely.points(allp), return_distance=True, all_matches=False)
    ok = (dist > rt + 1e-4) & (dist <= d + 1e-3) & shapely.contains_xy(near, allp[:, 0], allp[:, 1])
    z = -np.minimum(depth, (dist - rt) / tan_h)
    out, k = [], 0
    for c in dense:
        cur = []
        for j in range(k, k + len(c)):
            if ok[j]:
                cur.append((float(allp[j, 0]), float(allp[j, 1]), float(z[j])))
            elif cur:
                out.append(cur)
                cur = []
        if cur:
            out.append(cur)
        k += len(c)
    return [p for p in out if len(p) >= 2]


def _excursions(g: _Graph, cycle: list, m) -> list:
    """« Finition 3D uniquement » (relevé dans TE13) : le tour sans l'anneau, chaque sortie de l'anneau à part (un tiré d'angle, une
    branche étroite), du pied à son retour au pied, en suivant l'anneau depuis le premier sommet du contour."""
    rings = [i for i, h in enumerate(cycle) if g.he[h][4] == 'anneau']
    if not rings:
        return [g.flat(cycle)]
    i0 = rings[0]
    if m is not None:
        i0 = min(rings, key=lambda i: math.dist(g.he[cycle[i]][2][0][:2], m[:2]))
    turn = cycle[i0:] + cycle[:i0]
    # le premier sommet : sa sortie, juste avant l'anneau qui en part, doit venir en premier
    k = len(turn)
    while k > 0 and g.he[turn[k - 1]][4] != 'anneau':
        k -= 1
    turn = turn[k:] + turn[:k]
    out, run = [], []
    for h in turn:
        if g.he[h][4] == 'anneau':
            if run:
                out.append(g.flat(run))
                run = []
        else:
            run.append(h)
    if run:
        out.append(g.flat(run))
    return out


def _pull_corners(reg, max_angle: float) -> list:
    """Angles saillants de la forme plus fermés que `max_angle` : [(bord de la forme, sommet, bissectrice, sinus du demi-angle)]. Ne dépend
    pas de la passe : calculé une fois par Finition (sur un gros dessin, 11 767 formes reprises à chaque passe)."""
    out = []
    if max_angle <= 0:
        return out
    for poly in getattr(reg, 'geoms', [reg]):
        if poly.geom_type != 'Polygon' or poly.is_empty:
            continue
        edge = None
        for v, b, ang in S.corner_pulls(poly, False, max_angle):
            s = math.sin(ang / 2)
            if s > 1e-6:
                edge = poly.boundary if edge is None else edge
                out.append((edge, v, b, s))
    return out


def _pull_reaches(corners: list, d: float) -> list:
    """Pour chaque angle : jusqu'où sa bissectrice reste à égale distance des deux côtés, jusqu'à la distance d du bord. Rend la distance au
    bord du point atteint : d si l'outil a la place, moins dans une partie étroite. Huit points le long de la bissectrice (une autre paroi
    peut barrer le chemin avant le bout), puis 14 dichotomies, pour tous les angles à la fois : les mêmes points et les mêmes distances
    qu'angle par angle, sans un objet Python par point (720 000 sur un gros dessin)."""
    import numpy as np
    import shapely
    n = len(corners)
    if not n:
        return []
    edges = np.empty(n, dtype=object)
    edges[:] = [c[0] for c in corners]
    vx = np.array([c[1][0] for c in corners], dtype=float)
    vy = np.array([c[1][1] for c in corners], dtype=float)
    bx = np.array([c[2][0] for c in corners], dtype=float)
    by = np.array([c[2][1] for c in corners], dtype=float)
    s = np.array([c[3] for c in corners], dtype=float)
    t1 = d / s

    def ok(idx, t, eps):
        return np.abs(shapely.distance(edges[idx], shapely.points(vx[idx] + bx[idx] * t, vy[idx] + by[idx] * t)) - t * s[idx]) <= eps
    first = np.full(n, 9)                                 # premier des huit points où l'égale distance cesse ; 9 : aucun
    for k in range(1, 9):
        live = np.nonzero(first == 9)[0]
        if not len(live):
            break
        bad = ~ok(live, t1[live] * k / 8, 1e-4)
        first[live[bad]] = k
    out = [d] * n
    sel = np.nonzero(first < 9)[0]
    if len(sel):
        kf = first[sel]
        lo = np.where(kf > 1, t1[sel] * (kf - 1) / 8, 0.0)
        hi = t1[sel] * kf / 8
        for _ in range(14):
            m = (lo + hi) / 2
            good = ok(sel, m, 1e-5)
            lo = np.where(good, m, lo)
            hi = np.where(good, hi, m)
        for i, r in zip(sel.tolist(), (lo * s[sel]).tolist()):
            out[i] = r
    return out


def _pulls(reg, d: float, max_angle: float, corners=None) -> list:
    """Angles saillants de la forme plus fermés que `max_angle` : [(sommet, bissectrice, sinus du demi-angle, distance atteinte)].
    `corners` : ceux de `_pull_corners(reg, max_angle)`, déjà calculés."""
    corners = _pull_corners(reg, max_angle) if corners is None else corners
    return [(v, b, s, r) for (_e, v, b, s), r in zip(corners, _pull_reaches(corners, d))]


#: écart (mm) entre les points contrôlés le long d'un tiré d'angle, et ce que le cône peut y entamer
PULL_STEP = 0.1
PULL_TOL = 0.01


def _limit_pulls(pulls: list, walls) -> list:
    """Les tirés d'angle, arrêtés avant la première paroi que le cône toucherait. `_pull_reach` essaie huit points : sur un tiré de 7,6 mm d'un dessin réel,
    une paroi passait entre deux, et le cône y entrait de 0,2 mm. Ici, tous les 0,1 mm, tous les tirés à la fois."""
    import numpy as np
    import shapely
    if not pulls or walls is None:
        return pulls
    v = np.array([p[0][:2] for p in pulls], dtype=float)
    b = np.array([p[1][:2] for p in pulls], dtype=float)
    s = np.array([p[2] for p in pulls], dtype=float)
    ts = np.array([p[3] for p in pulls], dtype=float) / s
    n = np.clip((ts / PULL_STEP).astype(int) + 1, 1, 400)
    who = np.repeat(np.arange(len(pulls)), n)
    ends = np.cumsum(n)
    k = np.arange(ends[-1]) - np.repeat(ends - n, n) + 1
    t = ts[who] * k / n[who]
    xy = v[who] + b[who] * t[:, None]
    at, dist = walls.query_nearest(shapely.points(xy), return_distance=True, all_matches=False)
    near = np.full(len(t), np.inf)
    near[at[0]] = dist
    bad = near < t * s[who] - PULL_TOL
    if not bad.any():
        return pulls
    out = list(pulls)
    for i in np.unique(who[bad]).tolist():
        first = float(t[bad & (who == i)].min())
        v0, b0, s0, _r = pulls[i]
        out[i] = (v0, b0, s0, max(0.0, first - float(ts[i] / n[i])) * s0)
    return out


def _level_graph(reg, z: float, rt: float, tan_h: float, op, step: float, qs: int, wall_right: bool, walls=None, corners=None) -> tuple:
    """Le graphe d'une passe à la cote z, et l'ensemble des sommets de tiré d'angle (avec ceux dont le pied n'est pas sur l'anneau).
    `corners` : les angles de `_pull_corners`, communs à toutes les passes."""
    import shapely
    from shapely.geometry import LineString
    depth = -z
    d = rt + depth * tan_h
    ax_step = max(0.02, min(step, d / 2)) if d > 0 else 0.02
    snap = 3 * ax_step
    g = _Graph(wall_right, snap)
    base = S.erode(reg, d, qs)
    if not base.is_empty:
        for ring in S.rings_of(base, not wall_right):
            g.chain([(p[0], p[1], z) for p in ring], 'anneau')
    max_angle = float(getattr(op, 'corner_pull_angle', 135.0) or 0.0)
    walls = walls if walls is not None else _walls_index(reg)
    pulls = _limit_pulls(_pulls(reg, d, max_angle, corners), walls)
    # les axes, sans ce que les tirés d'angle font déjà : leur géométrie exacte remplace celle du Voronoï
    tubes = [LineString([v, (v[0] + b[0] * reach / s, v[1] + b[1] * reach / s)]) for v, b, s, reach in pulls if reach > 1e-6]
    chains = _axis_chains(reg, d, rt, tan_h, depth, step, qs, pulls, walls)
    if chains and tubes:
        tree = shapely.STRtree(tubes)
        kept = []
        for c in chains:
            mid = c[len(c) // 2]
            hits = tree.query(shapely.points(mid[0], mid[1]), predicate='dwithin', distance=snap)
            spur = False
            if len(hits):
                line = LineString([p[:2] for p in c])
                spur = any(tubes[int(i)].distance(shapely.points(line.coords[0])) <= snap and
                           tubes[int(i)].distance(shapely.points(line.coords[-1])) <= snap and
                           tubes[int(i)].buffer(snap).covers(line) for i in hits)
            if not spur:
                kept.append(c)
        chains = kept
    eps = max(1e-3, min(0.005, ax_step / 4))

    def clear(a, b) -> bool:
        """Le cône passe de a à b sans toucher de paroi (à 0,01 mm près)."""
        n = max(2, min(12, int(math.dist(a[:2], b[:2]) / max(ax_step / 2, 0.01)) + 1))
        for i in range(n + 1):
            t = i / n
            x, y, zi = a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]), a[2] + t * (b[2] - a[2])
            if zi < -1e-6 and walls.query_nearest(shapely.points(x, y), return_distance=True, all_matches=False)[1][0] < rt - zi * tan_h - 0.01:
                return False
        return True

    for c in chains:
        c = _rdp3(c, eps)
        for end, inner in ((0, 1), (-1, -2)):             # les bouts rejoignent le nœud voisin, si le cône y passe
            at = g.near(c[end], snap)
            if at is not None and clear(g.pos[at], c[inner]):
                c[end] = g.pos[at]
        g.edge(c, 'axe')
    _drop_short_leaves(g, 4 * ax_step)
    apex_z = rt / tan_h if op.ramp else 0.0
    short = set()
    for v, b, s, reach in pulls:
        if reach <= rt + 1e-3:
            continue                                      # la pointe n'y entre pas
        t = reach / s
        foot = (v[0] + b[0] * t, v[1] + b[1] * t, -min(depth, (reach - rt) / tan_h))
        top = rt / s if not op.ramp else 0.0              # sans plongée : jusqu'à la surface ; avec : jusqu'au sommet de la forme
        apex = (v[0] + b[0] * top, v[1] + b[1] * top, apex_z)
        at = g.near(foot, snap)
        if at is not None:
            hs = g.out.get(at, ())
            if reach < d - 1e-4 and hs and all(g.he[h][4] == 'axe' for h in hs) and all(clear(foot, g.he[h][2][1]) for h in hs):
                g.move(at, foot)                          # le pied du tiré d'angle est exact, l'axe approché s'y raccorde
            elif clear(apex, g.pos[at]):
                foot = g.pos[at]
        if g.edge([apex, foot], 'tire', 1e-4) and reach < d - 1e-4:
            short.add((round(apex[0], 4), round(apex[1], 4)))
    return g, short


def _drop_short_leaves(g: _Graph, limit: float) -> None:
    """Enlève les petits bouts d'axe sans issue laissés par le Voronoï."""
    dead = set()
    for k, e in enumerate(g.he):
        if k in dead or e[4] != 'axe' or k % 2:
            continue
        free = len(g.out[e[0]]) == 1 or len(g.out[e[1]]) == 1
        length = sum(math.dist(a[:2], b[:2]) for a, b in zip(e[2], e[2][1:]))
        if free and length < limit:
            dead |= {k, e[3]}
    if not dead:
        return
    for n, hs in list(g.out.items()):
        g.out[n] = [h for h in hs if h not in dead]
        if not g.out[n]:
            del g.out[n]
    for k in dead:
        g.he[k][4] = 'dos'                                # plus jamais un départ de tour


def _owners(g: _Graph, cycles: list, tree, wall_right: bool, rt: float, tan_h: float, stock: float) -> list:
    """Le contour du dessin que longe chaque tour : on vise la paroi, du côté où elle doit être, à la distance où le cône la touche, en
    quelques points du tour ; le contour le plus visé l'emporte. Toutes les visées de la passe en une seule requête."""
    import numpy as np
    import shapely
    aims, of = [], []
    for c, cycle in enumerate(cycles):
        every = max(1, len(cycle) // 24)
        for h in cycle[::every] + [x for x in cycle if g.he[x][4] == 'axe'][:8]:
            e = g.he[h]
            if e[4] == 'tire':
                continue
            path = e[2]
            for a, b in zip(path, path[1:]):
                dx, dy = b[0] - a[0], b[1] - a[1]
                n = math.hypot(dx, dy)
                if n < 1e-9:
                    continue
                nx, ny = (dy / n, -dx / n) if wall_right else (-dy / n, dx / n)
                zm = (a[2] + b[2]) / 2
                dist = rt + max(0.0, -zm) * tan_h + stock
                aims.append(((a[0] + b[0]) / 2 + nx * dist, (a[1] + b[1]) / 2 + ny * dist))
                of.append(c)
                break
    votes: list = [{} for _c in cycles]
    if aims:
        for c, i in zip(of, tree.nearest(shapely.points(np.array(aims, dtype=float))).tolist()):
            votes[c][i] = votes[c].get(i, 0) + 1
    lone = [c for c, v in enumerate(votes) if not v]       # rien que des tirés d'angle : le contour le plus près du sommet
    out = [max(v, key=v.get) if v else -1 for v in votes]
    if lone:
        tops = np.array([g.he[cycles[c][0]][2][0][:2] for c in lone], dtype=float)
        for c, i in zip(lone, tree.nearest(shapely.points(tops)).tolist()):
            out[c] = int(i)
    return out


def _rotate(path: list, q) -> list:
    """Le même tour fermé, qui part du point le plus près de q (ajouté s'il tombe au milieu d'un segment)."""
    ring = [p[:2] for p in path]
    _d, i, c = S._closest_on_ring(ring, q)
    a, b = path[i], path[i + 1]
    n = math.dist(a[:2], b[:2])
    t = math.dist(a[:2], c) / n if n > 1e-12 else 0.0
    start = (c[0], c[1], a[2] + t * (b[2] - a[2]))
    out = [start] + path[i + 1:] + path[1:i + 1] + [start]
    clean = [out[0]]
    for p in out[1:]:
        if math.dist(p, clean[-1]) > 1e-9:
            clean.append(p)
    return clean


def _start_path(path: list, m, offset: float, short: set, em_pos) -> list:
    """Où commence le tour du contour. Avec un sommet du dessin : s'il y a un tiré d'angle ici, on part de son sommet, sinon du point
    relevé dans TE13 (après l'arrondi). Sans : au plus près de l'outil."""
    if m is None:
        return _rotate(path, em_pos[:2]) if em_pos is not None else path
    best = min(range(len(path)), key=lambda i: math.dist(path[i][:2], m[:2]))
    p = path[best]
    # le sommet d'un tiré d'angle : les deux voisins sont le même pied, plus bas
    prev, nxt = path[best - 1], path[(best + 1) % (len(path) - 1)]
    if 0 < best < len(path) - 1 and math.dist(prev[:2], nxt[:2]) < 1e-9 and p[2] > prev[2]:
        out = path[best:] + path[1:best + 1]
        if (round(p[0], 4), round(p[1], 4)) in short:
            out = out[:-1]                                # pied dans une partie étroite : TE ne remonte pas à la fin
        return out
    if best in (0, len(path) - 1) and math.dist(path[1][:2], path[-2][:2]) < 1e-9 and p[2] > path[1][2]:
        if (round(p[0], 4), round(p[1], 4)) in short:
            return path[:-1]
        return path
    ring2d = [q[:2] for q in path]
    return _rotate(path, S._start_after_corner(ring2d, m, offset))


#: un chemin plus court (mm) est un point : des centaines d'allers-retours sur quelques microns ne seraient pas une pente
FLAT_PATH = 0.02


def _v_entry(em, path: list, descent: float, angle: float) -> None:
    """Plongée angulaire (TE13) : on avance sur le chemin, moitié de la longueur que demande la descente à cet angle, et on revient au
    départ. La descente s'ajoute à la cote du chemin, tirés d'angle compris. Si le chemin est trop court : autant d'allers-retours qu'il faut."""
    tan_a = math.tan(math.radians(angle))
    total_len = sum(math.dist(a[:2], b[:2]) for a, b in zip(path, path[1:]))
    if tan_a <= 1e-6 or total_len < FLAT_PATH:
        return                                            # un point : pas de place pour une pente, l'outil y descend droit
    half = descent / tan_a / 2
    trips = max(1, math.ceil(half / total_len - 1e-9))
    for k in range(trips):
        d_i = descent / trips
        base = descent - (k + 1) * d_i
        length = d_i / tan_a
        h = length / 2
        out = [(path[0], 0.0)]
        s = 0.0
        for a, b in zip(path, path[1:]):
            n = math.dist(a[:2], b[:2])
            if n <= 1e-12:
                continue
            if s + n >= h - 1e-9:
                t = (h - s) / n
                out.append(((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]), a[2] + t * (b[2] - a[2])), h))
                break
            s += n
            out.append((b, s))
        for p, si in out[1:]:
            em.feed(p[0], p[1], p[2] + base + d_i * (1 - si / length))
        for p, si in out[-2::-1]:
            em.feed(p[0], p[1], p[2] + base + d_i * si / length)


def _emit(em, path: list, z_prev: float, z: float, ramp: bool, angle: float) -> None:
    descent = max(0.0, z_prev - z) if ramp else 0.0
    x, y, z0 = path[0]
    start = z0 + descent
    if em.pos is not None and em.pos[2] < em.safe:
        em.moves.append(Move('rapid', em.pos[0], em.pos[1], em.safe))
    em.moves.append(Move('rapid', x, y, em.safe))
    high = max(start, em.clear)
    em.moves.append(Move('rapid', x, y, high))
    em.pos = (x, y, high)
    em.plunge(start)
    if descent > 0:
        _v_entry(em, path, descent, angle)
    for p in path[1:]:
        em.feed(p[0], p[1], p[2])


def finish_order(contours: list, polys: list, drawing_order: bool = False) -> tuple:
    """L'ordre relevé dans TE13 sur quatre dessins. En poche par poche et tri manuel : les formes extérieures de gauche à droite, puis les
    contours intérieurs, des plus englobés aux moins englobés, de gauche à droite. Sinon : la première forme extérieure, puis le reste de
    cette liste à l'envers. Rend aussi l'ensemble des contours extérieurs (ceux que personne n'englobe)."""
    import shapely
    depth = []
    tree = shapely.STRtree(polys)
    for i, pts in enumerate(contours):
        hits = tree.query(shapely.points(pts[0][0], pts[0][1]), predicate='intersects')
        depth.append(sum(1 for j in hits if int(j) != i and polys[int(j)].covers(polys[i])))

    def key(i):
        return (polys[i].bounds[0], polys[i].bounds[1])
    tops = sorted([i for i in range(len(contours)) if depth[i] == 0], key=key)
    inner = sorted([i for i in range(len(contours)) if depth[i] > 0], key=lambda i: (-depth[i], *key(i)))
    listed = tops + inner
    if drawing_order:
        return listed, set(tops)
    return listed[:1] + listed[1:][::-1], set(tops)


def finish_te(doc, setup, op, tool, tp, em, here, by_shape=None, lines=None, reg=None) -> None:
    """La Finition relevée dans TE13 : voir l'en-tête du module. `by_shape` (la Gamme) : `by_shape(closed, polys)` rend [(contours de la forme, fond)] :
    forme par forme et à chaque passe, `fond(rang de la passe)`, puis les contours de la forme à cette passe. `lines`, `reg` : les contours
    aplatis des formes de l'opération et leur région, quand l'appelant les a déjà."""
    import shapely
    from shapely.geometry import LineString, Polygon
    from .advanced import _body
    tol = setup.tolerance
    if lines is None:
        lines = S.polylines([g for it in S.source_items(doc, op) if (g := S.item_geometry(it))], tol)
    reg = S.region_from_lines(lines) if reg is None else reg
    if reg.is_empty:
        tp.warnings.append('gravure 2,5D : aucun contour fermé')
        return
    tan_h = math.tan(math.radians(tool.angle) / 2)
    rt = tool.tip / 2
    r_max = _body(tool) / 2
    depth = abs(op.depth) if op.depth > 0 else (r_max - rt) / tan_h
    d_flat = rt + depth * tan_h
    qs = S._quad_segs(max(d_flat, tol), tol)
    stock = max(0.0, float(op.stock or 0.0))
    if stock > 0.0:                                       # comme TE : les arrondis restent centrés sur les sommets du dessin
        reg = S.erode(reg, stock, qs)
        if reg.is_empty:
            tp.warnings.append(f'gravure 2,5D : surépaisseur de {stock:g} mm trop grande pour ces formes')
            return
    if d_flat > r_max + 1e-9:
        tp.warnings.append(f'finition : à {depth:g} mm, le cône de l\'outil ne va pas jusqu\'en surface ({2 * r_max:g} mm de corps) ; '
                           f'le bord reste en retrait de {d_flat - r_max:.3f} mm')
    closed = [pts for pts, c in lines if c and len(pts) >= 4]
    if not closed:
        tp.warnings.append('gravure 2,5D : aucun contour fermé')
        return
    polys = [Polygon([p[:2] for p in pts]).buffer(0) for pts in closed]
    by_pass = getattr(op, 'pass_order', 'poche') == 'global'
    order, tops = finish_order(closed, polys, not by_pass and getattr(op, 'order_mode', 'auto') == 'dessin')
    tree = shapely.STRtree([LineString([p[:2] for p in pts]) for pts in closed])
    skip = bool(getattr(op, 'finish_skip_frame', False))
    wall_right = bool(op.climb)
    vstep = max(0.0, float(getattr(op, 'vcarve_step', 0.0) or 0.0))
    cotes = S.levels(depth, vstep) if vstep > 0 else [-depth]
    step = max(0.01, op.resolution or 0.05)
    # manuel, puis premier sommet : comme les autres parcours
    marks = S.start_marks(doc, op, tol)
    by_policy = getattr(op, 'start_policy', 'proche') == 'dessin'
    first = {i: (pts[0][0], pts[0][1], tuple(pts[-2][:2]), tuple(pts[1][:2])) for i, pts in enumerate(closed)} if by_policy else {}
    only_3d = bool(getattr(op, 'finish_3d_only', False))
    by_level = []
    walls = _walls_index(reg)
    corners = _pull_corners(reg, float(getattr(op, 'corner_pull_angle', 135.0) or 0.0))
    for level, z in enumerate(cotes):
        progress.step(level, len(cotes))
        g, short = _level_graph(reg, z, rt, tan_h, op, step, qs, wall_right, walls, corners)
        tours: dict = {}
        cycles = g.faces()
        for cycle, who in zip(cycles, _owners(g, cycles, tree, wall_right, rt, tan_h, stock)):
            if only_3d:
                tours.setdefault(who, []).extend(_excursions(g, cycle, first.get(who)))
            else:
                tours.setdefault(who, []).append(g.flat(cycle))
        by_level.append((tours, short))
    hand = [m for m in marks if len(m) < 4 or not by_policy]
    ramp = bool(op.ramp)
    angle = S.ramp_angle_of(op) if ramp else 0.0

    def cut(c: int, k: int) -> None:
        tours, short = by_level[k]
        prev = cotes[k - 1] if k else 0.0
        z = cotes[k]
        for path in tours.get(c, ()):
            if min(p[2] for p in path) >= prev - 1e-6:
                continue                                  # rien de plus bas qu'à la passe d'avant : relevé dans TE13
            if only_3d:
                _emit(em, path, prev, z, ramp, angle)
                continue
            m = first.get(c)
            near = d_flat + stock + 1.0
            for h in hand:
                if S._closest_on_ring([p[:2] for p in path], h)[0] <= near:
                    m = h
                    break
            offset = rt - z * tan_h + stock
            _emit(em, _start_path(path, m, offset, short, em.pos), prev, z, ramp, angle)

    if by_shape is not None:
        shapes = by_shape(closed, polys)
        # MODE_MULTIPASSE de TE : Global, chaque passe sur tout le dessin ; sinon, chaque forme jusqu'au fond
        visits = [(s, k) for k in range(len(cotes)) for s in shapes] if getattr(op, 'pass_order', 'poche') == 'global' else             [(s, k) for s in shapes for k in range(len(cotes))]
        for (contours, floor), k in visits:
            floor(k)
            for c in contours:
                cut(c, k)
        return
    if by_pass:
        for k in range(len(cotes)):
            for c in order:
                if not (skip and c in tops):
                    cut(c, k)
    else:
        for c in order:
            if not (skip and c in tops):
                for k in range(len(cotes)):
                    cut(c, k)
    if not em.moves and skip:
        tp.warnings.append('finition : cadre englobant ignoré, il ne reste aucun contour à usiner (comme TypeEdit, tous les contours '
                           'extérieurs sont ignorés)')
