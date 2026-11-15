"""Round 274 : détourage et poche à l'outil conique — contour respecté en
surface (rayon du cône au niveau de la matière) ou au fond (pointe sur le
contour), comme TypeEdit ; recouvrement d'après la largeur qui coupe."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model as M, simulate as SIM, strategies as S, tpp
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape

V = dict(name='V60', kind='conique', diameter=6, angle=60, tip=0.2)


def setup_letter():
    d = Document()
    d.plate = None
    d.add(Shape(path=geom.Path([geom.rect(0, 0, 6, 3)]), tool=1))
    setup = M.setup_of(d)
    v = M.CamTool(**V)
    setup.tools = [v]
    return d, setup, v


class TestConical(unittest.TestCase):
    def test_radius(self):
        v = M.CamTool(**V)
        self.assertAlmostEqual(S.cut_radius(M.Operation(depth=0.3), v), 0.1 + 0.3 * 0.57735, 4)
        self.assertAlmostEqual(S.cut_radius(M.Operation(depth=0.3, contour_ref='fond'), v), 0.1, 6)
        f = M.CamTool(name='F2', diameter=2)
        self.assertEqual(S.cut_radius(M.Operation(depth=0.3, contour_ref='fond'), f), 1.0)

    def test_pocket_surface_matches_drawing(self):
        d, setup, v = setup_letter()
        tp = S.compute(d, setup, M.Operation(kind='poche', depth=0.3, step_down=0.3, tool_id=v.id))
        self.assertFalse(tp.warnings)                                             # plus « outil trop gros »
        sim = SIM.simulate([tp], setup, res=0.02)

        def z(x, y):
            return float(sim.H[int(round((y - sim.y0) / sim.res)), int(round((x - sim.x0) / sim.res))])
        self.assertLess(z(0.05, 1.5), -0.05)                                      # creusé jusqu'au bord
        self.assertGreater(z(-0.08, 1.5), -0.02)                                  # pas au-delà du dessin
        self.assertAlmostEqual(z(3, 1.5), -0.3, 2)

    def test_contour_and_typeedit(self):
        d, setup, v = setup_letter()
        tp = S.compute(d, setup, M.Operation(kind='contour', side='interieur', depth=0.3, step_down=0.3, tool_id=v.id,
                                             contour_ref='fond'))
        xs = [m.x for m in tp.moves if m.kind == 'feed']
        self.assertAlmostEqual(min(xs), 0.1, 6)                                   # pointe à 0,1 du bord
        p = tpp.Preset(name='g', kind='CP_Cutting_3D', sections={'Properties': {'CUT2D_ON_BOTTOM': '1'}})
        self.assertEqual(tpp.to_template(p)['operations'][0]['contour_ref'], 'fond')


if __name__ == '__main__':
    unittest.main()
