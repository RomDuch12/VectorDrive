"""Round 432 : un volume reste hachuré même avec l'affichage Remplissage."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import solids as S

app = QApplication.instance() or QApplication([])


@unittest.skipUnless(S.available(), 'manifold3d absent')
class TestHatchWithFill(unittest.TestCase):
    def test_fill_on(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.resize(800, 600)
            c = w.canvas
            c.doc.add(S.make_shape(S.box(0, 0, 0, 40, 40, 10)))
            c.show_fill = True
            w.show()
            app.processEvents()
            c.resize(700, 500)
            c.fit()
            app.processEvents()
            img = c.grab().toImage()
            p0, p1 = c.to_screen(5, 5), c.to_screen(35, 35)
            xs = range(int(min(p0.x(), p1.x())) + 4, int(max(p0.x(), p1.x())) - 4)    # chaque point (un sur deux
            ys = range(int(min(p0.y(), p1.y())) + 4, int(max(p0.y(), p1.y())) - 4)    # manque les hachures à 45°)
            colours = {img.pixelColor(x, y).rgb() for x in xs for y in ys}
            self.assertGreater(len(colours), 1)                       # hachures, pas un aplat
        finally:
            w.canvas.show_fill = False
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
