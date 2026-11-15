"""Round 579 : Ouvrir — un dossier réseau (partage, lecteur réseau) est lu dans le fil de calcul : un partage
hors d'atteinte ne fige plus la fenêtre (Annuler s'il tarde)."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from vectordrive.ui import file_browser as FB
from vectordrive.ui import symbols as S

app = QApplication.instance() or QApplication([])


class TestRemote(unittest.TestCase):
    def test_is_remote(self):
        self.assertTrue(S.is_remote('\\\\serveur\\partage\\dossier'))
        self.assertTrue(S.is_remote('//serveur/partage'))
        self.assertFalse(S.is_remote(tempfile.gettempdir()))

    def test_list_dir(self):
        d = pathlib.Path(tempfile.mkdtemp())
        (d / 'Sous').mkdir()
        (d / 'a.dxf').write_text('0\nEOF\n', encoding='ascii')
        (d / 'b.txt').write_text('x', encoding='ascii')
        files, dirs, stats = S.list_dir(d, ('.dxf',))
        self.assertEqual([f.name for f in files], ['a.dxf'])
        self.assertEqual([x.name for x in dirs], ['Sous'])
        self.assertIn(str(d / 'a.dxf'), stats)
        self.assertIsNone(S.list_dir(d / 'absent', ('.dxf',)))

    def test_remote_in_worker(self):
        d = pathlib.Path(tempfile.mkdtemp())
        (d / 'a.dxf').write_text('0\nEOF\n', encoding='ascii')
        s = QSettings(os.path.join(tempfile.mkdtemp(), 's.ini'), QSettings.Format.IniFormat)
        p = FB.FileBrowserPanel(s)
        p.EXTS = FB.BROWSER_EXT
        from vectordrive.ui import progress as UP
        with mock.patch.object(S, 'is_remote', return_value=True), \
                mock.patch.object(UP, 'run', wraps=UP.run) as run:
            p.show_folder(d)
        self.assertTrue(any(c.args[2] is S.list_dir for c in run.call_args_list))
        self.assertIn('a.dxf', [p.list.item(i).text() for i in range(p.list.count())])
        (d / 'Sous').mkdir()
        from PySide6.QtWidgets import QTreeWidgetItem
        it = QTreeWidgetItem([d.name])
        it.setData(0, 0x0100, str(d))
        p._add_placeholder(it, d)
        with mock.patch.object(S, 'is_remote', return_value=True):
            p._expand(it)                                                      # arbre : dépliage en fond
        self.assertEqual([it.child(i).text(0) for i in range(it.childCount())], ['Sous'])
        p.deleteLater()


if __name__ == '__main__':
    unittest.main()
