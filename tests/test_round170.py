"""Round 170 : textes sur arcs multiples (TypeEdit, ID_COMPO_TEXTENARCSMULTIPLES)."""
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


def radii(path, center=(0, 0)):
    return [math.dist(p, center) for c in path.contours for p in c.flatten(0.01)]


@unittest.skipIf(FONT is None, 'aucune police de référence')
class TestWarp(unittest.TestCase):
    def test_modes_stay_in_ring(self):
        for mode in TX.ARC_MODES:
            p = TX.arc_warp('ABC', FONT, 5.0, (0, 0), 30.0, 90.0, True, mode)
            r = radii(p)
            self.assertTrue(p.contours, mode)
            self.assertGreater(min(r), 29.0, mode)                               # au-dessus de la ligne de base
            self.assertLess(max(r), 36.5, mode)                                  # sous la hauteur des lettres
            ys = [y for c in p.contours for _x, y in c.flatten(0.01)]
            self.assertGreater(min(ys), 0, mode)                                 # en haut (angle 90°)

    def test_not_mirrored(self):
        def signs(p):
            out = []
            for c in p.contours:
                pts = c.flatten(0.01)
                out.append(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1])) > 0)
            return out
        for cw, ang in ((True, 90.0), (False, 270.0)):
            ref = signs(TX.arc_warp('ABC', FONT, 5.0, (0, 0), 30.0, ang, cw, 'radial'))
            self.assertEqual(signs(TX.arc_warp('ABC', FONT, 5.0, (0, 0), 30.0, ang, cw, 'simple')), ref)
            self.assertEqual(signs(TX.arc_warp('ABC', FONT, 5.0, (0, 0), 30.0, ang, cw, 'incline')), ref)
            straight = signs(TX.layout('ABC', FONT, 5.0, align='center'))
            self.assertEqual(ref, straight)                                      # même sens que le texte droit

    def test_counter_clockwise_inside(self):
        p = TX.arc_warp('ABC', FONT, 5.0, (0, 0), 30.0, 270.0, False, 'incline')
        r = radii(p)
        self.assertLess(max(r), 31.0)                                            # lettres vers le centre
        self.assertGreater(min(r), 23.5)
        self.assertLess(max(y for c in p.contours for _x, y in c.flatten(0.01)), 0)

    def test_incline_sides_point_to_center(self):
        # un I en inclinée : ses deux côtés sont des rayons ; en radiale, ils restent parallèles
        inc = TX.arc_warp('I', FONT, 10.0, (0, 0), 20.0, 90.0, True, 'incline')
        rad = TX.arc_warp('I', FONT, 10.0, (0, 0), 20.0, 90.0, True, 'radial')
        def spread(p):                                                           # écart des x en haut et en bas
            pts = [pt for c in p.contours for pt in c.flatten(0.01)]
            lo = [x for x, y in pts if y < 21]
            hi = [x for x, y in pts if y > 28]
            return (max(lo) - min(lo)), (max(hi) - min(hi))
        lo, hi = spread(inc)
        self.assertGreater(hi, lo * 1.2)                                         # s'évase vers l'extérieur
        lo, hi = spread(rad)
        self.assertAlmostEqual(hi, lo, delta=0.2 * lo)

    def test_text_and_command(self):
        app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertEqual(TE_ACTIONS['ID_COMPO_TEXTENARCSMULTIPLES'], 'text_arcs')
        w = MainWindow()
        try:
            a = w.canvas.doc.add(Text(text='Première', font=FONT, size=4))
            b = w.canvas.doc.add(Text(text='Seconde', font=FONT, size=4))
            w.canvas.select([a, b])
            dlg = w.text_arcs_dialog(exec_dialog=False)
            dlg.cx.setValue(125)
            dlg.cy.setValue(100)
            dlg.same_type.setChecked(True)
            dlg.widgets[0][3].setCurrentIndex(dlg.widgets[0][3].findData('radial'))
            rows = dlg.rows()
            self.assertEqual([r[3] for r in rows], ['radial', 'radial'])
            self.assertGreater(rows[0][0], rows[1][0])                           # 1re ligne à l'extérieur
            w.text_arcs([a, b], dlg.center(), rows)
            self.assertEqual(a.extra['arc_warp']['center'], [125, 100])
            r = radii(a.outline, (125, 100))
            self.assertAlmostEqual(min(r), rows[0][0], delta=1.0)
            self.assertEqual(TX.outline_for(a).bbox(), a.outline.bbox())         # recalculé à l'identique
            w.undo()
            self.assertNotIn('arc_warp', w.canvas.doc.layers[0].items[0].extra)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
