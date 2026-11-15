"""Round 188 : longueur maximale des textes, compression par ligne ou par paragraphe."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import fonts, text as TX
from vectordrive.core.document import Text

FONT = 'Arial'


def widths(t):
    """Largeur d'encre de chaque ligne du contour (du haut vers le bas)."""
    rows = {}
    for g, mat in TX._placed(t.text, t.font, t.size, t.align, t.spacing, t.line_spacing, t.width_ratio, True,
                             False, False, TX.compression(t)):
        b = g.bbox()
        x0, _ = mat.apply((b[0], b[1]))
        x1, _ = mat.apply((b[2], b[3]))
        lo, hi = rows.get(round(mat.f, 6), (x0, x1))
        rows[round(mat.f, 6)] = (min(lo, x0), max(hi, x1))
    return [hi - lo for _y, (lo, hi) in sorted(rows.items(), reverse=True)]


def advance_widths(t):
    got = TX._rows(t.text, t.font, t.size, t.spacing, t.width_ratio, True, False, False, TX.compression(t))
    return [total for _p, total, _w in got[2]]


@unittest.skipUnless(fonts.find_font(FONT), 'police Arial absente')
class TestCompression(unittest.TestCase):
    def test_no_limit_unchanged(self):
        t = Text(text='Paul DURAND\nAtelier', font=FONT, size=6.0)
        self.assertIsNone(TX.compression(t))
        plain = TX.outline_for(t)
        t.extra['max_length'] = {'length': 500.0, 'by': 'line'}                  # plus long que le texte
        self.assertEqual(TX.compression(t), [1.0, 1.0])
        self.assertEqual(TX.outline_for(t).bbox(), plain.bbox())

    def test_line_and_paragraph(self):
        t = Text(text='Jean-Christophe MARTINEAU\nAtelier', font=FONT, size=6.0, spacing=0.3)
        natural = advance_widths(t)
        t.extra['max_length'] = {'length': natural[0] * 0.6, 'by': 'line'}
        f = TX.compression(t)
        self.assertLess(f[0], 1.0)
        self.assertEqual(f[1], 1.0 if natural[1] <= natural[0] * 0.6 else f[1])
        got = advance_widths(t)
        self.assertAlmostEqual(got[0], natural[0] * 0.6, places=6)                 # tient juste, interlettrage gardé
        t.extra['max_length']['by'] = 'paragraph'
        g = TX.compression(t)
        self.assertEqual(g[0], g[1])
        self.assertEqual(g[0], f[0])
        self.assertLess(advance_widths(t)[1], natural[1])                        # la courte aussi resserrée

    def test_fixed_and_floor(self):
        t = Text(text='0123456789', font=FONT, size=5.0)
        t.extra.update(spacing_mode='fixed', max_length={'length': 10.0})
        got = TX._rows(t.text, t.font, t.size, t.spacing, t.width_ratio, False, True, False, TX.compression(t))
        self.assertAlmostEqual(got[2][0][1], 10.0, places=6)
        t.extra['max_length'] = {'length': 0.01}
        self.assertEqual(TX.compression(t), [0.05])                                # jamais écrasé à rien


@unittest.skipUnless(fonts.find_font(FONT), 'police Arial absente')
class TestUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_textbar_and_actions(self):
        from vectordrive.core.geom import Affine
        from vectordrive.io.vnd_write import styled
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertEqual(TE_ACTIONS['ID_RAPIDO_LINE_BTNCOMPBYLINE_DLL'], 'text_compress_line')
        self.assertEqual(TE_ACTIONS['ID_RAPIDO_LINE_BTNCOMPBYPARA_DLL'], 'text_compress_para')
        w = MainWindow()
        try:
            t = Text(text='Marie-Antoinette DUPONT\nService', font=FONT, size=5.0, matrix=Affine(1, 0, 0, 1, 10, 50))
            t.outline = TX.outline_for(t)
            w.canvas.doc.add(t)
            w.canvas.selection = [t]
            w._on_selection()
            wide = t.outline.bbox()[2] - t.outline.bbox()[0]
            self.assertEqual(w.textbar.set_max_length(30.0), 1)
            b = t.outline.bbox()
            self.assertLess(b[2] - b[0], min(wide, 30.5))
            self.assertIn('Compression appliquée', w.statusBar().currentMessage())
            self.assertTrue(styled(t))
            w.A['text_compress_para'].trigger()
            self.assertEqual(t.extra['max_length'], {'length': 30.0, 'by': 'paragraph'})
            w.textbar.refresh()
            self.assertEqual(w.textbar.max_length.value(), 30.0)
            self.assertTrue(w.A['text_compress_para'].isChecked())
            self.assertEqual(w.textbar.set_max_length(30.0), 0)                  # rien de changé
            w.textbar.set_max_length(0.0, 'line')
            self.assertNotIn('max_length', t.extra)
        finally:
            w.modified = False
            w.close()

    def test_variables_follow(self):
        """Un texte variable trop long se resserre à chaque état."""
        t = Text(text='Bob', font=FONT, size=5.0)
        t.extra['max_length'] = {'length': 20.0}
        short = TX.outline_for(t).bbox()
        t.text = 'Bartholomew-Alexander'
        long_ = TX.outline_for(t).bbox()
        self.assertLessEqual(long_[2] - long_[0], 20.0 + 1e-6)
        self.assertLess(short[2] - short[0], 20.0)


if __name__ == '__main__':
    unittest.main()
