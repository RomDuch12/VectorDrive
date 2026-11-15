"""Round 57 : enveloppe."""
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import envelope as E
from vectordrive.core import geom
from vectordrive.core.document import Shape, Text
from vectordrive.core.geom import Affine, Line, Path


def max_error(src, res, f):
    """Écart maximal entre l'image exacte de points de `src` et le tracé `res`
    (distance au polygone très fin de `res`)."""
    import numpy as np
    err = 0.0
    for cs, cr in zip(src.contours, res.contours):
        R = np.array(cr.flatten(1e-6))
        A, B = R[:-1], R[1:]
        AB = B - A
        L2 = np.maximum((AB * AB).sum(1), 1e-30)
        for s in cs.segments:
            for k in range(11):
                q = np.array(f(s.point(k / 10)))
                t = np.clip(((q - A) * AB).sum(1) / L2, 0, 1)
                d = np.hypot(*(A + AB * t[:, None] - q).T)
                err = max(err, float(d.min()))
    return err


class TestEnvelope(unittest.TestCase):
    def test_all_kinds_follow_exact_mapping(self):
        sq = Shape(path=Path([geom.rect(0, 0, 40, 10), geom.circle((20, 5), 3)]))
        for kind in E.KINDS:
            spec = E.EnvelopeSpec(kind=kind, amount=40, tolerance=0.005)
            g = E.build([sq], spec)
            src, res = g.children[0].path, g.children[1].path
            self.assertLess(max_error(src, res, E.mapping(spec, src.bbox())), 0.006, kind)
            self.assertTrue(all(c.closed for c in res.contours))

    def test_shapes(self):
        line = Shape(path=Path([geom.Contour([Line((0, 10), (40, 10))], False), geom.rect(0, 0, 40, 10)]))
        g = E.build([line], E.EnvelopeSpec('arc', 50))
        top = g.children[1].path.contours[0]
        self.assertAlmostEqual(max(y for _, y in top.flatten(1e-4)), 15, places=3)
        self.assertAlmostEqual(top.start[1], 10)                  # bords inchangés
        g = E.build([line], E.EnvelopeSpec('trapeze', 50))
        bb = g.children[1].path.contours[0].bbox()
        self.assertAlmostEqual(bb[2] - bb[0], 20, places=6)       # haut réduit de moitié
        self.assertIsInstance(g.children[1].path.contours[0].segments[0], Line)   # reste droit

    def test_vertical_lines_stay_lines(self):
        g = E.build([Shape(path=Path([geom.rect(0, 0, 40, 10)]))], E.EnvelopeSpec('arc', 30))
        kinds = [type(s).__name__ for s in g.children[1].path.contours[0].segments]
        self.assertEqual(kinds.count('Line'), 2)

    def test_text_tools_and_rebuild(self):
        t = Text(text='BFM', font='Arial', size=10, tool=2)
        r = Shape(path=Path([geom.rect(0, -2, 30, 1)]), tool=5)
        g = E.build([t, r], E.EnvelopeSpec('bombe', 30))
        self.assertEqual([c.tool for c in g.children], [2, 5, 2, 5])
        self.assertEqual([c.visible for c in g.children], [False, False, True, True])
        g2 = E.rebuild(g.transformed(Affine.translation(100, 0)), E.EnvelopeSpec('vague', 20))
        self.assertGreater(g2.children[2].path.bbox()[0], 100)
        self.assertEqual(g2.extra['envelope']['kind'], 'vague')

    def test_identity(self):
        sq = Shape(path=Path([geom.circle((0, 0), 5)]))
        g = E.build([sq], E.EnvelopeSpec('arc', 0))
        self.assertLess(max_error(sq.path, g.children[1].path, lambda p: p), 1e-6)


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_new_and_edit(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w._add_items([Shape(path=Path([geom.rect(0, 0, 40, 10)]))])
            w._envelope_dialog = lambda spec: E.EnvelopeSpec('arche', 30)
            w.new_envelope()
            g = w.canvas.selection[0]
            self.assertEqual(g.extra['envelope']['kind'], 'arche')
            w._envelope_dialog = lambda spec: E.EnvelopeSpec('pince', 10)
            w._item_double_clicked(g)
            self.assertEqual(w.canvas.selection[0].extra['envelope']['kind'], 'pince')
            w.undo()
            gs = [it for it in w.canvas.doc.iter_items() if 'envelope' in it.extra]
            self.assertEqual([x.extra['envelope']['kind'] for x in gs], ['arche'])
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
