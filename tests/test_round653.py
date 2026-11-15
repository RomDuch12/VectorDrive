"""Round 653 : relecture 649-651. Surfaces posées en 2D : opération
rattachée à son calque (une face « dessus » ne prive plus le dessin de ses
calques, deux surfaces de même prise gardent chacune sa cote), rattachement
défait quand il ne vaut plus et absent des modèles de parcours, contenu qui
suit la pièce placée autrement, face tournée vers le bas refusée. Arrêt réel
(« Retournement de la pièce ») entre deux prises de l'automatisme 3D, et
changement de prise sans arrêt signalé avant l'écriture. Corps posé à part :
espace de travail de sa prise, vue 3D à jour. Ctrl+chiffres : Windows
seulement, rien en attente d'une touche à l'autre."""
import os
import sys
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_CAM_TEMPLATES', os.path.join(tempfile.mkdtemp(), 'modeles_fao'))

import numpy as np
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication

from tests.test_round596 import FakeDoc, two_boxes_stl
from tests.test_round649 import bbox, face_with, rect
from tests.test_round650 import key
from vectordrive.cam import auto3d as A
from vectordrive.cam import mill3d, model, preflight, strategies
from vectordrive.cam import templates as TPL
from vectordrive.core import placement3d as P3
from vectordrive.core import surface2d as S2
from vectordrive.core import workspace as WS
from vectordrive.core.document import Document, Plate

app = QApplication.instance() or QApplication([])


def faces(path):
    raw = mill3d.raw_model(path)
    return {'x20': face_with(raw, (1, 0, 0), lambda c: np.abs(c[:, 0] - 20) < 1e-6),
            'x50': face_with(raw, (1, 0, 0), lambda c: np.abs(c[:, 0] - 50) < 1e-6),
            'top2': face_with(raw, (0, 0, 1), lambda c: (np.abs(c[:, 2] - 4) < 1e-6) & (c[:, 0] > 30)),
            'bottom1': face_with(raw, (0, 0, 1), lambda c: (np.abs(c[:, 2]) < 1e-6) & (c[:, 0] < 30)),
            'top1': face_with(raw, (0, 0, 1), lambda c: (np.abs(c[:, 2] - 6) < 1e-6) & (c[:, 0] < 30))}


def ids(items):
    return [it.id for it in items]


def outline_box(L):
    b = [it.bbox() for it in L.items if S2.is_outline(it)][0]
    return tuple(round(float(v), 4) for v in b)


class Base(unittest.TestCase):
    def setUp(self):
        self.path = two_boxes_stl()
        self.F = faces(self.path)
        self.doc = Document()
        self.doc.source_path = self.path
        self.mark = rect(1, 1, 5, 3)
        self.doc.active_layer.items.append(self.mark)
        self.ground = self.doc.active_layer

    def surface(self, face):
        L = S2.add_layer(self.doc, S2.pose(self.doc, self.path, [self.F[face]]))
        sh = rect(2, 2, 2, 1, tool=L.tool)
        L.items.append(sh)
        return L, sh


class TestFilter(Base):
    def test_top_face_keeps_drawing(self):
        L, engr = self.surface('top2')                                         # dessus du second bloc : Z -2
        self.assertEqual(S2.layer_key(self.doc, L), ('', -1))
        top = model.Operation(kind='gravure', sources=[0])
        self.assertEqual(ids(strategies.source_items(self.doc, top)), [self.mark.id])   # le dessin, pas la surface
        s = model.CamSetup(tools=[model.CamTool(kind='fraise', diameter=1.0, name='F1')])
        op = model.Operation(kind='gravure', tool_id=s.tools[0].id, items=[engr.id], depth=0.2)
        drawing = model.Operation(kind='gravure', tool_id=s.tools[0].id, items=[self.mark.id], depth=0.2)
        s.operations = [op, drawing]
        self.assertEqual(S2.sync(self.doc, s), 1)
        self.assertEqual((op.setup_face, op.z_start), ('', -2.0))
        self.assertEqual(ids(strategies.source_items(self.doc, op)), [engr.id])
        self.assertEqual(ids(strategies.source_items(self.doc, drawing)), [self.mark.id])
        tp = strategies.compute(self.doc, s, drawing)
        self.assertAlmostEqual(min(m.z for m in tp.moves), -0.2, 6)          # le dessin depuis le haut

    def test_two_surfaces_same_setup(self):
        L1, e1 = self.surface('x20')                                          # côté +X à Z -30
        L2, e2 = self.surface('x50')                                          # côté +X à Z 0
        self.assertEqual(S2.layer_key(self.doc, L1), S2.layer_key(self.doc, L2))
        self.assertEqual(e1.tool, e2.tool)
        o1, o2 = model.Operation(kind='gravure', sources=[0]), model.Operation(kind='gravure', sources=[0])
        self.assertTrue(S2.adopt(self.doc, o1, L1))
        self.assertTrue(S2.adopt(self.doc, o2, L2))
        self.assertEqual((o1.z_start, o2.z_start), (-30.0, 0.0))
        self.assertEqual(ids(strategies.source_items(self.doc, o1)), [e1.id])  # chacune sa surface, sa cote
        self.assertEqual(ids(strategies.source_items(self.doc, o2)), [e2.id])

    def test_detach(self):
        L, engr = self.surface('x20')
        s = model.CamSetup()
        op = model.Operation(kind='gravure', items=[engr.id])
        safe = op.safe_z
        s.operations = [op]
        S2.sync(self.doc, s)
        self.assertEqual((op.setup_face, op.z_start, op.safe_z), ('+X', -30.0, safe + 30.0))
        L.items.remove(engr)
        self.ground.items.append(engr)                                        # objet ramené sur le dessin
        self.assertEqual(S2.sync(self.doc, s), 1)
        self.assertEqual((op.setup_face, op.body3d, op.z_start, op.safe_z, op.surface2d), ('', -1, 0.0, safe, {}))
        self.assertEqual(ids(strategies.source_items(self.doc, op)), [engr.id])
        self.assertEqual(S2.sync(self.doc, s), 0)

    def test_user_edits_kept(self):
        L, engr = self.surface('x20')
        s = model.CamSetup()
        op = model.Operation(kind='gravure', items=[engr.id])
        s.operations = [op]
        S2.sync(self.doc, s)
        op.z_start = -29.5                                                    # retouché par l'utilisateur
        self.assertEqual(S2.sync(self.doc, s), 0)
        self.assertEqual(op.z_start, -29.5)                                   # pas remis
        S2.detach(op)
        self.assertEqual((op.setup_face, op.z_start), ('', -29.5))           # sa cote à lui reste

    def test_layer_deleted(self):
        L, engr = self.surface('x20')
        color = model.Operation(kind='gravure', sources=[0])
        S2.adopt(self.doc, color, L)
        self.doc.layers.remove(L)
        self.assertEqual(strategies.source_items(self.doc, color), [])        # rien
        s = model.CamSetup(operations=[color])
        self.assertEqual(S2.sync(self.doc, s), 0)                             # round 656 : gardée rattachée,
        self.assertEqual(color.setup_face, '+X')                              # elle n'usine pas le dessin
        self.assertEqual(strategies.source_items(self.doc, color), [])
        self.assertTrue(S2.orphaned(self.doc, color))

    def test_templates(self):
        L, engr = self.surface('x20')
        tool = model.CamTool(kind='fraise', diameter=1.0, name='F1')
        op = model.Operation(kind='gravure', tool_id=tool.id, items=[engr.id])
        S2.attach(self.doc, op, L)
        for d in (TPL.single(op, tool, 'essai')['operations'][0],
                  TPL.from_setup(model.CamSetup(tools=[tool], operations=[op]), 'essai')['operations'][0]):
            self.assertEqual((d['setup_face'], d['z_start'], d['surface2d']), ('', 0.0, {}))
            self.assertAlmostEqual(d['safe_z'], model.Operation().safe_z, 6)
        self.assertEqual(op.setup_face, '+X')                                  # l'opération du dessin : inchangée


class TestFollow(Base):
    def setUp(self):
        super().setUp()
        self.doc.extra[P3.KEY] = P3.to_dict(P3.Placement('+Z', 0.0, 'centre'))
        self.doc.plate = Plate(x=0, y=0, width=100, height=100)

    def check_followed(self, L):
        self.assertTrue(S2.stale(self.doc, L))
        op = model.Operation(kind='gravure', sources=[0])
        S2.attach(self.doc, op, L)
        self.assertEqual(strategies.source_items(self.doc, op), [])           # pas suivi : pas usiné
        self.assertEqual(S2.follow(self.doc), 1)
        self.assertFalse(S2.stale(self.doc, L))
        want = bbox(S2.pose(self.doc, self.path, [self.F['x20']])['loops'])
        np.testing.assert_allclose(outline_box(L), want, atol=1e-3)           # là où la face est maintenant
        self.assertEqual(len(strategies.source_items(self.doc, op)), 1)

    def test_plate(self):
        L, _e = self.surface('x20')
        self.assertFalse(S2.stale(self.doc, L))
        self.doc.plate = Plate(x=0, y=0, width=200, height=100)              # pièce centrée : elle bouge
        self.check_followed(L)

    def test_rotation(self):
        L, _e = self.surface('x20')
        self.doc.extra[P3.KEY] = P3.to_dict(P3.Placement('+Z', 90.0, 'centre'))
        self.check_followed(L)
        self.assertEqual(S2.follow(self.doc), 0)

    def test_volumes_and_old_layers(self):
        L, _e = self.surface('x20')
        del L.extra[S2.KEY]['pl']                                            # calque d'une version d'avant
        self.doc.plate = Plate(x=0, y=0, width=200, height=100)
        self.assertFalse(S2.stale(self.doc, L))
        self.assertEqual(S2.follow(self.doc), 0)


class TestFacingDown(unittest.TestCase):
    def test_parity(self):
        path = two_boxes_stl()
        F, raw = faces(path), mill3d.raw_model(path)
        from vectordrive.core import faces3d
        tri = lambda f: faces3d.face_triangles(raw.face_ids(), [f])            # noqa: E731
        self.assertTrue(S2.facing_down(raw, tri(F['bottom1'])))               # dessous : le corps au-dessus
        self.assertFalse(S2.facing_down(raw, tri(F['top1'])))
        self.assertFalse(S2.facing_down(raw, tri(F['top2'])))                 # l'autre corps ne compte pas
        self.assertFalse(S2.pose(FakeDoc(path), path, [F['x20']])['down'])

    def test_flipped_normal(self):
        path = two_boxes_stl()
        F = faces(path)
        real = S2.outward_normal
        with mock.patch.object(S2, 'outward_normal', side_effect=lambda m, i: -real(m, i)):   # sens faux
            info = S2.pose(FakeDoc(path), path, [F['x20']])
        self.assertEqual((info['face'], info['z'], info['down']), ('+X', -30.0, False))     # la pose inverse


class TestStops(unittest.TestCase):
    def setUp(self):
        self.path = two_boxes_stl()
        self.doc = Document()
        self.doc.source_path = self.path
        self.tool = model.CamTool(kind='fraise', diameter=1.0, name='F1', spindle=10000)

    def run_ops(self, *ops):
        s = model.CamSetup(tools=[self.tool], operations=list(ops))
        tps = [model.Toolpath(o.id, '', [], name=o.name) if o.kind == 'instruction' else       # arrêts écrits aussi
               model.Toolpath(o.id, self.tool.id, [model.Move('feed', 1, 1, -0.5)], name=o.name) for o in ops]
        return s, tps

    def op(self, name, face='', body=-1):
        return model.Operation(kind='gravure', name=name, tool_id=self.tool.id, setup_face=face, body3d=body,
                               model_path=self.path)

    def test_changes(self):
        a, b = self.op('A'), self.op('B', '-Z')
        s, tps = self.run_ops(a, b)
        out = preflight.setup_changes(self.doc, s, tps)
        self.assertEqual([lv for lv, _t in out], [preflight.BLOQUANT])
        self.assertIn('« B »', out[0][1])
        r = preflight.inspect(self.doc, s, tps)
        self.assertTrue(any('« B »' in t for t in r.blocking()))
        msg = model.Operation(kind='instruction', instruction='message', params={'message': 'x'})
        s, tps = self.run_ops(a, msg, b)
        self.assertEqual(len(preflight.setup_changes(self.doc, s, tps)), 1)     # un message n'arrête pas
        stop = model.Operation(kind='instruction', instruction='retournement')
        s, tps = self.run_ops(a, stop, b)
        self.assertEqual(preflight.setup_changes(self.doc, s, tps), [])
        c = self.op('C', '', 1)
        s, tps = self.run_ops(a, c)
        self.assertEqual([lv for lv, _t in preflight.setup_changes(self.doc, s, tps)], [preflight.ATTENTION])
        same = self.op('D', '+Z')                                               # « dessus » écrit : même prise
        s, tps = self.run_ops(a, same)
        self.assertEqual(preflight.setup_changes(self.doc, s, tps), [])

    def test_auto3d_stop(self):
        seq = A.builtin()['Ébauche et finition']
        tools = [model.CamTool(kind='fraise', diameter=6, cut_length=30)]
        info = A.PartInfo(50, 40, 10, 0, 40)
        out = A.plan_all(seq, tools, [], {-1: info, 0: info}, groups=[(0, ['+Z', '-Z'])], body_names={0: 'Noyau'})
        stops = [p.op for p in out if p.op.kind == 'instruction']
        self.assertEqual(len(stops), 2)
        self.assertTrue(all(o.instruction == 'retournement' and o.params['park'] for o in stops))
        self.assertEqual(stops[1].params['message'], 'Poser Noyau : dessous vers l\'outil')


class TestBodyClamp(unittest.TestCase):
    def test_gone(self):
        path = two_boxes_stl()
        doc = FakeDoc(path)
        P3.set_body(doc, 5, P3.Placement('-Z', 0.0, 'centre'))              # corps qui n'existe plus
        self.assertEqual(WS.drawing_face(doc, path, 5), '+Z')
        self.assertEqual(WS.norm_face(doc, '-Z', path, 5), '-Z')            # comme side_placement


@unittest.skipUnless(__import__('vectordrive.core.solids', fromlist=['x']).available(), 'manifold3d absent')
class TestWindow(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.open_path(two_boxes_stl())
        self.w._ensure_panel3d()
        self.p = self.w.panel3d
        self.assertTrue(self.p.refresh())

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_view_follows_body(self):
        p = self.p
        p.place_body(1, placement=P3.Placement('+X', 0.0, 'centre'))
        b = p.view.model.bounds()
        self.assertAlmostEqual(b[5] - b[2], 10.0, 4)
        p.place_body(1, placement=P3.Placement('+Z', 0.0, 'centre'))           # même corps, montré : redessiné
        b = p.view.model.bounds()
        self.assertAlmostEqual(b[5] - b[2], 4.0, 4)

    def test_workspace_of_body(self):
        cp = self.w.cam_panel
        self.p.place_body(1, placement=P3.Placement('-Z', 0.0, 'centre'))
        d1 = cp.workspace_dialog(exec_dialog=False, setup=('-Z', 1))
        d2 = cp.workspace_dialog(exec_dialog=False, setup=('+Z', 1))
        self.assertEqual((d1.setup_key, d2.setup_key), (('', 1), ('+Z', 1)))
        d1.deleteLater()
        d2.deleteLater()

    def test_plate_adjust(self):
        from vectordrive.core.geom import Affine
        w = self.w
        doc = w.canvas.doc
        path = self.p.machining_path()
        L = S2.add_layer(doc, S2.pose(doc, path, [faces(path)['x20']]))
        before = outline_box(L)
        other = rect(0, 0, 1, 1)
        doc.layers[0].items.append(other)
        w.apply_plate(Plate(x=0, y=0, width=300, height=200), adjust=Affine.translation(10.0, 0.0))
        self.assertEqual(outline_box(L), before)                              # la surface suit la pièce, pas la composition
        moved = next(it for it in doc.layers[0].items if it.id == other.id)
        self.assertAlmostEqual(moved.bbox()[0], 10.0, 6)

    def test_digit_row(self):
        w = self.w
        ev = lambda kind: key(kind, Qt.Key.Key_Egrave, 0x37, 'è')               # noqa: E731
        with mock.patch.object(sys, 'platform', 'darwin'):
            self.assertFalse(w._digit_row(ev(QEvent.Type.ShortcutOverride)))   # touches virtuelles de Windows
        if sys.platform != 'win32':
            return
        w._digit_eaten = 0x37                                                 # restée d'une touche d'avant
        w.A['direction'].setEnabled(False)
        self.assertFalse(w._digit_row(ev(QEvent.Type.ShortcutOverride)))
        self.assertFalse(w._digit_row(ev(QEvent.Type.KeyPress)))               # pas mangée


if __name__ == '__main__':
    unittest.main()
