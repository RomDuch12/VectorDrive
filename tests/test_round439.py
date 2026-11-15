"""Round 439 : menus et boîtes ponctuels libérés — répétés, ils n'accumulent pas de widgets."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QCoreApplication, QEvent, QTimer
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


def settle():
    for _ in range(3):
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()


def close_popups():
    """Menus et boîtes refermés aussitôt ouverts."""
    for get in (app.activePopupWidget, app.activeModalWidget):
        m = get()
        if m is not None:
            (m.reject if hasattr(m, 'reject') else m.close)()


class TestNoLeak(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        sh = Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]))
        self.w.canvas.doc.add(sh)
        self.w.canvas.selection = [sh]
        self.timer = QTimer()
        self.timer.timeout.connect(close_popups)
        self.timer.start(30)

    def tearDown(self):
        self.timer.stop()
        self.w.modified = False
        self.w.close()

    def test_repeated(self):
        for key in ('palette_align', 'undo_list', 'redo_list', 'cad_massprop'):
            counts = []
            for _ in range(4):
                self.w.A[key].trigger()
                close_popups()
                settle()
                counts.append(len(app.allWidgets()))
            self.assertEqual(counts[-1], counts[1], (key, counts))


if __name__ == '__main__':
    unittest.main()
