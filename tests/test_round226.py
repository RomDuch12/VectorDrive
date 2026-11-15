"""Round 226 : photos de téléphone — l'orientation EXIF est appliquée à
l'ouverture (une photo prise en portrait arrivait couchée), taille en mm et
réduction cohérentes avec l'image redressée."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

try:
    from PIL import Image as PILImage
except ImportError:                                    # Pillow n'est pas une dépendance de VectorDrive
    PILImage = None


def exif_jpeg(path: pathlib.Path, w: int, h: int, orientation: int) -> pathlib.Path:
    im = PILImage.new('RGB', (w, h), 'white')
    exif = PILImage.Exif()
    exif[0x0112] = orientation
    im.save(str(path), 'JPEG', exif=exif.tobytes(), dpi=(254, 254))
    return path


@unittest.skipIf(PILImage is None, 'Pillow absent (écriture des données EXIF)')
class TestExifOrientation(unittest.TestCase):
    def test_portrait_photo_is_upright(self):
        from vectordrive.io import raster
        tmp = pathlib.Path(tempfile.mkdtemp())
        f = exif_jpeg(tmp / 'photo.jpg', 400, 200, 6)                        # capteur 400 × 200, à tourner de 90°
        img, orig, note = raster.load_image(f)
        self.assertEqual((img.width(), img.height()), (200, 400))            # redressée
        self.assertEqual((orig.width(), orig.height()), (200, 400))          # taille d'origine dans le même sens
        doc = raster.read(f)
        im = next(doc.iter_leaves())
        self.assertAlmostEqual(im.matrix.a, 20.0, 1)                         # 200 px à 254 dpi
        self.assertAlmostEqual(-im.matrix.d, 40.0, 1)
        with mock.patch.object(raster, 'MAX_PIXELS', 20_000):                # réduite ET redressée
            img, orig, note = raster.load_image(f)
            self.assertLess(img.width(), img.height())
            self.assertEqual((orig.width(), orig.height()), (200, 400))
            self.assertIn('à 100 × 200 px', note)

    def test_plain_image_unchanged(self):
        from vectordrive.io import raster
        tmp = pathlib.Path(tempfile.mkdtemp())
        f = exif_jpeg(tmp / 'droite.jpg', 300, 100, 1)
        img, orig, note = raster.load_image(f)
        self.assertEqual((img.width(), img.height(), orig.width(), orig.height(), note), (300, 100, 300, 100, None))


if __name__ == '__main__':
    unittest.main()
