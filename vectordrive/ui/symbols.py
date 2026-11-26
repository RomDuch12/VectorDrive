"""Bibliothèque de symboles (.smb) : dossiers, vignettes, recherche,
insertion par double-clic ou glisser-déposer.

Les vignettes viennent de l'aperçu DIB enregistré dans chaque symbole :
instantané, même pour des milliers de fichiers. Le chargement se fait par
petits paquets pour ne jamais figer l'interface.
"""
from __future__ import annotations

import pathlib

from PySide6.QtCore import QMimeData, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDrag, QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (QCheckBox, QDialog, QFileDialog, QHBoxLayout, QHeaderView, QInputDialog, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMenu, QMessageBox, QPushButton, QSlider,
                               QSplitter, QStyle, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from ..io import smb
from .canvas import dib_to_qimage
from ..i18n import tr

#: bibliothèques de symboles proposées d'office (les plugins en ajoutent)
DEFAULT_ROOTS: list[pathlib.Path] = []
THUMB = 72
#: tailles des vignettes proposées (curseur) ; au-delà de la vignette enregistrée, tracé vectoriel
THUMB_MIN, THUMB_MAX = 48, 320
#: réglage : taille des vignettes (panneau, grande fenêtre)
SIZE_KEY = 'symboles/taille'
#: réglage : derniers fichiers posés (le plus récent d'abord) ; ligne « Récents » de l'arbre
RECENT_KEY = 'symboles/recents'
RECENT_MAX = 30
RECENTS = '::recents'
#: réglage : favoris (fichiers et dossiers) ; ligne « Favoris » de l'arbre
FAV_KEY = 'symboles/favoris'
FAVORITES = '::favoris'
VIRTUAL = (RECENTS, FAVORITES)


def favorite_paths(settings, key: str = FAV_KEY) -> list[pathlib.Path]:
    """Favoris qui existent encore (fichiers et dossiers), dans l'ordre d'ajout."""
    v = settings.value(key, []) if settings is not None else []
    if isinstance(v, str):
        v = [v] if v else []
    return [pathlib.Path(p) for p in (v or []) if p and (is_remote(p) or pathlib.Path(p).exists())]


def toggle_favorite(settings, path, key: str = FAV_KEY) -> bool:
    """Ajoute (ou retire) un favori ; rend vrai s'il est maintenant favori."""
    p = str(pathlib.Path(path))
    cur = [str(x) for x in favorite_paths(settings, key)]
    if any(c.lower() == p.lower() for c in cur):
        settings.setValue(key, [c for c in cur if c.lower() != p.lower()])
        return False
    settings.setValue(key, cur + [p])
    return True


def favorite_split(settings, key: str = FAV_KEY, exts=()) -> tuple[list, list]:
    """(dossiers, fichiers) favoris, dans l'ordre d'ajout. Un favori d'un partage n'est pas lu (hors d'atteinte, il
    figerait la fenêtre) : avec une extension de `exts` c'est un fichier, sinon un dossier."""
    exts = tuple(e.lower() for e in exts)
    dirs, files = [], []
    for p in favorite_paths(settings, key):
        if is_remote(p):
            (files if p.suffix.lower() in exts else dirs).append(p)
        elif p.is_dir():
            dirs.append(p)
        elif p.is_file():
            files.append(p)
    return dirs, files


def recent_files(settings) -> list[pathlib.Path]:
    """Derniers fichiers posés qui existent encore."""
    v = settings.value(RECENT_KEY, []) if settings is not None else []
    if isinstance(v, str):
        v = [v] if v else []
    # réseau : gardés sans vérifier (un partage hors d'atteinte ne fige pas la fenêtre)
    return [pathlib.Path(p) for p in (v or []) if p and (is_remote(p) or pathlib.Path(p).is_file())]


def remember_recent(settings, path) -> None:
    """Fichier posé : en tête des récents (sans doublon, 30 au plus)."""
    if settings is None:
        return
    p = str(pathlib.Path(path))
    old = [str(x) for x in recent_files(settings) if str(x).lower() != p.lower()]
    settings.setValue(RECENT_KEY, ([p] + old)[:RECENT_MAX])
BIG_SIZE_KEY = 'symboles/taille_grande'


#: fichiers posables depuis la bibliothèque (symboles TypeEdit, dessins DXF, dessins VectorDrive)
LIBRARY_EXT = ('.smb', '.dxf', '.vdz', '.vnd', '.svg', '.dwg')


def library_root() -> pathlib.Path:
    """Bibliothèque de l'atelier (touche B) : dossier `bibliotheque` à côté
    du programme (`VECTORDRIVE_BIBLIOTHEQUE` : ailleurs ; sans exécutable :
    dans les données de VectorDrive). Créé au premier usage."""
    import os
    from .. import portable
    forced = os.environ.get('VECTORDRIVE_BIBLIOTHEQUE')
    if forced:
        return pathlib.Path(forced)
    base = portable.app_dir() or portable.data_dir()
    return base / 'bibliotheque'


#: dossiers de la bibliothèque interne : les logos employés dans un BAT, les fichiers qu'on y garde (clic droit)
LOGOS_DIR = 'Logos BAT'
KEPT_DIR = 'Favoris'


def logo_library() -> pathlib.Path:
    """Dossier « Logos BAT » de la bibliothèque interne : chaque logo d'un BAT validé y est copié une fois, pour
    les fois suivantes (pas créé ici)."""
    return library_root() / LOGOS_DIR


def internal_favorites() -> pathlib.Path:
    """Dossier « Favoris » de la bibliothèque interne : les fichiers qu'on y copie pour les garder (pas créé
    ici)."""
    return library_root() / KEPT_DIR


def logo_exts() -> tuple:
    """Extensions des fichiers qui servent de logo à un BAT : les images, puis les dessins que VectorDrive lit."""
    from ..io import proof
    return tuple(e.lstrip('*') for e in proof.logo_filter().split())


def is_below(path, folder) -> bool:
    """`path` est-il `folder`, ou dans `folder` ? (comparaison des chemins : le disque n'est pas lu)"""
    import os
    try:
        pathlib.Path(os.path.abspath(path)).relative_to(os.path.abspath(folder))
    except (ValueError, OSError):
        return False
    return True


def same_content(a, b) -> bool:
    """Les deux fichiers ont-ils le même contenu ? (faux aussi si l'un ne se lit pas)"""
    import os
    try:
        sa, sb = os.stat(a), os.stat(b)
        if sa.st_size != sb.st_size:
            return False
        if sa.st_mtime == sb.st_mtime:                   # même taille, même date (la copie la garde) : le même
            return True
        with open(a, 'rb') as fa, open(b, 'rb') as fb:
            while True:
                x, y = fa.read(1 << 16), fb.read(1 << 16)
                if x != y:
                    return False
                if not x:
                    return True
    except OSError:
        return False


#: le choix du nom d'une copie gardée et sa pose (rapides : le dossier local seulement), une à la fois (round 1164)
_KEEP_LOCK = __import__('threading').Lock()
#: fichier temporaire d'une copie gardée (`tempfile.mkstemp` : « .vdkeep.<nom>.<8 signes>.tmp », préfixe propre à
#: l'application : jamais un fichier de l'utilisateur) ; au-delà d'un jour : un reste (application quittée pendant
#: une copie), retiré à la copie suivante dans ce dossier
KEEP_PREFIX = '.vdkeep.'
KEEP_TMP = r'\.vdkeep\..+\.[a-z0-9_]{8}\.tmp'
KEEP_TMP_AGE = 86400.0
#: les fichiers temporaires des copies en cours (chemins normalisés, sous `_KEEP_LOCK`) : jamais purgés
_KEEP_BUSY: set = set()
#: hors Windows, la copie est posée par un lien dur (qui échoue si le nom est pris ; `os.rename` y écraserait)
_KEEP_LINK = __import__('os').name != 'nt'


def _linked(tmp, dst) -> bool:
    """`tmp` posé sous `dst` par un lien dur, puis retiré ; FileExistsError si `dst` est pris ; faux si le disque
    n'a pas de liens durs (FAT, certains partages) : à poser autrement."""
    import os
    try:
        os.link(tmp, dst)
    except FileExistsError:
        raise
    except (OSError, AttributeError, NotImplementedError):
        return False
    try:
        os.unlink(tmp)                                   # (pas `_drop_tmp` : même fichier que la copie, ses droits
    except OSError:                                      # restent ; un reste éventuel : purgé plus tard)
        pass
    return True


def _drop_tmp(tmp) -> None:
    """Le fichier temporaire d'une copie retiré, même en lecture seule (attribut copié de l'original par `copy2` :
    Windows refuse alors de l'effacer ; pas de changement d'attribut sur un lien) ; sans erreur s'il ne s'efface
    pas."""
    import os
    import stat
    try:
        if os.name == 'nt' and not os.path.islink(tmp):     # (ailleurs, inutile pour effacer)
            os.chmod(tmp, stat.S_IREAD | stat.S_IWRITE)
        os.unlink(tmp)
    except OSError:
        pass


def _purge_tmp(folder) -> None:
    """Les fichiers temporaires de copie de plus d'un jour retirés de `folder` : ceux de notre motif seulement, ni
    lien ni dossier, jamais celui d'une copie en cours ; l'âge : la plus récente de la date du contenu (celle de
    l'original, que `copy2` reporte) et de celle de création ou de changement du fichier."""
    import os
    import re
    import time
    limit = time.time() - KEEP_TMP_AGE
    with _KEEP_LOCK:                                     # (une copie qui pose son temporaire attend)
        try:
            entries = list(os.scandir(folder))
        except OSError:
            return
        for e in entries:
            try:
                if not re.fullmatch(KEEP_TMP, e.name) or not e.is_file(follow_symlinks=False) \
                        or os.path.normcase(e.path) in _KEEP_BUSY:
                    continue
                st = e.stat(follow_symlinks=False)
            except OSError:
                continue
            if max(st.st_mtime, st.st_ctime) < limit:
                _drop_tmp(e.path)


def keep_copy(src, folder, made: list | None = None) -> pathlib.Path | None:
    """`src` gardé une fois dans `folder` (créé au besoin), sous son nom : déjà dans ce dossier, il n'est pas
    recopié ; un fichier de même nom et de même contenu y est déjà sa copie (pas de doublon) ; de même nom mais
    d'un autre contenu : « nom (2) »… Rend la copie (ajoutée à `made` si elle vient d'être faite) ; None : `src`
    n'est pas un fichier. OSError : copie impossible. Deux copies en même temps (fil des logos d'un partage, round
    1164) : chacune son fichier temporaire, le nom de destination choisi ensuite sous verrou."""
    import os
    import shutil
    import stat
    import tempfile
    src, folder = pathlib.Path(src), pathlib.Path(folder)
    if not src.is_file():
        return None
    if is_below(src, folder):
        return src
    folder.mkdir(parents=True, exist_ok=True)
    _purge_tmp(folder)                                   # (restes d'une copie interrompue : round 1164)
    n = 1
    while True:
        dst = folder / (src.name if n == 1 else f'{src.stem} ({n}){src.suffix}')
        if not dst.exists():
            break
        if dst.is_file() and same_content(src, dst):
            return dst
        n += 1
    # copie entière ou rien (disque plein, partage coupé), dans un fichier temporaire à elle (extension non montrée)
    fd, name = tempfile.mkstemp(dir=folder, prefix=KEEP_PREFIX + src.name + '.', suffix='.tmp')
    os.close(fd)
    tmp, busy = pathlib.Path(name), os.path.normcase(name)
    with _KEEP_LOCK:
        _KEEP_BUSY.add(busy)                             # (jamais purgé pendant la copie)
    try:
        shutil.copy2(src, tmp)
        os.chmod(tmp, stat.S_IMODE(os.stat(tmp).st_mode) | stat.S_IWRITE)   # modifiable (original en lecture seule)
        with _KEEP_LOCK:                                 # le nom : choisi maintenant (une autre copie a pu le
            n = 1                                        # prendre pendant la nôtre)
            while True:
                dst = folder / (src.name if n == 1 else f'{src.stem} ({n}){src.suffix}')
                if not os.path.lexists(dst):             # (un lien cassé de ce nom : pris aussi)
                    try:
                        if not (_KEEP_LINK and _linked(tmp, dst)):
                            os.rename(tmp, dst)          # (Windows : sans écraser ; ailleurs, sans liens durs)
                        break
                    except FileExistsError:              # pris entre-temps : le nom suivant
                        n += 1
                        continue
                if dst.is_file() and same_content(tmp, dst):    # la même, posée entre-temps : la sienne
                    _drop_tmp(tmp)
                    return dst
                n += 1
    except OSError:
        _drop_tmp(tmp)
        raise
    finally:
        with _KEEP_LOCK:
            _KEEP_BUSY.discard(busy)
    if made is not None:
        made.append(dst)
    return dst


def default_roots() -> list[pathlib.Path]:
    from .. import portable
    from ..plugins import REGISTRY
    extra = str(portable.settings().value('symboles/dossiers_extra', '') or '')
    lib = library_root()
    try:
        lib.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return [lib] + DEFAULT_ROOTS + [pathlib.Path(r) for r in REGISTRY.symbol_roots] + \
        [pathlib.Path(d.strip()) for d in extra.split(';') if d.strip()]


#: symboles lus pour la séance : (chemin, date, taille) → objet ; une nouvelle pose en est une copie
_GROUPS: dict = {}
GROUPS_MAX = 32


def file_as_group(path):
    """Un fichier de la bibliothèque comme un seul objet centré sur
    l'origine : symbole .smb, ou tout dessin lisible (DXF, VDZ…) groupé.
    Gardé pour la séance (poser dix fois le même gros DXF ne le relit
    qu'une fois) ; chaque appel rend une copie neuve (identifiants propres)."""
    p = pathlib.Path(path)
    try:
        st = p.stat()
        key = (str(p.resolve()).lower(), st.st_mtime, st.st_size)
    except OSError:
        key = None
    hit = _GROUPS.get(key) if key else None
    if hit is not None:
        return hit.clone()
    g = _read_as_group(p)
    if key and g is not None:
        if len(_GROUPS) >= GROUPS_MAX:
            _GROUPS.pop(next(iter(_GROUPS)))
        _GROUPS[key] = g
        return g.clone()
    return g


def _read_as_group(p: pathlib.Path):
    from ..core.document import Group
    from ..core.geom import Affine
    from ..io import companion, smb
    if p.suffix.lower() == '.smb':
        return smb.as_group(str(p))
    doc = companion.open_document(str(p), plates=False)      # son compagnon, sans plaques de reprise (round 1174)
    items = [it for L in doc.layers for it in L.items if getattr(it, 'visible', True)]
    if not items:
        return None
    colors = doc.tool_colors(items)                      # couleurs du fichier, gardées à la pose
    g = items[0] if len(items) == 1 and isinstance(items[0], Group) else Group(children=items)
    bb = g.bbox()
    if bb:
        g = g.transformed(Affine.translation(-(bb[0] + bb[2]) / 2, -(bb[1] + bb[3]) / 2))
    g.name = p.stem
    g = g.clone()
    g.extra['tool_colors'] = colors
    return g


def _leaves_of(path):
    """(objets du fichier, couleur d'outil → hex) : symbole ou dessin."""
    from ..io import companion, smb
    p = pathlib.Path(path)
    if p.suffix.lower() == '.smb':
        doc = smb.read(str(p))
    else:
        doc = companion.open_document(str(p), plates=False)  # son compagnon, sans plaques de reprise (round 1174)
    return list(doc.iter_leaves()), doc


def external_reader(path) -> bool:
    """Fichier lu par un autre logiciel (Inkscape, convertisseur CATIA) : ni vignette ni fiche d'office — en tracer
    une par fichier d'un dossier lancerait ce logiciel autant de fois. Ouvert, il est lu comme les autres."""
    from ..io import registry
    f = registry.by_extension(path)
    return f is not None and f.key in ('inkscape', 'catia', 'dwg')


def describe_file(path) -> str:
    """Fiche d'un fichier de la bibliothèque : nom, taille (mm), objets, contours."""
    p = pathlib.Path(path)
    from . import nc_preview
    if nc_preview.is_program(p):                         # programme machine : sa fiche
        return nc_preview.describe(p)
    if external_reader(p):
        from ..io import registry
        hint = tr('lu par un autre logiciel : aperçu une fois ouvert')
        return f'{p.name}\n{tr(registry.by_extension(p).label)}\n{hint}'
    try:
        leaves, doc = _leaves_of(p)
    except Exception as ex:                              # fichier illisible : la raison
        return f'{p.name}\n{tr("illisible")} : {ex}'
    bb = doc.bbox()
    n_c = sum(len(getattr(getattr(it, 'path', None) or getattr(it, 'outline', None), 'contours', []) or [])
              for it in leaves)
    lines = [p.name]
    if bb:
        lines.append(f'{bb[2] - bb[0]:.2f} × {bb[3] - bb[1]:.2f} mm'.replace('.', ','))
    lines.append(tr('{0} objet(s), {1} contour(s)').format(len(leaves), n_c))
    tools = sorted({int(getattr(it, 'tool', 0) or 0) for it in leaves})
    if len(tools) > 1:                                   # couleurs gardées : combien d'outils
        lines.append(tr('{0} couleurs (outils {1})').format(len(tools), ', '.join(str(t + 1) for t in tools[:8])
                                                           + (' …' if len(tools) > 8 else '')))
    try:
        import datetime as _dt
        st = p.stat()
        lines.append(f'{st.st_size / 1024:.0f} Ko — ' + _dt.datetime.fromtimestamp(st.st_mtime).strftime('%d/%m/%Y'))
    except OSError:
        pass
    return '\n'.join(lines)


def dwg_preview_image(path, size: int = THUMB):
    """Vignette d'un DWG : l'aperçu enregistré dans son en-tête (le fond d'AutoCAD compris), centré sur un carré
    blanc ; None s'il n'en a pas. Sans ODA File Converter : instantané."""
    from PySide6.QtCore import Qt as _Qt
    from PySide6.QtGui import QColor, QImage, QPainter
    from ..io import dwg
    got = dwg.preview(path)
    if got is None:
        return None
    kind, data = got
    src = QImage.fromData(data, 'PNG') if kind == 'png' else dib_to_qimage(data)
    if src is None or src.isNull():
        return None
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor('white'))
    scaled = src.scaled(size, size, _Qt.AspectRatioMode.KeepAspectRatio, _Qt.TransformationMode.SmoothTransformation)
    painter = QPainter(img)
    painter.drawImage((size - scaled.width()) // 2, (size - scaled.height()) // 2, scaled)
    painter.end()
    return img


def preview_image(path, size: int = THUMB):
    """Vignette d'un fichier (symbole, DXF, VDZ…) tracée à la taille voulue :
    formes fermées teintées, contours à la couleur de leur outil."""
    from PySide6.QtCore import Qt as _Qt
    from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen
    from . import nc_preview
    if nc_preview.is_program(path):                      # programme machine : son parcours vu de dessus
        return nc_preview.preview_image(path, size)
    if pathlib.Path(path).suffix.lower() == '.dwg':      # l'aperçu de son en-tête, sans ODA File Converter
        return dwg_preview_image(path, size)
    if external_reader(path):
        return None
    try:
        leaves, doc = _leaves_of(path)
    except Exception:
        return None
    bb = doc.bbox()
    if not bb or bb[2] <= bb[0] and bb[3] <= bb[1]:
        return None
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor('white'))
    m = max(3, size // 24)
    span = max(bb[2] - bb[0], bb[3] - bb[1], 1e-9)
    k = (size - 2 * m) / span
    ox = m + ((size - 2 * m) - (bb[2] - bb[0]) * k) / 2
    oy = m + ((size - 2 * m) - (bb[3] - bb[1]) * k) / 2
    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    by_color: dict = {}
    _draw_images(painter, leaves, bb, k, ox, oy, size)       # images du dessin (logo scanné, photo…) dessous
    for it in leaves:
        p = getattr(it, 'path', None) or getattr(it, 'outline', None)
        if not p:
            continue
        qp = QPainterPath()
        qp.setFillRule(_Qt.FillRule.OddEvenFill)
        closed = False
        for c in p.contours:
            pts = c.flatten(max(0.02, 0.4 / k))
            if len(pts) < 2:
                continue
            qp.moveTo(ox + (pts[0][0] - bb[0]) * k, size - (oy + (pts[0][1] - bb[1]) * k))
            for x, y in pts[1:]:
                qp.lineTo(ox + (x - bb[0]) * k, size - (oy + (y - bb[1]) * k))
            if c.closed:
                qp.closeSubpath()
                closed = True
        try:
            col = doc.tool_color(getattr(it, 'tool', 0)) or '#1c3d6b'
        except Exception:                                # symbole sans table d'outils
            col = '#1c3d6b'
        if col.lower() in ('#ffffff', 'white'):
            col = '#1c3d6b'
        by_color.setdefault(col, []).append((qp, closed))
    for col, paths in by_color.items():
        tint = QColor(col)
        tint.setAlpha(40)
        for qp, closed in paths:
            painter.setPen(QPen(QColor(col), max(1.0, size / 220)))
            painter.setBrush(tint if closed else _Qt.BrushStyle.NoBrush)
            painter.drawPath(qp)
    painter.end()
    return img


def _draw_images(painter, leaves, bb, k: float, ox: float, oy: float, size: int) -> None:
    """Images du dessin dans la vignette, à leur place (comme le plan de travail)."""
    from PySide6.QtGui import QImage, QTransform
    from ..core.document import Image
    to_img = QTransform(k, 0, 0, -k, ox - bb[0] * k, size - oy + bb[1] * k)    # dessin → vignette
    for im in leaves:
        if not isinstance(im, Image) or not im.data:
            continue
        q = dib_to_qimage(im.data) if im.fmt == 'dib' else None
        if q is None:
            q = QImage.fromData(im.data)
        if q is None or q.isNull():
            continue
        m = im.matrix
        t = QTransform(m.a / q.width(), m.b / q.width(), m.c / q.height(), m.d / q.height(), m.e, m.f)
        painter.save()
        painter.setTransform(t * to_img)
        painter.setRenderHint(painter.RenderHint.SmoothPixmapTransform, True)
        painter.drawImage(0, 0, q)
        painter.restore()


class ImageCache:
    """Vignettes déjà tracées, (chemin, taille, date) → QImage, bornées en
    mémoire (F10 › Performances : `perf/cache_vignettes`, en Mo) : les moins
    récemment vues partent d'abord."""

    def __init__(self, budget_mb: float = 256):
        from collections import OrderedDict
        self._d = OrderedDict()
        self._sizes: dict = {}                           # (chemin, date) → tailles gardées
        self.budget = int(budget_mb * 1024 * 1024)
        self.used = 0

    @staticmethod
    def _size(img) -> int:
        try:
            return int(img.sizeInBytes()) if img is not None else 64
        except (AttributeError, RuntimeError):
            return 64

    def set_budget(self, mb: float) -> None:
        self.budget = int(max(16, mb) * 1024 * 1024)
        self._trim()

    def _forget(self, key) -> None:
        if isinstance(key, tuple) and len(key) == 3:
            sizes = self._sizes.get((key[0], key[2]))
            if sizes is not None:
                sizes.discard(key[1])
                if not sizes:
                    del self._sizes[(key[0], key[2])]

    def _trim(self) -> None:
        while self.used > self.budget and self._d:
            k, img = self._d.popitem(last=False)
            self.used -= self._size(img)
            self._forget(k)

    def nearest(self, path: str, size: int, mtime):
        """(vignette, taille) gardée du même fichier à une autre taille : la plus
        petite au moins aussi grande, sinon la plus grande ; (None, 0) sinon."""
        sizes = self._sizes.get((path, mtime))
        if not sizes:
            return None, 0
        bigger = [s for s in sizes if s >= size and self._d.get((path, s, mtime)) is not None]
        pick = min(bigger) if bigger else max((s for s in sizes if self._d.get((path, s, mtime)) is not None),
                                              default=0)
        return (self._d.get((path, pick, mtime)), pick) if pick else (None, 0)

    def get(self, key, default=None):
        if key in self._d:
            self._d.move_to_end(key)
            return self._d[key]
        return default

    def __contains__(self, key) -> bool:
        return key in self._d

    def __getitem__(self, key):
        self._d.move_to_end(key)
        return self._d[key]

    def __setitem__(self, key, img) -> None:
        if key in self._d:
            self.used -= self._size(self._d.pop(key))
        self._d[key] = img
        self.used += self._size(img)
        if isinstance(key, tuple) and len(key) == 3:
            self._sizes.setdefault((key[0], key[2]), set()).add(key[1])
        self._trim()

    def __len__(self) -> int:
        return len(self._d)

    def clear(self) -> None:
        self._d.clear()
        self._sizes.clear()
        self.used = 0


#: vignettes des dessins déjà tracées (chemin, taille, date → QImage), bornées en mémoire
_PREVIEWS = ImageCache()
#: fiches des fichiers (chemin, date → texte) déjà lues pour la séance
_INFOS: dict = {}


def _details(path, side: int, want_img: bool, want_info: bool):
    """(grand aperçu, fiche) d'un fichier — dans le fil de la fiche."""
    img = preview_image(path, side) if want_img else None
    info = describe_file(path) if want_info else None
    if len(_INFOS) > 2000:
        _INFOS.clear()
    return img, info
#: au-delà de ce temps moyen par vignette (s : gros DXF, dossier réseau), les suivantes sont tracées
#: sur plusieurs processus (la lecture d'un dessin est du Python : un seul cœur par processus)
SLOW_PREVIEW_S = 0.5
_PROC_POOL = None
_APP = None                                     # application Qt d'un processus de vignettes


def _timed_preview(path, size):
    """(vignette QImage, durée) — dans le fil des vignettes."""
    import time
    t0 = time.perf_counter()
    img = preview_image(path, size)
    return img, time.perf_counter() - t0


def preview_png(path, size):
    """(vignette en PNG, durée) — dans un processus de vignettes."""
    import time
    global _APP
    from PySide6.QtCore import QBuffer, QIODevice
    from PySide6.QtGui import QGuiApplication
    _APP = QGuiApplication.instance() or QGuiApplication([])
    t0 = time.perf_counter()
    img = preview_image(path, size)
    if img is None or img.isNull():
        return b'', time.perf_counter() - t0
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, 'PNG')
    return bytes(buf.data()), time.perf_counter() - t0


#: processus des vignettes rendus après ce temps sans travail (s) : 6 × 150 Mo ne restent pas en mémoire
PROC_IDLE_S = 60.0
_PROC_USED = 0.0


def preview_processes():
    """Processus des vignettes lentes (créés au premier besoin, rendus après
    PROC_IDLE_S secondes sans travail : release_preview_processes)."""
    global _PROC_POOL, _PROC_USED
    import time
    _PROC_USED = time.monotonic()
    if _PROC_POOL is None:
        import atexit
        import multiprocessing
        from concurrent.futures import ProcessPoolExecutor
        from .. import plugins as PL
        from ..core import workers
        _PROC_POOL = ProcessPoolExecutor(max(1, min(6, workers.process_limit())), mp_context=multiprocessing.get_context('spawn'),
                                         initializer=workers._start_process, initargs=(bool(PL.REGISTRY.plugins),))
        atexit.register(lambda: workers.terminate_pool(_PROC_POOL))
    return _PROC_POOL


def release_preview_processes(force: bool = False) -> bool:
    """Processus des vignettes arrêtés s'ils n'ont pas servi depuis
    PROC_IDLE_S secondes (ou tout de suite avec `force`) ; rend vrai s'il y en avait."""
    global _PROC_POOL
    import time
    if _PROC_POOL is None or (not force and time.monotonic() - _PROC_USED < PROC_IDLE_S):
        return False
    from ..core import workers
    pool, _PROC_POOL = _PROC_POOL, None
    workers.terminate_pool(pool)
    return True
#: rôle des lignes de la liste : 'dir' (dossier), 'up' (dossier parent), sinon fichier
ROLE_KIND = Qt.ItemDataRole.UserRole + 1


#: attributs Windows « caché » et « système » (FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM)
HIDDEN_ATTRS = 0x2 | 0x4
#: éléments masqués montrés quand même (F10 › Fichiers, comme « Éléments masqués » de l'explorateur)
SHOW_HIDDEN = False


def is_hidden(entry) -> bool:
    """Fichier ou dossier caché ou système de Windows (AppData, Cookies…), comme l'explorateur les omet ;
    `entry` : os.DirEntry (attributs déjà lus par scandir) ou chemin."""
    if SHOW_HIDDEN:
        return False
    try:
        st = entry.stat(follow_symlinks=False) if hasattr(entry, 'is_dir') and hasattr(entry, 'path') \
            else pathlib.Path(entry).lstat()
    except OSError:
        return False
    return bool(getattr(st, 'st_file_attributes', 0) & HIDDEN_ATTRS)


_REMOTE: dict = {}


def is_remote(path) -> bool:
    """Dossier réseau (partage UNC, lecteur réseau) : sa lecture peut tarder (atelier hors d'atteinte)."""
    import os
    s = str(path)
    if s.startswith(('\\\\', '//')):
        return True
    drive = os.path.splitdrive(s)[0]
    if not drive or os.name != 'nt':
        return False
    if drive not in _REMOTE:
        try:
            import ctypes
            _REMOTE[drive] = ctypes.windll.kernel32.GetDriveTypeW(drive + '\\') == 4    # DRIVE_REMOTE
        except Exception:                                # noqa: BLE001 — sans l'API : disque local
            _REMOTE[drive] = False
    return _REMOTE[drive]


def list_dir(path: pathlib.Path, exts):
    """(fichiers d'extension `exts`, sous-dossiers, {chemin: (date, taille)}) d'un dossier, cachés et système
    omis, en une lecture ; None s'il n'existe pas ou ne se lit pas."""
    import os
    try:
        if not path.is_dir():
            return None
        with os.scandir(path) as sc:
            entries = [e for e in sc if not is_hidden(e)]
    except OSError:
        return None
    stats: dict = {}
    files, dirs = [], []
    exts = tuple(e.lower() for e in exts)
    for e in entries:
        try:
            if e.is_dir():
                dirs.append(pathlib.Path(e.path))
            elif e.is_file() and os.path.splitext(e.name)[1].lower() in exts:
                files.append(pathlib.Path(e.path))
            else:
                continue
        except OSError:
            continue
        remember_stat(stats, e)
    dirs.sort(key=lambda p: p.name.lower())
    return files, dirs, stats


def remember_stat(stats: dict, entry) -> None:
    """stats[chemin] = (date, taille) d'une entrée de os.scandir (sous Windows, déjà lues avec le dossier)."""
    try:
        st = entry.stat(follow_symlinks=False)
        stats[entry.path] = (st.st_mtime, st.st_size)
    except OSError:
        pass


def known_stat(stats: dict | None, p: pathlib.Path):
    """(date, taille) de `p` : celle lue avec le dossier, sinon demandée au disque ; (0, None) si absent."""
    v = (stats or {}).get(str(p))
    if v is not None:
        return v
    if is_remote(p):                                     # réseau : pas d'accès dans le fil de l'interface
        return 0, None
    try:
        st = p.stat()
        return st.st_mtime, st.st_size
    except OSError:
        return 0, None


def walk_files(base: pathlib.Path, exts, match=None, limit: int = 4000, below_only: bool = False,
               out: list | None = None, match_path=None, stats: dict | None = None) -> list:
    """Fichiers de `base` et de ses sous-dossiers dont l'extension est dans `exts` (et dont le nom
    satisfait `match(nom)`), en profondeur, dossiers dans l'ordre du nom ; `below_only` : ceux des
    sous-dossiers seulement. Lecture du disque au plus juste (os.scandir, sans dossiers cachés ni
    système) ; avancement et Annuler (core.progress) ; `out` reçoit les fichiers au fur et à mesure
    (ce qui est lu reste si l'on annule). `match_path(chemin)` : essayé quand le nom ne répond pas
    (textes contenus dans le fichier…)."""
    import os
    from ..core import progress as P
    out = [] if out is None else out
    exts = tuple(e.lower() for e in exts)
    stack, dirs = [str(base)], 0
    while stack and len(out) < limit:
        d = stack.pop()
        P.check()
        try:
            with os.scandir(d) as sc:
                entries = list(sc)
        except OSError:
            continue
        dirs += 1
        task = P.current() if dirs % 25 == 0 else None
        if task is not None:                             # avancement indéterminé : dossiers lus, fichiers trouvés
            task.fraction = -1.0
            task.text = tr('{0} dossiers lus, {1} fichiers trouvés').format(dirs, len(out))
        subs = []
        for e in entries:
            try:
                if e.is_dir(follow_symlinks=False):
                    if not e.name.startswith(('.', '$')) and not is_hidden(e):
                        subs.append(e.path)
                elif (not below_only or d != str(base)) and os.path.splitext(e.name)[1].lower() in exts \
                        and not is_hidden(e) \
                        and (match is None or match(e.name)
                             or (match_path is not None and match_path(pathlib.Path(e.path)))):
                    out.append(pathlib.Path(e.path))
                    if stats is not None:
                        remember_stat(stats, e)
                    if len(out) >= limit:
                        break
            except OSError:
                continue
        stack.extend(sorted(subs, key=str.lower, reverse=True))
    return out


def move_into(src: pathlib.Path, folder: pathlib.Path, copy: bool = False) -> pathlib.Path:
    """Déplace (ou copie) un fichier ou un dossier dans `folder` ; nom libre
    (« nom (2) ») si la place est prise. Rend le nouveau chemin."""
    import shutil
    dst = folder / src.name
    n = 2
    while dst.exists():
        dst = folder / f'{src.stem} ({n}){src.suffix}' if src.is_file() else folder / f'{src.name} ({n})'
        n += 1
    if copy:
        (shutil.copytree if src.is_dir() else shutil.copy2)(src, dst)
    else:
        shutil.move(str(src), str(dst))
    return dst


def to_trash(path: pathlib.Path) -> bool:
    """Fichier ou dossier envoyé à la corbeille (jamais effacé pour de bon)."""
    from PySide6.QtCore import QFile
    return bool(QFile.moveToTrash(str(path)))


def _selection_drag(ev) -> bool:
    """Un glisser-déposer de la sélection du dessin (canvas.SELECTION_MIME), parti de cette instance ? (une autre
    a sa propre sélection : ce n'est pas elle qu'on enregistrerait ici)"""
    from .canvas import own_selection_drag
    return own_selection_drag(ev)


def _accept_copy(ev) -> None:
    """La sélection lâchée sur la Bibliothèque y est ajoutée et reste dans le dessin : une copie (curseur « + »)."""
    ev.setDropAction(Qt.DropAction.CopyAction)
    ev.accept()


class FolderTree(QTreeWidget):
    """Arbre des dossiers : y déposer des fichiers de la liste (ou de
    l'explorateur) les range dans le dossier visé ; y déposer la sélection
    du dessin l'y ajoute."""
    filesDropped = Signal(list, str, bool)       # chemins, dossier, copie
    selectionDropped = Signal(str)               # la sélection du dessin, dans ce dossier

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)

    def _target(self, ev):
        it = self.itemAt(ev.position().toPoint())
        return it.data(0, Qt.ItemDataRole.UserRole) if it is not None else None

    def dragEnterEvent(self, ev) -> None:
        if _selection_drag(ev):
            _accept_copy(ev)
        elif ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dragMoveEvent(self, ev) -> None:
        target = self._target(ev)
        if _selection_drag(ev) and target and target not in VIRTUAL:
            _accept_copy(ev)
        elif ev.mimeData().hasUrls() and target:
            ev.acceptProposedAction()
        else:
            ev.ignore()

    def dropEvent(self, ev) -> None:
        folder = self._target(ev)
        if _selection_drag(ev):
            if folder and folder not in VIRTUAL:         # Récents, Favoris : pas des dossiers
                _accept_copy(ev)
                # après le glisser-déposer (le nom est demandé dans une fenêtre)
                QTimer.singleShot(0, lambda f=folder: self.selectionDropped.emit(f))
            else:
                ev.ignore()
            return
        files = [u.toLocalFile() for u in ev.mimeData().urls() if u.isLocalFile()]
        if folder and files:
            copy = bool(ev.modifiers() & Qt.KeyboardModifier.ControlModifier) or ev.source() is None
            ev.acceptProposedAction()
            self.filesDropped.emit(files, folder, copy)


class SymbolList(QListWidget):
    selectionDropped = Signal()                  # la sélection du dessin lâchée sur la liste (dossier affiché)

    def __init__(self, size: int = THUMB):
        super().__init__()
        self.setAcceptDrops(True)                    # la sélection du dessin seulement (le reste : comme avant)
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.set_thumb(size)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setMovement(QListWidget.Movement.Static)
        self.viewport().setAcceptDrops(True)             # Static les retire au viewport : aucun dépôt n'arrivait
        self.setWordWrap(True)
        self.setDragEnabled(True)
        self.setUniformItemSizes(False)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)

    def set_thumb(self, size: int) -> None:
        self.thumb = int(size)
        self.setIconSize(QSize(self.thumb, self.thumb))
        self.setGridSize(QSize(self.thumb + 28, self.thumb + 34))

    def dragEnterEvent(self, ev) -> None:
        if _selection_drag(ev):
            _accept_copy(ev)
        else:
            ev.ignore()

    def dragMoveEvent(self, ev) -> None:
        if _selection_drag(ev):
            _accept_copy(ev)
        else:
            ev.ignore()

    def dropEvent(self, ev) -> None:
        if _selection_drag(ev):
            _accept_copy(ev)
            QTimer.singleShot(0, self.selectionDropped.emit)    # après le glisser-déposer (fenêtre du nom)
        else:
            ev.ignore()

    def startDrag(self, actions) -> None:
        items = [i for i in self.selectedItems() if i.data(ROLE_KIND) != 'up'] or \
            ([self.currentItem()] if self.currentItem() is not None else [])
        if not items:
            return
        it = items[0]
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(i.data(Qt.ItemDataRole.UserRole)) for i in items])
        drag = QDrag(self)
        drag.setMimeData(mime)
        if not it.icon().isNull():
            drag.setPixmap(it.icon().pixmap(48, 48))
        drag.exec(Qt.DropAction.CopyAction)


class LibraryWindow(QDialog):
    """La bibliothèque en grande fenêtre (non modale) : dossiers, grandes
    vignettes, aperçu et fiche ; double-clic : posé dans le dessin."""

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.vd_keep = True                              # réemployée : pas détruite à la fermeture
        self.setWindowTitle(tr('Bibliothèque'))
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.setSizeGripEnabled(True)
        self.settings = settings
        lay = QVBoxLayout(self)
        self.panel = SymbolPanel(settings, self, big=True)
        lay.addWidget(self.panel)
        self.close_after = QCheckBox(tr('Fermer après avoir posé'))
        self.close_after.setToolTip(tr('La fenêtre se ferme dès qu\'un fichier est posé dans le dessin'))
        self.close_after.setChecked(settings.value('symboles/fermer_apres', 'false') in (True, 'true'))
        self.close_after.toggled.connect(lambda on: settings.setValue('symboles/fermer_apres', bool(on)))
        self.click_place = QCheckBox(tr('Double-clic : fermer la fenêtre et poser le dessin d\'un clic'))
        self.click_place.setToolTip(tr('Le dessin suit le pointeur dans le plan de travail ; un clic le pose '
                                       '(centré), Échap : rien. Décoché : posé au centre de la vue'))
        self.click_place.setChecked(settings.value('symboles/poser_au_clic', 'true') in (True, 'true'))
        self.click_place.toggled.connect(lambda on: settings.setValue('symboles/poser_au_clic', bool(on)))
        self.click_place.toggled.connect(lambda on: self.close_after.setEnabled(not on))
        self.close_after.setEnabled(not self.click_place.isChecked())
        row = QHBoxLayout()
        row.addWidget(self.click_place)
        row.addWidget(self.close_after)
        row.addStretch(1)
        lay.addLayout(row)
        from PySide6.QtGui import QKeySequence, QShortcut
        QShortcut(QKeySequence('F11'), self, activated=self.toggle_full_screen)
        from .tool_filters import open_large
        self.resize(1400, 860)
        open_large(self, settings, 'symboles/grande_agrandie')

    def toggle_full_screen(self) -> bool:
        from .tool_filters import toggle_full_screen
        return toggle_full_screen(self)

    def placed(self) -> None:
        """Un fichier vient d'être posé : la fenêtre se ferme si on l'a demandé."""
        if self.close_after.isChecked():
            self.close()

    def done(self, r) -> None:                                  # noqa: D401 — API Qt
        from .tool_filters import remember_large
        remember_large(self, self.settings, 'symboles/grande_agrandie')
        super().done(r)


class SymbolPanel(QWidget):
    insertRequested = Signal(str)
    saveRequested = Signal()                     # enregistrer la sélection sous… (fenêtre Enregistrer sous)
    addSelectionRequested = Signal(object)       # ajouter la sélection du dessin au dossier donné (None : affiché)
    printRequested = Signal(str)                 # « Imprimer… » : le dessin imprimé sans l'ouvrir
    bigRequested = Signal()                      # ouvrir la bibliothèque en grande fenêtre

    #: fichiers montrés ; réglages (favoris, dossiers, sous-dossiers) ; plus grande vignette
    EXTS = LIBRARY_EXT
    FAV = FAV_KEY
    ROOTS_KEY = 'symboles/dossiers'
    DEEP_KEY = 'symboles/sous_dossiers'
    SIZE_MAX = THUMB_MAX
    SEARCH_HINT = 'Rechercher (nom des fichiers, textes des symboles et des VND)…'
    SHOW_EXT = False                             # nom des fichiers avec son extension
    LOGOS_SHOWN = True                           # « Logos BAT » et « Favoris » internes : aussi les images (logos)

    def __init__(self, settings, parent=None, big: bool = False):
        super().__init__(parent)
        self.settings = settings
        self.big = big
        self._size_key = BIG_SIZE_KEY if big else SIZE_KEY
        try:
            size = int(float(settings.value(self._size_key, 160 if big else THUMB)))
        except (TypeError, ValueError):
            size = 160 if big else THUMB
        size = max(THUMB_MIN, min(self.SIZE_MAX, size))
        self.roots = self._initial_roots(settings)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr(self.SEARCH_HINT))
        self.search.returnPressed.connect(self._search)
        top.addWidget(self.search, 1)
        add = QPushButton('+')
        add.setToolTip(tr('Ajouter un dossier de symboles'))
        add.setFixedWidth(28)
        add.clicked.connect(self._add_root)
        top.addWidget(add)
        self.add_selection = QPushButton(tr('Ajouter la sélection'))
        self.add_selection.setToolTip(tr('La sélection du dessin enregistrée en symbole dans le dossier affiché '
                                         '(seul le nom est demandé)'))
        self.add_selection.clicked.connect(lambda: self.addSelectionRequested.emit(self.target_folder()))
        top.addWidget(self.add_selection)
        lay.addLayout(top)
        nav = QHBoxLayout()
        self.where = QLabel()
        self.where.setWordWrap(True)
        self.where.setStyleSheet('color: #868e96;')
        nav.addWidget(self.where, 1)
        self.deep = QCheckBox(tr('Sous-dossiers'))
        self.deep.setToolTip(tr('Montrer aussi les fichiers des sous-dossiers (sinon : les dossiers, puis les '
                                'fichiers du dossier, comme dans l\'explorateur)'))
        self.deep.setChecked(settings.value(self.DEEP_KEY, 'false') in (True, 'true'))
        self.deep.toggled.connect(self._deep_toggled)
        nav.addWidget(self.deep)
        lay.addLayout(nav)
        zoom = QHBoxLayout()
        self.size_label = QLabel(tr('Vignettes'))
        zoom.addWidget(self.size_label)
        self.size = QSlider(Qt.Orientation.Horizontal)
        self.size.setRange(THUMB_MIN, self.SIZE_MAX)
        self.size.setSingleStep(8)
        self.size.setPageStep(32)
        self.size.setValue(size)
        self.size.setToolTip(tr('Taille des vignettes (Ctrl + molette sur la liste)'))
        self.size.valueChanged.connect(self._size_changed)
        zoom.addWidget(self.size, 1)
        if not big:
            b = QPushButton(tr('Grande fenêtre'))
            b.setToolTip(tr('La bibliothèque dans une grande fenêtre : grandes vignettes, aperçu et fiche'))
            b.clicked.connect(self.bigRequested.emit)
            zoom.addWidget(b)
            self.big_button = b
        lay.addLayout(zoom)
        split = QSplitter(Qt.Orientation.Vertical)
        self.tree = FolderTree()
        self.tree.setHeaderHidden(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)   # suit la largeur du panneau
        self.tree.itemClicked.connect(self._folder_clicked)
        self.tree.itemExpanded.connect(self._expand)
        self.tree.filesDropped.connect(lambda files, folder, copy: self.place_files(files, folder, copy))
        self.tree.selectionDropped.connect(lambda folder: self.addSelectionRequested.emit(pathlib.Path(folder)))
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(lambda pos: self.menu(self.tree, pos))
        self.list = SymbolList(size)
        self.list.viewport().installEventFilter(self)
        self.list.selectionDropped.connect(lambda: self.addSelectionRequested.emit(self.target_folder()))
        self.list.verticalScrollBar().valueChanged.connect(self._scrolled)
        self.list.currentItemChanged.connect(lambda it, _p: self._preview_later())
        self.list.itemDoubleClicked.connect(self._activated)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(lambda pos: self.menu(self.list, pos))
        for keys, slot in (('F2', self.rename_selected), (QKeySequence.StandardKey.Delete, self.delete_selected),
                           ('Backspace', self.go_up), ('Return', self.open_selected)):
            for w in (self.list, self.tree):
                sc = QShortcut(QKeySequence(keys), w)
                sc.setContext(Qt.ShortcutContext.WidgetShortcut)
                sc.activated.connect(slot)
        # aperçu grand format et fiche du fichier choisi
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(120, 120)
        self.preview.setStyleSheet('background: white; border: 1px solid #ced4da;')
        self.file_info = QLabel()
        self.file_info.setWordWrap(True)
        self.file_info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        side = QWidget()
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.addWidget(self.preview, 1)
        sl.addWidget(self.file_info)
        if big:                                          # grande fenêtre : dossiers | vignettes | aperçu
            split.setOrientation(Qt.Orientation.Horizontal)
            split.addWidget(self.tree)
            split.addWidget(self.list)
            split.addWidget(side)
            split.setSizes([260, 900, 380])
        else:
            split.addWidget(self.tree)
            split.addWidget(self.list)
            split.addWidget(side)
            split.setSizes([160, 400, 170])
        lay.addWidget(split, 1)
        self._prev_timer = QTimer(self)
        self._prev_timer.setSingleShot(True)
        self._prev_timer.setInterval(120)
        self._prev_timer.timeout.connect(self.update_preview)
        self._pending: list[QListWidgetItem] = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._load_some)
        self._fill_tree()

    def _initial_roots(self, settings) -> list[pathlib.Path]:
        roots = settings.value(self.ROOTS_KEY, None)
        out = [pathlib.Path(r) for r in (roots or []) if r] or [r for r in default_roots() if r.is_dir()]
        lib = library_root()                       # la bibliothèque de l'atelier (B) toujours en tête
        if lib.is_dir() and all(r.resolve() != lib.resolve() for r in out if r.exists()):
            out.insert(0, lib)
        return out

    # --- dossiers -----------------------------------------------------------
    def _fill_tree(self) -> None:
        old = self._favorites_item()
        fav_open = old is not None and old.isExpanded()  # « Favoris » déplié le reste, l'arbre refait
        self.tree.clear()
        rec = QTreeWidgetItem(['★ ' + tr('Récents')])
        rec.setData(0, Qt.ItemDataRole.UserRole, RECENTS)
        rec.setToolTip(0, tr('Les derniers fichiers posés dans un dessin'))
        self.tree.addTopLevelItem(rec)
        fav = QTreeWidgetItem(['☆ ' + tr('Favoris')])
        fav.setData(0, Qt.ItemDataRole.UserRole, FAVORITES)
        fav.setToolTip(0, tr('Fichiers et dossiers retenus (clic droit › Ajouter aux favoris)'))
        self.tree.addTopLevelItem(fav)
        self._fill_favorites()
        fav.setExpanded(fav_open)
        for r in self.roots:
            it = QTreeWidgetItem([r.name or str(r)])
            it.setData(0, Qt.ItemDataRole.UserRole, str(r))
            it.setToolTip(0, str(r))
            self.tree.addTopLevelItem(it)
            self._add_placeholder(it, r)

    def _favorites_item(self):
        return next((self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())
                     if self.tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole) == FAVORITES), None)

    def _fill_favorites(self) -> None:
        """Les dossiers favoris sous « Favoris », chacun dépliable en arborescence (ses sous-dossiers lus au
        dépliage ; un partage n'est pas lu ici : hors d'atteinte, il ne fige rien). Les mêmes dossiers qu'avant :
        l'arbre reste tel quel (ce qui est déplié le reste)."""
        node = self._favorites_item()
        if node is None:
            return
        dirs = [str(p) for p in favorite_split(self.settings, self.FAV, type(self).EXTS)[0]]
        for k in reversed(range(node.childCount())):     # les absents retirés ; les autres restent (dépliés,
            if node.child(k).data(0, Qt.ItemDataRole.UserRole) not in dirs:      # ligne choisie gardée)
                node.takeChild(k)
        for k, d in enumerate(dirs):                     # les nouveaux insérés à leur rang (ordre d'ajout)
            if k < node.childCount() and node.child(k).data(0, Qt.ItemDataRole.UserRole) == d:
                continue
            p = pathlib.Path(d)
            ch = QTreeWidgetItem([p.name or d])
            ch.setData(0, Qt.ItemDataRole.UserRole, d)
            ch.setToolTip(0, d)
            node.insertChild(k, ch)
            self._add_placeholder(ch, p)

    def _is_file(self, p: pathlib.Path) -> bool:
        """`p` est-il un fichier ? Sur un partage : d'après son extension, sans le lire (hors d'atteinte, il figerait
        la fenêtre)."""
        if is_remote(p):
            return p.suffix.lower() in tuple(self.EXTS) + tuple(type(self).EXTS)
        return p.is_file()

    def _is_dir(self, p: pathlib.Path) -> bool:
        return not self._is_file(p) if is_remote(p) else p.is_dir()

    def _add_placeholder(self, it: QTreeWidgetItem, path: pathlib.Path) -> None:
        if is_remote(path):                              # un partage : pas lu ici (vu au dépliage)
            it.addChild(QTreeWidgetItem(['…']))
            return
        try:
            if any(p.is_dir() for p in path.iterdir()):
                it.addChild(QTreeWidgetItem(['…']))
        except OSError:
            pass

    def _subfolders(self, path: pathlib.Path) -> list:
        """Les sous-dossiers de `path`, par nom ; un partage : lus dans le fil de calcul (Annuler s'il tarde) ; un
        dossier disparu ou illisible (favori d'une clé débranchée) : aucun, sans erreur."""
        if is_remote(path):
            from .progress import Cancelled, run
            try:
                listed = run(self, tr('Lecture de {0}').format(path.name or str(path)), list_dir, path, ())
            except (Cancelled, Exception):               # noqa: BLE001 — partage absent : rien à déplier
                listed = None
            return list(listed[1]) if listed else []
        try:
            return sorted((p for p in path.iterdir() if p.is_dir()), key=lambda p: p.name.lower())
        except OSError:
            return []

    def _expand(self, it: QTreeWidgetItem) -> None:
        if it.childCount() == 1 and it.child(0).text(0) == '…':
            it.takeChild(0)
            path = pathlib.Path(it.data(0, Qt.ItemDataRole.UserRole))
            for d in self._subfolders(path):
                ch = QTreeWidgetItem([d.name])
                ch.setData(0, Qt.ItemDataRole.UserRole, str(d))
                it.addChild(ch)
                self._add_placeholder(ch, d)

    def open_library(self) -> None:
        """Bibliothèque de l'atelier ouverte : dossier déplié (ses
        sous-dossiers dans l'arbre), son contenu en vignettes."""
        lib = library_root()
        top = next((self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())
                    if pathlib.Path(self.tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole)) == lib), None)
        if top is None:
            top = next((self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())
                        if self.tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole) not in VIRTUAL), None)
        if top is None:
            return
        self.tree.setCurrentItem(top)
        top.setExpanded(True)
        self.show_folder(pathlib.Path(top.data(0, Qt.ItemDataRole.UserRole)))

    def _add_root(self) -> None:
        d = QFileDialog.getExistingDirectory(self, tr('Dossier de symboles'))
        if d:
            self.roots.append(pathlib.Path(d))
            self.settings.setValue(self.ROOTS_KEY, [str(r) for r in self.roots])
            self._fill_tree()

    def _folder_clicked(self, it: QTreeWidgetItem) -> None:
        if it.data(0, Qt.ItemDataRole.UserRole) == RECENTS:
            self.show_recents()
            return
        if it.data(0, Qt.ItemDataRole.UserRole) == FAVORITES:
            self.show_favorites()
            return
        self.show_folder(pathlib.Path(it.data(0, Qt.ItemDataRole.UserRole)))

    def show_favorites(self) -> None:
        """Les favoris : dossiers, puis fichiers."""
        self._folder = None
        self._unreadable = False
        self._recents_shown = False
        self._favs_shown = True
        dirs, files = favorite_split(self.settings, self.FAV, type(self).EXTS)     # (un partage : sans le lire)
        self._fill_favorites()                           # l'arbre suit (favori d'une autre fenêtre, dossier parti)
        self.show_files(files, {str(f): '' for f in files}, folders=dirs)
        self.where.setText(tr('Favoris') + f' ({len(dirs) + len(files)})')

    def show_recents(self) -> None:
        """Les derniers fichiers posés, le plus récent d'abord."""
        self._folder = None
        self._unreadable = False
        self._recents_shown = True
        self._favs_shown = False
        files = recent_files(self.settings)
        self.show_files(files, {str(f): '' for f in files})
        self.where.setText(tr('Récents') + f' ({len(files)})')

    #: au-delà, un dossier et ses sous-dossiers ne sont pas listés en entier
    MAX_LISTED = 4000

    def show_folder(self, path: pathlib.Path) -> None:
        """Le dossier comme dans l'explorateur : son dossier parent (..), ses
        sous-dossiers, puis ses fichiers ; « Sous-dossiers » coché : aussi les
        fichiers de ses sous-dossiers, à la suite."""
        exts = self._exts_of(path)
        if is_remote(path):                              # réseau : lu dans le fil de calcul (Annuler s'il tarde)
            from .progress import Cancelled, run
            try:
                listed = run(self, tr('Lecture de {0}').format(path.name or str(path)), list_dir, path, exts)
            except Cancelled:
                listed = None
            except Exception:                            # noqa: BLE001 — partage absent : dossier vide
                listed = None
        else:
            listed = list_dir(path, exts)
        if listed is None:
            self._folder = None                          # illisible : plus de dossier visé (ajouter la sélection),
            self._unreadable = True                      # pas même celui de l'arbre
            self.show_files([])
            return
        files, dirs, self._stats = listed
        direct = self.sorted_files(files)
        deeper, stopped = [], False
        if self.deep.isChecked():
            deeper, stopped = self._deeper_files(path, self.MAX_LISTED - len(direct))
        self._folder = path
        self._unreadable = False
        self._recents_shown = False
        self._favs_shown = False
        self.show_files(direct + deeper, folders=dirs, up=self._parent_in_library(path))
        self.where.setText(self._crumbs(path) + (' — ' + tr('sous-dossiers : lecture arrêtée ({0} fichiers)')
                                                 .format(len(deeper)) if stopped else ''))
        self.select_in_tree(path)

    def _deeper_files(self, path: pathlib.Path, limit: int):
        """(fichiers des sous-dossiers de `path`, lecture arrêtée ?) : lus dans le fil de calcul
        (barre d'avancement et Annuler au-delà d'un instant : un disque réseau ou un dossier de
        dizaines de milliers de fichiers ne fige plus la fenêtre) ; Annuler garde ce qui est lu."""
        from .progress import Cancelled, run
        found: list = []
        try:
            run(self, tr('Lecture des sous-dossiers de {0}').format(path.name or str(path)), walk_files,
                path, self._exts_of(path), None, max(0, limit), True, found, None, getattr(self, '_stats', None))
            stopped = False
        except Cancelled:
            stopped = True
        found.sort(key=lambda q: [x.lower() for x in q.relative_to(path).parts])
        return found, stopped

    def _exts_of(self, path) -> tuple:
        """Les fichiers montrés dans le dossier `path` : dans « Logos BAT » et « Favoris » de la bibliothèque
        interne, aussi les images et les autres dessins qui servent de logo."""
        if self.LOGOS_SHOWN and (is_below(path, logo_library()) or is_below(path, internal_favorites())):
            return tuple(self.EXTS) + tuple(e for e in logo_exts() if e not in self.EXTS)
        return tuple(self.EXTS)

    def sorted_files(self, files) -> list:
        """Fichiers dans l'ordre de la liste : symboles d'abord, puis par nom."""
        return sorted(files, key=lambda p: (p.suffix.lower() != '.smb', p.name.lower()))

    def _root_of(self, path: pathlib.Path) -> pathlib.Path | None:
        for r in self.roots:
            try:
                path.resolve().relative_to(r.resolve())
                return r
            except (ValueError, OSError):
                continue
        return None

    def _parent_in_library(self, path: pathlib.Path) -> pathlib.Path | None:
        r = self._root_of(path)
        return path.parent if r is not None and path.resolve() != r.resolve() else None

    def _crumbs(self, path: pathlib.Path) -> str:
        r = self._root_of(path)
        if r is None:
            return str(path)
        rel = path.resolve().relative_to(r.resolve()).parts
        return ' › '.join([r.name or str(r)] + list(rel))

    def _descend(self, it: QTreeWidgetItem, path) -> bool:
        """`path` choisi sous la ligne `it` de l'arbre, dépliée jusqu'à lui ; faux : il n'est pas dans son dossier
        (chemins comparés sans lire le disque)."""
        base = str(it.data(0, Qt.ItemDataRole.UserRole) or '')
        if not base or base.startswith('::'):
            return False
        try:
            parts = pathlib.Path(path).relative_to(base).parts
        except ValueError:
            return False
        for part in parts:
            it.setExpanded(True)
            self._expand(it)
            it = next((it.child(k) for k in range(it.childCount())
                       if it.child(k).text(0).lower() == part.lower()), None)
            if it is None:
                return True                              # (sous-dossier pas montré : la ligne choisie reste)
        self.tree.blockSignals(True)
        self.tree.setCurrentItem(it)
        self.tree.blockSignals(False)
        return True

    def select_in_tree(self, path: pathlib.Path) -> None:
        """Le dossier choisi dans l'arbre (ses parents dépliés) : dans la branche de la ligne déjà choisie s'il
        en vient (un dossier favori déplié sous « Favoris » y reste), sinon sous sa bibliothèque, sinon sous son
        dossier favori."""
        cur = self.tree.currentItem()
        if cur is not None and self._descend(cur, path):
            return
        r = self._root_of(path)
        if r is None:                                    # hors des bibliothèques : sous son dossier favori
            node = self._favorites_item()
            for k in range(node.childCount() if node is not None else 0):
                if self._descend(node.child(k), path):
                    node.setExpanded(True)
                    break
            return
        it = next((self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())
                   if pathlib.Path(self.tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole)) == r), None)
        for part in path.resolve().relative_to(r.resolve()).parts:
            if it is None:
                return
            it.setExpanded(True)
            self._expand(it)
            it = next((it.child(k) for k in range(it.childCount()) if it.child(k).text(0) == part), None)
        if it is not None:
            self.tree.blockSignals(True)
            self.tree.setCurrentItem(it)
            self.tree.blockSignals(False)

    def _size_changed(self, v: int) -> None:
        """Vignettes agrandies ou réduites : retracées à la nouvelle taille."""
        self.settings.setValue(self._size_key, int(v))
        self.list.set_thumb(int(v))
        if getattr(self, '_recents_shown', False):
            self.show_recents()
        elif getattr(self, '_favs_shown', False):
            self.show_favorites()
        elif getattr(self, '_folder', None) is not None and not self.search.text().strip():
            self.show_folder(self._folder)
        else:
            for i in range(self.list.count()):
                it = self.list.item(i)
                if it.data(ROLE_KIND) is None:
                    self._pending.append(it)
            self._timer.start(0)

    def eventFilter(self, obj, ev) -> bool:                          # noqa: N802 (API Qt)
        from PySide6.QtCore import QEvent
        if obj is self.list.viewport() and ev.type() == QEvent.Type.Wheel \
                and ev.modifiers() & Qt.KeyboardModifier.ControlModifier:
            step = 16 if ev.angleDelta().y() > 0 else -16
            self.size.setValue(self.size.value() + step)
            return True
        return super().eventFilter(obj, ev)

    def _preview_later(self) -> None:
        self._prev_timer.start()

    def update_preview(self) -> None:
        """Aperçu grand format et fiche du fichier choisi (dossier : son contenu)."""
        it = self.list.currentItem()
        if it is None:
            self.preview.clear()
            self.file_info.clear()
            return
        path = pathlib.Path(it.data(Qt.ItemDataRole.UserRole))
        if it.data(ROLE_KIND) in ('dir', 'up'):
            self.preview.setPixmap(it.icon().pixmap(64, 64))
            if is_remote(path):                          # un partage : son nom, sans compter son contenu
                self.file_info.setText(path.name or str(path))
                return
            try:
                n = sum(1 for p in path.iterdir() if p.suffix.lower() in self.EXTS)
                d = sum(1 for p in path.iterdir() if p.is_dir())
            except OSError:
                n = d = 0
            self.file_info.setText(f'{path.name}\n' + tr('{0} fichier(s), {1} dossier(s)').format(n, d))
            return
        side = max(120, min(self.preview.width(), self.preview.height()) - 8)
        if is_remote(path):                              # un partage : la date lue avec son dossier, sinon 0
            mtime = known_stat(getattr(self, '_stats', None), path)[0]
        else:
            try:
                mtime = path.stat().st_mtime
            except OSError:
                mtime = 0
        exact = _PREVIEWS.get((str(path), side, mtime))
        near = exact if exact is not None else _PREVIEWS.nearest(str(path), side, mtime)[0]
        if near is None and it.data(ROLE_KIND) is None and not it.icon().isNull() \
                and getattr(self, '_view', '') != 'details':      # Détails : l'icône n'est pas une vignette
            near = it.icon().pixmap(side, side).toImage()     # la vignette de la liste, en attendant
        if near is not None:
            self.preview.setPixmap(QPixmap.fromImage(near.scaled(
                side, side, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)))
        else:
            self.preview.clear()
        info = _INFOS.get((str(path), mtime))
        self.file_info.setText(info if info is not None else f'{path.name}\n…')
        if exact is not None and info is not None:
            return
        # grand aperçu et fiche dans un fil : un gros DXF (2 lectures de 3 s) ne fige plus la fenêtre
        from concurrent.futures import ThreadPoolExecutor
        if getattr(self, '_dpool', None) is None:
            self._dpool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='fiche')
            self._dtimer = QTimer(self)
            self._dtimer.setInterval(40)
            self._dtimer.timeout.connect(self._details_ready)
        self._dgen = getattr(self, '_dgen', 0) + 1
        self._djob = (self._dgen, path, side, mtime,
                      self._dpool.submit(_details, path, side, exact is None, info is None))
        self._dtimer.start()

    def _details_ready(self) -> None:
        job = getattr(self, '_djob', None)
        if job is None or not job[4].done():
            return
        self._dtimer.stop()
        self._djob = None
        gen, path, side, mtime, fut = job
        try:
            img, info = fut.result()
        except Exception:                                # noqa: BLE001 — fichier illisible : fiche d'erreur
            img, info = None, None
        if img is not None:
            _PREVIEWS[(str(path), side, mtime)] = img
        if info is not None:
            _INFOS[(str(path), mtime)] = info
        cur = self.list.currentItem()
        if gen != self._dgen or cur is None or pathlib.Path(cur.data(Qt.ItemDataRole.UserRole)) != path:
            return                                       # un autre fichier a été choisi entre-temps
        if img is not None:
            self.preview.setPixmap(QPixmap.fromImage(img))
        if info is not None:
            self.file_info.setText(info)

    def _deep_toggled(self, on: bool) -> None:
        self.settings.setValue(self.DEEP_KEY, bool(on))
        if getattr(self, '_folder', None) is not None:
            self.show_folder(self._folder)

    def _activated(self, it) -> None:
        kind = it.data(ROLE_KIND)
        if kind in ('dir', 'up'):
            self.show_folder(pathlib.Path(it.data(Qt.ItemDataRole.UserRole)))
        else:
            self.insertRequested.emit(it.data(Qt.ItemDataRole.UserRole))

    def open_selected(self) -> None:
        it = self.list.currentItem()
        if it is not None:
            self._activated(it)

    def go_up(self) -> None:
        up = self._parent_in_library(self._folder) if getattr(self, '_folder', None) else None
        if up is not None:
            self.show_folder(up)

    # --- gestion : dossiers et fichiers -------------------------------------------------------
    def refresh(self) -> None:
        """Arbre refait (dossiers créés, renommés, supprimés) et dossier relu."""
        folder = getattr(self, '_folder', None)
        self._fill_tree()
        if folder is not None:
            self.show_folder(folder if folder.is_dir() else (self._parent_in_library(folder) or self.roots[0]))

    def selected_paths(self, widget=None) -> list[pathlib.Path]:
        if widget is self.tree:
            it = self.tree.currentItem()
            return [pathlib.Path(it.data(0, Qt.ItemDataRole.UserRole))] if it is not None else []
        return [pathlib.Path(i.data(Qt.ItemDataRole.UserRole)) for i in self.list.selectedItems()
                if i.data(ROLE_KIND) != 'up']

    def new_folder(self, parent: pathlib.Path | None = None, name: str | None = None) -> pathlib.Path | None:
        parent = parent or getattr(self, '_folder', None) or self.current_folder()
        if parent is None:
            return None
        if name is None:
            name, ok = QInputDialog.getText(self, tr('Nouveau dossier'), tr('Nom du dossier :'))
            if not ok:
                return None
        name = str(name).strip().replace('/', '-').replace('\\', '-')
        if not name:
            return None
        d = parent / name
        try:
            d.mkdir(parents=False, exist_ok=True)
        except OSError as ex:
            QMessageBox.warning(self, tr('Bibliothèque'), str(ex))
            return None
        self.refresh()
        return d

    def rename(self, path: pathlib.Path, name: str | None = None) -> pathlib.Path | None:
        if any(path.resolve() == r.resolve() for r in self.roots if r.exists()):
            return None                                  # une bibliothèque elle-même : pas ici
        if name is None:
            name, ok = QInputDialog.getText(self, tr('Renommer'), tr('Nom :'),
                                            text=path.stem if path.is_file() else path.name)
            if not ok:
                return None
        name = str(name).strip().replace('/', '-').replace('\\', '-')
        if not name:
            return None
        dst = path.with_name(name + (path.suffix if path.is_file() and not pathlib.Path(name).suffix else ''))
        if dst.exists():
            QMessageBox.warning(self, tr('Bibliothèque'), tr('« {0} » existe déjà.').format(dst.name))
            return None
        try:
            path.rename(dst)
        except OSError as ex:
            QMessageBox.warning(self, tr('Bibliothèque'), str(ex))
            return None
        if getattr(self, '_folder', None) is not None and self._folder == path:
            self._folder = dst
        self.refresh()
        return dst

    def rename_selected(self) -> None:
        w = self.tree if self.tree.hasFocus() else self.list
        paths = self.selected_paths(w)
        if len(paths) == 1:
            self.rename(paths[0])

    def delete(self, paths: list[pathlib.Path], confirm: bool = True) -> int:
        """Fichiers et dossiers envoyés à la corbeille (après confirmation)."""
        paths = [p for p in paths if not any(p.resolve() == r.resolve() for r in self.roots if r.exists())]
        if not paths:
            return 0
        if confirm and QMessageBox.question(
                self, tr('Bibliothèque'), tr('Envoyer {0} élément(s) à la corbeille ?\n{1}').format(
                    len(paths), '\n'.join(p.name for p in paths[:8]))) != QMessageBox.StandardButton.Yes:
            return 0
        n = sum(1 for p in paths if to_trash(p))
        folder = getattr(self, '_folder', None)
        if folder is not None and not folder.exists():
            self._folder = self._parent_in_library(folder) or (self.roots[0] if self.roots else None)
        self.refresh()
        return n

    def delete_selected(self) -> None:
        self.delete(self.selected_paths(self.tree if self.tree.hasFocus() else self.list))

    def place_files(self, files, folder, copy: bool = False) -> int:
        """Fichiers rangés dans `folder` : déplacés depuis la bibliothèque,
        copiés depuis ailleurs (ou avec Ctrl)."""
        folder = pathlib.Path(folder)
        n = 0
        for f in files:
            src = pathlib.Path(f)
            if not src.exists() or src.parent.resolve() == folder.resolve():
                continue
            if src.is_dir() and (folder.resolve() == src.resolve() or src.resolve() in folder.resolve().parents):
                continue                                 # un dossier ne va pas dans lui-même
            try:
                move_into(src, folder, copy=copy or self._root_of(src) is None)
                n += 1
            except OSError as ex:
                QMessageBox.warning(self, tr('Bibliothèque'), str(ex))
        self.refresh()
        return n

    def import_files(self, folder: pathlib.Path | None = None, files=None) -> int:
        folder = folder or getattr(self, '_folder', None) or self.current_folder()
        if folder is None:
            return 0
        if files is None:
            files, _ = QFileDialog.getOpenFileNames(self, tr('Importer dans la bibliothèque'), '',
                                                    tr('Symboles et dessins (*.smb *.dxf *.vdz *.vnd *.svg)'))
        return self.place_files(files, folder, copy=True) if files else 0

    def move_to(self, paths: list[pathlib.Path]) -> int:
        roots = [r for r in self.roots if r.is_dir()]
        if not roots:
            return 0
        d = QFileDialog.getExistingDirectory(self, tr('Déplacer vers'), str(getattr(self, '_folder', roots[0])))
        return self.place_files([str(p) for p in paths], d) if d else 0

    def menu(self, widget, pos, exec_menu: bool = True):
        """Clic droit (arbre ou liste) : ouvrir, insérer, nouveau dossier,
        renommer, déplacer, corbeille, importer, enregistrer la sélection ici."""
        from PySide6.QtGui import QCursor
        if widget is self.tree:
            it = self.tree.itemAt(pos) if pos is not None else self.tree.currentItem()
            if it is not None:
                self.tree.setCurrentItem(it)
                if it.data(0, Qt.ItemDataRole.UserRole) in VIRTUAL:
                    self._folder_clicked(it)
                    return None
                self.show_folder(pathlib.Path(it.data(0, Qt.ItemDataRole.UserRole)))
        else:
            it = self.list.itemAt(pos) if pos is not None else None
            if it is not None and not it.isSelected():
                self.list.clearSelection()
                it.setSelected(True)
        paths = self.selected_paths(widget) if (widget is self.tree or self.list.selectedItems()) else []
        m = QMenu(self)
        files = [p for p in paths if self._is_file(p)]
        if widget is self.list and len(paths) == 1 and self._is_dir(paths[0]):
            m.addAction(tr('Ouvrir'), lambda: self.show_folder(paths[0]))
        if widget is self.list and files:
            m.addAction(tr('Insérer dans le dessin'), lambda: [self.insertRequested.emit(str(f)) for f in files])
        from .nc_preview import is_program
        if widget is self.list and len(files) == 1 and not is_program(files[0]):
            pa = m.addAction(tr('Imprimer…'), lambda: self.printRequested.emit(str(files[0])))
            pa.setToolTip(tr('Imprimer ce dessin à l\'échelle sans l\'ouvrir (F10 › Impression)'))
        m.addSeparator()
        m.addAction(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder), tr('Nouveau dossier…'),
                    lambda: self.new_folder(paths[0] if widget is self.tree and paths else None))
        if len(paths) == 1:
            m.addAction(tr('Renommer…'), lambda: self.rename(paths[0])).setShortcut(QKeySequence('F2'))
        if paths:
            m.addAction(tr('Déplacer vers…'), lambda: self.move_to(paths))
            m.addAction(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon), tr('Envoyer à la corbeille'),
                        lambda: self.delete(paths)).setShortcut(QKeySequence.StandardKey.Delete)
        m.addSeparator()
        if paths:
            fav = any(str(f).lower() == str(paths[0]).lower() for f in favorite_paths(self.settings, self.FAV))
            m.addAction('☆ ' + (tr('Retirer des favoris') if fav else tr('Ajouter aux favoris')),
                        lambda: self.toggle_favorites(paths))
        if files and not all(is_below(f, internal_favorites()) for f in files):
            m.addAction(tr('Copier dans la bibliothèque interne'), lambda: self.copy_to_library(files))
        m.addAction(tr('Importer des fichiers ici…'), lambda: self.import_files())
        here = paths[0] if len(paths) == 1 and self._is_dir(paths[0]) else self.target_folder()
        m.addAction(tr('Ajouter la sélection du dessin ici…'), lambda: self.addSelectionRequested.emit(here))
        m.addAction(tr('Enregistrer la sélection sous…'), self.saveRequested.emit)
        m.addAction(tr('Ouvrir dans l\'explorateur'), self.reveal)
        m.addAction(tr('Actualiser'), self.refresh)
        if exec_menu:
            m.exec(widget.viewport().mapToGlobal(pos) if pos is not None else QCursor.pos())
            m.deleteLater()
        return m

    def toggle_favorites(self, paths) -> None:
        added = {str(pathlib.Path(p)) for p in paths if toggle_favorite(self.settings, p, self.FAV)}
        self._fill_favorites()
        node = self._favorites_item()
        if node is not None and any(node.child(k).data(0, Qt.ItemDataRole.UserRole) in added
                                    for k in range(node.childCount())):
            node.setExpanded(True)                       # un dossier ajouté : montré sous « Favoris »
        if getattr(self, '_favs_shown', False):
            self.show_favorites()

    def copy_to_library(self, files) -> list:
        """Les fichiers copiés une fois dans le dossier « Favoris » de la bibliothèque interne : ils y restent même
        si l'original bouge ; même nom et même contenu déjà là : pas de doublon ; même nom, autre contenu : « nom
        (2) ». Rend les copies."""
        folder = internal_favorites()
        new_folder = not folder.is_dir()
        done, errors = [], []
        for f in files:
            try:
                kept = keep_copy(f, folder)
            except OSError as ex:
                errors.append(f'{pathlib.Path(f).name} : {ex}')
                if not folder.is_dir():                  # le dossier ne se crée pas : inutile d'insister
                    break
                continue
            if kept is not None:
                done.append(kept)
        if errors:                                       # une seule boîte pour toute la sélection
            QMessageBox.warning(self, tr('Bibliothèque'), '\n'.join(errors))
        shown = getattr(self, '_folder', None)
        if done and shown is not None and is_below(shown, folder):
            self.refresh()                               # (ce dossier est affiché : son contenu relu)
        elif done and new_folder:
            self._fill_tree()                            # le dossier neuf se voit dans l'arbre
            if shown is not None:
                self.select_in_tree(shown)
        self.where.setText(tr('{0} fichier(s) copié(s) dans la bibliothèque interne (dossier « Favoris »)')
                           .format(len(done)))
        return done

    def reveal(self) -> None:
        from PySide6.QtCore import QUrl as _U
        from PySide6.QtGui import QDesktopServices
        folder = getattr(self, '_folder', None) or self.current_folder()
        if folder is not None:
            QDesktopServices.openUrl(_U.fromLocalFile(str(folder)))

    def target_folder(self) -> pathlib.Path | None:
        """Où ajouter la sélection : le dossier affiché, sinon celui choisi dans l'arbre ; None : aucun dossier (les
        favoris, les récents)."""
        if getattr(self, '_favs_shown', False) or getattr(self, '_recents_shown', False) or \
                getattr(self, '_unreadable', False):
            return None
        shown = getattr(self, '_folder', None)
        if shown is not None:
            return pathlib.Path(shown)
        f = self.current_folder()
        return f if f is not None and str(f) not in VIRTUAL else None

    def select_file(self, path) -> bool:
        """Le fichier `path` choisi (et montré) dans la liste ; faux : absent."""
        want = str(pathlib.Path(path)).lower()
        for i in range(self.list.count()):
            it = self.list.item(i)
            if str(it.data(Qt.ItemDataRole.UserRole) or '').lower() == want:
                self.list.clearSelection()
                it.setSelected(True)
                self.list.setCurrentItem(it)
                self.list.scrollToItem(it)
                return True
        return False

    def current_folder(self) -> pathlib.Path | None:
        """Dossier choisi dans l'arbre, sinon la première bibliothèque."""
        it = self.tree.currentItem()
        if it is not None:
            return pathlib.Path(it.data(0, Qt.ItemDataRole.UserRole))
        return self.roots[0] if self.roots else None

    def _index(self):
        if getattr(self, '_text_index', None) is None:
            from ..core import fonts
            self._text_index = smb.TextIndex(fonts.cache_file().parent / 'symboles_textes.json')
        return self._text_index

    def _search(self) -> None:
        """Symboles dont le nom ou un texte (paragraphe, cote) contient la
        recherche, sans tenir compte de la casse ni des accents."""
        q = self.search.text().strip()
        if not q:
            return
        from .progress import Cancelled, run
        try:
            found = run(self, tr('Recherche de symboles'), smb.search, self.roots, q, self._index(), 400, self.EXTS)
        except Cancelled:
            return
        self.show_files([f for f, _t in found], {str(f): t for f, t in found if t})

    # --- vignettes ----------------------------------------------------------
    def show_files(self, files, hits: dict | None = None, folders=(), up=None) -> None:
        self._generation = getattr(self, '_generation', 0) + 1     # vignettes en cours : pour l'ancienne liste
        for job in getattr(self, '_jobs', None) or []:
            job[2].cancel()
        self._jobs = []
        self.list.clear()
        self._pending = []
        base = getattr(self, '_folder', None) if hits is None else None
        t = self.list.thumb

        def sized(sp):                                   # icône du système centrée dans une case de vignette
            from PySide6.QtGui import QPainter
            n = max(16, min(64, t // 2))
            pm = self.style().standardIcon(sp).pixmap(n, n)
            box = QPixmap(t, t)
            box.fill(Qt.GlobalColor.transparent)
            qp = QPainter(box)
            qp.drawPixmap((t - pm.width()) // 2, (t - pm.height()) // 2, pm)
            qp.end()
            return QIcon(box)
        dir_icon = sized(QStyle.StandardPixmap.SP_DirIcon)
        # case vide à la taille de la vignette : la ligne a d'emblée sa taille définitive (sinon la
        # vignette arrivée plus tard est dessinée dans la place du seul nom : tronquée au défilement)
        blank_pm = QPixmap(t, t)
        blank_pm.fill(Qt.GlobalColor.transparent)
        blank = QIcon(blank_pm)
        if up is not None:
            it = QListWidgetItem(sized(QStyle.StandardPixmap.SP_FileDialogToParent), '..')
            it.setData(Qt.ItemDataRole.UserRole, str(up))
            it.setData(ROLE_KIND, 'up')
            it.setToolTip(tr('Dossier parent (Retour arrière)'))
            self.list.addItem(it)
        for d in list(folders)[:self.MAX_LISTED]:
            it = QListWidgetItem(dir_icon, d.name)
            it.setData(Qt.ItemDataRole.UserRole, str(d))
            it.setData(ROLE_KIND, 'dir')
            it.setToolTip(str(d))
            self.list.addItem(it)
        for f in files:
            hit = (hits or {}).get(str(f), '')
            sub = ''
            if base is not None and f.parent != base:
                try:
                    sub = '/'.join(f.parent.relative_to(base).parts) + '\n'     # sous-dossier au-dessus du nom
                except ValueError:
                    sub = ''
            it = QListWidgetItem(blank, sub + (f.name if self.SHOW_EXT else f.stem)
                                 + (f'\n« {hit[:30]} »' if hit else ''))
            it.setData(Qt.ItemDataRole.UserRole, str(f))
            it.setToolTip(str(f) + (f'\n{hit}' if hit else ''))
            self.list.addItem(it)
            self._pending.append(it)
        self._timer.start(0)

    def _load_some(self) -> None:
        """Vignettes par petites tranches (40 ms au plus) : celles des
        symboles tout de suite (aperçu enregistré dans le fichier), celles
        des dessins (DXF, VDZ… à lire et tracer) dans un fil à part — un DXF
        lourd prend plus d'une seconde."""
        import time
        t0 = time.perf_counter()
        self._collect_previews()
        self._visible_first()
        while self._pending and time.perf_counter() - t0 < 0.04:
            if len(getattr(self, '_jobs', None) or []) >= self.queue_size():
                break                                    # file du fil de fond pleine : la suite attend
            it = self._pending.pop(0)
            try:
                f = pathlib.Path(it.data(Qt.ItemDataRole.UserRole))
                if f.suffix.lower() == '.smb' and self.list.thumb <= 96 and not is_remote(f):
                    dib = smb.thumbnail_dib(f.read_bytes())       # petite vignette : celle du fichier, instantanée
                    if dib:
                        self._set_icon(it, dib_to_qimage(dib))
                    else:
                        self._background_preview(it, f)
                else:
                    self._background_preview(it, f)               # grande : tracée à la taille voulue
            except OSError:
                pass
        if not self._pending and not getattr(self, '_jobs', None):
            self._timer.stop()
            if _PROC_POOL is not None:                   # plus rien à tracer : processus rendus après un temps
                QTimer.singleShot(int(PROC_IDLE_S * 1000) + 500, release_preview_processes)

    #: vignettes confiées au fil de fond à la fois (les autres attendent : celles de l'écran passent devant)
    QUEUE = 6

    def _visible_first(self) -> None:
        """Les lignes visibles passent en tête des vignettes à faire."""
        if len(self._pending) < 2:
            return
        vp = self.list.viewport().rect()
        seen, rest = [], []
        for it in self._pending:
            try:
                (seen if self.list.visualItemRect(it).intersects(vp) else rest).append(it)
            except RuntimeError:                         # ligne détruite (liste refaite)
                continue
        self._pending = seen + rest

    def _scrolled(self, *_a) -> None:
        if self._pending:
            self._timer.start(0)

    def _set_icon(self, it, img) -> None:
        if img is not None:
            t = self.list.thumb
            it.setIcon(QIcon(QPixmap.fromImage(img).scaled(
                t, t, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)))

    def _background_preview(self, it, f) -> None:
        from concurrent.futures import ThreadPoolExecutor
        if getattr(self, '_pool', None) is None:
            self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='vignettes')
            self._jobs = []
            self._times: list = []
        size = self.list.thumb
        if is_remote(f):                                 # un partage : lu par le fil des vignettes seulement
            key = (str(f), size, known_stat(getattr(self, '_stats', None), f)[0])
        else:
            try:
                key = (str(f), size, f.stat().st_mtime)
            except OSError:
                key = (str(f), size, 0)
        cached = _PREVIEWS.get(key)
        if cached is not None:
            self._set_icon(it, cached)
            return
        near, near_size = _PREVIEWS.nearest(key[0], size, key[2])
        if near is not None:                             # même fichier, autre taille : affichée tout de suite
            self._set_icon(it, near)
            if near_size >= size:                        # réduite d'une plus grande : pas besoin de retracer
                _PREVIEWS[key] = near.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                                             Qt.TransformationMode.SmoothTransformation)
                return
        if self.slow_previews():                         # gros dessins : plusieurs processus
            fut = preview_processes().submit(preview_png, str(f), size)
        else:
            fut = self._pool.submit(_timed_preview, f, size)
        self._jobs.append((it, key, fut, self._generation))

    def slow_previews(self) -> bool:
        """Vignettes lentes (moyenne des dernières au-delà de SLOW_PREVIEW_S) ?"""
        t = getattr(self, '_times', None) or []
        return len(t) >= 3 and sum(t[-8:]) / len(t[-8:]) > SLOW_PREVIEW_S

    def queue_size(self) -> int:
        """Vignettes confiées à la fois : QUEUE au fil, davantage aux processus."""
        if self.slow_previews():
            from ..core import workers
            return 2 * max(1, min(6, workers.process_limit()))
        return self.QUEUE

    def _collect_previews(self) -> None:
        jobs = getattr(self, '_jobs', None) or []
        keep = []
        for it, f, fut, gen in jobs:
            if not fut.done():
                keep.append((it, f, fut, gen))
                continue
            try:
                img, dt = fut.result()
                if isinstance(img, bytes):              # d'un processus : PNG
                    from PySide6.QtGui import QImage
                    img = QImage.fromData(img) if img else None
                self._times = (getattr(self, '_times', []) + [dt])[-32:]
            except Exception:                       # noqa: BLE001 — dessin illisible : pas de vignette
                img = None
            if img is not None:
                _PREVIEWS[f] = img                  # f : (chemin, taille, date) ; borné en mémoire
            if gen == self._generation:            # liste pas changée entre-temps
                self._set_icon(it, img)
        self._jobs = keep
