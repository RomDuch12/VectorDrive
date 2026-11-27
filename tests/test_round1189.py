"""Round « points minimaux » (demande du 27/11) : « Fonctions décalage avec congés et autres et lissages minimiser le
nombre de point en courbe et utiliser les points hors courbe ». Les tracés produits par Décaler, les booléens, le
Pathfinder, « Supprimer les intersections » et la Courbe lisse ont le moins de nœuds possible : droites, arcs exacts,
Bézier — à l'écart toléré (F10 › Dessin) ; interrupteur coupé : comme avant."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'rlisse.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

import tests  # noqa: E402,F401
import numpy as np  # noqa: E402
import shapely  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from vectordrive.core import geom, parallel, pathops  # noqa: E402
from vectordrive.core.geom import Conic, Contour, Cubic, Line, Path  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : les tracés produits gardaient des nœuds rapprochés (16 Bézier par quart de cercle, polygones)'
TOL = 0.01


def cf():
    from vectordrive.core import curvefit                # absent de l'arbre d'avant : l'essai échoue
    return curvefit


def nodes(p: Path) -> int:
    return sum(len(c.nodes()) for c in p.contours)


def offset(p: Path, d: float, join: str = 'round') -> Path:
    out, _e, _a = parallel.offset_job(p, [d], join)
    return out[0]


def deviation(a: Path, b: Path) -> float:
    """Écart mesuré par échantillonnage serré (1 µm), dans les deux sens, contour par contour."""
    worst = 0.0
    for ca, cb in zip(a.contours, b.contours):
        pa, pb = np.asarray(ca.flatten(1e-4)), np.asarray(cb.flatten(1e-4))
        if ca.closed:
            pa, pb = np.vstack([pa, pa[:1]]), np.vstack([pb, pb[:1]])
        la, lb = shapely.LineString(pa), shapely.LineString(pb)
        worst = max(worst, float(shapely.distance(lb, shapely.points(pa)).max()),
                    float(shapely.distance(la, shapely.points(pb)).max()))
    return worst


def arcs(c: Contour) -> list:
    return [s.circle_params() for s in c.segments if isinstance(s, Conic)]


S_SHAPE = Path([Contour([Cubic((0, 0), (10, 20), (20, -20), (30, 0)), Cubic((30, 0), (40, 20), (50, 0), (60, 10)),
                         Line((60, 10), (60, -10)), Line((60, -10), (0, -10)), Line((0, -10), (0, 0))], True)])


class Fit(unittest.TestCase):

    def test_offset_circle_four_arcs(self):
        raw = offset(Path([geom.circle((0, 0), 10)]), 1.0)
        self.assertGreater(nodes(raw), 16)                                   # le moteur coupe le cercle en morceaux
        got = cf().minimal_path(raw, TOL)
        self.assertLessEqual(nodes(got), 4, BEFORE)
        c = got.contours[0]
        self.assertTrue(c.closed)
        self.assertTrue(all(isinstance(s, Conic) for s in c.segments))      # arcs exacts (points hors courbe)
        for center, r, _a0, _sw in arcs(c):
            self.assertAlmostEqual(r, 11.0, places=4)
            self.assertLess(math.hypot(*center), 1e-4)
        self.assertLess(deviation(raw, got), TOL)

    def test_offset_rounded_rectangle_eight_nodes(self):
        for d, r in ((1.0, 4.0), (-1.0, 2.0)):
            raw = offset(Path([geom.rect(0, 0, 40, 20, 3)]), d)
            got = cf().minimal_path(raw, TOL)
            c = got.contours[0]
            self.assertEqual(nodes(got), 8, BEFORE)                          # 4 droites + 4 arcs
            self.assertEqual(sum(isinstance(s, Line) for s in c.segments), 4)
            self.assertEqual(sorted(round(a[1], 4) for a in arcs(c)), [r] * 4)
            for s in c.segments:                                             # raccords tangents (G1)
                if isinstance(s, Line):
                    i = c.segments.index(s)
                    nxt = c.segments[(i + 1) % len(c.segments)]
                    v = (s.p1[0] - s.p0[0], s.p1[1] - s.p0[1])
                    t = (nxt.p1[0] - nxt.p0[0], nxt.p1[1] - nxt.p0[1])
                    self.assertLess(abs(v[0] * t[1] - v[1] * t[0]) / math.hypot(*v) / math.hypot(*t), 1e-6)
            self.assertLess(deviation(raw, got), TOL)

    def test_sharp_rectangle_rounded_outside_sharp_inside(self):
        sq = Path([geom.rect(0, 0, 40, 20)])
        got = cf().minimal_path(offset(sq, 1.0), TOL)
        self.assertEqual(nodes(got), 8, BEFORE)
        self.assertEqual(sorted(round(a[1], 4) for a in arcs(got.contours[0])), [1.0] * 4)
        inner = cf().minimal_path(offset(sq, -1.0), TOL)
        corners = [(1.0, 1.0), (39.0, 1.0), (39.0, 19.0), (1.0, 19.0)]
        self.assertEqual(sorted(inner.contours[0].nodes()), sorted(corners))

    def test_sharp_corners_kept(self):
        two = pathops.boolean(Path([geom.circle((0, 0), 10)]), Path([geom.circle((12, 0), 8)]), 'union')
        got = cf().minimal_path(two, TOL)
        self.assertLess(nodes(got), 10, BEFORE)
        pts = got.contours[0].nodes()
        y = math.sqrt(100 - 7.5 ** 2)                                        # les deux croisements des cercles
        for q in ((7.5, y), (7.5, -y)):
            self.assertLess(min(math.hypot(p[0] - q[0], p[1] - q[1]) for p in pts), 1e-6)
        self.assertEqual(sorted({round(a[1], 3) for a in arcs(got.contours[0])}), [8.0, 10.0])
        self.assertTrue(all(isinstance(s, Conic) for s in got.contours[0].segments))
        self.assertLess(deviation(two, got), TOL)
        # un coin vif d'une forme qui en a : il reste un nœud
        inner = cf().minimal_path(offset(S_SHAPE, -1.0), TOL)
        for q in ((59.0, -9.0), (1.0, -9.0)):
            self.assertLess(min(math.hypot(p[0] - q[0], p[1] - q[1]) for p in inner.contours[0].nodes()), 1e-6)

    def test_tolerance_respected_curves(self):
        for p in (Path([geom.ellipse((0, 0), 20, 8)]), S_SHAPE):
            raw = offset(p, 1.0)
            fine = cf().minimal_path(raw, TOL)
            self.assertLess(nodes(fine), nodes(raw) / 3, BEFORE)
            self.assertLessEqual(deviation(raw, fine), TOL)
            coarse = cf().minimal_path(raw, 0.1)
            self.assertLessEqual(nodes(coarse), nodes(fine))
            self.assertLessEqual(deviation(raw, coarse), 0.1)

    def test_open_contour(self):
        c = Contour([Cubic((0, 0), (10, 20), (20, -20), (30, 0)), Line((30, 0), (40, 0))], False)
        raw = offset(Path([c]), 1.0)
        got = cf().minimal_path(raw, TOL)
        k, r = got.contours[0], raw.contours[0]
        self.assertFalse(k.closed)
        self.assertLess(len(k.segments), len(r.segments) / 2, BEFORE)
        self.assertEqual(k.start, r.start)                                  # bouts gardés
        self.assertEqual(k.end, r.end)
        self.assertIsInstance(k.segments[-1], Line)                         # la droite reste une droite
        self.assertLessEqual(deviation(raw, got), TOL)

    def test_dense_polyline_and_polygon(self):
        ring = [(10 * math.cos(i / 100 * 2 * math.pi), 10 * math.sin(i / 100 * 2 * math.pi)) for i in range(100)]
        got = cf().minimal_path(Path([geom.polyline(ring, closed=True)]), TOL)
        self.assertEqual(nodes(got), 4, BEFORE)                              # un cercle, sans nœud de couture de plus
        self.assertTrue(got.contours[0].closed)
        hexa = Path([geom.polygon((0, 0), 10, 6)])
        self.assertIs(cf().minimal_path(hexa, TOL), hexa)                    # rien à gagner : tel quel
        exact = Path([geom.rect(0, 0, 40, 20, 3)])                           # déjà minimal (congés exacts)
        self.assertIs(cf().minimal_path(exact, TOL), exact)

    def test_contours_refitted_never_cross(self):
        outer, hole = geom.circle((0, 0), 10), geom.circle((0, 0), 9)
        moved = geom.ellipse((1.5, 0), 10, 10)                               # un refait qui croiserait le trou
        got = cf()._kept_apart([outer, hole], [moved, hole], TOL)
        self.assertIs(got[0], outer, BEFORE)                                 # repris tel quel
        self.assertIs(cf()._kept_apart([outer, hole], [moved, hole], TOL)[1], hole)
        far = geom.ellipse((0.0, 0.0), 10.002, 10.002)                       # sans croisement : gardé
        self.assertIs(cf()._kept_apart([outer, hole], [far, hole], TOL)[0], far)

    def test_micro_segment_is_not_a_corner(self):
        arc = geom.arc_conics((0, 0), 10, 10, 0, 90)
        a, b = arc[0].split()
        speck = Line(a.end, (a.end[0] + 1e-4, a.end[1] - 1e-4))           # direction de hasard, 0,14 µm
        c = Contour([a, speck, Conic(speck.end, b.p1, b.p2, b.w)], False)
        self.assertEqual(cf()._corners(c.segments, False, cf().CORNER_DEG, TOL), [], BEFORE)

    def test_smooth_reports_true_deviation(self):
        from vectordrive.core import smoothcurve as SC
        sq = Path([geom.rect(0, 0, 40, 20)])
        report: dict = {}
        got = cf().smooth(sq, 2.0, 1.0, 0.01, 0.01, report)
        self.assertLess(got.segment_count(), 20, BEFORE)
        self.assertLessEqual(SC.deviation(sq, got, 0.01), report['deviation'] + 1e-9)
        self.assertEqual(cf().smooth(sq, 2.0, 1.0, 0.01, 0.0).segment_count(), SC.smooth(sq, 2.0).segment_count())

    def test_switch_off_keeps_paths(self):
        raw = offset(Path([geom.circle((0, 0), 10)]), 1.0)
        out = cf().minimal_paths([raw], 0.0)
        self.assertIs(out[0], raw)
        self.assertEqual(cf().minimal_pairs([(raw, 3)], 0.0), [(raw, 3)])

    def test_cam_accepts_minimal_paths(self):
        from vectordrive.cam import model, strategies
        from vectordrive.core.document import Document, Plate, Shape
        doc = Document()
        doc.plate = Plate(width=100.0, height=60.0, thickness=5.0)
        path = cf().minimal_path(offset(Path([geom.rect(20, 10, 40, 20, 3)]), 1.0), TOL)
        self.assertTrue(any(isinstance(s, Conic) for c in path.contours for s in c.segments))
        sh = Shape(path=path, tool=0)
        doc.add(sh)
        s = model.CamSetup()
        t = model.CamTool(name='F2', diameter=2.0, number=1, cut_length=10, step_down=0.5, stepover=0.4)
        s.tools = [t]
        s.operations = [model.Operation(name='C', kind='contour', tool_id=t.id, items=[sh.id], depth=0.5)]
        tp = strategies.compute(doc, s, s.operations[0])
        self.assertTrue(tp.moves)


class Window(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.close()
        cls.win.deleteLater()
        app.processEvents()

    def setUp(self):
        from vectordrive.core.document import Layer
        self.doc = self.win.canvas.doc
        self.layer = Layer(name='Plan 1')
        self.doc.layers[:] = [self.layer]
        self.doc.active = self.layer.id
        self.win._undo.clear()
        for k in ('dessin/points_minimaux', 'dessin/points_tolerance', 'decalage/distance', 'decalage/jonction',
                  'decalage/garder', 'decalage/dernier', 'decalage/reunir'):
            self.addCleanup(self.win.settings.remove, k)

    def put(self, *paths):
        from vectordrive.core.document import Shape
        items = [Shape(path=p, tool=0) for p in paths]
        self.layer.items[:] = items
        self.win.canvas.select(items)
        return items

    def shapes(self):
        return [it for L in self.doc.layers for it in L.items]

    def test_options(self):
        from vectordrive.ui import options
        self.assertIn('dessin/points_minimaux', options.BY_KEY, BEFORE)
        self.assertTrue(options.BY_KEY['dessin/points_minimaux'].default)   # activé d'office
        self.assertEqual(options.BY_KEY['dessin/points_tolerance'].default, 0.01)
        self.assertEqual(self.win.points_tolerance(), 0.01)
        self.win.settings.setValue('dessin/points_minimaux', False)
        self.assertEqual(self.win.points_tolerance(), 0.0)

    def offset_circle(self):
        self.put(Path([geom.circle((0, 0), 10)]))
        self.win.offset_selection({'distance': 1.0, 'join': 'round', 'count': 1, 'keep': False, 'last_only': False,
                                   'union': True})
        return self.shapes()

    def test_offset_command_and_undo(self):
        got = self.offset_circle()
        self.assertEqual(len(got), 1)
        self.assertEqual(nodes(got[0].path), 4, BEFORE)
        self.assertTrue(all(isinstance(s, Conic) for s in got[0].path.contours[0].segments))
        self.win.undo()                                                      # Ctrl+Z : le cercle d'origine
        back = self.shapes()
        self.assertEqual(len(back), 1)
        self.assertAlmostEqual(back[0].path.bbox()[2], 10.0, places=9)

    def test_offset_switch_off_as_before(self):
        self.win.settings.setValue('dessin/points_minimaux', False)
        self.assertEqual(self.win.points_tolerance(), 0.0, BEFORE)          # l'interrupteur, coupé
        got = self.offset_circle()
        ref = offset(Path([geom.circle((0, 0), 10)]), 1.0)
        self.assertEqual(got[0].path.contours, ref.contours)                # comme avant
        self.assertGreater(nodes(got[0].path), 16)

    def test_boolean_union(self):
        self.put(Path([geom.circle((0, 0), 10)]), Path([geom.circle((12, 0), 8)]))
        self.win.boolean('union')
        got = self.shapes()
        self.assertEqual(len(got), 1)
        self.assertLess(nodes(got[0].path), 10, BEFORE)

    def test_intersections_union(self):
        from vectordrive.core import intersect as I
        items = self.put(Path([geom.circle((0, 0), 10)]), Path([geom.circle((12, 0), 8)]))
        self.win.apply_intersections(I.find(items), 'union', 0.0)        # Intersections › Réunion
        got = self.shapes()
        self.assertEqual(len(got), 1)
        self.assertLess(nodes(got[0].path), 10, BEFORE)

    def test_shape_builder_untouched_click_does_nothing(self):
        self.put(Path([geom.circle((0, 0), 10)]), Path([geom.circle((12, 0), 8)]))
        from unittest import mock
        from vectordrive.core import curvefit
        with mock.patch.object(curvefit, 'minimal_pairs', side_effect=AssertionError('calcul pour rien')):
            self.assertEqual(self.win.shape_build([(50.0, 50.0), (60.0, 60.0)]), 0)   # le geste ne touche rien
        self.assertGreater(self.win.shape_build([(-5.0, 0.0), (5.0, 0.0)]), 0, BEFORE)
        self.assertTrue(all(nodes(x.path) < 10 for x in self.shapes()))

    def test_pathfinder_merge(self):
        self.put(Path([geom.rect(0, 0, 40, 20, 3)]), Path([geom.circle((40, 10), 6)]))
        new = self.win.pathfinder('merge')
        self.assertEqual(len(new), 1)
        self.assertLess(nodes(new[0].path), 20, BEFORE)                      # au lieu de près de 200 sommets
        self.assertTrue(any(isinstance(s, Conic) for c in new[0].path.contours for s in c.segments))

    def test_smooth_curve(self):
        src = Path([geom.rect(0, 0, 40, 20)])
        self.put(src)
        worst = self.win._smooth_selection({'length': 2.0, 'sharpness': 1.0, 'tolerance': 0.01})
        got = self.shapes()[0].path
        self.assertLess(got.segment_count(), 20, BEFORE)                     # la B-spline lisse en avait 180
        self.assertIsNotNone(worst)
        from vectordrive.core import smoothcurve as SC
        self.assertLessEqual(SC.deviation(src, got, 0.01), worst + 1e-9)    # l'écart annoncé est le vrai


if __name__ == '__main__':
    unittest.main()
