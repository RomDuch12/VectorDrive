"""Format natif VectorDrive (.vdz) : JSON versionné dans une archive zip.

Lisible par un humain (dézipper, ouvrir `document.json`), diffable, et
extensible : un champ inconnu d'une version future est ignoré, un champ
absent prend sa valeur par défaut.
"""
from __future__ import annotations

import json
import zipfile

import base64

from ..core.document import Document, Group, Image, Layer, Plate, Shape, Text, Tool
from ..core.geom import Affine, Conic, Contour, Cubic, Line, Path

FORMAT_VERSION = 1


def _seg_out(s) -> list:
    if isinstance(s, Line):
        return ['L', *s.p0, *s.p1]
    if isinstance(s, Cubic):
        return ['C', *s.p0, *s.p1, *s.p2, *s.p3]
    if isinstance(s, Conic):
        return ['Q', *s.p0, *s.p1, *s.p2, s.w]
    raise TypeError(s)


def _seg_in(a: list):
    k = a[0]
    if k == 'L':
        return Line((a[1], a[2]), (a[3], a[4]))
    if k == 'C':
        return Cubic((a[1], a[2]), (a[3], a[4]), (a[5], a[6]), (a[7], a[8]))
    if k == 'Q':
        return Conic((a[1], a[2]), (a[3], a[4]), (a[5], a[6]), a[7])
    raise ValueError(f'segment inconnu {k!r}')


def _path_out(p: Path | None):
    if p is None:
        return None
    return [{'closed': c.closed, 'segs': [_seg_out(s) for s in c.segments]}
            for c in p.contours]


def _path_in(d) -> Path | None:
    if d is None:
        return None
    return Path([Contour([_seg_in(s) for s in c['segs']], c.get('closed', False))
                 for c in d])


def _jsonable(v):
    """Données `extra` : on ne garde que ce qui passe en JSON."""
    try:
        json.dumps(v)
        return v
    except TypeError:
        if isinstance(v, dict):
            return {k: _jsonable(x) for k, x in v.items() if not isinstance(x, (bytes, bytearray))}
        return None


def _item_out(it) -> dict:
    base = {'id': it.id, 'name': it.name, 'tool': it.tool,
            'visible': it.visible, 'locked': it.locked,
            'extra': _jsonable(it.extra) or {}}
    if isinstance(it, Shape):
        base.update(kind='shape', path=_path_out(it.path), filled=it.filled)
    elif isinstance(it, Text):
        base.update(kind='text', text=it.text, font=it.font, size=it.size,
                    matrix=list(it.matrix.to_tuple()), align=it.align,
                    spacing=it.spacing, line_spacing=it.line_spacing,
                    width_ratio=it.width_ratio, outline=_path_out(it.outline))
    elif isinstance(it, Group):
        base.update(kind='group', children=[_item_out(c) for c in it.children])
    elif isinstance(it, Image):
        base.update(kind='image', fmt=it.fmt, matrix=list(it.matrix.to_tuple()),
                    data=base64.b64encode(it.data).decode('ascii'))
    return base


def _item_in(d: dict):
    common = dict(id=d['id'], name=d.get('name', ''), tool=d.get('tool', 0),
                  visible=d.get('visible', True), locked=d.get('locked', False),
                  extra=d.get('extra', {}))
    k = d.get('kind')
    if k == 'shape':
        return Shape(path=_path_in(d['path']) or Path(), filled=d.get('filled', False), **common)
    if k == 'text':
        return Text(text=d.get('text', ''), font=d.get('font', 'Arial'),
                    size=d.get('size', 10.0), matrix=Affine(*d.get('matrix', (1, 0, 0, 1, 0, 0))),
                    align=d.get('align', 'left'), spacing=d.get('spacing', 0.0),
                    line_spacing=d.get('line_spacing', 1.2),
                    width_ratio=d.get('width_ratio', 1.0),
                    outline=_path_in(d.get('outline')), **common)
    if k == 'group':
        return Group(children=[_item_in(c) for c in d.get('children', [])], **common)
    if k == 'image':
        return Image(data=base64.b64decode(d.get('data', '')), fmt=d.get('fmt', 'dib'),
                     matrix=Affine(*d.get('matrix', (1, 0, 0, 1, 0, 0))), **common)
    raise ValueError(f'objet inconnu {k!r}')


def _layer_out(L) -> dict:
    out = {'id': L.id, 'name': L.name, 'visible': L.visible, 'locked': L.locked,
           'tool': L.tool, 'items': [_item_out(it) for it in L.items]}
    extra = _jsonable(L.extra)
    if extra:                                            # surface posée en 2D (core.surface2d)…
        out['extra'] = extra
    return out


def to_dict(doc: Document) -> dict:
    return {
        'format': 'VectorDrive',
        'version': FORMAT_VERSION,
        'plate': doc.plate.__dict__ if doc.plate else None,
        'tools': [t.__dict__ for t in doc.tools],
        'active': doc.active,
        'layers': [_layer_out(L) for L in doc.layers],
        'extra': _doc_extra(doc),
    }


def _doc_extra(doc) -> dict:
    extra = _jsonable({k: v for k, v in doc.extra.items() if not isinstance(v, bytes)}) or {}
    import os
    from . import model3d
    src = model3d.source_of(doc)
    if src:                                              # pièce 3D du dessin : retrouvée à la réouverture
        extra = {**extra, model3d.SOURCE_KEY: os.path.abspath(src)}
    return extra


def from_dict(d: dict) -> Document:
    if d.get('format') != 'VectorDrive':
        raise ValueError('ce n\'est pas un document VectorDrive')
    doc = Document(layers=[])
    if d.get('plate'):
        from dataclasses import fields as _fields
        names = {f.name for f in _fields(Plate)}             # champs d'une autre version ignorés
        doc.plate = Plate(**{k: v for k, v in d['plate'].items() if k in names})
    if d.get('tools'):
        doc.tools = [Tool(**t) for t in d['tools']]
    for L in d.get('layers', []):
        doc.layers.append(Layer(name=L.get('name', ''), visible=L.get('visible', True),
                                locked=L.get('locked', False), id=L.get('id') or Layer().id,
                                tool=L.get('tool', 0), extra=dict(L.get('extra') or {}),
                                items=[_item_in(i) for i in L.get('items', [])]))
        if 'tool' not in L:
            doc.layers[-1].tool = next((it.tool for it in doc.layers[-1].items), 0)
    doc.active = d.get('active', '')
    doc.extra = d.get('extra', {})
    return doc


def _chunks(v, depth: int = 0):
    """Morceaux de `json.dumps(v, ensure_ascii=False, separators=(',', ':'))`
    — dictionnaires et listes ouverts jusqu'aux objets de premier niveau
    (document, calques, objets), le reste encodé d'un coup."""
    if depth < 4 and isinstance(v, dict) and all(type(k) is str for k in v):
        yield '{'
        for i, (k, x) in enumerate(v.items()):
            yield (',' if i else '') + json.dumps(k, ensure_ascii=False) + ':'
            yield from _chunks(x, depth + 1)
        yield '}'
    elif depth < 4 and isinstance(v, list):
        yield '['
        for i, x in enumerate(v):
            if i:
                yield ','
            yield from _chunks(x, depth + 1)
        yield ']'
    else:
        yield json.dumps(v, ensure_ascii=False, separators=(',', ':'))


def dumps(d: dict) -> str:
    """JSON du document, identique à `json.dumps` mais encodé objet par
    objet : un fil de fond rend la main à l'interface entre deux objets."""
    return ''.join(_chunks(d))


#: le VND dont vient le dessin (`doc.extra['vnd_source']`), gardé tel quel dans le .vdz : relu, le dessin se réécrit en VND
#: comme avant l'enregistrement (textes et cotes TypeEdit modifiables, outils, machine et parcours de la source)
SOURCE_MEMBER = 'source.vnd'


def vnd_source(doc: Document) -> bytes | None:
    data = doc.extra.get('vnd_source') if isinstance(doc.extra, dict) else None
    return bytes(data) if isinstance(data, (bytes, bytearray)) and data else None


def attach_source(doc: Document, data: bytes) -> bool:
    """Rend au dessin relu le VND dont il vient, et ce que le JSON n'avait pas gardé (`vnd.relink`). False : `data`
    illisible, rien de changé (le dessin s'écrira comme un dessin neuf)."""
    from . import vnd
    if not isinstance(doc.extra, dict) or vnd.relink(doc, data) is None:
        return False
    doc.extra['vnd_source'] = data
    return True


def write(doc: Document, path, *, level: int | None = None) -> None:
    """`level` : compression (1 rapide … 9 compacte ; défaut de zlib). Le
    JSON est compressé au fil de l'encodage, par paquets d'environ 1 Mo. Le
    VND d'origine, s'il y en a un, est joint (`SOURCE_MEMBER`)."""
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED, compresslevel=level) as z:
        with z.open('document.json', 'w') as f:
            buf, n = [], 0
            for part in _chunks(to_dict(doc)):
                buf.append(part)
                n += len(part)
                if n > 1 << 20:
                    f.write(''.join(buf).encode('utf-8'))
                    buf, n = [], 0
            f.write(''.join(buf).encode('utf-8'))
        z.writestr('mimetype', 'application/x-vectordrive')
        src = vnd_source(doc)
        if src is not None:
            z.writestr(SOURCE_MEMBER, src, compresslevel=1)


def snapshot(doc: Document) -> Document:
    """Copie du document qu'un fil de fond peut enregistrer pendant que
    l'interface continue : structure copiée, tracés partagés (jamais
    modifiés en place), guides et notes copiés."""
    import copy
    from ..core.document import struct_copy_layers
    s = copy.copy(doc)
    s.layers = struct_copy_layers(doc.layers)
    s.plate = copy.deepcopy(doc.plate)
    s.tools = copy.deepcopy(doc.tools)
    s.extra = {k: (copy.deepcopy(v) if k in ('guides', 'guides_obliques', 'notes') else v)
               for k, v in doc.extra.items()}
    return s


def write_atomic(doc: Document, path, *, level: int | None = None) -> None:
    """Écrit à côté puis remplace : jamais de fichier à moitié écrit."""
    import os
    tmp = f'{path}.tmp'
    try:
        write(doc, tmp, level=level)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def read(path) -> Document:
    with zipfile.ZipFile(path) as z:
        d = json.loads(z.read('document.json').decode('utf-8'))
        src = z.read(SOURCE_MEMBER) if SOURCE_MEMBER in z.namelist() else None
    doc = from_dict(d)
    if src:
        attach_source(doc, src)
    doc.source_path = str(path)
    doc.source_format = 'vdz'
    return doc
