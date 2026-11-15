"""Programmes machine (G-code ISO, Heidenhain, et les langages des plugins :
SimPL…) en vignette et en fiche, pour le navigateur Ouvrir et la
bibliothèque : le parcours lu (cam.ncread) vu de dessus, un trait de
couleur par outil, les rapides en pointillé gris.
"""
from __future__ import annotations

import pathlib

from ..i18n import tr

#: programmes ISO et Heidenhain que VectorDrive lit lui-même (les plugins en ajoutent : `program_exts`)
NC_EXT = ('.nc', '.iso', '.tap', '.ngc', '.gcode', '.gc', '.cnc', '.mpf', '.spf', '.eia', '.din', '.ptp', '.h')
#: au-delà, un programme n'est pas lu pour sa vignette (lu à l'ouverture seulement)
MAX_BYTES = 64 * 1024 * 1024
#: couleurs des outils successifs
COLORS = ('#1c3d6b', '#c92a2a', '#2b8a3e', '#e67700', '#862e9c', '#0b7285', '#5c940d', '#a61e4d')


def program_exts() -> tuple:
    """Extensions des programmes lus : celles de VectorDrive, puis celles des lecteurs des plugins."""
    out = list(NC_EXT)
    try:
        from ..plugins import REGISTRY
        for _label, exts, _read, _sniff in REGISTRY.nc_readers:
            out += [e.lower() for e in exts or () if e.lower() not in out]
    except Exception:                                    # registre des plugins indisponible : ceux du cœur
        pass
    return tuple(out)


def is_program(path) -> bool:
    return pathlib.Path(path).suffix.lower() in program_exts()


def read_program(path):
    """Parcours du programme (Toolpath, un parcours par outil dans `parts`)."""
    from ..cam import ncread
    p = pathlib.Path(path)
    if p.stat().st_size > MAX_BYTES:
        raise ValueError(tr('programme trop grand pour un aperçu'))
    text = p.read_text(encoding='utf-8', errors='replace')
    return ncread.read(text, p.name, path=str(p))


def _parts(tp) -> list:
    return [q for q in (getattr(tp, 'parts', None) or []) if q.moves] or [tp]


def _xy_bounds(parts):
    """Emprise XY des avances (sinon de tous les mouvements) : un rapide vers
    l'origine machine n'écrase pas la vignette."""
    pts = [(m.x, m.y) for q in parts for m in q.moves if m.kind != 'rapid']
    if not pts:
        pts = [(m.x, m.y) for q in parts for m in q.moves]
    if not pts:
        return None
    xs, ys = [x for x, _y in pts], [y for _x, y in pts]
    return min(xs), min(ys), max(xs), max(ys)


def preview_image(path, size: int = 160):
    """Vignette du programme (QImage carrée, fond blanc) ; None : illisible ou vide."""
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygonF
    try:
        tp = read_program(path)
    except Exception:
        return None
    parts = _parts(tp)
    bb = _xy_bounds(parts)
    if bb is None:
        return None
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor('white'))
    m = max(3, size // 24)
    span = max(bb[2] - bb[0], bb[3] - bb[1], 1e-6)
    k = (size - 2 * m) / span
    ox = m + ((size - 2 * m) - (bb[2] - bb[0]) * k) / 2
    oy = m + ((size - 2 * m) - (bb[3] - bb[1]) * k) / 2
    tol = max(0.005, 0.5 / k)
    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    rapid = QPen(QColor('#adb5bd'), 1.0, Qt.PenStyle.DashLine)
    for i, q in enumerate(parts):
        feed = QPen(QColor(COLORS[i % len(COLORS)]), max(1.0, size / 260))
        for kind, pts in q.polylines(tol):
            poly = QPolygonF([QPointF(ox + (x - bb[0]) * k, size - (oy + (y - bb[1]) * k)) for x, y, _z in pts])
            painter.setPen(rapid if kind == 'rapid' else feed)
            painter.drawPolyline(poly)
    painter.end()
    return img


def describe(path) -> str:
    """Fiche du programme : nom, langage, emprise, outils, longueurs, taille du fichier."""
    p = pathlib.Path(path)
    try:
        tp = read_program(p)
    except Exception as ex:
        return f'{p.name}\n{tr("illisible")} : {ex}'
    lines = [p.name]
    try:
        from ..cam import ncread
        head = p.read_text(encoding='utf-8', errors='replace')[:4000]
        d = ncread.dialect(head, p.name)
        lines.append({'iso': tr('Programme ISO (G-code)'), 'heidenhain': tr('Programme Heidenhain')}.get(d, tr(d)))
    except Exception:                                    # langage non reconnu : la fiche sans lui
        pass
    parts = _parts(tp)
    bb = _xy_bounds(parts)
    if bb:
        lines.append(f'{bb[2] - bb[0]:.2f} × {bb[3] - bb[1]:.2f} mm'.replace('.', ','))
    box = tp.bbox()
    if box:
        lines.append(tr('Z de {0} à {1} mm').format(f'{box[2]:.3f}'.replace('.', ','), f'{box[5]:.3f}'.replace('.', ',')))
    feed, fast = tp.lengths()
    lines.append(tr('{0} outil(s), {1} mouvement(s)').format(len(parts), len(tp.moves)))
    lines.append(tr('{0} mm en avance, {1} mm en rapide').format(f'{feed:.0f}', f'{fast:.0f}'))
    secs = getattr(tp, 'machine_seconds', None)
    if secs:                                             # durée calculée par la machine (fichiers joints)
        from ..cam.timing import format_duration
        lines.append(tr('Durée machine : {0}').format(format_duration(float(secs))))
    if tp.warnings:
        lines.append('; '.join(str(w) for w in tp.warnings[:3]))
    try:
        import datetime as _dt
        st = p.stat()
        lines.append(f'{st.st_size / 1024:.0f} Ko — ' + _dt.datetime.fromtimestamp(st.st_mtime).strftime('%d/%m/%Y'))
    except OSError:
        pass
    return '\n'.join(lines)
