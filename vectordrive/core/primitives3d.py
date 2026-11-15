"""Primitives en relief (TypeEdit : surfaces Sphère, Ellipsoïde, Cône,
Cylindre, Tore, Cube) : la moitié haute du solide, posée sur Z = 0, en carte
de hauteurs combinable avec un relief existant (comme les galbes).

Le solide tient dans `size_x` × `size_y` autour de son centre ; `height` :
hauteur du sommet (0 : celle du solide rond, demi-largeur). Cône : rayon
du dessus `radius2` (0 : pointu) ; tore : rayon du tube `radius2` (0 : un
quart de la demi-largeur) ; cylindre couché selon `axis` ('x' ou 'y').

Dôme par profil : un profil dessiné — X : distance à l'axe depuis son
point le plus à gauche, Y : hauteur depuis son point le plus bas — tourné
autour d'un axe vertical, sur un tour complet ou de l'angle de départ à
l'angle d'arrivée (bouton, coupe, dôme à profil libre). L'axe couché
(TypeEdit : révolution) est « TypeArt de révolution » (core.typeart).
"""
from __future__ import annotations

from dataclasses import dataclass

KINDS = (('sphere', 'Sphère'), ('ellipsoide', 'Ellipsoïde'), ('cone', 'Cône'), ('cylindre', 'Cylindre couché'),
         ('tore', 'Tore'), ('pave', 'Pavé'))


@dataclass
class PrimitiveSpec:
    kind: str = 'sphere'
    size_x: float = 20.0            # encombrement (mm) ; sphère : diamètre
    size_y: float = 20.0
    height: float = 0.0             # hauteur du sommet (mm, 0 : demi-largeur)
    radius2: float = 0.0            # cône : rayon du dessus ; tore : rayon du tube (mm)
    axis: str = 'x'                 # cylindre couché : axe
    resolution: float = 0.1
    margin: float = 1.0
    mode: str = 'ajouter'
    limit: bool = False


def heights(spec: PrimitiveSpec, X, Y, cx: float, cy: float):
    """(hauteurs, dedans) du solide centré en (cx, cy) aux points (X, Y)."""
    import numpy as np
    a = max(1e-6, spec.size_x / 2)
    b = max(1e-6, (spec.size_x if spec.kind == 'sphere' else spec.size_y) / 2)
    dx, dy = (X - cx) / a, (Y - cy) / b
    k = spec.kind
    if k in ('sphere', 'ellipsoide'):
        h = spec.height if spec.height > 0 else min(a, b)
        q = 1 - dx * dx - dy * dy
        return h * np.sqrt(np.clip(q, 0, None)), q > 0
    if k == 'cone':
        h = spec.height if spec.height > 0 else min(a, b)
        r = np.sqrt(dx * dx + dy * dy)
        t = min(0.999, max(0.0, spec.radius2 / a))
        return h * np.clip((1 - r) / (1 - t), 0, 1), r < 1
    if k == 'cylindre':
        d = dy if spec.axis == 'x' else dx
        w = b if spec.axis == 'x' else a
        h = spec.height if spec.height > 0 else w
        q = 1 - d * d
        inside = (q > 0) & (np.abs(dx if spec.axis == 'x' else dy) <= 1)
        return h * np.sqrt(np.clip(q, 0, None)), inside
    if k == 'tore':
        rr = spec.radius2 if spec.radius2 > 0 else a / 4
        rr = min(rr, a / 2)
        R = a - rr
        rho = np.hypot(X - cx, (Y - cy) * (a / b))
        q = rr * rr - (rho - R) ** 2
        h = spec.height if spec.height > 0 else rr
        return h / rr * np.sqrt(np.clip(q, 0, None)), q > 0
    h = spec.height if spec.height > 0 else min(a, b)           # pavé
    inside = (np.abs(dx) <= 1) & (np.abs(dy) <= 1)
    return np.where(inside, h, 0.0), inside


def primitive_relief(spec: PrimitiveSpec, centers, tool: int = 0, onto=None):
    """Image du relief : le solide à chaque centre de `centers`, combiné
    avec `onto` selon spec.mode (entre eux : le plus haut)."""
    import numpy as np
    from .typeart import _apply
    a = spec.size_x / 2
    b = (spec.size_x if spec.kind == 'sphere' else spec.size_y) / 2
    centers = [tuple(c[:2]) for c in centers] or [(a, b)]
    bounds = (min(c[0] for c in centers) - a, min(c[1] for c in centers) - b,
              max(c[0] for c in centers) + a, max(c[1] for c in centers) + b)

    def field(X, Y):
        H, ok = np.zeros_like(X), np.zeros(X.shape, bool)
        for cx, cy in centers:
            h, i = heights(spec, X, Y, cx, cy)
            H, ok = np.maximum(H, np.where(i, h, 0.0)), ok | i
        return H, ok
    return _apply(bounds, spec, field, tool, onto, dict(KINDS).get(spec.kind, 'Relief'))


@dataclass
class RevolutionSpec:
    start_angle: float = 0.0        # révolution partielle : de… (°, sens trigonométrique)
    end_angle: float = 360.0        # … à (°) ; 360 d'écart : révolution complète
    height: float = 0.0             # hauteur ramenée à (mm, 0 : celle du profil)
    resolution: float = 0.1
    margin: float = 1.0
    mode: str = 'ajouter'
    limit: bool = False


def profile_of(points) -> tuple:
    """(rayons croissants, hauteurs) d'un profil dessiné ; à rayon égal, le
    plus haut."""
    import numpy as np
    P = np.asarray([p[:2] for p in points], float)
    r, z = P[:, 0] - P[:, 0].min(), P[:, 1] - P[:, 1].min()
    order = np.argsort(r, kind='stable')
    r, z = r[order], z[order]
    keep_r, keep_z = [], []
    for ri, zi in zip(r.tolist(), z.tolist()):
        if keep_r and abs(ri - keep_r[-1]) < 1e-9:
            keep_z[-1] = max(keep_z[-1], zi)
        else:
            keep_r.append(ri)
            keep_z.append(zi)
    return np.asarray(keep_r), np.asarray(keep_z)


def revolution_relief(points, spec: RevolutionSpec, center, tool: int = 0, onto=None):
    """Image du relief du profil `points` tourné autour de `center`."""
    import math

    import numpy as np
    from .typeart import _apply
    R, Z = profile_of(points)
    if len(R) < 2 or R[-1] <= 1e-9:
        return None
    if spec.height > 0 and Z.max() > 1e-12:
        Z = Z * (spec.height / Z.max())
    cx, cy = center[:2]
    full = abs(spec.end_angle - spec.start_angle) >= 360 - 1e-9
    a0 = math.radians(spec.start_angle) % (2 * math.pi)
    span = math.radians(spec.end_angle - spec.start_angle) % (2 * math.pi)

    def field(X, Y):
        rho = np.hypot(X - cx, Y - cy)
        inside = rho <= R[-1]
        if not full:
            ang = (np.arctan2(Y - cy, X - cx) - a0) % (2 * math.pi)
            inside &= ang <= span + 1e-12
        return np.interp(rho, R, Z), inside
    rmax = float(R[-1])
    return _apply((cx - rmax, cy - rmax, cx + rmax, cy + rmax), spec, field, tool, onto, 'Révolution')


@dataclass
class BilinearSpec:
    """Surface bilinéaire (TypeEdit) : hauteurs aux quatre coins d'un
    rectangle, raccordées en surface réglée (plan gauche)."""
    z_bl: float = 0.0               # coin bas-gauche (mm)
    z_br: float = 2.0               # bas-droit
    z_tl: float = 2.0               # haut-gauche
    z_tr: float = 4.0               # haut-droit
    resolution: float = 0.1
    margin: float = 0.0
    mode: str = 'ajouter'
    limit: bool = False


def bilinear_relief(spec: BilinearSpec, bounds, tool: int = 0, onto=None, region=None):
    """Image de la surface sur le rectangle `bounds` (x0, y0, x1, y1) ;
    `region` (shapely) : seulement dedans."""
    import numpy as np
    from .typeart import _apply
    x0, y0, x1, y1 = bounds
    if x1 - x0 <= 1e-9 or y1 - y0 <= 1e-9:
        return None

    def field(X, Y):
        u = np.clip((X - x0) / (x1 - x0), 0, 1)
        v = np.clip((Y - y0) / (y1 - y0), 0, 1)
        Hh = (spec.z_bl * (1 - u) * (1 - v) + spec.z_br * u * (1 - v) + spec.z_tl * (1 - u) * v
              + spec.z_tr * u * v)
        inside = (X >= x0) & (X <= x1) & (Y >= y0) & (Y <= y1)
        if region is not None:
            from .galbe import _inside
            res = float(X[0, 1] - X[0, 0]) if X.shape[1] > 1 else spec.resolution
            inside &= _inside(region, float(X[0, 0] - res / 2), float(Y[0, 0] + res / 2), X.shape[1], X.shape[0],
                              res)
        return Hh, inside
    return _apply(bounds, spec, field, tool, onto, 'Surface bilinéaire')
