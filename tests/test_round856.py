"""Round 856 : plongée angulaire à distance maxi (manuel de TE, page 653) et limite en Z des tirés d'angle (page 655)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model as M
from vectordrive.cam import strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape


class Base(unittest.TestCase):
    KIND = 'contour'

    def path_of(self, contour=None, tool=None, **params):
        doc = Document()
        doc.plate = Plate(width=200.0, height=200.0)
        doc.layers = [Layer(name='A', items=[Shape(path=geom.Path([contour or geom.rect(10, 10, 40, 20)]))])]
        setup = M.setup_of(doc)
        tool = tool or M.CamTool(name='F', diameter=2.0)
        setup.tools.append(tool)
        op = M.Operation(kind=self.KIND, tool_id=tool.id)
        op.depth = 1.0
        for k, v in params.items():
            setattr(op, k, v)
        setup.operations.append(op)
        M.store(doc, setup)
        return S.compute(doc, setup, op, (0.0, 0.0))

    @staticmethod
    def slope_part(tp):
        """Les mouvements de la descente : ceux avant d'atteindre la cote la plus basse."""
        cuts = [m for m in tp.moves if m.kind != 'rapid']
        low = min(m.z for m in cuts)
        n = next(i for i, m in enumerate(cuts) if m.z <= low + 1e-9)
        return cuts[:n + 1], low


class TestClosed(Base):
    ARGS = dict(side='sur', ramp=True, ramp_angle=2.0, step_down=1.0)         # une seule passe

    def extent(self, moves):
        return max(math.dist((a.x, a.y), (moves[0].x, moves[0].y)) for a in moves)

    def test_without_limit_it_goes_along_the_contour(self):
        moves, _low = self.slope_part(self.path_of(**self.ARGS))
        self.assertGreater(self.extent(moves), 15.0)

    def test_the_limit_is_respected(self):
        tp = self.path_of(ramp_max=5.0, **self.ARGS)
        moves, low = self.slope_part(tp)
        self.assertAlmostEqual(low, -1.0, places=6)
        self.assertLessEqual(self.extent(moves), 5.0 + 1e-6)

    def test_the_angle_stays(self):
        moves, _low = self.slope_part(self.path_of(ramp_max=5.0, **self.ARGS))
        for a, b in zip(moves, moves[1:]):
            run = math.dist((a.x, a.y), (b.x, b.y))
            if run > 1e-6:
                self.assertAlmostEqual(abs(b.z - a.z) / run, math.tan(math.radians(2.0)), places=5)

    def test_the_whole_contour_is_cut_afterwards(self):
        tp = self.path_of(ramp_max=5.0, **self.ARGS)
        cuts = [m for m in tp.moves if m.kind != 'rapid']
        n = next(i for i, m in enumerate(cuts) if m.z <= -1.0 + 1e-9)
        bottom = cuts[n:]
        self.assertGreaterEqual(sum(math.dist((a.x, a.y), (b.x, b.y)) for a, b in zip(bottom, bottom[1:]) if a.z <= -1 + 1e-9 and b.z <= -1 + 1e-9), 120.0 - 1e-6)
        for corner in ((10.0, 10.0), (50.0, 10.0), (50.0, 30.0), (10.0, 30.0)):
            self.assertTrue(any(math.dist((m.x, m.y), corner) < 1e-6 for m in bottom), corner)

    def test_a_larger_limit_than_the_contour_changes_nothing(self):
        a = self.path_of(**self.ARGS)
        b = self.path_of(ramp_max=500.0, **self.ARGS)
        self.assertEqual(len(a.moves), len(b.moves))

    def test_zero_changes_nothing(self):
        a = self.path_of(**self.ARGS)
        b = self.path_of(ramp_max=0.0, **self.ARGS)
        self.assertEqual(len(a.moves), len(b.moves))

    def test_each_level_ramps(self):
        tp = self.path_of(ramp_max=5.0, **dict(self.ARGS, step_down=0.4))
        self.assertAlmostEqual(min(m.z for m in tp.moves), -1.0, places=6)
        slopes = [m for a, m in zip(tp.moves, tp.moves[1:]) if abs(m.x - 15.0) < 1e-6 and m.kind != 'rapid']
        self.assertEqual(len(slopes), 3)                       # chaque passe redescend sur les 5 premiers mm

    def test_it_stays_off_the_tabs(self):
        tp = self.path_of(side='sur', ramp=True, ramp_angle=2.0, ramp_max=200.0, tabs=2, tab_width=2.0, tab_height=0.5)
        self.assertAlmostEqual(min(m.z for m in tp.moves), -1.0, places=6)
        cuts = [m for m in tp.moves if m.kind != 'rapid']
        self.assertGreater(max(m.z for m in cuts[1:]), -0.51)     # les pontets sont là


class TestOpen(Base):
    KIND = 'gravure'

    def line(self):
        return geom.Contour([geom.Line((10.0, 10.0), (60.0, 10.0))], False)

    def test_the_zigzag_stays_at_the_start(self):
        tp = self.path_of(self.line(), ramp=True, ramp_angle=2.0, ramp_max=4.0, step_down=1.0)
        moves, low = self.slope_part(tp)
        self.assertAlmostEqual(low, -1.0, places=6)
        self.assertLessEqual(max(m.x for m in moves), 14.0 + 1e-6)

    def test_the_whole_line_is_cut(self):
        tp = self.path_of(self.line(), ramp=True, ramp_angle=2.0, ramp_max=4.0, step_down=1.0)
        self.assertAlmostEqual(max(m.x for m in tp.moves if m.kind != 'rapid'), 60.0, places=6)


class TestPull(Base):
    KIND = 'decoupe3d'

    def lshape(self):
        pts = [(10, 10), (50, 10), (50, 30), (30, 30), (30, 50), (10, 50)]
        return geom.Contour([geom.Line(a, b) for a, b in zip(pts, pts[1:] + pts[:1])], True)

    def cone(self):
        t = M.CamTool(name='C', diameter=6.0)
        t.kind, t.angle, t.tip = 'conique', 60.0, 0.2
        return t

    def high(self, tp):
        cuts = [m for m in tp.moves if m.kind != 'rapid']
        return max(m.z for m in cuts)

    def test_by_default_it_stops_at_the_surface(self):
        tp = self.path_of(self.lshape(), self.cone(), side='exterieur', corner_pull=True)
        self.assertTrue(any('tiré' in w for w in tp.warnings), tp.warnings)
        self.assertLessEqual(self.high(tp), 1e-6)

    def test_it_goes_above(self):
        tp = self.path_of(self.lshape(), self.cone(), side='exterieur', corner_pull=True, corner_pull_z=1.5)
        self.assertAlmostEqual(self.high(tp), 1.5, places=6)

    def test_along_the_same_slope(self):
        tp = self.path_of(self.lshape(), self.cone(), side='exterieur', corner_pull=True, corner_pull_z=1.5)
        cuts = [m for m in tp.moves if m.kind != 'rapid']
        i = next(k for k, m in enumerate(cuts) if abs(m.z - 1.5) < 1e-6)
        a, b, c = cuts[i - 2], cuts[i - 1], cuts[i]
        s1 = (b.z - a.z) / math.dist((a.x, a.y), (b.x, b.y))
        s2 = (c.z - b.z) / math.dist((b.x, b.y), (c.x, c.y))
        self.assertAlmostEqual(s1, s2, places=5)

    def test_it_never_goes_over_the_clearance(self):
        tp = self.path_of(self.lshape(), self.cone(), side='exterieur', corner_pull=True, corner_pull_z=500.0, safe_z=3.0)
        self.assertLessEqual(self.high(tp), 3.0 + 1e-6)


class TestForm(unittest.TestCase):

    def test_the_form_offers_them(self):
        from vectordrive.ui import cam_panel as P
        self.assertIn('corner_pull_z', P.KIND_FIELDS['decoupe3d'])
        for n in ('ramp_max', 'corner_pull_z'):
            self.assertIn(n, P.LABELS)
        names = [f for _title, fields in P.OP_SECTIONS for f in fields]
        self.assertIn('ramp_max', names)
        self.assertIn('corner_pull_z', names)


if __name__ == '__main__':
    unittest.main()
