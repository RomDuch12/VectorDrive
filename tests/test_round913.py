"""Round 913 : le plan de travail redimensionné pendant qu'il est caché (Qt rejoue la taille, ancienne taille -1)
garde le zoom choisi ; « Tout voir » seulement à la première taille, ou si la vue est encore celle du dernier
cadrage. Le zoom d'un gros dessin passe toujours par l'aperçu, puis le rendu net."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r913.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Shape  # noqa: E402


class HiddenResize(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.resize(900, 700)
        self.c = self.w.canvas
        for i in range(30):
            self.c.doc.add(Shape(path=geom.Path([geom.circle((i * 6.0, 12.0), 2.5)])))
        self.c.invalidate()
        self.c.grab()

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def view(self):
        return (self.c.scale, self.c.ox, self.c.oy)

    def replay_size(self):
        """Le plan de travail, caché, change de taille puis revient : Qt rejoue la taille au rendu suivant."""
        c = self.c
        wd, ht = c.width(), c.height()
        c.resize(wd - 50, ht - 30)
        c.resize(wd, ht)
        c.grab()

    def test_zoom_is_kept(self):
        self.c.zoom_at(1.6, QPointF(120, 140))
        zoomed = self.view()
        self.replay_size()
        self.assertEqual(self.view(), zoomed)

    def test_pan_is_kept(self):
        c = self.c
        c.ox += 37.0
        c.oy -= 21.0
        moved = self.view()
        self.replay_size()
        self.assertEqual(self.view(), moved)

    def test_untouched_view_is_fitted_again(self):
        c = self.c
        first = self.view()
        self.assertEqual(c._fit_view, first)                                # cadré à la première taille
        c.resize(c.width() // 2, c.height())                                # plus étroit, caché
        c.grab()
        self.assertNotEqual(self.view(), first)                             # « Tout voir » à la nouvelle taille
        self.assertEqual(c._fit_view, self.view())

    def test_slow_zoom_goes_through_the_preview(self):
        c = self.c
        first = c._scene_k
        c._render_ms = 500.0                                                # dessin « lent »
        c.zoom_at(1.25, QPointF(150, 200))
        self.replay_size()
        self.assertEqual(c._scene_k, first)                                 # aperçu : scène non refaite
        self.assertTrue(c._refine.isActive())
        c._refine.stop()
        c._refine_now()
        c.grab()
        self.assertNotEqual(c._scene_k, first)                              # puis le rendu net à la nouvelle vue


if __name__ == '__main__':
    unittest.main()
