"""Round 1041 : demande du 15/11 ~17 h 50 « romduch with claude et gmail.com visible uniquement dans à propos pas le
ruban aide »."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1041.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication, QLabel, QMessageBox  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.i18n import tr  # noqa: E402


class AuthorOnlyInAbout(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()
        cls.w.deleteLater()

    def test_only_in_the_about_box(self):
        from vectordrive.ui.ribbon import RibbonGroup
        texts = [lbl.text().lower() for lbl in self.w.ribbon.findChildren(QLabel)]
        self.assertTrue(texts)
        self.assertFalse([t for t in texts if 'romduch' in t or 'with claude' in t])   # avant : groupe de l'onglet Aide
        self.assertNotIn(tr('Développé par'), [g.title.text() for g in self.w.ribbon.findChildren(RibbonGroup)])
        got = []
        with mock.patch.object(QMessageBox, 'about', side_effect=lambda _p, _t, text: got.append(text)):
            self.w.about()
        self.assertEqual(len(got), 1)
        self.assertIn('RomDuch with Claude', got[0])
        self.assertIn('romduch' + chr(64) + 'gmail.com', got[0])


if __name__ == '__main__':
    unittest.main()
