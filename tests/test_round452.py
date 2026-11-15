"""Round 452 : FAO — « Vérifier l'outil » (surface hors d'atteinte, plus gros Ø qui passe partout) ;
3D — arêtes de la plaque en filaire, trajectoires colorées par profondeur."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication, QMessageBox

from vectordrive.cam import model, toolfit
from vectordrive.cam.model import Move, Toolpath
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape

app = QApplication.instance() or QApplication([])


def doc():
    d = Document()
    d.add(Shape(path=geom.Path([geom.rect(0, 0, 30, 20)]), tool=0))            # large
    d.add(Shape(path=geom.Path([geom.rect(40, 0, 1.0, 20)]), tool=0))          # fente de 1 mm
    return d


class TestFit(unittest.TestCase):
    def test_check(self):
        d = doc()
        op = model.Operation(kind='poche', sources=[0], depth=1.0)
        small = toolfit.check(d, op, model.CamTool(name='F0.8', kind='fraise', diameter=0.8))
        self.assertEqual(small.parts, 2)
        self.assertLess(small.fraction, 0.005)
        big = toolfit.check(d, op, model.CamTool(name='F2', kind='fraise', diameter=2.0))
        self.assertGreater(big.unreached, 19.0)                                  # la fente entière (20 mm²)
        self.assertAlmostEqual(big.fit_diameter, 1.0, delta=0.08)               # 1 mm passe partout (ou presque)
        self.assertEqual(toolfit.check(Document(), op, model.CamTool()).area, 0.0)

    def test_form_button(self):
        from vectordrive.ui.cam_panel import FieldsDialog
        d = doc()
        t = model.CamTool(name='F2', kind='fraise', diameter=2.0, number=4)
        op = model.Operation(kind='poche', sources=[0], depth=1.0, tool_id=t.id)
        dlg = FieldsDialog(None, 'Op', op, d, [t])
        try:
            self.assertIsNotNone(dlg.fit_button)
            with mock.patch.object(QMessageBox, 'information') as box:
                msg = dlg.check_tool()
                box.assert_called_once()
            self.assertIn('T4 F2', msg)
            self.assertIn("n'atteint pas", msg)
            self.assertIn('Ø 1', msg)
        finally:
            dlg.reject()


class Test3D(unittest.TestCase):
    def test_depth_colors_and_edges(self):
        from vectordrive.ui import view3d as V
        tp = Toolpath(op_id='', tool_id='', name='a')
        tp.moves = [Move('rapid', 0, 0, 5), Move('plunge', 0, 0, -0.1), Move('feed', 5, 0, -0.1),
                    Move('feed', 5, 0, -2.0), Move('feed', 10, 0, -2.0)]
        arr, _r = V.path_batch([tp], colors='profondeur')
        shallow, deep = arr[arr[:, 2] > -0.5], arr[arr[:, 2] < -1.5]
        self.assertGreater(float(shallow[:, 7].mean()), float(deep[:, 7].mean()))   # vert en surface, sombre au fond
        e = V.box_edges(V.box(0, 0, 10, 5, -3, 0))
        self.assertEqual(e.shape, (24, 9))
        self.assertEqual((float(e[:, 2].min()), float(e[:, 2].max())), (-3.0, 0.0))


if __name__ == '__main__':
    unittest.main()
