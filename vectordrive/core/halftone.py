"""Photo → trame vectorielle à graver.

Entrée : niveaux de gris (tableau numpy, 0 = noir, 1 = blanc), première
ligne en haut. Deux styles :

* ``dots``  — grille de points ronds au pas `pitch` ; l'**aire** du point
  est proportionnelle à la densité (noir plein : points jointifs) ;
* ``lines`` — lignes horizontales au pas `pitch` dont l'**épaisseur** suit
  la densité (contours fermés, pour un remplissage laser).

`gamma` > 1 éclaircit les tons moyens, < 1 les fonce ; `invert` pour une
gravure qui éclaircit la matière (anodisé, laqué…).
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np

from . import geom
from .document import Group, Shape
from .geom import Contour, Path


@dataclass
class HalftoneSpec:
    width: float = 50.0          # largeur du résultat, mm (hauteur : proportions de l'image)
    pitch: float = 0.5           # pas de la trame, mm
    style: str = 'dots'          # dots | lines
    gamma: float = 1.0
    invert: bool = False
    min_size: float = 0.05       # en dessous (diamètre ou épaisseur, mm) : rien
    source: str = ''             # chemin de l'image (re-édition)

    @classmethod
    def from_dict(cls, d: dict) -> 'HalftoneSpec':
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def _sample(gray: np.ndarray, cols: int, rows: int) -> np.ndarray:
    """Moyenne de l'image sur chaque cellule de la grille (rows × cols)."""
    h, w = gray.shape
    ys = np.linspace(0, h, rows + 1).astype(int)
    xs = np.linspace(0, w, cols + 1).astype(int)
    # sommes cumulées 2D : moyenne exacte de chaque bloc
    s = np.pad(gray.astype(float), ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    y0, y1 = ys[:-1][:, None], np.maximum(ys[1:], ys[:-1] + 1)[:, None]
    x0, x1 = xs[:-1][None, :], np.maximum(xs[1:], xs[:-1] + 1)[None, :]
    y1 = np.minimum(y1, h)
    x1 = np.minimum(x1, w)
    total = s[y1, x1] - s[y0, x1] - s[y1, x0] + s[y0, x0]
    return total / ((y1 - y0) * (x1 - x0))


def density(gray: np.ndarray, spec: HalftoneSpec) -> np.ndarray:
    """Densité 0..1 (1 = noir plein) de chaque cellule ; ligne 0 en haut."""
    h, w = gray.shape
    cols = max(1, int(round(spec.width / spec.pitch)))
    rows = max(1, int(round(cols * h / w)))
    g = np.clip(_sample(gray, cols, rows), 0, 1)
    k = g if spec.invert else 1 - g
    return np.power(k, spec.gamma)


def paths(gray: np.ndarray, spec: HalftoneSpec) -> Path:
    k = density(gray, spec)
    rows, cols = k.shape
    p = spec.pitch
    top = (rows - 1) * p
    contours: list[Contour] = []
    if spec.style == 'lines':
        for r in range(rows):
            yc = top - r * p + p / 2
            t = (k[r] * p).tolist()                       # épaisseur = densité × pas
            run = []
            for c in range(cols + 1):
                if c < cols and t[c] >= spec.min_size:
                    run.append(c)
                    continue
                if run:
                    xs = [(i + 0.5) * p for i in run]
                    upper = [(x, yc + t[i] / 2) for x, i in zip(xs, run)]
                    lower = [(x, yc - t[i] / 2) for x, i in zip(xs, run)]
                    pts = [(run[0] * p, yc + t[run[0]] / 2)] + upper + [((run[-1] + 1) * p, yc + t[run[-1]] / 2),
                                                                        ((run[-1] + 1) * p, yc - t[run[-1]] / 2)] \
                        + lower[::-1] + [(run[0] * p, yc - t[run[0]] / 2)]
                    contours.append(geom.polyline(pts, closed=True))
                    run = []
        return Path(contours)
    # points : aire ∝ densité ; noir plein = disque d'aire p² (diamètre 1,128 p)
    dia = (2 * p * np.sqrt(k / math.pi)).tolist()
    for r in range(rows):
        for c in range(cols):
            d = dia[r][c]
            if d >= spec.min_size:
                contours.append(geom.circle(((c + 0.5) * p, top - r * p + p / 2), d / 2))
    return Path(contours)


def build(gray: np.ndarray, spec: HalftoneSpec, tool: int = 0) -> Group:
    sh = Shape(path=paths(gray, spec), filled=True, tool=tool, name='trame')
    g = Group(children=[sh], name='Photo (trame)', tool=tool)
    g.extra['halftone'] = asdict(spec)
    return g


def coverage(path: Path, spec: HalftoneSpec, shape) -> float:
    """Taux de noir obtenu (aire gravée / aire totale) — contrôle."""
    from . import pathops
    rows, cols = shape
    return pathops.area(path) / (rows * cols * spec.pitch ** 2)
