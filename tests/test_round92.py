"""Round 92 : FAO — outils, opérations, parcours 2D / 2,5D (gravure,
détourage, poche, perçage), G-code, parcours TypeEdit (.000…), panneau."""
import math
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from shapely.geometry import LineString, Point, Polygon

from vectordrive.cam import edit, model, post, strategies, typeedit
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def doc_with(*shapes):
    d = Document()
    for path, tool in shapes:
        d.layers[0].items.append(Shape(path=path, tool=tool))
    return d


def setup(*ops, tools=None):
    s = model.CamSetup()
    s.tools = tools or [model.CamTool(name='F2', diameter=2.0, step_down=0.5, number=1)]
    for o in ops:
        o.tool_id = o.tool_id or s.tools[0].id
        s.operations.append(o)
    return s


def cut_points(tp):
    return [(m.x, m.y, m.z) for m in tp.moves if m.kind != 'rapid']


def signed_area(pts):
    return 0.5 * sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:]))


class TestModel(unittest.TestCase):
    def test_roundtrip_and_storage(self):
        s = setup(model.Operation(name='a', kind='poche', depth=1.5, sources=[2]))
        back = model.CamSetup.from_dict(s.to_dict())
        self.assertEqual(back.to_dict(), s.to_dict())
        d = Document()
        model.store(d, s)
        from vectordrive.io import native
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'a.vdz')
            native.write(d, f)
            again = model.setup_of(native.read(f))
        self.assertEqual(again.operations[0].depth, 1.5)
        self.assertEqual(again.tools[0].diameter, 2.0)
        self.assertEqual(model.CamTool.from_dict({'diameter': 3, 'inconnu': 1}).diameter, 3)

    def test_levels_and_radius(self):
        self.assertEqual(strategies.levels(1.0, 0.3), [-0.25, -0.5, -0.75, -1.0])
        self.assertEqual(strategies.levels(0.2, 0.5), [-0.2])
        v = model.CamTool(kind='conique', diameter=6, tip=0.2, angle=90)
        self.assertAlmostEqual(v.radius_at(0.5), 0.6)
        self.assertAlmostEqual(v.radius_at(10), 3.0)


class TestStrategies(unittest.TestCase):
    def test_engraving_levels_and_safety(self):
        d = doc_with((geom.Path([geom.rect(0, 0, 20, 10)]), 0))
        op = model.Operation(kind='gravure', depth=1.0)
        tp = strategies.compute(d, setup(op), op)
        self.assertEqual(tp.moves[0].kind, 'rapid')
        self.assertEqual(tp.moves[0].z, op.safe_z)
        zs = sorted({round(z, 6) for _x, _y, z in cut_points(tp)})
        self.assertEqual(zs, [-1.0, -0.5])
        self.assertEqual(tp.moves[-1].z, op.safe_z)                      # remonté à la fin
        feed, _rapid = tp.lengths()
        self.assertAlmostEqual(feed, 2 * 60 + 1.5, places=6)              # deux tours + plongées depuis 0,5

    def test_outside_contour_climb_and_tabs(self):
        d = doc_with((geom.Path([geom.rect(0, 0, 20, 10)]), 0))
        op = model.Operation(kind='contour', side='exterieur', depth=2.0, tabs=2, tab_width=2, tab_height=0.5)
        tp = strategies.compute(d, setup(op), op)
        rect = Polygon([(0, 0), (20, 0), (20, 10), (0, 10)])
        deep = [(x, y) for x, y, z in cut_points(tp) if z <= -1.999]
        self.assertTrue(deep)
        for x, y in deep:
            self.assertAlmostEqual(rect.exterior.distance(Point(x, y)), 1.0, delta=0.02)
        ring = [(x, y) for x, y, z in cut_points(tp) if abs(z + 0.5) < 1e-9 or abs(z + 1.0) < 1e-9]
        self.assertLess(signed_area(ring + ring[:1]), 0)                   # avalant : sens horaire
        self.assertIn(-1.5, {round(z, 6) for _x, _y, z in cut_points(tp)})  # pontets à −(2 − 0,5)

    def test_inside_contour(self):
        d = doc_with((geom.Path([geom.rect(0, 0, 20, 10)]), 0))
        op = model.Operation(kind='contour', side='interieur', depth=0.5)
        tp = strategies.compute(d, setup(op), op)
        inner = Polygon([(1, 1), (19, 1), (19, 9), (1, 9)])
        for x, y, _z in cut_points(tp):
            self.assertLess(inner.exterior.distance(Point(x, y)), 0.02)

    def test_pocket_clears_area_and_avoids_island(self):
        d = doc_with((geom.Path([geom.rect(0, 0, 30, 16), geom.circle((10, 8), 3)]), 0))
        op = model.Operation(kind='poche', depth=0.5)
        tp = strategies.compute(d, setup(op), op)
        reg = strategies.region([d.layers[0].items[0].path], 0.01)
        allowed = reg.buffer(-0.995)
        segs = []
        prev = None
        for m in tp.moves:
            if prev is not None and m.kind != 'rapid' and m.z < 0:
                self.assertTrue(allowed.contains(Point(m.x, m.y)))
                if (prev.x, prev.y) != (m.x, m.y):
                    segs.append(LineString([(prev.x, prev.y), (m.x, m.y)]))
            prev = m
        # matière enlevée partout où l'outil peut aller (rayon 1 mm)
        from shapely.ops import unary_union
        swept = unary_union(segs).buffer(1.0)
        reachable = reg.buffer(-1.0).buffer(1.0)
        self.assertLess(reachable.difference(swept).area, 0.02 * reachable.area)

    def test_drilling_with_pecks(self):
        d = doc_with((geom.Path([geom.circle((5, 5), 1.0)]), 1), (geom.Path([geom.circle((15, 5), 1.0)]), 1),
                     (geom.Path([geom.rect(0, 0, 20, 10)]), 0))
        drill = model.CamTool(name='Foret 2', kind='foret', diameter=2.0, number=2, cut_length=10)
        op = model.Operation(kind='percage', depth=3.0, peck=1.0, sources=[1])
        tp = strategies.compute(d, setup(op, tools=[drill]), op)
        plunges = [round(m.z, 6) for m in tp.moves if m.kind == 'plunge']
        self.assertEqual(plunges, [-1, -2, -3, -1, -2, -3])
        self.assertEqual({(m.x, m.y) for m in tp.moves if m.kind == 'plunge'}, {(5, 5), (15, 5)})

    def test_warnings(self):
        d = doc_with((geom.Path([geom.rect(0, 0, 4, 4)]), 0))
        op = model.Operation(kind='contour', side='interieur', depth=5)
        tp = strategies.compute(d, setup(op, tools=[model.CamTool(diameter=6, cut_length=3)]), op)
        self.assertTrue(any('trop gros' in w for w in tp.warnings))
        self.assertTrue(any('longueur utile' in w for w in tp.warnings))


class TestPostAndTypeEdit(unittest.TestCase):
    def arcs(self):
        tp = model.Toolpath(op_id='', tool_id='', name='arc', source='typeedit')
        tp.moves = [model.Move('rapid', 10, 0, 1), model.Move('feed', 10, 0, -0.2),
                    model.Move('arc_ccw', 0, 10, -0.2, 0, 0), model.Move('arc_cw', 10, 0, -0.2, 0, 0),
                    model.Move('rapid', 10, 0, 1)]
        return tp


    def test_arc_points_direction(self):
        tp = self.arcs()
        pts = model.arc_points((10, 0, 0), tp.moves[2], 0.01)
        self.assertGreater(pts[len(pts) // 2][1], 0)                      # anti-horaire : par le haut
        self.assertAlmostEqual(math.hypot(*pts[len(pts) // 2][:2]), 10, places=9)
        feed, _ = tp.lengths()
        self.assertAlmostEqual(feed, 1.2 + 2 * (math.pi * 10 / 2), delta=0.01)   # plongée + deux quarts

    def test_typeedit_roundtrip(self):
        tp = self.arcs()
        data = typeedit.write_bytes(tp, comment='Contour [CUT 3.02]', tool_number=3, tool_diameter=6,
                                    tool_angle=30, tool_tip=0.6)
        self.assertEqual(data[6:10], b'0112')
        back = typeedit.read_bytes(data)
        self.assertEqual(back.name, 'Contour [CUT 3.02]')
        self.assertEqual(back.header['tool'], {'number': 3, 'diameter': 6.0, 'angle': 30.0, 'tip': 0.6})
        self.assertEqual([(m.kind, m.x, m.y, m.z, m.cx, m.cy) for m in back.moves],
                         [(m.kind, m.x, m.y, m.z, m.cx if m.is_arc else 0.0, m.cy if m.is_arc else 0.0)
                          for m in tp.moves])
        with self.assertRaises(typeedit.VnvError):
            typeedit.read_bytes(data[:-5])

    def test_companions(self):
        with tempfile.TemporaryDirectory() as tmp:
            for n in ('a.vnd', 'a.000', 'a.001', 'a.BAK', 'ab.000'):
                pathlib.Path(tmp, n).write_bytes(typeedit.write_bytes(self.arcs()) if n[-1].isdigit() else b'')
            self.assertEqual([p.name for p in typeedit.companions(os.path.join(tmp, 'a.vnd'))], ['a.000', 'a.001'])
            self.assertEqual(len(typeedit.read_all(os.path.join(tmp, 'a.vnd'))), 2)

    def test_reverse(self):
        tp = self.arcs()
        r = edit.reversed_toolpath(tp)
        self.assertEqual(r.moves[2].kind, 'arc_ccw')                      # le retour de l'arc horaire
        self.assertAlmostEqual(r.lengths()[0], tp.lengths()[0], places=6)
        rr = edit.reversed_toolpath(r)
        self.assertEqual([(m.x, m.y, m.z) for m in rr.moves], [(m.x, m.y, m.z) for m in tp.moves])


class TestPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.canvas.doc.add(Shape(path=geom.Path([geom.rect(0, 0, 20, 10)])))

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_ops_from_colors_compute_and_post(self):
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        p = self.w.cam_panel
        p.ops_from_colors()
        s = p.setup()
        self.assertEqual(len(s.operations), 1)
        tps = p.compute()
        self.assertEqual(len(self.w.canvas.toolpaths), 1)
        self.assertIn('Temps estimé', p.info.text())
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, 'p.nc')
            old = QFileDialog.getSaveFileName, QMessageBox.information
            QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (out, ''))
            QMessageBox.information = staticmethod(lambda *a, **k: None)
            try:
                p.win.settings.setValue('fao/verifier', False)
                from tests._posts import registered            # post-processeurs : plugins (round 218)
                with registered():
                    p.post_process()
            finally:
                QFileDialog.getSaveFileName, QMessageBox.information = old
                p.win.settings.remove('fao/verifier')                  # réglage remis pour les essais suivants
            self.assertIn('M30', pathlib.Path(out).read_text(encoding='ascii'))
        p.paths.item(0).setCheckState(p.paths.item(0).checkState().__class__.Unchecked)
        self.assertEqual(self.w.canvas.toolpaths, [])
        self.assertEqual(tps[0].op_id, s.operations[0].id)

    def test_typeedit_import_creates_tools(self):
        tp = TestPostAndTypeEdit.arcs(None)
        with tempfile.TemporaryDirectory() as tmp:
            pathlib.Path(tmp, 'b.vnd').write_bytes(b'')
            typeedit.write(tp, os.path.join(tmp, 'b.000'), comment='CP_Finishing', tool_number=4,
                           tool_diameter=6, tool_angle=30, tool_tip=0.2)
            tps = self.w.cam_panel.import_typeedit([os.path.join(tmp, 'b.vnd')])
        self.assertEqual(len(tps), 1)
        t = self.w.cam_panel.setup().tool(tps[0].tool_id)
        self.assertEqual((t.number, t.diameter, t.angle, t.kind), (4, 6.0, 30.0, 'conique'))
        self.assertEqual(len(self.w.canvas.toolpaths), 1)


if __name__ == '__main__':
    unittest.main()
