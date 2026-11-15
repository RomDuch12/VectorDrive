"""Round 668 : relecture de l'usinage 3D en plusieurs prises. Contours de
zone qui suivent la pièce (placement gardé quand on les choisit) ; corps
positionné à part retourné : arrêt bloquant, arrêt ajouté avec sa vraie
pose (gardée : contrôlée si la pose du corps change ensuite), inséré après
les opérations de même pose ; même face réelle : pas bloquant ; autre
fichier : face de la prise ; zone montrée dans la prise montrée puis
remplacée telle quelle ; parcours sans opération montrés dans la prise du
dessin seulement ; volumes : recomposition sans arêtes."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_CAM_TEMPLATES', os.path.join(tempfile.mkdtemp(), 'modeles_fao'))

import numpy as np

from tests.test_round596 import FakeDoc, two_boxes_stl
from vectordrive.cam import mill3d, model, preflight, strategies
from vectordrive.core import placement3d as P3
from vectordrive.core import solids as SO
from vectordrive.core.document import Plate


def follow(doc, path):
    """Placement du dessin recalé sur la plaque (comme MainWindow._part_follows_plate)."""
    from vectordrive.io import model3d
    cur = P3.of(doc)
    m = model3d.load(path, P3.Placement(cur.face, cur.rot))
    P3.resolve(cur, m.bounds(), (doc.plate.x, doc.plate.y, doc.plate.width, doc.plate.height))
    doc.extra[P3.KEY] = P3.to_dict(cur)


def tp_of(o, tool):
    if o.kind == 'instruction':
        return model.Toolpath(o.id, '', [], name=o.name)
    return model.Toolpath(o.id, tool.id, [model.Move('feed', 1, 1, -0.5)], name=o.name)


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestZoneFollows(unittest.TestCase):
    def test_contours_follow_plate(self):
        path = two_boxes_stl()                                                    # bloc B : x 40..50, haut 4
        doc = FakeDoc(path, P3.Placement('+Z', 0.0, 'centre'), Plate(x=0, y=0, width=100, height=100))
        follow(doc, path)
        dx, dy = P3.of(doc).dx, P3.of(doc).dy
        loop = [[40 + dx, dy, 4.0], [50 + dx, dy, 4.0], [50 + dx, 10 + dy, 4.0], [40 + dx, 10 + dy, 4.0]]
        st = model.CamSetup(tools=[model.CamTool(kind='fraise', diameter=2, stepover=0.4, step_down=10)])
        op = model.Operation(kind='surface3d', tool_id=st.tools[0].id, depth=0, resolution=0.25,
                             contours3d=[loop], model_path=path)
        op.contours3d_pl = mill3d.zone_frame(doc, path)                           # gardé au choix
        self.assertEqual(op.contours3d_pl['dx'], dx)
        doc.plate = Plate(x=0, y=0, width=200, height=100)                        # la pièce suit (+50 en X)
        follow(doc, path)
        nx = P3.of(doc).dx
        self.assertAlmostEqual(nx - dx, 50.0)
        feeds = [mv.x for mv in strategies.compute(doc, st, op).moves if mv.kind == 'feed']
        self.assertTrue(feeds)
        self.assertGreaterEqual(min(feeds), 40 + nx - 1e-6)                       # toujours sur le bloc B
        self.assertLessEqual(max(feeds), 50 + nx + 1e-6)
        moved = mill3d.zone_op(doc, op).contours3d[0]
        self.assertTrue(np.allclose(np.asarray(moved)[:, 0], np.asarray(loop)[:, 0] + 50.0))

    def test_old_contours_as_before(self):
        path = two_boxes_stl()
        doc = FakeDoc(path, P3.Placement('+Z', 0.0, 'centre'), Plate(x=0, y=0, width=100, height=100))
        follow(doc, path)
        op = model.Operation(kind='surface3d', contours3d=[[[1, 2, 3], [4, 2, 3], [4, 5, 3]]], model_path=path)
        self.assertIs(mill3d.zone_op(doc, op), op)                                # sans placement gardé : tels quels
        self.assertEqual(mill3d.zone_frame(doc, ''), {})                          # volumes du dessin : rien à suivre
        self.assertIn('contours3d_pl', model.Operation.from_dict({'contours3d_pl': {'dx': 1}}).__dict__)


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestBodyApartStops(unittest.TestCase):
    def setUp(self):
        self.path = two_boxes_stl()
        self.doc = FakeDoc(self.path, P3.Placement('+Z', 0.0, 'centre'), Plate(x=0, y=0, width=100, height=100))
        follow(self.doc, self.path)
        P3.set_body(self.doc, 1, P3.Placement('-Z', 0.0, 'centre'))              # corps 2 posé dessous, à part
        self.tool = model.CamTool(kind='fraise', diameter=1.0, name='F1')

    def op(self, name, face='', body=-1):
        return model.Operation(kind='surface3d', name=name, tool_id=self.tool.id, setup_face=face, body3d=body,
                               model_path=self.path)

    def test_whole_then_body_apart(self):
        a = self.op('A')
        for c in (self.op('C', '', 1), self.op('C2', '-Z', 1)):
            s = model.CamSetup(tools=[self.tool], operations=[a, c])
            tps = [tp_of(o, self.tool) for o in s.operations]
            self.assertEqual([lv for lv, _t in preflight.setup_changes(self.doc, s, tps)], [preflight.BLOQUANT])
            added = preflight.add_stops(self.doc, s, tps)
            self.assertEqual(len(added), 1)
            self.assertIn('dessous', added[0].params['message'])               # pas « comme le dessin »

    def test_body_turned_back_to_its_pose(self):
        b, c = self.op('B', '+Z', 1), self.op('C', '', 1)
        s = model.CamSetup(tools=[self.tool], operations=[b, c])
        added = preflight.add_stops(self.doc, s, [tp_of(o, self.tool) for o in s.operations])
        self.assertEqual(len(added), 1)
        self.assertIn('dessous', added[0].params['message'])

    def test_stop_announcing_other_pose(self):
        a = self.op('A')
        stop = model.Operation(name='Poser le corps 2', kind='instruction', instruction='retournement',
                               params={'message': 'm', 'setup': ['', 1]}, tool_id='')
        s = model.CamSetup(tools=[self.tool], operations=[stop, a])
        notes = preflight.stop_notes(self.doc, s, [tp_of(o, self.tool) for o in s.operations])
        self.assertEqual([lv for lv, _t in notes], [preflight.BLOQUANT])          # corps retourné ≠ pièce

    def test_same_pose_other_body_still_a_note(self):
        P3.set_body(self.doc, 1, P3.Placement('+Z', 0.0, 'centre'))              # même face : tenu à côté ?
        s = model.CamSetup(tools=[self.tool], operations=[self.op('A'), self.op('C', '', 1)])
        tps = [tp_of(o, self.tool) for o in s.operations]
        self.assertEqual([lv for lv, _t in preflight.setup_changes(self.doc, s, tps)], [preflight.ATTENTION])
        self.assertEqual(preflight.add_stops(self.doc, s, tps), [])

    def test_announced_pose_checked_later(self):
        a, c = self.op('A'), self.op('C', '', 1)
        s = model.CamSetup(tools=[self.tool], operations=[a, c])
        added = preflight.add_stops(self.doc, s, [tp_of(o, self.tool) for o in s.operations])
        self.assertEqual(added[0].params['setup'], ['-Z', 1])                      # la pose annoncée
        tps = [tp_of(o, self.tool) for o in s.operations]
        self.assertEqual(preflight.stop_notes(self.doc, s, tps), [])
        P3.set_body(self.doc, 1, P3.Placement('+X', 0.0, 'centre'))              # pose changée depuis
        self.assertEqual([lv for lv, _t in preflight.stop_notes(self.doc, s, tps)], [preflight.BLOQUANT])

    def test_same_real_face_not_blocking(self):
        s = model.CamSetup(tools=[self.tool], operations=[self.op('A'), self.op('B', '+Z', 1)])
        tps = [tp_of(o, self.tool) for o in s.operations]                         # dessus des deux : même face
        self.assertEqual([lv for lv, _t in preflight.setup_changes(self.doc, s, tps)], [preflight.ATTENTION])

    def test_other_file_keeps_setup_face(self):
        from tests.test_round596 import pocket_stl
        other = model.Operation(kind='surface3d', name='O', tool_id=self.tool.id, body3d=0, model_path=pocket_stl())
        P3.set_body(self.doc, 1, None)
        self.doc.extra[P3.KEY] = P3.to_dict(P3.Placement('-Z', 0.0, 'centre'))    # pièce du dessin dessous
        s = model.CamSetup(tools=[self.tool], operations=[self.op('A'), other])
        tps = [tp_of(o, self.tool) for o in s.operations]
        self.assertNotIn(preflight.BLOQUANT, [lv for lv, _t in preflight.setup_changes(self.doc, s, tps)])

    def test_stop_after_same_pose(self):
        a, b, c = self.op('A'), self.op('B', '', 0), self.op('C', '', 1)
        s = model.CamSetup(tools=[self.tool], operations=[a, b, c])
        added = preflight.add_stops(self.doc, s, [tp_of(o, self.tool) for o in (a, c)])   # B décochée
        self.assertEqual([o.name for o in s.operations], ['A', 'B', added[0].name, 'C'])

    def test_auto3d_stop_announces_body_pose(self):
        from vectordrive.cam import auto3d as A
        seq = next(iter(A.builtin().values()))
        info = A.analyze(mill3d.raw_model(self.path))
        out = A.plan_all(seq, [], [], {-1: info, 1: info}, groups=[(-1, ['']), (1, [''])], model_path=self.path,
                         own_faces={1: '-Z'})
        stops = [p.op for p in out if p.op.kind == 'instruction']
        self.assertEqual(len(stops), 2)
        self.assertIn('dessous', stops[1].params['message'])
        self.assertEqual(stops[1].params['setup'], ['-Z', 1])


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestViewSetups(unittest.TestCase):
    from tests import test_round657 as _R
    setUp, tearDown, names = _R.TestWindow.setUp, _R.TestWindow.tearDown, _R.TestWindow.names

    def show(self, key):
        p = self.p
        p._fill_setups(p._model_source())
        i = p.setup_view.findData(key)
        self.assertGreaterEqual(i, 0)
        p.setup_view.setCurrentIndex(i)
        self.assertTrue(p.refresh())

    def add_flipped(self, enabled=True):
        cp = self.cp
        s = cp.setup()
        o = model.Operation(kind='surface3d', name='Dessous', tool_id=s.tools[0].id, setup_face='-Z',
                            contours3d=[[[2.0, 2.0, 6.0], [8.0, 2.0, 6.0], [8.0, 6.0, 6.0], [2.0, 6.0, 6.0]]],
                            enabled=enabled)
        o.contours3d_pl = mill3d.zone_frame(self.doc, mill3d.model_path(self.doc, o))
        s.operations.append(o)
        cp.save(s)
        return o

    def test_zone_shown_then_replaced(self):
        o = self.add_flipped()
        self.show('-Z|-1')
        p = self.p
        shown = p._zone_loops_shown(o)
        self.assertFalse(np.allclose(np.asarray(shown), np.asarray(o.contours3d)))   # dans la prise retournée
        p.show_zone(o)
        back = p.loops_in_drawing()                                               # « Remplacer la zone »
        self.assertTrue(np.allclose(np.asarray(back), np.asarray(o.contours3d), atol=1e-6))

    def test_loose_paths_only_in_drawing_setup(self):
        self.add_flipped()
        te = model.Toolpath('', '', [model.Move('feed', 0, 0, 0), model.Move('feed', 5, 0, 0)], name='TE')
        self.cp.display(list(self.cp.toolpaths) + [te])
        self.show('-Z|-1')
        self.assertNotIn(te, self.p.view.model_paths)
        self.show('|-1')
        self.assertIn(te, self.p.view.model_paths)


if __name__ == '__main__':
    unittest.main()
