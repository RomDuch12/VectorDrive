"""Round 784 : gamme de relief, profondeur d'un nouveau parcours sur un relief."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())

import numpy as np
from PySide6.QtWidgets import QApplication, QMessageBox

from vectordrive.cam import model, strategies as S
from vectordrive.core import galbe as GB
from vectordrive.core.document import Layer, Shape
from vectordrive.core.geom import Path, rect


def dome(top=3.0, n=60):
    y, x = np.mgrid[0:n, 0:n]
    r = np.hypot(x - (n - 1) / 2, y - (n - 1) / 2) / ((n - 1) / 2)
    return GB.encode(np.clip(1 - r * r, 0, 1) * top, 0.0, 30.0, 0.5, GB.GalbeSpec(z_max=top), 0, 'Dôme')


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.win = MainWindow()
        cls.panel = cls.win.cam_panel

    @classmethod
    def tearDownClass(cls):
        cls.win.close()

    def setUp(self):
        doc = self.win.canvas.doc
        doc.layers = [Layer(name='Plan 1')]
        doc.active = doc.layers[0].id
        self.img = dome()
        doc.layers[0].items.append(self.img)
        self.win.canvas.select([self.img])
        s = self.panel.setup()
        s.operations = []
        self.big = model.CamTool(name='F6', kind='fraise', diameter=6.0, step_down=1.0, feed=800.0, number=11)
        self.mid = model.CamTool(name='F2', kind='fraise', diameter=2.0, step_down=1.0, feed=800.0, number=12)
        self.ball = model.CamTool(name='B1', kind='boule', diameter=1.0, step_down=1.0, feed=800.0, number=13)
        s.tools = [self.mid, self.ball, self.big]
        self.panel.save(s)

    def _make(self, **kw):
        s = self.panel.setup()
        with mock.patch.object(self.panel, 'compute'):
            return self.panel.new_relief_gamme(exec_dialog=False, **kw), s


class Gamme(Base):
    def test_palette(self):
        from vectordrive.ui.cam_palette import FAMILIES
        from vectordrive.ui.cam_panel import presets
        self.assertIn('gamme_relief', dict(FAMILIES)['Usinage 3D'])
        self.assertIn('gamme_relief', presets())
        self.assertIn('cam_new_gamme_relief', self.win.A)

    def test_ribbon_once(self):
        found = [b for i in range(self.win.ribbon.count()) for g in self.win.ribbon.page(i).groups() for b in g.buttons()
                 if b.defaultAction() is self.win.A['cam_new_gamme_relief']]
        self.assertEqual(len(found), 1)

    def test_te_links(self):
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertEqual(TE_ACTIONS['ID_CMD_TP_TYPEART'], 'cam_new_relief')
        self.assertEqual(TE_ACTIONS['ID_CMD_TP_TYPEARTSEQUENCE'], 'cam_new_gamme_relief')

    def test_order_from_big_to_small(self):
        ops, s = self._make(tool_ids=[self.mid.id, self.big.id], finish_id=self.ball.id, stock=0.2)
        self.assertEqual([o.kind for o in ops], ['ebauche3d', 'reprise3d', 'surface3d'])
        self.assertEqual([o.tool_id for o in ops], [self.big.id, self.mid.id, self.ball.id])
        self.assertEqual(ops[1].ref_tool_id, self.big.id)
        self.assertEqual(ops[0].stock, 0.2)
        self.assertEqual(ops[2].stock, 0.0)

    def test_rough_only(self):
        ops, s = self._make(tool_ids=[self.big.id])
        self.assertEqual([o.kind for o in ops], ['ebauche3d'])

    def test_three_tools_chain(self):
        ops, s = self._make(tool_ids=[self.ball.id, self.mid.id, self.big.id])
        self.assertEqual([o.kind for o in ops], ['ebauche3d', 'reprise3d', 'reprise3d'])
        self.assertEqual(ops[2].ref_tool_id, self.mid.id)

    def test_scope_is_the_selection(self):
        ops, s = self._make(tool_ids=[self.big.id])
        self.assertEqual(ops[0].items, [self.img.id])

    def test_operations_saved(self):
        ops, s = self._make(tool_ids=[self.big.id, self.mid.id])
        self.assertEqual([o.id for o in self.panel.setup().operations], [o.id for o in ops])

    def test_every_operation_cuts(self):
        ops, s = self._make(tool_ids=[self.big.id, self.mid.id], finish_id=self.ball.id, stock=0.1)
        doc = self.win.canvas.doc
        for o in ops:
            tp = S.compute(doc, s, o)
            self.assertTrue([m for m in tp.moves if m.kind == 'feed'], o.name)

    def test_rough_keeps_its_stock(self):
        ops, s = self._make(tool_ids=[self.big.id], stock=0.3)
        tp = S.compute(self.win.canvas.doc, s, ops[0])
        low = min(m.z for m in tp.moves if m.kind == 'feed')
        self.assertGreater(low, -3.0)

    def test_no_relief(self):
        self.win.canvas.select([])
        self.assertIsNone(self.panel.new_relief_gamme(exec_dialog=False, tool_ids=[self.big.id]))

    def test_shape_is_not_a_relief(self):
        sh = Shape(path=Path([rect(0, 0, 5, 5)]))
        self.win.canvas.doc.layers[0].items.append(sh)
        self.win.canvas.select([sh])
        self.assertIsNone(self.panel.new_relief_gamme(exec_dialog=False, tool_ids=[self.big.id]))

    def test_no_tool(self):
        with mock.patch.object(QMessageBox, 'information') as info:
            self.assertIsNone(self.panel.new_relief_gamme(exec_dialog=False, tool_ids=[]))
        info.assert_called_once()

    def test_same_diameter_refused(self):
        twin = model.CamTool(name='F6b', kind='fraise', diameter=6.0, step_down=1.0, feed=800.0, number=14)
        s = self.panel.setup()
        s.tools.append(twin)
        self.panel.save(s)
        with mock.patch.object(QMessageBox, 'information') as info:
            self.assertIsNone(self.panel.new_relief_gamme(exec_dialog=False, tool_ids=[self.big.id, twin.id]))
        info.assert_called_once()

    def test_dialog(self):
        ids, fin, stock, depth = self.panel._relief_gamme_dialog(self.panel.setup(), 0.15, 0.0, run=False)
        self.assertEqual(ids, [self.big.id])                          # le plus gros, coché d'avance
        self.assertEqual(fin, self.ball.id)                           # la plus petite boule
        self.assertEqual(stock, 0.15)
        self.assertEqual(depth, 0.0)

    def test_dialog_cancel(self):
        from PySide6.QtWidgets import QDialog
        with mock.patch.object(QDialog, 'exec', return_value=0):
            self.assertIsNone(self.panel.new_relief_gamme(exec_dialog=True))

    def test_dialog_ok(self):
        from PySide6.QtWidgets import QDialog
        with mock.patch.object(QDialog, 'exec', return_value=1), mock.patch.object(self.panel, 'compute'):
            ops = self.panel.new_relief_gamme(exec_dialog=True)
        self.assertEqual([o.kind for o in ops], ['ebauche3d', 'surface3d'])

    def test_new_operation_goes_through_the_gamme(self):
        with mock.patch.object(self.panel, 'new_relief_gamme', return_value='ok') as g:
            self.assertEqual(self.panel.new_operation('gamme_relief', exec_dialog=False), 'ok')
        g.assert_called_once()


class Depth(Base):
    """La profondeur d'un nouveau parcours sur un relief : sa hauteur, pas le préréglage."""

    def test_relief_operation(self):
        with mock.patch.object(self.panel, 'compute_op'):
            o = self.panel.new_operation('relief', exec_dialog=False)
        self.assertAlmostEqual(o.depth, 3.0, places=2)

    def test_finish_operation(self):
        with mock.patch.object(self.panel, 'compute_op'):
            o = self.panel.new_operation('finition', exec_dialog=False)
        self.assertAlmostEqual(o.depth, 3.0, places=2)

    def test_plain_image_keeps_the_preset(self):
        self.img.extra.pop('galbe')
        with mock.patch.object(self.panel, 'compute_op'):
            o = self.panel.new_operation('relief', exec_dialog=False)
        self.assertEqual(o.depth, 1.0)

    def test_relief_is_not_squashed(self):
        with mock.patch.object(self.panel, 'compute_op'):
            o = self.panel.new_operation('relief', exec_dialog=False)
        tp = S.compute(self.win.canvas.doc, self.panel.setup(), o)
        self.assertAlmostEqual(min(m.z for m in tp.moves if m.kind == 'feed'), -3.0, delta=0.1)


if __name__ == '__main__':
    unittest.main()
