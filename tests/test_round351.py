"""Round 351 : découpe 3D, tiré d'angle au pied (TypeEdit : TAP) — au pied des
angles saillants de la pièce, l'outil va jusqu'au sommet du décalage à
onglet : le pied du flanc devient vif (poinçons)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model as M, strategies as S, tpp
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def run(**kw):
    d = Document()
    d.plate = None
    d.add(Shape(path=geom.Path([geom.rect(0, 0, 20, 10)]), tool=1))
    setup = M.setup_of(d)
    t = M.CamTool(name='V90', kind='conique', diameter=6, angle=90, tip=0.2)
    setup.tools = [t]
    return S.compute(d, setup, M.Operation(kind='decoupe3d', depth=1, step_down=0.5, side='exterieur', tool_id=t.id,
                                           **kw))


class TestFoot(unittest.TestCase):
    def test_foot(self):
        tp = run(foot_pull=True)
        self.assertTrue(any("4 tiré(s) d'angle au pied" in w for w in tp.warnings), tp.warnings)
        r_low = 0.1 + 1.0                                                # rayon du cône à 1 mm
        far = max(math.dist((m.x, m.y), (20, 10)) for m in tp.moves if m.kind == 'feed' and m.z == -1
                  and m.x > 20 and m.y > 10)
        self.assertAlmostEqual(far, r_low / math.sin(math.radians(45)), 3)   # sommet de l'onglet
        self.assertFalse(any('pied' in w for w in run().warnings))

    def test_typeedit(self):
        p = tpp.Preset(name='d3', kind='CP_Cutting_3D', sections={
            'SPECIALDECOUPE': {'DecInternal': '2', 'Mode3DOnly': '1'},
            'Properties': {'TAP': '1', 'TAPMinAngle': '22.50', 'TAPMaxAngle': '135.00'}})
        o = tpp.to_template(p)['operations'][0]
        self.assertTrue(o['foot_pull'])
        self.assertEqual((o['foot_pull_min'], o['foot_pull_max']), (22.5, 135.0))


if __name__ == '__main__':
    unittest.main()
