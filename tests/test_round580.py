"""Round 580 : Récents d'Ouvrir — un fichier d'un partage réseau n'est ni vérifié ni lu dans le fil de
l'interface (partage hors d'atteinte : pas de gel)."""
import os
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


class TestRemoteRecents(unittest.TestCase):
    def test_no_disk_access(self):
        remote = '//absent/partage/plaque.dxf'
        s = QSettings(os.path.join(tempfile.mkdtemp(), 's.ini'), QSettings.Format.IniFormat)
        s.setValue('fichiers/recents', [remote])
        p = FB.FileBrowserPanel(s)
        p.EXTS = FB.BROWSER_EXT
        import pathlib
        with mock.patch.object(pathlib.Path, 'is_file', side_effect=AssertionError('accès réseau')), \
                mock.patch.object(pathlib.Path, 'stat', side_effect=AssertionError('accès réseau')):
            p.show_recents()
        rows = [p.list.item(i) for i in range(p.list.count())]
        self.assertEqual([r.text() for r in rows], ['plaque.dxf'])
        self.assertEqual(rows[0].data(FB.ROLE_DETAILS)[:2], (0, None))
        self.assertEqual(S.known_stat(None, pathlib.Path(remote)), (0, None))
        p.deleteLater()


if __name__ == '__main__':
    unittest.main()
