"""Round 1160 (v1.17.0) : « Imports pdf contenant image matricielle : be compatible; » ; « BaT ne pas garder en
mémoire champs clients et ref (sauf si plusieurs édition de bat dans un même fichier) car user doit choisir dans
carnet client. » ; « Enregistrement fichier vnd par défaut (vdz seul réglable); »."""
import os
import pathlib
import tempfile
import unittest
import zlib
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1160.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ.setdefault('VECTORDRIVE_CLOSED_TABS', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ.setdefault('VECTORDRIVE_KEYS_MEMORY', '1')

from PySide6.QtCore import QBuffer, QIODevice, QMarginsF, QRectF  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPageSize, QPainter, QPdfWriter  # noqa: E402
from PySide6.QtWidgets import QApplication, QFileDialog  # noqa: E402

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Image, Shape  # noqa: E402

app = QApplication.instance() or QApplication([])
PT = 25.4 / 72
BEFORE_PDF = 'avant : les images matricielles d’un PDF étaient ignorées (page vide)'
BEFORE_BAT = 'avant : le client et la référence du dernier BAT revenaient dans tout nouveau BAT'
BEFORE_SAVE = 'avant : un dessin jamais enregistré se proposait en VDZ'


# --- PDF écrits à la main ----------------------------------------------------------------------------------------
def stream(dic: str, data: bytes) -> bytes:
    return b'<< ' + dic.encode('latin-1') + b' /Length %d >>\nstream\n' % len(data) + data + b'\nendstream'


def pdf_file(content: bytes, objects=(), xobjects: str = '', size=(200, 100), name='essai.pdf', catalog='') -> str:
    """Un PDF d'une page dans un dossier temporaire : `content` (son flux), `objects` (numérotés à partir de 5),
    `xobjects` (« /Im0 5 0 R … »), `catalog` : ajouté au catalogue."""
    objs = [b'<< /Type /Catalog /Pages 2 0 R %s >>' % catalog.encode('latin-1'),
            b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
            ('<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %g %g] /Resources << /XObject << %s >> >> '
             '/Contents 4 0 R >>' % (size[0], size[1], xobjects)).encode('latin-1'),
            stream('', content)] + list(objects)
    out = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += b'%d 0 obj\n' % i + o + b'\nendobj\n'
    at = len(out)
    out += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objs) + 1)
    for o in offsets:
        out += b'%010d 00000 n \n' % o
    out += b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objs) + 1, at)
    p = os.path.join(tempfile.mkdtemp(), name)
    pathlib.Path(p).write_bytes(bytes(out))
    return p


def image(dic: str, data: bytes) -> bytes:
    return stream('/Type /XObject /Subtype /Image ' + dic, data)


def encoded(q: QImage, fmt: str) -> bytes:
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    assert q.save(buf, fmt, 100 if fmt == 'JPEG' else -1)
    return bytes(buf.data())


def jpeg(w: int, h: int, color: str) -> bytes:
    q = QImage(w, h, QImage.Format.Format_RGB32)
    q.fill(QColor(color))
    return encoded(q, 'JPEG')


def png_filtered(rows: list, bpp: int, kinds: list) -> bytes:
    """Lignes d'octets filtrées en PNG (types 0 à 4), comme un encodeur : la référence des essais du prédicteur."""
    out, prev = bytearray(), bytes(len(rows[0]))
    for row, t in zip(rows, kinds):
        enc = bytearray()
        for i, x in enumerate(row):
            a = row[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if t == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if pa <= pb and pa <= pc else b if pb <= pc else c
            else:
                pred = (0, a, b, (a + b) // 2)[t]
            enc.append((x - pred) & 255)
        out += bytes([t]) + enc
        prev = row
    return bytes(out)


def read(path):
    from vectordrive.io import registry
    return registry.open_document(path)


def items(doc, kind=None):
    return [it for L in doc.layers for it in L.items if kind is None or isinstance(it, kind)]


def pixels(im):
    q = QImage.fromData(im.data)
    assert not q.isNull()
    return q


def near(a, b, tol=1e-6):
    return abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol


class PdfImages(unittest.TestCase):
    def test_flate_rgb_image_at_its_place_with_the_vectors(self):
        rgb = bytes([255, 0, 0, 0, 255, 0, 0, 0, 255, 255, 255, 255])
        p = pdf_file(b'0 0 m 10 10 l S q 72 0 0 36 72 36 cm /Im0 Do Q',
                     [image('/Width 2 /Height 2 /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode',
                            zlib.compress(rgb))], '/Im0 5 0 R')
        doc = read(p)
        ims = items(doc, Image)
        self.assertEqual(len(ims), 1, BEFORE_PDF)
        self.assertEqual(len(items(doc, Shape)), 1)                         # les vecteurs : comme avant
        im = ims[0]
        self.assertEqual(im.fmt, 'png')
        self.assertTrue(near(im.matrix.apply((0, 0)), (72 * PT, 72 * PT)))  # le haut de l'image, à gauche
        self.assertTrue(near(im.matrix.apply((1, 1)), (144 * PT, 36 * PT)))
        q = pixels(im)
        self.assertEqual((q.width(), q.height()), (2, 2))
        self.assertEqual([q.pixelColor(x, y).name() for x, y in ((0, 0), (1, 0), (0, 1), (1, 1))],
                         ['#ff0000', '#00ff00', '#0000ff', '#ffffff'])
        self.assertTrue(any('image(s) matricielle(s)' in r for r in doc.report), doc.report)

    def test_predictor_gray_cmyk_and_decode(self):
        gray = b'\x01' + bytes([0, 64, 64, 127]) + b'\x00' + bytes([255, 128, 64, 0])    # ligne 1 en « Sub »
        objs = [image('/Width 4 /Height 2 /ColorSpace /DeviceGray /BitsPerComponent 8 /Filter /FlateDecode '
                      '/DecodeParms << /Predictor 15 /Colors 1 /BitsPerComponent 8 /Columns 4 >>', zlib.compress(gray)),
                image('/Width 2 /Height 1 /ColorSpace /DeviceCMYK /BitsPerComponent 8',
                      bytes([0, 255, 255, 0, 0, 0, 0, 255])),
                image('/Width 8 /Height 1 /ColorSpace /DeviceGray /BitsPerComponent 1 /Decode [1 0]',
                      bytes([0b10100000])),
                image('/Width 2 /Height 1 /ColorSpace [/ICCBased 9 0 R] /BitsPerComponent 16',
                      bytes([0xff, 0xff, 0, 0, 0, 0, 0, 0, 0, 0, 0xff, 0xff])),
                stream('/N 3', b'')]
        p = pdf_file(b'q 40 0 0 20 0 0 cm /A Do Q q 20 0 0 10 50 0 cm /B Do Q q 80 0 0 10 0 50 cm /C Do Q '
                     b'q 20 0 0 10 100 50 cm /D Do Q', objs, '/A 5 0 R /B 6 0 R /C 7 0 R /D 8 0 R')
        ims = items(read(p), Image)
        self.assertEqual(len(ims), 4, BEFORE_PDF)
        g, c, d, icc = (pixels(im) for im in ims)
        self.assertEqual([g.pixelColor(x, 0).red() for x in range(4)], [0, 64, 128, 255])
        self.assertEqual([g.pixelColor(x, 1).red() for x in range(4)], [255, 128, 64, 0])
        self.assertEqual([c.pixelColor(x, 0).name() for x in range(2)], ['#ff0000', '#000000'])
        self.assertEqual([d.pixelColor(x, 0).red() for x in range(4)], [0, 255, 0, 255])    # /Decode [1 0] : inversé
        self.assertEqual([icc.pixelColor(x, 0).name() for x in range(2)], ['#ff0000', '#0000ff'])  # 16 bits, ICC à 3

    def test_jpeg_with_soft_mask_rotated_and_mirrored(self):
        mask = bytes([0, 0, 255, 255] * 2)
        objs = [image('/Width 4 /Height 2 /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /SMask 6 0 R',
                      jpeg(4, 2, '#0000ff')),
                image('/Width 4 /Height 2 /ColorSpace /DeviceGray /BitsPerComponent 8', mask)]
        p = pdf_file(b'q 0 36 -72 0 100 10 cm /J Do Q q -72 0 0 36 172 50 cm /J Do Q', objs, '/J 5 0 R')
        ims = items(read(p), Image)
        self.assertEqual(len(ims), 2, BEFORE_PDF)
        turned, mirrored = ims
        self.assertTrue(near(turned.matrix.apply((0, 0)), (28 * PT, 10 * PT)))         # un quart de tour
        self.assertTrue(near(turned.matrix.apply((1, 0)), (28 * PT, 46 * PT)))
        self.assertTrue(near(mirrored.matrix.apply((0, 0)), (172 * PT, 86 * PT)))      # retournée
        self.assertTrue(near(mirrored.matrix.apply((1, 1)), (100 * PT, 50 * PT)))
        q = pixels(turned)
        self.assertEqual(q.pixelColor(0, 0).alpha(), 0)                     # masque doux : transparent à gauche
        right = q.pixelColor(3, 1)
        self.assertEqual(right.alpha(), 255)
        self.assertGreater(right.blue(), 230)
        self.assertLess(right.red() + right.green(), 30)

    def test_image_only_pdf_from_qt_is_no_longer_empty(self):
        p = os.path.join(tempfile.mkdtemp(), 'scan.pdf')
        src = QImage(40, 20, QImage.Format.Format_RGB32)
        src.fill(QColor('#ff0000'))
        wr = QPdfWriter(p)
        wr.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        wr.setPageMargins(QMarginsF(0, 0, 0, 0))
        wr.setResolution(72)
        painter = QPainter(wr)
        painter.drawImage(QRectF(100, 100, 200, 100), src)
        painter.end()
        doc = read(p)
        ims = items(doc, Image)
        self.assertEqual(len(ims), 1, BEFORE_PDF)
        bb = ims[0].bbox()
        H = 842
        for got, want in zip(bb, (100 * PT, (H - 200) * PT, 300 * PT, (H - 100) * PT)):
            self.assertAlmostEqual(got, want, delta=0.5)
        q = pixels(ims[0])
        self.assertEqual((q.width(), q.height()), (40, 20))
        self.assertGreater(q.pixelColor(20, 10).red(), 230)

    def test_mask_palette_and_inline_image(self):
        objs = [image('/Width 8 /Height 1 /ImageMask true /BitsPerComponent 1', bytes([0b00001111])),
                image('/Width 2 /Height 1 /ColorSpace [/Indexed /DeviceRGB 1 <FF000000FF00>] /BitsPerComponent 8',
                      bytes([1, 0]))]
        p = pdf_file(b'1 0 0 rg q 80 0 0 10 0 0 cm /M Do Q q 20 0 0 10 0 50 cm /P Do Q '
                     b'q 20 0 0 10 150 50 cm BI /W 2 /H 1 /CS /RGB /BPC 8 /F /AHx ID FF00000000FF> EI Q',
                     objs, '/M 5 0 R /P 6 0 R')
        doc = read(p)
        ims = items(doc, Image)
        self.assertEqual(len(ims), 3, BEFORE_PDF)
        m, pal, inline = (pixels(im) for im in ims)
        self.assertEqual((m.pixelColor(0, 0).name(), m.pixelColor(0, 0).alpha()), ('#ff0000', 255))   # fond courant
        self.assertEqual(m.pixelColor(7, 0).alpha(), 0)
        self.assertEqual([pal.pixelColor(x, 0).name() for x in range(2)], ['#00ff00', '#ff0000'])
        self.assertEqual([inline.pixelColor(x, 0).name() for x in range(2)], ['#ff0000', '#0000ff'])
        self.assertTrue(near(ims[2].matrix.apply((0, 1)), (150 * PT, 50 * PT)))

    def test_fax_ccitt_image_and_its_decode_array(self):
        g4 = bytes.fromhex('3317fff0010010')                                 # 16 × 8, moitié gauche d'une teinte
        fax = '/Width 16 /Height 8 /ColorSpace /DeviceGray /BitsPerComponent 1 /Filter /CCITTFaxDecode '
        objs = [image(fax + '/DecodeParms << /K -1 /Columns 16 /Rows 8 >>', g4),
                image(fax + '/DecodeParms << /K -1 /Columns 16 /Rows 8 >> /Decode [1 0]', g4),
                image(fax + '/DecodeParms << /K -1 /Columns 16 /Rows 8 /BlackIs1 true >>', g4),
                image(fax + '/DecodeParms << /K -1 /Columns 16 /Rows 8 /BlackIs1 true >> /Decode [1 0]', g4)]
        p = pdf_file(b'q 16 0 0 8 0 0 cm /A Do /B Do /C Do /D Do Q', objs, '/A 5 0 R /B 6 0 R /C 7 0 R /D 8 0 R')
        ims = items(read(p), Image)
        self.assertEqual(len(ims), 4, BEFORE_PDF)
        halves = []
        for im in ims:
            q = pixels(im)
            self.assertEqual((q.width(), q.height()), (16, 8))
            left = {q.pixelColor(x, y).name() for x in range(8) for y in range(8)}
            right = {q.pixelColor(x, y).name() for x in range(8, 16) for y in range(8)}
            self.assertEqual((len(left), len(right)), (1, 1))
            self.assertEqual(left | right, {'#000000', '#ffffff'})
            halves.append(left.pop())
        plain, decode, black1, both = halves
        self.assertNotEqual(decode, plain)                                  # /Decode [1 0] : inversé
        self.assertNotEqual(black1, plain)                                  # /BlackIs1 seul : inversé aussi
        self.assertEqual(both, plain)                                       # les deux : pas en négatif

    def test_unsupported_or_broken_images_warn_without_crashing(self):
        objs = [image('/Width 4 /Height 4 /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /JPXDecode',
                      b'\x00\x00\x00\x0cjP  \r\n\x87\n'),
                image('/Width 4 /Height 4 /ColorSpace /DeviceGray /BitsPerComponent 1 /Filter /JBIG2Decode',
                      b'\x97JB2'),
                image('/Width 4 /Height 4 /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode',
                      b'pas zlib'),
                image('/Height 4 /ColorSpace /DeviceRGB /BitsPerComponent 8', b'\x00' * 48),
                image('/Width 2 /Height 2 /ColorSpace /DeviceRGB /BitsPerComponent 8', b'\xff\x00\x00' + bytes(7)),
                image('/Width 2 /Height 2 /ColorSpace /DeviceRGB /BitsPerComponent 8', b'\xff\x00\x00')]
        p = pdf_file(b'0 0 50 50 re f q 10 0 0 10 0 0 cm /A Do /B Do /C Do /D Do /E Do /F Do Q', objs,
                     '/A 5 0 R /B 6 0 R /C 7 0 R /D 8 0 R /E 9 0 R /F 10 0 R')
        doc = read(p)
        self.assertEqual(len(items(doc, Shape)), 1)                         # le reste du PDF est lu
        report = ' | '.join(doc.report)
        self.assertIn('JPEG 2000', report, BEFORE_PDF)
        self.assertIn('JBIG2', report)
        self.assertIn('largeur', report)
        self.assertIn('abîmées', report)                                    # Flate illisible : ignorée
        self.assertIn('tronquée', report)                                   # un peu courte : complétée
        self.assertIn('incomplète', report)                                 # bien trop courte : refusée
        self.assertNotIn('Error', report)                                   # jamais d'anglais technique
        ims = items(doc, Image)
        self.assertEqual(len(ims), 1)
        self.assertEqual(pixels(ims[0]).pixelColor(0, 0).name(), '#ff0000')

    def test_memory_bounds_on_the_real_size(self):
        from vectordrive.io import raster
        big = QImage(400, 300, QImage.Format.Format_RGB32)
        big.fill(QColor('#ff0000'))
        objs = [image('/Width 100 /Height 100 /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode',
                      encoded(big, 'JPEG')),                                # annoncée 100 × 100, en vrai 400 × 300
                image('/Width 20000 /Height 20000 /ColorSpace /DeviceGray /BitsPerComponent 1', bytes(1000)),
                image('/Width 300 /Height 200 /ColorSpace /DeviceGray /BitsPerComponent 8', bytes(60000))]
        p = pdf_file(b'q 10 0 0 10 0 0 cm /A Do /B Do /C Do Q', objs, '/A 5 0 R /B 6 0 R /C 7 0 R')
        with mock.patch.object(raster, 'MAX_PIXELS', 10_000):
            doc = read(p)
        ims = items(doc, Image)
        self.assertEqual(len(ims), 2, BEFORE_PDF)                           # la tronquée : refusée, sans mémoire
        for im in ims:
            q = pixels(im)
            self.assertLessEqual(q.width() * q.height(), 10_000)
            self.assertGreater(q.width() * q.height(), 5_000)
        self.assertAlmostEqual(pixels(ims[0]).width() / pixels(ims[0]).height(), 4 / 3, delta=0.05)
        self.assertEqual(sum('réduite' in r for r in doc.report), 1)       # dit une seule fois
        self.assertIn('incomplète', ' '.join(doc.report))
        from vectordrive.io import pdf_image
        with mock.patch.object(pdf_image, 'MAX_SAMPLES', 1000):
            doc = read(p)
        self.assertEqual(items(doc, Image), [])
        self.assertEqual(sum('trop grande' in r for r in doc.report), 1)

    def test_large_flate_image_with_png_predictor(self):
        import time
        w, h = 5200, 5000                                                   # 26 Mpx, 78 Mo décodés (> 75 Mo de pypdf)
        first = bytes((3 * (k // 3) + k % 3) % 256 for k in range(3 * w))
        z = zlib.compressobj()
        parts = [z.compress(b'\x00' + first)]
        row = bytes(3 * w)
        for y in range(1, h):
            parts.append(z.compress((b'\x04' if y % 2 else b'\x02') + row))    # Paeth et Up : la ligne d'au-dessus
        parts.append(z.flush())
        data = b''.join(parts)
        p = pdf_file(b'q 200 0 0 192 0 0 cm /A Do Q',
                     [image(f'/Width {w} /Height {h} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode '
                            f'/DecodeParms << /Predictor 15 /Colors 3 /BitsPerComponent 8 /Columns {w} >>', data)],
                     '/A 5 0 R')
        t0 = time.monotonic()
        doc = read(p)
        ims = items(doc, Image)
        self.assertEqual(len(ims), 1, BEFORE_PDF + ' ; ' + ' | '.join(doc.report))
        self.assertLess(time.monotonic() - t0, 60)
        q = pixels(ims[0])
        self.assertEqual((q.width(), q.height()), (w, h))
        for x, y in ((0, 0), (1, 4999), (100, 2500), (5199, 1)):
            c = q.pixelColor(x, y)
            self.assertEqual((c.red(), c.green(), c.blue()), tuple((3 * x + i) % 256 for i in range(3)), (x, y))

    def test_predictors_exact_in_every_depth(self):
        import random
        import numpy as np
        from vectordrive.io import pdf_image
        rng = random.Random(1160)
        for colors, bpc, cols in ((1, 1, 13), (1, 2, 11), (1, 4, 7), (3, 8, 5), (1, 16, 6), (3, 16, 4), (4, 8, 3)):
            row = (cols * colors * bpc + 7) // 8
            bpp = max(1, colors * bpc // 8)
            rows = [bytes(rng.randrange(256) for _ in range(row)) for _ in range(6)]
            parms = {'/Predictor': 15, '/Colors': colors, '/BitsPerComponent': bpc, '/Columns': cols}
            got = pdf_image.unpredict(png_filtered(rows, bpp, [0, 1, 2, 3, 4, 1]), parms)
            self.assertEqual(got, b''.join(rows), ('PNG', colors, bpc))
            # TIFF 2 : différence avec l'échantillon de gauche, modulo 2^bpc
            n = cols * colors
            s = np.array([[rng.randrange(1 << bpc) for _ in range(n)] for _ in range(4)], np.int64)
            diff = s.reshape(4, cols, colors).copy()
            diff[:, 1:] = (diff[:, 1:] - diff[:, :-1]) % (1 << bpc)
            parms['/Predictor'] = 2
            self.assertEqual(pdf_image.unpredict(pack(diff.reshape(4, n), bpc, row), parms), pack(s, bpc, row),
                             ('TIFF', colors, bpc))

    def test_same_logo_decoded_once_and_its_optional_layer(self):
        from vectordrive.io import pdf_image
        ops = b''.join(b'q 5 0 0 5 %d 0 cm /L Do Q ' % (k * 6) for k in range(100))
        objs = [image('/Width 2 /Height 1 /ColorSpace /DeviceRGB /BitsPerComponent 8 /OC 6 0 R', bytes(6)),
                b'<< /Type /OCG /Name (Logos) >>']
        p = pdf_file(ops, objs, '/L 5 0 R', size=(700, 100),
                     catalog='/OCProperties << /OCGs [6 0 R] /D << /OFF [6 0 R] >> >>')
        with mock.patch.object(pdf_image, 'decode', wraps=pdf_image.decode) as dec:
            doc = read(p)
        ims = items(doc, Image)
        self.assertEqual(len(ims), 100, BEFORE_PDF)
        self.assertEqual(dec.call_count, 1)                                 # un seul décodage
        self.assertTrue(all(im.data is ims[0].data for im in ims))          # les mêmes données
        layer = next(L for L in doc.layers if ims[0] in L.items)
        self.assertEqual((layer.name, layer.visible), ('Logos', False))     # le calque de son /OC, masqué

    def test_adobe_cmyk_jpeg(self):
        px = bytes([0, 255, 255, 0] * 64)                                   # rouge en CMJN
        data = encoded(QImage(px, 8, 8, 32, QImage.Format.Format_CMYK8888).copy(), 'JPEG')
        self.assertIn(b'Adobe', data)                                       # JPEG CMJN « Adobe » (inversé)
        p = pdf_file(b'q 8 0 0 8 0 0 cm /A Do Q',
                     [image('/Width 8 /Height 8 /ColorSpace /DeviceCMYK /BitsPerComponent 8 /Filter /DCTDecode',
                            data)], '/A 5 0 R')
        ims = items(read(p), Image)
        self.assertEqual(len(ims), 1, BEFORE_PDF)
        c = pixels(ims[0]).pixelColor(4, 4)
        self.assertGreater(c.red(), 230)
        self.assertLess(c.green() + c.blue(), 40)

    def test_reduced_image_skips_qt_png_and_the_slow_predictor(self):
        import numpy as np
        from vectordrive.io import pdf_image, raster
        w = h = 200
        gray = np.array([[(7 * x + 3 * y) % 256 for x in range(w)] for y in range(h)], np.uint8)
        levels = np.array([[(x // 3 + y) % 4 for x in range(w)] for y in range(h)], np.uint8)
        two = pack(levels, 2, w // 4)

        def pdf(bpc, rows, kinds):
            data = zlib.compress(png_filtered(rows, 1, kinds))
            return pdf_file(b'q 20 0 0 20 0 0 cm /A Do Q', [image(
                f'/Width {w} /Height {h} /ColorSpace /DeviceGray /BitsPerComponent {bpc} /Filter /FlateDecode '
                f'/DecodeParms << /Predictor 15 /Colors 1 /BitsPerComponent {bpc} /Columns {w} >>', data)], '/A 5 0 R')
        up = pdf(8, [bytes(r) for r in gray], [2] * h)
        up2 = pdf(2, [two[k:k + w // 4] for k in range(0, len(two), w // 4)], [2] * h)
        paeth = pdf(8, [bytes(r) for r in gray], [4] * h)
        with mock.patch.object(raster, 'MAX_PIXELS', 10_000), mock.patch.object(pdf_image, 'SLOW_BYTES', 1000), \
                mock.patch.object(pdf_image, '_png_samples', wraps=pdf_image._png_samples) as qt_png:
            for p, want in ((up, gray), (up2, levels.astype(np.uint16) * 85)):
                ims = items(read(p), Image)
                self.assertEqual(len(ims), 1)
                q = pixels(ims[0]).convertToFormat(QImage.Format.Format_Grayscale8)
                self.assertEqual((q.width(), q.height()), (100, 100))       # une ligne et une colonne sur deux
                for x, y in ((0, 0), (37, 81), (99, 99), (50, 3)):
                    self.assertEqual(q.pixelColor(x, y).red(), int(want[2 * y, 2 * x]), (x, y))
            self.assertEqual(qt_png.call_count, 0, 'avant : le PNG de Qt lisait l’image entière avant de la réduire')
            doc = read(paeth)
        self.assertEqual(items(doc, Image), [], 'avant : Paeth octet par octet en Python sur une grande image')
        self.assertIn('Paeth', ' '.join(doc.report))

    def test_qt_reader_limit_fixed_while_decoding_then_given_back(self):
        from PySide6.QtGui import QImageReader
        from vectordrive.io import pdf_image
        real = QImageReader.setAllocationLimit
        self.addCleanup(real, QImageReader.allocationLimit())
        p = pdf_file(b'q 8 0 0 8 0 0 cm /A Do Q',
                     [image('/Width 8 /Height 8 /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode',
                            jpeg(8, 8, '#00ff00'))], '/A 5 0 R')
        seen = []

        def spy(v):
            seen.append(v)
            real(v)
        for before in (0, 256, 4096):
            real(before)
            seen.clear()
            with mock.patch.object(QImageReader, 'setAllocationLimit', side_effect=spy):
                self.assertEqual(len(items(read(p), Image)), 1)
            self.assertEqual(seen[:1], [pdf_image.QT_LIMIT], ('avant : laissée telle quelle', before))
            self.assertEqual(QImageReader.allocationLimit(), before)       # rendue

    def test_truncated_jpeg_is_said(self):
        import random
        rng = random.Random(1160)
        q = QImage(64, 64, QImage.Format.Format_RGB32)
        for y in range(64):
            for x in range(64):
                q.setPixelColor(x, y, QColor(rng.randrange(256), rng.randrange(256), rng.randrange(256)))
        data = encoded(q, 'JPEG')
        p = pdf_file(b'q 8 0 0 8 0 0 cm /A Do Q',
                     [image('/Width 64 /Height 64 /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode',
                            data[:len(data) * 7 // 10])], '/A 5 0 R')
        doc = read(p)
        self.assertEqual(len(items(doc, Image)), 1)
        self.assertIn('tronquée', ' '.join(doc.report), 'avant : JPEG tronqué sans un mot')


class Companion(unittest.TestCase):
    def test_what_the_vnd_keeps_needs_no_companion(self):
        from vectordrive.core.document import Document, Group
        from vectordrive.core.geom import Affine
        from vectordrive.io import companion
        solid = QImage(4, 2, QImage.Format.Format_ARGB32)
        solid.fill(QColor(255, 0, 0, 255))
        rgba = encoded(solid, 'PNG')
        self.assertEqual(rgba[25], 6)                                       # PNG RGBA, tout opaque
        clear = QImage(4, 2, QImage.Format.Format_ARGB32)
        clear.fill(QColor(0, 0, 255, 100))
        see = encoded(clear, 'PNG')
        flat = Affine(8, 0, 0, -4, 0, 4)
        self.assertFalse(companion.image_rich(Image(data=rgba, fmt='png', matrix=flat)),
                         'avant : un PNG RGBA tout opaque passait pour transparent')
        self.assertFalse(companion.image_rich(Image(data=rgba, fmt='png', matrix=Affine(-8, 0, 0, -4, 8, 4))),
                         'avant : une image seulement retournée demandait un compagnon')
        self.assertTrue(companion.image_rich(Image(data=rgba, fmt='png', matrix=Affine.rotation(30) @ flat)))
        self.assertTrue(companion.image_rich(Image(data=see, fmt='png', matrix=flat)))
        doc = Document()
        doc.layers[0].items.append(Group(children=[Image(data=see, fmt='png', matrix=flat)]))
        self.assertIn('groupe(s) avec textes ou images', ' | '.join(companion.reasons(doc)))

    def test_images_matched_layer_by_layer_with_the_first_shown_layer_first(self):
        from vectordrive.core.document import Document, Layer
        from vectordrive.core.geom import Affine
        from vectordrive.io import companion, raster, registry
        clear = QImage(4, 2, QImage.Format.Format_ARGB32)
        clear.fill(QColor(0, 0, 255, 100))
        red = QImage(6, 3, QImage.Format.Format_RGB32)
        red.fill(QColor('#ff0000'))
        a = Image(data=encoded(clear, 'PNG'), fmt='png', matrix=Affine(8, 0, 0, -4, 40, 4))        # logo transparent
        b = Image(data=encoded(red, 'PNG'), fmt='png', matrix=Affine(-12, 0, 0, -6, 12, 30))       # photo retournée
        doc = Document()
        doc.layers[0].name, doc.layers[0].visible = 'Photo', False
        doc.layers[0].items.append(b)
        doc.layers.append(Layer(name='Logos', items=[a]))
        doc.extra['vnd_premier_plan'] = True                                # « premier calque montré en tête »
        p = os.path.join(tempfile.mkdtemp(), 'logos.vnd')
        registry.save_document(doc, p)
        companion.sync(doc, p)
        back = registry.open_document(p)
        self.assertEqual([L.name for L in back.layers], ['Logos', 'Photo'])  # l'ordre du VND : Logos en tête
        companion.apply(back, p)
        got = {L.name: [it for it in L.items if isinstance(it, Image)] for L in back.layers}
        self.assertEqual(got['Logos'][0].data, a.data)                      # le logo, transparent
        photo = raster.qimage_of(got['Photo'][0])
        self.assertEqual((photo.width(), photo.height()), (6, 3), 'avant : la photo prenait les pixels du logo')
        self.assertEqual(photo.pixelColor(1, 1).name(), '#ff0000')
        m = got['Photo'][0].matrix
        for u, v in zip((m.a, m.b, m.c, m.d, m.e, m.f), (-12, 0, 0, -6, 12, 30)):
            self.assertAlmostEqual(u, v, places=6)                          # retournée : le VND garde le signe

    @staticmethod
    def marker(x=10.0, y=10.0):
        """Un point de construction TypeEdit d'origine, tel que `vnd.py` le lit : groupe sans enfants + `vnd_obj`."""
        from vectordrive.core.document import Group
        from vectordrive.io.mfc import MfcClass, MfcObject
        from vectordrive.io.vnd_write import V13_SCHEMAS, _bbox_m, _obdao_fields
        o = MfcObject(MfcClass('CMarker', V13_SCHEMAS['CMarker']))
        o.fields = _obdao_fields(_bbox_m((x, y, x, y)))
        o.fields.update(pos=(x / 1000, y / 1000, 0.0), ints=[0] * 7)
        g = Group(children=[], name='Point de construction')
        g.extra['vnd'] = {'wraps': 0}
        g.extra['vnd_obj'] = o
        return g

    def test_text_and_image_come_back_beside_a_typeedit_object_without_children(self):
        from vectordrive.core.document import Document, Layer, Text
        from vectordrive.core.geom import Affine
        from vectordrive.io import companion, registry, vnd_write
        red = QImage(6, 3, QImage.Format.Format_RGB32)
        red.fill(QColor('#ff0000'))
        y = Image(data=encoded(red, 'PNG'), fmt='png',
                  matrix=Affine.translation(60, 20) @ Affine.rotation(30) @ Affine(12, 0, 0, -6, 0, 6))
        doc = Document()
        doc.layers[0].items += [self.marker(), Text(text='BFM', font='Arial', size=8,
                                                    matrix=Affine.translation(15, 15))]
        doc.layers.append(Layer(name='Photo', items=[y]))
        p = os.path.join(tempfile.mkdtemp(), 'axe.vnd')
        from vectordrive.core.text import ensure_outlines
        ensure_outlines(doc)                                                # comme `registry.save_document`
        data, _report = vnd_write.write_document(doc, allow_foreign=True)  # comme dans son propre VND TypeEdit
        pathlib.Path(p).write_bytes(data)
        companion.sync(doc, p)
        back = registry.open_document(p)
        self.assertIn('Point de construction', [it.name for it in back.layers[0].items])
        companion.apply(back, p)
        texts = [it for L in back.layers for it in L.items if isinstance(it, Text)]
        self.assertEqual([t.text for t in texts], ['BFM'], 'texte modifiable perdu à côté du point de construction')
        ims = [it for L in back.layers for it in L.items if isinstance(it, Image)]
        self.assertEqual([(im.data, im.matrix) for im in ims], [(y.data, y.matrix)], 'avant : image tournée perdue')

    def test_first_shown_order_counts_a_typeedit_object_as_written(self):
        from vectordrive.core.document import Layer, Text
        from vectordrive.core.geom import Affine
        from vectordrive.io import companion
        g = self.marker()
        g.extra['vnd_obj'] = None                                           # tel que le compagnon le relit
        self.assertTrue(companion._written(g), 'avant : objet TypeEdit sans enfants compté « pas écrit »')
        comp = [Layer(name='Plan 1', items=[g]),
                Layer(name='Plan 1', items=[Text(text='A', font='Arial', size=8, matrix=Affine.translation(5, 5))])]
        vnd = [Layer(name='Plan 1'), Layer(name='Plan 1')]
        self.assertEqual(companion._in_vnd_order(vnd, comp, 'premier'), [0, 1])     # le point est montré : en tête

    def test_turned_image_comes_back_at_its_place_with_an_origin(self):
        from vectordrive.core.document import Document
        from vectordrive.core.geom import Affine
        from vectordrive.io import companion, registry
        clear = QImage(4, 2, QImage.Format.Format_ARGB32)
        clear.fill(QColor(0, 0, 255, 100))
        im = Image(data=encoded(clear, 'PNG'), fmt='png',
                   matrix=Affine.translation(60, 20) @ Affine.rotation(30) @ Affine(8, 0, 0, -4, 0, 4))
        doc = Document()
        doc.layers[0].items += [square(10.0), im]
        doc.extra['origine'] = (50.0, 25.0)                                 # le zéro du VND : tout est décalé
        p = os.path.join(tempfile.mkdtemp(), 'origine.vnd')
        registry.save_document(doc, p)
        companion.sync(doc, p)
        self.assertTrue(companion.companion_path(p).is_file())
        self.assertIn('1 image(s)', ' | '.join(companion.reasons(doc)), 'avant : image transparente pas comptée')
        back = registry.open_document(p)
        companion.apply(back, p)
        sq = next(it for L in back.layers for it in L.items if isinstance(it, Shape))
        ims = [it for L in back.layers for it in L.items if isinstance(it, Image)]
        self.assertEqual(len(ims), 1)
        self.assertAlmostEqual(sq.bbox()[0], 10.0, places=6)                # relu dans le repère du dessin (1167)
        self.assertAlmostEqual(sq.bbox()[1], 0.0, places=6)
        self.assertEqual([(i.data, i.matrix) for i in ims], [(im.data, im.matrix)])  # l'image du compagnon, à sa place

    def test_twin_layer_names_with_a_hidden_first_layer_take_nothing(self):
        from vectordrive.core.document import Document, Layer
        from vectordrive.core.geom import Affine
        from vectordrive.io import companion, registry
        turn = Affine.translation(20, 20) @ Affine.rotation(30)
        green = QImage(4, 2, QImage.Format.Format_RGB32)
        green.fill(QColor('#00ff00'))
        red = QImage(6, 3, QImage.Format.Format_RGB32)
        red.fill(QColor('#ff0000'))
        for case, with_contour in (('A', False), ('B', True)):
            x = Image(data=encoded(green, 'PNG'), fmt='png', matrix=turn @ Affine(8, 0, 0, -4, 0, 4))
            x.visible = False                                               # masquée : pas écrite dans le VND
            y = Image(data=encoded(red, 'PNG'), fmt='png', matrix=turn @ Affine(12, 0, 0, -6, 40, 6))
            doc = Document()
            doc.layers[0].items.append(x)                                   # « Plan 1 » : rien de montré
            second = Layer(name=doc.layers[0].name, items=[y])              # « Plan 1 » aussi
            if with_contour:
                c = square(70.0)
                c.tool = 0                                                  # même outil : un seul calque TypeEdit
                second.items.append(c)
            doc.layers.append(second)
            doc.extra['vnd_premier_plan'] = True                            # « premier calque montré en tête »
            p = os.path.join(tempfile.mkdtemp(), f'jumeaux{case}.vnd')
            registry.save_document(doc, p)
            companion.sync(doc, p)
            self.assertTrue(companion.companion_path(p).is_file(), 'avant : images tournées sans compagnon')
            back = registry.open_document(p)
            said = ' | '.join(companion.apply(back, p))
            self.assertNotIn('renommer', said, case)                        # ordre refait vérifié par les contenus
            self.assertEqual([L.id for L in back.layers], [second.id, doc.layers[0].id],
                             (case, 'avant : id de calque repris à l’aveugle (opérations FAO redirigées)'))
            ims = [it for L in back.layers for it in companion._walk(L.items) if isinstance(it, Image)]
            self.assertEqual(len(ims), 1, case)
            self.assertNotEqual(ims[0].data, x.data, (case, 'avant : l’image masquée X remplaçait Y'))
            self.assertFalse(near((ims[0].matrix.e, ims[0].matrix.f), (x.matrix.e, x.matrix.f), 1e-3), case)
            q = QImage.fromData(ims[0].data) if ims[0].fmt == 'png' else None
            if q is None:
                from vectordrive.io import raster
                q = raster.qimage_of(ims[0])
            self.assertEqual(q.pixelColor(1, 1).name(), '#ff0000', case)    # Y, la seule écrite, reste Y

    def test_twin_layer_names_in_drawing_order_get_everything_back(self):
        from vectordrive.core.document import Document, Layer, Text
        from vectordrive.core.geom import Affine
        from vectordrive.io import companion, registry
        clear = QImage(4, 2, QImage.Format.Format_ARGB32)
        clear.fill(QColor(0, 0, 255, 100))
        im = Image(data=encoded(clear, 'PNG'), fmt='png',
                   matrix=Affine.translation(60, 20) @ Affine.rotation(30) @ Affine(8, 0, 0, -4, 0, 4))
        doc = Document()                                                    # ordre « dessin » : le réglage d'office
        doc.layers[0].items.append(Text(text='A', font='Arial', size=8, matrix=Affine.translation(5, 5)))
        doc.layers.append(Layer(name=doc.layers[0].name, items=[
            im, Text(text='B', font='Arial', size=8, matrix=Affine.translation(5, 30))]))
        p = os.path.join(tempfile.mkdtemp(), 'jumeaux.vnd')
        registry.save_document(doc, p)
        companion.sync(doc, p)
        back = registry.open_document(p)
        said = ' | '.join(companion.apply(back, p))
        self.assertNotIn('renommer', said)
        self.assertEqual([L.id for L in back.layers], [L.id for L in doc.layers],
                         'avant : calques jumeaux écartés, opérations FAO détachées')
        self.assertEqual([[it.text for it in L.items if isinstance(it, Text)] for L in back.layers], [['A'], ['B']])
        ims = [it for L in back.layers for it in L.items if isinstance(it, Image)]
        self.assertEqual([(i.data, i.matrix) for i in ims], [(im.data, im.matrix)])

    def test_twin_layer_names_of_a_retouched_vnd_take_no_layer_id(self):
        from vectordrive.core.document import Document, Layer, Text
        from vectordrive.core.geom import Affine
        from vectordrive.io import companion, registry
        doc = Document()                                                    # ordre « dessin » : le réglage d'office
        a0 = doc.layers[0]
        a0.name = 'A'
        a0.items.append(Text(text='A0', font='Arial', size=8, matrix=Affine.translation(5, 5)))
        a1 = Layer(name='A', items=[Text(text='A1', font='Arial', size=8, matrix=Affine.translation(5, 30))])
        b = Layer(name='B', items=[square(40.0)])
        doc.layers += [a1, b]
        p = os.path.join(tempfile.mkdtemp(), 'retouche.vnd')
        registry.save_document(doc, p)
        companion.sync(doc, p)
        doc.layers[:] = [a1, b, a0]                                         # « retouché dans TypeEdit » : réordonné
        registry.save_document(doc, p)                                      # empreinte changée, compagnon d'avant
        back = registry.open_document(p)
        said = ' | '.join(companion.apply(back, p))
        self.assertIn('renommer les calques', said)                         # dit dans les remarques, sans fenêtre
        self.assertEqual([L.name for L in back.layers], ['A', 'B', 'A'])
        self.assertFalse({L.id for L in back.layers} & {a0.id, a1.id},
                         'avant : un calque A prenait l’id de l’autre (opérations FAO redirigées)')

    def test_twin_layers_behind_a_layer_the_vnd_leaves_empty_keep_their_ids(self):
        from vectordrive.core.document import Document, Layer, Text
        from vectordrive.core.geom import Affine
        from vectordrive.io import companion, registry
        doc = Document()
        x = doc.layers[0]
        x.name = 'X'
        x.items.append(Text(text='', font='Arial', size=8, matrix=Affine.translation(5, 5)))   # rien à écrire
        a = Layer(name='Plan', items=[square(0.0)])
        a.visible = False
        b = Layer(name='Plan', items=[square(40.0)])
        doc.layers += [a, b]
        doc.extra['vnd_premier_plan'] = True                                # « premier calque montré en tête »
        p = os.path.join(tempfile.mkdtemp(), 'vide.vnd')
        registry.save_document(doc, p)
        companion.sync(doc, p)
        back = registry.open_document(p)
        self.assertEqual([L.name for L in back.layers], ['Plan', 'X', 'Plan'])     # écrit [b, X, a]
        said = ' | '.join(companion.apply(back, p))
        self.assertIn('renommer les calques', said)                         # ordre retrouvé par le repli
        ids = [L.id for L in back.layers]
        self.assertNotEqual(ids[0], a.id, 'avant : b prenait l’id de a (FAO de a et de b échangées)')
        self.assertNotEqual(ids[2], b.id, 'avant : a prenait l’id de b')
        self.assertAlmostEqual(back.layers[0].items[0].bbox()[0], 40.0, places=3)   # b garde son contour

    def test_twin_check_wants_the_direct_order_and_the_same_boxes(self):
        from vectordrive.core.document import Layer
        from vectordrive.io import companion
        hidden = Layer(name='Plan', items=[square(0.0)])
        hidden.visible = False
        comp = [hidden, Layer(name='Plan', items=[square(40.0)])]
        vnd = [Layer(name='Plan', items=[square(40.0)]), Layer(name='Plan', items=[square(0.0)])]
        self.assertEqual(companion._twins(vnd, comp, 'premier', [1, 0]), set())        # l'ordre de l'écriture
        self.assertEqual(companion._twins(vnd, comp, 'premier', [0, 1]), {'Plan'},
                         'avant : un ordre du repli, pas celui de l’écriture, passait pour vérifié')
        swapped = [Layer(name='Plan', items=[square(0.0)]), Layer(name='Plan', items=[square(40.0)])]
        self.assertEqual(companion._twins(swapped, comp, 'premier', [1, 0]), {'Plan'},
                         'avant : des contours à 40 mm l’un de l’autre passaient pour les mêmes')

    def test_no_image_from_a_twin_layer_named_in_the_warning_even_split_by_tool(self):
        from vectordrive.core.document import Document, Layer
        from vectordrive.core.geom import Affine
        from vectordrive.io import companion, registry
        clear = QImage(4, 2, QImage.Format.Format_ARGB32)
        clear.fill(QColor(0, 0, 255, 100))
        im = Image(data=encoded(clear, 'PNG'), fmt='png',
                   matrix=Affine.translation(60, 20) @ Affine.rotation(30) @ Affine(8, 0, 0, -4, 0, 4))
        doc = Document()
        doc.layers[0].name, doc.layers[0].visible = 'Plan', False
        doc.layers[0].items.append(square(0.0))
        doc.layers.append(Layer(name='Plan', items=[im, square(40.0)]))     # image outil 0, contour outil 1 : partagé
        doc.extra['vnd_premier_plan'] = True
        p = os.path.join(tempfile.mkdtemp(), 'partage.vnd')
        registry.save_document(doc, p)
        companion.sync(doc, p)
        back = registry.open_document(p)
        self.assertEqual([L.name for L in back.layers], ['Plan', 'Plan', 'Plan (2)'])
        said = ' | '.join(companion.apply(back, p))
        self.assertIn('renommer les calques', said)
        ims = [it for L in back.layers for it in companion._walk(L.items) if isinstance(it, Image)]
        self.assertEqual(len(ims), 1)
        self.assertNotEqual(ims[0].data, im.data, 'avant : image reprise d’un calque cité dans la remarque')

    def test_turned_image_comes_back_with_an_origin_at_zero(self):
        from vectordrive.core.document import Document
        from vectordrive.core.geom import Affine
        from vectordrive.io import companion, registry
        clear = QImage(4, 2, QImage.Format.Format_ARGB32)
        clear.fill(QColor(0, 0, 255, 100))
        im = Image(data=encoded(clear, 'PNG'), fmt='png',
                   matrix=Affine.translation(60, 20) @ Affine.rotation(30) @ Affine(8, 0, 0, -4, 0, 4))
        doc = Document()
        doc.layers[0].items.append(im)
        doc.extra['origine'] = (0.0, 0.0)                                   # posée au zéro : rien de décalé
        p = os.path.join(tempfile.mkdtemp(), 'zero.vnd')
        registry.save_document(doc, p)
        companion.sync(doc, p)
        back = registry.open_document(p)
        companion.apply(back, p)
        ims = [it for L in back.layers for it in L.items if isinstance(it, Image)]
        self.assertEqual([(i.data, i.matrix) for i in ims], [(im.data, im.matrix)], 'avant : image tournée perdue')


def pack(s, bpc: int, row: int) -> bytes:
    """Échantillons (lignes, n) → octets de `row` par ligne (gros-boutiste en 16 bits) : la référence des essais."""
    import numpy as np
    s = np.asarray(s)
    if bpc == 16:
        return s.astype('>u2').tobytes()
    if bpc == 8:
        return s.astype(np.uint8).tobytes()
    out = bytearray()
    for line in s:
        bits = ''.join(format(int(v), f'0{bpc}b') for v in line)
        bits += '0' * (row * 8 - len(bits))
        out += bytes(int(bits[k:k + 8], 2) for k in range(0, len(bits), 8))
    return bytes(out)


# --- fenêtre : import du PDF, BAT, enregistrement -----------------------------------------------------------------
def settings():
    from vectordrive.portable import settings as st
    return st()


def square(x=0.0):
    return Shape(path=geom.Path([geom.rect(x, 0, 10, 10)]), tool=1)


def png(path, color='#1040c0'):
    """Un petit logo PNG (dossier temporaire) ; rend son chemin."""
    q = QImage(8, 8, QImage.Format.Format_RGB32)
    q.fill(QColor(color))
    assert q.save(path, 'PNG')
    return path


class Window(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        for t in cls.w.docs:
            t.modified = False
        cls.w.modified = False
        cls.w.close()
        cls.w.deleteLater()
        app.processEvents()

    def setUp(self):
        st = settings()
        touched = ('bat/', 'fichiers/', 'dossier/')                         # dossier/importer, dossier/enregistrer…
        before = {k: st.value(k) for k in st.allKeys() if k.startswith(touched)}

        def put_back():
            for k in st.allKeys():
                if k.startswith(touched) and k not in before:
                    st.remove(k)
            for k, v in before.items():
                st.setValue(k, v)
            st.sync()
        self.addCleanup(put_back)
        self.w.new_document()
        self.w.canvas.doc.add(square())

    # 1. l'import d'un PDF qui n'a que des images
    def test_import_of_an_image_only_pdf_adds_the_image(self):
        w = self.w
        p = pdf_file(b'q 72 0 0 36 72 36 cm /Im0 Do Q',
                     [image('/Width 2 /Height 1 /ColorSpace /DeviceRGB /BitsPerComponent 8', bytes(6))], '/Im0 5 0 R',
                     name='photo.pdf')
        with mock.patch.object(QFileDialog, 'getOpenFileName', return_value=(p, '')):
            w.import_dialog()
        got = [it for it in w.canvas.selection if isinstance(it, Image)]
        self.assertEqual(len(got), 1, BEFORE_PDF)
        self.assertEqual(len(items(w.canvas.doc, Image)), 1)

    # 2. BAT : client et référence
    def bat(self, values=None, accept=True, logo2=None):
        """La fenêtre du BAT ouverte par `_proof_info` : rend (champs proposés, info) ; `values` écrits (et `logo2`
        posé) avant de valider. Le second logo proposé : `seen['logo2']`."""
        from vectordrive.ui import batdialog
        seen = {}

        def fake_exec(dlg):
            seen.update({k: e.text() for k, e in dlg.edits.items()})
            seen['logo2'] = dlg.logo2.currentData() or ''
            for k, v in (values or {}).items():
                dlg.edits[k].setText(v)
            if logo2 is not None:
                dlg.set_logo(dlg.logo2, logo2)
            return 1 if accept else 0
        with mock.patch.object(batdialog.BatDialog, 'exec', fake_exec):
            info = self.w._proof_info()
        return seen, info

    def test_new_drawing_opens_without_the_last_client(self):
        st = self.w.settings
        for k, v in (('client', 'Ancien client'), ('reference', 'R-OLD'), ('designation', 'Plaque'),
                     ('bat_number', '4'), ('notes', 'vieille remarque'), ('page', 'A3')):
            st.setValue(f'bat/{k}', v)
        seen, _info = self.bat(accept=False)
        self.assertEqual((seen['client'], seen['reference'], seen['designation']), ('', '', ''), BEFORE_BAT)
        self.assertEqual(seen['bat_number'], '1')
        for k in ('client', 'reference', 'designation', 'bat_number', 'notes'):
            self.assertFalse(st.contains(f'bat/{k}'), k)                     # retirés au premier passage
        self.assertEqual(st.value('bat/page'), 'A3')                        # la mise en page, elle, reste retenue
        from vectordrive.ui.batdialog import BatDialog
        from vectordrive.io import proof
        dlg = BatDialog(self.w, self.w.canvas.doc, proof.ProofInfo())
        self.addCleanup(dlg.deleteLater)
        self.assertTrue(dlg.edits['client'].placeholderText())              # « choisir dans le carnet »
        modified = self.w.modified
        self.bat({'material': ''})                                          # validé, cartouche vide
        self.assertNotIn('bat', self.w.canvas.doc.extra)                    # rien à garder dans le dessin
        self.assertEqual(self.w.modified, modified)

    def test_material_taken_from_the_plate_does_not_fill_the_title_block(self):
        from vectordrive.core.document import Plate
        w = self.w
        w.canvas.doc.plate = Plate(material='Laiton')
        modified = w.modified
        seen, _info = self.bat()                                            # validé tel que proposé
        self.assertEqual(seen['material'], 'Laiton')                        # reprise de la plaque
        self.assertNotIn('bat', w.canvas.doc.extra, 'avant : la matière de la plaque rendait le cartouche rempli')
        self.assertEqual(w.modified, modified)
        self.bat({'client': 'Dupont'})
        self.assertEqual((w.canvas.doc.extra['bat']['client'], w.canvas.doc.extra['bat']['material']), ('Dupont', ''))

    def test_bat_fields_survive_a_vnd_and_its_companion(self):
        w = self.w
        self.bat({'client': 'Dupont', 'reference': 'R-7'})
        folder = tempfile.mkdtemp()
        with mock.patch.object(QFileDialog, 'getSaveFileName', return_value=(os.path.join(folder, 'piece'), '')):
            w.save()
        vnd = os.path.join(folder, 'piece.vnd')
        self.assertTrue(os.path.isfile(vnd))
        self.assertTrue(os.path.isfile(os.path.join(folder, 'piece.vdz')), BEFORE_BAT)     # le compagnon
        w.canvas.doc.extra.pop('bat')
        self.assertTrue(w.open_path(vnd))
        self.assertEqual(w.canvas.doc.extra.get('bat', {}).get('client'), 'Dupont')
        seen, _info = self.bat(accept=False)
        self.assertEqual((seen['client'], seen['reference']), ('Dupont', 'R-7'))

    def test_second_edition_of_the_same_drawing_keeps_its_client(self):
        w = self.w
        first = w.docs[w.doc_index]
        logo = png(os.path.join(tempfile.mkdtemp(), 'dupont.png'))
        seen, info = self.bat({'client': 'Dupont', 'reference': 'R-12', 'bat_number': '2'}, logo2=logo)
        self.assertEqual((info.client, info.reference, info.logo2), ('Dupont', 'R-12', logo))
        self.assertFalse(w.settings.contains('bat/client'), BEFORE_BAT)
        self.assertFalse(w.settings.contains('bat/reference'))
        self.assertFalse(w.settings.contains('bat/logo2'))
        self.assertEqual(w.canvas.doc.extra['bat']['client'], 'Dupont')     # dans le dessin
        self.assertEqual(w.canvas.doc.extra['bat']['logo2'], logo)
        self.assertTrue(w.modified)
        seen, _info = self.bat(accept=False)                                # deuxième édition : ceux du dessin
        self.assertEqual((seen['client'], seen['reference'], seen['bat_number']), ('Dupont', 'R-12', '2'))
        self.assertEqual(os.path.normcase(seen['logo2']), os.path.normcase(logo))
        w.new_document()                                                    # un autre dessin : vide
        seen, _info = self.bat(accept=False)
        self.assertEqual((seen['client'], seen['reference'], seen['logo2']), ('', '', ''))
        w.switch_tab(w.docs.index(first))
        out = os.path.join(tempfile.mkdtemp(), 'bat.vdz')                   # enregistré, rouvert : toujours là
        self.assertTrue(w._write(out))
        self.assertTrue(w.open_path(out))
        seen, _info = self.bat(accept=False)
        self.assertEqual((seen['client'], seen['reference']), ('Dupont', 'R-12'))
        self.assertEqual(os.path.normcase(seen['logo2']), os.path.normcase(logo))

    def test_client_typed_by_hand_gets_no_previous_client_logo(self):
        w = self.w
        from vectordrive.ui import options
        self.assertNotIn('bat/logo2', options.BY_KEY, BEFORE_BAT)          # plus un réglage de F10
        w.settings.setValue('bat/logo2', png(os.path.join(tempfile.mkdtemp(), 'ancien.png')))
        logo = png(os.path.join(tempfile.mkdtemp(), 'dupont.png'))
        seen, _info = self.bat({'client': 'Dupont'}, logo2=logo)            # un premier dessin, son client
        self.assertEqual(seen['logo2'], '')                                 # l'ancien réglage : retiré
        self.assertFalse(w.settings.contains('bat/logo2'))
        w.new_document()                                                    # un dessin neuf, client tapé à la main
        seen, info = self.bat({'client': 'Martin'})
        self.assertEqual(seen['logo2'], '', BEFORE_BAT)
        self.assertEqual((info.client, info.logo2), ('Martin', ''))
        self.assertEqual(w.canvas.doc.extra['bat']['logo2'], '')

    # 3. VND d'office
    def test_new_drawing_is_saved_as_vnd_by_default(self):
        w = self.w
        from vectordrive.ui import closed_store
        w.settings.remove('fichiers/format_enregistrement')
        folder = tempfile.mkdtemp()
        vnd = tr_filter(w, 1)
        with mock.patch.object(QFileDialog, 'getSaveFileName', return_value=(os.path.join(folder, 'neuf'), '')) as ask:
            w.save()                                                        # Ctrl+S d'un dessin jamais enregistré
        self.assertEqual(ask.call_args[0][4], vnd, BEFORE_SAVE)
        self.assertTrue(os.path.isfile(os.path.join(folder, 'neuf.vnd')))
        self.assertTrue(w.path.lower().endswith('neuf.vnd'))
        # un VDZ ouvert se réenregistre en VDZ
        p = os.path.join(folder, 'garde.vdz')
        self.assertTrue(w._write(p))
        self.assertTrue(w.open_path(p))
        with mock.patch.object(QFileDialog, 'getSaveFileName', return_value=('', '')) as ask:
            w.save_as()
        self.assertEqual(ask.call_args[0][4], tr_filter(w, 0))
        # un brouillon gardé (onglet fermé sans question) reste un .vdz interne
        w.new_document()
        w.canvas.doc.add(square(30.0))
        kept = closed_store.keep(w.docs[w.doc_index], where=pathlib.Path(tempfile.mkdtemp()))
        self.assertTrue(str(kept.as_dict()['file']).endswith('.vdz'))

    def test_turned_and_transparent_images_come_back_from_the_vnd(self):
        w = self.w
        from vectordrive.core.geom import Affine
        opaque = QImage(4, 2, QImage.Format.Format_RGB32)
        opaque.fill(QColor('#ff0000'))
        clear = QImage(4, 2, QImage.Format.Format_ARGB32)
        clear.fill(QColor(0, 0, 255, 100))
        turned = Image(data=encoded(opaque, 'PNG'), fmt='png',
                       matrix=Affine.translation(20, 20) @ Affine.rotation(30) @ Affine(8, 0, 0, -4, 0, 4))
        see = Image(data=encoded(clear, 'PNG'), fmt='png', matrix=Affine(8, 0, 0, -4, 40, 4))
        w.canvas.doc.add(turned)
        w.canvas.doc.add(see)
        folder = tempfile.mkdtemp()
        with mock.patch.object(QFileDialog, 'getSaveFileName', return_value=(os.path.join(folder, 'images'), '')):
            w.save()                                                        # Ctrl+S d'un dessin neuf : VND
        vnd = os.path.join(folder, 'images.vnd')
        self.assertTrue(os.path.isfile(vnd))
        self.assertTrue(os.path.isfile(os.path.join(folder, 'images.vdz')), 'avant : pas de compagnon')
        self.assertTrue(w.open_path(vnd))
        back = items(w.canvas.doc, Image)
        self.assertEqual(len(back), 2)
        for a, b in zip((turned, see), back):
            self.assertEqual(b.data, a.data)                                # la transparence gardée
            for u, v in zip((a.matrix.a, a.matrix.b, a.matrix.c, a.matrix.d, a.matrix.e, a.matrix.f),
                            (b.matrix.a, b.matrix.b, b.matrix.c, b.matrix.d, b.matrix.e, b.matrix.f)):
                self.assertAlmostEqual(u, v, places=6)                      # la rotation gardée

    def test_vdz_is_the_only_other_choice(self):
        w = self.w
        from vectordrive.ui import options
        o = options.BY_KEY['fichiers/format_enregistrement']
        self.assertEqual((o.default, [c[0] for c in o.choices]), ('vnd', ['vnd', 'vdz']), BEFORE_SAVE)
        w.settings.setValue('fichiers/format_enregistrement', 'vdz')
        folder = tempfile.mkdtemp()
        with mock.patch.object(QFileDialog, 'getSaveFileName', return_value=(os.path.join(folder, 'neuf'), '')) as ask:
            w.save_as()
        self.assertEqual(ask.call_args[0][4], tr_filter(w, 0))
        self.assertTrue(os.path.isfile(os.path.join(folder, 'neuf.vdz')))
        self.assertEqual(w.save_default_ext(), '.vdz')


def tr_filter(w, i):
    """Le libellé du filtre VDZ (0) ou VND (1) de la boîte « Enregistrer sous »."""
    return w.save_filters()[i][0]


if __name__ == '__main__':
    unittest.main()
