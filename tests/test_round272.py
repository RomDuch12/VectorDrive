"""Round 272 : poche en balayage (TypeEdit : passes parallèles à un angle
fixe, optimisé ou croisé X et Y ; aller-retour ou dans un seul sens ; tour
du contour avant ou après) ; modèles TypeEdit SPECIALSWEEPING."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model as M, simulate as SIM, strategies as S, tpp
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def run(**kw):
    d = Document()
    d.plate = None
    d.add(Shape(path=geom.Path([geom.rect(0, 0, 30, 10)]), tool=1))
    setup = M.setup_of(d)
    t = M.CamTool(name='F2', diameter=2, stepover=0.4)
    setup.tools = [t]
    tp = S.compute(d, setup, M.Operation(kind='poche', depth=1, step_down=1, tool_id=t.id, pocket_mode='balayage', **kw))
    return tp, setup


def uncut(tp, setup):
    sim = SIM.simulate([tp], setup, res=0.05)
    H = sim.H
    sub = H[int((1.2 - sim.y0) / sim.res):int((8.8 - sim.y0) / sim.res),
            int((1.2 - sim.x0) / sim.res):int((28.8 - sim.x0) / sim.res)]
    return float((sub > -0.99).mean())


class TestSweepPocket(unittest.TestCase):
    def test_modes_clear_the_pocket(self):
        for am in ('fixe', 'optimise', 'croise'):
            tp, setup = run(sweep_angle_mode=am, sweep_angle=90.0)
            self.assertEqual(uncut(tp, setup), 0.0, am)

    def test_optimised_angle(self):
        zone = S.region([geom.Path([geom.rect(0, 0, 30, 10)])], 0.01)
        self.assertAlmostEqual(abs(math.cos(math.radians(S.sweep_angles(M.Operation(sweep_angle_mode='optimise'),
                                                                          zone)[0]))), 1.0, 6)
        self.assertEqual(S.sweep_angles(M.Operation(sweep_angle=30, sweep_angle_mode='croise'), zone), [30.0, 120.0])
        fixed, _s = run(sweep_angle=90.0)
        opt, _s = run(sweep_angle=90.0, sweep_angle_mode='optimise')
        self.assertLess(len(opt.moves), len(fixed.moves))                          # moins de passes

    def test_one_way_and_contour(self):
        tp, setup = run(sweep_direction='avalant', sweep_contour='avant')
        feeds = [(a, b) for a, b in zip(tp.moves, tp.moves[1:]) if b.kind == 'feed' and abs(b.y - a.y) < 1e-9
                 and abs(b.x - a.x) > 1]
        xs = [b.x - a.x for a, b in feeds]
        self.assertTrue(all(dx > 0 for dx in xs[4:]))                               # passes dans un seul sens
        self.assertEqual(uncut(tp, setup), 0.0)

    def test_typeedit(self):
        p = tpp.Preset(name='b', kind='CP_Sweeping', sections={
            'SPECIALSWEEPING': {'AngleDecal': str(math.pi / 2), 'AngleMode': '2', 'SweepingMode': '1',
                                'BreakAngleMode': '3', 'Stepover': '7.e-004', 'Allowance': '0.'}})
        o = tpp.to_template(p)['operations'][0]
        self.assertEqual((o['pocket_mode'], o['sweep_angle'], o['sweep_contour']), ('balayage', 90.0, 'apres'))
        self.assertAlmostEqual(o['stepover_mm'], 0.7)


if __name__ == '__main__':
    unittest.main()
