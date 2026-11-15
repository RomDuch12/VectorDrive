"""Round 360 : accrochage parallèle — direction du dernier trait droit
survolé, parallèle menée du dernier point cliqué."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Shape
from vectordrive.core.snap import Snap

app = QApplication.instance() or QApplication([])


class TestParallel(unittest.TestCase):
    def test_parallel(self):
        line = Shape(path=geom.Path([geom.polyline([(0, 0), (10, 10)])]))       # à 45°
        sn = Snap(enabled=True, modes={'parallel'}, anchor=(20, 0))
        self.assertIsNone(sn.query(5.1, 5.0, 0.5, [line]))                     # survol : direction retenue
        self.assertAlmostEqual(sn.par_dir[0], math.sqrt(0.5))
        h = sn.query(25.2, 5.0, 0.5, [line])
        self.assertEqual(h.kind, 'parallel')
        self.assertAlmostEqual(h.x - 20, h.y, 9)                               # sur la parallèle à 45° par (20, 0)
        self.assertEqual(len(sn.track_lines), 1)
        sn.clear_tracking()
        self.assertIsNone(sn.par_dir)


if __name__ == '__main__':
    unittest.main()
