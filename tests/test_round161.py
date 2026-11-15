"""Round 161 : arc tangent à deux cercles (TypeEdit, ID_COMPO_CERCLE_TANGENT)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Shape
from vectordrive.core.shapes import tangent_arcs


def ends(c):
    pts = c.flatten(0.001)
    return pts[0], pts[-1]


class TestArcs(unittest.TestCase):
    def check_tangent(self, arc, R, circles, enclosing=False):
        pts = arc.flatten(0.001)
        # centre de l'arc : à R de tous ses points
        a, b = pts[0], pts[-1]
        for (c, r) in circles:
            p = min((a, b), key=lambda q: abs(math.dist(q, c) - r))
            self.assertAlmostEqual(math.dist(p, c), r, places=4)              # contact sur le cercle
        return pts

    def test_outside(self):
        arcs = tangent_arcs((0, 0), 5, (20, 0), 5, 6)
        self.assertEqual(len(arcs), 2)
        for arc in arcs:
            pts = self.check_tangent(arc, 6, [((0, 0), 5), ((20, 0), 5)])
            mid = pts[len(pts) // 2]
            self.assertTrue(4 < mid[0] < 16)                                  # le congé est entre les cercles
            for p in pts:
                self.assertGreaterEqual(math.dist(p, (0, 0)), 5 - 1e-6)       # sans entrer dans les cercles
                self.assertGreaterEqual(math.dist(p, (20, 0)), 5 - 1e-6)
        self.assertEqual(tangent_arcs((0, 0), 5, (20, 0), 5, 4), [])           # trop court pour l'écart
        self.assertEqual(tangent_arcs((0, 0), 5, (20, 0), 5, 0), [])

    def test_enclosing(self):
        arcs = tangent_arcs((0, 0), 5, (20, 0), 5, 30, enclosing=True)
        self.assertEqual(len(arcs), 2)
        for arc in arcs:
            self.check_tangent(arc, 30, [((0, 0), 5), ((20, 0), 5)], True)
        self.assertEqual(tangent_arcs((0, 0), 5, (20, 0), 5, 4, enclosing=True), [])

    def test_single_solution(self):
        arcs = tangent_arcs((0, 0), 5, (20, 0), 5, 5)                          # les centres se touchent : 1 arc
        self.assertEqual(len(arcs), 1)


class TestCommand(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_command(self):
        from unittest import mock

        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertEqual(TE_ACTIONS['ID_COMPO_CERCLE_TANGENT'], 'tangent_arc')
        w = MainWindow()
        try:
            doc = w.canvas.doc
            a = doc.add(Shape(path=geom.Path([geom.circle((0, 0), 5)])))
            b = doc.add(Shape(path=geom.Path([geom.circle((20, 0), 5)])))
            w.canvas.select([a])
            with mock.patch('vectordrive.ui.main_window.QMessageBox.information') as info:
                self.assertEqual(w.tangent_arc(6), [])
            self.assertTrue(info.called)
            w.canvas.select([a, b])
            new = w.tangent_arc(6)
            self.assertEqual(len(new), 2)
            self.assertIn(new[0], doc.layers[0].items)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
