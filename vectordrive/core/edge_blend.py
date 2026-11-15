"""Congés et chanfreins sur les arêtes qu'on choisit, comme les blends de SolidCraft, mais sur un
maillage : le volume n'a pas de faces exactes, seulement ses triangles.

Une arête vive est une suite de côtés de triangles dont les normales divergent ; elle se continue à
travers un sommet tant qu'aucune autre arête vive n'y arrive et qu'elle tourne peu (le bord d'un
cylindre facetté reste une seule arête). Pour chacune, on balaie une section le long de l'arête :
saillante, ce qu'elle enferme est retiré ; rentrante, ajouté. La section déborde un peu des faces,
pour que le booléen ne dépende pas de faces confondues.

Au bout d'une arête saillante, le balayage continue dans le vide, ce qui donne un profil propre sur
la face d'à côté ; s'il rencontrait de la matière (une paroi plus haute), il s'arrête au sommet.
Trois congés de même rayon qui se rejoignent à un coin s'y raccordent par une portion de sphère.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import solids as SO

SHARP_DEG = 30.0            # au-delà, deux triangles voisins font une arête vive
MAX_TURN_DEG = 45.0         # au-delà, l'arête s'arrête à ce sommet
PICK_TOL = 0.5              # mm : une arête retrouvée d'après un point noté
MAX_SEGMENTS = 32           # côtés d'un quart de cercle, au plus
CHORD_TOL = 0.01            # mm
MIN_AREA2 = 1e-6            # double de l'aire : en dessous, la normale d'un triangle ne veut rien dire
PROBES = 16                 # sections contrôlées par arête


class EdgeBlendError(SO.SolidError):
    pass


def _unit(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-12 else v


@dataclass
class Chain:
    """Une arête vive. `points` : ses sommets, le premier répété à la fin si elle est fermée ;
    `left`, `right` : les normales des faces de chaque côté, côté par côté, dans le sens de parcours."""
    points: np.ndarray
    left: np.ndarray
    right: np.ndarray
    convex: bool
    closed: bool
    angle: float

    def length(self) -> float:
        return float(np.linalg.norm(np.diff(self.points, axis=0), axis=1).sum())

    def middle(self) -> list:
        """Un point sur l'arête, à mi-longueur : la façon de la retrouver après un recalcul."""
        steps = np.linalg.norm(np.diff(self.points, axis=0), axis=1)
        run = np.cumsum(steps)
        half = run[-1] / 2.0
        k = int(np.searchsorted(run, half))
        before = run[k - 1] if k else 0.0
        t = (half - before) / max(steps[k], 1e-12)
        q = self.points[k] + (self.points[k + 1] - self.points[k]) * t
        return [float(q[0]), float(q[1]), float(q[2])]

    def distance(self, q) -> float:
        q = np.asarray(q, dtype=np.float64)
        a, b = self.points[:-1], self.points[1:]
        ab = b - a
        t = np.clip(((q - a) * ab).sum(axis=1) / np.maximum((ab * ab).sum(axis=1), 1e-18), 0.0, 1.0)
        return float(np.linalg.norm(q - (a + ab * t[:, None]), axis=1).min())


def sharp_chains(solid, angle: float = SHARP_DEG) -> list:
    """Les arêtes vives du volume."""
    v = np.asarray(solid.verts, dtype=np.float64)
    t = np.asarray(solid.tris, dtype=np.int64)
    if not len(t):
        return []
    n = np.cross(v[t[:, 1]] - v[t[:, 0]], v[t[:, 2]] - v[t[:, 0]])
    area2 = np.linalg.norm(n, axis=1)
    n = n / np.where(area2 > 0.0, area2, 1.0)[:, None]
    u, w = t.ravel(), t[:, [1, 2, 0]].ravel()
    tri = np.repeat(np.arange(len(t)), 3)
    big = int(v.shape[0]) + 1
    key = u * big + w
    order = np.argsort(key)
    sorted_key = key[order]
    pos = np.searchsorted(sorted_key, w * big + u)
    pos[pos >= len(key)] = 0
    found = sorted_key[pos] == w * big + u
    other = tri[order[pos]]
    keep = (u < w) & found & (area2[tri] >= MIN_AREA2) & (area2[other] >= MIN_AREA2)
    keep &= (n[tri] * n[other]).sum(axis=1) < math.cos(math.radians(angle))
    edges = [(int(a), int(b), int(c), int(d)) for a, b, c, d in zip(u[keep], w[keep], tri[keep], other[keep])]
    if not edges:
        return []
    at: dict = {}
    for k, (a, b, _l, _r) in enumerate(edges):
        at.setdefault(a, []).append(k)
        at.setdefault(b, []).append(k)
    convex = {}
    for k, (a, b, c, d) in enumerate(edges):
        convex[k] = float(np.cross(n[c], n[d]) @ (v[b] - v[a])) > 0.0
    limit = math.cos(math.radians(MAX_TURN_DEG))

    def passes(x: int) -> bool:
        """L'arête continue-t-elle à travers ce sommet ?"""
        here = at[x]
        if len(here) != 2 or convex[here[0]] != convex[here[1]]:
            return False
        ends = [edges[k][1] if edges[k][0] == x else edges[k][0] for k in here]
        return float(_unit(v[x] - v[ends[0]]) @ _unit(v[ends[1]] - v[x])) >= limit

    through = {x: passes(x) for x in at}
    seen = set()
    chains = []

    def walk(start: int, first: int) -> Chain:
        """De `start` par le côté `first`, jusqu'à un sommet qui l'arrête ou au départ."""
        pts, left, right, angles = [start], [], [], []
        x, k = start, first
        while True:
            seen.add(k)
            a, b, c, d = edges[k]
            y = b if a == x else a
            l, r = (c, d) if a == x else (d, c)
            left.append(n[l])
            right.append(n[r])
            angles.append(math.degrees(math.acos(max(-1.0, min(1.0, float(n[c] @ n[d]))))))
            pts.append(y)
            if y == start or not through[y]:
                break
            k = at[y][0] if at[y][1] == k else at[y][1]
            if k in seen:
                break
            x = y
        return Chain(v[pts].copy(), np.array(left), np.array(right), convex[first], pts[0] == pts[-1] and len(pts) > 2,
                     float(np.mean(angles)))

    for x in at:
        if not through[x]:
            for k in at[x]:
                if k not in seen:
                    chains.append(walk(x, k))
    for k in range(len(edges)):
        if k not in seen:
            chains.append(walk(edges[k][0], k))
    return chains


def find(chains: list, pick, tol: float = PICK_TOL) -> int:
    """Le rang de l'arête la plus proche du point noté."""
    if chains:
        d = [c.distance(pick) for c in chains]
        k = int(np.argmin(d))
        if d[k] <= tol:
            return k
    raise EdgeBlendError(f'arête introuvable près de ({pick[0]:g} ; {pick[1]:g} ; {pick[2]:g})')


def _frames(ch: Chain) -> tuple:
    """Par sommet : la normale de chaque face, perpendiculaire à l'arête, et le sens de l'arête."""
    dirs = np.diff(ch.points, axis=0)
    dirs = dirs / np.maximum(np.linalg.norm(dirs, axis=1), 1e-12)[:, None]
    if ch.closed:
        before = np.roll(np.arange(len(dirs)), 1)
        d = dirs + dirs[before]
        a, b = ch.left + ch.left[before], ch.right + ch.right[before]
        pts = ch.points[:-1]
    else:
        pad = lambda s: np.vstack((s[:1], s[:-1] + s[1:], s[-1:])) if len(s) > 1 else np.vstack((s, s))
        d, a, b = pad(dirs), pad(ch.left), pad(ch.right)
        pts = ch.points
    d = d / np.maximum(np.linalg.norm(d, axis=1), 1e-12)[:, None]
    a = a - (a * d).sum(axis=1)[:, None] * d
    b = b - (b * d).sum(axis=1)[:, None] * d
    a = a / np.maximum(np.linalg.norm(a, axis=1), 1e-12)[:, None]
    b = b / np.maximum(np.linalg.norm(b, axis=1), 1e-12)[:, None]
    return pts, a, b, d


def _setback(a, b, convex: bool, r: float, fillet: bool) -> tuple:
    """(t1, t2, recul, angle de la matière ou du vide entre les faces)."""
    sign = 1.0 if convex else -1.0
    t1 = _unit(-(b - (b @ a) * a)) * sign
    t2 = _unit(-(a - (a @ b) * b)) * sign
    phi = math.acos(max(-1.0, min(1.0, float(t1 @ t2))))
    return t1, t2, (r / math.tan(phi / 2.0) if fillet else r), phi


def _section(e, a, b, convex: bool, r: float, fillet: bool, arc_sides: int) -> np.ndarray:
    """La section au sommet `e` : T1 débordé, T1, l'arc ou le pan, T2, T2 débordé, et l'arête débordée
    (dernière, le balayage se ferme en éventail autour d'elle)."""
    t1, t2, back, phi = _setback(a, b, convex, r, fillet)
    q1, q2 = e + t1 * back, e + t2 * back
    if fillet:
        c = e + _unit(t1 + t2) * (r / math.sin(phi / 2.0))
        u1, u2 = q1 - c, q2 - c
        sweep = math.pi - phi
        s = math.sin(sweep)
        arc = [c + (math.sin((1.0 - i / arc_sides) * sweep) * u1 + math.sin(i / arc_sides * sweep) * u2) / s
               for i in range(1, arc_sides)]
    else:
        arc = []
    eps = max(2e-3, min(0.02, r * 0.02))
    o = 1.0 if convex else -1.0
    tip = e + (a + b) * (o * eps / max(1.0 + float(a @ b), 0.2))
    return np.array([q1 + a * (o * eps), q1] + arc + [q2, q2 + b * (o * eps), tip])


def _sweep(sections: list, closed: bool):
    """Le volume balayé par les sections."""
    M = SO._m()
    n, m = len(sections), len(sections[0])
    verts = np.concatenate(sections)
    tris = []
    for i in range(n if closed else n - 1):
        j = (i + 1) % n
        for k in range(m):
            l = (k + 1) % m
            p, q, s, t = i * m + k, i * m + l, j * m + k, j * m + l
            tris += [(p, q, t), (p, t, s)]
    if not closed:
        last = (n - 1) * m
        for k in range(m - 2):
            tris.append((m - 1, k + 1, k))
            tris.append((last + m - 1, last + k, last + k + 1))
    tris = np.array(tris, dtype=np.uint32)
    p0, p1, p2 = verts[tris[:, 0]], verts[tris[:, 1]], verts[tris[:, 2]]
    if float((p0 * np.cross(p1, p2)).sum()) < 0.0:
        tris = tris[:, ::-1]
    man = M.Manifold(M.Mesh(vert_properties=np.asarray(verts, dtype=np.float32), tri_verts=tris))
    if man.status() != M.Error.NoError:
        raise EdgeBlendError('rayon trop grand pour cette arête : le balayage se recoupe')
    return man


def _radii(ch: Chain, r0: float, r1: float, count: int) -> list:
    """Le rayon à chaque sommet : de r0 à r1 le long de l'arête."""
    if ch.closed or r1 <= 0.0 or r1 == r0:
        return [r0] * count
    steps = np.linalg.norm(np.diff(ch.points, axis=0), axis=1)
    run = np.r_[0.0, np.cumsum(steps)] / max(steps.sum(), 1e-12)
    return [r0 + (r1 - r0) * float(s) for s in run]


def _near_surface(q: np.ndarray, tris: np.ndarray, boxes: tuple, tol: float) -> bool:
    """Le point est-il à moins de `tol` de la surface ?"""
    keep = np.all(boxes[0] - tol <= q, axis=1) & np.all(boxes[1] + tol >= q, axis=1)
    t = tris[keep]
    if not len(t):
        return False
    a, b, c = t[:, 0], t[:, 1], t[:, 2]
    ab, ac, ap = b - a, c - a, q - a
    n = np.cross(ab, ac)
    nn = np.maximum((n * n).sum(axis=1), 1e-24)
    u = (np.cross(ap, ac) * n).sum(axis=1) / nn
    w = (np.cross(ab, ap) * n).sum(axis=1) / nn
    inside = (u >= -1e-6) & (w >= -1e-6) & (u + w <= 1.0 + 1e-6)
    if np.any(np.abs((ap * n).sum(axis=1))[inside] / np.sqrt(nn[inside]) <= tol):
        return True
    for p0, p1 in ((a, b), (b, c), (c, a)):
        d = p1 - p0
        s = np.clip(((q - p0) * d).sum(axis=1) / np.maximum((d * d).sum(axis=1), 1e-18), 0.0, 1.0)
        if np.any(np.linalg.norm(q - (p0 + d * s[:, None]), axis=1) <= tol):
            return True
    return False


def _fits(frames: tuple, convex: bool, radii: list, fillet: bool, tris: np.ndarray, boxes: tuple) -> bool:
    """Le raccord tombe-t-il sur les faces de l'arête ? Sinon, le rayon dépasse leur largeur."""
    pts, a, b, _d = frames
    count = len(pts)
    for i in sorted(set(int(k) for k in np.linspace(0, count - 1, min(PROBES, count)))):
        t1, t2, back, _phi = _setback(a[i], b[i], convex, radii[i], fillet)
        tol = 0.02 + 0.02 * back
        if not (_near_surface(pts[i] + t1 * back, tris, boxes, tol) and _near_surface(pts[i] + t2 * back, tris, boxes, tol)):
            return False
    return True


def largest(ch: Chain, solid, fillet: bool = True, start: float = 1000.0) -> float:
    """Le plus grand rayon qui tient sur les faces de l'arête (à 2 % près)."""
    frames = _frames(ch)
    tris = np.asarray(solid.triangles(), dtype=np.float64)
    boxes = (tris.min(axis=1), tris.max(axis=1))
    count = len(frames[0])
    low, high = 0.0, start
    if _fits(frames, ch.convex, [high] * count, fillet, tris, boxes):
        return high
    for _i in range(16):
        mid = (low + high) / 2.0
        if _fits(frames, ch.convex, [mid] * count, fillet, tris, boxes):
            low = mid
        else:
            high = mid
        if high - low < low * 0.02:
            break
    return low


def _arc_sides(r: float) -> int:
    """Côtés de l'arc d'un quart de cercle pour tenir CHORD_TOL."""
    if r <= CHORD_TOL:
        return 3
    step = 2.0 * math.acos(1.0 - CHORD_TOL / r)
    return max(3, min(MAX_SEGMENTS, int(math.ceil(math.pi / 2.0 / step))))


def _body(man, ch: Chain, frames: tuple, radii: list, fillet: bool):
    """Ce qu'il faut retirer ou ajouter le long de l'arête."""
    pts, a, b, d = frames
    sides = _arc_sides(max(radii)) if fillet else 1
    sections = [_section(pts[i], a[i], b[i], ch.convex, radii[i], fillet, sides) for i in range(len(pts))]
    if ch.closed:
        return _sweep(sections, True)
    if ch.convex:                       # continuer dans le vide, s'il y en a
        reach = max(2.0 * max(radii), 1.0)
        for end, out in ((0, -d[0]), (-1, d[-1])):
            more = sections[end] + out * reach
            prism = _sweep([sections[end], more] if end else [more, sections[end]], False)
            if (man ^ prism).volume() <= 1e-5 + 1e-4 * prism.volume():
                if end:
                    sections.append(more)
                else:
                    sections.insert(0, more)
    return _sweep(sections, False)


def _corners(chosen: list, r: float) -> list:
    """Les coins où trois congés saillants de même rayon se rejoignent : la pièce de sphère à retirer."""
    M = SO._m()
    ends: dict = {}
    for ch, frames in chosen:
        if ch.closed or not ch.convex:
            continue
        pts, a, b, d = frames
        for i, out in ((0, d[0]), (-1, -d[-1])):
            ends.setdefault(tuple(np.round(pts[i], 4)), []).append((pts[i], a[i], b[i], out))
    cutters = []
    for ones in ends.values():
        if len(ones) != 3:
            continue
        normals = []
        for _p, a, b, _o in ones:
            for n in (a, b):
                if all(float(n @ m) < 0.999 for m in normals):
                    normals.append(n)
        if len(normals) != 3:
            continue
        v = ones[0][0]
        N = np.array(normals)
        if abs(np.linalg.det(N)) < 1e-3:
            continue
        c = np.linalg.solve(N, N @ v - r)
        pts = []
        for _p, a, b, _o in ones:
            sweep = math.acos(max(-1.0, min(1.0, float(a @ b))))
            s = math.sin(sweep)
            sides = _arc_sides(r)
            for i in range(sides + 1):
                k = i / sides
                pts.append(c + r * (math.sin((1.0 - k) * sweep) * a + math.sin(k * sweep) * b) / s)
        pts.append(v + _unit(N.sum(axis=0)) * max(2e-3, r * 0.02))
        hull = M.Manifold.hull_points(np.array(pts, dtype=np.float32))
        ball = M.Manifold.sphere(r, 4 * _arc_sides(r)).translate(tuple(float(x) for x in c))
        cutters.append(hull - ball)
    return cutters


def apply(solid, values: dict):
    """Le volume avec ses congés ou chanfreins. `values` : kind ('fillet' ou 'chamfer'), radius,
    radius_end (0 : constant), picks (un point sur chaque arête)."""
    M = SO._m()
    fillet = values.get('kind', 'fillet') != 'chamfer'
    r0, r1 = float(values.get('radius', 1.0)), float(values.get('radius_end', 0.0) or 0.0)
    if r0 <= 0.0:
        raise EdgeBlendError('rayon nul')
    picks = values.get('picks') or []
    if not picks:
        raise EdgeBlendError('aucune arête choisie')
    chains = sharp_chains(solid)
    ranks = []
    for q in picks:
        k = find(chains, q)
        if k not in ranks:
            ranks.append(k)
    man = solid.manifold()
    tris = np.asarray(solid.triangles(), dtype=np.float64)
    boxes = (tris.min(axis=1), tris.max(axis=1))
    cuts, adds, chosen = [], [], []
    for k in ranks:
        ch = chains[k]
        frames = _frames(ch)
        radii = _radii(ch, r0, r1, len(frames[0]))
        if not _fits(frames, ch.convex, radii, fillet, tris, boxes):
            top = largest(ch, solid, fillet, max(radii))
            raise EdgeBlendError(f'rayon trop grand pour cette arête : au plus {top:.2f} mm environ')
        (cuts if ch.convex else adds).append(_body(man, ch, frames, radii, fillet))
        chosen.append((ch, frames))
    if cuts:
        man = man - M.Manifold.batch_boolean(cuts, M.OpType.Add)
    if fillet and r1 <= 0.0:
        for cutter in _corners(chosen, r0):
            man = man - cutter
    if adds:
        man = man + M.Manifold.batch_boolean(adds, M.OpType.Add)
    out = SO._solid(man, solid.name)
    out.color = solid.color
    return out
