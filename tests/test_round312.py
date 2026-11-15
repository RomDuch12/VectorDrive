"""Round 312 : trait à largeur variable (profil de largeur) — linéaire,
effilé aux deux bouts, ondulé ; traits ouverts et fermés."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom, varstroke as VS
from vectordrive.core.cadtools import mass_properties
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])
LINE = geom.Path([geom.polyline([(0, 0), (100, 0)])])


def area(p):
    return mass_properties(p)['area']


class TestVarStroke(unittest.TestCase):
    def test_linear(self):
        p = VS.var_stroke(LINE, VS.VarStrokeSpec(profile='lineaire', w_start=0, w_end=4))
        self.assertAlmostEqual(area(p), 200, 3)                         # triangle 100 × 4 / 2
        self.assertAlmostEqual(p.bbox()[3], 2, 6)

    def test_tapered(self):
        p = VS.var_stroke(LINE, VS.VarStrokeSpec(profile='effile', w_end=4))
        self.assertAlmostEqual(area(p), 400 * 2 / 3.14159265, 0)       # ∫ 4 sin(πt) = 8/π × 100
        self.assertAlmostEqual(VS.width_at(VS.VarStrokeSpec(profile='effile', w_end=4), 0.5), 4)

    def test_wavy_and_closed(self):
        spec = VS.VarStrokeSpec(profile='ondule', w_start=1, w_end=3, waves=5)
        self.assertAlmostEqual(VS.width_at(spec, 0.0), 1)
        self.assertAlmostEqual(VS.width_at(spec, 0.1), 3)
        ring = VS.var_stroke(geom.Path([geom.circle((0, 0), 10)]), VS.VarStrokeSpec(profile='lineaire', w_start=2, w_end=2))
        self.assertEqual(len(ring.contours), 2)                         # couronne
        self.assertAlmostEqual(area(ring), 3.14159 * (11 ** 2 - 9 ** 2), 0)

    def test_command(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            s = Shape(path=LINE)
            c.doc.add(s)
            c.select([s])
            new = w.var_stroke({'profile': 'lineaire', 'w_start': 2, 'w_end': 2, 'waves': 4})
            self.assertEqual(len(new), 1)
            self.assertTrue(new[0].path.contours[0].closed)
            self.assertAlmostEqual(area(new[0].path), 200, 3)
            w.undo()
            self.assertEqual(c.doc.layers[0].items[0].id, s.id)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
