"""Round 295 : repérage d'accrochage (F11) — les points accrochés survolés
sont retenus, le curseur s'accroche sur leurs verticales, horizontales et
croisements ; lignes de repérage dessinées en pointillé."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Shape
from vectordrive.core.snap import Snap, track

app = QApplication.instance() or QApplication([])


class TestTrack(unittest.TestCase):
    def test_track(self):
        h, lines = track(10.2, 50, 0.5, [(10, 0)])
        self.assertEqual((h.x, h.y, h.kind), (10, 50, 'tracking'))
        self.assertEqual(lines, [(10, 0, 10, 50)])
        h, lines = track(10.1, 19.8, 0.5, [(10, 0), (30, 20)])      # croisement des deux
        self.assertEqual((h.x, h.y), (10, 20))
        self.assertEqual(len(lines), 2)
        self.assertEqual(track(5, 5, 0.5, [(10, 0)]), (None, []))

    def test_snap(self):
        sn = Snap(enabled=True, modes={'node'}, tracking=True)
        items = [Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]))]
        self.assertEqual(sn.query(10.1, 10.1, 0.5, items).kind, 'node')    # survol : acquis
        self.assertEqual(sn.tracked, [(10.0, 10.0)])
        h = sn.query(10.2, 40, 0.5, items)
        self.assertEqual((h.x, h.y, h.kind), (10.0, 40, 'tracking'))
        sn.tracking = False
        self.assertIsNone(sn.query(10.2, 40, 0.5, items))
        sn.acquire(1, 1)
        sn.acquire(2, 2)
        sn.acquire(10, 10)
        self.assertEqual(sn.tracked[0], (10, 10))
        sn.clear_tracking()
        self.assertEqual(sn.tracked, [])

    def test_window(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            c.doc.add(Shape(path=geom.Path([geom.rect(0, 0, 10, 10)])))
            w.A['snap_tracking'].setChecked(True)
            self.assertTrue(c.snap.enabled and c.snap.tracking)
            self.assertIn('Repérage', w.lbl_snap.text())
            c.snap.modes = {'node'}
            c.snap_doc(c.to_screen(10, 10))
            x, y = c.snap_doc(c.to_screen(10.01, 30))
            self.assertAlmostEqual(x, 10.0, 9)
            self.assertEqual(c._snap_hit.kind, 'tracking')
            im = QImage(200, 200, QImage.Format.Format_ARGB32)
            p = QPainter(im)
            c._paint_snap(p)                                                  # lignes et croix sans erreur
            p.end()
            w.set_tool('rect')
            self.assertEqual(c.snap.tracked, [])                              # nouveau mode : oubliés
            w.A['snap_tracking'].setChecked(False)
            self.assertFalse(c.snap.tracking)
        finally:
            w.set_tool('select')
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
