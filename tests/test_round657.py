"""Round 657 : relecture 655-656. Parcours d'une opération désactivée ou
supprimée plus écrits ; arrêt placé juste après la prise d'avant (avant un
palpage de la suivante) ; pièce 3D gardée par le .vdz, l'onglet dupliqué et
le compagnon d'un VND (prises, surfaces posées) ; parcours recalculés quand
une surface a suivi la pièce hors du panneau FAO, décochés gardés ;
vérification coupée : tout ce qui rendrait le programme faux est signalé."""
import os
import pathlib
import shutil
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_CAM_TEMPLATES', os.path.join(tempfile.mkdtemp(), 'modeles_fao'))

from PySide6.QtWidgets import QApplication

from tests.test_round596 import two_boxes_stl
from tests.test_round649 import rect
from tests.test_round653 import Base, faces
from vectordrive.cam import mill3d, model, preflight
from vectordrive.core import placement3d as P3
from vectordrive.core import surface2d as S2
from vectordrive.core.document import Plate
from vectordrive.io import model3d, native

app = QApplication.instance() or QApplication([])


class TestStops(unittest.TestCase):
    def setUp(self):
        from vectordrive.core.document import Document
        self.path = two_boxes_stl()
        self.doc = Document()
        self.doc.source_path = self.path
        self.tool = model.CamTool(kind='fraise', diameter=1.0, name='F1', spindle=10000)

    def op(self, name, face=''):
        return model.Operation(kind='gravure', name=name, tool_id=self.tool.id, setup_face=face,
                               model_path=self.path)

    def tp(self, o):
        if o.kind == 'instruction':
            return model.Toolpath(o.id, '', [], name=o.name)
        return model.Toolpath(o.id, self.tool.id, [model.Move('feed', 1, 1, -0.5)], name=o.name)

    def test_after_previous_setup(self):
        a, b = self.op('A'), self.op('B', '-Z')
        probe = model.Operation(kind='instruction', name='Palpage', instruction='message', params={'message': 'p'})
        s = model.CamSetup(tools=[self.tool], operations=[a, probe, b])
        added = preflight.add_stops(self.doc, s, [self.tp(o) for o in s.operations])
        self.assertEqual(len(added), 1)
        self.assertEqual([o.name for o in s.operations], ['A', added[0].name, 'Palpage', 'B'])   # palpage retourné

    def test_moved_paths(self):
        a, b = self.op('A'), self.op('B', '-Z')
        s = model.CamSetup(tools=[self.tool], operations=[a, b])
        added = preflight.add_stops(self.doc, s, [self.tp(b), self.tp(a)])        # parcours déplacés à la main
        self.assertEqual([o.name for o in s.operations], ['A', added[0].name, 'B'])  # ordre des opérations

    def test_post_blocking_and_safety(self):
        a = self.op('A')
        s = model.CamSetup(tools=[self.tool], operations=[a])
        w = 'BLOQUANT : arrêt « Poser » non écrit par ce post'
        r = preflight.inspect(self.doc, s, [self.tp(a)], post_warnings=[w])
        self.assertIn(w, r.blocking())
        self.assertEqual(preflight.safety(self.doc, s, [self.tp(a)], [w, 'autre chose']), [w])


class TestSource3d(Base):
    def test_vdz_keeps_part(self):
        self.doc.source_format = 'stl'
        self.doc.extra[P3.KEY] = P3.to_dict(P3.Placement('-Z', 90.0, 'centre'))
        self.doc.plate = Plate(x=0, y=0, width=100, height=100)
        L, _e = self.surface('x20')
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'piece.vdz')
            native.write_atomic(self.doc, f)
            back = native.read(f)
            self.assertEqual(back.source_path, f)
            self.assertEqual(os.path.normcase(model3d.source_of(back)), os.path.normcase(os.path.abspath(self.path)))
            self.assertTrue(mill3d._is_source(back, self.path))
            M = next(x for x in back.layers if x.id == L.id)
            self.assertFalse(S2.stale(back, M))                                  # même placement : rien ne bouge
            self.assertEqual(S2.follow(back), 0)
            moved = os.path.join(tmp, 'ailleurs')                                # rangés ensemble ailleurs
            os.makedirs(moved)
            shutil.copy(self.path, os.path.join(moved, os.path.basename(self.path)))
            back.source_path = os.path.join(moved, 'piece.vdz')
            back.extra[model3d.SOURCE_KEY] = os.path.join(tmp, 'parti', os.path.basename(self.path))
            self.assertEqual(model3d.source_of(back), os.path.join(moved, os.path.basename(self.path)))

    def test_companion_restores_layers(self):
        from vectordrive.io import companion, vnd
        from vectordrive.io.vnd_write import write
        L, engr = self.surface('x20')
        op = model.Operation(kind='gravure', name='Côté', items=[engr.id])
        S2.attach(self.doc, op, L)
        self.assertIn('surfaces posées en 2D', companion.reasons(self.doc))
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'p.vnd')
            write(self.doc, f)
            companion.sync(self.doc, f)
            back = vnd.read(f)
            companion.apply(back, f)
            M = next((x for x in back.layers if x.id == L.id), None)
            self.assertIsNotNone(M)                                              # même id : rattachements gardés
            self.assertEqual(S2.of_layer(M), S2.of_layer(L))
            self.assertIn(back.active, {x.id for x in back.layers} | {''})


@unittest.skipUnless(__import__('vectordrive.core.solids', fromlist=['x']).available(), 'manifold3d absent')
class TestWindow(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.open_path(two_boxes_stl())
        self.w._ensure_panel3d()
        self.p = self.w.panel3d
        self.assertTrue(self.p.refresh())
        cp = self.cp = self.w.cam_panel
        doc = self.doc = self.w.canvas.doc
        ground = doc.layers[0]
        self.m1, self.m2 = rect(1, 1, 5, 3, tool=ground.tool), rect(8, 1, 4, 2, tool=ground.tool)
        ground.items += [self.m1, self.m2]
        s = cp.setup()
        self.t = model.CamTool(kind='fraise', diameter=1.0, name='F1', number=1, spindle=10000)
        s.tools.append(self.t)
        s.operations = [model.Operation(kind='gravure', name='Un', tool_id=self.t.id, items=[self.m1.id], depth=0.2),
                        model.Operation(kind='gravure', name='Deux', tool_id=self.t.id, items=[self.m2.id],
                                        depth=0.2)]
        cp.save(s)
        self.assertEqual(len([tp for tp in cp.compute() if tp.moves]), 2)

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def names(self, tps):
        ops = {o.id: o.name for o in self.cp.setup().operations}
        return [ops.get(tp.op_id, tp.op_id or '—') for tp in tps if tp.moves or not tp.op_id]

    def test_disabled_and_deleted_not_written(self):
        cp = self.cp
        s = cp.setup()
        s.operations[1].enabled = False
        cp.save(s)                                                               # parcours encore coché
        self.assertEqual(self.names(cp.current_paths()), ['Un'])
        s = cp.setup()
        s.operations[1].enabled = True
        del s.operations[0]                                                      # supprimée sans recalcul
        cp.save(s)
        te = model.Toolpath('', '', [model.Move('feed', 0, 0, 0)], name='TE')
        te.shown = True
        cp.toolpaths.append(te)
        self.assertEqual(self.names(cp.current_paths()), ['Deux', '—'])          # parcours sans opération gardé

    def test_recompute_after_outside_follow(self):
        cp, doc = self.cp, self.doc
        doc.extra[P3.KEY] = P3.to_dict(P3.Placement('+Z', 0.0, 'centre'))
        doc.plate = Plate(x=0, y=0, width=100, height=100)
        path = self.p.machining_path()
        L = S2.add_layer(doc, S2.pose(doc, path, [faces(path)['x20']]))
        engr = rect(2, 2, 2, 1, tool=L.tool)
        L.items.append(engr)
        s = cp.setup()
        s.operations.append(model.Operation(kind='gravure', name='Côté', tool_id=self.t.id, items=[engr.id],
                                            depth=0.2))
        cp.save(s)
        tps = cp.compute()
        side = next(tp for tp in tps if self.names([tp]) == ['Côté'])
        x0 = min(m.x for m in side.moves)
        cp.toolpaths[0].shown = False                                            # « Un » décoché
        doc.plate = Plate(x=0, y=0, width=200, height=100)                     # comme apply_plate :
        self.assertEqual(S2.follow(doc), 1)                                      # la surface suit tout de suite
        out = cp.current_paths()
        self.assertEqual(self.names(out), ['Deux', 'Côté'])                     # recalculés, « Un » toujours décoché
        side = next(tp for tp in out if self.names([tp]) == ['Côté'])
        self.assertAlmostEqual(min(m.x for m in side.moves) - x0, 50.0, delta=1e-6)   # là où est la face

    def test_duplicate_keeps_part(self):
        src = model3d.source_of(self.doc)
        self.w.duplicate_tab()
        dup = self.w.canvas.doc
        self.assertIsNot(dup, self.doc)
        self.assertIsNone(dup.source_path)
        self.assertEqual(model3d.source_of(dup), src)

    def test_guard_when_off(self):
        cp, doc = self.cp, self.doc
        self.w.settings.setValue('fao/verifier', False)
        try:
            L = S2.add_layer(doc, S2.pose(doc, self.p.machining_path(), [faces(self.p.machining_path())['x20']]))
            L.items.append(rect(2, 2, 2, 1, tool=L.tool))
            L.extra = {}                                                         # pose perdue
            cp.last_guard = None
            self.assertTrue(cp.preflight(cp.checked_paths(), ['BLOQUANT : arrêt non écrit'], exec_dialog=False))
            box = cp.last_guard
            self.assertIsNotNone(box)
            self.assertNotIn('Ajouter les arrêts', [b.text() for b in box.buttons()])   # pas d'arrêt qui manque
            self.assertIn('arrêt non écrit', box.text())
            self.assertIn('plus) une surface posée', box.text())
        finally:
            self.w.settings.setValue('fao/verifier', True)

    def test_enter_does_not_write(self):
        from PySide6.QtWidgets import QDialogButtonBox
        from vectordrive.ui.preflight_dialog import PreflightDialog
        r = preflight.Report()
        r.notes = [(preflight.BLOQUANT, 'x')]
        dlg = PreflightDialog(self.cp, r)
        bb = dlg.findChild(QDialogButtonBox)
        self.assertTrue(bb.button(QDialogButtonBox.StandardButton.Cancel).isDefault())
        self.assertFalse(bb.button(QDialogButtonBox.StandardButton.Ok).isDefault())


if __name__ == '__main__':
    unittest.main()
