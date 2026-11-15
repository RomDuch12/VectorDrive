"""Cotes paramétrées : linéaires (alignée, horizontale, verticale),
angulaire, radiale et de longueur d'arc, avec les options de cotation qu'on attend d'un
logiciel de gravure (celles de TypeEdit) — symbole de chaque extrémité et
sa taille, ligne de cote intérieure, extérieure ou absente, lignes
d'attache, leur débord et leur écart à l'objet, police, hauteur, position
et orientation du texte, préfixe, suffixe, unité, précision.

Une cote est un groupe de trois formes (traits, symboles pleins, texte)
qui garde sa définition dans `Group.extra['cote']` : on la rouvre (double-
clic) pour en changer une option, elle est recalculée. `build` rend
[traits, symboles pleins, texte].

Cotes d'inspection (cadre autour du texte, libellé et taux d'inspection) et
espacement des cotes parallèles : d'après CADCraft (storytold/cadcraft,
© 2026 ArtCraft Team and the CADCraft contributors, MIT OR Apache-2.0,
utilisé sous MIT) — DIMINSPECT (`crates/render/src/dim.rs`) et DIMSPACE
(`crates/engine/src/cmd/annotate/edit.rs`) ; de même les ressauts : rayon
à ressaut (DIMJOGGED, `crates/render/src/dim/variants.rs`) et ressaut de
ligne de cote (DIMJOGLINE, `crates/render/src/dim/linear.rs`).
"""
from __future__ import annotations

import contextvars
import math
from dataclasses import asdict, dataclass, field, fields

from . import geom
from .geom import Affine, Contour, Line, Path

KEY = 'cote'
KINDS = {'libre': 'Cote alignée', 'horizontale': 'Cote horizontale', 'verticale': 'Cote verticale',
         'angulaire': 'Cote angulaire', 'radiale': 'Cote radiale', 'arc': 'Cote de longueur d\'arc',
         'ordonnee': 'Cote en ordonnée', 'repere': 'Repère (flèche et texte)'}
SYMBOLS = {'pleine': 'Flèche pleine', 'ouverte': 'Flèche ouverte', 'oblique': 'Trait oblique', 'point': 'Point',
           'aucun': 'Aucun (trait seul)'}
LINES = {'interieure': 'Entre les lignes d\'attache', 'exterieure': 'À l\'extérieur', 'aucune': 'Sans ligne de cote'}
ORIENT = {'alignee': 'Le long de la cote', 'horizontale': 'Horizontal', 'verticale': 'Vertical'}
UNITS = {'': 'Aucune', 'mm': 'mm', 'cm': 'cm', 'm': 'm', 'in': 'pouces (″)'}
INSPECT = {'': 'Aucune', 'ronde': 'Cadre à bouts ronds', 'angulaire': 'Cadre à bouts pointus',
           'sans': 'Sans cadre (libellé et taux seuls)'}
#: cotes dont le texte peut être une cote d'inspection ; cotes que l'on espace
INSPECTED = ('libre', 'horizontale', 'verticale', 'angulaire', 'radiale')
LINEAR = ('libre', 'horizontale', 'verticale')
#: cadres d'inspection posés par `_text` pendant `build`
_FRAMES = contextvars.ContextVar('dims_frames', default=None)
_SCALE = {'': 1.0, 'mm': 1.0, 'cm': 0.1, 'm': 0.001, 'in': 1 / 25.4}


@dataclass
class DimStyle:
    start: str = 'pleine'
    end: str = 'pleine'
    symbol: float = 2.5             # taille des symboles (mm)
    line: str = 'interieure'
    outside: float = 5.0            # longueur des lignes de cote extérieures (mm)
    ext_lines: bool = True          # lignes d'attache
    ext_beyond: float = 1.5         # débord des lignes d'attache au-delà de la ligne de cote
    ext_gap: float = 1.0            # écart entre l'objet coté et les lignes d'attache
    font: str = 'Arial'
    text_height: float = 3.5
    text_offset: float = 1.0        # écart du texte à la ligne (0 : dans la ligne, coupée)
    orientation: str = 'alignee'
    prefix: str = ''
    suffix: str = ''
    unit: str = ''
    decimals: int = 2
    diameter: bool = False          # cote radiale : le diamètre (Ø)
    inspect: str = ''               # cote d'inspection : '', 'ronde', 'angulaire', 'sans' (voir INSPECT)
    inspect_label: str = ''         # à gauche de la valeur
    inspect_rate: str = ''          # taux d'inspection, à droite de la valeur


@dataclass
class Dim:
    kind: str = 'libre'
    points: list = field(default_factory=list)      # [p1, p2] ; angulaire [p1, sommet, p3] ; radiale [centre, point]
    # linéaire [p1, p2, ressaut] ; radiale à ressaut [centre, point, départ de la ligne] ;
    # ordonnée [origine, point, bout du trait] ; repère [pointe, coude] ;
    # longueur d'arc [début, centre, fin, un point de l'arc] (rayon de l'arc de cote : offset)
    offset: float = 10.0            # position de la ligne de cote (rayon de l'arc ; débord de la radiale)
    style: DimStyle = field(default_factory=DimStyle)

    def value(self) -> float:
        """Mesure en mm (degrés pour l'angulaire)."""
        p = [tuple(q) for q in self.points]
        if self.kind == 'angulaire':
            a1 = math.atan2(p[0][1] - p[1][1], p[0][0] - p[1][0])
            a3 = math.atan2(p[2][1] - p[1][1], p[2][0] - p[1][0])
            d = abs((math.degrees(a3 - a1) + 180.0) % 360.0 - 180.0)
            return d
        if self.kind == 'radiale':
            r = geom.dist(p[0], p[1])
            return 2 * r if self.style.diameter else r
        if self.kind == 'arc':
            _c, r, _a1, sweep = arc_sweep(p)
            return r * math.radians(abs(sweep))
        if self.kind == 'ordonnee':
            return (p[1][0] - p[0][0]) if ordinate_axis(self) == 'x' else (p[1][1] - p[0][1])
        if self.kind == 'repere':
            return 0.0
        u = _direction(self)
        return abs((p[1][0] - p[0][0]) * u[0] + (p[1][1] - p[0][1]) * u[1])

    def label(self) -> str:
        s = self.style
        if self.kind == 'repere':
            return (s.prefix + s.suffix) or '?'
        v = self.value()
        if self.kind == 'angulaire':
            num, unit = f'{v:.{max(0, s.decimals)}f}', '°'
        else:
            num = f'{v * _SCALE.get(s.unit, 1.0):.{max(0, s.decimals)}f}'
            unit = '' if not s.unit else ('″' if s.unit == 'in' else ' ' + s.unit)
        num = num.replace('.', ',')
        pre = ('Ø' if self.kind == 'radiale' and s.diameter else 'R' if self.kind == 'radiale' else
               ('X ' if ordinate_axis(self) == 'x' else 'Y ') if self.kind == 'ordonnee' else '') + s.prefix
        return f'{pre}{num}{unit}{s.suffix}'


# --- dictionnaires (extra du groupe) -------------------------------------------------------------

def to_dict(d: Dim) -> dict:
    out = asdict(d)
    out['points'] = [list(map(float, p)) for p in d.points]
    return out


def from_dict(d: dict) -> Dim | None:
    if not isinstance(d, dict) or d.get('kind') not in KINDS:
        return None
    names = {f.name for f in fields(DimStyle)}
    st = DimStyle(**{k: v for k, v in (d.get('style') or {}).items() if k in names})
    try:
        return Dim(d['kind'], [tuple(p) for p in d.get('points') or []], float(d.get('offset', 10.0)), st)
    except (TypeError, ValueError):
        return None


def style_from_dict(d) -> DimStyle:
    names = {f.name for f in fields(DimStyle)}
    try:
        return DimStyle(**{k: v for k, v in (d or {}).items() if k in names})
    except TypeError:
        return DimStyle()


def transformed(d: dict, m) -> dict | None:
    """Définition après une similitude (points, débord) ; None sinon."""
    from .forms import _similarity
    sim = _similarity(m)
    dim = from_dict(d)
    if sim is None or dim is None:
        return None
    s, _rot, mirror = sim
    dim.points = [m.apply(tuple(p)) for p in dim.points]
    dim.offset *= -s if (mirror and dim.kind in ('libre', 'horizontale', 'verticale')) else s
    if dim.kind in ('horizontale', 'verticale') and abs(_rot % 90.0) > 1e-9:
        dim.kind = 'libre'
    return to_dict(dim)


# --- géométrie -------------------------------------------------------------------------------------

def ordinate_axis(dim: Dim) -> str:
    """Cote en ordonnée : 'x' si le trait part à la verticale (on lit
    l'abscisse), 'y' s'il part à l'horizontale."""
    if len(dim.points) < 3:
        return 'x'
    (px, py), (ex, ey) = dim.points[1], dim.points[2]
    return 'x' if abs(ey - py) >= abs(ex - px) else 'y'


def _direction(dim: Dim):
    if dim.kind == 'horizontale':
        return (1.0, 0.0)
    if dim.kind == 'verticale':
        return (0.0, 1.0)
    (x1, y1), (x2, y2) = dim.points[0], dim.points[1]
    L = math.hypot(x2 - x1, y2 - y1) or 1.0
    return ((x2 - x1) / L, (y2 - y1) / L)


def _symbol(kind: str, tip, d, size: float):
    """(traits, plein) d'un symbole en `tip`, corps vers la direction d."""
    nx, ny = -d[1], d[0]
    if kind == 'aucun' or size <= 0:
        return [], []
    if kind == 'point':
        return [], [geom.circle(tip, size * 0.25)]
    if kind == 'oblique':
        h = size * 0.5
        a = (tip[0] + (d[0] + nx) * h * 0.7071, tip[1] + (d[1] + ny) * h * 0.7071)
        b = (tip[0] - (d[0] + nx) * h * 0.7071, tip[1] - (d[1] + ny) * h * 0.7071)
        return [geom.polyline([b, a])], []
    hw = size * 0.18 if kind == 'pleine' else size * 0.3
    bx, by = tip[0] + d[0] * size, tip[1] + d[1] * size
    p, q = (bx + nx * hw, by + ny * hw), (bx - nx * hw, by - ny * hw)
    if kind == 'ouverte':
        return [geom.polyline([p, tip, q])], []
    return [], [geom.polyline([tip, p, q], closed=True)]


def _inspected(dim: Dim):
    """Texte d'une cote d'inspection centré sur l'origine (libellé, valeur,
    taux séparés par des traits) et son cadre, dans le repère du texte ;
    rend (texte, demi-largeur hors tout, cadre, marge du cadre)."""
    from . import text as T
    st = dim.style
    h = st.text_height
    g = 0.3 * h
    laid, x, seps = [], 0.0, []
    for s in (str(st.inspect_label).strip()[:256], dim.label(), str(st.inspect_rate).strip()[:256]):
        p = T.layout(s, st.font, h) if s else None
        bb = p.bbox() if p else None
        if not bb:
            continue
        if laid:
            seps.append(x + g)
            x += 2 * g
        laid.append(p.transformed(Affine.translation(x - bb[0], 0.0)))
        x += bb[2] - bb[0]
    w = x
    text = Path([c.transformed(Affine.translation(-w / 2, 0.0)) for p in laid for c in p.contours])
    if st.inspect == 'sans':
        return text, w / 2, [], 0.0
    hw, hh, cy = w / 2 + g, h / 2 + g, h / 2
    frame = [geom.polyline([(s - w / 2, cy - hh), (s - w / 2, cy + hh)]) for s in seps]
    if st.inspect == 'ronde':
        frame.append(Contour([Line((-hw, cy + hh), (hw, cy + hh))] + geom.arc_conics((hw, cy), hh, hh, 90.0, -180.0)
                             + [Line((hw, cy - hh), (-hw, cy - hh))]
                             + geom.arc_conics((-hw, cy), hh, hh, 270.0, -180.0), True))
    else:
        frame.append(geom.polyline([(-hw, cy + hh), (hw, cy + hh), (hw + hh, cy), (hw, cy - hh), (-hw, cy - hh),
                                    (-hw - hh, cy)], closed=True))
    return text, hw + hh, frame, g


def _text(dim: Dim, mid, ang: float, normal, side: float):
    """Texte posé en `mid`, tourné de `ang`, décalé vers `normal`·side ;
    rend (contours, demi-largeur). Cote d'inspection : le cadre va aux
    traits de la cote (voir `build`)."""
    from . import text as T
    st = dim.style
    frame, pad = [], 0.0
    if st.inspect in INSPECT and st.inspect and dim.kind in INSPECTED:
        t, half, frame, pad = _inspected(dim)
    else:
        t = T.layout(dim.label(), st.font, st.text_height, align='center')
        bb = t.bbox() or (0, 0, 0, 0)
        half = (bb[2] - bb[0]) / 2
    if st.orientation == 'horizontale':
        ang = 0.0
    elif st.orientation == 'verticale':
        ang = 90.0
    elif ang > 90.0001 or ang < -89.9999:
        ang -= 180.0                                     # toujours lisible
    if st.text_offset <= 1e-9:                           # dans la ligne : centré dessus
        base = (mid[0] - normal[0] * 0, mid[1])
        m = Affine.translation(*mid) @ Affine.rotation(ang) @ Affine.translation(0, -st.text_height / 2)
    else:
        off = st.text_offset + pad if side >= 0 else -(st.text_offset + pad + st.text_height)
        base = (mid[0] + normal[0] * off, mid[1] + normal[1] * off)
        m = Affine.translation(*base) @ Affine.rotation(ang)
    if frame and (got := _FRAMES.get()) is not None:
        got.extend(c.transformed(m) for c in frame)
    return t.transformed(m), half


def arc_sweep(points):
    """(centre, rayon, angle de départ, balayage signé) d'une cote de longueur
    d'arc [début, centre, fin, un point de l'arc], en degrés ; l'arc est
    celui qui passe par le point (sans lui : le plus court)."""
    p1, c, p3 = (tuple(p) for p in points[:3])
    a1 = math.degrees(math.atan2(p1[1] - c[1], p1[0] - c[0]))
    ccw = (math.degrees(math.atan2(p3[1] - c[1], p3[0] - c[0])) - a1) % 360.0
    if len(points) > 3:
        pm = tuple(points[3])
        ccw = ccw if ccw > 1e-9 else 360.0                # départ sur l'arrivée : le tour entier
        tm = (math.degrees(math.atan2(pm[1] - c[1], pm[0] - c[0])) - a1) % 360.0
        sweep = ccw if tm <= ccw else ccw - 360.0
    else:
        sweep = (ccw + 180.0) % 360.0 - 180.0
    return c, geom.dist(c, p1), a1, sweep


def build(dim: Dim) -> list[Path]:
    tok = _FRAMES.set([])
    try:
        out = _build(dim)
        frames = _FRAMES.get()
    finally:
        _FRAMES.reset(tok)
    if frames and out:
        out = [Path(out[0].contours + frames)] + list(out[1:])
    return out


def _build(dim: Dim) -> list[Path]:
    if dim.kind == 'angulaire':
        return _angular(dim)
    if dim.kind == 'arc':
        return _arc_length(dim)
    if dim.kind == 'radiale':
        return _radial(dim)
    if dim.kind == 'ordonnee':
        return _ordinate(dim)
    if dim.kind == 'repere':
        return _leader(dim)
    return _linear(dim)


def _ordinate(dim: Dim) -> list[Path]:
    """Cote en ordonnée : trait d'attache du point vers son bout (vertical
    pour une abscisse, horizontal pour une ordonnée, coudé si le bout est à
    côté), valeur au bout, dans l'axe du trait."""
    st = dim.style
    if len(dim.points) < 3:
        return []
    p, e = tuple(dim.points[1]), tuple(dim.points[2])
    vertical = ordinate_axis(dim) == 'x'
    L = (e[1] - p[1]) if vertical else (e[0] - p[0])
    if abs(L) < 1e-9:
        return []
    sg = 1.0 if L > 0 else -1.0
    u = (0.0, sg) if vertical else (sg, 0.0)
    start = (p[0] + u[0] * st.ext_gap, p[1] + u[1] * st.ext_gap)
    jog = (p[0], e[1] - u[1] * min(abs(L) / 3, 2.0)) if vertical else (e[0] - u[0] * min(abs(L) / 3, 2.0), p[1])
    pts = [start, jog, e] if (abs(e[0] - p[0]) > 1e-9 if vertical else abs(e[1] - p[1]) > 1e-9) else [start, e]
    if vertical and len(pts) == 3:
        pts.insert(2, (e[0], jog[1] + u[1] * min(abs(L) / 3, 2.0) * 0.5))
    elif len(pts) == 3:
        pts.insert(2, (jog[0] + u[0] * min(abs(L) / 3, 2.0) * 0.5, e[1]))
    lines = [geom.polyline(pts)] if st.line != 'aucune' else []
    from . import text as T
    t = T.layout(dim.label(), st.font, st.text_height, align='left')
    bb = t.bbox() or (0, 0, 0, 0)
    ang = math.degrees(math.atan2(u[1], u[0])) if st.orientation == 'alignee' else 0.0
    if ang > 90.0001 or ang < -89.9999:
        ang -= 180.0
        t = t.transformed(Affine.translation(-(bb[2] - bb[0]), 0))
    gap = st.text_offset if st.text_offset > 1e-9 else 0.5
    m = Affine.translation(e[0] + u[0] * gap, e[1] + u[1] * gap) @ Affine.rotation(ang) @ \
        Affine.translation(0, -st.text_height / 2)
    return [Path(lines), Path([]), t.transformed(m)]


def _leader(dim: Dim) -> list[Path]:
    """Repère : flèche sur la pointe, trait jusqu'au coude, court palier
    horizontal, texte au bout du palier."""
    st = dim.style
    if len(dim.points) < 2:
        return []
    tip, elbow = tuple(dim.points[0]), tuple(dim.points[1])
    d = geom.dist(tip, elbow)
    if d < 1e-9:
        return []
    sg = 1.0 if elbow[0] >= tip[0] else -1.0
    land = (elbow[0] + sg * max(0.0, st.ext_beyond), elbow[1])
    lines = [geom.polyline([tip, elbow, land])]
    u = ((elbow[0] - tip[0]) / d, (elbow[1] - tip[1]) / d)
    ln, filled = _symbol(st.start, tip, u, st.symbol)
    lines += ln
    from . import text as T
    t = T.layout(dim.label(), st.font, st.text_height, align='left')
    bb = t.bbox() or (0, 0, 0, 0)
    gap = st.text_offset if st.text_offset > 1e-9 else 0.5
    x = land[0] + gap if sg > 0 else land[0] - gap - (bb[2] - bb[0])
    return [Path(lines), Path(filled), t.transformed(Affine.translation(x, land[1] - st.text_height / 2))]


def _linear(dim: Dim) -> list[Path]:
    st = dim.style
    p1, p2 = tuple(dim.points[0]), tuple(dim.points[1])
    u = _direction(dim)
    n = (-u[1], u[0])
    base = (p1[0] + n[0] * dim.offset, p1[1] + n[1] * dim.offset)
    o1 = (base[0] - p1[0]) * n[0] + (base[1] - p1[1]) * n[1]
    o2 = (base[0] - p2[0]) * n[0] + (base[1] - p2[1]) * n[1]
    a = (p1[0] + n[0] * o1, p1[1] + n[1] * o1)
    b = (p2[0] + n[0] * o2, p2[1] + n[1] * o2)
    if (b[0] - a[0]) * u[0] + (b[1] - a[1]) * u[1] < 0:
        a, b = b, a
    if geom.dist(a, b) < 1e-9:
        return []
    lines, filled = [], []
    if st.ext_lines:
        for p, o in ((p1, o1), (p2, o2)):
            sg = 1.0 if o >= 0 else -1.0
            if abs(o) > st.ext_gap:
                lines.append(geom.polyline([(p[0] + n[0] * st.ext_gap * sg, p[1] + n[1] * st.ext_gap * sg),
                                            (p[0] + n[0] * (o + st.ext_beyond * sg), p[1] + n[1] * (o + st.ext_beyond * sg))]))
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    side = 1.0 if dim.offset >= 0 else -1.0
    txt, half = _text(dim, mid, math.degrees(math.atan2(u[1], u[0])), n, side)
    if st.line == 'interieure':
        cut = st.text_offset <= 1e-9 and st.orientation == 'alignee'     # ligne coupée par le texte
        jog = _jog(dim, a, b, u, n, half + 1.0 if cut else None) if len(dim.points) > 2 else None
        if jog is not None:
            pieces, zig = jog
            lines += [geom.polyline(q) for q in pieces] + [geom.polyline(zig)]
        elif cut:
            gap = half + 1.0
            lines.append(geom.polyline([a, (mid[0] - u[0] * gap, mid[1] - u[1] * gap)]))
            lines.append(geom.polyline([(mid[0] + u[0] * gap, mid[1] + u[1] * gap), b]))
        else:
            lines.append(geom.polyline([a, b]))
        heads = ((a, u, st.start), (b, (-u[0], -u[1]), st.end))
    elif st.line == 'exterieure':
        lines.append(geom.polyline([(a[0] - u[0] * st.outside, a[1] - u[1] * st.outside), a]))
        lines.append(geom.polyline([b, (b[0] + u[0] * st.outside, b[1] + u[1] * st.outside)]))
        heads = ((a, (-u[0], -u[1]), st.start), (b, u, st.end))
    else:
        heads = ()
    for tip, d, kind in heads:
        ln, fl = _symbol(kind, tip, d, st.symbol)
        lines += ln
        filled += fl
    return [Path(lines), Path(filled), txt]


def _angular(dim: Dim) -> list[Path]:
    st = dim.style
    p1, v, p3 = (tuple(p) for p in dim.points[:3])
    a1 = math.degrees(math.atan2(p1[1] - v[1], p1[0] - v[0]))
    a3 = math.degrees(math.atan2(p3[1] - v[1], p3[0] - v[0]))
    sweep = (a3 - a1 + 180.0) % 360.0 - 180.0           # angle intérieur, signé
    r = abs(dim.offset) or 10.0
    lines, filled = [], []
    if st.ext_lines:
        for p, a in ((p1, a1), (p3, a3)):
            d0 = geom.dist(p, v)
            t = math.radians(a)
            if r > d0 + st.ext_gap:
                lines.append(geom.polyline([(v[0] + (d0 + st.ext_gap) * math.cos(t), v[1] + (d0 + st.ext_gap) * math.sin(t)),
                                            (v[0] + (r + st.ext_beyond) * math.cos(t), v[1] + (r + st.ext_beyond) * math.sin(t))]))
    if abs(sweep) > 1e-9 and st.line != 'aucune':
        from .geom import Contour
        lines.append(Contour(geom.arc_conics(v, r, r, a1, sweep), False))
    sgn = 1.0 if sweep >= 0 else -1.0
    for a, kind, s2 in ((a1, st.start, sgn), (a3, st.end, -sgn)):
        t = math.radians(a)
        tip = (v[0] + r * math.cos(t), v[1] + r * math.sin(t))
        d = (-math.sin(t) * s2, math.cos(t) * s2)          # tangent, vers l'intérieur de l'arc
        ln, fl = _symbol(kind, tip, d, st.symbol)
        lines += ln
        filled += fl
    am = math.radians(a1 + sweep / 2)
    mid = (v[0] + r * math.cos(am), v[1] + r * math.sin(am))
    normal = (math.cos(am), math.sin(am))
    if st.orientation == 'alignee':                      # tangent à l'arc : peu lisible ; posé à plat, dehors
        from . import text as T
        frame, pad = [], 0.0
        if st.inspect in INSPECT and st.inspect:
            t, w2, frame, pad = _inspected(dim)
        else:
            t = T.layout(dim.label(), st.font, st.text_height, align='center')
            bb = t.bbox() or (0, 0, 0, 0)
            w2 = (bb[2] - bb[0]) / 2
        h = st.text_height
        reach = st.text_offset + abs(normal[0]) * w2 + abs(normal[1]) * (h / 2 + pad) + 0.5
        cx, cy = mid[0] + normal[0] * reach, mid[1] + normal[1] * reach
        m = Affine.translation(cx, cy - h / 2)
        txt = t.transformed(m)
        if frame and (got := _FRAMES.get()) is not None:
            got.extend(c.transformed(m) for c in frame)
    else:
        txt, _half = _text(dim, mid, math.degrees(am) - 90.0, normal, 1.0)
    return [Path(lines), Path(filled), txt]


def _arc_length(dim: Dim) -> list[Path]:
    """Cote de longueur d'arc (comme DIMARC en DAO, d'après CADCraft) : arc de
    cote concentrique de rayon `offset`, lignes d'attache radiales, texte le
    long de l'arc (ou à plat) et symbole d'arc au-dessus du nombre."""
    from . import text as T
    from .geom import Contour
    st = dim.style
    c, r, a1, sweep = arc_sweep(dim.points)
    if r < 1e-9 or abs(sweep) < 1e-9:
        return []
    R = abs(dim.offset) or r + 5.0
    lines, filled = [], []
    if st.ext_lines:
        for a in (a1, a1 + sweep):
            t = math.radians(a)
            u = (math.cos(t), math.sin(t))
            if R > r + st.ext_gap:                          # arc de cote dehors
                d0, d1 = r + st.ext_gap, R + st.ext_beyond
            elif R < r - st.ext_gap:                        # dedans
                d0, d1 = r - st.ext_gap, max(R - st.ext_beyond, 0.0)
            else:
                continue
            lines.append(geom.polyline([(c[0] + u[0] * d0, c[1] + u[1] * d0), (c[0] + u[0] * d1, c[1] + u[1] * d1)]))
    if st.line != 'aucune':
        lines.append(Contour(geom.arc_conics(c, R, R, a1, sweep), False))
    sgn = 1.0 if sweep >= 0 else -1.0
    for a, kind, s2 in ((a1, st.start, sgn), (a1 + sweep, st.end, -sgn)):
        t = math.radians(a)
        tip = (c[0] + R * math.cos(t), c[1] + R * math.sin(t))
        ln, fl = _symbol(kind, tip, (-math.sin(t) * s2, math.cos(t) * s2), st.symbol)
        lines += ln
        filled += fl
    am = math.radians(a1 + sweep / 2)
    n = (math.cos(am), math.sin(am))
    t = T.layout(dim.label(), st.font, st.text_height, align='center')
    bb = t.bbox() or (0, 0, 0, 0)
    w2, h = (bb[2] - bb[0]) / 2, st.text_height
    if st.orientation == 'horizontale':
        ang = 0.0
    elif st.orientation == 'verticale':
        ang = 90.0
    else:                                                   # tangent à l'arc, toujours lisible
        ang = (math.degrees(am) - 90.0 + 180.0) % 360.0 - 180.0
        if ang > 90.0001 or ang < -89.9999:
            ang -= 180.0 if ang > 0 else -180.0
    ra = math.radians(ang)
    xn, yn = math.cos(ra) * n[0] + math.sin(ra) * n[1], -math.sin(ra) * n[0] + math.cos(ra) * n[1]
    lift, bump = 0.25 * h, 0.35 * h                         # symbole : écart au texte, flèche de l'arc
    top = h / 2 + lift + bump
    if R >= r:                                              # texte dehors : son bord (et celui du symbole) côté arc
        reach = R + st.text_offset + w2 * abs(xn) - min(-h / 2 * yn, top * yn)
    else:                                                   # arc de cote dedans : texte vers le centre
        sag = R - math.sqrt(max(R * R - w2 * w2, 0.0))      # l'arc de cote descend vers les bouts du texte
        reach = R - st.text_offset - w2 * abs(xn) - max(-h / 2 * yn, top * yn) - sag
    m = Affine.translation(c[0] + n[0] * reach, c[1] + n[1] * reach) @ Affine.rotation(ang)
    txt = t.transformed(m @ Affine.translation(0, -h / 2))
    half = max(w2, h / 2)
    rho = (half * half + bump * bump) / (2 * bump)          # arc du symbole par ses bouts et son sommet
    th = math.degrees(math.asin(min(1.0, half / rho)))
    sym = Contour(geom.arc_conics((0.0, h / 2 + lift + bump - rho), rho, rho, 90.0 + th, -2 * th), False)
    lines.append(sym.transformed(m))
    return [Path(lines), Path(filled), txt]


def _jog(dim: Dim, a, b, u, n, text_gap):
    """Ressaut d'une ligne de cote linéaire en a-b (comme DIMJOGLINE) :
    (morceaux de la ligne, zigzag), ou None (pas la place, ou sur le texte
    coupant la ligne : demi-largeur `text_gap`)."""
    h = 1.5 * dim.style.text_height
    rj = h / 2
    L = geom.dist(a, b)
    q = tuple(dim.points[2])
    t = (q[0] - a[0]) * u[0] + (q[1] - a[1]) * u[1]
    if not math.isfinite(t) or h <= 0 or L < 2 * rj + 1e-9:
        return None
    t = min(max(t, rj), L - rj)
    cuts = [(t - rj, t + rj)]
    if text_gap is not None:
        if abs(t - L / 2) < text_gap + rj:
            return None
        cuts.append((L / 2 - text_gap, L / 2 + text_gap))
    cuts.sort()
    pieces, s = [], 0.0
    for c0, c1 in cuts + [(L, L)]:
        if c0 > s + 1e-9:
            pieces.append([(a[0] + u[0] * s, a[1] + u[1] * s), (a[0] + u[0] * c0, a[1] + u[1] * c0)])
        s = max(s, c1)

    def at(x, y):
        return (a[0] + u[0] * (t + x) + n[0] * y, a[1] + u[1] * (t + x) + n[1] * y)

    return pieces, [at(-rj, 0.0), at(-rj / 4, h / 2), at(rj / 4, -h / 2), at(rj, 0.0)]


def _jogged(c, r: float, u, o):
    """Rayon à ressaut (comme DIMJOGGED) : la ligne part de `o` (centre
    déporté) parallèle au rayon et rejoint le rayon par un ressaut à 45°
    (plus raide s'il manque de place) à mi-chemin ; points de `o` jusqu'au
    bout du ressaut côté arc, ou None (`o` hors du cercle)."""
    n = (-u[1], u[0])
    h = (o[0] - c[0]) * n[0] + (o[1] - c[1]) * n[1]
    to = (o[0] - c[0]) * u[0] + (o[1] - c[1]) * u[1]
    if not (math.isfinite(h) and math.isfinite(to)) or to >= r - 1e-9:
        return None
    o = (c[0] + u[0] * to + n[0] * h, c[1] + u[1] * to + n[1] * h)
    if abs(h) < 1e-9:
        return [o]
    run = min(abs(h), 0.8 * (r - to))
    tj = (to + r) / 2
    return [o, (c[0] + u[0] * (tj - run / 2) + n[0] * h, c[1] + u[1] * (tj - run / 2) + n[1] * h),
            (c[0] + u[0] * (tj + run / 2), c[1] + u[1] * (tj + run / 2))]


def _radial(dim: Dim) -> list[Path]:
    st = dim.style
    c, p = tuple(dim.points[0]), tuple(dim.points[1])
    r = geom.dist(c, p)
    if r < 1e-9:
        return []
    u = ((p[0] - c[0]) / r, (p[1] - c[1]) / r)
    out = (p[0] + u[0] * dim.offset, p[1] + u[1] * dim.offset)
    start = (c[0] - u[0] * r, c[1] - u[1] * r) if st.diameter else c
    jog = _jogged(c, r, u, tuple(dim.points[2])) if len(dim.points) > 2 and not st.diameter else None
    lines = [geom.polyline((jog or [start]) + [p, out])] if st.line != 'aucune' else []
    filled = []
    for tip, d, kind in ((p, (-u[0], -u[1]), st.end), ) + (((start, u, st.start),) if st.diameter else ()):
        ln, fl = _symbol(kind, tip, d, st.symbol)
        lines += ln
        filled += fl
    n = (-u[1], u[0])
    txt, _half = _text(dim, out, math.degrees(math.atan2(u[1], u[0])), n, 1.0)
    return [Path(lines), Path(filled), txt]


def quick(points, bbox, style: DimStyle | None = None, mode: str = 'chaine', gap: float = 8.0) -> list[Dim]:
    """Cotation rapide (comme QDIM en DAO) : `points` (centres des cercles,
    coins des autres objets…) cotés en X sous la boîte `bbox` et en Y à sa
    gauche — en chaîne (d'un point au suivant) ou depuis une ligne de base
    (tout depuis le premier, lignes décalées). Rend les cotes."""
    style = style or DimStyle()
    x0, y0, x1, y1 = bbox
    out = []
    for axis in ('x', 'y'):
        vals = sorted({round(p[0] if axis == 'x' else p[1], 6) for p in points})
        if len(vals) < 2:
            continue
        ref = [min(points, key=lambda p, v=v: abs((p[0] if axis == 'x' else p[1]) - v)) for v in vals]
        step = 2.2 * style.text_height
        for k in range(1, len(ref)):
            a = ref[0] if mode == 'base' else ref[k - 1]
            b = ref[k]
            extra = (k - 1) * step if mode == 'base' else 0.0
            if axis == 'x':                                 # sous la boîte : n = (0, 1), ligne à y0 − gap
                line = y0 - gap - extra
                out.append(Dim('horizontale', [tuple(a), tuple(b)], line - a[1], style))
            else:                                           # à gauche : n = (−1, 0), ligne à x0 − gap
                line = x0 - gap - extra
                out.append(Dim('verticale', [tuple(a), tuple(b)], a[0] - line, style))
    return out


@dataclass
class FrameDims:
    """Cotes automatiques d'un cadre (Maj+C)."""
    width: bool = True              # largeur (cote horizontale)
    height: bool = True             # hauteur (cote verticale)
    h_side: str = 'dessous'         # largeur : 'dessous' ou 'dessus'
    v_side: str = 'gauche'          # hauteur : 'gauche' ou 'droite'
    gap: float = 8.0                # écart entre le cadre et la ligne de cote (mm)
    each: bool = True               # un jeu de cotes par objet choisi (sinon l'ensemble)
    circles: bool = False           # diamètre des cercles choisis


def frame_dims(bbox, spec: FrameDims | None = None, style: DimStyle | None = None) -> list[Dim]:
    """Largeur et hauteur d'un encombrement (x0, y0, x1, y1), placées selon
    `spec`."""
    spec = spec or FrameDims()
    style = style or DimStyle()
    x0, y0, x1, y1 = bbox
    out = []
    if spec.width and x1 - x0 > 1e-9:
        y = y1 if spec.h_side == 'dessus' else y0
        out.append(Dim('horizontale', [(x0, y), (x1, y)], spec.gap if spec.h_side == 'dessus' else -spec.gap,
                       style))
    if spec.height and y1 - y0 > 1e-9:
        x = x1 if spec.v_side == 'droite' else x0
        out.append(Dim('verticale', [(x, y0), (x, y1)], -spec.gap if spec.v_side == 'droite' else spec.gap,
                       style))
    return out


def space(dims: list[Dim], spacing: float) -> int:
    """Cotes linéaires parallèles à intervalle régulier à partir de la plus
    proche de l'objet coté (comme DIMSPACE) ; 0 : toutes sur sa ligne. La
    base est prise dans la plus grande famille de cotes parallèles ; les
    autres restent. Les cotes déplacées sont changées en place (débord) ;
    rend leur nombre."""
    lin = [d for d in dims if d.kind in LINEAR and len(d.points) >= 2]
    if len(lin) < 2 or not math.isfinite(spacing):
        return 0

    def parallel(a, b):
        ua, ub = _direction(a), _direction(b)
        return abs(ua[0] * ub[1] - ua[1] * ub[0]) <= 1e-6

    base = max(lin, key=lambda d: (sum(parallel(d, e) for e in lin), -abs(d.offset)))
    ub = _direction(base)
    nb = (-ub[1], ub[0])

    def at(p):
        return p[0] * nb[0] + p[1] * nb[1]

    b0 = at(base.points[0]) + base.offset
    side = 1.0 if base.offset >= 0 else -1.0
    others = []
    for d in lin:
        if d is base or not parallel(d, base):
            continue
        u = _direction(d)
        k = 1.0 if u[0] * ub[0] + u[1] * ub[1] > 0 else -1.0         # sa normale, celle de la base ou l'opposée
        others.append(((at(d.points[0]) + d.offset * k - b0) * side, d, k))
    others.sort(key=lambda o: o[0])
    for i, (_o, d, k) in enumerate(others):
        d.offset = (b0 + side * spacing * (i + 1) - at(d.points[0])) * k
    return len(others)


def group(dim: Dim, tool: int = 0):
    """La cote en groupe (traits, symboles pleins, texte), définition gardée."""
    from .document import Group, Shape
    lines, filled, txt = build(dim)
    g = Group(children=[Shape(path=lines, tool=tool), Shape(path=filled, filled=True, tool=tool),
                        Shape(path=txt, filled=True, tool=tool)], name='Cote')
    g.extra[KEY] = to_dict(dim)
    return g


def rebuild(g, dim: Dim) -> None:
    """Le groupe de la cote recalculé d'après `dim` (en place)."""
    lines, filled, txt = build(dim)
    tool = g.children[0].tool if g.children else 0
    from .document import Shape
    g.children = [Shape(path=lines, tool=tool), Shape(path=filled, filled=True, tool=tool),
                  Shape(path=txt, filled=True, tool=tool)]
    g.extra = {**g.extra, KEY: to_dict(dim)}


def dim_of(g) -> Dim | None:
    """Définition de la cote, si le groupe en est encore une."""
    from .document import Group
    if not isinstance(g, Group) or len(g.children) != 3:
        return None
    return from_dict(g.extra.get(KEY))
