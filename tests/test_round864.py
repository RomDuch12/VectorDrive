"""Round 864 : la simulation en objet relief (manuel de TE, page 776 imprimée)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', os.path.join(tempfile.mkdtemp(), 'session'))
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')

import numpy as np
from PySide6.QtWidgets import QApplication

from vectordrive.cam import model as M
from vectordrive.cam import simulate
from vectordrive.cam import strategies as S
from vectordrive.core import galbe as GB
from vectordrive.core import geom
from vectordrive.core.document import Document, Image, Layer, Plate, Shape
from vectordrive.ui.sim_dialog import SimDialog

app = QApplication.instance() or QApplication([])


def steps():
    """10 mm x 5 mm au pas de 0,1 ; x de 5 à 15, y de 2 à 7 : un trou de 0,5 à droite, plus haut que le milieu."""
    H = np.zeros((51, 101))
    H[35:45, 70:90] = -0.5
    return simulate.SimResult(H=H, x0=5.0, y0=2.0, res=0.1, deepest=-0.5)


def paths():
    doc = Document()
    doc.plate = Plate(width=60.0, height=60.0)
    doc.layers = [Layer(name='A', items=[Shape(path=geom.Path([geom.rect(10, 10, 20, 20)]))])]
    setup = M.setup_of(doc)
    tool = M.CamTool(name='F', diameter=2.0)
    setup.tools.append(tool)
    op = M.Operation(kind='poche', tool_id=tool.id, depth=1.0)
    setup.operations.append(op)
    M.store(doc, setup)
    return S.compute(doc, setup, op, (0.0, 0.0)), setup


class TestToRelief(unittest.TestCase):

    def test_an_object_with_the_depth(self):
        img = simulate.to_relief(steps())
        self.assertIsInstance(img, Image)
        self.assertAlmostEqual(img.extra['galbe']['relief_depth'], 0.5, places=6)

    def test_nothing_cut(self):
        self.assertIsNone(simulate.to_relief(simulate.SimResult(H=np.zeros((5, 5)), x0=0.0, y0=0.0, res=0.1)))

    def test_it_stays_in_place(self):
        b = simulate.to_relief(steps()).bbox()
        self.assertAlmostEqual(b[0], 4.95, places=6)
        self.assertAlmostEqual(b[2], 15.05, places=6)
        self.assertAlmostEqual(b[1], 1.95, places=6)
        self.assertAlmostEqual(b[3], 7.05, places=6)

    def test_the_heights_read_back(self):
        got = GB.decode(simulate.to_relief(steps()))
        H, x0, y1, res = got
        self.assertAlmostEqual(res, 0.1, places=6)
        self.assertEqual(H.shape, (51, 101))
        self.assertAlmostEqual(float(H.min()), -0.5, places=3)
        self.assertAlmostEqual(float(H.max()), 0.0, places=3)

    def test_the_hole_is_at_the_same_place(self):
        H, x0, y1, res = GB.decode(simulate.to_relief(steps()))
        ys, xs = np.nonzero(H < -0.25)
        px = x0 + (xs + 0.5) * res
        py = y1 - (ys + 0.5) * res
        self.assertAlmostEqual(float(px.min()), 12.0, places=6)      # x0 + 70 x 0,1
        self.assertAlmostEqual(float(px.max()), 13.9, places=6)
        self.assertAlmostEqual(float(py.min()), 5.5, places=6)       # y0 + 35 x 0,1
        self.assertAlmostEqual(float(py.max()), 6.4, places=6)

    def test_the_tool_and_the_name(self):
        img = simulate.to_relief(steps(), tool=3, name='Essai')
        self.assertEqual((img.tool, img.name), (3, 'Essai'))

    def test_a_stock_above_zero(self):
        s = steps()
        s.H = s.H + 1.0                                  # brut d'un mm au-dessus de la pièce
        s.H[0, 0] = -1.0
        img = simulate.to_relief(s)
        self.assertAlmostEqual(img.extra['galbe']['relief_depth'], 2.0, places=6)


class TestDialog(unittest.TestCase):

    def setUp(self):
        simulate._SIM_CACHE.clear()
        self.tp, self.setup_doc = paths()

    def test_no_button_without_a_drawing(self):
        d = SimDialog(None, [self.tp], self.setup_doc)
        self.assertTrue(d.relief_button.isHidden())
        self.assertIsNone(d.lay_relief())
        d.done(0)

    def test_it_lays_once(self):
        got = []
        d = SimDialog(None, [self.tp], self.setup_doc, on_relief=got.append)
        self.assertFalse(d.relief_button.isHidden())
        d.relief_button.click()
        self.assertEqual(len(got), 1)
        self.assertIsInstance(got[0], Image)
        self.assertFalse(d.relief_button.isEnabled())
        d.run()
        self.assertTrue(d.relief_button.isEnabled())
        d.done(0)

    def test_nothing_cut_says_so(self):
        got = []
        d = SimDialog(None, [self.tp], self.setup_doc, on_relief=got.append)
        d.result = simulate.SimResult(H=np.zeros((5, 5)), x0=0.0, y0=0.0, res=0.1)
        self.assertIsNone(d.lay_relief())
        self.assertEqual(got, [])
        self.assertIn('Rien de creusé', d.info.text())
        d.done(0)


class TestPanel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.close()

    def test_it_goes_on_the_active_layer(self):
        w = self.win
        doc = w.canvas.doc
        s = Shape(path=geom.Path([geom.rect(10, 10, 20, 20)]))
        layer = Layer(name='Plan 1', items=[s])
        doc.layers[:] = [layer]
        doc.active = layer.id
        doc.plate = Plate(width=60.0, height=60.0)
        w._undo.clear()
        w.canvas.select([s])
        panel = w.cam_panel
        setup = panel.setup()
        setup.operations[:] = []
        panel.save(setup)
        simulate._SIM_CACHE.clear()
        panel.new_operation('gravure', exec_dialog=False)
        d = panel.simulate(exec_dialog=False)
        img = d.lay_relief()
        d.done(0)
        self.assertIn(img, layer.items)
        self.assertEqual(w.canvas.selection, [img])
        b = img.bbox()
        self.assertTrue(b[0] < 10.0 < 30.0 < b[2])
        w.undo()
        self.assertEqual(len(w.canvas.doc.layers[0].items), 1)


if __name__ == '__main__':
    unittest.main()
