"""Round 426 : Décaler [A] — distance sélectionnée d'emblée, jonction et original repris."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


class TestOffsetDialog(unittest.TestCase):
    def test_type_replaces(self):
        from vectordrive.ui.dialogs import OffsetDialog
        dlg = OffsetDialog(None, 2.5, 'miter', False)
        dlg.show()
        app.processEvents()
        self.assertEqual(dlg.dist.lineEdit().selectedText().strip(), '2,500' if ',' in dlg.dist.text() else '2.500')
        for ch in '5':
            app.sendEvent(dlg.dist, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_5, Qt.KeyboardModifier.NoModifier, ch))
        dlg.dist.interpretText()
        self.assertEqual(dlg.dist.value(), 5.0)
        self.assertEqual(dlg.join.currentData(), 'miter')
        self.assertFalse(dlg.keep.isChecked())
        dlg.close()

    def test_remembered(self):
        from vectordrive.ui import dialogs
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        seen = []
        real = dialogs.OffsetDialog

        class Fake(real):
            def exec(self):
                seen.append((self.dist.value(), self.join.currentData(), self.keep.isChecked()))
                self.dist.setValue(3.0)
                self.join.setCurrentIndex(self.join.findData('bevel'))
                self.keep.setChecked(False)
                return True
        try:
            sh = Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]))
            w.canvas.doc.add(sh)
            with mock.patch.object(dialogs, 'OffsetDialog', Fake):
                w.canvas.select([sh])
                w.offset_dialog()
                w.canvas.select([w.canvas.doc.layers[0].items[0]])
                w.offset_dialog()
            self.assertEqual(seen[1], (3.0, 'bevel', False))                 # la fois d'avant
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
