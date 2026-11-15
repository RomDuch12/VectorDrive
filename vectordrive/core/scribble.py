"""Gribouillis (comme l'effet Scribble des logiciels de dessin vectoriel) :
les formes fermées remplies d'un zigzag continu — un seul trait tant que la
forme le permet, l'outil ne remonte pas d'une ligne à la suivante.

Réglages : angle des lignes, écart, débord (la pointe du zigzag dépasse
ou reste en deçà du bord), variation (écarts et pointes tirés au hasard,
effet fait main ; graine fixe).
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from .geom import Contour, Line, Path


@dataclass
class ScribbleSpec:
    angle: float = 45.0             # angle des lignes (°)
    spacing: float = 1.0            # écart entre deux lignes (mm)
    overshoot: float = 0.0          # débord des pointes au-delà du bord (mm ; négatif : en deçà)
    variation: float = 0.0          # variation au hasard (0 à 1 : part de l'écart)
    seed: int = 1


def scribble(path: Path, spec: ScribbleSpec) -> Path:
    """Zigzags (contours ouverts) remplissant les formes fermées de `path`."""
    import shapely
    from shapely import affinity
    from .pathops import _to_shapely
    reg = _to_shapely(Path([c for c in path.contours if c.closed]))
    if reg.is_empty or spec.spacing <= 0:
        return Path([])
    rnd = random.Random(spec.seed)
    rot = affinity.rotate(reg, -spec.angle, origin=(0, 0))
    x0, y0, x1, y1 = rot.bounds
    rows = []
    y = y0 + spec.spacing / 2
    while y < y1:
        line = shapely.LineString([(x0 - 1, y), (x1 + 1, y)])
        cut = rot.intersection(line)
        segs = [list(g.coords) for g in getattr(cut, 'geoms', [cut]) if g.geom_type == 'LineString' and g.length > 1e-9]
        segs.sort(key=lambda c: min(c[0][0], c[-1][0]))
        rows.append([sorted(c) for c in segs])
        jitter = spec.variation * spec.spacing * (rnd.random() * 2 - 1) if spec.variation else 0.0
        y += max(spec.spacing * 0.2, spec.spacing + jitter)
    # chaînes : on relie une rangée à la suivante tant qu'il n'y a qu'un segment
    # de chaque côté et que le lien reste dans la forme (sinon nouvelle chaîne)
    # la liaison d'une pointe à la suivante peut déborder comme les pointes
    zone = rot.buffer(max(0.0, spec.overshoot) + spec.variation * spec.spacing + spec.spacing * 0.05 + 1e-6)
    chains: list[list] = []
    cur: list = []
    flip = False
    prev_n = 0
    for segs in rows:
        if len(segs) != 1 or prev_n != 1:
            if cur:
                chains.append(cur)
            cur = []
        if len(segs) != 1:
            for s in segs:
                chains.append(_tips(s, spec, rnd, False))
            prev_n = len(segs)
            flip = False
            continue
        pts = _tips(segs[0], spec, rnd, flip)
        if cur:
            link = shapely.LineString([cur[-1], pts[0]])
            if not zone.contains(link):
                chains.append(cur)
                cur = []
        cur += pts
        flip = not flip
        prev_n = 1
    if cur:
        chains.append(cur)
    ca, sa = math.cos(math.radians(spec.angle)), math.sin(math.radians(spec.angle))
    out = []
    for c in chains:
        pts = [(x * ca - y * sa, x * sa + y * ca) for x, y in c]
        segs = [Line(a, b) for a, b in zip(pts, pts[1:]) if math.dist(a, b) > 1e-9]
        if segs:
            out.append(Contour(segs, False))
    return Path(out)


def _tips(seg, spec: ScribbleSpec, rnd, flip: bool) -> list:
    """Les deux bouts d'une ligne, avec débord et variation, dans le sens du zigzag."""
    (ax, ay), (bx, by) = seg[0], seg[-1]
    v = spec.variation * spec.spacing
    a = (ax - spec.overshoot + (rnd.uniform(-v, v) if v else 0.0), ay)
    b = (bx + spec.overshoot + (rnd.uniform(-v, v) if v else 0.0), by)
    return [b, a] if flip else [a, b]
