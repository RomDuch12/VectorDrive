"""Round 1147 (demande du 24/11) : « corriger poche limitée, si on coche aussi sa passe de finition, fait un tour de
finition en trop le long du bord intérieur de la bande »."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1147.ini'))

from shapely.geometry import Point, box  # noqa: E402

from vectordrive.cam import model as M, strategies as S  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Shape  # noqa: E402

BEFORE = 'avant : la finition faisait aussi le tour du bord intérieur de la bande (pas une paroi)'
LOGO = box(40, 20, 60, 40)
FRAME = box(0, 0, 100, 60)


def run(rects, **kw):
    d = Document()
    d.plate = None
    for x, y, w, h in rects:
        d.add(Shape(path=geom.Path([geom.rect(x, y, w, h)]), tool=1))
    setup = M.setup_of(d)
    t = M.CamTool(name='F2', kind='fraise', diameter=2.0)
    setup.tools = [t]
    op = dict(kind='poche', depth=0.5, tool_id=t.id, stepover_mm=1.0, finish=True, stock=0.2)
    op.update(kw)
    return S.compute(d, setup, M.Operation(**op))


def fin_points(tp):
    """Les points des avances de la passe de finition."""
    return [Point(m.x, m.y) for m in tp.moves if getattr(m, 'fin', False) and m.kind != 'rapid']


def far_from(pts, walls):
    return max(min(w.distance(p) for w in walls) for p in pts)


class Finish(unittest.TestCase):
    def test_framed_pocket_finish_only_on_the_walls(self):
        tp = run([(0, 0, 100, 60), (40, 20, 20, 20)], vcarve_max_steps=2)       # le cadre repassé : deux bandes
        pts = fin_points(tp)
        self.assertTrue(pts)
        walls = [FRAME.boundary, LOGO.boundary]
        self.assertLess(far_from(pts, walls), 1.0 + 0.05, BEFORE)              # au rayon des vraies parois
        self.assertTrue(any(LOGO.boundary.distance(p) < 1.05 for p in pts))     # le logo fini
        self.assertTrue(any(FRAME.boundary.distance(p) < 1.05 for p in pts))    # le cadre aussi

    def test_plain_pocket_skip_frame(self):
        tp = run([(0, 0, 30, 30)], vcarve_max_steps=2, finish_skip_frame=True)  # pas de cadre : sa paroi finie
        pts = fin_points(tp)
        wall = box(0, 0, 30, 30).boundary
        self.assertTrue(pts)
        self.assertLess(far_from(pts, [wall]), 1.0 + 0.05, BEFORE)
        self.assertAlmostEqual(min(wall.distance(p) for p in pts), 1.0, 2)

    def test_logo_only_when_frame_skipped(self):
        tp = run([(0, 0, 100, 60), (40, 20, 20, 20)], vcarve_max_steps=3, finish_skip_frame=True)
        pts = fin_points(tp)
        self.assertTrue(pts)
        self.assertLess(far_from(pts, [LOGO.boundary]), 1.0 + 0.05, BEFORE)

    def test_sweep_finish_too(self):
        tp = run([(0, 0, 30, 30)], vcarve_max_steps=2, pocket_mode='balayage')
        pts = fin_points(tp)
        wall = box(0, 0, 30, 30).boundary
        self.assertTrue(pts)
        self.assertLess(far_from(pts, [wall]), 1.0 + 0.05, BEFORE)

    def test_whole_pocket_unchanged(self):
        tp = run([(0, 0, 30, 30)])                                              # pas limitée : le tour entier
        pts = fin_points(tp)
        wall = box(0, 0, 30, 30).boundary
        self.assertLess(far_from(pts, [wall]), 1.0 + 0.05)
        self.assertGreater(len(pts), 3)
        self.assertIsNone(S._BAND.get())                                        # rien ne reste après le calcul

    def test_shut_levels_finish(self):
        tp = run([(0, 0, 30, 30)], vcarve_max_steps=2, depth=2.0, step_down=0.5, finish_shut_levels=True)
        pts = fin_points(tp)
        self.assertTrue(pts)
        self.assertLess(far_from(pts, [box(0, 0, 30, 30).boundary]), 1.0 + 0.05, BEFORE)

    def test_cleared_keeps_the_stock_along_the_band(self):
        d = Document()                                                      # ce que la poche limitée finie a vidé :
        d.plate = None                                                      # la surépaisseur reste au bord de la bande
        d.add(Shape(path=geom.Path([geom.rect(0, 0, 30, 30)]), tool=1))
        setup = M.setup_of(d)
        t = M.CamTool(name='F2', kind='fraise', diameter=2.0)
        setup.tools = [t]
        op = M.Operation(kind='poche', depth=0.5, tool_id=t.id, stepover_mm=1.0, finish=True, stock=0.2,
                         vcarve_max_steps=2)
        got = S.cleared_by(d, op, t, setup.tolerance)
        self.assertTrue(got.contains(Point(0.05, 15)))                      # la paroi : finie
        self.assertTrue(got.contains(Point(3.1, 15)))
        self.assertFalse(got.contains(Point(3.3, 15)), 'avant : la lamelle de surépaisseur crue vidée')
        op.finish = False
        self.assertFalse(S.cleared_by(d, op, t, setup.tolerance).contains(Point(0.1, 15)))   # sans finition : 0,2 laissé

    def test_band_walls_helper(self):
        self.assertIsNone(S.band_walls(1.0))                                    # hors d'une poche limitée
        op = M.Operation(kind='poche', vcarve_max_steps=2)
        self.assertIsNone(S.band_edges(op, box(0, 0, 0, 0).buffer(0)))


if __name__ == '__main__':
    unittest.main()
