"""Round 33 : images bitmap (ouverture, export PNG/JPEG, écriture VND)."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import geom
from vectordrive.core.document import Document, Image, Plate, Shape
from vectordrive.core.geom import Path
from vectordrive.io import raster, registry, vnd, vnd_write


class TestRaster(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_export_png_size_and_pixels(self):
        from PySide6.QtGui import QImage
        d = Document()
        d.add(Shape(path=Path([geom.rect(0, 0, 10, 5)]), filled=True))
        with tempfile.TemporaryDirectory() as tmp:
            f = pathlib.Path(tmp) / 'a.png'
            raster.write(d, f, raster.RasterSpec(dpi=254, margin=1, include_plate=False))
            img = QImage(str(f))
        self.assertEqual((img.width(), img.height()), (120, 70))        # 10 px/mm, marge 1 mm
        self.assertAlmostEqual(img.dotsPerMeterX(), 10000, delta=1)
        self.assertNotEqual(img.pixelColor(60, 35).name(), '#ffffff')   # intérieur rempli
        self.assertEqual(img.pixelColor(3, 3).name(), '#ffffff')

    def test_jpeg_and_transparency(self):
        from PySide6.QtGui import QImage
        d = Document()
        d.plate = Plate(20, 10)
        d.add(Shape(path=Path([geom.circle((10, 5), 3)])))
        with tempfile.TemporaryDirectory() as tmp:
            f = pathlib.Path(tmp) / 'a.jpg'
            registry.save_document(d, f)
            img = QImage(str(f))
            self.assertFalse(img.isNull())
            g = pathlib.Path(tmp) / 't.png'
            raster.write(d, g, raster.RasterSpec(dpi=100, transparent=True, include_plate=False))
            self.assertEqual(QImage(str(g)).pixelColor(0, 0).alpha(), 0)

    def test_open_image_document_and_vnd(self):
        from PySide6.QtGui import QColor, QImage
        img = QImage(200, 100, QImage.Format.Format_RGB32)
        img.fill(QColor('white'))
        for x in range(50, 150):
            for y in range(25, 75):
                img.setPixelColor(x, y, QColor('black'))
        img.setDotsPerMeterX(10000)                                   # 254 dpi : 10 px/mm
        img.setDotsPerMeterY(10000)
        with tempfile.TemporaryDirectory() as tmp:
            f = pathlib.Path(tmp) / 'logo.png'
            img.save(str(f))
            d = registry.open_document(f)
            im = d.layers[0].items[0]
            self.assertIsInstance(im, Image)
            self.assertEqual(im.fmt, 'png')
            bb = im.bbox()
            self.assertAlmostEqual(bb[2] - bb[0], 20, places=6)
            self.assertAlmostEqual(bb[3] - bb[1], 10, places=6)
            # écrit en VND : DIB 24 bits relue
            data, _rep = vnd_write.write_document(d)
            g = pathlib.Path(tmp) / 'logo.vnd'
            g.write_bytes(data)
            back = registry.open_document(g)
        ims = [it for it in back.iter_leaves() if isinstance(it, Image)]
        self.assertEqual(len(ims), 1)
        self.assertEqual(ims[0].fmt, 'dib')
        self.assertEqual(raster.dib_info(ims[0].data), (200, 100, 24))
        bb2 = ims[0].bbox()
        for a, b in zip(bb, bb2):
            self.assertAlmostEqual(a, b, places=6)

    def test_empty_drawing(self):
        with self.assertRaises(ValueError):
            raster.render(Document(), raster.RasterSpec())


if __name__ == '__main__':
    unittest.main()
