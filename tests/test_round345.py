"""Round 345 : fiche de réglage (feuille d'atelier) — plaque, outils,
opérations dans l'ordre, temps, avertissements, vue des trajectoires."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.cam import model as M
from vectordrive.core import geom
from vectordrive.core.document import Plate, Shape

app = QApplication.instance() or QApplication([])


class TestSheet(unittest.TestCase):
    def test_sheet(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            c.doc.plate = Plate(100, 50, material='Laiton', thickness=1.5)
            c.doc.add(Shape(path=geom.Path([geom.rect(10, 10, 30, 20)]), tool=0))
            s = w.cam_panel.setup()
            t = M.CamTool(name='Fraise 2', diameter=2, number=4)
            s.tools = [t]
            s.operations = [M.Operation(name='Détourage', kind='contour', side='exterieur', depth=1.5, step_down=0.5,
                                        tool_id=t.id)]
            w.cam_panel.save(s)
            path = os.path.join(tempfile.mkdtemp(), 'fiche.html')
            self.assertEqual(w.setup_sheet(path, open_it=False), path)
            with open(path, encoding='utf-8') as f:
                h = f.read()
            for needle in ('Fiche de réglage', 'Laiton', '100 × 50 mm', 'T4', 'Fraise 2', 'Détourage', '1,5 mm',
                           '<svg', 'polyline'):
                self.assertIn(needle, h)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
