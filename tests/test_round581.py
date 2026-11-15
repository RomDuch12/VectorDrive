"""Round 581 : Bibliothèque — récents et favoris sur un partage réseau gardés sans le vérifier (pas
d'attente d'un partage hors d'atteinte)."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QSettings

from vectordrive.ui import symbols as S


class TestRemoteLists(unittest.TestCase):
    def test_no_check(self):
        s = QSettings(os.path.join(tempfile.mkdtemp(), 's.ini'), QSettings.Format.IniFormat)
        local = pathlib.Path(tempfile.mkdtemp()) / 'absent.smb'
        s.setValue(S.RECENT_KEY, ['//absent/partage/a.smb', str(local)])
        s.setValue(S.FAV_KEY, ['//absent/partage/Dossier', str(local)])
        real = pathlib.Path.is_file

        def guarded(self):
            if str(self).startswith('\\'):
                raise AssertionError('accès réseau')
            return real(self)
        with mock.patch.object(pathlib.Path, 'is_file', guarded):
            self.assertEqual([p.name for p in S.recent_files(s)], ['a.smb'])      # local absent : retiré
        self.assertEqual([p.name for p in S.favorite_paths(s)], ['Dossier'])


if __name__ == '__main__':
    unittest.main()
