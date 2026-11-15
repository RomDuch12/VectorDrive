"""Round 463 : outils du document reconnus dans Mes outils ; les absents copiés d'un clic."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.cam import model, toollib

app = QApplication.instance() or QApplication([])


class TestMatch(unittest.TestCase):
    def test_find(self):
        a = model.CamTool(name='Fraise 2', diameter=2, ref='0068432A')
        a.folder = 'Datron'
        b = model.CamTool(name='V30', kind='conique', diameter=3, angle=30, tip=0.2)
        lib = [a, b]
        self.assertIs(toollib.find_match(model.CamTool(name='autre nom', diameter=5, ref='0068432a'), lib), a)
        self.assertIs(toollib.find_match(model.CamTool(name='v30', kind='conique', diameter=3, angle=30, tip=0.2),
                                         lib), b)
        self.assertIsNone(toollib.find_match(model.CamTool(name='V30', kind='conique', diameter=3, angle=60), lib))


class TestPanel(unittest.TestCase):
    def test_tooltip_and_copy(self):
        tmp = pathlib.Path(tempfile.mkdtemp()) / 'tools.json'
        known = model.CamTool(name='Fraise 2', diameter=2, ref='REF2')
        known.folder = 'Atelier'
        toollib.save([known], tmp)
        old = os.environ.get('VECTORDRIVE_TOOLS')
        os.environ['VECTORDRIVE_TOOLS'] = str(tmp)
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            cp = w.cam_panel
            s = cp.setup()
            s.tools = [model.CamTool(name='Fraise 2 doc', diameter=2, ref='REF2', number=1),
                       model.CamTool(name='Nouvelle', diameter=4, number=2)]
            cp.save(s)
            self.assertIn('Dans Mes outils : Atelier', cp.tools.item(0, 1).toolTip())
            self.assertIn('Absent de Mes outils', cp.tools.item(1, 1).toolTip())
            self.assertEqual(cp.copy_missing_tools(), 1)
            lib = toollib.load(tmp)
            self.assertEqual([t.name for t in lib], ['Fraise 2', 'Nouvelle'])
            self.assertEqual(lib[1].folder, 'Copiés des dessins')
            self.assertEqual(cp.copy_missing_tools(), 0)                          # déjà copiés
        finally:
            w.modified = False
            w.close()
            if old is None:
                os.environ.pop('VECTORDRIVE_TOOLS', None)
            else:
                os.environ['VECTORDRIVE_TOOLS'] = old


if __name__ == '__main__':
    unittest.main()
