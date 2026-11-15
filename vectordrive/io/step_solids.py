"""STEP (AP214) de volumes simples — pavés tournés autour de Z et cylindres
d'axe Z — en vraies faces (plans, cylindres) : un solide par volume, nommé
et coloré, que tout logiciel de CAO ouvre et modifie (matériel de serrage,
machines : `core.workspace.to_step`).

Volume : {'kind': 'box', 'corners': [(x, y)…4], 'z0', 'z1'} ou
{'kind': 'cyl', 'cx', 'cy', 'r', 'z0', 'z1'}, plus 'name' et 'color'
(r, g, b entre 0 et 1)."""
from __future__ import annotations

import math
from datetime import datetime

from ..cam.tooldraw import _Step, _ascii, _f

GREY = (0.62, 0.64, 0.68)


def _axis(st: _Step, p, n, ref) -> str:
    return st.e(f"AXIS2_PLACEMENT_3D('',{st.pt(*p)},{st.dr(*n)},{st.dr(*ref)})")


def _oe(st: _Step, edge: str, same: bool) -> str:
    return st.e(f"ORIENTED_EDGE('',*,*,{edge},{'.T.' if same else '.F.'})")


def _face(st: _Step, loops, surf: str) -> str:
    """Face plane ou courbe : la première boucle extérieure, les autres des trous."""
    bounds = []
    for k, edges in enumerate(loops):
        lp = st.e(f"EDGE_LOOP('',({','.join(edges)}))")
        bounds.append(st.e(f"{'FACE_OUTER_BOUND' if k == 0 else 'FACE_BOUND'}('',{lp},.T.)"))
    return st.e(f"ADVANCED_FACE('',({','.join(bounds)}),{surf},.T.)")


def _line_edge(st: _Step, a, b, va: str, vb: str) -> str:
    d = [b[i] - a[i] for i in range(3)]
    L = math.sqrt(sum(v * v for v in d)) or 1.0
    vec = st.e(f"VECTOR('',{st.dr(*(v / L for v in d))},{_f(L)})")      # entité à part (ISO 10303-21)
    ln = st.e(f"LINE('',{st.pt(*a)},{vec})")
    return st.e(f"EDGE_CURVE('',{va},{vb},{ln},.T.)")


def _box(st: _Step, corners, z0: float, z1: float) -> list[str]:
    """Faces d'un pavé : quatre coins (x, y) — remis dans le sens direct —, bas z0, haut z1."""
    c = [(float(x), float(y)) for x, y in corners]
    area = sum(c[i][0] * c[(i + 1) % 4][1] - c[(i + 1) % 4][0] * c[i][1] for i in range(4))
    if area < 0:
        c = c[::-1]
    lo = [(x, y, z0) for x, y in c]
    up = [(x, y, z1) for x, y in c]
    vlo = [st.e(f"VERTEX_POINT('',{st.pt(*p)})") for p in lo]
    vup = [st.e(f"VERTEX_POINT('',{st.pt(*p)})") for p in up]
    eb = [_line_edge(st, lo[i], lo[(i + 1) % 4], vlo[i], vlo[(i + 1) % 4]) for i in range(4)]
    et = [_line_edge(st, up[i], up[(i + 1) % 4], vup[i], vup[(i + 1) % 4]) for i in range(4)]
    ev = [_line_edge(st, lo[i], up[i], vlo[i], vup[i]) for i in range(4)]
    faces = [_face(st, [[_oe(st, eb[i], False) for i in (3, 2, 1, 0)]],
                   st.e(f"PLANE('',{_axis(st, lo[0], (0, 0, -1), (1, 0, 0))})")),
             _face(st, [[_oe(st, et[i], True) for i in range(4)]],
                   st.e(f"PLANE('',{_axis(st, up[0], (0, 0, 1), (1, 0, 0))})"))]
    for i in range(4):
        j = (i + 1) % 4
        dx, dy = c[j][0] - c[i][0], c[j][1] - c[i][1]
        L = math.hypot(dx, dy) or 1.0
        n = (dy / L, -dx / L, 0.0)                       # vers l'extérieur (coins dans le sens direct)
        surf = st.e(f"PLANE('',{_axis(st, lo[i], n, (dx / L, dy / L, 0.0))})")
        faces.append(_face(st, [[_oe(st, eb[i], True), _oe(st, ev[j], True), _oe(st, et[i], False),
                                 _oe(st, ev[i], False)]], surf))
    return faces


def _cyl(st: _Step, cx: float, cy: float, r: float, z0: float, z1: float) -> list[str]:
    """Faces d'un cylindre d'axe Z : disque du bas, surface, disque du haut."""
    va = st.e(f"VERTEX_POINT('',{st.pt(cx + r, cy, z0)})")
    vb = st.e(f"VERTEX_POINT('',{st.pt(cx + r, cy, z1)})")
    circles = []
    for v, z in ((va, z0), (vb, z1)):
        ax = _axis(st, (cx, cy, z), (0, 0, 1), (1, 0, 0))
        circ = st.e(f"CIRCLE('',{ax},{_f(r)})")
        circles.append(st.e(f"EDGE_CURVE('',{v},{v},{circ},.T.)"))
    ca, cb = circles
    seam = _line_edge(st, (cx + r, cy, z0), (cx + r, cy, z1), va, vb)
    return [_face(st, [[_oe(st, ca, False)]], st.e(f"PLANE('',{_axis(st, (cx, cy, z0), (0, 0, -1), (1, 0, 0))})")),
            _face(st, [[_oe(st, ca, True), _oe(st, seam, True), _oe(st, cb, False), _oe(st, seam, False)]],
                  st.e(f"CYLINDRICAL_SURFACE('',{_axis(st, (cx, cy, z0), (0, 0, 1), (1, 0, 0))},{_f(r)})")),
            _face(st, [[_oe(st, cb, True)]], st.e(f"PLANE('',{_axis(st, (cx, cy, z1), (0, 0, 1), (1, 0, 0))})"))]


def step_text(solids, name: str = 'espace', *, title: str = 'VectorDrive - espace de travail', extra=None) -> str:
    """Le texte STEP des volumes `solids` (voir le module) ; les volumes
    plats ou vides sont omis. `extra(st)` : d'autres solides, déjà en faces — [(nom, faces, couleur)] (`io.write3d`)."""
    st = _Step()
    nom = _ascii(name) or 'espace'
    ctx = st.e("APPLICATION_CONTEXT('core data for automotive mechanical design processes')")
    st.e(f"APPLICATION_PROTOCOL_DEFINITION('international standard','automotive_design',2000,{ctx})")
    pctx = st.e(f"PRODUCT_CONTEXT('',{ctx},'mechanical')")
    prod = st.e(f"PRODUCT('{nom}','{nom}','',({pctx}))")
    st.e(f"PRODUCT_RELATED_PRODUCT_CATEGORY('part',$,({prod}))")
    pdf = st.e(f"PRODUCT_DEFINITION_FORMATION('','',{prod})")
    pdc = st.e(f"PRODUCT_DEFINITION_CONTEXT('part definition',{ctx},'design')")
    pd = st.e(f"PRODUCT_DEFINITION('design','',{pdf},{pdc})")
    pds = st.e(f"PRODUCT_DEFINITION_SHAPE('','',{pd})")
    lg = st.e("(LENGTH_UNIT()NAMED_UNIT(*)SI_UNIT(.MILLI.,.METRE.))")
    an = st.e("(NAMED_UNIT(*)PLANE_ANGLE_UNIT()SI_UNIT($,.RADIAN.))")
    so = st.e("(NAMED_UNIT(*)SI_UNIT($,.STERADIAN.)SOLID_ANGLE_UNIT())")
    unc = st.e(f"UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-07),{lg},'distance_accuracy_value',"
               f"'confusion accuracy')")
    rctx = st.e(f"(GEOMETRIC_REPRESENTATION_CONTEXT(3)GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT(({unc}))"
                f"GLOBAL_UNIT_ASSIGNED_CONTEXT(({lg},{an},{so}))"
                f"REPRESENTATION_CONTEXT('Context #1','3D Context with UNIT and UNCERTAINTY'))")
    breps, styled = [], []
    for s in solids:
        z0, z1 = float(s['z0']), float(s['z1'])
        if z1 - z0 < 1e-6:
            continue
        if s['kind'] == 'box':
            if abs(sum(s['corners'][i][0] * s['corners'][(i + 1) % 4][1] - s['corners'][(i + 1) % 4][0]
                       * s['corners'][i][1] for i in range(4))) < 1e-9:
                continue
            faces = _box(st, s['corners'], z0, z1)
        else:
            if float(s['r']) < 1e-6:
                continue
            faces = _cyl(st, float(s['cx']), float(s['cy']), float(s['r']), z0, z1)
        shell = st.e(f"CLOSED_SHELL('',({','.join(faces)}))")
        brep = st.e(f"MANIFOLD_SOLID_BREP('{_ascii(s.get('name', '')) or 'volume'}',{shell})")
        breps.append(brep)
        styled += [(face, tuple(s.get('color') or GREY)) for face in faces]   # couleur sur chaque face : lue partout
    for label, faces, rgb in (extra(st) if extra is not None else ()):
        if not faces:
            continue
        shell = st.e(f"CLOSED_SHELL('',({','.join(faces)}))")
        breps.append(st.e(f"MANIFOLD_SOLID_BREP('{_ascii(label) or 'volume'}',{shell})"))
        styled += [(face, tuple(rgb or GREY)) for face in faces]
    origin = _axis(st, (0, 0, 0), (0, 0, 1), (1, 0, 0))
    absr = st.e(f"ADVANCED_BREP_SHAPE_REPRESENTATION('{nom}',({','.join(breps + [origin])}),{rctx})")
    st.e(f"SHAPE_DEFINITION_REPRESENTATION({pds},{absr})")
    items, styles = [], {}
    for item, rgb in styled:
        if rgb not in styles:
            col = st.e(f"COLOUR_RGB('',{_f(rgb[0])},{_f(rgb[1])},{_f(rgb[2])})")
            fsc = st.e(f"FILL_AREA_STYLE_COLOUR('',{col})")
            fas = st.e(f"FILL_AREA_STYLE('',({fsc}))")
            ssfa = st.e(f"SURFACE_STYLE_FILL_AREA({fas})")
            sss = st.e(f"SURFACE_SIDE_STYLE('',({ssfa}))")
            ssu = st.e(f"SURFACE_STYLE_USAGE(.BOTH.,{sss})")
            styles[rgb] = st.e(f"PRESENTATION_STYLE_ASSIGNMENT(({ssu}))")
        items.append(st.e(f"STYLED_ITEM('color',({styles[rgb]}),{item})"))
    if items:
        st.e(f"MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION('',({','.join(items)}),{rctx})")
    date = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    head = ["ISO-10303-21;", "HEADER;", f"FILE_DESCRIPTION(('{_ascii(title) or 'VectorDrive'}'),'2;1');",
            f"FILE_NAME('{nom}.step','{date}',('VectorDrive'),(''),'VectorDrive','VectorDrive','');",
            "FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));", "ENDSEC;", "DATA;"]
    body = [f"#{k + 1}={ligne};" for k, ligne in enumerate(st.lignes)]
    return "\n".join(head + body + ["ENDSEC;", "END-ISO-10303-21;", ""])


def write(path: str, solids, name: str = 'espace') -> str:
    with open(path, 'w', encoding='ascii', newline='\n') as f:
        f.write(step_text(solids, name))
    return path
