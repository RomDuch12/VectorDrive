"""La plaque d'un dessin, écrite en clair dans les formats qui ont une place pour une note — DXF : propriété
personnalisée du dessin ; IGES : section de départ ; SVG : attributs de la racine — et relue : le dessin revient avec
sa plaque (et, en SVG, à sa place) sans fichier compagnon.

La note est une ligne de JSON en ASCII, les champs de `Plate` ; un champ inconnu est ignoré, une note abîmée aussi.
"""
from __future__ import annotations

import html
import json
import math
from dataclasses import fields

from ..core.document import Plate

#: nom de la note, le même dans tous les formats
TAG = 'VectorDrive plaque'
#: au-delà, la note n'est pas écrite (propriété d'un DXF : 255 caractères) — le compagnon garde alors la plaque
MAX = 250
#: attributs de la racine d'un SVG écrit par VectorDrive : la plaque, et la page dans le dessin (coin bas-gauche,
#: largeur, hauteur) — la note ne vaut que tant que la page du fichier est restée celle-là
SVG_PLATE, SVG_ORIGIN = 'data-vd-plaque', 'data-vd-origine'


def to_text(plate) -> str:
    """La note de la plaque ; '' sans plaque, ou si la note serait trop longue."""
    if plate is None:
        return ''
    text = json.dumps(plate.__dict__, ensure_ascii=True, separators=(',', ':'), sort_keys=True)
    return text if len(text) <= MAX else ''


def _number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def from_dict(d) -> Plate | None:
    if not isinstance(d, dict):
        return None
    base, names, out = Plate(), {f.name for f in fields(Plate)}, {}
    for k, v in d.items():
        if k not in names:
            continue                                     # champ d'une autre version
        ref = getattr(base, k)
        if isinstance(ref, bool):
            ok = isinstance(v, bool)
        elif isinstance(ref, float):
            ok = _number(v)
        elif isinstance(ref, str):
            ok = isinstance(v, str)
        elif isinstance(ref, list):
            ok = isinstance(v, list) and len(v) == len(ref) and all(_number(x) for x in v)
        else:
            ok = False
        if not ok:
            return None
        out[k] = float(v) if isinstance(ref, float) else ([float(x) for x in v] if isinstance(ref, list) else v)
    if not out.get('width', 0) > 0 or not out.get('height', 0) > 0:
        return None
    return Plate(**out)


def from_text(text) -> Plate | None:
    """La plaque d'une note, ou None : pas de note, note abîmée."""
    try:
        return from_dict(json.loads(text)) if text else None
    except (TypeError, ValueError):
        return None


def find_in(text: str) -> Plate | None:
    """La plaque d'une note « VectorDrive plaque : {…} » posée dans un texte libre (section de départ d'un IGES)."""
    at = text.find(TAG + ' : ')
    if at < 0:
        return None
    try:
        d, _end = json.JSONDecoder().raw_decode(text[at + len(TAG) + 3:].lstrip())
    except ValueError:
        return None
    return from_dict(d)


def of_dxf(drawing) -> Plate | None:
    """La plaque notée dans les propriétés personnalisées d'un DXF (document ezdxf)."""
    try:
        return from_text(drawing.header.custom_vars.get(TAG))
    except Exception:                                    # noqa: BLE001 — en-tête sans propriétés, ou abîmé
        return None


def svg_page(text, view_box, tol: float = 1e-3):
    """Le coin bas-gauche de la page dans le dessin, d'après la note `text` (« x0 y0 largeur hauteur »), si la page du
    fichier (`view_box` : les quatre nombres de son viewBox) est restée celle de l'écriture ; None sinon — page
    recadrée par un autre logiciel, note absente ou d'une autre forme : le fichier se lit comme tout SVG."""
    try:
        x0, y0, w, h = (float(v) for v in str(text or '').split())
    except ValueError:
        return None
    if len(view_box) != 4 or not all(math.isfinite(v) for v in (x0, y0, w, h)):
        return None
    same = abs(view_box[0] - x0) <= tol and abs(view_box[1]) <= tol and abs(view_box[2] - w) <= tol \
        and abs(view_box[3] - h) <= tol
    return (x0, y0) if same else None


def svg_attributes(plate, x0: float, y0: float, w: float, h: float) -> str:
    """Les attributs à poser sur la racine d'un SVG : la page dans le dessin, et la plaque s'il y en a une."""
    out = f' {SVG_ORIGIN}="{float(x0)!r} {float(y0)!r} {float(w)!r} {float(h)!r}"'
    note = to_text(plate)
    if note:
        out += f' {SVG_PLATE}="{html.escape(note, quote=True)}"'
    return out
