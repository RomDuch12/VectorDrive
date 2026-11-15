"""Cadres de tolérancement (GD&T, ISO 1101 / ASME Y14.5) : la chaîne d'un
cadre comme l'entité TOLERANCE des DXF (lignes séparées par ^J, cases par
%%v, symboles écrits en caractères de la police « gdt » dans des
{\\Fgdt;…}), sa composition, sa mise en page et ses symboles, dessinés en
traits : aucune police de symboles n'est nécessaire.

Portage de CADCraft (storytold/cadcraft, © 2026 ArtCraft Team and the
CADCraft contributors, MIT OR Apache-2.0, utilisé sous MIT) —
`crates/doc/src/gdt.rs` (`parse_frame`, `compose_frame`, `layout_frame`,
`symbol_prims`). Modifications : tracés VectorDrive (cercles et arcs
exacts), textes en contours, groupe qui garde sa définition (rouvert par un
double-clic) et la suit dans les similitudes, champs du dialogue.
"""
from __future__ import annotations

import math
import re

from . import geom
from .geom import Affine, Contour, Path

KEY = 'tolerance'
#: bornes d'une chaîne de cadre (fichiers, réglages : jamais sûrs)
MAX_FRAME_CHARS = 4096
MAX_FRAME_ROWS = 8
MAX_FRAME_CELLS = 12

#: symbole → caractère de la police « gdt »
CODES = {'position': 'j', 'concentricity': 'r', 'symmetry': 'i', 'parallelism': 'f', 'perpendicularity': 'b',
         'angularity': 'a', 'cylindricity': 'g', 'flatness': 'c', 'circularity': 'e', 'straightness': 'u',
         'surfaceprofile': 'd', 'lineprofile': 'k', 'circularrunout': 'h', 'totalrunout': 't', 'diameter': 'n',
         'mmc': 'm', 'lmc': 'l', 'rfs': 's', 'projected': 'p'}
FROM_CODE = {c: k for k, c in CODES.items()}
#: caractéristiques géométriques (la première case d'une ligne), dans l'ordre des normes
CHARACTERISTICS = ('straightness', 'flatness', 'circularity', 'cylindricity', 'lineprofile', 'surfaceprofile',
                   'parallelism', 'perpendicularity', 'angularity', 'position', 'concentricity', 'symmetry',
                   'circularrunout', 'totalrunout')
LABELS = {'straightness': 'Rectitude', 'flatness': 'Planéité', 'circularity': 'Circularité',
          'cylindricity': 'Cylindricité', 'lineprofile': 'Forme d\'une ligne', 'surfaceprofile': 'Forme d\'une surface',
          'parallelism': 'Parallélisme', 'perpendicularity': 'Perpendicularité', 'angularity': 'Inclinaison',
          'position': 'Localisation', 'concentricity': 'Coaxialité', 'symmetry': 'Symétrie',
          'circularrunout': 'Battement circulaire', 'totalrunout': 'Battement total'}
#: conditions de matière : lettre du dialogue → symbole
MATERIAL = {'M': 'mmc', 'L': 'lmc', 'S': 'rfs'}


# --- chaîne du cadre ------------------------------------------------------------------------------

def parse_frame(text: str) -> list[list[list[tuple[str, str]]]]:
    """Lignes de cases ; une case est une suite de morceaux ('t', texte) ou
    ('s', symbole). Les codes de mise en forme inconnus sont sautés, un code
    inachevé termine la chaîne ; tailles bornées."""
    cs = str(text or '')[:MAX_FRAME_CHARS]
    rows = [[[]]]
    gdt, stack = False, []

    def push(kind, val):
        cell = rows[-1][-1]
        if kind == 't' and cell and cell[-1][0] == 't':
            cell[-1] = ('t', cell[-1][1] + val)
        else:
            cell.append((kind, val))

    i, n = 0, len(cs)
    while i < n:
        c = cs[i]
        nxt = cs[i + 1] if i + 1 < n else None
        if (c == '^' and nxt in ('J', 'j')) or (c == '\\' and nxt == 'P') or c == '\n':
            if len(rows) >= MAX_FRAME_ROWS:
                break
            rows.append([[]])
            i += 1 if c == '\n' else 2
            continue
        if c == '\r':
            i += 1
            continue
        if c == '%' and nxt == '%':
            if i + 2 >= n:
                break
            o = cs[i + 2].lower()
            if o == 'v':
                if len(rows[-1]) < MAX_FRAME_CELLS:
                    rows[-1].append([])
            elif o == 'c':
                push('s', 'diameter')
            elif o == 'd':
                push('t', '°')
            elif o == 'p':
                push('t', '±')
            elif o == '%':
                push('t', '%')
            else:
                push('t', '%%' + cs[i + 2])
            i += 3
            continue
        if c == '{':
            if len(stack) < 64:
                stack.append(gdt)
            i += 1
        elif c == '}':
            gdt = stack.pop() if stack else False
            i += 1
        elif c == '\\':
            if nxt in ('\\', '{', '}'):
                push('t', nxt)
                i += 2
            elif nxt in ('F', 'f'):                          # police : « gdt » dessine les symboles
                end = cs.find(';', i + 2)
                if end < 0:
                    break
                gdt = cs[i + 2:end].split('|')[0].strip().lower().startswith('gdt')
                i = end + 1
            elif nxt in ('A', 'C', 'c', 'H', 'Q', 'T', 'W', 'S'):   # codes à valeur jusqu'au « ; »
                end = cs.find(';', i + 2)
                if end < 0:
                    break
                i = end + 1
            elif nxt in ('L', 'l', 'O', 'o', 'K', 'k'):
                i += 2
            elif nxt == '~':
                push('t', ' ')
                i += 2
            elif nxt is None:
                break
            else:
                push('t', '\\')
                i += 1
        elif gdt:
            push(*(('s', FROM_CODE[c]) if c in FROM_CODE else ('t', c)))
            i += 1
        else:
            push('t', c)
            i += 1
    return rows


def _empty(cell) -> bool:
    return all(k == 't' and not v.strip() for k, v in cell)


def _escape(s: str) -> str:
    out = []
    for c in str(s)[:256]:
        out.append({'\\': '\\\\', '{': '\\{', '}': '\\}', '%': '%%%', '\n': ' ', '\r': ' ', '^': ' '}.get(c, c))
    return ''.join(out)


def _sym(name: str) -> str:
    return '{\\Fgdt;' + CODES[name] + '}'


def compose_frame(lines: list[dict], height: str = '', projected: bool = False, datum_id: str = '') -> str:
    """Chaîne d'un cadre : lignes {'symbol', 'tol1', 'tol2', 'datums'} (tol :
    {'diameter', 'value', 'material'} ; référence : {'letter', 'material'} ;
    material : 'M', 'L', 'S' ou ''), hauteur de zone projetée, identificateur
    de référence."""
    def tol(t):
        if not t:
            return ''
        m = MATERIAL.get(str(t.get('material') or '').upper())
        v = str(t.get('value') or '').strip()
        if not v and not t.get('diameter') and not m:
            return ''
        return (_sym('diameter') if t.get('diameter') else '') + _escape(v) + (_sym(m) if m else '')

    out = []
    for ln in lines[:MAX_FRAME_ROWS]:
        sym = ln.get('symbol') or ''
        cells = [_sym(sym) if sym in CODES else '', tol(ln.get('tol1')), tol(ln.get('tol2'))]
        for d in (ln.get('datums') or [])[:3]:
            m = MATERIAL.get(str(d.get('material') or '').upper())
            cells.append(_escape(str(d.get('letter') or '').strip()) + (_sym(m) if m else ''))
        while cells and not cells[-1]:
            cells.pop()
        if cells:
            out.append('%%v'.join(cells))
    if str(height).strip() or projected:
        out.append(_escape(str(height).strip()) + (_sym('projected') if projected else ''))
    if str(datum_id).strip():
        out.append(_escape(str(datum_id).strip()))
    return '^J'.join(out)


# --- champs du dialogue (une ligne, trois références, identificateur) ---------------------------------

_DATUM = re.compile(r'^\s*(.*?)\s*(?:\(\s*([MLSmls])\s*\))?\s*$')


def compose_fields(f: dict) -> str:
    """Chaîne d'après les champs du dialogue : symbol, diameter, value,
    material, datum1..3 (« B » ou « B(M) »), datum_id."""
    datums = []
    for k in ('datum1', 'datum2', 'datum3'):
        m = _DATUM.match(str(f.get(k) or ''))
        datums.append({'letter': m.group(1), 'material': (m.group(2) or '').upper()})
    while datums and not datums[-1]['letter']:
        datums.pop()
    line = {'symbol': f.get('symbol') or '', 'datums': datums,
            'tol1': {'diameter': bool(f.get('diameter')), 'value': f.get('value') or '', 'material': f.get('material') or ''}}
    return compose_frame([line], datum_id=f.get('datum_id') or '')


def fields_of(text: str) -> dict:
    """Champs du dialogue d'après une chaîne (ce qui dépasse une ligne et
    trois références est laissé de côté : voir `compose_fields`)."""
    letter = {v: k for k, v in MATERIAL.items()}
    f = {'symbol': '', 'diameter': False, 'value': '', 'material': '', 'datum1': '', 'datum2': '', 'datum3': '',
         'datum_id': ''}
    rows = parse_frame(text)
    first = rows[0] if rows else []
    if first:
        f['symbol'] = next((v for k, v in first[0] if k == 's' and v in CHARACTERISTICS), '')
    if len(first) > 1:
        c = first[1]
        f['diameter'] = any(r == ('s', 'diameter') for r in c)
        f['value'] = ''.join(v for k, v in c if k == 't').strip()
        f['material'] = next((letter[v] for k, v in c if k == 's' and v in letter), '')
    for j, c in enumerate(first[3:6]):
        m = next((letter[v] for k, v in c if k == 's' and v in letter), '')
        txt = ''.join(v for k, v in c if k == 't').strip()
        f[f'datum{j + 1}'] = txt + (f'({m})' if m else '')
    if len(rows) > 1 and len(rows[-1]) == 1 and not any(k == 's' for k, _v in rows[-1][0]):
        f['datum_id'] = ''.join(v for _k, v in rows[-1][0]).strip()
    return f


# --- mise en page -------------------------------------------------------------------------------------

def symbol_prims(name: str) -> list[tuple]:
    """Tracé d'un symbole dans le carré unité : ('line', points),
    ('circle', centre, rayon), ('arc', centre, rayon, début, fin) en degrés
    (sens direct), ('fill', triangle)."""
    def arrow(tip, d):
        n = math.hypot(*d)
        u = (d[0] / n, d[1] / n)
        bx, by = tip[0] - u[0] * 0.3, tip[1] - u[1] * 0.3
        return ('fill', [tip, (bx - u[1] * 0.1, by + u[0] * 0.1), (bx + u[1] * 0.1, by - u[0] * 0.1)])

    def circled(rest):
        return [('circle', (0.5, 0.5), 0.5)] + rest

    if name == 'position':
        return [('circle', (0.5, 0.5), 0.3), ('line', [(0, 0.5), (1, 0.5)]), ('line', [(0.5, 0), (0.5, 1)])]
    if name == 'concentricity':
        return [('circle', (0.5, 0.5), 0.45), ('circle', (0.5, 0.5), 0.25)]
    if name == 'symmetry':
        return [('line', [(0, 0.5), (1, 0.5)]), ('line', [(0.2, 0.2), (0.8, 0.2)]), ('line', [(0.2, 0.8), (0.8, 0.8)])]
    if name == 'parallelism':
        return [('line', [(0.1, 0.05), (0.5, 0.95)]), ('line', [(0.5, 0.05), (0.9, 0.95)])]
    if name == 'perpendicularity':
        return [('line', [(0.05, 0.05), (0.95, 0.05)]), ('line', [(0.5, 0.05), (0.5, 0.95)])]
    if name == 'angularity':
        return [('line', [(0.95, 0.05), (0.05, 0.05), (0.85, 0.75)])]
    if name == 'cylindricity':
        r, t = 0.3, math.radians(65.0)
        d, nx, ny = (math.cos(t), math.sin(t)), -math.sin(t) * r, math.cos(t) * r
        return [('circle', (0.5, 0.5), r)] + [
            ('line', [(0.5 + s * nx - d[0] * 0.5, 0.5 + s * ny - d[1] * 0.5),
                      (0.5 + s * nx + d[0] * 0.5, 0.5 + s * ny + d[1] * 0.5)]) for s in (1, -1)]
    if name == 'flatness':
        return [('line', [(0, 0.25), (0.7, 0.25), (1, 0.75), (0.3, 0.75), (0, 0.25)])]
    if name == 'circularity':
        return [('circle', (0.5, 0.5), 0.45)]
    if name == 'straightness':
        return [('line', [(0, 0.5), (1, 0.5)])]
    if name == 'surfaceprofile':
        return [('arc', (0.5, 0.2), 0.45, 0.0, 180.0), ('line', [(0.05, 0.2), (0.95, 0.2)])]
    if name == 'lineprofile':
        return [('arc', (0.5, 0.2), 0.45, 0.0, 180.0)]
    if name == 'circularrunout':
        return [('line', [(0.2, 0.05), (0.7, 0.95)]), arrow((0.7, 0.95), (0.5, 0.9))]
    if name == 'totalrunout':
        return [('line', [(0.05, 0.05), (0.5, 0.05)]), ('line', [(0.05, 0.05), (0.45, 0.95)]),
                ('line', [(0.5, 0.05), (0.9, 0.95)]), arrow((0.45, 0.95), (0.4, 0.9)), arrow((0.9, 0.95), (0.4, 0.9))]
    if name == 'diameter':
        return [('circle', (0.5, 0.5), 0.35), ('line', [(0.1, 0), (0.9, 1)])]
    if name == 'mmc':
        return circled([('line', [(0.3, 0.25), (0.3, 0.75), (0.5, 0.45), (0.7, 0.75), (0.7, 0.25)])])
    if name == 'lmc':
        return circled([('line', [(0.38, 0.75), (0.38, 0.25), (0.65, 0.25)])])
    if name == 'rfs':
        return circled([('arc', (0.5, 0.625), 0.125, 20.0, 270.0), ('arc', (0.5, 0.375), 0.125, 200.0, 90.0)])
    if name == 'projected':
        return circled([('line', [(0.5, 0.5), (0.38, 0.5), (0.38, 0.75), (0.5, 0.75)]),
                        ('arc', (0.5, 0.625), 0.125, -90.0, 90.0), ('line', [(0.38, 0.5), (0.38, 0.25)])])
    return []


def _prim_contours(prims, ox: float, oy: float, s: float):
    """(traits, pleins) des primitives d'un symbole posé en (ox, oy), côté s."""
    lines, fills = [], []
    for p in prims:
        if p[0] == 'line':
            lines.append(geom.polyline([(ox + x * s, oy + y * s) for x, y in p[1]]))
        elif p[0] == 'circle':
            lines.append(geom.circle((ox + p[1][0] * s, oy + p[1][1] * s), p[2] * s))
        elif p[0] == 'arc':
            sweep = (p[4] - p[3]) % 360.0 or 360.0
            lines.append(Contour(geom.arc_conics((ox + p[1][0] * s, oy + p[1][1] * s), p[2] * s, p[2] * s, p[3], sweep),
                                 False))
        else:
            fills.append(geom.polyline([(ox + x * s, oy + y * s) for x, y in p[1]], closed=True))
    return lines, fills


def layout(text: str, h: float, gap: float, measure) -> dict:
    """Cadre mis en page, origine au milieu du bord gauche de la première
    ligne, axe X le long du cadre : {'frame': [polylignes], 'lines' / 'fills' :
    contours des symboles, 'texts': [(x, y, texte)] (bas gauche, hauteur h),
    'width', 'rows'}. `measure(texte, h)` : largeur d'un texte."""
    h = min(h, 1e6) if math.isfinite(h) and h > 0 else 2.5
    gap = min(max(abs(gap), h * 0.25), h * 2.0) if math.isfinite(gap) else h * 0.5
    row_h = 2.0 * h
    rows = [[c for c in r if not _empty(c)] for r in parse_frame(text)]
    rows = [r for r in rows if r]
    out = {'frame': [], 'lines': [], 'fills': [], 'texts': [], 'width': 0.0, 'rows': len(rows)}

    def run_w(r):
        if r[0] == 's':
            return h
        w = measure(r[1], h)
        return min(max(w, 0.0), h * 4096.0) if math.isfinite(w) else 0.0

    prev = 0.0
    for k, row in enumerate(rows):
        top = h - k * row_h
        bot, mid = top - row_h, top - h
        x = 0.0
        for cell in row:
            sep = 0.25 * h                                   # morceaux un peu écartés (modificateur après la valeur)
            w = sum(run_w(r) for r in cell) + sep * max(len(cell) - 1, 0)
            cw = max(w + 2.0 * gap, row_h)
            out['frame'].append([(x, top), (x, bot)])
            cx = x + (cw - w) / 2.0
            for r in cell:
                if r[0] == 's':
                    ln, fl = _prim_contours(symbol_prims(r[1]), cx, mid - h / 2.0, h)
                    out['lines'] += ln
                    out['fills'] += fl
                else:
                    out['texts'].append((cx, mid - h / 2.0, r[1]))
                cx += run_w(r) + sep
            x += cw
        out['frame'].append([(x, top), (x, bot)])
        if k == 0:
            out['frame'].append([(0.0, top), (x, top)])
        elif x > prev:                                      # le bord haut qui dépasse la ligne du dessus
            out['frame'].append([(prev, top), (x, top)])
        out['frame'].append([(0.0, bot), (x, bot)])
        out['width'] = max(out['width'], x)
        prev = x
    return out


def _num(v, default: float) -> float:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return default
    return v if math.isfinite(v) else default


def build(spec: dict) -> list[Path]:
    """[traits (cadre et symboles), pleins (flèches), textes en contours]
    d'un cadre {'text', 'insert', 'rotation', 'height', 'gap', 'font'}."""
    from . import text as T
    h, font = _num(spec.get('height'), 2.5), spec.get('font') or 'Arial'
    h = min(h, 1e6) if h > 0 else 2.5

    def measure(t, hh):
        bb = T.layout_bbox(t, font, hh)
        return (bb[2] - bb[0]) if bb else 0.0

    lay = layout(spec.get('text', ''), h, _num(spec.get('gap'), h / 2), measure)
    x, y = (spec.get('insert') or (0.0, 0.0))[:2]
    m = Affine.translation(_num(x, 0.0), _num(y, 0.0)) @ Affine.rotation(_num(spec.get('rotation'), 0.0))
    lines = Path([geom.polyline(p) for p in lay['frame']] + lay['lines']).transformed(m)
    fills = Path(lay['fills']).transformed(m)
    txt = []
    for tx, ty, t in lay['texts']:
        tp = T.layout(t, font, h)
        bb = tp.bbox()
        if bb:                                               # l'encre (pas l'approche) commence en tx
            txt += tp.transformed(Affine.translation(tx - bb[0], ty)).contours
    return [lines, fills, Path(txt).transformed(m)]


# --- groupe -------------------------------------------------------------------------------------------

def group(spec: dict, tool: int = 0):
    """Le cadre en groupe (traits, pleins, textes), définition gardée."""
    from .document import Group, Shape
    lines, fills, txt = build(spec)
    g = Group(children=[Shape(path=lines, tool=tool), Shape(path=fills, filled=True, tool=tool),
                        Shape(path=txt, filled=True, tool=tool)], name='Cadre de tolérancement')
    g.extra[KEY] = dict(spec)
    return g


def rebuild(g, spec: dict) -> None:
    """Le groupe du cadre recalculé d'après `spec` (en place)."""
    from .document import Shape
    lines, fills, txt = build(spec)
    tool = g.children[0].tool if g.children else 0
    g.children = [Shape(path=lines, tool=tool), Shape(path=fills, filled=True, tool=tool),
                  Shape(path=txt, filled=True, tool=tool)]
    g.extra = {**g.extra, KEY: dict(spec)}


def spec_of(g) -> dict | None:
    """Définition du cadre, si le groupe en est encore un."""
    from .document import Group
    d = g.extra.get(KEY) if isinstance(g, Group) and len(g.children) == 3 else None
    return d if isinstance(d, dict) and isinstance(d.get('text'), str) else None


def transformed(d: dict, m) -> dict | None:
    """Définition après une similitude sans miroir (point d'insertion,
    rotation, hauteur) ; None sinon (le cadre reste un dessin)."""
    from .forms import _similarity
    sim = _similarity(m)
    if sim is None or sim[2]:
        return None
    s, rot, _mirror = sim
    x, y = d.get('insert') or (0.0, 0.0)
    return {**d, 'insert': list(m.apply((float(x), float(y)))), 'rotation': float(d.get('rotation') or 0.0) + rot,
            'height': float(d.get('height') or 2.5) * s,
            'gap': float(d['gap']) * s if d.get('gap') is not None else None}
