"""Round 342 : gomme — surfaces fermées entamées ou coupées en deux, traits
ouverts coupés, objet effacé en entier, annulable."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication

from vectordrive.core import eraser as ER, geom
from vectordrive.core.cadtools import mass_properties
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


class TestEraser(unittest.TestCase):
    def test_core(self):
        band = ER.eraser_region([(10, -5), (10, 15)], 1.0)                  # coupe verticale de 2 mm
        cut = ER.erase(geom.Path([geom.rect(0, 0, 20, 10)]), band)
        self.assertEqual(len(cut.contours), 2)
        self.assertAlmostEqual(mass_properties(cut)['area'], 180.0, 3)
        line = ER.erase(geom.Path([geom.polyline([(0, 5), (20, 5)])]), band)
        self.assertEqual(len(line.contours), 2)
        self.assertAlmostEqual(sum(c.length() for c in line.contours), 18.0, 3)
        self.assertIsNone(ER.erase(geom.Path([geom.rect(50, 50, 2, 2)]), band))   # pas touché
        gone = ER.erase(geom.Path([geom.rect(9.5, 0, 1, 1)]), band)
        self.assertEqual(gone.contours, [])

    def test_tool(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            c.doc.add(Shape(path=geom.Path([geom.rect(0, 0, 20, 10)])))
            c.doc.add(Shape(path=geom.Path([geom.rect(9.6, 20, 0.8, 0.8)])))        # sous la gomme : effacé
            w.set_tool('eraser')
            t = c.tool_obj
            t.key(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_BracketRight, Qt.KeyboardModifier.NoModifier))
            self.assertAlmostEqual(c.eraser_radius, 1.25)

            def e(kind, buttons):
                return QMouseEvent(kind, QPointF(0, 0), QPointF(0, 0), Qt.MouseButton.LeftButton, buttons,
                                   Qt.KeyboardModifier.NoModifier)
            t.press(c.to_screen(10, -5), (10.0, -5.0), e(QEvent.Type.MouseButtonPress, Qt.MouseButton.LeftButton))
            for y in range(-4, 26, 2):
                t.move(c.to_screen(10, y), (10.0, float(y)), e(QEvent.Type.MouseMove, Qt.MouseButton.LeftButton))
            t.release(c.to_screen(10, 25), (10.0, 25.0), e(QEvent.Type.MouseButtonRelease, Qt.MouseButton.NoButton))
            items = c.doc.layers[0].items
            self.assertEqual(len(items), 1)
            self.assertEqual(len(items[0].path.contours), 2)
            w.undo()
            self.assertEqual(len(c.doc.layers[0].items), 2)
        finally:
            w.set_tool('select')
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
