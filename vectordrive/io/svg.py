"""SVG : lecture et écriture, courbes conservées.

Trois pièges classiques (déjà rencontrés dans TauDrive) :

* l'axe Y du SVG descend, celui du dessin monte : on retourne ;
* l'unité vient du couple `width`/`height` + `viewBox` ; sans unité
  physique, l'unité utilisateur est le pixel CSS (1/96 de pouce) ;
* l'arc elliptique `A` est donné par ses extrémités : on retrouve le centre
  et on le rend en coniques exactes.
"""
from __future__ import annotations

import math
import pathlib
import re
import xml.etree.ElementTree as ET

from ..core.document import Document, Group, Layer, Shape, Text
from ..core.geom import (Affine, Conic, Contour, Cubic, Line, Path, PathBuilder,
                         arc_conics, dist)

SVG_NS = '{http://www.w3.org/2000/svg}'
XLINK = '{http://www.w3.org/1999/xlink}href'
UNIT_MM = {'mm': 1.0, 'cm': 10.0, 'in': 25.4, 'pt': 25.4 / 72, 'pc': 25.4 / 6,
           'px': 25.4 / 96, '': 25.4 / 96, 'm': 1000.0, 'q': 0.25}

_NUM = re.compile(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?')


class SvgError(ValueError):
    pass


def _length_mm(text: str | None, default: float | None = None) -> float | None:
    if not text:
        return default
    m = re.fullmatch(r'\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*([a-zA-Z%]*)\s*', text)
    if not m:
        return default
    unit = m.group(2).lower()
    if unit == '%':
        return default
    return float(m.group(1)) * UNIT_MM.get(unit, 25.4 / 96)


def parse_transform(text: str | None) -> Affine:
    m = Affine()
    if not text:
        return m
    for name, args in re.findall(r'(\w+)\s*\(([^)]*)\)', text):
        v = [float(x) for x in _NUM.findall(args)]
        if name == 'matrix' and len(v) == 6:
            t = Affine(*v)
        elif name == 'translate':
            t = Affine.translation(v[0], v[1] if len(v) > 1 else 0.0)
        elif name == 'scale':
            t = Affine.scaling(v[0], v[1] if len(v) > 1 else v[0])
        elif name == 'rotate':
            t = Affine.rotation(v[0], (v[1], v[2]) if len(v) > 2 else (0.0, 0.0))
        elif name == 'skewX':
            t = Affine(1, 0, math.tan(math.radians(v[0])), 1, 0, 0)
        elif name == 'skewY':
            t = Affine(1, math.tan(math.radians(v[0])), 0, 1, 0, 0)
        else:
            continue
        m = m @ t
    return m


def _tokens(d: str):
    i, n = 0, len(d)
    while i < n:
        c = d[i]
        if c.isalpha() and c not in 'eE':
            yield c
            i += 1
        elif c in ' ,\t\r\n':
            i += 1
        else:
            m = _NUM.match(d, i)
            if not m:
                raise SvgError(f'chemin illisible près de « {d[i:i + 20]} »')
            yield float(m.group())
            i = m.end()


def _arc_flags(d: str):
    """Les drapeaux d'arc peuvent être collés (« a5 5 0 011 1 »). On
    re-découpe le texte des commandes A/a pour isoler chaque drapeau."""
    def fix(m):
        cmd, body = m.group(1), m.group(2)
        nums = []
        i = 0
        k = 0
        while i < len(body):
            if body[i] in ' ,\t\r\n':
                i += 1
                continue
            if k % 7 in (3, 4) and body[i] in '01':
                nums.append(body[i])
                i += 1
            else:
                mm = _NUM.match(body, i)
                if not mm:
                    break
                nums.append(mm.group())
                i = mm.end()
            k += 1
        return cmd + ' ' + ' '.join(nums) + ' '
    return re.sub(r'([Aa])([^A-Za-df-z]*)', fix, d)


def parse_path(d: str, m: Affine) -> Path:
    b = PathBuilder(m)
    toks = list(_tokens(_arc_flags(d)))
    i = 0
    cmd = None
    cur = (0.0, 0.0)
    start = (0.0, 0.0)
    last_c2 = None          # dernier contrôle cubique (S)
    last_q = None           # dernier contrôle quadratique (T)

    def nums(k):
        nonlocal i
        v = toks[i:i + k]
        if len(v) < k or any(isinstance(x, str) for x in v):
            raise SvgError('arguments manquants dans un chemin')
        i += k
        return v

    while i < len(toks):
        if isinstance(toks[i], str):
            cmd = toks[i]
            i += 1
            if cmd in 'Zz':
                b.close()
                cur = start
                last_c2 = last_q = None
                continue
        if cmd is None:
            raise SvgError('chemin sans commande initiale')
        rel = cmd.islower()
        c = cmd.upper()
        ox, oy = cur if rel else (0.0, 0.0)
        if c == 'M':
            x, y = nums(2)
            cur = start = (ox + x, oy + y)
            b.move_to(cur)
            cmd = 'l' if rel else 'L'       # suite implicite = lineto
            last_c2 = last_q = None
        elif c == 'L':
            x, y = nums(2)
            cur = (ox + x, oy + y)
            b.line_to(cur)
            last_c2 = last_q = None
        elif c == 'H':
            (x,) = nums(1)
            cur = ((cur[0] if rel else 0.0) + x, cur[1])
            b.line_to(cur)
            last_c2 = last_q = None
        elif c == 'V':
            (y,) = nums(1)
            cur = (cur[0], (cur[1] if rel else 0.0) + y)
            b.line_to(cur)
            last_c2 = last_q = None
        elif c == 'C':
            x1, y1, x2, y2, x, y = nums(6)
            c1, c2, p = (ox + x1, oy + y1), (ox + x2, oy + y2), (ox + x, oy + y)
            b.cubic_to(c1, c2, p)
            cur, last_c2, last_q = p, c2, None
        elif c == 'S':
            x2, y2, x, y = nums(4)
            c1 = (2 * cur[0] - last_c2[0], 2 * cur[1] - last_c2[1]) if last_c2 else cur
            c2, p = (ox + x2, oy + y2), (ox + x, oy + y)
            b.cubic_to(c1, c2, p)
            cur, last_c2, last_q = p, c2, None
        elif c == 'Q':
            x1, y1, x, y = nums(4)
            q, p = (ox + x1, oy + y1), (ox + x, oy + y)
            b.quad_to(q, p)
            cur, last_q, last_c2 = p, q, None
        elif c == 'T':
            x, y = nums(2)
            q = (2 * cur[0] - last_q[0], 2 * cur[1] - last_q[1]) if last_q else cur
            p = (ox + x, oy + y)
            b.quad_to(q, p)
            cur, last_q, last_c2 = p, q, None
        elif c == 'A':
            rx, ry, phi, large, sweep, x, y = nums(7)
            p = (ox + x, oy + y)
            for seg in _svg_arc(cur, p, abs(rx), abs(ry), phi, bool(large), bool(sweep)):
                b.add_segment(seg.transformed(m))
            b._pos = p                       # le builder suit la position
            cur, last_c2, last_q = p, None, None
        else:
            raise SvgError(f'commande de chemin inconnue {cmd!r}')
    return b.path()


def _svg_arc(p0, p1, rx, ry, phi_deg, large, sweep):
    """Arc SVG (paramétrage par extrémités, repère Y vers le bas) →
    coniques, dans le repère utilisateur SVG."""
    if dist(p0, p1) < 1e-12:
        return []
    if rx < 1e-12 or ry < 1e-12:
        return [Line(p0, p1)]
    phi = math.radians(phi_deg)
    co, si = math.cos(phi), math.sin(phi)
    dx, dy = (p0[0] - p1[0]) / 2, (p0[1] - p1[1]) / 2
    x1 = co * dx + si * dy
    y1 = -si * dx + co * dy
    lam = (x1 * x1) / (rx * rx) + (y1 * y1) / (ry * ry)
    if lam > 1:
        s = math.sqrt(lam)
        rx, ry = rx * s, ry * s
    num = rx * rx * ry * ry - rx * rx * y1 * y1 - ry * ry * x1 * x1
    den = rx * rx * y1 * y1 + ry * ry * x1 * x1
    coef = math.sqrt(max(0.0, num / den)) if den else 0.0
    if large == sweep:
        coef = -coef
    cx1 = coef * rx * y1 / ry
    cy1 = -coef * ry * x1 / rx
    cx = co * cx1 - si * cy1 + (p0[0] + p1[0]) / 2
    cy = si * cx1 + co * cy1 + (p0[1] + p1[1]) / 2

    def ang(ux, uy, vx, vy):
        a = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
        return a
    t1 = ang(1, 0, (x1 - cx1) / rx, (y1 - cy1) / ry)
    dt = ang((x1 - cx1) / rx, (y1 - cy1) / ry, (-x1 - cx1) / rx, (-y1 - cy1) / ry)
    if not sweep and dt > 0:
        dt -= 2 * math.pi
    elif sweep and dt < 0:
        dt += 2 * math.pi
    segs = arc_conics((cx, cy), rx, ry, math.degrees(t1), math.degrees(dt), phi_deg)
    if segs:
        f, l = segs[0], segs[-1]
        segs[0] = Conic(p0, f.p1, f.p2, f.w)
        l = segs[-1]
        segs[-1] = Conic(l.p0, l.p1, p1, l.w)
    return segs


def _points(text: str) -> list[tuple[float, float]]:
    v = [float(x) for x in _NUM.findall(text or '')]
    return list(zip(v[0::2], v[1::2]))


def _style(el) -> dict:
    st = {}
    for part in (el.get('style') or '').split(';'):
        if ':' in part:
            k, v = part.split(':', 1)
            st[k.strip()] = v.strip()
    for k in ('display', 'visibility', 'stroke', 'fill'):
        if el.get(k) is not None:
            st.setdefault(k, el.get(k))
    return st


def _shape_path(tag: str, el, m: Affine) -> Path | None:
    f = lambda k, d=0.0: float(_NUM.findall(el.get(k) or '')[0]) if _NUM.findall(el.get(k) or '') else d
    if tag == 'path':
        d = el.get('d')
        return parse_path(d, m) if d else None
    if tag == 'rect':
        x, y, w, h = f('x'), f('y'), f('width'), f('height')
        if w <= 0 or h <= 0:
            return None
        rx = el.get('rx')
        ry = el.get('ry')
        rxv = f('rx') if rx is not None else (f('ry') if ry is not None else 0.0)
        ryv = f('ry') if ry is not None else rxv
        rxv, ryv = min(rxv, w / 2), min(ryv, h / 2)
        if rxv <= 0 or ryv <= 0:
            d = f'M{x},{y} H{x + w} V{y + h} H{x} Z'
        else:
            d = (f'M{x + rxv},{y} H{x + w - rxv} A{rxv},{ryv} 0 0 1 {x + w},{y + ryv} '
                 f'V{y + h - ryv} A{rxv},{ryv} 0 0 1 {x + w - rxv},{y + h} H{x + rxv} '
                 f'A{rxv},{ryv} 0 0 1 {x},{y + h - ryv} V{y + ryv} A{rxv},{ryv} 0 0 1 {x + rxv},{y} Z')
        return parse_path(d, m)
    if tag in ('circle', 'ellipse'):
        cx, cy = f('cx'), f('cy')
        if tag == 'circle':
            rx = ry = f('r')
        else:
            rx, ry = f('rx'), f('ry')
        if rx <= 0 or ry <= 0:
            return None
        segs = [s.transformed(m) for s in arc_conics((cx, cy), rx, ry, 0, 360)]
        return Path([Contour(segs, True)])
    if tag == 'line':
        b = PathBuilder(m)
        b.move_to((f('x1'), f('y1')))
        b.line_to((f('x2'), f('y2')))
        return b.path()
    if tag in ('polyline', 'polygon'):
        pts = _points(el.get('points'))
        if len(pts) < 2:
            return None
        b = PathBuilder(m)
        b.move_to(pts[0])
        for p in pts[1:]:
            b.line_to(p)
        if tag == 'polygon':
            b.close()
        return b.path()
    return None


def read(path) -> Document:
    return read_data(pathlib.Path(path).read_bytes(), str(path))


_PREDEFINED = {'amp', 'lt', 'gt', 'quot', 'apos'}
_TAG = re.compile(r'<([A-Za-z_][\w:.-]*)((?:[^<>"\']|"[^"]*"|\'[^\']*\')*?)(/?)>')
_ATTR = re.compile(r'([A-Za-z_][\w:.-]*)\s*=\s*("[^"]*"|\'[^\']*\')')


def repair(raw: bytes) -> tuple[bytes, list[str]]:
    """Défauts courants des SVG d'Illustrator et d'autres outils, réparés
    seulement si la lecture stricte échoue : entités sans leur DOCTYPE
    (`&ns_extend;`), attributs en double, guillemets orphelins dans une
    balise. Rend (texte réparé, remarques)."""
    text = raw.decode('utf-8', 'replace')
    notes: list[str] = []
    declared = set(re.findall(r'<!ENTITY\s+([A-Za-z_][\w.-]*)', text))

    def entity(m):
        name = m.group(1)
        if name in _PREDEFINED or name in declared:
            return m.group(0)
        notes.append(f'entité « {name} » non définie')
        return f'urn:entite:{name}'
    text = re.sub(r'&([A-Za-z_][\w.-]*);', entity, text)
    # guillemet orphelin avant la fin d'une balise : height="42px" ">
    text, n1 = re.subn(r'(=\s*"[^"<>]*")\s+"(\s*/?>)', r'\1\2', text)
    # valeur sans guillemet fermant en fin de balise : height="42px>
    text, n2 = re.subn(r'(=\s*"[^"<>\n]*)(/?>)(\s*\n)', r'\1"\2\3', text)
    if n1 or n2:
        notes.append('guillemets mal fermés')

    def tag(m):
        name, body, slash = m.group(1), m.group(2) or '', m.group(3)
        attrs, seen = [], set()
        for a, v in _ATTR.findall(body):
            if a in seen:
                notes.append(f'attribut « {a} » en double')
                continue
            seen.add(a)
            attrs.append(f'{a}={v}')
        rest = _ATTR.sub('', body).strip()
        if rest:
            notes.append(f'texte parasite dans <{name}> : {rest[:20]}')
        return '<' + name + ''.join(' ' + a for a in attrs) + slash + '>'
    text = _TAG.sub(tag, text)
    return text.encode('utf-8'), list(dict.fromkeys(notes))


def read_data(raw: bytes, source: str = '') -> Document:
    """SVG en mémoire (presse-papiers, glisser-déposer…)."""
    notes: list[str] = []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        fixed, notes = repair(raw)
        try:
            root = ET.fromstring(fixed)
        except ET.ParseError:
            raise SvgError(f'XML invalide : {e}') from e
    doc = Document(layers=[], source_path=source, source_format='svg')
    if notes:
        doc.report.append('SVG réparé : ' + ', '.join(notes[:4]) + (' …' if len(notes) > 4 else ''))
    # échelle du document : unités utilisateur → mm
    w_mm = _length_mm(root.get('width'))
    h_mm = _length_mm(root.get('height'))
    vb = [float(x) for x in _NUM.findall(root.get('viewBox') or '')]
    if len(vb) == 4 and vb[2] > 0 and vb[3] > 0:
        sx = (w_mm / vb[2]) if w_mm else 25.4 / 96
        sy = (h_mm / vb[3]) if h_mm else sx
        if not w_mm and h_mm:
            sx = sy
        base = Affine.scaling(sx, sy) @ Affine.translation(-vb[0], -vb[1])
        height = vb[3] * sy
    else:
        base = Affine.scaling(25.4 / 96)
        height = h_mm or 0.0
    flip = Affine(1, 0, 0, -1, 0, height)          # Y vers le haut
    top = flip @ base
    from . import plate_note
    origin = plate_note.svg_page(root.get(plate_note.SVG_ORIGIN), vb)    # écrit par VectorDrive, page inchangée :
    if origin is not None:                                               # sa plaque, et le dessin à sa place
        doc.plate = plate_note.from_text(root.get(plate_note.SVG_PLATE))
        top = Affine.translation(origin[0], origin[1]) @ top
    ids = {el.get('id'): el for el in root.iter() if el.get('id')}
    layers: dict[str, Layer] = {}
    from .colors import ToolColors, parse_css
    colors = ToolColors(doc)                             # une couleur = un outil (F10 › Fichiers)

    def layer_for(name: str) -> Layer:
        if name not in layers:
            layers[name] = Layer(name=name)
            doc.layers.append(layers[name])
        return layers[name]

    def walk(el, m: Affine, layer_name: str, out: list, depth=0, paint=(None, 'black')):
        tag = el.tag.replace(SVG_NS, '') if isinstance(el.tag, str) else ''
        st = _style(el)
        paint = (st.get('stroke', paint[0]), st.get('fill', paint[1]))   # trait et fond hérités
        color = parse_css(paint[0]) or parse_css(paint[1])
        if st.get('display') == 'none' or tag in ('defs', 'symbol', 'clipPath', 'mask',
                                                   'pattern', 'marker', 'metadata', 'title', 'desc',
                                                   'linearGradient', 'radialGradient', 'style'):
            return
        mm = m @ parse_transform(el.get('transform'))
        if tag in ('svg', 'g', 'a', 'switch') or depth == 0:
            label = el.get('{http://www.inkscape.org/namespaces/inkscape}label')
            is_layer = el.get('{http://www.inkscape.org/namespaces/inkscape}groupmode') == 'layer'
            name = (label or el.get('id') or layer_name) if is_layer else layer_name
            items: list = []
            for ch in el:
                walk(ch, mm, name, items, depth + 1, paint)
            if is_layer or depth == 0:
                layer_for(name).items.extend(items)
            elif items:
                out.append(Group(children=items, name=el.get('id') or ''))
            return
        if tag == 'use':
            ref = ids.get((el.get(XLINK) or el.get('href') or '').lstrip('#'))
            if ref is not None:
                t = Affine.translation(float(el.get('x') or 0), float(el.get('y') or 0))
                inner: list = []
                for ch in (ref if ref.tag.endswith(('symbol', 'g')) else [ref]):
                    walk(ch, mm @ t, layer_name, inner, depth + 1, paint)
                out.extend(inner)
            return
        if tag == 'text':
            try:
                t = _svg_text(el, mm, font_notes)
            except Exception as ex:                      # texte abîmé : signalé, le reste continue
                doc.report.append(f'texte SVG non repris : {ex}')
                return
            if t is not None:
                t.tool = colors.tool(color)
                out.append(t)
                texts[0] += 1
            return
        p = _shape_path(tag, el, mm)
        if p:
            out.append(Shape(path=p, name=el.get('id') or '', tool=colors.tool(color)))

    texts, font_notes = [0], set()
    walk(root, top, 'Calque 1', [])
    if texts[0]:
        doc.report.append(f'{texts[0]} texte(s) SVG repris en textes vivants')
        doc.report.extend(sorted(font_notes))
    doc.layers = [L for L in doc.layers if L.items] or [Layer(name='Calque 1')]
    from .colors import black_first
    black_first(doc, colors)
    return doc


# --- textes ------------------------------------------------------------------

_ANCHOR = {'start': 'left', 'middle': 'center', 'end': 'right'}


def _prop(el, name: str, st: dict | None = None):
    st = _style(el) if st is None else st
    v = st.get(name)
    return v if v is not None else el.get(name)


def _first_num(text: str | None) -> float | None:
    found = _NUM.findall(text or '')
    return float(found[0]) if found else None


def _svg_font(families: str | None, notes: set) -> tuple[str, float]:
    """(police du poste, hauteur des capitales / corps) pour une liste CSS
    « Arial, sans-serif » ; Arial si aucune n'est là (noté)."""
    from ..core import fonts
    names = [n.strip().strip('\'"') for n in (families or '').split(',') if n.strip()]
    for n in names:
        if n.lower() in ('serif', 'sans-serif', 'monospace', 'cursive', 'fantasy', 'system-ui'):
            continue
        f = fonts.find_font(n) if fonts.is_available(n) else None
        if f:
            m = fonts.metrics(*f)
            try:
                fam = fonts.load(*f)['name'].getDebugName(1) or n
            except Exception:
                fam = n
            return fam, m['cap'] / m['upem']
    if names and not all(n.lower() in ('serif', 'sans-serif', 'monospace') for n in names):
        notes.add(f'police SVG « {names[0]} » absente : Arial')
    f = fonts.find_font('Arial')
    ratio = 0.716
    if f:
        m = fonts.metrics(*f)
        ratio = m['cap'] / m['upem']
    return 'Arial', ratio


def _svg_text(el, mm: Affine, notes: set):
    """<text> (et ses <tspan>) → texte vivant : ligne de base à (x, y),
    corps `font-size` (unités utilisateur ou absolues) ramené en hauteur de
    capitales, ancrage start/middle/end, un retour à la ligne par <tspan>
    posé sur un autre y (ou avec dy)."""
    st = _style(el)
    lines, cur = [], [(el.text or '')]
    first_y = _first_num(el.get('y'))
    for ch in el:
        tag = ch.tag.replace(SVG_NS, '') if isinstance(ch.tag, str) else ''
        if tag == 'tspan':
            y = _first_num(ch.get('y'))
            new_line = ch.get('dy') is not None or (y is not None and first_y is not None and abs(y - first_y) > 1e-9
                                                   and ''.join(cur).strip())
            if new_line:
                lines.append(''.join(cur))
                cur = []
                if y is not None:
                    first_y = y
            cur.append(''.join(ch.itertext()))
        cur.append(ch.tail or '')
    lines.append(''.join(cur))
    lines = [' '.join(s.split()) for s in lines]
    text = '\n'.join(lines).strip('\n')
    if not text.strip():
        return None
    size = _prop(el, 'font-size', st)
    em_user = (_length_mm(size, None) or 0.0) / (25.4 / 96) if size else 16.0 * 1.0   # 16 px : défaut CSS
    x, y = _first_num(el.get('x')) or 0.0, _first_num(el.get('y')) or 0.0
    p0 = mm.apply((x, y))
    p1 = mm.apply((x + 1.0, y))
    s = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    rot = math.degrees(math.atan2(p1[1] - p0[1], p1[0] - p0[0]))
    fam, ratio = _svg_font(_prop(el, 'font-family', st), notes)
    size_mm = em_user * s * ratio
    if size_mm <= 0:
        return None
    t = Text(text=text, font=fam, size=size_mm, align=_ANCHOR.get(str(_prop(el, 'text-anchor', st) or 'start'), 'left'),
             name=el.get('id') or '')
    if str(_prop(el, 'font-style', st) or '') in ('italic', 'oblique'):
        t.extra['italic'] = 12.0
    t.matrix = Affine.translation(p0[0], p0[1]) @ Affine.rotation(rot)
    return t


# --- écriture ----------------------------------------------------------------

def _fmt(v: float) -> str:
    s = f'{v:.4f}'.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


def path_d(p: Path, H: float) -> str:
    """Chemin SVG (Y retourné : y_svg = H − y)."""
    out = []
    P = lambda q: f'{_fmt(q[0])},{_fmt(H - q[1])}'
    for c in p.contours:
        if not c.segments:
            continue
        out.append('M' + P(c.start))
        for s in c.segments:
            if isinstance(s, Line):
                out.append('L' + P(s.p1))
            elif isinstance(s, Cubic):
                out.append('C' + ' '.join(P(q) for q in (s.p1, s.p2, s.p3)))
            elif isinstance(s, Conic):
                if abs(s.w - 1) < 1e-12:
                    out.append('Q' + P(s.p1) + ' ' + P(s.p2))
                    continue
                arc = s.circle_params()
                if arc:
                    _c, r, _a0, sweep = arc
                    # Y retourné : le sens s'inverse
                    out.append(f'A{_fmt(r)},{_fmt(r)} 0 {1 if abs(sweep) > 180 else 0} '
                               f'{0 if sweep > 0 else 1} ' + P(s.p2))
                else:
                    for cb in s.to_cubics():
                        out.append('C' + ' '.join(P(q) for q in (cb.p1, cb.p2, cb.p3)))
        if c.closed:
            out.append('Z')
    return ' '.join(out)


def write(doc: Document, path) -> None:
    pathlib.Path(path).write_text(to_string(doc, note=True), encoding='utf-8')


def to_string(doc: Document, *, include_plate: bool = True, note: bool = False) -> str:
    """Le SVG du dessin. `note` (fichier enregistré) : la racine porte la plaque et la place de la page dans le
    dessin, pour le relire tel quel."""
    bb = doc.bbox(include_plate=include_plate) or (0, 0, 100, 100)
    x0, y0, x1, y1 = bb
    w, h = max(x1 - x0, 1e-3), max(y1 - y0, 1e-3)
    H = y1
    extra = ''
    if note:
        from . import plate_note
        extra = plate_note.svg_attributes(doc.plate, x0, y0, w, h)
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<svg xmlns="http://www.w3.org/2000/svg" '
             'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
             f'width="{_fmt(w)}mm" height="{_fmt(h)}mm" '
             f'viewBox="{_fmt(x0)} 0 {_fmt(w)} {_fmt(h)}"{extra}>',
             '<!-- VectorDrive -->']

    def emit(it, indent):
        if not it.visible:
            return
        if isinstance(it, Group):
            lines.append(f'{indent}<g>')
            for ch in it.children:
                emit(ch, indent + '  ')
            lines.append(f'{indent}</g>')
            return
        p = getattr(it, 'path', None) or getattr(it, 'outline', None)
        if not p:
            return
        color = doc.item_color(it)
        fill = color if getattr(it, 'filled', False) else 'none'
        lines.append(f'{indent}<path d="{path_d(p, H)}" fill="{fill}" stroke="{color}" '
                     f'stroke-width="0.1"/>')

    for L in doc.layers:
        if not L.visible:
            continue
        name = L.name.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;')
        lines.append(f'<g inkscape:groupmode="layer" inkscape:label="{name}">')
        for it in L.items:
            emit(it, '  ')
        lines.append('</g>')
    lines.append('</svg>')
    return '\n'.join(lines)
