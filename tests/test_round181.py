"""Round 181 : aperçu pendant les manipulations (TypeEdit : F4)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Shape


class TestPreview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_toggle_and_paint(self):
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertEqual(TE_ACTIONS['ID_MANIPULER_PREVUE'], 'drag_preview')
        w = MainWindow()
        try:
            c = w.canvas
            items = [c.doc.add(Shape(path=geom.Path([geom.rect(i * 10, 0, 5, 5)]))) for i in range(3)]
            c.select(items)
            act = w.A['drag_preview']
            self.assertTrue(act.isChecked())
            self.assertEqual(act.shortcut().toString(), 'F4')
            img = QImage(100, 100, QImage.Format.Format_RGB32)
            p = QPainter(img)
            self.assertEqual(c._paint_moving(p), 3)                              # objets entiers
            act.setChecked(False)
            self.assertFalse(c.drag_preview)
            self.assertEqual(c._paint_moving(p), 0)                              # rectangle seulement
            p.end()
            act.setChecked(True)
            self.assertTrue(c.drag_preview)
        finally:
            w.modified = False
            w.close()

    def test_gesture_paints_with_bbox_only(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            s = c.doc.add(Shape(path=geom.Path([geom.rect(0, 0, 5, 5)])))
            c.select([s])
            c.drag_preview = False
            c._drag = {'kind': 'move', 'start': None, 'delta': (2.0, 3.0)}
            img = QImage(100, 100, QImage.Format.Format_RGB32)
            p = QPainter(img)
            c._paint_gesture(p)                                                  # sans erreur
            p.end()
            c._drag = None
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
