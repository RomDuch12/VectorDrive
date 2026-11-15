"""Round 506 : simulation d'usinage — fenêtre de calcul au rayon où l'outil touche encore la matière
(fraise conique qui grave peu profond : quelques dixièmes au lieu du rayon de l'outil), même matière au bit
près, simulation complète et pas à pas."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np

from vectordrive.cam import model, simulate as SIM, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def setup_and_paths():
    d = Document()
    d.plate = None
    for i in range(4):
        d.add(Shape(path=geom.Path([geom.circle((8 * i, 0), 3)]), tool=0))
    d.add(Shape(path=geom.Path([geom.rect(-4, 6, 30, 5)]), tool=0))
    s = model.CamSetup()
    v = model.CamTool(name='V', kind='conique', diameter=6.0, angle=60.0, tip=0.1, feed=1000.0, step_down=0.5)
    b = model.CamTool(name='B', kind='boule', diameter=3.0, feed=1000.0, stepover=0.4, step_down=0.5)
    f = model.CamTool(name='F', kind='fraise', diameter=1.0, feed=1000.0, stepover=0.4, step_down=0.5)
    s.tools = [v, b, f]
    s.operations = [model.Operation(tool_id=v.id, kind='gravure', depth=0.2),
                    model.Operation(tool_id=b.id, kind='gravure', depth=0.4),
                    model.Operation(tool_id=f.id, kind='poche', depth=0.6),
                    model.Operation(tool_id=v.id, kind='vcarve', depth=1.0)]
    return s, [S.compute(d, s, op) for op in s.operations]


def full_radius(tool, r, res):
    return lambda depth: r                               # l'ancien calcul : tout le rayon de l'outil


class TestCutRadius(unittest.TestCase):
    def test_same_material(self):
        s, tps = setup_and_paths()
        fast = SIM.simulate(tps, s, max_cells=300_000)
        SIM._SIM_CACHE.clear()                                          # vraiment recalculée (mémoire, 512)
        with mock.patch.object(SIM, 'cut_radius_of', full_radius):
            ref = SIM.simulate(tps, s, max_cells=300_000)
        self.assertEqual(float(np.abs(fast.H - ref.H).max()), 0.0)
        self.assertLess(fast.H.min(), -0.9)
        base = SIM.SimResult(np.zeros_like(fast.H), fast.x0, fast.y0, fast.res)
        n = sum(len(tp.moves) for tp in tps)
        a = SIM.simulate_range(tps, s, base, n // 3, n)
        with mock.patch.object(SIM, 'cut_radius_of', full_radius):
            b = SIM.simulate_range(tps, s, base, n // 3, n)
        self.assertEqual(float(np.abs(a.H - b.H).max()), 0.0)

    def test_radius_values(self):
        v = model.CamTool(kind='conique', diameter=6.0, angle=60.0, tip=0.1)
        at = SIM.cut_radius_of(v, 3.0, 0.01)
        self.assertLess(at(0.2), 0.05 + 0.2 * np.tan(np.radians(30)) + 0.03)
        self.assertGreater(at(0.2), 0.05 + 0.2 * np.tan(np.radians(30)))
        self.assertEqual(at(50.0), 3.0)                                  # plus profond que le cône : tout
        flat = SIM.cut_radius_of(model.CamTool(kind='fraise', diameter=2.0), 1.0, 0.01)
        self.assertAlmostEqual(flat(0.1), 1.0, places=6)


if __name__ == '__main__':
    unittest.main()
