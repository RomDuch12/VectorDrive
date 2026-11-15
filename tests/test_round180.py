"""Round 180 : italique et souligné des textes (TypeEdit, Rapido)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import fonts, text as TX
from vectordrive.core.document import Text

FONT = next((f for f in ('Arial', 'DejaVu Sans', 'Segoe UI', 'Calibri') if fonts.is_available(f)), None)


@unittest.skipIf(FONT is None, 'aucune police de référence')
class TestStyles(unittest.TestCase):
    def test_underline(self):
        t = Text(text='AB\nCDEF', font=FONT, size=10)
        plain = TX.outline_for(t)
        t.extra['underline'] = True
        u = TX.outline_for(t)
        self.assertEqual(len(u.contours), len(plain.contours) + 2)                 # une barre par ligne
        bars = u.contours[-2:]
        b0, b1 = bars[0].bbox(), bars[1].bbox()
        self.assertAlmostEqual(b0[3] - b0[1], 0.7, places=6)
        self.assertLess(b0[3], 0)                                                  # sous la ligne de base
        self.assertGreater(b1[2] - b1[0], b0[2] - b0[0])                           # 2e ligne plus longue

    def test_italic_shears(self):
        t = Text(text='I', font=FONT, size=10)
        b = TX.outline_for(t).bbox()
        t.extra['italic'] = 12.0
        bi = TX.outline_for(t).bbox()
        self.assertAlmostEqual((bi[2] - bi[0]) - (b[2] - b[0]), 10 * math.tan(math.radians(12)), delta=0.6)
        self.assertAlmostEqual(bi[1], b[1], places=6)                              # pied sur la ligne de base

    def test_toggle_command(self):
        app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertEqual((TE_ACTIONS['ID_RAPIDO_CHAR_PBITALIC'], TE_ACTIONS['ID_RAPIDO_CHAR_PBUNDERLINE_DLL']),
                         ('text_italic', 'text_underline'))
        w = MainWindow()
        try:
            a = w.canvas.doc.add(Text(text='A', font=FONT, size=5))
            b = w.canvas.doc.add(Text(text='B', font=FONT, size=5))
            b.extra['italic'] = 12.0
            w.canvas.select([a, b])
            w.toggle_text_style('italic')
            self.assertEqual((a.extra.get('italic'), b.extra.get('italic')), (12.0, 12.0))     # mis à tous
            w.toggle_text_style('italic')
            self.assertEqual((a.extra.get('italic'), b.extra.get('italic')), (None, None))     # retiré
            w.toggle_text_style('underline')
            self.assertTrue(a.extra['underline'])
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
