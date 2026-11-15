"""Copier-coller d'objets entre TypeEdit et VectorDrive.

Quand on copie dans TypeEdit, il dépose deux formats Windows à son nom, en plus d'une image :

- `TypeEditZoneVersion` : 32 octets, 1 puis le numéro de format (0x2A3), complétés de zéros ;
- `TypeEditZone` : la table des polices des textes (u32 n, n noms de 64 octets, comme en tête d'un VND), u16 nombre
  d'objets, puis les objets dans une seule archive MFC (la table des classes est commune) : en haut, toujours des
  `CZone`, comme dans un plan d'un VND. Coordonnées en mètres, celles du dessin. Le bloc est complété de zéros jusqu'à
  un multiple de 4 Ko.

Un objet TypeEdit ne porte pas d'outil : collé, il prend celui du plan courant, dans un sens comme dans l'autre.
"""
from __future__ import annotations

import contextlib
import struct

from ..core.document import Item, drop_source_object, struct_copy
from ..core.geom import Affine, bbox_union

FORMAT = 'TypeEditZone'
FORMAT_VERSION = 'TypeEditZoneVersion'
MIME = f'application/x-qt-windows-mime;value="{FORMAT}"'
MIME_VERSION = f'application/x-qt-windows-mime;value="{FORMAT_VERSION}"'
VERSION = struct.pack('<II', 1, 0x2A3).ljust(32, b'\0')
FONT_NAME = 64
MAX_FONTS = 4096
MAX_OBJECTS = 0xFFFF
BLOCK = 4096


class ClipError(ValueError):
    """Contenu illisible, ou rien à écrire."""


def _forget(it: Item) -> None:
    """Oublie les objets TypeEdit d'origine : ils renvoient à une table des polices qui n'est pas celle du dessin."""
    drop_source_object(it)
    for ch in getattr(it, 'children', ()):
        _forget(ch)


def read(data: bytes) -> tuple[list, list[str]]:
    """Objets d'un bloc `TypeEditZone` : (objets VectorDrive, remarques). Les outils sont à poser par l'appelant."""
    from . import vnd
    from .mfc import Archive
    data = bytes(data)
    if len(data) < 6:
        raise ClipError('bloc trop court')
    n = struct.unpack_from('<I', data, 0)[0]
    pos = 4 + FONT_NAME * n
    if n > MAX_FONTS or pos + 2 > len(data):
        raise ClipError('table des polices illisible')
    fonts = [data[4 + FONT_NAME * k:4 + FONT_NAME * (k + 1)].split(b'\0')[0].decode('cp1252', 'replace')
             for k in range(n)]
    count = struct.unpack_from('<H', data, pos)[0]
    report: list[str] = []
    items: list = []
    try:
        ar = Archive(data, pos + 2, vnd.READERS)
        ar.brep_ends = {}
        for _ in range(count):
            obj = ar.read_object()
            if obj is not None:
                items.extend(vnd._to_items(obj, report, {'fonts': fonts}))
    except Exception as ex:                              # octets venus d'ailleurs : tout échec de lecture se vaut
        raise ClipError(f'objets illisibles : {ex}') from ex
    for it in items:
        _forget(it)
    return items, report


def _in_zone(node, VW):
    """En haut du bloc, TypeEdit n'a que des zones."""
    if node.cls.name == 'CZone':
        return node
    z = VW.MfcObject(VW.MfcClass('CZone', VW.SCHEMAS['CZone']))
    z.fields = VW._obdao_fields(tuple(node.fields.get('bbox', VW.EMPTY_BBOX)))
    z.fields['ctn_version'] = 3
    z.children.append(node)
    return VW._deepen(z)


def build(items, *, fonts: list[str] | None = None, origin=None, doc=None) -> bytes:
    """Bloc `TypeEditZone` des objets. Les textes restent modifiables quand TypeEdit peut les relire (sinon, en
    courbes). `fonts` : table des polices du VND d'où viennent les objets, pour écrire tels quels ceux qu'il a lus ; sans
    elle, ils sont refaits. `origin` : origine du dessin, le zéro de TypeEdit. `doc` : le dessin, dont les outils donnent
    leur couleur aux courbes (sans lui : noires, sauf celles qui ont la leur)."""
    from . import vnd_write as VW
    work, _dropped = VW.clean_items([struct_copy(it) for it in items])
    if fonts is None:
        for it in work:
            _forget(it)
    if origin and (abs(float(origin[0])) > 1e-9 or abs(float(origin[1])) > 1e-9):
        m = Affine.translation(-float(origin[0]), -float(origin[1]))
        work = [it.transformed(m) for it in work]
    saved = VW._LIVE
    live = VW._LIVE = VW._LiveTexts(list(fonts or []))
    try:
        with VW._using_tools(doc) if doc is not None else contextlib.nullcontext():
            nodes = [_in_zone(n, VW) for n in (VW._zone(it) for it in work) if n is not None]
    finally:
        VW._LIVE = saved
    if not nodes:
        raise ClipError('rien à copier')
    if len(nodes) > MAX_OBJECTS:                         # le compteur tient sur 16 bits : une zone les réunit
        top = VW.MfcObject(VW.MfcClass('CZone', VW.SCHEMAS['CZone']))
        top.fields = VW._obdao_fields(VW._bbox_m(bbox_union(it.bbox() for it in work)))
        top.fields['ctn_version'] = 3
        top.children = nodes
        nodes = [top]
    w = VW.MfcWriter()
    w.u32(len(live.names))
    for name in live.names:
        w.raw(name.encode('cp1252', 'replace')[:FONT_NAME - 1].ljust(FONT_NAME, b'\0'))
    w.u16(len(nodes))
    for node in nodes:
        w.write_object(node)
    return bytes(w.buf).ljust(-(-len(w.buf) // BLOCK) * BLOCK, b'\0')
