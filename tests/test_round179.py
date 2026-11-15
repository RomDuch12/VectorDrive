"""Round 179 : espacement des textes (TypeEdit, Rapido) — fixe, proportionnel, typographique."""
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
class TestSpacing(unittest.TestCase):
    def test_fixed_cells(self):
        # en chasse fixe, « 1i1 » et « WWW » ont la même largeur de pas : même début des caractères suivants
        a = TX._placed('1iW', FONT, 5.0, 'left', 0.0, 1.2, 1.0, True, True)
        xs = [mat.e if hasattr(mat, 'e') else mat.apply((0, 0))[0] for _g, mat in a]
        steps = [round(b - x, 6) for x, b in zip(xs, xs[1:])]
        self.assertNotEqual(steps[0], steps[1])                                  # glyphes centrés : décalages ≠
        w_fixed = TX.layout('1i1', FONT, 5.0, fixed=True).bbox()
        w_prop = TX.layout('1i1', FONT, 5.0, kerning=False).bbox()
        self.assertGreater(w_fixed[2] - w_fixed[0], w_prop[2] - w_prop[0])        # le i prend une case entière

    def test_kerning_toggle(self):
        typo = TX.layout('AV', FONT, 10.0).bbox()
        prop = TX.layout('AV', FONT, 10.0, kerning=False).bbox()
        self.assertGreaterEqual(prop[2] - prop[0], typo[2] - typo[0] - 1e-9)       # sans crénage : pas plus serré

    def test_command(self):
        app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertEqual(TE_ACTIONS['ID_RAPIDO_LINE_BTNESPFIXE_DLL'], 'line_fixed')
        w = MainWindow()
        try:
            t = w.canvas.doc.add(Text(text='1i1', font=FONT, size=5))
            t.outline = TX.outline_for(t)
            w0 = t.outline.bbox()
            w.canvas.select([t])
            w.set_spacing_mode('fixed')
            self.assertEqual(t.extra['spacing_mode'], 'fixed')
            self.assertGreater(t.outline.bbox()[2] - t.outline.bbox()[0], w0[2] - w0[0])
            w.set_spacing_mode('typo')
            self.assertNotIn('spacing_mode', t.extra)
            self.assertAlmostEqual(t.outline.bbox()[2], w0[2], places=6)
            w.undo()
            self.assertEqual(w.canvas.doc.layers[0].items[-1].extra.get('spacing_mode'), 'fixed')
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
