"""Impression directe : page BAT (mêmes éléments que le PDF) ou dessin à
l'échelle (1:1 centré par défaut ; format, orientation, échelle, position
et marge réglables : F10 › Impression). Testable sans imprimante : un
QPrinter peut écrire un PDF."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPageLayout, QPageSize, QPainter, QPen, QTransform
from PySide6.QtPrintSupport import QPrinter

from ..core import geom
from ..core.document import Group
from ..core.geom import Path
from .canvas import to_qpath


def _leaves(items):
    for it in items:
        if not it.visible:
            continue
        if isinstance(it, Group):
            yield from _leaves(it.children)
        else:
            yield it


def _mm_transform(printer: QPrinter, page_w: float, page_h: float, offset=(0.0, 0.0)) -> QTransform:
    """mm du document (Y vers le haut) → points de l'imprimante, origine en
    bas à gauche de la page, `offset` en mm."""
    dpm = printer.resolution() / 25.4
    # la zone peinte commence au bord imprimable : on la ramène au bord de la feuille
    paper = printer.pageLayout().fullRectPixels(printer.resolution())
    paint = printer.pageLayout().paintRectPixels(printer.resolution())
    ox = paper.left() - paint.left()
    oy = paper.top() - paint.top()
    return QTransform(dpm, 0, 0, -dpm, ox + offset[0] * dpm, oy + (page_h - offset[1]) * dpm)


#: la dernière impression d'un dessin : échelle demandée (None : « ajuster »), échelle obtenue, nombre de feuilles
LAST: dict = {}


def reduced() -> float | None:
    """L'échelle à laquelle le dernier dessin imprimé a été réduit pour tenir sur la feuille, quand une échelle était
    demandée ; None s'il a gardé la sienne (ou s'il était à ajuster)."""
    asked, k = LAST.get('asked'), LAST.get('scale')
    return k if asked and k is not None and k < asked * (1.0 - 1e-6) else None


#: réglages de F10 › Impression (dessin) : clé → valeur par défaut
PRINT_DEFAULTS = {'format': 'A4', 'orientation': 'auto', 'echelle': '1', 'position': 'centre', 'marge': 10.0,
                  'plaque': True, 'selection': False, 'reduire': True, 'mosaique': False}
PAGE_IDS = {'A4': QPageSize.PageSizeId.A4, 'A3': QPageSize.PageSizeId.A3, 'A5': QPageSize.PageSizeId.A5,
            'Letter': QPageSize.PageSizeId.Letter, 'A6': QPageSize.PageSizeId.A6, 'A2': QPageSize.PageSizeId.A2,
            'A1': QPageSize.PageSizeId.A1}
#: échelles normalisées, de la plus grande à la plus petite : « ajustée à la feuille, à l'échelle conseillée » (les
#: réductions : celles du BAT, `proof.NORMAL_FACTORS`)
STANDARD_SCALES = (50.0, 20.0, 10.0, 5.0, 2.0, 1.0, 0.5, 0.4, 0.2, 0.1, 0.05, 0.04, 0.02, 0.01)


def advised_scale(fit: float) -> float:
    """La plus grande échelle normalisée qui ne dépasse pas `fit` (celle qui remplirait la feuille) ; plus petit que
    toutes : la plus petite."""
    return next((s for s in STANDARD_SCALES if s <= fit * (1.0 + 1e-9)), STANDARD_SCALES[-1])


def sheet_mm(fmt: str, orientation: str = 'auto', bb=None) -> tuple:
    """(largeur, hauteur) de la feuille `fmt` (mm) dans l'orientation donnée ; 'auto' : selon la boîte `bb`."""
    size = QPageSize(PAGE_IDS.get(fmt, QPageSize.PageSizeId.A4)).size(QPageSize.Unit.Millimeter)
    w, h = sorted((size.width(), size.height()))
    wide = orientation == 'paysage' or (orientation == 'auto' and bb is not None and bb[2] - bb[0] > bb[3] - bb[1])
    return (h, w) if wide else (w, h)


def extent(doc, opts: dict | None = None, items=None) -> tuple:
    """(boîte imprimée en mm ou None, plaque montrée ?) : les objets (`items`, sinon le dessin visible) et la plaque
    si elle est imprimée (pas avec la sélection seule) ; `quoi` 'plaque' : la plaque seule (le dessin y est coupé)."""
    from ..cam.fixture import shown
    doc, items = shown(doc, items)                       # plaque de reprise posée : pas imprimée (question 43)
    o = dict(PRINT_DEFAULTS, **(opts or {}))
    pl = doc.plate
    if o.get('quoi') == 'plaque' and pl is not None:
        return (pl.x, pl.y, pl.x + pl.width, pl.y + pl.height), bool(o['plaque']) and pl.visible
    leaves_src = items if items else list(doc.iter_items(visible_only=True))
    show_plate = bool(o['plaque']) and (not items or o.get('quoi') == 'calques') and pl is not None and pl.visible
    bb = geom.bbox_union(it.bbox() for it in leaves_src) if leaves_src else None
    if show_plate:
        pb = (pl.x, pl.y, pl.x + pl.width, pl.y + pl.height)
        bb = pb if bb is None else (min(bb[0], pb[0]), min(bb[1], pb[1]), max(bb[2], pb[2]), max(bb[3], pb[3]))
    return bb, show_plate


def fit_scale(opts: dict, bb, pw: float, ph: float) -> tuple:
    """(échelle, échelle demandée ou None, feuilles de la mosaïque ou None) de la boîte `bb` sur une feuille pw × ph
    (mm), marge comprise : « ajuster » remplit la feuille, « conseillee » prend l'échelle normalisée qui tient ; une
    échelle donnée trop grande passe en mosaïque ou est réduite (réglages)."""
    o = dict(PRINT_DEFAULTS, **(opts or {}))
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    m = max(0.0, float(o['marge']))
    aw, ah = max(1.0, pw - 2 * m), max(1.0, ph - 2 * m)
    fit = min(aw / max(w, 1e-9), ah / max(h, 1e-9))
    e = str(o['echelle'])
    if e == 'ajuster':
        return fit, None, None
    if e == 'conseillee':
        return advised_scale(fit), None, None
    try:
        k = float(e.replace(',', '.'))
    except ValueError:
        k = 1.0
    k = k if k > 0 else 1.0
    if o.get('mosaique') and (w * k > aw or h * k > ah):
        return k, k, mosaic_tiles(bb, k, m, aw, ah)         # à l'échelle, sur plusieurs feuilles
    if o['reduire'] and (w * k > aw or h * k > ah):
        return fit, k, None
    return k, k, None


def print_options(settings) -> dict:
    """Réglages d'impression du dessin (F10 › Impression)."""
    from .options import BY_KEY, value
    out = dict(PRINT_DEFAULTS)
    for k in out:
        key = f'impression/{k}'
        if key in BY_KEY:
            out[k] = value(settings, key)
    return out


def setup_printer(printer: QPrinter, opts: dict) -> None:
    """Format et orientation de la feuille selon les réglages (avant la boîte d'impression)."""
    if opts.get('format') in PAGE_IDS:
        printer.setPageSize(QPageSize(PAGE_IDS[opts['format']]))
    if opts.get('orientation') in ('portrait', 'paysage'):
        printer.setPageOrientation(QPageLayout.Orientation.Landscape if opts['orientation'] == 'paysage'
                                   else QPageLayout.Orientation.Portrait)


def print_drawing(doc, printer: QPrinter, opts: dict | None = None, items=None) -> tuple[float, float]:
    """Dessin à l'échelle sur la feuille (par défaut : 1:1, centré, orientation selon le dessin).
    `opts` (print_options) : échelle (« 1 », « 2 », « 0.5 »…, « ajuster » ou « conseillee »), orientation
    (« auto » : selon le dessin), position (« centre » ou « coin » : en bas à gauche à la marge), marge (mm),
    plaque, réduire (un dessin plus grand que la feuille est réduit), `quoi` ('plaque' : la plaque et ce qu'elle
    contient, coupé à son bord ; 'calques' : `items` avec la plaque) ; `items` : seulement ces objets.
    Renvoie le format de la feuille (mm)."""
    from ..cam.fixture import shown
    doc, items = shown(doc, items)                       # plaque de reprise posée : pas imprimée (question 43)
    o = dict(PRINT_DEFAULTS, **(opts or {}))
    leaves_src = items if items else list(doc.iter_items(visible_only=True))
    bb, show_plate = extent(doc, o, items)
    clip = bb if o.get('quoi') == 'plaque' and doc.plate is not None else None
    full = printer.pageLayout().fullRect(QPageLayout.Unit.Millimeter)
    pw, ph = full.width(), full.height()
    k, offset = 1.0, (0.0, 0.0)
    asked = None                                         # l'échelle demandée, quand ce n'est pas « ajuster »
    tiles = None                                         # mosaïque : [(décalage, zone du dessin, libellé)]
    if bb:
        w, h = bb[2] - bb[0], bb[3] - bb[1]
        if o['orientation'] == 'auto' and (w > h) != (pw > ph):     # orientation selon le dessin
            printer.setPageOrientation(QPageLayout.Orientation.Landscape if w > h
                                       else QPageLayout.Orientation.Portrait)
            full = printer.pageLayout().fullRect(QPageLayout.Unit.Millimeter)
            pw, ph = full.width(), full.height()
        m = max(0.0, float(o['marge']))
        k, asked, tiles = fit_scale(o, bb, pw, ph)
        if o['position'] == 'coin':
            offset = (m - bb[0] * k, m - bb[1] * k)
        else:
            offset = ((pw - w * k) / 2 - bb[0] * k, (ph - h * k) / 2 - bb[1] * k)
    p = QPainter(printer)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    for n, (off, zone, label) in enumerate(tiles or [(offset, None, '')]):
        if n:
            printer.newPage()
        p.save()
        p.setTransform(QTransform.fromScale(k, k) * _mm_transform(printer, pw, ph, off))
        cut = zone
        if clip is not None:                             # la plaque : le dessin coupé à son bord
            cut = clip if cut is None else (max(cut[0], clip[0]), max(cut[1], clip[1]), min(cut[2], clip[2]),
                                            min(cut[3], clip[3]))
        if cut is not None:                              # feuille de la mosaïque : sa part du dessin seulement
            from PySide6.QtCore import QRectF
            p.setClipRect(QRectF(cut[0], cut[1], max(0.0, cut[2] - cut[0]), max(0.0, cut[3] - cut[1])))
        _paint_drawing(p, doc, leaves_src, show_plate, k)
        p.restore()
        if zone is not None:
            _tile_marks(p, printer, pw, ph, m, label)
    p.end()
    LAST.clear()
    LAST.update(asked=asked, scale=k, sheets=len(tiles) if tiles else 1)
    return pw, ph


#: mosaïque : recouvrement entre deux feuilles voisines (mm, à recouper ou superposer)
MOSAIC_OVERLAP = 6.0


def mosaic_tiles(bb, k: float, m: float, aw: float, ah: float) -> list:
    """Feuilles d'une mosaïque à l'échelle `k` : [(décalage page, zone du dessin, libellé)], de bas en
    haut et de gauche à droite (colonnes A, B… ; rangées 1, 2…)."""
    import math
    w, h = (bb[2] - bb[0]) * k, (bb[3] - bb[1]) * k
    sx, sy = max(1.0, aw - MOSAIC_OVERLAP), max(1.0, ah - MOSAIC_OVERLAP)
    nx = max(1, math.ceil((w - MOSAIC_OVERLAP) / sx - 1e-9))
    ny = max(1, math.ceil((h - MOSAIC_OVERLAP) / sy - 1e-9))
    out = []
    for j in range(ny):
        for i in range(nx):
            x0, y0 = bb[0] + i * sx / k, bb[1] + j * sy / k
            zone = (x0, y0, x0 + aw / k, y0 + ah / k)
            label = f'{chr(65 + i % 26)}{j + 1}  ({len(out) + 1}/{nx * ny})'
            out.append(((m - x0 * k, m - y0 * k), zone, label))
    return out


def _paint_drawing(p: QPainter, doc, leaves_src, show_plate: bool, k: float) -> None:
    pen = QPen(QColor('black'), 0.1 / k)
    if show_plate:
        pl = doc.plate
        p.setPen(QPen(QColor('#888888'), 0.1 / k, Qt.PenStyle.DashLine))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(to_qpath(Path([geom.rect(pl.x, pl.y, pl.width, pl.height, pl.corner_radius)])))
    for leaf in _leaves(leaves_src):
        path = getattr(leaf, 'path', None) or getattr(leaf, 'outline', None)
        if not path:
            continue
        q = to_qpath(path)
        q.setFillRule(Qt.FillRule.OddEvenFill)
        p.setPen(pen)
        p.setBrush(QColor('black') if getattr(leaf, 'filled', False) or leaf.__class__.__name__ == 'Text'
                   else Qt.BrushStyle.NoBrush)
        p.drawPath(q)


def _tile_marks(p: QPainter, printer: QPrinter, pw: float, ph: float, m: float, label: str) -> None:
    """Cadre de la zone imprimée (à recouper) et repère de la feuille (« B2 (5/6) »)."""
    p.save()
    p.setTransform(_mm_transform(printer, pw, ph))
    p.setPen(QPen(QColor('#999999'), 0.15, Qt.PenStyle.DashLine))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(to_qpath(Path([geom.rect(m, m, pw - 2 * m, ph - 2 * m)])))
    p.restore()
    p.save()
    p.resetTransform()
    dpm = printer.resolution() / 25.4
    f = p.font()
    f.setPixelSize(max(8, int(3.0 * dpm)))
    p.setFont(f)
    p.setPen(QColor('#666666'))
    p.drawText(int((m + 1) * dpm), int((m - 1.5) * dpm), label)
    p.restore()


def paint_prims(p: QPainter, prims, base: QTransform, min_pen: float = 0.0) -> None:
    """Primitives d'une page BAT (mm, y vers le haut) peintes avec `base`
    (mm → appareil) ; les images à leur pleine résolution."""
    from ..io.raster import qimage_of
    seen: dict = {}                                      # la même image (filigrane répété) : décodée une fois
    for pr in prims:
        if pr.image is not None:
            if id(pr.image) not in seen:
                seen[id(pr.image)] = qimage_of(pr.image)
            q = seen[id(pr.image)]
            if q is None:
                continue
            m = pr.matrix
            p.setTransform(QTransform(m.a / q.width(), m.b / q.width(), m.c / q.height(), m.d / q.height(),
                                      m.e, m.f) * base)
            p.drawImage(0, 0, q)
            continue
        p.setTransform(base)
        q = to_qpath(pr.path)
        q.setFillRule(Qt.FillRule.OddEvenFill)
        col = QColor.fromRgbF(*pr.color)
        p.setPen(QPen(col, max(pr.width, min_pen)) if pr.width > 0 else Qt.PenStyle.NoPen)
        fcol = QColor.fromRgbF(*pr.fill_color) if getattr(pr, 'fill_color', None) else col
        p.setBrush(fcol if pr.fill else Qt.BrushStyle.NoBrush)
        p.drawPath(q)


def print_proof(doc, info, printer: QPrinter, items=None) -> None:
    """Page BAT (format et orientation choisis) : mêmes primitives que l'épreuve PDF."""
    from ..io import proof
    prims, PW, PH = proof.build(doc, info, items)
    from PySide6.QtCore import QSizeF
    ids = {'A4': QPageSize.PageSizeId.A4, 'A3': QPageSize.PageSizeId.A3, 'A5': QPageSize.PageSizeId.A5,
           'Letter': QPageSize.PageSizeId.Letter}
    page = getattr(info, 'page', 'A4')
    printer.setPageSize(QPageSize(ids[page]) if page in ids
                        else QPageSize(QSizeF(min(PW, PH), max(PW, PH)), QPageSize.Unit.Millimeter))
    printer.setPageOrientation(QPageLayout.Orientation.Landscape if PW > PH else QPageLayout.Orientation.Portrait)
    p = QPainter(printer)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    tf = _mm_transform(printer, PW, PH)
    paint_prims(p, prims, tf)
    for title, lines in proof.price_pages(doc, info, items):     # question 29 : la page des prix
        for page in proof.price_page_prims(info, title, lines, PW, PH):
            printer.newPage()
            paint_prims(p, page, tf)
    p.end()
