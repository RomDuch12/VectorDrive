"""Round 347 : formes paramétrées — oblong, anneau, secteur de couronne ;
éditables, suivent déplacements, rotations, miroirs."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import forms as F, geom
from vectordrive.core.cadtools import mass_properties

app = QApplication.instance() or QApplication([])


def area(p):
    return mass_properties(p)['area']


class TestForms(unittest.TestCase):
    def test_slot(self):
        p = F.Slot(cx=0, cy=0, length=20, width=6).build()
        self.assertEqual(tuple(round(v, 6) for v in p.bbox()), (-10, -3, 10, 3))
        self.assertAlmostEqual(area(p), 14 * 6 + math.pi * 9, delta=0.1)
        p = F.Slot(length=20, width=6, angle=90).build()
        self.assertAlmostEqual(p.bbox()[3] - p.bbox()[1], 20, 6)

    def test_ring_sector(self):
        self.assertAlmostEqual(area(F.Ring(r_out=10, r_in=6).build()), math.pi * (100 - 36), delta=0.1)
        self.assertAlmostEqual(area(F.Sector(r_out=10, r_in=5, start=0, sweep=90).build()),
                               math.pi * (100 - 25) / 4, delta=0.1)
        self.assertAlmostEqual(area(F.Sector(r_out=10, r_in=0, start=30, sweep=60).build()), math.pi * 100 / 6, delta=0.1)
        self.assertEqual(len(F.Sector(r_out=10, r_in=5, sweep=360).build().contours), 2)

    def test_edit_and_transform(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            sh = w.create_form('sector', spec=F.Sector(r_out=10, r_in=5, start=0, sweep=90))
            spec = F.spec_of(sh)
            self.assertEqual(spec.kind, 'sector')
            m = geom.Affine(-1, 0, 0, 1, 0, 0)                            # miroir gauche-droite
            d = F.transformed(F.to_dict(spec), m, sh.path.transformed(m))
            self.assertIsNotNone(d)
            back = F.from_dict(d)
            self.assertAlmostEqual(area(back.build()), area(sh.path), delta=0.1)
            mirrored = sh.path.transformed(m).bbox()
            self.assertEqual(tuple(round(v, 6) for v in back.build().bbox()), tuple(round(v, 6) for v in mirrored))
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
