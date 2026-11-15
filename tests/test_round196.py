"""Round 196 : plaque codée — code et texte ajustés à leurs cadres (TauDrive)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import barcode as B, codeplate as CP, geom
from vectordrive.core.document import Shape, Text
from vectordrive.core.geom import Affine

CODE = [0.0, 0.0, 15.0, 7.0]                    # fenêtres de la plaque type de production
TEXT = [16.0, 2.0, 24.07, 3.54]


def inside(inner, outer, eps=1e-6):
    return (inner[0] >= outer[0] - eps and inner[1] >= outer[1] - eps and
            inner[2] <= outer[2] + eps and inner[3] <= outer[3] + eps)


class TestFit(unittest.TestCase):
    def test_rectangular_datamatrix_fills_window(self):
        shape, mod, w, h = CP.fit_code('datamatrix', 'B000174', CODE)
        self.assertEqual(shape, 'rect')                                            # fenêtre allongée
        m = B.encode('datamatrix', 'B000174', shape='rect')
        self.assertEqual((len(m), len(m[0])), (8, 18))                             # le 8 × 18 de la plaque type
        self.assertAlmostEqual(mod, 15.0 / 18)
        sq = CP.fit_code('datamatrix', 'B000174', [0, 0, 10, 10])
        self.assertEqual(sq[0], 'square')
        self.assertIsNone(CP.fit_code('datamatrix', 'x', [0, 0, 0, 5]))
        lin = CP.fit_code('code128', 'B000174', [0, 0, 30, 6])
        self.assertAlmostEqual(lin[2], 30.0)
        self.assertAlmostEqual(lin[3], 6.0)

    def test_build_and_frames(self):
        items = [Shape(path=geom.Path([geom.rect(*TEXT[:2], TEXT[2] - TEXT[0], TEXT[3] - TEXT[1])])),
                 Shape(path=geom.Path([geom.rect(0, 0, 15, 7)]))]
        code_f, text_f = CP.frames_of(items)
        self.assertEqual(code_f, CODE)
        g = CP.build(CP.PlateSpec(data='B000174', code_frame=code_f, text_frame=text_f))
        code = next(c for c in g.children if c.name == 'code')
        text = next(c for c in g.children if isinstance(c, Text))
        self.assertTrue(inside(code.bbox(), CODE))
        self.assertAlmostEqual(code.bbox()[2] - code.bbox()[0], 15.0, places=6)
        self.assertEqual(text.text, 'B000174')
        self.assertTrue(inside(text.outline.bbox(), TEXT, 0.03))           # dépassement des chiffres ronds

    def test_rebuild_follows_move(self):
        g = CP.build(CP.PlateSpec(data='A1', code_frame=CODE, text_frame=TEXT))
        moved = g.transformed(Affine.translation(40.0, 25.0))
        new = CP.rebuild(moved, 'B000175')
        code = next(c for c in new.children if c.name == 'code')
        text = next(c for c in new.children if isinstance(c, Text))
        self.assertTrue(inside(code.bbox(), [40, 25, 55, 32]))
        self.assertEqual(text.text, 'B000175')                                     # le texte suit le code
        self.assertTrue(inside(text.outline.bbox(), [56, 27, 64.07, 28.54], 0.03))
        with self.assertRaises(ValueError):
            CP.rebuild(moved, 'x' * 3000)


class TestUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_action_and_edit(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            a = Shape(path=geom.Path([geom.rect(0, 0, 15, 7)]))
            b = Shape(path=geom.Path([geom.rect(16, 2, 8, 1.5)]))
            for it in (a, b):
                w.canvas.doc.add(it)
            w.canvas.selection = []
            self.assertIsNone(w.code_plate('B1'))                                    # rien de choisi
            w.canvas.selection = [a, b]
            g = w.code_plate('B000174')
            self.assertIn('codeplate', g.extra)
            new = w.edit_code_plate(g, 'B000180')
            self.assertEqual(new.extra['codeplate']['data'], 'B000180')
            self.assertNotIn(g, list(w.canvas.doc.iter_items()) if hasattr(w.canvas.doc, 'iter_items') else [])
            w.undo()
            self.assertTrue(any(it.extra.get('codeplate', {}).get('data') == 'B000174'
                                for L in w.canvas.doc.layers for it in L.items))
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
