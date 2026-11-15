"""Bases d'outils TypeEdit / LaserType (`TeToolDataBase.Dbt`,
`LtToolDataBase.Dbt`) : archive MFC, arbre de `BdONode` (dossiers) dont
les feuilles sont des `BdOTool`.
Interopérabilité seulement.

BdONode : i32 n (−1 = feuille outil), CString nom, u8, puis n nœuds ou
l'outil. BdOTool : i32 version, CString nom, bloc de définition (0x378
octets « TOutilASCII » avant la version 3, 0x3F8 « TOutil » ensuite),
puis (version ≥ 2) une table de paramètres CMapParam (u32 n, n × (u32,
clé, valeur, u32, u32) ; chaînes CVnStringUnicode : u32 longueur puis les
caractères UTF-16 et leur zéro final), p. ex. MODE_GRAVURE = 0.

Bloc (TOutil ; TOutilASCII : chaînes de 64 octets ANSI au lieu de 64
caractères UTF-16, d'où un décalage de −0x80 après elles) :

    +0x00 i32 index    +0x04 i32 type (0 conique, 1 cylindrique, 2 boule,
    3 torique, 4 conique à bout rond, 6 laser, 7 couteau)
    +0x08 f64 diamètre (m)   +0x10 f64 demi-angle (rad)   +0x18 f64 troncature (m)
    +0x20 f64 rayon (m)      +0x28 i32 nb d'échantillons, +0x30 20 × (z, r) f64
    +0x170 référence         +0x1F0 fournisseur
    +0x270 profondeur mini, maxi, passe, hauteurs de passe mini et maxi (m),
           avances nominale, rapide, mini, maxi, descente, plongée (m/min),
           broche nominale, mini, maxi (tr/min), vitesse de coupe
    +0x2E8 i32 nombre de dents
"""
from __future__ import annotations

import math
import pathlib
import struct
from dataclasses import dataclass, field

from ..io.mfc import Archive, ArchiveError, MfcObject
from .model import CamTool

KINDS = {0: 'conique', 1: 'fraise', 2: 'boule', 3: 'fraise', 4: 'conique', 6: 'laser', 7: 'fraise'}
NAMES = {0: 'conique', 1: 'cylindrique', 2: 'boule', 3: 'torique', 4: 'conique à bout rond', 6: 'laser',
         7: 'couteau'}


class DbtError(ValueError):
    pass


@dataclass
class DbtTool:
    path: list                      # dossiers, du haut vers le bas
    name: str
    version: int
    type: int
    tool: CamTool
    raw: bytes = b''
    notes: list = field(default_factory=list)


def _read_node(ar: Archive, obj: MfcObject) -> None:
    n = ar.i32()
    obj.fields['name'] = ar.cstring()
    obj.fields['flag'] = ar.u8()
    if n < 0:
        obj.fields['tool'] = ar.read_object()
    else:
        if n > 100000:
            raise ArchiveError(f'nœud de {n} enfants à {ar.pos}')
        for _ in range(n):
            ch = ar.read_object()
            if ch is not None:
                obj.children.append(ch)


def _vn_string(ar: Archive) -> str:
    """CVnStringUnicode (Fondation) : u32 n puis n + 1 caractères UTF-16
    (zéro final compris)."""
    n = ar.u32()
    if n > 1 << 20:
        raise ArchiveError(f'chaîne de {n} caractères à {ar.pos - 4}')
    return ar.raw(2 * (n + 1)).decode('utf-16-le', 'replace').rstrip(chr(0))


def _read_tool(ar: Archive, obj: MfcObject) -> None:
    v = obj.fields['version'] = ar.i32()
    obj.fields['name'] = ar.cstring()
    obj.fields['block'] = ar.raw(0x378 if v < 3 else 0x3f8)
    params = []
    if v >= 2:
        n = ar.u32()
        if n > 10000:
            raise ArchiveError(f'table de {n} paramètres à {ar.pos}')
        for _ in range(n):
            params.append((ar.u32(), _vn_string(ar), _vn_string(ar), ar.u32(), ar.u32()))
    obj.fields['params'] = params


READERS = {'BdONode': _read_node, 'BdOTool': _read_tool}


def _tool_of(name: str, version: int, b: bytes) -> tuple[int, CamTool, list]:
    wide = version >= 3 or len(b) >= 0x3f8
    d = lambda o: struct.unpack_from('<d', b, o)[0]       # noqa: E731
    ty = struct.unpack_from('<i', b, 4)[0]
    if wide:
        ref = b[0x170:0x1f0].decode('utf-16-le', 'replace').split('\0')[0]
        sup = b[0x1f0:0x270].decode('utf-16-le', 'replace').split('\0')[0]
        o = 0x270
    else:
        ref = b[0x170:0x1b0].split(b'\0')[0].decode('cp1252', 'replace')
        sup = b[0x1b0:0x1f0].split(b'\0')[0].decode('cp1252', 'replace')
        o = 0x1f0
    vals = struct.unpack_from('<15d', b, o)
    (_mind, _maxd, passd, _minh, _maxh, fnom, _ffast, _fmin, _fmax, fdes, fplg, snom, _smin, _smax,
     _cut) = vals
    teeth = struct.unpack_from('<i', b, o + 0x78)[0]
    notes = []
    kind = KINDS.get(ty, 'fraise')
    if ty in (3, 7) or ty not in KINDS:
        notes.append(f'outil {NAMES.get(ty, ty)} : repris comme fraise droite')
    t = CamTool(name=name, kind=kind, diameter=round(d(8) * 1000, 6),
                angle=round(2 * math.degrees(d(0x10)), 6) if kind == 'conique' else 0.0,
                tip=round((d(0x18) if ty == 0 else 2 * d(0x20)) * 1000, 6) if kind == 'conique' else 0.0,
                flutes=max(1, teeth), number=struct.unpack_from('<i', b, 0)[0], ref=ref, vendor=sup,
                spindle=snom, feed=round(fnom * 1000, 6), plunge=round(fplg * 1000, 6),
                ramp_feed=round(fdes * 1000, 6), step_down=round(passd * 1000, 6) or 0.2)
    return ty, t, notes


def read_bytes(data: bytes) -> list[DbtTool]:
    ar = Archive(data, 0, READERS)
    try:
        root = ar.read_object()
    except (ArchiveError, struct.error) as ex:
        raise DbtError(f'base d\'outils illisible : {ex}') from None
    if root is None or root.cls.name != 'BdONode':
        raise DbtError('ce n\'est pas une base d\'outils TypeEdit')
    out: list[DbtTool] = []

    def walk(node, path):
        tool = node.fields.get('tool')
        if tool is not None:
            ty, t, notes = _tool_of(tool.fields['name'] or node.fields['name'], tool.fields['version'],
                                    tool.fields['block'])
            out.append(DbtTool(path, t.name, tool.fields['version'], ty, t, tool.fields['block'], notes))
            return
        for ch in node.children:
            walk(ch, path + [node.fields['name']] if node is not root else path)
    walk(root, [])
    return out


def read(path) -> list[DbtTool]:
    return read_bytes(pathlib.Path(path).read_bytes())


# --- écriture (version 2, bloc TOutilASCII) ---------------------------------------------

def _tool_block(t: CamTool) -> bytes:
    b = bytearray(0x378)
    ty = {'conique': 0, 'fraise': 1, 'boule': 2, 'laser': 6, 'foret': 1}.get(t.kind, 1)
    struct.pack_into('<ii', b, 0, int(t.number), ty)
    struct.pack_into('<4d', b, 8, t.diameter / 1000,
                     math.radians(t.angle) / 2 if t.kind == 'conique' else 0.0,
                     (t.tip if t.kind == 'conique' else t.diameter) / 1000, 0.0)
    b[0x170:0x1b0] = t.ref.encode('cp1252', 'replace')[:63].ljust(0x40, b'\0')
    b[0x1b0:0x1f0] = t.vendor.encode('cp1252', 'replace')[:63].ljust(0x40, b'\0')
    f = lambda v: v / 1000.0                              # noqa: E731
    struct.pack_into('<15d', b, 0x1f0, 0.0, 0.1, f(t.step_down), 0.0, 0.1, f(t.feed), 3.0, f(t.feed),
                     f(t.feed), f(t.ramp_feed or t.plunge), f(t.plunge), t.spindle, t.spindle, t.spindle, 0.001)
    struct.pack_into('<i', b, 0x1f0 + 0x78, max(1, int(t.flutes)))
    return bytes(b)


def _cstring(s: str) -> bytes:
    b = s.encode('cp1252', 'replace')
    if len(b) < 0xff:
        return bytes([len(b)]) + b
    return b'\xff' + struct.pack('<H', len(b)) + b


def write_bytes(tools: list[CamTool], folder: str = 'VectorDrive') -> bytes:
    """Base d'outils au format TypeEdit (version 2) : un dossier, un outil
    par feuille. **À valider avec TypeEdit.**"""
    out = bytearray()
    # racine : nouvelle classe BdONode (schéma 1), 1 enfant
    out += b'\xff\xff' + struct.pack('<HH', 1, 7) + b'BdONode'
    out += struct.pack('<i', 1) + _cstring('Base de données outils') + b'\x01'
    out += struct.pack('<H', 0x8001)                       # référence de classe BdONode
    out += struct.pack('<i', len(tools)) + _cstring(folder) + b'\x01'
    # table des objets MFC : 1 classe BdONode, 2 racine, 3 dossier
    tool_class = None
    count = 3
    for t in tools:
        out += struct.pack('<H', 0x8001)
        count += 1                                         # nœud de l'outil
        out += struct.pack('<i', -1) + _cstring(t.name) + b'\x00'
        if tool_class is None:
            out += b'\xff\xff' + struct.pack('<HH', 1, 7) + b'BdOTool'
            count += 1
            tool_class = count                             # classe BdOTool
        else:
            out += struct.pack('<H', 0x8000 | tool_class)
        count += 1                                         # l'outil
        out += struct.pack('<i', 2) + _cstring(t.name) + _tool_block(t) + struct.pack('<I', 0)
    return bytes(out)
