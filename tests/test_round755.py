"""Round 755 : gravure 2,5D en « contour 2D » à l'outil conique (30°, pointe 0,6) : pas de remontées d'angle, un
contour au fond à décalage XY réglable, le fond vidé là où les parcours d'avant ne sont pas passés. La gravure en
passes décalées, contrôlée à la simulation (fiabilité : rien hors de la forme, profondeur tenue)."""
import math
import os
import pathlib
import tempfile
import unittest

import numpy as np

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.cam import simulate as SIM
from vectordrive.cam import strategies as S
from vectordrive.cam.model import CamSetup, CamTool, Operation
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape

app = QApplication.instance() or QApplication([])
RT, TAN = 0.3, math.tan(math.radians(15))
DEPTH = 0.5
D_FLAT = RT + DEPTH * TAN


def logo():
    return Shape(path=geom.Path([geom.rect(10, 10, 20, 12)]), filled=True)


def world(items=None):
    doc = Document()
    doc.plate = Plate(50, 40)
    doc.layers = [Layer(name='A', items=items or [logo()])]
    setup = CamSetup(tools=[CamTool(id='c', name='30 0.6', kind='conique', diameter=6.0, angle=30.0, tip=0.6),
                            CamTool(id='f', name='F2', kind='fraise', diameter=2.0)])
    return doc, setup


def contour_op(**k):
    base = dict(name='c', kind='vcarve', tool_id='c', depth=DEPTH, vcarve_mode='contour', resolution=0.05)
    base.update(k)
    return Operation(**base)


def cut_points(tp):
    return [m for m in tp.moves if m.kind != 'rapid' and m.z < 0]


def heights(tps, setup, res=0.05):
    sim = SIM.simulate(tps, setup, res=res, margin=2.0, stock=None)
    return sim


def sample(sim, x, y):
    j = int(round((x - sim.x0) / sim.res))
    i = int(round((y - sim.y0) / sim.res))
    if not (0 <= i < sim.H.shape[0] and 0 <= j < sim.H.shape[1]):
        return 0.0                                                            # hors de la carte : pas touché
    return float(sim.H[i, j])


class TestContour2D(unittest.TestCase):
    def test_no_corner_lifts(self):
        doc, setup = world()
        tp = S.compute(doc, setup, contour_op())
        zs = {round(m.z, 6) for m in cut_points(tp)}
        self.assertEqual(zs, {-DEPTH})                                        # tout au fond : aucune remontée

    def test_ring_where_cone_touches_edge(self):
        doc, setup = world()
        tp = S.compute(doc, setup, contour_op(vcarve_edges_only=True))
        xs = [m.x for m in cut_points(tp)]
        ys = [m.y for m in cut_points(tp)]
        self.assertAlmostEqual(min(xs), 10 + D_FLAT, places=3)
        self.assertAlmostEqual(max(xs), 30 - D_FLAT, places=3)
        self.assertAlmostEqual(min(ys), 10 + D_FLAT, places=3)
        self.assertAlmostEqual(max(ys), 22 - D_FLAT, places=3)

    def test_xy_offset(self):
        doc, setup = world()
        for off in (0.1, -0.1):
            tp = S.compute(doc, setup, contour_op(vcarve_edges_only=True, vcarve_offset=off))
            self.assertAlmostEqual(min(m.x for m in cut_points(tp)), 10 + D_FLAT + off, places=3)

    def test_floor_cleared(self):
        doc, setup = world()
        tp = S.compute(doc, setup, contour_op())
        sim = heights([tp], setup)
        self.assertAlmostEqual(sample(sim, 20, 16), -DEPTH, places=2)
        self.assertAlmostEqual(sample(sim, 12, 12), -DEPTH, places=2)
        lengths = tp.lengths()
        edges = S.compute(doc, setup, contour_op(vcarve_edges_only=True)).lengths()
        self.assertGreater(lengths[0], edges[0] * 2)                          # le fond vidé : bien plus long

    def test_nothing_outside_the_form(self):
        doc, setup = world()
        tp = S.compute(doc, setup, contour_op())
        sim = heights([tp], setup)
        for x, y in ((9.9, 16), (30.1, 16), (20, 9.9), (20, 22.1)):
            self.assertGreaterEqual(sample(sim, x, y), -1e-6)                 # le cône s'arrête au bord
        self.assertLess(sample(sim, 10.1, 16), -0.01)                         # et il y arrive

    def test_only_what_previous_left(self):
        doc, setup = world()
        pocket = Operation(name='p', kind='poche', tool_id='f', depth=DEPTH)
        linked = contour_op(link_previous=True)
        setup.operations = [pocket, linked]
        rough, tp = S.compute_all(doc, setup)
        alone = S.compute(doc, setup, contour_op())
        self.assertLess(tp.lengths()[0], alone.lengths()[0] * 0.7)            # le fond déjà vidé n'est pas refait
        xs = [m.x for m in cut_points(tp)]
        self.assertAlmostEqual(min(xs), 10 + D_FLAT, places=3)                # le contour reste entier
        sim = heights([rough, tp], setup)
        self.assertAlmostEqual(sample(sim, 20, 16), -DEPTH, places=2)
        self.assertGreaterEqual(sample(sim, 9.9, 16), -1e-6)

    def test_previous_left_a_corner(self):
        """Coin étroit où la fraise d'avant n'entre pas : le cône y vide ce qu'il peut."""
        wedge = Shape(path=geom.Path([geom.polyline([(10, 10), (40, 10), (40, 30)], closed=True)]))
        doc, setup = world([wedge])
        setup.operations = [Operation(name='p', kind='poche', tool_id='f', depth=DEPTH), contour_op(link_previous=True)]
        rough, tp = S.compute_all(doc, setup)
        self.assertTrue(cut_points(tp))
        self.assertEqual({round(m.z, 6) for m in cut_points(tp)}, {-DEPTH})
        sim = heights([rough], setup)
        sim2 = heights([rough, tp], setup)
        self.assertLessEqual(sample(sim2, 15, 11), sample(sim, 15, 11) + 1e-6)

    def test_narrow_parts_reported(self):
        narrow = Shape(path=geom.Path([geom.rect(10, 10, 20, 0.5)]))
        doc, setup = world([narrow])
        tp = S.compute(doc, setup, contour_op())
        self.assertFalse(tp.moves[1:] and cut_points(tp))
        self.assertTrue(any('plus étroites' in w for w in tp.warnings))

    def test_partly_out_of_reach_reported(self):
        arrow = Shape(path=geom.Path([geom.polyline([(10, 10), (30, 10), (30, 20), (10, 10.2)], closed=True)]))
        doc, setup = world([arrow])
        tp = S.compute(doc, setup, contour_op())
        self.assertTrue(any('hors de portée' in w for w in tp.warnings))

    def test_z_steps(self):
        doc, setup = world()
        tp = S.compute(doc, setup, contour_op(vcarve_step=0.2))
        zs = sorted({round(m.z, 4) for m in cut_points(tp)})
        self.assertEqual(zs[0], -DEPTH)
        self.assertGreater(len(zs), 1)

    def test_climb_and_other_mode_untouched(self):
        doc, setup = world()
        a = S.compute(doc, setup, Operation(name='v', kind='vcarve', tool_id='c', depth=DEPTH, resolution=0.05))
        self.assertGreater(len({round(m.z, 4) for m in cut_points(a)}), 1)    # passes décalées : le cône monte aux bords
        self.assertEqual(Operation(name='x').vcarve_offset, 0.0)
        self.assertEqual(Operation(name='x').vcarve_mode, 'passes')


class TestPassesReliable(unittest.TestCase):
    """Gravure en passes décalées, contrôlée à la simulation sur des formes variées."""

    def check(self, shape, inside, outside, depth=DEPTH):
        doc, setup = world([shape])
        tp = S.compute(doc, setup, Operation(name='v', kind='vcarve', tool_id='c', depth=depth, resolution=0.05))
        self.assertTrue(cut_points(tp))
        self.assertGreaterEqual(min(m.z for m in cut_points(tp)), -depth - 1e-9)
        sim = heights([tp], setup)
        for p in inside:
            self.assertAlmostEqual(sample(sim, *p), -depth, places=1, msg=str(p))
        for p in outside:
            self.assertGreaterEqual(sample(sim, *p), -0.02, msg=str(p))

    def test_rectangle(self):
        self.check(logo(), [(20, 16)], [(9.8, 16), (30.2, 16), (20, 9.8), (20, 22.2)])

    def test_with_hole(self):
        ring = Shape(path=geom.Path([geom.rect(10, 5, 30, 30), geom.circle((25, 20), 6)]))
        self.check(ring, [(13, 20)], [(25, 20), (8, 20), (42, 20)])

    def test_curves(self):
        self.check(Shape(path=geom.Path([geom.circle((20, 20), 8)])), [(20, 20)], [(29, 20), (20, 29)])

    def test_no_rapid_hit(self):
        doc, setup = world([logo(), Shape(path=geom.Path([geom.circle((40, 30), 3)]))])
        tp = S.compute(doc, setup, Operation(name='v', kind='vcarve', tool_id='c', depth=DEPTH, resolution=0.05))
        self.assertEqual(SIM.simulate([tp], setup, res=0.1, stock=None).rapid_hits, [])


class TestPanel(unittest.TestCase):
    def test_form_knows_the_mode(self):
        from vectordrive.ui import cam_panel as P
        src = pathlib.Path(P.__file__).read_text(encoding='utf-8')
        self.assertIn("'contour': 'Contour 2D sans remontées d\\'angle, puis vidage'", src)
        self.assertIn('vcarve_offset', P.KIND_FIELDS['vcarve'] if hasattr(P, 'KIND_FIELDS') else src)

    def test_roundtrip(self):
        op = contour_op(vcarve_offset=0.15)
        again = Operation.from_dict(op.to_dict())
        self.assertEqual((again.vcarve_mode, again.vcarve_offset), ('contour', 0.15))
        self.assertTrue(np.isfinite(again.vcarve_offset))


if __name__ == '__main__':
    unittest.main()
