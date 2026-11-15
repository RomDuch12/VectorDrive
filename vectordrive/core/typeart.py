"""Outils TypeArt de création de reliefs (TypeEdit ▸ TypeArt ▸ Outils), sur
la carte de hauteurs du galbe (`core.galbe`) :

* **dôme** sur des marqueurs : gaussien (cloche), sphérique, Bézier
  quadratique (cloche de verre) — diamètre et hauteur ;
* **TypeArt extrudé** : l'intérieur des formes fermées décalé en Z (marche
  à flancs droits) ;
* **TypeArt de révolution** : une courbe tournée autour d'un axe posé dans
  le plan (deux marqueurs, ou les extrémités d'une droite) — vu de dessus,
  la hauteur à la distance v de l'axe vaut √(r(u)² − v²) ;
* **facette** (plan incliné par trois points) : dans les formes fermées,
  le plan passant par trois points de cotes données ;
* **mode prismatique** : des lettres à Z constant, le profil choisi sur leur
  bord, et le plateau au centre.

Chaque relief se combine au relief choisi avec lui selon le mode de
combinaison de TypeArt (remplacer, ajouter, soustraire, maximum, minimum,
moyenne ; limiter au relief existant).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from . import galbe as GB

DOME_SHAPES = (('gauss', 'Gaussienne'), ('sphere', 'Sphérique'), ('bezier', 'Bézier quadratique'))


@dataclass
class DomeSpec:
    shape: str = 'sphere'
    diameter: float = 20.0
    height: float = 3.0
    resolution: float = 0.1
    margin: float = 1.0
    mode: str = 'ajouter'
    limit: bool = False


@dataclass
class ExtrudeSpec:
    z: float = 1.0                  # décalage en Z (mm ; négatif : en creux)
    resolution: float = 0.1
    margin: float = 1.0
    mode: str = 'ajouter'
    limit: bool = False


@dataclass
class RevolutionSpec:
    resolution: float = 0.1
    margin: float = 1.0
    mode: str = 'ajouter'
    limit: bool = False


@dataclass
class PlaneSpec:
    z1: float = 0.0                 # cotes des trois points (dans l'ordre de sélection)
    z2: float = 2.0
    z3: float = 0.0
    resolution: float = 0.1
    margin: float = 1.0
    mode: str = 'ajouter'
    limit: bool = False


# --- profils ---------------------------------------------------------------------------------
def dome_profile(shape: str, r, R: float, H: float):
    """Hauteur d'un dôme à la distance r du centre (numpy), 0 au-delà de R."""
    import numpy as np
    R = max(1e-9, R)
    t = np.clip(np.asarray(r, float) / R, 0.0, 1.0)
    if shape == 'gauss':
        k = 4.5
        h = (np.exp(-k * t * t) - math.exp(-k)) / (1 - math.exp(-k))
    elif shape == 'bezier':
        # quadratique (0, H) → contrôle (R, H) → (R, 0) : x = R(2s − s²), z = H(1 − s²)
        s = 1.0 - np.sqrt(np.clip(1.0 - t, 0.0, 1.0))
        h = 1.0 - s * s
    else:
        h = np.sqrt(np.clip(1.0 - t * t, 0.0, 1.0))
    return np.where(np.asarray(r) <= R, H * h, 0.0)


def revolution_radius(profile_pts, axis_a, axis_b):
    """Fonction u → rayon r(u) de la courbe autour de l'axe (u : abscisse le
    long de l'axe depuis `axis_a`) : (us triés, rs) à interpoler, 0 hors de
    l'étendue de la courbe."""
    import numpy as np
    ax, ay = axis_a
    dx, dy = axis_b[0] - ax, axis_b[1] - ay
    n = math.hypot(dx, dy)
    if n < 1e-9:
        raise ValueError('axe de révolution nul')
    ux, uy = dx / n, dy / n
    P = np.asarray(profile_pts, float)
    u = (P[:, 0] - ax) * ux + (P[:, 1] - ay) * uy
    v = np.abs(-(P[:, 0] - ax) * uy + (P[:, 1] - ay) * ux)
    order = np.argsort(u, kind='stable')
    return u[order], v[order], (ax, ay, ux, uy)


# --- grilles ---------------------------------------------------------------------------------
@dataclass
class PrismSpec:
    resolution: float = 0.1
    margin: float = 1.0
    mode: str = 'ajouter'
    limit: bool = False


def prism_profile(points) -> tuple:
    """Le profil, de son bout le plus bas (le bord de l'objet) à l'autre : (largeurs croissantes, hauteurs depuis ce bout)."""
    import numpy as np
    p = np.asarray(points, dtype=float)
    if len(p) < 2:
        raise ValueError('profil')
    if p[0, 1] > p[-1, 1]:
        p = p[::-1]
    xs = np.maximum.accumulate(np.abs(p[:, 0] - p[0, 0]))
    zs = p[:, 1] - p[0, 1]
    if xs[-1] <= 0:
        raise ValueError('profil')
    keep = np.concatenate(([True], np.diff(xs) > 0))
    return xs[keep], zs[keep]


def prism(region, profile_points, spec: PrismSpec, tool: int = 0, onto=None):
    """Hauteur selon la distance au bord : le profil, puis son dernier Z jusqu'au centre."""
    import numpy as np
    if region is None or region.is_empty:
        return None
    xs, zs = prism_profile(profile_points)

    def field(X, Y):
        res = abs(X[0, 1] - X[0, 0]) if X.shape[1] > 1 else 1.0
        inside = GB._inside(region, X[0, 0] - res / 2, Y[0, 0] + res / 2, X.shape[1], X.shape[0], res)
        d = np.maximum(GB._edt(inside) - 0.5, 0.0) * res
        return np.interp(d, xs, zs), inside
    return _apply(region.bounds, spec, field, tool, onto, 'Prismatique')


def _apply(bounds, spec, field, tool: int, onto, name: str):
    """Image du relief `field(X, Y) -> (H, inside)` sur une grille couvrant
    `bounds` (et le relief `onto`, combiné selon spec.mode)."""
    import numpy as np
    m = max(0.0, spec.margin)
    b = (bounds[0] - m, bounds[1] - m, bounds[2] + m, bounds[3] + m)
    res = max(0.01, spec.resolution)
    old = None
    if onto is not None:
        got = GB.decode(onto)
        if got is None:
            return None
        oH, ox0, oy1, ores = got
        ob = onto.bbox()
        b = (min(b[0], ob[0]), min(b[1], ob[1]), max(b[2], ob[2]), max(b[3], ob[3]))
        res = min(res, ores)
    x0, y1, nx, ny, res = GB._grid(b, res)
    xs = x0 + (np.arange(nx) + 0.5) * res
    ys = y1 - (np.arange(ny) + 0.5) * res
    X, Y = np.meshgrid(xs, ys)
    new, inside = field(X, Y)
    if onto is not None:
        old = GB._sample(oH, ox0, oy1, ores, x0, y1, nx, ny, res)
        H = GB.combine(old, new, inside, spec.mode, spec.limit)
    else:
        H = np.where(inside, new, 0.0)
    gspec = GB.GalbeSpec(z_max=float(H.max()), z_min=float(H.min()), resolution=res, margin=m, mode=spec.mode,
                         limit=spec.limit)
    return GB.encode(H, x0, y1, res, gspec, tool, (onto.name if onto is not None else '') or name)


def dome(centers, spec: DomeSpec, tool: int = 0, onto=None):
    """Dômes centrés sur les points `centers` (marqueurs)."""
    import numpy as np
    if not centers:
        return None
    R = max(1e-6, spec.diameter / 2)
    xs = [c[0] for c in centers]
    ys = [c[1] for c in centers]

    def field(X, Y):
        H = np.zeros(X.shape)
        inside = np.zeros(X.shape, bool)
        for cx, cy in centers:
            r = np.hypot(X - cx, Y - cy)
            H = np.maximum(H, dome_profile(spec.shape, r, R, spec.height))
            inside |= r <= R
        return H, inside
    return _apply((min(xs) - R, min(ys) - R, max(xs) + R, max(ys) + R), spec, field, tool, onto, 'Dôme')


def extrude(region, spec: ExtrudeSpec, tool: int = 0, onto=None):
    """L'intérieur des formes fermées (région shapely) décalé de spec.z."""
    import numpy as np
    if region is None or region.is_empty:
        return None

    def field(X, Y):
        res = abs(X[0, 1] - X[0, 0]) if X.shape[1] > 1 else 1.0
        inside = GB._inside(region, X[0, 0] - res / 2, Y[0, 0] + res / 2, X.shape[1], X.shape[0], res)
        return np.full(X.shape, float(spec.z)), inside
    return _apply(region.bounds, spec, field, tool, onto, 'Extrudé')


def revolution(profile_pts, axis_a, axis_b, spec: RevolutionSpec, tool: int = 0, onto=None):
    """La courbe (points) tournée autour de l'axe (a, b) du plan."""
    import numpy as np
    us, rs, (ax, ay, ux, uy) = revolution_radius(profile_pts, axis_a, axis_b)
    if len(us) < 2 or float(rs.max()) <= 0:
        return None
    rmax = float(rs.max())
    ends = [(ax + ux * u + s * (-uy) * rmax, ay + uy * u + s * ux * rmax) for u in (us[0], us[-1]) for s in (-1, 1)]

    def field(X, Y):
        U = (X - ax) * ux + (Y - ay) * uy
        V = -(X - ax) * uy + (Y - ay) * ux
        r = np.interp(U, us, rs, left=0.0, right=0.0)
        inside = (np.abs(V) <= r) & (U >= us[0]) & (U <= us[-1])
        return np.sqrt(np.clip(r * r - V * V, 0.0, None)), inside
    return _apply((min(p[0] for p in ends), min(p[1] for p in ends), max(p[0] for p in ends),
                   max(p[1] for p in ends)), spec, field, tool, onto, 'Révolution')


def plane_through(p1, p2, p3):
    """(a, b, c) du plan z = a x + b y + c par trois points (x, y, z)."""
    import numpy as np
    A = np.array([[p[0], p[1], 1.0] for p in (p1, p2, p3)])
    if abs(np.linalg.det(A)) < 1e-12:
        raise ValueError('les trois points sont alignés')
    return tuple(float(v) for v in np.linalg.solve(A, np.array([p1[2], p2[2], p3[2]], float)))


def plane(region, points, spec: PlaneSpec, tool: int = 0, onto=None):
    """Facette : dans la région, le plan passant par les trois points (x, y)
    aux cotes spec.z1, z2, z3."""
    import numpy as np
    if region is None or region.is_empty or len(points) < 3:
        return None
    a, b, c = plane_through((*points[0], spec.z1), (*points[1], spec.z2), (*points[2], spec.z3))

    def field(X, Y):
        res = abs(X[0, 1] - X[0, 0]) if X.shape[1] > 1 else 1.0
        inside = GB._inside(region, X[0, 0] - res / 2, Y[0, 0] + res / 2, X.shape[1], X.shape[0], res)
        return a * X + b * Y + c, inside
    return _apply(region.bounds, spec, field, tool, onto, 'Facette')
