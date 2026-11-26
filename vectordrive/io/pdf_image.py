"""Images matricielles d'un PDF → objets Image du dessin (round 1160, demande « Imports pdf contenant image
matricielle : be compatible »).

Une image du PDF (XObject /Image appelé par « Do », ou image en ligne « BI … ID … EI ») devient une image du dessin,
posée à sa place et à sa taille (matrice courante, rotation et miroir compris), comme une image importée directement :
la vectorisation la reprend ensuite. Les données sont défaites ici, bornées par la taille annoncée de l'image (jamais
par le plafond de 75 Mo de pypdf) : Flate par zlib, prédicteurs PNG et TIFF par numpy (ou par le lecteur PNG de Qt,
pour qui un flux Flate à prédicteur PNG est un PNG tout fait, quand l'image n'est pas à réduire ; les filtres PNG
« Average » et « Paeth » hors de Qt, octet par octet, bornés par `SLOW_BYTES`), ASCIIHex, ASCII85, RunLength et LZW
par pypdf ; Qt décode le JPEG (DCTDecode, CMJN Adobe compris) et le fax (CCITT, par l'en-tête TIFF de pypdf),
réduits à la lecture au-delà de `raster.MAX_PIXELS`. Les échantillons (1, 2, 4, 8 ou 16 bits) passent par des
tables de correspondance : gris, RVB, CMJN, palette (Indexed), ICC (selon leur nombre de composantes), teinte
d'accompagnement en gris, tableau /Decode, masque (/ImageMask : peint de la couleur de fond courante), masque doux
/SMask, masque /Mask (image ou plage de couleurs). JPEG 2000 (JPX) et JBIG2 ne se décodent pas ici : remarque, le
reste du PDF est lu. Une image trop grande, incomplète ou abîmée : remarque en clair, jamais d'exception.
"""
from __future__ import annotations

import math
import struct
import zlib

from ..core.document import Image
from ..core.geom import Affine
from ..i18n import tr

#: carré unité de l'image du dessin (v vers le bas, comme un fichier image) → celui de l'image PDF (v vers le haut)
FLIP = Affine(1, 0, 0, -1, 0, 1)
#: filtres non décodés ici : leur nom en clair
UNSUPPORTED = {'/JPXDecode': 'JPEG 2000 (JPX)', '/JBIG2Decode': 'JBIG2'}
#: pixels annoncés au plus, et octets décodés au plus (vérifiés avant tout décodage)
MAX_SAMPLES = 1_000_000_000
MAX_BYTES = 512 * 1024 * 1024
#: données décodées plus courtes que cette part de la taille annoncée : image refusée (sinon complétée)
SHORT = 0.5
#: limite de mémoire du lecteur d'images de Qt pendant un décodage (Mo), rendue ensuite
QT_LIMIT = 1024
#: octets au plus défaits par la boucle Python des filtres PNG « Average » et « Paeth » (hors lecteur PNG de Qt) :
#: au-delà, l'image est refusée avec une remarque plutôt que de figer l'import
SLOW_BYTES = 8 * 1024 * 1024
#: abréviations des images en ligne (clés, puis valeurs)
INLINE_KEYS = {'/W': '/Width', '/H': '/Height', '/BPC': '/BitsPerComponent', '/CS': '/ColorSpace', '/F': '/Filter',
               '/DP': '/DecodeParms', '/IM': '/ImageMask', '/D': '/Decode', '/I': '/Interpolate', '/L': '/Length'}
INLINE_VALUES = {'/G': '/DeviceGray', '/RGB': '/DeviceRGB', '/CMYK': '/DeviceCMYK', '/I': '/Indexed',
                 '/AHx': '/ASCIIHexDecode', '/A85': '/ASCII85Decode', '/LZW': '/LZWDecode', '/Fl': '/FlateDecode',
                 '/RL': '/RunLengthDecode', '/CCF': '/CCITTFaxDecode', '/DCT': '/DCTDecode'}


class Skipped(ValueError):
    """Image laissée de côté : la raison, en clair, va dans les remarques de l'import."""


def _too_big() -> str:
    return tr('Image(s) PDF trop grande(s) pour être importée(s) : ignorée(s)')


def _reduced() -> str:
    return tr('Image(s) PDF très grande(s) : réduite(s) à l’import')


def _obj(v):
    """L'objet pointé (référence indirecte pypdf) ou la valeur telle quelle."""
    return v.get_object() if hasattr(v, 'get_object') else v


def _names(v) -> list[str]:
    """Liste de noms (un nom seul, ou un tableau) ; [] si absente."""
    v = _obj(v)
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        return [INLINE_VALUES.get(str(_obj(x)), str(_obj(x))) for x in v]
    return [INLINE_VALUES.get(str(v), str(v))]


def _parms(src, n: int) -> list:
    """Les /DecodeParms de chaque filtre (objets pypdf, ou {})."""
    p = _obj(src.get('/DecodeParms'))
    if isinstance(p, (list, tuple)):
        out = [_obj(x) for x in p]
    else:                                                # un seul dictionnaire : celui du dernier filtre
        out = [None] * max(0, n - 1) + [p]
    out = [x if hasattr(x, 'get') else {} for x in out]
    return (out + [{}] * n)[:n]


def _truth(v) -> bool:
    """Booléen PDF (BooleanObject de pypdf, ou bool)."""
    v = _obj(v)
    return bool(getattr(v, 'value', v))


def _int(d, key, default: int) -> int:
    try:
        return int(_obj(d.get(key, default)))
    except (TypeError, ValueError, AttributeError):
        return default


# --- données : filtres défaits, bornés par la taille attendue --------------------------------------------------
def _inflate(data: bytes, limit: int) -> bytes:
    """Flate défait par zlib, au plus `limit` octets ; un flux abîmé rend ce qu'il a pu (sans en-tête zlib aussi)."""
    for wbits in (15, -15):
        d, out, total = zlib.decompressobj(wbits), [], 0
        try:
            for i in range(0, len(data), 1 << 16):
                chunk = d.decompress(data[i:i + (1 << 16)], max(1, limit - total))
                out.append(chunk)
                total += len(chunk)
                if total >= limit:
                    break
        except zlib.error:
            if not out and wbits == 15:
                continue                                 # pas d'en-tête zlib : deflate brut
        return b''.join(out)[:limit]
    return b''


def _unpack(a, bpc: int, count: int):
    """Échantillons de `bpc` bits (< 8) de chaque ligne d'octets `a` (lignes, octets) → (lignes, count) uint8."""
    import numpy as np
    bits = np.unpackbits(a, axis=1)
    weights = (1 << np.arange(bpc - 1, -1, -1)).astype(np.uint8)
    usable = bits.shape[1] // bpc * bpc
    return (bits[:, :usable].reshape(a.shape[0], -1, bpc) * weights).sum(axis=2, dtype=np.uint8)[:, :count]


def _pack(s, bpc: int, row: int):
    """L'inverse de `_unpack` : (lignes, n) échantillons → (lignes, row) octets."""
    import numpy as np
    shifts = np.arange(bpc - 1, -1, -1, dtype=np.uint8)
    bits = ((s[..., None] >> shifts) & 1).astype(np.uint8).reshape(s.shape[0], -1)
    pad = row * 8 - bits.shape[1]
    if pad > 0:
        bits = np.hstack([bits, np.zeros((s.shape[0], pad), np.uint8)])
    return np.packbits(bits[:, :row * 8], axis=1)


def _paeth_or_average(cur, prev, bpp: int, paeth: bool):
    """Une ligne en filtre PNG « Average » (3) ou « Paeth » (4) : octet par octet (chacun dépend du précédent)."""
    c, p = cur.tolist(), prev.tolist()
    out = [0] * len(c)
    for i in range(len(c)):
        left = out[i - bpp] if i >= bpp else 0
        if paeth:
            ul = p[i - bpp] if i >= bpp else 0
            up = p[i]
            q = left + up - ul
            pa, pb, pc = abs(q - left), abs(q - up), abs(q - ul)
            pred = left if pa <= pb and pa <= pc else up if pb <= pc else ul
        else:
            pred = (left + p[i]) >> 1
        out[i] = (c[i] + pred) & 255
    return out


def unpredict(data: bytes, parms) -> bytes:
    """Prédicteur d'un flux Flate ou LZW défait (TIFF 2 ou PNG ≥ 10), numpy : justes en 1, 2, 4, 8 et 16 bits."""
    import numpy as np
    pred = _int(parms, '/Predictor', 1)
    if pred < 2:
        return data
    colors, bpc, cols = _int(parms, '/Colors', 1), _int(parms, '/BitsPerComponent', 8), _int(parms, '/Columns', 1)
    if bpc not in (1, 2, 4, 8, 16) or colors < 1 or cols < 1:
        return data
    row = (cols * colors * bpc + 7) // 8
    if pred == 2:                                        # TIFF : différence avec l'échantillon de gauche
        n = len(data) // row
        a = np.frombuffer(data, np.uint8, count=n * row).reshape(n, row)
        if bpc == 8:
            return np.cumsum(a[:, :cols * colors].reshape(n, cols, colors), axis=1, dtype=np.uint8).tobytes()
        if bpc == 16:
            s = a[:, :cols * colors * 2].copy().view('>u2').reshape(n, cols, colors)
            return np.cumsum(s, axis=1, dtype=np.uint16).astype('>u2').tobytes()
        s = _unpack(a, bpc, cols * colors).reshape(n, cols, colors)
        s = (np.cumsum(s, axis=1, dtype=np.uint8) & ((1 << bpc) - 1)).reshape(n, cols * colors)
        return _pack(s, bpc, row).tobytes()
    bpp = max(1, colors * bpc // 8)                      # PNG : un octet de filtre par ligne
    stride = row + 1
    n = len(data) // stride
    a = np.frombuffer(data, np.uint8, count=n * stride).reshape(n, stride)
    kinds = a[:, 0]
    whole = row // bpp * bpp
    slow = int(np.count_nonzero((kinds == 3) | (kinds == 4) | ((kinds == 1) & (whole != row)))) * row
    if slow > SLOW_BYTES:                                # octet par octet en Python : trop long, refusée
        raise Skipped(tr('Image PDF trop grande pour son prédicteur PNG (Average ou Paeth) : ignorée'))
    rows = a[:, 1:].copy()
    prev = np.zeros(row, np.uint8)
    for r in range(n):
        t, cur = int(kinds[r]), rows[r]
        if t == 1:                                       # Sub : somme cumulée, pixel par pixel
            cur = np.cumsum(cur.reshape(-1, bpp), axis=0, dtype=np.uint8).reshape(-1) if whole == row \
                else np.array(_sub(cur, bpp), np.uint8)
        elif t == 2:                                     # Up
            cur = cur + prev
        elif t in (3, 4):                                # Average, Paeth
            cur = np.array(_paeth_or_average(cur, prev, bpp, t == 4), np.uint8)
        rows[r] = cur
        prev = rows[r]
    return rows.tobytes()


def _sub(cur, bpp: int) -> list:
    """Filtre PNG « Sub » d'une ligne dont la longueur n'est pas un multiple de `bpp`."""
    out = cur.tolist()
    for i in range(bpp, len(out)):
        out[i] = (out[i] + out[i - bpp]) & 255
    return out


def _unfiltered(raw: bytes, filters: list, parms: list, limit: int) -> bytes:
    """Les filtres `filters` défaits l'un après l'autre (Flate au plus `limit` octets, prédicteurs compris)."""
    from pypdf.filters import ASCII85Decode, ASCIIHexDecode, LZWDecode, RunLengthDecode
    data = raw
    for f, p in zip(filters, parms):
        if f == '/ASCIIHexDecode':
            data = ASCIIHexDecode.decode(data)
        elif f == '/ASCII85Decode':
            data = ASCII85Decode.decode(data)
        elif f == '/FlateDecode':
            pred = _int(p, '/Predictor', 1)
            cap = limit
            if pred >= 10:                               # un octet de filtre en tête de chaque ligne
                cols = _int(p, '/Columns', 1) * _int(p, '/Colors', 1) * _int(p, '/BitsPerComponent', 8)
                cap = limit + limit // max(1, (cols + 7) // 8) + 1
            data = unpredict(_inflate(data, cap), p)
        elif f in ('/LZWDecode', '/RunLengthDecode'):
            try:
                data = (LZWDecode if f == '/LZWDecode' else RunLengthDecode).decode(data)
            except Exception as ex:                      # noqa: BLE001 — plafond de pypdf, flux abîmé
                raise Skipped(tr('Image PDF compressée en {0} trop grande ou abîmée : ignorée').format(
                    'LZW' if f == '/LZWDecode' else 'RunLength')) from ex
            if f == '/LZWDecode':
                data = unpredict(data, p)
        else:
            raise Skipped(tr('Image PDF au filtre {0} non pris en charge : ignorée').format(f.lstrip('/')))
        if isinstance(data, str):
            data = data.encode('latin-1')
    return bytes(data)


def _qt_decode(data: bytes, notes: set, scale: bool = True):
    """QImage d'un JPEG, d'un TIFF (fax) ou d'un PNG ; taille lue d'abord : au-delà de `raster.MAX_PIXELS`, réduite à
    la lecture (`scale`) ; la limite de mémoire de Qt fixée à `QT_LIMIT` Mo le temps du décodage, puis rendue telle
    qu'elle était. None s'il ne se lit pas."""
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QSize
    from PySide6.QtGui import QImageReader
    from .raster import MAX_PIXELS, _app
    _app()
    old = QImageReader.allocationLimit()
    QImageReader.setAllocationLimit(QT_LIMIT)            # levée ou abaissée ailleurs : la nôtre, le temps de lire
    try:
        buf = QBuffer()
        buf.setData(QByteArray(data))
        buf.open(QIODevice.OpenModeFlag.ReadOnly)
        r = QImageReader(buf)
        size = r.size()
        if scale and size.isValid() and size.width() * size.height() > MAX_PIXELS:
            k = math.sqrt(MAX_PIXELS / (size.width() * size.height()))
            r.setScaledSize(QSize(max(1, int(size.width() * k)), max(1, int(size.height() * k))))
            notes.add(_reduced())
        q = r.read()
    finally:
        QImageReader.setAllocationLimit(old)
    return None if q.isNull() else q


def _array(q, fmt, channels: int, dtype='uint8'):
    """Pixels d'une QImage convertie en `fmt` : (h, w, channels) (copie)."""
    import numpy as np
    q = q.convertToFormat(fmt)
    w, h = q.width(), q.height()
    item = np.dtype(dtype).itemsize
    px = np.frombuffer(q.constBits(), np.dtype(dtype), count=q.sizeInBytes() // item)
    return px.reshape(h, q.bytesPerLine() // item)[:, :channels * w].reshape(h, w, channels).copy()


def _png_samples(zdata: bytes, w: int, h: int, n: int, bpc: int):
    """Échantillons d'un flux Flate à prédicteur PNG, lus par le lecteur PNG de Qt (le flux est l'IDAT d'un PNG) :
    (h, w, n) exacts ; None si la forme n'existe pas en PNG ou que Qt ne le lit pas (numpy prend la suite)."""
    import numpy as np
    from PySide6.QtGui import QImage
    ctype = {1: 0, 2: 4, 3: 2, 4: 6}.get(n)
    if ctype is None or (n > 1 and bpc not in (8, 16)) or bpc not in (1, 2, 4, 8, 16):
        return None

    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(d, zlib.crc32(t)) & 0xffffffff)
    png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, bpc, ctype, 0, 0, 0))
           + chunk(b'IDAT', zdata) + chunk(b'IEND', b''))
    q = _qt_decode(png, set(), scale=False)
    if q is None or (q.width(), q.height()) != (w, h):
        return None
    F = QImage.Format
    if n == 1 and bpc <= 8:
        g = _array(q, F.Format_Grayscale8, 1)
        if bpc < 8:                                      # Qt étale les niveaux sur 0…255 : remis à leur valeur
            maxv = (1 << bpc) - 1
            g = ((g.astype(np.uint16) * maxv + 127) // 255).astype(np.uint8)
        return g
    if n == 1:
        return _array(q, F.Format_Grayscale16, 1, 'uint16')
    if bpc == 8:
        if n == 3:
            return _array(q, F.Format_RGB888, 3)
        px = _array(q, F.Format_RGBA8888, 4)
        return px[..., [0, 3]].copy() if n == 2 else px
    px = _array(q, F.Format_RGBA64, 4, 'uint16')
    return px[..., [0, 3]].copy() if n == 2 else px[..., :n].copy()


def _samples(data: bytes, w: int, h: int, n: int, bpc: int, step: int, notes: set):
    """Échantillons bruts (h, w, n), une ligne et une colonne sur `step` ; données un peu courtes (PDF abîmé) :
    complétées, et dit ; bien trop courtes : refusée."""
    import numpy as np
    row = (w * n * bpc + 7) // 8
    need = row * h
    if len(data) < need:
        if len(data) < need * SHORT:
            raise Skipped(tr('Image PDF incomplète (données bien plus courtes que sa taille annoncée) : ignorée'))
        notes.add(tr('Image PDF tronquée : complétée'))
        data = bytes(data) + bytes(need - len(data))
    raw = np.frombuffer(data, np.uint8, count=need).reshape(h, row)[::step]
    if bpc == 8:
        return raw[:, :w * n].reshape(-1, w, n)[:, ::step]
    if bpc == 16:
        return np.ascontiguousarray(raw[:, :w * n * 2]).view('>u2').reshape(-1, w, n)[:, ::step].astype(np.uint16)
    return _unpack(np.ascontiguousarray(raw), bpc, w * n).reshape(-1, w, n)[:, ::step]


def _sample_array(src, filters: list, parms: list, w: int, h: int, n: int, bpc: int, step: int, notes: set):
    """Les échantillons de l'image (filtres défaits) : le lecteur PNG de Qt pour un Flate à prédicteur PNG qui en a
    la forme et n'a pas à être réduit (Qt lirait l'image entière), sinon zlib et numpy."""
    row = (w * n * bpc + 7) // 8
    raw = src.raw()
    if step == 1 and filters and filters[-1] == '/FlateDecode':
        p = parms[-1]
        if _int(p, '/Predictor', 1) >= 10 and _int(p, '/Colors', 1) == n and \
                _int(p, '/BitsPerComponent', 8) == bpc and _int(p, '/Columns', 1) == w:
            s = _png_samples(_unfiltered(raw, filters[:-1], parms[:-1], row * h), w, h, n, bpc)
            if s is not None:
                return s
    data = _unfiltered(raw, filters, parms, row * h)
    if not data:                                         # flux abîmé : rien de décodé
        raise Skipped(tr('Image PDF illisible (données absentes ou abîmées) : ignorée'))
    return _samples(data, w, h, n, bpc, step, notes)


# --- couleurs ------------------------------------------------------------------------------------------------
def _color_space(cs, resources, depth: int = 0) -> tuple[str, int, object]:
    """(genre, nombre de composantes, complément) d'un espace de couleurs : 'gray', 'rgb', 'cmyk', 'ink' (teinte
    d'accompagnement, lue en gris), 'indexed' (complément : (palette RVB (n, 3) uint8, valeur haute))."""
    import numpy as np
    cs = _obj(cs)
    if depth > 4:
        raise Skipped(tr('Image PDF à l’espace de couleurs trop imbriqué : ignorée'))
    if cs is None:
        return 'gray', 1, None
    if isinstance(cs, (list, tuple)) and len(cs) == 1:
        cs = _obj(cs[0])
    if not isinstance(cs, (list, tuple)):
        name = INLINE_VALUES.get(str(cs), str(cs))
        if name in ('/DeviceGray', '/CalGray'):
            return 'gray', 1, None
        if name in ('/DeviceRGB', '/CalRGB'):
            return 'rgb', 3, None
        if name == '/DeviceCMYK':
            return 'cmyk', 4, None
        res = _obj(resources)
        named = _obj(_obj(res.get('/ColorSpace')).get(name)) if res is not None and res.get('/ColorSpace') else None
        if named is not None:                            # image en ligne : nom de la ressource de la page
            return _color_space(named, None, depth + 1)
        raise Skipped(tr('Image PDF à l’espace de couleurs {0} non pris en charge : ignorée').format(name.lstrip('/')))
    kind = str(_obj(cs[0]))
    if kind == '/ICCBased':
        n = _int(_obj(cs[1]), '/N', 3)
        return {1: ('gray', 1, None), 3: ('rgb', 3, None), 4: ('cmyk', 4, None)}.get(n) or \
            _color_space(_obj(cs[1]).get('/Alternate'), resources, depth + 1)
    if kind in ('/CalGray', '/CalRGB'):
        return _color_space(kind, resources, depth + 1)
    if kind in ('/Indexed', '/I'):
        base, bn, _x = _color_space(cs[1], resources, depth + 1)
        if base == 'indexed':
            raise Skipped(tr('Image PDF à palette sur palette : ignorée'))
        hival = max(0, min(255, int(_obj(cs[2]))))
        look = _obj(cs[3])
        look = look.get_data() if hasattr(look, 'get_data') else bytes(look.original_bytes if hasattr(
            look, 'original_bytes') else look)
        look = look + bytes(max(0, (hival + 1) * bn - len(look)))
        pal = np.frombuffer(look[:(hival + 1) * bn], np.uint8).reshape(1, hival + 1, bn)
        return 'indexed', 1, (_to_rgb([pal[..., i] for i in range(bn)], base)[0], hival)
    if kind == '/Separation':
        return 'ink', 1, None
    if kind == '/DeviceN':
        return 'ink', len(_obj(cs[1])), None
    raise Skipped(tr('Image PDF à l’espace de couleurs {0} non pris en charge : ignorée').format(kind.lstrip('/')))


def _to_rgb(comps: list, kind: str):
    """Composantes uint8 (0 → 0, 255 → pleine valeur), une par plan (h, w) → RVB uint8 (h, w, 3), sans flottants."""
    import numpy as np
    if kind == 'gray':
        return np.repeat(comps[0][..., None], 3, axis=2)
    if kind == 'rgb':
        return np.dstack(comps[:3])
    if kind == 'cmyk':
        k = 255 - comps[3].astype(np.uint16)
        return np.dstack([((255 - c.astype(np.uint16)) * k + 127) // 255 for c in comps[:3]]).astype(np.uint8)
    ink = comps[0] if len(comps) == 1 else np.maximum.reduce(comps)    # teinte : 0 = papier, 255 = pleine encre
    return np.repeat((255 - ink)[..., None], 3, axis=2)


def _decode_array(d, n: int, maxv: int, indexed: bool) -> list:
    """Tableau /Decode : [(min, max)] par composante (d'office : [0, 1], ou [0, 2^bpc − 1] pour une palette)."""
    dec = _obj(d.get('/Decode'))
    default = [(0.0, float(maxv) if indexed else 1.0)] * n
    try:
        vals = [float(_obj(x)) for x in dec] if dec is not None else []
    except (TypeError, ValueError):
        return default
    if len(vals) < 2 * n:
        return default
    return [(vals[2 * i], vals[2 * i + 1]) for i in range(n)]


def _lut(d: tuple, maxv: int):
    """Table de correspondance échantillon → composante uint8 selon (min, max) du /Decode."""
    import numpy as np
    v = d[0] + np.arange(maxv + 1, dtype=np.float64) * ((d[1] - d[0]) / maxv)
    return np.clip(np.rint(v * 255), 0, 255).astype(np.uint8)


# --- l'image ---------------------------------------------------------------------------------------------------
class Source:
    """Une image du PDF : son dictionnaire (clés complètes) et ses données encodées (`raw()`)."""

    def __init__(self, dic, raw_fn):
        self.dic = dic
        self.raw = raw_fn

    def get(self, key, default=None):
        return self.dic.get(key, default)


def xobject_source(xo) -> Source:
    """Source d'un XObject /Image (pypdf) : ses données telles qu'écrites (déchiffrées), filtres compris."""
    return Source(xo, lambda: bytes(getattr(xo, '_data', b'') or b''))


def inline_source(operands) -> Source:
    """Source d'une image en ligne (opérandes « INLINE IMAGE » de pypdf : réglages abrégés et données brutes)."""
    settings = operands.get('settings') or {}
    dic = {}
    for k, v in settings.items():
        k = INLINE_KEYS.get(str(k), str(k))
        dic[k] = _names(v) if k == '/Filter' else _obj(v)
    raw = bytes(operands.get('data') or b'')
    return Source(dic, lambda: raw)


def _step(w: int, h: int) -> int:
    """Une ligne et une colonne sur combien, pour rester sous `raster.MAX_PIXELS` (réduction avant les couleurs)."""
    from .raster import MAX_PIXELS
    return max(1, math.ceil(math.sqrt(w * h / MAX_PIXELS))) if w * h > MAX_PIXELS else 1


def decode(src: Source, fill: str | None, resources, notes: set, mask_depth: int = 0):
    """(RVB (h, w, 3) uint8, alpha (h, w) uint8 ou None) d'une image du PDF ; Skipped si elle ne se décode pas."""
    import numpy as np
    w, h = _int(src, '/Width', 0), _int(src, '/Height', 0)
    if w <= 0 or h <= 0:
        raise Skipped(tr('Image PDF sans largeur ou hauteur lisible : ignorée'))
    filters = _names(src.get('/Filter'))
    for f in filters:
        if f in UNSUPPORTED:
            raise Skipped(tr('Image PDF en {0} non décodée : l’exporter en PNG ou JPEG depuis le logiciel d’origine, '
                             'puis l’importer').format(UNSUPPORTED[f]))
    parms = _parms(src, len(filters))
    stencil = _truth(src.get('/ImageMask'))
    bpc = 1 if stencil else _int(src, '/BitsPerComponent', 8)
    kind, n, extra = ('gray', 1, None) if stencil else _color_space(src.get('/ColorSpace'), resources)
    last = filters[-1] if filters else ''
    if w * h > MAX_SAMPLES:
        notes.add(_too_big())
        raise Skipped('')
    alpha, s = None, None
    if last in ('/DCTDecode', '/CCITTFaxDecode'):        # JPEG, fax : Qt (taille réelle lue, réduite au besoin)
        data = _unfiltered(src.raw(), filters[:-1], parms[:-1], MAX_BYTES)
        if last == '/CCITTFaxDecode':
            from pypdf.filters import CCITTFaxDecode
            data = CCITTFaxDecode.decode(data, parms[-1] or None, h)
        q = _qt_decode(data, notes)
        if q is None:
            raise Skipped(tr('Image PDF en fax (CCITT) non décodée : ignorée') if last == '/CCITTFaxDecode'
                          else tr('Image PDF en JPEG illisible : ignorée'))
        if last == '/DCTDecode' and not data.rstrip(b'\0\t\n\f\r ').endswith(b'\xff\xd9'):
            notes.add(tr('Image PDF tronquée : complétée'))       # JPEG sans sa fin : Qt complète le bas en gris
        w, h = q.width(), q.height()                     # celle du JPEG (réduite au besoin), pas celle annoncée
        dec = _decode_array(src, n, 1, False)
        flipped = all(a > b for a, b in dec)
        from PySide6.QtGui import QImage
        if q.format() == QImage.Format.Format_CMYK8888 and flipped:
            px = 255 - _array(q, QImage.Format.Format_CMYK8888, 4)      # CMJN au /Decode inversé
            q = QImage(px.tobytes(), w, h, 4 * w, QImage.Format.Format_CMYK8888).copy()
            dec = [(0.0, 1.0)] * n
        rgb = _array(q, QImage.Format.Format_RGB888, 3)
        if stencil:
            on = rgb[..., 0] < 128                       # sombre = échantillon 0 = peint (d'office)
            rgb, alpha = _stencil(~on if flipped else on, fill)
        elif any(d != (0.0, 1.0) for d in dec) and kind in ('gray', 'rgb'):
            luts = [_lut(dec[min(i, n - 1)], 255) for i in range(3)]     # (gris : la même pour les trois)
            rgb = np.dstack([luts[i][rgb[..., i]] for i in range(3)])
    else:
        if bpc not in (1, 2, 4, 8, 16):
            raise Skipped(tr('Image PDF de {0} bits par composante non prise en charge : ignorée').format(bpc))
        if (w * n * bpc + 7) // 8 * h > MAX_BYTES:
            notes.add(_too_big())
            raise Skipped('')
        step = _step(w, h)
        if step > 1:
            notes.add(_reduced())
        s = _sample_array(src, filters, parms, w, h, n, bpc, step, notes)
        h, w = s.shape[:2]
        maxv = (1 << bpc) - 1
        dec = _decode_array(src, n, maxv, kind == 'indexed')
        if stencil:                                      # masque 1 bit : peint là où l'échantillon vaut 0
            rgb, alpha = _stencil(s[..., 0] == (1 if dec[0][0] > dec[0][1] else 0), fill)
        elif kind == 'indexed':
            pal, hival = extra
            lo, hi = dec[0]
            idx = np.clip(np.rint(lo + np.arange(maxv + 1) * ((hi - lo) / maxv)), 0, hival).astype(np.intp)
            rgb = pal[idx[s[..., 0]]]
        else:
            rgb = _to_rgb([_lut(dec[i], maxv)[s[..., i]] for i in range(n)], kind)
        mask = _obj(src.get('/Mask'))
        if isinstance(mask, (list, tuple)) and not stencil:     # plage de couleurs transparente (échantillons bruts)
            try:
                r = [int(_obj(x)) for x in mask][:2 * n]
                hit = np.ones((h, w), bool)
                for i in range(n):
                    hit &= (s[..., i] >= r[2 * i]) & (s[..., i] <= r[2 * i + 1])
                alpha = np.where(hit, 0, 255).astype(np.uint8)
            except (TypeError, ValueError, IndexError):
                notes.add(tr('Masque de couleurs d’une image PDF illisible : ignoré'))
    rgb = np.ascontiguousarray(rgb, np.uint8)
    for key, soft in (('/SMask', True), ('/Mask', False)):
        mo = _obj(src.get(key))
        if mo is None or isinstance(mo, (list, tuple)) or not hasattr(mo, 'get') or mask_depth:
            continue
        try:
            if soft:
                a_rgb, _a = decode(xobject_source(mo), None, None, notes, mask_depth + 1)
                a = a_rgb[..., 0]
            else:                                        # masque dur (un /ImageMask) : 0 = montré, 1 = caché (d'office)
                a_rgb, a_on = decode(xobject_source(mo), '#000000', None, notes, mask_depth + 1)
                a = a_on if a_on is not None else 255 - a_rgb[..., 0]
        except Exception:                                # noqa: BLE001 — masque abîmé : image sans masque
            notes.add(tr('Masque d’une image PDF illisible : image gardée sans lui'))
            continue
        if a.shape != (h, w):                            # masque d'une autre taille : au plus proche
            a = a[np.arange(h) * a.shape[0] // h][:, np.arange(w) * a.shape[1] // w]
        alpha = a if alpha is None else np.minimum(alpha, a)
    return rgb, (None if alpha is None else np.ascontiguousarray(alpha, np.uint8))


def _stencil(on, fill: str | None):
    """Masque 1 bit (/ImageMask) → (RVB de la couleur de fond courante, alpha : opaque là où il peint)."""
    import numpy as np
    from .colors import rgb_of
    try:
        color = rgb_of(fill or '#000000')
    except ValueError:                                   # couleur illisible : noir
        color = (0, 0, 0)
    rgb = np.empty(on.shape + (3,), np.uint8)
    rgb[...] = color
    return rgb, np.where(on, 255, 0).astype(np.uint8)


def to_png(rgb, alpha) -> bytes:
    """PNG des pixels (avec alpha s'il y en a une)."""
    from PySide6.QtCore import QBuffer, QIODevice
    from PySide6.QtGui import QImage
    from .raster import _app
    _app()
    h, w = rgb.shape[:2]
    if alpha is not None and (alpha != 255).any():
        import numpy as np
        px = np.ascontiguousarray(np.dstack([rgb, alpha]), np.uint8)
        q = QImage(px.data, w, h, 4 * w, QImage.Format.Format_RGBA8888).copy()
    else:
        q = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    q.save(buf, 'PNG')
    return bytes(buf.data())


def image_item(src: Source, ctm: Affine, fill: str | None, resources, report: list, name: str = '',
               cache: dict | None = None, key=None) -> Image | None:
    """L'objet Image du dessin pour une image du PDF peinte sous la matrice `ctm` (carré unité de l'image → mm du
    dessin) ; None si elle ne se décode pas (la raison va dans `report`, une seule fois) ou n'a pas de surface.
    `cache`, `key` : la même image (même XObject, même couleur de fond) n'est décodée qu'une fois par import, et
    ses copies partagent les mêmes données."""
    m = ctm @ FLIP
    if abs(m.a * m.d - m.b * m.c) < 1e-12:
        return None                                      # image écrasée en un trait : rien à poser
    if cache is not None and key is not None and key in cache:
        data = cache[key]
    else:
        notes: set = set()
        try:
            rgb, alpha = decode(src, fill, resources, notes)
            data = to_png(rgb, alpha)
        except Skipped as ex:
            if str(ex):
                notes.add(str(ex))
            data = None
        except Exception:                                # noqa: BLE001 — image abîmée : le reste du PDF est lu
            notes.add(tr('Image PDF illisible (données abîmées) : ignorée'))
            data = None
        for t in sorted(notes):
            if t not in report:
                report.append(t)
        if cache is not None and key is not None:
            cache[key] = data
    if data is None:
        return None
    return Image(data=data, fmt='png', matrix=m, name=name)
