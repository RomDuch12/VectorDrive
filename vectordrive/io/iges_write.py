"""IGES (*.igs) : écriture du dessin, en courbes exactes.

Chaque contour devient une courbe composite (102) de ses segments : droite (110), Bézier cubique ou conique en
NURBS d'un seul morceau (126, degré 3, ou degré 2 rationnelle : les arcs de cercle restent des arcs). Un niveau
IGES par calque (1, 2, 3…), en millimètres, Z = 0. Les textes sont écrits en contours ; les images, que l'IGES ne
connaît pas, sont laissées de côté (le compte rendu le dit). Chaque contour porte sa couleur (celle de son outil, ou
la sienne) : un des numéros de l'IGES (rouge, vert, bleu…) ou une définition de couleur (314) ; le noir reste sans
couleur.

Écrit d'après la spécification IGES 5.3 : sections S, G, D, P, T en lignes de 80 colonnes ; relu par `io.iges`.
"""
from __future__ import annotations

import datetime as dt
import pathlib

from ..core.document import Document, Group, Image, Shape, Text
from ..core.geom import Conic, Cubic, Line


#: les couleurs que l'IGES désigne par un numéro (champ 13 de l'entrée) ; les autres ont leur entité 314
STANDARD = {'#ff0000': 2, '#00ff00': 3, '#0000ff': 4, '#ffff00': 5, '#ff00ff': 6, '#00ffff': 7, '#ffffff': 8}


def _hex(color) -> str:
    """« #rrggbb » en minuscules ; le noir pour toute autre écriture."""
    c = str(color or '').lower()
    return c if len(c) == 7 and c[0] == '#' and all(ch in '0123456789abcdef' for ch in c[1:]) else '#000000'


def _real(v: float) -> str:
    """Un réel IGES : toujours un point décimal, exposant en E."""
    s = f'{float(v):.10g}'
    if 'e' in s:
        m, e = s.split('e')
        return (m if '.' in m else m + '.') + 'E' + str(int(e))
    return s if '.' in s else s + '.'


def _hollerith(s: str) -> str:
    s = s.encode('ascii', 'replace').decode('ascii')
    return f'{len(s)}H{s}' if s else ''                  # chaîne vide : champ vide


def _leaves(items):
    for it in items:
        if isinstance(it, Group):
            yield from _leaves(it.children)
        else:
            yield it


def _contours(doc: Document) -> tuple[list, int]:
    """[(niveau, couleur, contour)] dans l'ordre du dessin, et le nombre d'images laissées de côté."""
    out, images = [], 0
    for level, layer in enumerate(doc.layers, 1):
        for it in _leaves(layer.items):
            if isinstance(it, Image):
                images += 1
                continue
            path = it.path if isinstance(it, Shape) else (it.outline if isinstance(it, Text) else None)
            color = _hex(doc.item_color(it)) if path is not None else '#000000'
            for c in (path.contours if path is not None else ()):
                if c.segments:
                    out.append((level, color, c))
    return out, images


def _nurbs(points: list, weights: list) -> list[str]:
    """Paramètres d'une entité 126 d'un seul morceau de Bézier (degré = nombre de points − 1), dans le plan Z = 0."""
    deg = len(points) - 1
    rational = any(abs(w - 1.0) > 1e-12 for w in weights)
    v = ['126', str(deg), str(deg), '1', '0', '0' if rational else '1', '0']
    v += ['0.'] * (deg + 1) + ['1.'] * (deg + 1)
    v += [_real(w) for w in weights]
    for x, y in points:
        v += [_real(x), _real(y), '0.']
    return v + ['0.', '1.', '0.', '0.', '1.']


def _segment(s) -> list[str]:
    if isinstance(s, Line):
        return ['110', _real(s.p0[0]), _real(s.p0[1]), '0.', _real(s.p1[0]), _real(s.p1[1]), '0.']
    if isinstance(s, Cubic):
        return _nurbs([s.p0, s.p1, s.p2, s.p3], [1.0, 1.0, 1.0, 1.0])
    if isinstance(s, Conic):
        return _nurbs([s.p0, s.p1, s.p2], [1.0, float(s.w), 1.0])
    raise TypeError(s)


def _lines(text: str, width: int) -> list[str]:
    return [text[i:i + width] for i in range(0, len(text), width)] or ['']


def _wrap(fields: list[str], width: int = 64) -> list[str]:
    """Les champs séparés par des virgules, terminés par un point-virgule, coupés entre deux champs."""
    out, cur = [], ''
    for i, f in enumerate(fields):
        piece = f + (';' if i == len(fields) - 1 else ',')
        while len(piece) > width:                        # un champ plus long qu'une ligne (chaîne) : coupé
            room = width - len(cur)
            cur += piece[:room]
            piece = piece[room:]
            out.append(cur)
            cur = ''
        if len(cur) + len(piece) > width:
            out.append(cur)
            cur = ''
        cur += piece
    if cur:
        out.append(cur)
    return out


def to_string(doc: Document, name: str = 'dessin.igs') -> tuple[str, int, int]:
    """Le texte du fichier IGES, le nombre de contours écrits et le nombre d'images laissées de côté."""
    contours, images = _contours(doc)
    entities: list[tuple[int, int, str, int, list[str]]] = []   # (type, niveau, statut, couleur, champs)
    number = {'#000000': 0}                              # le noir : sans couleur
    for _level, color, _c in contours:
        if color in number:
            continue
        if color in STANDARD:
            number[color] = STANDARD[color]
        else:                                            # sa définition (en pour cent), désignée par son entrée
            number[color] = -(2 * len(entities) + 1)
            rgb = [_real(int(color[i:i + 2], 16) / 2.55) for i in (1, 3, 5)]
            entities.append((314, 0, '00000200', 0, ['314', *rgb]))
    for level, color, c in contours:
        first = len(entities)
        for s in c.segments:
            v = _segment(s)
            entities.append((int(v[0]), level, '00010000', number[color], v))   # dépend de sa courbe composite
        children = [str(2 * k + 1) for k in range(first, len(entities))]
        entities.append((102, level, '00000000', number[color], ['102', str(len(children)), *children]))
    d_lines, p_lines = [], []
    for k, (kind, level, status, color, v) in enumerate(entities):
        de = 2 * k + 1
        rows = _wrap(v)
        start = len(p_lines) + 1
        for row in rows:
            p_lines.append(f'{row:<64} {de:>7}P{len(p_lines) + 1:>7}')
        a = f'{kind:>8}{start:>8}{0:>8}{0:>8}{level:>8}{0:>8}{0:>8}{0:>8}{status:>8}'
        b = f'{kind:>8}{0:>8}{color:>8}{len(rows):>8}{0:>8}{"":>8}{"":>8}{"":>8}{0:>8}'
        d_lines.append(f'{a}D{de:>7}')
        d_lines.append(f'{b}D{de + 1:>7}')
    now = dt.datetime.now().strftime('%Y%m%d.%H%M%S')
    box = doc.bbox(include_plate=False) or (0.0, 0.0, 100.0, 100.0)
    biggest = max(abs(v) for v in box) or 1.0
    g = ['1H,', '1H;', _hollerith('VectorDrive'), _hollerith(name), _hollerith('VectorDrive'), _hollerith('1'),
         '32', '38', '6', '308', '15', _hollerith('VectorDrive'), '1.', '2', _hollerith('MM'), '1', '0.1',
         _hollerith(now), '1.E-6', _real(biggest), _hollerith(''), _hollerith(''), '11', '0', _hollerith(now)]
    g_lines = [f'{row:<72}G{i:>7}' for i, row in enumerate(_wrap(g, 72), 1)]
    s_text = ['VectorDrive : courbes exactes, un niveau par calque, en millimetres']
    from . import plate_note
    note = plate_note.to_text(doc.plate)
    if note:                                             # la plaque : notée dans la section de départ
        s_text += _lines(f'{plate_note.TAG} : {note}', 72)
    s_lines = [f'{row:<72}S{i:>7}' for i, row in enumerate(s_text, 1)]
    t = f'S{len(s_lines):>7}G{len(g_lines):>7}D{len(d_lines):>7}P{len(p_lines):>7}'
    lines = s_lines + g_lines + d_lines + p_lines + [f'{t:<72}T{1:>7}']
    return '\n'.join(lines) + '\n', len(contours), images


def write(doc: Document, path) -> None:
    text, _n, images = to_string(doc, pathlib.Path(path).name)
    tmp = pathlib.Path(str(path) + '.tmp')
    tmp.write_text(text, encoding='ascii', newline='\n')
    tmp.replace(path)
    if images:
        doc.report.append(f'IGES : {images} image(s) laissée(s) de côté (le format ne garde que des courbes)')
