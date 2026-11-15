"""Modèles de parcours TypeEdit (`.ttpl`, dossier PRESET de TypeEdit) :
XML `gangdrill.BdOTool` — l'outil (type, diamètre, troncature, rayon,
avances en m/min, broche, profondeur maxi, passe) et sa table de
paramètres `mapparam.CMapParam` (clé = valeur). Interopérabilité seulement.

Unités du XML : longueurs en mm, angles en radians (demi-angle), avances en
m/min. Lu en modèle d'usinage VectorDrive (un outil, une opération) ; un
modèle d'une opération s'écrit en `.ttpl` pour TypeEdit.
"""
from __future__ import annotations

import math
import pathlib
import xml.etree.ElementTree as ET
from xml.sax.saxutils import quoteattr

from . import model
from .tooldb import KINDS

ROOT_TAG = 'gangdrill.BdOTool'
MAP_TAG = 'mapparam.CMapParam'
#: nature VectorDrive → type TypeEdit
TYPES = {'conique': 0, 'fraise': 1, 'boule': 2, 'laser': 6}
#: dossiers où TypeEdit range ses modèles (V13, V15)
PRESET_DIRS = ['C:/TypeEdit_V13-LaserType_V13/PRESET', 'C:/TypeEdit_V15-LaserType_V15/PRESET',
               'C:/ProgramData/Gravotech/TypeEdit_V15-LaserType_V15/PRESET']


def _f(attrs: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(attrs.get(key, default))
    except (TypeError, ValueError):
        return default


def op_kind_for(kind: str, name: str = '') -> str:
    """Opération VectorDrive d'un modèle TypeEdit : la nature de l'outil, et
    le nom (« Contournage », « Perçage », « Poche »…) quand il le dit."""
    n = (name or '').lower()
    if 'poche' in n:
        return 'poche'
    if 'contour' in n or 'détour' in n or 'detour' in n or 'découp' in n:
        return 'detourage'
    if 'perç' in n or 'perc' in n:
        return 'percage'
    return {'conique': 'gravure', 'laser': 'laser_gravure'}.get(kind, 'detourage')


def parse(text: str, name: str = '') -> dict:
    """Modèle d'usinage (dict de `cam.templates`) d'un `.ttpl`."""
    root = ET.fromstring(text)
    if root.tag != ROOT_TAG:
        raise ValueError(f'pas un modèle de parcours TypeEdit ({root.tag})')
    a = root.attrib
    params = {}
    m = root.find(MAP_TAG)
    if m is not None:
        params.update({k: v for k, v in m.attrib.items()})
        for ch in m:                                     # entrées éventuelles <… key=… value=…/>
            k = ch.attrib.get('key') or ch.attrib.get('name') or ch.tag
            params[k] = ch.attrib.get('value', ch.text or '')
    kind = KINDS.get(int(_f(a, 'type', 1)), 'fraise')
    tool_name = a.get('toolName') or name or 'Outil TypeEdit'
    diameter = _f(a, 'diameter', 1.0)
    half = _f(a, 'angle', 0.0)
    tool = model.CamTool(
        name=tool_name, kind=kind, diameter=diameter,
        tip=_f(a, 'truncation') if kind == 'conique' else 0.0,
        angle=round(math.degrees(2 * half), 6) if half else 0.0,
        flutes=max(1, int(_f(a, 'nbdent', 1))), cut_length=_f(a, 'maxDepth', 3.0) or 3.0,
        number=max(1, int(_f(a, 'num', 1))), ref=a.get('reference', ''), vendor=a.get('supplier', ''),
        spindle=_f(a, 'snominal', 20000.0) or 20000.0, feed=round(_f(a, 'fnominal', 0.6) * 1000, 6) or 600.0,
        plunge=round(_f(a, 'fplg', 0.2) * 1000, 6) or 200.0,
        step_down=_f(a, 'passDepth', 0.2) or 0.2)
    if _f(a, 'radius'):
        tool.geometry['R'] = _f(a, 'radius')
    op = model.Operation(name=name or tool_name, kind=op_kind_for(kind, f'{name} {tool_name}'), tool_id=tool.id,
                         depth=_f(a, 'maxDepth', 0.2) or 0.2, step_down=_f(a, 'passDepth', 0.0),
                         sources=[])
    return {'name': name or tool_name, 'description': f'Modèle de parcours TypeEdit ({tool_name})',
            'tools': [tool.to_dict()], 'operations': [op.to_dict()], 'post': '', 'machine': '',
            'typeedit': {'attrs': dict(a), 'params': params}}


def read(path) -> dict:
    p = pathlib.Path(path)
    data = p.read_bytes()
    try:
        text = data.decode('utf-8') if b'encoding="UTF-8"' in data[:80].upper() else data.decode('latin-1')
    except UnicodeDecodeError:
        text = data.decode('latin-1')
    # ElementTree refuse une déclaration d'encodage dans une chaîne déjà décodée
    if text.startswith('<?xml'):
        text = text[text.index('?>') + 2:]
    return parse(text.strip(), p.stem)


def to_xml(tpl: dict) -> str:
    """`.ttpl` d'un modèle d'une opération (son premier outil) ; les
    attributs et paramètres TypeEdit d'un modèle importé sont repris, les
    valeurs de l'outil et de l'opération VectorDrive l'emportent."""
    ops = tpl.get('operations') or []
    tools = {d.get('id'): d for d in tpl.get('tools') or []}
    op = model.Operation.from_dict(ops[0]) if ops else model.Operation()
    td = tools.get(op.tool_id) or next(iter(tools.values()), None)
    t = model.CamTool.from_dict(td) if td else model.CamTool()
    te = tpl.get('typeedit') or {}
    a = {k: str(v) for k, v in (te.get('attrs') or {}).items()}
    for i in range(10):                                  # tables d'usure (vides) attendues par TypeEdit
        a.setdefault(f'tablusi_{i}', '0')
        a.setdefault(f'tablmax_{i}', '1e+011')
        a.setdefault(f'tabcor_{i}', '1')
        a.setdefault(f'tabnum_{i}', '1')
    for i in range(20):
        a.setdefault(f'sampler_{i}', '0')
        a.setdefault(f'samplez_{i}', '0')
    a.setdefault('nbvalsample', '0')
    a.setdefault('limitangle', '0.349066')
    a.setdefault('cutspeed', '0.001')
    a.setdefault('avancepardent', '0.001')
    a.setdefault('volcop', '0')
    a.setdefault('ffast', '4')
    a.setdefault('fmin', '1')
    a.setdefault('fmax', '1')
    a.setdefault('maxpassheight', '0.1')
    a.setdefault('minpassheight', '0')
    a.setdefault('mindepth', '0')
    a.update({
        'type': str(TYPES.get(t.kind, 1)), 'num': str(t.number), 'diameter': f'{t.diameter:g}',
        'angle': f'{math.radians(t.angle / 2):.12g}' if t.angle else '0',
        'truncation': f'{(t.tip if t.kind == "conique" else t.diameter):g}',
        'radius': f'{float((t.geometry or {}).get("R", 0) or 0):g}',
        'maxDepth': f'{op.depth:g}', 'passDepth': f'{(op.step_down or t.step_down):g}',
        'snominal': f'{t.spindle:g}', 'smin': f'{t.spindle:g}', 'smax': f'{t.spindle:g}',
        'fnominal': f'{t.feed / 1000:g}', 'fplg': f'{t.plunge / 1000:g}', 'fdes': f'{t.feed / 1000:g}',
        'nbdent': str(max(1, t.flutes)), 'supplier': t.vendor, 'reference': t.ref,
        'toolName': t.name})
    params = te.get('params') or {}
    attrs = ' '.join(f'{k}={quoteattr(v)}' for k, v in a.items())
    pattrs = ''.join(f' {k}={quoteattr(str(v))}' for k, v in params.items() if k.replace('_', '').isalnum())
    return (f'<?xml version="1.0" encoding="ISO-8859-1" ?>\n<{ROOT_TAG} {attrs}>\n'
            f'\t<{MAP_TAG}{pattrs}>\n\t</{MAP_TAG}>\n</{ROOT_TAG}>\n')


def write(tpl: dict, path) -> pathlib.Path:
    p = pathlib.Path(path)
    p.write_bytes(to_xml(tpl).encode('latin-1', 'replace'))
    return p


def installed() -> list[pathlib.Path]:
    """Modèles `.ttpl` des TypeEdit du poste."""
    import os
    if os.environ.get('VECTORDRIVE_NO_TYPEEDIT') == '1':
        return []
    out = []
    for d in PRESET_DIRS:
        p = pathlib.Path(d)
        if p.is_dir():
            out += sorted(p.glob('*.ttpl'))
    return out
