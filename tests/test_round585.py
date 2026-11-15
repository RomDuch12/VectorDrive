"""Round 585 : « Imprimer… » au clic droit de la bibliothèque aussi (grande fenêtre et panneau) ; pas pour un
programme machine."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from vectordrive.ui.symbols import SymbolPanel

app = QApplication.instance() or QApplication([])


class TestLibraryPrint(unittest.TestCase):
    def test_menu(self):
        d = pathlib.Path(tempfile.mkdtemp())
        (d / 'a.dxf').write_text('0\nEOF\n', encoding='ascii')
        s = QSettings(os.path.join(tempfile.mkdtemp(), 's.ini'), QSettings.Format.IniFormat)
        p = SymbolPanel(s)
        p.show_folder(d)
        got = []
        p.printRequested.connect(got.append)
        row = next(i for i in range(p.list.count()) if p.list.item(i).text() == 'a')
        p.list.item(row).setSelected(True)
        m = p.menu(p.list, None, exec_menu=False)
        act = next(a for a in m.actions() if a.text() == 'Imprimer…')
        act.trigger()
        self.assertEqual(got, [str(d / 'a.dxf')])
        p.deleteLater()


if __name__ == '__main__':
    unittest.main()
