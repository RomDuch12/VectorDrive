"""Round 5 : calques ↔ outils, accrochage, duplication, surface, options."""
import math
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import duplicate, geom
from vectordrive.core.document import Document, Group, Layer, Shape
from vectordrive.core.geom import Path
from vectordrive.core.snap import Snap
from vectordrive.io import native, registry, vnd, vnd_write
from tests.corpus import corpus

ROOT = pathlib.Path(__file__).resolve().parents[2]
VND_DATRON = corpus('vnd_datron_1')


def square(x=0, y=0, w=10, tool=0):
    return Shape(path=Path([geom.rect(x, y, w, w)]), tool=tool)


class TestSnap(unittest.TestCase):
    def setUp(self):
        self.s = Snap(enabled=True, grid_step=5.0)
        self.items = [square(0, 0, 10), Shape(path=Path([geom.circle((50, 50), 10)]))]

    def test_node(self):
        h = self.s.query(10.3, 9.8, 1.0, self.items)
        self.assertEqual((h.kind, h.x, h.y), ('node', 10, 10))

    def test_middle(self):
        h = self.s.query(5.2, 0.3, 1.0, self.items)
        self.assertEqual(h.kind, 'middle')
        self.assertAlmostEqual(h.x, 5)
        self.assertAlmostEqual(h.y, 0)

    def test_center_of_circle(self):
        h = self.s.query(50.4, 49.7, 1.0, self.items)
        self.assertEqual(h.kind, 'center')
        self.assertAlmostEqual(h.x, 50, places=9)
        self.assertAlmostEqual(h.y, 50, places=9)

    def test_arc_midpoint_on_circle(self):
        # milieu d'un quart de cercle = point du cercle à 45°
        h = self.s.query(50 + 7.2, 50 + 7.0, 1.0, self.items)
        self.assertEqual(h.kind, 'middle')
        self.assertAlmostEqual(math.hypot(h.x - 50, h.y - 50), 10, places=9)

    def test_grid_and_disabled(self):
        h = self.s.query(24.6, 30.4, 1.0, self.items)
        self.assertEqual((h.kind, h.x, h.y), ('grid', 25, 30))
        self.s.modes = {'node'}
        self.assertIsNone(self.s.query(24.6, 30.4, 1.0, self.items))
        self.s.enabled = False
        self.assertIsNone(self.s.query(10, 10, 1.0, self.items))

    def test_exclude(self):
        h = self.s.query(10.1, 10.1, 1.0, self.items, exclude=[self.items[0]])
        self.assertEqual(h.kind, 'grid')

    def test_group_leaves(self):
        g = Group(children=[square(100, 100, 4)])
        h = self.s.query(104.2, 100.1, 1.0, [g])
        self.assertEqual((h.kind, h.x, h.y), ('node', 104, 100))


class TestDuplicate(unittest.TestCase):
    def test_linear(self):
        out = duplicate.linear([square()], 3, 15, 0)
        self.assertEqual([round(o.bbox()[0], 9) for o in out], [15, 30, 45])
        self.assertEqual(len({o.id for o in out}), 3)

    def test_grid(self):
        out = duplicate.grid([square()], 3, 2, 20, 20)
        self.assertEqual(len(out), 5)
        self.assertIn((40.0, 20.0), [(round(o.bbox()[0], 9), round(o.bbox()[1], 9)) for o in out])

    def test_circular_full(self):
        out = duplicate.circular([square(95, -5, 10)], 4, (0, 0), 360)
        centers = sorted((round((o.bbox()[0] + o.bbox()[2]) / 2, 6), round((o.bbox()[1] + o.bbox()[3]) / 2, 6))
                         for o in out)
        self.assertEqual(centers, sorted([(0.0, 100.0), (-100.0, 0.0), (0.0, -100.0)]))

    def test_circular_arc_without_rotation(self):
        tri = Shape(path=Path([geom.polygon((100, 0), 5, 3)]))
        out = duplicate.circular([tri], 3, (0, 0), 90, rotate=False)
        self.assertEqual(len(out), 2)
        last, b = out[-1].bbox(), tri.bbox()
        px, py = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        # le centre de l'objet tourne de 90° autour de l'origine
        self.assertAlmostEqual((last[0] + last[2]) / 2, -py, places=9)
        self.assertAlmostEqual((last[1] + last[3]) / 2, px, places=9)
        # sans rotation, les dimensions de l'objet sont conservées
        self.assertAlmostEqual(last[2] - last[0], tri.bbox()[2] - tri.bbox()[0], places=9)

    def test_clone_renews_group_ids(self):
        g = Group(children=[square(), square(20)])
        c = g.clone()
        self.assertNotEqual(c.id, g.id)
        self.assertFalse({x.id for x in c.children} & {x.id for x in g.children})


class TestLayers(unittest.TestCase):
    def test_active_layer(self):
        d = Document(layers=[Layer('A', tool=0), Layer('B', tool=3)])
        self.assertEqual(d.active_layer.name, 'A')
        d.active = d.layers[1].id
        sh = d.add(square())
        self.assertIs(d.layer_of(sh), d.layers[1])

    def test_infer_tools(self):
        d = Document(layers=[Layer('A', items=[square(tool=4), square(tool=4), square(tool=1)])])
        d.infer_layer_tools()
        self.assertEqual(d.layers[0].tool, 4)

    def test_native_round_trip(self):
        d = Document(layers=[Layer('A', tool=2, items=[square(tool=2)]), Layer('B', tool=5)])
        d.active = d.layers[1].id
        with tempfile.TemporaryDirectory() as t:
            f = pathlib.Path(t) / 'a.vdz'
            native.write(d, f)
            back = registry.open_document(f)
        self.assertEqual([L.tool for L in back.layers], [2, 5])
        self.assertEqual(back.active_layer.name, 'B')

    @unittest.skipUnless(VND_DATRON.exists(), 'VND du corpus absent')
    def test_vnd_layer_tool_written(self):
        doc = vnd.read(VND_DATRON)
        L = next(L for L in doc.layers if L.items)
        new_tool = (L.tool + 3) % 10
        L.tool = new_tool
        vnd._set_tool(L.items, new_tool)                 # comme le panneau Calques (r547 : l'outil des objets compte)
        data, _report = vnd_write.write_document(doc)
        with tempfile.TemporaryDirectory() as t:
            f = pathlib.Path(t) / 'b.vnd'
            f.write_bytes(data)
            back = vnd.read(f)
        self.assertEqual(next(M for M in back.layers if M.name == L.name).tool, new_tool)
        # structure inchangée : fin d'origine conservée (FAO, réglages)
        self.assertEqual(data[-3000:], VND_DATRON.read_bytes()[-3000:])


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def make(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        w.modified = False
        return w

    def test_layers_panel(self):
        w = self.make()
        doc = w.canvas.doc
        w.layers_panel.add_layer()
        self.assertEqual(len(doc.layers), 2)
        self.assertIs(doc.active_layer, doc.layers[1])
        self.assertEqual(w.canvas.current_tool_index, doc.layers[1].tool)
        sh = doc.add(square(), doc.layers[0])
        w.canvas.select([sh])
        w.layers_panel.selection_to_layer()
        self.assertIs(doc.layer_of(sh), doc.layers[1])
        self.assertEqual(sh.tool, doc.layers[1].tool)
        w.layers_panel.delete_layer()
        self.assertEqual(len(doc.layers), 1)
        self.assertEqual(sh.tool, doc.layers[0].tool)
        w.undo()
        self.assertEqual(len(w.canvas.doc.layers), 2)
        w.modified = False
        w.close()

    def test_duplicate_and_area(self):
        w = self.make()
        doc = w.canvas.doc
        ring = Shape(path=Path([geom.circle((0, 0), 10), geom.circle((0, 0), 5)]))
        doc.add(ring)
        w.canvas.select([ring])
        n, a = w.selection_area()
        self.assertEqual(n, 2)
        self.assertAlmostEqual(a, math.pi * 75, delta=1e-3)
        new = w.duplicate({'mode': 'circular', 'ci_n': 6, 'center': (50, 0), 'ci_angle': 360.0,
                           'rotate': True})
        self.assertEqual(len(new), 5)
        self.assertEqual(sum(1 for _ in doc.iter_items()), 6)
        w.modified = False
        w.close()

    def test_canvas_snap(self):
        from PySide6.QtCore import QPointF
        w = self.make()
        c = w.canvas
        doc = c.doc
        doc.add(square(0, 0, 10))
        c.resize(800, 600)
        c.fit((0, 0, 100, 100))
        w.A['snap'].setChecked(True)
        q = c.to_screen(10.4, 10.3)
        x, y = c.snap_doc(QPointF(q.x(), q.y()))
        self.assertEqual((x, y), (10, 10))
        self.assertEqual(c._snap_hit.kind, 'node')
        w.A['snap'].setChecked(False)
        x, y = c.snap_doc(QPointF(q.x(), q.y()))
        self.assertNotEqual((x, y), (10, 10))
        w.modified = False
        w.close()


if __name__ == '__main__':
    unittest.main()
