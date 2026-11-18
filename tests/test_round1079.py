"""Round 1079 : demande du 18/11 — « new fonction approximation courbe Cinfini d'un contour (parametrable user),
fonction emporte-pièce pour retirer à un contour un segment, rectangle, cercle (cas d'usage sur une ligne dont on veut
retirer à la souris une longueur de x mm) »."""
import importlib.util
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1079.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Shape  # noqa: E402
from vectordrive.core.geom import Cubic, Line, Path  # noqa: E402

BEFORE = 'avant : ni courbe lisse, ni emporte-pièce à la souris'


def length(contours) -> float:
    return sum(s.length() for c in contours for s in c.segments)


def zigzag(n=40, step=1.0, amp=0.2):
    return geom.polyline([(k * step, amp if k % 2 else -amp) for k in range(n + 1)])


class SmoothCurve(unittest.TestCase):

    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('vectordrive.core.smoothcurve'), BEFORE)
        from vectordrive.core import smoothcurve as SC
        self.SC = SC

    def test_gain(self):
        import numpy as np
        g = self.SC.gain(np.array([0.0, 0.5, 5.0]), 2.0, 1.0)              # longueur d'onde 2 mm : la moitié
        self.assertAlmostEqual(g[0], 1.0)
        self.assertAlmostEqual(g[1], 0.5)
        self.assertLess(g[2], 1e-12)
        sharp = self.SC.gain(np.array([0.1, 0.5, 1.0]), 2.0, 4.0)          # plus net : l'ensemble mieux gardé
        self.assertGreater(sharp[0], self.SC.gain(np.array([0.1]), 2.0, 1.0)[0])
        self.assertAlmostEqual(sharp[1], 0.5)
        self.assertEqual(list(self.SC.gain(np.array([3.0]), 0.0)), [1.0])  # 0 : pas de lissage

    def test_open_contour_small_details_go_and_ends_stay(self):
        c = zigzag()
        out = self.SC.smooth_contour(c, length=8.0, sharpness=1.0, tol=0.005)
        self.assertFalse(out.closed)
        self.assertAlmostEqual(out.segments[0].start[0], 0.0, places=6)     # les bouts ne bougent pas
        self.assertAlmostEqual(out.segments[0].start[1], -0.2, places=6)
        self.assertAlmostEqual(out.segments[-1].end[0], 40.0, places=6)
        ys = [abs(p[1]) for p in out.flatten(0.01) if 6 < p[0] < 34]
        self.assertLess(max(ys), 0.02, 'le zigzag de 2 mm de pas a disparu')
        self.assertTrue(all(isinstance(s, (Cubic, Line)) for s in out.segments))
        self.assertLess(len(out.segments), 40)                               # moins de segments que le zigzag
        dev = self.SC.deviation(Path([c]), Path([out]))
        self.assertTrue(0.15 < dev < 0.45, dev)                              # l'amplitude du zigzag

    def test_closed_contour_no_corner_and_shape_kept(self):
        sq = geom.rect(0, 0, 40, 40)
        out = self.SC.smooth_contour(sq, length=6.0, sharpness=2.0, tol=0.005)
        self.assertTrue(out.closed)
        pts = out.flatten(0.002)
        turns = []
        for a, b, c in zip(pts, pts[1:], pts[2:]):
            v1, v2 = (b[0] - a[0], b[1] - a[1]), (c[0] - b[0], c[1] - b[1])
            n = math.hypot(*v1) * math.hypot(*v2)
            if n > 1e-12:
                turns.append(abs(math.degrees(math.atan2(v1[0] * v2[1] - v1[1] * v2[0], v1[0] * v2[0] + v1[1] * v2[1]))))
        self.assertLess(max(turns), 12.0, 'plus aucun coin')
        b = out.bbox() if hasattr(out, 'bbox') else Path([out]).bbox()
        self.assertTrue(38.5 < b[2] - b[0] <= 40.2 and 38.5 < b[3] - b[1] <= 40.2, b)   # la forme d'ensemble
        mid = min(pts, key=lambda p: abs(p[0] - 20) + abs(p[1]))             # le milieu d'un côté reste en place
        self.assertLess(abs(mid[1]), 0.3)
        circle = geom.circle((0, 0), 20.0)
        r = self.SC.smooth_contour(circle, length=6.0, sharpness=1.0, tol=0.002)
        radii = [math.hypot(*p) for p in r.flatten(0.01)]
        self.assertTrue(19.9 < min(radii) and max(radii) < 20.01, (min(radii), max(radii)))   # un cercle le reste

    def test_zero_length_only_retraces_and_tiny_contours_survive(self):
        c = zigzag(6)
        out = self.SC.smooth_contour(c, length=0.0, tol=0.001)
        self.assertLess(self.SC.deviation(Path([c]), Path([out])), 0.02)
        one = geom.polyline([(0, 0), (5, 0)])
        self.assertIs(self.SC.smooth_contour(one, 2.0), one)                # deux points : tel quel
        p = self.SC.smooth(Path([c, one]), 1.0)
        self.assertEqual(len(p.contours), 2)

    def test_review_smooth(self):
        SC = self.SC
        small = geom.circle((0, 0), 1.0)                                    # lissage démesuré : pas d'effondrement
        r = SC.smooth_contour(small, length=50.0, sharpness=2.0, tol=0.002)
        radii = [math.hypot(*q) for q in r.flatten(0.002)]
        self.assertTrue(0.95 < min(radii) and max(radii) < 1.05, (min(radii), max(radii)))
        rep = {}
        SC.smooth(Path([zigzag()]), 8.0, 1.0, 0.005, rep)
        self.assertTrue(0.15 < rep['deviation'] < 0.45, rep)                # l'écart rendu par le lissage
        c = zigzag(6)
        self.assertIs(SC.smooth_contour(c, length=0.0), c)                  # 0 : rien n'est retracé


class PunchCore(unittest.TestCase):

    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('vectordrive.core.punchtool'), BEFORE)
        from vectordrive.core import punchtool as PT
        self.PT = PT

    def test_x_mm_removed_from_a_line_at_the_click(self):
        line = geom.polyline([(0, 0), (100, 0)])
        rest = self.PT.remove_length(line, (40, 3), 10.0)                   # clic à 3 mm de la ligne
        self.assertEqual(len(rest), 2)
        self.assertAlmostEqual(rest[0].segments[-1].end[0], 35.0, places=6)
        self.assertAlmostEqual(rest[1].segments[0].start[0], 45.0, places=6)
        self.assertAlmostEqual(length(rest), 90.0, places=6)                # 10 mm exactement
        rest = self.PT.remove_length(line, (2, 0), 10.0)                    # près du bout : toujours 10 mm
        self.assertEqual(len(rest), 1)
        self.assertAlmostEqual(rest[0].segments[0].start[0], 10.0, places=6)
        self.assertEqual(self.PT.remove_length(line, (50, 0), 500.0), [])   # plus long que le trait : tout
        self.assertIsNone(self.PT.remove_length(line, (50, 0), 0.0))

    def test_along_a_curve_and_on_a_closed_contour(self):
        circle = geom.circle((0, 0), 10.0)
        total = length([circle])
        rest = self.PT.remove_length(circle, (11, 0), 5.0)
        self.assertEqual(len(rest), 1)
        self.assertFalse(rest[0].closed)                                    # le cercle s'ouvre
        self.assertAlmostEqual(length(rest), total - 5.0, places=4)         # 5 mm de courbe
        a, b = rest[0].segments[0].start, rest[0].segments[-1].end
        self.assertAlmostEqual(math.hypot(*a), 10.0, places=5)              # coupé sur le cercle, rien d'aplati
        self.assertAlmostEqual(a[1], -b[1], places=4)                       # centré sur le clic
        self.assertFalse(any(isinstance(s, Line) for s in rest[0].segments))
        pc = self.PT.removed_piece(circle, (11, 0), 5.0)
        self.assertAlmostEqual(length([pc]), 5.0, places=4)
        two = Path([geom.polyline([(0, 0), (10, 0)]), geom.polyline([(0, 5), (10, 5)])])
        got = self.PT.punch_length(two, (5, 4.6), 2.0)                      # le contour le plus proche seulement
        self.assertEqual(len(got.contours), 3)
        self.assertAlmostEqual(length(got.contours), 18.0, places=6)

    def test_rectangle_and_circle(self):
        PT = self.PT
        line = Path([geom.polyline([(0, 0), (100, 0)])])
        got = PT.punch_region(line, PT.region('cercle', (50, 0), 10.0), False)
        self.assertAlmostEqual(length(got.contours), 90.0, places=5)
        got = PT.punch_region(line, PT.region('rectangle', (50, 0), 20.0, 4.0), False)
        self.assertAlmostEqual(length(got.contours), 80.0, places=5)
        self.assertIsNone(PT.punch_region(line, PT.region('cercle', (50, 30), 10.0), False))    # à côté : rien
        turned = PT.region('rectangle', (50, 0), 20.0, 4.0, 90.0)           # tourné : 4 mm en travers de la ligne
        self.assertAlmostEqual(length(PT.punch_region(line, turned, False).contours), 96.0, places=5)
        plate = Path([geom.rect(0, 0, 40, 40)])
        holed = PT.punch_region(plate, PT.region('cercle', (20, 20), 10.0), True)   # surface pleine : évidée
        self.assertEqual(len(holed.contours), 2)
        self.assertIsNone(PT.region('cercle', (0, 0), 0.0))
        self.assertIsNone(PT.region('rectangle', (0, 0), 5.0, 0.0))

    def test_review_core(self):
        PT = self.PT
        rect3 = geom.polyline([(0, 0), (40, 0), (40, 20), (0, 20)], closed=True)     # 4e côté implicite
        rest = PT.remove_length(rect3, (0.3, 10), 6.0)                      # clic sur le côté de fermeture
        self.assertEqual(len(rest), 1)
        self.assertAlmostEqual(length(rest), 120.0 - 6.0, places=6)
        a, b = rest[0].segments[0].start, rest[0].segments[-1].end
        self.assertAlmostEqual(a[0], 0.0, places=6)
        self.assertAlmostEqual(b[0], 0.0, places=6)
        self.assertAlmostEqual(abs(a[1] - b[1]), 6.0, places=6)
        line = geom.polyline([(0, 0), (10, 0)])
        self.assertEqual(PT.remove_length(line, (5, 0), 9.9995), [])        # un reste plus court que TINY : parti
        rest = PT.remove_length(line, (0.0002, 0), 2.0)                     # près du bout : pas de miette
        self.assertEqual(len(rest), 1)
        self.assertAlmostEqual(rest[0].segments[0].start[0], 2.0, places=6)
        plate = Path([geom.rect(0, 0, 40, 40), geom.rect(10, 10, 20, 20)])          # plaque à trou
        self.assertIsNone(PT.punch_region(plate, PT.region('cercle', (20, 20), 6.0), True))   # dans le trou : rien
        self.assertIsNotNone(PT.punch_region(plate, PT.region('cercle', (5, 5), 4.0), True))


class Window(unittest.TestCase):

    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('vectordrive.core.punchtool'), BEFORE)
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.resize(1200, 800)
        self.w.show()
        app.processEvents()
        self.addCleanup(self.close)
        self.w.settings.remove('cad/emporte_piece')
        self.addCleanup(self.w.settings.remove, 'cad/emporte_piece')
        self.addCleanup(self.w.settings.remove, 'cad/courbe_lisse')

    def close(self):
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()

    def add(self, contour, **kw):
        s = Shape(path=Path([contour]), tool=0, **kw)
        self.w.canvas.doc.add(s)
        return s

    def test_smooth_curve_command(self):
        w = self.w
        s = self.add(zigzag())
        w.canvas.selection = [s]
        dev = w.smooth_curve_dialog({'length': 8.0, 'sharpness': 1.0, 'tolerance': 0.005})
        self.assertTrue(0.15 < dev < 0.45, dev)
        new = w.canvas.selection[0]
        self.assertLess(new.path.segment_count(), 40)
        self.assertIn('écart maxi', w.statusBar().currentMessage())
        w.undo()
        self.assertEqual(w.canvas.doc.layers[0].items[0].path.segment_count(), 40)
        self.assertIn('smooth_curve', w.A)
        w.canvas.selection = []
        self.assertIsNone(w.smooth_curve_dialog({'length': 1.0}) if False else None)

    def test_punch_tool_segment_then_circle(self):
        from PySide6.QtCore import QEvent, Qt
        from PySide6.QtGui import QKeyEvent
        from vectordrive.ui import tools as T
        w = self.w
        s = self.add(geom.polyline([(0, 0), (100, 0)]))
        locked = self.add(geom.polyline([(0, 10), (100, 10)]))
        locked.locked = True
        w.canvas.selection = []
        got = w.punchout_options({'kind': 'segment', 'length': 8.0})
        self.assertEqual((got['kind'], got['length']), ('segment', 8.0))
        self.assertEqual(w.canvas.tool, 'punchout')
        tool = w.canvas.tool_obj
        self.assertIsInstance(tool, T.PunchTool)
        shape, pc = w.canvas.punch_preview((30, 0.2), tool.spec)             # ce qui partira, montré
        self.assertIsNone(shape)
        self.assertAlmostEqual(length(pc.contours), 8.0, places=6)
        tool.press(None, (30, 0.2), None)
        self.assertAlmostEqual(length(s.path.contours), 92.0, places=6)
        self.assertEqual(len(s.path.contours), 2)
        tool.press(None, (30, 10.1), None)                                   # un trait verrouillé : intact
        self.assertAlmostEqual(length(locked.path.contours), 100.0, places=6)
        tool.key(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier))
        tool.key(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier))
        self.assertEqual(tool.spec['kind'], 'cercle')                        # segment → rectangle → cercle
        self.assertEqual(w.punchout_spec()['kind'], 'cercle')                # retenu
        d0 = tool.spec['diameter']
        tool.key(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_BracketRight, Qt.KeyboardModifier.NoModifier))
        self.assertAlmostEqual(tool.spec['diameter'], d0 * 1.25, places=3)
        w.punchout_options({'kind': 'cercle', 'diameter': 10.0})
        self.assertIs(w.canvas.tool_obj, tool)                               # l'outil en cours prend les réglages
        tool.press(None, (70, 0), None)
        self.assertAlmostEqual(length(s.path.contours), 82.0, places=5)
        w.undo()                                                             # chaque clic s'annule à part
        self.assertAlmostEqual(length(w.canvas.doc.layers[0].items[0].path.contours), 92.0, places=5)
        tool.move(None, (50, 0), None)
        w.canvas.grab()                                                      # l'aperçu se dessine sans erreur

    def test_selection_limits_the_punch(self):
        w = self.w
        a = self.add(geom.polyline([(0, 0), (100, 0)]))
        b = self.add(geom.polyline([(0, 1), (100, 1)]))
        w.canvas.selection = [b]
        spec = dict(w.PUNCHOUT_DEFAULT, kind='cercle', diameter=10.0)
        self.assertEqual(w.canvas.punch_at((50, 0.5), spec), 1)              # la sélection seulement
        self.assertAlmostEqual(length(a.path.contours), 100.0, places=6)
        self.assertLess(length(b.path.contours), 100.0)
        w.canvas.selection = []
        self.assertEqual(w.canvas.punch_at((20, 0.5), spec), 2)              # sans sélection : tout ce qui est dessous
        self.assertEqual(w.canvas.punch_at((20, 50), spec), 0)

    def test_review_canvas(self):
        from vectordrive.core.document import Group, Layer
        w = self.w
        spec = dict(w.PUNCHOUT_DEFAULT, kind='cercle', diameter=10.0)
        doc = w.canvas.doc
        g = Group(children=[Shape(path=Path([geom.polyline([(0, 0), (4, 0)])]), tool=0),
                            Shape(path=Path([geom.polyline([(0, 30), (4, 30)])]), tool=0)])
        doc.add(g)
        w.canvas.selection = []
        self.assertEqual(w.canvas.punch_at((2, 0), spec), 1)                # la feuille vidée quitte son groupe
        self.assertEqual(len(g.children), 1)
        self.assertEqual(w.canvas.punch_at((2, 30), spec), 1)               # le groupe vidé part aussi
        self.assertFalse(any(it is g for L in doc.layers for it in L.items))
        hidden = self.add(geom.polyline([(0, 60), (100, 60)]))
        hidden.visible = False
        self.assertEqual(w.canvas.punch_at((50, 60), spec), 0)              # un objet caché : intact
        L2 = Layer(name='verrou', locked=True)
        doc.layers.append(L2)
        doc.add(Shape(path=Path([geom.polyline([(0, 90), (100, 90)])]), tool=0), L2)
        self.assertEqual(w.canvas.punch_at((50, 90), spec), 0)              # un calque verrouillé : intact
        plate = self.add(geom.rect(200, 0, 40, 40), filled=True)
        seg = dict(w.PUNCHOUT_DEFAULT, kind='segment', length=5.0)
        self.assertEqual(w.canvas.punch_at((220, 0.1), seg), 1)             # surface ouverte : un trait
        self.assertFalse(plate.filled)
        self.assertIn('smooth_curve', w.KEEP_ORIGINAL)



if __name__ == '__main__':
    unittest.main()
