"""Round 1170 : « Decaler (A) un contour ouvert : meme comportement que TE, créé un contour ouvert decalé partout de la
même distance; ». Un contour ouvert décalé donne un contour ouvert parallèle, d'un seul côté (+ : à droite du sens
de tracé, − : à gauche), à la même distance partout ; les fermés ne changent pas."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'roffs.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

import numpy as np  # noqa: E402
import shapely  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from vectordrive.core import geom, parallel  # noqa: E402
from vectordrive.core.geom import Conic, Contour, Cubic, Line, Path  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : un contour ouvert décalé devenait le contour fermé de son trait'
KEYS = ('decalage/distance', 'decalage/jonction', 'decalage/garder', 'decalage/dernier', 'decalage/reunir')


def offsets(c: Contour, d: float, join: str = 'round') -> list:
    """Les contours rendus par Décaler (`offset_job`) pour un seul contour à une distance."""
    out, _exact, _approx = parallel.offset_job(Path([c]), [d], join)
    return [k for p in out for k in p.contours]


def samples(c: Contour, per: int = 40) -> np.ndarray:
    return np.array([s.point(t) for s in c.segments for t in np.linspace(0.0, 1.0, per)], float)


def distances(res: Contour, orig: Contour) -> np.ndarray:
    """Distances (échantillonnées) de la parallèle au tracé d'origine, aplati à 1 µm."""
    line = shapely.LineString(orig.flatten(1e-6))
    pts = samples(res)
    return shapely.distance(line, shapely.points(pts[:, 0], pts[:, 1]))


def near(p, q, eps=1e-6):
    return math.hypot(p[0] - q[0], p[1] - q[1]) < eps


class OpenOffset(unittest.TestCase):

    def one_open(self, c, d, join='round'):
        res = offsets(c, d, join)
        self.assertEqual(len(res), 1, BEFORE)
        self.assertFalse(res[0].closed, BEFORE)
        return res[0]

    def assertConstant(self, res, orig, d, eps=1e-3):
        dd = distances(res, orig)
        self.assertLess(float(np.max(np.abs(dd - abs(d)))), eps)

    def test_line_both_sides(self):
        c = Contour([Line((0, 0), (20, 0))], False)
        right = self.one_open(c, 2.0)                    # + : à droite du sens de tracé (vers le bas, Y vers le haut)
        self.assertTrue(near(right.start, (0, -2)) and near(right.end, (20, -2)), (right.start, right.end))
        self.assertConstant(right, c, 2.0)
        left = self.one_open(c, -2.0)
        self.assertTrue(near(left.start, (0, 2)) and near(left.end, (20, 2)))   # bouts perpendiculaires : sans bouchon
        self.assertConstant(left, c, 2.0)

    def test_l_polyline_round_and_sharp(self):
        c = geom.polyline([(0, 0), (20, 0), (20, 15)])
        out = self.one_open(c, 2.0)                       # autour du coin : arc exact
        self.assertTrue(near(out.start, (0, -2)) and near(out.end, (22, 15)))
        self.assertTrue(any(isinstance(s, Conic) for s in out.segments))
        self.assertConstant(out, c, 2.0)
        inner = self.one_open(c, -2.0)                    # dans le coin : les deux parallèles coupées à leur rencontre
        self.assertTrue(near(inner.start, (0, 2)) and near(inner.end, (18, 15)))
        self.assertIn((18.0, 2.0), [tuple(round(v, 9) for v in p) for p in inner.nodes()])
        self.assertConstant(inner, c, 2.0)
        vif = self.one_open(c, 2.0, 'miter')              # angle vif : la pointe, que des droites
        self.assertTrue(all(type(s) is Line for s in vif.segments))
        self.assertIn((22.0, -2.0), [tuple(round(v, 9) for v in p) for p in vif.nodes()])
        dd = distances(vif, c)
        self.assertGreater(float(dd.min()), 2.0 - 1e-6)
        self.assertLess(float(dd.max()), 2.0 * math.sqrt(2) + 1e-6)
        bevel = self.one_open(c, 2.0, 'bevel')            # chanfreiné : une droite d'un bout à l'autre du coin
        self.assertIn(((20.0, -2.0), (22.0, 0.0)),
                      [tuple(tuple(round(v, 9) for v in q) for q in (s.start, s.end)) for s in bevel.segments])
        self.assertTrue(all(type(s) is Line for s in bevel.segments))

    def test_arc_exact_both_sides(self):
        c = geom.arc((0, 0), 10.0, 0.0, 90.0)
        for d, r in ((3.0, 13.0), (-3.0, 7.0)):          # + : le grand rayon (extérieur), − : le petit
            out = self.one_open(c, d)
            pts = samples(out)
            self.assertLess(float(np.max(np.abs(np.hypot(pts[:, 0], pts[:, 1]) - r))), 1e-9)   # concentrique, exact
            self.assertTrue(near(out.start, (r, 0)) and near(out.end, (0, r)))
        self.assertEqual(offsets(c, -12.0), [])          # plus loin que le centre : rien

    def test_bezier_within_tolerance(self):
        c = Contour([Cubic((0, 0), (10, 10), (20, -10), (30, 0))], False)
        for d in (1.0, -1.0):
            out = self.one_open(c, d)
            self.assertConstant(out, c, 1.0)

    def test_tight_loop_is_cleaned_in_one_piece(self):
        # un coin arrondi de rayon 1, décalé de 3 de son côté intérieur : la boucle tombe, un seul contour
        segs = [Line((-20, 0), (0, 0))] + geom.arc((0, 1), 1.0, -90.0, 90.0).segments + [Line((1, 1), (1, 20))]
        c = Contour(segs, False)
        out = self.one_open(c, -3.0)
        self.assertConstant(out, c, 3.0)
        self.assertTrue(near(out.start, (-20, 3)) and near(out.end, (-2, 20)))
        self.assertConstant(self.one_open(c, 3.0), c, 3.0)   # de l'autre côté : arc concentrique de rayon 4
        # une Bézier au coude serré : la parallèle brute fait une queue d'aronde, ôtée sans couper le contour
        bend = Contour([Line((-10, 0), (0, 0)), Cubic((0, 0), (10, 0), (10, 0), (10, 10)), Line((10, 10), (10, 30))],
                       False)                            # rayon de courbure de 2,65 au coude
        raw = parallel.parallel_raw(bend, 4.0)                       # à gauche du sens : l'intérieur du coude
        from vectordrive.core.trim import self_crossings
        self.assertTrue(self_crossings(raw))                         # il y a bien une boucle à ôter
        out = self.one_open(bend, -4.0)
        self.assertConstant(out, bend, 4.0)
        self.assertTrue(near(out.start, (-10, 4)) and near(out.end, (6, 30)))

    def test_side_is_right_of_travel(self):
        diag = self.one_open(Contour([Line((0, 0), (5, 5))], False), math.sqrt(2))
        self.assertTrue(near(diag.start, (1, -1)) and near(diag.end, (6, 4)))               # + : à droite du sens
        rev = self.one_open(geom.arc((0, 0), 10.0, 90.0, -90.0), 3.0)                       # arc horaire : + dedans
        self.assertAlmostEqual(math.hypot(*rev.start), 7.0, places=9)
        self.assertTrue(near(rev.start, (0, 7)) and near(rev.end, (7, 0)))
        self.assertAlmostEqual(math.hypot(*self.one_open(geom.arc((0, 0), 10.0, 90.0, -90.0), -3.0).start), 13.0,
                               places=9)

    def test_almost_straight_does_not_flip(self):
        # presque droites, bossées d'un micron d'un côté ou de l'autre, loin de l'origine : toujours à droite
        for bump in (1e-6, -1e-6, 1e-3, -1e-3):
            c = geom.polyline([(1000, 1000), (1050, 1000 + bump), (1100, 1000)])
            out = self.one_open(c, 2.0)
            self.assertAlmostEqual(out.start[1], 998.0, places=3)
            self.assertAlmostEqual(out.end[1], 998.0, places=3)
            self.assertConstant(out, c, 2.0)

    def test_bevel_with_short_segments(self):
        # escalier aux marches de 1, chanfreiné à 3 : le chanfrein du premier coin, recoupé, reste un chanfrein
        c = geom.polyline([(0, 0), (10, 0), (10, 1), (11, 1), (11, 2), (21, 2)])
        res = offsets(c, 3.0, 'bevel')
        self.assertEqual(len(res), 1)                                             # d'un seul tenant
        self.assertTrue(all(not k.closed and all(type(s) is Line for s in k.segments) for k in res))
        dd = np.concatenate([distances(k, c) for k in res])
        self.assertGreater(float(dd.min()), 3.0 * math.cos(math.pi / 4) - 1e-3)   # au plus près : mi-chanfrein
        self.assertLess(float(dd.max()), 3.0 + 1e-3)
        self.assertLess(float(dd.min()), 2.9)                                     # le chanfrein est gardé
        self.assertTrue(near(res[0].start, (0, -3)) and near(res[-1].end, (21, -1)))

    def test_miter_beyond_limit_is_bevelled(self):
        c = geom.polyline([(0, 0), (20, 0), (0, 2)])    # angle aigu (≈ 5,7°) : la pointe irait à ≈ 20 mm
        out = self.one_open(c, 1.0, 'miter')
        self.assertTrue(all(type(s) is Line for s in out.segments))
        self.assertLess(out.bbox()[2], 20.5)                                     # chanfreinée à la limite
        self.assertGreater(float(distances(out, c).min()), 0.0)
        self.assertAlmostEqual(self.one_open(c, 1.0).bbox()[2], 21.0, places=6)   # arrondie : l'arc autour du coin

    def test_joined_ends_offset_like_closed(self):
        c = geom.polyline([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])       # ouvert, bouts confondus
        self.assertFalse(c.closed)
        res = offsets(c, 1.0)
        ref, _ok = parallel.offset_checked(Path([Contour(c.segments, True)]), 1.0)
        self.assertEqual(res, ref.contours)                                      # comme le carré fermé
        self.assertEqual(tuple(round(v, 6) for v in Path(res).bbox()), (-1, -1, 11, 11))

    def test_big_distance_on_an_l(self):
        c = geom.polyline([(0, 0), (20, 0), (20, 15)])
        out = self.one_open(c, 30.0)                                             # dehors : arc de rayon 30
        self.assertConstant(out, c, 30.0)
        self.assertTrue(near(out.start, (0, -30)) and near(out.end, (50, 15)))
        self.assertEqual(offsets(c, -30.0), [])                                  # dedans : plus rien à 30 du L

    def test_several_offsets(self):
        c = Contour([Line((0, 0), (20, 0))], False)
        out, _e, _a = parallel.offset_job(Path([c]), [1.0, 2.0, 3.0])
        self.assertEqual(len(out), 3)
        for p, d in zip(out, (1.0, 2.0, 3.0)):
            self.assertEqual(len(p.contours), 1)
            self.assertFalse(p.contours[0].closed)
            self.assertTrue(near(p.contours[0].start, (0, -d)) and near(p.contours[0].end, (20, -d)))

    def test_heavy_contour_and_errors_fall_back(self):
        from unittest import mock
        xs = np.linspace(0.0, 450.0, 4502)
        c = geom.polyline([(float(x), float(2 * math.sin(x / 5))) for x in xs])
        self.assertGreater(len(c.segments), parallel.EXACT_LIMIT)
        res = offsets(c, 0.5)                                                    # polyligne (shapely), sans erreur
        self.assertTrue(res)
        self.assertTrue(all(not k.closed for k in res))
        dd = np.concatenate([distances(k, c) for k in res])
        self.assertLess(float(np.max(np.abs(dd - 0.5))), 1e-3)
        line = Contour([Line((0, 0), (20, 0))], False)
        with mock.patch.object(parallel, 'parallel', side_effect=RuntimeError('essai')):
            out = self.one_open(line, 2.0)                                       # erreur du calcul exact : repli
            self.assertTrue(near(out.start, (0, -2)) and near(out.end, (20, -2)))
            with mock.patch('shapely.LineString', side_effect=RuntimeError('essai')):
                self.assertEqual(parallel.offset_job(Path([line]), [2.0]), ([], 0, 0))   # rien, sans exception

    def test_mixed_path_closed_part_unchanged(self):
        sq = geom.rect(0, 0, 10, 10)
        line = Contour([Line((0, 20), (10, 20))], False)
        out, _e, _a = parallel.offset_job(Path([sq, line]), [1.0, 2.0])
        self.assertEqual(len(out), 2)
        for p, d in zip(out, (1.0, 2.0)):
            ref, _ok = parallel.offset_checked(Path([sq]), d)
            self.assertEqual([k for k in p.contours if k.closed], ref.contours)   # les fermés : comme avant
            lines = [k for k in p.contours if not k.closed]
            self.assertEqual(len(lines), 1, BEFORE)
            self.assertTrue(near(lines[0].start, (0, 20 - d)) and near(lines[0].end, (10, 20 - d)))


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

    def setUp(self):
        from vectordrive.core.document import Layer, Plate
        self.doc = self.win.canvas.doc
        self.layer = Layer(name='Plan 1')
        self.doc.layers[:] = [self.layer]
        self.doc.active = self.layer.id
        self.doc.plate = Plate(width=300.0, height=200.0)
        self.win._undo.clear()

    def tearDown(self):
        for k in KEYS:
            self.win.settings.remove(k)

    def test_mixed_selection_union_and_undo(self):
        from vectordrive.core.document import Shape
        square = Shape(path=Path([geom.rect(0, 0, 10, 10)]), tool=0)
        line = Shape(path=Path([Contour([Line((-5, 12), (15, 12))], False)]), tool=0)   # son décalage croise le carré
        self.layer.items[:] = [square, line]
        self.win.canvas.select([square, line])
        self.win.offset_selection({'distance': 3.0, 'join': 'round', 'count': 1, 'keep': False, 'last_only': False,
                                   'union': True})
        items = list(self.layer.items)
        self.assertEqual(len(items), 2, BEFORE)          # pas réunis : le décalage d'un contour ouvert reste à part
        opened = [k for it in items for k in it.path.contours if not k.closed]
        self.assertEqual(len(opened), 1, BEFORE)
        self.assertTrue(near(opened[0].start, (-5, 9)) and near(opened[0].end, (15, 9)))
        ref, _ok = parallel.offset_checked(square.path, 3.0)
        closed = [it for it in items if all(k.closed for k in it.path.contours)]
        self.assertEqual(len(closed), 1)
        self.assertEqual(closed[0].path.contours, ref.contours)    # le carré : exactement comme avant
        self.win.undo()                                             # Ctrl+Z : les deux d'origine
        back = [it for L in self.win.canvas.doc.layers for it in L.items]
        self.assertEqual(len(back), 2)
        self.assertEqual(sorted(tuple(round(v, 9) for v in it.path.bbox()) for it in back),
                         [(-5.0, 12.0, 15.0, 12.0), (0.0, 0.0, 10.0, 10.0)])
        self.assertTrue(any(not k.closed for it in back for k in it.path.contours))

    def test_several_offsets_in_the_window(self):
        from vectordrive.core.document import Shape
        line = Shape(path=Path([Contour([Line((0, 0), (20, 0))], False)]), tool=0)
        self.layer.items[:] = [line]
        self.win.canvas.select([line])
        self.win.offset_selection({'distance': 1.0, 'join': 'round', 'count': 3, 'keep': True, 'last_only': False,
                                   'union': True})
        items = [it for L in self.win.canvas.doc.layers for it in L.items]
        self.assertEqual(len(items), 4, BEFORE)                     # l'original et trois parallèles, à part
        self.assertTrue(all(not k.closed for it in items for k in it.path.contours), BEFORE)
        self.assertEqual(sorted(round(it.path.bbox()[1], 9) for it in items), [-3.0, -2.0, -1.0, 0.0])

    def test_dialog_says_it(self):
        from vectordrive.ui.dialogs import OffsetDialog
        dlg = OffsetDialog(None)
        try:
            self.assertIn('ouvert', dlg.dist.toolTip(), 'avant : rien ne disait le sort d’un contour ouvert')
        finally:
            dlg.deleteLater()


if __name__ == '__main__':
    unittest.main()
