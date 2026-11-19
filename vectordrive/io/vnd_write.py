"""Écriture des documents TypeEdit (.vnd).

Deux usages :

1. **Réécriture** d'un VND relu : l'arbre MFC lu par `vnd.parse` est
   resérialisé champ par champ. Sans modification, le fichier produit est
   identique à l'octet (test de non-régression) ; c'est la preuve que
   chaque lecteur a son symétrique exact.
2. **Création** à partir d'un `Document` VectorDrive : calques, zones,
   courbes et contours sont générés avec les valeurs par défaut observées
   dans les fichiers TypeEdit (objet version 9, GUID neufs).

La fin du document (support, plans, grille, variables, outils, machine,
chemins d'outil, repères) n'est pas reconstruite : elle est recopiée. Elle
ne contient que des déclarations de classes nouvelles, jamais de renvoi à
un indice antérieur — sauf les chemins d'outil FAO. D'où la règle :

* même nombre d'objets qu'à la lecture → fin d'origine complète ;
* sinon → fin d'origine jusqu'à la machine (`CInfoGii`), puis la fin du
  modèle sans FAO. Les chemins d'outil d'origine sont alors perdus
  (VectorDrive ne fait pas de FAO) et `report` le signale.
"""
from __future__ import annotations

import contextlib
import math
import pathlib
import struct
import uuid
from collections import Counter

from ..core.document import Document, Group, Image, Item, Layer, Shape, Text
from ..core.geom import Conic, Contour, Cubic, Line, bbox_union
from . import vnd
from .mfc import MfcClass, MfcObject

MM_TO_M = 1 / 1000.0
EMPTY_BBOX = (1e100, 1e100, 1e100, -1e100, -1e100, -1e100)

#: Schémas de classes écrits par TypeEdit dans les fichiers observés.
SCHEMAS = {'CTravail': 10, 'CCalque': 8, 'CZone': 1, 'CCourbe': 1, 'CContour': 2,
           'CPropertyExtend': 5, 'CVnImage': 5}

#: TypeEdit 13 (celui de l'atelier, 32 bits) : schéma de chaque classe tel
#: que ses DLL le déclarent (CRuntimeClass.m_wSchema, relevé dans
#: l'installation V13 pour l'interopérabilité). 0x8000000n = classe à
#: versions (MFC accepte tout schéma ≤ n) ; sinon le schéma doit être égal ;
#: 0xFFFF = classe abstraite (pas vérifiée). La V15 monte CTravail à 11,
#: CCalque à 9, CObCadran à 7, CObNewBCode1D/2D à 2 : TypeEdit 13 ne les
#: relit pas.
V13_SCHEMAS = {
    'CCalque': 0x80000008, 'CCenterLine': 1, 'CContour': 0x80000002, 'CCotationAngle': 0x80000001,
    'CCotationDiameter': 0x80000001, 'CCotationHorizontale': 0x80000001, 'CCotationLaterale': 0x80000001,
    'CCotationLineaire': 0xFFFF, 'CCotationRadial': 0x80000001, 'CCotationVerticale': 0x80000001, 'CCourbe': 1,
    'CMarker': 1, 'CMetaObj': 0x80000001, 'CObBCode': 0x80000004, 'CObBraille': 0x8000000A,
    'CObBrep': 0x80000002, 'CObCadran': 0x80000005, 'CObDaoCtn': 0xFFFF, 'CObNewBCode1D': 0x80000001,
    'CObNewBCode2D': 0x80000001, 'CParagraphe': 0x80000006, 'CPropertyExtend': 0x80000005,
    'CTravail': 0x8000000A, 'CTrou': 1, 'CVbitmap': 0x80000007, 'CVnImage': 0x80000005, 'CZone': 1,
    'CObList': 0xFFFF,
}
#: en-têtes des objets écrits par TypeEdit 13 : CObDao version 9, CObjGuid
#: version 2 (TypeEdit 14 et 15 : 10 et 3, propriétés en CString)
V13_OBDAO = 9
V13_GUID = 2

COURBE_TRAILER = bytes(16) + struct.pack('<II', 4, 0)
POINT_NODE = 0x0D
POINT_CTRL = 0x0C


class VndWriteError(ValueError):
    pass


class MfcWriter:
    """`CArchive` en écriture : étiquettes, table d'indices partagée."""

    def __init__(self):
        self.buf = bytearray()
        self.classes: dict[str, int] = {}
        self.objects: dict[int, int] = {}       # id(MfcObject) → indice
        self.count = 1                           # indice 0 = NULL

    # types de base
    def u8(self, v): self.buf += struct.pack('<B', v)
    def u16(self, v): self.buf += struct.pack('<H', v)
    def u32(self, v): self.buf += struct.pack('<I', v & 0xFFFFFFFF)
    def i32(self, v): self.buf += struct.pack('<i', v)
    def u64(self, v): self.buf += struct.pack('<Q', v)
    def f64(self, v): self.buf += struct.pack('<d', v)
    def f64s(self, vs): self.buf += struct.pack(f'<{len(vs)}d', *vs)
    def raw(self, b): self.buf += b

    def std_string(self, s: str) -> None:
        b = s.encode('cp1252', 'replace')
        self.u32(len(b))
        self.raw(b)

    def cstring(self, s: str) -> None:
        """`CString` MFC : ANSI si possible, sinon UTF-16 (marqueur FF FE FF) ;
        une chaîne lue en UTF-16 (`WideStr`) le reste."""
        from .mfc import WideStr
        try:
            if isinstance(s, WideStr):
                raise UnicodeEncodeError('cp1252', s, 0, 0, 'lue en UTF-16')
            b = s.encode('cp1252')
            unicode = False
        except UnicodeEncodeError:
            b = s.encode('utf-16-le', 'surrogatepass')
            unicode = True
        n = len(b) // 2 if unicode else len(b)            # en unités UTF-16 : un emoji en compte deux
        if unicode:
            self.u8(0xFF)
            self.u16(0xFFFE)
        if n < 0xFF:
            self.u8(n)
        elif n < 0xFFFE:
            self.u8(0xFF)
            self.u16(n)
        else:
            self.u8(0xFF)
            self.u16(0xFFFF)
            self.u32(n)
        self.raw(b)

    def _index_tag(self, idx: int, cls: bool) -> None:
        if idx < 0x7FFF:
            self.u16((0x8000 | idx) if cls else idx)
        else:
            self.u16(0x7FFF)
            self.u32((0x80000000 | idx) if cls else idx)

    def write_object(self, obj: MfcObject | None) -> None:
        """`CArchive::WriteObject`."""
        if obj is None:
            self.u16(0)
            return
        if id(obj) in self.objects:
            self._index_tag(self.objects[id(obj)], cls=False)
            return
        name = obj.cls.name
        if name in self.classes:
            self._index_tag(self.classes[name], cls=True)
        else:
            self.u16(0xFFFF)
            self.u16(obj.cls.schema)
            nb = name.encode('ascii')
            self.u16(len(nb))
            self.raw(nb)
            self.classes[name] = self.count
            self.count += 1
        self.objects[id(obj)] = self.count
        self.count += 1
        WRITERS[name](self, obj)

    def embedded(self, obj: MfcObject) -> None:
        WRITERS[obj.cls.name](self, obj)


# --- écrivains de classes (symétriques des lecteurs de vnd.py) -----------------

def w_obdao(w: MfcWriter, obj: MfcObject) -> None:
    f = obj.fields
    w.f64s(f['bbox'])
    w.u32(f['flags'])
    if f['flags'] & ~1 not in vnd._MODERN:
        return
    ver = f['version']
    w.u32(ver)
    if ver < 1:
        return
    w.u32(f['f88'])
    if 2 <= ver <= 7:
        w.std_string(f.get('name', ''))
    if ver >= 3:
        w.u32(f['f8c'])
    if ver < 4:
        return
    w.u32(f['f90'])
    w.u32(f['f94'])
    if ver == 6:
        w.raw(bytes.fromhex(f['guid']))
    elif ver > 6:
        gv = f.get('guid_ver', 2)
        w.u32(gv)
        w.raw(bytes.fromhex(f['guid']))
        gp = f.get('guid_props', {})
        if gv < 3:
            if gv == 2:
                w.u32(len(gp))
                for k, v in gp.items():
                    w.std_string(k)
                    w.std_string(v)
        else:
            w.u32(len(gp))
            for k, v in gp.items():
                w.cstring(k)
                w.cstring(v)
    props = f.get('props', {})
    if ver < 10:
        if ver > 7:
            w.u64(len(props))
            for k, v in props.items():
                w.std_string(k)
                w.std_string(v)
        if ver > 8:
            w.u32(0)
    else:
        w.u64(len(props))
        for k, v in props.items():
            w.cstring(k)
            w.cstring(v)
        w.u32(0)


def w_obdao_fin(w: MfcWriter, obj: MfcObject) -> None:
    w_obdao(w, obj)
    if obj.fields['flags'] & ~1 in (0x1000010, 0x1000100):
        w.u32(obj.fields.get('fin', 1))


def w_obdao_ctn(w: MfcWriter, obj: MfcObject) -> None:
    w_obdao(w, obj)
    f = obj.fields
    mode = f['flags'] & ~1
    if mode == 0x1001000:
        w.u32(f.get('ctn_version', 3))
        slots = f.get('slots', obj.children)
        w.u32(len(slots))
        for ch in slots:
            w.write_object(ch)
    elif mode == 0x1000100:
        w.write_object(f.get('oblist'))
    else:
        w_oblist(w, f['inline_list'])
    for fx in f.get('fixed', []):
        w.embedded(fx)
    if mode in (0x1000010, 0x1000100):
        w.u32(f.get('ctn_tail', 0))


def w_oblist(w: MfcWriter, obj: MfcObject) -> None:
    slots = obj.fields.get('slots', obj.children)
    if obj.fields.get('big_count') or len(slots) >= 0xFFFF:
        w.u16(0xFFFF)
        w.u32(len(slots))
    else:
        w.u16(len(slots))
    for ch in slots:
        w.write_object(ch)


def w_calque(w: MfcWriter, obj: MfcObject) -> None:
    w_obdao_ctn(w, obj)
    f = obj.fields
    w.cstring(f.get('layer_name', 'Plan 1'))
    w.raw(f['attrs'])
    v = obj.cls.schema
    if v > 6:
        if v < 9:
            w.std_string(f.get('axis_name', 'O X Y Z'))
        else:
            w.cstring(f.get('axis_name', 'O X Y Z'))


def w_zone(w: MfcWriter, obj: MfcObject) -> None:
    w_obdao_ctn(w, obj)


def w_courbe(w: MfcWriter, obj: MfcObject) -> None:
    w_obdao_ctn(w, obj)
    w.raw(obj.fields.get('trailer', COURBE_TRAILER))


def w_contour(w: MfcWriter, obj: MfcObject) -> None:
    w_obdao_fin(w, obj)
    f = obj.fields
    w.i32(f['type'])
    pts = f['points']
    w.u32(len(pts))
    w.raw(b''.join(struct.pack('<4dI', *p) for p in pts))
    if obj.cls.schema > 1:
        w.write_object(f.get('ext_obj'))


def w_property_extend(w: MfcWriter, obj: MfcObject) -> None:
    f = obj.fields
    v = f['version']
    w.i32(v)
    if v > 0:
        w.u64(f['f10'])
        w.u32(f['f0c'])
        w.u32(f['color'])
    if v > 1:
        w.u32(f['fill_color'])
    if v > 2:
        for x in f['f20_2c']:
            w.u32(x)
        w.i32(len(f['ints']))
        for x in f['ints']:
            w.u32(x)
        w.u32(f['f40'])
        w.u32(f['f44'])
    if v > 3:
        w.u64(f['f48'])
        w.i32(len(f['doubles']))
        for x in f['doubles']:
            w.f64(x)
    if v < 5:
        return
    w.f64s(f['f80_98'])
    for key, zkey in (('s60', 'zone_a'), ('s70', 'zone_b')):
        b = f.get(key, '').encode('cp1252', 'replace')
        w.i32(len(b))
        w.raw(b)
        z = f.get(zkey)
        w.u32(1 if z is not None else 0)
        if z is not None:
            w.embedded(z)


def w_vnimage(w: MfcWriter, obj: MfcObject) -> None:
    w_obdao_fin(w, obj)
    f = obj.fields
    v = obj.cls.schema
    w.f64s(f['geom'])
    w.i32(len(f['bitmap']))
    w.raw(f['bitmap'])
    if v < 2:
        return
    w.u32(f['f128'])
    if v in (4, 5):
        w.u32(f.get('has_courbe', 0))
        if f.get('has_courbe'):
            w.write_object(f.get('courbe'))


def _w_txtpara(w: MfcWriter, para: dict) -> None:
    w.raw(para['para'])
    w.u32(len(para['lines']))
    for r in para['lines']:
        w.raw(r)
    w.u32(len(para['chars']))
    for r in para['chars']:
        w.raw(r)


def w_paragraphe(w: MfcWriter, obj: MfcObject) -> None:
    w_obdao_fin(w, obj)
    f = obj.fields
    w.u32(f['f8'])
    w.raw(f['f140'])
    w.u32(f['has_para2'])
    w.u32(f['f160'])
    w.f64s(f['origin'])
    _w_txtpara(w, f['para1'])
    if f['has_para2']:
        _w_txtpara(w, f['para2'])
    w.u32(f['f164'])
    w.u32(len(f['blob']))
    w.raw(f['blob'])
    w.f64s(f['cube'])
    w.u32(len(f['boxes']))
    for bx in f['boxes']:
        w.raw(struct.pack('<8fI', *bx))
    w.write_object(f.get('courbe1'))
    w.write_object(f.get('courbe2'))
    if obj.cls.schema > 5:
        w.u32(f['f148'])


def w_layout(w: MfcWriter, layout, values: dict, version: int) -> None:
    for op in layout:
        kind, key = op[0], op[1]
        if kind == 'u32':
            w.u32(values[key])
        elif kind == 'f64':
            w.f64(values[key])
        elif kind == 'ws':
            n, raw = values[key]
            w.i32(n)
            w.raw(raw)
        elif kind == 'wx':
            n, extra, raw = values[key]
            w.i32(n)
            w.u32(extra)
            w.raw(raw)
        elif kind == 'bytes':
            n, raw = values[key]
            w.i32(n)
            w.raw(raw)
        elif kind == 'ver':
            if version >= key:
                w_layout(w, op[2], values, version)


def w_cotation(w: MfcWriter, obj: MfcObject) -> None:
    w_obdao_fin(w, obj)
    f = obj.fields
    v = f['cot_version']
    w.u32(v)
    w_layout(w, vnd.COTATION_INFO, f['info'], v)
    n, raw = f['text']
    w.i32(n)
    w.raw(raw)
    w.f64s(f['cube'])
    w.f64s(f['v328'])
    w.f64s(f['pts'])
    if v > 0x112F:
        for pe in f['cot_props']:
            w.embedded(pe)
        w.u32(f['has_zone'])
        if f['has_zone']:
            w.write_object(f['zone'])
    if v > 0x1643:
        w.f64s(f['pts2'])


def w_marker(w: MfcWriter, obj: MfcObject) -> None:
    w_obdao_fin(w, obj)
    w.f64s(obj.fields['pos'])
    for i in obj.fields['ints']:
        w.u32(i)


def _w_bcode_str(w: MfcWriter, value, schema: int) -> None:
    if schema < 4:
        b = value if isinstance(value, (bytes, bytearray)) else str(value).encode('latin-1', 'replace')
        w.u32(len(b))
        w.raw(bytes(b))
    else:
        w.cstring(value)


def w_bcode(w: MfcWriter, obj: MfcObject) -> None:
    """CObBCode : relu tel quel (norme et dessin d'origine)."""
    w_obdao_fin(w, obj)
    f = obj.fields
    v = obj.cls.schema
    w.u8(f['has_zone'])
    if f['has_zone']:
        w.write_object(f['zone'])
    w.u32(f['norme_len'])
    w.raw(f['norme'])
    _w_bcode_str(w, f['data'], v)
    if v >= 2:
        w.u8(f['var_flag'])
        w.u32(f['i124'])
        if f['var_flag']:
            _w_bcode_str(w, f['var'], v)
        if v > 2:
            w.f64(f['d138'])


def w_new_bcode(w: MfcWriter, obj: MfcObject) -> None:
    """CObNewBCode1D / CObNewBCode2D : réécrits tels quels."""
    w_obdao_fin(w, obj)
    f = obj.fields
    w.u8(f['has_zone'])
    if f['has_zone']:
        w.write_object(f['zone'])
    w.u32(f['norme_len'])
    w.raw(f['norme'])
    w.cstring(f['data'])
    w.u8(f['var_flag'])
    w.u8(f['adv_var'])
    w.u32(f['i128'])
    if f['var_flag'] or f['adv_var']:
        w.cstring(f['var'] or '')
    w.f64(f['d140'])
    if obj.cls.schema > 1:
        w.raw(f['b198'])
        w.raw(f['b148'])


def w_braille(w: MfcWriter, obj: MfcObject) -> None:
    """CObBraille : valeurs relues, dans l'ordre du fichier."""
    w_obdao_fin(w, obj)
    for kind, value in obj.fields['ops']:
        if kind == 'obj':
            w.write_object(value)
        elif kind == 'cstr':
            w.cstring(value)
        else:
            getattr(w, kind)(value)


def w_cadran(w: MfcWriter, obj: MfcObject) -> None:
    """CObCadran : réécrit tel quel (réglages d'origine, bruts)."""
    w_obdao_fin(w, obj)
    f = obj.fields
    v = obj.cls.schema
    if 1 <= v <= 7:
        for k in ('courbe', 'zone'):
            w.u32(f['has_' + k])
            if f['has_' + k]:
                w.write_object(f[k])
        w.u32(f['c250'])
        w.u32(f['c254'])
        if v < 7:
            w.u32(f['name_n'])
            if f['name_n']:
                w.raw(f['name'])
                if v >= 6:
                    w.raw(f['name_extra'])
        else:
            w.cstring(f['name'])
        w.u32(f['has_var'])
        if f['has_var']:
            w.write_object(f['var'])
        w.u32(f['has_vernier'])
        if f['has_vernier']:
            w.raw(f['vernier']['raw'])
    if v > 2:
        w.embedded(f['prop_a'])
        w.embedded(f['prop_b'])
        if 'd_f8' in f:
            w.f64(f['d_f8'])


def w_trou(w: MfcWriter, obj: MfcObject) -> None:
    w_marker(w, obj)
    w.f64(obj.fields['rayon'])
    w.f64(obj.fields['profondeur'])


def w_centerline(w: MfcWriter, obj: MfcObject) -> None:
    w_obdao_fin(w, obj)
    w.f64s(obj.fields['p'])
    for i in obj.fields['ints']:
        w.u32(i)


def w_brep(w: MfcWriter, obj: MfcObject) -> None:
    """CObBrep : en-tête, entier, flux SMLib d'origine tel quel."""
    w_obdao_fin(w, obj)
    w.u32(obj.fields['brep_flag'])
    w.raw(obj.fields['brep_raw'])


WRITERS = {
    'CObBrep': w_brep,
    'CMarker': w_marker,
    'CTrou': w_trou,
    'CObBCode': w_bcode,
    'CObNewBCode1D': w_new_bcode,
    'CObNewBCode2D': w_new_bcode,
    'CObCadran': w_cadran,
    'CObBraille': w_braille,
    'CCenterLine': w_centerline,
    **{name: w_cotation for name in vnd.COTATIONS},
    'CParagraphe': w_paragraphe,
    'CCalque': w_calque,
    'CZone': w_zone,
    'CCourbe': w_courbe,
    'CContour': w_contour,
    'CPropertyExtend': w_property_extend,
    'CVnImage': w_vnimage,
    'CObDaoCtn': w_obdao_ctn,
    'CObList': w_oblist,
}


def _w_travail_head(w: MfcWriter, obj: MfcObject) -> None:
    """CTravail jusqu'à la fin de ses calques ; la suite est recopiée."""
    w_obdao(w, obj)
    f = obj.fields
    w.u32(f.get('ctn_version', 3))
    slots = f.get('slots', obj.children)
    w.u32(len(slots))
    for ch in slots:
        w.write_object(ch)


WRITERS['CTravail'] = _w_travail_head


# --- réécriture d'un VND relu ------------------------------------------------------

archive_start = vnd.archive_start


def rewrite(data: bytes) -> bytes:
    """Relit puis réécrit un VND : doit redonner le fichier à l'identique."""
    root, ar = vnd.parse(data)
    pos = archive_start(data)
    w = MfcWriter()
    w.write_object(root)
    return data[:pos] + bytes(w.buf) + data[root.fields['tail_offset']:]


# --- création à partir d'un Document ----------------------------------------------

def _guid() -> str:
    return uuid.uuid4().bytes_le.hex()


def _obdao_fields(bbox, name: str | None = None) -> dict:
    f = {'bbox': tuple(bbox), 'flags': 0x01001000, 'version': 9, 'f88': 1, 'f8c': 0,
         'f90': 1, 'f94': 1, 'guid_ver': 2, 'guid': _guid(),
         'guid_props': {'OBJETINFOS_CLASSNAME': 'CObDao'}, 'props': {}}
    if name:
        f['props'] = {'NAME': name}
    return f


def _bbox_m(bb) -> tuple:
    if not bb:
        return EMPTY_BBOX
    x0, y0, x1, y1 = bb
    return (x0 * MM_TO_M, y0 * MM_TO_M, 0.0, x1 * MM_TO_M, y1 * MM_TO_M, 0.0)


def contour_points(c: Contour) -> list[tuple]:
    """Segments (mm) → points TypeEdit homogènes (m) avec drapeaux."""
    pts: list[tuple] = []

    def node(p):
        pts.append((p[0] * MM_TO_M, p[1] * MM_TO_M, 0.0, 1.0, POINT_NODE))

    def ctrl(p, w=1.0):
        pts.append((p[0] * MM_TO_M * w, p[1] * MM_TO_M * w, 0.0, w, POINT_CTRL))

    segs = list(c.segments)
    if not segs:
        return pts
    if not c.closed:
        node(segs[0].start)
    for s in segs:
        if isinstance(s, Line):
            pass
        elif isinstance(s, Conic):
            ctrl(s.p1, s.w)
        elif isinstance(s, Cubic):
            ctrl(s.p1)
            ctrl(s.p2)
        node(s.end)
    if c.closed and segs and math.dist(segs[-1].end, segs[0].start) > 1e-9:
        node(segs[0].start)          # fermeture implicite → droite explicite
    return pts


#: Gauss-Legendre sur [0, 1] : 3 points (exact jusqu'au degré 5 : x·y' d'une
#: cubique), 10 points pour les coniques (rationnelles)
_GL3 = ((0.1127016653792583, 0.2777777777777778), (0.5, 0.4444444444444444), (0.8872983346207417, 0.2777777777777778))
_GL10 = tuple((0.5 * (1 + x), 0.5 * w) for x, w in (
    (-0.9739065285171717, 0.0666713443086881), (-0.8650633666889845, 0.1494513491505806),
    (-0.6794095682990244, 0.2190863625159820), (-0.4333953941292472, 0.2692667193099963),
    (-0.1488743389816312, 0.2955242247147529), (0.1488743389816312, 0.2955242247147529),
    (0.4333953941292472, 0.2692667193099963), (0.6794095682990244, 0.2190863625159820),
    (0.8650633666889845, 0.1494513491505806), (0.9739065285171717, 0.0666713443086881)))


def fast_signed_area(c: Contour) -> float | None:
    """Aire signée exacte d'un contour fermé, sans l'aplatir : formule de
    Green segment par segment (droites exactes, cubiques par Gauss à 3
    points — exact —, coniques à 10 points). None si un segment n'est pas
    d'un type connu."""
    s = 0.0
    for seg in c.segments:
        if isinstance(seg, Line):
            (x0, y0), (x1, y1) = seg.p0, seg.p1
            s += x0 * y1 - x1 * y0
        elif isinstance(seg, Cubic):
            (x0, y0), (x1, y1), (x2, y2), (x3, y3) = seg.p0, seg.p1, seg.p2, seg.p3
            for t, w in _GL3:
                u = 1 - t
                b0, b1, b2, b3 = u * u * u, 3 * u * u * t, 3 * u * t * t, t * t * t
                x = b0 * x0 + b1 * x1 + b2 * x2 + b3 * x3
                y = b0 * y0 + b1 * y1 + b2 * y2 + b3 * y3
                d0, d1, d2 = 3 * u * u, 6 * u * t, 3 * t * t
                dx = d0 * (x1 - x0) + d1 * (x2 - x1) + d2 * (x3 - x2)
                dy = d0 * (y1 - y0) + d1 * (y2 - y1) + d2 * (y3 - y2)
                s += w * (x * dy - y * dx)
        elif isinstance(seg, Conic):
            p0, p1, p2, wc = seg.p0, seg.p1, seg.p2, seg.w
            for t, w in _GL10:
                u = 1 - t
                a0, a1, a2 = u * u, 2 * u * t * wc, t * t
                den = a0 + a1 + a2
                x = (a0 * p0[0] + a1 * p1[0] + a2 * p2[0]) / den
                y = (a0 * p0[1] + a1 * p1[1] + a2 * p2[1]) / den
                # dérivées : (N'D − N D') / D²
                da0, da1, da2 = -2 * u, 2 * wc * (u - t), 2 * t
                dden = da0 + da1 + da2
                nx = a0 * p0[0] + a1 * p1[0] + a2 * p2[0]
                ny = a0 * p0[1] + a1 * p1[1] + a2 * p2[1]
                dnx = da0 * p0[0] + da1 * p1[0] + da2 * p2[0]
                dny = da0 * p0[1] + da1 * p1[1] + da2 * p2[1]
                dx = (dnx * den - nx * dden) / (den * den)
                dy = (dny * den - ny * dden) / (den * den)
                s += w * (x * dy - y * dx)
        else:
            return None
    if c.segments:
        (xe, ye), (xs, ys) = c.segments[-1].end, c.segments[0].start
        s += xe * ys - xs * ye                                    # fermeture implicite
    return s / 2


def _contour_type(c: Contour) -> int:
    if not c.closed:
        return 0
    a = fast_signed_area(c)
    if a is not None:
        bb = c.bbox()
        scale = ((bb[2] - bb[0]) ** 2 + (bb[3] - bb[1]) ** 2) if bb else 0.0
        if abs(a) > 1e-9 * scale:                              # sens net : pas besoin d'aplatir
            return 1 if a >= 0 else 2
    return 1 if c.signed_area() >= 0 else 2


def _property_extend(thickness_m: float = 0.0005) -> MfcObject:
    o = MfcObject(MfcClass('CPropertyExtend', SCHEMAS['CPropertyExtend']))
    o.fields = {'version': 5, 'f10': struct.unpack('<Q', struct.pack('<d', thickness_m))[0],
                'f0c': 0, 'color': 0, 'fill_color': 0, 'f20_2c': [65536, 12, 0, 4],
                'ints': [], 'f40': 4, 'f44': 0, 'f48': 0, 'doubles': [],
                'f80_98': (0.0, 0.0, 0.0, 0.0), 's60': '', 's70': ''}
    return o


#: Couleur d'un outil du dessin en cours d'écriture (`Document.tool_color`), None hors écriture
_TOOL_COLOR = None


@contextlib.contextmanager
def _using_tools(doc):
    """Le temps d'écrire les courbes de `doc` : leur couleur vient de ses outils."""
    global _TOOL_COLOR
    saved = _TOOL_COLOR
    _TOOL_COLOR = doc.tool_color
    try:
        yield
    finally:
        _TOOL_COLOR = saved


def _trailer(shape: Shape) -> bytes:
    """Fin de courbe : TypeEdit y lit la couleur qu'il montre (noir sinon, quel que soit l'outil). Une courbe lue dans TypeEdit garde
    la sienne tant qu'elle reste sur son outil ; une autre prend la couleur de son outil, celle qu'elle a dans VectorDrive."""
    extra = shape.extra if isinstance(shape.extra, dict) else {}
    vx = extra.get('vnd') or {}
    tool = int(shape.tool)
    raw = vx.get('trailer')
    if isinstance(raw, (bytes, bytearray)) and len(raw) == len(COURBE_TRAILER) and vx.get('tool') == tool:
        return bytes(raw)
    own = extra.get('te_color')
    user = extra.get('couleur')                          # la couleur propre donnée dans VectorDrive : celle de la courbe
    if isinstance(user, str) and len(user) == 7 and user.startswith('#'):
        col = user
    elif own and len(own) == 2 and own[1] == tool:
        col = own[0]
    else:
        col = _TOOL_COLOR(tool) if _TOOL_COLOR is not None else None
    if not str(col).startswith('#') or len(str(col)) != 7:
        return COURBE_TRAILER
    try:
        c = vnd.hex_colorref(col)
    except ValueError:
        return COURBE_TRAILER
    return struct.pack('<6I', 0, 0, c, 0, 4, c) if c else COURBE_TRAILER


def _courbe(shape: Shape) -> MfcObject:
    cb = MfcObject(MfcClass('CCourbe', SCHEMAS['CCourbe']))
    cb.fields = _obdao_fields(_bbox_m(shape.bbox()), shape.name or None)
    cb.fields['ctn_version'] = 3
    cb.fields['trailer'] = _trailer(shape)
    drawn = [c for c in shape.path.contours if c.segments]
    kept = (shape.extra.get('vnd') or {}).get('props') if isinstance(shape.extra, dict) else None
    rows = kept.rows if isinstance(kept, vnd.ContourProps) and len(kept.rows) == len(drawn) else None
    for k, c in enumerate(drawn):
        co = MfcObject(MfcClass('CContour', SCHEMAS['CContour']))
        co.fields = _obdao_fields(_bbox_m(c.bbox()))
        co.fields['type'] = _contour_type(c)
        co.fields['points'] = contour_points(c)
        co.fields['ext_obj'] = _property_extend()
        if rows:
            co.fields['ext_obj'].fields.update(rows[k])
        cb.children.append(co)
    # contours dégénérés de la source (un seul point : non dessinables) remis
    # à leur place, tant que les autres contours sont les mêmes en nombre
    vx = shape.extra.get('vnd', {}) if isinstance(shape.extra, dict) else {}
    empties = vx.get('empty_contours')
    if empties and len(cb.children) == vx.get('drawn_contours'):
        for i, obj in empties:
            cb.children.insert(min(i, len(cb.children)), as_v13(obj))   # venus d'un GVT : en-tête V13
        if not shape.path.contours:                    # courbe réduite à des points
            bbs = [o.fields['bbox'] for _i, o in empties if o.fields.get('bbox', EMPTY_BBOX)[0] < 1e99]
            if bbs:
                cb.fields['bbox'] = (min(b[0] for b in bbs), min(b[1] for b in bbs), min(b[2] for b in bbs),
                                     max(b[3] for b in bbs), max(b[4] for b in bbs), max(b[5] for b in bbs))
    return cb


def v13_issues(root: MfcObject | None) -> list[str]:
    """Ce qui, dans un arbre d'objets à écrire, n'est pas lisible par
    TypeEdit 13 : classe inconnue de la V13, schéma plus récent, en-tête
    d'objet (CObDao, CObjGuid) de TypeEdit 14 ou 15. Liste vide = compatible."""
    out: dict[str, int] = {}
    seen = set()

    def note(msg):
        out[msg] = out.get(msg, 0) + 1

    def walk(o):
        if not isinstance(o, MfcObject) or id(o) in seen:
            return
        seen.add(id(o))
        name, sch = o.cls.name, o.cls.schema
        ref = V13_SCHEMAS.get(name)
        if ref is None:
            note(f'{name} : classe inconnue de TypeEdit 13')
        elif ref != 0xFFFF and sch:
            ok = sch <= (ref & 0x7FFFFFFF) if ref & 0x80000000 else sch == ref
            if not ok:
                note(f'{name} : schéma {sch} (TypeEdit 13 : {ref & 0x7FFFFFFF})')
        f = o.fields
        if 'bbox' in f and f.get('version', 0) > V13_OBDAO:
            note(f'{name} : en-tête de TypeEdit 14 ou plus (version {f["version"]})')
        elif f.get('guid_ver', 0) > V13_GUID:
            note(f'{name} : identifiant de TypeEdit 14 ou plus (version {f["guid_ver"]})')
        for c in o.children:
            walk(c)
        for v in f.values():
            if isinstance(v, MfcObject):
                walk(v)
            elif isinstance(v, (list, tuple)):
                for x in v:
                    if isinstance(x, MfcObject):
                        walk(x)
                    elif isinstance(x, list) and len(x) == 2 and isinstance(x[1], MfcObject):
                        walk(x[1])                     # valeurs gardées dans l'ordre (braille)
    walk(root)
    return [f'{m} (× {n})' if n > 1 else m for m, n in out.items()]


def as_v13(obj: MfcObject) -> MfcObject:
    """Copie d'un objet simple de TypeEdit 14/15 avec l'en-tête de
    TypeEdit 13 (CObDao 9, CObjGuid 2 : propriétés en chaînes ANSI) ; le
    reste de l'objet ne change pas d'une version à l'autre pour les classes
    concernées (contours d'un point gardés tels quels)."""
    f = obj.fields
    if f.get('version', 0) <= V13_OBDAO and f.get('guid_ver', 0) <= V13_GUID:
        return obj
    import copy
    c = copy.copy(obj)
    c.fields = dict(f)
    if c.fields.get('version', 0) > V13_OBDAO:
        c.fields['version'] = V13_OBDAO
    if c.fields.get('guid_ver', 0) > V13_GUID:
        c.fields['guid_ver'] = V13_GUID
    return c


def _vnimage(im: Image) -> MfcObject:
    o = MfcObject(MfcClass('CVnImage', SCHEMAS['CVnImage']))
    m = im.matrix
    if abs(m.b) > 1e-12 or abs(m.c) > 1e-12:
        x0, y0, x1, y1 = im.bbox()          # TypeEdit : image non tournée
        x_tl, y_tl, x_br, y_br = x0, y1, x1, y0
    else:
        x_tl, y_tl = m.e, m.f
        x_br, y_br = m.e + m.a, m.f + m.d
    vx = im.extra.get('vnd', {}) if isinstance(im.extra, dict) else {}
    o.fields = _obdao_fields(_bbox_m(im.bbox()))
    o.fields.update(geom=(x_tl * MM_TO_M, y_tl * MM_TO_M, x_br * MM_TO_M, y_br * MM_TO_M,
                          vx.get('geom5', 0.0)),
                    bitmap=im.data if im.fmt == 'dib' else b'', f128=vx.get('f128', 0),
                    has_courbe=0)
    return o


def _wraps(item: Item) -> int:
    """Nombre de zones à objet unique qui enveloppaient l'item dans la
    source. Par défaut : 1 pour une courbe ou une image, 0 pour un groupe
    (qui est déjà une zone)."""
    vx = item.extra.get('vnd', {}) if isinstance(item.extra, dict) else {}
    return vx.get('wraps', 0 if isinstance(item, Group) else 1)


def _shift_bbox(bb, dx: float, dy: float):
    if bb[0] > 1e99:                                   # boîte vide
        return bb
    return (bb[0] + dx, bb[1] + dy, bb[2], bb[3] + dx, bb[4] + dy, bb[5])


def translated_object(obj: MfcObject, dx: float, dy: float) -> MfcObject | None:
    """Copie de l'objet TypeEdit translatée de (dx, dy) m, comme le fait
    son `Deplace` (MaudeTxt.dll pour les textes : boîte, origine, cube,
    courbes associées, boîtes des caractères ; les attributs de
    caractères et de lignes sont relatifs ; MaudeCotation.dll pour les
    cotes). None si l'objet n'est pas translatable sans risque (texte
    sur courbe avec données non décodées…) : il sera alors écrit comme
    dessin."""
    import copy
    name = obj.cls.name
    c = copy.copy(obj)
    c.fields = dict(obj.fields)
    c.children = []
    if 'bbox' in c.fields:
        c.fields['bbox'] = _shift_bbox(c.fields['bbox'], dx, dy)
    if name == 'CParagraphe':
        f = c.fields
        if f.get('blob') or f.get('has_para2'):
            return None
        f['origin'] = (f['origin'][0] + dx, f['origin'][1] + dy) + tuple(f['origin'][2:])
        f['cube'] = _shift_bbox(f['cube'], dx, dy)
        f['boxes'] = [tuple(v + (dx if i % 2 == 0 else dy) for i, v in enumerate(b[:8])) + tuple(b[8:])
                      for b in f['boxes']]
        for k in ('courbe1', 'courbe2'):
            if f.get(k) is not None:
                t = translated_object(f[k], dx, dy)
                if t is None:
                    return None
                f[k] = t
                c.children.append(t)
        return c
    if name in vnd.COTATIONS:
        # MaudeCotation.dll, Deplace : boîte, vecteur 0x328, les deux points
        # d'attache, dessin généré ; le 3e point est une direction, le cube
        # un cache que TypeEdit ne translate pas
        f = c.fields
        v = f['v328']
        f['v328'] = (v[0] + dx, v[1] + dy) + tuple(v[2:])
        p = list(f['pts'])
        p[0] += dx
        p[1] += dy
        p[3] += dx
        p[4] += dy
        f['pts'] = tuple(p)
        if f.get('zone') is not None:
            t = translated_object(f['zone'], dx, dy)
            if t is None:
                return None
            f['zone'] = t
            c.children.append(t)
        return c
    if name == 'CObBraille':
        # MaudeExt.dll, Deplace : paragraphe, dessin des points, position
        f = c.fields
        ops = f['ops'] = [list(op) for op in f['ops']]
        for k in ('par', 'zone'):
            if k in f:
                t = translated_object(ops[f[k]][1], dx, dy)
                if t is None:
                    return None
                ops[f[k]][1] = t
                c.children.append(t)
        ops[f['pos_x']][1] += dx
        ops[f['pos_y']][1] += dy
        return c
    if name == 'CObCadran':
        # MaudeCadran.dll, Deplace : dessin généré, courbe de base, centre
        # des réglages (+0x10 de l'en-tête)
        f = c.fields
        for k in ('courbe', 'zone'):
            if f.get(k) is not None:
                t = translated_object(f[k], dx, dy)
                if t is None:
                    return None
                f[k] = t
                c.children.append(t)
        ver = f.get('vernier')
        if ver and ver.get('has'):
            raw = bytearray(ver['raw'])
            x, y = struct.unpack_from('<2d', raw, 4 + 0x10)
            struct.pack_into('<2d', raw, 4 + 0x10, x + dx, y + dy)
            f['vernier'] = dict(ver, raw=bytes(raw))
        return c
    if name in ('CTrou', 'CMarker'):
        p = c.fields['pos']
        c.fields['pos'] = (p[0] + dx, p[1] + dy) + tuple(p[2:])
        return c
    if name == 'CCenterLine':
        p = c.fields['p']
        c.fields['p'] = (p[0] + dx, p[1] + dy, p[2], p[3] + dx, p[4] + dy) + tuple(p[5:])
        return c
    if name == 'CContour':
        c.fields['points'] = [(x + dx * w, y + dy * w, z, w, fl) for x, y, z, w, fl in c.fields.get('points', [])]
        return c
    if name in ('CCourbe', 'CZone'):
        mapping = {}
        for ch in obj.children:
            t = translated_object(ch, dx, dy)
            if t is None:
                return None
            mapping[id(ch)] = t
            c.children.append(t)
        if 'slots' in c.fields:
            if any(s is not None and id(s) not in mapping for s in c.fields['slots']):
                return None
            c.fields['slots'] = [mapping[id(s)] if s is not None else None for s in c.fields['slots']]
        return c
    return None


def source_object(item: Item) -> MfcObject | None:
    """Objet TypeEdit d'origine (texte CParagraphe, cote, trou) encore
    valable : ni transformé (hors translation), ni copié, ni édité depuis
    la lecture. Une translation cumulée donne une copie translatée."""
    obj = item.extra.get('vnd_obj')
    if obj is None or item.extra.get('vnd_moved'):
        return None
    dx, dy = item.extra.get('vnd_shift', (0.0, 0.0))
    if abs(dx) > 1e-12 or abs(dy) > 1e-12:
        return translated_object(obj, dx * MM_TO_M, dy * MM_TO_M)
    return obj


#: 7 entiers du marqueur d'un trou, tels que TypeEdit les écrit
TROU_INTS = [0, 0, 0, 0, 0, 4, 0]


def _trou(item: Item) -> MfcObject | None:
    """CTrou (Maude.dll) : trou de perçage reconstruit depuis le cercle
    (déplacé, copié, redimensionné…) et sa profondeur."""
    from ..core.holes import circle_of
    g = circle_of(item)
    if g is None:
        return None
    x, y, r = g
    info = item.extra.get('trou') or {}
    depth = float(info.get('profondeur', 0.0))
    o = MfcObject(MfcClass('CTrou', 1))
    o.fields = _obdao_fields(((x - r) * MM_TO_M, (y - r) * MM_TO_M, -depth * MM_TO_M,
                              (x + r) * MM_TO_M, (y + r) * MM_TO_M, 0.0),
                             item.name if item.name not in ('', 'Trou') else None)
    o.fields['pos'] = (x * MM_TO_M, y * MM_TO_M, 0.0)
    o.fields['ints'] = list(info.get('ints') or TROU_INTS)
    o.fields['rayon'] = r * MM_TO_M
    o.fields['profondeur'] = depth * MM_TO_M
    return o


class _LiveTexts:
    """Textes écrits en paragraphes TypeEdit modifiables (CParagraphe) : la
    table des polices du fichier (celles de la base, puis les nouvelles)."""

    def __init__(self, names: list[str]):
        self.base = list(names)
        self.names = list(names)
        self.count = 0
        self.curves: Counter = Counter()               # textes laissés en courbes, par raison (compte rendu)

    def node(self, t: Text) -> MfcObject | None:
        from . import paragraph as PG
        if not t.text.strip() or not t.outline:
            return None                                # rien à tracer : ni texte ni courbes, rien à compter
        why = curves_reason(t)
        if why is not None:
            self.curves[why] += 1
            return None
        idx = self.names.index(t.font) if t.font in self.names else len(self.names)
        p = PG.build(t, idx)
        if p is None:                                  # sur courbe, en arc, étiré, en miroir… : en courbes
            self.curves[WHY_SHAPE] += 1
            return None
        if idx == len(self.names):
            self.names.append(t.font)
        self.count += 1
        return p                                       # la zone qui l'entoure vient de `_zone`, comme TypeEdit

    @staticmethod
    def allowed(t: Text) -> bool:
        """Le texte s'écrit en texte TypeEdit modifiable (voir `curves_reason`)."""
        return curves_reason(t) is None


#: raisons d'un texte écrit en courbes alors que les textes sont modifiables (compte rendu de l'enregistrement)
WHY_STYLE = 'mise en forme que TypeEdit ne garde pas (justifié, italique, souligné, chasse…)'
WHY_FONT = 'police que TypeEdit ne trouve pas (intégrée à VectorDrive, SVG ou non installée dans Windows)'
WHY_MISSING = 'police absente du poste'
WHY_NAME = 'nom de police que TypeEdit ne reconnaît pas'
WHY_VARIABLE = 'police variable, que TypeEdit ne reconnaît pas'
WHY_SHAPE = 'texte sur courbe, en arc, étiré ou en miroir'


def curves_reason(t: Text) -> str | None:
    """Pourquoi ce texte s'écrit en courbes plutôt qu'en texte TypeEdit modifiable, ou None. TypeEdit 13 relit
    (validé le 18/10 et le 12/11 sur ses captures) les textes en police installée sur le poste (TrueType / OpenType)
    ou de TypeEdit (lue par un plugin), sur une ou plusieurs lignes. Il ne trouve pas les polices de VectorDrive
    (intégrées, SVG, ajoutées dans ses dossiers) ni une police absente : il n'ouvre le fichier qu'une fois la police
    installée (retour de l'atelier du 12/11). Il ne reconnaît pas une police variable ni un nom réduit à la clé interne
    (« arialnarrow ») (mesuré le 06/11)."""
    from ..core import fontformats
    from ..core import fonts as F
    if styled(t):
        return WHY_STYLE
    if F.builtin_named(t.font) is not None:
        return WHY_FONT
    if not F.is_available(t.font):                    # pas la police de remplacement de find_font
        return WHY_MISSING
    if t.font in F.PLUGIN_FONTS:
        return None                                    # police de TypeEdit, lue par un plugin
    if t.font == F._key(t.font):
        return WHY_NAME
    found = F.find_font(t.font)
    if found and fontformats.of(found[0]) is not None:
        return None
    if not F.installed(t.font):
        return WHY_FONT
    return WHY_VARIABLE if F.is_variable(t.font) else None


def styled(t: Text) -> bool:
    """Mise en forme que le paragraphe TypeEdit écrit ne garderait pas
    (justifié, italique, souligné, petites majuscules, ligne de base, arc
    déformé, chasse fixe ou proportionnelle, longueur maximale, réglages par
    lettre) : texte écrit en courbes."""
    if t.align not in ('left', 'center', 'right'):
        return True
    if any(t.extra.get(k) for k in ('italic', 'underline', 'small_caps', 'baseline', 'arc_warp', 'chars', 'rtl')):
        return True
    if float((t.extra.get('max_length') or {}).get('length', 0.0) or 0.0) > 0:
        return True                                   # longueur maximale : lignes resserrées
    return t.extra.get('spacing_mode', 'typo') != 'typo'


#: textes vivants de l'écriture en cours (None : textes en courbes)
_LIVE: _LiveTexts | None = None


def _node(item: Item) -> MfcObject | None:
    """Objet MFC propre à l'item : objet d'origine s'il est intact, sinon
    CZone (groupe), CTrou, CCourbe, CVnImage."""
    src = source_object(item)
    if src is not None:
        return src
    obj = item.extra.get('vnd_obj')
    if obj is not None and obj.cls.name == 'CObBrep':
        return obj                                     # flux SMLib non transformable : solide laissé en place
    if 'trou' in item.extra:
        o = _trou(item)
        if o is not None:
            return o
    if isinstance(item, Group):
        z = MfcObject(MfcClass('CZone', SCHEMAS['CZone']))
        z.fields = _obdao_fields(_bbox_m(item.bbox()), item.name or None)
        z.fields['ctn_version'] = 3
        for ch in item.children:
            o = _zone(ch)
            if o is not None:
                z.children.append(o)
        if not z.children and item.extra.get('vnd', {}).get('empty_zone'):
            return z                                   # zone vide de la source : gardée telle quelle
        return _deepen(z) if z.children else None
    if isinstance(item, Image):
        if item.data and item.fmt != 'dib':
            # PNG, JPEG… : converti en DIB, la forme des images TypeEdit
            import copy
            from .raster import to_dib
            dib = to_dib(item.data, item.fmt)
            if dib is None:
                return None
            item = copy.copy(item)
            item.data, item.fmt = dib, 'dib'
        return _vnimage(item) if item.data else None
    if _LIVE is not None and isinstance(item, Text):
        z = _LIVE.node(item)
        if z is not None:
            return z
    p = item.path if isinstance(item, Shape) else (item.outline if isinstance(item, Text) else None)
    if not p:
        vx = item.extra.get('vnd', {}) if isinstance(item.extra, dict) else {}
        if isinstance(item, Shape) and vx.get('empty_contours') and not vx.get('drawn_contours'):
            return _courbe(item)                       # courbe d'un seul point de la source
        return None
    return _courbe(item if isinstance(item, Shape) else Shape(path=p, tool=item.tool, name=item.name))


def _deepen(o: MfcObject) -> MfcObject:
    """Bas de la boîte (z) = le plus bas de ceux des enfants : la
    profondeur des trous remonte dans les zones et le calque."""
    zs = [c.fields['bbox'][2] for c in o.children
          if c is not None and 'bbox' in c.fields and -1e99 < c.fields['bbox'][2] < 0]
    if zs and o.fields['bbox'][2] > min(zs):
        bb = list(o.fields['bbox'])
        bb[2] = min(zs)
        o.fields['bbox'] = tuple(bb)
    return o


def _zone(item: Item) -> MfcObject | None:
    """L'objet de l'item, enveloppé dans autant de zones que dans la source.
    Un objet masqué n'est pas écrit (comme dans les autres exports) : les
    objets d'origine gardés masqués dans un tampon, des hachures… ne
    doivent pas partir à la gravure."""
    if not getattr(item, 'visible', True):
        return None
    node = _node(item)
    if node is None:
        return None
    bb = item.bbox()
    names = (item.extra.get('vnd') or {}).get('zone_names') if isinstance(item.extra, dict) else None
    for k in range(1, _wraps(item) + 1):
        z = MfcObject(MfcClass('CZone', SCHEMAS['CZone']))
        name = (names.get(k) or names.get(str(k))) if names else None    # dans un dessin natif, la clé est du texte
        z.fields = _obdao_fields(_bbox_m(bb) if bb else tuple(node.fields.get('bbox', EMPTY_BBOX)), name)
        z.fields['ctn_version'] = 3
        z.children.append(node)
        node = _deepen(z)
    return node


def _item_tool(it: Item) -> int:
    """Outil d'un objet : celui de sa première feuille (un groupe TypeEdit est d'un seul calque)."""
    if isinstance(it, Group):
        for ch in it.children:
            return _item_tool(ch)
    return int(getattr(it, 'tool', 0) or 0)


def _tool_layers(layers: list) -> list:
    """[(calque, outil)] : dans TypeEdit un calque = un outil = une couleur. Un calque dont les objets
    sont de plusieurs outils devient un calque TypeEdit par outil (le premier garde son nom, les
    suivants « nom (n° d'outil) ») : chaque objet garde sa couleur."""
    import copy
    out = []
    for L in layers:
        groups: dict = {}
        for it in L.items:
            groups.setdefault(_item_tool(it), []).append(it)
        if len(groups) <= 1:
            out.append((L, next(iter(groups), L.tool)))
            continue
        for k, (t, items) in enumerate(groups.items()):
            sub = copy.copy(L)
            sub.items = items
            if k:
                sub.name = f'{L.name} ({t + 1})'
            out.append((sub, t))
    return out


def _calque(layer: Layer, tool: int, current: bool, template: MfcObject | None) -> MfcObject:
    cq = MfcObject(MfcClass('CCalque', SCHEMAS['CCalque']))
    cq.fields = _obdao_fields(_bbox_m(bbox_union(it.bbox() for it in layer.items)), layer.name)
    cq.fields['ctn_version'] = 3
    for it in layer.items:
        z = _zone(it)
        if z is not None:
            cq.children.append(z)
    _deepen(cq)
    rep = MfcObject(MfcClass('CObDaoCtn', 0))
    rep.fields = _obdao_fields(EMPTY_BBOX)
    rep.fields['ctn_version'] = 3
    cq.fields['fixed'] = [rep]
    cq.fields['layer_name'] = layer.name
    attrs = bytearray(struct.pack('<IIII', 1 if layer.locked else 0, 1 if current else 0, tool,
                                  1 if layer.visible else 0))
    attrs += bytes(8) + struct.pack('<II', 0x00F4F4F4, 0)
    cq.fields['attrs'] = bytes(attrs)
    cq.fields['axis_name'] = 'O X Y Z'
    return cq


def write_order(layers: list, writes=None, first_shown: bool = False) -> list:
    """L'ordre d'écriture des calques d'un VND (rangs dans `layers`) : celui du dessin (demande du 19/11 :
    « Respecter l'ordre des calques TE-VD »). `first_shown` (réglage « Enregistrement en VND : le premier calque qui a
    quelque chose à montrer écrit en tête », décoché d'office) : TypeEdit 13 n'affiche à l'ouverture que son premier
    plan — le premier calque qui a quelque chose à montrer passe en tête, les autres gardent leur ordre (round 751).
    `writes(calque)` : écrit-il quelque chose (d'office : il a des objets)."""
    writes = writes or (lambda L: bool(L.items))
    order = list(range(len(layers)))
    if not first_shown:
        return order
    shown = ([k for k in order if writes(layers[k]) and layers[k].visible]
             or [k for k in order if writes(layers[k])])
    if shown and shown[0] != order[0]:
        order.remove(shown[0])
        order.insert(0, shown[0])
    return order


def first_shown_of(doc) -> bool:
    """Le réglage « premier calque montré en tête », porté par le document (`ui.main_window._vnd_options`)."""
    return bool(doc.extra.get('vnd_premier_plan')) if isinstance(getattr(doc, 'extra', None), dict) else False


def layer_order(layers: list, writes=None) -> tuple:
    """L'ordre d'écriture des calques d'un VND jusqu'à 0.955.0, que relisent les compagnons d'alors (`io.companion`) :
    (rangs dans `layers`, {id d'une copie VD Géo écrite cachée : id de son calque d'origine, écrit visible}).
    `writes(calque)` : écrit-il quelque chose (d'office : il a des objets).

    TypeEdit 13 ouvre toujours sur son premier plan, seul, quel que soit le plan marqué courant. 1) La copie en VD Géo
    d'un calque dont la police manque (`core.missing_fonts`), quand c'est elle que le dessin montre et que son
    original a de quoi s'écrire : l'original passe devant elle, compté visible, elle comptée cachée (réponse de
    l'utilisateur du 14/11 : TypeEdit ouvre sur le calque d'origine, dont il fait installer ou remplacer la police).
    2) Le premier calque qui a quelque chose à montrer passe en tête, les autres gardent leur ordre. Le compagnon
    (`io.companion`) refait cet ordre sur ses calques pour retrouver ceux du VND."""
    import types
    from ..core import missing_fonts as MF
    writes = writes or (lambda L: bool(L.items))
    present = {L.id for L in layers}
    behind = {c.id: de for de, c in MF.copies(types.SimpleNamespace(layers=layers)).items()
              if de in present and de != c.id and c.visible and any(writes(L) for L in layers if L.id == de)}
    front = set(behind.values())
    order = list(range(len(layers)))
    for cid, de in behind.items():
        first = next(n for n, k in enumerate(order) if layers[k].id == cid)
        late = [k for k in order[first:] if layers[k].id == de]       # l'original écrit après sa copie : avant elle
        if late:
            order = [k for k in order if k not in late]
            first = next(n for n, k in enumerate(order) if layers[k].id == cid)
            order[first:first] = late

    def visible(L) -> bool:
        return L.id in front or (L.visible and L.id not in behind)
    shown = ([k for k in order if writes(layers[k]) and visible(layers[k])]
             or [k for k in order if writes(layers[k])])
    if shown and shown[0] != order[0]:
        order.remove(shown[0])
        order.insert(0, shown[0])
    return order, behind


def _calques(layers: list, report: list | None = None, first_shown: bool = False) -> list[MfcObject]:
    """Les calques TypeEdit du document, dans l'ordre du dessin (`write_order`) ; le premier plan est seul le plan
    courant. TypeEdit 13 n'affiche à l'ouverture que son premier plan : masqué, le compte rendu le dit (réglage
    `first_shown` : le premier qui a quelque chose à montrer passe en tête)."""
    built = [(L, _calque(L, tool, False, None)) for L, tool in _tool_layers(layers)]
    made = {id(L): c for L, c in built}
    subs = [L for L, _c in built]
    order = write_order(subs, lambda L: bool(made[id(L)].children), first_shown)
    moved = bool(order) and order[0] != 0
    built = [built[k] for k in order]
    if report is not None and built:
        if moved:
            report.append(f"plan « {built[0][0].name} » écrit en premier : TypeEdit n'affiche à l'ouverture que "
                          'son premier plan')
        elif not built[0][0].visible and any(L.visible and c.children for L, c in built[1:]):
            report.append(f"premier plan « {built[0][0].name} » masqué : TypeEdit, qui n'affiche à l'ouverture que "
                          'son premier plan, ouvrira sur une page blanche')
    if built:
        a = bytearray(built[0][1].fields['attrs'])
        a[4:8] = struct.pack('<I', 1)
        built[0][1].fields['attrs'] = bytes(a)
    return [c for _L, c in built]


def ink_pixels(leaves, W: int = 100, H: int = 100) -> set[tuple[int, int]]:
    """Pixels tracés d'un aperçu W × H (dessin centré, marge 5 %), lignes
    comptées de bas en haut comme dans une DIB."""
    return set(ink_pixels_by_leaf(leaves, W, H))


def ink_pixels_by_leaf(leaves, W: int = 100, H: int = 100) -> dict:
    """{pixel: objet qui l'a tracé (le dernier)} d'un aperçu W × H, comme `ink_pixels`."""
    leaves = list(leaves)
    bb = bbox_union(it.bbox() for it in leaves)
    out: dict = {}
    if not bb:
        return out
    x0, y0, x1, y1 = bb
    s = 0.9 * min(W / max(x1 - x0, 1e-6), H / max(y1 - y0, 1e-6))
    ox = (W - (x1 - x0) * s) / 2 - x0 * s
    oy = (H - (y1 - y0) * s) / 2 - y0 * s
    for it in leaves:
        p = getattr(it, 'path', None) or getattr(it, 'outline', None)
        if not p:
            continue
        for pl in p.flatten(max(0.1, 1 / s)):
            for i in range(len(pl) - 1):
                (ax, ay), (bx, by) = pl[i], pl[i + 1]
                if not math.isfinite(ax + ay + bx + by):
                    continue
                n = int(max(abs(bx - ax), abs(by - ay)) * s) + 1
                for k in range(n + 1):
                    t = k / n
                    px = int(ox + (ax + (bx - ax) * t) * s)
                    py = int(oy + (ay + (by - ay) * t) * s)
                    if 0 <= px < W and 0 <= py < H:
                        out[(px, py)] = it
    return out


def _thumbnail(doc: Document) -> bytes:
    """Aperçu 100 × 100 en 16 couleurs (DIB), comme TypeEdit."""
    W = H = 100
    stride = 52                                  # 100 px × 4 bits, aligné sur 4 octets
    row = b'\xff' * 50 + b'\x00\x00'            # index 15 = blanc ; 2 octets de bourrage
    pix = bytearray(row * H)
    for px, py in ink_pixels(doc.iter_leaves(visible_only=True), W, H):
        o = py * stride + px // 2
        if px % 2 == 0:
            pix[o] = pix[o] & 0x0F
        else:
            pix[o] = pix[o] & 0xF0
    header = struct.pack('<IiiHHIIiiII', 40, W, H, 1, 4, 0, len(pix), 2953, 2953, 0, 0)
    pal = bytes([0, 0, 0, 0, 0, 0, 128, 0, 0, 128, 0, 0, 0, 128, 128, 0, 128, 0, 0, 0,
                 128, 0, 128, 0, 128, 128, 0, 0, 128, 128, 128, 0, 192, 192, 192, 0,
                 0, 0, 255, 0, 0, 255, 0, 0, 0, 255, 255, 0, 255, 0, 0, 0, 255, 0, 255, 0,
                 255, 255, 0, 0, 255, 255, 255, 0])
    return header + pal + bytes(pix)


THUMB_OFFSET = 5554          # position de la DIB dans l'en-tête (fichiers observés)


def _head(base: bytes, doc: Document, new_fonts: list[str] = ()) -> bytearray:
    """En-tête du VND écrit : celui de `base` (dates, réglages, table des
    polices des textes gardés), aperçu refait.

    Dans les VND de TypeEdit V15, la table des polices suit l'aperçu : un
    u32 n à l'octet 10 854 (fin de la place de l'aperçu), n noms de 64
    octets, puis l'archive. L'aperçu ne doit pas déborder sur ce compteur
    (ses 4 derniers octets de bourrage sont coupés)."""
    pos = archive_start(base)
    head = bytearray(base[:pos])
    cpos, names = vnd.font_table(base, pos)
    if not names:
        cpos = pos - 4                               # pas de texte : compteur nul juste avant l'archive
    thumb = _thumbnail(doc)[:max(0, cpos - THUMB_OFFSET)]
    head[THUMB_OFFSET:THUMB_OFFSET + len(thumb)] = thumb
    head[cpos:cpos + 4] = struct.pack('<I', len(names) + len(new_fonts))
    for name in new_fonts:                            # la table précède l'archive : ajout à la fin
        head += name.encode('cp1252', 'replace')[:63].ljust(64, b'\0')
    return head


def _without_foreign_objects(doc: Document) -> tuple[Document, int]:
    """Copie structurelle du document sans objets TypeEdit d'origine
    (textes, cotes) : ils viennent d'un autre fichier (symbole ouvert puis
    enregistré en VND…) et renvoient à sa table des polices, dont on ne
    sait pas l'équivalent dans un VND. Rend (copie, nombre de textes et
    cotes qui seront écrits comme dessin)."""
    import copy
    from ..core.document import drop_source_object, struct_copy_layers
    n = 0

    def drop(items):
        nonlocal n
        for it in items:
            if 'vnd_obj' in it.extra and not isinstance(it, Shape):
                n += 1
            drop_source_object(it)
            drop(getattr(it, 'children', ()))
    d = copy.copy(doc)
    d.layers = struct_copy_layers(doc.layers)
    for L in d.layers:
        drop(L.items)
    return d, n


def build(doc: Document, template: bytes) -> tuple[bytes, list[str]]:
    """Crée un VND : en-tête et fin de document du modèle, dessin du `doc`."""
    report: list[str] = []
    root_t, ar_t = vnd.parse(template)
    pos = archive_start(template)
    head = bytearray(template[:pos])
    thumb = _thumbnail(doc)
    head[12:pos - 2] = bytes(pos - 2 - 12)
    head[THUMB_OFFSET:THUMB_OFFSET + len(thumb)] = thumb
    # outils : un calque VectorDrive par outil TypeEdit
    root = MfcObject(MfcClass('CTravail', SCHEMAS['CTravail']))
    page = root_t.fields['bbox']
    draw = _bbox_m(doc.bbox())
    bb = (min(page[0], draw[0]), min(page[1], draw[1]), page[2],
          max(page[3], draw[3]), max(page[4], draw[4]), page[5]) if doc.bbox() else page
    root.fields = _obdao_fields(bb)
    root.fields['ctn_version'] = 3
    with _using_tools(doc):
        root.children.extend(_calques(list(doc.layers), report, first_shown_of(doc)))   # calques vides compris
    w = MfcWriter()
    w.write_object(root)
    tail = template[root_t.fields['tail_offset']:]
    return bytes(head) + bytes(w.buf) + tail, report


def _close(a, b, tol: float = 1e-12) -> bool:
    """Mêmes nombres à `tol` près (m) : la géométrie n'a pas bougé."""
    if a is b:
        return True
    ta, tb = type(a), type(b)
    if ta in (int, float) and tb in (int, float):
        return abs(a - b) <= tol
    if ta not in (tuple, list) or tb not in (tuple, list) or len(a) != len(b):
        return False
    if len(a) > 8 and a and type(a[0]) in (tuple, list):
        # listes de points : d'un bloc par numpy (formes régulières seulement)
        try:
            import numpy as np
            A = np.asarray(a, dtype=float)
            B = np.asarray(b, dtype=float)
        except (ValueError, TypeError):
            A = B = None
        if A is not None and A.shape == B.shape and A.ndim == 2:
            return bool(np.all(np.abs(A - B) <= tol))
    for x, y in zip(a, b):
        tx, ty = type(x), type(y)
        if tx in (int, float) and ty in (int, float):
            if abs(x - y) > tol:
                return False
        elif not _close(x, y, tol):
            return False
    return True


def _same_points(old_pts, old_type: int, new_pts) -> bool:
    """Les points d'origine décrivent le même contour que les nouveaux :
    on les réencode comme VectorDrive le ferait et on compare."""
    if len(old_pts) == len(new_pts) and _close(old_pts, new_pts):
        return True
    segs = vnd.contour_segments(old_pts, closed=old_type != 0)
    if not segs:
        return False
    return _close(contour_points(Contour(segs, closed=old_type != 0)), new_pts)


#: géométrie reportée d'un objet à l'autre (hors points et boîte)
_GEOMETRY = ('pos', 'rayon', 'profondeur', 'geom', 'origin', 'cube', 'boxes', 'v328', 'pts')


def _patch(old: MfcObject | None, new: MfcObject | None) -> bool:
    """Reporte la géométrie de `new` dans `old` (même structure garantie
    par la signature) : GUID, propriétés et attributs d'origine conservés.
    Ce qui n'a pas bougé garde ses nombres d'origine, boîtes comprises
    (TypeEdit les calcule à sa façon) : un dessin inchangé est réécrit à
    l'octet près. Rend True si la géométrie du sous-arbre est inchangée."""
    if old is None or new is None:
        return old is None and new is None
    same = True
    if 'points' in new.fields:
        if 'points' in old.fields and _same_points(old.fields['points'], old.fields.get('type', 0),
                                                   new.fields['points']):
            pass
        else:
            same = False
            old.fields['points'] = new.fields['points']
            if 'type' in new.fields:
                old.fields['type'] = new.fields['type']
    for k in _GEOMETRY:
        if k in new.fields and not (k in old.fields and _close(old.fields[k], new.fields[k])):
            same = False
            old.fields[k] = new.fields[k]
    if 'ops' in new.fields and 'ops' in old.fields:
        # braille déplacé : réels (position) ; les objets suivent par les enfants
        for o, n in zip(old.fields['ops'], new.fields['ops']):
            if o[0] == 'f64' and struct.pack('<d', o[1]) != struct.pack('<d', n[1]):
                same = False
                o[1] = n[1]
    if (new.fields.get('vernier') or {}).get('raw') not in (None, (old.fields.get('vernier') or {}).get('raw')):
        same = False                                   # cadran déplacé : centre de ses réglages
        old.fields['vernier'] = new.fields['vernier']
    if 'layer_name' in new.fields:
        old.fields['layer_name'] = new.fields['layer_name']
    if old.cls.name == 'CCalque' and 'props' in old.fields and 'NAME' in old.fields['props']:
        old.fields['props']['NAME'] = new.fields.get('layer_name', old.fields['props']['NAME'])
    if old.cls.name == 'CCalque' and len(old.fields.get('attrs', b'')) >= 12 and 'attrs' in new.fields:
        # outil du calque (3ᵉ entier) ; le reste des attributs d'origine est gardé
        a = bytearray(old.fields['attrs'])
        a[8:12] = new.fields['attrs'][8:12]
        old.fields['attrs'] = bytes(a)
    for o, n in zip(old.fields.get('slots', old.children), new.fields.get('slots', new.children)):
        same = _patch(o, n) and same
    if 'bbox' in new.fields and not same and not _close(old.fields.get('bbox'), new.fields['bbox']):
        old.fields['bbox'] = new.fields['bbox']
    return same


def _paragraphs(root: MfcObject) -> list:
    """Les textes TypeEdit (`CParagraphe`) de l'arbre, dans l'ordre de `vnd.structure_signature`."""
    out = []

    def walk(o):
        if o is None:
            return
        if o.cls.name == 'CParagraphe':
            out.append(o)
        if 'oblist' in o.fields:
            walk(o.fields['oblist'])
        else:
            lst = o.fields.get('inline_list')
            for ch in (lst.fields['slots'] if lst is not None else o.fields.get('slots', o.children)):
                walk(ch)
        if o.cls.name == 'CContour':
            walk(o.fields.get('ext_obj'))
        if o.cls.name == 'CVnImage' and o.fields.get('courbe') is not None:
            walk(o.fields['courbe'])
    walk(root)
    return out


#: ce qui fait le texte d'un paragraphe TypeEdit (caractères, police, taille, alignement, angle), hors géométrie
_TEXT_KEYS = ('f8', 'f140', 'has_para2', 'para1', 'para2')


def _texts_differ(old_root: MfcObject, new_root: MfcObject) -> bool:
    """Un texte TypeEdit refait (texte, police, taille, alignement, angle…) entre l'arbre d'origine et le nouveau, de
    même structure : le report de la géométrie (`_patch`) ne le suivrait pas."""
    return any(any(o.fields.get(k) != n.fields.get(k) for k in _TEXT_KEYS)
               for o, n in zip(_paragraphs(old_root), _paragraphs(new_root)))


def _tree(doc: Document, page_bbox, report: list | None = None) -> MfcObject:
    root = MfcObject(MfcClass('CTravail', SCHEMAS['CTravail']))
    draw = _bbox_m(doc.bbox())
    if doc.bbox():
        bb = (min(page_bbox[0], draw[0]), min(page_bbox[1], draw[1]), page_bbox[2],
              max(page_bbox[3], draw[3]), max(page_bbox[4], draw[4]), page_bbox[5])
    else:
        bb = page_bbox
    root.fields = _obdao_fields(bb)
    root.fields['ctn_version'] = 3
    with _using_tools(doc):
        root.children.extend(_calques(list(doc.layers) or [Layer(name='Plan 1')], report,
                                      first_shown_of(doc)))  # calques vides compris
    return root


def _all_items(doc: Document):
    def walk(it):
        yield it
        if isinstance(it, Group) and it.extra.get('vnd_obj') is None:
            for ch in it.children:
                yield from walk(ch)
    for L in doc.layers:
        for it in L.items:
            yield from walk(it)


#: Au-delà (mm : mille kilomètres), une coordonnée n'a plus de sens.
MAX_COORD = 1e9
#: L'outil d'un calque est écrit sur 32 bits ; TypeEdit le lit signé.
MAX_TOOL = 0x7FFFFFFF


def _number_ok(v) -> bool:
    """Faux pour NaN, l'infini et l'absurde."""
    try:
        return abs(v) < MAX_COORD
    except TypeError:
        return False


def _point_ok(p) -> bool:
    return _number_ok(p[0]) and _number_ok(p[1])


def _contour_ok(c: Contour) -> bool:
    for s in c.segments:
        if isinstance(s, Line):
            pts = (s.p0, s.p1)
        elif isinstance(s, Cubic):
            pts = (s.p0, s.p1, s.p2, s.p3)
        elif isinstance(s, Conic):
            if not (_number_ok(s.w) and s.w > 0):
                return False
            pts = (s.p0, s.p1, s.p2)
        else:
            pts = (s.start, s.end)
        if not all(_point_ok(p) for p in pts):
            return False
    return True


def _matrix_ok(m) -> bool:
    return all(_number_ok(v) for v in (m.a, m.b, m.c, m.d, m.e, m.f))


def _tool_ok(t) -> bool:
    try:
        return 0 <= int(t or 0) <= MAX_TOOL
    except (TypeError, ValueError, OverflowError):
        return False


def _clean_item(it: Item, notes: Counter) -> Item | None:
    """Objet écrivable, ou None s'il ne reste rien. `it` est une copie : modifiable."""
    if not _tool_ok(it.tool):
        it.tool = 0
        notes['outil'] += 1
    if isinstance(it, Group):
        had = len(it.children)
        it.children = [c for c in (_clean_item(ch, notes) for ch in it.children) if c is not None]
        return None if had and not it.children else it
    if isinstance(it, Shape):
        good = [c for c in it.path.contours if _contour_ok(c)]
        if len(good) != len(it.path.contours):
            notes['contour'] += len(it.path.contours) - len(good)
            if not good:
                return None
            it.path = type(it.path)(good)
        return it
    matrix = getattr(it, 'matrix', None)
    outline = getattr(it, 'outline', None)
    size = getattr(it, 'size', 1.0)
    if ((matrix is not None and not _matrix_ok(matrix)) or not _number_ok(size)
            or (outline is not None and not all(_contour_ok(c) for c in outline.contours))):
        notes['objet'] += 1
        return None
    return it


def _item_clean(it: Item) -> bool:
    if not _tool_ok(it.tool):
        return False
    if isinstance(it, Group):
        return all(_item_clean(ch) for ch in it.children)
    if isinstance(it, Shape):
        return all(_contour_ok(c) for c in it.path.contours)
    matrix = getattr(it, 'matrix', None)
    outline = getattr(it, 'outline', None)
    return ((matrix is None or _matrix_ok(matrix)) and _number_ok(getattr(it, 'size', 1.0))
            and (outline is None or all(_contour_ok(c) for c in outline.contours)))


def clean_items(items: list[Item]) -> tuple[list[Item], Counter]:
    """(objets écrivables, ce qui a été écarté) : `items` n'est pas touché ; sans défaut, la liste rendue est la même."""
    notes: Counter = Counter()
    if all(_item_clean(it) for it in items):
        return items, notes
    from ..core.document import struct_copy
    return [c for c in (_clean_item(struct_copy(it), notes) for it in items) if c is not None], notes


def _plate_ok(p) -> bool:
    return all(_number_ok(v or 0.0) for v in (p.width, p.height, p.x, p.y, p.thickness))


def clean_document(doc: Document) -> tuple[Document, list[str]]:
    """Le document tel qu'il peut aller dans un VND, et les remarques. Un document sain est rendu tel quel. Le document
    de l'utilisateur n'est jamais touché : ce qui est écarté l'est du fichier seulement."""
    import copy
    extra = doc.extra if isinstance(doc.extra, dict) else {}
    origin = extra.get('origine')
    bad_origin = bool(origin) and not _point_ok(origin)
    bad_plate = doc.plate is not None and not _plate_ok(doc.plate)
    bad_layers = any(not _tool_ok(L.tool) or not isinstance(L.name, str) for L in doc.layers)
    if not bad_origin and not bad_plate and not bad_layers and all(_item_clean(it) for L in doc.layers for it in L.items):
        return doc, []
    out = copy.copy(doc)
    out.extra = dict(extra)
    notes: Counter = Counter()
    report: list[str] = []
    if bad_origin:
        out.extra.pop('origine', None)
        report.append('origine du dessin invalide : le zéro du VND reste celui du dessin')
    if bad_plate:
        out.plate = None
        report.append('plaque aux dimensions invalides : non écrite dans le VND')
    layers = []
    for L in doc.layers:
        c = copy.copy(L)
        if not isinstance(c.name, str):
            c.name = str(c.name) if c.name is not None else ''
        if not _tool_ok(c.tool):
            c.tool = 0
            notes['outil'] += 1
        c.items, found = clean_items(L.items)
        notes.update(found)
        layers.append(c)
    out.layers = layers
    if notes['contour']:
        report.append(f'{notes["contour"]} contour(s) aux coordonnées invalides écarté(s) du VND')
    if notes['objet']:
        report.append(f'{notes["objet"]} objet(s) aux coordonnées invalides écarté(s) du VND')
    if notes['outil']:
        report.append(f'{notes["outil"]} numéro(s) d\'outil impossible(s) : outil 1 dans le VND')
    return out, report


def write_document(doc: Document, template: bytes | None = None, *,
                   allow_foreign: bool = False, live_texts: bool | None = None) -> tuple[bytes, list[str]]:
    """VND du document (voir `_write_document`). `live_texts` : textes
    écrits en paragraphes TypeEdit modifiables plutôt qu'en courbes, quand
    TypeEdit peut les relire (`curves_reason`) ; par défaut
    `doc.extra['vnd_textes_vivants']`."""
    global _LIVE
    if live_texts is None:
        live_texts = bool(doc.extra.get('vnd_textes_vivants')) if isinstance(doc.extra, dict) else False
    doc, merged = merged_copies(doc)
    doc, cleaned = clean_document(doc)
    cleaned = merged + cleaned
    doc = at_origin(doc)
    if not live_texts:
        data, report = _write_document(doc, template, allow_foreign=allow_foreign)
        return data, cleaned + report
    _LIVE = _LiveTexts([])
    try:
        data, report = _write_document(doc, template, allow_foreign=allow_foreign)
        return data, cleaned + report
    finally:
        _LIVE = None


def merged_copies(doc: Document) -> tuple[Document, list[str]]:
    """Le document tel que le VND l'écrit : la copie en VD Géo d'un calque (police absente du poste) écrite à sa
    place, pas en plus (`core.missing_fonts.for_vnd`) ; et les remarques. Le document de l'utilisateur n'est pas
    touché."""
    import copy
    from ..core import missing_fonts as MF
    layers, info = MF.for_vnd(list(doc.layers))
    if len(layers) == len(doc.layers) and all(a is b for a, b in zip(layers, doc.layers)):
        return doc, []
    out = copy.copy(doc)
    out.layers = layers
    report = []
    for p in info.values():
        c, L, n = p['copie'], p['original'], p['repris']
        if p['sorte'] == 'fusion':
            line = f'plan « {L.name} » : sa copie en {MF.FONT} (police absente du poste) écrite à sa place, pas en plus'
            if n:
                line += f" ; {n} objet(s) TypeEdit d'origine"
            if len(c.items) > n:
                line += f' ; {len(c.items) - n} modifié(s) ou ajouté(s), tel(s) que VectorDrive les montre'
            if p['retires']:
                line += f" ; {p['retires']} objet(s) d'origine retiré(s) de la copie : pas écrit(s)"
            report.append(line)
        elif p['sorte'] == 'devant':
            report.append(f'copie en {MF.FONT} du plan « {L.name} » écrite derrière lui, cachée (sans correspondance '
                          "de ses objets avec ceux d'origine : dessin d'avant 0.956.0)")
    return out, report


def at_origin(doc: Document) -> Document:
    """Copie du document dont l'origine (doc.extra['origine'], placée au
    centre de la plaque par exemple) devient le zéro du fichier : TypeEdit
    rouvre la même plaque avec la même origine. Sans origine : le document."""
    import copy
    import dataclasses
    from ..core.document import struct_copy_layers
    from ..core.geom import Affine
    o = doc.extra.get('origine') if isinstance(doc.extra, dict) else None
    if not o or (abs(float(o[0])) < 1e-9 and abs(float(o[1])) < 1e-9):
        return doc
    m = Affine.translation(-float(o[0]), -float(o[1]))
    out = copy.copy(doc)
    out.layers = struct_copy_layers(doc.layers)
    for L in out.layers:
        L.items = [it.transformed(m) for it in L.items]
    if doc.plate is not None:
        out.plate = dataclasses.replace(doc.plate, x=doc.plate.x - float(o[0]), y=doc.plate.y - float(o[1]))
    out.extra = dict(doc.extra)
    out.extra.pop('origine', None)
    out.extra['vnd_origin_shift'] = (float(o[0]), float(o[1]))
    return out


def _write_document(doc: Document, template: bytes | None = None, *,
                    allow_foreign: bool = False) -> tuple[bytes, list[str]]:
    """VND du document. Repart du fichier source s'il y en a un (fin de
    document, outils, machine, GUID), sinon du modèle. Les textes et
    cotes TypeEdit ne sont réécrits tels quels que dans leur propre VND
    (`allow_foreign` : essais seulement)."""
    report: list[str] = []
    source = doc.extra.get('vnd_source') if isinstance(doc.extra, dict) else None
    if not source and not allow_foreign:
        doc, foreign = _without_foreign_objects(doc)
        if foreign:
            report.append(f'{foreign} texte(s) ou cote(s) TypeEdit venu(s) d\'un autre fichier : '
                          'écrit(s) comme dessin')
    lost = Counter(it.extra['vnd_obj'].cls.name == 'CObBrep' for it in _all_items(doc)
                   if it.extra.get('vnd_obj') is not None and it.extra['vnd_obj'].cls.name in vnd.HIDDEN_OBJECTS
                   and source_object(it) is None)
    if lost[True]:
        report.append(f'{lost[True]} solide(s) 3D déplacé(s) ou transformé(s) : laissé(s) à leur position '
                      "d'origine (leur géométrie SMLib n'est pas transformable)")
    if lost[False]:
        report.append(f"{lost[False]} point(s) ou axe(s) de construction tourné(s) ou mis à l'échelle : "
                      'non réécrit(s)')
    drawn = [it for it in _all_items(doc) if it.extra.get('vnd_obj') is not None and not isinstance(it, Shape)
             and it.extra['vnd_obj'].cls.name not in vnd.HIDDEN_OBJECTS and source_object(it) is None]
    turned = sum(1 for it in drawn if it.extra.get('vnd_moved'))
    if turned:
        report.append(f"{turned} objet(s) TypeEdit (texte, cote…) tourné(s) ou mis à l'échelle : écrit(s) comme "
                      'dessin (plus modifiables comme tels dans TypeEdit)')
    if len(drawn) > turned:
        report.append(f'{len(drawn) - turned} objet(s) TypeEdit déplacé(s) dont la position ne se corrige pas sans '
                      'risque (code-barres…) : écrit(s) comme dessin, à leur nouvelle place')
    template = template or default_template()
    base = source or template
    root_b, ar_b = vnd.parse(base)                     # une seule lecture de la source
    if source:
        bad = v13_issues(root_b)
        if bad:
            # VND d'une version plus récente que celle de l'atelier : on repart
            # du modèle (TypeEdit 13), objets TypeEdit écrits comme dessin
            report.append('VND source plus récent que TypeEdit 13 (' + bad[0] + ') : réécrit au format de '
                          'TypeEdit 13 depuis le modèle')
            source = None
            doc, _n = _without_foreign_objects(doc)
            base = template
            root_b, ar_b = vnd.parse(base)
    if _LIVE is not None:
        _LIVE.__init__(vnd.font_table(base)[1])        # indices des polices : ceux de la base d'abord
    new_root = _tree(doc, root_b.fields['bbox'], report)
    new_fonts = _LIVE.names[len(_LIVE.base):] if _LIVE is not None else []
    head = _head(base, doc, new_fonts)
    live_lines = []                                    # en fin de compte rendu : la barre d'état en montre la fin
    if _LIVE is not None and _LIVE.count:
        live_lines.append(f'{_LIVE.count} texte(s) écrit(s) en texte TypeEdit modifiable')
    if _LIVE is not None and _LIVE.curves:
        live_lines.append(f'{sum(_LIVE.curves.values())} texte(s) en courbes : '
                          + ' ; '.join(f'{why} ({n})' for why, n in _LIVE.curves.most_common()))
    shifted = isinstance(doc.extra, dict) and doc.extra.get('vnd_origin_shift')
    if shifted:
        report.append('origine du dessin ({0:g} ; {1:g} mm) écrite comme zéro de TypeEdit'.format(*shifted))
    if (source and not shifted and vnd.structure_signature(new_root) == doc.extra.get('vnd_signature')
            and not _texts_differ(root_b, new_root)):
        # structure inchangée : arbre d'origine, géométrie à jour, fin complète (un texte refait n'y passe pas :
        # `_patch` ne reporte que la géométrie, TypeEdit aurait gardé l'ancien texte)
        _patch(root_b, new_root)
        written = root_b
        w = MfcWriter()
        w.write_object(root_b)
        tail = base[root_b.fields['tail_offset']:]
    else:
        written = new_root
        w = MfcWriter()
        w.write_object(new_root)
        tail = _spliced_tail(base, root_b, ar_b, template, report)
    bad = v13_issues(written)
    if bad:
        report.append('à vérifier dans TypeEdit 13 : ' + ' ; '.join(bad[:3]))
    if doc.plate is not None:
        tail = set_plate(tail, doc.plate, report)
    tail = set_tool_colors(tail, doc, report)
    body = bytes(w.buf) + tail
    report.extend(live_lines)
    if source and body == source[archive_start(source):]:
        return source, report                        # rien n'a changé : le fichier d'origine, aperçu compris
    return bytes(head) + body, report


#: ordre des 12 plans du support (deux fois) : (axe, valeur prise dans la plaque)
_PLANES = [(0, 'y0'), (0, 'y1'), (1, 'x0'), (1, 'x1'), (2, 'z0'), (2, 'z1')] * 2


def set_plate(tail: bytes, plate, report: list[str] | None = None) -> bytes:
    """Reporte la plaque (mm) dans la fin de document : boîte du support
    et ses 12 plans (faces y=0, y=H, x=0, x=W, z=−ép., z=0, deux fois).
    Rien n'est changé si la plaque est déjà celle du fichier."""
    from .mfc import Archive
    v = {'x0': plate.x / 1000, 'y0': plate.y / 1000, 'x1': (plate.x + plate.width) / 1000,
         'y1': (plate.y + plate.height) / 1000, 'z0': -(plate.thickness or 0) / 1000, 'z1': 0.0}
    ar = Archive(bytes(tail), 0, vnd.READERS)
    old = struct.unpack_from('<6d', tail, 0)
    new = (v['x0'], v['y0'], v['z0'], v['x1'], v['y1'], v['z1'])
    if all(abs(a - b) < 1e-9 for a, b in zip(old, new)):         # 1 nm : arrondis de TypeEdit
        return tail
    buf = bytearray(tail)
    sup = MfcObject(MfcClass('CSupport', 0))
    vnd.read_obdao_ctn(ar, sup)
    planes = []
    for _ in range(12):
        start = ar.pos
        o = MfcObject(MfcClass('CPlan', 0))
        vnd.read_obdao(ar, o)
        vpos = ar.pos
        ar.f64()
        axis = ar.u32()
        planes.append((start, vpos, axis))
    if [a for _s, _v, a in planes] != [a for a, _k in _PLANES]:
        if report is not None:
            report.append('plans du support dans un ordre inattendu : plaque non reportée')
        return tail
    struct.pack_into('<6d', buf, 0, *new)
    fixed = {0: (1, 4), 1: (0, 3), 2: (2, 5)}            # indices de la coordonnée fixe dans la boîte
    for (start, vpos, axis), (_a, key) in zip(planes, _PLANES):
        bb = list(struct.unpack_from('<6d', buf, start))
        for i in fixed[axis]:
            bb[i] = v[key]
        struct.pack_into('<6d', buf, start, *bb)
        struct.pack_into('<d', buf, vpos, v[key])
    return bytes(buf)


def set_tool_colors(tail: bytes, doc, report: list[str] | None = None) -> bytes:
    """Couleurs des outils du dessin reportées dans la table des outils de TypeEdit (fin de document) :
    TypeEdit montre alors les mêmes couleurs. Seule la couleur (COLORREF) de chaque outil existant change ;
    rien n'est changé si elles sont déjà celles du fichier."""
    from .mfc import Archive
    try:
        ar = Archive(bytes(tail), 0, vnd.READERS)
        head = vnd.parse_tail_head(ar)
    except Exception as ex:                              # fin de document inattendue : laissée telle quelle
        if report is not None:
            report.append(f'couleurs des outils non reportées dans TypeEdit ({ex})')
        return tail
    buf = None
    for i, pos in enumerate(head.get('tool_color_pos', [])):
        t = next((t for t in doc.tools if t.index == i), None)
        if t is None or not str(t.color).startswith('#') or len(str(t.color)) != 7:
            continue
        want = vnd.hex_colorref(t.color)
        if struct.unpack_from('<I', tail, pos)[0] & 0xFFFFFF != want:
            buf = buf if buf is not None else bytearray(tail)
            struct.pack_into('<I', buf, pos, want)
    return bytes(buf) if buf is not None else tail


def _spliced_tail(base: bytes, root_b, ar_b, template: bytes, report: list[str]) -> bytes:
    """Fin du fichier de base jusqu'à la machine, puis fin du modèle (sans
    FAO). Si la base est le modèle, sa fin telle quelle."""
    tail_b = base[root_b.fields['tail_offset']:]
    if base is template:
        return tail_b
    root_t, ar_t = vnd.parse(template)
    try:
        ar_b.pos = root_b.fields['tail_offset']
        hb = vnd.parse_tail_head(ar_b)
        ar_t.pos = root_t.fields['tail_offset']
        ht = vnd.parse_tail_head(ar_t)
    except Exception as ex:
        report.append(f'réglages TypeEdit d\'origine non relus ({ex}) : réglages du modèle')
        return template[root_t.fields['tail_offset']:]
    if b'CToolPath' in base[hb['gii_end']:]:
        report.append('chemins d\'outil FAO d\'origine non conservés (structure modifiée)')
    return base[root_b.fields['tail_offset']:hb['gii_end']] + template[ht['gii_end']:]


def default_template() -> bytes:
    """VND de départ des dessins neufs : celui d'un plugin (modèle de
    d'un atelier), sinon le modèle neutre du cœur."""
    from ..plugins import REGISTRY
    if REGISTRY.vnd_template and pathlib.Path(REGISTRY.vnd_template).is_file():
        return pathlib.Path(REGISTRY.vnd_template).read_bytes()
    p = pathlib.Path(__file__).resolve().parents[1] / 'ressources' / 'vnd_modele.vnd'
    if not p.exists():
        raise VndWriteError('modèle VND absent (vectordrive/ressources/vnd_modele.vnd)')
    return p.read_bytes()


def _expected_items(doc: Document) -> int:
    """Objets de premier niveau qui doivent se retrouver dans le fichier : visibles, et avec quelque chose à écrire."""
    def counts(it) -> bool:
        if not getattr(it, 'visible', True):
            return False
        if isinstance(it, Image):
            return bool(it.data)
        if isinstance(it, Group):
            return any(counts(ch) for ch in it.children)
        return bool(it.bbox())
    return sum(1 for L in doc.layers for it in L.items if counts(it))


def check_written(doc: Document, data: bytes) -> list[str]:
    """Relit le VND qui vient d'être fabriqué, avant qu'il n'aille sur le disque. Illisible, ou vide alors que le dessin
    ne l'est pas : `VndWriteError`, et le fichier déjà là reste intact. Moins grave : les remarques rendues."""
    expected = _expected_items(clean_document(doc)[0])
    try:
        root, _ar = vnd.parse(data, partial=True)
    except Exception as ex:
        raise VndWriteError(f'VND fabriqué illisible, rien n\'est écrit : {ex}') from ex
    calques = [c for c in root.children if c.cls.name == 'CCalque']
    got = sum(len(c.children) for c in calques)
    if expected and not got:
        raise VndWriteError(f'VND fabriqué vide alors que le dessin a {expected} objet(s), rien n\'est écrit')
    notes = []
    if root.fields.get('partial_error'):
        notes.append(f'relecture du VND incomplète ({root.fields["partial_error"]}) : à vérifier dans TypeEdit')
    if expected and calques and not calques[0].children:
        notes.append('premier plan du VND vide : TypeEdit s\'ouvrira sur un plan sans objet')

    def walk(o):
        if o.cls.name == 'CContour' and not vnd.points_finite(o.fields):
            notes.append('coordonnées invalides dans une courbe du VND')
        for ch in o.children:
            if ch is not None:
                walk(ch)
    for c in calques:
        walk(c)
    return list(dict.fromkeys(notes))


def write_atomic(path, data: bytes) -> None:
    """Le fichier apparaît d'un seul coup, complet : une panne en cours d'écriture laisse l'ancien intact. Un fichier
    tenu ouvert par un autre logiciel donne une erreur, pas un fichier à moitié écrit."""
    import os
    p = pathlib.Path(path)
    tmp = p.with_name(f'.{p.name}.{os.getpid()}.tmp')
    try:
        with open(tmp, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def write(doc: Document, path) -> None:
    data, report = write_document(doc)
    report = report + check_written(doc, data)
    doc.report.extend(report)
    write_atomic(path, data)
