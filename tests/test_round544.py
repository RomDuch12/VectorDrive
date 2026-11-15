"""Round 544 : grande fenêtre de la bibliothèque — un double-clic ferme la fenêtre et le dessin se pose
d'un clic (son contour suit le pointeur ; Échap : rien)."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

DXF = "0\nSECTION\n2\nENTITIES\n0\nLINE\n8\n0\n10\n0\n20\n0\n11\n10\n21\n4\n0\nENDSEC\n0\nEOF\n"


class TestPlaceByClick(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.f = pathlib.Path(tempfile.mkdtemp()) / 'a.dxf'
        self.f.write_text(DXF, encoding='ascii')
        self.w = MainWindow()

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_double_click_then_click(self):
        from vectordrive.ui import tools as T
        w = self.w
        lw = w.library_window(show=True)
        self.assertTrue(lw.click_place.isChecked())                               # par défaut
        self.assertFalse(lw.close_after.isEnabled())
        lw.panel.insertRequested.emit(str(self.f))
        self.assertFalse(lw.isVisible())                                          # fermée aussitôt
        self.assertIsInstance(w.canvas.tool_obj, T.PlaceGroupTool)
        self.assertEqual(len(list(w.canvas.doc.iter_items())), 0)                 # rien avant le clic
        w.canvas.tool_obj.move(None, (100.0, 50.0), None)
        w.canvas.tool_obj.press(None, (100.0, 50.0), None)
        items = list(w.canvas.doc.iter_items())
        self.assertEqual(len(items), 1)
        bb = items[0].bbox()
        self.assertAlmostEqual((bb[0] + bb[2]) / 2, 100.0, places=6)              # centré sur le clic
        self.assertAlmostEqual((bb[1] + bb[3]) / 2, 50.0, places=6)
        self.assertEqual(w.canvas.tool, 'select')                                 # l'outil rend la main

    def test_escape(self):
        w = self.w
        self.assertTrue(w.place_symbol_by_click(str(self.f)))
        w.canvas.toolFinished.emit()                                              # Échap
        self.assertEqual(w.canvas.tool, 'select')
        self.assertEqual(len(list(w.canvas.doc.iter_items())), 0)

    def test_big_outline_is_frame(self):
        from vectordrive.core import geom
        from vectordrive.core.document import Group, Shape
        from vectordrive.ui import tools as T
        g = Group(children=[Shape(path=geom.Path([geom.circle((i, 0), 0.4)])) for i in range(T.PlaceGroupTool.OUTLINE_LEAVES + 1)])
        t = T.PlaceGroupTool(self.w.canvas, g, lambda p: None)
        self.assertEqual(len(t.outline.contours), 1)


if __name__ == '__main__':
    unittest.main()
