"""Round 414 : les volumes dans le dessin — placement, enregistrement, annulation, 3D, STL."""
import math
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import geom
from vectordrive.core import solids as S
from vectordrive.core.document import Document


@unittest.skipUnless(S.available(), 'manifold3d absent')
class TestSolidItems(unittest.TestCase):
    def test_shape_and_transforms(self):
        sh = S.make_shape(S.cylinder(10, 10, 0, 5, 20))
        self.assertTrue(S.is_solid(sh))
        b = sh.bbox()
        self.assertAlmostEqual(b[0], 5, places=3)
        self.assertAlmostEqual(b[2], 15, places=3)
        moved = sh.transformed(geom.Affine.translation(100, 0))
        self.assertEqual(tuple(round(v, 3) for v in S.of_item(moved).bounds()), (105, 5, 0, 115, 15, 20))
        self.assertEqual(S.of_item(sh).bounds()[0], S.of_item(sh).bounds()[0])           # l'original reste
        self.assertAlmostEqual(S.of_item(sh).bounds()[0], 5, places=3)
        big = sh.transformed(geom.Affine.scaling(2, center=(10, 10)))                    # similitude : Z aussi
        self.assertAlmostEqual(S.of_item(big).bounds()[5], 40, places=3)
        wide = sh.transformed(geom.Affine.scaling(2, 1, center=(10, 10)))               # étirement : Z garde
        self.assertAlmostEqual(S.of_item(wide).bounds()[5], 20, places=3)
        mir = sh.transformed(geom.Affine(-1, 0, 0, 1, 0, 0))
        v = S.of_item(mir)
        self.assertAlmostEqual(v.volume(), S.of_item(sh).volume(), places=3)              # faces vers l'extérieur
        v.manifold()
        clone = sh.clone()
        self.assertTrue(S.is_solid(clone))

    def test_save_reload(self):
        from vectordrive.io import registry
        d = Document()
        sh = S.make_shape(S.box(0, 0, 0, 10, 20, 30))
        d.add(sh.transformed(geom.Affine.translation(5, 5)))
        p = pathlib.Path(tempfile.mkdtemp()) / 'v.vdz'
        registry.save_document(d, str(p))
        d2 = registry.open_document(str(p))
        vols = S.doc_solids(d2)
        self.assertEqual(len(vols), 1)
        self.assertEqual(tuple(round(x, 6) for x in vols[0][1].bounds()), (5, 5, 0, 15, 25, 30))

    def test_doc_and_model(self):
        d = Document()
        d.add(S.make_shape(S.box(0, 0, 0, 10, 10, 10)))
        d.add(S.make_shape(S.sphere(30, 0, 5, 5)))
        vols = S.doc_solids(d)
        self.assertEqual(len(vols), 2)
        m = S.to_model([s for _i, s in vols])
        self.assertEqual(m.parts, 2)
        self.assertEqual(len(m.triangles), len(m.colors))
        d.layers[0].visible = False
        self.assertEqual(S.doc_solids(d), [])

    def test_window(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            sh = S.make_shape(S.box(0, 0, 0, 10, 10, 10))
            c.doc.add(sh)
            c.select([sh])
            w.push_undo()
            c.transform_selection(geom.Affine.translation(50, 0))
            moved = c.doc.layers[0].items[0]
            self.assertAlmostEqual(S.of_item(moved).bounds()[0], 50)
            w.undo()
            self.assertAlmostEqual(S.of_item(c.doc.layers[0].items[0]).bounds()[0], 0)
            w.set_view_mode('3d')
            self.assertTrue(w.panel3d.refresh())
            self.assertIsNotNone(w.panel3d.model)
            self.assertEqual(w.panel3d.model.parts, 1)
            w.set_view_mode('2d')
            c.select(c.doc.layers[0].items)
            out = pathlib.Path(tempfile.mkdtemp()) / 'v.stl'
            n = w.export_stl(str(out), params={'base': 2.0, 'height': 3.0, 'max_cells': 1000})
            self.assertEqual(n, 12)                                              # le cube seul, pas extrudé
        finally:
            w.modified = False
            w.close()
        del app


if __name__ == '__main__':
    unittest.main()
