"""Relief d'un modèle 3D (TypeEdit ▸ TypeArt : transformation d'une surface
en objet TypeArt) : la pièce maillée (STL, STEP, 3D XML), vue d'un côté,
devient une carte de hauteurs — le plus haut point de la pièce en chaque
nœud, le bas de la pièce à Z = 0 — combinable avec un relief existant.

Taille réelle, ou ramenée à une plus grande dimension donnée ; hauteur
réelle (à l'échelle), ou ramenée à un Z max. donné (bas-relief).
"""
from __future__ import annotations

from dataclasses import dataclass

VIEWS = (('dessus', 'Dessus'), ('dessous', 'Dessous'), ('avant', 'Avant'), ('arriere', 'Arrière'),
         ('gauche', 'Gauche'), ('droite', 'Droite'))
#: rotations (lignes : nouveaux X, Y, Z) — le côté regardé devient le haut
_ROT = {'dessus': ((1, 0, 0), (0, 1, 0), (0, 0, 1)), 'dessous': ((1, 0, 0), (0, -1, 0), (0, 0, -1)),
        'avant': ((1, 0, 0), (0, 0, 1), (0, -1, 0)), 'arriere': ((-1, 0, 0), (0, 0, 1), (0, 1, 0)),
        'gauche': ((0, -1, 0), (0, 0, 1), (-1, 0, 0)), 'droite': ((0, 1, 0), (0, 0, 1), (1, 0, 0))}


@dataclass
class MeshReliefSpec:
    view: str = 'dessus'
    size: float = 0.0               # plus grande dimension vue (mm, 0 : taille réelle)
    z_max: float = 0.0              # hauteur du relief (mm, 0 : hauteur réelle à l'échelle)
    resolution: float = 0.1
    margin: float = 1.0
    mode: str = 'ajouter'
    limit: bool = False


def oriented(tris, view: str = 'dessus'):
    """Triangles (n, 3, 3) tournés pour que le côté `view` regarde vers +Z,
    puis posés : coin bas-gauche en (0, 0), bas à Z = 0."""
    import numpy as np
    T = np.asarray(tris, float).reshape(-1, 3, 3) @ np.asarray(_ROT.get(view, _ROT['dessus']), float).T
    lo = T.reshape(-1, 3).min(axis=0)
    return T - lo


def mesh_relief(tris, spec: MeshReliefSpec, tool: int = 0, onto=None, at=(0.0, 0.0)):
    """Image du relief de la pièce ; `at` : coin bas-gauche (mm)."""
    import numpy as np
    from .typeart import _apply
    from ..cam.advanced import heightmap_from_triangles
    T = oriented(tris, spec.view)
    if not len(T):
        return None
    hi = T.reshape(-1, 3).max(axis=0)
    if spec.size > 0 and max(hi[0], hi[1]) > 0:
        T = T * (spec.size / max(hi[0], hi[1]))
        hi = T.reshape(-1, 3).max(axis=0)
    if spec.z_max > 0 and hi[2] > 0:
        T[..., 2] *= spec.z_max / hi[2]
    T[..., 0] += at[0]
    T[..., 1] += at[1]
    lo, hi = T.reshape(-1, 3).min(axis=0), T.reshape(-1, 3).max(axis=0)

    def field(X, Y):
        xs, ys = X[0], Y[:, 0]
        res = float(xs[1] - xs[0]) if len(xs) > 1 else spec.resolution
        H = heightmap_from_triangles(T, float(xs[0]), float(ys[-1]), len(xs), len(ys), res)[::-1]
        ok = np.isfinite(H)
        return np.where(ok, H, 0.0), ok
    return _apply((float(lo[0]), float(lo[1]), float(hi[0]), float(hi[1])), spec, field, tool, onto,
                  'Modèle 3D')
