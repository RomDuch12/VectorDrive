"""Round 224 : grandes images — Qt refusait toute image de plus de 256 Mo
décodés (photos de 8 334 et 10 000 px de côté de l'atelier : « image
illisible ») ; limite levée, image réduite à l'ouverture au-delà de
MAX_PIXELS, taille en mm de l'original gardée, raison de Qt dans l'erreur."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtGui import QColor, QImage, QImageReader
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


def png(path: pathlib.Path, w: int, h: int, dpi: float = 254.0) -> pathlib.Path:
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(QColor('white'))
    img.setDotsPerMeterX(int(dpi / 0.0254))
    img.setDotsPerMeterY(int(dpi / 0.0254))
    img.save(str(path))
    return path


class TestLargeImages(unittest.TestCase):
    def test_limit_lifted_and_reduced_on_load(self):
        from vectordrive.io import raster
        tmp = pathlib.Path(tempfile.mkdtemp())
        f = png(tmp / 'grande.png', 400, 300)                                 # 254 dpi : 40 × 30 mm
        img, orig, note = raster.load_image(f)
        self.assertEqual(QImageReader.allocationLimit(), 0)                   # plus de refus à 256 Mo
        self.assertEqual((img.width(), img.height(), note), (400, 300, None))
        with mock.patch.object(raster, 'MAX_PIXELS', 30_000):                 # au-delà : réduite à la lecture
            img, orig, note = raster.load_image(f)
            self.assertEqual((orig.width(), orig.height()), (400, 300))
            self.assertLessEqual(img.width() * img.height(), 30_000)
            self.assertAlmostEqual(img.width() / img.height(), 4 / 3, 1)
            self.assertIn('réduite de 400 × 300', note)
            doc = raster.read(f)
        im = next(doc.iter_leaves())
        self.assertAlmostEqual(im.matrix.a, 40.0, 1)                          # taille réelle de l'original
        self.assertAlmostEqual(-im.matrix.d, 30.0, 1)
        self.assertTrue(any('400 × 300 px' in r for r in doc.report))
        self.assertTrue(any('réduite' in r for r in doc.report))

    def test_error_says_why(self):
        from vectordrive.io import raster
        tmp = pathlib.Path(tempfile.mkdtemp())
        bad = tmp / 'rien.jpg'
        bad.write_bytes(b'pas une image')
        with self.assertRaises(ValueError) as cm:
            raster.load_image(bad)
        self.assertIn('rien.jpg', str(cm.exception))
        self.assertIn('(', str(cm.exception))                                 # la raison de Qt

    def test_load_gray_uses_it(self):
        from vectordrive.ui.dialogs import load_gray
        tmp = pathlib.Path(tempfile.mkdtemp())
        g = load_gray(str(png(tmp / 'p.png', 50, 20)))
        self.assertEqual(g.shape, (20, 50))
        self.assertAlmostEqual(float(g.max()), 1.0, 3)


if __name__ == '__main__':
    unittest.main()
