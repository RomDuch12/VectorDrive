"""Round 646 : gravure 2,5D profonde en paliers (passe en Z de la gravure) —
même pièce finie qu'en une fois ; à chaque palier, tout ce qui doit être
plus bas est creusé jusqu'à la cote (crêtes d'au plus un quart de passe) ;
sans passe, ou une passe plus grande que la profondeur, la gravure d'avant à
l'identique ; ligne médiane (intaille) aussi."""
import copy
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np

from vectordrive.cam import advanced as A
from vectordrive.cam import model, simulate, strategies
from vectordrive.cam.model import CamTool
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape

TAN = np.tan(np.radians(30.0))                       # cône de 60°


def carve(step=0.0, mode='passes', w=12.0, h=8.0, depth=3.0):
    d = Document()
    d.plate = None
    sh = Shape(path=geom.Path([geom.rect(0, 0, w, h)]), tool=0)
    d.add(sh)
    s = model.CamSetup()
    cone = CamTool(name='Cône 60', kind='conique', diameter=6.0, tip=0.2, angle=60.0, number=1, cut_length=15,
                   step_down=0.4)
    s.tools = [cone]
    op = model.Operation(name='Gravure', kind='vcarve', tool_id=cone.id, items=[sh.id], depth=depth,
                         vcarve_step=step, vcarve_mode=mode, resolution=0.1)
    s.operations = [op]
    return d, s, strategies.compute(d, s, op)


def cuts(tp):
    return [m for m in tp.moves if m.kind != 'rapid']


def heights(tp, s, upto=None):
    t = copy.copy(tp)
    t.moves = tp.moves[:upto] if upto is not None else list(tp.moves)
    sim = simulate.simulate([t], s, res=0.05, margin=1.0)
    return sim


def max_inside(sim, x0, y0, x1, y1):
    j0, j1 = int(np.ceil((x0 - sim.x0) / sim.res)), int((x1 - sim.x0) / sim.res)
    i0, i1 = int(np.ceil((y0 - sim.y0) / sim.res)), int((y1 - sim.y0) / sim.res)
    return float(sim.H[i0:i1 + 1, j0:j1 + 1].max())


class TestLayers(unittest.TestCase):
    def test_same_part(self):
        _d, s, one = carve(0.0)
        _d, s2, lay = carve(1.0)
        self.assertEqual(lay.warnings, [w for w in one.warnings if 'une passe' not in w])
        self.assertTrue(any('une passe' in w for w in one.warnings), one.warnings)     # 3 mm d'un coup : signalé
        a, b = heights(one, s).H, heights(lay, s2).H
        self.assertEqual(a.shape, b.shape)
        self.assertLess(float(np.abs(a - b).max()), 1e-6)                          # même pièce finie
        self.assertGreater(len(cuts(lay)), len(cuts(one)))

    def test_levels_in_order(self):
        _d, s, lay = carve(1.0)
        zs = [m.z for m in cuts(lay)]
        at = {lv: [i for i, z in enumerate(zs) if abs(z - lv) < 1e-9] for lv in (-1.0, -2.0)}
        self.assertTrue(at[-1.0] and at[-2.0])
        for lv in (-1.0, -2.0):                                                 # palier fini avant de descendre
            self.assertLess(max(at[lv]), min(i for i, z in enumerate(zs) if z < lv - 1e-6))
        # fin du 1er palier : tout ce qui doit être plus bas que 1 mm est creusé jusqu'à 1 mm (crêtes ≤ ¼ passe)
        k1 = [i for i, m in enumerate(lay.moves) if m.kind != 'rapid' and abs(m.z + 1.0) < 1e-9][-1] + 1
        rt = 0.1
        d1 = rt + 1.0 * TAN + 0.15                         # là où la gravure finie est sous 1 mm
        top = max_inside(heights(lay, s, k1), d1, d1, 12 - d1, 8 - d1)
        self.assertLessEqual(top, -1.0 + A.LAYER_RIDGE * 1.0 + 0.03)
        self.assertGreaterEqual(min(m.z for m in lay.moves[:k1]), -1.0 - 1e-9)       # rien de plus bas avant
        k2 = [i for i, m in enumerate(lay.moves) if m.kind != 'rapid' and abs(m.z + 2.0) < 1e-9][-1] + 1
        d2 = rt + 2.0 * TAN + 0.15
        top2 = max_inside(heights(lay, s, k2), d2, d2, 12 - d2, 8 - d2)
        self.assertLessEqual(top2, -2.0 + A.LAYER_RIDGE * 1.0 + 0.03)

    def test_unchanged_without_step(self):
        _d, _s, one = carve(0.0)
        _d, _s, big = carve(5.0)                                                 # passe > profondeur : en une fois
        self.assertEqual([(m.kind, m.x, m.y, m.z) for m in one.moves], [(m.kind, m.x, m.y, m.z) for m in big.moves])

    def test_form_field(self):
        from vectordrive.ui import cam_panel as CP
        self.assertIn('vcarve_step', CP.KIND_FIELDS['vcarve'])
        self.assertIn('vcarve_step', CP.LABELS)
        self.assertTrue(any('vcarve_step' in fields for _t, fields in CP.OP_SECTIONS))
        self.assertEqual(model.Operation().vcarve_step, 0.0)


class TestAxis(unittest.TestCase):
    def test_axis_layers(self):
        pts = [(0, 0, 0.0), (1, 0, -0.5), (2, 0, -1.5), (3, 0, -2.5), (4, 0, -1.5), (5, 0, -0.5), (6, 0, 0.0)]
        out = A.axis_layers(pts, [-1.0, -2.0, -2.5])
        self.assertEqual([[p[2] for p in r] for r in out[0]], [[0.0, -0.5, -1.0, -1.0, -1.0, -0.5, 0.0]])
        self.assertEqual([[p[2] for p in r] for r in out[1]], [[-0.5, -1.5, -2.0, -1.5, -0.5]])
        self.assertEqual([[p[2] for p in r] for r in out[2]], [[-1.5, -2.5, -1.5]])
        self.assertEqual(A.axis_layers(pts, [-2.5]), [[pts]])

    def test_axis_mode(self):
        _d, s, one = carve(0.0, 'axe', w=30.0, h=4.0, depth=4.0)
        _d, s2, lay = carve(1.5, 'axe', w=30.0, h=4.0, depth=4.0)
        deep = -min(m.z for m in cuts(one))
        self.assertGreater(deep, 3.0)
        lv = strategies.levels(deep, 1.5)
        self.assertEqual(len(lv), 3)
        zs = [m.z for m in cuts(lay)]
        self.assertAlmostEqual(min(zs), -deep, places=9)
        first_deep = min(i for i, z in enumerate(zs) if z < lv[0] - 1e-6)
        self.assertTrue(any(abs(z - lv[0]) < 1e-9 for z in zs[:first_deep]))     # palier d'abord
        a, b = heights(one, s).H, heights(lay, s2).H
        self.assertLess(float(np.abs(a - b).max()), 1e-6)


if __name__ == '__main__':
    unittest.main()
