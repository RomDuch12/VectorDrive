"""Round 557 : F10 › Fichiers « Symboles créés : couleurs gardées » — décoché, le symbole est écrit sans le
bloc VectorDrive (exactement comme TypeEdit)."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import geom
from vectordrive.core.document import Shape
from vectordrive.io import smb


class TestOption(unittest.TestCase):
    def test_off(self):
        items = [Shape(path=geom.Path([geom.rect(0, 0, 5, 5)]), tool=3)]
        f = pathlib.Path(tempfile.mkdtemp()) / 's.smb'
        smb.KEEP_COLORS = False
        try:
            smb.write(items, f, tools={3: '#ff0000'})
        finally:
            smb.KEEP_COLORS = True
        self.assertNotIn(smb.COLORS_MAGIC, f.read_bytes())
        smb.write(items, f, tools={3: '#ff0000'})
        self.assertIn(smb.COLORS_MAGIC, f.read_bytes())

    def test_option_applied(self):
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.options import BY_KEY
        self.assertTrue(BY_KEY['symboles/couleurs'].default)
        w = MainWindow()
        try:
            w.settings.setValue('symboles/couleurs', False)
            w.apply_options()
            self.assertFalse(smb.KEEP_COLORS)
        finally:
            w.settings.setValue('symboles/couleurs', True)
            w.apply_options()
            w.modified = False
            w.close()
        self.assertTrue(smb.KEEP_COLORS)


if __name__ == '__main__':
    unittest.main()
