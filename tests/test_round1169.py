"""Round 1169 : « Mode Ctrl+7 : ne pas mettre les fleches (réservées à une autre fonction parametres) colorier en
noir (ou blanc en mode sombre) les contours ouverts, en vert les sens horaires, bleu les antihoraires (clair en mode
sombre foncé en mode clair) »."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'rctrl7.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Group, Shape  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : Ctrl+7 mettait l’anti-horaire en vert, l’horaire en bleu, et une flèche au départ'


def reverse(c):
    """Le même contour parcouru dans l'autre sens."""
    return geom.Contour([s.reversed() for s in reversed(c.segments)], c.closed)


def ccw_rect(x, y, w, h):
    c = geom.rect(x, y, w, h)
    return c if c.signed_area() > 0 else reverse(c)


def cw_rect(x, y, w, h):
    return reverse(ccw_rect(x, y, w, h))


def dist(a: QColor, b: QColor) -> int:
    return abs(a.red() - b.red()) + abs(a.green() - b.green()) + abs(a.blue() - b.blue())


class Colors(unittest.TestCase):
    def test_colors_by_theme(self):
        from vectordrive.core import orient
        self.assertTrue(hasattr(orient, 'colors'), BEFORE)
        light, dark = orient.colors(False), orient.colors(True)
        self.assertEqual(QColor(light['open']).name(), '#000000')              # ouvert : noir en thème clair
        self.assertEqual(QColor(dark['open']).name(), '#ffffff')               # … blanc en thème sombre
        for pal in (light, dark):
            g, b = QColor(pal['cw']), QColor(pal['ccw'])
            self.assertTrue(g.green() > g.blue() + 40 and g.green() > g.red())     # horaire : vert
            self.assertTrue(b.blue() > b.green() + 40 and b.blue() > b.red())      # anti-horaire : bleu
        for k in ('cw', 'ccw'):
            self.assertLess(QColor(light[k]).lightness(), 110)                 # foncés en thème clair
            self.assertGreater(QColor(dark[k]).lightness(), 160)               # clairs en thème sombre
        self.assertIs(orient.colors(), orient.COLORS)                          # export (papier) : celles du clair
        # repère du dessin, Y vers le haut comme à l'écran : aire signée positive = anti-horaire (bleu)
        c = geom.Contour([geom.Line((0, 0), (10, 0)), geom.Line((10, 0), (10, 10)),
                          geom.Line((10, 10), (0, 10)), geom.Line((0, 10), (0, 0))], True)
        self.assertGreater(c.signed_area(), 0)
        self.assertEqual(orient.orientation(c), 'ccw')                         # droite puis haut : anti-horaire
        self.assertEqual(orient.orientation(reverse(c)), 'cw')

    def test_export_follows(self):
        from vectordrive.core.document import Document
        from vectordrive.io import raster
        d = Document()
        d.add(Shape(path=geom.Path([ccw_rect(0, 0, 10, 10)])))
        d.add(Shape(path=geom.Path([cw_rect(20, 0, 10, 10)])))
        img = raster.render(d, raster.RasterSpec(dpi=100, orientation=True, include_plate=False, margin=1,
                                                 line_mm=0.6, tool_widths=False))
        k = 100 / 25.4

        def px(x, y):
            return QColor(img.pixel(int((x + 1) * k), int((11 - y) * k)))
        self.assertGreater(px(0, 5).blue(), px(0, 5).green() + 40, BEFORE)    # anti-horaire : bleu
        self.assertGreater(px(20, 5).green(), px(20, 5).blue() + 40)          # horaire : vert


class Canvas(unittest.TestCase):
    """Le canevas, 4 px par mm, traits sur les centres des pixels (ox, oy en x,5)."""

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        c = cls.w.canvas
        c.resize(700, 500)
        d = c.doc
        cls.cw = d.add(Shape(path=geom.Path([cw_rect(0, 0, 20, 20)])))
        cls.ccw = d.add(Shape(path=geom.Path([ccw_rect(30, 0, 20, 20)])))
        cls.open = d.add(Shape(path=geom.Path([geom.Contour([geom.Line((60, 10), (80, 10))], False)])))
        # un objet à trou : extérieur anti-horaire, trou horaire
        cls.holed = d.add(Shape(path=geom.Path([ccw_rect(90, 0, 40, 40), cw_rect(100, 10, 20, 20)])))
        cls.group = d.add(Group(children=[Shape(path=geom.Path([cw_rect(0, 50, 20, 20)]))]))
        # trait ouvert seul, loin des autres : la flèche irait à gauche de son départ
        cls.lone = d.add(Shape(path=geom.Path([geom.Contour([geom.Line((60, -30), (80, -30))], False)])))

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def setUp(self):
        c = self.w.canvas
        c.select([])
        c.show_fill = False
        c.show_starts = c.show_nodes = False
        c.scale, c.ox, c.oy = 4.0, 20.5, 300.5

    def grab(self, direction=True, arrows=False):
        c = self.w.canvas
        c.show_direction = direction
        if hasattr(c, 'show_arrows'):
            c.show_arrows = arrows
        c.update()
        return c.grab().toImage()

    def ink(self, img, x, y):
        """Couleur peinte en (x, y) du dessin : le pixel du voisinage 3×3 le plus loin du fond voisin."""
        P = self.w.canvas.to_screen(x, y)
        cx, cy = int(P.x()), int(P.y())
        bg = img.pixelColor(cx - 8, cy - 8)                                    # en biais : hors d'un trait droit
        best = bg
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                q = img.pixelColor(cx + dx, cy + dy)
                if dist(q, bg) > dist(best, bg):
                    best = q
        return best

    def check(self, dark: bool):
        with mock.patch('vectordrive.ui.icons.dark_theme', return_value=dark):
            img = self.grab()
        cw, ccw = self.ink(img, 0, 10), self.ink(img, 30, 10)
        op, hole_out, hole_in = self.ink(img, 70, 10), self.ink(img, 90, 20), self.ink(img, 100, 20)
        grp = self.ink(img, 0, 60)
        for col in (cw, hole_in, grp):                                         # horaires (trou, groupe) : vert
            self.assertGreater(col.green(), col.blue() + 40, BEFORE)
            self.assertGreater(col.green(), col.red())
        for col in (ccw, hole_out):                                            # anti-horaires : bleu
            self.assertGreater(col.blue(), col.green() + 40)
            self.assertGreater(col.blue(), col.red())
        return cw, ccw, op

    def test_light_theme(self):
        cw, ccw, op = self.check(False)
        self.assertLess(op.lightness(), 60)                                    # ouvert : noir
        self.assertLess(cw.lightness(), 110)                                   # foncés
        self.assertLess(ccw.lightness(), 130)
        self.w.canvas.select([self.cw])                                        # sélectionné : surligné, pas en vert
        with mock.patch('vectordrive.ui.icons.dark_theme', return_value=False):
            img = self.grab()
        col = self.ink(img, 0, 10)
        self.assertFalse(col.green() > col.blue() + 40 and col.green() > col.red())
        col = self.ink(img, 30, 10)                                            # les autres gardent leur sens
        self.assertGreater(col.blue(), col.green() + 40)

    def test_dark_theme(self):
        cw, ccw, op = self.check(True)
        self.assertGreater(op.lightness(), 230)                                # ouvert : blanc
        self.assertGreater(cw.lightness(), 160)                                # clairs
        self.assertGreater(ccw.lightness(), 160)

    def test_canvas_colors_follow_theme(self):
        from vectordrive.core import orient
        c = self.w.canvas
        self.assertTrue(hasattr(c, 'orient_colors'), BEFORE)
        for dark in (False, True):
            with mock.patch('vectordrive.ui.icons.dark_theme', return_value=dark):
                self.assertEqual(c.orient_colors(), orient.colors(dark))

    def wing_ink(self, img) -> int:
        """Écart au fond le plus fort là où la flèche du trait seul serait (à gauche de son départ)."""
        A = self.w.canvas.to_screen(60, -30)
        bg = img.pixelColor(int(A.x()) - 20, int(A.y()))
        pts = [A + QPointF(-2, 0)] + [A + QPointF(-6.86 * t, s * 4.12 * t) for t in (0.5, 0.65, 0.8, 0.95)
                                      for s in (1, -1)]
        return max(dist(img.pixelColor(int(q.x()), int(q.y())), bg) for q in pts)

    def test_no_arrow_in_ctrl7(self):
        img = self.grab(direction=True, arrows=False)
        P = self.w.canvas.to_screen(70, -30)
        bg = img.pixelColor(int(P.x()) - 8, int(P.y()) - 8)
        self.assertGreater(dist(self.ink(img, 70, -30), bg), 100)               # le trait, lui, est là
        self.assertLess(self.wing_ink(img), 60, BEFORE)

    def test_arrows_are_their_own_setting(self):
        from vectordrive.ui import options
        c = self.w.canvas
        self.assertIn('vue/fleches_sens', options.BY_KEY, BEFORE)
        self.assertFalse(options.BY_KEY['vue/fleches_sens'].default)
        self.assertFalse(c.show_arrows)
        img = self.grab(direction=False, arrows=True)                          # flèches sans Ctrl+7
        self.assertGreater(self.wing_ink(img), 100)
        img = self.grab(direction=True, arrows=True)                           # et avec
        self.assertGreater(self.wing_ink(img), 100)
        c.show_direction = c.show_arrows = False
        st = self.w.settings
        try:
            st.setValue('vue/fleches_sens', True)
            self.w.apply_options()
            self.assertTrue(c.show_arrows)
            self.assertFalse(c.show_direction)                                 # Ctrl+7 n'est pas touché
        finally:
            st.remove('vue/fleches_sens')
            self.w.apply_options()
        self.assertFalse(c.show_arrows)

    def test_tooltip(self):
        tip = self.w.A['direction'].toolTip()
        self.assertNotIn('flèche au départ', tip, BEFORE)
        self.assertIn('vert (horaire)', tip)


if __name__ == '__main__':
    unittest.main()
