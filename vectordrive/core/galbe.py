"""Galbe (TypeEdit : TypeArt ▸ Galbe) — relief bombé de formes fermées, en
carte de hauteurs que la stratégie Relief usine.

La hauteur d'un point ne dépend que de sa distance d au bord de la forme
(trous compris) : `z_min` au bord, montée avec l'angle de départ (90° :
vertical), `z_max` à `distance` du bord avec l'angle d'arrivée (0° : sommet
plat), plateau au-delà. Une forme plus étroite que deux fois `distance`
n'atteint pas `z_max`, comme dans TypeEdit. Le profil est une courbe de
Bézier tangente aux deux angles (quart d'ellipse pour 90° / 0°).

Un galbe se combine à un galbe existant comme dans TypeArt (`MODES`) :
remplacer, ajouter, soustraire, maximum, minimum, moyenne — dans la zone
du nouveau galbe ; « limiter » ne le pose que sur le galbe existant.
`smooth` : lissage (TypeArt : Lissage, nombre de passes), sur tout le
galbe ou dans une zone.

La carte est une image en niveaux de gris sur 16 bits (65 536 niveaux :
1/65 535 de la profondeur, au lieu des marches de 1/255 des cartes 8 bits
d'avant, toujours relues) : blanc au plus haut, noir au plus bas (le fond, ou un creux sous le fond après une soustraction).
Usinée en Relief avec la profondeur `relief_depth` gardée dans
`extra['galbe']` : le sommet affleure, le fond est abaissé (bas-relief) ;
« Relief : blanc en creux » donne le galbe en creux (moule, empreinte).
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

#: côté de la carte au-delà duquel le pas est relâché (pixels)
MAX_SIDE = 1600
_K = 0.5523                                         # quart de cercle en Bézier cubique
#: compression du profil (TypeEdit) : sommet plat quand Z max. est atteint ; Z max. atteint partout sur
#: l'arête (profil ramené à la demi-largeur locale) ; hauteur proportionnelle à la demi-largeur locale
COMPRESSIONS = (('aucune', 'Pas de compression'), ('longueur', 'Compression sur la longueur'),
                ('proportionnelle', 'Compression proportionnelle'))
MODES = (('remplacer', 'Remplacer'), ('ajouter', 'Ajouter'), ('soustraire', 'Soustraire'),
         ('maximum', 'Maximum'), ('minimum', 'Minimum'), ('moyenne', 'Moyenne'))


@dataclass
class GalbeSpec:
    z_max: float = 2.0              # hauteur du sommet (mm)
    z_min: float = 0.0              # hauteur au bord (mm)
    distance: float = 3.0           # longueur de la montée, depuis le bord (mm)
    start_angle: float = 90.0       # pente au bord (°, 90 : verticale)
    end_angle: float = 0.0          # pente au sommet (°, 0 : plat)
    resolution: float = 0.1         # pas de la carte (mm)
    margin: float = 1.0             # fond laissé autour des formes (mm)
    mode: str = 'remplacer'         # combinaison avec un galbe existant (MODES)
    limit: bool = False             # ne galber que sur le galbe existant
    compression: str = 'aucune'     # COMPRESSIONS
    profile_pts: list | None = None  # profil dessiné (galbe asymétrique) : [(distance, hauteur)…]

    @classmethod
    def from_dict(cls, d: dict) -> 'GalbeSpec':
        return cls(**{k: v for k, v in (d or {}).items() if k in cls.__dataclass_fields__})


def profile_length(spec: GalbeSpec) -> float:
    """Longueur de la montée : `distance`, ou la largeur du profil dessiné."""
    if spec.profile_pts:
        xs = [p[0] for p in spec.profile_pts]
        return max(1e-6, max(xs) - min(xs))
    return max(1e-6, spec.distance)


def profile(spec: GalbeSpec, d):
    """Hauteurs (numpy) aux distances au bord `d` (mm, ≥ 0)."""
    import numpy as np
    if spec.profile_pts:
        # galbe asymétrique : le profil dessiné (abscisse : distance au bord
        # depuis son point le plus à gauche ; ordonnée : hauteur depuis son bas)
        from .sweep import profile_table
        px, ph = profile_table(spec.profile_pts, 0.005)
        return spec.z_min + np.interp(np.clip(np.asarray(d, dtype=float), 0.0, float(px[-1])), px, ph)
    D = max(1e-6, spec.distance)
    dz = spec.z_max - spec.z_min
    a0 = math.radians(min(90.0, max(0.0, spec.start_angle)))
    a1 = math.radians(min(90.0, max(0.0, spec.end_angle)))
    k0 = _K * math.hypot(D * math.cos(a0), abs(dz) * math.sin(a0))
    k1 = _K * math.hypot(D * math.cos(a1), abs(dz) * math.sin(a1))
    s = 1.0 if dz >= 0 else -1.0
    p0, p3 = (0.0, spec.z_min), (D, spec.z_max)
    p1 = (k0 * math.cos(a0), spec.z_min + s * k0 * math.sin(a0))
    p2 = (D - k1 * math.cos(a1), spec.z_max - s * k1 * math.sin(a1))
    t = np.linspace(0.0, 1.0, 2049)
    u = 1 - t
    xs = u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0]
    zs = u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]
    xs = np.maximum.accumulate(xs)                  # abscisses croissantes (np.interp)
    return np.interp(np.clip(np.asarray(d, dtype=float), 0.0, D), xs, zs)


def _edt(inside):
    """Distance (pixels) de chaque pixel intérieur au plus proche pixel
    extérieur (transformée exacte, séparable : colonnes puis lignes)."""
    import numpy as np
    ny, nx = inside.shape
    big = float(nx + ny)
    g = np.where(inside, big, 0.0)
    for y in range(1, ny):
        np.minimum(g[y], g[y - 1] + 1.0, out=g[y])
    for y in range(ny - 2, -1, -1):
        np.minimum(g[y], g[y + 1] + 1.0, out=g[y])
    xs = np.arange(nx, dtype=float)
    diff2 = (xs[:, None] - xs[None, :]) ** 2
    out = np.empty((ny, nx))
    for y in range(ny):
        out[y] = np.min(g[y][None, :] ** 2 + diff2, axis=1)
    return np.sqrt(out)


def _grid(bounds, res: float):
    """(x0, y1, nx, ny, pas) d'une carte couvrant `bounds`, côté borné."""
    x0, y0, x1, y1 = bounds
    res = max(0.01, res, (x1 - x0) / MAX_SIDE, (y1 - y0) / MAX_SIDE)
    return x0, y1, max(2, int(math.ceil((x1 - x0) / res))), max(2, int(math.ceil((y1 - y0) / res))), res


def _inside(region, x0, y1, nx, ny, res):
    import numpy as np
    import shapely
    XX, YY = np.meshgrid(x0 + (np.arange(nx) + 0.5) * res, y1 - (np.arange(ny) + 0.5) * res)
    shapely.prepare(region)
    return shapely.contains_xy(region, XX, YY)


def ridge_distance(d, max_iter: int = 4000):
    """Demi-largeur locale de la forme en chaque point : la distance au bord
    du point d'arête atteint en montant au plus raide. Hors de l'arête la
    distance au bord monte d'un pixel par pixel ; sur l'arête (axe médian),
    nettement moins (< 0,9) : ces points gardent leur propre distance."""
    import numpy as np
    ny, nx = d.shape
    offs = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    P = np.pad(d, 1, mode='constant', constant_values=-1.0)
    slopes = np.stack([(P[1 + dy:1 + dy + ny, 1 + dx:1 + dx + nx] - d) / math.hypot(dx, dy) for dy, dx in offs])
    best = np.argmax(slopes, axis=0)
    steep = np.take_along_axis(slopes, best[None], 0)[0]
    pix = max(1e-12, float(np.min(np.diff(np.unique(d))[:1])) if d.size > 1 and np.unique(d).size > 1 else 1.0)
    ridge = (steep < 0.9 * pix) | (d <= 0)
    jj, ii = np.indices(d.shape)
    tj = np.clip(jj + np.array([o[0] for o in offs])[best], 0, ny - 1)
    ti = np.clip(ii + np.array([o[1] for o in offs])[best], 0, nx - 1)
    tj = np.where(ridge, jj, tj)
    ti = np.where(ridge, ii, ti)
    # pointeurs vers le voisin le plus haut, suivis par doublement jusqu'à l'arête
    for _ in range(max(1, int(math.ceil(math.log2(max(ny, nx) + 1))) + 1)):
        tj, ti = tj[tj, ti], ti[tj, ti]
    return d[tj, ti]


def _heights_on(region, spec: GalbeSpec, x0, y1, nx, ny, res):
    """(hauteurs, intérieur) du galbe de la région sur une grille donnée."""
    import numpy as np
    inside = _inside(region, x0, y1, nx, ny, res)
    # un pixel « dehors » tout autour : une forme qui touche le bord de la
    # carte (fond de 0 mm) y a bien son bord
    e = _edt(np.pad(inside, 1, mode='constant', constant_values=False))[1:-1, 1:-1]
    d = np.maximum(0.0, e * res - res / 2)                # distance au bord, pas au centre du pixel voisin
    comp = getattr(spec, 'compression', 'aucune')
    if comp in ('longueur', 'proportionnelle'):
        D = profile_length(spec)
        R = np.maximum(ridge_distance(np.where(inside, d, 0.0)), res / 2)
        t = np.clip(d / R, 0.0, 1.0)
        H = profile(spec, t * D)                          # le profil entier tient dans la demi-largeur
        if comp == 'proportionnelle':
            H = spec.z_min + (H - spec.z_min) * np.clip(R / D, 0.0, 1.0)
        return np.where(inside, H, 0.0), inside
    return np.where(inside, profile(spec, d), 0.0), inside


def heightmap(region, spec: GalbeSpec):
    """(hauteurs [ny, nx] du haut vers le bas, x0, y1, pas) d'une région
    shapely ; None si vide."""
    if region is None or region.is_empty:
        return None
    b = region.bounds
    m = max(0.0, spec.margin)
    x0, y1, nx, ny, res = _grid((b[0] - m, b[1] - m, b[2] + m, b[3] + m), max(0.01, spec.resolution))
    H, _inside_ = _heights_on(region, spec, x0, y1, nx, ny, res)
    return H, x0, y1, res


def encode(H, x0: float, y1: float, res: float, spec: GalbeSpec, tool: int = 0, name: str = 'Galbe'):
    """Image en niveaux de gris de la carte (blanc au plus haut, noir au plus
    bas), réglages et profondeur à usiner dans `extra['galbe']`."""
    import numpy as np
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice
    from PySide6.QtGui import QImage
    from .document import Image
    from .geom import Affine
    base = min(0.0, float(H.min()))
    top = max(float(H.max()), base + 1e-9)
    g = np.clip(np.round((H - base) / (top - base) * 65535.0), 0, 65535).astype(np.uint16)
    ny, nx = g.shape
    q = QImage(g.tobytes(), nx, ny, nx * 2, QImage.Format.Format_Grayscale16).copy()
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    q.save(buf, 'PNG')
    buf.close()
    img = Image(data=bytes(ba), fmt='png', matrix=Affine(nx * res, 0, 0, -ny * res, x0, y1), tool=tool, name=name)
    img.extra['galbe'] = dict(asdict(spec), relief_depth=top - base, base=base, top=top)
    return img


def decode(img):
    """(hauteurs, x0, y1, pas) d'une image de galbe ; None si illisible, ou
    tournée, inclinée, retournée (la carte ne se relit que posée droite)."""
    import numpy as np
    from PySide6.QtGui import QImage
    m = img.matrix
    if abs(m.b) > 1e-9 or abs(m.c) > 1e-9 or m.a <= 0 or m.d >= 0:
        return None
    g = img.extra.get('galbe') or {}
    q = QImage.fromData(img.data)
    if q.isNull() or abs((m.a / q.width()) / (-m.d / q.height()) - 1) > 0.01:
        return None                                      # illisible, ou étirée d'un seul côté
    gray = gray_array(q)
    base = float(g.get('base', 0.0))
    depth = float(g.get('relief_depth', 1.0))
    x0, y0, x1, y1 = img.bbox()
    return base + gray * depth, x0, y1, (x1 - x0) / q.width()


def gray_array(q):
    """Niveaux de gris 0…1 (numpy) d'une QImage : 16 bits pour une carte
    16 bits, sinon 8 bits."""
    import numpy as np
    from PySide6.QtGui import QImage
    if q.format() == QImage.Format.Format_Grayscale16:
        arr = np.frombuffer(q.constBits(), np.uint16, q.sizeInBytes() // 2).reshape(q.height(), q.bytesPerLine() // 2)
        return arr[:, :q.width()].astype(float) / 65535.0
    q = q.convertToFormat(QImage.Format.Format_Grayscale8)
    arr = np.frombuffer(q.constBits(), np.uint8, q.sizeInBytes()).reshape(q.height(), q.bytesPerLine())
    return arr[:, :q.width()].astype(float) / 255.0


def _sample(H, ox0, oy1, ores, x0, y1, nx, ny, res):
    """Carte H (origine ox0, oy1, pas ores) relue sur une autre grille
    (plus proche voisin, 0 au-dehors)."""
    import numpy as np
    xs = x0 + (np.arange(nx) + 0.5) * res
    ys = y1 - (np.arange(ny) + 0.5) * res
    i = np.floor((xs - ox0) / ores).astype(int)
    j = np.floor((oy1 - ys) / ores).astype(int)
    out = np.zeros((ny, nx))
    oki = (i >= 0) & (i < H.shape[1])
    okj = (j >= 0) & (j < H.shape[0])
    out[np.ix_(okj, oki)] = H[np.ix_(j[okj], i[oki])]
    return out


def combine(old, new, inside, mode: str, limit: bool = False):
    """Carte combinée : dans la zone du nouveau galbe (`inside`, réduite au
    galbe existant si `limit`), selon `mode` ; ailleurs, l'existant."""
    import numpy as np
    zone = inside & (old > 0) if limit else inside
    res = {'ajouter': old + new, 'soustraire': old - new, 'maximum': np.maximum(old, new),
           'minimum': np.minimum(old, new), 'moyenne': (old + new) / 2}.get(mode, new)
    return np.where(zone, res, old)


def build_image(region, spec: GalbeSpec, tool: int = 0, onto=None):
    """Image du galbe de la région ; `onto` : image d'un galbe existant,
    combinée selon `spec.mode` sur une carte qui couvre les deux. None si
    rien à galber."""
    if region is None or region.is_empty:
        return None
    if onto is None:
        H, x0, y1, res = heightmap(region, spec)
        return encode(H, x0, y1, res, spec, tool)
    got = decode(onto)
    if got is None:
        return None
    oH, ox0, oy1, ores = got
    b, ob = region.bounds, onto.bbox()
    m = max(0.0, spec.margin)
    x0, y1, nx, ny, res = _grid((min(b[0] - m, ob[0]), min(b[1] - m, ob[1]), max(b[2] + m, ob[2]),
                                 max(b[3] + m, ob[3])), min(max(0.01, spec.resolution), ores))
    new, inside = _heights_on(region, spec, x0, y1, nx, ny, res)
    old = _sample(oH, ox0, oy1, ores, x0, y1, nx, ny, res)
    return encode(combine(old, new, inside, spec.mode, spec.limit), x0, y1, res, spec, tool, onto.name or 'Galbe')


def smooth(img, passes: int = 1, region=None):
    """Lissage (TypeArt) : moyenne 3 × 3 répétée `passes` fois, sur tout le
    galbe ou dans `region` ; nouvelle image."""
    import numpy as np
    got = decode(img)
    if got is None:
        return None
    H, x0, y1, res = got
    zone = _inside(region, x0, y1, H.shape[1], H.shape[0], res) if region is not None else None
    for _ in range(max(0, int(passes))):
        P = np.pad(H, 1, mode='edge')
        S = sum(P[1 + dy:P.shape[0] - 1 + dy, 1 + dx:P.shape[1] - 1 + dx]
                for dy in (-1, 0, 1) for dx in (-1, 0, 1)) / 9.0
        H = S if zone is None else np.where(zone, S, H)
    spec = GalbeSpec.from_dict(img.extra.get('galbe') or {})
    return encode(H, x0, y1, res, spec, img.tool, img.name or 'Galbe')
