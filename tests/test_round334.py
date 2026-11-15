"""Round 334 : nettoyer les superpositions (comme OVERKILL en DAO) — bords
communs fusionnés, traits joints, tracés refermés, par outil."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom, overkill as OK
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


class TestOverkill(unittest.TestCase):
    def test_adjacent_rects(self):
        a = geom.Path([geom.rect(0, 0, 10, 10)])
        b = geom.Path([geom.rect(10, 0, 10, 10)])                    # bord commun x = 10
        new, removed = OK.overkill([a, b])
        self.assertAlmostEqual(removed, 10.0, 6)
        self.assertAlmostEqual(sum(c.length() for c in new.contours), 70.0, 6)

    def test_overlap_and_join(self):
        p = [geom.Path([geom.polyline([(0, 0), (10, 0)])]), geom.Path([geom.polyline([(5, 0), (15, 0)])])]
        new, removed = OK.overkill(p)
        self.assertEqual(len(new.contours), 1)
        self.assertAlmostEqual(new.contours[0].length(), 15.0, 6)
        self.assertAlmostEqual(removed, 5.0, 6)
        ring = OK.overkill([geom.Path([geom.polyline([(0, 0), (10, 0), (10, 10)])]),
                            geom.Path([geom.polyline([(10, 10), (0, 10), (0, 0)])])])[0]
        self.assertEqual(len(ring.contours), 1)
        self.assertTrue(ring.contours[0].closed)
        self.assertFalse(OK.straight_only(geom.Path([geom.circle((0, 0), 2)])))

    def test_command(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            a = Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]), tool=1)
            b = Shape(path=geom.Path([geom.rect(10, 0, 10, 10)]), tool=1)
            c = Shape(path=geom.Path([geom.rect(10, 0, 10, 10)]), tool=2)            # autre outil : gardé à part
            for s in (a, b, c):
                w.canvas.doc.add(s)
            w.canvas.select([a, b, c])
            self.assertAlmostEqual(w.overkill(), 10.0, 6)
            self.assertEqual(sorted(s.tool for s in w.canvas.doc.layers[0].items), [1, 2])
            w.undo()
            self.assertEqual(len(w.canvas.doc.layers[0].items), 3)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
