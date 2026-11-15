"""Lecture des documents TypeEdit / Gravostyle (.vnd).

En bref :

    en-tête 12 octets : magic 0x00211173, u32 début de l'archive, u32 ?
    vignette (jusqu'au début de l'archive)
    archive MFC : CTravail ─ CCalque[] ─ CZone[] ─ CCourbe[] ─ CContour[] ─ points

Unités du fichier : **mètres**. Points de contrôle en coordonnées
**homogènes** (x·w, y·w, z·w, w) ; bit 0 du drapeau d'un point = nœud
(fin d'une portion de courbe). Entre deux nœuds : 0 point → droite,
1 point → conique (arc exact si w < 1), 2 points → Bézier cubique.
"""
from __future__ import annotations

import math
import pathlib
import struct

from ..core.document import Document, Group, Image, Layer, Plate, Shape, Text, Tool
from ..core.geom import Affine, Conic, Contour, Cubic, Line, Path, Segment
from ..core.geom import circle as circle_contour
from .mfc import Archive, ArchiveError, MfcClass, MfcObject

MAGIC = 0x00211173
GVT_MAGIC = 0x00290768          # .gvt (TypeEdit 9 et plus) : même archive MFC
M_TO_MM = 1000.0
MM_TO_M = 1.0 / M_TO_MM

#: Drapeaux d'un CObDao qui annoncent le format « moderne » (version, GUID,
#: propriétés). Les autres valeurs = ancien format, réduit à la bbox.
_MODERN = (0x1000010, 0x1000100, 0x1001000)


class VndError(ValueError):
    pass


# --- lecteurs de classes -------------------------------------------------------

def _guid(ar: Archive, f: dict) -> None:
    """CObjGuid::Serialize."""
    ver = ar.u32()
    f['guid_ver'] = ver
    f['guid'] = ar.raw(16).hex()
    props = {}
    if ver < 3:
        if ver == 2:
            for _ in range(ar.u32()):
                k = ar.std_string()
                props[k] = ar.std_string()
    else:
        for _ in range(ar.u32()):
            k = ar.cstring()
            props[k] = ar.cstring()
    f['guid_props'] = props


def _map_parameters(ar: Archive, f: dict) -> None:
    n = ar.u32()
    if n > 0:
        raise ArchiveError(f'CMapParam non encore décodé ({n} paramètres) à {ar.pos}')


def read_obdao(ar: Archive, obj: MfcObject) -> None:
    """CObDao::Serialize — en-tête commun à tous les objets du dessin."""
    f = obj.fields
    f['bbox'] = ar.f64s(6)
    flags = ar.u32()
    f['flags'] = flags
    if flags & ~1 not in _MODERN:
        return
    ver = ar.u32()
    f['version'] = ver
    if ver < 1:
        return
    f['f88'] = ar.u32()
    if 2 <= ver <= 7:
        f['name'] = ar.std_string()
    if ver >= 3:
        f['f8c'] = ar.u32()
    if ver < 4:
        return
    f['f90'] = ar.u32()
    f['f94'] = ar.u32()
    if ver == 6:
        f['guid'] = ar.raw(16).hex()
    elif ver > 6:
        _guid(ar, f)
    props = {}
    if ver < 10:
        if ver > 7:
            for _ in range(ar.u64()):
                k = ar.std_string()
                props[k] = ar.std_string()
        if ver > 8:
            _map_parameters(ar, f)
    else:
        for _ in range(ar.u64()):
            k = ar.cstring()
            props[k] = ar.cstring()
        _map_parameters(ar, f)
    f['props'] = props
    if 'name' not in f and 'NAME' in props:
        f['name'] = props['NAME']


def _add_child(obj: MfcObject, ch: MfcObject | None) -> None:
    """Enfant lu par référence. Une référence vers un objet dont la lecture
    n'est pas terminée (la liste elle-même ou un ancêtre) est un pointeur de
    retour, écrit par d'anciens TypeEdit : gardé dans `slots` pour la
    réécriture, mais pas compté comme enfant (sinon le dessin boucle)."""
    if ch is not None and ch.end > 0:
        obj.children.append(ch)


def read_obdao_fin(ar: Archive, obj: MfcObject) -> None:
    read_obdao(ar, obj)
    if obj.fields['flags'] & ~1 in (0x1000010, 0x1000100):
        obj.fields['fin'] = ar.u32()


def read_obdao_ctn(ar: Archive, obj: MfcObject, n_fixed: int = 0) -> None:
    """CObDaoCtn::Serialize — un objet qui contient d'autres objets.

    Après la liste des enfants viennent les `n_fixed` objets « fixes »
    (`getNbFixe` / `getAtFixe`), sérialisés directement, sans étiquette.
    """
    read_obdao(ar, obj)
    mode = obj.fields['flags'] & ~1
    if mode == 0x1001000:
        obj.fields['ctn_version'] = ar.u32()     # lu en ligne (invisible au décompilé)
        n = ar.u32()
        slots = []                               # None = emplacement vide (étiquette 0)
        for _ in range(n):
            ch = ar.read_object()
            slots.append(ch)
            _add_child(obj, ch)
        obj.fields['slots'] = slots
    elif mode == 0x1000100:
        # format ancien : les enfants passent par un objet CObList
        lst = ar.read_object()
        obj.fields['oblist'] = lst
        if lst is not None:
            for c in lst.fields.get('slots', lst.children):
                _add_child(obj, c)
    else:
        # format plus ancien encore : CObList::Serialize en ligne
        lst = MfcObject(MfcClass('CObList', 0), start=ar.pos)
        _oblist_body(ar, lst)
        obj.fields['inline_list'] = lst
        for c in lst.fields['slots']:
            _add_child(obj, c)
    fixed = []
    for i in range(n_fixed):
        fixed.append(ar.embedded('CObDaoCtn', 0))
    if fixed:
        obj.fields['fixed'] = fixed
    if mode in (0x1000010, 0x1000100):
        # formats anciens : un entier de plus en fin de conteneur (le test de
        # Maude porte sur une variable que le format moderne a écrasée par
        # la version du conteneur — d'où son absence en V15)
        obj.fields['ctn_tail'] = ar.u32()


def _oblist_body(ar: Archive, obj: MfcObject) -> None:
    """CObList::Serialize : compte (WORD, ou 0xFFFF + DWORD), puis objets."""
    n = ar.u16()
    obj.fields['big_count'] = n == 0xFFFF
    if n == 0xFFFF:
        n = ar.u32()
    slots = []
    for _ in range(n):
        ch = ar.read_object()
        slots.append(ch)
        _add_child(obj, ch)
    obj.fields['slots'] = slots


def read_oblist(ar: Archive, obj: MfcObject) -> None:
    _oblist_body(ar, obj)


def read_calque(ar: Archive, obj: MfcObject) -> None:
    """CCalque::Serialize. Schéma ≥ 8 : un objet fixe (repère du calque)
    après les zones. Puis le nom, des attributs lus en ligne (32 octets au
    schéma 8 : visibilité, verrou, couleur 0x00f4f4f4…) et le nom du
    repère (« O X Y Z »)."""
    v = obj.cls.schema
    read_obdao_ctn(ar, obj, n_fixed=1 if v - 1 > 6 else 0)
    obj.fields['layer_name'] = ar.cstring()
    # attributs lus en ligne : 4 octets par palier de version 2..5, puis 16
    n_attr = (4 * min(max(v - 1, 0), 4)) + (16 if v > 5 else 0)
    obj.fields['attrs'] = ar.raw(n_attr)
    if v > 6:
        if v < 9:
            obj.fields['axis_name'] = ar.std_string()
        else:
            obj.fields['axis_name'] = ar.cstring()


def read_zone(ar: Archive, obj: MfcObject) -> None:
    read_obdao_ctn(ar, obj)


#: Fin de CCourbe, lue en ligne (le décompilé n'en montre que l'effet :
#: champs +0x108 = 0, +0x114 = 0, +0x118 = 4). Observé : 16 × 0, 4, 0.
COURBE_TRAILER = 24


def read_courbe(ar: Archive, obj: MfcObject) -> None:
    read_obdao_ctn(ar, obj)
    obj.fields['trailer'] = ar.raw(COURBE_TRAILER)


def read_contour(ar: Archive, obj: MfcObject) -> None:
    """CContour::Serialize : type, points, propriétés étendues."""
    read_obdao_fin(ar, obj)
    f = obj.fields
    f['type'] = ar.i32()                  # 0 ouvert, 1 fermé trigo, 2 fermé horaire
    n = ar.u32()
    if n > 10_000_000:
        raise ArchiveError(f'nombre de points aberrant {n} à {ar.pos - 4}')
    raw = ar.raw(36 * n)
    f['points'] = list(struct.iter_unpack('<4dI', raw))      # (x, y, z, w, drapeau), en C
    f['finite'] = _finite_points(raw, n)
    if obj.cls.schema > 1:
        ext = ar.read_object()
        f['ext_obj'] = ext
        if ext is not None:
            f['ext'] = ext.fields


def read_property_extend(ar: Archive, obj: MfcObject) -> None:
    """CPropertyExtend::Serialize — couleur, épaisseur, attributs."""
    f = obj.fields
    v = ar.i32()
    f['version'] = v
    if v > 0:
        f['f10'] = ar.u64()
        f['f0c'] = ar.u32()
        f['color'] = ar.u32()
    if v > 1:
        f['fill_color'] = ar.u32()
    if v > 2:
        f['f20_2c'] = [ar.u32() for _ in range(4)]
        n = ar.i32()
        f['ints'] = [ar.u32() for _ in range(max(0, n))]
        f['f40'] = ar.u32()
        f['f44'] = ar.u32()
    if v > 3:
        f['f48'] = ar.u64()
        n = ar.i32()
        f['doubles'] = [ar.f64() for _ in range(max(0, n))]
    if v < 5:
        return
    f['f80_98'] = ar.f64s(4)
    n = ar.i32()
    f['s60'] = ar.raw(max(0, n)).decode('cp1252', 'replace')
    if ar.u32():
        f['zone_a'] = ar.embedded('CZone', 1)
    n = ar.i32()
    f['s70'] = ar.raw(max(0, n)).decode('cp1252', 'replace')
    if ar.u32():
        f['zone_b'] = ar.embedded('CZone', 1)


def read_vnimage(ar: Archive, obj: MfcObject) -> None:
    """CVnImage::Serialize — image bitmap posée dans le dessin."""
    read_obdao_fin(ar, obj)
    f = obj.fields
    v = obj.cls.schema
    # coin haut-gauche (x, y), coin bas-droit (x, y), angle ? — en mètres
    f['geom'] = ar.f64s(5)
    n = ar.i32()
    f['bitmap'] = ar.raw(max(0, n))        # DIB : BITMAPINFOHEADER + pixels
    if v < 2:
        return
    f['f128'] = ar.u32()
    if v in (4, 5):
        f['has_courbe'] = ar.u32()
        if f['has_courbe']:
            ch = ar.read_object()
            f['courbe'] = ch
            _add_child(obj, ch)


# --- texte -------------------------------------------------------

def _txtattr_para(ar: Archive) -> bytes:
    """CTxtAttrPara : version, entier, 2 f64, puis selon version."""
    st = ar.pos
    v = ar.u32()
    ar.raw(4 + 16 + (8 if v >= 2 else 0) + (16 if v >= 3 else 0) + (4 if v > 3 else 0))
    return ar.data[st:ar.pos]


def _txtattr_line(ar: Archive) -> bytes:
    """CTxtAttrLine : version, entier, 5 f64, puis selon version."""
    st = ar.pos
    v = ar.u32()
    ar.raw(4 + 40 + (8 if v > 1 else 0) + (4 if v > 2 else 0) + (8 if v > 3 else 0))
    return ar.data[st:ar.pos]


#: Taille d'un CTxtAttrChar selon sa version (version comprise). La v5 —
#: seule vue — fait 204 octets ; les champs connus sont décodés par
#: `char_attrs`.
TXT_CHAR_SIZE = {2: 80, 3: 84, 4: 92, 5: 204}


def _txtattr_char(ar: Archive) -> bytes:
    st = ar.pos
    v = ar.u32()
    if v not in TXT_CHAR_SIZE:
        raise ArchiveError(f'attribut de caractère version {v} non décodé à {st}')
    ar.raw(TXT_CHAR_SIZE[v] - 4)
    return ar.data[st:ar.pos]


def char_attrs(raw: bytes) -> dict:
    """Champs utiles d'un CTxtAttrChar : code Unicode, indice de police
    (table du fichier), hauteur des capitales (m), rapport de largeur.
    En v5, les 112 derniers octets sont un CPropertyExtend intégré."""
    v, code, font = struct.unpack_from('<III', raw, 0)
    height, ratio = struct.unpack_from('<dd', raw, 12)
    return {'version': v, 'code': code, 'font': font, 'height': height, 'ratio': ratio}


def layout_paragraph(par: MfcObject, font_table: list[str]) -> tuple[str, str, float, 'Path']:
    """Texte TypeEdit → (texte, police, hauteur mm, contour en mm).

    Le fichier ne garde pas les glyphes : il garde, pour chaque caractère,
    son code, sa police, sa hauteur de capitales et sa boîte (4 coins).
    On pose le glyphe exact de la police installée : échelle donnée par la
    hauteur, ligne de base tirée de la boîte, glyphe centré dans la boîte
    (la boîte suit la chasse et l'interlettrage de TypeEdit).
    """
    from ..core import fonts as F
    from ..core.geom import Affine as A
    chars = [char_attrs(r) for r in par.fields['para1']['chars']]
    boxes = par.fields.get('boxes', [])
    text = paragraph_text(par)
    font_name = 'Arial'
    if chars:
        idx = chars[0]['font']
        if 0 <= idx < len(font_table):
            font_name = font_table[idx]
    found = F.find_font(font_name)
    contours = []
    height = chars[0]['height'] * M_TO_MM if chars else 0.0
    if found:
        m = F.metrics(*found)
        for c, bx in zip(chars, boxes):
            if c['code'] in (0, 9, 10, 13, 32):
                continue
            g, _adv = F.glyph(found[0], found[1], chr(c['code']))
            if not g:
                continue
            gb = g.bbox()
            x0, y0, x1, y1, x2, y2, x3, y3 = (v * M_TO_MM for v in bx[:8])
            ux, uy = x3 - x0, y3 - y0
            vx, vy = x1 - x0, y1 - y0
            w, H = math.hypot(ux, uy), math.hypot(vx, vy)
            if w < 1e-9 or H < 1e-9:
                continue
            ux, uy, vx, vy = ux / w, uy / w, vx / H, vy / H
            em = c['height'] * M_TO_MM / (m['cap'] / m['upem']) if c['height'] > 0 else H
            s = em / m['upem']
            sx = s * (c['ratio'] or 1.0)
            # ligne de base : fraction « descente » de la boîte
            base = H * m['descent'] / (m['ascent'] + m['descent'])
            # centre horizontal de l'encre au centre de la boîte
            cx_ink = (gb[0] + gb[2]) / 2 * sx
            off_u = w / 2 - cx_ink
            ox = x0 + ux * off_u + vx * base
            oy = y0 + uy * off_u + vy * base
            mat = A(ux * sx, uy * sx, vx * s, vy * s, ox, oy)
            contours.extend(cc.transformed(mat) for cc in g.contours)
    return text, font_name, height, Path(contours)


def paragraph_matrix(par: MfcObject, t) -> Affine:
    """Position d'un texte TypeEdit pour la mise en page de VectorDrive :
    angle de la ligne de base (boîte du 1er caractère), rapport de largeur,
    interlettrage, interligne et alignement (déduits des lignes et des
    boîtes de caractères), puis translation qui pose le texte recalculé
    sur le tracé TypeEdit. Sert quand le texte est modifié : il reste en
    place au lieu de partir à l'origine."""
    from ..core import fonts as F
    from ..core import text as TX
    boxes = par.fields.get('boxes') or []
    ang = 0.0
    if boxes:
        x0, y0, *_r = boxes[0]
        x3, y3 = boxes[0][6], boxes[0][7]
        if math.hypot(x3 - x0, y3 - y0) > 1e-12:
            ang = math.atan2(y3 - y0, x3 - x0)
    if not t.outline or not t.text.strip():
        return Affine()
    chars = [char_attrs(r) for r in par.fields['para1']['chars']]
    # rapport de largeur des caractères (étroit, large), s'il est commun
    ratios = {round(c['ratio'] or 1.0, 6) for c in chars if c['code'] not in (0, 9, 10, 13, 32)}
    if len(ratios) == 1:
        t.width_ratio = ratios.pop()
    unrot = Affine.rotation(-math.degrees(ang))
    # texte droit (le cas courant) : boîte du contour déjà connue
    a = t.outline.bbox() if abs(ang) < 1e-12 else t.outline.transformed(unrot).bbox()
    if not a:
        return Affine()
    lines = t.text.split('\n')
    # alignement : 2 bits bas des drapeaux de la 1re ligne (0 gauche, 1 droite, 2 centré)
    la = par.fields['para1']['lines']
    known = bool(la) and len(la[0]) >= 8
    if known:
        t.align = {0: 'left', 1: 'right', 2: 'center'}.get(struct.unpack_from('<I', la[0], 4)[0] & 3, t.align)
    if len(lines) > 1:
        # interligne : décalages verticaux des lignes (m)
        ys = [struct.unpack_from('<5d', ln, 8)[1] for ln in par.fields['para1']['lines'] if len(ln) >= 48]
        ff = F.find_font(t.font)
        if len(ys) >= 2 and ff:
            em = TX.em_for_height(ff, t.size)
            pitch = abs(ys[1] - ys[0]) * M_TO_MM
            if em > 0 and pitch > 0:
                t.line_spacing = pitch / em
        # alignement : bords des lignes d'après les boîtes des caractères
        ext: list[list[float]] = [[]]
        for c, bx in zip(chars, boxes):
            if c['code'] == 13:
                ext.append([])
                continue
            if c['code'] in (0, 9, 10, 32):
                continue
            px = [unrot.apply((bx[k] * M_TO_MM, bx[k + 1] * M_TO_MM))[0] for k in (0, 2, 4, 6)]
            ext[-1] += [min(px), max(px)]
        rows = [(min(e), max(e)) for e in ext if e]
        if len(rows) > 1 and not known:
            spread = {'left': max(r[0] for r in rows) - min(r[0] for r in rows),
                      'right': max(r[1] for r in rows) - min(r[1] for r in rows),
                      'center': max((r[0] + r[1]) / 2 for r in rows) - min((r[0] + r[1]) / 2 for r in rows)}
            t.align = min(spread, key=spread.get)
    # boîtes de la mise en page de VectorDrive (sans construire les contours)
    try:
        b = TX.layout_bbox(t.text, t.font, t.size, width_ratio=t.width_ratio, align=t.align,
                           line_spacing=t.line_spacing)
    except Exception:
        return Affine()
    if not b:
        return Affine()
    # interlettrage qui redonne la largeur TypeEdit (ligne la plus longue)
    n = max(len(ln.rstrip()) for ln in lines)
    if n > 1:
        t.spacing = ((a[2] - a[0]) - (b[2] - b[0])) / (n - 1)
        b = TX.layout_bbox(t.text, t.font, t.size, width_ratio=t.width_ratio, spacing=t.spacing,
                           align=t.align, line_spacing=t.line_spacing) or b
    # le texte recalculé, tourné, translaté sur le tracé TypeEdit
    rot = Affine.rotation(math.degrees(ang))
    if t.align == 'center':
        dx = (a[0] + a[2]) / 2 - (b[0] + b[2]) / 2
    elif t.align == 'right':
        dx = a[2] - b[2]
    else:
        dx = a[0] - b[0]
    return rot @ Affine.translation(dx, a[1] - b[1])


def relayout(t, font_table: list[str], fonts: dict | None = None) -> bool:
    """Texte TypeEdit relu (`vnd_obj`) redessiné quand sa police n'est plus la même que celle de la lecture —
    installée depuis, ou remplacée (`fonts` : {police du fichier : police employée}) : ses glyphes posés dans les
    boîtes de TypeEdit, son interlettrage et sa position recalés sur elle (à la lecture, ils l'étaient sur la police de
    remplacement). Un texte transformé depuis (autre chose qu'une translation) garde sa mise en page, l'interlettrage
    recalé. Rend faux si ce n'est pas un texte TypeEdit relu."""
    from ..core import text as TX
    obj = (t.extra or {}).get('vnd_obj')
    if getattr(getattr(obj, 'cls', None), 'name', None) != 'CParagraphe':
        return False
    table = [(fonts or {}).get(f, f) for f in font_table]
    text, font, height, raw = layout_paragraph(obj, table)
    fresh = Text(text=text, font=font, size=height, outline=raw)
    m = paragraph_matrix(obj, fresh)
    if t.text == text and t.font == font and not t.extra.get('vnd_moved') and raw.contours:
        dx, dy = t.extra.get('vnd_shift', (0.0, 0.0))
        move = Affine.translation(dx, dy)
        t.spacing, t.width_ratio, t.align, t.line_spacing = (fresh.spacing, fresh.width_ratio, fresh.align,
                                                             fresh.line_spacing)
        t.matrix = move @ m
        t.outline = raw.transformed(move)
        return True
    if t.font == font:
        t.spacing = fresh.spacing
    t.outline = TX.outline_for(t)
    return True


def _txtpara(ar: Archive) -> dict:
    """CTxtPara : attributs de paragraphe, de lignes, de caractères."""
    para = _txtattr_para(ar)
    lines = [_txtattr_line(ar) for _ in range(ar.u32())]
    n = ar.u32()
    if n > 1_000_000:
        raise ArchiveError(f'nombre de caractères aberrant {n}')
    chars = [_txtattr_char(ar) for _ in range(n)]
    return {'para': para, 'lines': lines, 'chars': chars}


def read_paragraphe(ar: Archive, obj: MfcObject) -> None:
    """CParagraphe (texte vivant) : attributs, caractères, boîte de chaque
    caractère (4 coins en float32, m), courbes associées."""
    if obj.cls.schema < 5:
        raise ArchiveError('texte TypeEdit ancien (CParagraphe < 5) non décodé')
    read_obdao_fin(ar, obj)
    f = obj.fields
    f['f8'] = ar.u32()
    f['f140'] = ar.raw(8)
    f['has_para2'] = ar.u32()
    f['f160'] = ar.u32()
    f['origin'] = ar.f64s(3)
    f['para1'] = _txtpara(ar)
    if f['has_para2']:
        f['para2'] = _txtpara(ar)
    f['f164'] = ar.u32()
    f['blob'] = ar.raw(ar.u32())
    f['cube'] = ar.f64s(6)
    nb = ar.u32()
    f['boxes'] = [struct.unpack_from('<8fI', ar.raw(36)) for _ in range(nb)]
    f['courbe1'] = ar.read_object()
    f['courbe2'] = ar.read_object()
    for c in (f['courbe1'], f['courbe2']):
        if c is not None:
            obj.children.append(c)
    if obj.cls.schema > 5:
        f['f148'] = ar.u32()


def paragraph_text(obj: MfcObject) -> str:
    chars = obj.fields['para1']['chars']
    out = []
    for raw in chars:
        c = char_attrs(raw)['code']
        if c == 0:
            break
        out.append('\n' if c == 13 else chr(c))
    return ''.join(out)


def read_travail(ar: Archive, obj: MfcObject) -> None:
    """CTravail::Serialize : calques, puis réglages du document. Les
    réglages ne sont pas encore décodés : on s'arrête après les calques et
    on garde le reste brut pour la réécriture."""
    read_obdao_ctn(ar, obj)
    obj.fields['tail_offset'] = ar.pos


def _read_plane(ar: Archive) -> tuple:
    """Plan du support : CObDao + position (m) + axe (0 = Y, 1 = X, 2 = Z)."""
    o = MfcObject(MfcClass('CPlan', 0))
    read_obdao(ar, o)
    return (o.fields['bbox'], ar.f64(), ar.u32())


def _read_variable(ar: Archive, obj: MfcObject) -> None:
    """CVariable (MaudeTxt.dll, schéma ≥ 2) : variables du document — `u32`
    n listes ; chacune `u32` k puis k chaînes CVnStringUnicode (`u32`
    nombre de caractères, UTF-16 et un caractère nul ; vide : la longueur
    seule) ; enfin un `u32`.
    Les listes vont dans `obj.fields['variables']`."""
    n = ar.u32()
    if n > 10000:
        raise ArchiveError(f'variables TypeEdit : {n} listes à {ar.pos - 4}')
    lists = []
    for _ in range(n):
        k = ar.u32()
        vals = []
        for _ in range(k):
            m = ar.u32()
            if m > 100000:
                raise ArchiveError(f'variable TypeEdit de {m} caractères à {ar.pos - 4}')
            vals.append(ar.raw(2 * m).decode('utf-16-le', 'replace'))
            if m and ar.raw(2) != b'\0\0':                 # chaîne vide : sa longueur seule
                raise ArchiveError(f'variable TypeEdit non terminée à {ar.pos - 2}')
        lists.append(vals)
    obj.fields['variables'] = lists
    obj.fields['f18'] = ar.u32()


def parse_tail_head(ar: Archive) -> dict:
    """Début de la fin de document, jusqu'à la machine (`CInfoGii`) :
    support (plaque) et ses 12 plans, plan-repère, grille, variables,
    version de modèle, table des outils, machine.

    Tout ce qui suit (chemins d'outil, couleurs et paramètres, laser,
    repères) reste brut. `gii_end` = position où il commence.
    """
    out: dict = {}
    sup = MfcObject(MfcClass('CSupport', 0))
    read_obdao_ctn(ar, sup)
    out['support_bbox'] = sup.fields['bbox']
    out['planes'] = [_read_plane(ar) for _ in range(12)]
    out['support_u32'] = ar.u32()
    rep = MfcObject(MfcClass('CPlanRepere', 0))
    read_obdao_ctn(ar, rep)
    gr = MfcObject(MfcClass('CGrille', 0))
    read_obdao_fin(ar, gr)
    out['grille'] = ar.f64s(7)
    saved = ar.readers.get('CVariable')
    ar.readers['CVariable'] = _read_variable
    try:
        var = ar.read_object()
    finally:
        if saved is None:
            ar.readers.pop('CVariable', None)
    out['variables'] = var.fields.get('variables', []) if var is not None else []
    out['model_version'] = ar.u32()
    n = struct.unpack('<h', ar.raw(2))[0]
    tools = []
    out['tool_color_pos'] = []                           # position de la couleur de chaque outil (réécriture)
    for _ in range(max(0, min(n, 200))):
        out['tool_color_pos'].append(ar.pos)
        color = ar.u32()
        name = ar.cstring()
        size = ar.u32()
        ar.raw(size)
        tools.append((color, name))
    out['tools'] = tools
    out['machine'] = ar.cstring()
    out['postpro'] = ar.cstring()
    out['travel'] = ar.f64s(6)
    ar.raw(ar.u32())
    out['gii'] = ar.u32()
    out['gii_end'] = ar.pos
    return out


def colorref_hex(c: int) -> str:
    """COLORREF Windows (0x00BBGGRR) → '#rrggbb'."""
    return f'#{c & 0xFF:02x}{(c >> 8) & 0xFF:02x}{(c >> 16) & 0xFF:02x}'


def hex_colorref(col: str) -> int:
    """'#rrggbb' → COLORREF Windows (0x00BBGGRR)."""
    c = col.lstrip('#')
    r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    return r | (g << 8) | (b << 16)


# --- cotations, marqueurs, axes ---------------------------------------------------
# cotations : CObDaoFin, version, bloc
# « tag_Cotation_Infos » (CoInfoStreamAlgIO::Load), texte imposé (UTF-16),
# CCube3D, GmVector3 ; CCotationLineaire (et Horizontale, Verticale,
# Laterale) ajoute 3 points, 4 CPropertyExtend, la zone de dessin générée
# (facultative) et 3 points de plus selon la version.

#: Bloc d'informations de cotation, dans l'ordre du fichier : (type, clé).
#: 'ws' = compteur puis caractères UTF-16 ; 'wx' = compteur, entier, puis
#: caractères ; 'ver' = bloc présent à partir d'une version.
COTATION_INFO = (
    ('u32', 'type'), ('u32', 'i08'), ('u32', 'i0c'), ('u32', 'i10'),
    ('f64', 'd18'), ('f64', 'd20'), ('f64', 'd28'), ('u32', 'i30'), ('f64', 'd38'),
    ('u32', 'i40'), ('f64', 'd48'), ('f64', 'd50'), ('u32', 'i58'), ('u32', 'i5c'),
    ('f64', 'd80'), ('f64', 'dd0'), ('wx', 's60'),
    ('ver', 0x1131, (('f64', 'df8'), ('wx', 'sd8'))),
    ('ws', 's88'), ('ws', 'sa0'), ('ws', 'sb8'),
    ('u32', 'i118'), ('u32', 'i11c'), ('f64', 'd100'), ('f64', 'd108'), ('f64', 'd110'),
    ('u32', 'i120'), ('u32', 'i124'), ('u32', 'i128'), ('u32', 'i160'), ('u32', 'i164'),
    ('u32', 'i168'), ('f64', 'v130x'), ('f64', 'v130y'), ('f64', 'v130z'),
    ('f64', 'v148x'), ('f64', 'v148y'), ('f64', 'v148z'), ('f64', 'd170'),
    ('u32', 'i180'), ('u32', 'i184'), ('u32', 'i188'), ('bytes', 'b190'), ('u32', 'i198'),
    ('bytes', 'b1a0'),
)


def read_layout(ar: Archive, layout, version: int) -> dict:
    out = {}
    for op in layout:
        kind, key = op[0], op[1]
        if kind == 'u32':
            out[key] = ar.u32()
        elif kind == 'f64':
            out[key] = ar.f64()
        elif kind == 'ws':
            n = ar.i32()
            out[key] = (n, ar.raw(2 * n) if n > 0 else b'')
        elif kind == 'wx':
            n = ar.i32()
            extra = ar.u32()
            out[key] = (n, extra, ar.raw(2 * n) if n > 0 else b'')
        elif kind == 'bytes':
            n = ar.i32()
            out[key] = (n, ar.raw(n) if n > 0 else b'')
        elif kind == 'ver':
            if version >= key:
                out.update(read_layout(ar, op[2], version))
        else:                                       # pragma: no cover
            raise ValueError(kind)
    return out


def read_cotation(ar: Archive, obj: MfcObject) -> None:
    read_obdao_fin(ar, obj)
    f = obj.fields
    v = f['cot_version'] = ar.u32()
    f['info'] = read_layout(ar, COTATION_INFO, v)
    n = ar.i32()
    f['text'] = (n, ar.raw(2 * n) if n > 0 else b'')
    f['cube'] = ar.f64s(6)
    f['v328'] = ar.f64s(3)
    f['pts'] = ar.f64s(9)                    # 3 points (GmVector3), m
    if v > 0x112F:
        f['cot_props'] = [ar.embedded('CPropertyExtend') for _ in range(4)]
        f['has_zone'] = ar.u32()
        f['zone'] = ar.read_object() if f['has_zone'] else None
        if f['zone'] is not None:
            obj.children.append(f['zone'])
    if v > 0x1643:
        f['pts2'] = ar.f64s(9)


def cotation_text(obj: MfcObject) -> str:
    n, raw = obj.fields.get('text', (0, b''))
    return raw.decode('utf-16-le', 'replace') if n > 0 else ''


def read_marker(ar: Archive, obj: MfcObject) -> None:
    """CMarker : point de construction."""
    read_obdao_fin(ar, obj)
    obj.fields['pos'] = ar.f64s(3)
    obj.fields['ints'] = [ar.u32() for _ in range(7)]


def _bcode_str(ar: Archive, schema: int):
    """Chaîne d'un code-barres : octets ASCII précédés de leur nombre
    (schéma < 4), sinon CString MFC."""
    if schema < 4:
        return ar.raw(ar.u32())
    return ar.cstring()


def read_bcode(ar: Archive, obj: MfcObject) -> None:
    """CObBCode : code-barres TypeEdit — en-tête CObDaoFin, dessin du code
    (CZone, facultatif : une image ou des formes), bloc de « norme »
    (longueur comprise, symbologie et réglages du moteur de codes), données,
    puis (schéma ≥ 2) variable et (schéma > 2) un réel."""
    read_obdao_fin(ar, obj)
    v = obj.cls.schema
    f = obj.fields
    f['has_zone'] = ar.u8()
    f['zone'] = ar.read_object() if f['has_zone'] else None
    n = ar.u32()
    f['norme_len'] = n
    f['norme'] = ar.raw(n - 4) if n >= 4 else b''
    f['data'] = _bcode_str(ar, v)
    if v >= 2:
        f['var_flag'] = ar.u8()
        f['i124'] = ar.u32()
        f['var'] = _bcode_str(ar, v) if f['var_flag'] else None
        if v > 2:
            f['d138'] = ar.f64()


def read_new_bcode(ar: Archive, obj: MfcObject) -> None:
    """CObNewBCode1D / CObNewBCode2D : codes-barres de TypeEdit V15
    (MaudeBCode.dll) — en-tête CObDaoFin, dessin du code (CZone
    facultative, 1 octet de présence), bloc de norme (longueur comprise,
    comme CObBCode), données (CString), 2 octets (variable, variable
    avancée), `u32`, nom de variable (CString) si l'un des deux octets
    est non nul, un réel, puis (schéma > 1) deux blocs de 0x58 et 0x50
    octets."""
    read_obdao_fin(ar, obj)
    f = obj.fields
    f['has_zone'] = ar.u8()
    f['zone'] = ar.read_object() if f['has_zone'] else None
    n = ar.u32()
    if n < 4 or n - 4 > len(ar.data) - ar.pos:
        raise ArchiveError(f'code-barres TypeEdit : bloc de norme de {n} octets à {ar.pos - 4}')
    f['norme_len'] = n
    f['norme'] = ar.raw(n - 4)
    f['data'] = ar.cstring()
    f['var_flag'] = ar.u8()
    f['adv_var'] = ar.u8()
    f['i128'] = ar.u32()
    f['var'] = ar.cstring() if f['var_flag'] or f['adv_var'] else None
    f['d140'] = ar.f64()
    if obj.cls.schema > 1:
        f['b198'] = ar.raw(0x58)
        f['b148'] = ar.raw(0x50)


#: codes-barres TypeEdit : ancien (CObBCode) et ceux de la V15
BARCODES = {'CObBCode': '', 'CObNewBCode1D': '1D', 'CObNewBCode2D': '2D'}


def bcode_text(value) -> str:
    return value.decode('latin-1') if isinstance(value, (bytes, bytearray)) else str(value or '')


def bcode_norm(obj: MfcObject) -> str:
    """Identifiant de la norme (« *DLSOFT*1D*1 »…) en tête du bloc."""
    import re
    m = re.match(rb'[\x20-\x7e]{3,}', obj.fields.get('norme', b'')[4:])
    return m.group(0).decode('ascii') if m else ''


def _cadran_vernier(ar: Archive, schema: int) -> dict:
    """Réglages d'un cadran (CGVernier, MaudeCadran.dll) : en-tête de
    0x70 octets (centre en +0x10), nombres, police, textes, motif des
    graduations (un caractère par graduation, chacune décrite par 48
    octets : type, longueurs…), puis un style de texte (CTxtAttrStyle :
    attributs de caractère, de ligne, de paragraphe). Les chaînes sont en
    ASCII avant le schéma 6, en UTF-16 ensuite. Gardé brut pour la
    réécriture (`raw`)."""
    st = ar.pos
    v = {'has': ar.u32()}
    if v['has']:
        v['head'] = ar.raw(0x70 + 36)
        n = ar.i32()
        v['police'] = ar.raw(max(0, n))
        ar.raw(40)
        n = ar.i32()
        v['texte_d8'] = ar.raw(max(0, n))
        ar.raw(8)
        n = ar.i32()
        v['texte'] = ar.raw(max(0, n))
        n = ar.i32()
        if n > 0:
            v['graduations'] = ar.raw(n if schema < 6 else 2 * n)
            ar.raw(48 * n)
    ar.u32()
    _txtattr_char(ar), _txtattr_line(ar), _txtattr_para(ar)
    v['raw'] = ar.data[st:ar.pos]
    return v


def cadran_text(value: bytes, schema: int) -> str:
    if not value:
        return ''
    if schema >= 6:
        # TypeEdit écrit certains de ces textes avec un nombre de caractères
        # pris pour un nombre d'octets : moitié tronquée, octet impair
        return value[:len(value) // 2 * 2].decode('utf-16-le', 'replace').rstrip('\x00')
    return value.decode('cp1252', 'replace').rstrip('\x00')


def read_cadran(ar: Archive, obj: MfcObject) -> None:
    """CObCadran : cadran ou règle graduée TypeEdit (MaudeCadran.dll) —
    en-tête CObDaoFin, courbe de base et dessin généré (CZone)
    facultatifs, deux couleurs, nom, variable facultative, réglages
    (CGVernier), puis (schéma > 2) deux CPropertyExtend intégrés et
    (schéma > 3, réglages présents) un réel."""
    read_obdao_fin(ar, obj)
    v = obj.cls.schema
    f = obj.fields
    if 1 <= v <= 7:
        for k in ('courbe', 'zone'):
            f['has_' + k] = ar.u32()
            f[k] = ar.read_object() if f['has_' + k] else None
            if f[k] is not None:
                obj.children.append(f[k])
        f['c250'] = ar.u32()
        f['c254'] = ar.u32()
        if v < 7:
            n = f['name_n'] = ar.u32()
            if n:
                f['name'] = ar.raw(4 if v < 2 else n) if v < 6 else ar.raw(2 * n)
                if v >= 6:
                    f['name_extra'] = ar.raw(6 * n)
        else:
            f['name'] = ar.cstring()
        f['has_var'] = ar.u32()
        f['var'] = ar.read_object() if f['has_var'] else None
        f['has_vernier'] = ar.u32()
        f['vernier'] = _cadran_vernier(ar, v) if f['has_vernier'] else None
    if v > 2:
        f['prop_a'] = ar.embedded('CPropertyExtend')
        f['prop_b'] = ar.embedded('CPropertyExtend')
        if v > 3 and (f.get('vernier') or {}).get('has'):
            f['d_f8'] = ar.f64()


def cadran_name(obj: MfcObject) -> str:
    n = obj.fields.get('name')
    if isinstance(n, str):
        return n
    return cadran_text(n or b'', obj.cls.schema)


def read_braille(ar: Archive, obj: MfcObject) -> None:
    """CObBraille : texte braille TypeEdit (MaudeExt.dll) — en-tête
    CObDaoFin, paragraphe (CParagraphe en mode braille) et dessin des
    points (CZone) facultatifs, textes, réglages, style de texte
    (CTxtAttrStyle), position (3 f64), marges… Schémas 1 à 8 : chaînes
    ASCII précédées de leur longueur ; 9 et 10 : CString.

    Les valeurs sont gardées dans l'ordre du fichier (`ops`) pour une
    réécriture à l'identique ; `f[clé]` donne l'indice d'une valeur dans
    `ops` (paragraphe, dessin, texte, position)."""
    read_obdao_fin(ar, obj)
    v = obj.cls.schema
    if not 1 <= v <= 10:
        raise ArchiveError(f'texte braille TypeEdit : schéma {v} inconnu')
    f = obj.fields
    ops = f['ops'] = []

    def put(kind, value, key=None):
        if key:
            f[key] = len(ops)
        ops.append([kind, value])
        return value

    def child(key):
        if put('u32', ar.u32()):
            _add_child(obj, put('obj', ar.read_object(), key))

    def text(key=None):
        if v >= 9:
            put('cstr', ar.cstring(), key)
            return
        n = put('u32', ar.u32())
        if n:
            put('raw', ar.raw(4 if v < 2 else n), key)

    child('par')
    child('zone')
    put('u32', ar.u32())
    text('texte')
    text('texte2')
    for _ in range(4):
        put('u32', ar.u32())
    put('raw', _txtattr_char(ar) + _txtattr_line(ar) + _txtattr_para(ar))
    put('f64', ar.f64(), 'pos_x')
    put('f64', ar.f64(), 'pos_y')
    put('f64', ar.f64())
    for k in ('u32', 'u32', 'u32', 'f64', 'f64'):
        put(k, ar.f64() if k == 'f64' else ar.u32())
    if v >= 9:
        put('cstr', ar.cstring())
        put('f64', ar.f64())
        for _ in range(3):
            put('u32', ar.u32())
        if v == 10:
            put('f64', ar.f64())
            put('u32', ar.u32())
    elif v > 2:
        text()                                     # texte d'affichage
        if v > 3:
            text('police')                         # « NH-Braille » par défaut
            if v > 4:
                put('f64', ar.f64())
            for since in (6, 7, 8):
                if v >= since:
                    put('u32', ar.u32())


def braille_field(obj: MfcObject, key: str):
    i = obj.fields.get(key)
    return None if i is None else obj.fields['ops'][i][1]


def braille_text(obj: MfcObject, key: str = 'texte') -> str:
    t = braille_field(obj, key)
    if isinstance(t, (bytes, bytearray)):
        return t.decode('cp1252', 'replace').rstrip('\x00')
    return t or ''


def read_trou(ar: Archive, obj: MfcObject) -> None:
    """CTrou : trou de perçage = marqueur (centre) + rayon et
    profondeur (2 f64, m)."""
    read_marker(ar, obj)
    obj.fields['rayon'] = ar.f64()
    obj.fields['profondeur'] = ar.f64()


class BrepEnd(ArchiveError):
    """Fin du flux d'un solide 3D (CObBrep) pas encore retrouvée."""

    def __init__(self, start: int, data_pos: int):
        super().__init__(f"solide 3D (CObBrep) à l'octet {start} : fin du flux introuvable")
        self.start, self.data_pos = start, data_pos


def read_brep(ar: Archive, obj: MfcObject) -> None:
    """CObBrep : solide 3D. Après l'en-tête, un entier puis le
    flux binaire du noyau SMLib (IwBrepData::ReadPartFromDB), sans longueur
    annoncée : sa fin est retrouvée par `parse` (positions candidates
    validées par une relecture complète) et ses octets gardés tels quels."""
    read_obdao_fin(ar, obj)
    obj.fields['brep_flag'] = ar.u32()
    end = getattr(ar, 'brep_ends', {}).get(obj.start)
    if end is None:
        raise BrepEnd(obj.start, ar.pos)
    obj.fields['brep_raw'] = ar.raw(end - ar.pos)


#: drapeaux d'en-tête CObDao « modernes », tels qu'écrits (bit 0 compris)
_FLAG_BYTES = tuple(struct.pack('<I', f | b) for f in _MODERN for b in (0, 1))


def _plausible_header(data: bytes, p: int) -> bool:
    """Un en-tête CObDao commence en `p` : boîte (6 f64, m) vide ou
    plausible, drapeaux modernes, version raisonnable."""
    if p < 0 or p + 56 > len(data):
        return False
    bb = struct.unpack_from('<6d', data, p)
    if all(abs(v) >= 1e99 for v in bb):
        if not (bb[0] > 0 > bb[3]):
            return False
    elif not (all(math.isfinite(v) and abs(v) < 100 for v in bb)
              and bb[0] <= bb[3] and bb[1] <= bb[4] and bb[2] <= bb[5]):
        return False
    return 1 <= struct.unpack_from('<I', data, p + 52)[0] <= 30


def brep_candidates(data: bytes, start: int, table: list) -> list[int]:
    """Fins possibles du flux d'un CObBrep commencé en `start` : début d'un
    objet étiqueté d'une classe connue (déjà vue ou nouvelle) ou d'un objet
    fixe sans étiquette (repère d'un calque, support…)."""
    names = [(n, n.encode('ascii')) for n in READERS]
    out = set()
    for fb in _FLAG_BYTES:
        i = data.find(fb, start + 48)
        while i >= 0:
            p = i - 48
            if _plausible_header(data, p):
                out.add(p)
                tag = struct.unpack_from('<H', data, p - 2)[0] if p >= start + 2 else 0
                if tag & 0x8000 and tag != 0xFFFF:
                    idx = tag & 0x7FFF
                    if idx < len(table) and isinstance(table[idx], MfcClass) and table[idx].name in READERS:
                        out.add(p - 2)
                for _n, nb in names:
                    q = p - 6 - len(nb)
                    if q >= start and data[q:q + 2] == b'\xff\xff' and data[q + 6:p] == nb \
                            and struct.unpack_from('<H', data, q + 4)[0] == len(nb):
                        out.add(q)
            i = data.find(fb, i + 1)
    return sorted(out)


def read_centerline(ar: Archive, obj: MfcObject) -> None:
    """CCenterLine : axe de construction, deux points 3D."""
    read_obdao_fin(ar, obj)
    obj.fields['p'] = ar.f64s(6)
    obj.fields['ints'] = [ar.u32() for _ in range(3)]


# --- objets des GVT : relief (Maude3D) et métafichier --------------------------------

def _zmap(ar: Archive) -> dict:
    """Carte de valeurs : origine (2 f64), réel, pas X et Y (f64),
    largeur, hauteur (i32), puis largeur × hauteur float32."""
    z = {'origin': ar.f64s(2), 'f': ar.f64(), 'step': ar.f64s(2)}
    w, h = ar.i32(), ar.i32()
    if w < 0 or h < 0 or w * h > 200_000_000:
        raise ArchiveError(f'carte de hauteurs aberrante {w} × {h} à {ar.pos}')
    z['w'], z['h'] = w, h
    z['data'] = ar.raw(4 * w * h)
    return z


def read_vbitmap(ar: Archive, obj: MfcObject) -> None:
    """CVbitmap : relief en carte de hauteurs."""
    read_obdao_fin(ar, obj)
    f = obj.fields
    v = obj.cls.schema
    f['map'] = _zmap(ar)
    if v > 1:
        hv, n = ar.u32(), ar.u32()
        f['histo'] = {'version': hv, 'n': n}
        if n:
            raise ArchiveError(f'relief avec historique d\'édition ({n} commandes) : pas encore lu par VectorDrive')
        if hv > 2:
            f['histo']['current'] = ar.u32()
        if v >= 3:
            f['b3c8'] = ar.u8()
        if v >= 4:
            f['b3c9'] = ar.u8()
        if v >= 5:
            f['has_map2'] = ar.u8()
            if f['has_map2']:
                f['map2'] = _zmap(ar)
            if v == 6:
                f['guid6'] = ar.raw(16)


def heightmap_dib(w: int, h: int, data: bytes) -> bytes:
    """Carte de hauteurs (float32, 1e30 = sans donnée) → DIB 8 bits en
    niveaux de gris (plus haut = plus clair), lignes de bas en haut comme la
    carte."""
    import numpy as np
    a = np.frombuffer(data, '<f4').reshape(h, w).astype(float)
    valid = a < 1e29
    if valid.any():
        lo, hi = a[valid].min(), a[valid].max()
        g = np.where(valid, (a - lo) / (hi - lo or 1.0) * 255, 255)
    else:
        g = np.full(a.shape, 255.0)
    g = g.astype(np.uint8)
    stride = (w + 3) & ~3
    rows = np.zeros((h, stride), np.uint8)
    rows[:, :w] = g
    pal = bytes(b for i in range(256) for b in (i, i, i, 0))
    header = struct.pack('<IiiHHIIiiII', 40, w, h, 1, 8, 0, stride * h, 2835, 2835, 256, 0)
    return header + pal + rows.tobytes()


def read_metaobj(ar: Archive, obj: MfcObject) -> None:
    """CMetaObj : métafichier Windows (EMF) dans un cadre."""
    read_obdao_fin(ar, obj)
    f = obj.fields
    f['meta_version'] = ar.u32()
    f['geom'] = ar.f64s(5)
    n = ar.u32()
    f['emf'] = ar.raw(n)


#: objets lus mais sans dessin 2D : gardés tels quels, non affichés
HIDDEN_OBJECTS = {'CObBrep': 'solide 3D', 'CMarker': 'point de construction',
                  'CCenterLine': 'axe de construction'}

#: cotes TypeEdit ; rayon et diamètre dérivent de la cote
#: latérale sans Serialize propre : même enregistrement
COTATIONS = ('CCotationLineaire', 'CCotationHorizontale', 'CCotationVerticale', 'CCotationLaterale',
             'CCotationAngle', 'CCotationRadial', 'CCotationDiameter')

READERS = {
    'CTravail': read_travail,
    'CCalque': read_calque,
    'CZone': read_zone,
    'CCourbe': read_courbe,
    'CContour': read_contour,
    'CPropertyExtend': read_property_extend,
    'CObList': read_oblist,
    'CVnImage': read_vnimage,
    'CObDaoCtn': read_obdao_ctn,
    'CParagraphe': read_paragraphe,
    'CMarker': read_marker,
    'CObBCode': read_bcode,
    'CObNewBCode1D': read_new_bcode,
    'CObNewBCode2D': read_new_bcode,
    'CObCadran': read_cadran,
    'CObBraille': read_braille,
    'CTrou': read_trou,
    'CCenterLine': read_centerline,
    'CObBrep': read_brep,
    'CVbitmap': read_vbitmap,
    'CMetaObj': read_metaobj,
    **{name: read_cotation for name in COTATIONS},
}


# --- conversion en géométrie ---------------------------------------------------

_POINT_DTYPE = None


def _finite_points(raw: bytes, n: int) -> bool:
    """Toutes les coordonnées (x, y, z, w) des points sont-elles finies ?
    (numpy sur les octets : un contour corrompu a des NaN.)"""
    global _POINT_DTYPE
    if n == 0:
        return True
    import numpy as np
    if _POINT_DTYPE is None:
        _POINT_DTYPE = np.dtype([('c', '<f8', 4), ('f', '<u4')])
    return bool(np.isfinite(np.frombuffer(raw, _POINT_DTYPE, count=n)['c']).all())


def points_finite(obj_fields: dict) -> bool:
    f = obj_fields.get('finite')
    if f is not None:
        return f
    return all(math.isfinite(v) for p in obj_fields.get('points', []) for v in p[:4])


def contour_segments(points, closed: bool) -> list[Segment]:
    """Points TypeEdit (homogènes, drapeau bit 0 = nœud) → segments en mm."""
    n = len(points)
    if n < 2:
        return []
    k = M_TO_MM
    if closed:
        # le premier nœud est le dernier point marqué : on fait tourner la
        # liste pour qu'elle commence par lui
        last_node = -1
        for i in range(n - 1, -1, -1):
            if points[i][4] & 1:
                last_node = i
                break
        if last_node < 0:
            return []
        seq = list(points[last_node:]) + list(points[:last_node])
        seq.append(seq[0])
    else:
        seq = points
    # coordonnées cartésiennes (mm) de tous les points d'un coup
    xy = [((x / w * k, y / w * k) if (w > 1e-15 or w < -1e-15) else (x * k, y * k)) for x, y, _z, w, _f in seq]
    segs: list[Segment] = []
    append = segs.append
    start = xy[0]
    c0 = -1                                           # indice du 1er point de contrôle en attente
    nc = 0
    for j in range(1, len(seq)):
        if not seq[j][4] & 1:
            if nc == 0:
                c0 = j
            nc += 1
            continue
        end = xy[j]
        if nc == 0:
            dx, dy = end[0] - start[0], end[1] - start[1]
            if dx * dx + dy * dy > 1e-18:
                append(Line(start, end))
        elif nc == 1:
            w = seq[c0][3]
            append(Conic(start, xy[c0], end, w if (w > 1e-15 or w < -1e-15) else 1.0))
        elif nc == 2:
            append(Cubic(start, xy[c0], xy[c0 + 1], end))
        else:
            # degré > 3 : rare ; on passe par les points de contrôle
            prev = start
            for q in range(c0, c0 + nc):
                append(Line(prev, xy[q]))
                prev = xy[q]
            append(Line(prev, end))
        start = end
        nc = 0
    return segs


def transformed_contour(obj: MfcObject, m) -> MfcObject:
    """Copie d'un CContour transformé par l'affine `m` (en mm) : points
    homogènes (x·w, y·w) et boîte. Sert aux contours d'un seul point, que
    VectorDrive ne dessine pas mais que la réécriture du VND garde."""
    import copy
    c = copy.copy(obj)
    c.fields = dict(obj.fields)
    e, f = m.e * MM_TO_M, m.f * MM_TO_M
    pts = [(m.a * x + m.c * y + e * w, m.b * x + m.d * y + f * w, z, w, fl)
           for x, y, z, w, fl in obj.fields.get('points', [])]
    c.fields['points'] = pts
    bb = obj.fields.get('bbox')
    if bb is not None and bb[0] < 1e99 and pts:
        xy = [(x / w, y / w) if abs(w) > 1e-15 else (x, y) for x, y, _z, w, _f in pts]
        xs, ys = [p[0] for p in xy], [p[1] for p in xy]
        c.fields['bbox'] = (min(xs), min(ys), bb[2], max(xs), max(ys), bb[5])
    return c


#: Propriétés d'un contour gardées pour la réécriture (les textes et les zones qu'elles peuvent porter sont à part)
CONTOUR_PROPS = ('f10', 'f0c', 'color', 'fill_color', 'f20_2c', 'ints', 'f40', 'f44', 'f48', 'doubles', 'f80_98')


class ContourProps:
    """Propriétés des contours dessinés d'une courbe, dans l'ordre, pour la réécriture du VND. Une classe à part : elles
    n'ont rien à faire dans un dessin natif (`native._jsonable` ne garde que ce qui passe en JSON)."""
    __slots__ = ('rows',)

    def __init__(self, rows: list):
        self.rows = rows


def _contour_row(ext: dict, pool: dict) -> dict:
    """Les propriétés d'un contour ; peu de valeurs différentes sur tout un fichier : un seul dictionnaire pour chacune."""
    row = {k: ext[k] for k in CONTOUR_PROPS if k in ext}
    return pool.setdefault(repr(row), row)


def _to_items(obj: MfcObject, report: list[str], ctx: dict | None = None) -> list:
    """Arbre MFC → objets VectorDrive. `ctx['fonts']` : table des polices
    du fichier (symboles)."""
    ctx = ctx or {}
    name = obj.cls.name
    if name == 'CParagraphe':
        text, font, height, outline = layout_paragraph(obj, ctx.get('fonts', []))
        t = Text(text=text, font=font, size=height, outline=outline, name=obj.fields.get('name', ''))
        t.matrix = paragraph_matrix(obj, t)
        t.extra['vnd'] = {'guid': obj.fields.get('guid'), 'wraps': 0}
        t.extra['vnd_obj'] = obj           # objet d'origine, pour la réécriture
        if not outline and text.strip():
            report.append(f'texte « {text[:20]} » : glyphes introuvables dans « {font} »')
        from ..core import fonts as _F
        if text.strip() and not _F.is_available(font):
            report.append(f'police « {font} » absente du poste : textes dessinés avec une police de remplacement')
        return [t]
    if name == 'CObList':
        items = []
        for ch in obj.children:
            items.extend(_to_items(ch, report, ctx))
        return items
    if name == 'CCourbe':
        contours = []
        empties = []                       # contours d'un seul point : gardés pour la réécriture
        color = None
        rows = []
        pool = ctx.setdefault('contour_props', {}) if isinstance(ctx, dict) else {}
        for i, ch in enumerate(obj.children):
            if ch.cls.name != 'CContour':
                report.append(f'objet {ch.cls.name} ignoré dans une courbe')
                continue
            t = ch.fields.get('type', 0)
            pts = ch.fields.get('points', [])
            if not points_finite(ch.fields):
                # contour corrompu dans la source (coordonnées NaN) : pas
                # dessiné, mais gardé tel quel pour la réécriture
                report.append('contour corrompu (coordonnées invalides) ignoré dans une courbe')
                empties.append((i, ch))
                continue
            segs = contour_segments(pts, closed=t != 0)
            ext = ch.fields.get('ext') or {}
            if segs:
                contours.append(Contour(segs, closed=t != 0))
                rows.append(_contour_row(ext, pool))
            else:
                empties.append((i, ch))
            if color is None and 'color' in ext:
                color = ext['color']
        sh = Shape(path=Path(contours), name=obj.fields.get('name', ''))
        sh.extra['vnd'] = {'guid': obj.fields.get('guid'), 'color': color, 'wraps': 0,
                           'trailer': obj.fields.get('trailer'), 'props': ContourProps(rows)}
        # la couleur que TypeEdit montre, relevée le 06/11 : la 3ᵉ valeur de la fin de courbe, pas celle des contours ni l'outil
        trailer = obj.fields.get('trailer') or b''
        if len(trailer) >= 12:
            sh.extra['te_color'] = [colorref_hex(struct.unpack_from('<I', trailer, 8)[0]), 0]
        if empties:
            sh.extra['vnd']['empty_contours'] = empties
            sh.extra['vnd']['drawn_contours'] = len(contours)
        return [sh]
    if name == 'CVnImage':
        x0, y0, x1, y1 = (v * M_TO_MM for v in obj.fields['geom'][:4])
        im = Image(data=obj.fields['bitmap'], fmt='dib',
                   matrix=Affine(x1 - x0, 0, 0, y1 - y0, x0, y0), name=obj.fields.get('name', ''))
        im.extra['vnd'] = {'guid': obj.fields.get('guid'), 'f128': obj.fields.get('f128', 0),
                           'geom5': obj.fields['geom'][4], 'wraps': 0}
        return [im]
    if name == 'CVbitmap':
        m = obj.fields['map']
        ox, oy = (v * M_TO_MM for v in m['origin'])
        W, H = (v * M_TO_MM for v in m['step'])            # taille totale de la carte
        im = Image(data=heightmap_dib(m['w'], m['h'], m['data']), fmt='dib',
                   matrix=Affine(W, 0, 0, -H, ox, oy + H), name='Relief')
        im.extra['vnd'] = {'guid': obj.fields.get('guid'), 'wraps': 0}
        report.append('relief (carte de hauteurs) affiché en niveaux de gris, non modifiable')
        return [im]
    if name == 'CMetaObj':
        x0, y0, x1, y1 = (v * M_TO_MM for v in obj.fields['geom'][:4])
        frame = Shape(path=Path([Contour([Line((x0, y0), (x1, y0)), Line((x1, y0), (x1, y1)),
                                          Line((x1, y1), (x0, y1)), Line((x0, y1), (x0, y0))], True)]),
                      name='Métafichier EMF')
        report.append('métafichier Windows (EMF) : seul son cadre est affiché')
        return [frame]
    if name in ('CZone',):
        items = []
        for ch in obj.children:
            items.extend(_to_items(ch, report, ctx))
        if len(items) == 1:
            # zone à un seul objet : on compte les enveloppes successives
            vx = items[0].extra.setdefault('vnd', {})
            vx['wraps'] = vx.get('wraps', 0) + 1
            if obj.fields.get('name'):                 # son nom, remis à la réécriture
                vx.setdefault('zone_names', {})[vx['wraps']] = obj.fields['name']
            return items
        g = Group(children=items, name=obj.fields.get('name', ''))
        g.extra['vnd'] = {'guid': obj.fields.get('guid'), 'wraps': 0}
        if not items:
            g.extra['vnd']['empty_zone'] = True        # zone vide : réécrite telle quelle
        return [g]
    if name == 'CContour':
        t = obj.fields.get('type', 0)
        segs = contour_segments(obj.fields.get('points', []), closed=t != 0)
        return [Shape(path=Path([Contour(segs, closed=t != 0)]))] if segs else []
    if name in BARCODES:
        data = bcode_text(obj.fields.get('data'))
        zone = obj.fields.get('zone')
        parts = _to_items(zone, report, ctx) if zone is not None else []
        if len(parts) == 1 and isinstance(parts[0], Group):
            parts = parts[0].children
        if not parts:
            report.append(f'code-barres « {data} » sans dessin enregistré : gardé tel quel')
        g = Group(children=parts, name=f'Code-barres : {data}')
        g.extra['vnd'] = {'guid': obj.fields.get('guid'), 'wraps': 0}
        g.extra['vnd_obj'] = obj               # code d'origine, réécrit s'il est inchangé
        g.extra['typeedit_barcode'] = {'donnee': data, 'norme': bcode_norm(obj), 'famille': BARCODES[name],
                                       'variable': bcode_text(obj.fields.get('var')) if obj.fields.get('var') else ''}
        return [g]
    if name == 'CObBraille':
        label = braille_text(obj)
        zone = braille_field(obj, 'zone')
        parts = _to_items(zone, report, ctx) if zone is not None else []
        if len(parts) == 1 and isinstance(parts[0], Group):
            parts = parts[0].children
        if not parts:
            report.append(f'braille « {label[:20]} » sans dessin enregistré : gardé tel quel')
        g = Group(children=parts, name=f'Braille : {label}' if label else 'Braille')
        g.extra['vnd'] = {'guid': obj.fields.get('guid'), 'wraps': 0}
        g.extra['vnd_obj'] = obj               # braille d'origine, réécrit s'il est inchangé
        g.extra['typeedit_braille'] = {'texte': label, 'police': braille_text(obj, 'police')}
        return [g]
    if name == 'CObCadran':
        label = cadran_name(obj)
        zone = obj.fields.get('zone')
        parts = _to_items(zone, report, ctx) if zone is not None else []
        if len(parts) == 1 and isinstance(parts[0], Group):
            parts = parts[0].children
        if not parts:
            report.append('cadran TypeEdit sans dessin enregistré : gardé tel quel')
        g = Group(children=parts, name=f'Cadran : {label}' if label else 'Cadran')
        g.extra['vnd'] = {'guid': obj.fields.get('guid'), 'wraps': 0}
        g.extra['vnd_obj'] = obj               # cadran d'origine, réécrit s'il est inchangé
        ver = obj.fields.get('vernier') or {}
        g.extra['typeedit_cadran'] = {
            'nom': label,
            'graduations': cadran_text(ver.get('graduations', b''), obj.cls.schema),
            'police': cadran_text(ver.get('police', b''), obj.cls.schema),
            'texte': cadran_text(ver.get('texte', b''), obj.cls.schema)}
        return [g]
    if name in COTATIONS:
        # dessin de la cote tel que TypeEdit l'a calculé : ligne de cote,
        # texte, lignes d'attache, flèches
        label = cotation_text(obj)
        zone = obj.fields.get('zone')
        if zone is None:
            report.append(f'cote « {label} » sans dessin enregistré : ignorée')
            return []
        parts = _to_items(zone, report, ctx)
        if len(parts) == 1 and isinstance(parts[0], Group):
            parts = parts[0].children
        if not all(math.isfinite(v) for v in obj.fields['pts'][:6]) or \
                not all(math.isfinite(v) for it in parts for v in (it.bbox() or ())):
            # cote abîmée dans la source (points NaN) : rien à dessiner, mais
            # l'objet d'origine est gardé pour la réécriture
            report.append(f'cote « {label} » aux coordonnées invalides : non affichée, gardée telle quelle')
            parts = []
        g = Group(children=parts, name='Cote')
        g.extra['vnd'] = {'guid': obj.fields.get('guid'), 'wraps': 0}
        g.extra['vnd_obj'] = obj           # cote d'origine, réécrite si inchangée
        g.extra['cotation'] = {'classe': name, 'texte': label,
                               'points_mm': [round(v * M_TO_MM, 6) for v in obj.fields['pts'][:6]]}
        return [g]
    if name == 'CTrou':
        # trou de perçage : cercle à son diamètre, profondeur conservée
        x, y = (v * M_TO_MM for v in obj.fields['pos'][:2])
        r = obj.fields['rayon'] * M_TO_MM
        if r <= 0:
            report.append('trou de rayon nul : dessiné en cercle de 0,5 mm')
            r = 0.5
        sh = Shape(path=Path([circle_contour((x, y), r)]), name=obj.fields.get('name', '') or 'Trou')
        sh.extra['vnd'] = {'guid': obj.fields.get('guid'), 'wraps': 0}
        sh.extra['vnd_obj'] = obj           # trou d'origine, réécrit s'il est intact
        sh.extra['trou'] = {'profondeur': round(obj.fields['profondeur'] * M_TO_MM, 9),
                            'ints': list(obj.fields['ints'])}
        return [sh]
    if name in HIDDEN_OBJECTS:
        # sans dessin 2D (solide 3D, point ou axe de construction) : rien à
        # l'écran, l'objet d'origine est gardé pour la réécriture du VND
        label = HIDDEN_OBJECTS[name]
        report.append(f'{label} non affiché, gardé tel quel pour la réécriture du VND')
        g = Group(children=[], name=label[0].upper() + label[1:])
        g.extra['vnd'] = {'guid': obj.fields.get('guid'), 'wraps': 0}
        g.extra['vnd_obj'] = obj
        return [g]
    report.append(f'objet {name} non converti')
    return []


def summarize_report(report: list[str]) -> list[str]:
    """Remarques identiques regroupées (« … (× 12) »), ordre conservé."""
    from collections import Counter
    n = Counter(report)
    out = []
    for r in report:
        if r in n:
            out.append(r if n[r] == 1 else f'{r} (× {n[r]})')
            del n[r]
    return out


def archive_start(data: bytes) -> int:
    """Début de l'archive MFC : en-tête[1] + 2 dans tous les fichiers vus
    (les deux octets précédents terminent l'aperçu)."""
    start = struct.unpack_from('<I', data, 4)[0]
    if data[start + 2:start + 4] == b'\xff\xff':
        return start + 2                         # VND
    if data[start - 2:start] == b'\xff\xff':
        return start - 2                         # GVT : en-tête[1] désigne le schéma du CTravail
    return data.find(b'\xff\xff', start)


def font_table(data: bytes, start: int | None = None) -> tuple[int, list[str]]:
    """Table des polices des textes, juste avant l'archive (GVT, VND et
    symboles) : u32 n puis n noms ANSI de 64 octets complétés de zéros ;
    les caractères des paragraphes y renvoient par leur indice. Rend
    (position du compteur, noms). Dans un VND, la table suit l'aperçu
    (compteur à l'octet 10 854 des fichiers TypeEdit V15) ; sans texte,
    n = 0."""
    a = archive_start(data) if start is None else start
    for n in range(64, 0, -1):
        p = a - 4 - 64 * n
        if p < 12 or struct.unpack_from('<I', data, p)[0] != n:
            continue
        names = []
        for k in range(n):
            name = data[p + 4 + 64 * k:p + 4 + 64 * (k + 1)].split(b'\0')[0]
            if not name or any(c < 32 for c in name):
                break
            names.append(name.decode('cp1252', 'replace'))
        else:
            return p, names
    return a - 4, []


#: relectures au plus pour retrouver la fin des solides 3D d'un fichier
BREP_MAX_TRIES = 60


def _parse_once(data: bytes, pos: int, ends: dict):
    ar = Archive(data, pos, READERS)
    ar.brep_ends = ends
    try:
        return ar.read_object(), ar, None
    except (ArchiveError, struct.error) as ex:
        return None, ar, ex


def _parse_breps(data: bytes, pos: int):
    """Lecture de l'archive. Chaque solide 3D (CObBrep) arrête la lecture
    à la fin inconnue de son flux : on essaie ses fins candidates dans
    l'ordre. Une fin tient si la relecture va au bout ou bute sur un solide
    plus loin ; sinon on passe à la suivante, et quand un solide n'en a
    plus, on revient sur le précédent. À défaut, la lecture allée le plus
    loin est rendue (partielle)."""
    ends: dict[int, int] = {}
    stack: list[list] = []                       # [début, candidats, indice]
    best = (-1, {})
    for _ in range(BREP_MAX_TRIES + 1):
        root, ar, ex = _parse_once(data, pos, ends)
        if ex is None:
            return root, ar, None
        if ar.pos > best[0]:
            best = (ar.pos, dict(ends))
        if isinstance(ex, BrepEnd) and (not stack or ex.start > ends[stack[-1][0]]):
            stack.append([ex.start, brep_candidates(data, ex.data_pos, ar.table), -1])
        while stack:                             # fin suivante du solide le plus récent
            top = stack[-1]
            top[2] += 1
            if top[2] < len(top[1]):
                ends[top[0]] = top[1][top[2]]
                break
            ends.pop(top[0], None)
            stack.pop()
        if not stack:
            break
    root, ar, ex = _parse_once(data, pos, best[1])
    return root, ar, ex


def parse(data: bytes, *, partial: bool = False) -> tuple[MfcObject, Archive]:
    """Racine CTravail et archive. `partial` : si un objet ne se lit pas
    (classe inconnue…), rend ce qui précède — objets en cours rattachés à
    leurs parents, erreur dans `root.fields['partial_error']`."""
    if len(data) < 12:
        raise VndError('fichier trop court')
    magic, start, _unk = struct.unpack_from('<3I', data, 0)
    if magic not in (MAGIC, GVT_MAGIC):
        raise VndError(f'signature inconnue {magic:#x} (attendu {MAGIC:#x} ou {GVT_MAGIC:#x})')
    pos = archive_start(data)
    if pos < 0:
        raise VndError('archive MFC introuvable')
    root, ar, ex = _parse_breps(data, pos)
    if ex is not None:
        if not partial or not ar.stack or ar.stack[0].cls.name != 'CTravail':
            raise ex
        for parent, child in zip(ar.stack, ar.stack[1:]):
            if not any(c is child for c in parent.children):
                parent.children.append(child)
        root = ar.stack[0]
        root.fields['partial_error'] = str(ex)
        return root, ar
    if root is None or root.cls.name != 'CTravail':
        raise VndError(f'racine inattendue : {root!r}')
    return root, ar


def calque_tool(calque: MfcObject) -> int:
    """Numéro d'outil du calque : 3ᵉ entier des attributs (TypeEdit : un
    calque = un outil = une couleur)."""
    attrs = calque.fields.get('attrs', b'')
    return struct.unpack_from('<I', attrs, 8)[0] if len(attrs) >= 12 else 0


def _set_tool(items, tool: int) -> None:
    for it in items:
        it.tool = tool
        own = it.extra.get('te_color')
        if own:
            own[1] = tool
        vx = it.extra.get('vnd')
        if isinstance(vx, dict) and 'trailer' in vx:
            vx['tool'] = tool
        if isinstance(it, Group):
            _set_tool(it.children, tool)


def read(path: str | pathlib.Path) -> Document:
    data = pathlib.Path(path).read_bytes()
    root, ar = parse(data, partial=True)
    partial = root.fields.get('partial_error')
    gvt = struct.unpack_from('<I', data, 0)[0] == GVT_MAGIC
    doc = Document(layers=[], source_path=str(path), source_format='gvt' if gvt else 'vnd')
    fonts = font_table(data)[1]
    ctx = {'fonts': fonts}
    doc.extra['vnd_fonts'] = fonts
    for calque in root.children:
        if calque.cls.name != 'CCalque':
            doc.report.append(f'{calque.cls.name} au niveau des calques, ignoré')
            continue
        layer = Layer(name=calque.fields.get('layer_name') or calque.fields.get('name') or 'Plan')
        tool = calque_tool(calque)
        layer.tool = tool
        layer.extra['vnd'] = {'guid': calque.fields.get('guid'), 'tool': tool}
        for zone in calque.children:
            layer.items.extend(_to_items(zone, doc.report, ctx))
        _set_tool(layer.items, tool)
        doc.layers.append(layer)
    # fin de document : plaque, outils, machine
    tail = None
    if partial:
        doc.extra['vnd_partial'] = str(partial)
        doc.report.append(f'lecture interrompue ({partial}) : dessin partiel, '
                          'plaque et réglages TypeEdit non lus, réécriture à l\'identique impossible')
    else:
        try:
            tail = parse_tail_head(ar)
        except (ArchiveError, struct.error) as ex:
            doc.report.append(f'réglages TypeEdit non lus : {ex}')
    if tail:
        x0, y0, z0, x1, y1, z1 = (v * M_TO_MM for v in tail['support_bbox'])
        doc.plate = Plate(width=x1 - x0, height=y1 - y0, x=x0, y=y0, thickness=z1 - z0)
        if tail['tools']:
            doc.tools = [Tool(i, colorref_hex(c), n) for i, (c, n) in enumerate(tail['tools'])]
        doc.extra['vnd_machine'] = {'nom': tail['machine'], 'postpro': tail['postpro'],
                                    'courses_mm': [v * M_TO_MM for v in tail['travel']]}
        if tail.get('variables'):
            doc.extra['typeedit_variables'] = tail['variables']     # variables du document (séries…)
    else:
        bb = root.fields.get('bbox')
        if bb:
            doc.extra['page_mm'] = tuple(v * M_TO_MM for v in bb)
    doc.report = summarize_report(doc.report)
    if gvt or partial:
        # un GVT ne sert pas de base binaire à un VND (en-tête et versions
        # d'objets différents) : textes et cotes seront écrits comme dessin
        from ..core.document import drop_source_object

        def drop(items):
            for it in items:
                drop_source_object(it)
                drop(getattr(it, 'children', ()))
        for L in doc.layers:
            drop(L.items)
        return doc
    # pour la réécriture : le fichier source, et la signature de sa structure
    doc.extra['vnd_source'] = data
    doc.extra['vnd_signature'] = structure_signature(root)
    return doc


def structure_signature(root: MfcObject) -> list[str]:
    """Suite des classes des objets du dessin, dans l'ordre d'écriture :
    deux documents de même signature allouent les mêmes indices MFC."""
    sig: list[str] = []

    def walk(o):
        if o is None:
            sig.append('-')
            return
        sig.append(o.cls.name)
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
    return sig


#: classes jamais gardées comme objet d'origine d'un groupe (les cotes, codes, braille, cadrans et objets cachés le sont)
_NOT_GROUP_SOURCES = ('CParagraphe', 'CTrou', 'CCourbe', 'CContour', 'CZone', 'CCalque', 'CObList', 'CPropertyExtend',
                      'CVnImage', 'CTravail')


def _source_kind_ok(item, obj: MfcObject) -> bool:
    """L'objet d'origine `obj` est bien de la sorte que la lecture donne à `item`."""
    name = obj.cls.name
    if isinstance(item, Text):
        return name == 'CParagraphe'
    if isinstance(item, Shape):
        return name == 'CTrou'
    if isinstance(item, Group):
        return name not in _NOT_GROUP_SOURCES
    return False


def relink(doc: Document, data: bytes) -> int | None:
    """Dessin relu d'un .vdz, d'une session ou d'une récupération, avec le VND dont il vient (`data`) : ce que le JSON n'a
    pas pu garder est repris dans `data` par GUID. Les objets TypeEdit d'origine (textes, cotes, codes, trous…) des seuls
    objets qui les avaient encore à l'enregistrement (clé `vnd_obj` restée à None) ; sans objet de ce GUID, ou d'une autre
    sorte, l'objet est écrit comme dessin, comme avant. Pour les courbes : leur fin, les propriétés de leurs contours et
    leurs contours d'un seul point. Rend le nombre d'objets repris ; None si `data` n'est pas un VND lisible en entier
    (rien n'est changé)."""
    from ..core.document import drop_source_object
    try:
        root, _ar = parse(data)
    except Exception:                                    # noqa: BLE001 — fichier abîmé : on garde le dessin tel quel
        return None
    found: dict = {}
    twice: set = set()
    seen: set = set()
    stack = [root]
    while stack:
        o = stack.pop()
        if id(o) in seen:
            continue
        seen.add(id(o))
        g = o.fields.get('guid')
        if g:
            if g in found and found[g] is not o:
                twice.add(g)                             # GUID en double : on ne devine pas lequel
            found[g] = o
        if o.cls.name == 'CCourbe':
            continue                                     # ses contours n'ont pas d'objet à reprendre
        stack.extend(o.children)
        for v in o.fields.values():
            if isinstance(v, MfcObject):
                stack.append(v)
            elif isinstance(v, (list, tuple)) and v and isinstance(v[0], MfcObject):
                stack.extend(x for x in v if isinstance(x, MfcObject))
    ctx: dict = {'contour_props': {}}
    n = 0

    def fix(items):
        nonlocal n
        for it in items:
            x = it.extra if isinstance(it.extra, dict) else {}
            v = x.get('vnd') if isinstance(x.get('vnd'), dict) else {}
            g = v.get('guid')
            obj = found.get(g) if g and g not in twice else None
            if 'vnd_obj' in x and x['vnd_obj'] is None:
                if obj is not None and _source_kind_ok(it, obj):
                    x['vnd_obj'] = obj
                    n += 1
                else:
                    drop_source_object(it)
            if isinstance(it, Shape) and 'props' in v and v['props'] is None and obj is not None \
                    and obj.cls.name == 'CCourbe':
                back = _to_items(obj, [], ctx)           # la courbe telle que la lecture la donne
                bv = back[0].extra.get('vnd') if back else None
                if isinstance(bv, dict):
                    for k in ('trailer', 'props', 'empty_contours', 'drawn_contours'):
                        if k in bv:
                            v[k] = bv[k]
                    n += 1
            fix(getattr(it, 'children', ()) or ())
    for L in doc.layers:
        fix(L.items)
    return n
