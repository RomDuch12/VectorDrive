"""Round 609 : corrections de la relecture du code 3D — trou ouvert par-dessous non percé du dessus, trous
de même diamètre mais de profondeurs différentes percés à part, centre sur un demi-pas ; sens d'un contact
quand un corps en enveloppe un autre ; faces en pente choisies balayées ; niveaux constants sur des parois
choisies ; corps inconnu ; fonds plats d'un plan incliné ; corps encastré qui suit son parent ; plus gros
outil qui tient ; corps pris entre deux plans ; coques d'un maillage orientées chacune."""
import math
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from tests.test_round591 import face_under, feeds, pocket_stl
from tests.test_round595 import box_tris, model_of
from tests.test_round606 import arc
from vectordrive.cam import auto3d as A
from vectordrive.cam import mill3d, model, strategies
from vectordrive.core import holes3d as H
from vectordrive.core import mechanics as M
from vectordrive.core import solids as SO
from vectordrive.core import watertight as WT
from vectordrive.core.document import Document
from vectordrive.io import model3d

app = QApplication.instance() or QApplication([])


def holed(parts_kinds):
    pieces = [box_tris(0, 0, 0, 40, 20, 20)] + [p for p, _k in parts_kinds]
    kinds = [{'genre': 'plan'}] + [k for _p, k in parts_kinds]
    tris = np.concatenate(pieces)
    fo = np.concatenate([np.full(len(p), i) for i, p in enumerate(pieces)])
    return model3d.Model3D(tris, np.ones((len(tris), 3)), np.zeros((0, 2, 3)), face_of=fo, face_kinds=kinds)


def cyl(cx, cy, r, z0, z1):
    return arc(cx, cy, r, z0, z1), {'genre': 'cylindre', 'axe': [0, 0, 1], 'centre': [cx, cy, z0], 'rayon': r,
                                    'creux': True}


class TestHoles(unittest.TestCase):
    def test_open_from_below_skipped(self):
        cap = box_tris(5, 5, 8, 15, 15, 8.0001)                      # le dessus du trou : de la matière
        m = holed([cyl(10, 10, 2.5, 0, 8), (cap, {'genre': 'plan'})])
        self.assertEqual(H.find(m), [])
        m2 = holed([cyl(10, 10, 2.5, 12, 20)])                       # borgne ouvert par le dessus : gardé
        self.assertEqual([(h.depth, h.through) for h in H.find(m2)], [(8.0, False)])

    def test_half_step_grouping(self):
        a = arc(3.75, 10, 2, 10, 20, 0, 180)
        b = arc(3.7499999999999, 10, 2, 10, 20, 180, 360)
        k = {'genre': 'cylindre', 'axe': [0, 0, 1], 'rayon': 2.0, 'creux': True}
        m = holed([(a, {**k, 'centre': [3.75, 10, 10]}), (b, {**k, 'centre': [3.7499999999999, 10, 10]})])
        self.assertEqual(len(H.find(m)), 1)

    def test_same_diameter_two_depths(self):
        from vectordrive.ui.view3d import Panel3D
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            m = holed([cyl(10, 10, 3, 0, 20), cyl(30, 10, 3, 15, 20)])
            p = Panel3D(w)
            p.model = m
            p.view.set_model(m)
            _c, ops = p.holes_to_drilling()
            self.assertEqual(sorted(o.depth for o in ops), [5.0, 20.5])      # deux perçages, pas un de 20,5
        finally:
            w.modified = False
            w.close()


class TestMechanics(unittest.TestCase):
    def test_core_in_cavity_lifts_out(self):
        cavity = np.concatenate([box_tris(0, 0, 0, 30, 30, 5), box_tris(0, 0, 5, 5, 30, 20),
                                 box_tris(25, 0, 5, 30, 30, 20), box_tris(5, 0, 5, 25, 5, 20),
                                 box_tris(5, 25, 5, 25, 30, 20)])
        core = box_tris(10, 10, 5, 20, 20, 12)
        m = model_of(cavity, core)
        mv = M.motions(m, M.Settings(fixed=0))
        self.assertEqual(len(mv), 1)
        self.assertGreater(mv[0].axis[2], 0.99)                       # le noyau sort par le haut

    def test_fixed_child_follows(self):
        m = model_of(box_tris(0, 0, 0, 10, 10, 5), box_tris(0, 0, 5, 10, 10, 10), box_tris(0, 0, 10, 2, 2, 11))
        js = [M.Joint(0, 1, 'appui', (0.0, 0.0, 1.0), (0, 0, 5)), M.Joint(1, 2, 'encastrement')]
        mv = M.motions(m, M.Settings(fixed=0), js)
        fixed = [x for x in mv if x.kind == 'fixe']
        self.assertEqual((fixed[0].body, fixed[0].parent), (2, 1))
        poses = M.poses(mv, 1.0)
        np.testing.assert_allclose(poses[2][1], poses[1][1], atol=1e-12)    # la poignée suit la porte

    def test_between_two_planes(self):
        d = M.free_direction([np.array([0, 0, 1.0]), np.array([0, 0, -1.0])])
        self.assertIsNotNone(d)
        self.assertLess(abs(d[2]), 1e-9)                              # glisse dans le plan

    def test_mesh_orientation_by_volume(self):
        inward = box_tris(0, 0, 0, 10, 10, 5)
        outward = inward[:, ::-1]
        for lower in (inward, outward):
            m = model_of(lower, box_tris(0, 0, 5, 10, 10, 10))
            js = M.joints(m)
            np.testing.assert_allclose(js[0].axis, [0, 0, 1], atol=1e-9)


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestMill(unittest.TestCase):
    def test_sloped_face_swept(self):
        from vectordrive.io import stl_write
        w = SO.wedge(0, 0, 0, 40, 20, 10) if hasattr(SO, 'wedge') else None
        if w is None:
            self.skipTest('pas de biseau')
        f = pathlib.Path(tempfile.mkdtemp()) / 'biseau.stl'
        stl_write.write_stl(str(f), w.triangles())
        m = mill3d.load_model(Document(), str(f))
        T = m.triangles
        nz = np.abs(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])[:, 2])
        slope = [int(m.face_ids()[i]) for i in range(len(T))
                 if 0.2 < nz[i] / max(np.linalg.norm(np.cross(T[i, 1] - T[i, 0], T[i, 2] - T[i, 0])), 1e-12) < 0.99]
        self.assertTrue(slope)
        st = model.CamSetup(tools=[model.CamTool(kind='boule', diameter=6, stepover=0.2, step_down=50)])
        op = model.Operation(kind='surface3d', tool_id=st.tools[0].id, depth=0, resolution=0.25, model_path=str(f),
                             faces3d=sorted(set(slope)))
        fs = feeds(strategies.compute(Document(), st, op))
        ys = {round(mv.y, 2) for mv in fs}
        self.assertGreater(len(ys), 10)                               # la pente est balayée, pas 1 %

    def test_waterline_on_walls(self):
        f = pocket_stl()
        m = mill3d.load_model(Document(), f)
        walls = sorted({int(m.face_ids()[i]) for i in range(len(m.triangles))
                        if abs(np.cross(m.triangles[i, 1] - m.triangles[i, 0],
                                        m.triangles[i, 2] - m.triangles[i, 0])[2]) < 1e-6
                        and 9.9 < m.triangles[i, :, 0].mean() < 30.1 and 4.9 < m.triangles[i, :, 1].mean() < 15.1
                        and m.triangles[i, :, 2].mean() > 5.0})                        # parois de la poche
        self.assertTrue(walls)
        st = model.CamSetup(tools=[model.CamTool(kind='boule', diameter=2, step_down=1.0)])
        op = model.Operation(kind='niveaux3d', tool_id=st.tools[0].id, depth=0, resolution=0.1, model_path=f,
                             faces3d=walls, step_down=1.0)
        tp = strategies.compute(Document(), st, op)
        self.assertTrue(feeds(tp), tp.warnings)                       # les parois de la poche, pas rien

    def test_unknown_body_is_whole_part(self):
        from vectordrive.core import placement3d as P3
        from vectordrive.core.document import Plate
        from tests.test_round596 import FakeDoc, two_boxes_stl
        f = two_boxes_stl()
        doc = FakeDoc(f, P3.Placement('+Z', 0.0, 'centre'), Plate(x=0, y=0, width=200, height=100))
        self.assertEqual(P3.to_dict(mill3d.side_placement(doc, f, '', 5)),
                         P3.to_dict(mill3d.side_placement(doc, f, '', -1)))

    def test_inclined_plane_no_floors(self):
        X, _Y = np.meshgrid(np.arange(500) * 0.2, np.arange(500) * 0.2)
        Hm = -X * 0.1                                                   # pente de 10 mm sur 100 mm selon X
        self.assertEqual(mill3d.flat_heights(Hm, 0.2, math.pi * 4, 4.0), [])
        Hm[100:300, 100:300] = -3.0
        self.assertEqual(mill3d.flat_heights(Hm, 0.2, math.pi * 4, 4.0), [-3.0])


class TestPlanAndRepair(unittest.TestCase):
    def test_big_rule_nothing_fits(self):
        tools = [model.CamTool(kind='fraise', diameter=d, cut_length=30) for d in (3, 6, 10)]
        t = A.pick_tool(A.Step('ebauche3d', tool_kind='fraise', rule='gros'), tools, A.PartInfo(8, 8, 5, 0, 8))
        self.assertEqual(t.diameter, 3)

    @unittest.skipUnless(SO.available(), 'manifold3d absent')
    def test_cavity_shell_oriented(self):
        outer = box_tris(0, 0, 0, 10, 10, 10)[:, ::-1]                # vers l'extérieur
        cavity = box_tris(3, 3, 3, 7, 7, 7)[:, ::-1]                  # mal orientée (vers l'extérieur aussi)
        s = WT.to_solid(np.concatenate([outer, cavity]))
        self.assertAlmostEqual(s.volume(), 1000 - 64, 6)
        two = WT.to_solid(np.concatenate([outer, box_tris(20, 0, 0, 24, 4, 4)]))   # deux blocs, l'un retourné
        self.assertAlmostEqual(two.volume(), 1000 + 64, 6)


if __name__ == '__main__':
    unittest.main()
