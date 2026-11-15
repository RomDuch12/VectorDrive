"""Retouches d'un relief TypeArt (TypeEdit ▸ TypeArt ▸ Outils), sur la carte
de hauteurs H (numpy, mm) d'un galbe :

* **recalage en Z** : le haut, le milieu, le bas (ou une cote donnée) du
  relief amené à une hauteur ;
* **ajustement dynamique** : nouveau Z max., courbure du profil (γ) ;
* **ajuster au volume** : les hauteurs étirées entre un Z min. et un Z max. ;
* **inverser** (miroir en Z) : bosses en creux et inversement ;
* **trancher** : le relief coupé sous et au-dessus de deux cotes ;
* **rehausser les détails** : les petits reliefs accentués (masque flou) ;
* **bas-relief** : la hauteur ramenée à une profondeur, les détails gardés ;
* **remplir les trous** : les cuvettes fermées comblées jusqu'à leur bord ;
* **matrice / poinçon** : le poinçon (le relief, élargi d'un jeu) et la
  matrice (son empreinte retournée, en creux) ;
* **adapter à un outil** : ce que l'outil peut réellement usiner (parois
  dépouillées, détails trop fins comblés) ;
* **multicopie** linéaire ou circulaire, **perlage** (le long d'une
  courbe) : le relief d'une zone recopié dans le relief ;
* **effacer une partie** : seul le relief dans la zone est gardé (ou bien
  la zone est effacée) ; **extraire une partie** : la zone devient un relief
  à part, recadré sur elle (et, au choix, ôtée de l'original) ;
* **aligner un plan à zéro** (TypeEdit) : le plan passant par le relief
  sous trois marqueurs ramené à Z 0 — un relief palpé de travers redressé ;
* **tranches** (TypeEdit : Tranches) : les contours du relief à des cotes
  successives (courbes de niveau), du haut vers le bas ou l'inverse — pour
  retrouver le contour d'un objet palpé ;
* **facettes au bord** (TypeEdit) : autour du relief, une pente de la hauteur
  de son bord jusqu'à zéro, sur une largeur : le bord à pic s'adoucit ;
* **bordure** (TypeEdit : Bordure) : le relief prolongé autour d'un contour,
  sur une largeur — dans la continuité de son bord, ou à plat à un Z donné ;
  sans sortir de la carte.

Toutes rendent une nouvelle carte ; `apply_to_image` refait l'image.
"""
from __future__ import annotations

import math

from . import galbe as GB

REFERENCES = (('haut', 'Haut'), ('milieu', 'Milieu'), ('bas', 'Bas'), ('valeur', 'Cote donnée'))
PUNCH_KINDS = (('poincon', 'Poinçon'), ('matrice', 'Matrice'), ('les_deux', 'Matrice et poinçon'))
BORDER_MODES = (('continuite', 'Dans la continuité du relief'), ('z_constant', 'À plat, à Z constant'))
PLACE_MODES = (('zmin_zmax', 'Son point le plus bas sur le point le plus haut'),
               ('base_zmax', 'Son plan de base sur le point le plus haut'),
               ('inclinaison', 'Son plan de base suit la surface'))


def place(base_img, top_img, mode: str = 'base_zmax', name: str | None = None):
    """Poser un relief sur un autre (TypeEdit : Poser) : là où le relief
    `top_img` a du relief, il remplace celui de `base_img`, posé dessus —
    'zmin_zmax' : son point le plus bas au niveau du point le plus haut du
    dessous ; 'base_zmax' : son plan de base (Z 0) à ce niveau ;
    'inclinaison' : son plan de base épouse la surface (hauteurs ajoutées).
    Carte agrandie aux deux, au pas le plus fin ; None si illisible."""
    import numpy as np
    a, t = GB.decode(base_img), GB.decode(top_img)
    if a is None or t is None:
        return None
    ba, bt = base_img.bbox(), top_img.bbox()
    b = (min(ba[0], bt[0]), min(ba[1], bt[1]), max(ba[2], bt[2]), max(ba[3], bt[3]))
    x0, y1, nx, ny, res = GB._grid(b, min(a[3], t[3]))
    Hb = GB._sample(a[0], a[1], a[2], a[3], x0, y1, nx, ny, res)
    Ht = GB._sample(t[0], t[1], t[2], t[3], x0, y1, nx, ny, res)
    foot = np.abs(Ht) > 1e-12
    if not foot.any():
        return None
    if mode == 'inclinaison':
        new = np.where(foot, Hb + Ht, Hb)
    else:
        top = float(Hb[foot].max())
        off = top - float(Ht[foot].min()) if mode == 'zmin_zmax' else top
        new = np.where(foot, Ht + off, Hb)
    spec = GB.GalbeSpec.from_dict(base_img.extra.get('galbe') or {})
    spec.z_max, spec.z_min, spec.resolution = float(new.max()), float(new.min()), res
    return GB.encode(new, x0, y1, res, spec, base_img.tool, name or base_img.name or 'Relief')


def level_plane(H, x0: float, y1: float, res: float, points):
    """Aligner un plan à zéro : le plan passant par les hauteurs de H sous
    les trois points (x, y) est retranché — ces points arrivent à Z 0, le
    relief est redressé. ValueError si les points sont alignés ou hors de
    la carte."""
    import numpy as np
    from .typeart import plane_through
    ny, nx = H.shape
    xyz = []
    for x, y in points[:3]:
        i, j = int((x - x0) / res), int((y1 - y) / res)
        if not (0 <= i < nx and 0 <= j < ny):
            raise ValueError('marqueur hors du relief')
        xyz.append((x0 + (i + 0.5) * res, y1 - (j + 0.5) * res, float(H[j, i])))   # centre du pixel lu
    a, b, c = plane_through(*xyz)
    X = x0 + (np.arange(nx) + 0.5) * res
    Y = y1 - (np.arange(ny) + 0.5) * res
    return H - (a * X[None, :] + b * Y[:, None] + c)


def keep_zone(H, inside, invert: bool = False):
    """Effacer une partie : hors de la zone (dans la zone si `invert`), le
    relief ramené à 0."""
    import numpy as np
    return np.where(~inside if invert else inside, H, 0.0)


def crop_zone(H, inside):
    """Extraire une partie : (carte recadrée sur la zone, à 0 hors d'elle,
    rangée de début, colonne de début) ; None si la zone est vide."""
    import numpy as np
    rows, cols = np.nonzero(inside)
    if not len(rows):
        return None
    r0, r1, c0, c1 = rows.min(), rows.max() + 1, cols.min(), cols.max() + 1
    return np.where(inside, H, 0.0)[r0:r1, c0:c1], int(r0), int(c0)


def slices(H, x0: float, y1: float, res: float, first: float, step: float, count: int,
           top_down: bool = True) -> list:
    """Tranches : [(cote, [contours])] — la 1re à `first` sous le haut (du
    bas si `top_down` est faux), les suivantes tous les `step` ; contours
    fermés autour de ce qui dépasse la cote, en mm."""
    import numpy as np
    from .geom import Affine
    from .trace import TraceSpec, trace
    top, bot = float(H.max()), float(H.min())
    spec = TraceSpec(threshold=0.5, speckle=2.0, tolerance=0.6)
    m = Affine(res, 0, 0, -res, x0, y1)
    out = []
    for k in range(max(0, int(count))):
        z = top - first - k * step if top_down else bot + first + k * step
        if z > top + 1e-12 or z < bot - 1e-12:
            break
        ink = H >= z
        if not ink.any():
            continue
        gray = np.pad(np.where(ink, 0.0, 1.0), 1, constant_values=1.0)   # bord blanc : contours fermés
        cs = [c.transformed(Affine(1, 0, 0, 1, -1, -1)).transformed(m) for c in trace(gray, spec)]
        out.append((z, cs))
    return out


def border(H, inside, band, mode: str = 'continuite', z: float = 0.0):
    """Bordure : dans `band` (masque autour de la zone `inside`), le relief
    prolongé — 'continuite' : chaque point prend la hauteur du bord le plus
    proche (propagation pas à pas, moyenne des voisins déjà remplis) ;
    'z_constant' : la cote `z`."""
    import numpy as np
    band = band & ~inside
    out = H.astype(float).copy()
    if mode == 'z_constant':
        out[band] = float(z)
        return out
    known = inside.copy()
    todo = band.copy()
    while todo.any():
        s = np.zeros_like(out)
        n = np.zeros_like(out)
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)):
            k = np.roll(known, (dy, dx), axis=(0, 1))
            v = np.roll(out, (dy, dx), axis=(0, 1))
            if dy:                                       # pas de reprise par l'autre bord de la carte
                k[0 if dy > 0 else -1, :] = False
            if dx:
                k[:, 0 if dx > 0 else -1] = False
            s += np.where(k, v, 0.0)
            n += k
        front = todo & (n > 0)
        if not front.any():
            break
        out[front] = s[front] / n[front]
        known |= front
        todo &= ~front
    return out


def edge_facets(H, res: float, distance: float, eps: float = 1e-6):
    """Facettes au bord : hors du relief, sur `distance` mm, la hauteur du bord le plus proche descend jusqu'à zéro."""
    import numpy as np
    from . import galbe as GB
    out = H.astype(float).copy()
    support = np.abs(out) > eps
    if distance <= 0 or not support.any() or support.all():
        return out
    px = float(distance) / float(res)
    d = GB._edt(~support)
    band = ~support & (d < px + 1.0)
    edge = border(out, support, band)
    out[band] = edge[band] * np.clip(1.0 - d[band] / (px + 1.0), 0.0, 1.0)
    return out


def z_align(H, ref: str = 'bas', target: float = 0.0, value: float = 0.0):
    """Recalage en Z : le point de référence du relief amené à `target`."""
    r = {'haut': float(H.max()), 'milieu': (float(H.max()) + float(H.min())) / 2, 'bas': float(H.min())}.get(ref,
                                                                                                             value)
    return H + (target - r)


def dynamic(H, z_max: float, gamma: float = 1.0):
    """Ajustement dynamique : le sommet amené à z_max, profil courbé par γ
    (1 : linéaire ; < 1 : relève les zones basses ; > 1 : les atténue)."""
    import numpy as np
    top = float(H.max())
    if top <= 0:
        return H.copy()
    n = np.clip(H / top, 0, None)
    return np.where(H > 0, z_max * n ** max(0.05, gamma), H)


def to_volume(H, z_min: float, z_max: float):
    """Ajuster au volume : hauteurs étirées linéairement entre z_min et z_max."""
    lo, hi = float(H.min()), float(H.max())
    if hi - lo < 1e-12:
        return H * 0 + z_min
    return z_min + (H - lo) * (z_max - z_min) / (hi - lo)


def invert(H):
    """Miroir en Z : les bosses deviennent des creux (et inversement)."""
    return -H


def slice_(H, z_low: float, z_high: float, rebase: bool = True):
    """Trancher : relief gardé entre deux cotes ; `rebase` : la tranche posée
    sur le fond (Z bas → 0)."""
    import numpy as np
    out = np.clip(H, z_low, z_high)
    return out - z_low if rebase else out


def blur(H, radius_px: float):
    """Flou ~ gaussien : trois flous de boîte séparables (sommes cumulées)."""
    import numpy as np
    r = max(0, int(round(radius_px / math.sqrt(3))))
    if r == 0:
        return H.copy()
    out = H.astype(float)
    for _ in range(3):
        for axis in (0, 1):
            P = np.pad(out, [(r + 1, r) if a == axis else (0, 0) for a in (0, 1)], mode='edge')
            c = np.cumsum(P, axis=axis)
            if axis == 0:
                out = (c[2 * r + 1:, :] - c[:-2 * r - 1, :]) / (2 * r + 1)
            else:
                out = (c[:, 2 * r + 1:] - c[:, :-2 * r - 1]) / (2 * r + 1)
    return out


def raise_detail(H, res: float, radius: float = 1.0, amount: float = 1.0):
    """Rehausser les détails : H + amount × (H − flou(H)) (rayon en mm)."""
    return H + amount * (H - blur(H, radius / res))


def bas_relief(H, res: float, depth: float, detail_radius: float = 2.0, detail_share: float = 0.3):
    """Bas-relief : formes générales ramenées à (1 − part) de `depth`, détails
    (plus fins que `detail_radius` mm) gardés sur le reste."""
    import numpy as np
    base = blur(H, detail_radius / res)
    detail = H - base
    lo, hi = float(base.min()), float(base.max())
    span = max(1e-9, hi - lo)
    b = (base - lo) / span * depth * (1 - detail_share)
    d = detail
    dmax = float(np.abs(d).max())
    if dmax > 1e-12:
        d = d / dmax * depth * detail_share
    out = b + d
    lo2, hi2 = float(out.min()), float(out.max())
    return (out - lo2) * (depth / (hi2 - lo2)) if hi2 - lo2 > 1e-12 else out - lo2


def fill_holes(H, max_iter: int = 5000):
    """Remplir les trous : chaque cuvette fermée comblée jusqu'au niveau de
    son point de débordement (reconstruction par érosion depuis le bord)."""
    import numpy as np
    F = np.full(H.shape, float(H.max()))
    F[0, :], F[-1, :], F[:, 0], F[:, -1] = H[0, :], H[-1, :], H[:, 0], H[:, -1]
    for _ in range(max_iter):
        P = np.pad(F, 1, mode='edge')
        m = np.minimum.reduce([P[1:-1, 1:-1], P[:-2, 1:-1], P[2:, 1:-1], P[1:-1, :-2], P[1:-1, 2:],
                               P[:-2, :-2], P[:-2, 2:], P[2:, :-2], P[2:, 2:]])
        G = np.maximum(H, m)
        if np.array_equal(G, F):
            break
        F = G
    return F


def dilate_disc(H, radius_px: float, sphere: bool = True, res: float = 1.0):
    """Relief élargi de `radius_px` (pixels de `res` mm) : boule (ou disque
    plat) promenée sur la surface — décalage 3D approché."""
    import numpy as np
    k = int(math.ceil(radius_px))
    if k <= 0:
        return H.copy()
    ny, nx = H.shape
    P = np.pad(H, k, mode='edge')
    out = H.copy()
    for dy in range(-k, k + 1):
        for dx in range(-k, k + 1):
            d2 = dx * dx + dy * dy
            if d2 > radius_px * radius_px:
                continue
            lift = (math.sqrt(radius_px * radius_px - d2) - radius_px) * res if sphere else 0.0
            np.maximum(out, P[k + dy:k + dy + ny, k + dx:k + dx + nx] + lift, out=out)
    return out


def punch_die(H, res: float, offset: float = 0.0):
    """(poinçon, matrice) : le poinçon est le relief élargi du jeu `offset`
    (mm) ; la matrice, son empreinte en creux retournée gauche-droite (elle
    se pose face au poinçon), le fond à Z = 0."""
    import numpy as np
    grown = dilate_disc(H, offset / res, res=res) + offset if offset > 0 else H.copy()
    grown = grown - float(grown.min())                   # le fond reste à Z = 0
    die = -np.fliplr(grown)                              # creux : 0 au bord, plus profond sous les bosses
    return H.copy(), die


def adapt_to_tool(H, res: float, tool, dilation_only: bool = True):
    """Ce que l'outil peut usiner : la pointe posée au plus bas sans entrer
    dans le relief en chaque point (compensation), puis la surface laissée
    par l'outil — le plus bas de l'outil au-dessus de chaque point (parois
    dépouillées, détails trop fins comblés). Sans « dilatation seule » : la
    cote de la pointe (ébauche, laisse plus de matière)."""
    import numpy as np
    from ..cam.advanced import compensate, tool_profile
    T = compensate(H, res, tool)
    if not dilation_only:
        return T
    r = tool.diameter / 2
    k = max(0, int(math.ceil(r / res)))
    ny, nx = H.shape
    P = np.pad(T, k, mode='constant', constant_values=np.inf)
    out = np.full(H.shape, np.inf)
    for dy in range(-k, k + 1):
        for dx in range(-k, k + 1):
            prof = tool_profile(tool, np.array([math.hypot(dx, dy) * res]))[0]
            if not math.isfinite(prof):
                continue
            np.minimum(out, P[k + dy:k + dy + ny, k + dx:k + dx + nx] + prof, out=out)
    return np.where(np.isfinite(out), np.maximum(out, H), H)


# --- duplication dans le relief (multicopie, perlage) -----------------------------------------
def placements_linear(nx: int, ny: int, dx: float, dy: float):
    """Copies en grille : (décalage x, décalage y, angle °), l'original exclu."""
    return [(i * dx, j * dy, 0.0) for j in range(max(1, ny)) for i in range(max(1, nx)) if i or j]


def placements_circular(n: int, total: float = 360.0):
    """n exemplaires répartis sur `total` degrés autour du centre (l'original exclu)."""
    n = max(1, int(n))
    step = total / n if abs(total - 360.0) < 1e-9 else (total / (n - 1) if n > 1 else 0.0)
    return [(0.0, 0.0, k * step) for k in range(1, n)]


def placements_on_curve(points, origin, count: int, rotate: bool = True):
    """Perlage : `count` exemplaires répartis le long de la courbe (points),
    le motif (centré sur `origin`) posé sur chaque point, tourné selon la
    tangente si `rotate`."""
    import numpy as np
    P = np.asarray(points, float)
    if len(P) < 2 or count < 1:
        return []
    seg = np.hypot(*np.diff(P, axis=0).T)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    L = float(cum[-1])
    closed = float(np.hypot(*(P[-1] - P[0]))) < 1e-9
    ts = np.linspace(0, L, count, endpoint=not closed) if count > 1 else np.array([0.0])
    out = []
    for t in ts:
        i = min(len(seg) - 1, int(np.searchsorted(cum, t, side='right') - 1))
        f = (t - cum[i]) / seg[i] if seg[i] > 0 else 0.0
        x, y = P[i] + f * (P[i + 1] - P[i])
        ang = math.degrees(math.atan2(*(P[i + 1] - P[i])[::-1])) if rotate else 0.0
        out.append((float(x - origin[0]), float(y - origin[1]), ang))
    return out


def multicopy(H, x0: float, y1: float, res: float, zone, center, placements, mode: str = 'maximum'):
    """Le relief de la zone (masque booléen de la grille) recopié selon les
    placements (dx, dy, angle° autour de `center`), combiné (`mode`) dans la
    même carte ; ce qui sort de la carte est perdu."""
    import numpy as np
    ny, nx = H.shape
    X, Y = np.meshgrid(x0 + (np.arange(nx) + 0.5) * res, y1 - (np.arange(ny) + 0.5) * res)
    out = H.copy()
    cx, cy = center
    for dx, dy, ang in placements:
        a = math.radians(ang)
        ca, sa = math.cos(a), math.sin(a)
        # point source de chaque pixel : translation puis rotation inverses
        u, v = X - dx - cx, Y - dy - cy
        sx, sy = cx + ca * u + sa * v, cy - sa * u + ca * v
        i = np.floor((sx - x0) / res).astype(int)
        j = np.floor((y1 - sy) / res).astype(int)
        ok = (i >= 0) & (i < nx) & (j >= 0) & (j < ny)
        ii, jj = np.where(ok, i, 0), np.where(ok, j, 0)
        src_in = ok & zone[jj, ii]
        src = H[jj, ii]
        out = GB.combine(out, np.where(src_in, src, 0.0), src_in, mode)
    return out


def make_seamless(H):
    """Texture raccordable : le relief fondu avec sa copie décalée d'une
    demi-taille (poids nul au bord, plein au milieu) — ses bords opposés se
    raccordent en pavage."""
    import numpy as np
    ny, nx = H.shape
    S = np.roll(np.roll(H, ny // 2, axis=0), nx // 2, axis=1)
    wy = 1.0 - np.abs(np.linspace(-1.0, 1.0, ny))
    wx = 1.0 - np.abs(np.linspace(-1.0, 1.0, nx))
    w = np.minimum.outer(wy, wx)
    ws = np.roll(np.roll(w, ny // 2, axis=0), nx // 2, axis=1)
    tot = w + ws
    tot[tot < 1e-12] = 1.0
    return (H * w + S * ws) / tot


def z_at(img, x: float, y: float) -> float | None:
    """Cote du relief en (x, y) (bilinéaire) ; None hors de la carte."""
    got = GB.decode(img)
    if got is None:
        return None
    H, x0, y1, res = got
    ny, nx = H.shape
    fx, fy = (x - x0) / res - 0.5, (y1 - y) / res - 0.5
    if not (-0.5 <= fx <= nx - 0.5 and -0.5 <= fy <= ny - 0.5):
        return None
    fx, fy = min(max(fx, 0.0), nx - 1.0), min(max(fy, 0.0), ny - 1.0)
    i, j = int(fx), int(fy)
    i1, j1 = min(i + 1, nx - 1), min(j + 1, ny - 1)
    tx, ty = fx - i, fy - j
    return float((H[j, i] * (1 - tx) + H[j, i1] * tx) * (1 - ty) + (H[j1, i] * (1 - tx) + H[j1, i1] * tx) * ty)


def profile(img, a, b, n: int = 200) -> list[tuple[float, float]]:
    """Profil du relief de a à b : [(distance depuis a, cote)] (points hors
    de la carte omis)."""
    L = math.dist(a, b)
    out = []
    for k in range(n + 1):
        t = k / n
        z = z_at(img, a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        if z is not None:
            out.append((L * t, z))
    return out


def merge_reliefs(images, mode: str = 'ajouter', limit: bool = False, name: str = 'Relief'):
    """Combiner des reliefs (TypeEdit : coller un objet TypeArt dans le
    courant) : le premier est le relief courant, les suivants s'y combinent
    selon `mode` là où ils ont du relief (hauteur non nulle) ; carte agrandie
    à l'ensemble, au pas le plus fin. Rend l'image combinée."""
    import numpy as np
    got = [(im, GB.decode(im)) for im in images]
    got = [(im, g) for im, g in got if g is not None]
    if len(got) < 2:
        return None
    boxes = [im.bbox() for im, _g in got]
    b = (min(x[0] for x in boxes), min(x[1] for x in boxes), max(x[2] for x in boxes), max(x[3] for x in boxes))
    res = min(g[3] for _im, g in got)
    x0, y1, nx, ny, res = GB._grid(b, res)
    first = got[0][1]
    H = GB._sample(first[0], first[1], first[2], first[3], x0, y1, nx, ny, res)
    for _im, (h, ox0, oy1, ores) in got[1:]:
        new = GB._sample(h, ox0, oy1, ores, x0, y1, nx, ny, res)
        H = GB.combine(H, new, np.abs(new) > 1e-12, mode, limit)
    spec = GB.GalbeSpec.from_dict(got[0][0].extra.get('galbe') or {})
    spec.z_max, spec.z_min, spec.resolution = float(H.max()), float(H.min()), res
    return GB.encode(H, x0, y1, res, spec, got[0][0].tool, got[0][0].name or name)


def apply_to_image(img, H, name: str | None = None):
    """Nouvelle image du relief `H` à la place de `img` (même grille)."""
    got = GB.decode(img)
    if got is None:
        return None
    _old, x0, y1, res = got
    spec = GB.GalbeSpec.from_dict(img.extra.get('galbe') or {})
    return GB.encode(H, x0, y1, res, spec, img.tool, name or img.name or 'Galbe')
