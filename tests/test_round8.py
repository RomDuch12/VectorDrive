"""Round 8 : codes-barres, contours superposés, sens, mesure."""
import math
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import barcode as B
from vectordrive.core import cleanup, codes, geom
from vectordrive.core.document import Document, Group, Layer, Shape
from vectordrive.core.geom import Affine, Path
from vectordrive.io import native, registry

try:
    import numpy as np
    import zxingcpp
except ImportError:                       # décodeur de contrôle (outil de test)
    zxingcpp = None


def rasterize(path: Path, px_per_mm: float = 12.0, margin_mm: float = 4.0):
    """Dessin vectoriel → image en niveaux de gris (noir = matière gravée)."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QImage, QPainter, QTransform
    from PySide6.QtWidgets import QApplication
    from vectordrive.ui.canvas import to_qpath
    QApplication.instance() or QApplication([])
    x0, y0, x1, y1 = path.bbox()
    w = int((x1 - x0 + 2 * margin_mm) * px_per_mm)
    h = int((y1 - y0 + 2 * margin_mm) * px_per_mm)
    img = QImage(w, h, QImage.Format.Format_Grayscale8)
    img.fill(QColor('white'))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setTransform(QTransform(px_per_mm, 0, 0, -px_per_mm, (margin_mm - x0) * px_per_mm,
                              (y1 + margin_mm) * px_per_mm))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor('black'))
    qp = to_qpath(path)
    qp.setFillRule(Qt.FillRule.OddEvenFill)
    p.drawPath(qp)
    p.end()
    ptr = img.constBits()
    arr = np.frombuffer(ptr, np.uint8, img.sizeInBytes()).reshape(h, img.bytesPerLine())[:, :w]
    return arr.copy()


class TestCode128(unittest.TestCase):
    def test_table(self):
        self.assertEqual(len(B._C128), 107)
        self.assertEqual(len(set(B._C128)), 107)
        for i, pat in enumerate(B._C128):
            widths = [int(c) for c in pat]
            self.assertEqual(sum(widths), 13 if i == 106 else 11, i)
            self.assertEqual(sum(widths[0::2]) % 2, 0, i)        # barres : somme paire

    def test_subsets(self):
        v = B.code128_values('1234567890')
        self.assertEqual(v[0], 105)                               # départ C
        self.assertEqual(v[1:6], [12, 34, 56, 78, 90])
        v = B.code128_values('AB12345678CD')
        self.assertIn(99, v)                                      # passage en C
        self.assertEqual(B.code128_values('Wikipedia')[-2], 88)   # contrôle de l'exemple courant
        with self.assertRaises(B.CodeError):
            B.code128('é')


@unittest.skipIf(zxingcpp is None, 'zxing-cpp absent (pip install zxing-cpp)')
class TestDecodeDrawn(unittest.TestCase):
    """Le dessin vectoriel produit se relit avec un décodeur indépendant."""

    def check(self, spec, fmt):
        body, _txt = codes.paths(spec)
        res = zxingcpp.read_barcodes(rasterize(body))
        got = [(r.format.name, r.text) for r in res]
        expect = codes.human_text(spec) if spec.kind == 'ean13' else spec.text
        self.assertIn((fmt, expect), got, f'{spec.kind}/{spec.style}: {got}')

    def test_2d_styles(self):
        for style in ('runs', 'squares', 'outline'):
            with self.subTest(style=style):
                self.check(codes.BarcodeSpec('datamatrix', 'BFM 2026 #42', 0.5, style=style), 'DataMatrix')
                self.check(codes.BarcodeSpec('qr', 'https://bfm.example/VectorDrive', 0.5, style=style), 'QRCode')

    def test_linear(self):
        self.check(codes.BarcodeSpec('code128', 'VD0042-A42', 0.3, height=10), 'Code128')
        self.check(codes.BarcodeSpec('code39', 'BFM-2026', 0.3, height=10), 'Code39')
        self.check(codes.BarcodeSpec('ean13', '400638133393', 0.33, height=15), 'EAN13')


class TestBarcodeItem(unittest.TestCase):
    def test_group_and_save(self):
        spec = codes.BarcodeSpec('datamatrix', 'ABC123', 0.4, style='outline')
        g = codes.build(spec, tool=3)
        self.assertEqual(g.tool, 3)
        self.assertTrue(all(c.filled for c in g.children))
        bb = g.bbox()
        self.assertAlmostEqual(bb[0], 0)
        self.assertAlmostEqual(bb[1], 0)
        d = Document()
        d.add(g.transformed(Affine.translation(10, 20)))
        with tempfile.TemporaryDirectory() as t:
            f = pathlib.Path(t) / 'b.vdz'
            native.write(d, f)
            back = registry.open_document(f).layers[0].items[0]
        self.assertEqual(codes.BarcodeSpec.from_dict(back.extra['barcode']), spec)

    def test_dots(self):
        spec = codes.BarcodeSpec('datamatrix', 'X', 1.0, style='dots', dot_ratio=0.5)
        body, _ = codes.paths(spec)
        n_dark = sum(v for row in codes.matrix(spec) for v in row)
        self.assertEqual(len(body.contours), n_dark)
        self.assertAlmostEqual(body.contours[0].length(), math.pi * 0.5, places=9)


class TestCleanup(unittest.TestCase):
    def test_same_contour(self):
        a = geom.rect(0, 0, 10, 10)
        self.assertTrue(cleanup.same_contour(a, a.reversed()))
        self.assertTrue(cleanup.same_contour(a, a.transformed(Affine.translation(0.004, 0))))
        self.assertFalse(cleanup.same_contour(a, a.transformed(Affine.translation(0.05, 0))))
        self.assertFalse(cleanup.same_contour(a, geom.rect(0, 0, 10, 10.5)))
        c = geom.circle((5, 5), 4)
        self.assertFalse(cleanup.same_contour(a, c))

    def test_dedupe_aligned(self):
        s1 = Shape(path=Path([geom.rect(0, 0, 5, 5), geom.circle((20, 0), 2)]))
        s2 = Shape(path=Path([geom.rect(0, 0, 5, 5)]))
        s3 = Shape(path=Path([geom.circle((20, 0), 2), geom.rect(40, 0, 5, 5)]))
        res, n = cleanup.dedupe([s1, s2, s3])
        self.assertEqual(n, 2)
        self.assertIs(res[0], s1)
        self.assertIsNone(res[1])
        self.assertEqual(len(res[2].path.contours), 1)

    def test_window_per_layer(self):
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            d = w.canvas.doc
            d.layers = [Layer('A', tool=0), Layer('B', tool=1)]
            for L in d.layers:
                L.items.append(Shape(path=Path([geom.rect(0, 0, 10, 10)]), tool=L.tool))
            d.layers[0].items.append(Shape(path=Path([geom.rect(0, 0, 10, 10)])))
            self.assertEqual(w.remove_duplicates(0.01), 1)            # dans le calque A seulement
            self.assertEqual([len(L.items) for L in d.layers], [1, 1])
            self.assertEqual(w.remove_duplicates(0.01, across=True), 1)
            self.assertEqual([len(L.items) for L in d.layers], [1, 0])
            w.undo()
            self.assertEqual([len(L.items) for L in w.canvas.doc.layers], [1, 1])
            # sens inverse
            sh = w.canvas.doc.layers[0].items[0]
            area = sh.path.contours[0].signed_area()
            w.canvas.select([sh])
            w.reverse_contours()
            self.assertAlmostEqual(w.canvas.selection[0].path.contours[0].signed_area(), -area)
        finally:
            w.modified = False
            w.close()

    def test_measure_text(self):
        from vectordrive.ui.tools import MeasureTool
        s = MeasureTool.describe((0, 0), (3, 4))
        self.assertIn('5.000', s)
        self.assertIn('53.13', s)


if __name__ == '__main__':
    unittest.main()
