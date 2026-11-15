"""Round 359 : accrochage prolongement (EXTENSION) — le bout d'un trait droit
survolé est retenu, puis le curseur s'accroche sur son prolongement."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Shape
from vectordrive.core.snap import Snap, extension

app = QApplication.instance() or QApplication([])


class TestExtension(unittest.TestCase):
    def test_core(self):
        h, line = extension(25.0, 0.3, 0.5, [(20, 0, 1, 0)])
        self.assertEqual((h.kind, h.x, h.y), ('extension', 25.0, 0.0))
        self.assertEqual(line, (20, 0, 25.0, 0.0))
        self.assertEqual(extension(15.0, 0.3, 0.5, [(20, 0, 1, 0)])[0], None)       # pas en arrière

    def test_snap(self):
        line = Shape(path=geom.Path([geom.polyline([(0, 0), (20, 0)])]))
        sn = Snap(enabled=True, modes={'node', 'extension'})
        self.assertEqual(sn.query(20.1, 0.1, 0.5, [line]).kind, 'node')               # survol : retenu
        self.assertEqual(sn.ext_ends[0], (20, 0, 1.0, 0.0))
        h = sn.query(30.0, 0.2, 0.5, [line])
        self.assertEqual((h.kind, round(h.y, 9)), ('extension', 0.0))
        self.assertEqual(sn.track_lines, [(20, 0, 30.0, 0.0)])
        h = sn.query(-8.0, -0.2, 0.5, [line])                                          # l'autre bout n'est pas retenu
        self.assertIsNone(h)
        sn.clear_tracking()
        self.assertEqual(sn.ext_ends, [])


if __name__ == '__main__':
    unittest.main()
