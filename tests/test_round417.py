"""Round 417 : volumes — Z, rotation 3D, symétrie, coupe, section, vue à plat, interférence, séparer."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import solids as S

app = QApplication.instance() or QApplication([])


def rb(b):
    return tuple(round(v, 4) + 0.0 for v in b)


@unittest.skipUnless(S.available(), 'manifold3d absent')
class TestCore(unittest.TestCase):
    def test_flat_views(self):
        b = S.box(0, 0, 0, 10, 20, 30)
        self.assertEqual(rb(S.flatshot(b, 'dessus').bbox()), (0, 0, 10, 20))
        self.assertEqual(rb(S.flatshot(b, 'face').bbox()), (0, 0, 10, 30))
        self.assertEqual(rb(S.flatshot(b, 'cote').bbox()), (0, 0, 20, 30))     # Y à droite
        w = S.wedge(0, 0, 0, 10, 20, 30)
        face = S.flatshot(w, 'face')
        self.assertEqual(len(face.contours[0].segments), 3)                       # le coin vu de face : un triangle

    def test_cuts(self):
        b = S.box(0, 0, 0, 10, 20, 30)
        up, down = S.split(b, (0, 0, 1), 10)
        self.assertEqual(rb(up.bounds()), (0, 0, 10, 10, 20, 30))
        self.assertEqual(rb(down.bounds()), (0, 0, 0, 10, 20, 10))
        self.assertIsNone(S.split(b, (0, 0, 1), 50)[0])
        self.assertEqual(rb(S.section(b, 5).bbox()), (0, 0, 10, 20))
        r = b.transformed(S.rotation('x', 90))
        self.assertEqual(rb(r.bounds()), (0, -30, 0, 10, 0, 20))
        self.assertEqual(rb(b.transformed(S.mirror_z(0)).bounds()), (0, 0, -30, 10, 20, 0))

    def test_components_interference(self):
        u = S.boolean('union', [S.box(0, 0, 0, 10, 10, 10), S.box(50, 0, 0, 5, 5, 5)])
        self.assertEqual(sorted(round(c.volume()) for c in S.components(u)), [125, 1000])
        got = S.interference([S.box(0, 0, 0, 10, 10, 10), S.box(5, 0, 0, 10, 10, 10), S.box(100, 0, 0, 1, 1, 1)])
        self.assertEqual([(i, j, round(c.volume(), 3)) for i, j, c in got], [(0, 1, 500.0)])


@unittest.skipUnless(S.available(), 'manifold3d absent')
class TestCommands(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.c = self.w.canvas
        self.a = S.make_shape(S.box(0, 0, 0, 10, 20, 30))
        self.c.doc.add(self.a)
        self.c.select([self.a])

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def items(self):
        return [it for L in self.c.doc.layers for it in L.items]

    def test_move_rotate_mirror(self):
        new = self.w.solid_move_z(params={'dz': 5.0})
        self.assertEqual(rb(S.of_item(new[0]).bounds())[2], 5)
        self.assertEqual(new[0].id, self.a.id)                                     # même objet, même place
        new = self.w.solid_rotate3d(params={'axis': 'y', 'angle': 90.0, 'together': False})
        b = S.of_item(new[0]).bounds()
        self.assertAlmostEqual(b[5] - b[2], 10, places=4)                          # couché
        self.assertAlmostEqual(new[0].bbox()[2] - new[0].bbox()[0], 30, places=3)  # silhouette à jour
        new = self.w.solid_mirror_z(params={'z': 0.0, 'copy': True})
        self.assertEqual(len(new), 2)
        self.assertEqual(len(self.items()), 2)
        self.w.undo()
        self.assertEqual(len(self.items()), 1)

    def test_slice_section_flatshot(self):
        new = self.w.solid_slice(params={'plane': 'z', 'value': 10.0, 'keep': 'deux'})
        self.assertEqual(len(new), 2)
        self.c.select(new)
        kept = self.w.solid_slice(params={'plane': 'x', 'value': 5.0, 'keep': 'moins'})
        self.assertEqual(len(kept), 2)
        self.assertTrue(all(S.of_item(k).bounds()[3] <= 5 + 1e-6 for k in kept))
        self.c.select(kept)
        sec = self.w.solid_section(params={'z': 2.0})
        self.assertEqual(len(sec), 1)
        self.assertFalse(S.is_solid(sec[0]))
        self.c.select(kept)
        flat = self.w.solid_flatshot(params={'view': 'face', 'gap': 10.0})
        self.assertEqual(len(flat), 2)
        self.assertAlmostEqual(min(f.bbox()[0] for f in flat), 15, places=4)

    def test_interfere_separate(self):
        b = S.make_shape(S.box(5, 0, 0, 10, 10, 10))
        self.c.doc.add(b)
        self.c.select([self.a, b])
        got = self.w.solid_interfere(params={'add': True})
        self.assertEqual(len(got), 1)
        self.assertAlmostEqual(S.of_item(got[0]).volume(), 500, places=3)
        far = S.make_shape(S.box(100, 0, 0, 5, 5, 5))
        self.c.doc.add(far)
        self.c.select([self.a, far])
        uni = self.w.solid_boolean('union')
        self.c.select(uni)
        parts = self.w.solid_separate()
        self.assertEqual(len(parts), 2)


if __name__ == '__main__':
    unittest.main()
