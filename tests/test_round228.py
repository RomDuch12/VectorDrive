"""Round 228 : les textes des PDF deviennent des textes vivants (chaîne
décodée par pypdf, position, corps, police de base ou Arial, rotation)."""
import math
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

try:
    from reportlab.pdfgen import canvas
except ImportError:                                    # reportlab n'est pas une dépendance de VectorDrive
    canvas = None

PT = 25.4 / 72


def sample(path: pathlib.Path) -> pathlib.Path:
    c = canvas.Canvas(str(path), pagesize=(200, 100))
    c.setFont('Helvetica-Bold', 12)
    c.drawString(20, 30, 'Bonjour PDF')
    c.setFont('Times-Italic', 8)
    c.drawString(100, 60, 'Penché')
    c.saveState()
    c.translate(150, 20)
    c.rotate(30)
    c.setFont('Helvetica', 6)
    c.drawString(0, 0, 'Tourné')
    c.restoreState()
    c.line(0, 0, 200, 0)
    c.save()
    return path


@unittest.skipIf(canvas is None, 'reportlab absent (écriture du PDF d\'essai)')
class TestPdfTexts(unittest.TestCase):
    def test_texts_become_live(self):
        from vectordrive.core import fonts
        from vectordrive.core.document import Text
        from vectordrive.io import registry
        d = registry.open_document(str(sample(pathlib.Path(tempfile.mkdtemp()) / 'textes.pdf')))
        texts = {t.text: t for t in d.iter_leaves() if isinstance(t, Text)}
        self.assertEqual(set(texts), {'Bonjour PDF', 'Penché', 'Tourné'})
        b = texts['Bonjour PDF']
        self.assertIn('Arial', b.font)                                               # Helvetica → Arial (gras si présent)
        x, y = b.matrix.apply((0.0, 0.0))
        self.assertAlmostEqual((x, y), (20 * PT, 30 * PT), 3)                         # ligne de base en mm
        m = fonts.metrics(*fonts.find_font(b.font))
        self.assertAlmostEqual(b.size, 12 * PT * m['cap'] / m['upem'], 3)
        p = texts['Penché']
        self.assertIn('Times', p.font)
        self.assertEqual(p.extra.get('italic'), 12.0)
        r = texts['Tourné']
        x, y = r.matrix.apply((0.0, 0.0))
        ux, uy = r.matrix.apply((1.0, 0.0))
        self.assertAlmostEqual(math.degrees(math.atan2(uy - y, ux - x)), 30.0, 3)
        self.assertAlmostEqual((x, y), (150 * PT, 20 * PT), 3)
        self.assertEqual(sum(1 for it in d.iter_leaves() if not isinstance(it, Text)), 1)   # la ligne
        self.assertTrue(any('3 texte(s) PDF repris' in r for r in d.report), d.report)
        self.assertFalse(any('non vectorisé' in r for r in d.report), d.report)


if __name__ == '__main__':
    unittest.main()
