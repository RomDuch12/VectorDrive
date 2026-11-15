"""SculptArt (TypeEdit ▸ TypeArt) : retoucher un relief au pinceau.

Chaque touche du pinceau agit dans un disque de rayon `radius` (mm), avec
une atténuation douce vers le bord (gaussienne) :

* **ajouter** / **creuser** : monte ou descend de `strength` mm au centre ;
* **lisser** : rapproche chaque point de la moyenne de ses voisins ;
* **aplanir** : ramène les points vers la hauteur du centre du pinceau ;
* **bruit** : écarts au hasard de ± `strength` (texture, grain) ;
* **pousser** : la matière entraînée dans le sens du geste ;
* **attirer** : la matière resserrée vers le centre du pinceau.

Les fonctions modifient la carte H (numpy, lignes du haut vers le bas,
origine x0, y1, pas res) en place, dans la seule fenêtre du pinceau.
"""
from __future__ import annotations

import math

BRUSHES = (('ajouter', 'Ajouter'), ('creuser', 'Creuser'), ('lisser', 'Lisser'), ('aplanir', 'Aplanir'),
           ('bruit', 'Bruit'), ('pousser', 'Pousser'), ('attirer', 'Attirer'))
#: masque (pochoir, comme les masques de couleur de TypeEdit) : formes fermées
#: choisies avec le relief — le pinceau ne touche que dedans, ou que dehors
MASKS = (('dedans', 'Dans les formes choisies'), ('dehors', 'Hors des formes choisies'), ('aucun', 'Sans masque'))
#: Miroir de SculptArt (TypeEdit) : le geste reproduit par symétrie autour du centre
MIRRORS = (('aucun', 'Sans'), ('h', 'Axe horizontal'), ('v', 'Axe vertical'), ('deux', 'Deux axes perpendiculaires'),
           ('multi', 'Multi-axe'))


def mirror_maps(mode: str, n: int = 4) -> list:
    """Parties linéaires (a, b, c, d) des copies du geste : identité d'abord.
    Multi-axe : n secteurs tournés de 360°/n, chacun aussi reflété — axes
    de symétrie à 180°·k/n de l'horizontale (n impair : pas d'axe vertical,
    comme TypeEdit), n de 2 à 10."""
    if mode == 'h':
        return [(1, 0, 0, 1), (1, 0, 0, -1)]
    if mode == 'v':
        return [(1, 0, 0, 1), (-1, 0, 0, 1)]
    if mode == 'deux':
        return [(1, 0, 0, 1), (1, 0, 0, -1), (-1, 0, 0, 1), (-1, 0, 0, -1)]
    if mode == 'multi':
        n = max(2, min(10, int(n)))
        out = []
        for k in range(n):
            t = 2 * math.pi * k / n
            c, s = math.cos(t), math.sin(t)
            out.append((c, -s, s, c))                         # rotation
            out.append((c, s, s, -c))                         # réflexion d'axe à t/2
        return out
    return [(1, 0, 0, 1)]


def mirrored(p, center, m) -> tuple[float, float]:
    a, b, c, d = m
    x, y = p[0] - center[0], p[1] - center[1]
    return (center[0] + a * x + b * y, center[1] + c * x + d * y)


def _window(H, x0: float, y1: float, res: float, cx: float, cy: float, radius: float):
    ny, nx = H.shape
    i0 = max(0, int(math.floor((cx - radius - x0) / res)))
    i1 = min(nx, int(math.ceil((cx + radius - x0) / res)) + 1)
    j0 = max(0, int(math.floor((y1 - (cy + radius)) / res)))
    j1 = min(ny, int(math.ceil((y1 - (cy - radius)) / res)) + 1)
    return i0, i1, j0, j1


def _sample(H, x0: float, y1: float, res: float, X, Y):
    """Hauteurs de H aux points (X, Y) (bilinéaire, bord prolongé)."""
    import numpy as np
    ny, nx = H.shape
    fx = np.clip((X - x0) / res - 0.5, 0, nx - 1)
    fy = np.clip((y1 - Y) / res - 0.5, 0, ny - 1)
    i0, j0 = np.floor(fx).astype(int), np.floor(fy).astype(int)
    i1, j1 = np.minimum(i0 + 1, nx - 1), np.minimum(j0 + 1, ny - 1)
    tx, ty = fx - i0, fy - j0
    return (H[j0, i0] * (1 - tx) + H[j0, i1] * tx) * (1 - ty) + (H[j1, i0] * (1 - tx) + H[j1, i1] * tx) * ty


def dab(H, x0: float, y1: float, res: float, cx: float, cy: float, radius: float, strength: float,
        brush: str = 'ajouter', rng=None, direction=(0.0, 0.0)) -> bool:
    """Une touche du pinceau en (cx, cy) ; False si elle tombe hors de la carte."""
    import numpy as np
    radius = max(res, radius)
    i0, i1, j0, j1 = _window(H, x0, y1, res, cx, cy, radius)
    if i1 <= i0 or j1 <= j0:
        return False
    xs = x0 + (np.arange(i0, i1) + 0.5) * res
    ys = y1 - (np.arange(j0, j1) + 0.5) * res
    X, Y = np.meshgrid(xs, ys)
    d = np.hypot(X - cx, Y - cy) / radius
    w = np.where(d < 1.0, np.exp(-4.0 * d * d), 0.0)
    sub = H[j0:j1, i0:i1]
    if brush in ('ajouter', 'creuser'):
        sub += (strength if brush == 'ajouter' else -strength) * w
    elif brush == 'lisser':
        P = np.pad(sub, 1, mode='edge')
        mean = sum(P[1 + dy:P.shape[0] - 1 + dy, 1 + dx:P.shape[1] - 1 + dx]
                   for dy in (-1, 0, 1) for dx in (-1, 0, 1)) / 9.0
        sub += w * (mean - sub)
    elif brush == 'aplanir':
        jc = min(max(int((y1 - cy) / res), 0), H.shape[0] - 1)
        ic = min(max(int((cx - x0) / res), 0), H.shape[1] - 1)
        sub += 0.5 * w * (H[jc, ic] - sub)
    elif brush == 'bruit':
        rng = rng or np.random.default_rng()
        sub += strength * w * (rng.random(sub.shape) * 2 - 1)
    elif brush == 'pousser':
        # chaque point prend la hauteur d'un peu en arrière dans le sens du geste
        ddx, ddy = direction
        src = _sample(H, x0, y1, res, X - ddx * w, Y - ddy * w)
        sub[...] = src
    elif brush == 'attirer':
        k = min(0.9, max(0.0, strength))                    # resserrement au centre (0 à 0,9)
        src = _sample(H, x0, y1, res, cx + (X - cx) * (1 + k * w), cy + (Y - cy) * (1 + k * w))
        sub[...] = src
    return True


def stroke(H, x0: float, y1: float, res: float, a, b, radius: float, strength: float, brush: str,
           spacing: float | None = None, rng=None) -> int:
    """Touches régulières (tous les `spacing` mm, un tiers du rayon par
    défaut) de a à b, b compris, a exclu ; rend leur nombre."""
    spacing = spacing or max(res, radius / 3)
    L = math.dist(a, b)
    n = max(1, int(L / spacing))
    k = 0
    step = ((b[0] - a[0]) / n, (b[1] - a[1]) / n)
    for i in range(1, n + 1):
        t = i / n
        if dab(H, x0, y1, res, a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, radius, strength, brush, rng,
               direction=step):
            k += 1
    return k
