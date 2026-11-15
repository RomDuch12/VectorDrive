"""Round 587 : Ouvrir en Détails — colonne Type au nom du format (« AutoCAD DXF », « Symbole TypeEdit »…),
« Programme … » pour un programme machine."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from vectordrive.ui import file_browser as FB

app = QApplication.instance() or QApplication([])


class TestTypes(unittest.TestCase):
    def test_types(self):
        d = pathlib.Path(tempfile.mkdtemp())
        for n in ('a.dxf', 'b.smb', 'c.nc', 'd.step'):
            (d / n).write_text('x', encoding='ascii')
        s = QSettings(os.path.join(tempfile.mkdtemp(), 's.ini'), QSettings.Format.IniFormat)
        p = FB.FileBrowserPanel(s)
        p.EXTS = FB.BROWSER_EXT + ('.nc',)
        p.show_folder(d)
        kinds = {p.list.item(i).text(): p.list.item(i).data(FB.ROLE_DETAILS)[2] for i in range(p.list.count())
                 if p.list.item(i).data(FB.ROLE_KIND) is None}
        self.assertEqual(kinds['a.dxf'], 'AutoCAD DXF')
        self.assertEqual(kinds['b.smb'], 'Symbole TypeEdit')
        self.assertEqual(kinds['c.nc'], 'Programme NC')
        self.assertTrue(kinds['d.step'].startswith('STEP'))
        p.deleteLater()


if __name__ == '__main__':
    unittest.main()
