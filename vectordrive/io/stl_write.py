"""Écriture STL (binaire) pour l'impression 3D ou un autre logiciel de FAO :

* **relief** (galbe, dôme, balayage… : carte de hauteurs) posé sur un socle
  d'épaisseur donnée — surface en grille de triangles, flancs et dessous
  fermés (maillage étanche) ;
* **formes fermées extrudées** d'une hauteur donnée (trous compris) :
  triangulation contrainte du dessus et du dessous, flancs le long des
  contours.

Unités : mm. Les triangles sont orientés vers l'extérieur.
"""
from __future__ import annotations

import struct


def write_stl(path, tris, name: str = 'VectorDrive') -> int:
    """Écrit les triangles (N × 3 × 3, numpy ou liste) ; rend leur nombre."""
    import numpy as np
    T = np.asarray(tris, dtype=np.float64).reshape(-1, 3, 3)
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    ln = np.linalg.norm(n, axis=1)
    n = np.divide(n, ln[:, None], out=np.zeros_like(n), where=ln[:, None] > 0)
    rec = np.zeros(len(T), dtype=[('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')])
    rec['n'] = n
    rec['v'] = T
    with open(path, 'wb') as f:
        f.write(name.encode('ascii', 'replace')[:80].ljust(80, b' '))
        f.write(struct.pack('<I', len(T)))
        f.write(rec.tobytes())
    return len(T)


def heightmap_mesh(H, x0: float, y1: float, res: float, base: float = 2.0, stride: int = 1):
    """Maillage étanche d'une carte de hauteurs H (lignes du haut vers le bas,
    origine x0, y1, pas res) : dessus à base + (H − min H), dessous à 0."""
    import numpy as np
    H = np.asarray(H, float)[::max(1, stride), ::max(1, stride)]
    res = res * max(1, stride)
    ny, nx = H.shape
    Z = H - float(H.min()) + max(0.0, base)
    xs = x0 + (np.arange(nx) + 0.5) * res
    ys = y1 - (np.arange(ny) + 0.5) * res
    X, Y = np.meshgrid(xs, ys)
    P = np.stack([X, Y, Z], axis=-1)
    a, b = P[:-1, :-1], P[:-1, 1:]                         # coin haut gauche, haut droit
    c, d = P[1:, :-1], P[1:, 1:]                           # bas gauche, bas droit (y décroissant)
    top = np.concatenate([np.stack([a, c, b], -2).reshape(-1, 3, 3), np.stack([b, c, d], -2).reshape(-1, 3, 3)])
    B = P.copy()
    B[..., 2] = 0.0
    ba, bb, bc, bd = B[:-1, :-1], B[:-1, 1:], B[1:, :-1], B[1:, 1:]
    bottom = np.concatenate([np.stack([ba, bb, bc], -2).reshape(-1, 3, 3),
                             np.stack([bb, bd, bc], -2).reshape(-1, 3, 3)])
    walls = []

    def wall(edge_top, edge_bot):
        """Bande entre une arête du dessus et la même au sol (sens donné)."""
        t0, t1 = edge_top[:-1], edge_top[1:]
        b0, b1 = edge_bot[:-1], edge_bot[1:]
        walls.append(np.stack([t0, b0, t1], -2))
        walls.append(np.stack([t1, b0, b1], -2))
    # tour dans le sens des aiguilles vu de dessus (y vers le haut) : normales vers l'extérieur
    wall(P[0, ::-1], B[0, ::-1])                           # haut (y max), de droite à gauche
    wall(P[:, 0], B[:, 0])                                 # gauche, de haut en bas
    wall(P[-1, :], B[-1, :])                               # bas, de gauche à droite
    wall(P[::-1, -1], B[::-1, -1])                         # droite, de bas en haut
    return np.concatenate([top, bottom] + walls)


def extrude_mesh(region, height: float, z0: float = 0.0):
    """Maillage étanche de la région shapely (polygones, trous compris)
    extrudée de z0 à z0 + height."""
    import numpy as np
    import shapely
    from shapely.geometry import LinearRing
    out = []
    z1 = z0 + height
    polys = [p for p in getattr(region, 'geoms', [region]) if p.geom_type == 'Polygon' and not p.is_empty]
    for poly in polys:
        tri = shapely.constrained_delaunay_triangles(poly)
        for t in getattr(tri, 'geoms', []):
            (ax, ay), (bx, by), (cx, cy) = list(t.exterior.coords)[:3]
            if (bx - ax) * (cy - ay) - (by - ay) * (cx - ax) < 0:    # sens trigonométrique vu de dessus
                (bx, by), (cx, cy) = (cx, cy), (bx, by)
            out.append([(ax, ay, z1), (bx, by, z1), (cx, cy, z1)])   # dessus, normale +z
            out.append([(ax, ay, z0), (cx, cy, z0), (bx, by, z0)])   # dessous, normale −z
        for ring, outer in [(poly.exterior, True)] + [(h, False) for h in poly.interiors]:
            pts = list(ring.coords)
            ccw = LinearRing(pts).is_ccw
            if ccw != outer:                                 # extérieur trigonométrique, trous horaires
                pts.reverse()
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                out.append([(ax, ay, z0), (bx, by, z0), (bx, by, z1)])
                out.append([(ax, ay, z0), (bx, by, z1), (ax, ay, z1)])
    return np.asarray(out, float).reshape(-1, 3, 3)


def volume(tris) -> float:
    """Volume (mm³) d'un maillage fermé bien orienté (théorème de la divergence)."""
    import numpy as np
    T = np.asarray(tris, float)
    return float(np.einsum('ij,ij->i', T[:, 0], np.cross(T[:, 1], T[:, 2])).sum() / 6.0)
