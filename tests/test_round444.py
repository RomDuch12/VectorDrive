"""Round 444 : Ctrl+7 sens des contours (vert horaire, bleu anti-horaire, noir ouvert : round 1169),
Ctrl+8 couleurs des outils, Ctrl+9 remplissage ; mêmes réglages à l'export ; 3D filaire par défaut."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom, orient
from vectordrive.core.document import Document, Shape

app = QApplication.instance() or QApplication([])


def doc3():
    d = Document()
    ccw = geom.rect(0, 0, 10, 10)
    cw = geom.Path([geom.rect(20, 0, 10, 10)]).reversed().contours[0] if hasattr(geom.Path, 'reversed') else None
    if cw is None:
        cw = geom.rect(20, 0, 10, 10)
        cw = geom.Contour([s.reversed() for s in reversed(cw.segments)], True)
    line = geom.Contour([geom.Line((40, 0), (50, 10))], False)
    for c in (ccw, cw, line):
        d.add(Shape(path=geom.Path([c]), tool=0))
    return d


class TestOrient(unittest.TestCase):
    def test_split(self):
        d = doc3()
        kinds = [list(orient.split(it.path)) for it in d.iter_leaves()]
        self.assertEqual(kinds, [['ccw'], ['cw'], ['open']])

    def test_export_colors(self):
        from vectordrive.io import raster
        d = doc3()
        img = raster.render(d, raster.RasterSpec(dpi=100, orientation=True, include_plate=False, margin=1,
                                                 line_mm=0.6, tool_widths=False))
        k = 100 / 25.4

        def px(x, y):                                            # mm du dessin → pixel (y vers le haut)
            return QColor(img.pixel(int((x + 1) * k), int((11 - y) * k)))
        self.assertGreater(px(0, 5).blue(), px(0, 5).green())        # anti-horaire : bleu (round 1169)
        self.assertGreater(px(20, 5).green(), px(20, 5).blue())      # horaire : vert
        self.assertLess(px(45, 5).lightness(), 80)                   # ouvert : noir


class TestWindow(unittest.TestCase):
    def test_actions_and_3d(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            self.assertEqual(w.A['direction'].shortcut().toString(), 'Ctrl+7')
            self.assertEqual(w.A['tool_colors'].shortcut().toString(), 'Ctrl+8')
            self.assertEqual(w.A['fill'].shortcut().toString(), 'Ctrl+9')
            self.assertTrue(w.A['tool_colors'].isChecked() and w.canvas.tool_colors)
            w.A['tool_colors'].trigger()
            self.assertFalse(w.canvas.tool_colors)
            for leaf in doc3().iter_leaves():
                w.canvas.doc.add(leaf)
            w.A['direction'].trigger()
            w.canvas.resize(400, 300)
            w.canvas.grab()                                           # dessin sans erreur
            self.assertTrue(w.canvas._orient)
            from vectordrive.ui.view3d import View3D
            self.assertEqual(View3D().display, 'filaire')
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
