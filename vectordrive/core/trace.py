"""Vectorisation d'une image en noir et blanc (logo, tampon, signature) :
contours fermés autour des zones d'encre.

1. seuil (Otsu par défaut) → pixels d'encre ;
2. bords entre pixels d'encre et de fond suivis en boucles (encre à
   gauche en repère mathématique : extérieurs dans le sens direct, trous
   dans le sens horaire) ; deux pixels qui ne se touchent que par un coin
   restent séparés ;
3. escaliers remplacés par les milieux des pas, simplifiés (Douglas-
   Peucker), coins détectés à l'angle ;
4. entre deux coins : courbe de Catmull-Rom (Bézier cubiques) passant
   par les sommets, ou droites si le lissage est coupé.

Coordonnées rendues : repère de l'image (x vers la droite, y vers le
bas, 1 = un pixel, (0, 0) = coin haut gauche). Numpy seulement.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .geom import Contour, Cubic, Line


#: au-delà, l'image n'est pas un dessin au trait (photo, bruit) : refus
MAX_EDGES = 2_000_000


@dataclass
class TraceSpec:
    threshold: float = -1.0           # 0…1 ; < 0 : seuil d'Otsu
    invert: bool = False              # encre claire sur fond sombre
    speckle: float = 4.0              # aire minimale (pixels²) d'un contour gardé
    tolerance: float = 0.8            # écart de simplification (pixels)
    corner_angle: float = 60.0        # virage (°) au-delà duquel un sommet est un coin
    smooth: bool = True               # courbes entre les coins
    centerline: bool = False          # trait central (gravure en un passage) au lieu des contours
    min_length: float = 3.0           # trait central : barbules plus courtes ignorées (pixels)
    arcs: bool = False                # résultat en arcs de cercle et droites (TypeEdit : vectoriser en arcs
                                      # et segments) — mieux suivis par la machine que des Bézier
    segment: float = 0.0              # longueur des segments (pixels) entre les coins ; 0 : selon l'écart
    curvature: bool = False           # courbure continue : contour lissé (noyau gaussien, C∞) avant les courbes
    smoothing: float = 2.0            # courbure continue : force du lissage (pixels)
    colors: int = 1                   # couleurs cherchées ; 1 : noir et blanc (seuil)
    keep_background: bool = False     # couleurs : tracer aussi le fond

    @classmethod
    def from_dict(cls, d: dict) -> 'TraceSpec':
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def otsu(gray: np.ndarray) -> float:
    """Seuil d'Otsu d'une image en niveaux de gris 0…1."""
    hist, edges = np.histogram(gray, bins=256, range=(0.0, 1.0))
    p = hist.astype(float) / max(1, hist.sum())
    omega = np.cumsum(p)
    mu = np.cumsum(p * np.arange(256))
    mu_t = mu[-1]
    with np.errstate(divide='ignore', invalid='ignore'):
        sigma = (mu_t * omega - mu) ** 2 / (omega * (1 - omega))
    sigma[~np.isfinite(sigma)] = -1
    k = int(np.argmax(sigma))
    return float(edges[k + 1])


def binarize(gray: np.ndarray, spec: TraceSpec) -> np.ndarray:
    t = otsu(gray) if spec.threshold < 0 else spec.threshold
    ink = gray < t
    return ~ink if spec.invert else ink


def trace_loops(ink: np.ndarray) -> list[np.ndarray]:
    """Boucles de sommets du réseau des pixels (x, y entiers), encre à
    droite en repère image (donc à gauche une fois y retourné)."""
    H, W = ink.shape
    b = np.zeros((H + 2, W + 2), bool)
    b[1:-1, 1:-1] = ink
    A, B = b[:-1, :], b[1:, :]                       # au-dessus / au-dessous d'une ligne du réseau
    starts, ends = [], []
    r, c = np.nonzero(B & ~A)                        # encre dessous : vers +x
    starts.append(np.stack([c, r + 1], 1)); ends.append(np.stack([c + 1, r + 1], 1))
    r, c = np.nonzero(A & ~B)                        # encre dessus : vers −x
    starts.append(np.stack([c + 1, r + 1], 1)); ends.append(np.stack([c, r + 1], 1))
    L, R = b[:, :-1], b[:, 1:]                       # à gauche / à droite d'une colonne du réseau
    r, c = np.nonzero(L & ~R)                        # encre à gauche : vers +y
    starts.append(np.stack([c + 1, r], 1)); ends.append(np.stack([c + 1, r + 1], 1))
    r, c = np.nonzero(R & ~L)                        # encre à droite : vers −y
    starts.append(np.stack([c + 1, r + 1], 1)); ends.append(np.stack([c + 1, r], 1))
    S = np.concatenate(starts)
    E = np.concatenate(ends)
    n = len(S)
    if n > MAX_EDGES:
        raise ValueError(f'image trop détaillée ({n} bords de pixels) : photo ou trame ? '
                         'Essayer un autre seuil ou une image plus petite')
    if not n:
        return []
    key = S[:, 1].astype(np.int64) * (W + 3) + S[:, 0]
    endkey = E[:, 1].astype(np.int64) * (W + 3) + E[:, 0]
    order = np.argsort(key, kind='stable')
    skey = key[order]
    first = np.searchsorted(skey, endkey, 'left')
    last = np.searchsorted(skey, endkey, 'right')
    D = (E - S)
    used = np.zeros(n, bool)
    loops = []
    S_l, D_l = S.tolist(), D.tolist()
    order_l, first_l, last_l = order.tolist(), first.tolist(), last.tolist()
    for e0 in range(n):
        if used[e0]:
            continue
        pts = []
        e = e0
        while True:
            used[e] = True
            pts.append(S_l[e])
            lo, hi = first_l[e], last_l[e]
            if hi - lo == 1:
                nxt = order_l[lo]
            else:
                # sommet en selle : virage à droite (repère image), les
                # pixels qui se touchent par un coin restent séparés
                dx, dy = D_l[e]
                nxt = max((order_l[k] for k in range(lo, hi)),
                          key=lambda k2: dx * D_l[k2][1] - dy * D_l[k2][0])
            if used[nxt]:
                break
            e = nxt
        loops.append(np.asarray(pts, float) - 1.0)    # retrait de la bordure
    return loops


def _area(p: np.ndarray) -> float:
    x, y = p[:, 0], p[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def _rdp(p: np.ndarray, tol: float) -> list[int]:
    """Indices gardés par Douglas-Peucker sur une polyligne ouverte."""
    keep = [0, len(p) - 1]
    stack = [(0, len(p) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        a, b = p[i], p[j]
        seg = p[i + 1:j]
        ab = b - a
        L = math.hypot(*ab)
        if L < 1e-12:
            d = np.hypot(*(seg - a).T)
        else:
            d = np.abs(ab[0] * (seg[:, 1] - a[1]) - ab[1] * (seg[:, 0] - a[0])) / L
        k = int(np.argmax(d))
        if d[k] > tol:
            m = i + 1 + k
            keep.append(m)
            stack.append((i, m))
            stack.append((m, j))
    return sorted(set(keep))


def simplify_loop(loop: np.ndarray, tol: float) -> np.ndarray:
    """Milieux des pas de l'escalier, puis Douglas-Peucker sur la boucle
    (coupée en ses deux points les plus éloignés)."""
    mid = (loop + np.roll(loop, -1, axis=0)) / 2
    if len(mid) < 4:
        return mid
    i0 = 0
    i1 = int(np.argmax(np.hypot(*(mid - mid[0]).T)))
    if i1 == 0:
        return mid
    a = np.concatenate([mid[i0:i1 + 1]])
    b = np.concatenate([mid[i1:], mid[:1]])
    ka = _rdp(a, tol)
    kb = _rdp(b, tol)
    pts = [a[k] for k in ka[:-1]] + [b[k] for k in kb[:-1]]
    return np.asarray(pts)


def _corners(p: np.ndarray, angle: float) -> np.ndarray:
    v_in = p - np.roll(p, 1, axis=0)
    v_out = np.roll(p, -1, axis=0) - p
    n_in = np.hypot(*v_in.T)
    n_out = np.hypot(*v_out.T)
    cos = (v_in * v_out).sum(1) / np.maximum(n_in * n_out, 1e-12)
    turn = np.degrees(np.arccos(np.clip(cos, -1, 1)))
    return turn > angle


def to_contour(p: np.ndarray, spec: TraceSpec) -> Contour:
    n = len(p)
    pts = [tuple(map(float, q)) for q in p]
    if not spec.smooth or n < 3:
        return Contour([Line(pts[i], pts[(i + 1) % n]) for i in range(n)], True)
    corner = _corners(p, spec.corner_angle)
    segs = []
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        if corner[i] and corner[(i + 1) % n]:
            segs.append(Line(a, b))
            continue
        prev = pts[i - 1] if not corner[i] else a
        nxt = pts[(i + 2) % n] if not corner[(i + 1) % n] else b
        c1 = (a[0] + (b[0] - prev[0]) / 6, a[1] + (b[1] - prev[1]) / 6)
        c2 = (b[0] - (nxt[0] - a[0]) / 6, b[1] - (nxt[1] - a[1]) / 6)
        segs.append(Cubic(a, c1, c2, b))
    return Contour(segs, True)


def _gauss_closed(p: np.ndarray, sigma: float) -> np.ndarray:
    """Boucle lissée par un noyau gaussien (périodique) : courbe C∞, les
    marches de pixels effacées."""
    n = len(p)
    if sigma <= 0 or n < 5:
        return p
    r = int(min(n // 2 - 1, max(1, math.ceil(3 * sigma))))
    x = np.arange(-r, r + 1)
    k = np.exp(-x ** 2 / (2 * sigma ** 2))
    k /= k.sum()
    ext = np.vstack([p[-r:], p, p[:r]])
    return np.column_stack([np.convolve(ext[:, i], k, mode='valid') for i in range(2)])


def _gauss_open(p: np.ndarray, sigma: float) -> np.ndarray:
    """Même lissage sur un morceau entre deux coins (extrémités fixes)."""
    n = len(p)
    if sigma <= 0 or n < 5:
        return p
    r = int(min(n - 2, max(1, math.ceil(3 * sigma))))
    x = np.arange(-r, r + 1)
    k = np.exp(-x ** 2 / (2 * sigma ** 2))
    k /= k.sum()
    ext = np.vstack([2 * p[0] - p[r:0:-1], p, 2 * p[-1] - p[-2:-r - 2:-1]])     # reflet : tangente gardée
    out = np.column_stack([np.convolve(ext[:, i], k, mode='valid') for i in range(2)])
    out[0], out[-1] = p[0], p[-1]
    return out


def _resample(p: np.ndarray, step: float, closed: bool) -> np.ndarray:
    """Points tous les `step` environ (abscisse curviligne), extrémités gardées."""
    q = np.vstack([p, p[:1]]) if closed else p
    d = np.hypot(*np.diff(q, axis=0).T)
    s = np.concatenate([[0.0], np.cumsum(d)])
    total = s[-1]
    if total <= 0 or step <= 0:
        return p
    n = max(3 if closed else 1, int(round(total / step)))
    t = np.linspace(0.0, total, n + 1)
    if closed:
        t = t[:-1]
    return np.column_stack([np.interp(t, s, q[:, 0]), np.interp(t, s, q[:, 1])])


def _fair(loop: np.ndarray, p: np.ndarray, spec: TraceSpec) -> np.ndarray:
    """Sommets d'une boucle avec longueur de segments et courbure continue :
    entre les coins (pris sur la boucle simplifiée), contour lissé (si
    demandé) puis rééchantillonné ; les coins restent vifs."""
    step = spec.segment if spec.segment > 0 else max(2.0, 4 * spec.tolerance)
    sigma = max(0.0, spec.smoothing) if spec.curvature else 0.0
    corner = _corners(p, spec.corner_angle) if spec.corner_angle < 180 else np.zeros(len(p), bool)
    ci = np.flatnonzero(corner)
    if not sigma:                                      # sans lissage : la boucle simplifiée, rééchantillonnée
        if not len(ci):
            return _resample(p, step, True)
        out = []
        for a, b in zip(ci, list(ci[1:]) + [ci[0] + len(p)]):
            out.append(_resample(np.vstack([p, p])[a:b + 1], step, False)[:-1])
        return np.vstack(out)
    mid = (loop + np.roll(loop, -1, axis=0)) / 2
    if not len(ci):
        return _resample(_gauss_closed(mid, sigma), step, True)
    # coins reportés sur la boucle dense ; lissage entre eux, coins gardés vifs, à leur vraie place
    near = sorted({int(np.argmin(np.hypot(*(mid - p[i]).T))) for i in ci})
    at = {i: _sharp_point(mid, i) for i in near}
    out = []
    for a, b in zip(near, near[1:] + [near[0] + len(mid)]):
        part = _gauss_open(np.vstack([mid, mid])[a:b + 1], sigma)
        part[0], part[-1] = at[a], at[b % len(mid)]
        out.append(_resample(part, step, False)[:-1])
    return np.vstack(out)


def _sharp_point(mid: np.ndarray, i: int) -> np.ndarray:
    """Le coin que coupent les milieux des pas : là où se croisent les deux côtés qui y arrivent."""
    n = len(mid)
    k = min(6, n // 4)
    if k < 3:
        return mid[i]
    a0, a1 = mid[(i - k) % n], mid[(i - 1) % n]
    b0, b1 = mid[(i + 1) % n], mid[(i + k) % n]
    u, v = a1 - a0, b1 - b0
    cross = u[0] * v[1] - u[1] * v[0]
    if abs(cross) < 1e-6 * max(1e-9, np.hypot(*u) * np.hypot(*v)):
        return mid[i]
    t = ((b0[0] - a0[0]) * v[1] - (b0[1] - a0[1]) * v[0]) / cross
    x = a0 + u * t
    return x if np.hypot(*(x - mid[i])) <= 1.5 else mid[i]


def trace(gray: np.ndarray, spec: TraceSpec) -> list[Contour]:
    """Image en niveaux de gris (0 noir … 1 blanc, ligne 0 en haut) →
    contours fermés, repère de l'image."""
    return _trace_ink(binarize(np.asarray(gray, float), spec), spec)


def _trace_ink(ink: np.ndarray, spec: TraceSpec) -> list[Contour]:
    """Contours fermés autour des pixels d'encre."""
    out = []
    for loop in trace_loops(ink):
        if abs(_area(loop)) < spec.speckle:
            continue
        p = simplify_loop(loop, spec.tolerance)
        if (spec.segment > 0 or spec.curvature) and len(p) >= 3:
            p = _fair(loop, p, spec)
        if len(p) < 3:                                  # tache plus petite que l'écart : milieux des pas
            p = (loop + np.roll(loop, -1, axis=0)) / 2
        if len(p) >= 3:
            out.append(to_contour(p, spec))
    return out


# --- plusieurs couleurs ------------------------------------------------------------

#: Écart de couleur (Lab) en deçà duquel deux couleurs n'en font qu'une
SAME_COLOR = 8.0
#: Part de l'image en deçà de laquelle une couleur n'en est pas une (bruit, pixels isolés)
MIN_SHARE = 0.0005
#: Pixels analysés pour trouver les couleurs : le tirage reste rapide et ne change pas d'une fois sur l'autre
MAX_SAMPLES = 50_000
MAX_COLORS = 32
#: Écart admis (pixels) en réajustant un contour lissé en peu de courbes
FIT_TOL = 0.4


def to_lab(rgb: np.ndarray) -> np.ndarray:
    """RGB 0…1 → Lab : les écarts y comptent à peu près comme à l'œil."""
    c = np.asarray(rgb, float)
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    x = (c[..., 0] * 0.4124 + c[..., 1] * 0.3576 + c[..., 2] * 0.1805) / 0.95047
    y = c[..., 0] * 0.2126 + c[..., 1] * 0.7152 + c[..., 2] * 0.0722
    z = (c[..., 0] * 0.0193 + c[..., 1] * 0.1192 + c[..., 2] * 0.9505) / 1.08883

    def f(t):
        return np.where(t > 0.008856, np.cbrt(t), 7.787 * t + 16 / 116)
    fx, fy, fz = f(x), f(y), f(z)
    return np.stack((116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)), axis=-1)


def _kmeans(points: np.ndarray, n: int, iterations: int = 16) -> np.ndarray:
    """Centres de `n` groupes ; premier centre le plus fréquent, puis chaque fois le point le plus mal servi au hasard
    fixé : le même dessin donne les mêmes couleurs."""
    rng = np.random.default_rng(0)
    centers = [points[rng.integers(len(points))]]
    d2 = ((points - centers[0]) ** 2).sum(1)
    for _ in range(1, n):
        total = d2.sum()
        if total <= 1e-9:
            break
        centers.append(points[rng.choice(len(points), p=d2 / total)])
        d2 = np.minimum(d2, ((points - centers[-1]) ** 2).sum(1))
    c = np.array(centers)
    for _ in range(iterations):
        lab = ((points[:, None, :] - c[None, :, :]) ** 2).sum(2).argmin(1)
        moved = np.array([points[lab == k].mean(0) if (lab == k).any() else c[k] for k in range(len(c))])
        if np.abs(moved - c).max() < 0.05:
            c = moved
            break
        c = moved
    return c


def _nearest(lab: np.ndarray, centers: np.ndarray) -> np.ndarray:
    """Numéro du centre le plus proche de chaque pixel, par tranches : une grande image tient en mémoire."""
    shape = lab.shape[:-1]
    flat = lab.reshape(-1, 3)
    out = np.empty(len(flat), np.int32)
    for i in range(0, len(flat), 200_000):
        part = flat[i:i + 200_000]
        out[i:i + 200_000] = ((part[:, None, :] - centers[None, :, :]) ** 2).sum(2).argmin(1)
    return out.reshape(shape)


def _erode(mask: np.ndarray) -> np.ndarray:
    m = mask.copy()
    m[1:, :] &= mask[:-1, :]
    m[:-1, :] &= mask[1:, :]
    m[:, 1:] &= mask[:, :-1]
    m[:, :-1] &= mask[:, 1:]
    m[0, :] = m[-1, :] = m[:, 0] = m[:, -1] = False
    return m


def _is_halo(mask: np.ndarray, center: np.ndarray, others: np.ndarray) -> bool:
    """Couleur faite des seuls pixels adoucis du bord entre deux autres : partout très fine, et mélange de deux couleurs."""
    if len(others) < 2 or _erode(mask).sum() > 0.05 * max(1, mask.sum()):
        return False
    for i in range(len(others)):
        for j in range(i + 1, len(others)):
            ab = np.linalg.norm(others[i] - others[j])
            if np.linalg.norm(others[i] - center) + np.linalg.norm(center - others[j]) < ab + max(4.0, 0.1 * ab):
                return True
    return False


def find_colors(rgb: np.ndarray, n: int, mask: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """(centres Lab, numéro de couleur de chaque pixel ; -1 hors `mask`). Les couleurs presque égales sont réunies ; les
    couleurs de quelques pixels et les liserés adoucis entre deux couleurs sont rendus à leurs voisines."""
    lab = to_lab(np.asarray(rgb, float))
    H, W = lab.shape[:2]
    valid = lab.reshape(-1, 3) if mask is None else lab[mask]
    if len(valid) == 0:
        raise ValueError('image entièrement transparente')
    step = max(1, len(valid) // MAX_SAMPLES)
    centers = _kmeans(valid[::step].astype(float), max(1, min(int(n), MAX_COLORS)))
    # couleurs presque égales : une seule
    keep: list[np.ndarray] = []
    for c in centers:
        for k, o in enumerate(keep):
            if np.linalg.norm(o - c) < SAME_COLOR:
                keep[k] = (o + c) / 2
                break
        else:
            keep.append(c)
    centers = np.array(keep)
    while True:
        labels = _nearest(lab, centers)
        if mask is not None:
            labels = np.where(mask, labels, -1)
        total = (labels >= 0).sum()
        share = [(labels == k).sum() / total for k in range(len(centers))]
        drop = next((k for k in np.argsort(share) if len(centers) > 1 and share[k] < MIN_SHARE), None)
        if drop is None:
            drop = next((k for k in np.argsort(share) if len(centers) > 2 and _is_halo(
                labels == k, centers[k], np.delete(centers, k, axis=0))), None)
        if drop is None:
            return centers, labels
        centers = np.delete(centers, drop, axis=0)


def background_of(labels: np.ndarray) -> int:
    """La couleur du fond : celle qui borde le plus l'image. -1 si le fond est transparent."""
    edge = np.concatenate((labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1]))
    if (edge < 0).mean() > 0.5:
        return -1
    known = edge[edge >= 0]
    return int(np.bincount(known).argmax()) if len(known) else -1


def _hex(rgb) -> str:
    return '#' + ''.join(f'{int(round(float(np.clip(v, 0, 1)) * 255)):02x}' for v in rgb)


def trace_colors(rgb: np.ndarray, spec: TraceSpec, mask: np.ndarray | None = None) -> list[tuple[str, list[Contour]]]:
    """Image RGB (0…1, ligne 0 en haut) → [(couleur '#rrggbb', contours fermés)], du plus grand au plus petit, repère de
    l'image. `mask` : pixels réels de l'image (faux : transparent). Le fond n'est tracé que si on le demande."""
    import dataclasses

    from . import fitcurve, progress
    rgb = np.asarray(rgb, float)
    centers, labels = find_colors(rgb, spec.colors, mask)
    spec = dataclasses.replace(spec, curvature=True)      # un logo : des courbes franches, pas de facettes
    bg = -1 if spec.keep_background else background_of(labels)
    out = []
    for k in range(len(centers)):
        progress.check()
        if k == bg:
            continue
        ink = labels == k
        contours = [fitcurve.approximate_contour(c, FIT_TOL, corner=spec.corner_angle * 0.6) for c in _trace_ink(ink, spec)]
        if contours:
            out.append((int(ink.sum()), _hex(np.median(rgb[ink], axis=0)), contours))
    out.sort(key=lambda t: -t[0])
    return [(col, cs) for _n, col, cs in out]


# --- trait central (gravure en un passage) -----------------------------------------

def thin(ink: np.ndarray) -> np.ndarray:
    """Squelette d'un dessin au trait (amincissement de Zhang et Suen)."""
    img = np.zeros((ink.shape[0] + 2, ink.shape[1] + 2), np.uint8)
    img[1:-1, 1:-1] = ink
    while True:
        changed = False
        for step in (0, 1):
            P = img
            p2, p3, p4 = P[:-2, 1:-1], P[:-2, 2:], P[1:-1, 2:]
            p5, p6, p7 = P[2:, 2:], P[2:, 1:-1], P[2:, :-2]
            p8, p9 = P[1:-1, :-2], P[:-2, :-2]
            seq = [p2, p3, p4, p5, p6, p7, p8, p9, p2]
            B = p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9
            A = sum(((seq[k] == 0) & (seq[k + 1] == 1)).astype(np.uint8) for k in range(8))
            if step == 0:
                c = (p2 * p4 * p6 == 0) & (p4 * p6 * p8 == 0)
            else:
                c = (p2 * p4 * p8 == 0) & (p2 * p6 * p8 == 0)
            kill = (P[1:-1, 1:-1] == 1) & (B >= 2) & (B <= 6) & (A == 1) & c
            if kill.any():
                img[1:-1, 1:-1][kill] = 0
                changed = True
        if not changed:
            return img[1:-1, 1:-1].astype(bool)


_ORTHO = ((1, 0), (-1, 0), (0, 1), (0, -1))
_DIAG = ((1, 1), (1, -1), (-1, 1), (-1, -1))


def _neighbours(sk: np.ndarray, x: int, y: int) -> list[tuple[int, int]]:
    """Voisins utiles : les 4 directs, et un voisin en diagonale seulement
    s'il n'est pas déjà rejoint par un voisin direct (pas de triangles)."""
    H, W = sk.shape
    out = []
    for dx, dy in _ORTHO:
        u, v = x + dx, y + dy
        if 0 <= u < W and 0 <= v < H and sk[v, u]:
            out.append((u, v))
    for dx, dy in _DIAG:
        u, v = x + dx, y + dy
        if 0 <= u < W and 0 <= v < H and sk[v, u] and not sk[y, u] and not sk[v, x]:
            out.append((u, v))
    return out


def skeleton_paths(sk: np.ndarray, min_length: float = 3.0) -> list[tuple[np.ndarray, bool]]:
    """Polylignes (centres de pixels) du squelette, coupées aux extrémités
    et aux embranchements : [(points, fermée)]. Les branches libres plus
    courtes que `min_length` pixels (barbules) sont retirées."""
    ys, xs = np.nonzero(sk)
    nb = {(x, y): _neighbours(sk, x, y) for x, y in zip(xs.tolist(), ys.tolist())}
    nodes = {p for p, n in nb.items() if len(n) != 2}
    seen: set[tuple] = set()
    paths = []

    def walk(a, b):
        pts = [a, b]
        seen.add((a, b)); seen.add((b, a))
        prev, cur = a, b
        while cur not in nodes:
            nxt = [q for q in nb[cur] if q != prev and (cur, q) not in seen]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            seen.add((prev, cur)); seen.add((cur, prev))
            pts.append(cur)
            if cur == a:
                break
        return pts

    for a in sorted(nodes):
        for b in nb[a]:
            if (a, b) not in seen:
                pts = walk(a, b)
                free = len(nb[pts[0]]) == 1 or len(nb[pts[-1]]) == 1
                length = sum(math.hypot(p[0] - q[0], p[1] - q[1]) for p, q in zip(pts, pts[1:]))
                if free and length < min_length and not (len(nb[pts[0]]) == 1 and len(nb[pts[-1]]) == 1
                                                        and length >= 1):
                    continue
                paths.append((np.asarray(pts, float) + 0.5, False))
    for a in sorted(nb):                                # boucles sans nœud (cercles…)
        for b in nb[a]:
            if (a, b) not in seen:
                pts = walk(a, b)
                if len(pts) > 3 and pts[-1] == pts[0]:
                    paths.append((np.asarray(pts[:-1], float) + 0.5, True))
    return paths


def join_straight(paths: list[tuple[np.ndarray, bool]], max_turn: float = 45.0) -> list[tuple[np.ndarray, bool]]:
    """Raccorde, à chaque embranchement, les branches qui se prolongent
    (virage de moins de `max_turn` degrés) : un trait qui traverse un
    croisement reste d'un seul tenant, moins de levées d'outil."""
    paths = [(np.asarray(p), c) for p, c in paths]
    lim = -math.cos(math.radians(max_turn))

    def outward(p: np.ndarray, at_end: bool):
        k = min(6, len(p) - 1)
        a, b = (p[-1], p[-1 - k]) if at_end else (p[0], p[k])
        d = b - a
        n = math.hypot(*d)
        return d / n if n > 0 else None

    while True:
        ends: dict[tuple, list] = {}
        for i, (p, closed) in enumerate(paths):
            if not closed and len(p) >= 2:
                ends.setdefault(tuple(p[0]), []).append((i, False))
                ends.setdefault(tuple(p[-1]), []).append((i, True))
        best = None
        for lst in ends.values():
            for x in range(len(lst)):
                for y in range(x + 1, len(lst)):
                    (i, ei), (j, ej) = lst[x], lst[y]
                    if i == j:
                        continue
                    da, db = outward(paths[i][0], ei), outward(paths[j][0], ej)
                    if da is None or db is None:
                        continue
                    cos = float(np.dot(da, db))
                    if cos < lim and (best is None or cos < best[0]):
                        best = (cos, i, ei, j, ej)
        if best is None:
            return paths
        _cos, i, ei, j, ej = best
        pi = paths[i][0] if ei else paths[i][0][::-1]          # finit au nœud
        pj = paths[j][0][::-1] if ej else paths[j][0]          # part du nœud
        merged = np.vstack([pi, pj[1:]])
        closed = bool(np.allclose(merged[0], merged[-1])) and len(merged) > 3
        if closed:
            merged = merged[:-1]
        paths = [x for k, x in enumerate(paths) if k not in (i, j)] + [(merged, closed)]


def to_open_contour(p: np.ndarray, spec: 'TraceSpec') -> Contour:
    pts = [tuple(map(float, q)) for q in p]
    n = len(pts)
    if not spec.smooth or n < 3:
        return Contour([Line(pts[i], pts[i + 1]) for i in range(n - 1)], False)
    v_in = p[1:-1] - p[:-2]
    v_out = p[2:] - p[1:-1]
    cos = (v_in * v_out).sum(1) / np.maximum(np.hypot(*v_in.T) * np.hypot(*v_out.T), 1e-12)
    corner = np.r_[True, np.degrees(np.arccos(np.clip(cos, -1, 1))) > spec.corner_angle, True]
    segs = []
    for i in range(n - 1):
        a, b = pts[i], pts[i + 1]
        if corner[i] and corner[i + 1]:
            segs.append(Line(a, b))
            continue
        prev = pts[i - 1] if not corner[i] else a
        nxt = pts[i + 2] if not corner[i + 1] else b
        c1 = (a[0] + (b[0] - prev[0]) / 6, a[1] + (b[1] - prev[1]) / 6)
        c2 = (b[0] - (nxt[0] - a[0]) / 6, b[1] - (nxt[1] - a[1]) / 6)
        segs.append(Cubic(a, c1, c2, b))
    return Contour(segs, False)


def _smooth_points(p: np.ndarray, closed: bool, k: int = 2) -> np.ndarray:
    """Moyenne glissante sur 2k + 1 points (extrémités fixes si ouvert) :
    efface les marches d'un pixel du squelette."""
    n = len(p)
    if n < 2 * k + 3:
        return p
    if closed:
        ext = np.vstack([p[-k:], p, p[:k]])
        c = np.cumsum(np.vstack([np.zeros((1, 2)), ext]), axis=0)
        return (c[2 * k + 1:] - c[:-2 * k - 1]) / (2 * k + 1)
    c = np.cumsum(np.vstack([np.zeros((1, 2)), p]), axis=0)
    mid = (c[2 * k + 1:] - c[:-2 * k - 1]) / (2 * k + 1)
    out = p.copy()
    out[k:n - k] = mid
    return out


def trace_centerline(gray: np.ndarray, spec: 'TraceSpec') -> list[Contour]:
    """Trait central des zones d'encre (une ligne par trait du dessin)."""
    ink = binarize(np.asarray(gray, float), spec)
    if int(ink.sum()) > MAX_EDGES:
        raise ValueError('image trop chargée pour un trait central : essayer un autre seuil')
    sk = thin(ink)
    # épaisseur moyenne du trait ≈ aire d'encre / longueur du squelette :
    # une branche libre plus courte est une barbule de l'amincissement
    width = float(ink.sum()) / max(1, int(sk.sum()))
    out = []
    for pts, closed in join_straight(skeleton_paths(sk, max(spec.min_length, 1.2 * width))):
        pts = _smooth_points(pts, closed)
        if closed:
            q = simplify_loop(np.vstack([pts, pts[:1]])[:-1], spec.tolerance) if len(pts) > 4 else pts
            if len(q) >= 3:
                out.append(to_contour(q, spec))
            continue
        keep = _rdp(pts, spec.tolerance) if len(pts) > 2 else list(range(len(pts)))
        q = pts[keep]
        if len(q) >= 2:
            out.append(to_open_contour(q, spec))
    return out
