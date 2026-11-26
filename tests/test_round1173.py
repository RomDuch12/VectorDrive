"""Round 1173 (demande : « compatibilité heic. ») : HEIC, HEIF et AVIF lus partout où le PNG et le JPEG le sont.
Aucun essai ne dépend d'un décodeur réel (simulé) ; ceux qui en essaient un vrai sont sautés s'il est absent."""
import ctypes
import os
import pathlib
import shutil
import sys
import tempfile
import types
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'rheic.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtGui import QColor, QColorSpace, QImage  # noqa: E402
from PySide6.QtWidgets import QApplication, QComboBox, QFileDialog, QMessageBox  # noqa: E402

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Image, Shape  # noqa: E402
from vectordrive.io import registry  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : HEIC, HEIF et AVIF n’étaient lus nulle part (« format non pris en charge »)'


def heif():
    from vectordrive.io import heif as H                 # avant : module absent
    return H


def picture(w=200, h=100, dpi=100.0):
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(QColor('red'))
    for y in range(h):
        for x in range(w // 2, w):
            img.setPixelColor(x, y, QColor('blue'))
    img.setDotsPerMeterX(round(dpi / 0.0254))
    img.setDotsPerMeterY(round(dpi / 0.0254))
    return img


def fake(img, icc=None):
    """Un décodeur simulé : rend toujours cette image (déjà redressée, comme WIC et pillow-heif)."""
    return lambda path: (QImage(img), icc)


def asymmetric(w, h, base=0):
    """Une petite image dont chaque pixel a sa couleur : toute rotation ou miroir se voit."""
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    for y in range(h):
        for x in range(w):
            img.setPixelColor(x, y, QColor(40 + 80 * x, 60 + 60 * y, 9 + base))
    return img


def hook(H, index, nargs, hr):
    """`_method` où la méthode COM n° `index` (à `nargs` paramètres) rend `hr` sans appeler WIC."""
    real = H._method

    def method(obj, i, restype, *argtypes):
        if i == index and len(argtypes) == nargs:
            return lambda *a: hr
        return real(obj, i, restype, *argtypes)
    return mock.patch.object(H, '_method', method)


def signed(hr):
    return hr - (1 << 32)                                # un HRESULT d'échec, tel que ctypes le rend (c_long)


def same_pixels(test, got, want):
    test.assertEqual((got.width(), got.height()), (want.width(), want.height()))
    for y in range(want.height()):
        for x in range(want.width()):
            test.assertEqual(got.pixelColor(x, y).name(), want.pixelColor(x, y).name(), (x, y))


def absent(path):
    return None


def broken(path):
    raise ValueError('flux abîmé')


class Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def file(self, name='photo.heic'):
        p = self.tmp / name
        p.write_bytes(b'ftypheic, simule')                # le décodeur est simulé : le contenu ne compte pas
        return str(p)

    def decoders(self, *fns):
        """Les décodeurs du poste remplacés par ceux-là (Qt sans module HEIF, comme sous Windows)."""
        H = heif()
        for p in (mock.patch.object(H, 'DECODERS', [(f'd{i}', f) for i, f in enumerate(fns)]),
                  mock.patch.object(H, 'qt_reads', lambda path: False)):
            p.start()
            self.addCleanup(p.stop)
        return H


class Filters(unittest.TestCase):
    def test_open_and_import_filters(self):
        heif()
        f = registry.by_extension('C:/photos/IMG_0001.HEIC')
        self.assertIsNotNone(f, BEFORE)
        self.assertEqual(f.key, 'image')                 # une image comme les autres (pas un dessin, pas un logo tracé)
        self.assertIsNotNone(f.reader)
        for ext in ('.heic', '.heif', '.avif'):
            self.assertIsNotNone(registry.by_extension('a' + ext))
            self.assertIsNone(registry.writer_for('a' + ext))           # jamais écrit
            self.assertIn('*' + ext, registry.filter_string())          # Ouvrir, Importer
            self.assertNotIn('*' + ext, registry.filter_string(write=True))
        self.assertNotIn('.heic', [e for f in registry.save_formats() for e in f.extensions])

    def test_browser_logo_and_option_filters(self):
        heif()
        from vectordrive.io import proof, raster
        from vectordrive.ui import file_browser as FB, font_recognize, options, symbols
        self.assertIn('.heic', FB.BROWSER_EXT)
        table = dict(FB.filters())
        self.assertIn('.heic', table['Images'])
        self.assertNotIn('.heic', table['Autres dessins (HPGL, EMF, WMF, CorelDRAW, Visio…)'])
        self.assertIn('.avif', font_recognize.IMAGE_EXT)
        self.assertIn('*.heic', proof.logo_filter().split())
        self.assertFalse(proof.is_vector_logo('logo.heic'))             # un logo HEIC : une image
        self.assertIn('.heif', symbols.logo_exts())                     # « Logos BAT » de la bibliothèque interne
        self.assertIn('*.heic', options.BY_KEY['bat/logo'].extra['filter'])
        self.assertEqual(raster.IMAGE_EXT[-3:], ('.heic', '.heif', '.avif'))
        self.assertIn('*.png', raster.image_patterns().split())

    def test_dialog_filters(self):
        heif()
        from vectordrive.ui import batdialog, dialogs, path_report as PR
        asked = []

        def ask(*a, **k):
            asked.append(a[3])
            return '', ''
        with mock.patch.object(QFileDialog, 'getOpenFileName', ask):
            d = dialogs.HalftoneDialog()                 # Photo (trame)
            d._browse()
            r = PR.PathReportDialog(None)                # image du rapport de parcours
            r._image_toggled(True)
            box = QComboBox()
            box.addItem('', '')
            box.addItem('Choisir un fichier…', '?')
            batdialog.BatDialog._pick_logo(types.SimpleNamespace(set_logo=mock.Mock()), box, 1)   # logo du BAT
        self.assertEqual(len(asked), 3)
        for f in asked:
            self.assertIn('*.heic', f, BEFORE)
            self.assertIn('*.jpg', f)
        d.close()
        r.close()


class Decoding(Tmp):
    def test_opened_like_a_png(self):
        self.decoders(fake(picture(200, 100, dpi=100.0)))
        doc = registry.open_document(self.file())
        ims = [it for L in doc.layers for it in L.items if isinstance(it, Image)]
        self.assertEqual(len(ims), 1)
        self.assertEqual(ims[0].fmt, 'png')                       # rangée en PNG : relue partout, sans décodeur
        self.assertAlmostEqual(ims[0].matrix.a, 50.8, places=3)   # 200 px à 100 dpi
        self.assertAlmostEqual(abs(ims[0].matrix.d), 25.4, places=3)
        self.assertEqual(doc.source_format, 'image')
        self.assertIn('image 200 × 100 px', doc.report[0])
        from vectordrive.io import raster
        q = raster.qimage_of(ims[0])
        self.assertEqual(q.pixelColor(10, 50).name(), '#ff0000')
        self.assertEqual(q.pixelColor(190, 50).name(), '#0000ff')

    def test_turned_once(self):
        # WIC et pillow-heif rendent l'image déjà redressée : rendue telle quelle, pixel pour pixel (pas de 2e tour)
        src = asymmetric(3, 2)
        H = self.decoders(fake(src))
        same_pixels(self, H.decode(self.file()), src)
        # Pillow seul (AVIF) : l'orientation EXIF appliquée une fois par exif_transpose, rien de plus ensuite
        upright = asymmetric(2, 3, base=100).convertToFormat(QImage.Format.Format_RGBA8888)
        raw = bytes(upright.constBits())[:upright.sizeInBytes()]
        turned = []

        class Im:                                        # une image Pillow simulée
            def __init__(self, size, data, info):
                self.size, self.data, self.info = size, data, info

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def seek(self, n):
                self.seeked = n

            def convert(self, mode):
                self.mode = mode
                return self

            def tobytes(self, *a):
                return self.data

        def exif_transpose(im):                          # 3 × 2 + orientation 6 → 2 × 3 redressée
            turned.append(im.size)
            return Im((2, 3), raw, {})

        opened = Im((3, 2), b'\0' * 24, {'dpi': (300.0, 300.0)})
        mods = {'PIL.Image': types.SimpleNamespace(registered_extensions=lambda: {'.avif': 'AVIF'},
                                                   open=lambda path: opened),
                'PIL.ImageOps': types.SimpleNamespace(exif_transpose=exif_transpose)}
        self.decoders(H._pillow)

        def imp(name):
            if name not in mods:
                raise ImportError(name)
            return mods[name]
        with mock.patch.object(H.importlib, 'import_module', imp):
            got = H.decode(self.file('photo.avif'))
        self.assertEqual(turned, [(3, 2)])                              # une fois, sur l'image du fichier
        self.assertEqual(opened.seeked, 0)                              # l'image principale
        same_pixels(self, got, upright)                                 # pas retournée une 2e fois après Pillow
        self.assertEqual(got.dotsPerMeterX(), round(300 / 0.0254))      # résolution lue par Pillow
        self.assertEqual(got.dotsPerMeterY(), round(300 / 0.0254))
        with mock.patch.object(H.importlib, 'import_module', imp):
            self.assertIsNone(H._pillow(self.file('photo.heic')))      # HEIC sans pillow-heif : pas Pillow
        with mock.patch.object(H.importlib, 'import_module', imp), mock.patch.object(H, 'MAX_DECODED', 5):
            with self.assertRaises(ValueError) as cm:
                H._pillow(self.file('photo.avif'))                      # trop grande : refusée avant toute copie
        self.assertIn('3 × 2 px', str(cm.exception))
        self.assertEqual(turned, [(3, 2)])

    def test_wic_absent_or_damaged(self):
        if sys.platform != 'win32':
            self.skipTest('Windows seulement')
        H = self.decoders(heif()._wic)
        p = self.file()
        with mock.patch.object(H, '_wic_has_heif', lambda factory: True):
            with hook(H, 3, 5, signed(0x88982F50)):                     # décodeur HEIF là, contenu non reconnu
                with self.assertRaises(ValueError) as cm:
                    H.decode(p)
            self.assertNotIsInstance(cm.exception, H.DecoderMissing)    # fichier abîmé
            self.assertIn('contenu non reconnu (0x88982F50)', str(cm.exception))
            with hook(H, 3, 5, signed(0xC00D5212)):                     # HEVC (AV1) manquant : pas « abîmé »
                self.assertIsNone(H._wic(p))
                with self.assertRaises(H.DecoderMissing) as cm:
                    H.decode(p)
            self.assertIn('Extensions vidéo HEVC', str(cm.exception))
        with mock.patch.object(H, '_wic_has_heif', lambda factory: False), hook(H, 3, 5, signed(0x88982F50)):
            self.assertIsNone(H._wic(p))                                # sans extension HEIF : décodeur absent

    def test_color_profile_to_srgb(self):
        p3 = bytes(QColorSpace(QColorSpace.NamedColorSpace.DisplayP3).iccProfile())
        img = QImage(4, 4, QImage.Format.Format_ARGB32)
        img.fill(QColor(200, 60, 40))
        H = self.decoders(fake(img, icc=p3))
        got = H.decode(self.file())
        self.assertNotEqual(got.pixelColor(1, 1).name(), QColor(200, 60, 40).name())   # P3 → sRGB : plus saturé
        self.assertGreater(got.pixelColor(1, 1).red(), 200)
        self.assertEqual(got.colorSpace(), QColorSpace(QColorSpace.NamedColorSpace.SRgb))
        H = self.decoders(fake(img, icc=b'pas un profil'))
        self.assertEqual(H.decode(self.file()).pixelColor(1, 1).name(), QColor(200, 60, 40).name())

    def test_next_decoder_and_unreadable(self):
        H = self.decoders(absent, broken, fake(picture(20, 10)))
        self.assertEqual(H.decode(self.file()).size().width(), 20)      # absent, puis abîmé : le suivant
        H = self.decoders(absent, broken)
        with self.assertRaises(ValueError) as cm:
            H.decode(self.file())
        self.assertNotIsInstance(cm.exception, H.DecoderMissing)        # un décodeur l'a lu : le fichier est abîmé
        self.assertIn('flux abîmé', str(cm.exception))
        self.assertIn('photo.heic', str(cm.exception))
        with self.assertRaises(OSError):
            H.decode(str(self.tmp / 'absent.heic'))

    def test_big_photo_reduced(self):
        calls = []
        dec = fake(picture(400, 300), icc=bytes(QColorSpace(QColorSpace.NamedColorSpace.DisplayP3).iccProfile()))
        H = self.decoders(lambda path: calls.append(path) or dec(path))
        from vectordrive.io import raster
        converted = []
        real_srgb = H.to_srgb
        p = self.file()
        with mock.patch.object(H, 'to_srgb', lambda img, icc: converted.append(img.size()) or real_srgb(img, icc)):
            img, orig, note = raster.load_image(p, max_pixels=12_000)
        self.assertEqual((orig.width(), orig.height()), (400, 300))
        self.assertLessEqual(img.width() * img.height(), 12_000)
        self.assertEqual(converted, [img.size()])                      # réduite d'abord, convertie en sRGB ensuite
        self.assertEqual(img.colorSpace(), QColorSpace(QColorSpace.NamedColorSpace.SRgb))
        self.assertIn('400 × 300', note)
        # Photo (trame) redemande la taille à chaque changement d'un champ : décodée une fois par version du fichier
        del calls[:]
        q = self.tmp / 'autre.heic'
        q.write_bytes(b'ftypheic, simule')
        for _ in range(3):
            self.assertEqual(raster.pixel_size(str(q)), (400, 300))
        self.assertEqual(len(calls), 1)
        self.assertEqual(raster.pixel_size(p), (400, 300))              # déjà décodée par load_image
        self.assertEqual(len(calls), 1)
        st = q.stat()
        os.utime(q, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))   # fichier changé : relu
        self.assertEqual(raster.pixel_size(str(q)), (400, 300))
        self.assertEqual(len(calls), 2)
        self.assertFalse(raster.read_qimage(p).isNull())

    def test_optional_decoders_absent(self):
        H = heif()
        p = self.file()
        with mock.patch.object(H.importlib, 'import_module', side_effect=ImportError('pas de Pillow')):
            self.assertIsNone(H._pillow(p))
        with mock.patch.object(H.sys, 'platform', 'linux'):
            self.assertIsNone(H._wic(p))


class Fallback(Tmp):
    def test_clear_message_never_a_crash(self):
        H = self.decoders(absent, absent)
        p = self.file('IMG_0001.heic')
        with self.assertRaises(H.DecoderMissing) as cm:
            H.decode(p)
        msg = str(cm.exception)
        for word in ('HEIC', 'décodeur absent', 'Extensions d’image HEIF', 'HEVC', 'Microsoft Store', 'pillow-heif',
                     'IMG_0001.heic'):
            self.assertIn(word, msg)
        self.assertIsInstance(cm.exception, ValueError)                 # les appelants l'attrapent comme les autres
        self.assertIn('AV1', H.missing_message('x.avif'))
        self.assertIn('Pillow 11.3', H.missing_message('x.avif'))         # hors portable : le module Python aussi
        with mock.patch.object(sys, 'frozen', True, create=True):       # portable : les extensions Windows seules
            portable = H.missing_message(p)
            avif = H.missing_message('x.avif')
        for word in ('HEIC', 'décodeur absent', 'Extensions d’image HEIF', 'HEVC', 'Microsoft Store', 'IMG_0001.heic'):
            self.assertIn(word, portable)
        self.assertIn('AV1', avif)
        for m in (portable, avif):
            self.assertNotIn('pillow', m.lower())
            self.assertNotIn('Python', m)
        self.assertEqual(H.problem(p), msg)
        self.assertEqual(H.problem(str(self.tmp / 'a.png')), '')
        with self.assertRaises(ValueError) as cm:
            registry.open_document(p)                                   # Ouvrir, Importer : la boîte le montre
        self.assertIn('décodeur absent', str(cm.exception))
        from vectordrive.io import proof, raster
        from vectordrive.ui import path_report as PR
        self.assertTrue(raster.read_qimage(p).isNull())
        self.assertIsNone(raster.pixel_size(p))
        self.assertIsNone(proof.logo_image(p))                          # BAT sans logo, comme un logo illisible
        self.assertFalse(PR.image_ok(p))

    def test_dialogs_say_what_to_install(self):
        self.decoders(absent)
        p = self.file()
        from vectordrive.ui import batdialog, dialogs, path_report as PR
        warned = []
        with mock.patch.object(QFileDialog, 'getOpenFileName', lambda *a, **k: (p, '')), \
                mock.patch.object(QMessageBox, 'warning', lambda *a, **k: warned.append(a[2])):
            r = PR.PathReportDialog(None)
            r.use_image.setChecked(True)
            self.assertFalse(r.use_image.isChecked())
            fake_bat = types.SimpleNamespace(set_logo=mock.Mock())
            box = QComboBox()
            box.addItem('Choisir un fichier…', '?')
            batdialog.BatDialog._pick_logo(fake_bat, box, 0)
            fake_bat.set_logo.assert_called_once_with(box, '')         # logo non pris
        self.assertEqual(len(warned), 2)
        self.assertTrue(all('décodeur absent' in m for m in warned))
        d = dialogs.HalftoneDialog()
        d.source.setText(p)
        self.assertIn('décodeur absent', d.info.text())
        self.decoders(fake(picture(200, 100)))
        d.source.setText(p + ' ')
        d.source.setText(p)
        self.assertIn('200 × 100 px', d.info.text())                  # Photo (trame) : la taille de la photo
        with mock.patch.object(QFileDialog, 'getOpenFileName', lambda *a, **k: (p, '')):
            r2 = PR.PathReportDialog(None)
            r2.use_image.setChecked(True)
            self.assertTrue(r2.use_image.isChecked())
            self.assertEqual(r2.image_path, p)
            self.assertFalse(r2.preview.pixmap().isNull())
        for x in (r, r2, d):
            x.close()


class Window(Tmp):
    def setUp(self):
        super().setUp()
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        if not self.w.docs:
            self.w.new_document()
        self.addCleanup(self.clean)

    def clean(self):
        for t in self.w.docs:
            t.modified = False
        self.w.modified = False
        self.w.close()

    def test_drop_open_and_message(self):
        w = self.w
        self.decoders(fake(picture(200, 100)))
        p = self.file()
        w._file_dropped(p, 0.0, 0.0)                                    # glissé-déposé : importée
        self.assertTrue(any(isinstance(it, Image) for it in w.canvas.selection), BEFORE)
        self.assertTrue(w.open_path(p))                                 # Ouvrir
        self.assertTrue(any(isinstance(it, Image) for L in w.canvas.doc.layers for it in L.items))
        self.decoders(absent)
        critical = []
        with mock.patch.object(QMessageBox, 'critical', lambda *a, **k: critical.append(a[2])):
            w._file_dropped(p, 0.0, 0.0)
        self.assertEqual(len(critical), 1)
        self.assertIn('décodeur absent', critical[0])

    def test_vectorize_and_nest_report(self):
        w = self.w
        heif()
        asked, warned = [], []

        def ask(*a, **k):
            asked.append(a[3])
            return '', ''
        with mock.patch.object(QFileDialog, 'getOpenFileName', ask):
            w.canvas.select([])
            w.trace_image()                                             # Vectoriser un fichier image
        self.assertIn('*.heic', asked[0], BEFORE)
        w.canvas.doc.add(Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]), tool=1))
        w.canvas.invalidate()
        self.decoders(absent)
        pdf = str(self.tmp / 'r.pdf')
        with mock.patch.object(QFileDialog, 'getOpenFileName', ask), \
                mock.patch.object(QMessageBox, 'warning', lambda *a, **k: warned.append(a[2])):
            self.assertEqual(w.nest_report(pdf, {'comment': '', 'with_image': True}, open_it=False), pdf)
            self.assertIn('*.heic', asked[1])
            self.assertEqual(w.nest_report(pdf, {'comment': '', 'with_image': True, 'image': self.file()},
                                           open_it=False), pdf)           # rapport fait, sans l'image
        self.assertEqual(len(warned), 1)
        self.assertIn('décodeur absent', warned[0])


def wic_encode(img, path):
    """Un HEIC fabriqué par l'encodeur HEIF de Windows (WIC) ; exception s'il manque."""
    H = heif()
    M, P = H._method, ctypes.POINTER
    img = img.convertToFormat(QImage.Format.Format_ARGB32)
    ole32 = ctypes.windll.ole32
    ole32.CoInitializeEx(None, 2)
    f, enc, st, fr, bag, bmp = (ctypes.c_void_p() for _ in range(6))
    clsid, iid = H._GUID.parse(H.CLSID_WIC_FACTORY), H._GUID.parse(H.IID_WIC_FACTORY)
    H._ok(ole32.CoCreateInstance(ctypes.byref(clsid), None, 1, ctypes.byref(iid), ctypes.byref(f)), 'fabrique')
    try:
        g = H._GUID.parse(H.CONTAINER_HEIF)
        H._ok(M(f, 8, ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p, P(ctypes.c_void_p))(
            ctypes.byref(g), None, ctypes.byref(enc)), 'CreateEncoder')
        H._ok(M(f, 14, ctypes.c_long, P(ctypes.c_void_p))(ctypes.byref(st)), 'CreateStream')
        H._ok(M(st, 15, ctypes.c_long, ctypes.c_wchar_p, ctypes.c_ulong)(str(path), 0x40000000), 'flux')
        H._ok(M(enc, 3, ctypes.c_long, ctypes.c_void_p, ctypes.c_int)(st, 2), 'Initialize')
        H._ok(M(enc, 10, ctypes.c_long, P(ctypes.c_void_p), P(ctypes.c_void_p))(ctypes.byref(fr), ctypes.byref(bag)),
              'CreateNewFrame')
        H._ok(M(fr, 3, ctypes.c_long, ctypes.c_void_p)(bag), 'Initialize')
        H._ok(M(fr, 4, ctypes.c_long, ctypes.c_uint, ctypes.c_uint)(img.width(), img.height()), 'SetSize')
        data = bytes(img.constBits())[:img.sizeInBytes()]
        buf = ctypes.create_string_buffer(data, len(data))
        pf = H._GUID.parse(H.PIXEL_BGRA)
        H._ok(M(f, 20, ctypes.c_long, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint,
                ctypes.c_void_p, P(ctypes.c_void_p))(img.width(), img.height(), ctypes.byref(pf), img.bytesPerLine(),
                                                     len(data), buf, ctypes.byref(bmp)), 'CreateBitmapFromMemory')
        H._ok(M(fr, 11, ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p)(bmp, None), 'WriteSource')
        H._ok(M(fr, 12, ctypes.c_long)(), 'Commit')
        H._ok(M(enc, 11, ctypes.c_long)(), 'Commit')
    finally:
        H._release(bmp, bag, fr, st, enc, f)


def reddish(c):
    return c.red() > 180 and c.blue() < 80


def bluish(c):
    return c.blue() > 180 and c.red() < 80


class Real(Tmp):
    """Le vrai décodeur du poste, s'il est là (sauté sinon)."""

    def test_real_heic(self):
        if sys.platform != 'win32':
            self.skipTest('Windows seulement')
        H = heif()
        p = self.tmp / 'vrai.heic'
        try:
            wic_encode(picture(64, 32), p)
        except Exception as ex:                                         # noqa: BLE001 — pas d'encodeur HEIF ici
            self.skipTest(f'encodeur HEIF absent : {ex}')
        if H._wic(str(p)) is None and H._pillow(str(p)) is None:
            self.skipTest('décodeur HEIC absent')
        doc = registry.open_document(str(p))
        im = next(it for L in doc.layers for it in L.items if isinstance(it, Image))
        from vectordrive.io import raster
        q = raster.qimage_of(im)
        self.assertEqual((q.width(), q.height()), (64, 32))
        self.assertTrue(reddish(q.pixelColor(8, 16)), q.pixelColor(8, 16).name())
        self.assertTrue(bluish(q.pixelColor(56, 16)), q.pixelColor(56, 16).name())
        (self.tmp / 'abime.heic').write_bytes(p.read_bytes()[:200])     # tronqué : illisible, pas « absent »
        with self.assertRaises(ValueError) as cm:
            H.decode(str(self.tmp / 'abime.heic'))
        self.assertNotIsInstance(cm.exception, H.DecoderMissing)
        # WIC décode au CopyPixels : son échec garde son message (pas BufferError de la vue sur la QImage)
        self.decoders(H._wic)
        with hook(H, 7, 4, signed(0x80004005)):
            with self.assertRaises(H._WicError) as cm:
                H._wic(str(p))
            self.assertEqual(str(cm.exception), 'pixels : 0x80004005')
            with self.assertRaises(ValueError) as cm:
                H.decode(str(p))
        self.assertIn('pixels : 0x80004005', str(cm.exception))
        self.assertNotIn('buffer', str(cm.exception))
        with hook(H, 7, 4, signed(0xC00D5212)):                         # HEVC absent : vu à ce moment-là
            self.assertIsNone(H._wic(str(p)))
            with self.assertRaises(H.DecoderMissing) as cm:
                H.decode(str(p))
        self.assertIn('Extensions vidéo HEVC', str(cm.exception))

    def test_real_avif_turned(self):
        try:
            from PIL import Image as PI, features
        except ImportError:
            self.skipTest('Pillow absent')
        if not features.check('avif'):
            self.skipTest('Pillow sans AVIF')
        H = heif()
        im = PI.new('RGB', (64, 32), (255, 0, 0))
        im.paste((0, 0, 255), (32, 0, 64, 32))
        ex = PI.Exif()
        ex[0x0112] = 6                                                  # photo prise de côté : ¼ de tour horaire
        p = str(self.tmp / 'tourne.avif')
        im.save(p, exif=ex.tobytes(), quality=90)
        tried = 0
        for name, fn in list(H.DECODERS):
            if fn(p) is None:
                continue
            tried += 1
            self.decoders(fn)
            q = H.decode(p)
            self.assertEqual((q.width(), q.height()), (32, 64), name)  # tournée une fois (deux : 64 × 32 à l'envers)
            self.assertTrue(reddish(q.pixelColor(16, 8)), name)
            self.assertTrue(bluish(q.pixelColor(16, 56)), name)
        if not tried:
            self.skipTest('décodeur AVIF absent')


if __name__ == '__main__':
    unittest.main()
