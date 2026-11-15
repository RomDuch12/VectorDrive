"""Round 461 : bibliothèque — VND et SVG acceptés ; outils importés : indication pour les réserver à
la machine du réglage (sans question modale)."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from vectordrive.cam import model, toollib

app = QApplication.instance() or QApplication([])

SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="40mm" height="20mm" viewBox="0 0 40 20">'
       '<rect x="1" y="1" width="38" height="18" fill="none" stroke="black"/></svg>')
CSV = 'name;kind;diameter\nF2;fraise;2\nF3;fraise;3\n'


class TestLibraryFormats(unittest.TestCase):
    def test_svg_listed_and_previewed(self):
        from vectordrive.ui import symbols as S
        root = pathlib.Path(tempfile.mkdtemp())
        (root / 'cadre.svg').write_text(SVG, encoding='utf-8')
        st = QSettings(os.path.join(tempfile.mkdtemp(), 'r.ini'), QSettings.Format.IniFormat)
        p = S.SymbolPanel(st)
        p.roots = [root]
        p._fill_tree()
        p.show_folder(root)
        self.assertEqual([p.list.item(i).text() for i in range(p.list.count())], ['cadre'])
        self.assertIsNotNone(S.preview_image(root / 'cadre.svg', 100))
        self.assertIsNotNone(S.file_as_group(root / 'cadre.svg'))
        p.deleteLater()


class TestImportHint(unittest.TestCase):
    def test_hint(self):
        from vectordrive.ui.toollib_dialog import ToolLibraryDialog
        tmp = pathlib.Path(tempfile.mkdtemp())
        p = tmp / 'tools.json'
        toollib.save([model.CamTool(name='F1', diameter=1.0)], p)
        (tmp / 'achat.csv').write_text(CSV, encoding='utf-8')
        dlg = ToolLibraryDialog(None, None, p)
        try:
            self.assertEqual(dlg.offer_machine([model.CamTool()]), '')               # pas de machine : rien
            dlg._machine = ('datron', 'DATRON Next')
            self.assertEqual(dlg.import_file(tmp / 'achat.csv'), 2)
            self.assertIn('« DATRON Next »', dlg.info.text())
            self.assertTrue(all(not t.machines for t in toollib.load(p)))            # rien changé sans le demander
            self.assertEqual(dlg.selected_folder(), 'achat')                          # Machines… vise ce dossier
        finally:
            dlg.close()


if __name__ == '__main__':
    unittest.main()
