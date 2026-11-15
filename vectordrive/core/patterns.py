"""Création de texture (TypeEdit : Effets spéciaux ▸ Création de texture,
ID_COMPO_TEXTURING) : un motif de traits, dans une case, répété par
symétrie pour couvrir les contours fermés choisis, et coupé à eux (règle
pair-impair : un contour intérieur reste vide).

Le motif est un modèle (`PRESETS` : chevrons, vagues, écailles, briques,
croisillons, zigzag) ou les traits sélectionnés (la case est alors leur
boîte). Symétries (`SYMMETRIES`) : translation, miroir gauche-droite ou
haut-bas d'une case sur deux, miroirs croisés, demi-tour, quinconce
(rangées décalées d'une demi-case). L'ensemble peut être tourné.
"""
from __future__ import annotations

import math

from .geom import Contour, Line, Path

SYMMETRIES = (('translation', 'Translation'), ('miroir_h', 'Miroir gauche-droite'), ('miroir_v', 'Miroir haut-bas'),
              ('miroirs', 'Miroirs croisés'), ('demi_tour', 'Demi-tour'), ('quinconce', 'Quinconce'))


def _arc(n=12):
    return [(0.5 - 0.5 * math.cos(math.pi * k / n), 0.5 * math.sin(math.pi * k / n)) for k in range(n + 1)]


#: modèles : (libellé, traits dans la case unité, rapport hauteur / largeur de la case, symétrie conseillée)
PRESETS = {
    'chevrons': ('Chevrons', [[(0.0, 0.2), (0.5, 0.8), (1.0, 0.2)]], 0.5, 'translation'),
    'vagues': ('Vagues', [[(k / 16, 0.5 + 0.35 * math.sin(2 * math.pi * k / 16)) for k in range(17)]], 0.5,
               'translation'),
    'ecailles': ('Écailles', [_arc()], 0.5, 'quinconce'),
    'briques': ('Briques', [[(0.0, 0.0), (1.0, 0.0)], [(0.0, 0.0), (0.0, 1.0)]], 0.5, 'quinconce'),
    'croisillons': ('Croisillons', [[(0.0, 0.0), (1.0, 1.0)], [(0.0, 1.0), (1.0, 0.0)]], 1.0, 'translation'),
    'zigzag': ('Zigzag', [[(0.0, 0.0), (0.25, 1.0), (0.5, 0.0), (0.75, 1.0), (1.0, 0.0)]], 0.5, 'translation'),
}


def preset_motif(key: str, width: float) -> tuple[list, tuple[float, float], str]:
    """(traits, (largeur, hauteur) de la case, symétrie conseillée) d'un modèle."""
    _label, lines, ratio, sym = PRESETS[key]
    h = width * ratio
    return [[(x * width, y * h) for x, y in pl] for pl in lines], (width, h), sym


def motif_of(polylines: list) -> tuple[list, tuple[float, float]]:
    """Traits sélectionnés ramenés à l'origine de leur boîte, et cette boîte."""
    pts = [p for pl in polylines for p in pl]
    x0, y0 = min(p[0] for p in pts), min(p[1] for p in pts)
    w = max(p[0] for p in pts) - x0
    h = max(p[1] for p in pts) - y0
    return [[(x - x0, y - y0) for x, y in pl] for pl in polylines], (max(w, 1e-3), max(h, 1e-3))


def _variant(pl, i: int, j: int, w: float, h: float, sym: str) -> list:
    """Le motif de la case (i, j) selon la symétrie, dans la case."""
    fx = sym in ('miroir_h', 'miroirs') and i % 2 == 1
    fy = sym in ('miroir_v', 'miroirs') and j % 2 == 1
    if sym == 'demi_tour' and (i + j) % 2 == 1:
        fx = fy = True
    return [((w - x) if fx else x, (h - y) if fy else y) for x, y in pl]


def tile(region, motif: list, cell: tuple[float, float], symmetry: str = 'translation', angle: float = 0.0) -> Path:
    """Le motif répété sur la région shapely (cases de `cell`, symétrie,
    rotation `angle` en degrés autour du centre de la région), coupé à elle :
    traits ouverts."""
    from shapely import affinity
    from shapely.geometry import MultiLineString
    if region is None or region.is_empty or not motif:
        return Path()
    w, h = cell
    cx, cy = region.centroid.x, region.centroid.y
    work = affinity.rotate(region, -angle, origin=(cx, cy)) if angle else region
    x0, y0, x1, y1 = work.bounds
    nx, ny = int(math.ceil((x1 - x0) / w)) + 2, int(math.ceil((y1 - y0) / h)) + 1
    if nx * ny * len(motif) > 400_000:
        raise ValueError('case trop petite pour cette surface')
    lines = []
    for j in range(ny):
        shift = (w / 2 if symmetry == 'quinconce' and j % 2 else 0.0) - w
        for i in range(nx):
            ox, oy = x0 + shift + i * w, y0 + j * h
            for pl in motif:
                pts = [(ox + x, oy + y) for x, y in _variant(pl, i, j, w, h, symmetry)]
                if len(pts) >= 2:
                    lines.append(pts)
    ml = MultiLineString(lines)
    if angle:
        ml = affinity.rotate(ml, angle, origin=(cx, cy))
    cut = ml.intersection(region)
    out = []
    for g in getattr(cut, 'geoms', [cut]):
        if g.geom_type == 'LineString' and not g.is_empty:
            c = list(g.coords)
            segs = [Line(a, b) for a, b in zip(c, c[1:]) if math.dist(a, b) > 1e-9]
            if segs:
                out.append(Contour(segs, False))
        elif g.geom_type == 'MultiLineString':
            for s in g.geoms:
                c = list(s.coords)
                segs = [Line(a, b) for a, b in zip(c, c[1:]) if math.dist(a, b) > 1e-9]
                if segs:
                    out.append(Contour(segs, False))
    return Path(out)
