"""Round 365 : primitives en relief (TypeEdit : Sphère, Ellipsoïde, Cône,
Cylindre, Tore, Cube) — hauteurs, emprise, combinaison."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from vectordrive.core import galbe as GB, primitives3d as P3
from vectordrive.core.relief_ops import z_at

app = QApplication.instance() or QApplication([])


def H(kind, x, y, **kw):
    sp = P3.PrimitiveSpec(kind=kind, **kw)
    h, ok = P3.heights(sp, np.array([[float(x)]]), np.array([[float(y)]]), 0.0, 0.0)
    return round(float(h[0, 0]), 6), bool(ok[0, 0])


class TestPrimitives(unittest.TestCase):
    def test_heights(self):
        self.assertEqual(H('sphere', 0, 0, size_x=20), (10.0, True))
        self.assertAlmostEqual(H('sphere', 6, 0, size_x=20)[0], 8.0)              # √(100 − 36)
        self.assertFalse(H('sphere', 11, 0, size_x=20)[1])
        self.assertEqual(H('ellipsoide', 0, 0, size_x=20, size_y=10, height=3)[0], 3.0)
        self.assertAlmostEqual(H('cone', 5, 0, size_x=20)[0], 5.0)                # pente 1
        self.assertEqual(H('cone', 1, 0, size_x=20, radius2=2)[0], 10.0)         # dessus plat de rayon 2
        self.assertEqual(H('cylindre', 9, 0, size_x=20, size_y=10)[0], 5.0)       # couché selon X
        self.assertAlmostEqual(H('cylindre', 0, 3, size_x=20, size_y=10)[0], 4.0)
        self.assertEqual(H('tore', 0, 0, size_x=20)[1], False)                    # trou du tore
        self.assertEqual(H('tore', 7.5, 0, size_x=20)[0], 2.5)                    # tube de rayon 2,5
        self.assertEqual(H('pave', 9, 4, size_x=20, size_y=10, height=2)[0], 2.0)

    def test_relief(self):
        sp = P3.PrimitiveSpec(kind='sphere', size_x=10, resolution=0.1, margin=0)
        img = P3.primitive_relief(sp, [(20, 20), (40, 20)])
        b = img.bbox()
        self.assertEqual(tuple(round(v, 3) for v in b[:2]), (15.0, 15.0))
        self.assertAlmostEqual(z_at(img, 20, 20), 5.0, 1)
        self.assertAlmostEqual(z_at(img, 40, 20), 5.0, 1)
        self.assertAlmostEqual(img.extra['galbe']['relief_depth'], 5.0, 1)
        sp2 = P3.PrimitiveSpec(kind='pave', size_x=4, size_y=4, height=1, margin=0, mode='ajouter')
        both = P3.primitive_relief(sp2, [(20, 20)], onto=img)
        self.assertAlmostEqual(z_at(both, 20, 20), 6.0, 1)                       # ajouté au relief
        self.assertIsNotNone(GB.decode(both))

    def test_window(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            img = w.relief_primitive(P3.PrimitiveSpec(kind='cone', size_x=10, size_y=10, height=2, margin=0))
            pl = w.canvas.doc.plate
            self.assertAlmostEqual(z_at(img, pl.width / 2, pl.height / 2), 2.0, 1)
            self.assertIn(img, w.canvas.doc.layers[0].items)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
