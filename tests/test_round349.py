"""Round 349 : poche concentrique, optimisation des angles (TypeEdit :
OPTIMISATION_ANGLES_G2D) — la matière restée dans un angle aigu est reprise."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model as M, simulate as SIM, strategies as S, tpp
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape

TRI = [(0, 0), (40, 0), (0, 14)]                                    # angle aigu de 19° en (40, 0)


def run(**kw):
    d = Document()
    d.plate = None
    d.add(Shape(path=geom.Path([geom.polyline(TRI, closed=True)]), tool=1))
    setup = M.setup_of(d)
    t = M.CamTool(name='F2', diameter=2, stepover=0.9)
    setup.tools = [t]
    tp = S.compute(d, setup, M.Operation(kind='poche', depth=1, step_down=1, tool_id=t.id, **kw))
    return tp, setup


def uncut_near_tip(tp, setup):
    sim = SIM.simulate([tp], setup, res=0.05)
    H = sim.H
    count = total = 0
    for j in range(H.shape[0]):
        for i in range(H.shape[1]):
            x, y = sim.x0 + (i + 0.5) * sim.res, sim.y0 + (j + 0.5) * sim.res
            # dans le triangle, près de la pointe aiguë mais à plus de 1 mm des bords (zone atteignable)
            if 22 < x < 34 and y > 0.6 and y < 14 * (1 - x / 40) - 0.6:
                total += 1
                count += H[j, i] > -0.99
    return count / max(total, 1)


class TestCornerOpt(unittest.TestCase):
    def test_reach(self):
        plain, setup = run()
        opt, setup_opt = run(corner_opt=True, corner_opt_angle=135)
        self.assertTrue(any("reprise(s) d'angle" in w for w in opt.warnings), opt.warnings)
        self.assertLess(uncut_near_tip(opt, setup_opt), 0.01)
        # round 936 : au pas plus large que le rayon, la reprise se fait d'office là où il resterait de la matière
        self.assertTrue(any("reprise(s) d'angle" in w for w in plain.warnings), plain.warnings)
        self.assertLess(uncut_near_tip(plain, setup), 0.01)

    def test_spurs_stay_inside(self):
        from shapely.geometry import Polygon
        allowed = Polygon(TRI).buffer(-1.0)
        pts = list(allowed.buffer(-1.8).exterior.coords)
        inside = S.within_test(allowed)
        out, k = S.corner_spurs(pts, 1.8, 135, inside)
        self.assertGreater(k, 0)
        for p in out:
            self.assertTrue(allowed.buffer(1e-6).contains(__import__('shapely').geometry.Point(p)))

    def test_typeedit(self):
        p = tpp.Preset(name='g', kind='CP_Sweeping', sections={'FAO_NEWPARAMGLOB': {
            'OPTIMISATION_ANGLES_G2D': '1', 'OPTIANGLEG2D_AngleMax': str(math.radians(120))}})
        o = tpp.to_template(p)['operations'][0]
        self.assertTrue(o['corner_opt'])
        self.assertAlmostEqual(o['corner_opt_angle'], 120.0, 3)


if __name__ == '__main__':
    unittest.main()
