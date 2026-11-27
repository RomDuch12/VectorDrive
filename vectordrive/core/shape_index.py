"""Reconnaissance de dessins et de formes, entièrement réglable, et index des dossiers choisis (demande du 27/11 :
« New fonction reconnaissance dessin/forme user_full_parametrable : Indexage manuel de certains dossiers pour
accélérer par la suite. Assistant IA peut accèder à cet index. »).

La signature d'un dessin (ou d'une sélection) se calcule sur ses contours, courbes aplaties (`Contour.flatten`), les
trop petits écartés :
- la silhouette : le plus grand contour fermé (sinon le plus long ouvert), rééchantillonné à pas égal, centré, de
  norme 1 et tourné dans le sens trigonométrique ; deux silhouettes se comparent par la corrélation la meilleure sur
  tous les points de départ (transformée de Fourier), en complexe : la rotation se trouve d'elle-même ;
- les moments de ligne normalisés (ordre 2 et 3, tous les contours) : leurs invariants de Hu quand la rotation ne
  compte pas, le 7e en valeur absolue quand le miroir ne compte pas ;
- l'allongement (axes d'inertie, ou largeur / hauteur quand la rotation compte), le nombre de contours, le nombre de
  trous (contours fermés dans un nombre impair d'autres), le remplissage (aire pleine / aire de l'enveloppe convexe),
  la taille et la position (comptées seulement si l'échelle, la position comptent).

Chaque critère donne une ressemblance de 0 à 1 ; le score est leur moyenne pondérée (poids réglables), en %. Les
réglages de la ressemblance (`Match`) s'appliquent à l'index tel quel ; ceux de l'indexation (`Params` : taille
mini des contours, textes, finesse) changent les signatures : les fichiers sont relus à la mise à jour suivante.

L'index (JSON, dans le dossier des données comme celui des favoris) garde par fichier sa taille, sa date, sa
signature, ses dimensions, ses calques, ses textes et un petit croquis pour la liste : la recherche ne relit aucun
fichier. Sa mise à jour est lancée à la main, dans un fil de calcul (`IndexJob`, avancement et Annuler par
`core.progress`), incrémentale (taille et date de modification).

Sans Qt."""
from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import os
import pathlib
import threading
import time
import unicodedata

import numpy as np

from . import progress

VERSION = 1
#: le fichier de l'index, à côté de celui des favoris de la fenêtre Ouvrir
INDEX_FILE = 'formes_index.json'
#: formats proposés d'office (lus par le cœur sans autre logiciel) ; l'utilisateur en ajoute ou en retire
DEFAULT_EXTS = ('.vdz', '.vnd', '.vnl', '.vnm', '.gvt', '.dxf', '.svg', '.smb', '.plt', '.hpgl')
#: jamais indexés : lus par un autre logiciel (le lancer pour chaque fichier d'un dossier), ou des images
NEVER_KEYS = ('dwg', 'inkscape', 'catia', 'metafile', 'image')
#: les critères, dans l'ordre de la fenêtre
CRITERIA = ('contour', 'moments', 'aspect', 'count', 'holes', 'fill', 'size', 'position')
#: croquis de la liste : au plus tant de contours, de points par contour (coordonnées de 0 à 255)
SKETCH_CONTOURS = 12
SKETCH_POINTS = 48
#: textes retenus d'un dessin : au plus tant de caractères chacun, tous ensemble
TEXT_CHARS = 200
TEXTS_CHARS = 4000
#: pendant une mise à jour, l'index est enregistré toutes les tant de fiches lues, ou de secondes
SAVE_EVERY = 200
SAVE_SECONDS = 60.0
#: les fiches oubliées (« pierres tombales » datées, gardées dans le fichier) : une autre fenêtre ne les fait pas
#: revenir ; oubliées elles-mêmes après TOMB_DAYS jours, au plus MAX_TOMBS
TOMB_DAYS = 30
MAX_TOMBS = 20000
#: les calques retenus par fiche, et la longueur de leur nom
MAX_LAYERS = 50
LAYER_CHARS = 80


class Busy(RuntimeError):
    """Une mise à jour de l'index est déjà en cours (le message est dit, traduit, par l'interface)."""


@dataclasses.dataclass
class Params:
    """Réglages de l'indexation : ils changent les signatures (un changement : fichiers relus à la mise à jour)."""
    min_size: float = 0.5        # mm : un contour plus petit (diagonale de son encombrement) est ignoré
    min_rel: float = 1.0         # % de la taille du dessin : de même
    texts: bool = False          # les contours des textes comptés (leurs mots sont toujours retenus)
    hidden: bool = False         # les objets et calques masqués comptés
    points: int = 64             # points de la silhouette rééchantillonnée (finesse de la comparaison)
    precision: float = 0.2       # % de la taille du dessin : écart toléré à l'aplatissement des courbes
    max_contours: int = 400      # au plus tant de contours (les plus grands) pour les trous et le remplissage

    def clean(self) -> 'Params':
        p = dataclasses.replace(self)
        p.min_size = _clamp(p.min_size, 0.0, 1000.0, 0.5)
        p.min_rel = _clamp(p.min_rel, 0.0, 50.0, 1.0)
        p.texts, p.hidden = bool(p.texts), bool(p.hidden)
        p.points = int(_clamp(p.points, 16, 512, 64))
        p.precision = _clamp(p.precision, 0.01, 5.0, 0.2)
        p.max_contours = int(_clamp(p.max_contours, 10, 5000, 400))
        return p

    def digest(self) -> str:
        return hashlib.sha1(json.dumps(dataclasses.asdict(self.clean()), sort_keys=True).encode()).hexdigest()[:12]


@dataclasses.dataclass
class Match:
    """Réglages de la ressemblance : appliqués à l'index tel quel."""
    scale: bool = True           # vrai : la taille ne compte pas (agrandie, réduite : reconnue)
    rotation: bool = True        # vrai : l'orientation ne compte pas
    mirror: bool = True          # vrai : une forme retournée (miroir) est reconnue
    position: bool = True        # vrai : l'emplacement sur la plaque ne compte pas
    w_contour: float = 4.0       # poids de chaque critère (0 : ignoré)
    w_moments: float = 2.0
    w_aspect: float = 1.0
    w_count: float = 1.0
    w_holes: float = 1.0
    w_fill: float = 1.0
    w_size: float = 1.0          # compté seulement si la taille compte
    w_position: float = 1.0      # compté seulement si l'emplacement compte
    severity: float = 2.0        # exigence : chaque ressemblance élevée à cette puissance (1 : indulgent)
    threshold: float = 70.0      # % : en dessous, pas montré
    limit: int = 50              # résultats au plus

    def clean(self) -> 'Match':
        m = dataclasses.replace(self)
        for f in ('scale', 'rotation', 'mirror', 'position'):
            setattr(m, f, bool(getattr(m, f)))
        for c in CRITERIA:
            setattr(m, 'w_' + c, _clamp(getattr(m, 'w_' + c), 0.0, 100.0, 1.0))
        m.severity = _clamp(m.severity, 0.25, 10.0, 2.0)
        m.threshold = _clamp(m.threshold, 0.0, 100.0, 70.0)
        m.limit = int(_clamp(m.limit, 1, 10000, 50))
        return m

    def weight(self, c: str) -> float:
        if c == 'size' and self.scale or c == 'position' and self.position:
            return 0.0
        return float(getattr(self, 'w_' + c))


def _clamp(v, lo, hi, default):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return default
    if v != v:
        return default
    return min(hi, max(lo, v))


def from_dict(cls, d):
    """Un `Params` ou un `Match` d'un dictionnaire (réglages relus) : clés inconnues ignorées, valeurs bornées."""
    names = {f.name for f in dataclasses.fields(cls)}
    obj = cls(**{k: v for k, v in (d or {}).items() if k in names})
    return obj.clean()


def fold(text: str) -> str:
    """Sans casse ni accents (comparer des mots)."""
    t = unicodedata.normalize('NFKD', str(text or '')).casefold()
    return ''.join(c for c in t if not unicodedata.combining(c))


# --- les contours d'un dessin -----------------------------------------------------------------------------------
def leaves_of(items, hidden: bool = False) -> list:
    """Les objets feuilles de `items` (groupes dépliés) ; masqués omis sauf `hidden`."""
    from .document import Group
    out, stack = [], list(reversed(list(items)))
    while stack:
        it = stack.pop()
        if not hidden and not getattr(it, 'visible', True):
            continue
        if isinstance(it, Group):
            stack.extend(reversed(list(it.children)))
        else:
            out.append(it)
    return out


def doc_items(doc, hidden: bool = False) -> list:
    """Les objets de premier niveau du dessin (calques masqués omis sauf `hidden`)."""
    return [it for L in doc.layers if hidden or getattr(L, 'visible', True) for it in L.items]


def _paths_and_texts(items, params: Params):
    from .document import Image, Shape, Text
    paths, texts = [], []
    for it in leaves_of(items, params.hidden):
        if isinstance(it, Text):
            if str(it.text or '').strip():
                texts.append(str(it.text))
            if params.texts and it.outline:
                paths.append(it.outline)
        elif isinstance(it, Shape):
            paths.append(it.path)
        elif not isinstance(it, Image):
            p = getattr(it, 'path', None)
            if p is not None and hasattr(p, 'contours'):
                paths.append(p)
    return paths, texts


def polylines(items, params: Params):
    """([(points (k, 2), fermé)], textes) : les contours retenus de `items`, courbes aplaties."""
    paths, texts = _paths_and_texts(items, params)
    contours = [c for p in paths for c in p.contours if c.segments]
    boxes = []
    for c in contours:
        try:
            boxes.append(c.bbox())
        except (ValueError, TypeError):
            boxes.append(None)
    good = [b for b in boxes if b]
    if not good:
        return [], texts
    x0, y0 = min(b[0] for b in good), min(b[1] for b in good)
    x1, y1 = max(b[2] for b in good), max(b[3] for b in good)
    diag = math.hypot(x1 - x0, y1 - y0)
    if diag <= 1e-9:
        return [], texts
    tol = max(diag * params.precision / 100.0, 1e-5)
    smallest = max(params.min_size, diag * params.min_rel / 100.0)
    out = []
    for c, b in zip(contours, boxes):
        if not b or math.hypot(b[2] - b[0], b[3] - b[1]) < smallest:
            continue
        pts = np.asarray(c.flatten(tol), dtype=float)
        if len(pts) < 2 or not np.isfinite(pts).all():
            continue
        closed = bool(c.closed) or (len(pts) > 3 and np.hypot(*(pts[0] - pts[-1])) <= tol)
        if closed and np.hypot(*(pts[0] - pts[-1])) > 1e-12:
            pts = np.vstack([pts, pts[:1]])
        out.append((pts, closed))
    return out, texts


def _area(pts) -> float:
    x, y = pts[:, 0], pts[:, 1]
    return 0.5 * float(np.dot(x[:-1], y[1:]) - np.dot(x[1:], y[:-1]))


def _resample(pts, n: int, closed: bool):
    """`n` points à pas égal le long de la ligne (sans répéter le premier pour un contour fermé)."""
    d = np.hypot(*np.diff(pts, axis=0).T)
    s = np.concatenate([[0.0], np.cumsum(d)])
    total = s[-1]
    if total <= 1e-12:
        return np.repeat(pts[:1], n, axis=0)
    t = np.linspace(0.0, total, n, endpoint=not closed)
    return np.column_stack([np.interp(t, s, pts[:, 0]), np.interp(t, s, pts[:, 1])])


def _inside(pt, poly) -> bool:
    """Le point dans le polygone (règle pair-impair)."""
    x, y = pt
    xs, ys = poly[:-1, 0], poly[:-1, 1]
    xe, ye = poly[1:, 0], poly[1:, 1]
    cross = (ys > y) != (ye > y)
    with np.errstate(divide='ignore', invalid='ignore'):
        xi = xs + (y - ys) * (xe - xs) / (ye - ys)
    return bool(np.count_nonzero(cross & (x < xi)) % 2)


def _hull_area(pts) -> float:
    """Aire de l'enveloppe convexe (chaîne monotone)."""
    p = np.unique(np.round(pts, 9), axis=0)
    if len(p) < 3:
        return 0.0
    p = p[np.lexsort((p[:, 1], p[:, 0]))]

    def half(seq):
        h = []
        for q in seq:
            while len(h) >= 2 and ((h[-1][0] - h[-2][0]) * (q[1] - h[-2][1])
                                   - (h[-1][1] - h[-2][1]) * (q[0] - h[-2][0])) <= 0:
                h.pop()
            h.append(tuple(q))
        return h
    lower, upper = half(p), half(p[::-1])
    hull = np.asarray(lower[:-1] + upper[:-1] + lower[:1])
    return abs(_area(hull))


def signature(items, params: Params | None = None) -> dict | None:
    """La signature des objets `items` (dictionnaire JSON) ; None s'il n'y reste aucun contour."""
    params = (params or Params()).clean()
    return signature_of(polylines(items, params)[0], params)


def signature_of(lines, params: Params) -> dict | None:
    if not lines:
        return None
    allpts = np.vstack([p for p, _c in lines])
    x0, y0 = allpts.min(axis=0)
    x1, y1 = allpts.max(axis=0)
    w, h = float(x1 - x0), float(y1 - y0)
    # moments de ligne (densité uniforme le long des contours : ouverts et fermés de même), sur des points pris à
    # pas égal (8 fois ceux de la silhouette, répartis selon la longueur de chaque contour)
    lens = [float(np.hypot(*np.diff(p, axis=0).T).sum()) for p, _c in lines]
    length = float(sum(lens))
    if length <= 1e-12:
        return None
    mids, ws = [], []
    for (p, c), ln in zip(lines, lens):
        if ln <= 1e-12:
            continue
        k = max(4, int(round(8 * params.points * ln / length)))
        mids.append(_resample(p, k, c))
        ws.append(np.full(k, ln / k))
    mid, seg = np.vstack(mids), np.concatenate(ws)
    cx, cy = (mid * seg[:, None]).sum(axis=0) / length
    dx, dy = mid[:, 0] - cx, mid[:, 1] - cy

    def eta(p, q):
        return float((seg * dx ** p * dy ** q).sum() / length ** (p + q + 1))
    etas = [eta(2, 0), eta(1, 1), eta(0, 2), eta(3, 0), eta(2, 1), eta(1, 2), eta(0, 3)]
    # la silhouette : le plus grand contour fermé, sinon le plus long ouvert
    closed = [(abs(_area(p)), p) for p, c in lines if c and len(p) >= 4]
    if closed and max(closed, key=lambda t: t[0])[0] > 1e-12:
        main, main_closed = max(closed, key=lambda t: t[0])[1], True
    else:
        main, main_closed = max(lines, key=lambda t: float(np.hypot(*np.diff(t[0], axis=0).T).sum()))[0], False
    n = params.points
    r = _resample(main, n, main_closed)
    if main_closed and _area(np.vstack([r, r[:1]])) < 0:
        r = r[::-1]                                      # sens trigonométrique
    z = (r[:, 0] - r[:, 0].mean()) + 1j * (r[:, 1] - r[:, 1].mean())
    norm = float(np.sqrt((np.abs(z) ** 2).sum()))
    z = z / norm if norm > 1e-12 else z * 0
    # trous et remplissage : les plus grands contours fermés
    rings = sorted(((abs(_area(p)), p) for p, c in lines if c and len(p) >= 4), key=lambda t: -t[0])
    rings = [t for t in rings if t[0] > 1e-12][:params.max_contours]
    bx = np.array([(p[:, 0].min(), p[:, 1].min(), p[:, 0].max(), p[:, 1].max()) for _a, p in rings]).reshape(-1, 4)
    holes, filled = 0, 0.0
    for i, (ai, pi) in enumerate(rings):
        # seuls les plus grands, dont l'encombrement contient le sien, peuvent le contenir (tri par aire, filtre
        # des encombrements d'un seul coup : quelques milliers de contours restent rapides)
        b = bx[i]
        cand = np.nonzero((bx[:i, 0] <= b[0]) & (bx[:i, 1] <= b[1]) & (bx[:i, 2] >= b[2]) & (bx[:i, 3] >= b[3]))[0]
        depth = sum(1 for j in cand if _inside(pi[0], rings[j][1]))
        if depth % 2:
            holes += 1
            filled -= ai
        else:
            filled += ai
    hull = _hull_area(allpts)
    fill = max(0.0, min(1.0, filled / hull)) if hull > 1e-12 else 0.0
    m = np.array([[etas[0], etas[1]], [etas[1], etas[2]]])
    ev = np.linalg.eigvalsh(m)
    axes = float(math.sqrt(max(ev[0], 0.0) / ev[1])) if ev[1] > 1e-18 else 1.0
    return {'n': len(lines), 'open': sum(1 for _p, c in lines if not c), 'holes': holes,
            'bbox': [_r(x0), _r(y0), _r(x1), _r(y1)], 'w': _r(w), 'h': _r(h), 'size': _r(math.hypot(w, h)),
            'center': [_r(cx), _r(cy)], 'eta': [float(f'{e:.6g}') for e in etas], 'axes': round(axes, 5),
            'fill': round(fill, 5), 'closed': main_closed,
            'main': [round(float(v), 5) for v in np.column_stack([z.real, z.imag]).ravel()]}


def _r(v) -> float:
    return round(float(v), 4)


def sketch(lines, params: Params | None = None) -> list:
    """Petit croquis pour la liste des résultats : les plus grands contours, coordonnées entières de 0 à 255 dans
    le carré de l'encombrement (Y vers le haut)."""
    if not lines:
        return []
    allpts = np.vstack([p for p, _c in lines])
    lo = allpts.min(axis=0)
    span = float(max((allpts.max(axis=0) - lo).max(), 1e-9))
    big = sorted(lines, key=lambda t: -float(np.ptp(t[0], axis=0).sum()))[:SKETCH_CONTOURS]
    out = []
    for p, _c in big:
        k = max(1, int(math.ceil(len(p) / SKETCH_POINTS)))
        q = p[::k]
        if len(p) > 1 and k > 1:
            q = np.vstack([q, p[-1:]])
        out.append([int(v) for v in np.clip(np.round((q - lo) / span * 255), 0, 255).astype(int).ravel()])
    return out


# --- la ressemblance --------------------------------------------------------------------------------------------
def _z(sig) -> np.ndarray:
    v = np.asarray(sig.get('main') or [], dtype=float)
    return v[0::2] + 1j * v[1::2]


def _match_len(za, zb):
    if len(za) == len(zb) or not len(zb):
        return zb
    t = np.linspace(0, 1, len(za), endpoint=False)
    s = np.linspace(0, 1, len(zb), endpoint=False)
    zb = np.interp(t, s, zb.real) + 1j * np.interp(t, s, zb.imag)
    n = float(np.sqrt((np.abs(zb) ** 2).sum()))
    return zb / n if n > 1e-12 else zb


def _corr(za, zb, rotation: bool, cyclic: bool) -> float:
    """La meilleure corrélation des deux silhouettes (norme 1) : 1 si elles se superposent."""
    if cyclic:
        c = np.fft.ifft(np.fft.fft(za) * np.conj(np.fft.fft(zb)))
        vals = [c]
    else:                                                # ligne ouverte : ses deux sens
        vals = [np.array([np.vdot(zb, za)]), np.array([np.vdot(zb[::-1], za)])]
    best = max(float((np.abs(v) if rotation else v.real).max()) for v in vals)
    return max(0.0, min(1.0, best))


def contour_similarity(a: dict, b: dict, m: Match) -> float:
    za, zb = _z(a), _z(b)
    if not len(za) or not len(zb):
        return 0.0
    zb = _match_len(za, zb)
    cyclic = bool(a.get('closed')) and bool(b.get('closed'))
    cands = [zb]
    if m.mirror:                                         # retournée : de gauche à droite, de haut en bas
        cands += [np.conj(zb)[::-1], -np.conj(zb)[::-1]]
    best = max(_corr(za, c, m.rotation, cyclic) for c in cands)
    # la corrélation de deux formes quelconques reste haute (deux taches se ressemblent) : la distance de
    # Procuste (0 : la même ; √2 : opposées) ramenée de 0 à 1
    return max(0.0, 1.0 - math.sqrt(max(0.0, 2.0 - 2.0 * best)))


def _hu(e, mirror: bool) -> np.ndarray:
    n20, n11, n02, n30, n21, n12, n03 = e
    h1 = n20 + n02
    h2 = math.sqrt((n20 - n02) ** 2 + 4 * n11 ** 2)
    h3 = math.sqrt((n30 - 3 * n12) ** 2 + (3 * n21 - n03) ** 2)
    h4 = math.sqrt((n30 + n12) ** 2 + (n21 + n03) ** 2)
    h7 = ((3 * n21 - n03) * (n30 + n12) * ((n30 + n12) ** 2 - 3 * (n21 + n03) ** 2)
          - (n30 - 3 * n12) * (n21 + n03) * (3 * (n30 + n12) ** 2 - (n21 + n03) ** 2))
    h7 = math.copysign(abs(h7) ** 0.25, h7)              # (même degré que les autres)
    return np.array([h1, h2, h3, h4, abs(h7) if mirror else h7])


def _rel(fa, fb) -> float:
    """1 - |a - b| / (|a| + |b|) : 1 pour deux vecteurs égaux, 0 pour opposés."""
    den = float(np.linalg.norm(fa) + np.linalg.norm(fb))
    return 1.0 if den <= 1e-15 else max(0.0, 1.0 - float(np.linalg.norm(fa - fb)) / den)


def moments_similarity(a: dict, b: dict, m: Match) -> float:
    ea, eb = a.get('eta'), b.get('eta')
    if not ea or not eb or len(ea) != 7 or len(eb) != 7:
        return 0.0
    if m.rotation:
        return _rel(_hu(ea, m.mirror), _hu(eb, m.mirror))
    va, vb = np.asarray(ea), np.asarray(eb)
    # les moments d'ordre 3 au même degré que ceux d'ordre 2 (racine cubique gardant le signe)
    va, vb = np.cbrt(va), np.cbrt(vb)
    best = _rel(va, vb)
    if m.mirror:                                         # x → -x : p impair change de signe ; y → -y : q impair
        for flip in (np.r_[1, -1, 1, -1, 1, -1, 1], np.r_[1, -1, 1, 1, -1, 1, -1]):
            best = max(best, _rel(va, vb * flip))
    return best


def _ratio(x, y) -> float:
    x, y = abs(float(x)), abs(float(y))
    return 1.0 if max(x, y) <= 1e-12 else min(x, y) / max(x, y)


def similarities(a: dict, b: dict, m: Match) -> dict:
    """La ressemblance (0 à 1) de chaque critère compté."""
    out = {}
    if m.weight('contour'):
        out['contour'] = contour_similarity(a, b, m)
    if m.weight('moments'):
        out['moments'] = moments_similarity(a, b, m)
    if m.weight('aspect'):
        if m.rotation:
            out['aspect'] = _ratio(a.get('axes', 1), b.get('axes', 1))
        else:                                            # largeur / hauteur (le miroir n'y change rien)
            ra = float(a.get('w', 0)) / max(float(a.get('h', 0)), 1e-12)
            rb = float(b.get('w', 0)) / max(float(b.get('h', 0)), 1e-12)
            out['aspect'] = _ratio(math.atan(ra), math.atan(rb))
    if m.weight('count'):
        out['count'] = _ratio(a.get('n', 0), b.get('n', 0))
    if m.weight('holes'):
        out['holes'] = (min(a.get('holes', 0), b.get('holes', 0)) + 1) / (max(a.get('holes', 0), b.get('holes', 0)) + 1)
    if m.weight('fill'):
        out['fill'] = max(0.0, 1.0 - abs(float(a.get('fill', 0)) - float(b.get('fill', 0))))
    if m.weight('size'):
        if m.rotation:
            out['size'] = _ratio(a.get('size', 0), b.get('size', 0))
        else:
            out['size'] = (_ratio(a.get('w', 0), b.get('w', 0)) + _ratio(a.get('h', 0), b.get('h', 0))) / 2
    if m.weight('position'):
        ca, cb = a.get('center') or [0, 0], b.get('center') or [0, 0]
        d = math.hypot(ca[0] - cb[0], ca[1] - cb[1])
        out['position'] = max(0.0, 1.0 - d / max(float(a.get('size', 0)), float(b.get('size', 0)), 1e-9))
    return out


def score(a: dict, b: dict, m: Match | None = None) -> tuple[float, dict]:
    """(score en %, ressemblance de chaque critère) de la signature `b` à la signature cherchée `a`."""
    m = (m or Match()).clean()
    sims = similarities(a, b, m)
    total = sum(m.weight(c) for c in sims)
    if total <= 0:
        return 0.0, sims
    s = sum(m.weight(c) * (v ** m.severity) for c, v in sims.items()) / total
    return round(100.0 * s, 2), sims


# --- l'index ------------------------------------------------------------------------------------------------------
def key_of(path) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


def default_path() -> pathlib.Path:
    """Le fichier de l'index : à côté des autres caches (VECTORDRIVE_CACHE pour les essais)."""
    from .fonts import cache_file
    return cache_file().parent / INDEX_FILE


def norm_exts(exts) -> tuple:
    """Les extensions « .dxf » en minuscules, sans doublon ; jamais celles lues par un autre logiciel ni les images."""
    out = []
    for e in exts or ():
        e = str(e).strip().lower()
        if not e:
            continue
        e = e if e.startswith('.') else '.' + e
        if e not in out and readable(e):
            out.append(e)
    return tuple(out)


def readable(ext: str) -> bool:
    """Une extension que le cœur lit lui-même (pas par un autre logiciel), qui n'est pas une image."""
    from ..io import registry
    f = registry.by_extension('x' + ext)
    return f is not None and f.reader is not None and f.key not in NEVER_KEYS


def read_drawing(path):
    """Le dessin `path` lu comme à l'ouverture, sans ses plaques de reprise."""
    from ..io import companion
    return companion.open_document(str(path), plates=False)


def describe(doc, params: Params | None = None) -> dict:
    """Ce que l'index retient d'un dessin : signature, dimensions, contours, calques, textes, croquis."""
    params = (params or Params()).clean()
    items = doc_items(doc, params.hidden)
    lines, texts = polylines(items, params)
    sig = signature_of(lines, params)
    every = 0                                            # tous les contours, même petits ou masqués
    for it in leaves_of(items, True):
        p = getattr(it, 'path', None) or getattr(it, 'outline', None)
        every += len(getattr(p, 'contours', None) or ())
    bb = doc.bbox()
    return {'sig': sig, 'w': _r(bb[2] - bb[0]) if bb else 0.0, 'h': _r(bb[3] - bb[1]) if bb else 0.0,
            'contours': every, 'layers': clip_layers(doc.layers), 'texts': clip_texts(texts),
            'sketch': sketch(lines, params)}


def clip_layers(layers) -> list:
    """Les calques d'un dessin bornés : MAX_LAYERS au plus, noms à LAYER_CHARS caractères."""
    return [{'name': ' '.join(str(getattr(L, 'name', '')).split())[:LAYER_CHARS],
             'objects': len(getattr(L, 'items', ()) or ())} for L in list(layers or ())[:MAX_LAYERS]]


def clip_texts(texts, each: int | None = None, total: int | None = None) -> list:
    """Les textes d'un dessin bornés : chacun à `each` caractères (TEXT_CHARS), tous ensemble à `total`
    (TEXTS_CHARS) ; les blancs répétés réduits."""
    each = TEXT_CHARS if each is None else each
    total = TEXTS_CHARS if total is None else total
    out, used = [], 0
    for t in texts or ():
        t = ' '.join(str(t).split())[:each]
        if not t:
            continue
        if used + len(t) > total:
            break
        out.append(t)
        used += len(t)
    return out


def _valid(rec) -> bool:
    """Une fiche relue du disque de la bonne forme (sinon : écartée, le fichier sera relu)."""
    if not isinstance(rec, dict) or not isinstance(rec.get('path'), str) or not isinstance(rec.get('p'), str):
        return False
    if isinstance(rec.get('size'), bool) or not isinstance(rec.get('size'), int) \
            or not isinstance(rec.get('mtime'), (int, float)):
        return False
    for k in ('w', 'h'):
        if not isinstance(rec.get(k, 0), (int, float)):
            return False
    if not isinstance(rec.get('contours', 0), int) or not isinstance(rec.get('texts', []), list) \
            or not all(isinstance(t, str) for t in rec.get('texts', [])) or not isinstance(rec.get('sketch', []), list):
        return False
    if isinstance(rec.get('at', 0), bool) or not isinstance(rec.get('at', 0), (int, float)):
        return False
    layers = rec.get('layers', [])
    if not isinstance(layers, list) or len(layers) > MAX_LAYERS or not all(
            isinstance(L, dict) and isinstance(L.get('name'), str) and len(L['name']) <= LAYER_CHARS
            and isinstance(L.get('objects', 0), int) and not isinstance(L.get('objects', 0), bool) for L in layers):
        return False
    sig = rec.get('sig')
    if sig is None:
        return True
    if not isinstance(sig, dict):
        return False
    try:
        nums = [sig[k] for k in ('n', 'holes', 'w', 'h', 'size', 'axes', 'fill')]
        ok = all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in nums)
        ok = ok and isinstance(sig['eta'], list) and len(sig['eta']) == 7 and isinstance(sig['main'], list) \
            and len(sig['main']) >= 4 and len(sig['main']) % 2 == 0 and isinstance(sig['center'], list) \
            and len(sig['center']) == 2 and all(isinstance(v, (int, float)) for v in sig['eta'] + sig['main']
                                                + sig['center'])
    except (KeyError, TypeError):
        return False
    return bool(ok)


class ShapeIndex:
    """L'index, gardé dans `path` (JSON). `files` : clé du fichier → fiche (avec l'empreinte `p` des réglages de
    l'indexation : une fiche d'autres réglages est relue à la mise à jour suivante).

    Le verrou `lock` n'est tenu que le temps d'une courte lecture (copie des fiches) ou écriture (une fiche) : jamais
    pendant la lecture d'un fichier ; une recherche, un résumé restent instantanés pendant une mise à jour."""

    def __init__(self, path=None):
        self.path = pathlib.Path(path) if path is not None else default_path()
        self.files: dict = {}
        self.dirty = False
        self.lock = threading.RLock()
        #: une seule mise à jour à la fois
        self.updating = threading.Lock()
        #: la dernière écriture manquée ('' : aucune), dite à l'utilisateur
        self.error = ''
        self._disk = None                                # (taille, date) du fichier tel que lu ou écrit
        self._tombs: dict = {}                           # clé → date de l'oubli (gardées dans le fichier)
        self._saving = threading.Lock()                  # une écriture à la fois (hors du verrou des fiches)
        self.load()

    # --- le fichier ------------------------------------------------------------------------------------------
    def _stamp(self):
        try:
            st = os.stat(self.path)
        except OSError:
            return None
        return st.st_size, st.st_mtime_ns

    def _read_disk(self) -> tuple:
        """(fiches, pierres tombales) du fichier ; (None, {}) s'il manque ou ne se lit pas."""
        try:
            data = json.loads(self.path.read_text(encoding='utf-8', errors='surrogatepass'))
        except (OSError, ValueError):
            return None, {}
        if not (isinstance(data, dict) and data.get('version') == VERSION and isinstance(data.get('files'), dict)):
            return None, {}
        files = {k: v for k, v in data['files'].items() if isinstance(k, str) and _valid(v)}   # abîmées : écartées
        tombs = data.get('removed')
        tombs = {k: float(t) for k, t in tombs.items() if isinstance(k, str) and isinstance(t, (int, float))
                 and not isinstance(t, bool) and math.isfinite(t)} if isinstance(tombs, dict) else {}
        return files, tombs

    def load(self) -> None:
        files, tombs = self._read_disk()
        with self.lock:
            self.files = files or {}
            self._tombs = tombs
            self._disk = self._stamp()
            self.dirty = False

    def snapshot(self) -> dict:
        """Une copie des fiches (le temps de la copie seulement sous le verrou)."""
        with self.lock:
            return dict(self.files)

    def save(self) -> bool:
        """Réécrit l'index s'il a changé (remplacement atomique). Sous le verrou, seulement la copie des fiches : la
        relecture du fichier, la fusion et l'écriture se font hors du verrou (une recherche n'attend jamais). Si le
        fichier a changé sur le disque depuis (une autre fenêtre), ses fiches plus récentes sont reprises et ses
        oublis (pierres tombales datées) appliqués aux fiches lues avant : rien n'est écrasé à l'aveugle, rien
        d'oublié ne revient. Rend vrai s'il a été écrit ; un échec est retenu dans `error`."""
        with self._saving:
            with self.lock:
                if not self.dirty:
                    return False
                files, tombs, seen = dict(self.files), dict(self._tombs), self._disk
                self.dirty = False
            adds, drops = {}, {}
            if self._stamp() not in (None, seen):        # écrit ailleurs depuis notre dernière lecture/écriture
                other, otombs = self._read_disk()
                for k, t in otombs.items():
                    if t > tombs.get(k, -1.0):
                        tombs[k] = t
                for k, rec in (other or {}).items():
                    cur = files.get(k)
                    if _at(rec) > (-1.0 if cur is None else _at(cur)) and _at(rec) > tombs.get(k, -1.0):
                        files[k] = adds[k] = rec
                for k in [k for k in files if _at(files[k]) < tombs.get(k, -1.0)]:
                    drops[k] = tombs[k]                  # oubliée ailleurs après sa lecture ici
                    del files[k]
            tombs = _prune(tombs, files)
            tmp = self.path.with_suffix(f'{self.path.suffix}.{os.getpid()}.{threading.get_ident()}.tmp')
            try:
                text = json.dumps({'version': VERSION, 'files': files, 'removed': tombs}, ensure_ascii=False)
                self.path.parent.mkdir(parents=True, exist_ok=True)
                tmp.write_text(text, encoding='utf-8', errors='surrogatepass')
                st = os.stat(tmp)                        # le fichier qu'on écrit, pas celui d'un autre entre-temps
                os.replace(tmp, self.path)
            except (OSError, ValueError, TypeError) as ex:
                try:
                    tmp.unlink()
                except OSError:
                    pass
                with self.lock:
                    self.dirty = True                    # à réécrire la fois suivante
                    self.error = f'{type(ex).__name__} : {ex}'
                return False
            with self.lock:
                self._disk = (st.st_size, st.st_mtime_ns)
                for k, rec in adds.items():              # les fiches ont pu changer pendant l'écriture : fusion
                    cur = self.files.get(k)
                    if (cur is None or _at(cur) < _at(rec)) and self._tombs.get(k, -1.0) < _at(rec):
                        self.files[k] = rec
                for k, t in drops.items():
                    cur = self.files.get(k)
                    if cur is not None and _at(cur) < t:
                        del self.files[k]
                for k, t in tombs.items():
                    if t > self._tombs.get(k, -1.0):
                        self._tombs[k] = t
                self._tombs = _prune(self._tombs, self.files)
                self.error = ''
            return True

    # --- mise à jour ------------------------------------------------------------------------------------------
    def update(self, folders, exts=DEFAULT_EXTS, params: Params | None = None, reader=None, hidden=None) -> dict:
        """Les dossiers `folders` parcourus (sous-dossiers compris ; liens et jonctions jamais suivis) : chaque fichier
        d'une extension de `exts` neuf, changé (taille, date) ou indexé avec d'autres réglages est lu (`reader`,
        d'office `read_drawing`) ; les fiches des fichiers disparus et des dossiers retirés sont oubliées (pas celles
        d'un dossier injoignable ou momentanément illisible). Enregistré toutes les SAVE_EVERY fiches ou
        SAVE_SECONDS secondes, et à la fin, même après Annuler (core.progress : ce qui est lu est gardé). Rend les
        comptes : lus, gardés, oubliés, illisibles, annulé, injoignables, erreur d'écriture. `Busy` si une autre
        mise à jour est en cours."""
        from .fav_index import top_roots
        if not self.updating.acquire(blocking=False):
            raise Busy('update already running')
        try:
            params = (params or Params()).clean()
            reader = reader or read_drawing
            exts = tuple(e.lower() for e in exts)
            digest = params.digest()
            stats = {'lus': 0, 'gardes': 0, 'oublies': 0, 'illisibles': 0, 'fichiers': 0, 'annule': False,
                     'injoignables': [], 'erreur': ''}
            last, since = time.monotonic(), 0
            try:
                known = self.snapshot()
                todo, seen, unreadable = [], set(), []
                for root in top_roots(folders):
                    if not os.path.isdir(str(root)):
                        stats['injoignables'].append(str(root))
                        continue
                    for path, st in self._walk(str(root), exts, hidden, unreadable):
                        k = key_of(path)
                        seen.add(k)
                        rec = known.get(k)
                        if (rec is not None and rec.get('size') == st.st_size and rec.get('mtime') == st.st_mtime
                                and rec.get('p') == digest):
                            stats['gardes'] += 1
                        else:
                            todo.append((k, path, st))
                keep = [key_of(r) for r in stats['injoignables'] + unreadable]
                with self.lock:                          # disparus, ou hors des dossiers choisis
                    now = time.time()
                    for k in [k for k in self.files if k not in seen and not any(_under(k, g) for g in keep)]:
                        del self.files[k]
                        self._tombs[k] = now
                        stats['oublies'] += 1
                        self.dirty = True
                for i, (k, path, st) in enumerate(todo):
                    progress.check()
                    task = progress.current()
                    if task is not None:
                        task.report(i / max(1, len(todo)), f'{i + 1} / {len(todo)} : {os.path.basename(path)}')
                    rec = {'path': path, 'size': st.st_size, 'mtime': st.st_mtime, 'p': digest}
                    try:                                 # (hors du verrou : la lecture peut durer)
                        rec.update(describe(reader(path), params))
                    except progress.Cancelled:
                        raise
                    except Exception as ex:              # noqa: BLE001 — illisible : retenu, relu s'il change
                        rec.update({'sig': None, 'error': f'{type(ex).__name__} : {str(ex)[:160]}'})
                        stats['illisibles'] += 1
                    rec['at'] = time.time()              # date de la lecture : la plus récente gagne à la fusion
                    with self.lock:
                        self.files[k] = rec
                        self._tombs.pop(k, None)
                        self.dirty = True
                    stats['lus'] += 1
                    since += 1
                    if since >= SAVE_EVERY or time.monotonic() - last >= SAVE_SECONDS:
                        self.save()
                        since, last = 0, time.monotonic()
            except progress.Cancelled:
                stats['annule'] = True
            finally:
                self.save()
            stats['fichiers'] = len(self.snapshot())
            stats['erreur'] = self.error
            return stats
        finally:
            self.updating.release()

    @staticmethod
    def _walk(root: str, exts, hidden=None, unreadable=None):
        """(chemin, stat) des fichiers d'extension `exts` sous `root`, dans l'ordre des noms ; les dossiers qui ne se
        lisent pas (droits, réseau coupé en cours) vont dans `unreadable`."""
        from .fav_index import _reparse
        stack = [root]
        while stack:
            folder = stack.pop()
            progress.check()
            try:
                with os.scandir(folder) as sc:
                    entries = sorted(sc, key=lambda e: e.name.lower())
            except OSError:
                if unreadable is not None:
                    unreadable.append(folder)
                continue
            subs = []
            for e in entries:
                try:
                    if e.name.startswith(('.', '$')) or _reparse(e) or (hidden is not None and hidden(e)):
                        continue
                    if e.is_dir(follow_symlinks=False):
                        subs.append(e.path)
                    elif e.is_file(follow_symlinks=False) and os.path.splitext(e.name)[1].lower() in exts:
                        yield e.path, e.stat(follow_symlinks=False)
                except OSError:
                    continue
            stack.extend(reversed(subs))

    # --- recherche ------------------------------------------------------------------------------------------------
    def records(self, params: Params | None = None, folders=None) -> list:
        """Les fiches à jour (réglages `params`) qui ont une signature, des dossiers `folders` si donnés."""
        digest = (params or Params()).clean().digest()
        keys = [key_of(f) for f in folders] if folders is not None else None
        return [r for k, r in self.snapshot().items() if r.get('sig') and r.get('p') == digest
                and (keys is None or any(_under(k, f) for f in keys))]

    def stale(self, params: Params | None = None, folders=None) -> int:
        """Les fiches indexées avec d'autres réglages (relues à la prochaine mise à jour)."""
        digest = (params or Params()).clean().digest()
        keys = [key_of(f) for f in folders] if folders is not None else None
        return sum(1 for k, r in self.snapshot().items() if r.get('p') != digest
                   and (keys is None or any(_under(k, f) for f in keys)))

    def search(self, query: dict, match: Match | None = None, params: Params | None = None, folders=None,
               exclude=()) -> list:
        """[(score %, fiche, ressemblance par critère)] des dessins indexés (des dossiers `folders` si donnés) qui
        ressemblent à la signature `query`, du plus semblable au moins semblable, au moins au seuil, au plus
        `limit`. `exclude` : chemins écartés (le dessin lui-même)."""
        m = (match or Match()).clean()
        skip = {key_of(p) for p in exclude if p}
        out = []
        for rec in self.records(params, folders):
            if key_of(rec['path']) in skip:
                continue
            s, sims = score(query, rec['sig'], m)
            if s >= m.threshold:
                out.append((s, rec, sims))
        out.sort(key=lambda t: (-t[0], t[1]['path'].lower()))
        return out[:m.limit]

    def find(self, *, width=None, height=None, contours=None, text: str = '', name: str = '', folders=None,
             limit: int = 200) -> list:
        """Les fiches selon des critères : largeur, hauteur, nombre de contours ((mini, maxi), None : sans borne),
        un texte contenu (mots sans casse ni accents), un nom de fichier contenant `name`."""
        def ok(v, rng):
            if not rng:
                return True
            lo, hi = rng
            return (lo is None or v >= lo) and (hi is None or v <= hi)
        words = fold(text).split()
        nm = fold(name)
        keys = [key_of(f) for f in folders] if folders is not None else None
        out = []
        for k, r in self.snapshot().items():
            if 'error' in r or (keys is not None and not any(_under(k, f) for f in keys)):
                continue
            if not (ok(r.get('w', 0), width) and ok(r.get('h', 0), height) and ok(r.get('contours', 0), contours)):
                continue
            if words:
                hay = fold(' '.join(r.get('texts') or ()))
                if not all(w in hay for w in words):
                    continue
            if nm and nm not in fold(os.path.basename(r['path'])):
                continue
            out.append(r)
        out.sort(key=lambda r: r['path'].lower())
        return out[:limit]

    def summary(self, folders=None) -> dict:
        keys = [key_of(f) for f in folders] if folders is not None else None
        recs = [r for k, r in self.snapshot().items() if keys is None or any(_under(k, f) for f in keys)]
        return {'files': len(recs), 'drawings': sum(1 for r in recs if r.get('sig')),
                'unreadable': sum(1 for r in recs if 'error' in r)}


def _at(rec) -> float:
    """La date de lecture d'une fiche (0 : d'avant les dates)."""
    v = rec.get('at', 0) if isinstance(rec, dict) else 0
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else 0.0


def _prune(tombs: dict, files: dict) -> dict:
    """Les pierres tombales encore utiles : de moins de TOMB_DAYS jours, sans fiche relue depuis, MAX_TOMBS au plus
    (les plus récentes)."""
    old = time.time() - TOMB_DAYS * 86400
    out = {k: t for k, t in tombs.items() if t >= old and not (k in files and _at(files[k]) >= t)}
    if len(out) > MAX_TOMBS:
        out = dict(sorted(out.items(), key=lambda kv: -kv[1])[:MAX_TOMBS])
    return out


def _under(key: str, root_key: str) -> bool:
    return key == root_key or key.startswith(root_key.rstrip(os.sep) + os.sep)


_SHARED: dict = {}
_SHARED_LOCK = threading.Lock()


def shared(path=None) -> ShapeIndex:
    """L'index de `path` (d'office celui des données), un seul par fichier pour tout le programme."""
    p = pathlib.Path(path) if path is not None else default_path()
    k = key_of(p)
    with _SHARED_LOCK:
        idx = _SHARED.get(k)
        if idx is None:
            idx = _SHARED[k] = ShapeIndex(p)
        return idx


class IndexJob:
    """Une mise à jour de l'index dans un fil de calcul : `task` (avancement, Annuler), `result` (les comptes) ou
    `error` à la fin, `done`. L'interface la suit sans attendre (minuterie) : elle n'est jamais bloquée."""

    def __init__(self, index: ShapeIndex, folders, exts, params: Params, reader=None, hidden=None):
        self.index = index
        self.task = progress.Task('index')
        self.result: dict | None = None
        self.error: BaseException | None = None
        self.done = False
        self._args = (list(folders), tuple(exts), params, reader, hidden)
        self.thread = threading.Thread(target=self._work, name='vd-index-formes', daemon=True)

    def _work(self) -> None:
        token = progress.attach(self.task)
        try:
            self.result = self.index.update(*self._args)
        except BaseException as ex:                      # noqa: BLE001 — rendue à l'interface
            self.error = ex
        finally:
            progress.detach(token)
            self.done = True

    def start(self) -> 'IndexJob':
        self.thread.start()
        return self

    def cancel(self) -> None:
        self.task.cancel()

    @property
    def running(self) -> bool:
        return not self.done

    def wait(self, timeout: float | None = None) -> bool:
        self.thread.join(timeout)
        return self.done
