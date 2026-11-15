"""Vérification du dessin avant gravure : ce qui risque de mal sortir sur
la machine (objet hors plaque, contour presque fermé, poussière, doublon,
texte sans glyphes, outil absent de la table…).

`check(doc)` rend une liste de `Issue`, des plus graves aux simples
informations ; chaque problème garde les objets de premier niveau
concernés (pour les sélectionner) et dit s'il sait se corriger tout seul
(`fix`).
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field

from .document import Document, Group, Image, Item, Shape, Text
from .geom import Path
from . import progress

SEVERITIES = ('erreur', 'attention', 'info')


def tr(text: str) -> str:
    """Repère des chaînes à traduire (la traduction se fait à l'affichage)."""
    return text

#: écart maximal (mm) d'un contour ouvert considéré comme « presque fermé »
GAP = 0.1
#: taille (mm) en dessous de laquelle un contour est de la poussière
DUST = 0.05
#: longueur (mm) au-dessous de laquelle une boucle d'auto-intersection est un
#: défaut (reprise d'outil, gravure doublée) plutôt qu'une forme voulue
LOOP = 2.0


def small_loops(c, limit: float = LOOP, first: bool = False) -> int:
    """Nombre de petites boucles où le contour se recoupe (0 si simple ;
    pré-test rapide par shapely sur le contour aplati, longueur des boucles
    estimée par les longueurs cumulées des segments). `first` : s'arrêter à
    la première."""
    import shapely
    if len(c.segments) < 2 or len(c.segments) > 5000:
        return 0
    from .parallel import _polyline
    pts = _polyline(c, 0.01)                       # numpy, fermeture comprise
    if len(pts) < 4:
        return 0
    try:
        if shapely.LineString(pts).is_simple:
            return 0
    except Exception:
        return 0
    from .trim import self_crossings
    cc = c.close() if c.closed else c
    import math as _m

    def approx_len(sg):                          # moyenne corde / polygone de contrôle
        cp = sg.controls()
        poly = sum(_m.dist(a, b) for a, b in zip(cp, cp[1:]))
        return (poly + _m.dist(cp[0], cp[-1])) / 2
    lens = [approx_len(sg) for sg in cc.segments]
    cum = [0.0]
    for L in lens:
        cum.append(cum[-1] + L)
    total = cum[-1]

    def at(g):
        i = min(int(g), len(lens) - 1)
        return cum[i] + (g - i) * lens[i]
    n = 0
    for ga, gb in self_crossings(cc):
        L = at(gb) - at(ga)
        if cc.closed:
            L = min(L, total - L)
        if L <= limit:
            n += 1
            if first:
                return n
    return n


@dataclass
class Issue:
    code: str
    severity: str
    message: str                       # modèle français : {0} nombre, {1} écart, {2} poussière
    count: int
    items: list[Item] = field(default_factory=list)
    fixable: bool = False
    params: tuple = (GAP, DUST)

    def text(self, translate=lambda s: s) -> str:
        return translate(self.message).format(self.count, f'{self.params[0]:g}', f'{self.params[1]:g}')


def _tops(doc: Document):
    """(calque, objet de premier niveau, feuille visible) pour tout le dessin visible."""
    for L in doc.layers:
        if not L.visible:
            continue
        for top in L.items:
            if not top.visible:
                continue
            stack = [top]
            while stack:
                it = stack.pop()
                if isinstance(it, Group):
                    stack.extend(ch for ch in it.children if ch.visible)
                else:
                    yield L, top, it


def _contours(leaf: Item):
    if isinstance(leaf, Shape):
        return leaf.path.contours
    if isinstance(leaf, Text) and leaf.outline:
        return leaf.outline.contours
    return []


def _add(found: dict, code: str, top: Item, n: int = 1) -> None:
    lst, k = found.setdefault(code, ([], [0]))
    if not any(x is top for x in lst):
        lst.append(top)
    k[0] += n


def check(doc: Document, *, gap: float = GAP, dust: float = DUST, duplicates: bool = True) -> list[Issue]:
    found: dict[str, tuple[list[Item], list[int]]] = {}
    plate = doc.plate
    if plate is not None:
        px0, py0 = plate.x, plate.y
        px1, py1 = plate.x + plate.width, plate.y + plate.height
    ntools = len(doc.tools)
    tops = list(_tops(doc))
    for ti, (L, top, leaf) in enumerate(tops):
        if ti % 8 == 0:
            progress.step(ti, len(tops), 'Vérification : objet {0} sur {1}')
        if isinstance(leaf, Text) and leaf.text.strip() and not leaf.outline:
            _add(found, 'texte_vide', top)
        if isinstance(leaf, Text) and leaf.text.strip() and leaf.outline and leaf.font:
            from . import fonts as _F
            if not _F.is_available(leaf.font):
                _add(found, 'police_absente', top)
        if isinstance(leaf, Image):
            _add(found, 'image', top)
        if not 0 <= leaf.tool < ntools:
            _add(found, 'outil_absent', top)
        bb = leaf.bbox()
        if plate is not None and bb and (bb[0] < px0 - 1e-6 or bb[1] < py0 - 1e-6
                                         or bb[2] > px1 + 1e-6 or bb[3] > py1 + 1e-6):
            _add(found, 'hors_plaque', top)
        elif plate is not None and bb and getattr(plate, 'has_margins', lambda: False)():
            ux0, uy0, ux1, uy1 = plate.usable()
            if bb[0] < ux0 - 1e-6 or bb[1] < uy0 - 1e-6 or bb[2] > ux1 + 1e-6 or bb[3] > uy1 + 1e-6:
                _add(found, 'hors_marges', top)
        for c in _contours(leaf):
            if not c.segments:
                continue
            cb = c.bbox()
            if max(cb[2] - cb[0], cb[3] - cb[1]) < dust:
                _add(found, 'poussiere', top)
                continue
            tw = doc.tool_width(leaf.tool)
            if tw > 0 and c.closed and min(cb[2] - cb[0], cb[3] - cb[1]) < tw:
                _add(found, 'trop_petit', top)
            if not c.closed:
                d = ((c.end[0] - c.start[0]) ** 2 + (c.end[1] - c.start[1]) ** 2) ** 0.5
                if 1e-6 < d <= gap and c.length() > 3 * gap:
                    _add(found, 'presque_ferme', top)
            if isinstance(leaf, Shape) and small_loops(c, first=True):
                _add(found, 'boucle', top)
    if duplicates:
        from .cleanup import dedupe
        for L in doc.layers:
            if not L.visible:
                continue
            items = [it for it in L.items if it.visible]
            out, n = dedupe(items)
            if n:
                for a, b in zip(items, out):
                    if a is not b:
                        _add(found, 'doublon', a, 0)
                found['doublon'][1][0] += n
    hidden = sum(1 for L in doc.layers for it in L.items if not L.visible or not it.visible)
    empty = [L for L in doc.layers if not L.items]

    spec = {
        'texte_vide': ('erreur', tr('Texte sans glyphes (police introuvable) : rien ne sera gravé ({0})'), False),
        'outil_absent': ('erreur', tr('Objet sur un outil absent de la table des outils ({0})'), False),
        'police_absente': ('attention', tr('Texte dans une police absente du poste, dessiné avec une police de remplacement ({0})'), False),
        'hors_plaque': ('attention', tr('Objet dépassant de la plaque ({0})'), False),
        'hors_marges': ('attention', tr('Objet dans les marges de la plaque ({0})'), False),
        'presque_ferme': ('attention', tr('Contour presque fermé (écart ≤ {1} mm) : à fermer ({0})'), True),
        'poussiere': ('attention', tr('Contour minuscule (moins de {2} mm) ({0})'), True),
        'doublon': ('attention', tr('Contour superposé à un autre : gravé deux fois ({0})'), True),
        'trop_petit': ('attention', tr('Contour fermé plus petit que la largeur de son outil ({0})'), False),
        'boucle': ('attention', tr('Contour qui se recoupe en petite boucle : trait gravé deux fois ({0})'), True),
        'image': ('info', tr('Image : ignorée par les exports machine SimPl et CLJOB ({0})'), False),
    }
    out: list[Issue] = []
    for code, (sev, msg, fixable) in spec.items():
        if code in found:
            items, k = found[code]
            out.append(Issue(code, sev, msg, k[0], items, fixable, (gap, dust)))
    if hidden:
        out.append(Issue('masque', 'info', tr('Objet masqué ou sur un calque masqué : ni affiché ni exporté ({0})'),
                         hidden))
    if empty:
        out.append(Issue('calque_vide', 'info', tr('Calque vide ({0})'), len(empty)))
    out.sort(key=lambda i: SEVERITIES.index(i.severity))
    return out


def fix_item(it: Item, code: str, *, gap: float = GAP, dust: float = DUST) -> Item | None:
    """Copie corrigée de l'objet pour `code` ('presque_ferme' : contour
    fermé sur son point de départ ; 'poussiere' : contour retiré). None si
    l'objet ne contient plus rien."""
    if isinstance(it, Group):
        ch = [x for x in (fix_item(c, code, gap=gap, dust=dust) for c in it.children) if x is not None]
        if not ch:
            return None
        g = copy.copy(it)
        g.children = ch
        return g
    if not isinstance(it, Shape):
        return it
    keep = []
    for c in it.path.contours:
        if not c.segments:
            continue
        if code == 'poussiere':
            cb = c.bbox()
            if max(cb[2] - cb[0], cb[3] - cb[1]) < dust:
                continue
        elif code == 'presque_ferme' and not c.closed:
            d = ((c.end[0] - c.start[0]) ** 2 + (c.end[1] - c.start[1]) ** 2) ** 0.5
            if d <= gap and c.length() > 3 * gap:
                c = c.close()
        elif code == 'boucle' and small_loops(c):
            from .parallel import remove_loops
            c = remove_loops(c, LOOP)
        keep.append(c)
    if not keep:
        return None
    s = copy.copy(it)
    s.path = Path(keep)
    s.extra = {k: v for k, v in it.extra.items() if k not in ('vnd_obj', 'vnd_moved', 'vnd_shift')} \
        if keep != it.path.contours else it.extra
    return s
