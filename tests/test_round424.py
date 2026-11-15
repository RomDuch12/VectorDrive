"""Round 424 : volumes hachurés dans le plan 2D."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core import solids as S
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


@unittest.skipUnless(S.available(), 'manifold3d absent')
class TestHatch(unittest.TestCase):
    def test_hatched(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.resize(800, 600)
            c = w.canvas
            vol = S.make_shape(S.box(0, 0, 0, 40, 40, 10))
            flat = Shape(path=geom.Path([geom.rect(60, 0, 40, 40)]))
            c.doc.add(vol)
            c.doc.add(flat)
            c.show_fill = False                                            # réglage laissé par un autre essai
            c.engrave_preview = False
            w.show()
            app.processEvents()
            c.resize(700, 500)
            c.fit()
            app.processEvents()
            img = c.grab().toImage()

            def inked(rect_doc):                                          # points qui diffèrent du premier
                p0, p1 = c.to_screen(rect_doc[0], rect_doc[1]), c.to_screen(rect_doc[2], rect_doc[3])
                bg = img.pixelColor(int(min(p0.x(), p1.x())) + 4, int(min(p0.y(), p1.y())) + 4)
                n = 0
                for x in range(int(min(p0.x(), p1.x())) + 4, int(max(p0.x(), p1.x())) - 4):      # chaque point :
                    for y in range(int(min(p0.y(), p1.y())) + 4, int(max(p0.y(), p1.y())) - 4):  # hachures à 45°
                        if img.pixelColor(x, y) != bg:
                            n += 1
                return n
            self.assertGreater(inked((5, 5, 35, 35)), 20)                  # le volume : hachures dedans
            self.assertEqual(inked((65, 5, 95, 35)), 0)                    # la forme simple : vide
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
