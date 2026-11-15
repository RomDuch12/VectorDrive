"""Round 512 : mémoire des simulations — la même simulation redemandée revient de la mémoire (copie),
une retouche des mouvements (même identifiant de parcours) la recalcule ; mémoire bornée en octets."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import edit, model, simulate as SIM, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def paths():
    d = Document()
    d.plate = None
    for i in range(3):
        d.add(Shape(path=geom.Path([geom.circle((8 * i, 0), 3)]), tool=0))
    s = model.CamSetup()
    f = model.CamTool(name='F', kind='fraise', diameter=1.0, feed=1000.0, stepover=0.4, step_down=0.5)
    s.tools = [f]
    s.operations = [model.Operation(tool_id=f.id, kind='poche', depth=0.6)]
    return s, S.compute_all(d, s)


class TestSimCache(unittest.TestCase):
    def setUp(self):
        SIM._SIM_CACHE.clear()

    def test_reuse_copy_and_invalidation(self):
        s, tps = paths()
        real = SIM._simulate
        with mock.patch.object(SIM, '_simulate', side_effect=real) as c:
            a = SIM.simulate(tps, s, max_cells=100_000)
            b = SIM.simulate(tps, s, max_cells=100_000)
            self.assertEqual(c.call_count, 1)
            self.assertIsNot(a.H, b.H)
            self.assertEqual(float(abs(a.H - b.H).max()), 0.0)
            b.H[:] = 5.0                                                # copie : la mémoire n'est pas touchée
            self.assertLess(SIM.simulate(tps, s, max_cells=100_000).H.min(), 0.0)
            moved = [edit.translated_toolpath(tps[0], 1.0, 0.0)]
            self.assertEqual(moved[0].uid, tps[0].uid)                  # même identifiant, mouvements autres
            SIM.simulate(moved, s, max_cells=100_000)
            self.assertEqual(c.call_count, 2)
            SIM.simulate(tps, s, max_cells=200_000)                     # autre grille
            self.assertEqual(c.call_count, 3)

    def test_last_run_report(self):
        S.clear_toolpath_cache()
        d = Document()
        d.plate = None
        d.add(Shape(path=geom.Path([geom.circle((0, 0), 3)]), tool=0))
        s = model.CamSetup()
        f = model.CamTool(name='F', kind='fraise', diameter=1.0, feed=1000.0, stepover=0.4, step_down=0.5)
        s.tools = [f]
        s.operations = [model.Operation(tool_id=f.id, kind='poche', depth=0.6),
                        model.Operation(tool_id=f.id, kind='contour', depth=0.6)]
        S.compute_all(d, s)
        self.assertEqual(S.LAST_RUN, {'reused': 0, 'computed': 2})
        S.compute_all(d, s)
        self.assertEqual(S.LAST_RUN, {'reused': 2, 'computed': 0})

    def test_budget(self):
        s, tps = paths()
        with mock.patch.object(SIM, 'SIM_CACHE_BYTES', 1):
            SIM.simulate(tps, s, max_cells=100_000)
        self.assertEqual(len(SIM._SIM_CACHE), 0)                        # trop gros pour la mémoire


if __name__ == '__main__':
    unittest.main()
