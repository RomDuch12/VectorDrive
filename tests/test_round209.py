"""Round 209 : collisions du porte-outil dans la simulation."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model, preflight as PF, simulate as SIM, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def pocket(depth, stickout, holder, side=6.0):
    d = Document()
    d.plate = None
    d.add(Shape(path=geom.Path([geom.rect(0, 0, side, side)]), tool=0))
    s = model.CamSetup()
    t = model.CamTool(name='F2', kind='fraise', diameter=2.0, step_down=2.0, cut_length=12.0,
                      stickout=stickout, holder_diameter=holder)
    s.tools = [t]
    op = model.Operation(kind='poche', tool_id=t.id, depth=depth, step_down=2.0)
    s.operations = [op]
    return d, s, op


class TestHolder(unittest.TestCase):
    def test_deep_narrow_pocket_collides(self):
        d, s, op = pocket(8.0, 5.0, 12.0)
        sim = SIM.simulate(S.compute_all(d, s), s, res=0.1)
        self.assertTrue(sim.collisions)
        e = sim.collisions[0]
        self.assertGreater(e['depth'], 0.5)
        self.assertLessEqual(e['z'], -5.0 + 1e-6)                                  # sous le dépassement
        self.assertTrue(any(w.startswith('collision') for w in sim.warnings))

    def test_no_collision_when_long_enough_or_unknown(self):
        d, s, op = pocket(8.0, 10.0, 12.0)
        self.assertEqual(SIM.simulate(S.compute_all(d, s), s, res=0.1).collisions, [])
        d, s, op = pocket(8.0, 0.0, 12.0)                                           # dépassement inconnu
        self.assertEqual(SIM.simulate(S.compute_all(d, s), s, res=0.1).collisions, [])
        d, s, op = pocket(3.0, 5.0, 12.0, side=40.0)                                # poche large, peu profonde
        self.assertEqual(SIM.simulate(S.compute_all(d, s), s, res=0.2).collisions, [])
        self.assertEqual(model.CamTool.from_dict({'name': 'ancien'}).stickout, 0.0)    # outils d'avant

    def test_preflight(self):
        d, s, op = pocket(8.0, 5.0, 12.0)
        rep = PF.inspect(d, s, S.compute_all(d, s))
        self.assertTrue(any('dépassement' in text for _lvl, text in rep.notes))
        d, s, op = pocket(3.0, 5.0, 12.0)
        rep = PF.inspect(d, s, S.compute_all(d, s))
        self.assertFalse(any('dépassement' in text for _lvl, text in rep.notes))


if __name__ == '__main__':
    unittest.main()
