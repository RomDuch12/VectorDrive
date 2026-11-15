"""Round 158 : marqueterie de TypeEdit (ID_MARQUETTERIE)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.cam import inlay, model
from vectordrive.core import geom, marquetry as MQ, pathops
from vectordrive.core.document import Group, Shape


def square(x=0.0, s=10.0):
    return Shape(path=geom.Path([geom.rect(x, 0, s, s)]), name='carré')


def width(sh):
    b = sh.bbox()
    return b[2] - b[0]


class TestForms(unittest.TestCase):
    def test_offsets_and_tools(self):
        f, m = MQ.forms([square()], MQ.MarquetrySpec(female_offset=0.2, male_offset=-0.1, female_tool=3, male_tool=4))
        self.assertAlmostEqual(width(f[0]), 10.4, places=3)
        self.assertAlmostEqual(width(m[0]), 9.8, places=3)
        self.assertEqual((f[0].tool, m[0].tool), (3, 4))
        self.assertEqual((f[0].name, m[0].name), ('carré — femelle', 'carré — mâle'))

    def test_rounded_corners_both_ways(self):
        # un L : un angle rentrant et cinq saillants ; tous arrondis
        L_shape = Shape(path=geom.Path([geom.polyline([(0, 0), (20, 0), (20, 5), (5, 5), (5, 20), (0, 20)],
                                                      closed=True)]))
        f, m = MQ.forms([L_shape], MQ.MarquetrySpec(corner_radius=1.0, female_offset=0, male_offset=0))
        a0 = pathops.area(L_shape.path)
        a1 = pathops.area(f[0].path)
        # saillants : 5 × (1 − π/4) retirés ; rentrant : (1 − π/4) ajouté
        self.assertAlmostEqual(a0 - a1, 4 * (1 - 3.14159265 / 4), delta=0.05)
        self.assertNotIn((20.0, 0.0), [tuple(round(v, 6) for v in pt) for pt in f[0].path.contours[0].flatten(0.01)])

    def test_mirror_text_group_and_open(self):
        tri = Shape(path=geom.Path([geom.polyline([(0, 0), (10, 0), (0, 10)], closed=True)]))
        f, m = MQ.forms([tri], MQ.MarquetrySpec(female_offset=0, male_offset=0, female_mirror=True))
        pts = f[0].path.contours[0].flatten(0.01)
        self.assertTrue(any(abs(x) < 1e-6 and abs(y - 10) < 1e-6 for x, y in pts) and
                        any(abs(x - 10) < 1e-6 and abs(y - 10) < 1e-6 for x, y in pts))   # retourné en Y
        g = Group(children=[square(), square(20)])
        line = Shape(path=geom.Path([geom.polyline([(0, 0), (5, 5)])]))
        f, m = MQ.forms([g, line], MQ.MarquetrySpec())
        self.assertEqual((len(f), len(m)), (1, 1))                      # le trait ouvert est ignoré
        self.assertEqual(len(f[0].path.contours), 2)

    def test_presets(self):
        s = model.CamSetup()
        cone = model.CamTool(name='V30', kind='conique', diameter=3, angle=30)
        s.tools = [model.CamTool(name='F2', diameter=2), cone]
        f, m = MQ.forms([square()], MQ.MarquetrySpec())
        self.assertEqual(inlay.operations(MQ.MarquetrySpec(), f, m, s), [])
        ops = inlay.operations(MQ.MarquetrySpec(preset='conique_borgne'), f, m, s, thickness=3.0)
        self.assertEqual([(o.kind, o.side, o.tool_id) for o in ops],
                         [('poche', 'exterieur', cone.id), ('contour', 'exterieur', cone.id)])
        self.assertEqual(ops[0].items, [f[0].id])
        self.assertEqual(ops[1].depth, 3.0)
        ops = inlay.operations(MQ.MarquetrySpec(preset='cylindrique_debouchant'), f, m, s, thickness=3.0)
        self.assertEqual([(o.kind, o.side, o.tool_id, o.depth) for o in ops],
                         [('contour', 'interieur', s.tools[0].id, 3.0), ('contour', 'exterieur', s.tools[0].id, 3.0)])


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_apply_and_undo(self):
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertEqual(TE_ACTIONS['ID_MARQUETTERIE'], 'marquetry')
        w = MainWindow()
        try:
            doc = w.canvas.doc
            sq = doc.add(square())
            w.canvas.select([sq])
            n_layers = len(doc.layers)
            f, m, ops = w.marquetry_dialog(exec_dialog=False,
                                          spec=MQ.MarquetrySpec(preset='conique_debouchant', nest=True))
            self.assertEqual(len(doc.layers), n_layers + 2)
            self.assertEqual([L.name for L in doc.layers[-2:]], [MQ.FEMALE_LAYER, MQ.MALE_LAYER])
            self.assertEqual(len(model.setup_of(doc).operations), 2)
            ids = {it.id for it in doc.layers[-1].items}
            self.assertEqual(set(model.setup_of(doc).operations[1].items), ids)      # imbriquées : mêmes objets
            self.assertIn(sq, doc.layers[0].items)                                   # plan d'origine intact
            w.undo()
            self.assertEqual(len(doc.layers), n_layers)
            self.assertEqual(model.setup_of(doc).operations, [])
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
