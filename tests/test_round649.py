"""Round 649 : surface 3D choisie posée sur un sous-onglet 2D — calque de la
prise qui la tourne vers l'outil (face d'un côté, face inclinée), contour en
guide jamais usiné, opérations de ses objets dans cette prise depuis la
cote de la face, objets d'une surface jamais usinés par une autre prise. Relecture 646-648 :
face du dessin écrite '+Z' (brut gardé à l'ébauche et à la simulation),
branche étroite et lignes médianes en paliers, « poser la pièce » pour une
seule prise retournée."""
import copy
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from tests.test_round596 import FakeDoc, two_boxes_stl
from vectordrive.cam import advanced as ADV
from vectordrive.cam import auto3d as A
from vectordrive.cam import mill3d, model, simulate, strategies
from vectordrive.core import faces3d, geom, stock3d
from vectordrive.core import placement3d as P3
from vectordrive.core import surface2d as S2
from vectordrive.core.document import Document, Shape

app = QApplication.instance() or QApplication([])


def wedge_stl():
    """Coin : rampe de (20, y, 0) à (0, y, 10), normales vers l'extérieur."""
    from vectordrive.io import stl_write
    A, B, C, D = (20, 0, 0), (20, 10, 0), (0, 10, 10), (0, 0, 10)
    O, E, F = (0, 0, 0), (0, 10, 0), (20, 10, 0)
    t = np.array([[A, B, C], [A, C, D],                       # rampe
                  [O, E, F], [O, F, A],                       # dessous
                  [O, D, C], [O, C, E],                       # dos
                  [O, A, D], [E, C, F]], dtype=float)         # bouts
    f = pathlib.Path(tempfile.mkdtemp()) / 'coin.stl'
    stl_write.write_stl(str(f), t)
    return str(f)


def face_with(m, normal, where):
    """Numéro de la face dont les triangles ont cette normale et passent par `where` (fonction des centres)."""
    t = np.asarray(m.triangles, dtype=np.float64)
    n = faces3d.normals(t)
    c = t.mean(axis=1)
    ok = (np.abs(n @ np.asarray(normal, dtype=float)) > 0.99) & where(c)     # blocs d'essai : normales vers le dedans
    return int(np.unique(m.face_ids()[ok])[0])


def bbox(loops):
    p = np.array([q for L in loops for q in L])
    return p[:, 0].min(), p[:, 1].min(), p[:, 0].max(), p[:, 1].max()


class TestPose(unittest.TestCase):
    def test_side_face(self):
        p = two_boxes_stl()
        doc = FakeDoc(p)
        raw = mill3d.raw_model(p)
        f = face_with(raw, (1, 0, 0), lambda c: np.abs(c[:, 0] - 20) < 1e-6)   # côté +X du premier bloc
        info = S2.pose(doc, p, [f])
        self.assertEqual(info['face'], '+X')
        self.assertAlmostEqual(info['z'], -30.0, 4)                           # sous le second bloc (X 50)
        self.assertLess(info['flat'], 1e-6)
        x0, y0, x1, y1 = bbox(info['loops'])
        self.assertEqual(sorted([round(x1 - x0, 4), round(y1 - y0, 4)]), [6.0, 10.0])
        top = face_with(raw, (0, 0, 1), lambda c: np.abs(c[:, 2] - 6) < 1e-6)
        info = S2.pose(doc, p, [top])
        self.assertEqual((info['face'], info['z']), ('+Z', 0.0))              # le dessus : la prise du dessin
        x0, y0, x1, y1 = bbox(info['loops'])
        self.assertEqual((round(x1 - x0, 4), round(y1 - y0, 4)), (20.0, 10.0))
        both = face_with(raw, (-1, 0, 0), lambda c: np.abs(c[:, 0]) < 1e-6)
        self.assertIsNone(S2.pose(doc, p, [f, both]))                       # orientations opposées
        self.assertIsNone(S2.pose(doc, p, [99999]))

    def test_inclined_face(self):
        p = wedge_stl()
        doc = FakeDoc(p)
        raw = mill3d.raw_model(p)
        n = np.array([1.0, 0.0, 2.0]) / np.sqrt(5.0)
        f = face_with(raw, n, lambda c: np.ones(len(c), dtype=bool))
        info = S2.pose(doc, p, [f])
        self.assertTrue(info['face'].startswith(P3.PREFIX))                  # posée sur une face plane
        self.assertAlmostEqual(info['z'], 0.0, 4)                             # la rampe : le haut de la pièce
        self.assertLess(info['flat'], 1e-6)
        x0, y0, x1, y1 = bbox(info['loops'])
        self.assertAlmostEqual(sorted([x1 - x0, y1 - y0])[1], np.sqrt(500.0), 3)   # la rampe à plat
        self.assertAlmostEqual(sorted([x1 - x0, y1 - y0])[0], 10.0, 3)


def rect(x, y, w, h, tool=0):
    return Shape(path=geom.Path([geom.polyline([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], closed=True)]),
                 tool=tool)


class TestLayers(unittest.TestCase):
    def setUp(self):
        self.path = two_boxes_stl()
        self.doc = Document()
        self.doc.source_path = self.path
        self.mark = rect(1, 1, 5, 3)
        self.doc.active_layer.items.append(self.mark)
        raw = mill3d.raw_model(self.path)
        f = face_with(raw, (1, 0, 0), lambda c: np.abs(c[:, 0] - 20) < 1e-6)
        self.info = S2.pose(self.doc, self.path, [f])
        self.L = S2.add_layer(self.doc, self.info)
        self.engr = rect(2, 2, 2, 1)
        self.L.items.append(self.engr)

    def test_layer(self):
        self.assertIs(self.doc.active_layer, self.L)
        self.assertIn('Côté +X', self.L.name)
        outline = [it for it in self.L.items if S2.is_outline(it)]
        self.assertEqual(len(outline), 1)
        self.assertTrue(outline[0].locked)
        self.assertEqual(S2.layer_key(self.doc, self.L), ('+X', -1))
        self.assertNotIn('loops', self.L.extra[S2.KEY])
        again = S2.add_layer(self.doc, self.info)
        self.assertNotEqual(again.name, self.L.name)                          # nom distinct

    def test_items_by_setup(self):
        top = model.Operation(kind='gravure', sources=[0])
        side = model.Operation(kind='gravure', sources=[0])
        self.assertTrue(S2.attach(self.doc, side, self.L))                    # rattachée à la surface (653)
        self.assertEqual(side.setup_face, '+X')
        self.assertEqual([it.id for it in strategies.source_items(self.doc, top)], [self.mark.id])
        self.assertEqual([it.id for it in strategies.source_items(self.doc, side)], [self.engr.id])   # sans le contour
        other = model.Operation(kind='gravure', sources=[0], setup_face='-Z')
        self.assertEqual([it.id for it in strategies.source_items(self.doc, other)], [self.mark.id])
        plain = Document()
        plain.active_layer.items.append(rect(0, 0, 1, 1))
        self.assertIsNone(S2.layer_filter(plain, top))                        # aucune surface : rien ne change

    def test_sync_and_compute(self):
        s = model.CamSetup(tools=[model.CamTool(kind='fraise', diameter=1.0, name='F1')])
        op = model.Operation(kind='gravure', tool_id=s.tools[0].id, items=[self.engr.id], depth=0.2)
        safe = op.safe_z
        drawing = model.Operation(kind='gravure', tool_id=s.tools[0].id, items=[self.mark.id], depth=0.2)
        s.operations = [op, drawing]
        self.assertEqual(S2.sync(self.doc, s), 1)
        self.assertEqual((op.setup_face, op.body3d, op.z_start), ('+X', -1, -30.0))
        self.assertAlmostEqual(op.safe_z, safe + 30.0, 6)                     # dégagement au-dessus de la pièce
        self.assertEqual((drawing.setup_face, drawing.z_start), ('', 0.0))
        self.assertEqual(S2.sync(self.doc, s), 0)                            # déjà fait
        tp = strategies.compute(self.doc, s, op)
        zs = [m.z for m in tp.moves]
        self.assertAlmostEqual(min(zs), -30.2, 4)                             # gravé depuis la face
        self.assertGreater(max(zs), 0.0)                                      # dégagement au-dessus du haut
        color = model.Operation(kind='gravure', sources=[0])
        self.assertTrue(S2.adopt(self.doc, color, self.L))                    # usinage par couleur sur la surface
        self.assertEqual(color.setup_face, '+X')
        drill = model.Operation(kind='surface3d')
        self.assertFalse(S2.attach(self.doc, drill, self.L))                  # stratégie 3D : sa propre zone


@unittest.skipUnless(__import__('vectordrive.core.solids', fromlist=['x']).available(), 'manifold3d absent')
class TestWindow(unittest.TestCase):
    def test_menu(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.open_path(two_boxes_stl())
            w._ensure_panel3d()
            p = w.panel3d
            self.assertTrue(p.refresh())
            raw = mill3d.raw_model(p.machining_path())
            f = face_with(raw, (1, 0, 0), lambda c: np.abs(c[:, 0] - 20) < 1e-6)
            p.view.sel_faces = {f}
            p._fill_use_menu()
            act = next(a for a in p.use_menu.actions() if a.text().startswith('Poser sur une surface 2D'))
            self.assertTrue(act.isEnabled())
            n_undo = len(w._undo)
            L = p.surface_to_layer()
            self.assertIs(w.canvas.doc.active_layer, L)
            self.assertEqual(len(w._undo), n_undo + 1)
            self.assertIn('Z -30', p.info.text())
            cp = w.cam_panel
            s = cp.setup()
            s.tools.append(model.CamTool(kind='fraise', diameter=1.0, name='F1'))
            cp.save(s)
            sh = rect(1, 1, 3, 2, tool=L.tool)
            L.items.append(sh)
            w.canvas.selection = [sh]
            o = cp.new_operation('gravure', exec_dialog=False)
            self.assertEqual((o.setup_face, o.z_start), ('+X', -30.0))
            p.view.sel_faces = set()
            self.assertIsNone(p.surface_to_layer())
        finally:
            w.modified = False
            w.close()


class TestDrawingFace(unittest.TestCase):
    def setup(self):
        s = model.CamSetup()
        s.stock3d = stock3d.to_dict(stock3d.Stock3D('bloc', sx=60, sy=20, sz=8, top=3))
        s.tools = [model.CamTool(kind='fraise', diameter=4.0, name='F4', step_down=1.0)]
        return s

    def test_rough_keeps_stock(self):
        doc = FakeDoc(two_boxes_stl())
        tops = []
        for face in ('', '+Z'):
            s = self.setup()
            op = model.Operation(kind='ebauche3d', tool_id=s.tools[0].id, setup_face=face, resolution=0.5, depth=2.0)
            s.operations = [op]
            tp = strategies.compute(doc, s, op)
            tops.append(max(m.z for m in tp.moves if m.kind != 'rapid'))
        self.assertGreater(tops[0], 1.0)                                     # premier palier dans le brut
        self.assertAlmostEqual(tops[1], tops[0], 6)                          # '+Z' écrit : pareil

    def test_stock_of(self):
        doc = FakeDoc(two_boxes_stl())
        s = self.setup()
        op = model.Operation(kind='surface3d', setup_face='+Z')
        s.operations = [op]
        tp = model.Toolpath(op.id, s.tools[0].id, [])
        self.assertIsNotNone(simulate.stock_of(doc, s, [tp]))
        op.setup_face = '-Z'
        self.assertIsNone(simulate.stock_of(doc, s, [tp]))


def t_shape(hw):
    pts = [(0, 0), (30, 0), (30, 6), (15 + hw, 6), (15 + hw, 26), (15 - hw, 26), (15 - hw, 6), (0, 6)]
    return Shape(path=geom.Path([geom.polyline(pts, closed=True)]), tool=0)


class TestVcarveLayers(unittest.TestCase):
    def test_narrow_leg_ridge(self):
        for hw in (1.38, 1.5):
            d = Document()
            d.plate = None
            sh = t_shape(hw)
            d.add(sh)
            s = model.CamSetup()
            cone = model.CamTool(name='C60', kind='conique', diameter=6.0, tip=0.2, angle=60.0, number=1,
                                 cut_length=15, step_down=0.4)
            s.tools = [cone]
            op = model.Operation(kind='vcarve', tool_id=cone.id, items=[sh.id], depth=0.0, vcarve_step=1.0,
                                 resolution=0.1)
            s.operations = [op]
            tp = strategies.compute(d, s, op)
            cuts = [m for m in tp.moves if m.kind != 'rapid']
            lz = strategies.levels(-min(m.z for m in cuts), 1.0)[0]
            idx = [i for i, m in enumerate(tp.moves) if m.kind != 'rapid' and abs(m.z - lz) < 1e-6]
            first = copy.copy(tp)
            first.moves = tp.moves[:idx[-1] + 1]                                # jusqu'au bout du premier palier
            sim = simulate.simulate([first], s, res=0.02, margin=1.0)
            i = int(round((15 - sim.x0) / sim.res))
            j0, j1 = int((12 - sim.y0) / sim.res), int((22 - sim.y0) / sim.res)
            ridge = float(sim.H[j0:j1, i - 1:i + 2].max()) - lz
            self.assertLessEqual(ridge, ADV.LAYER_RIDGE * -lz * 1.3, hw)          # crête bornée sur l'axe de la jambe

    def test_vanishes(self):
        from shapely.geometry import box
        a = (1.0, -1.0, box(0, 0, 10, 10).union(box(4.5, 10, 5.5, 30)))
        b = (2.0, -2.0, box(1, 1, 9, 9))
        self.assertTrue(ADV._vanishes(a, b, 0.5))                             # la jambe s'arrête
        self.assertFalse(ADV._vanishes((1.0, -1.0, box(0, 0, 10, 10)), b, 0.5))
        self.assertTrue(ADV._vanishes(a, (2.0, -2.0, box(0, 0, 0, 0).buffer(0)), 0.5))

    def test_axis_in_layers(self):
        em = strategies.Emitter(model.Operation(), model.CamTool(diameter=1.0))
        pts = [(0.0, 0.0, -0.2), (5.0, 0.0, -2.5), (10.0, 0.0, -0.2)]
        ADV._cut_axis(em, [pts], (0.0, 0.0), [-1.0, -2.0, -2.5])
        feeds = [round(m.z, 3) for m in em.moves if m.kind != 'rapid']
        self.assertEqual(min(feeds), -2.5)
        first_deep = next(k for k, z in enumerate(feeds) if z < -1.0 - 1e-9)
        self.assertTrue(all(z >= -1.0 - 1e-9 for z in feeds[:first_deep]))   # premier palier d'abord
        self.assertIn(-1.0, feeds)


class TestSingleSide(unittest.TestCase):
    def test_instruction(self):
        seq = A.builtin()['Ébauche seule']
        info = A.PartInfo(20, 10, 6)
        tools = [model.CamTool(kind='fraise', diameter=4.0, name='F4', cut_length=20)]
        down = A.plan_all(seq, tools, [], {-1: info}, groups=[(-1, ['-Z'])], home=('', '+Z'))
        self.assertEqual([p.op.kind for p in down], ['instruction', 'ebauche3d'])
        self.assertIn('dessous', down[1].op.name)
        same = A.plan_all(seq, tools, [], {-1: info}, groups=[(-1, ['+Z'])], home=('', '+Z'))
        self.assertEqual([p.op.kind for p in same], ['ebauche3d'])            # la face du dessin : sans message


if __name__ == '__main__':
    unittest.main()
