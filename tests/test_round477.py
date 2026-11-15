"""Round 477 : Finition 2,5D — surface de la gravure 2,5D balayée ; ébauche en paliers, décalage en XY."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from shapely.geometry import box

from vectordrive.cam import advanced as A, model, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def setup_doc(**kw):
    d = Document()
    d.plate = None
    d.add(Shape(path=geom.Path([geom.rect(0, 0, 10, 6)])))
    s = model.CamSetup()
    cone = model.CamTool(name='Conique 30', kind='conique', diameter=3.175, angle=30.0, tip=0.1)
    ball = model.CamTool(name='Boule 0,5', kind='boule', diameter=0.5, step_down=0.2, stepover=0.3)
    s.tools = [cone, ball]
    op = model.Operation(kind='finition25d', tool_id=ball.id, ref_tool_id=cone.id, depth=0.5, resolution=0.05,
                         **kw)
    s.operations = [op]
    return d, s, op


def crossing(cuts):
    """Cotes des segments en X qui traversent le milieu (x = 5, 2 < y < 4)."""
    out = []
    for a, b in zip(cuts, cuts[1:]):
        if abs(a.y - b.y) < 1e-9 and 2 < a.y < 4 and min(a.x, b.x) < 5 < max(a.x, b.x):
            out.append(max(a.z, b.z))
    return out


class TestSurface(unittest.TestCase):
    def test_engraving_surface(self):
        cone = model.CamTool(kind='conique', diameter=3.175, angle=90.0, tip=0.0)
        H = A.engraving_surface(box(0, 0, 10, 10), cone, 2.0, -1.0, -1.0, 121, 121, 0.1)
        self.assertEqual(H[0, 0], 0.0)                                      # dehors
        self.assertAlmostEqual(H[60, 60], -2.0)                             # au milieu : le fond
        self.assertAlmostEqual(H[60, 15], -0.5, places=6)                   # à 0,5 mm du bord, 90° : 0,5 mm


class TestFinish25D(unittest.TestCase):
    def test_finish(self):
        d, s, op = setup_doc()
        tp = S.compute(d, s, op)
        self.assertFalse([w for w in tp.warnings if 'finition 2,5D' in w], tp.warnings)
        cuts = [m for m in tp.moves if m.kind != 'rapid']
        self.assertAlmostEqual(min(m.z for m in cuts), -0.5, places=3)
        # une seule nappe : au milieu, les segments sont au fond, sans palier intermédiaire
        mid = crossing(cuts)
        self.assertTrue(mid and max(mid) < -0.49, mid[:5])

    def test_rough_xy(self):
        d, s, op = setup_doc(rough_mode=True, stock_xy=0.4)
        tp = S.compute(d, s, op)
        cuts = [m for m in tp.moves if m.kind != 'rapid']
        zs = sorted({round(z, 3) for z in crossing(cuts)})
        self.assertEqual(zs, [-0.5, -0.333, -0.167])                        # paliers égaux d'au plus 0,2 mm
        deep = [m for m in cuts if m.z < -0.45]
        edge = min(min(m.x, 10 - m.x, m.y, 6 - m.y) for m in deep)
        self.assertGreater(edge, 0.25 + 0.4 - 0.06)                         # rayon + décalage des flancs

    def test_needs_cone(self):
        d, s, op = setup_doc()
        op.ref_tool_id = ''
        tp = S.compute(d, s, op)
        self.assertTrue(any('outil conique' in w for w in tp.warnings))

    def test_ui(self):
        from vectordrive.ui import cam_panel as CP
        self.assertIn('finition25d', CP.PRESETS)
        self.assertIn('stock_xy', CP.KIND_FIELDS['finition25d'])
        self.assertIn('finition25d', model.op_kinds())


if __name__ == '__main__':
    unittest.main()
