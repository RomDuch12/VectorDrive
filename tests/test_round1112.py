"""Round 1112 : stratégies de découpe démesurées — Triangles à 10 000 000 pièces par côté (les champs le permettent) :
10¹⁴ diagonales, VectorDrive figé puis à court de mémoire. Au-delà de 100 000 traits : un message, rien de calculé."""
import os
import tempfile
import time
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1112.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from vectordrive.core import cutpatterns as CP  # noqa: E402

app = QApplication.instance() or QApplication([])
BIG = 10_000_000


class TestLimits(unittest.TestCase):
    def fast_refusal(self, fn, *a):
        t = time.time()
        with self.assertRaises(CP.TooMany) as cm:
            fn(*a)
        self.assertLess(time.time() - t, 1.0)
        self.assertGreater(cm.exception.count, CP.MAX_PIECES)
        self.assertIsInstance(cm.exception, ValueError)

    def test_refused_quickly(self):
        self.fast_refusal(CP.triangles, 600.0, 400.0, BIG, BIG)             # avant : 10¹⁴ diagonales
        self.fast_refusal(CP.triangles, 600.0, 400.0, 1000, 1000)
        self.fast_refusal(CP.rectangles, 600.0, 400.0, BIG, 2)               # avant : 10 millions de traits
        self.fast_refusal(CP.pie, 100.0, BIG)
        self.fast_refusal(CP.octagons, 600.0, 10_000_000.0, 1000)
        self.fast_refusal(CP.staggered_circles, 600.0, 400.0, 0.01)
        self.fast_refusal(CP.staggered_circles, 10_000_000.0, 10_000_000.0, 1e-300)   # (infini)
        self.fast_refusal(CP.staggered_circles, 1e7, 2e-4 - 5e-10, 1e-4)    # une rangée, dans la tolérance de la boucle
        self.fast_refusal(CP.staggered_circles, 1e7, float('inf'), 1.0)
        self.fast_refusal(CP.triangles, 600.0, 400.0, 10 ** 155, 10 ** 155)  # entier démesuré
        self.assertEqual(CP.TooMany(10 ** 400).count, float('inf'))

    def test_usual_sizes_unchanged(self):
        _p, g = CP.triangles(600.0, 400.0, 3, 2)
        self.assertEqual(len(g.contours), 2 + 1 + 6)
        _p, g = CP.rectangles(600.0, 400.0, 3, 2)
        self.assertEqual(len(g.contours), 3)
        _p, g = CP.staggered_circles(600.0, 400.0, 50.0)
        self.assertEqual(len(g.contours), 22)
        _p, g = CP.octagons(600.0, 400.0, 4)
        self.assertEqual(len(g.contours), 8)
        _o, g = CP.pie(100.0, 8)
        self.assertEqual(len(g.contours), 8)
        _p, g = CP.staggered_circles(3000.0, 2000.0, 5.0)                    # 69 000 cercles : encore permis
        self.assertGreater(len(g.contours), 60_000)
        self.assertLessEqual(len(g.contours), CP.MAX_PIECES)
        _p, g = CP.rectangles(600.0, 400.0, 50_000, 49_000)                  # juste en deçà
        self.assertEqual(len(g.contours), 49_999 + 48_999)

    def test_estimate_is_an_upper_bound(self):
        seen = []
        real = CP._check
        with mock.patch.object(CP, '_check', lambda n: (seen.append(n), real(n))):
            for L, W, r in ((600.0, 400.0, 50.0), (100.0, 100.0, 1.0), (55.0, 9.0, 4.4), (10.0, 3.0, 2.0), (1.0, 1.0, 3.0),
                            (10.0, 4.0 - 5e-10, 2.0), (8.0 - 5e-10, 4.0, 2.0)):   # (dans la tolérance de la boucle)
                seen.clear()
                _p, g = CP.staggered_circles(L, W, r)
                self.assertLessEqual(len(g.contours), seen[0] + 1e-9, (L, W, r))

    def test_octagons_zero_length(self):
        p, g = CP.octagons(0.0, 400.0, 4)                                    # avant : division par zéro
        self.assertEqual(g.contours, [])


class TestDialog(unittest.TestCase):
    def test_dialog_refuses_with_message(self):
        from vectordrive.ui import dialogs
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            n0 = sum(len(L.items) for L in w.canvas.doc.layers)
            real = dialogs.ParamsDialog.result_params

            def huge(self):
                p = real(self)
                p.nx = p.ny = BIG
                return p
            seen = []
            with mock.patch.object(dialogs.ParamsDialog, 'exec', lambda self: 1), \
                    mock.patch.object(dialogs.ParamsDialog, 'result_params', huge), \
                    mock.patch.object(QMessageBox, 'warning', lambda *a, **k: seen.append(a[2])):
                t = time.time()
                self.assertEqual(w.cut_pattern_dialog('triangles'), [])
                self.assertLess(time.time() - t, 5.0)
            self.assertEqual(len(seen), 1)
            self.assertIn('100 000', seen[0])
            self.assertIn('100 000 020 000 000', seen[0])          # 10¹⁴ + 2·10⁷ traits
            self.assertEqual(sum(len(L.items) for L in w.canvas.doc.layers), n0)
            self.assertEqual(int(w.settings.value('decoupe/triangles/nx')), BIG)   # gardées, à corriger
            with mock.patch.object(dialogs.ParamsDialog, 'exec', lambda self: 1):
                w.settings.setValue('decoupe/triangles/nx', 3)
                w.settings.setValue('decoupe/triangles/ny', 2)
                out = w.cut_pattern_dialog('triangles')                      # valeurs normales : posé
            self.assertEqual(len(out), 1)
        finally:
            for k in ('nx', 'ny', 'length', 'width', 'rising'):
                w.settings.remove(f'decoupe/triangles/{k}')
            w.modified = False
            w.close()
            w.deleteLater()


class TestMarks(unittest.TestCase):
    def test_marks_count(self):
        from vectordrive.core import cadtools as C, geom
        cs = [geom.rect(0, 0, 100, 50), geom.Contour([geom.Line((0, 0), (30, 0))], False)]
        self.assertEqual(C.marks_count(cs, 'divide', 5), 10.0)
        self.assertEqual(C.marks_count(cs, 'divide', 0), 4.0)
        self.assertAlmostEqual(C.marks_count(cs, 'measure', 10.0), 33.0)
        self.assertEqual(C.marks_count(cs, 'measure', 0.0), 0.0)
        for c in cs:                                                          # une borne haute du vrai nombre
            self.assertLessEqual(len(C.measure(c, 10.0)), C.marks_count([c], 'measure', 10.0))
            self.assertLessEqual(len(C.divide(c, 7)), C.marks_count([c], 'divide', 7))

    def test_divide_refused_quickly(self):
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            s = Shape(path=geom.Path([geom.rect(0, 0, 100, 50)]))
            c.doc.add(s)
            c.selection = [s]
            n0 = len(c.doc.layers[0].items)
            for kind, params in (('divide', {'count': BIG}), ('measure', {'step': 1e-6, 'from_end': False})):
                t = time.time()
                self.assertIsNone(w.cad_points(kind, params))                 # avant : 35 min, puis la mémoire épuisée
                self.assertLess(time.time() - t, 5.0)
                self.assertIn('100 000 au plus', w.statusBar().currentMessage())
                self.assertEqual(len(c.doc.layers[0].items), n0)
            g = w.cad_points('divide', {'count': 8})
            self.assertEqual(len(g.children), 8)
        finally:
            w.modified = False
            w.close()
            w.deleteLater()


if __name__ == '__main__':
    unittest.main()
