"""Round 957 : la fenêtre du BAT tient dans l'écran — ses réglages défilent quand l'écran est plus petit qu'eux, ses
boutons restent visibles."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r957.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QRect  # noqa: E402
from PySide6.QtGui import QScreen  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialogButtonBox  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.io import proof  # noqa: E402


class BatWindow(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def dialog(self, height: int):
        """La fenêtre du BAT ouverte sur un écran dont la zone de travail a cette hauteur."""
        from vectordrive.ui.batdialog import BatDialog
        with mock.patch.object(QScreen, 'availableGeometry', return_value=QRect(0, 0, 1920, height)):
            d = BatDialog(self.w, self.w.canvas.doc, proof.ProofInfo(company='Essai'))
            d.show()
            app.processEvents()
        self.addCleanup(d.close)
        return d

    def test_it_fits_a_1080p_screen(self):
        d = self.dialog(1032)                                               # 1920 × 1080, barre des tâches en bas
        self.assertLessEqual(d.height() + 48, 1032)                         # avant : 1 068 px, boutons hors de l'écran
        scroll = getattr(d, 'options_scroll', None)
        self.assertIsNotNone(scroll)
        buttons = d.findChild(QDialogButtonBox)
        self.assertFalse(scroll.isAncestorOf(buttons))                      # les boutons ne défilent pas
        self.assertLessEqual(buttons.mapTo(d, buttons.rect().bottomLeft()).y(), d.height())
        for field in (d.logo2, d.title_color, d.edits['client'], d.fit):    # tous les réglages sont dans le volet
            self.assertTrue(scroll.widget().isAncestorOf(field))
        self.assertGreater(scroll.verticalScrollBar().maximum(), 0)         # ce qui dépasse défile
        self.assertEqual(scroll.horizontalScrollBar().maximum(), 0)         # jamais en largeur
        scroll.ensureWidgetVisible(d.logo2)                                 # le dernier réglage s'atteint
        app.processEvents()
        self.assertFalse(d.logo2.visibleRegion().isEmpty())

    def test_a_taller_screen_shows_everything(self):
        d = self.dialog(1400)
        scroll = getattr(d, 'options_scroll', None)
        self.assertIsNotNone(scroll)                                        # avant : pas de volet
        self.assertEqual(scroll.verticalScrollBar().maximum(), 0)           # tout est là : rien ne défile
        self.assertGreaterEqual(d.height(), scroll.widget().sizeHint().height())


if __name__ == '__main__':
    unittest.main()
