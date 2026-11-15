"""Round 223 : simulation d'enlèvement de matière par lots de segments —
même grille au bit près que segment par segment, 5 × plus vite sur les
gros parcours."""
import math
import unittest

import numpy as np

from vectordrive.cam import model
from vectordrive.cam import simulate as SIM
from vectordrive.cam.model import Move, Toolpath


def mixed_path(kind: str, angle: float = 0.0) -> tuple:
    """Parcours mêlant segments courts, un long trait, un arc, une plongée
    en biais et une remontée ; outil `kind`."""
    t = model.CamTool(name='T', kind=kind, diameter=1.2, angle=angle, tip=0.1, step_down=0.3, cut_length=5)
    s = model.CamSetup(tools=[t])
    moves = [Move('rapid', 0, 0, 5), Move('plunge', 0, 0, -0.4)]
    for i in range(1, 60):                                                   # petits pas (arc aplati)
        a = i * 0.05
        moves.append(Move('feed', 3 * math.cos(a), 3 * math.sin(a), -0.4))
    moves.append(Move('feed', 40.0, 2.0, -0.4))                              # long : imprimé seul
    moves.append(Move('feed', 42.0, 6.0, -0.9))                              # en biais (rampe)
    moves.append(Move('arc_ccw', 38.0, 10.0, -0.9, 40.0, 8.0))               # arc
    moves.append(Move('feed', 38.0, 10.0, 1.0))                              # remontée hors matière
    moves.append(Move('rapid', 0, 0, 5))
    return [Toolpath(op_id='o', tool_id=t.id, moves=moves)], s


class TestBatch(unittest.TestCase):
    def grids(self, kind, angle=0.0, res=0.1):
        tps, s = mixed_path(kind, angle)
        fast = SIM.simulate(tps, s, res=res)
        saved = SIM.BATCH, SIM.MAX_WINDOW
        try:
            SIM.MAX_WINDOW = 0                                               # tout segment par segment
            slow = SIM.simulate(tps, s, res=res)
        finally:
            SIM.BATCH, SIM.MAX_WINDOW = saved
        return fast, slow

    def test_identical_to_segment_by_segment(self):
        for kind, angle in (('fraise', 0.0), ('boule', 0.0), ('conique', 60.0)):
            fast, slow = self.grids(kind, angle)
            self.assertTrue(np.array_equal(fast.H, slow.H), kind)           # au bit près
            self.assertGreater(fast.removed, 0.0)
            self.assertAlmostEqual(fast.deepest, -0.9, 6)

    def test_batches_are_used(self):
        tps, s = mixed_path('fraise')
        calls = []
        orig = SIM._stamp_batch
        try:
            SIM._stamp_batch = lambda H, segs, *a: calls.append(len(segs)) or orig(H, segs, *a)
            SIM.simulate(tps, s, res=0.1)
        finally:
            SIM._stamp_batch = orig
        self.assertTrue(calls and sum(calls) >= 60)                          # les petits pas sont passés par lots

    def test_holder_check_still_flushes(self):
        tps, s = mixed_path('fraise')
        s.tools[0].stickout = 0.5                                            # porte-outil bas : collision attendue
        s.tools[0].holder_diameter = 10.0
        sim = SIM.simulate(tps, s, res=0.1)
        self.assertTrue(sim.collisions)


if __name__ == '__main__':
    unittest.main()
