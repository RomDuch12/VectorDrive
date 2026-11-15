"""Round 582 : menu Fichier › Récents — un fichier d'un partage réseau n'est pas interrogé (taille et date
vides) : le menu s'ouvre aussitôt, même hors d'atteinte du partage."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.ui.recent import file_details


class TestRemoteRecent(unittest.TestCase):
    def test_no_access(self):
        with mock.patch.object(pathlib.Path, 'is_file', side_effect=AssertionError('accès réseau')), \
                mock.patch.object(pathlib.Path, 'stat', side_effect=AssertionError('accès réseau')):
            d = file_details('//absent/partage/plaque.vnd')
        self.assertTrue(d['exists'])
        self.assertEqual((d['size'], d['modified']), ('', ''))
        f = pathlib.Path(tempfile.mkdtemp()) / 'a.dxf'
        self.assertFalse(file_details(str(f))['exists'])                     # local absent : comme avant


if __name__ == '__main__':
    unittest.main()
