"""BAT (bon à tirer) : épreuve PDF à faire valider par le client.

Une page (A4 par défaut ; A3, A5 ou Letter ; paysage ou portrait selon le
dessin, ou imposé), qui montre **la sélection** s'il y en a une (ajustée à
la page : plus besoin de zoomer dans un grand plan de travail), sinon tout
le dessin sur sa plaque :

* le dessin, sur sa plaque, selon l'échelle choisie — taille réelle (1:1
  si elle tient, sinon la réduction normalisée immédiatement inférieure),
  normalisée (plus grande échelle normalisée qui tient, agrandissements
  10:1, 5:1, 2:1 compris), ajustée à la page, ou imposée — l'échelle est
  écrite ;
* les cotes d'encombrement (largeur × hauteur de la plaque, ou du dessin) ;
* la légende des outils employés (couleur = outil) ;
* un cartouche : client, référence, désignation, matière, dimensions,
  date, numéro de BAT, remarques, case « Bon pour accord ».

Les textes de la page sont des **contours vectoriels** (polices installées
via `core.text`) : aucune police à embarquer, rendu identique partout. Le
PDF est en qualité maximale : courbes de Bézier exactes (rien n'est
aplati), coordonnées au 1/10 000 de point, images à leur pleine résolution,
sans perte (Flate), transparence comprise.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import pathlib
import zlib
from dataclasses import dataclass, field

from ..core import brut as BR
from ..core import geom, text
from ..core.document import Document, Group, Image
from ..core.geom import Affine, Path
from ..i18n import decimal_sep, tr

PT_MM = 25.4 / 72
SCALES = (1, 2, 2.5, 5, 10, 20, 25, 50, 100)
#: échelles normalisées (facteur page/réel), des agrandissements aux réductions
NORMAL_FACTORS = (10, 5, 2, 1, 1 / 2, 1 / 2.5, 1 / 5, 1 / 10, 1 / 20, 1 / 25, 1 / 50, 1 / 100)
PAGES = {'A4': (210.0, 297.0), 'A3': (297.0, 420.0), 'A5': (148.0, 210.0), 'Letter': (215.9, 279.4)}
SCALE_MODES = ('vues', 'reelle', 'normalisee', 'ajuster', 'imposee')
#: agrandissements proposés pour une petite pièce (facteur page/réel)
ENLARGEMENTS = (20, 10, 5, 2.5, 2)
CONTENTS = ('auto', 'selection', 'tout')
FONT = 'Arial'


@dataclass
class ProofInfo:
    client: str = ''
    reference: str = ''
    designation: str = ''
    material: str = ''
    bat_number: str = '1'
    author: str = ''
    notes: str = ''
    date: str = field(default_factory=lambda: dt.date.today().strftime('%d/%m/%Y'))
    # mise en page
    content: str = 'auto'            # auto (la sélection s'il y en a une), selection, tout
    fit_selection: bool = False      # sélection ajustée à la page (sinon : échelle choisie)
    page: str = 'A4'                 # A4, A3, A5, Letter
    orientation: str = 'auto'        # auto, portrait, paysage
    scale_mode: str = 'vues'         # vues (1:1 cotée + agrandissement ou réduction), reelle, normalisee,
    #                                  ajuster, imposee
    enlarge_below: float = 30.0      # vues : agrandissement ajouté sous cette taille (mm)
    enlarge: bool = False            # vues : toujours ajouter une vue agrandie
    scale: float = 1.0               # échelle imposée (facteur : 2 = 2:1, 0,5 = 1:2)
    margin: float = 10.0             # mm
    title_block: bool = True         # cartouche
    dims: bool = True                # cotes d'encombrement
    legend: bool = True              # légende des outils
    mono: bool = False               # tout en noir (impression noir et blanc)
    fill: bool = False               # coloriage : formes fermées remplies (comme « Remplissage » à l'écran)
    #: coloriage : 'contour' (contours fermés seulement, pleins et vides alternés d'un contour à l'autre, chaque plein
    #: dans la couleur de son contour), 'noir' (de même, tout en noir) ou 'teinte' (chaque objet dans une teinte claire
    #: de la couleur de l'outil)
    fill_mode: str = 'contour'
    title_color: str = ''            # couleur du cartouche (#rrvvbb) ; vide : noir ; 'logo' : prise sur le logo
    theme_all: bool = False          # cette couleur aussi pour le cadre, l'en-tête et les cotes
    decimals: int = 2                # précision des cotes écrites
    keep_zeros: bool = False         # 12,50 plutôt que 12,5
    show_bruts: bool = True          # bruts des ensembles dessinés et cotés
    dims_each: bool = True           # une cote par gravure (chaque objet ou groupe de premier niveau)
    prices: bool = True              # prix du devis par gravure (si un plugin en donne un)
    #: les prix sur une page à part, après la page technique (si un plugin en donne une ; question 29)
    price_page: bool = True
    company: str = ''                # en-tête : nom de l'entreprise
    logo: str = ''                   # en-tête, à gauche : fichier du logo, image (PNG, JPEG…) ou dessin (SVG, PDF, DXF…)
    logo2: str = ''                  # en-tête, à droite : second logo (celui du client…)
    watermark: bool = False          # filigrane : un texte répété en biais, clair, en fond du dessin
    watermark_text: str = ''         # son texte ; vide : le nom de l'entreprise, sinon « BAT »
    watermark_color: str = ''        # sa couleur (#rrvvbb) ; vide : celle du cartouche, sinon un bleu
    watermark_kind: str = 'texte'    # son motif : 'texte' ou 'logo'
    watermark_logo: str = ''         # le logo du motif (image ou dessin) ; vide : celui de l'en-tête
    watermark_size: float = 9.0      # hauteur du texte (mm) ; le logo : le double
    watermark_angle: float = 30.0    # inclinaison (degrés)
    watermark_gap: float = 10.0      # écart entre deux motifs d'une rangée (mm) ; entre deux rangées : 0,4 fois autant
    watermark_strength: int = 20     # intensité (%) : 100, la couleur même ; peu, très clair
    watermark_layout: str = 'trame'  # 'trame' : répété en quinconce ; 'centre' : un seul, au milieu
    as_image: bool = False           # PDF : le dessin écrit en image — son tracé ne peut pas en être repris
    image_dpi: int = 300             # résolution de cette image (points par pouce)
    open_folder: bool = False        # après l'écriture du PDF : son dossier ouvert, le fichier montré
    #: dos de la gravure (demande du 27/11) : {'on', 'w', 'h', 'ep', 'trous', 'filetage', 'pos', 'x', 'y', 'dx', 'dy'}
    #: (voir `back_spec`) ; jamais dans les réglages : propre au client (carnet) et au dessin (`doc.extra`)
    back: dict = field(default_factory=dict)

#: champs du cartouche propres au dessin (round 1160, demande « BaT ne pas garder en mémoire champs clients et ref (sauf
#: si plusieurs édition de bat dans un même fichier) car user doit choisir dans carnet client ») : jamais dans les
#: réglages ; gardés dans le dessin (`doc.extra[DOC_KEY]`) pour sa prochaine édition du BAT. `logo2` : le logo du
#: client (second logo de l'en-tête), posé par le choix dans le carnet
DOC_FIELDS = ('client', 'reference', 'designation', 'material', 'bat_number', 'logo2')
DOC_KEY = 'bat'
#: le dos de la gravure du dernier BAT du dessin, dans `doc.extra[DOC_KEY]` (ignoré d'une version d'avant)
BACK_KEY = 'dos'


def doc_back(doc) -> dict:
    """Réglages du dos de la gravure du dernier BAT édité de ce dessin ({} : aucun)."""
    kept = doc.extra.get(DOC_KEY) if isinstance(getattr(doc, 'extra', None), dict) else None
    b = kept.get(BACK_KEY) if isinstance(kept, dict) else None
    return dict(b) if isinstance(b, dict) else {}


def doc_fields(doc) -> dict:
    """Champs du cartouche du dernier BAT édité de ce dessin ({} : aucun BAT encore)."""
    kept = doc.extra.get(DOC_KEY) if isinstance(getattr(doc, 'extra', None), dict) else None
    return {k: str(kept[k]) for k in DOC_FIELDS if isinstance(kept, dict) and kept.get(k) is not None}


def keep_doc_fields(doc, info) -> bool:
    """Les champs du cartouche de `info` gardés dans le dessin (rien si tous sont vides) ; rend vrai s'ils ont
    changé. La matière de la plaque, que le BAT reprend d'office, n'est pas gardée : le cartouche la reprend de la
    plaque, et elle seule ne rend pas le cartouche « rempli »."""
    if not isinstance(getattr(doc, 'extra', None), dict):
        return False
    new = {k: str(getattr(info, k) or '') for k in DOC_FIELDS}
    plate = getattr(doc, 'plate', None)
    if plate is not None and new['material'] == str(getattr(plate, 'material', '') or ''):
        new['material'] = ''
    back = back_spec(info)
    if not any(v for k, v in new.items() if k != 'bat_number') and new['bat_number'] in ('', '1') and not back:
        # cartouche vide (le n° d'office n'y compte pas), sans dos : rien à garder, ni compagnon pour lui
        return doc.extra.pop(DOC_KEY, None) is not None
    if back:                                         # le dos de la gravure, repris à la prochaine édition du BAT
        new[BACK_KEY] = back
    if doc.extra.get(DOC_KEY) == new:
        return False
    doc.extra[DOC_KEY] = new
    return True


LAYOUT_FIELDS = ('content', 'fit_selection', 'page', 'orientation', 'scale_mode', 'scale', 'margin',
                 'title_block', 'dims', 'legend', 'mono', 'enlarge_below', 'enlarge', 'fill', 'dims_each', 'prices',
                 'company', 'logo', 'fill_mode', 'title_color', 'theme_all', 'decimals', 'keep_zeros', 'logo2',
                 'show_bruts', 'watermark', 'watermark_text', 'watermark_color', 'as_image', 'image_dpi',
                 'open_folder', 'watermark_kind', 'watermark_logo', 'watermark_size', 'watermark_angle', 'watermark_gap',
                 'watermark_strength', 'watermark_layout', 'price_page')
#: hauteur du logo dans l'en-tête de la page (mm) ; largeur au plus
LOGO_H, LOGO_W = 10.0, 45.0
_LOGOS: dict = {}
#: logos gardés en mémoire (images, dessins) : l'en-tête, le deuxième logo, le filigrane…
LOGO_CACHE = 4


def _keep(cache: dict, key, value):
    """Garde `value` sous `key`, les plus anciens oubliés au-delà de `LOGO_CACHE` ; rend `value`."""
    while len(cache) >= LOGO_CACHE:
        cache.pop(next(iter(cache)), None)
    cache[key] = value
    return value


def logo_image(path: str):
    """Logo de l'en-tête en objet Image (PNG), gardé tant que le fichier ne change pas ; None si
    absent ou illisible."""
    import os
    try:
        key = (str(path), os.path.getmtime(path))
    except (OSError, TypeError, ValueError):
        return None
    if key in _LOGOS:
        return _LOGOS[key]
    try:
        from PySide6.QtCore import QBuffer, QIODevice
        from .raster import load_image
        img, _size, _note = load_image(path, max_pixels=4_000_000)
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        img.save(buf, 'PNG')
        got = (Image(data=bytes(buf.data()), fmt='png'), img.width() / max(1, img.height()))
    except Exception:                                # logo illisible : BAT sans logo
        got = None
    return _keep(_LOGOS, key, got)


#: logos dessinés : écrits en tracés exacts, sans passer par une image
VECTOR_LOGOS = ('.svg', '.pdf', '.ai', '.eps', '.ps', '.dxf', '.vnd', '.gvt', '.smb')
_VECTOR_LOGOS: dict = {}


def is_vector_logo(path) -> bool:
    """Le logo est-il un dessin, lu en tracés ? Tout format que VectorDrive lit, sauf les images."""
    if pathlib.Path(str(path)).suffix.lower() in VECTOR_LOGOS:
        return True
    from . import registry
    f = registry.by_extension(str(path))
    return f is not None and f.reader is not None and f.key != 'image'


def logo_filter() -> str:
    """Extensions de la boîte « Logo » : les images, puis tous les dessins que VectorDrive lit."""
    from . import registry
    exts = ['.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tif', '.tiff', '.webp', '.ico', '.heic', '.heif', '.avif']
    for f in registry.all_formats():
        if f.reader is not None:
            exts += [e for e in f.extensions if e not in exts]
    return ' '.join('*' + e for e in exts)


#: préréglages du BAT : ce qu'un préréglage ne garde pas (propre à chaque BAT ou à chaque client)
PRESET_SKIP = ('content', 'fit_selection', 'logo2')


def preset_of(info: 'ProofInfo') -> dict:
    """Ce qu'un préréglage garde d'un BAT : mise en page, couleurs, entreprise et logo, filigrane, PDF."""
    return {k: getattr(info, k) for k in LAYOUT_FIELDS if k not in PRESET_SKIP}


def logo_vector(path: str):
    """Logo dessiné : ([(contour, couleur)], [contours ouverts et leur couleur], boîte) gardés tant que le fichier ne
    change pas ; None s'il est absent, illisible ou vide."""
    import os
    if not is_vector_logo(path):
        return None
    try:
        key = (str(path), os.path.getmtime(path))
    except (OSError, TypeError, ValueError):
        return None
    if key in _VECTOR_LOGOS:
        return _VECTOR_LOGOS[key]
    return _keep(_VECTOR_LOGOS, key, _read_vector_logo(path))


def _read_vector_logo(path: str):
    from . import companion
    try:
        doc = companion.open_document(path, plates=False)    # son compagnon, sans plaques de reprise (round 1174)
    except Exception:                                # logo illisible : BAT sans logo
        return None
    closed, opened = [], []
    boxes = []
    for L in doc.layers:
        if not L.visible:
            continue
        for it in _leaves(L.items):
            p = getattr(it, 'path', None) or getattr(it, 'outline', None)
            if not p:
                continue
            col = _rgb(doc.item_color(it))
            closed += [(c, col) for c in p.contours if c.closed]
            opened += [(c, col) for c in p.contours if not c.closed]
            boxes.append(p.bbox())
    box = geom.bbox_union(boxes)
    if not box or box[2] - box[0] <= 0 or box[3] - box[1] <= 0:
        return None
    return closed, opened, box


def logo_color(path: str) -> str:
    """Couleur dominante d'un logo (#rrvvbb), en laissant le blanc, les gris et le noir ; vide s'il n'en a pas."""
    vec = logo_vector(path) if path else None
    if vec is not None:
        weight: dict = {}
        for c, col in vec[0] + vec[1]:
            r, g, b = col
            if max(r, g, b) - min(r, g, b) > 0.15:
                x0, y0, x1, y1 = c.bbox()
                weight[col] = weight.get(col, 0.0) + (x1 - x0) * (y1 - y0) + 1e-6
        if not weight:
            return ''
        r, g, b = max(weight, key=weight.get)
        return '#{:02x}{:02x}{:02x}'.format(round(r * 255), round(g * 255), round(b * 255))
    lg = logo_image(path) if path else None
    if lg is None:
        return ''
    import numpy as np
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage
    from .raster import qimage_of
    q = qimage_of(lg[0])
    if q is None or q.isNull():
        return ''
    q = q.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    q = q.convertToFormat(QImage.Format.Format_RGBA8888)
    px = np.frombuffer(bytes(q.constBits())[:q.sizeInBytes()], np.uint8).reshape(q.height(), q.bytesPerLine())
    px = px[:, :4 * q.width()].reshape(q.height(), q.width(), 4).astype(float)
    px = px[px[..., 3] > 128][:, :3]
    if not len(px):
        return ''
    hi, lo = px.max(axis=1), px.min(axis=1)
    vivid = px[(hi - lo) > 45]                       # ni blanc, ni gris, ni noir
    if len(vivid) * 50 < len(px):                    # moins de 2 % : ce n'est qu'un reflet
        return ''
    quant = (vivid // 48).astype(int)
    keys = quant[:, 0] * 36 + quant[:, 1] * 6 + quant[:, 2]
    top = np.bincount(keys).argmax()
    r, g, b = vivid[keys == top].mean(axis=0)
    return '#{:02x}{:02x}{:02x}'.format(round(r), round(g), round(b))


def accent(info: 'ProofInfo') -> tuple | None:
    """Couleur du thème (None : le noir de toujours). Jamais en noir et blanc."""
    if info.mono:
        return None
    c = getattr(info, 'title_color', '') or ''
    if c == 'logo':
        c = logo_color(info.logo) or logo_color(getattr(info, 'logo2', ''))
    return _rgb(c) if c else None


def _logo_prims(prims: list, path: str, x: float, top: float, right: bool = False) -> float:
    """Le logo dans sa place de l'en-tête, en haut à `top`, depuis `x` (ou jusqu'à `x` si `right`). Rend sa largeur,
    0 s'il n'y a pas de logo."""
    vec = logo_vector(path) if path else None
    if vec is not None:
        closed, opened, b = vec
        bw, bh = b[2] - b[0], b[3] - b[1]
        k = min(LOGO_W / bw, LOGO_H / bh)
        w = bw * k
        x0 = x - w if right else x
        m = Affine(k, 0, 0, k, x0 - b[0] * k, top - bh * k - b[1] * k)
        prims.extend(_regions_prims([(c.transformed(m), col) for c, col in closed], 0.05))
        for c, col in opened:
            prims.append(Prim(Path([c.transformed(m)]), col, 0.1))
        return w
    lg = logo_image(path) if path else None
    if lg is None:
        return 0.0
    img, ratio = lg
    h = LOGO_H
    w = min(LOGO_W, h * ratio)
    h = w / ratio if ratio else h
    prims.append(Prim(Path([]), image=img, matrix=Affine(w, 0, 0, -h, x - w if right else x, top)))
    return w


def _header(prims: list, info: 'ProofInfo', PW: float, PH: float, margin: float, scale_text: str) -> None:
    """En-tête de la page : logo, entreprise, puis « BAT — à valider avant fabrication » ; second logo à droite."""
    x, top = margin + 2, PH - margin - 1.5
    w = _logo_prims(prims, info.logo, x, top)
    if w:
        x += w + 3
    _logo_prims(prims, getattr(info, 'logo2', ''), PW - margin - 2, top, right=True)
    if info.company:
        lab = _label(info.company, 3.5, x, PH - margin - 6.5)
        prims.append(lab)
        bb = lab.path.bbox()
        x = (bb[2] if bb else x) + 4
    text = tr('BAT — à valider avant fabrication') + (f'   {scale_text}' if not info.title_block else '')
    tc = accent(info) if getattr(info, 'theme_all', False) else None
    prims.append(_label(text, 2.2, x, PH - margin - 5, color=tc or (0.6, 0.1, 0.1)))


def watermark_text(info: 'ProofInfo') -> str:
    """Texte du filigrane : celui qui est donné, sinon le nom de l'entreprise, sinon « BAT »."""
    return (str(getattr(info, 'watermark_text', '') or '').strip() or str(info.company or '').strip() or 'BAT')


def _wm(info: 'ProofInfo', key: str, lo: float, hi: float) -> float:
    """Réglage numérique du filigrane, borné ; illisible : son défaut."""
    try:
        v = float(getattr(info, key))
    except (TypeError, ValueError):
        v = float(getattr(ProofInfo, key))
    return max(lo, min(hi, v))


def watermark_color(info: 'ProofInfo') -> tuple:
    """Couleur du filigrane, claire : une teinte de la couleur donnée (sinon celle du cartouche, sinon un bleu), à
    l'intensité réglée (20 % d'office) ; en noir et blanc, un gris clair (de même)."""
    k = _wm(info, 'watermark_strength', WATERMARK_STRENGTH[0], WATERMARK_STRENGTH[1]) / 100.0
    if info.mono:
        return tint((0.0, 0.0, 0.0), 0.65 * k)
    c = str(getattr(info, 'watermark_color', '') or '')
    base = _rgb(c) if c else (accent(info) or (0.12, 0.31, 0.61))
    return tint(base, k)


#: filigrane, bornes des réglages : hauteur du texte (mm), angle (°), écart (mm), intensité (%) ; logo : hauteur du
#: texte multipliée par `WATERMARK_LOGO`
WATERMARK_SIZE, WATERMARK_ANGLE, WATERMARK_GAP, WATERMARK_STRENGTH = (1.0, 200.0), (-90.0, 90.0), (0.0, 200.0), (3, 100)
WATERMARK_LOGO = 2.0
#: logo image du filigrane : au plus tant de pixels de côté (le motif fait quelques centimètres ; répété, il se peint
#: et s'écrit une fois par motif)
WATERMARK_PIXELS = 1000
_WM_IMAGES: dict = {}


def watermark_image(img, col: tuple):
    """Le logo image en filigrane : chaque pixel dans la couleur `col`, d'autant plus opaque qu'il est foncé (le blanc
    et le transparent disparaissent), réduit à `WATERMARK_PIXELS` ; objet Image (PNG), le dernier gardé."""
    key = (len(img.data), hash(img.data), col)
    got = _WM_IMAGES.get(key)
    if got is not None:
        return got
    import numpy as np
    from PySide6.QtCore import QBuffer, QIODevice, Qt
    from PySide6.QtGui import QImage
    from .raster import _app, qimage_of
    _app()
    q = qimage_of(img)
    if q is None or q.isNull():
        return None
    if max(q.width(), q.height()) > WATERMARK_PIXELS:
        q = q.scaled(WATERMARK_PIXELS, WATERMARK_PIXELS, Qt.AspectRatioMode.KeepAspectRatio,
                     Qt.TransformationMode.SmoothTransformation)
    q = q.convertToFormat(QImage.Format.Format_RGBA8888)
    w, h = q.width(), q.height()
    px = np.frombuffer(bytes(q.constBits())[:q.sizeInBytes()], np.uint8).reshape(h, q.bytesPerLine())
    px = px[:, :4 * w].reshape(h, w, 4).astype(float)
    dark = 1.0 - (0.299 * px[..., 0] + 0.587 * px[..., 1] + 0.114 * px[..., 2]) / 255.0
    out = np.empty((h, w, 4), np.uint8)
    out[..., 0], out[..., 1], out[..., 2] = (round(c * 255) for c in col)
    out[..., 3] = np.clip(dark * px[..., 3], 0, 255).astype(np.uint8)
    res = QImage(out.tobytes(), w, h, 4 * w, QImage.Format.Format_RGBA8888).copy()
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    res.save(buf, 'PNG')
    got = Image(data=bytes(buf.data()), fmt='png')
    _WM_IMAGES.clear()                                   # l'aperçu peut se construire dans un autre fil : rendre `got`
    _WM_IMAGES[key] = got
    return got


def watermark_motif(info: 'ProofInfo') -> list:
    """Le motif du filigrane, droit, posé à l'origine (mm) : ses primitives. Le logo (`watermark_logo`, sinon celui de
    l'en-tête) dessiné ou image, haut de `WATERMARK_LOGO` fois la hauteur du texte, tout entier dans la couleur du
    filigrane ; pas de logo lisible : le texte."""
    col = watermark_color(info)
    size = _wm(info, 'watermark_size', *WATERMARK_SIZE)
    if getattr(info, 'watermark_kind', 'texte') == 'logo':
        path = str(getattr(info, 'watermark_logo', '') or '') or str(info.logo or '')
        vec = logo_vector(path) if path else None
        h = size * WATERMARK_LOGO
        if vec is not None:
            closed, opened, b = vec
            k = h / (b[3] - b[1])
            m = Affine(k, 0, 0, k, -b[0] * k, -b[1] * k)
            out = [Prim(p, col, 0, True, layer='dessin')
                   for p, _c in even_odd_regions([(c.transformed(m), col) for c, _col in closed])]
            out += [Prim(Path([c.transformed(m) for c, _col in opened]), col, max(0.05, h / 60.0), layer='dessin')] \
                if opened else []
            return out
        lg = logo_image(path) if path else None
        light = watermark_image(lg[0], col) if lg is not None else None
        if light is not None:
            return [Prim(Path([]), image=light, matrix=Affine(h * lg[1], 0, 0, -h, 0, h), layer='dessin')]
    lay = text.layout(watermark_text(info), FONT, size, align='center')
    return [Prim(lay, col, 0, True, layer='dessin')] if lay.contours else []


def _moved(pr: Prim, m: Affine) -> Prim:
    return Prim(pr.path.transformed(m) if pr.path.contours else Path([]), pr.color, pr.width, pr.fill, pr.fill_color,
                pr.image, (m @ pr.matrix) if pr.matrix is not None else None, pr.layer)


def _prims_box(prims: list):
    boxes = []
    for pr in prims:
        if pr.image is not None:
            pts = [pr.matrix.apply(q) for q in ((0, 0), (1, 0), (0, 1), (1, 1))]
            boxes.append((min(q[0] for q in pts), min(q[1] for q in pts), max(q[0] for q in pts), max(q[1] for q in pts)))
        elif pr.path.contours:
            boxes.append(pr.path.bbox())
    return geom.bbox_union([b for b in boxes if b])


def watermark_prims(info: 'ProofInfo', box: tuple) -> list:
    """Le filigrane dans `box` (x0, y0, x1, y1 en mm) : le motif (`watermark_motif`) incliné, d'une couleur claire —
    répété en quinconce, la trame centrée (rien ne dépasse de la boîte ; trop petite pour un seul motif : rien), ou un
    seul au milieu (réduit s'il ne tient pas)."""
    motif = watermark_motif(info)
    if not motif:
        return []
    turned = [_moved(pr, Affine.rotation(_wm(info, 'watermark_angle', *WATERMARK_ANGLE))) for pr in motif]
    bb = _prims_box(turned)
    if not bb:
        return []
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    x0, y0, x1, y1 = box
    if x1 <= x0 or y1 <= y0 or w <= 0 or h <= 0:
        return []
    if getattr(info, 'watermark_layout', 'trame') == 'centre':
        k = min(1.0, (x1 - x0) / w, (y1 - y0) / h)
        m = Affine.translation((x0 + x1) / 2, (y0 + y1) / 2) @ Affine.scaling(k) @ \
            Affine.translation(-(bb[0] + bb[2]) / 2, -(bb[1] + bb[3]) / 2)
        return [_moved(pr, m) for pr in turned]
    if w > x1 - x0 or h > y1 - y0:
        return []
    gap = _wm(info, 'watermark_gap', *WATERMARK_GAP)
    dx, dy = w + gap, 0.75 * h + 0.4 * gap                  # en quinconce : les rangées s'emboîtent
    nx = max(1, int((x1 - x0 - w) // dx) + 1)
    ny = max(1, int((y1 - y0 - h) // dy) + 1)
    left = x0 + (x1 - x0 - (nx - 1) * dx - w) / 2          # la trame, centrée dans la boîte
    low = y0 + (y1 - y0 - (ny - 1) * dy - h) / 2
    out = []
    for j in range(ny):
        shift = dx / 2 if (j % 2 and nx > 1) else 0.0
        for i in range(nx - (1 if shift else 0)):
            m = Affine.translation(left + i * dx + shift - bb[0], low + j * dy - bb[1])
            out += [_moved(pr, m) for pr in turned]
    return out


def wrap_text(s: str, size: float, width: float) -> list:
    """Le texte coupé en lignes d'au plus `width` mm au corps `size` : entre deux mots, dans un mot s'il est plus
    long que la ligne. Les retours à la ligne du texte sont gardés."""
    def wide(t: str) -> float:
        b = text.layout_bbox(t, FONT, size) if t.strip() else None
        return (b[2] - b[0]) if b else 0.0
    out = []
    for para in str(s or '').splitlines():
        cur = ''
        for word in para.split():
            trial = f'{cur} {word}' if cur else word
            if wide(trial) <= width:
                cur = trial
                continue
            if cur:
                out.append(cur)
            cur = word
            while wide(cur) > width and len(cur) > 1:    # un mot plus long que la ligne
                k = len(cur) - 1
                while k > 1 and wide(cur[:k]) > width:
                    k -= 1
                out.append(cur[:k])
                cur = cur[k:]
        out.append(cur)
    return out


#: remarques du cartouche : (corps, interligne) essayés du plus grand au plus petit
NOTE_SIZES = ((2.6, 4.2), (2.2, 3.6), (1.9, 3.1), (1.6, 2.6))


def notes_lines(notes: str, width: float, height: float) -> tuple:
    """Les remarques mises à la ligne dans une case de `width` × `height` mm : (lignes, corps, interligne). Le plus
    grand corps où tout tient ; au plus petit, ce qui dépasse est coupé et la dernière ligne finit par « … »."""
    lines, size, pitch = [], NOTE_SIZES[0][0], NOTE_SIZES[0][1]
    for size, pitch in NOTE_SIZES:
        lines = wrap_text(notes, size, width)
        room = max(1, int(max(0.0, height) // pitch) + 1)
        if len(lines) <= room:
            return lines, size, pitch
    lines = lines[:room]
    lines[-1] = (lines[-1][:-1] if len(lines[-1]) > 1 else lines[-1]) + '…'
    return lines, size, pitch


def number_format(info: 'ProofInfo'):
    """Écriture des cotes : `decimals` chiffres après la virgule, sans les zéros de la fin sauf `keep_zeros`."""
    try:
        d = max(0, min(6, int(getattr(info, 'decimals', 2))))
    except (TypeError, ValueError):
        d = 2
    keep = bool(getattr(info, 'keep_zeros', False))

    def fmt(v: float) -> str:
        s = f'{v:.{d}f}'
        if d and not keep:
            s = s.rstrip('0').rstrip('.')
        if s in ('-0', ''):
            s = '0'
        return s.replace('.', decimal_sep())
    return fmt


def scale_label(k: float) -> str:
    """Échelle écrite : « 1:2 », « 5:1 », « 1:1,37 »…"""
    fmt = lambda v: f'{v:.2f}'.rstrip('0').rstrip('.').replace('.', decimal_sep())
    if abs(k - 1) < 1e-9:
        return '1:1'
    return f'{fmt(k)}:1' if k > 1 else f'1:{fmt(1 / k)}'


def choose_scale(info: 'ProofInfo', FW: float, FH: float, aw: float, ah: float) -> float:
    """Facteur page/réel selon le mode d'échelle."""
    fits = lambda k: FW * k <= aw + 1e-9 and FH * k <= ah + 1e-9
    if info.scale_mode == 'imposee' and info.scale > 0:
        return float(info.scale)
    if info.scale_mode == 'ajuster':
        return min(aw / max(FW, 1e-9), ah / max(FH, 1e-9))
    if info.scale_mode == 'normalisee':
        return next((k for k in NORMAL_FACTORS if fits(k)), NORMAL_FACTORS[-1])
    return next((1 / s for s in SCALES if fits(1 / s)), 1 / SCALES[-1])


@dataclass
class Prim:
    path: Path
    color: tuple = (0, 0, 0)
    width: float = 0.25          # mm ; 0 = remplissage seul
    fill: bool = False
    fill_color: tuple | None = None   # couleur du remplissage (sinon `color`) : teinte claire du coloriage
    image: object = None         # objet Image du dessin…
    matrix: object = None        # … et carré unité (v vers le bas) → page (mm)
    layer: str = 'page'          # 'dessin' : ce qui montre le dessin (vues, cotes, filigrane) ; 'page' : le reste


def _rgb(hexcol: str) -> tuple:
    c = hexcol.lstrip('#')
    return tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)) if len(c) == 6 else (0, 0, 0)


def _leaves(items):
    for it in items:
        if not it.visible:
            continue
        if isinstance(it, Group):
            yield from _leaves(it.children)
        else:
            yield it


#: au-delà, plus d'imbrication calculée entre contours de couleurs différentes : un chemin pair-impair par couleur
MAX_REGION_CONTOURS = 4000


def even_odd_regions(contours: list) -> list:
    """Coloriage en pair-impair de [(contour fermé, couleur)] : [(chemin, couleur)] à remplir, du dehors vers le dedans.
    Un contour dans un autre est vide, le suivant plein… ; chaque plein prend la couleur de son contour, et ses trous
    sont les contours juste dedans, de quelque couleur qu'ils soient. Un contour tracé deux fois reste plein : c'est un
    accident de tracé, et la pièce ne doit pas disparaître de l'épreuve."""
    import numpy as np
    if len(contours) > MAX_REGION_CONTOURS:
        by_col: dict = {}
        for c, col in contours:
            by_col.setdefault(col, []).append(c)
        return [(Path(cs), col) for col, cs in by_col.items()]
    polys = []
    for c, col in contours:
        pts = np.array(c.flatten(), float)
        if len(pts) < 3:
            continue
        x, y = pts[:, 0], pts[:, 1]
        area = abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))) / 2
        polys.append((area, len(polys), c, col, pts, (x.min(), y.min(), x.max(), y.max())))
    polys.sort(key=lambda e: (-e[0], e[1]))

    def inside(p, pts):
        x0, y0 = pts[:, 0], pts[:, 1]
        x1, y1 = np.roll(x0, -1), np.roll(y0, -1)
        with np.errstate(divide='ignore', invalid='ignore'):
            cross = ((y0 > p[1]) != (y1 > p[1])) & (p[0] < (x1 - x0) * (p[1] - y0) / (y1 - y0) + x0)
        return bool(np.count_nonzero(cross) % 2)
    depth, kids = [0] * len(polys), [[] for _ in polys]
    for i, (_a, _k, _c, _col, pts, box) in enumerate(polys):
        samples = [pts[0], pts[len(pts) // 3], pts[2 * len(pts) // 3]]
        for j in range(i - 1, -1, -1):                   # du plus petit des plus grands : le premier qui contient
            b = polys[j][5]
            if box[0] < b[0] - 1e-9 or box[1] < b[1] - 1e-9 or box[2] > b[2] + 1e-9 or box[3] > b[3] + 1e-9:
                continue
            if sum(inside(p, polys[j][4]) for p in samples) >= 2:
                depth[i] = depth[j] + 1
                kids[j].append(i)
                break
    order = sorted(range(len(polys)), key=lambda k: depth[k])
    return [(Path([polys[k][2]] + [polys[h][2] for h in kids[k]]), polys[k][3]) for k in order if depth[k] % 2 == 0]


def _regions_prims(contours: list, width: float) -> list:
    """Les pleins en pair-impair, puis le trait de chaque contour dans sa couleur (les détails fins restent vus)."""
    out = [Prim(path, col, 0, True) for path, col in even_odd_regions(contours)]
    if width > 0:
        by_col: dict = {}
        for c, col in contours:
            by_col.setdefault(col, []).append(c)
        out += [Prim(Path(cs), col, width) for col, cs in by_col.items()]
    return out


def _label(s: str, h: float, x: float, y: float, align='left', color=(0, 0, 0)) -> Prim:
    p = text.layout(s, FONT, h, align=align).transformed(Affine.translation(x, y))
    return Prim(p, color, 0, True)


def _shown(doc, items):
    """Le BAT ne montre pas les plaques de reprise posées (`fixture.shown`, question 43 du 17/11)."""
    from ..cam.fixture import shown
    return shown(doc, items)


def uses_selection(info: ProofInfo, items) -> bool:
    """La page montre-t-elle la sélection (plutôt que tout le dessin) ?"""
    return bool(items) and info.content != 'tout'


def page_scale(doc: Document, info: ProofInfo, items=None) -> float:
    """Facteur page/réel que `build` emploiera."""
    return _geometry(doc, info, items)['k']


def bruts_on_page(doc: Document, info: ProofInfo, items=None) -> list:
    """(ensemble, brut) montrés sur la page."""
    doc, items = _shown(doc, items)
    if not getattr(info, 'show_bruts', True):
        return []
    if uses_selection(info, items):
        return list(BR.walk(items))
    return [e for L in doc.layers if L.visible for e in BR.walk(L.items)]


def _geometry(doc: Document, info: ProofInfo, items=None) -> dict:
    doc, items = _shown(doc, items)
    leaves = None
    bruts = bruts_on_page(doc, info, items)
    if uses_selection(info, items):
        leaves = list(_leaves(items))
        bb_draw = geom.bbox_union([it.bbox() for it in leaves] + [BR.bbox(b) for _it, b in bruts])
        plate = None
        ref = bb_draw
        if info.fit_selection:
            info = dataclasses.replace(info, scale_mode='ajuster')
    else:
        bb_draw = geom.bbox_union([doc.bbox()] + [BR.bbox(b) for _it, b in bruts])
        plate = doc.plate if (doc.plate and doc.plate.visible) else None
        ref = (plate.x, plate.y, plate.x + plate.width, plate.y + plate.height) if plate else bb_draw
    if ref is None:
        ref = (0, 0, 100, 50)
    W0, H0 = ref[2] - ref[0], ref[3] - ref[1]
    # cadrage : support ET dessin (des objets peuvent dépasser du support)
    frame = geom.bbox_union([ref, bb_draw]) or ref
    FW, FH = frame[2] - frame[0], frame[3] - frame[1]
    pw, ph = PAGES.get(info.page, PAGES['A4'])
    landscape = (FW >= FH) if info.orientation == 'auto' else info.orientation == 'paysage'
    PW, PH = (max(pw, ph), min(pw, ph)) if landscape else (min(pw, ph), max(pw, ph))
    margin = max(0.0, float(info.margin))
    title_h = 42.0 if info.title_block else 0.0
    back = back_spec(info)
    room = info.dims or any(b.get('cotes') != 'aucune' for _it, b in bruts) or bool(back)    # (le dos : ses cotes)
    pad = 12 if room else 4                          # place des cotes
    area = (margin + pad, margin + title_h + (14 if room else 4), PW - margin - pad, PH - margin - 14)
    back_area = None
    if back:                                         # le dos de la gravure : sa part de la page (demande du 27/11)
        area, back_area = split_back(area, FW, FH, back, pad)
    aw, ah = area[2] - area[0], area[3] - area[1]
    views = plan_views(info, FW, FH, area, pad)
    return dict(bb_draw=bb_draw, plate=plate, ref=ref, W0=W0, H0=H0, frame=frame, FW=FW, FH=FH, PW=PW, PH=PH,
                margin=margin, title_h=title_h, area=area, aw=aw, ah=ah, k=views[0]['k'], views=views,
                leaves=leaves, bruts=bruts, back=back, back_area=back_area)


def plan_views(info: 'ProofInfo', FW: float, FH: float, area, pad: float) -> list[dict]:
    """Vues de la page : {'k', 'area', 'label'}. Mode « vues » : la pièce à
    1:1 cotée ; si elle est petite (< `enlarge_below`, ou `enlarge`), une
    vue agrandie à côté ; si elle ne tient pas, une réduction normalisée."""
    aw, ah = area[2] - area[0], area[3] - area[1]
    if info.scale_mode != 'vues':
        k = choose_scale(info, FW, FH, aw, ah)
        return [{'k': k, 'area': area, 'label': ''}]
    fits = lambda k, w, h: FW * k <= w + 1e-9 and FH * k <= h + 1e-9          # noqa: E731
    if not fits(1.0, aw, ah):
        k = next((1 / s for s in SCALES if fits(1 / s, aw, ah)), 1 / SCALES[-1])
        return [{'k': k, 'area': area, 'label': tr('Réduction')}]
    one = {'k': 1.0, 'area': area, 'label': tr('Taille réelle')}
    if not (max(FW, FH) < info.enlarge_below or info.enlarge):
        return [one]
    gap = 2 * pad + 6
    if aw >= ah:                                     # côte à côte : 1:1 à gauche, détail à droite
        w1 = min(max(FW + gap, aw * 0.3), aw * 0.5)
        a1 = (area[0], area[1], area[0] + w1, area[3])
        a2 = (area[0] + w1 + gap, area[1], area[2], area[3])
    else:                                            # l'un sur l'autre : 1:1 en bas, détail en haut
        h1 = min(max(FH + gap, ah * 0.3), ah * 0.5)
        a1 = (area[0], area[1], area[2], area[1] + h1)
        a2 = (area[0], area[1] + h1 + gap, area[2], area[3])
    if not fits(1.0, a1[2] - a1[0], a1[3] - a1[1]):
        return [one]                                 # la vue 1:1 n'y tiendrait plus
    w2, h2 = a2[2] - a2[0], a2[3] - a2[1]
    k2 = next((k for k in ENLARGEMENTS if fits(k, w2, h2)), 0)
    if k2 <= 1:
        return [one]
    return [dict(one, area=a1), {'k': float(k2), 'area': a2, 'label': tr('Agrandissement')}]


def build(doc: Document, info: ProofInfo, items=None) -> tuple[list[Prim], float, float]:
    """Primitives de la page (mm, origine en bas à gauche) et format ;
    `items` : la sélection (voir `uses_selection`). Avec une page des prix (`price_page_wanted`), les prix n'y sont
    pas."""
    if price_page_wanted(info):
        info = dataclasses.replace(info, prices=False)
    doc, items = _shown(doc, items)
    g = _geometry(doc, info, items)
    plate, ref, W0, H0, frame, FW, FH = g['plate'], g['ref'], g['W0'], g['H0'], g['frame'], g['FW'], g['FH']
    PW, PH, margin, title_h = g['PW'], g['PH'], g['margin'], g['title_h']
    prims: list[Prim] = []
    theme = accent(info)
    wide = theme if theme and getattr(info, 'theme_all', False) else None     # thème : cadre, en-tête et cotes aussi
    # cadre de page
    prims.append(Prim(Path([geom.rect(margin, margin, PW - 2 * margin, PH - 2 * margin)]), wide or (0, 0, 0), 0.5))
    tools_used = {}
    leaves = list(g['leaves'] if g['leaves'] is not None else _leaves(doc.iter_items(visible_only=True)))
    blue = wide or (0.1, 0.25, 0.55)
    drawn = len(prims)                                   # à partir d'ici : ce qui montre le dessin
    if getattr(info, 'watermark', False):                # en fond : sous la plaque, le dessin et les cotes
        prims.extend(watermark_prims(info, (margin + 1.5, margin + title_h + 1.5, PW - margin - 1.5,
                                            PH - margin - 13.5)))
    fmt = number_format(info)
    overall = info.dims and not unit_dims(doc, info, items)
    for view in g['views']:
        kv, (ax0, ay0, ax1, ay1) = view['k'], view['area']
        aw, ah = ax1 - ax0, ay1 - ay0
        ox = ax0 + (aw - FW * kv) / 2 - frame[0] * kv
        oy = ay0 + (ah - FH * kv) / 2 - frame[1] * kv
        m = Affine(kv, 0, 0, kv, ox, oy)
        # plaque
        if plate:
            prims.append(Prim(Path([geom.rect(plate.x, plate.y, plate.width, plate.height,
                                              plate.corner_radius)]).transformed(m), (0.45, 0.45, 0.45), 0.35))
        # bruts des ensembles : sous le dessin
        for _it, b in g['bruts']:
            prims.append(Prim(BR.path(b).transformed(m), wide or BRUT_COLOR, 0.3))
        # dessin
        black = info.fill and getattr(info, 'fill_mode', 'contour') == 'noir'
        by_outline = info.fill and getattr(info, 'fill_mode', 'contour') == 'contour'
        closed_all = []                                  # logo noir : tous les contours fermés de la vue
        outlined = []                                    # couleur des contours : (contour fermé, couleur)
        for it in leaves:
            if isinstance(it, Image):
                prims.append(Prim(Path([]), image=it, matrix=m @ it.matrix))
                continue
            p = getattr(it, 'path', None) or getattr(it, 'outline', None)
            if not p:
                continue
            col = doc.item_color(it)
            tools_used[it.tool] = doc.tool_color(it.tool)
            filled = bool(getattr(it, 'filled', False))
            if by_outline:
                pt = p.transformed(m)
                rgb = _rgb(col)
                outlined += [(c, rgb) for c in pt.contours if c.closed]
                opened = [c for c in pt.contours if not c.closed]
                if opened:
                    prims.append(Prim(Path(opened), rgb, 0.2))
                continue
            if black:
                pt = p.transformed(m)
                closed_all += [c for c in pt.contours if c.closed]
                opened = [c for c in pt.contours if not c.closed]
                if opened:
                    prims.append(Prim(Path(opened), (0, 0, 0), 0.2))
                continue
            if not filled and info.fill and any(c.closed for c in p.contours):
                prims.append(Prim(p.transformed(m), _rgb(col), 0.2, True, tint(_rgb(col))))   # coloriage
            else:
                prims.append(Prim(p.transformed(m), _rgb(col), 0.2, filled))
        if outlined:
            prims.extend(_regions_prims(outlined, 0.1))
        if closed_all:                                   # un seul chemin, rempli en pair-impair : pleins et vides
            prims.append(Prim(Path(closed_all), (0, 0, 0), 0.1, True))      # alternent d'un contour à l'autre
        # cotes d'encombrement : traits et flèches à l'échelle, valeur réelle
        x0, y0 = m.apply((ref[0], ref[1]))
        x1, y1 = m.apply((ref[2], ref[3]))
        for (a, b, val, horiz) in ((((x0, y0), (x1, y0), W0, True), ((x0, y1), (x0, y0), H0, False))
                                   if overall else ()):
            parts = geom.dimension(a, b, -7, text_height=3.0)
            if not parts:
                continue
            lines, heads, _label_page = parts
            prims.append(Prim(lines, blue, 0.2))
            prims.append(Prim(heads, blue, 0, True))
            lbl = text.layout(fmt(val), FONT, 3.0, align='center')
            if horiz:
                prims.append(Prim(lbl.transformed(Affine.translation((x0 + x1) / 2, y0 - 7 - 4.6)), blue, 0, True))
            else:
                prims.append(Prim(lbl.transformed(Affine.translation(x0 - 8.5, (y0 + y1) / 2) @ Affine.rotation(90)),
                                  blue, 0, True))
        if view is g['views'][0]:
            prims.extend(_engraving_dims(doc, info, items, m, fmt))
        # libellé de la vue (plusieurs vues, ou mode « vues »)
        if view['label'] and (len(g['views']) > 1 or info.scale_mode == 'vues'):
            prims.append(_label(f"{view['label']} {scale_label(kv)}", 2.6, (ax0 + ax1) / 2, ay1 + 3.0, 'center',
                                color=(0.25, 0.25, 0.25)))
    if g['back']:                                    # le dos de la gravure (demande du 27/11) : à côté ou dessous
        prims.extend(back_prims(g['back'], g['back_area'], g['views'][0]['k'], fmt))
    for pr in prims[drawn:]:
        pr.layer = 'dessin'
    scale_text = ' + '.join(scale_label(v['k']) for v in g['views'])
    # légende des outils
    lx, ly = PW - margin - 4, PH - margin - 8
    if logo_vector(getattr(info, 'logo2', '')) is not None or logo_image(getattr(info, 'logo2', '')) is not None:
        ly -= LOGO_H + 1                                 # sous le second logo
    for t, col in (sorted(tools_used.items()) if info.legend else ()):
        name = next((tl.name for tl in doc.tools if tl.index == t), tr('Outil {0}').format(t))
        prims.append(Prim(Path([geom.rect(lx - 6, ly - 0.5, 5, 3)]), _rgb(col), 0, True))
        prims.append(_label(name, 2.5, lx - 8, ly, 'right'))
        ly -= 5
    if not info.title_block:
        _header(prims, info, PW, PH, margin, scale_text)
        return _mono(prims, info), PW, PH
    # cartouche (couleur au choix : traits, intitulés et fond clair ; jamais en noir et blanc)
    tx, ty, tw, th = margin, margin, PW - 2 * margin, title_h
    tc = theme
    ink, lab_col = (tc, tc) if tc else ((0, 0, 0), (0.4, 0.4, 0.4))
    if tc:
        prims.append(Prim(Path([geom.rect(tx, ty, tw, th)]), tc, 0, True, tint(tc, 0.12)))
    prims.append(Prim(Path([geom.rect(tx, ty, tw, th)]), ink, 0.5))
    cols = [tx, tx + tw * 0.34, tx + tw * 0.62, tx + tw * 0.80, tx + tw]
    for c in cols[1:-1]:
        prims.append(Prim(Path([geom.polyline([(c, ty), (c, ty + th)])]), ink, 0.25))
    rows = 4
    rh = th / rows
    for r in range(1, rows):
        prims.append(Prim(Path([geom.polyline([(tx, ty + r * rh), (cols[2], ty + r * rh)])]), ink, 0.15))
    fr = fmt
    one_brut = g['bruts'][0][1] if len(g['bruts']) == 1 and not plate else None   # un seul brut : sa taille, pas celle de la page
    w_brut, h_brut = BR.size(one_brut) if one_brut else (W0, H0)
    dims = f'{fr(w_brut)} × {fr(h_brut)} mm'
    if plate and plate.thickness:
        dims += tr(' × ép. {0}').format(fr(plate.thickness))
    elif one_brut and one_brut.get('thickness'):
        dims += tr(' × ép. {0}').format(fr(float(one_brut['thickness'])))
    cells = [(tr('Client'), info.client), (tr('Référence'), info.reference),
             (tr('Désignation'), info.designation), (tr('Matière'), info.material or (plate.material if plate else ''))]
    cells2 = [(tr('Dimensions'), dims), (tr('Échelle'), scale_text),
              (tr('Date'), info.date), (tr('BAT n°'), info.bat_number)]
    for i, (lab, val) in enumerate(cells):
        y = ty + th - (i + 1) * rh
        prims.append(_label(lab, 2.0, cols[0] + 2, y + rh - 3.2, color=lab_col))
        prims.append(_label(val, 3.2, cols[0] + 2, y + 1.8))
    for i, (lab, val) in enumerate(cells2):
        y = ty + th - (i + 1) * rh
        prims.append(_label(lab, 2.0, cols[1] + 2, y + rh - 3.2, color=lab_col))
        prims.append(_label(val, 3.2, cols[1] + 2, y + 1.8))
    prims.append(_label(tr('Remarques'), 2.0, cols[2] + 2, ty + th - 3.2, color=lab_col))
    lines, size, pitch = notes_lines(info.notes, cols[3] - cols[2] - 4, th - 10)     # à la ligne dans leur case
    for j, line in enumerate(lines):
        if line:
            prims.append(_label(line, size, cols[2] + 2, ty + th - 8 - j * pitch))
    prims.append(_label(tr('BON POUR ACCORD'), 2.2, cols[3] + 2, ty + th - 4.5, color=ink))
    prims.append(_label(tr('Date et signature :'), 2.0, cols[3] + 2, ty + th - 9, color=lab_col))
    _header(prims, info, PW, PH, margin, scale_text)
    if info.author:
        prims.append(_label(info.author, 2.0, cols[3] + 2, ty + 2, color=(0.4, 0.4, 0.4)))
    return _mono(prims, info), PW, PH


#: au-delà, coter et chiffrer chaque gravure n'a plus de sens — un dessin fait de centaines d'objets n'est pas une
#: planche de gravures : il est coté comme un tout
MAX_ENGRAVINGS = 40


def each_engraving(n: int) -> bool:
    """Des gravures à coter (et à chiffrer) une à une : plusieurs, mais pas plus de `MAX_ENGRAVINGS`."""
    return 1 < n <= MAX_ENGRAVINGS


def engravings(doc: Document, info: ProofInfo, items=None) -> list:
    """Gravures du BAT : les objets (ou groupes) de premier niveau — ceux de
    la sélection, sinon ceux des calques affichés."""
    doc, items = _shown(doc, items)
    if uses_selection(info, items):
        return [it for it in items if it.visible]
    return [it for L in doc.layers if L.visible for it in L.items if it.visible]


def unit_dims(doc: Document, info: ProofInfo, items=None) -> bool:
    """Plusieurs gravures cotées une à une (`dims_each`), ou des bruts cotés à part : leurs cotes
    suffisent, celles d'encombrement de l'ensemble ne sont pas écrites."""
    if any(b.get('cotes') != 'aucune' for _it, b in bruts_on_page(doc, info, items)):
        return True
    return bool(info.dims_each) and each_engraving(sum(1 for it in engravings(doc, info, items) if it.bbox()))


def engraving_price(objs: list) -> str | None:
    """Prix d'une gravure donné par un plugin (devis réglé), sinon None."""
    from ..plugins import REGISTRY
    for fn in REGISTRY.bat_prices:
        try:
            v = fn(objs)
        except Exception:                             # devis d'un plugin en défaut : BAT sans prix
            v = None
        if v:
            return str(v)
    return None


def price_page_wanted(info: ProofInfo) -> bool:
    """Les prix vont-ils sur leur page (question 29) ? Un plugin en donne une, « Prix du devis par gravure » et « Prix
    sur une page à part » sont cochés. Sans calculer le devis : l'aperçu reste rapide. (Un plugin sans devis réglé ne
    donne ni page ni prix par gravure : la page technique est la même.)"""
    from ..plugins import REGISTRY
    return bool(getattr(REGISTRY, 'bat_pages', [])) and bool(getattr(info, 'price_page', True)) \
        and bool(getattr(info, 'prices', True))


def price_pages(doc: Document, info: ProofInfo, items=None) -> list:
    """Les pages des prix données par les plugins (question 29) : [(titre, [lignes])] ; [] sans plugin qui en donne,
    ou quand « Prix du devis par gravure » ou « Prix sur une page à part » est décoché."""
    from ..plugins import REGISTRY
    if not price_page_wanted(info):
        return []
    eng = [it for it in engravings(doc, info, items) if it.bbox()]
    out = []
    for fn in REGISTRY.bat_pages:
        try:
            v = fn(doc, eng, info)
        except Exception:                             # devis d'un plugin en défaut : pas de page des prix
            v = None
        if v and len(v) == 2 and v[1]:
            out.append((str(v[0]), [str(x) for x in v[1]]))
    return out


#: page des prix : corps du titre, du texte, interligne, retrait d'une espace en tête de ligne (mm)
PRICE_TITLE, PRICE_SIZE, PRICE_LEAD, PRICE_INDENT = 5.0, 3.0, 4.6, 1.2


#: au plus tant de pages des prix pour une page donnée par un plugin (au-delà : « … » au bas de la dernière)
PRICE_PAGES_MAX = 20


def price_page_prims(info: ProofInfo, title: str, lines: list, PW: float, PH: float) -> list:
    """Les pages des prix d'une page donnée par un plugin : [[primitives d'une page]]. Chacune : cadre et en-tête du
    BAT (logos, entreprise), le titre (« (suite) » après la première), client, référence et date, puis les lignes,
    coupées à la largeur de la page ; une liste trop longue continue sur la page suivante (au plus
    `PRICE_PAGES_MAX`)."""
    margin = float(info.margin)
    theme = accent(info)
    wide = theme if theme and getattr(info, 'theme_all', False) else None
    x = margin + 4
    width = PW - 2 * margin - 8
    rows = []
    for line in lines:
        dx = (len(line) - len(line.lstrip(' '))) * PRICE_INDENT
        rows.extend((dx, part) for part in (wrap_text(line.strip(), PRICE_SIZE, width - dx) or ['']))
    ident = '   '.join(v for v in (info.client, info.reference, info.date) if str(v or '').strip())
    pages: list = []
    while True:
        prims: list = [Prim(Path([geom.rect(margin, margin, PW - 2 * margin, PH - 2 * margin)]), wide or (0, 0, 0),
                            0.5)]
        _header(prims, info, PW, PH, margin, '')
        y = PH - margin - LOGO_H - 9
        prims.append(_label(title + (tr(' (suite)') if pages else ''), PRICE_TITLE, x, y, color=theme or (0, 0, 0)))
        y -= PRICE_TITLE + 2
        if ident:
            prims.append(_label(ident, PRICE_SIZE, x, y, color=(0.35, 0.35, 0.35)))
            y -= PRICE_LEAD
        y -= 2
        last = len(pages) + 1 >= PRICE_PAGES_MAX
        while rows and y >= margin + PRICE_LEAD:
            if last and len(rows) > 1 and y - PRICE_LEAD < margin + PRICE_LEAD:
                prims.append(_label('…', PRICE_SIZE, x, y))
                rows = []
                break
            dx, part = rows.pop(0)
            if part:
                prims.append(_label(part, PRICE_SIZE, x + dx, y))
            y -= PRICE_LEAD
        pages.append(_mono(prims, info))
        if not rows:
            return pages


def readable_angle(ux: float, uy: float) -> float:
    """Angle d'écriture d'une cote de direction (ux, uy) : dans ]-90 ; 90], jamais la tête en bas ; une cote verticale se
    lit de bas en haut, comme les autres cotes de la page."""
    import math
    ang = math.degrees(math.atan2(uy, ux))
    if ang > 90.0001:
        ang -= 180
    elif ang < -89.9999:
        ang += 180
    return ang


def _aligned_dim(a, b, val: str, offset: float, h: float, color: tuple) -> list:
    """Cote entre deux points de la page, dans n'importe quel sens, sa valeur lisible du bon côté."""
    import math
    parts = geom.dimension(a, b, offset, text_height=h)
    if not parts:
        return []
    lines, heads, _p = parts
    L = math.dist(a, b)
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    nx, ny = -uy, ux
    ang = readable_angle(ux, uy)
    rad = math.radians(ang)
    upx, upy = -math.sin(rad), math.cos(rad)
    sign = 1 if offset >= 0 else -1
    ox, oy = nx * sign, ny * sign                    # vers le dehors
    gap = 1.2 if upx * ox + upy * oy > 0 else 1.2 + h
    mx = (a[0] + b[0]) / 2 + nx * offset + ox * gap
    my = (a[1] + b[1]) / 2 + ny * offset + oy * gap
    lbl = text.layout(val, FONT, h, align='center')
    return [Prim(lines, color, 0.15), Prim(heads, color, 0, True),
            Prim(lbl.transformed(Affine.translation(mx, my) @ Affine.rotation(ang)), color, 0, True)]


def _brut_dims(b: dict, m, fmt, color: tuple) -> list:
    """Le brut coté à part, le long de ses bords, au-dehors."""
    if b.get('cotes') not in ('les_deux', 'brut'):
        return []
    c = [m.apply((float(p[0]), float(p[1]))) for p in b['corners']]
    w, h = BR.size(b)
    return _aligned_dim(c[0], c[1], fmt(w), -5.0, 2.4, color) + _aligned_dim(c[3], c[0], fmt(h), -5.0, 2.4, color)


def _overlap(a: tuple, b: tuple, margin: float = 0.3) -> bool:
    return a[0] < b[2] + margin and b[0] < a[2] + margin and a[1] < b[3] + margin and b[1] < a[3] + margin


def _page_box(box: tuple, m) -> tuple:
    xa, ya = m.apply((box[0], box[1]))
    xb, yb = m.apply((box[2], box[3]))
    return min(xa, xb), min(ya, yb), max(xa, xb), max(ya, yb)


def _brut_label(b: dict, m, fmt, color: tuple, taken: list) -> Prim | None:
    """Nom et épaisseur du brut : au-dessus de lui, sinon à la première place libre autour. Rien de libre : au-dessus."""
    if b.get('cotes') not in ('les_deux', 'brut'):
        return None
    name = tr('Brut') + (f' {b["name"]}' if b.get('name') else '')
    if b.get('thickness'):
        name += tr(' × ép. {0}').format(fmt(float(b['thickness'])))
    c = [m.apply((float(p[0]), float(p[1]))) for p in b['corners']]
    x0, y0, x1, y1 = BR.bbox({'corners': [list(p) for p in c]})
    first = None
    for x, y, align in (((x0 + x1) / 2, y1 + 1.2, 'center'),     # au-dessus
                        ((x0 + x1) / 2, y0 - 12.0, 'center'),    # sous la cote du bas
                        (x1 + 1.2, y1 - 2.4, 'left'),            # à droite
                        (x0 - 9.6, y1 - 2.4, 'right')):          # à gauche de la cote de côté
        p = _label(name, 2.4, x, y, align, color=color)
        first = first or p
        box = p.path.bbox()
        if box and not any(_overlap(box, t) for t in taken):
            return p
    return first


def _engraving_dims(doc: Document, info: ProofInfo, items, m, fmt) -> list:
    """Cote (largeur, hauteur) et prix de chaque gravure, à côté d'elle ; les bruts, cotés à part."""
    out = []
    eng = [it for it in engravings(doc, info, items) if it.bbox()]
    theme = accent(info) if getattr(info, 'theme_all', False) else None
    bruts = bruts_on_page(doc, info, items)
    color = theme or BRUT_COLOR
    for _it, b in bruts:
        out.extend(_brut_dims(b, m, fmt, color))
    taken = [box for box in (p.path.bbox() for p in out) if box]     # les noms viennent après toutes les cotes des bruts
    taken += [_page_box(BR.bbox(b), m) for _it, b in bruts]
    taken += [_page_box(it.bbox(), m) for it in eng]
    for _it, b in bruts:
        name = _brut_label(b, m, fmt, color, taken)
        if name:
            out.append(name)
            taken.append(name.path.bbox())
    with_brut = {id(it): b for it, b in bruts}
    if not (info.dims_each or info.prices or bruts) or (len(eng) < 2 and not info.prices and not bruts):
        return out
    green = (0.05, 0.4, 0.2)
    blue = theme or (0.1, 0.25, 0.55)
    each = each_engraving(len(eng))
    for it in eng:
        own = with_brut.get(id(it))
        if own is None and not each and len(eng) > 1:    # trop de gravures : ni cote ni prix une à une
            continue
        bb = it.bbox()
        x0, y0 = m.apply((bb[0], bb[1]))
        x1, y1 = m.apply((bb[2], bb[3]))
        if (own.get('cotes') in ('les_deux', 'ensemble')) if own is not None else (info.dims_each and each):
            for a, b, val, horiz in (((x0, y0), (x1, y0), bb[2] - bb[0], True),
                                     ((x0, y1), (x0, y0), bb[3] - bb[1], False)):
                parts = geom.dimension(a, b, -3.5, text_height=2.2)
                if not parts or (abs(b[0] - a[0]) if horiz else abs(b[1] - a[1])) < 1.0:
                    continue
                lines, heads, _p = parts
                out.append(Prim(lines, blue, 0.15))
                out.append(Prim(heads, blue, 0, True))
                lbl = text.layout(fmt(val), FONT, 2.2, align='center')
                if horiz:
                    out.append(Prim(lbl.transformed(Affine.translation((x0 + x1) / 2, y0 - 3.5 - 3.4)), blue, 0, True))
                else:
                    out.append(Prim(lbl.transformed(Affine.translation(x0 - 5.4, (y0 + y1) / 2) @ Affine.rotation(90)),
                                    blue, 0, True))
        price = engraving_price([it]) if info.prices else None
        if price:
            out.append(_label(price, 2.6, (x0 + x1) / 2, y1 + 1.5, 'center', color=green))
    return out


#: couleur du brut et de ses cotes (ou celle du thème)
BRUT_COLOR = (0.55, 0.3, 0.05)
#: dos de la gravure (demande du 27/11) : le brut couleur laiton — celle des pièces en laiton de `core.stepgen` —, son
#: bord un peu plus foncé ; taraudages et cotes en noir
BACK_COLOR = (0.80, 0.66, 0.30)
BACK_EDGE = (0.55, 0.42, 0.12)
BACK_INK = (0.0, 0.0, 0.0)
#: dispositions des taraudages : aucun, un au milieu, deux sur l'axe horizontal, deux sur l'axe vertical, quatre aux
#: coins ; leurs positions : entraxes, ou distances aux bords
BACK_HOLES = ('', '1', '2h', '2v', '4')
BACK_POS = ('entraxe', 'bords')
#: pas des filetages métriques ISO (pas gros) : le foret de taraudage fait le diamètre moins le pas
METRIC_PITCH = {1.6: 0.35, 2.0: 0.4, 2.5: 0.45, 3.0: 0.5, 3.5: 0.6, 4.0: 0.7, 5.0: 0.8, 6.0: 1.0, 8.0: 1.25,
                10.0: 1.5, 12.0: 1.75, 14.0: 2.0, 16.0: 2.0}


#: un dos sans taraudage (un client du carnet qui n'a pas de dos : celui du client d'avant ne reste pas)
BACK_NONE = {'on': False, 'trous': '', 'filetage': '', 'pos': 'entraxe', 'x': 0.0, 'y': 0.0, 'dx': 0.0, 'dy': 0.0}


def back_read(info) -> dict:
    """Les réglages du dos de `info.back` relus sans faute, même décochés ou sans brut : {'on', 'w', 'h', 'ep',
    'trous', 'filetage', 'pos', 'x', 'y', 'dx', 'dy'} (mm ; 'trous' dans `BACK_HOLES`, 'pos' dans `BACK_POS`) ; {}
    s'il n'y en a pas."""
    b = getattr(info, 'back', None)
    if not isinstance(b, dict):
        return {}

    def num(key, lo=0.0):
        try:
            v = float(str(b.get(key) or 0).replace(',', '.'))
        except (TypeError, ValueError):
            return 0.0
        return max(lo, min(10000.0, v)) if v == v else 0.0         # (NaN : rien)
    holes, pos = str(b.get('trous') or ''), str(b.get('pos') or '')
    return {'on': b.get('on') in (True, 'true', 1), 'w': num('w'), 'h': num('h'), 'ep': num('ep'), 'x': num('x'),
            'y': num('y'), 'dx': num('dx', -10000.0), 'dy': num('dy', -10000.0),
            'trous': holes if holes in BACK_HOLES else '', 'pos': pos if pos in BACK_POS else 'entraxe',
            'filetage': str(b.get('filetage') or '').strip()}


def back_spec(info) -> dict:
    """Le dos de la gravure à représenter (`back_read`) ; {} sans dos : case décochée, ou brut sans largeur ou sans
    hauteur (la fenêtre le dit : `back_warnings`)."""
    out = back_read(info)
    return out if out.get('on') and out['w'] > 0 and out['h'] > 0 else {}


def back_warnings(info, doc=None) -> list:
    """Ce que la fenêtre du BAT doit dire du dos coché : brut à renseigner, cote des trous manquante, distance au
    bord trop grande (aucun trou), filetage illisible (des croix), filetage plus grand que l'écart des trous,
    taraudages qui dépasseraient du brut (pas dessinés), brut autre que celui du dessin `doc`. [] : rien à dire."""
    b = back_read(info)
    if not b.get('on'):
        return []
    if b['w'] <= 0 or b['h'] <= 0:
        return [tr('Dos : renseigner le brut (largeur et hauteur) — rien n’est dessiné sans lui')]
    fmt = number_format(info)
    out = []
    t, pos, sizes = b['trous'], b['pos'], thread_sizes(b['filetage'])
    for key, axis, side, used in (('x', 'X', b['w'], ('2h', '4')), ('y', 'Y', b['h'], ('2v', '4'))):
        if t not in used:
            continue
        if b[key] <= 0:
            out.append(tr('Dos : cote {0} des trous à renseigner — aucun trou dessiné').format(axis))
            continue
        if pos == 'bords' and b[key] >= side / 2:
            out.append(tr('Dos : distance au bord {0} d’au moins la moitié du brut — aucun trou dessiné').format(axis))
            continue
        gap = b[key] if pos == 'entraxe' else side - 2 * b[key]
        if sizes and gap < sizes[0]:
            out.append(tr('Dos : le filetage {0} est plus grand que l’écart des trous en {1} ({2} mm)').format(
                b['filetage'], axis, fmt(gap)))
    if t and b['filetage'] and sizes is None:
        out.append(tr('Dos : filetage « {0} » illisible — les trous sont marqués d’une croix').format(b['filetage']))
    lost = back_drawn(b)[1]
    if lost:
        out.append(tr('Dos : {0} taraudage(s) dépasseraient du brut — pas dessinés (entraxes, décalage ?)').format(
            len(lost)))
    d = back_defaults(doc) if doc is not None else {}
    if d and (abs(d['w'] - b['w']) > 1e-6 or abs(d['h'] - b['h']) > 1e-6):
        out.append(tr('Dos : brut de {0} × {1} mm, autre que celui du dessin ({2} × {3} mm)').format(
            fmt(b['w']), fmt(b['h']), fmt(d['w']), fmt(d['h'])))
    return out


def back_defaults(doc) -> dict:
    """Le brut du dos proposé d'office : la plaque du dessin, sinon son brut s'il n'en a qu'un ({} : rien de connu)."""
    plate = getattr(doc, 'plate', None)
    if plate is not None and plate.width > 0 and plate.height > 0:
        return {'w': float(plate.width), 'h': float(plate.height), 'ep': float(plate.thickness or 0)}
    bruts = [b for L in doc.layers for _it, b in BR.walk(L.items)]
    if len(bruts) != 1:
        return {}
    w, h = BR.size(bruts[0])
    try:
        ep = float(bruts[0].get('thickness') or 0)
    except (TypeError, ValueError):
        ep = 0.0
    return {'w': w, 'h': h, 'ep': ep}


def thread_sizes(name: str):
    """(diamètre nominal, diamètre du foret) d'un taraudage « M4 », « M2,5 », « M8x1 » (pas fin) ou d'un diamètre
    seul (« 4 ») ; None si la désignation ne se lit pas."""
    import re
    m = re.fullmatch(r'[Mm]? *([0-9]+(?:[.,][0-9]+)?)(?: *[xX×] *([0-9]+(?:[.,][0-9]+)?))?', str(name or '').strip())
    if not m:
        return None
    d = float(m.group(1).replace(',', '.'))
    p = float(m.group(2).replace(',', '.')) if m.group(2) else METRIC_PITCH.get(d, 0.15 * d)
    return (d, d - p) if 0 < p < d else None


def back_holes(back: dict) -> list:
    """Centres des taraudages vus de face (mm, origine au coin bas-gauche du brut) : seulement ceux que le formulaire
    place — deux trous sans entraxe ni distance aux bords : aucun, rien d'inventé. Un trou seul : au milieu, décalé ;
    en distances aux bords, le motif est centré sur le brut (sans décalage)."""
    W, H, t = back['w'], back['h'], back['trous']
    cx, cy = W / 2 + back['dx'], H / 2 + back['dy']
    if t == '1':
        return [(cx, cy)]
    if back['pos'] == 'bords':
        cx, cy = W / 2, H / 2
        xs = (back['x'], W - back['x']) if 0 < back['x'] < W / 2 else ()
        ys = (back['y'], H - back['y']) if 0 < back['y'] < H / 2 else ()
    else:
        xs = (cx - back['x'] / 2, cx + back['x'] / 2) if back['x'] > 0 else ()
        ys = (cy - back['y'] / 2, cy + back['y'] / 2) if back['y'] > 0 else ()
    if t == '2h':
        return [(x, cy) for x in xs]
    if t == '2v':
        return [(cx, y) for y in ys]
    if t == '4':
        return [(x, y) for y in ys for x in xs]
    return []


def back_drawn(back: dict) -> tuple:
    """(taraudages dessinés, taraudages hors du brut) : un taraudage qui dépasserait du brut n'est pas dessiné —
    jamais dans les cotes ni le cartouche ; la fenêtre le dit (`back_warnings`)."""
    sizes = thread_sizes(back['filetage'])
    r = sizes[0] / 2 if sizes else 0.0
    inside, out = [], []
    for x, y in back_holes(back):
        ok = r - 1e-9 <= x <= back['w'] - r + 1e-9 and r - 1e-9 <= y <= back['h'] - r + 1e-9
        (inside if ok else out).append((x, y))
    return inside, out


def split_back(area: tuple, FW: float, FH: float, back: dict, pad: float) -> tuple:
    """(place des vues de face, place de la vue de dos) : côte à côte (le dos à droite) ou l'une sur l'autre (le dos
    dessous), selon ce qui les montre le plus grandes ; chacune en proportion de sa taille."""
    x0, y0, x1, y1 = area
    aw, ah = x1 - x0, y1 - y0
    BW, BH = back['w'], back['h']
    gap = 2 * pad + 6                                # les cotes de l'une, la légende de l'autre
    side = min((aw - gap) / max(FW + BW, 1e-9), ah / max(FH, BH, 1e-9))
    stack = min(aw / max(FW, BW, 1e-9), (ah - gap) / max(FH + BH, 1e-9))
    if side >= stack:
        wf = (aw - gap) * FW / max(FW + BW, 1e-9)
        return (x0, y0, x0 + wf, y1), (x0 + wf + gap, y0, x1, y1)
    hb = (ah - gap) * BH / max(FH + BH, 1e-9)
    return (x0, y0 + hb + gap, x1, y1), (x0, y0, x1, y0 + hb)


def back_prims(back: dict, area: tuple, k_face: float, fmt) -> list:
    """La vue « Dos » dans `area` (mm de la page), à l'échelle de la face si elle y tient (sinon la réduction
    normalisée qui tient) : le brut couleur laiton vu de dos — miroir de la face, la gauche passe à droite —, ses
    taraudages qui tiennent dans le brut, en noir (le foret en trait fort, le filetage en trois quarts de cercle fin,
    comme en dessin technique ; sans filetage lisible : une croix) et les cotes données (entraxes, ou distances aux
    bords), en noir ; sous le brut, la légende « Dos » et son échelle, avec les taraudages (« 2 × M4 ») et
    l'épaisseur s'ils sont donnés."""
    W, H = back['w'], back['h']
    ax0, ay0, ax1, ay1 = area
    aw, ah = ax1 - ax0, ay1 - ay0
    if aw <= 0 or ah <= 0:
        return []
    fits = lambda k: W * k <= aw + 1e-9 and H * k <= ah + 1e-9          # noqa: E731
    k = k_face if fits(k_face) else next((1 / s for s in SCALES if fits(1 / s)), min(aw / W, ah / H))
    bx, by = ax0 + (aw - W * k) / 2, ay0 + (ah - H * k) / 2
    out = [Prim(Path([geom.rect(bx, by, W * k, H * k)]), BACK_EDGE, 0.3, True, BACK_COLOR)]
    holes = [(bx + (W - x) * k, by + y * k) for x, y in back_drawn(back)[0]]   # vu de dos : miroir en X
    sizes = thread_sizes(back['filetage'])
    for x, y in holes:
        if sizes:
            out.append(Prim(Path([geom.circle((x, y), sizes[1] * k / 2)]), BACK_INK, 0.3))
            out.append(Prim(Path([geom.arc((x, y), sizes[0] * k / 2, 90, 270)]), BACK_INK, 0.15))
        else:
            out.append(Prim(Path([geom.polyline([(x - 1.5, y), (x + 1.5, y)]),
                                  geom.polyline([(x, y - 1.5), (x, y + 1.5)])]), BACK_INK, 0.15))
    t, pos = back['trous'], back['pos']
    under = 5.0                                      # la légende, sous le brut (et sous sa cote)
    if holes and t in ('2h', '4') and back['x'] > 0:  # la rangée du bas, cotée sous le brut
        low = min(y for _x, y in holes)
        row = sorted(p for p in holes if abs(p[1] - low) < 1e-6)
        a, b = ((bx, row[0][1]), row[0]) if pos == 'bords' else (row[0], row[-1])
        dim = _aligned_dim(a, b, fmt(back['x']), -(row[0][1] - by) - 5.0, 2.4, BACK_INK)
        out += dim
        under = 13.0 if dim else under
    if holes and t in ('2v', '4') and back['y'] > 0:  # la colonne de gauche, cotée à gauche du brut
        left = min(x for x, _y in holes)
        col = sorted((p for p in holes if abs(p[0] - left) < 1e-6), key=lambda p: -p[1])       # du haut en bas
        a, b = ((col[0][0], by + H * k), col[0]) if pos == 'bords' else (col[0], col[-1])
        out += _aligned_dim(a, b, fmt(back['y']), -(col[0][0] - bx) - 5.0, 2.4, BACK_INK)
    parts = [f"{tr('Dos')} {scale_label(k)}"]
    if holes and back['filetage']:
        parts.append(f"{len(holes)} × {back['filetage']}")
    if back['ep'] > 0:
        parts.append(tr('ép. {0}').format(fmt(back['ep'])))
    # sous le brut : jamais sur l'en-tête, le second logo ou la légende des outils (en haut à droite de la page)
    out.append(_label(' — '.join(parts), 2.6, bx + W * k / 2, by - under, 'center', color=(0.25, 0.25, 0.25)))
    return out


def tint(rgb: tuple, k: float = 0.35) -> tuple:
    """Teinte claire d'une couleur (fond du coloriage, le trait reste lisible)."""
    return tuple(1.0 - (1.0 - c) * k for c in rgb)


def _mono(prims: list[Prim], info: ProofInfo) -> list[Prim]:
    """Noir et blanc : toutes les couleurs en noir (gris gardés pour les
    libellés et la plaque, lisibles à l'impression)."""
    if not info.mono:
        return prims
    for pr in prims:
        r, g, b = pr.color
        if not (abs(r - g) < 1e-6 and abs(g - b) < 1e-6):
            pr.color = (0, 0, 0)
        if pr.fill_color is not None:
            pr.fill_color = (0.82, 0.82, 0.82)                # coloriage en gris clair
    return prims


def _f(v: float) -> str:
    s = f'{v:.4f}'.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


def image_streams(item) -> tuple[int, int, bytes, bytes | None] | None:
    """Pixels d'une image du dessin pour le PDF, pleine résolution et sans
    perte : (largeur, hauteur, RVB compressé, alpha compressé ou None)."""
    from PySide6.QtGui import QImage
    from .raster import _app, qimage_of
    _app()
    q = qimage_of(item)
    if q is None or q.isNull():
        return None
    q = q.convertToFormat(QImage.Format.Format_RGBA8888)
    w, h = q.width(), q.height()
    import numpy as np
    px = np.frombuffer(bytes(q.constBits())[:q.sizeInBytes()], np.uint8)
    px = px.reshape(h, q.bytesPerLine())[:, :4 * w].reshape(h, w, 4)
    alpha = px[..., 3]
    return (w, h, zlib.compress(px[..., :3].tobytes(), 9),
            zlib.compress(alpha.tobytes(), 9) if (alpha != 255).any() else None)


def pdf_bytes(content_ops: list[str], W: float, H: float, images: list, title: str = '', more=()) -> bytes:
    """PDF (W × H points) : la page de `content_ops`, puis une page par liste d'opérations de `more` (la page des
    prix), les images (XObject /ImN, communes à toutes les pages) et les infos."""
    objs: list[bytes] = [b'<< /Type /Catalog /Pages 2 0 R >>', b'']
    at = []
    for ops in [content_ops, *more]:
        at.append(len(objs))
        objs.append(b'')                                 # la page, écrite une fois les images numérotées
        content = zlib.compress('\n'.join(ops).encode('ascii'), 6)   # 9 : 2 × plus lent pour 2 % de moins
        objs.append(b'<< /Length ' + str(len(content)).encode() + b' /Filter /FlateDecode >>\nstream\n'
                    + content + b'\nendstream')
    kids = ' '.join(f'{i + 1} 0 R' for i in at)
    objs[1] = f'<< /Type /Pages /Kids [{kids}] /Count {len(at)} >>'.encode()
    xobj = []
    for k, (w, h, rgb, alpha) in enumerate(images):
        smask = ''
        if alpha is not None:
            objs.append(f'<< /Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace /DeviceGray '
                        f'/BitsPerComponent 8 /Filter /FlateDecode /Length {len(alpha)} >>\nstream\n'.encode()
                        + alpha + b'\nendstream')
            smask = f' /SMask {len(objs)} 0 R'
        objs.append(f'<< /Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace /DeviceRGB '
                    f'/BitsPerComponent 8 /Interpolate false /Filter /FlateDecode /Length {len(rgb)}{smask} >>'
                    '\nstream\n'.encode() + rgb + b'\nendstream')
        xobj.append(f'/Im{k} {len(objs)} 0 R')
    # /Resources est obligatoire, même sans rien à déclarer : sans elle Inkscape 1.3 s'arrête à l'ouverture
    res = f'/Resources << /XObject << {" ".join(xobj)} >> >> ' if xobj else '/Resources << /ProcSet [/PDF] >> '
    for i in at:                                         # objet i + 1 : la page ; i + 2 : son contenu
        objs[i] = (f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {_f(W)} {_f(H)}] {res}'
                   f'/Contents {i + 2} 0 R >>').encode()
    title = ''.join(ch for ch in title if 32 <= ord(ch) < 127 and ch not in '()\\')
    objs.append(f'<< /Producer (VectorDrive) /Title ({title}) >>'.encode())
    out = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f'{i} 0 obj\n'.encode() + body + b'\nendobj\n'
    xref = len(out)
    out += f'xref\n0 {len(objs) + 1}\n0000000000 65535 f \n'.encode()
    for o in offsets:
        out += f'{o:010d} 00000 n \n'.encode()
    out += (f'trailer\n<< /Size {len(objs) + 1} /Root 1 0 R /Info {len(objs)} 0 R >>\n'
            f'startxref\n{xref}\n%%EOF\n').encode()
    return bytes(out)


#: carré unité du PDF (y vers le haut, 1re ligne en haut) → carré unité de l'image (v vers le bas)
PDF_UNIT = Affine(1, 0, 0, -1, 0, 1)


#: dessin en image : résolution permise, et nombre de pixels au plus (au-delà, la résolution baisse)
IMAGE_DPI = (72, 1200)
IMAGE_PIXELS = 60_000_000


def drawing_image(prims: list, PW: float, PH: float, dpi: float):
    """Les primitives du dessin peintes sur fond blanc dans une image : ((largeur, hauteur, RVB compressé, None),
    matrice carré unité → page en mm, comme `Prim.matrix`). None : rien à peindre."""
    boxes = []
    for pr in prims:
        if pr.image is not None:
            pts = [pr.matrix.apply(q) for q in ((0, 0), (1, 0), (0, 1), (1, 1))]
            boxes.append((min(q[0] for q in pts), min(q[1] for q in pts), max(q[0] for q in pts), max(q[1] for q in pts)))
        else:
            b = pr.path.bbox() if pr.path is not None and pr.path.contours else None
            if b:
                boxes.append((b[0] - pr.width, b[1] - pr.width, b[2] + pr.width, b[3] + pr.width))
    if not boxes:
        return None
    x0 = max(0.0, min(b[0] for b in boxes) - 0.5)
    y0 = max(0.0, min(b[1] for b in boxes) - 0.5)
    x1 = min(PW, max(b[2] for b in boxes) + 0.5)
    y1 = min(PH, max(b[3] for b in boxes) + 0.5)
    if x1 - x0 <= 0 or y1 - y0 <= 0:
        return None
    try:
        dpi = float(dpi)
    except (TypeError, ValueError):
        dpi = 300.0
    k = max(IMAGE_DPI[0], min(IMAGE_DPI[1], dpi)) / 25.4                  # pixels par millimètre
    k = min(k, (IMAGE_PIXELS / ((x1 - x0) * (y1 - y0))) ** 0.5)
    w, h = max(1, round((x1 - x0) * k)), max(1, round((y1 - y0) * k))
    from PySide6.QtGui import QColor, QImage, QPainter, QTransform
    from .raster import _app
    from ..ui.printing import paint_prims
    _app()
    img = QImage(w, h, QImage.Format.Format_RGB888)
    img.fill(QColor('white'))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    paint_prims(p, prims, QTransform(k, 0, 0, -k, -x0 * k, y1 * k), min_pen=1.0 / k)
    p.end()
    import numpy as np
    px = np.frombuffer(bytes(img.constBits())[:img.sizeInBytes()], np.uint8)
    px = px.reshape(h, img.bytesPerLine())[:, :3 * w]
    return (w, h, zlib.compress(px.tobytes(), 6), None), Affine(x1 - x0, 0, 0, -(y1 - y0), x0, y1)


def free_name(path) -> pathlib.Path:
    """Le chemin, ou « nom (2).pdf », « nom (3).pdf »… s'il existe déjà."""
    p = pathlib.Path(path)
    if not p.exists():
        return p
    stem = p.stem
    import re
    m = re.match(r'^(.*) \((\d+)\)$', stem)
    base, k = (m.group(1), int(m.group(2)) + 1) if m else (stem, 2)
    while (p.parent / f'{base} ({k}){p.suffix}').exists():
        k += 1
    return p.parent / f'{base} ({k}){p.suffix}'


def write(doc: Document, path, info: ProofInfo | None = None, items=None) -> None:
    from .pdf import path_ops
    from ..core.text import ensure_outlines
    info = info or ProofInfo()
    ensure_outlines(doc)                             # textes jamais affichés : présents sur le BAT
    prims, PW, PH = build(doc, info, items)          # sans les prix s'ils ont leur page
    pages = price_pages(doc, info, items)            # question 29 : les prix sur une page à part
    m = Affine.scaling(1 / PT_MM)
    ops = ['1 J 1 j']
    images = []
    if getattr(info, 'as_image', False):                 # le dessin en image : son tracé n'est pas dans le PDF
        got = drawing_image([pr for pr in prims if pr.layer == 'dessin'], PW, PH, getattr(info, 'image_dpi', 300))
        if got is not None:
            t = m @ got[1] @ PDF_UNIT
            ops.append(f'q {_f(t.a)} {_f(t.b)} {_f(t.c)} {_f(t.d)} {_f(t.e)} {_f(t.f)} cm /Im0 Do Q')
            images.append(got[0])
            prims = [pr for pr in prims if pr.layer != 'dessin']
    shared: dict = {}                                    # la même image (filigrane répété) : un seul objet
    _page_ops(prims, m, ops, images, shared)
    more = []
    for t, lines in pages:
        for page in price_page_prims(info, t, lines, PW, PH):
            more.append(['1 J 1 j'])
            _page_ops(page, m, more[-1], images, shared)
    title = 'BAT ' + (info.reference if info.reference else pathlib.Path(path).stem)
    pathlib.Path(path).write_bytes(pdf_bytes(ops, PW / PT_MM, PH / PT_MM, images, title, more))


def _page_ops(prims: list, m, ops: list, images: list, shared: dict) -> None:
    """Les opérations PDF des primitives d'une page, ajoutées à `ops` ; leurs images ajoutées à `images` (une seule
    fois chacune : `shared`, commun à toutes les pages)."""
    from .pdf import path_ops
    for pr in prims:
        if pr.image is not None:
            if id(pr.image) not in shared:
                st = image_streams(pr.image)
                shared[id(pr.image)] = None if st is None else len(images)
                if st is not None:
                    images.append(st)
            at = shared[id(pr.image)]
            if at is None:
                continue
            t = m @ pr.matrix @ PDF_UNIT
            ops.append(f'q {_f(t.a)} {_f(t.b)} {_f(t.c)} {_f(t.d)} {_f(t.e)} {_f(t.f)} cm /Im{at} Do Q')
            continue
        r, g, b = pr.color
        if pr.fill:
            fr, fg, fb = pr.fill_color or pr.color
            ops.append(f'{_f(fr)} {_f(fg)} {_f(fb)} rg')
        if pr.width > 0:
            ops.append(f'{_f(r)} {_f(g)} {_f(b)} RG {_f(pr.width / PT_MM)} w')
        ops.extend(path_ops(pr.path, m))
        if pr.fill and pr.width > 0:
            ops.append('B*')
        elif pr.fill:
            ops.append('f*')
        else:
            ops.append('S')
