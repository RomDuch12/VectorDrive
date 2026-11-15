"""Reconnaissance de police : des lettres mises en courbes comparées aux polices du poste, les plus proches d'abord.

Les contours choisis sont regroupés en lettres (les trous, les points et les accents avec leur lettre ; un cadre autour
du texte, un soulignement ou un trait barrant plusieurs lettres sont écartés). Chaque lettre devient une petite image de
sa forme : sa boîte ramenée à une grille de `R` cases (proportions gardées), remplie (pair-impair pour la sélection,
non nul pour les polices, dont le sens des contours est sûr), un trait ouvert (police monotrait) tracé épais, puis
adoucie. Chaque police donne l'image de ses lettres et de ses chiffres (`CHARS`). Une police est d'autant plus proche que
chaque lettre choisie ressemble à une de ses lettres (écart quadratique moyen, les plus mauvaises lettres écartées : une
lettre mal découpée ne fausse pas tout). Deux polices au dessin identique ne prennent qu'une place.

Les images d'une police sont gardées sur le disque (`cache_dir`), refaites quand son fichier change (un fichier abîmé
est effacé et refait ; une police illisible sur le moment n'est pas gardée) : la première reconnaissance relève toutes
les polices (quelques dizaines de secondes pour quelques centaines de polices), les suivantes sont immédiates. Les
lettres sont attendues sur une ligne à peu près horizontale."""
from __future__ import annotations

import hashlib
import math
import os
import pathlib
import threading
import time

import numpy as np

#: côté de la grille d'une lettre (cases), échantillons par case et par axe
R = 24
SUB = 3
#: les caractères relevés dans chaque police (lettres, chiffres, quelques lettres accentuées)
CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789éèêàâçùô'
#: au plus tant de contours lus dans la sélection ; au plus tant de points pour l'image d'une lettre
MAX_CONTOURS = 3000
MAX_POINTS = 20000
#: version des images gardées sur le disque (à changer avec R, SUB, CHARS ou le dessin des images)
VERSION = 2
#: nombre de propositions d'office
DEFAULT_COUNT = 5
#: demi-épaisseur d'un trait ouvert (cases)
STROKE = 0.6
#: part des lettres gardées pour la note d'une police (les plus ressemblantes)
KEEP = 0.8
#: écart quadratique moyen qui vaut une proximité nulle
FAR = 0.35
#: un contour ouvert dont les bouts sont à moins de cette part de sa taille est fermé (polyligne sans drapeau)
CLOSE_GAP = 0.01

_MEM: dict = {}                                       # clé → (caractères, images uint8)
_MEM_LOCK = threading.Lock()
_PRUNED = False


# --- images ------------------------------------------------------------------------------------------------------
def _box(polys) -> tuple | None:
    pts = [p for p, _c in polys if len(p)]
    if not pts:
        return None
    a = np.concatenate(pts)
    return float(a[:, 0].min()), float(a[:, 1].min()), float(a[:, 0].max()), float(a[:, 1].max())


def _blur(a: np.ndarray) -> np.ndarray:
    p = np.pad(a, 1)
    a = (p[:-2, 1:-1] + 2 * p[1:-1, 1:-1] + p[2:, 1:-1]) / 4.0
    p = np.pad(a, ((0, 0), (1, 1)))
    return (p[:, :-2] + 2 * p[:, 1:-1] + p[:, 2:]) / 4.0


def _is_closed(pts: np.ndarray, closed: bool) -> bool:
    """Fermé, ou ouvert dont les bouts se touchent presque (une polyligne DXF sans drapeau de fermeture)."""
    if closed:
        return True
    pts = np.asarray(pts, float)
    if len(pts) < 4:
        return False
    size = float(max(np.ptp(pts[:, 0]), np.ptp(pts[:, 1])))
    return size > 0 and float(np.hypot(*(pts[0] - pts[-1]))) <= CLOSE_GAP * size


def image(polys, box=None, nonzero: bool = False) -> np.ndarray:
    """Image (R × R, 0…1) d'une lettre : `polys` [(points N × 2, fermé)], dans sa boîte ramenée à la grille (une case
    de marge, centrée, proportions gardées). Remplissage pair-impair, ou non nul (`nonzero`, glyphes des polices) ;
    un contour très détaillé est allégé (au plus `MAX_POINTS` points)."""
    box = box or _box(polys)
    out = np.zeros((R, R), np.float32)
    if box is None:
        return out
    x0, y0, x1, y1 = box
    s = max(x1 - x0, y1 - y0)
    if s <= 0:
        return out
    total = sum(len(p) for p, _c in polys)
    step = max(1, math.ceil(total / MAX_POINTS))
    if step > 1:
        polys = [(np.asarray(p)[::step] if len(p) > 3 * step else p, cl) for p, cl in polys]
    k = (R - 2) / s
    off = np.array([(R - (x1 - x0) * k) / 2 - x0 * k, (R - (y1 - y0) * k) / 2 - y0 * k])
    n = R * SUB
    c = (np.arange(n) + 0.5) / SUB                     # centres des échantillons, en cases
    full = np.zeros((n, n), bool)                      # [ligne y, colonne x]
    closed = [np.asarray(p, float) * k + off for p, cl in polys if cl and len(p) >= 3]
    if closed:
        a = np.concatenate(closed)
        b = np.concatenate([np.roll(q, -1, axis=0) for q in closed])
        xa, ya, xb, yb = a[:, 0], a[:, 1], b[:, 0], b[:, 1]
        ys = c[:, None]
        span = (ys >= np.minimum(ya, yb)) & (ys < np.maximum(ya, yb))
        with np.errstate(divide='ignore', invalid='ignore'):
            xc = np.where(span, xa + (ys - ya) / (yb - ya) * (xb - xa), np.inf)
        if nonzero:                                    # sens des arêtes : on compte les tours
            order = np.argsort(xc, axis=1)
            xs = np.take_along_axis(xc, order, 1)
            w = np.where(span, np.sign(yb - ya)[None, :], 0.0)
            cw = np.cumsum(np.take_along_axis(w, order, 1), axis=1)
            idx = np.stack([np.searchsorted(row, c) for row in xs])
            wind = np.where(idx > 0, np.take_along_axis(cw, np.maximum(idx - 1, 0), 1), 0.0)
            full |= wind != 0
        else:
            xc.sort(axis=1)
            cnt = np.stack([np.searchsorted(row, c) for row in xc])
            full |= (cnt % 2) == 1
    opened = [np.asarray(p, float) * k + off for p, cl in polys if not cl and len(p) >= 2]
    if opened:
        gx, gy = np.meshgrid(c, c)
        pts = np.stack([gx.ravel(), gy.ravel()], 1)
        hit = np.zeros(len(pts), bool)
        for q in opened:
            a, b = q[:-1], q[1:]
            d = b - a
            ll = (d * d).sum(1)
            for i in range(0, len(a), 64):
                aa, dd, l2 = a[i:i + 64], d[i:i + 64], ll[i:i + 64]
                rel = pts[:, None, :] - aa[None, :, :]
                with np.errstate(divide='ignore', invalid='ignore'):
                    t = np.clip(np.where(l2 > 0, (rel * dd).sum(2) / l2, 0.0), 0.0, 1.0)
                near = rel - t[:, :, None] * dd[None, :, :]
                hit |= ((near * near).sum(2) <= STROKE * STROKE).any(1)
        full |= hit.reshape(n, n)
    cov = full.reshape(R, SUB, R, SUB).mean(axis=(1, 3))
    return _blur(cov).astype(np.float32)


def _polys(path, tol: float) -> list:
    out = []
    for ct in path.contours:
        if not ct:
            continue
        pts = np.asarray(ct.flatten(tol), float)
        if len(pts) >= 2:
            out.append((pts, _is_closed(pts, bool(ct.closed))))
    return out


def path_image(path) -> np.ndarray | None:
    """Image d'une lettre d'une police (son tracé, rempli non nul), None si elle est vide."""
    try:
        bb = path.bbox() if path is not None else None
    except ValueError:                                 # contour vide
        bb = None
    if not bb:
        return None
    s = max(bb[2] - bb[0], bb[3] - bb[1])
    if s <= 0:
        return None
    polys = _polys(path, s / (R * SUB * 2))
    return image(polys, bb, nonzero=True) if polys else None


# --- lettres de la sélection ---------------------------------------------------------------------------------------
def _inside(pt, poly: np.ndarray) -> bool:
    """Le point dans le polygone (pair-impair)."""
    x, y = float(pt[0]), float(pt[1])
    xa, ya = poly[:, 0], poly[:, 1]
    xb, yb = np.roll(xa, -1), np.roll(ya, -1)
    span = (ya > y) != (yb > y)
    with np.errstate(divide='ignore', invalid='ignore'):
        xc = xa + (y - ya) / (yb - ya) * (xb - xa)
    return bool(np.count_nonzero(span & (xc > x)) % 2)


def _side_by_side(boxes) -> bool:
    """Au moins deux boîtes l'une à côté de l'autre (pas l'une au-dessus de l'autre) : des lettres d'un mot."""
    bs = sorted(boxes)
    for p, q in zip(bs, bs[1:]):
        ov = min(p[2], q[2]) - max(p[0], q[0])
        if ov <= 0.5 * min(p[2] - p[0], q[2] - q[0]):
            return True
    return False


def letters(paths) -> list[tuple[list, tuple]]:
    """Les contours de `paths` (coordonnées du dessin) regroupés en lettres, de gauche à droite : [(polys, boîte)].
    Un contour dans un autre (un trou) va avec lui ; un petit contour au-dessus ou au-dessous d'une lettre (point,
    accent, cédille) aussi ; les tout petits restes (ponctuation) sont écartés, comme un cadre qui entoure plusieurs
    lettres et un trait plat qui en barre ou souligne plusieurs."""
    contours = [ct for p in paths if p is not None for ct in p.contours if ct][:MAX_CONTOURS]
    boxes = []
    for ct in contours:
        try:
            boxes.append(ct.bbox())
        except ValueError:                             # contour vide
            boxes.append(None)
    keep = [i for i, b in enumerate(boxes) if b and max(b[2] - b[0], b[3] - b[1]) > 0]
    if not keep:
        return []
    size = {i: max(boxes[i][2] - boxes[i][0], boxes[i][3] - boxes[i][1]) for i in keep}
    flat: dict = {}

    def poly(i):
        if i not in flat:
            pts = np.asarray(contours[i].flatten(size[i] / (R * SUB * 2)), float)
            flat[i] = (pts, _is_closed(pts, bool(contours[i].closed)))
        return flat[i]

    # les trous : un contour dans la boîte d'un plus grand (à 2 % de sa taille près), et dans son tracé s'il est fermé
    B = np.array([boxes[i] for i in keep], float)
    S = np.array([size[i] for i in keep], float)
    eps = (0.02 * S)[:, None]
    area = (B[:, 2] - B[:, 0]) * (B[:, 3] - B[:, 1])
    inside = (B[None, :, 0] >= B[:, None, 0] - eps) & (B[None, :, 1] >= B[:, None, 1] - eps) \
        & (B[None, :, 2] <= B[:, None, 2] + eps) & (B[None, :, 3] <= B[:, None, 3] + eps) \
        & (area[None, :] < area[:, None])
    children: dict = {}
    for a, b in zip(*np.nonzero(inside)):
        outer, inner = keep[a], keep[b]
        pts, cl = poly(outer)
        if cl and len(pts) >= 3 and not _inside(poly(inner)[0][0], pts):
            continue                                   # dans la boîte, pas dans le contour
        children.setdefault(outer, set()).add(inner)
    frames = set()
    for outer, ch in children.items():                 # un cadre : il entoure des lettres côte à côte
        top = [b for b in ch if not any(b in children.get(o, ()) for o in ch if o != b)]
        if len(top) >= 2 and _side_by_side([boxes[b] for b in top]):
            frames.add(outer)
    keep = [i for i in keep if i not in frames]
    if not keep:
        return []
    parent = {i: i for i in keep}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        a, b = find(i), find(j)
        if a != b:
            parent[b] = a

    def gbox(members):
        bs = [boxes[m] for m in members]
        return min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)

    def groups_now():
        g = {}
        for i in keep:
            g.setdefault(find(i), []).append(i)
        return g

    for outer, ch in children.items():
        if outer not in frames:
            for inner in ch:
                if inner not in frames:
                    union(outer, inner)
    # un trait plat qui souligne, barre ou surligne plusieurs lettres côte à côte : écarté
    gs = groups_now()
    gb = {g: gbox(m) for g, m in gs.items()}
    bars = set()
    for g, b in gb.items():
        w, h = b[2] - b[0], b[3] - b[1]
        if w <= 3 * h:
            continue
        under = [o for o, ob in gb.items() if o != g and b[0] <= (ob[0] + ob[2]) / 2 <= b[2]
                 and ob[2] - ob[0] < 0.5 * w]
        if len(under) >= 2 and _side_by_side([gb[o] for o in under]):
            bars.add(g)
    if bars:
        keep = [i for i in keep if find(i) not in bars]
        if not keep:
            return []
    changed = True
    while changed:                                     # points, accents, cédilles, lettres en plusieurs morceaux
        changed = False
        groups = groups_now()
        gb = {g: gbox(m) for g, m in groups.items()}
        roots = sorted(gb, key=lambda g: gb[g][0])
        for x, a in enumerate(roots):
            ba = gb[a]
            for b in roots[x + 1:]:
                bb = gb[b]
                if bb[0] >= ba[2]:
                    break
                if find(a) == find(b):
                    continue
                wa, wb = ba[2] - ba[0], bb[2] - bb[0]
                ov = min(ba[2], bb[2]) - max(ba[0], bb[0])
                if ov <= 0.5 * min(wa, wb):
                    continue
                ha, hb = ba[3] - ba[1], bb[3] - bb[1]
                vgap = max(ba[1], bb[1]) - min(ba[3], bb[3])  # > 0 : l'un au-dessus de l'autre
                lo, hi = (wa, wb) if ha < hb else (wb, wa)    # largeurs du plus petit, du plus grand
                small = min(ha, hb) < 0.45 * max(ha, hb) and lo <= 1.3 * hi   # pas plus large que la lettre
                if vgap <= 0 or (small and vgap < 0.8 * max(ha, hb)):
                    union(a, b)
                    changed = True
    found = [(gbox(m), m) for m in groups_now().values()]
    hs = sorted(b[3] - b[1] for b, _m in found)
    med = hs[len(hs) // 2]
    out = []
    for b, members in sorted(found, key=lambda e: (e[0][0], e[0][1])):
        if b[3] - b[1] < 0.25 * med and len(found) > 1:  # ponctuation, tiret
            continue
        polys = [poly(m) for m in members if len(poly(m)[0]) >= 2]
        if polys:
            out.append((polys, b))
    return out


def selection_images(paths) -> np.ndarray:
    """Images des lettres de `paths` : tableau (lettres, R × R)."""
    ims = [image(p, b) for p, b in letters(paths)]
    return np.stack(ims).reshape(len(ims), -1) if ims else np.zeros((0, R * R), np.float32)


#: plus petite tache d'une image prise pour un morceau de lettre (pixels²)
MIN_BLOB = 6.0


def image_paths(gray: np.ndarray) -> list:
    """Les formes d'une image (niveaux de gris 0…1, lignes de haut en bas) en tracés, y vers le haut, un pixel pour
    une unité : ce qu'il faut à `letters` pour y trouver des lettres (capture d'écran d'un texte). Le fond est ce qui
    domine : une écriture claire sur fond sombre est reconnue aussi. Les taches de quelques pixels sont écartées ;
    au-delà de `MAX_CONTOURS` formes, les plus grandes sont gardées. ValueError (de `trace.trace_loops`) pour une
    image trop détaillée (photo, trame)."""
    from . import trace as T
    from .geom import Path, polyline
    if gray is None or gray.ndim != 2 or min(gray.shape) < 3:
        return []
    ink = gray < T.otsu(gray)
    if ink.mean() > 0.5:
        ink = ~ink
    h = gray.shape[0]
    loops = [lp for lp in T.trace_loops(ink) if abs(T._area(lp)) >= MIN_BLOB]
    if len(loops) > MAX_CONTOURS:                          # capture chargée : les plus grandes formes, pas le haut
        loops = sorted(loops, key=lambda lp: -abs(T._area(lp)))[:MAX_CONTOURS]
    contours = []
    for loop in loops:
        pts = T.simplify_loop(loop.astype(float), 0.6)
        if len(pts) >= 3:
            contours.append(polyline([(float(x), float(h - y)) for x, y in pts], closed=True))
    return [Path(contours)] if contours else []


# --- polices -------------------------------------------------------------------------------------------------------
def cache_dir() -> pathlib.Path:
    from . import fonts
    return fonts.cache_file().parent / 'formes_polices'


def _key(path: str, index: int) -> str:
    from .. import __version__
    from . import fontformats, fonts
    try:
        st = os.stat(path)
        stamp = f'{st.st_size}:{st.st_mtime_ns}'
    except OSError:
        stamp = f'vd{__version__}' if fonts.builtin(path) is not None else 'absent'
    fmt = fontformats.of(path)
    reader = f'|{fmt.reader}' if fmt is not None else ''  # lue par un plugin : son lecteur (mis à jour : refaite)
    raw = f'{VERSION}|{R}|{SUB}|{CHARS}|{os.path.normcase(os.path.abspath(path))}|{index}|{stamp}{reader}'
    return hashlib.sha1(raw.encode('utf-8')).hexdigest()


def _glyphs(path: str, index: int):
    """(caractère, tracé) des `CHARS` de la police — un fichier TrueType ou OpenType ouvert pour l'occasion (pas
    celui que garde `fonts.load` : l'affichage s'en sert en même temps) ; les autres lues sans passer par le cache
    d'affichage des lettres (`fonts.glyph`), qu'elles videraient."""
    from . import fontformats, fonts
    from .geom import Path
    if fonts.builtin(path) is not None or fontformats.of(path) is not None or fonts._is_svg(path):
        read = getattr(fonts.glyph, '__wrapped__', fonts.glyph)
        for ch in CHARS:
            try:
                yield ch, read(path, index, ch)[0]
            except Exception:                          # noqa: BLE001 — lettre illisible : sautée
                continue
        return
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    from fontTools.ttLib import TTFont
    f = TTFont(path, fontNumber=index, lazy=True)
    try:
        cmap = f.getBestCmap() or {}
        gs = f.getGlyphSet()
        for ch in CHARS:
            g = cmap.get(ord(ch))
            if g is None or g not in gs:
                continue
            try:
                rec = DecomposingRecordingPen(gs)
                gs[g].draw(rec)
                pen = fonts._Pen()
                for op, args in rec.value:
                    getattr(pen, op)(*args)
                pen._flush(False)
            except Exception:                          # noqa: BLE001
                continue
            yield ch, Path(pen.contours)
    finally:
        f.close()


def _prune(folder: pathlib.Path) -> None:
    """Une fois par séance : les fichiers temporaires restés d'une écriture interrompue (plus d'une heure) effacés."""
    global _PRUNED
    if _PRUNED:
        return
    _PRUNED = True
    try:
        old = time.time() - 3600
        for t in folder.glob('*.tmp.npz'):
            try:
                if t.stat().st_mtime < old:
                    t.unlink()
            except OSError:
                pass
    except OSError:
        pass


def _load(path: str, index: int = 0):
    """(caractères, images uint8 (n, R × R)) d'une police : en mémoire, sur le disque, sinon relevées ; None :
    illisible sur le moment (rien de gardé, elle sera relue la prochaine fois)."""
    key = _key(path, index)
    with _MEM_LOCK:
        got = _MEM.get(key)
    if got is not None:
        return got
    folder = cache_dir()
    _prune(folder)
    f = folder / (key + '.npz')
    got = None
    try:
        with np.load(f) as z:
            got = (str(z['chars']), np.asarray(z['im'], np.uint8).reshape(-1, R * R))
    except FileNotFoundError:
        pass
    except Exception:                                  # noqa: BLE001 — abîmé (coupure, disque plein) : refait
        try:
            f.unlink()
        except OSError:
            pass
    if got is None:
        chars, ims = [], []
        try:
            for ch, p in _glyphs(path, index):
                im = path_image(p)
                if im is not None:
                    chars.append(ch)
                    ims.append(np.round(im.ravel() * 255).astype(np.uint8))
        except Exception:                              # noqa: BLE001 — illisible (fichier tenu, réseau…) : pas gardé
            return None
        got = (''.join(chars), np.stack(ims) if ims else np.zeros((0, R * R), np.uint8))
        if chars:                                      # sans lettre (lecteur en défaut ?) : pas sur le disque
            tmp = f.with_name(f.stem + f'.{os.getpid()}.{threading.get_ident()}.tmp.npz')
            try:
                f.parent.mkdir(parents=True, exist_ok=True)
                np.savez_compressed(tmp, chars=np.array(got[0]), im=got[1])
                os.replace(tmp, f)
            except OSError:
                pass
            finally:
                try:
                    tmp.unlink()
                except OSError:
                    pass
    with _MEM_LOCK:
        _MEM[key] = got
    return got


def table(path: str, index: int = 0) -> tuple[str, np.ndarray] | None:
    """(caractères, images (n, R × R), 0…1) d'une police : en mémoire, sur le disque, sinon relevées (et gardées) ;
    None : police illisible ou sans lettre."""
    got = _load(path, index)
    if got is None or not len(got[0]):
        return None
    return got[0], got[1].astype(np.float32) / 255.0


def distance(sel: np.ndarray, ims: np.ndarray) -> float:
    """Écart quadratique moyen entre les lettres choisies `sel` et, pour chacune, la lettre la plus ressemblante de
    `ims` ; les `1 - KEEP` plus mauvaises écartées."""
    if not len(sel) or not len(ims):
        return math.inf
    d = (sel * sel).sum(1)[:, None] + (ims * ims).sum(1)[None, :] - 2.0 * sel @ ims.T
    best = np.sort(np.maximum(d.min(1), 0.0) / sel.shape[1])
    kept = best[:max(1, int(math.ceil(KEEP * len(best))))]
    return float(math.sqrt(kept.mean()))


def proximity(dist: float) -> float:
    """0…1 : 1 pour des lettres identiques."""
    return max(0.0, 1.0 - dist / FAR) if math.isfinite(dist) else 0.0


def candidates(names) -> list[tuple[str, str, int]]:
    """(nom, fichier, indice) des polices `names` présentes sur le poste, une fois par fichier."""
    from . import fonts
    out, seen = [], set()
    for n in names:
        if not fonts.is_available(n):
            continue
        ff = fonts.find_font(n)
        if not ff or (ff[0], ff[1]) in seen:
            continue
        seen.add((ff[0], ff[1]))
        out.append((n, ff[0], ff[1]))
    return out


def rank(paths, names, count: int = DEFAULT_COUNT, progress=None, cancel=None, sel=None) -> list[tuple[str, float]]:
    """Les `count` polices de `names` les plus proches des lettres de `paths` (ou de leurs images `sel`), la plus
    proche d'abord : [(nom, proximité 0…1)] ; deux polices au dessin identique : la première seule. `progress(fait,
    total)` après chaque police ; `cancel()` vrai : arrêt, rien de rendu. Une police illisible est sautée."""
    if sel is None:
        sel = selection_images(paths)
    if not len(sel):
        return []
    cands = candidates(names)
    scored, seen = [], set()
    for i, (name, path, index) in enumerate(cands):
        if cancel is not None and cancel():
            return []
        try:
            t = _load(path, index)
        except Exception:                              # noqa: BLE001 — police sautée
            t = None
        if t is not None and len(t[0]):
            mark = hashlib.sha1(t[0].encode('utf-8') + t[1].tobytes()).digest()
            if mark not in seen:
                seen.add(mark)
                scored.append((distance(sel, t[1].astype(np.float32) / 255.0), name))
        if progress is not None:
            progress(i + 1, len(cands))
    scored.sort(key=lambda e: (e[0], e[1].casefold()))
    return [(n, proximity(d)) for d, n in scored[:max(1, int(count))]]
