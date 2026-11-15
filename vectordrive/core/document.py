"""Modèle de document VectorDrive, calqué sur celui de TypeEdit.

TypeEdit organise un *travail* (`CTravail`) en *calques* (`CCalque`, « Plan
1 »…), chaque calque contenant des *zones* (`CZone`), qui regroupent des
*courbes* (`CCourbe`) faites de *contours* (`CContour`). La couleur d'un
objet désigne l'**outil** qui le gravera.

VectorDrive garde la même hiérarchie, en plus simple :

    Document ─ Plate (la plaque)
             ─ Tool[]  (couleur = outil)
             ─ Layer[] ─ Item[] : Shape | Text | Group

Le document est indépendant de Qt : il se lit, s'écrit et se teste sans
interface.
"""
from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from typing import Iterator

from .geom import Affine, Path, bbox_union, IDENTITY


def new_id() -> str:
    return uuid.uuid4().hex


#: Palette par défaut des outils TypeEdit (couleurs 1 à 8).
DEFAULT_TOOL_COLORS = (
    '#000000', '#ff0000', '#00a000', '#0000ff',
    '#ff00ff', '#00c0c0', '#c08000', '#808080',
)


#: clé de `Item.extra` : la couleur propre d'un objet (« #rrggbb »), donnée par l'utilisateur
OWN_COLOR = 'couleur'


def own_color(it) -> str | None:
    """La couleur propre de l'objet (« #rrggbb »), ou None : il prend celle de son outil."""
    c = it.extra.get(OWN_COLOR) if isinstance(getattr(it, 'extra', None), dict) else None
    if isinstance(c, str) and len(c) == 7 and c.startswith('#'):
        try:
            int(c[1:], 16)
        except ValueError:
            return None
        return c.lower()
    return None


def set_own_color(items, color: str | None) -> int:
    """Donne la couleur `color` (« #rrggbb ») aux objets (groupes dépliés), ou la retire (None) : ils reprennent celle
    de leur outil. Rend le nombre d'objets changés."""
    n = 0
    for it in items:
        for leaf in _leaf_items(it):
            if not isinstance(leaf.extra, dict):
                leaf.extra = {}
            before = leaf.extra.get(OWN_COLOR)
            if color:
                leaf.extra[OWN_COLOR] = str(color).lower()
            else:
                leaf.extra.pop(OWN_COLOR, None)
            n += leaf.extra.get(OWN_COLOR) != before
    return n


@dataclass
class Tool:
    """Un outil du dessin = une couleur. Les paramètres de coupe vivent
    dans le réglage FAO du document (`vectordrive.cam`), où une opération
    désigne les couleurs qu'elle usine."""
    index: int
    color: str
    name: str = ''
    #: largeur gravée (mm) : diamètre de la fraise ou de la pointe, spot du
    #: laser ; 0 = inconnue. Sert à l'aperçu de gravure, pas à la FAO.
    width: float = 0.0


@dataclass
class Plate:
    """Plaque à graver. Origine (0, 0) au coin bas-gauche par défaut."""
    width: float = 100.0
    height: float = 50.0
    corner_radius: float = 0.0
    material: str = ''
    x: float = 0.0
    y: float = 0.0
    visible: bool = True
    thickness: float = 0.0           # épaisseur (support TypeEdit : z de −e à 0)
    #: marges (gauche, droite, bas, haut) en mm : zone gravable, vérifiée avant l'usinage
    margins: list = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])

    def usable(self) -> tuple[float, float, float, float]:
        """Zone gravable (x0, y0, x1, y1) : la plaque moins ses marges."""
        m = list(self.margins or [0.0, 0.0, 0.0, 0.0]) + [0.0] * 4
        return (self.x + m[0], self.y + m[2], self.x + self.width - m[1], self.y + self.height - m[3])

    def has_margins(self) -> bool:
        return any(abs(float(v)) > 1e-9 for v in (self.margins or []))

    #: point zéro de la plaque (TypeEdit) : coins ou centre
    ZEROS = (('', 'Inchangé'), ('bg', 'Coin bas-gauche'), ('hg', 'Coin haut-gauche'), ('c', 'Centre'),
             ('hd', 'Coin haut-droit'), ('bd', 'Coin bas-droit'))

    def zero_point(self, key: str) -> tuple[float, float] | None:
        """Point de la plaque désigné par `key` (ZEROS), None si inchangé."""
        x0, y0, x1, y1 = self.x, self.y, self.x + self.width, self.y + self.height
        return {'bg': (x0, y0), 'hg': (x0, y1), 'c': ((x0 + x1) / 2, (y0 + y1) / 2), 'hd': (x1, y1),
                'bd': (x1, y0)}.get(key)


@dataclass
class Item:
    id: str = field(default_factory=new_id)
    name: str = ''
    tool: int = 0
    visible: bool = True
    locked: bool = False
    #: Données propres au format d'origine (ex. GUID TypeEdit), conservées
    #: telles quelles pour une réécriture fidèle.
    extra: dict = field(default_factory=dict)

    def bbox(self):
        raise NotImplementedError

    def transformed(self, m: Affine) -> 'Item':
        raise NotImplementedError

    def clone(self) -> 'Item':
        """Copie avec de nouveaux identifiants (enfants compris). Une copie
        n'est plus l'objet TypeEdit d'origine (même GUID) : elle sera écrite
        comme un dessin. Les tracés sont partagés (jamais modifiés en place)."""
        c = struct_copy(self)

        def renew(x):
            x.id = new_id()
            drop_source_object(x)
            for ch in getattr(x, 'children', ()):
                renew(ch)
        renew(c)
        return c

    def _after_transform(self, c: 'Item', m: Affine) -> None:
        # objet TypeEdit d'origine (texte, cote, trou) : une simple
        # translation est cumulée (l'objet sera translaté à l'écriture) ;
        # toute autre transformation le rend caduc
        if 'vnd_obj' in self.extra and not m.is_identity:
            c.extra = dict(self.extra)
            if m.a == 1 and m.b == 0 and m.c == 0 and m.d == 1 and not self.extra.get('vnd_moved'):
                dx, dy = self.extra.get('vnd_shift', (0.0, 0.0))
                c.extra['vnd_shift'] = (dx + m.e, dy + m.f)
            else:
                c.extra['vnd_moved'] = True
        # brut de l'ensemble (BAT) : il suit l'ensemble
        brut = self.extra.get('brut') if isinstance(self.extra, dict) else None
        if isinstance(brut, dict) and brut.get('corners') and not m.is_identity:
            if c.extra is self.extra:
                c.extra = dict(self.extra)
            c.extra['brut'] = dict(brut, corners=[list(m.apply((float(p[0]), float(p[1])))) for p in brut['corners']])
        # pontets et points de départ posés à la main (FAO) : ils suivent la forme
        for key in ('tabs_xy', 'start_xy', 'lead_xy'):
            tabs = self.extra.get(key) if isinstance(self.extra, dict) else None
            if tabs and not m.is_identity:
                if c.extra is self.extra:
                    c.extra = dict(self.extra)
                c.extra[key] = [list(m.apply((float(t[0]), float(t[1])))) + list(t[2:]) for t in tabs]
        # contours d'un seul point gardés pour la réécriture du VND : ils
        # suivent la transformation
        vx = self.extra.get('vnd') if isinstance(self.extra, dict) else None
        if isinstance(vx, dict) and 'empty_contours' in vx and not m.is_identity:
            from ..io.vnd import transformed_contour
            if c.extra is self.extra:
                c.extra = dict(self.extra)
            c.extra['vnd'] = dict(vx, empty_contours=[(i, transformed_contour(o, m))
                                                      for i, o in vx['empty_contours']])
        # forme paramétrée (core.forms) : ses paramètres suivent une similitude ;
        # un étirement en fait une courbe
        cd = self.extra.get('cote') if isinstance(self.extra, dict) else None
        if isinstance(cd, dict) and not m.is_identity:
            from .dims import transformed as dim_transformed
            if c.extra is self.extra:
                c.extra = dict(self.extra)
            nd = dim_transformed(cd, m)
            if nd is None:
                c.extra.pop('cote', None)
            else:
                c.extra['cote'] = nd
        td = self.extra.get('tolerance') if isinstance(self.extra, dict) else None
        if isinstance(td, dict) and not m.is_identity:        # cadre de tolérancement (core.gdt)
            from .gdt import transformed as gdt_transformed
            if c.extra is self.extra:
                c.extra = dict(self.extra)
            nd = gdt_transformed(td, m)
            if nd is None:
                c.extra.pop('tolerance', None)
            else:
                c.extra['tolerance'] = nd
        sd = self.extra.get('solide') if isinstance(self.extra, dict) else None
        if isinstance(sd, dict) and not m.is_identity:        # volume 3D : son placement suit
            from .solids import transformed_extra
            if c.extra is self.extra:
                c.extra = dict(self.extra)
            c.extra['solide'] = transformed_extra(sd, m)
        cd = self.extra.get('corners') if isinstance(self.extra, dict) else None
        if isinstance(cd, dict) and not m.is_identity and getattr(c, 'path', None) is not None:
            from .corners import transformed as corners_transformed    # coins réglables : ils suivent
            if c.extra is self.extra:
                c.extra = dict(self.extra)
            nd = corners_transformed(cd, m, c.path)
            if nd is None:
                c.extra.pop('corners', None)
            else:
                c.extra['corners'] = nd
        fd = self.extra.get('forme') if isinstance(self.extra, dict) else None
        if isinstance(fd, dict) and not m.is_identity and getattr(c, 'path', None) is not None:
            from .forms import transformed
            if c.extra is self.extra:
                c.extra = dict(self.extra)
            nd = transformed(fd, m, c.path)
            if nd is None:
                c.extra.pop('forme', None)
            else:
                c.extra['forme'] = nd


@dataclass
class Shape(Item):
    path: Path = field(default_factory=Path)
    filled: bool = False

    def bbox(self):
        return self.path.bbox()

    def transformed(self, m: Affine) -> 'Shape':
        c = copy.copy(self)
        c.path = self.path.transformed(m)
        self._after_transform(c, m)
        return c


@dataclass
class Text(Item):
    """Texte vivant : la chaîne et la police sont gardées, le contour est
    recalculé à la demande (voir `vectordrive.core.fonts`)."""
    text: str = ''
    font: str = 'Arial'
    size: float = 10.0               # hauteur des capitales, mm
    matrix: Affine = IDENTITY        # placement (origine = ligne de base)
    align: str = 'left'              # left | center | right
    spacing: float = 0.0             # interlettrage, mm
    line_spacing: float = 1.2
    #: Contour calculé ou relu dans le fichier source (repli si la police
    #: n'est pas disponible).
    outline: Path | None = None
    #: Étirement horizontal des glyphes (1 = police telle quelle).
    width_ratio: float = 1.0

    def bbox(self):
        if self.outline:
            return self.outline.bbox()
        x, y = self.matrix.apply((0.0, 0.0))
        return (x, y, x + self.size * 0.6 * max(1, len(self.text)), y + self.size)

    def transformed(self, m: Affine) -> 'Text':
        c = copy.copy(self)
        c.matrix = m @ self.matrix
        if self.outline:
            c.outline = self.outline.transformed(m)
        if self.extra.get('on_path') is not None:
            c.extra = dict(self.extra)
            c.extra['on_path'] = self.extra['on_path'].transformed(m)
        if 'box' in self.extra:
            # texte dans un rectangle : le cadre suit une translation ou une
            # échelle d'axes ; une rotation le supprime (texte figé)
            c.extra = dict(c.extra)
            if m.b == 0.0 and m.c == 0.0:
                b = self.extra['box']
                xa, ya = m.apply((b['x0'], b['y0']))
                xb, yb = m.apply((b['x1'], b['y1']))
                c.extra['box'] = dict(b, x0=min(xa, xb), y0=min(ya, yb), x1=max(xa, xb), y1=max(ya, yb))
            else:
                c.extra.pop('box')
        if 'arc' in self.extra:
            # texte en arc : le centre suit une translation ; une rotation ou
            # une échelle laissent seulement la courbe porteuse (on_path)
            c.extra = dict(c.extra)
            if (m.a, m.b, m.c, m.d) == (1.0, 0.0, 0.0, 1.0):
                a = dict(self.extra['arc'])
                a['center'] = list(m.apply(tuple(a['center'])))
                c.extra['arc'] = a
            else:
                c.extra.pop('arc')
        self._after_transform(c, m)
        return c


@dataclass
class Image(Item):
    """Image bitmap posée dans le dessin.

    `matrix` envoie le carré unité de l'image (u, v) ∈ [0, 1]², v vers le
    bas comme dans un fichier image, sur le plan de travail en mm.
    `data` : contenu brut, au format `fmt` ('dib' = BITMAPINFOHEADER +
    pixels, comme TypeEdit ; 'png'…).
    """
    data: bytes = b''
    fmt: str = 'dib'
    matrix: Affine = IDENTITY

    def corners(self) -> list[tuple[float, float]]:
        return [self.matrix.apply(p) for p in ((0, 0), (1, 0), (1, 1), (0, 1))]

    def bbox(self):
        pts = self.corners()
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (min(xs), min(ys), max(xs), max(ys))

    def transformed(self, m: Affine) -> 'Image':
        c = copy.copy(self)
        c.matrix = m @ self.matrix
        self._after_transform(c, m)
        return c


@dataclass
class Group(Item):
    children: list[Item] = field(default_factory=list)

    def bbox(self):
        return bbox_union(ch.bbox() for ch in self.children if ch.visible) or bbox_union(ch.bbox() for ch in self.children)

    def transformed(self, m: Affine) -> 'Group':
        c = copy.copy(self)
        c.children = [ch.transformed(m) for ch in self.children]
        self._after_transform(c, m)
        return c


def struct_copy(item: Item) -> Item:
    """Copie de la structure (objets, groupes, dictionnaires `extra`) qui
    partage les tracés : ceux-ci ne sont jamais modifiés en place (toute
    transformation crée un nouveau `Path`). Coût proportionnel au nombre
    d'objets, pas au nombre de segments."""
    c = copy.copy(item)
    c.extra = dict(item.extra)
    if isinstance(item, Group):
        c.children = [struct_copy(ch) for ch in item.children]
    return c


def struct_copy_layers(layers: list['Layer']) -> list['Layer']:
    out = []
    for L in layers:
        c = copy.copy(L)
        c.items = [struct_copy(it) for it in L.items]
        c.extra = dict(L.extra)
        out.append(c)
    return out


def _walk_children(item):
    """Descendants d'un objet (enfants des groupes, en profondeur)."""
    for ch in getattr(item, 'children', ()) or ():
        yield ch
        yield from _walk_children(ch)


def _leaf_items(item):
    """Objets terminaux d'un objet (lui-même, ou les feuilles de ses groupes)."""
    kids = getattr(item, 'children', None)
    if kids is None:
        yield item
        return
    for ch in kids:
        yield from _leaf_items(ch)


def drop_source_object(item: Item) -> None:
    """Oublie l'objet TypeEdit d'origine (texte ou cote édité, copié…)."""
    if 'vnd_obj' in item.extra:
        item.extra = {k: v for k, v in item.extra.items() if k not in ('vnd_obj', 'vnd_moved', 'vnd_shift')}


@dataclass
class Layer:
    name: str = 'Plan 1'
    items: list[Item] = field(default_factory=list)
    visible: bool = True
    locked: bool = False
    id: str = field(default_factory=new_id)
    extra: dict = field(default_factory=dict)
    #: Outil (= couleur) du calque, comme dans TypeEdit : les objets créés
    #: dans le calque prennent cet outil.
    tool: int = 0


@dataclass
class Document:
    layers: list[Layer] = field(default_factory=lambda: [Layer()])
    plate: Plate | None = None
    tools: list[Tool] = field(default_factory=lambda: [
        Tool(i, c, f'Outil {i + 1}') for i, c in enumerate(DEFAULT_TOOL_COLORS)])
    #: Fichier d'origine, format et remarques de lecture.
    source_path: str = ''
    source_format: str = ''
    report: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)
    #: Identifiant du calque actif (vide : le premier).
    active: str = ''

    # --- parcours ---------------------------------------------------------
    def iter_items(self, *, visible_only: bool = False) -> Iterator[Item]:
        """Tous les objets de premier niveau, calque par calque."""
        for layer in self.layers:
            if visible_only and not layer.visible:
                continue
            for it in layer.items:
                if not visible_only or it.visible:
                    yield it

    def iter_leaves(self, *, visible_only: bool = False) -> Iterator[Item]:
        """Objets feuilles (groupes dépliés)."""
        def walk(it):
            if isinstance(it, Group):
                for ch in it.children:
                    if not visible_only or ch.visible:
                        yield from walk(ch)
            else:
                yield it
        for it in self.iter_items(visible_only=visible_only):
            yield from walk(it)

    def bbox(self, *, include_plate: bool = False, visible_only: bool = False):
        boxes = [it.bbox() for it in self.iter_items(visible_only=visible_only)]
        if include_plate and self.plate:
            p = self.plate
            boxes.append((p.x, p.y, p.x + p.width, p.y + p.height))
        return bbox_union(boxes)

    def tool_width(self, index: int) -> float:
        for t in self.tools:
            if t.index == index:
                return float(getattr(t, 'width', 0.0) or 0.0)
        return 0.0

    def tool_color(self, index: int) -> str:
        for t in self.tools:
            if t.index == index:
                return t.color
        return DEFAULT_TOOL_COLORS[index % len(DEFAULT_TOOL_COLORS)]

    def item_color(self, it) -> str:
        """Couleur d'un objet : celle de son outil, ou la couleur propre d'une courbe lue dans TypeEdit, tant qu'elle reste sur
        cet outil. Sans couleur propre, TypeEdit écrit du noir ; une courbe blanche, qu'il ne montre plus, reste visible ici."""
        user = own_color(it)                             # la couleur donnée à l'objet : quel que soit son outil
        if user:
            return user
        own = it.extra.get('te_color') if isinstance(it.extra, dict) else None
        if own and len(own) == 2 and own[1] == int(it.tool) and str(own[0]).lower() not in ('#000000', '#ffffff'):
            return own[0]
        return self.tool_color(it.tool)

    def tool_colors(self, items) -> dict:
        """{outil: couleur} des objets `items` (groupes dépliés) : leurs couleurs, à emporter
        avec eux dans un autre dessin (symbole, import)."""
        out = {}
        for it in items:
            for leaf in _leaf_items(it):
                out.setdefault(int(leaf.tool), self.tool_color(int(leaf.tool)))
        return out

    def adopt_tool_colors(self, items, colors: dict) -> dict:
        """Objets venus d'un autre dessin (`colors` : {outil: couleur} là-bas) : ils gardent leurs
        couleurs ici. Un outil de même couleur est repris ; sinon l'outil de même numéro prend la
        couleur s'il ne sert à rien d'autre, ou un outil neuf est ajouté. Rend {ancien: nouveau}."""
        used = {int(lf.tool) for L in self.layers for it in L.items for lf in _leaf_items(it)}
        remap = {}
        for idx, col in sorted((int(k), str(v)) for k, v in (colors or {}).items()):
            want = col.lower()
            if self.tool_color(idx).lower() == want:
                continue
            same = next((t.index for t in self.tools if t.color.lower() == want), None)
            if same is not None:
                remap[idx] = same
                continue
            if idx not in used and idx not in remap.values():
                self.tools = [t for t in self.tools if t.index != idx] + [Tool(idx, col, f'Outil {idx + 1}')]
                self.tools.sort(key=lambda t: t.index)
                continue
            new = max([t.index for t in self.tools] + list(used) + list(remap.values()) + [idx]) + 1
            self.tools.append(Tool(new, col, f'Outil {new + 1}'))
            remap[idx] = new
        if remap:
            for it in items:
                for leaf in [it] + list(_walk_children(it)):
                    leaf.tool = remap.get(int(leaf.tool), leaf.tool)
        return remap

    def find(self, item_id: str) -> Item | None:
        for it in self.iter_leaves():
            if it.id == item_id:
                return it
        return None

    @property
    def active_layer(self) -> Layer:
        if not self.layers:
            self.layers.append(Layer())
        for L in self.layers:
            if L.id == self.active:
                return L
        return self.layers[0]

    def layer_of(self, item: Item) -> Layer | None:
        """Calque contenant l'objet de premier niveau `item`."""
        for L in self.layers:
            if any(it is item for it in L.items):
                return L
        return None

    def infer_layer_tools(self) -> None:
        """Outil de chaque calque = outil le plus fréquent de ses objets
        (fichiers importés sans notion d'outil par calque)."""
        from collections import Counter
        for L in self.layers:
            c = Counter(getattr(it, 'tool', 0) for it in L.items)
            if c:
                L.tool = c.most_common(1)[0][0]

    def add(self, item: Item, layer: Layer | None = None) -> Item:
        (layer or self.active_layer).items.append(item)
        return item

    def stats(self) -> dict:
        n_items = n_contours = n_segments = 0
        for it in self.iter_leaves():
            n_items += 1
            p = it.path if isinstance(it, Shape) else getattr(it, 'outline', None)
            if p:
                n_contours += len(p.contours)
                n_segments += p.segment_count()
        return {'objets': n_items, 'contours': n_contours, 'segments': n_segments}
