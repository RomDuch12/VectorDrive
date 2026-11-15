"""Round 407 : duplication libre (TypeEdit) — chaque clic pose une copie."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QImage, QMouseEvent, QPainter
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


def ev():
    return QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(0, 0), QPointF(0, 0), Qt.MouseButton.LeftButton,
                       Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)


class TestFreeDup(unittest.TestCase):
    def test_place(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            s = Shape(path=geom.Path([geom.rect(0, 0, 4, 2)]))
            c.doc.add(s)
            c.select([s])
            w.set_tool('dup_free')
            t = c.tool_obj
            t.move(None, (20.0, 20.0), ev())
            img = QImage(200, 200, QImage.Format.Format_ARGB32)
            p = QPainter(img)
            t.paint(p)                                           # aperçu sans erreur
            p.end()
            for pt in ((20.0, 20.0), (40.0, 10.0)):
                t.press(None, pt, ev())
                t.release(None, pt, ev())
            items = c.doc.layers[0].items
            self.assertEqual(len(items), 3)
            centers = sorted(((it.bbox()[0] + it.bbox()[2]) / 2, (it.bbox()[1] + it.bbox()[3]) / 2) for it in items)
            self.assertEqual([tuple(round(v, 6) for v in cc) for cc in centers], [(2, 1), (20, 20), (40, 10)])
            w.undo()
            self.assertEqual(len(c.doc.layers[0].items), 2)
        finally:
            w.set_tool('select')
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
