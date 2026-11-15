"""Textures de relief (TypeEdit ▸ TypeArt) :

* **relief d'une image** (PhotoArt) : chaque gris devient une hauteur, du
  noir (Z du noir) au blanc (Z du blanc), linéaire ou courbé (γ) ;
* **texturing algorithmique** : bruit fractal (somme d'octaves de bruit
  lissé : fréquence, détails, gain, tirage) — standard, focal (plus fort au
  centre), rayures ou concentrique ;
* **tissage** : deux nappes de fils croisés qui passent alternativement
  dessus et dessous (pas, largeur des fils, hauteur, angle) ;
* **remplissage par texture** : un petit relief (le motif) répété en
  pavage.

Chaque fonction rend la hauteur (numpy) aux points X, Y (mm).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

FRACTALS = (('standard', 'Standard'), ('focal', 'Focal'), ('rayures', 'Rayures'), ('concentrique', 'Concentrique'))


@dataclass
class PhotoSpec:
    z_black: float = 0.0
    z_white: float = 2.0
    gamma: float = 1.0
    smooth: int = 1                 # passes de lissage
    resolution: float = 0.1
    margin: float = 0.0
    mode: str = 'ajouter'
    limit: bool = False


@dataclass
class FractalSpec:
    kind: str = 'standard'
    height: float = 0.5
    frequency: float = 0.5          # motifs par mm
    octaves: int = 4                # niveaux de détail
    gain: float = 0.5               # amplitude d'un niveau au suivant
    seed: int = 1
    resolution: float = 0.1
    margin: float = 0.0
    mode: str = 'ajouter'
    limit: bool = False


@dataclass
class WeaveSpec:
    pitch: float = 4.0              # écart entre fils (mm)
    width: float = 3.0              # largeur d'un fil (mm)
    height: float = 1.0
    angle: float = 0.0
    resolution: float = 0.1
    margin: float = 0.0
    mode: str = 'ajouter'
    limit: bool = False


def photo_heights(gray, spec: PhotoSpec):
    """Gris 0 (noir) … 1 (blanc) → hauteurs."""
    import numpy as np
    g = np.clip(np.asarray(gray, float), 0, 1) ** max(0.05, spec.gamma)
    return spec.z_black + g * (spec.z_white - spec.z_black)


def _value_noise(X, Y, freq: float, rnd):
    """Bruit de valeurs lissé (interpolation cosinus sur une grille aléatoire)."""
    import numpy as np
    u, v = X * freq, Y * freq
    i0, j0 = np.floor(u).astype(np.int64), np.floor(v).astype(np.int64)
    fu, fv = u - i0, v - j0
    fu = fu * fu * (3 - 2 * fu)
    fv = fv * fv * (3 - 2 * fv)
    imin, jmin = int(i0.min()), int(j0.min())
    grid = rnd.random((int(j0.max()) - jmin + 2, int(i0.max()) - imin + 2))
    a, b = i0 - imin, j0 - jmin
    g00, g10, g01, g11 = grid[b, a], grid[b, a + 1], grid[b + 1, a], grid[b + 1, a + 1]
    return (g00 * (1 - fu) + g10 * fu) * (1 - fv) + (g01 * (1 - fu) + g11 * fu) * fv


def fractal(X, Y, spec: FractalSpec, center=None):
    """Bruit fractal normalisé 0 … height, selon le type."""
    import numpy as np
    rnd = np.random.default_rng(int(spec.seed))
    total = np.zeros(X.shape)
    amp, norm, f = 1.0, 0.0, max(1e-4, spec.frequency)
    for _ in range(max(1, int(spec.octaves))):
        total += amp * _value_noise(X, Y, f, rnd)
        norm += amp
        amp *= spec.gain
        f *= 2
    n = total / max(norm, 1e-12)                          # 0 … 1
    cx, cy = center if center is not None else (float(X.mean()), float(Y.mean()))
    r = np.hypot(X - cx, Y - cy)
    if spec.kind == 'rayures':
        n = 0.5 + 0.5 * np.sin(2 * math.pi * spec.frequency * Y + 4 * (n - 0.5))
    elif spec.kind == 'concentrique':
        n = 0.5 + 0.5 * np.sin(2 * math.pi * spec.frequency * r + 4 * (n - 0.5))
    elif spec.kind == 'focal':
        R = float(r.max()) or 1.0
        n = n * (1 - r / R)
    lo, hi = float(n.min()), float(n.max())
    return (n - lo) / (hi - lo if hi > lo else 1.0) * spec.height


def weave(X, Y, spec: WeaveSpec):
    """Tissage : fils arrondis de deux nappes croisées à 90°, chacun passant
    alternativement au-dessus et au-dessous de l'autre nappe."""
    import numpy as np
    a = math.radians(spec.angle)
    U = X * math.cos(a) + Y * math.sin(a)
    V = -X * math.sin(a) + Y * math.cos(a)
    p = max(1e-3, spec.pitch)
    half = max(1e-3, min(spec.width, p) / 2)

    def nappe(across, along, sign):
        k = np.round(across / p)                         # numéro du fil
        d = np.abs(across - k * p)
        prof = np.sqrt(np.clip(1 - (d / half) ** 2, 0, None))
        par = np.where(k.astype(np.int64) % 2 == 0, 1.0, -1.0)
        # au croisement, les fils des deux nappes sont l'un dessus, l'autre dessous
        lift = 0.5 + 0.5 * sign * par * np.cos(math.pi * along / p)
        return prof * (0.55 + 0.45 * lift)
    A = nappe(V, U, 1.0)                                  # fils le long de U
    B = nappe(U, V, -1.0)                                 # fils le long de V
    return np.maximum(A, B) * spec.height


def tile(X, Y, T, tx0: float, ty1: float, tres: float, gap: float = 0.0):
    """Remplissage par texture : le motif T (carte du haut vers le bas,
    origine tx0, ty1, pas tres) répété en pavage, avec un écart `gap` entre
    deux motifs ; hauteurs aux points X, Y."""
    import numpy as np
    th, tw = T.shape
    pw, ph = tw * tres + gap, th * tres + gap
    u = np.mod(X - tx0, pw)
    v = np.mod(ty1 - Y, ph)
    inside = (u < tw * tres) & (v < th * tres)
    i = np.clip((u / tres).astype(int), 0, tw - 1)
    j = np.clip((v / tres).astype(int), 0, th - 1)
    return np.where(inside, T[j, i], 0.0)
