"""Round 608 : automatisme 3D — une étape ne descend pas plus bas que la longueur utile de son outil (le
porte-outil toucherait la pièce) ; la fenêtre le dit."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import auto3d as A
from vectordrive.cam import model


class TestReach(unittest.TestCase):
    def test_limited(self):
        tools = [model.CamTool(kind='fraise', diameter=10, cut_length=30),
                 model.CamTool(kind='boule', diameter=2, cut_length=6)]
        seq = A.builtin()['Ébauche et finition']
        out = A.plan(seq, tools, [], A.PartInfo(100, 60, 50, 0, 60))     # 50 mm de haut, toute la pièce
        rough, fin = out
        self.assertEqual((rough.op.depth, rough.limited), (30.0, 30.0))
        self.assertEqual((fin.op.depth, fin.limited), (6.0, 6.0))
        deep = A.plan(seq, [model.CamTool(kind='fraise', diameter=10, cut_length=80),
                            model.CamTool(kind='boule', diameter=2, cut_length=80)], [],
                      A.PartInfo(100, 60, 50, 0, 60))
        self.assertTrue(all(p.limited == 0.0 and p.op.depth == 0.0 for p in deep))   # assez longs : rien
        sel = A.plan(seq, tools, [], A.PartInfo(20, 20, 4, 0, 20), depth=4.0)
        self.assertTrue(all(p.limited == 0.0 and p.op.depth == 4.0 for p in sel))


if __name__ == '__main__':
    unittest.main()
