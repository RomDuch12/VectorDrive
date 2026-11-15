"""Parcours d'outil de TypeEdit : fichiers `.000`, `.001`… écrits à côté
du VND (un par outil ou par passe), format « VNV ». Interopérabilité seulement.

En-tête (0x144 octets, puis 0x48 si le bit 0 des drapeaux est mis) :

    0x000  u16  drapeaux (bit 0 : en-tête étendu ; 0xfff0 : nuls)
    0x002  u32  début des données (0x18c avec l'en-tête étendu)
    0x006  4 o  version (« 0112 »)
    0x00a  256 o commentaire : outil et stratégie (« Contour 3d [CUT 3.02]… »)
    0x10a  f64  échelle (1.0 ; les coordonnées sont divisées par elle)
    0x112  6 f64 boîte : xmin, xmax, ymin, ymax, zmin, zmax (mm)
    0x142  u16
    0x144  u16 + 4 f64   outil : numéro, diamètre (m), demi-angle (rad), pointe (m), 0
    0x166  u16 + 4 f64 + u32

Enregistrements : un octet de type puis ses données (mm) —
0 rapide (x, y, z) ; 1 droite ; 2 arc horaire (fin, centre) ; 3 arc
anti-horaire ; 0x0A point ; 0x0B six réels ; 0x21 trous (u16, u16 n,
n × (3 f64, u16, u16)) ; 0x22 trous actifs (u16, u16 n, n × u16) ;
0x24 (u16, 3 f64) ; 0x30 un réel ; 0x64 (3 f64, u32) ; 0xFE point ;
0xFF fin ; autre : u16 longueur + octets (commentaire).
"""
from __future__ import annotations

import math
import pathlib
import re
import struct

from .model import Move, Toolpath

HEADER = 0x144
HEADER_EXT = 0x48
VERSION = b'0112'


class VnvError(ValueError):
    pass


def _tool_of_header(number: int, rad: float, half: float, tip: float) -> dict:
    """Outil de l'en-tête, en mm et en degrés. VectorDrive écrivait autrefois le diamètre et la pointe en mètres : ces fichiers se relisent aussi."""
    old = abs(tip - rad) < 1e-9 if half == 0 else 0 < rad < 0.02
    diameter, tip_mm = (rad * 1000, tip * 1000) if old else (2 * rad, tip)
    angle = 2 * (half if abs(half) > math.pi / 2 else math.degrees(half))
    return {'number': number, 'diameter': round(diameter, 6), 'angle': round(angle, 6), 'tip': round(tip_mm, 6)}


def read_bytes(data: bytes, name: str = '') -> Toolpath:
    if len(data) < HEADER:
        raise VnvError('fichier de parcours trop court')
    flags, off = struct.unpack_from('<HI', data, 0)
    if flags & 0xfff0 or not HEADER <= off <= len(data):
        raise VnvError('en-tête de parcours TypeEdit invalide')
    comment = data[10:0x10a].split(b'\0')[0].decode('cp1252', 'replace').strip()
    scale = struct.unpack_from('<d', data, 0x10a)[0] or 1.0
    tp = Toolpath(op_id='', tool_id='', name=comment or name, source='typeedit')
    tp.header = {'flags': flags, 'version': data[6:10].decode('ascii', 'replace'), 'comment': comment,
                 'scale': scale, 'box': struct.unpack_from('<6d', data, 0x112)}
    if flags & 1 and len(data) >= HEADER + HEADER_EXT:
        # outil, relevé sur les parcours de TE13 : numéro, rayon (mm), demi-angle (degrés, ou radians selon le parcours), pointe (mm)
        n, rad, half, tip, _v = struct.unpack_from('<H4d', data, 0x144)
        tp.header['tool'] = _tool_of_header(n, rad, half, tip)
    moves = tp.moves
    pos = off
    k = 1.0 / scale
    try:
        pos, skipped = _records(data, pos, moves, k)
    except struct.error:
        raise VnvError('parcours tronqué') from None
    if skipped:
        tp.warnings.append(f'{skipped} enregistrement(s) non géométrique(s) ignoré(s)')
    return tp


def _records(data: bytes, pos: int, moves: list, k: float) -> tuple[int, int]:
    unpack = struct.unpack_from
    skipped = 0
    while pos < len(data):
        t = data[pos]
        pos += 1
        if t in (0, 1, 10, 0xfe):
            x, y, z = unpack('<3d', data, pos)
            pos += 24
            moves.append(Move('rapid' if t == 0 else 'feed', x * k, y * k, z * k))
        elif t in (2, 3):
            x, y, z, cx, cy, _cz = unpack('<6d', data, pos)
            pos += 48
            moves.append(Move('arc_cw' if t == 2 else 'arc_ccw', x * k, y * k, z * k, cx * k, cy * k))
        elif t == 0x0b:
            pos += 48
        elif t == 0x21:
            _a, n = unpack('<HH', data, pos)
            pos += 4 + 28 * n
        elif t == 0x22:
            _a, n = unpack('<HH', data, pos)
            pos += 4 + 2 * n
        elif t == 0x24:
            pos += 26
        elif t == 0x30:
            pos += 8
        elif t == 0x64:
            x, y, z, _i = unpack('<3dI', data, pos)
            pos += 28
            moves.append(Move('feed', x * k, y * k, z * k))
        elif t == 0xff:
            continue
        else:
            n = unpack('<H', data, pos)[0]
            pos += 2 + n
            skipped += 1
    if pos != len(data):
        raise VnvError(f'parcours tronqué ({pos} octets lus sur {len(data)})')
    return pos, skipped


def read(path) -> Toolpath:
    p = pathlib.Path(path)
    tp = read_bytes(p.read_bytes(), p.name)
    tp.file = p.name
    return tp


def write_bytes(tp: Toolpath, comment: str = '', tool_number: int = 0, tool_diameter: float = 0.0,
                tool_angle: float = 0.0, tool_tip: float = 0.0) -> bytes:
    """Parcours au format TypeEdit (en-tête étendu, arcs gardés) ; outil
    en mm et degrés (angle au sommet)."""
    head = bytearray(HEADER + HEADER_EXT)
    struct.pack_into('<HI', head, 0, 1, HEADER + HEADER_EXT)
    head[6:10] = VERSION
    c = (comment or tp.name).encode('cp1252', 'replace')[:255]
    head[10:10 + len(c)] = c
    struct.pack_into('<d', head, 0x10a, 1.0)
    bb = tp.bbox() or (0, 0, 0, 0, 0, 0)
    struct.pack_into('<6d', head, 0x112, bb[0], bb[3], bb[1], bb[4], bb[2], bb[5])
    struct.pack_into('<H4d', head, 0x144, tool_number, tool_diameter / 2.0, math.radians(tool_angle) / 2,
                     tool_tip or (0 if tool_angle else tool_diameter), 0.0)
    out = bytearray(head)
    for m in tp.moves:
        if m.is_arc:
            out += struct.pack('<B6d', 2 if m.kind == 'arc_cw' else 3, m.x, m.y, m.z, m.cx, m.cy, m.z)
        else:
            out += struct.pack('<B3d', 0 if m.kind == 'rapid' else 1, m.x, m.y, m.z)
    return bytes(out)


def write(tp: Toolpath, path, **kw) -> None:
    pathlib.Path(path).write_bytes(write_bytes(tp, **kw))


_NUM = re.compile(r'\.\d{3}$')


def companions(vnd_path) -> list[pathlib.Path]:
    """Fichiers de parcours d'un VND : même nom, extensions .000, .001…"""
    p = pathlib.Path(vnd_path)
    out = []
    for f in sorted(p.parent.glob(p.stem + '.*')):
        if _NUM.search(f.name) and f.stem == p.stem:
            out.append(f)
    return out


def read_all(vnd_path) -> list[Toolpath]:
    out = []
    for f in companions(vnd_path):
        try:
            out.append(read(f))
        except (VnvError, struct.error) as ex:
            tp = Toolpath(op_id='', tool_id='', name=f.name, source='typeedit')
            tp.warnings.append(f'{f.name} : {ex}')
            out.append(tp)
    return out


def vnd_tools(vnd_path) -> dict:
    """Outils des parcours, lus dans le VND : chaque CToolPath (MaudeFao)
    y porte le nom de son fichier (« piece.003 »), un libellé, deux entiers,
    puis l'outil complet (version, nom, bloc des bases d'outils .Dbt, avec
    avances et régimes). Rend {nom de fichier: CamTool}."""
    from . import tooldb
    p = pathlib.Path(vnd_path)
    try:
        data = p.read_bytes()
    except OSError:
        return {}
    out = {}
    for f in companions(p):
        name = f.name.encode('cp1252', 'replace')
        pat = bytes([len(name)]) + name
        i = data.find(pat)
        while i >= 0:
            tool = _tool_after(data, i, tooldb)
            if tool is not None:
                out[f.name] = tool
                break
            i = data.find(pat, i + 1)
    return out


def _tool_after(data: bytes, i: int, tooldb):
    from ..io.mfc import Archive, ArchiveError
    ar = Archive(data, i)
    try:
        ar.cstring()                                   # fichier du parcours
        ar.cstring()                                   # libellé (« Ø2 Z1 L4 »)
        ar.u32()
        ar.u32()
        version = ar.i32()
        if not 1 <= version <= 5:
            return None
        name = ar.cstring()
        block = ar.raw(0x378 if version < 3 else 0x3f8)
        _ty, tool, _notes = tooldb._tool_of(name, version, block)
    except (ArchiveError, struct.error, UnicodeDecodeError):
        return None
    if not 0 < tool.diameter <= 100:
        return None
    return tool
