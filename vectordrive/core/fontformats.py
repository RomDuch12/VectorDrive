"""Formats de polices apportés par les plugins : polices propriétaires, lues sur le poste, jamais redistribuées.

Le cœur lit lui-même TrueType et OpenType, les polices SVG (`svgfonts`) et ses polices monotrait intégrées. Un plugin
enregistre un format (`Api.add_font_format`) : ses extensions de fichier, l'étiquette de ses polices dans les listes,
ses dossiers, et son lecteur — nom de la police, glyphe et avance (dans les unités de ses métriques), métriques,
crénage, caractères dessinés.
"""
from __future__ import annotations

import math
import pathlib
from dataclasses import dataclass
from typing import Callable

from .geom import Path


@dataclass(eq=False)
class FontFormat:
    label: str                                       # infobulle de ses polices dans les listes
    extensions: tuple                                # ('.xyz', …), en minuscules
    font_name: Callable                              # chemin → nom affiché, ou None (pas une police)
    glyph: Callable                                  # (chemin, caractère) → (Path, avance)
    metrics: Callable                                # chemin → {'upem', 'ascent', 'descent', 'cap'}
    kerning: Callable | None = None                  # (chemin, gauche, droite) → crénage (unités des métriques)
    characters: Callable | None = None               # chemin → codes des caractères dessinés
    clear: Callable | None = None                    # oublier ce qui est lu (une police réécrite)
    dirs: tuple = ()                                 # dossiers où chercher ses polices
    clonable: bool = False                           # l'éditeur de polices peut partir d'elles
    reader: str = ''                                 # le lecteur (module et version du plugin) : changé, l'inventaire est refait
    filter_label: str = ''                           # libellé court de son filtre dans la liste des polices (« TypeEdit »)


#: extension → format
FORMATS: dict[str, FontFormat] = {}


def register(fmt: FontFormat) -> None:
    """Le format est lu désormais ; ses dossiers sont cherchés, l'inventaire des polices est refait."""
    from . import fonts
    for ext in fmt.extensions:
        FORMATS[ext.lower()] = fmt
    fonts.add_dirs(fmt.dirs)
    fonts.refresh()


def unregister(fmt: FontFormat) -> None:
    from . import fonts
    for ext in [e for e, f in FORMATS.items() if f is fmt]:
        del FORMATS[ext]
    fonts.refresh()


def of(path) -> FontFormat | None:
    """Le format qui lit ce fichier, sinon None (le cœur le lit, ou ce n'est pas une police)."""
    return FORMATS.get(pathlib.Path(str(path)).suffix.lower()) if FORMATS else None


def registered() -> list:
    """Les formats enregistrés, chacun une fois."""
    return list({id(f): f for f in FORMATS.values()}.values())


def group_of_file(path) -> str:
    """Le libellé du filtre (« TypeEdit ») du format qui a le sien et dont un dossier contient ce fichier (une police
    TrueType livrée avec ses polices), sinon ''. Chemins comparés en texte : aucun accès au disque."""
    import os
    try:
        p = os.path.normcase(os.path.abspath(str(path)))
    except (TypeError, ValueError):
        return ''
    for fmt in registered():
        if not fmt.filter_label:
            continue
        for d in fmt.dirs:
            k = os.path.normcase(os.path.abspath(str(d))).rstrip('\\/')
            if p.startswith(k + os.sep):
                return fmt.filter_label
    return ''


#: métriques d'une police dont le lecteur est en défaut : hauteur 1, boîte 1,25 / 0,75 (le texte reste)
FALLBACK_METRICS = {'upem': 1.0, 'ascent': 1.25, 'descent': 0.75, 'cap': 1.0}


def read_metrics(fmt: FontFormat, path: str) -> dict:
    """Les métriques lues par le plugin ; lecteur en défaut ou valeurs fausses : FALLBACK_METRICS."""
    try:
        m = fmt.metrics(path)
        got = {k: float(m[k]) for k in ('upem', 'ascent', 'descent', 'cap')}
        if all(math.isfinite(v) for v in got.values()) and got['upem'] > 0 and got['cap'] > 0:
            return dict(m, **got)
    except Exception:
        pass
    return dict(FALLBACK_METRICS)


def read_glyph(fmt: FontFormat, path: str, char: str) -> tuple:
    """(tracé, avance) lus par le plugin ; lecteur en défaut, caractère absent ou valeurs folles : vide, le texte
    reste."""
    try:
        g, adv = fmt.glyph(path, char)
        adv = float(adv)
    except Exception:
        return Path(), 0.0
    from . import fonts
    lim = 1e3 * fonts.metrics(path)['upem']
    if not math.isfinite(adv) or abs(adv) > lim:
        adv = 0.0
    if not isinstance(g, Path):
        return Path(), adv
    try:
        for c in g.contours:
            for seg in c.segments:
                if not all(math.isfinite(v) and abs(v) < lim for pt in (seg.start, seg.end) for v in pt):
                    return Path(), adv
    except Exception:
        return Path(), adv
    return g, adv


def read_kerning(fmt: FontFormat, path: str, left: str, right: str) -> float:
    """Crénage lu par le plugin ; lecteur en défaut ou valeur folle : 0."""
    if fmt.kerning is None:
        return 0.0
    try:
        v = float(fmt.kerning(path, left, right))
    except Exception:
        return 0.0
    from . import fonts
    return v if math.isfinite(v) and abs(v) < 10 * fonts.metrics(path)['upem'] else 0.0
