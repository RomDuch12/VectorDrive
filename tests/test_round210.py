"""Round 210 : dépassement estimé et écrou de pince de la machine."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model, simulate as SIM, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


class TestHolderOf(unittest.TestCase):
    def test_estimate(self):
        s = model.CamSetup(collet_length=15.0, nut_diameter=13.0)
        t = model.CamTool(name='F2', diameter=2.0, cut_length=6.0, geometry={'L1': 38, 'L2': 6})
        self.assertEqual(model.holder_of(t, s), (23.0, 13.0))                    # 38 − 15, écrou de la machine
        short = model.CamTool(name='F1', diameter=1.0, cut_length=8.0, geometry={'L1': 20, 'L3': 10})
        self.assertEqual(model.holder_of(short, s)[0], 11.0)                      # jamais moins qu'utile + 1
        own = model.CamTool(name='F3', stickout=9.0, holder_diameter=20.0, geometry={'L1': 50})
        self.assertEqual(model.holder_of(own, s), (9.0, 20.0))                    # valeurs de l'outil d'abord
        self.assertEqual(model.holder_of(t, model.CamSetup()), (0.0, 0.0))        # rien de connu
        d = model.CamSetup.from_dict(s.to_dict())
        self.assertEqual((d.collet_length, d.nut_diameter), (15.0, 13.0))

    def test_simulation_uses_machine(self):
        d = Document()
        d.plate = None
        d.add(Shape(path=geom.Path([geom.rect(0, 0, 6, 6)]), tool=0))
        s = model.CamSetup(collet_length=30.0, nut_diameter=12.0)
        t = model.CamTool(name='F2', kind='fraise', diameter=2.0, step_down=2.0, cut_length=12.0,
                          geometry={'L1': 35, 'L2': 4})                           # longueur utile 12
        s.tools = [t]
        s.operations = [model.Operation(kind='poche', tool_id=t.id, depth=8.0, step_down=2.0)]
        so, hd = model.holder_of(t, s)
        self.assertEqual(so, 13.0)                                                # max(35 − 30, 12 + 1)
        sim = SIM.simulate(S.compute_all(d, s), s, res=0.1)
        self.assertEqual(sim.collisions, [])                                      # 8 < 13 : pas de contact
        s.operations[0].depth = 16.0
        t.cut_length = 4.0                                                         # dépassement : max(5, 5) = 5
        self.assertEqual(model.holder_of(t, s)[0], 5.0)
        sim = SIM.simulate(S.compute_all(d, s), s, res=0.1)
        self.assertTrue(sim.collisions)


if __name__ == '__main__':
    unittest.main()
