"""Round 553 : BAT personnalisable — en-tête avec le logo et le nom de l'entreprise (F10 › BAT), dans
l'aperçu, le PDF et l'impression."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Document, Shape
from vectordrive.io import proof

app = QApplication.instance() or QApplication([])


def logo_file() -> str:
    img = QImage(200, 100, QImage.Format.Format_RGB32)
    img.fill(QColor('#204080'))
    f = pathlib.Path(tempfile.mkdtemp()) / 'logo.png'
    img.save(str(f))
    return str(f)


class TestHeader(unittest.TestCase):
    def setUp(self):
        self.doc = Document()
        self.doc.add(Shape(path=geom.Path([geom.rect(0, 0, 60, 20)])))

    def test_logo_and_company(self):
        info = proof.ProofInfo(company='Atelier Essai', logo=logo_file())
        prims, PW, PH = proof.build(self.doc, info)
        imgs = [p for p in prims if p.image is not None]
        self.assertEqual(len(imgs), 1)
        corners = [imgs[0].matrix.apply(c) for c in ((0, 0), (1, 1))]
        (x0, y0), (x1, y1) = corners
        self.assertAlmostEqual(y0 - y1, proof.LOGO_H, places=6)                 # 10 mm de haut
        self.assertAlmostEqual(x1 - x0, 2 * proof.LOGO_H, places=6)             # proportions 2:1
        self.assertGreaterEqual(y1, PH - info.margin - 14)                       # bande d'en-tête, hors du dessin
        f = pathlib.Path(tempfile.mkdtemp()) / 'bat.pdf'
        proof.write(self.doc, f, info)
        self.assertGreater(f.stat().st_size, 1000)

    def test_missing_logo(self):
        info = proof.ProofInfo(logo='Z:/absent/logo.png')
        prims, _PW, _PH = proof.build(self.doc, info)
        self.assertFalse([p for p in prims if p.image is not None])             # BAT sans logo, sans erreur

    def test_options(self):
        from vectordrive.ui.options import BY_KEY
        self.assertEqual(BY_KEY['bat/logo'].kind, 'file')
        self.assertIn('bat/company', BY_KEY)
        self.assertIn('logo', proof.LAYOUT_FIELDS)


if __name__ == '__main__':
    unittest.main()
