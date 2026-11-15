"""Round 454 : panneau FAO — outils et opérations avec la silhouette et la fiche de l'outil ; outil
réservé à d'autres machines signalé."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.cam import model

app = QApplication.instance() or QApplication([])


class TestPanel(unittest.TestCase):
    def test_icons_and_machine_warning(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            cp = w.cam_panel
            s = cp.setup()
            s.post = 'gcode'
            a = model.CamTool(name='Fraise 2', kind='fraise', diameter=2.0, number=1, machines=['datron'])
            b = model.CamTool(name='V30', kind='conique', diameter=3.0, angle=30, number=2)
            s.tools = [a, b]
            s.operations = [model.Operation(kind='gravure', tool_id=a.id, depth=0.2)]
            cp.save(s)
            cell = cp.tools.item(0, 1)
            self.assertFalse(cell.icon().isNull())
            self.assertIn('Réservé à d\'autres machines', cell.toolTip())
            self.assertNotIn('Réservé', cp.tools.item(1, 1).toolTip())
            op_tool = cp.ops.item(0, 2)
            self.assertTrue(op_tool.text().startswith('T1 Fraise 2 — Ø2'))
            self.assertFalse(op_tool.icon().isNull())
            self.assertIn('Machines', op_tool.toolTip())
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
