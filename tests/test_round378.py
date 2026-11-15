"""Round 378 : texte — ressorts (TypeEdit : fonction Ressort) : l'espace
libre de la ligne partagé entre les ressorts."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import fonts, text as TX
from vectordrive.core.document import Text

app = QApplication.instance() or QApplication([])
FONT = 'Arial'
S = TX.SPRING


@unittest.skipUnless(fonts.find_font(FONT), 'police Arial absente')
class TestSprings(unittest.TestCase):
    def test_split(self):
        p = TX.layout(f'A{S}B', FONT, 5.0, spring_width=50.0)
        b = p.bbox()
        self.assertAlmostEqual(b[0], TX.layout('A', FONT, 5.0).bbox()[0], 6)
        self.assertAlmostEqual(b[2], 50.0, 0)                               # B poussé au bout de la ligne
        self.assertEqual(len(p.contours), len(TX.layout('AB', FONT, 5.0).contours))   # le ressort ne se dessine pas

    def test_centered_and_shared(self):
        w = TX.advance('X', FONT, 5.0)
        c = TX.layout(f'{S}X{S}', FONT, 5.0, spring_width=40.0).bbox()
        self.assertAlmostEqual((c[0] + c[2]) / 2, 20.0, 0)                 # deux ressorts : centré
        r = TX.layout(f'{S}{S}X', FONT, 5.0, spring_width=40.0).bbox()
        self.assertAlmostEqual(r[2], 40.0, 0)
        self.assertGreater(w, 0)

    def test_widest_line_and_text(self):
        lines = TX.layout(f'MMMMMMMM\nA{S}B', FONT, 5.0).bbox()
        top = TX.layout('MMMMMMMM', FONT, 5.0).bbox()
        self.assertAlmostEqual(lines[2], top[2], 0)                         # sans largeur : la plus longue ligne
        t = Text(text=f'N{S}1', font=FONT, size=5.0)
        t.extra['fit'] = {'width': 60.0, 'mode': 'spacing'}
        self.assertAlmostEqual(TX.outline_for(t).bbox()[2], 60.0, delta=1.5)  # largeur imposée (approche du 1)
        self.assertEqual(t.spacing, 0.0)                                    # pas d'ajustement par l'interlettrage


if __name__ == '__main__':
    unittest.main()
