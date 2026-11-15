"""Round 1039 : demande du 15/11 ~10 h 45 — la barre d'état montre les coordonnées du point accroché."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1039.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Shape  # noqa: E402

app = QApplication.instance() or QApplication([])


def window():
    from vectordrive.ui.main_window import MainWindow
    w = MainWindow()
    w.settings.setValue('fenetre/plein_ecran', False)
    w.resize(1200, 800)
    w.show()
    app.processEvents()
    return w


def close(w):
    w.modified = False
    for t in getattr(w, 'docs', []):
        t.modified = False
    w.close()


def hover(c, p):
    p = QPointF(p)
    c.mouseMoveEvent(QMouseEvent(QEvent.Type.MouseMove, p, p, Qt.MouseButton.NoButton, Qt.MouseButton.NoButton,
                                 Qt.KeyboardModifier.NoModifier))


class SnappedPoint(unittest.TestCase):

    def setUp(self):
        self.w = window()
        self.c = self.w.canvas
        self.c.doc.add(Shape(path=geom.Path([geom.rect(0, 0, 30, 20)])))
        self.c.invalidate()
        self.c.snap.enabled = True
        self.c.snap.modes = set(self.c.snap.modes) | {'node', 'middle'}

    def tearDown(self):
        close(self.w)

    def test_the_status_bar_shows_the_snapped_point(self):
        hover(self.c, self.c.to_screen(30, 20) + QPointF(4, 3))                   # près du coin
        self.assertIsNotNone(self.c._snap_hit)
        text = self.w.lbl_pos.text()
        self.assertIn('30.000', text)                                            # avant : le pointeur, à côté
        self.assertIn('20.000', text)
        self.assertIn('Nœud', text)                                              # et la nature du point
        hover(self.c, self.c.to_screen(15, 0) + QPointF(2, -3))                   # près du milieu du bas
        text = self.w.lbl_pos.text()
        self.assertIn('15.000', text)
        self.assertIn('Milieu', text)

    def test_without_snap_the_pointer_and_the_origin(self):
        far = self.c.to_screen(80, 60)
        hover(self.c, far)
        self.assertIsNone(self.c._snap_hit)
        x, y = self.c.to_doc(far)
        self.assertEqual(self.w.lbl_pos.text(), f'X: {x:9.3f}  Y: {y:9.3f} mm')   # le pointeur, sans nature
        self.c.set_origin(10.0, 5.0)
        hover(self.c, self.c.to_screen(30, 20) + QPointF(4, 3))
        ox, oy = self.c.origin
        self.assertIn(f'{30 - ox:.3f}', self.w.lbl_pos.text())                   # par rapport à l'origine
        self.assertIn(f'{20 - oy:.3f}', self.w.lbl_pos.text())
        self.assertIn('Nœud', self.w.lbl_pos.text())

    def test_the_snap_kind_goes_with_the_snap_mark(self):
        hover(self.c, self.c.to_screen(30, 20) + QPointF(4, 3))
        self.assertIn('Nœud', self.w.lbl_pos.text())
        self.assertIsNotNone(self.c._snap_at)
        self.c.leaveEvent(QEvent(QEvent.Type.Leave))                          # le pointeur sort de la vue
        self.assertIsNone(self.c._snap_hit)
        self.assertNotIn('⌖', self.w.lbl_pos.text())                          # plus de point accroché
        self.assertIsNone(self.c._snap_at)                                   # Alt : pas depuis une position passée
        self.assertFalse(self.c.cycle_snap())

    def test_a_new_origin_rewrites_the_coordinates(self):
        hover(self.c, self.c.to_screen(30, 20) + QPointF(4, 3))
        self.assertIn('Nœud', self.w.lbl_pos.text())
        self.c.set_origin(30.0, 20.0)                                        # l'origine posée sur ce point
        self.assertTrue(self.w.lbl_pos.text().startswith(f'X: {0.0:9.3f}  Y: {0.0:9.3f} mm'), self.w.lbl_pos.text())
        self.assertIn('Nœud', self.w.lbl_pos.text())


if __name__ == '__main__':
    unittest.main()
