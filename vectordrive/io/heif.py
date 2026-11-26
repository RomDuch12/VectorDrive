"""Images HEIC, HEIF et AVIF (photos des téléphones) : lues par le décodeur que le poste a déjà, rien d'embarqué.

Qt ne les lit pas sous Windows (PySide6 n'a pas de module d'images HEIF). Dans l'ordre :

1. Qt lui-même, s'il a un jour un module pour ce format (kimageformats…) : `raster.load_image` le sert alors comme
   un PNG (`qt_reads`) ;
2. Pillow, s'il est installé : avec pillow-heif (HEIC, HEIF) ; seul à partir de la version 11.3 (AVIF). Jamais exigé
   ni embarqué — les roues de pillow-heif sont sous GPL-2.0 (encodeur x265 inclus) ; importé par `importlib`, pour
   que l'empaquetage ne l'emporte pas ;
3. le décodeur de Windows (WIC), avec les « Extensions d’image HEIF » et « Extensions vidéo HEVC » (ou « Extension
   vidéo AV1 » pour l'AVIF) du Microsoft Store, souvent déjà là : interfaces COM appelées à la main (ctypes), comme
   `core.spell`.

Aucun : `DecoderMissing` (une ValueError), qui dit quoi installer — jamais de plantage. Toujours l'image principale
du fichier (la première d'une séquence ou d'une rafale), ramenée en sRGB quand elle porte un profil ICC (Display P3
des iPhone…). Redressée une seule fois, par le décodeur : WIC et libheif (pillow-heif) appliquent eux-mêmes la
rotation et le miroir du HEIF (irot/imir) ; Pillow seul (AVIF) les rend en orientation EXIF, que `exif_transpose`
applique. Rien n'est tourné ici en plus (la norme HEIF dit d'ignorer l'orientation EXIF : double rotation sinon)."""
from __future__ import annotations

import ctypes
import importlib
import math
import pathlib
import sys

from ..i18n import tr

#: extensions lues ici quand Qt ne sait pas les lire
HEIF_EXT = ('.heic', '.heif', '.avif')
#: au-delà, une image n'est pas décodée (comme `raster.render`) : 1,6 Go de pixels
MAX_DECODED = 400_000_000


class DecoderMissing(ValueError):
    """Aucun décodeur pour ce format sur le poste : le message dit lequel installer."""


def is_heif(path) -> bool:
    return pathlib.Path(str(path)).suffix.lower() in HEIF_EXT


def kind(path) -> str:
    """'HEIC', 'HEIF' ou 'AVIF' : le nom du format, pour les messages."""
    return pathlib.Path(str(path)).suffix.lower().lstrip('.').upper() or 'HEIC'


def qt_reads(path) -> bool:
    """Qt a-t-il un module d'images pour ce format ? (aucun sous Windows aujourd'hui)"""
    from PySide6.QtGui import QImageReader
    fmt = pathlib.Path(str(path)).suffix.lower().lstrip('.').encode()
    return fmt in {bytes(f).lower() for f in QImageReader.supportedImageFormats()}


def missing_message(path) -> str:
    """Le message quand rien ne lit ce format : quoi installer."""
    name = pathlib.Path(str(path)).name
    if getattr(sys, 'frozen', False):                    # portable : elle ne voit pas le Pillow du poste
        if kind(path) == 'AVIF':
            return tr('Format AVIF : décodeur absent, installez l’« Extension vidéo AV1 » du Microsoft Store : '
                      '{0}').format(name)
        return tr('Format {0} : décodeur absent, installez les « Extensions d’image HEIF » et « Extensions vidéo '
                  'HEVC » du Microsoft Store : {1}').format(kind(path), name)
    if kind(path) == 'AVIF':
        return tr('Format AVIF : décodeur absent, installez l’« Extension vidéo AV1 » du Microsoft Store '
                  '(ou le module Python Pillow 11.3 ou plus récent) : {0}').format(name)
    return tr('Format {0} : décodeur absent, installez les « Extensions d’image HEIF » et « Extensions vidéo HEVC » '
              'du Microsoft Store (ou le module Python pillow-heif) : {1}').format(kind(path), name)


# --- après le décodage : en sRGB -----------------------------------------------------------------------------

def to_srgb(img, icc: bytes | None):
    """L'image ramenée en sRGB d'après son profil ICC (sans profil, ou profil illisible : telle quelle)."""
    if not icc:
        return img
    from PySide6.QtCore import QByteArray
    from PySide6.QtGui import QColorSpace
    try:
        cs = QColorSpace.fromIccProfile(QByteArray(bytes(icc)))
        srgb = QColorSpace(QColorSpace.NamedColorSpace.SRgb)
        if not cs.isValid() or cs == srgb:
            return img
        img.setColorSpace(cs)
        out = img.convertedToColorSpace(srgb)
        return img if out.isNull() else out
    except Exception:                                    # noqa: BLE001 — profil inattendu : couleurs d'origine
        return img


# --- les décodeurs : chacun rend (QImage déjà redressée, profil ICC ou None) ; None s'il est absent -------------

def _pillow(path):
    """Pillow (+ pillow-heif) s'ils sont installés et lisent ce format, sinon None."""
    try:
        Image = importlib.import_module('PIL.Image')
        ImageOps = importlib.import_module('PIL.ImageOps')
    except Exception:                                    # noqa: BLE001 — pas de Pillow : décodeur absent
        return None
    if kind(path) != 'AVIF':
        try:
            importlib.import_module('pillow_heif').register_heif_opener()
        except Exception:                                # noqa: BLE001 — pas de pillow-heif
            return None
    if pathlib.Path(str(path)).suffix.lower() not in Image.registered_extensions():
        return None                                      # Pillow sans AVIF (avant 11.3)
    from PySide6.QtGui import QImage
    with Image.open(str(path)) as im:
        im.seek(0)                                       # l'image principale (séquence, rafale)
        w, h = im.size
        if not w or not h or w * h > MAX_DECODED:       # avant toute copie des pixels
            raise ValueError(f'{w} × {h} px')
        icc = im.info.get('icc_profile')
        dpi = im.info.get('dpi')
        # pillow-heif applique irot/imir au décodage et remet l'orientation EXIF à 1 : ici sans effet ; Pillow seul
        # (AVIF) rend irot/imir en orientation EXIF, appliquée ici — une seule fois dans les deux cas
        im = ImageOps.exif_transpose(im)
        im = im.convert('RGBA')
        w, h = im.size
        q = QImage(im.tobytes('raw', 'RGBA'), w, h, 4 * w, QImage.Format.Format_RGBA8888).copy()
    try:
        dx, dy = (float(v) for v in dpi)
    except (TypeError, ValueError):                      # pas de résolution dans le fichier
        dx = dy = 0.0
    if dx > 1 and dy > 1:
        q.setDotsPerMeterX(round(dx / 0.0254))
        q.setDotsPerMeterY(round(dy / 0.0254))
    return q, icc


class _GUID(ctypes.Structure):
    _fields_ = [('a', ctypes.c_ulong), ('b', ctypes.c_ushort), ('c', ctypes.c_ushort), ('d', ctypes.c_ubyte * 8)]

    @classmethod
    def parse(cls, text: str) -> '_GUID':
        h = text.strip('{}').replace('-', '')
        return cls(int(h[:8], 16), int(h[8:12], 16), int(h[12:16], 16), (ctypes.c_ubyte * 8)(*bytes.fromhex(h[16:])))


CLSID_WIC_FACTORY = '{cacaf262-9370-4615-a13b-9f5539da4c0a}'
IID_WIC_FACTORY = '{ec5ec8a9-c395-4314-9c77-54d7a935ff70}'
PIXEL_BGRA = '{6fddc324-4e03-4bfe-b185-3d77768dc90f}'    # GUID_WICPixelFormat32bppBGRA = QImage ARGB32
CONTAINER_HEIF = '{e1e62521-6787-405b-a339-500715b5763f}'  # GUID_ContainerFormatHeif
#: « pas de décodeur » : format inconnu de WIC, ou extension HEIF sans le décodeur vidéo HEVC (AV1)
WIC_ABSENT = {0x88982F50, 0x88982F07, 0xC00D5212}
#: parmi eux, « composant introuvable » et « format inconnu » : si le décodeur HEIF est là, c'est le fichier qui est
#: abîmé ; 0xC00D5212 (MF_E_TOPO_CODEC_NOT_FOUND : HEVC ou AV1 manquant) reste « décodeur absent »
WIC_NOT_RECOGNIZED = {0x88982F50, 0x88982F07}
# Orientation : le décodeur HEIF de WIC rend les pixels déjà tournés (irot/imir appliqués ; constaté sous Windows 11,
# extension HEIF 1.2 : `/heifProps/{ushort=1}` vaut alors 1). Cette propriété n'est donc pas lue : double rotation.


def _method(obj, index: int, restype, *argtypes):
    """Méthode n° `index` de la table de l'objet COM `obj`, prête à appeler."""
    vtable = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    fn = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)(vtable[index])
    return lambda *a: fn(obj, *a)


def _release(*objs) -> None:
    for o in objs:
        if o:
            _method(o, 2, ctypes.c_ulong)()


class _WicError(ValueError):
    def __init__(self, what: str, hr: int):
        self.hr = hr & 0xFFFFFFFF
        super().__init__(f'{what} : 0x{self.hr:08X}')


def _ok(hr: int, what: str) -> None:
    if hr < 0:
        raise _WicError(what, hr)


def _wic_icc(factory, frame) -> bytes | None:
    """Le profil ICC de l'image (le premier), ou None."""
    P = ctypes.POINTER
    n = ctypes.c_uint(0)
    get = _method(frame, 9, ctypes.c_long, ctypes.c_uint, P(ctypes.c_void_p), P(ctypes.c_uint))
    if get(0, None, ctypes.byref(n)) < 0 or not n.value:
        return None
    ctx = (ctypes.c_void_p * n.value)()
    create = _method(factory, 15, ctypes.c_long, P(ctypes.c_void_p))
    try:
        for i in range(n.value):
            c = ctypes.c_void_p()
            _ok(create(ctypes.byref(c)), 'CreateColorContext')
            ctx[i] = c.value
        got = ctypes.c_uint(0)
        if get(n.value, ctx, ctypes.byref(got)) < 0:
            return None
        for i in range(min(got.value, n.value)):
            c = ctx[i]
            t = ctypes.c_int(0)
            if not c or _method(c, 6, ctypes.c_long, P(ctypes.c_int))(ctypes.byref(t)) < 0 or t.value != 1:
                continue                                 # 1 : WICColorContextProfile (2 : espace EXIF)
            size = ctypes.c_uint(0)
            prof = _method(c, 7, ctypes.c_long, ctypes.c_uint, ctypes.c_void_p, P(ctypes.c_uint))
            if prof(0, None, ctypes.byref(size)) < 0 or not size.value:
                continue
            buf = ctypes.create_string_buffer(size.value)
            if prof(size.value, buf, ctypes.byref(size)) >= 0:
                return buf.raw[:size.value]
    finally:
        _release(*[ctx[i] for i in range(n.value)])
    return None


def _wic_has_heif(factory) -> bool:
    """WIC a-t-il un décodeur HEIF (les « Extensions d’image HEIF ») ?"""
    dec = ctypes.c_void_p()
    g = _GUID.parse(CONTAINER_HEIF)
    hr = _method(factory, 7, ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(
        ctypes.byref(g), None, ctypes.byref(dec))
    _release(dec)
    return hr >= 0 and bool(dec)


def _wic(path):
    """Le décodeur de Windows (WIC) ; None hors de Windows, ou sans décodeur pour ce format."""
    if sys.platform != 'win32':
        return None
    from PySide6.QtGui import QImage
    P = ctypes.POINTER
    ole32 = ctypes.windll.ole32
    init = ole32.CoInitializeEx(None, 2)                 # COINIT_APARTMENTTHREADED ; déjà fait par Qt : sans effet
    factory, decoder, frame, conv = ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p()
    try:
        clsid, iid = _GUID.parse(CLSID_WIC_FACTORY), _GUID.parse(IID_WIC_FACTORY)
        if ole32.CoCreateInstance(ctypes.byref(clsid), None, 1, ctypes.byref(iid), ctypes.byref(factory)) < 0:
            return None                                  # pas de WIC (Windows sans composants d'images)
        try:
            hr = _method(factory, 3, ctypes.c_long, ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int,
                         P(ctypes.c_void_p))(str(path), None, 0x80000000, 0, ctypes.byref(decoder))
            if hr < 0 and (hr & 0xFFFFFFFF) in WIC_NOT_RECOGNIZED and _wic_has_heif(factory):
                raise ValueError(f'contenu non reconnu (0x{hr & 0xFFFFFFFF:08X})')   # décodeur là : fichier abîmé
            _ok(hr, 'décodeur')
            _ok(_method(decoder, 13, ctypes.c_long, ctypes.c_uint, P(ctypes.c_void_p))(0, ctypes.byref(frame)),
                'image')
            w, h = ctypes.c_uint(0), ctypes.c_uint(0)
            _ok(_method(frame, 3, ctypes.c_long, P(ctypes.c_uint), P(ctypes.c_uint))(ctypes.byref(w), ctypes.byref(h)),
                'taille')
            if not w.value or not h.value or w.value * h.value > MAX_DECODED:
                raise ValueError(f'{w.value} × {h.value} px')
            convert = ctypes.windll.windowscodecs.WICConvertBitmapSource
            convert.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
            convert.restype = ctypes.c_long
            fmt = _GUID.parse(PIXEL_BGRA)
            _ok(convert(ctypes.byref(fmt), frame, ctypes.byref(conv)), 'conversion')
            q = QImage(w.value, h.value, QImage.Format.Format_ARGB32)
            if q.isNull():
                raise ValueError(f'mémoire insuffisante pour {w.value} × {h.value} px')
            bits = q.bits()                              # les pixels copiés droit dans la QImage, sans tampon
            dst = None
            try:
                dst = (ctypes.c_char * q.sizeInBytes()).from_buffer(bits)
                hr = _method(conv, 7, ctypes.c_long, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p)(
                    None, q.bytesPerLine(), q.sizeInBytes(), dst)
            finally:
                dst = None                               # rend la vue avant release() (sinon BufferError)
                bits.release()
            _ok(hr, 'pixels')                            # WIC décode ici : HEVC (AV1) absent se voit à ce moment
        except _WicError as ex:
            if ex.hr in WIC_ABSENT:
                return None
            raise
        dpi_x, dpi_y = ctypes.c_double(0), ctypes.c_double(0)
        if _method(frame, 5, ctypes.c_long, P(ctypes.c_double), P(ctypes.c_double))(
                ctypes.byref(dpi_x), ctypes.byref(dpi_y)) >= 0 and dpi_x.value > 1 and dpi_y.value > 1:
            q.setDotsPerMeterX(round(dpi_x.value / 0.0254))
            q.setDotsPerMeterY(round(dpi_y.value / 0.0254))
        try:
            icc = _wic_icc(factory, frame)
        except Exception:                                # noqa: BLE001 — sans profil : couleurs d'origine
            icc = None
        return q, icc                                    # déjà redressée par WIC
    finally:
        _release(conv, frame, decoder, factory)
        if init in (0, 1):                               # S_OK, S_FALSE : rendu ; RPC_E_CHANGED_MODE : pas à nous
            ole32.CoUninitialize()


#: (nom, fonction) dans l'ordre d'essai — remplaçable dans les essais
DECODERS = [('Pillow', _pillow), ('Windows', _wic)]


#: taille des fichiers déjà décodés : {(chemin, date, octets): (largeur, hauteur)} — la fenêtre Photo la redemande
#: à chaque changement d'un champ
_SIZES: dict = {}


def _stamp(p: pathlib.Path):
    st = p.stat()
    return str(p), st.st_mtime_ns, st.st_size


def _read(path):
    """(QImage redressée, profil ICC ou None) par le premier décodeur qui lit le fichier ; mêmes erreurs que
    `decode`."""
    p = pathlib.Path(str(path))
    if not p.is_file():
        raise FileNotFoundError(tr('Fichier introuvable : {0}').format(p))
    errors = []
    for name, fn in DECODERS:
        try:
            got = fn(str(p))
        except Exception as ex:                          # noqa: BLE001 — le suivant essaie ; la raison est gardée
            errors.append(f'{name} : {ex}')
            continue
        if got is None:
            continue
        img, icc = got
        if img is None or img.isNull():
            errors.append(f'{name} : image vide')
            continue
        if len(_SIZES) > 64:
            _SIZES.clear()
        _SIZES[_stamp(p)] = (img.width(), img.height())
        return img, icc                                  # redressée par le décodeur : pas une 2e fois
    if errors:
        raise ValueError(tr('Image {0} illisible : {1} ({2})').format(kind(p), p.name, ' ; '.join(errors)))
    raise DecoderMissing(missing_message(p))


def decode(path):
    """QImage d'un HEIC, HEIF ou AVIF : la première image, redressée, en sRGB. `DecoderMissing` si rien ne lit ce
    format sur le poste ; ValueError si le fichier est abîmé ; OSError s'il est absent."""
    return to_srgb(*_read(path))


def load(path, cap: int):
    """Comme `raster.load_image` : (image, taille d'origine en px, remarque ou None), réduite au-delà de `cap`
    pixels (0 : jamais) avant la conversion en sRGB (une seule grande image en mémoire à la fois)."""
    from PySide6.QtCore import Qt
    img, icc = _read(path)
    size = img.size()
    note = None
    if cap and size.width() * size.height() > cap:
        k = math.sqrt(cap / (size.width() * size.height()))
        w, h = max(1, int(size.width() * k)), max(1, int(size.height() * k))
        dpm = (img.dotsPerMeterX(), img.dotsPerMeterY())
        img = img.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        img.setDotsPerMeterX(dpm[0])
        img.setDotsPerMeterY(dpm[1])
        note = f'image réduite de {size.width()} × {size.height()} à {w} × {h} px à l\'ouverture'
    return to_srgb(img, icc), size, note


def pixel_size(path) -> tuple[int, int]:
    """(largeur, hauteur) de l'image redressée ; décodée une fois tant que le fichier ne change pas. Mêmes erreurs
    que `decode`."""
    p = pathlib.Path(str(path))
    try:
        got = _SIZES.get(_stamp(p))
    except OSError:
        got = None
    if got is None:
        img, _icc = _read(p)
        got = (img.width(), img.height())
    return got


def problem(path) -> str:
    """'' si le fichier se lit (ou n'est pas un HEIC, HEIF, AVIF) ; sinon le message à montrer."""
    if not is_heif(path):
        return ''
    try:
        if qt_reads(path):
            return ''
        decode(path)
    except (ValueError, OSError) as ex:
        return str(ex)
    return ''
