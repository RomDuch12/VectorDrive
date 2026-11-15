"""Round 438 : fenêtres réemployées (caractères, filtre et modes de sélection, aimantation) rouvertes
après fermeture ; filtre d'événements de la fenêtre principale."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QEvent
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


class TestReopen(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_close_and_reopen(self):
        from PySide6.QtCore import QCoreApplication
        for key in ('char_map', 'select_filter', 'selection_modes'):
            self.w.A[key].trigger()
            tops = [t for t in app.topLevelWidgets() if t is not self.w and t.isVisible() and t.isWindow()]
            self.assertTrue(tops, key)
            for t in tops:
                t.close()                                         # la croix de la fenêtre
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            app.processEvents()
            self.w.A[key].trigger()                               # rouverte : plus d'objet détruit
            app.processEvents()
            self.assertTrue(any(t.isVisible() for t in app.topLevelWidgets() if t is not self.w), key)
            for t in app.topLevelWidgets():
                if t is not self.w and t.isVisible():
                    t.close()

    def test_event_filter_fast_path(self):
        from PySide6.QtCore import QPointF, Qt
        ev = QMouseEvent(QEvent.Type.MouseMove, QPointF(1, 1), QPointF(1, 1), Qt.MouseButton.NoButton,
                         Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
        self.assertFalse(self.w.eventFilter(self.w, ev))


if __name__ == '__main__':
    unittest.main()
