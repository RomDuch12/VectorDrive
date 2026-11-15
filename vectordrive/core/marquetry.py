"""Marqueterie (TypeEdit : ID_MARQUETTERIE) : formes mâles et femelles pour
la marqueterie ou l'incrustation.

D'une sélection (courbes fermées ou textes, sans les vectoriser), deux jeux
de formes : les **femelles** (le logement, usiné en poche ou détouré) et les
**mâles** (la pièce rapportée, détourée), chacun sur son plan — le plan
d'origine ne change pas. Réglages, comme TypeEdit :

- angles arrondis : tous les angles, rentrants comme saillants, des deux
  formes, pour qu'elles s'emboîtent (fermeture puis ouverture du rayon) ;
- décalage de chaque forme (un petit jeu entre les deux) ;
- miroir de chaque forme autour de l'axe X (outil conique, même matière
  pour les deux) ;
- imbrication facultative des formes mâles sur la plaque ;
- prédéfinis d'usinage : trou conique ou cylindrique, borgne (femelle en
  poche) ou débouchant (femelle détourée), mâle toujours détouré.
"""
from __future__ import annotations

from dataclasses import dataclass

from .document import Group, Shape, Text
from .geom import Affine, Path

#: prédéfini → (libellé, stratégie de la femelle, nature d'outil)
PRESETS = {
    'aucun': ('Aucun prédéfini', '', ''),
    'conique_borgne': ('Trou conique borgne', 'poche', 'conique'),
    'conique_debouchant': ('Trou conique débouchant', 'contour', 'conique'),
    'cylindrique_debouchant': ('Trou cylindrique débouchant', 'contour', 'fraise'),
    'cylindrique_borgne': ('Trou cylindrique borgne', 'poche', 'fraise'),
}
FEMALE_LAYER = 'Marqueterie — formes femelles'
MALE_LAYER = 'Marqueterie — formes mâles'


@dataclass
class MarquetrySpec:
    corner_radius: float = 0.0      # angles arrondis (mm, 0 = vifs)
    female_offset: float = 0.05     # forme femelle (logement) : > 0 plus grande
    male_offset: float = -0.05      # forme mâle (pièce) : < 0 plus petite
    female_mirror: bool = False     # miroir autour de l'axe X
    male_mirror: bool = False
    female_tool: int = 1            # couleur (outil du dessin) des formes femelles
    male_tool: int = 2
    nest: bool = False              # imbriquer les formes mâles sur la plaque
    preset: str = 'aucun'


def _geometry(it) -> list:
    """Contours fermés d'un objet (texte : son contour ; groupe : son contenu)."""
    if isinstance(it, Group):
        return [c for ch in it.children for c in _geometry(ch)]
    path = it.path if isinstance(it, Shape) else (it.outline if isinstance(it, Text) else None)
    return [c for c in (path.contours if path else []) if c.closed and c.segments]


def _round(path: Path, r: float) -> Path:
    """Tous les angles arrondis au rayon r : fermeture (+r, −r) pour les
    rentrants, ouverture (−r, +r) pour les saillants."""
    from . import pathops
    if r <= 0:
        return path
    return pathops.offset(pathops.offset(pathops.offset(path, r), -2 * r), r)


def _mirror(path: Path) -> Path:
    bb = path.bbox()
    if not bb:
        return path
    return path.transformed(Affine.scaling(1.0, -1.0, ((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2)))


def forms(items: list, spec: MarquetrySpec) -> tuple[list[Shape], list[Shape]]:
    """(femelles, mâles) : une forme de chaque par objet de la sélection
    qui a des contours fermés."""
    from . import pathops
    female, male = [], []
    for it in items:
        contours = _geometry(it)
        if not contours:
            continue
        base = _round(pathops.normalize(Path(contours)), spec.corner_radius)
        if not base.contours:                            # rayon plus grand que la forme
            continue
        name = it.name or (it.text if isinstance(it, Text) else '')
        for out, off, mirror, tool, kind in ((female, spec.female_offset, spec.female_mirror, spec.female_tool,
                                              'femelle'),
                                             (male, spec.male_offset, spec.male_mirror, spec.male_tool, 'mâle')):
            p = pathops.offset(base, off) if off else base
            if mirror:
                p = _mirror(p)
            if p.contours:
                out.append(Shape(path=p, tool=tool, name=f'{name} — {kind}'.strip(' —')))
    return female, male

