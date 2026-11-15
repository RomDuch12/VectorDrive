"""Round 588 : F10 › BAT › logo — « … » ouvre une boîte Ouvrir filtrée sur les images (plus « Enregistrer
sous » en JSON, celle du fichier d'outils)."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication, QFileDialog, QLineEdit

from vectordrive.ui import options as O

app = QApplication.instance() or QApplication([])


class TestLogoBrowse(unittest.TestCase):
    def test_open_images(self):
        holder = type('D', (), {})()
        e = QLineEdit()
        with mock.patch.object(QFileDialog, 'getOpenFileName', return_value=('C:/logo.png', '')) as op, \
                mock.patch.object(QFileDialog, 'getSaveFileName', side_effect=AssertionError('pas Enregistrer')):
            O.OptionsDialog._browse_file(holder, e, O.BY_KEY['bat/logo'])
        self.assertEqual(e.text(), 'C:/logo.png')
        self.assertIn('*.png', op.call_args.args[3])
        with mock.patch.object(QFileDialog, 'getSaveFileName', return_value=('C:/t.json', '')) as sv:
            O.OptionsDialog._browse_file(holder, e, O.BY_KEY['fao/bibliotheque'])
        self.assertEqual(sv.call_args.args[3], 'JSON (*.json)')


if __name__ == '__main__':
    unittest.main()
