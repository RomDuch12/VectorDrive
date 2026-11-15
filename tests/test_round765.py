"""Round 765 : vectoriser un logo en couleurs : une forme et un outil par couleur, le fond laissé de côté."""
import math
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', os.path.join(tempfile.mkdtemp(), 'session'))
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')

import numpy as np
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication, QFileDialog

from vectordrive.core import trace as TR
from vectordrive.core.document import Group, Image, Shape
from vectordrive.ui import dialogs
from vectordrive.ui.dialogs import qimage_rgb
from vectordrive.ui.main_window import MainWindow

app = QApplication.instance() or QApplication([])

RED, BLUE, GREEN = '#e01010', '#1030d0', '#10a030'


def logo(background='#ffffff', w=300, h=200, smooth=True) -> QImage:
    """Disque rouge, carré bleu, trait vert, sur un fond."""
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(QColor(background) if background else QColor(0, 0, 0, 0))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, smooth)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(RED))
    p.drawEllipse(QRectF(20, 40, 100, 100))
    p.setBrush(QColor(BLUE))
    p.drawRect(QRectF(150, 40, 80, 80))
    p.setBrush(QColor(GREEN))
    p.drawRect(QRectF(150, 150, 120, 20))
    p.end()
    return img


def area(contours) -> float:
    return abs(sum(c.signed_area() for c in contours))


def close(hex_a, hex_b, tol=24) -> bool:
    a = [int(hex_a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(hex_b[i:i + 2], 16) for i in (1, 3, 5)]
    return max(abs(x - y) for x, y in zip(a, b)) <= tol


class TestColors(unittest.TestCase):
    def run_trace(self, img=None, n=4, **k):
        rgb, real = qimage_rgb(img or logo())
        return TR.trace_colors(rgb, TR.TraceSpec(colors=n, **k), real)

    def test_three_colors_without_the_background(self):
        out = self.run_trace()
        self.assertEqual(len(out), 3)
        cols = [c for c, _ in out]
        for want in (RED, BLUE, GREEN):
            self.assertTrue(any(close(c, want) for c in cols), (want, cols))
        self.assertFalse(any(close(c, '#ffffff') for c in cols))

    def test_true_shapes_and_areas(self):
        by = {c: cs for c, cs in self.run_trace()}
        red = next(cs for c, cs in by.items() if close(c, RED))
        blue = next(cs for c, cs in by.items() if close(c, BLUE))
        green = next(cs for c, cs in by.items() if close(c, GREEN))
        self.assertAlmostEqual(area(red), math.pi * 50 ** 2, delta=0.02 * math.pi * 50 ** 2)
        self.assertAlmostEqual(area(blue), 6400, delta=0.02 * 6400)
        self.assertAlmostEqual(area(green), 2400, delta=0.03 * 2400)
        self.assertEqual(len(blue), 1)

    def test_largest_first(self):
        self.assertTrue(close(self.run_trace()[0][0], RED))

    def test_too_many_asked_gives_no_ghost(self):
        """10 couleurs demandées, 3 réelles : pas de liserés autour des formes."""
        out = self.run_trace(n=10)
        self.assertLessEqual(len(out), 4, [c for c, _ in out])
        for want in (RED, BLUE, GREEN):
            self.assertTrue(any(close(c, want) for c, _ in out), want)

    def test_halo_given_back(self):
        """Un dégradé d'un pixel entre deux couleurs franches n'est pas une couleur."""
        rgb = np.ones((100, 200, 3))
        rgb[:, :100] = 0.0
        rgb[:, 100] = 0.5
        rgb[:, 200 - 1] = 1.0
        centers, labels = TR.find_colors(rgb, 3)
        self.assertEqual(len(centers), 2)
        self.assertEqual(sorted(np.unique(labels)), [0, 1])

    def test_thin_real_color_kept(self):
        """Un filet d'une vraie couleur, fin mais pas un mélange des deux autres."""
        rgb = np.ones((100, 200, 3))
        rgb[:, :100] = 0.0
        rgb[:, 100:102] = (1.0, 0.0, 0.0)
        centers, _labels = TR.find_colors(rgb, 3)
        self.assertEqual(len(centers), 3)

    def test_background_kept_if_asked(self):
        out = self.run_trace(keep_background=True)
        self.assertEqual(len(out), 4)
        self.assertTrue(any(close(c, '#ffffff') for c, _ in out))

    def test_dark_background_also_left_out(self):
        out = self.run_trace(logo(background='#101010'))
        self.assertEqual(len(out), 3)
        self.assertFalse(any(close(c, '#101010') for c, _ in out))

    def test_transparent_background(self):
        out = self.run_trace(logo(background=None))
        self.assertEqual(len(out), 3)
        self.assertFalse(any(close(c, '#000000') for c, _ in out))

    def test_all_transparent_refused(self):
        img = QImage(50, 50, QImage.Format.Format_ARGB32)
        img.fill(QColor(0, 0, 0, 0))
        with self.assertRaises(ValueError):
            self.run_trace(img)

    def test_one_color_image_gives_nothing(self):
        img = QImage(50, 50, QImage.Format.Format_ARGB32)
        img.fill(QColor('#808080'))
        self.assertEqual(self.run_trace(img), [])

    def test_same_each_time(self):
        a = [(c, len(cs)) for c, cs in self.run_trace()]
        b = [(c, len(cs)) for c, cs in self.run_trace()]
        self.assertEqual(a, b)

    def test_speckles_ignored(self):
        img = logo(smooth=False)
        for x in range(0, 300, 40):
            img.setPixelColor(x, 5, QColor(RED))
        red = next(cs for c, cs in self.run_trace(img, speckle=4.0) if close(c, RED))
        self.assertEqual(len(red), 1)

    def test_rare_color_dropped(self):
        rgb = np.ones((400, 400, 3))
        rgb[100:200, 100:200] = 0.0
        rgb[300, 300] = (1.0, 0.0, 0.0)                              # un pixel
        centers, _labels = TR.find_colors(rgb, 3)
        self.assertEqual(len(centers), 2)

    def test_hole_kept(self):
        """Anneau rouge sur blanc, dans son trou une pastille bleue."""
        img = QImage(200, 200, QImage.Format.Format_ARGB32)
        img.fill(QColor('#ffffff'))
        p = QPainter(img)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(RED))
        p.drawEllipse(QRectF(20, 20, 160, 160))
        p.setBrush(QColor('#ffffff'))
        p.drawEllipse(QRectF(60, 60, 80, 80))
        p.setBrush(QColor(BLUE))
        p.drawEllipse(QRectF(85, 85, 30, 30))
        p.end()
        by = self.run_trace(img, n=3)
        red = next(cs for c, cs in by if close(c, RED))
        self.assertEqual(len(red), 2)
        blue = next(cs for c, cs in by if close(c, BLUE))
        self.assertEqual(len(blue), 1)

    def test_big_image_within_limits(self):
        rgb = np.ones((1500, 2000, 3))
        rgb[100:1000, 100:1500] = (0.8, 0.1, 0.1)
        out = TR.trace_colors(rgb, TR.TraceSpec(colors=3))
        self.assertEqual(len(out), 1)


class TestQuality(unittest.TestCase):
    def only(self, img):
        rgb, real = qimage_rgb(img)
        return TR.trace_colors(rgb, TR.TraceSpec(colors=3), real)

    def solid(self, draw):
        img = QImage(300, 300, QImage.Format.Format_ARGB32)
        img.fill(QColor('#ffffff'))
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(BLUE))
        draw(p)
        p.end()
        return img

    def test_rectangle_corners_are_sharp_and_true(self):
        (_col, cs), = self.only(self.solid(lambda p: p.drawRect(QRectF(40, 60, 200, 100))))
        self.assertEqual(len(cs), 1)
        bb = cs[0].bbox()
        for got, want in zip(bb, (40, 60, 240, 160)):
            self.assertAlmostEqual(got, want, delta=0.35)
        self.assertLessEqual(len(cs[0].segments), 8)                 # quatre côtés, pas cent petits morceaux
        pts = [s.start for s in cs[0].segments]
        for corner in ((40, 60), (240, 60), (240, 160), (40, 160)):
            self.assertLess(min(math.dist(q, corner) for q in pts), 0.6, corner)

    def test_circle_is_round_and_light(self):
        (_col, cs), = self.only(self.solid(lambda p: p.drawEllipse(QRectF(50, 50, 200, 200))))
        c = cs[0]
        self.assertLessEqual(len(c.segments), 30)
        pts = [c.segments[0].start]
        for s in c.segments:
            pts.extend(s.flatten(0.02))
        for x, y in pts:
            self.assertAlmostEqual(math.hypot(x - 150, y - 150), 100, delta=0.7)
        self.assertAlmostEqual(abs(c.signed_area()), math.pi * 100 ** 2, delta=0.01 * math.pi * 100 ** 2)

    def test_slanted_straight_edge_stays_straight(self):
        from PySide6.QtGui import QPolygonF
        from PySide6.QtCore import QPointF
        poly = QPolygonF([QPointF(40, 40), QPointF(260, 90), QPointF(240, 180), QPointF(20, 130)])
        (_col, cs), = self.only(self.solid(lambda p: p.drawPolygon(poly)))
        self.assertLessEqual(len(cs[0].segments), 20)
        self.assertAlmostEqual(abs(cs[0].signed_area()), 225.6 * 92.2, delta=0.02 * 225.6 * 92.2)

    def test_sharp_point(self):
        ink = np.zeros((60, 200), bool)
        ink[20:48, 30:180] = True
        loop = TR.trace_loops(ink)[0]
        mid = (loop + np.roll(loop, -1, axis=0)) / 2
        i = int(np.argmin(np.hypot(*(mid - (179.5, 20.0)).T)))
        x, y = TR._sharp_point(mid, i)
        self.assertAlmostEqual(x, 180.0, delta=0.1)
        self.assertAlmostEqual(y, 20.0, delta=0.1)

    def test_sharp_point_on_a_line_stays_there(self):
        mid = np.array([(float(k), 0.0) for k in range(40)])
        self.assertEqual(tuple(TR._sharp_point(mid, 20)), (20.0, 0.0))

    def test_too_short_stays_there(self):
        mid = np.array([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)])
        self.assertEqual(tuple(TR._sharp_point(mid, 1)), (1.0, 0.0))


class TestApproximateFix(unittest.TestCase):
    """Approximer sautait l'arrivée des courbes presque droites : le contour pouvait s'écarter de plusieurs mm."""

    def test_almost_straight_curves_keep_their_ends(self):
        from vectordrive.core import fitcurve, geom
        side = 100.0
        pts = [(0.0, 0.0), (side, 0.0), (side, side), (0.0, side)]
        segs = []
        for k in range(4):
            a, b = pts[k], pts[(k + 1) % 4]
            segs.append(geom.Cubic(a, (a[0] + (b[0] - a[0]) / 3, a[1] + (b[1] - a[1]) / 3),
                                   (a[0] + 2 * (b[0] - a[0]) / 3, a[1] + 2 * (b[1] - a[1]) / 3), b))
        c = fitcurve.approximate_contour(geom.Contour(segs, True), 0.05)
        self.assertAlmostEqual(abs(c.signed_area()), side * side, delta=1.0)
        starts = [s.start for s in c.segments]
        for q in pts:
            self.assertLess(min(math.dist(q, x) for x in starts), 0.1, q)

    def test_curves_still_followed(self):
        from vectordrive.core import fitcurve, geom
        c = fitcurve.approximate_contour(geom.circle((0.0, 0.0), 50.0), 0.02)
        self.assertAlmostEqual(abs(c.signed_area()), math.pi * 2500, delta=5.0)


class TestQImage(unittest.TestCase):
    def test_colors_and_alpha(self):
        img = QImage(4, 2, QImage.Format.Format_ARGB32)
        img.fill(QColor(0, 0, 0, 0))
        img.setPixelColor(1, 0, QColor(255, 0, 0))
        rgb, real = qimage_rgb(img)
        self.assertEqual(rgb.shape, (2, 4, 3))
        self.assertEqual(tuple(rgb[0, 1]), (1.0, 0.0, 0.0))
        self.assertTrue(real[0, 1])
        self.assertFalse(real[1, 1])

    def test_reduced(self):
        img = QImage(1000, 500, QImage.Format.Format_RGB32)
        img.fill(QColor('white'))
        self.assertEqual(qimage_rgb(img, max_side=100)[0].shape, (50, 100, 3))

    def test_odd_stride(self):
        img = QImage(7, 3, QImage.Format.Format_RGB888)
        img.fill(QColor(10, 20, 30))
        rgb, real = qimage_rgb(img)
        self.assertEqual(rgb.shape, (3, 7, 3))
        self.assertAlmostEqual(rgb[2, 6, 2], 30 / 255)
        self.assertTrue(real.all())


class Fake:
    """Le dialogue de paramètres, répondu d'avance."""
    answers = {}

    def __init__(self, _parent, _title, params, labels, *a, **k):
        Fake.labels = labels
        self.params = params
        for key, v in Fake.answers.items():
            setattr(self.params, key, v)

    def exec(self):
        return True

    def result_params(self):
        return self.params


class TestWindow(unittest.TestCase):
    def setUp(self):
        self.w = MainWindow()
        self.saved = dialogs.ParamsDialog, QFileDialog.getOpenFileName
        dialogs.ParamsDialog = Fake
        self.w.settings.remove('vectorisation')

    def tearDown(self):
        dialogs.ParamsDialog, QFileDialog.getOpenFileName = self.saved[0], staticmethod(self.saved[1])
        self.w.settings.remove('vectorisation')          # les essais suivants repartent des réglages d'usine
        self.w.modified = False
        self.w.close()

    def run_on_file(self, **answers):
        Fake.answers = answers
        with tempfile.TemporaryDirectory() as tmp:
            f = pathlib.Path(tmp) / 'logo.png'
            logo().save(str(f))
            QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (str(f), ''))
            self.w.trace_image()

    def test_a_group_of_filled_shapes_one_tool_each(self):
        self.run_on_file(colors=4, width=150.0)
        g = self.w.canvas.selection[0]
        self.assertIsInstance(g, Group)
        self.assertEqual(len(g.children), 3)
        tools = [s.tool for s in g.children]
        self.assertEqual(len(set(tools)), 3)
        doc = self.w.canvas.doc
        for s in g.children:
            self.assertIsInstance(s, Shape)
            self.assertTrue(s.filled)
            self.assertTrue(close(doc.tool_color(s.tool), s.name, tol=2), (doc.tool_color(s.tool), s.name))

    def test_size_asked_is_kept(self):
        self.run_on_file(colors=4, width=150.0)
        g = self.w.canvas.selection[0]
        bb = g.bbox()
        self.assertAlmostEqual(bb[2] - bb[0], 150.0 * (270 - 20) / 300, delta=0.5)

    def test_y_goes_up(self):
        self.run_on_file(colors=4, width=150.0)
        g = self.w.canvas.selection[0]
        green = next(s for s in g.children if close(s.name, GREEN))
        red = next(s for s in g.children if close(s.name, RED))
        self.assertLess(green.bbox()[1], red.bbox()[1])              # le trait vert est en bas de l'image

    def test_undo_removes_at_once(self):
        before = len(self.w.canvas.doc.layers[0].items)
        self.run_on_file(colors=4, width=100.0)
        self.w.undo()
        self.assertEqual(len(self.w.canvas.doc.layers[0].items), before)

    def test_existing_work_keeps_its_color(self):
        doc = self.w.canvas.doc
        keep = doc.tool_color(0)
        from vectordrive.core import geom
        doc.add(Shape(path=geom.Path([geom.rect(0, 0, 5, 5)]), tool=0))
        self.run_on_file(colors=4, width=100.0)
        self.assertEqual(doc.tool_color(0), keep)

    def test_one_color_is_the_old_behaviour(self):
        self.run_on_file(colors=1, width=100.0)
        s = self.w.canvas.selection[0]
        self.assertIsInstance(s, Shape)
        self.assertFalse(s.filled)

    def test_centerline_stays_single(self):
        self.run_on_file(colors=4, centerline=True, width=100.0)
        self.assertIsInstance(self.w.canvas.selection[0], Shape)

    def test_remembered(self):
        self.run_on_file(colors=5, keep_background=True, width=100.0)
        self.assertEqual(int(self.w.settings.value('vectorisation/couleurs')), 5)
        self.assertIn(self.w.settings.value('vectorisation/fond'), (True, 'true'))

    def test_image_in_the_drawing(self):
        from PySide6.QtCore import QBuffer, QIODevice

        from vectordrive.core.geom import Affine
        b = QBuffer()
        b.open(QIODevice.OpenModeFlag.WriteOnly)
        logo().save(b, 'PNG')
        im = Image(data=bytes(b.data()), fmt='png', matrix=Affine(90, 0, 0, -60, 10, 70))
        self.w.canvas.doc.add(im)
        self.w.canvas.invalidate()
        self.w.canvas.select([im])
        Fake.answers = {'colors': 4}
        self.w.trace_image()
        g = self.w.canvas.selection[0]
        self.assertIsInstance(g, Group)
        bb = g.bbox()
        self.assertAlmostEqual(bb[0], 10 + 90 * 20 / 300, delta=0.3)
        self.assertAlmostEqual(bb[3], 70 - 60 * 40 / 200, delta=0.3)

    def test_arcs_option(self):
        from vectordrive.core.geom import Cubic
        self.run_on_file(colors=4, arcs=True, width=150.0)
        g = self.w.canvas.selection[0]
        for s in g.children:
            for c in s.path.contours:
                self.assertFalse(any(isinstance(x, Cubic) for x in c.segments))


if __name__ == '__main__':
    unittest.main()
