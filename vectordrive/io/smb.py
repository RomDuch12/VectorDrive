"""Symboles TypeEdit (.smb) : dessins enregistrés sans coordonnées.

Même archive MFC que le VND :

    en-tête 12 octets : magic 0x00061074, u32 début des données, u32 ?
    aperçu DIB 100 × 100
    u32 n, puis n noms de police de 64 octets (table des polices du symbole)
    zone racine, sérialisée sans étiquette (format moderne ou ancien)

À l'insertion, un symbole est posé à l'endroit voulu : ses coordonnées
propres ne comptent pas (d'où « sans coordonnées »).

Couleurs (r547) : un symbole TypeEdit n'a pas de couleur (elle vient du
calque où on le pose). VectorDrive ajoute après l'archive un petit bloc
« VDSMBCOL » (JSON : couleur de chaque outil employé, outil de chaque
zone) que TypeEdit ne lit pas ; relu, il redonne à chaque objet son outil
et sa couleur.
"""
from __future__ import annotations

import pathlib
import struct

from ..core.document import Document, Group, Layer
from ..core.geom import Affine
from . import vnd
from .mfc import Archive
from ..core import progress

MAGIC = 0x00061074
#: bloc des couleurs de VectorDrive, après l'archive : signature, u32 longueur, JSON
COLORS_MAGIC = b'VDSMBCOL'
#: bloc des couleurs écrit (réglage symboles/couleurs, F10 › Fichiers)
KEEP_COLORS = True
#: textes TypeEdit modifiables à l'export en SMB (réglage symboles/textes_vivants, F10 › Fichiers)
LIVE_TEXTS = True


class SmbError(ValueError):
    pass


def parse(data: bytes):
    if len(data) < 12:
        raise SmbError('fichier trop court')
    magic, start, _x = struct.unpack_from('<3I', data, 0)
    if magic != MAGIC:
        raise SmbError(f'signature inconnue {magic:#x}' + (' (fichier PDF renommé)' if data[:4] == b'%PDF' else ''))
    if start + 4 > len(data):
        raise SmbError('début des données hors du fichier')
    ar = Archive(data, start, vnd.READERS)
    n = ar.u32()
    if n > 64:
        raise SmbError(f'table des polices aberrante ({n})')
    font_table = [ar.raw(64).split(b'\0')[0].decode('cp1252', 'replace') for _ in range(n)]
    root = ar.embedded('CObDaoCtn', 0)
    return root, font_table, ar


def rewrite(data: bytes) -> bytes:
    """Relit puis réécrit un symbole : doit redonner le fichier à l'identique."""
    from .vnd_write import MfcWriter
    root, font_table, ar = parse(data)
    start = struct.unpack_from('<I', data, 4)[0]
    w = MfcWriter()
    w.u32(len(font_table))
    w.raw(data[start + 4:start + 4 + 64 * len(font_table)])
    w.embedded(root)
    return data[:start] + bytes(w.buf) + data[ar.pos:]


def thumbnail_dib(data: bytes) -> bytes | None:
    """Aperçu DIB de l'en-tête (BITMAPINFOHEADER trouvé avant les données)."""
    start = struct.unpack_from('<I', data, 4)[0]
    i = data.find(struct.pack('<IiiHH', 40, 100, 100, 1, 8), 12, start)
    if i < 0:
        i = data.find(struct.pack('<IiiHH', 40, 100, 100, 1, 4), 12, start)
    return data[i:start] if i >= 0 else None


def read(path) -> Document:
    data = pathlib.Path(path).read_bytes()
    if data[:5] == b'%PDF-':
        # symbole enregistré en PDF sous l'extension .smb (cela arrive)
        from . import pdf
        doc = pdf.read(path)
        doc.report.insert(0, 'fichier PDF portant l\'extension .smb : lu comme un PDF')
        return doc
    root, font_table, ar = parse(data)
    doc = Document(layers=[Layer(name=pathlib.Path(path).stem)], source_path=str(path),
                   source_format='smb')
    colors = read_colors(data, ar.pos)
    zones = colors.get('zones') or []
    items = []
    looks = colors.get('objets') or []
    for i, ch in enumerate(root.children):
        got = vnd._to_items(ch, doc.report, {'fonts': font_table})
        if i < len(zones):
            _apply_tools(got, zones[i])
        if i < len(looks):
            _apply_looks(got, looks[i])
        items.extend(got)
    for k, col in (colors.get('tools') or {}).items():
        try:
            idx = int(k)
        except ValueError:
            continue
        from ..core.document import Tool
        doc.tools = [t for t in doc.tools if t.index != idx] + [Tool(idx, str(col), f'Outil {idx + 1}')]
    doc.tools.sort(key=lambda t: t.index)
    if len(items) > 1:
        items = [Group(children=items, name=pathlib.Path(path).stem)]
    doc.layers[0].items = items
    doc.extra['smb_fonts'] = font_table
    doc.extra['smb_colors'] = bool(colors)
    doc.report = vnd.summarize_report(doc.report)
    return doc


def read_colors(data: bytes, pos: int) -> dict:
    """Bloc des couleurs de VectorDrive placé en `pos` (après l'archive), {} s'il manque."""
    import json
    if data[pos:pos + len(COLORS_MAGIC)] != COLORS_MAGIC or pos + len(COLORS_MAGIC) + 4 > len(data):
        return {}
    n = struct.unpack_from('<I', data, pos + len(COLORS_MAGIC))[0]
    start = pos + len(COLORS_MAGIC) + 4
    try:
        v = json.loads(data[start:start + n].decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return {}
    return v if isinstance(v, dict) else {}


def _apply_tools(items, spec) -> None:
    """Outil(s) d'une zone relue : un numéro pour toute la zone, ou un par objet (dans l'ordre)."""
    leaves = [lf for it in items for lf in _iter_leaves(it)]
    if isinstance(spec, int):
        tools = [spec] * len(leaves)
    elif isinstance(spec, list) and spec and all(isinstance(t, int) for t in spec):
        tools = spec if len(spec) == len(leaves) else [spec[0]] * len(leaves)
    else:
        return
    for lf, t in zip(leaves, tools):
        lf.tool = t
    for it in items:
        if isinstance(it, Group):
            it.tool = tools[0] if tools else it.tool


def _look(lf) -> dict:
    """Ce qu'un objet montre en plus de son outil : sa couleur propre (« c »), son remplissage (« f »)."""
    from ..core.document import own_color
    out = {}
    c = own_color(lf)
    if c:
        out['c'] = c
    if getattr(lf, 'filled', False):
        out['f'] = 1
    return out


def _apply_looks(items, spec) -> None:
    """Couleur propre et remplissage des objets d'une zone relue (`_look`, un par objet dans l'ordre). Un texte
    écrit en courbes revient en plusieurs objets : s'ils avaient tous le même aspect, chacun le reprend."""
    from ..core.document import OWN_COLOR
    leaves = [lf for it in items for lf in _iter_leaves(it)]
    if not isinstance(spec, list) or not spec or not all(isinstance(x, dict) for x in spec):
        return
    if len(spec) != len(leaves):
        if any(x != spec[0] for x in spec):
            return
        spec = [spec[0]] * len(leaves)
    for lf, look in zip(leaves, spec):
        c = look.get('c')
        if isinstance(c, str) and len(c) == 7 and c.startswith('#'):
            lf.extra[OWN_COLOR] = c
        if look.get('f') and hasattr(lf, 'filled'):
            lf.filled = True


def _colors_block(items, tools: dict | None) -> bytes:
    """Bloc des couleurs (outil de chaque zone, couleur de chaque outil employé ; version 2 : couleur propre et
    remplissage de chaque objet, clé « objets » que les versions d'avant ne lisent pas), b'' si tout est à l'outil 0
    de couleur ordinaire, sans couleur propre ni remplissage."""
    import json
    if not KEEP_COLORS:
        return b''
    zones = []
    for it in items:
        t = [int(lf.tool) for lf in _iter_leaves(it)]
        zones.append(t[0] if t and len(set(t)) == 1 else t)
    looks = [[_look(lf) for lf in _iter_leaves(it)] for it in items]
    styled = any(x for row in looks for x in row)
    used = sorted({int(lf.tool) for it in items for lf in _iter_leaves(it)})
    cols = {str(i): (tools or {}).get(i) for i in used if (tools or {}).get(i)}
    if used == [0] and not cols and not styled:
        return b''
    data = {'v': 2 if styled else 1, 'tools': cols, 'zones': zones}
    if styled:
        data['objets'] = looks
    blob = json.dumps(data, separators=(',', ':')).encode('utf-8')
    return COLORS_MAGIC + struct.pack('<I', len(blob)) + blob


def as_group(path) -> Group | None:
    """Le symbole comme un seul objet, centré sur l'origine, prêt à poser (ses couleurs dans
    `extra['tool_colors']`, à reprendre par le dessin où on le pose)."""
    doc = read(path)
    items = doc.layers[0].items
    if not items:
        return None
    g = items[0] if isinstance(items[0], Group) else Group(children=items)
    bb = g.bbox()
    if bb:
        g = g.transformed(Affine.translation(-(bb[0] + bb[2]) / 2, -(bb[1] + bb[3]) / 2))
    g.name = pathlib.Path(path).stem
    # une copie posée n'est pas l'objet du fichier symbole (GUID, cotes…)
    g = g.clone()
    if doc.extra.get('smb_colors'):                   # symbole TypeEdit sans couleurs : celles du calque
        g.extra['tool_colors'] = doc.tool_colors([g])
    return g


# --- écriture --------------------------------------------------------------------

#: Taille de l'en-tête des symboles V15 : 12 octets + aperçu DIB 8 bits
#: 100 × 100 (40 + palette 1024 + 10 000 pixels).
DATA_START = 11076
VERSION_V15 = 1100


def _palette() -> bytes:
    """Palette 256 couleurs : couleurs fixes de Windows en tête et en fin
    (0 = noir, 255 = blanc, comme les symboles TypeEdit), gris au milieu."""
    head = [(0, 0, 0), (128, 0, 0), (0, 128, 0), (128, 128, 0), (0, 0, 128), (128, 0, 128),
            (0, 128, 128), (192, 192, 192), (192, 220, 192), (166, 202, 240)]
    tail = [(255, 251, 240), (160, 160, 164), (128, 128, 128), (255, 0, 0), (0, 255, 0),
            (255, 255, 0), (0, 0, 255), (255, 0, 255), (0, 255, 255), (255, 255, 255)]
    mid = [(v, v, v) for v in (int(10 + i * 235 / 235) for i in range(236))]
    out = bytearray()
    for r, g, b in head + mid + tail:
        out += bytes((b, g, r, 0))                 # RGBQUAD : bleu, vert, rouge, 0
    return bytes(out)


def _palette_rgb() -> list[tuple[int, int, int]]:
    pal = _palette()
    return [(pal[i + 2], pal[i + 1], pal[i]) for i in range(0, len(pal), 4)]


def thumbnail_8bpp(leaves, tools: dict | None = None) -> bytes:
    """Aperçu DIB 100 × 100 du symbole (celui de la bibliothèque et de TypeEdit) ; `tools` ({outil:
    couleur}) : chaque trait à la couleur la plus proche de la palette, sinon tout en noir."""
    from .vnd_write import ink_pixels_by_leaf
    pix = bytearray(b'\xff' * 10000)              # blanc
    pal = _palette_rgb()
    index: dict = {}

    def nearest(col: str) -> int:
        if col not in index:
            c = col.lstrip('#')
            rgb = (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)) if len(c) == 6 else (0, 0, 0)
            index[col] = min(range(len(pal) - 1), key=lambda i: sum((a - b) ** 2 for a, b in zip(pal[i], rgb)))
        return index[col]
    for (px, py), leaf in ink_pixels_by_leaf(leaves, 100, 100).items():
        col = (tools or {}).get(int(getattr(leaf, 'tool', 0) or 0))
        pix[py * 100 + px] = nearest(col) if col else 0     # noir sans couleur
    header = struct.pack('<IiiHHIIiiII', 40, 100, 100, 1, 8, 0, 10000, 2953, 2953, 0, 0)
    return header + _palette() + bytes(pix)


def build(items, *, live_texts: bool = False, tools: dict | None = None) -> bytes:
    """Symbole V15 à partir d'objets VectorDrive : centré sur l'origine.
    Textes en courbes (table de polices vide), comme les symboles TypeEdit
    sans texte vivant ; `live_texts` : textes TypeEdit
    vivants (`CParagraphe`) et table des polices du symbole. `tools` :
    {outil: couleur} du dessin — couleurs gardées dans le bloc VDSMBCOL."""
    from ..core.document import Text, drop_source_object, struct_copy
    from ..core.geom import bbox_union
    from . import paragraph as PG
    from .mfc import MfcClass, MfcObject
    from .vnd_write import SCHEMAS, MfcWriter, _bbox_m, _obdao_fields, _zone, curves_reason

    def plain(it):
        c = struct_copy(it)

        def walk(x):
            drop_source_object(x)
            for ch in getattr(x, 'children', ()):
                walk(ch)
        walk(c)
        return c
    items = [plain(it) for it in items if it.visible]
    bb = bbox_union(it.bbox() for it in items)
    if not bb:
        raise SmbError('rien à enregistrer')
    m = Affine.translation(-(bb[0] + bb[2]) / 2, -(bb[1] + bb[3]) / 2)
    items = [it.transformed(m) for it in items]
    root = MfcObject(MfcClass('CObDaoCtn', 0))
    root.fields = _obdao_fields(_bbox_m(bbox_union(it.bbox() for it in items)))
    root.fields['ctn_version'] = 3
    font_table: list[str] = []

    def zone(it):
        """Comme `_zone`, mais un texte devient un paragraphe vivant (dans
        une zone, comme TypeEdit) quand c'est possible."""
        if live_texts and isinstance(it, Text) and curves_reason(it) is None:   # mêmes règles que le VND
            name = it.font
            idx = font_table.index(name) if name in font_table else len(font_table)
            p = PG.build(it, idx)
            if p is not None:
                if name not in font_table:
                    font_table.append(name)
                z = MfcObject(MfcClass('CZone', SCHEMAS['CZone']))
                z.fields = _obdao_fields(p.fields['bbox'])
                z.fields['ctn_version'] = 3
                z.children.append(p)
                return z
        if live_texts and isinstance(it, Group):
            kids = [k for k in (zone(ch) for ch in it.children) if k is not None]
            if not kids:
                return None
            z = MfcObject(MfcClass('CZone', SCHEMAS['CZone']))
            z.fields = _obdao_fields(_bbox_m(it.bbox()))
            z.fields['ctn_version'] = 3
            z.children = kids
            return z
        return _zone(it)

    import types
    from ..core.document import DEFAULT_TOOL_COLORS
    from .vnd_write import _using_tools

    def color_of(index):                                 # la couleur des courbes écrites : celle de leur outil
        return (tools or {}).get(int(index)) or DEFAULT_TOOL_COLORS[int(index) % len(DEFAULT_TOOL_COLORS)]
    kept = []
    with _using_tools(types.SimpleNamespace(tool_color=color_of)):
        for it in items:
            node = zone(it)
            if node is not None:
                root.children.append(node)
                kept.append(it)
    w = MfcWriter()
    w.u32(len(font_table))                          # table des polices (vide sans texte vivant)
    for name in font_table:
        w.raw(name.encode('cp1252', 'replace')[:63].ljust(64, b'\0'))
    w.embedded(root)
    leaves = [lf for it in items for lf in _iter_leaves(it)]
    head = struct.pack('<3I', MAGIC, DATA_START, VERSION_V15) + thumbnail_8bpp(leaves, tools)
    assert len(head) == DATA_START
    return head + bytes(w.buf) + _colors_block(kept, tools)


def _iter_leaves(it):
    if isinstance(it, Group):
        for ch in it.children:
            yield from _iter_leaves(ch)
    else:
        yield it


def write(items, path, *, live_texts: bool = False, tools: dict | None = None) -> None:
    pathlib.Path(path).write_bytes(build(items, live_texts=live_texts, tools=tools))


def write_document(doc, path) -> None:
    """Export : le dessin visible entier, comme un symbole (couleurs gardées)."""
    items = list(doc.iter_items(visible_only=True))
    write(items, path, live_texts=LIVE_TEXTS, tools=doc.tool_colors(items))



# --- textes contenus (recherche dans la bibliothèque) --------------------------------

def texts_of(data: bytes) -> list[str]:
    """Textes TypeEdit d'un symbole (paragraphes et valeurs de cotes)."""
    root, _fonts, _ar = parse(data)
    return _tree_texts(root)


def vnd_texts_of(data: bytes) -> list[str]:
    """Textes TypeEdit d'un dessin VND (paragraphes et valeurs de cotes), même partiellement lisible."""
    root, _ar = vnd.parse(data, partial=True)
    return _tree_texts(root)


def _tree_texts(root) -> list[str]:
    out: list[str] = []

    def walk(o):
        if o is None:
            return
        name = o.cls.name
        if name == 'CParagraphe':
            t = vnd.paragraph_text(o).strip()
            if t:
                out.append(t)
        elif name in vnd.COTATIONS:
            t = vnd.cotation_text(o).strip()
            if t:
                out.append(t)
        for c in o.fields.get('slots', o.children) or []:
            walk(c)
    walk(root)
    return out


def file_texts(path: str) -> list[str]:
    """Textes TypeEdit d'un fichier VND ou SMB ([] s'il ne se lit pas) — dans un processus de calcul."""
    try:
        data = pathlib.Path(path).read_bytes()
        return vnd_texts_of(data) if path.lower().endswith('.vnd') else texts_of(data)
    except Exception:                                    # noqa: BLE001 — fichier abîmé : sans texte
        return []


def _stamp(f: pathlib.Path):
    st = f.stat()
    return [round(st.st_mtime, 3), st.st_size]


class TextIndex:
    """Index nom de fichier → textes contenus, gardé dans un fichier JSON
    (date et taille de chaque symbole : un symbole modifié est relu)."""

    def __init__(self, path):
        import json
        self.path = pathlib.Path(path)
        try:
            self.data = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            self.data = {}
        self.dirty = False

    def texts(self, f: pathlib.Path) -> list[str]:
        try:
            st = f.stat()
        except OSError:
            return []
        key = str(f)
        e = self.data.get(key)
        stamp = [round(st.st_mtime, 3), st.st_size]
        if e and e[0] == stamp:
            return e[1]
        try:
            data = f.read_bytes()
            t = vnd_texts_of(data) if f.suffix.lower() == '.vnd' else texts_of(data)
        except Exception:
            t = []
        self.data[key] = [stamp, t]
        self.dirty = True
        return t

    def missing(self, files) -> list:
        """Fichiers à lire (absents de l'index, ou modifiés depuis)."""
        out = []
        for f in files:
            try:
                e = self.data.get(str(f))
                if not e or e[0] != _stamp(f):
                    out.append(f)
            except OSError:
                continue
        return out

    def fill(self, files) -> int:
        """Textes des fichiers manquants lus d'avance, sur plusieurs processus s'il y en a beaucoup
        (avancement et Annuler : core.progress) ; rend le nombre de fichiers lus."""
        todo = self.missing(files)
        if not todo:
            return 0
        from ..core import workers
        got = workers.adaptive_map(file_texts, [(str(f),) for f in todo], text='Textes du fichier {0} sur {1}')
        for f, t in zip(todo, got):
            try:
                self.data[str(f)] = [_stamp(f), t]
            except OSError:
                continue
        self.dirty = True
        return len(todo)

    def save(self) -> None:
        import json
        if not self.dirty:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, ensure_ascii=False), encoding='utf-8')
            self.dirty = False
        except OSError:
            pass


def search(roots, query: str, index: 'TextIndex | None' = None, limit: int = 400,
           exts=('.smb',)) -> list[tuple[pathlib.Path, str]]:
    """Fichiers de la bibliothèque (extensions `exts`) dont le nom, ou un texte TypeEdit (SMB, VND), contient
    `query` (sans tenir compte de la casse ni des accents) : [(fichier, texte trouvé ou '')]. Les textes
    pas encore lus le sont d'avance, sur plusieurs processus s'ils sont nombreux (index gardé)."""
    import unicodedata

    def norm(s: str) -> str:
        return ''.join(c for c in unicodedata.normalize('NFD', s.lower()) if not unicodedata.combining(c))
    q = norm(query.strip())
    if not q:
        return []
    exts = tuple(e.lower() for e in exts)
    files: list[pathlib.Path] = []
    for r in roots:
        for f in pathlib.Path(r).rglob('*'):
            progress.check()
            if f.suffix.lower() in exts:
                files.append(f)
    named = {f for f in files if q in norm(f.stem)}
    hits: dict = {}
    if index is not None:
        rest = [f for f in files if f not in named and f.suffix.lower() in ('.smb', '.vnd')]
        index.fill(rest)
        for f in rest:
            hit = next((t for t in index.texts(f) if q in norm(t)), None)
            if hit is not None:
                hits[f] = hit
        index.save()
    found = [(f, hits.get(f, '')) for f in files if f in named or f in hits]
    return found[:limit]
