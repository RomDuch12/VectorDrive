"""Round 415 : ruban 3D — primitives, extrusion, révolution, booléens, propriétés de masse."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import forms as F
from vectordrive.core import geom
from vectordrive.core import solids as S
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


@unittest.skipUnless(S.available(), 'manifold3d absent')
class TestSolidCommands(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.c = self.w.canvas

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def items(self):
        return [it for L in self.c.doc.layers for it in L.items]

    def test_primitives_on_markers(self):
        m1 = F.make(F.Marker(cx=10, cy=10))
        m2 = F.make(F.Marker(cx=50, cy=10))
        self.c.doc.add(m1)
        self.c.doc.add(m2)
        self.c.select([m1, m2])
        new = self.w.solid_primitive('cylinder', params={'r': 5.0, 'h': 8.0, 'z0': 0.0})
        self.assertEqual(len(new), 2)
        b = S.of_item(new[1]).bounds()
        self.assertAlmostEqual((b[0] + b[3]) / 2, 50, places=3)
        self.assertAlmostEqual(b[5], 8)
        for kind in ('box', 'wedge', 'cone', 'sphere', 'pyramid', 'torus'):
            self.c.select([])
            got = self.w.solid_primitive(kind, params={})
            self.assertEqual(len(got), 1, kind)
            self.assertGreater(S.of_item(got[0]).volume(), 0, kind)
        self.assertIn('solid_box', self.w.A)

    def test_extrude_revolve(self):
        sh = Shape(path=geom.Path([geom.rect(0, 0, 40, 30), geom.rect(10, 10, 10, 10)]))
        self.c.doc.add(sh)
        self.c.select([sh])
        new = self.w.solid_extrude(params={'height': 5.0, 'taper': 0.0, 'z0': 0.0, 'delete': True})
        self.assertEqual(len(new), 1)
        self.assertNotIn(sh, self.items())                       # remplacée
        self.assertAlmostEqual(S.of_item(new[0]).volume(), 1100 * 5, places=3)
        self.w.undo()
        self.assertEqual(len(self.items()), 1)
        self.assertFalse(S.is_solid(self.items()[0]))
        prof = Shape(path=geom.Path([geom.rect(10, 0, 5, 20)]))
        axis = Shape(path=geom.Path([geom.polyline([(0, 0), (0, 30)])]))
        self.c.doc.add(prof)
        self.c.doc.add(axis)
        self.c.select([prof, axis])
        rv = self.w.solid_revolve(params={'angle': 360.0, 'start': 0.0, 'delete': False})
        self.assertEqual(len(rv), 1)
        self.assertAlmostEqual(S.of_item(rv[0]).volume(), math.pi * 125 * 20, delta=30)
        self.assertIn(axis, self.items())                         # l'axe reste

    def test_boolean_and_massprop(self):
        a = S.make_shape(S.box(0, 0, 0, 10, 20, 30))
        b = S.make_shape(S.cylinder(5, 10, -1, 3, 40))
        self.c.doc.add(a)
        self.c.doc.add(b)
        self.c.select([a, b])
        res = self.w.solid_boolean('subtract')
        self.assertEqual(len(res), 1)
        self.assertEqual(len(self.items()), 1)
        self.assertAlmostEqual(S.of_item(res[0]).volume(), 6000 - math.pi * 9 * 30, delta=5)
        self.assertEqual(len(res[0].path.contours), 2)          # silhouette : le trou se voit de dessus
        self.c.select(res)
        d = self.w.solid_massprop(params={'density': 2.7})
        self.assertAlmostEqual(d['mass'], d['volume'] / 1000 * 2.7)
        self.assertIn('Volume', d['text'])
        self.w.undo()
        self.assertEqual(len(self.items()), 2)
        self.c.select([self.items()[0]])
        self.assertEqual(self.w.solid_boolean('union'), [])      # il en faut deux


if __name__ == '__main__':
    unittest.main()
