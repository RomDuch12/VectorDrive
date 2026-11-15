"""Round 134 : textes TypeEdit vivants de plusieurs lignes — une ligne de
base par ligne dans `courbe1` (TypeEdit 13 n'affichait que la 1ʳᵉ ligne)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import fonts as F
from vectordrive.core import text as TX
from vectordrive.core.document import Text
from vectordrive.core.geom import Affine
from vectordrive.io import paragraph as PG


@unittest.skipUnless(F.find_font('Arial'), 'Arial absente')
class TestBaselines(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QApplication.instance() or QApplication([])

    def build(self, text, align='center'):
        t = Text(text=text, font='Arial', size=6, align=align, matrix=Affine.translation(100, 150))
        t.outline = TX.outline_for(t)
        return t, PG.build(t, 0)

    def baselines(self, p):
        out = []
        for c in p.fields['courbe1'].children:
            pts = c.fields['points']
            out.append(((pts[0][0] * 1000, pts[0][1] * 1000), (pts[-1][0] * 1000, pts[-1][1] * 1000)))
        return out

    def test_one_baseline_per_line(self):
        t, p = self.build('Beijing\n(Att Fichier)')
        bl = self.baselines(p)
        self.assertEqual(len(bl), 2)
        (a0, a1), (b0, b1) = bl
        self.assertAlmostEqual(a0[1], 150.0, places=6)                     # 1ʳᵉ ligne au point d'ancrage
        self.assertAlmostEqual(a0[1], a1[1], places=9)                      # horizontale
        self.assertLess(b0[1], a0[1])                                       # 2ᵉ ligne plus bas
        pitch = TX.em_for_height(F.find_font('Arial'), 6) * t.line_spacing
        self.assertAlmostEqual(a0[1] - b0[1], pitch, places=6)
        # centrées : milieux alignés sur 100 mm, la 2ᵉ (plus longue) plus large
        self.assertAlmostEqual((a0[0] + a1[0]) / 2, 100.0, delta=0.5)
        self.assertAlmostEqual((b0[0] + b1[0]) / 2, 100.0, delta=0.5)
        self.assertGreater(b1[0] - b0[0], a1[0] - a0[0])
        self.assertEqual(len(p.fields['para1']['lines']), 2)

    def test_single_line_unchanged(self):
        _t, p = self.build('Plaque 12', 'left')
        self.assertEqual(len(self.baselines(p)), 1)

    def test_blank_line_has_no_baseline(self):
        _t, p = self.build('Haut\n\nBas')
        self.assertEqual(len(self.baselines(p)), 2)
        self.assertEqual(len(p.fields['para1']['lines']), 3)


if __name__ == '__main__':
    unittest.main()
