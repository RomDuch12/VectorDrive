"""Round 656 : relecture 652-654. Calque de surface posée gardé à
l'enregistrement (sa marque était perdue : l'opération rattachée usinait le
dessin), marque refaite quand la surface suit la pièce (l'annulation
gardait la nouvelle), usinage par couleur d'une surface supprimée qui
n'usine plus le dessin entier, arrêt entre deux prises vérifié dans l'ordre
des parcours écrits, parcours recalculés avant d'écrire quand une surface a
suivi la pièce. Automatisme 3D : colonne « Outil » lisible."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_CAM_TEMPLATES', os.path.join(tempfile.mkdtemp(), 'modeles_fao'))

from PySide6.QtWidgets import QApplication

from tests.test_round596 import two_boxes_stl
from tests.test_round649 import rect
from tests.test_round653 import Base, faces
from vectordrive.cam import model, preflight, strategies
from vectordrive.core import placement3d as P3
from vectordrive.core import surface2d as S2
from vectordrive.core.document import Plate, struct_copy_layers
from vectordrive.io import native

app = QApplication.instance() or QApplication([])


class TestSaved(Base):
    def test_round_trip(self):
        L, engr = self.surface('x20')
        op = model.Operation(kind='gravure', name='Côté', items=[engr.id])
        S2.attach(self.doc, op, L)
        s = model.CamSetup(operations=[op])
        model.store(self.doc, s)
        back = native.from_dict(native.to_dict(self.doc))
        back.source_path = self.path
        M = next(x for x in back.layers if x.id == L.id)
        self.assertEqual(S2.of_layer(M), S2.of_layer(L))                       # marque de la surface gardée
        s2 = model.setup_of(back)
        self.assertEqual(S2.sync(back, s2), 0)                                  # toujours rattachée
        o = s2.operations[0]
        self.assertEqual(o.setup_face, '+X')
        self.assertIs(S2.op_layer(back, o), M)
        plain = native.to_dict(self.doc)['layers'][0]
        self.assertNotIn('extra', plain)                                        # calque ordinaire : rien de plus

    def test_lost_pose_blocks(self):
        L, engr = self.surface('x20')
        d = native.to_dict(self.doc)
        for x in d['layers']:
            x.pop('extra', None)                                                # écrit par 0.523.0 à 0.527.0
        old = native.from_dict(d)
        old.source_path = self.path
        self.assertEqual([x.id for x in S2.lost(old)], [L.id])
        r = preflight.inspect(old, model.CamSetup(), [])
        self.assertTrue(any('plus) une surface posée' in t for t in r.blocking()))
        self.assertEqual(S2.lost(self.doc), [])
        M = next(x for x in old.layers if x.id == L.id)
        M.items = [it for it in M.items if S2.is_outline(it)]                   # rien à usiner : pas bloquant
        r = preflight.inspect(old, model.CamSetup(), [])
        self.assertFalse(any('plus) une surface posée' in t for t in r.blocking()))


class TestShared(Base):
    def test_undo_copy_keeps_old_mark(self):
        self.doc.extra[P3.KEY] = P3.to_dict(P3.Placement('+Z', 0.0, 'centre'))
        self.doc.plate = Plate(x=0, y=0, width=100, height=100)
        L, _e = self.surface('x20')
        snap = struct_copy_layers(self.doc.layers)                              # pas d'annulation
        old = dict(S2.of_layer(L)['pl'])
        self.doc.plate = Plate(x=0, y=0, width=200, height=100)
        self.assertEqual(S2.follow(self.doc), 1)
        self.assertNotEqual(S2.of_layer(L)['pl'], old)
        M = next(x for x in snap if x.id == L.id)
        self.assertEqual(S2.of_layer(M)['pl'], old)                             # la copie garde la sienne


class TestOrphan(Base):
    def test_colour_op_of_deleted_surface(self):
        L, _e = self.surface('x20')
        op = model.Operation(kind='gravure', name='Couleur', sources=[L.tool])
        self.assertTrue(S2.attach(self.doc, op, L))
        s = model.CamSetup(operations=[op])
        self.doc.layers.remove(L)
        self.assertEqual(S2.sync(self.doc, s), 0)                               # gardée rattachée
        self.assertEqual(op.setup_face, '+X')
        self.assertTrue(S2.orphaned(self.doc, op))
        self.assertEqual(strategies.source_items(self.doc, op), [])            # n'usine pas le dessin
        r = preflight.inspect(self.doc, s, [])
        self.assertTrue(any('n\'existe plus' in t for _lv, t in r.notes))
        self.doc.layers.append(L)                                               # annulée : la revoilà
        self.assertFalse(S2.orphaned(self.doc, op))
        self.assertEqual(len(strategies.source_items(self.doc, op)), 1)

    def test_signature(self):
        L, _e = self.surface('x20')
        a = strategies._doc_signature(self.doc)
        L.extra = {**L.extra, S2.KEY: {**S2.of_layer(L), 'z': -9.0}}
        self.assertNotEqual(strategies._doc_signature(self.doc), a)


class TestWrittenOrder(unittest.TestCase):
    def setUp(self):
        self.path = two_boxes_stl()
        from vectordrive.core.document import Document
        self.doc = Document()
        self.doc.source_path = self.path
        self.tool = model.CamTool(kind='fraise', diameter=1.0, name='F1', spindle=10000)

    def tp(self, o):
        if o.kind == 'instruction':
            return model.Toolpath(o.id, '', [], name=o.name)
        return model.Toolpath(o.id, self.tool.id, [model.Move('feed', 1, 1, -0.5)], name=o.name)

    def test_order_of_paths(self):
        a = model.Operation(kind='gravure', name='A', tool_id=self.tool.id, model_path=self.path)
        stop = model.Operation(kind='instruction', instruction='retournement')
        b = model.Operation(kind='gravure', name='B', tool_id=self.tool.id, setup_face='-Z', model_path=self.path)
        s = model.CamSetup(tools=[self.tool], operations=[a, stop, b])
        ta, ts, tb = self.tp(a), self.tp(stop), self.tp(b)
        lv = lambda tps: [x for x, _t in preflight.setup_changes(self.doc, s, tps)]   # noqa: E731
        self.assertEqual(lv([ta, ts, tb]), [])
        self.assertEqual(lv([ta, tb]), [preflight.BLOQUANT])                     # arrêt décoché
        self.assertEqual(lv([ta, tb, ts]), [preflight.BLOQUANT])                 # parcours déplacé avant l'arrêt
        drill = model.Operation(kind='percage', name='D', tool_id=self.tool.id, setup_face='-Z')
        td = model.Toolpath(drill.id, self.tool.id, [], name='D')
        td.cycles = [{'kind': 'drill', 'x': 1, 'y': 1, 'depth': 2}]
        s.operations.append(drill)
        self.assertEqual(lv([tb, td]), [])
        self.assertEqual(lv([ta, td]), [preflight.BLOQUANT])                     # perçage : cycles seulement

    def test_add_once(self):
        a = model.Operation(kind='gravure', name='A', tool_id=self.tool.id, model_path=self.path)
        b = model.Operation(kind='gravure', name='B', tool_id=self.tool.id, setup_face='-Z', model_path=self.path)
        s = model.CamSetup(tools=[self.tool], operations=[a, b])
        ta, tb = self.tp(a), self.tp(b)
        tb2 = self.tp(b)
        self.assertEqual(len(preflight.add_stops(self.doc, s, [ta, tb, ta, tb2])), 1)   # une fois par opération


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

    def test_recompute_when_followed(self):
        w, cp = self.w, self.w.cam_panel
        doc = w.canvas.doc
        doc.extra[P3.KEY] = P3.to_dict(P3.Placement('+Z', 0.0, 'centre'))
        doc.plate = Plate(x=0, y=0, width=100, height=100)
        path = self.p.machining_path()
        L = S2.add_layer(doc, S2.pose(doc, path, [faces(path)['x20']]))
        L.items.append(rect(2, 2, 2, 1, tool=L.tool))
        def path(name):
            tp = model.Toolpath('', '', [model.Move('feed', 0, 0, 0)], name=name)    # sans opération : écrit
            tp.shown = True
            return tp
        new, old = path('refait'), path('ancien')
        cp._remember('_surface_states', S2.state(doc))                          # parcours calculés ainsi
        with mock.patch.object(cp, 'compute', return_value=[new]) as comp, \
                mock.patch.object(cp, 'checked_paths', return_value=[old]):
            self.assertEqual(cp.current_paths(), [old])                         # rien n'a bougé
            doc.plate = Plate(x=0, y=0, width=200, height=100)                 # pièce centrée : elle bouge
            self.assertEqual(cp.current_paths(), [new])
            self.assertEqual(comp.call_count, 1)
        self.assertFalse(S2.stale(doc, L))

    def test_groups_normalised(self):
        cp = self.w.cam_panel
        s = cp.setup()
        s.operations = [model.Operation(kind='gravure', name='Dessus écrit', setup_face='+Z')]
        cp.save(s)
        self.assertNotIn(('+Z', -1), self.p.setup_groups())                     # c'est la prise du dessin

    def test_auto3d_tool_column(self):
        from PySide6.QtWidgets import QHeaderView
        from vectordrive.ui.auto3d_dialog import COL_TOOL, TOOL_COL
        dlg = self.p.auto3d(exec_dialog=False, sequence='Ébauche et finition')
        hh = dlg.table.horizontalHeader()
        self.assertNotEqual(hh.sectionResizeMode(COL_TOOL), QHeaderView.ResizeMode.Stretch)
        self.assertGreaterEqual(dlg.table.columnWidth(COL_TOOL), TOOL_COL[0])
        self.assertLessEqual(dlg.table.columnWidth(COL_TOOL), TOOL_COL[1])


if __name__ == '__main__':
    unittest.main()
