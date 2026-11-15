"""Round 714 : DXF — multilignes, repères multiples et cotes de longueur d'arc
éclatés ; droites infinies (XLINE, RAY) en lignes de construction, à
l'échelle de $INSUNITS ; calque caché écarté."""
import os
import tempfile
import unittest

import ezdxf
from ezdxf.math import Vec2
from ezdxf.render import mleader

from vectordrive.core.document import Text
from vectordrive.io import dxf as VD


def _dxf(insunits: int, build) -> str:
    doc = ezdxf.new('R2018', setup=True)
    doc.header['$INSUNITS'] = insunits
    build(doc, doc.modelspace())
    p = os.path.join(tempfile.mkdtemp(), 'essai.dxf')
    doc.saveas(p)
    return p


class TestRead(unittest.TestCase):
    def test_exploded_and_construction_lines(self):
        def build(doc, msp):
            msp.add_line((0, 0), (10, 0))
            msp.add_mline([(0, 20), (30, 20), (30, 40)], dxfattribs={'layer': 'multi'})
            b = msp.add_multileader_mtext('Standard')
            b.set_content('Note')
            b.add_leader_line(mleader.ConnectionSide.left, [Vec2(50, 50)])
            b.build(insert=Vec2(60, 60))
            msp.add_arc_dim_3p(base=(0, 80), center=(0, 60), p1=(10, 60), p2=(0, 70)).render()
            msp.add_xline((5, 5), (1, 1))
            msp.add_xline((0, 7), (-1, 0))
            msp.add_ray((3, 0), (0, -1))
            doc.layers.add('cache').off()
            msp.add_xline((0, 0), (1, 2), dxfattribs={'layer': 'cache'})
        r = VD.read(_dxf(4, build))
        for t in ('MLINE', 'MULTILEADER', 'ARC_DIMENSION', 'XLINE', 'RAY'):
            self.assertFalse([m for m in r.report if m.startswith(t)], t)
        multi = next(L for L in r.layers if L.name == 'multi')
        self.assertGreaterEqual(len(multi.items), 4)                              # les traits de la multiligne
        texts = [it.text for L in r.layers for it in L.items if isinstance(it, Text)]
        self.assertIn('Note', texts)                                              # texte du repère
        self.assertEqual(r.extra['guides'], [['h', 7.0], ['v', 3.0]])
        self.assertEqual(r.extra['guides_obliques'], [[5.0, 5.0, 45.0]])         # calque caché écarté
        self.assertIn('3 ligne(s) de construction (XLINE, RAY) reprises en guides', r.report)

    def test_units(self):
        def build(doc, msp):
            msp.add_line((0, 0), (10, 0))
            msp.add_xline((1, 2), (0.8660254037844387, 0.5))
        r = VD.read(_dxf(5, build))                                               # en cm
        x, y, a = r.extra['guides_obliques'][0]
        self.assertAlmostEqual(x, 10.0)
        self.assertAlmostEqual(y, 20.0)
        self.assertAlmostEqual(a, 30.0)
        self.assertNotIn('guides', r.extra)


if __name__ == '__main__':
    unittest.main()
