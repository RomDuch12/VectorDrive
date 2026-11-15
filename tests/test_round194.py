"""Round 194 : fichiers récents 1 à 4 et réglage des machines en commandes (TypeEdit)."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="40mm" height="20mm" viewBox="0 0 40 20">'
       '<rect x="5" y="5" width="30" height="10"/></svg>')


class TestRecent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_mapping(self):
        from vectordrive.ui.shortcuts import TE_ACTIONS
        for n in range(1, 5):
            self.assertEqual(TE_ACTIONS[f'ID_FILE_MRU_FILE{n}'], f'recent_{n}')
        self.assertEqual(TE_ACTIONS['ID_MACHINING_SETUPMACHINES'], 'cam_machines')

    def test_open_recent(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                a = pathlib.Path(tmp, 'plaque_a.svg')
                b = pathlib.Path(tmp, 'plaque_b.svg')
                for p in (a, b):
                    p.write_text(SVG, encoding='utf-8')
                gone = str(pathlib.Path(tmp, 'disparu.svg'))
                w.settings.setValue('fichiers/recents', [str(b), gone, str(a)])
                w._recent_tips()
                self.assertEqual(w.A['recent_1'].toolTip(), 'plaque_b.svg')
                self.assertFalse(w.open_recent(2))                                    # introuvable
                self.assertFalse(w.open_recent(4))                                    # pas de 4e
                w.modified = False
                self.assertTrue(w.open_recent(3))
                self.assertEqual(pathlib.Path(w.path or w.canvas.doc.source_path).name, 'plaque_a.svg')
                self.assertIn('cam_machines', w.A)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
