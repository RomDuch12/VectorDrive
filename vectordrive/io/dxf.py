"""DXF : lecture et écriture, via ezdxf (MIT).

Lecture : arcs, cercles et bulges de polylignes deviennent des coniques
exactes ; les splines passent par la décomposition de Bézier d'ezdxf ;
blocs, cotes, repères, multilignes et tableaux éclatés ; droites infinies
(XLINE, RAY) en lignes de construction ; cadres de tolérancement
(TOLERANCE) en cadres modifiables ; maillages 3D (polyface, polymesh,
MESH, 3DFACE) en volumes — un objet chacun, les 3DFACE d'un calque et d'une
couleur ensemble —, un maillage ouvert en son contour vu de dessus ; calques
éteints ou gelés écartés (une sauvegarde associative cachée ne doit pas se
graver). Un calque DXF = un calque VectorDrive.

Écriture : R2010, une LWPOLYLINE par contour quand il n'a que des droites
et des arcs de cercle (bulges exacts), une SPLINE sinon.
"""
from __future__ import annotations

import math
import pathlib

import ezdxf
from ezdxf import path as ezpath

from ..core.document import Document, Layer, Shape, Group, Text
from ..core.geom import (Affine, Conic, Contour, Cubic, Line, Path, arc_conics,
                         Point, bulge_segment, dist)

#: Facteur vers le mm selon $INSUNITS (0 = sans unité → mm supposé).
INSUNITS_MM = {0: 1.0, 1: 25.4, 2: 304.8, 4: 1.0, 5: 10.0, 6: 1000.0, 8: 0.0000254,
               9: 0.0254, 10: 914.4, 13: 0.001, 14: 100.0}


class DxfError(ValueError):
    pass


#: entités lues par leur décomposition (traits, textes, blocs de flèches)
EXPLODED = ('DIMENSION', 'ARC_DIMENSION', 'LARGE_RADIAL_DIMENSION', 'LEADER', 'MLEADER', 'MULTILEADER', 'MLINE',
            'ACAD_TABLE')


def _construction(e) -> tuple[float, float, float] | None:
    """XLINE (droite infinie) ou RAY (demi-droite) : (x, y, angle de 0 à
    180°) de la ligne de construction, ou None (droite verticale en Z)."""
    p, u = e.dxf.start, e.dxf.unit_vector
    if math.hypot(u.x, u.y) < 1e-12:
        return None
    return p.x, p.y, math.degrees(math.atan2(u.y, u.x)) % 180.0


def _tolerance(e, d, tool: int) -> Group | None:
    """Cadre de tolérancement (TOLERANCE) en groupe `core.gdt` : hauteur du
    texte et écart du style de cote (DIMTXT, DIMGAP, multipliés par
    DIMSCALE), axe X de l'entité ; None s'il est vide."""
    from ..core import gdt
    text = str(e.dxf.get('content', '') or '')
    if not any(any(not gdt._empty(c) for c in row) for row in gdt.parse_frame(text)):
        return None
    name = e.dxf.get('dimstyle', 'Standard')
    st = d.dimstyles.get(name) if d.dimstyles.has_entry(name) else None

    def var(key, default):
        v = st.dxf.get(key) if st is not None else None
        v = d.header.get('$' + key.upper(), default) if v is None else v
        try:
            v = float(v)
        except (TypeError, ValueError):
            return default
        return v if math.isfinite(v) and v > 0 else default

    sc = var('dimscale', 1.0)
    h = var('dimtxt', 2.5) * sc
    u = e.dxf.get('x_axis_vector', (1.0, 0.0, 0.0))
    ux, uy = float(u[0]), float(u[1])
    p = e.dxf.get('insert', (0.0, 0.0, 0.0))
    rot = math.degrees(math.atan2(uy, ux)) if math.hypot(ux, uy) > 1e-12 else 0.0
    return gdt.group({'text': text, 'insert': [float(p[0]), float(p[1])], 'rotation': rot, 'height': h,
                      'gap': var('dimgap', h / 4 / sc) * sc, 'font': 'Arial'}, tool)


def _add_guides(doc: Document, lines, scale: float) -> None:
    """Lignes de construction en guides du dessin : horizontale ou verticale
    → guide ordinaire, sinon guide oblique (une demi-droite devient une
    droite entière)."""
    for x, y, a in lines:
        x, y = x * scale, y * scale
        if min(a, 180.0 - a) < 1e-6:
            doc.extra.setdefault('guides', []).append(['h', y])
        elif abs(a - 90.0) < 1e-6:
            doc.extra.setdefault('guides', []).append(['v', x])
        else:
            doc.extra.setdefault('guides_obliques', []).append([x, y, round(a, 9)])


def _hidden_layers(doc) -> set[str]:
    out = set()
    for L in doc.layers:
        try:
            if L.is_off() or L.is_frozen() or not L.dxf.get('plot', 1):
                out.add(L.dxf.name)
        except Exception:
            pass
    return out


def _entity_contours(e, report: list[str]) -> list[Contour]:
    t = e.dxftype()
    if t == 'LINE':
        s, f = e.dxf.start, e.dxf.end
        return [Contour([Line((s.x, s.y), (f.x, f.y))])]
    if t == 'CIRCLE' and _flat(e):
        c = e.dxf.center
        return [Contour(arc_conics((c.x, c.y), e.dxf.radius, e.dxf.radius, 0, 360), True)]
    if t == 'ARC' and _flat(e):
        c = e.dxf.center
        a0, a1 = e.dxf.start_angle, e.dxf.end_angle
        sweep = (a1 - a0) % 360 or 360
        return [Contour(arc_conics((c.x, c.y), e.dxf.radius, e.dxf.radius, a0, sweep))]
    if t == 'ELLIPSE' and _flat(e):
        c = e.dxf.center
        maj = e.dxf.major_axis
        rx = math.hypot(maj.x, maj.y)
        ry = rx * e.dxf.ratio
        rot = math.degrees(math.atan2(maj.y, maj.x))
        p0 = math.degrees(e.dxf.start_param)
        p1 = math.degrees(e.dxf.end_param)
        sweep = (p1 - p0) % 360 or 360
        closed = abs(sweep - 360) < 1e-9
        return [Contour(arc_conics((c.x, c.y), rx, ry, p0, sweep, rot), closed)]
    if t == 'LWPOLYLINE' and _flat(e):
        pts = list(e.get_points('xyb'))
        if len(pts) < 2:
            return []
        closed = bool(e.closed)
        segs = []
        n = len(pts)
        for i in range(n if closed else n - 1):
            x0, y0, b0 = pts[i]
            x1, y1, _ = pts[(i + 1) % n]
            if dist((x0, y0), (x1, y1)) > 1e-12:
                segs += bulge_segment((x0, y0), (x1, y1), b0)
        return [Contour(segs, closed)] if segs else []
    if t == 'POLYLINE' and _flat(e) and _plain_2d(e):
        # ancienne polyligne 2D (sommets VERTEX, bulges) : comme LWPOLYLINE — le
        # chemin générique d'ezdxf la découpe en courbes, 5 à 10 fois plus lent
        pts = [(v.dxf.location.x, v.dxf.location.y, v.dxf.get('bulge', 0.0) or 0.0) for v in e.vertices]
        if len(pts) < 2:
            return []
        closed = bool(e.is_closed)
        segs = []
        n = len(pts)
        for i in range(n if closed else n - 1):
            x0, y0, b0 = pts[i]
            x1, y1, _ = pts[(i + 1) % n]
            if dist((x0, y0), (x1, y1)) > 1e-12:
                segs += bulge_segment((x0, y0), (x1, y1), b0)
        return [Contour(segs, closed)] if segs else []
    # tout le reste (SPLINE, POLYLINE lissée ou 3D, HATCH, SOLID, 3D…) : chemin ezdxf
    try:
        p = ezpath.make_path(e)
    except Exception:
        report.append(f'{t} non pris en charge')
        return []
    return _from_ezpath(p)


def _is_mesh(e) -> bool:
    """Maillage 3D : POLYLINE polyface ou polymesh, MESH, 3DFACE."""
    t = e.dxftype()
    if t in ('3DFACE', 'MESH'):
        return True
    try:
        return t == 'POLYLINE' and bool(e.is_poly_face_mesh or e.is_polygon_mesh)
    except Exception:
        return False


def _mesh_triangles(e):
    """Triangles (n, 3, 3) d'un maillage 3D DXF, ses faces en éventail."""
    import numpy as np
    from ezdxf.render import MeshBuilder
    if e.dxftype() == '3DFACE':
        v = [tuple(p) for p in e.wcs_vertices()]
        faces = [range(len(v))]
    else:
        mb = MeshBuilder.from_mesh(e) if e.dxftype() == 'MESH' else MeshBuilder.from_polyface(e)
        v, faces = [tuple(p) for p in mb.vertices], mb.faces
    out = [(v[f[0]], v[f[k]], v[f[k + 1]]) for f in (list(f) for f in faces) for k in range(1, len(f) - 1)]
    return np.asarray(out, dtype=float).reshape(-1, 3, 3)


def _mesh_item(T, tool: int):
    """Maillage (n, 3, 3) en forme du dessin : un volume s'il est fermé,
    sinon son contour vu de dessus (réunion des triangles projetés) ; None
    si rien n'en reste. Rend (forme, fermé)."""
    import numpy as np
    from ..core import solids as SO
    from ..core.geom import polyline
    try:
        return SO.make_shape(SO.from_triangles(T, 'Maillage'), tool), True
    except SO.SolidError:
        pass
    except Exception:                                    # maillage abîmé : son contour, comme ouvert
        pass
    M = SO._m()
    P = T[:, :, :2]
    a = (P[:, 1, 0] - P[:, 0, 0]) * (P[:, 2, 1] - P[:, 0, 1]) - (P[:, 2, 0] - P[:, 0, 0]) * (P[:, 1, 1] - P[:, 0, 1])
    P = np.where((a < 0)[:, None, None], P[:, ::-1], P)[np.abs(a) > 1e-12]   # tous en sens direct
    if not len(P):
        return None, False
    cs = M.CrossSection(list(P), M.FillRule.NonZero)
    loops = [polyline([tuple(map(float, q)) for q in poly], closed=True) for poly in cs.to_polygons() if len(poly) >= 3]
    return (Shape(path=Path(loops), tool=tool, name='Maillage ouvert') if loops else None), False


def _plain_2d(e) -> bool:
    """POLYLINE 2D sans lissage (ni courbe ni spline ajustée) ni largeurs à suivre."""
    try:
        return e.is_2d_polyline and not (int(e.dxf.flags) & (2 | 4)) and \
            not any(int(v.dxf.flags) & (1 | 8 | 16) for v in e.vertices)
    except Exception:
        return False


def _flat(e) -> bool:
    """Entité dans le plan XY (extrusion +Z) : sinon, chemin générique."""
    try:
        z = e.dxf.extrusion
        return abs(z.x) < 1e-9 and abs(z.y) < 1e-9 and z.z > 0
    except Exception:
        return True


class _P:
    __slots__ = ('x', 'y')

    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)


def _v(v) -> _P:
    return _P(v.x, v.y)


def _from_ezpath(p) -> list[Contour]:
    out: list[Contour] = []
    for sub in p.sub_paths():
        segs = []
        cur = _v(sub.start)
        for cmd in sub.commands():
            k = cmd.type.name
            end = _v(cmd.end)
            if k == 'LINE_TO':
                if dist((cur.x, cur.y), (end.x, end.y)) > 1e-12:
                    segs.append(Line((cur.x, cur.y), (end.x, end.y)))
            elif k == 'CURVE3_TO':
                c = _v(cmd.ctrl)
                segs.append(Conic((cur.x, cur.y), (c.x, c.y), (end.x, end.y), 1.0))
            elif k == 'CURVE4_TO':
                c1, c2 = _v(cmd.ctrl1), _v(cmd.ctrl2)
                segs.append(Cubic((cur.x, cur.y), (c1.x, c1.y), (c2.x, c2.y), (end.x, end.y)))
            elif k == 'MOVE_TO':
                pass
            cur = end
        if segs:
            closed = sub.is_closed or dist(segs[0].start, segs[-1].end) < 1e-9
            out.append(Contour(segs, closed))
    return out


def _read_raw(path) -> Document:
    """Lecteur de secours par codes de groupe, pour les DXF qu'ezdxf
    refuse (marqueurs de sous-classe absents, écrits par des exports
    simplistes) : LINE, CIRCLE, ARC, LWPOLYLINE, POLYLINE/VERTEX, avec
    bulges et calques. Coordonnées prises telles quelles."""
    raw = pathlib.Path(path).read_bytes()
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        text = raw.decode('cp1252', 'replace')
    lines = text.splitlines()
    pairs = [(lines[i].strip(), lines[i + 1].strip()) for i in range(0, len(lines) - 1, 2)]
    try:
        start = next(i for i, (c, v) in enumerate(pairs) if c == '2' and v == 'ENTITIES')
    except StopIteration:
        raise DxfError('section ENTITIES absente')
    ents, cur = [], None
    for c, v in pairs[start + 1:]:
        if c == '0':
            if cur:
                ents.append(cur)
            if v == 'ENDSEC':
                cur = None
                break
            cur = [v, []]
        elif cur is not None:
            cur[1].append((c, v))
    layers: dict[str, Layer] = {}

    def add(layer, contour):
        L = layers.setdefault(layer, Layer(name=layer))
        L.items.append(Shape(path=Path([contour])))

    def poly(points, closed):
        segs = []
        n = len(points)
        for k in range(n if closed else n - 1):
            (x0, y0, b), (x1, y1, _b) = points[k], points[(k + 1) % n]
            if (x0, y0) != (x1, y1):
                segs.extend(bulge_segment((x0, y0), (x1, y1), b) if abs(b) > 1e-12 else [Line((x0, y0), (x1, y1))])
        return Contour(segs, closed) if segs else None

    i = 0
    skipped = set()
    while i < len(ents):
        kind, g = ents[i]
        d = {}
        for c, v in g:
            d.setdefault(c, v)
        layer = d.get('8', '0')
        num = lambda c, default=0.0: float(d.get(c, default))
        if kind == 'LINE':
            add(layer, Contour([Line((num('10'), num('20')), (num('11'), num('21')))], False))
        elif kind in ('CIRCLE', 'ARC'):
            r = num('40')
            a0, a1 = (num('50'), num('51')) if kind == 'ARC' else (0.0, 360.0)
            sweep = (a1 - a0) % 360 or 360
            add(layer, Contour(arc_conics((num('10'), num('20')), r, r, a0, sweep), kind == 'CIRCLE'))
        elif kind == 'LWPOLYLINE':
            pts = []
            for c, v in g:
                if c == '10':
                    pts.append([float(v), 0.0, 0.0])
                elif c == '20' and pts:
                    pts[-1][1] = float(v)
                elif c == '42' and pts:
                    pts[-1][2] = float(v)
            ct = poly([tuple(p) for p in pts], bool(int(d.get('70', 0)) & 1))
            if ct:
                add(layer, ct)
        elif kind == 'POLYLINE':
            closed = bool(int(d.get('70', 0)) & 1)
            pts = []
            i += 1
            while i < len(ents) and ents[i][0] == 'VERTEX':
                vd = dict(ents[i][1])
                pts.append((float(vd.get('10', 0)), float(vd.get('20', 0)), float(vd.get('42', 0))))
                i += 1
            ct = poly(pts, closed)
            if ct:
                add(layer, ct)
            continue
        elif kind not in ('SEQEND', 'VERTEX'):
            skipped.add(kind)
        i += 1
    doc = Document(layers=list(layers.values()) or [Layer(name='0')], source_path=str(path),
                   source_format='dxf')
    doc.report.append('DXF non conforme (refusé par ezdxf) : lu par le lecteur de secours')
    if skipped:
        doc.report.append('entités ignorées par le lecteur de secours : ' + ', '.join(sorted(skipped)))
    return doc


# --- textes ------------------------------------------------------------------

#: interligne DXF : 5/3 de la hauteur des capitales entre lignes de base
MTEXT_PITCH = 5.0 / 3.0
#: alignement horizontal DXF → VectorDrive
_HALIGN = {'LEFT': 'left', 'CENTER': 'center', 'RIGHT': 'right', 'MIDDLE': 'center', 'ALIGNED': 'left',
           'FIT': 'left'}


def _style_font(d, style_name: str, notes: set) -> str:
    """Police d'un style DXF : famille TrueType si elle est sur le poste,
    sinon Arial (les polices SHX d'AutoCAD n'existent pas ici) ; la
    substitution est notée."""
    from ..core import fonts
    style = d.styles.get(style_name) if style_name else None
    candidates = []
    if style is not None:
        try:
            fam = style.get_extended_font_data()[0]
            if fam:
                candidates.append(fam)
        except Exception:
            pass
        f = str(style.dxf.get('font', '') or '')
        if f and not f.lower().endswith('.shx'):
            candidates.append(pathlib.Path(f).stem)
        if style_name and style_name.lower() not in ('standard', 'annotative'):
            candidates.append(style_name)
    for c in candidates:
        found = fonts.find_font(c) if fonts.is_available(c) else None
        if found:
            try:                                          # nom de famille de la police elle-même (« Arial », pas « arial »)
                fam = fonts.load(found[0], found[1])['name'].getDebugName(1)
                return fam or c
            except Exception:
                return c
    shown = (str(style.dxf.get('font', '') or '') if style is not None else '') or (candidates[0] if candidates
                                                                                        else style_name)
    if shown:
        notes.add(f'police DXF « {shown} » absente : Arial')
    return 'Arial'


def _dxf_text(e, d, notes: set) -> Text | None:
    """TEXT / ATTRIB / MTEXT → texte vivant (cotes en unités du fichier)."""
    kind = e.dxftype()
    if kind == 'MTEXT':
        text = e.plain_text().replace('\r', '')
        h = float(e.dxf.char_height or 0)
        if not text.strip() or h <= 0:
            return None
        lines = text.split('\n')
        ap = int(e.dxf.get('attachment_point', 1) or 1)
        row, col = (ap - 1) // 3, (ap - 1) % 3
        align = ('left', 'center', 'right')[col]
        lsf = float(e.dxf.get('line_spacing_factor', 1.0) or 1.0)
        pitch = MTEXT_PITCH * h * lsf
        block = h + (len(lines) - 1) * pitch
        dy = (-h, block / 2 - h, block - h)[row]          # ligne de base de la 1re ligne par rapport au point
        x, y = float(e.dxf.insert.x), float(e.dxf.insert.y)
        rot = float(e.get_rotation())
        t = Text(text='\n'.join(lines), font=_style_font(d, e.dxf.get('style', 'Standard'), notes), size=h,
                 align=align, line_spacing=1.2 * lsf)
        t.matrix = Affine.translation(x, y) @ Affine.rotation(rot) @ Affine.translation(0.0, dy)
        return t
    text = str(e.dxf.get('text', '') or '')
    h = float(e.dxf.get('height', 0) or 0)
    if not text.strip() or h <= 0:
        return None
    try:
        al, p1, p2 = e.get_placement()
        name = al.name
    except Exception:
        name, p1, p2 = 'LEFT', e.dxf.insert, None
    parts = name.split('_')
    v, hname = (parts[0], parts[1]) if len(parts) == 2 else (None, parts[0])
    if name == 'MIDDLE':
        v = 'MIDDLE'
    frac = {'TOP': 1.0, 'MIDDLE': 0.5}.get(v, 0.0)        # part de la hauteur sous le point d'ancrage
    rot = float(e.dxf.get('rotation', 0.0) or 0.0)
    extra = {}
    if name in ('ALIGNED', 'FIT') and p2 is not None:
        width = math.hypot(p2.x - p1.x, p2.y - p1.y)
        if width > 0:
            rot = math.degrees(math.atan2(p2.y - p1.y, p2.x - p1.x))
            extra['fit'] = {'width': width, 'mode': 'width'}
    t = Text(text=text, font=_style_font(d, e.dxf.get('style', 'Standard'), notes), size=h,
             align=_HALIGN.get(hname, 'left'), width_ratio=float(e.dxf.get('width', 1.0) or 1.0))
    obl = float(e.dxf.get('oblique', 0.0) or 0.0)
    if obl:
        extra['italic'] = obl
    if extra:
        t.extra.update(extra)
    t.matrix = Affine.translation(float(p1.x), float(p1.y)) @ Affine.rotation(rot) @ Affine.translation(0.0, -frac * h)
    return t


def _entity_color(e, d, layer: str, block_color: str | None) -> str | None:
    """Couleur effective d'une entité (« #rrggbb ») : couleur vraie, couleur indexée, celle du calque
    (DUCALQUE) ou du bloc (DUBLOC) ; le 7 des DAO (blanc ou noir selon le fond) compte pour le noir."""
    from ezdxf.colors import aci2rgb, int2rgb
    from .colors import hex_of
    tc = e.dxf.get('true_color')
    if tc is not None:
        return hex_of(*int2rgb(tc))
    aci = e.dxf.get('color', 256)
    if aci == 0:
        return block_color
    if aci == 256:
        try:
            lay = d.layers.get(layer)
        except Exception:                                # noqa: BLE001 — calque absent de la table
            lay = None
        if lay is None:
            return None
        ltc = lay.dxf.get('true_color')
        if ltc is not None:
            return hex_of(*int2rgb(ltc))
        aci = abs(int(lay.dxf.get('color', 7) or 7))
    if aci in (7, 255) or not 1 <= aci <= 255:
        return '#000000' if aci == 7 or aci > 255 or aci < 1 else hex_of(*aci2rgb(aci))
    return hex_of(*aci2rgb(aci))


def read(path) -> Document:
    try:
        d = ezdxf.readfile(str(path))
    except (IOError, ezdxf.DXFStructureError) as ex:
        try:
            from ezdxf import recover
            d, _audit = recover.readfile(str(path))
        except Exception:
            try:
                return _read_raw(path)
            except Exception:
                raise DxfError(f'DXF illisible : {ex}') from ex
    doc = Document(layers=[], source_path=str(path), source_format='dxf')
    from . import plate_note
    doc.plate = plate_note.of_dxf(d)                     # la plaque notée par VectorDrive dans le dessin
    scale = INSUNITS_MM.get(d.header.get('$INSUNITS', 0), 1.0) or 1.0
    # beaucoup d'exports déclarent des mètres alors qu'ils écrivent des mm :
    # on ne fait confiance à l'unité que si les cotes restent plausibles
    hidden = _hidden_layers(d)
    m = Affine.scaling(scale) if scale != 1.0 else None
    layers: dict[str, Layer] = {}
    from .colors import ToolColors
    colors = ToolColors(doc)                             # une couleur = un outil (F10 › Fichiers)

    def add(e, layer_name, color):
        if layer_name in hidden:
            return
        tool = colors.tool(color)
        for c in _entity_contours(e, doc.report):
            if m is not None:
                c = c.transformed(m)
            L = layers.get(layer_name)
            if L is None:
                L = layers[layer_name] = Layer(name=layer_name)
                doc.layers.append(L)
            L.items.append(Shape(path=Path([c]), tool=tool))

    def walk(entities, layer_override=None, depth=0, block_color=None):
        for e in entities:
            t = e.dxftype()
            lay = e.dxf.get('layer', '0')
            if lay == '0' and layer_override:
                lay = layer_override
            color = _entity_color(e, d, lay, block_color)
            if t == 'INSERT':
                if depth > 16:
                    continue
                try:
                    walk(e.virtual_entities(), lay, depth + 1, color)
                except Exception as ex:
                    doc.report.append(f'bloc {e.dxf.name} non éclaté : {ex}')
                continue
            if t in ('TEXT', 'MTEXT', 'ATTRIB'):
                if lay in hidden or getattr(e, 'is_invisible', False):
                    continue
                try:
                    item = _dxf_text(e, d, font_notes)
                except Exception as ex:                  # texte abîmé : signalé, le reste continue
                    doc.report.append(f'{t} non repris : {ex}')
                    continue
                if item is not None:
                    if m is not None:
                        item = item.transformed(m)
                    item.tool = colors.tool(color)
                    L = layers.get(lay)
                    if L is None:
                        L = layers[lay] = Layer(name=lay)
                        doc.layers.append(L)
                    L.items.append(item)
                    texts[0] += 1
                continue
            if t in EXPLODED:
                try:
                    walk(e.virtual_entities(), lay, depth + 1, color)
                except Exception:
                    doc.report.append(f'{t} non éclaté')
                continue
            if t in ('XLINE', 'RAY'):
                if lay not in hidden and (g := _construction(e)) is not None:
                    xlines.append(g)
                continue
            if t == 'TOLERANCE':
                if lay in hidden:
                    continue
                try:
                    item = _tolerance(e, d, colors.tool(color))
                except Exception as ex:
                    doc.report.append(f'TOLERANCE non repris : {ex}')
                    continue
                if item is not None:
                    if m is not None:
                        item = item.transformed(m)
                    L = layers.get(lay)
                    if L is None:
                        L = layers[lay] = Layer(name=lay)
                        doc.layers.append(L)
                    L.items.append(item)
                    frames[0] += 1
                continue
            if t in ('POINT', 'VIEWPORT', 'IMAGE', 'WIPEOUT', 'OLE2FRAME'):
                continue
            if _is_mesh(e):
                if lay in hidden:
                    continue
                try:
                    tri = _mesh_triangles(e)
                except Exception as ex:
                    doc.report.append(f'{t} non repris : {ex}')
                    continue
                if len(tri):
                    tool = colors.tool(color)
                    if t == '3DFACE':                    # faces isolées : un maillage par calque et par couleur
                        faces3d.setdefault((lay, tool), []).append(tri)
                    else:
                        meshes.append((lay, tool, tri))
                continue
            add(e, lay, color)

    texts, font_notes, xlines, frames, meshes, faces3d = [0], set(), [], [0], [], {}
    walk(d.modelspace())
    if texts[0]:
        doc.report.append(f'{texts[0]} texte(s) DXF repris en textes vivants')
        doc.report.extend(sorted(font_notes))
    if frames[0]:
        doc.report.append(f'{frames[0]} cadre(s) de tolérancement (TOLERANCE) repris')
    if scale > 1.0:
        bb = doc.bbox()
        # TypeEdit (et d'autres) déclarent des mètres mais écrivent des mm :
        # au-delà de 10 m d'emprise, l'unité déclarée n'est pas crédible
        # pour une pièce à graver ; on garde les cotes telles qu'écrites.
        if bb and max(abs(v) for v in bb) > 10_000:
            inv = Affine.scaling(1 / scale)
            for L in doc.layers:
                L.items = [it.transformed(inv) for it in L.items]
            doc.report.append('$INSUNITS ignoré (cotes déjà en mm)')
            scale = 1.0
    import numpy as np                                   # maillages 3D : à l'échelle retenue, en mm
    meshes += [(lay, tool, np.concatenate(parts)) for (lay, tool), parts in faces3d.items()]
    got = [0, 0]
    for lay, tool, tri in meshes:
        try:
            item, closed = _mesh_item(tri * scale, tool)
        except Exception as ex:                          # manifold3d absent
            doc.report.append(f'maillage 3D non repris : {ex}')
            continue
        if item is None:
            continue
        L = layers.get(lay)
        if L is None:
            L = layers[lay] = Layer(name=lay)
            doc.layers.append(L)
        L.items.append(item)
        got[0 if closed else 1] += 1
    if got[0]:
        doc.report.append(f'{got[0]} maillage(s) 3D (polyface, MESH, 3DFACE) repris en volumes')
    if got[1]:
        doc.report.append(f'{got[1]} maillage(s) 3D ouvert(s) repris en contour vu de dessus')
    if xlines:
        _add_guides(doc, xlines, scale)
        doc.report.append(f'{len(xlines)} ligne(s) de construction (XLINE, RAY) reprises en guides')
    if not doc.layers:
        doc.layers.append(Layer(name='0'))
    from .colors import black_first
    black_first(doc, colors)
    return doc


# --- écriture ----------------------------------------------------------------

def _bulge_of(s: Conic) -> float | None:
    arc = s.circle_params()
    if not arc:
        return None
    sweep = arc[3]
    return math.tan(math.radians(sweep) / 4)


def write(doc: Document, path) -> None:
    out = ezdxf.new('R2010', setup=True)
    out.header['$INSUNITS'] = 4          # mm
    msp = out.modelspace()
    from . import plate_note
    note = plate_note.to_text(doc.plate)
    if note:                                             # la plaque : notée dans le dessin, et ses limites
        out.header.custom_vars.append(plate_note.TAG, note)
        msp.reset_limits((doc.plate.x, doc.plate.y), (doc.plate.x + doc.plate.width, doc.plate.y + doc.plate.height))
    from ezdxf.colors import rgb2int
    from . import colors as io_colors
    from .colors import nearest_aci, rgb_of
    aci: dict = {}
    per_tool = isinstance(doc.extra, dict) and bool(doc.extra.get('dxf_calques_outils'))
    for L in doc.layers:
        if L.name not in out.layers and not per_tool:
            out.layers.add(L.name)
        for it in _leaves(L.items):
            p = getattr(it, 'path', None) or getattr(it, 'outline', None)
            if not p or not it.visible:
                continue
            col = doc.tool_color(int(it.tool)).lower()       # couleur de l'outil : gardée (r548)
            if isinstance(it.extra, dict) and it.extra.get('couleur'):
                col = doc.item_color(it).lower()             # sa couleur propre, si l'objet en a une
            if col not in aci:
                aci[col] = nearest_aci(col)
            layer = L.name
            if per_tool:                                 # un calque par outil, de sa couleur (FAO par calque)
                layer = f'Outil {int(it.tool) + 1}'
                if layer not in out.layers:
                    out.layers.add(layer, color=aci[col])
            attribs = {'layer': layer, 'color': aci[col]}
            if col != '#000000' or io_colors.DXF_BLACK_TRUE:  # le noir aussi : TypeEdit rend le 7 seul en blanc
                attribs['true_color'] = rgb2int(rgb_of(col))
            if io_colors.DXF_ARCS:                        # droites et arcs seulement : lus partout de même
                from ..core import biarc
                p = biarc.to_arcs(p, io_colors.DXF_ARC_TOL)
            for c in p.contours:
                _write_contour(msp, c, attribs)
    out.saveas(str(path))


def _leaves(items):
    """Objets feuilles visibles (un groupe masqué masque ses enfants)."""
    for it in items:
        if not it.visible:
            continue
        if isinstance(it, Group):
            yield from _leaves(it.children)
        else:
            yield it


def full_circle(c: Contour, tol: float = 1e-6) -> tuple[Point, float] | None:
    """(centre, rayon) si le contour est un cercle complet fait d'arcs (un
    trou à percer ou tarauder) ; None sinon."""
    if not c.closed or not c.segments or dist(c.end, c.start) > tol:
        return None
    total, center, r = 0.0, None, None
    for s in c.segments:
        if not isinstance(s, Conic):
            return None
        arc = s.circle_params()
        if not arc:
            return None
        (cx, cy), rr, _a0, sweep = arc
        if center is None:
            center, r = (cx, cy), rr
        elif dist(center, (cx, cy)) > tol * max(1.0, r) or abs(rr - r) > tol * max(1.0, r):
            return None
        if total and (sweep > 0) != (total > 0):
            return None
        total += sweep
    return (center, r) if abs(abs(total) - 360.0) < 1e-6 else None


def _write_contour(msp, c: Contour, attribs) -> None:
    if not c.segments:
        return
    circ = full_circle(c)
    if circ is not None:
        # un vrai CIRCLE : centre et rayon exacts pour les logiciels de FAO
        # (NeoDrive y reconnaît un trou à percer ou tarauder)
        msp.add_circle(circ[0], circ[1], dxfattribs=attribs)
        return
    bulges: list[float] = []
    ok = True
    for s in c.segments:
        if isinstance(s, Line):
            bulges.append(0.0)
        elif isinstance(s, Conic):
            b = _bulge_of(s)
            if b is None:
                ok = False
                break
            bulges.append(b)
        else:
            ok = False
            break
    if ok:
        pts = [(s.start[0], s.start[1], b) for s, b in zip(c.segments, bulges)]
        closed = c.closed and dist(c.end, c.start) < 1e-6
        if not closed:
            pts.append((c.end[0], c.end[1], 0.0))
        msp.add_lwpolyline(pts, format='xyb', close=closed, dxfattribs=attribs)
        return
    # contour courbe : une seule SPLINE cubique (les droites deviennent des
    # Bézier dégénérées), pour qu'un contour reste une entité
    from ezdxf.math import Bezier4P as _B4, Vec3, bezier_to_bspline

    def Bezier4P(pts):
        return _B4([Vec3(q[0], q[1], 0) for q in pts])
    curves = []
    for s in c.segments:
        if isinstance(s, Line):
            p0, p1 = s.p0, s.p1
            curves.append(Bezier4P([p0, _lerp(p0, p1, 1 / 3), _lerp(p0, p1, 2 / 3), p1]))
        elif isinstance(s, Cubic):
            curves.append(Bezier4P([s.p0, s.p1, s.p2, s.p3]))
        elif isinstance(s, Conic):
            for cb in s.to_cubics():
                curves.append(Bezier4P([cb.p0, cb.p1, cb.p2, cb.p3]))
    if c.closed and dist(c.end, c.start) > 1e-9:
        curves.append(Bezier4P([c.end, _lerp(c.end, c.start, 1 / 3),
                                _lerp(c.end, c.start, 2 / 3), c.start]))
    spline = msp.add_spline(dxfattribs=attribs)
    spline.apply_construction_tool(bezier_to_bspline(curves))
    if c.closed:
        spline.closed = True


def _lerp(p, q, t):
    return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)
