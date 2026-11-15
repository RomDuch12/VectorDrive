"""Le dessin en volume, pour « Enregistrer sous » : STEP, STL et 3D XML.

Ce qui part dans le fichier :

* les **volumes** de l'onglet 3D, tels quels (en STEP : en facettes planes) ;
* les **reliefs**, posés sur un socle (STL et 3D XML ; pas en STEP) ;
* les **formes fermées** du dessin, tirées de l'épaisseur de la plaque (3 mm quand elle n'en a pas), le dessus à Z 0
  comme sur la machine ; règle pair-impair : un contour dans un autre est un trou, un contour dans ce trou une île.

En STEP, les formes fermées sont de vrais solides (AP214, `MANIFOLD_SOLID_BREP`) : un plan par segment droit, un
cylindre par arc de cercle (un trou rond reste un trou rond pour le logiciel de CAO), une surface d'extrusion par
courbe de Bézier ou arc d'ellipse. Des contours qui se croisent ou se touchent sont d'abord réunis (pair-impair) en
polygones : le solide reste juste, ses flancs sont alors des facettes.

3D XML : écrit d'après le schéma publié par Dassault (représentation tessellée, `PolygonalRepType`), relu par
VectorDrive.
"""
from __future__ import annotations

import math
import pathlib

from ..cam.tooldraw import _ascii, _f
from ..core.document import Image
from ..core.geom import Conic, Contour, Cubic, Line
from .step_solids import _axis, _line_edge, _oe

DEFAULT_THICKNESS = 3.0          # mm : plaque sans épaisseur
BASE = 2.0                       # mm : socle sous un relief
MAX_CELLS = 1_000_000            # points d'un relief en STL
MAX_CELLS_XML = 250_000          # … en 3D XML (du texte : dix fois plus lourd)
MAX_FACETS = 100_000             # facettes d'un STEP : au-delà, aucun logiciel de CAO ne l'ouvre en un temps raisonnable
GREY = (0.62, 0.64, 0.68)
FLAT = 0.01                      # mm : écart de corde des courbes aplaties (maillages, inclusions)


class Nothing3D(ValueError):
    """Rien à écrire en volume, ou trop pour ce format."""


# --- ce que le dessin donne en volume -----------------------------------------------------------------------------
def thickness(doc) -> float:
    """Épaisseur dont les formes fermées sont tirées : celle de la plaque, 3 mm sans elle."""
    e = float(getattr(doc.plate, 'thickness', 0.0) or 0.0) if doc.plate is not None else 0.0
    return e if e > 1e-6 else DEFAULT_THICKNESS


def _rgb(color) -> tuple:
    if not color:
        return GREY
    return tuple(int(color[k:k + 2], 16) / 255.0 for k in (1, 3, 5))


#: marques des cotes (les nôtres, celles lues dans TypeEdit) : elles renseignent le dessin, pas la pièce
DIMENSIONS = ('cote', 'cotation')


def _part_leaves(doc):
    """Objets visibles du dessin, groupes dépliés, sans les cotes."""
    def walk(items):
        for it in items:
            extra = it.extra if isinstance(getattr(it, 'extra', None), dict) else {}
            if not getattr(it, 'visible', True) or any(extra.get(k) for k in DIMENSIONS):
                continue
            children = getattr(it, 'children', None)
            if children is not None:
                yield from walk(children)
            else:
                yield it
    for layer in doc.layers:
        if getattr(layer, 'visible', True):
            yield from walk(layer.items)


def _closed(c) -> bool:
    """Contour fermé, ou dont les bouts se rejoignent (dessins importés)."""
    return bool(c.segments) and (c.closed or (len(c.segments) > 1 and math.dist(c.start, c.end) < 1e-6))


def flat_paths(doc) -> list:
    """[(tracé, couleur)] des objets à plat visibles — ni volume, ni relief, ni cote — qui ont un contour fermé."""
    from ..cam.strategies import item_geometry
    from ..core import solids as SO
    from ..core.document import own_color
    out = []
    for it in _part_leaves(doc):
        if SO.is_solid(it) or isinstance(it, Image):
            continue
        p = item_geometry(it)
        if p is not None and any(_closed(c) for c in p.contours):
            out.append((p, _rgb(own_color(it))))
    return out


def volumes(doc) -> list:
    """Les volumes visibles du dessin (core.solids.Solid), placés."""
    from ..core import solids as SO
    return [s for _it, s in SO.doc_solids(doc) if not s.is_empty()]


def relief_meshes(doc, max_cells: int = MAX_CELLS) -> list:
    """Maillages fermés des reliefs visibles (carte de hauteurs sur un socle de `BASE` mm)."""
    import numpy as np
    from ..core import galbe as GB
    from . import stl_write as STL
    out = []
    for it in doc.iter_leaves(visible_only=True):
        if isinstance(it, Image) and isinstance(it.extra, dict) and 'galbe' in it.extra:
            got = GB.decode(it)
            if got is None:
                continue
            H, x0, y1, res = got
            stride = max(1, int(np.ceil(np.sqrt(H.size / max(1000, int(max_cells))))))
            out.append(STL.heightmap_mesh(H, x0, y1, res, BASE, stride))
    return out


def flat_mesh(doc):
    """Maillage fermé des formes fermées tirées de l'épaisseur (de −e à 0), ou None."""
    from . import stl_write as STL
    reg = flat_region(doc)
    if reg is None or reg.is_empty:
        return None
    e = thickness(doc)
    T = STL.extrude_mesh(reg, e, -e)
    return T if len(T) else None


def _nothing() -> Nothing3D:
    from ..i18n import tr
    return Nothing3D(tr('Rien à écrire en volume : le dessin n\'a ni volume, ni relief, ni forme fermée.'))


def bodies(doc, max_cells: int = MAX_CELLS) -> list:
    """[(genre, nom, triangles (n, 3, 3), couleur)] : volumes, reliefs, formes fermées tirées ('dessin')."""
    out = [('volume', s.name or f'Volume {k + 1}', s.triangles(), tuple(s.color)[:3])
           for k, s in enumerate(volumes(doc))]
    out += [('relief', f'Relief {k + 1}', T, GREY) for k, T in enumerate(relief_meshes(doc, max_cells))]
    T = flat_mesh(doc)
    if T is not None:
        out.append(('dessin', 'Dessin', T, GREY))
    if not out:
        raise _nothing()
    return out


def _note_bodies(doc, parts: list) -> None:
    kinds = [k for k, _n, _t, _c in parts]
    _note(doc, kinds.count('volume'), kinds.count('relief'), 'dessin' in kinds)


def _note(doc, n_vol: int, n_rel: int, flat: bool) -> None:
    """Ce qui est parti, pour la barre d'état."""
    from ..i18n import tr
    bits = []
    if n_vol:
        bits.append(tr('{0} volume(s)').format(n_vol))
    if n_rel:
        bits.append(tr('{0} relief(s)').format(n_rel))
    if flat:
        bits.append(tr('formes fermées tirées de {0} mm').format(f'{thickness(doc):g}'))
    doc.report.append(tr('en volume : {0}').format(', '.join(bits)))


# --- STL ------------------------------------------------------------------------------------------------------
def write_stl(doc, path) -> None:
    import numpy as np
    from . import stl_write as STL
    parts = bodies(doc)
    STL.write_stl(path, np.concatenate([T for _k, _n, T, _c in parts]),
                  _ascii(pathlib.Path(path).stem) or 'VectorDrive')
    _note_bodies(doc, parts)


# --- 3D XML ---------------------------------------------------------------------------------------------------
NS = ('xmlns="http://www.3ds.com/xsd/3DXML" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
      'xmlns:xlink="http://www.w3.org/1999/xlink"')


def _triples(A) -> str:
    """(n, 3) → 'x y z,x y z…'."""
    import io
    import numpy as np
    buf = io.StringIO()
    np.savetxt(buf, np.asarray(A, float).reshape(-1, 3), fmt='%.6g', delimiter=' ', newline=',')
    return buf.getvalue().rstrip(',')


def _rep(k: int, tris, color) -> str:
    """Une représentation polygonale : trois sommets par triangle (arêtes vives), leurs normales."""
    import numpy as np
    T = np.asarray(tris, float).reshape(-1, 3, 3)
    N = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    L = np.linalg.norm(N, axis=1)
    keep = L > 1e-12
    T, N = T[keep], N[keep] / L[keep][:, None]
    r, g, b = (f'{float(v):.4g}' for v in color[:3])
    idx = ' '.join(map(str, range(3 * len(T))))
    return (f'<Rep xsi:type="PolygonalRepType" id="{k}" accuracy="{FLAT:g}" solid="1">'
            f'<Faces><Face triangles="{idx}"><SurfaceAttributes>'
            f'<Color xsi:type="RGBAColorType" red="{r}" green="{g}" blue="{b}" alpha="1"/>'
            f'</SurfaceAttributes></Face></Faces>'
            f'<VertexBuffer><Positions>{_triples(T)}</Positions>'
            f'<Normals>{_triples(np.repeat(N, 3, axis=0))}</Normals></VertexBuffer></Rep>')


def write_3dxml(doc, path) -> None:
    import zipfile
    from datetime import datetime
    parts = bodies(doc, MAX_CELLS_XML)
    name = _ascii(pathlib.Path(path).stem).replace('&', ' ').replace('<', ' ').replace('>', ' ').replace('"', ' ') \
        .strip() or 'piece'
    head = '<?xml version="1.0" encoding="utf-8"?>\n'
    reps = ''.join(_rep(k + 2, T, c) for k, (_kind, _n, T, c) in enumerate(parts))
    rep = f'{head}<XMLRepresentation version="1.2" {NS}><Root xsi:type="BagRepType" id="1">{reps}</Root>' \
          f'</XMLRepresentation>\n'
    product = (f'{head}<Model_3dxml {NS}><Header><SchemaVersion>4.3</SchemaVersion><Title>{name}</Title>'
               f'<Generator>VectorDrive</Generator><Created>{datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}</Created>'
               f'</Header><ProductStructure root="1">'
               f'<Reference3D xsi:type="Reference3DType" id="1" name="{name}"/>'
               f'<ReferenceRep xsi:type="ReferenceRepType" id="2" name="{name}_rep" format="TESSELLATED" '
               f'version="1.2" associatedFile="urn:3DXML:{name}.3DRep"/>'
               f'<InstanceRep xsi:type="InstanceRepType" id="3" name="{name}_rep.1"><IsAggregatedBy>1</IsAggregatedBy>'
               f'<IsInstanceOf>2</IsInstanceOf></InstanceRep></ProductStructure></Model_3dxml>\n')
    manifest = (f'{head}<Manifest xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                f'xsi:noNamespaceSchemaLocation="Manifest.xsd"><Root>{name}.3dxml</Root>'
                f'<WithAuthoringData>false</WithAuthoringData></Manifest>\n')
    tmp = str(path) + '.tmp'
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('Manifest.xml', manifest)
        z.writestr(f'{name}.3dxml', product)
        z.writestr(f'{name}.3DRep', rep)
    pathlib.Path(tmp).replace(path)
    _note_bodies(doc, parts)


def write_mesh(doc, path) -> None:
    """STL ou 3D XML, selon l'extension."""
    (write_3dxml if str(path).lower().endswith('.3dxml') else write_stl)(doc, path)


# --- STEP : contours → boucles orientées ------------------------------------------------------------------------
def _null(s) -> bool:
    pts = [s.p0, s.p1] + ([s.p2] if hasattr(s, 'p2') else []) + ([s.p3] if hasattr(s, 'p3') else [])
    return all(math.dist(pts[0], p) < 1e-9 for p in pts[1:])


def _clean(c: Contour) -> list:
    """Segments d'un contour fermé : sans segment nul, refermé par une droite s'il ne l'est pas."""
    segs = [s for s in c.segments if not _null(s)]
    if segs and math.dist(segs[-1].end, segs[0].start) > 1e-9:
        segs.append(Line(segs[-1].end, segs[0].start))
    return segs


def _reversed(segs: list) -> list:
    return [s.reversed() for s in reversed(segs)]


#: deux contours de même aire sont le même quand leurs encombrements ne diffèrent pas de plus (mm)
DUPLICATE = 1e-3


def loops_of(doc) -> list:
    """[(segments, couleur)] de chaque contour fermé des objets à plat. Un contour sans aire est écarté ; un contour
    posé deux fois (doublon) ne compte qu'une fois — deux fois, la règle pair-impair l'effacerait."""
    from shapely.geometry import Polygon
    out, seen = [], {}
    for p, color in flat_paths(doc):
        for c in p.contours:
            if not _closed(c):
                continue
            segs = _clean(c)
            if not segs:
                continue
            pts = Contour(segs, True).flatten(FLAT)
            if len(pts) < 4:
                continue
            poly = Polygon(pts)
            if poly.area < 1e-6:
                continue
            if poly.is_valid:                            # doublon : même aire au même endroit, à un rien près
                area, box = poly.area, poly.bounds
                eps = 1e-6 * max(1.0, area)
                cx, cy = math.floor(poly.centroid.x), math.floor(poly.centroid.y)
                near = [q for dx in (-1, 0, 1) for dy in (-1, 0, 1) for q in seen.get((cx + dx, cy + dy), ())]
                # la différence symétrique coûte : seulement contre ceux de même aire ET de même encombrement (des
                # points identiques posés côte à côte ont la même aire, pas la même place)
                if any(abs(a - area) < eps and max(abs(u - v) for u, v in zip(b, box)) < DUPLICATE
                       and q.symmetric_difference(poly).area < eps for a, b, q in near):
                    continue
                seen.setdefault((cx, cy), []).append((area, box, poly))
            out.append((segs, color))
    return out


def flat_region(doc, loops=None):
    """Région shapely (pair-impair) des formes fermées, doublons écartés ; None sans forme fermée. `loops` : les
    contours déjà relevés (`loops_of`), pour ne pas les relever deux fois."""
    from ..cam import strategies as S
    lines = []
    for segs, _c in (loops_of(doc) if loops is None else loops):
        pts = list(Contour(segs, True).flatten(FLAT))
        if math.dist(pts[0], pts[-1]) > 1e-9:
            pts.append(pts[0])
        lines.append((pts, True))
    return S.region_from_lines(lines) if lines else None


def nested(loops: list):
    """[(extérieur, [trous], couleur)] — l'extérieur dans le sens direct, les trous dans le sens horaire : la matière
    est toujours à gauche du parcours. None quand des contours se croisent, se touchent ou se recoupent eux-mêmes
    (à réunir d'abord : `polygons`)."""
    import shapely
    from shapely.geometry import Polygon
    polys = []
    for segs, _c in loops:
        pts = Contour(segs, True).flatten(FLAT)
        if len(pts) < 4:
            return None
        poly = Polygon(pts)
        if not poly.is_valid or poly.area < 1e-9:
            return None
        polys.append(poly)
    tree = shapely.STRtree(polys)
    inside = [[] for _ in polys]                     # les contours qui contiennent celui-ci
    for i, p in enumerate(polys):
        for j in tree.query(p):
            j = int(j)
            if j == i:
                continue
            q = polys[j]
            if shapely.contains_properly(q, p):
                inside[i].append(j)
            elif not shapely.contains_properly(p, q) and p.intersects(q):
                return None
    out, index = [], {}
    for i in sorted(range(len(polys)), key=lambda k: len(inside[k])):
        segs, color = loops[i]
        ccw = polys[i].exterior.is_ccw
        if len(inside[i]) % 2 == 0:
            index[i] = len(out)
            out.append((segs if ccw else _reversed(segs), [], color))
        else:
            parent = min(inside[i], key=lambda k: polys[k].area)     # le plus petit contour qui le contient
            if parent not in index:
                return None
            out[index[parent]][1].append(_reversed(segs) if ccw else segs)
    return out


def polygons(doc, loops=None) -> list:
    """Les formes fermées réunies (pair-impair) en polygones : [(extérieur, [trous], couleur)] en segments droits."""
    from shapely.geometry.polygon import orient
    reg = flat_region(doc, loops)
    out = []
    for poly in (getattr(reg, 'geoms', [reg]) if reg is not None else []):
        if poly.geom_type != 'Polygon' or poly.is_empty:
            continue
        poly = orient(poly, 1.0)                         # extérieur direct, trous horaires
        rings = [list(poly.exterior.coords)] + [list(r.coords) for r in poly.interiors]
        loops = [[Line(a, b) for a, b in zip(r, r[1:]) if math.dist(a, b) > 1e-9] for r in rings]
        if len(loops[0]) >= 3:
            out.append((loops[0], [lp for lp in loops[1:] if len(lp) >= 3], GREY))
    return out


def prisms(doc) -> list:
    """Les formes fermées en prismes à tirer : contours exacts s'ils s'emboîtent sans se toucher, polygones sinon."""
    loops = loops_of(doc)
    if not loops:
        return []
    got = nested(loops)
    return got if got is not None else polygons(doc, loops)


# --- STEP : faces -----------------------------------------------------------------------------------------------
def circle_of(s: Conic):
    """(cx, cy, r, sens direct) quand la conique est un arc de cercle, sinon None."""
    (x0, y0), (x1, y1), (x2, y2) = s.p0, s.p1, s.p2
    a, b, chord = math.hypot(x1 - x0, y1 - y0), math.hypot(x1 - x2, y1 - y2), math.hypot(x2 - x0, y2 - y0)
    if chord < 1e-9 or a < 1e-9 or abs(a - b) > 1e-7 * max(1.0, a) or not 0.0 < s.w < 1.0:
        return None
    cos_half = chord / (2.0 * a)                         # l'angle entre la corde et la tangente : la moitié de l'arc
    if abs(s.w - cos_half) > 1e-7 or cos_half >= 1.0 - 1e-12:
        return None
    sin_half = math.sqrt(1.0 - cos_half * cos_half)
    r = chord / (2.0 * sin_half)
    mx, my = (x0 + x2) / 2.0, (y0 + y2) / 2.0
    d = math.hypot(mx - x1, my - y1)
    if d < 1e-12:
        return None
    cx, cy = mx + (mx - x1) / d * r * cos_half, my + (my - y1) / d * r * cos_half
    return cx, cy, r, (x0 - cx) * (y2 - cy) - (y0 - cy) * (x2 - cx) > 0


def _face(st, loops, surf: str, same: bool = True) -> str:
    """Face : la première boucle extérieure, les autres des trous ; `same` : la normale de la surface sort de la
    matière (sinon la face la retourne — un trou rond : son cylindre regarde vers l'axe)."""
    bounds = []
    for k, edges in enumerate(loops):
        lp = st.e(f"EDGE_LOOP('',({','.join(edges)}))")
        bounds.append(st.e(f"{'FACE_OUTER_BOUND' if k == 0 else 'FACE_BOUND'}('',{lp},.T.)"))
    return st.e(f"ADVANCED_FACE('',({','.join(bounds)}),{surf},{'.T.' if same else '.F.'})")


def _curve(st, s, a, b, z: float) -> str:
    """La courbe de Bézier ou la conique à la hauteur z, ses extrémités posées sur les sommets a et b."""
    if isinstance(s, Cubic):
        refs = ','.join(st.pt(x, y, z) for x, y in (a, s.p1, s.p2, b))
        return st.e(f"B_SPLINE_CURVE_WITH_KNOTS('',3,({refs}),.UNSPECIFIED.,.F.,.F.,(4,4),(0.,1.),.UNSPECIFIED.)")
    refs = ','.join(st.pt(x, y, z) for x, y in (a, s.p1, b))
    if abs(s.w - 1.0) < 1e-12:
        return st.e(f"B_SPLINE_CURVE_WITH_KNOTS('',2,({refs}),.UNSPECIFIED.,.F.,.F.,(3,3),(0.,1.),.UNSPECIFIED.)")
    return st.e(f"(BOUNDED_CURVE()B_SPLINE_CURVE(2,({refs}),.UNSPECIFIED.,.F.,.F.)"
                f"B_SPLINE_CURVE_WITH_KNOTS((3,3),(0.,1.),.UNSPECIFIED.)CURVE()GEOMETRIC_REPRESENTATION_ITEM()"
                f"RATIONAL_B_SPLINE_CURVE((1.,{_f(s.w)},1.))REPRESENTATION_ITEM(''))")


def _loop_faces(st, segs: list, z0: float, z1: float):
    """Flancs d'un contour dont la matière est à gauche du parcours : (faces, arêtes du bas, arêtes du haut)."""
    n = len(segs)
    P = [s.start for s in segs]
    vb = [st.e(f"VERTEX_POINT('',{st.pt(x, y, z0)})") for x, y in P]
    vt = [st.e(f"VERTEX_POINT('',{st.pt(x, y, z1)})") for x, y in P]
    ev = [_line_edge(st, (x, y, z0), (x, y, z1), vb[i], vt[i]) for i, (x, y) in enumerate(P)]
    eb, et, faces = [], [], []
    for i, s in enumerate(segs):
        j = (i + 1) % n
        a, b = P[i], P[j]
        same = True
        arc = circle_of(s) if isinstance(s, Conic) else None
        if isinstance(s, Line):
            e0 = _line_edge(st, (*a, z0), (*b, z0), vb[i], vb[j])
            e1 = _line_edge(st, (*a, z1), (*b, z1), vt[i], vt[j])
            dx, dy = b[0] - a[0], b[1] - a[1]
            L = math.hypot(dx, dy) or 1.0
            surf = st.e(f"PLANE('',{_axis(st, (*a, z0), (dy / L, -dx / L, 0.0), (dx / L, dy / L, 0.0))})")
        elif arc is not None:
            cx, cy, r, same = arc
            sense = '.T.' if same else '.F.'             # le cercle tourne dans le sens direct
            c0 = st.e(f"CIRCLE('',{_axis(st, (cx, cy, z0), (0, 0, 1), (1, 0, 0))},{_f(r)})")
            c1 = st.e(f"CIRCLE('',{_axis(st, (cx, cy, z1), (0, 0, 1), (1, 0, 0))},{_f(r)})")
            e0 = st.e(f"EDGE_CURVE('',{vb[i]},{vb[j]},{c0},{sense})")
            e1 = st.e(f"EDGE_CURVE('',{vt[i]},{vt[j]},{c1},{sense})")
            surf = st.e(f"CYLINDRICAL_SURFACE('',{_axis(st, (cx, cy, z0), (0, 0, 1), (1, 0, 0))},{_f(r)})")
        else:
            c0, c1 = _curve(st, s, a, b, z0), _curve(st, s, a, b, z1)
            e0 = st.e(f"EDGE_CURVE('',{vb[i]},{vb[j]},{c0},.T.)")
            e1 = st.e(f"EDGE_CURVE('',{vt[i]},{vt[j]},{c1},.T.)")
            vec = st.e(f"VECTOR('',{st.dr(0, 0, 1)},{_f(z1 - z0)})")
            surf = st.e(f"SURFACE_OF_LINEAR_EXTRUSION('',{c0},{vec})")      # normale : à droite du parcours
        eb.append(e0)
        et.append(e1)
        faces.append(_face(st, [[_oe(st, e0, True), _oe(st, ev[j], True), _oe(st, e1, False), _oe(st, ev[i], False)]],
                           surf, same))
    return faces, eb, et


def prism_faces(st, outer: list, holes: list, z0: float, z1: float) -> list:
    """Faces du prisme : flancs de chaque contour, dessous et dessus percés des trous."""
    faces, tops, bottoms = [], [], []
    for segs in [outer] + list(holes):
        f, eb, et = _loop_faces(st, segs, z0, z1)
        faces += f
        tops.append([_oe(st, e, True) for e in et])
        bottoms.append([_oe(st, e, False) for e in reversed(eb)])
    x, y = outer[0].start
    faces.append(_face(st, bottoms, st.e(f"PLANE('',{_axis(st, (x, y, z0), (0, 0, -1), (1, 0, 0))})")))
    faces.append(_face(st, tops, st.e(f"PLANE('',{_axis(st, (x, y, z1), (0, 0, 1), (1, 0, 0))})")))
    return faces


def facet_faces(st, solid) -> list:
    """Un volume maillé en facettes planes : sommets et arêtes partagés (coque fermée)."""
    import numpy as np
    V = np.asarray(solid.verts, float)
    verts, edges, faces = {}, {}, []

    def vertex(k: int) -> str:
        if k not in verts:
            verts[k] = st.e(f"VERTEX_POINT('',{st.pt(*V[k])})")
        return verts[k]
    for a, b, c in np.asarray(solid.tris, int).tolist():
        nrm = np.cross(V[b] - V[a], V[c] - V[a])
        L = float(np.linalg.norm(nrm))
        if L < 1e-12:
            continue
        loop = []
        for u, v in ((a, b), (b, c), (c, a)):
            key = (u, v) if u < v else (v, u)
            if key not in edges:
                edges[key] = _line_edge(st, tuple(V[key[0]]), tuple(V[key[1]]), vertex(key[0]), vertex(key[1]))
            loop.append(_oe(st, edges[key], u < v))
        d = V[b] - V[a]
        d = d / (float(np.linalg.norm(d)) or 1.0)
        faces.append(_face(st, [loop], st.e(f"PLANE('',{_axis(st, tuple(V[a]), tuple(nrm / L), tuple(d))})")))
    return faces


def step_text(doc, name: str = 'piece') -> str:
    """Le texte STEP du dessin : un solide par forme fermée (et ses trous), un par volume."""
    from ..i18n import tr
    from . import step_solids as SS
    vols = volumes(doc)
    n_facets = sum(len(s.tris) for s in vols)
    if n_facets > MAX_FACETS:
        raise Nothing3D(tr('Volumes trop fins pour un STEP ({0} facettes, {1} au plus) : enregistrez en STL.')
                        .format(n_facets, MAX_FACETS))
    flat = prisms(doc)
    if not vols and not flat:
        raise _nothing()
    e = thickness(doc)

    def extra(st):
        out = [(f'Forme {k + 1}', prism_faces(st, outer, holes, -e, 0.0), color)
               for k, (outer, holes, color) in enumerate(flat)]
        out += [(s.name or f'Volume {k + 1}', facet_faces(st, s), tuple(s.color)[:3]) for k, s in enumerate(vols)]
        return out
    text = SS.step_text([], name, title='VectorDrive', extra=extra)
    _note(doc, len(vols), 0, bool(flat))
    return text


def write_step(doc, path) -> None:
    text = step_text(doc, _ascii(pathlib.Path(path).stem) or 'piece')
    tmp = str(path) + '.tmp'
    with open(tmp, 'w', encoding='ascii', newline='\n') as f:
        f.write(text)
    pathlib.Path(tmp).replace(path)
