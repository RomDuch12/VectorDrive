"""Round 658 : relecture de 657. Arrêt ajouté après toute la prise d'avant
(une opération décochée ou désactivée ne se retrouve plus derrière lui) et
arrêt qui annonce une autre prise que celle qui le suit bloquant ; pièce 3D
du même nom à côté du dessin préférée et signalée, chemins des surfaces
posées et des opérations remis sur elle ; modèles de dessin sans pièce 3D ;
contour d'une surface posée remarqué au retour d'un VND ; parcours
recalculés par document, la liste gardée comme on l'avait laissée."""
import os
import shutil
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
from tests import test_round657 as R657
from vectordrive.cam import mill3d, model, preflight
from vectordrive.core import surface2d as S2
from vectordrive.core.document import Document
from vectordrive.io import model3d, native

app = QApplication.instance() or QApplication([])


class TestStops(unittest.TestCase):
    def setUp(self):
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

    def names(self, s):
        return [o.name if o.instruction != 'retournement' else 'ARRÊT' for o in s.operations]

    def test_after_whole_previous_setup(self):
        a, x, b = self.op('A'), self.op('X'), self.op('B', '-Z')
        s = model.CamSetup(tools=[self.tool], operations=[a, x, b])
        added = preflight.add_stops(self.doc, s, [self.tp(a), self.tp(b)])        # X décochée
        self.assertEqual(self.names(s), ['A', 'X', 'ARRÊT', 'B'])                 # X reste avant l'arrêt
        self.assertEqual(added[0].params['setup'], ['-Z', -1])
        self.assertEqual(preflight.stop_notes(self.doc, s, [self.tp(o) for o in s.operations]), [])
        x2 = self.op('X2')
        x2.enabled = False
        s = model.CamSetup(tools=[self.tool], operations=[a, x2, b])
        preflight.add_stops(self.doc, s, [self.tp(a), self.tp(b)])
        self.assertEqual(self.names(s), ['A', 'X2', 'ARRÊT', 'B'])                # désactivée : pareil

    def test_misplaced_stop_blocks(self):
        a, x, b = self.op('A'), self.op('X'), self.op('B', '-Z')
        stop = model.Operation(name='Poser', kind='instruction', instruction='retournement',
                               params={'message': 'Poser', 'park': True, 'setup': ['-Z', -1]})
        s = model.CamSetup(tools=[self.tool], operations=[a, stop, x, b])
        tps = [self.tp(o) for o in s.operations]
        notes = preflight.stop_notes(self.doc, s, tps)
        self.assertEqual([lv for lv, _t in notes], [preflight.BLOQUANT])
        self.assertIn('« X »', notes[0][1])
        self.assertTrue(any('« X »' in t for t in preflight.safety(self.doc, s, tps)))
        self.assertTrue(any('« X »' in t for t in preflight.inspect(self.doc, s, tps).blocking()))
        hand = model.Operation(name='Main', kind='instruction', instruction='retournement', params={'message': 'm'})
        s.operations[1] = hand                                                    # arrêt fait à la main
        self.assertEqual(preflight.stop_notes(self.doc, s, [self.tp(o) for o in s.operations]), [])

    def test_third_setup_checked_later(self):
        a, y, b = self.op('A'), self.op('Y', '+X'), self.op('B', '-Z')
        s = model.CamSetup(tools=[self.tool], operations=[a, y, b])
        preflight.add_stops(self.doc, s, [self.tp(a), self.tp(b)])                # Y décochée
        self.assertEqual(self.names(s), ['A', 'ARRÊT', 'Y', 'B'])
        tps = [self.tp(o) for o in s.operations]                                  # Y cochée ensuite
        self.assertTrue(any('« Y »' in t for t in preflight.safety(self.doc, s, tps)))

    def test_active_without_path(self):
        a, b = self.op('A'), self.op('B')
        s = model.CamSetup(tools=[self.tool], operations=[a, b])
        ta, tb = self.tp(a), self.tp(b)
        r = preflight.inspect(self.doc, s, [ta], all_paths=[ta])
        self.assertTrue(any(lv == preflight.ATTENTION and '« B » est active' in t for lv, t in r.notes))
        tb.on = False                                                        # à l'arrêt (round 1163)
        r = preflight.inspect(self.doc, s, [ta], all_paths=[ta, tb])
        self.assertTrue(any(lv == preflight.INFO and '« B » : parcours à l\'arrêt' in t for lv, t in r.notes))
        r = preflight.inspect(self.doc, s, [ta, tb])                              # sans la liste : rien
        self.assertFalse(any('« B »' in t for _lv, t in r.notes))


class TestSource(Base):
    def test_near_preferred(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = os.path.join(tmp, 'B')
            os.makedirs(job)
            near = os.path.join(job, os.path.basename(self.path))
            shutil.copy(self.path, near)                                          # dossier copié : sa pièce
            doc = Document()
            doc.source_path = os.path.join(job, 'dessin.vdz')
            doc.extra[model3d.SOURCE_KEY] = self.path                             # l'ancienne existe encore
            self.assertEqual(os.path.normcase(model3d.source_of(doc)), os.path.normcase(near))
            note = model3d.twin_note(doc)
            self.assertIn(os.path.normcase(near), os.path.normcase(note))
            self.assertIn(os.path.normcase(self.path), os.path.normcase(note))
            self.assertTrue(any('Deux pièces 3D' in t for _lv, t in preflight.inspect(doc, model.CamSetup(), []).notes))
            self.assertEqual(model3d.resolve(doc, self.path), model3d.source_of(doc))   # surface faite avec l'ancienne
            os.remove(near)
            self.assertEqual(model3d.source_of(doc), self.path)
            self.assertIsNone(model3d.twin_note(doc))

    def test_moved_surface_path(self):
        L, _e = self.surface('x20')
        d = S2.of_layer(L)
        good, key = S2.placement_of(self.doc, d), S2.layer_key(self.doc, L)
        self.assertIsNotNone(good)
        gone = os.path.join(tempfile.mkdtemp(), 'parti', os.path.basename(self.path))    # lecteur vu autrement
        L.extra = {**L.extra, S2.KEY: {**d, 'path': gone}}
        self.assertEqual(S2.placement_of(self.doc, S2.of_layer(L)), good)
        self.assertEqual(S2.layer_key(self.doc, L), key)
        self.assertEqual(mill3d.model_path(self.doc, model.Operation(kind='surface3d', model_path=gone)), gone)  # 659
        other = os.path.join(os.path.dirname(gone), 'autre.stl')
        self.assertEqual(model3d.resolve(self.doc, other), other)                 # autre nom : laissé

    def test_template_without_part(self):
        from vectordrive.io import doc_templates as DT
        self.doc.extra[model3d.SOURCE_KEY] = self.path
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {'VECTORDRIVE_DOC_TEMPLATES': tmp}):
            f = DT.save(self.doc, 'modèle')
            back = native.read(str(f))
        self.assertNotIn(model3d.SOURCE_KEY, back.extra)
        self.assertEqual(self.doc.extra[model3d.SOURCE_KEY], self.path)          # le dessin, lui, la garde
        self.assertEqual(self.doc.source_path, self.path)

    def test_companion_outline(self):
        from vectordrive.io import companion, vnd
        from vectordrive.io.vnd_write import write
        L, _e = self.surface('x20')
        n = len([it for it in L.items if S2.is_outline(it)])
        self.assertGreater(n, 0)
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'p.vnd')
            write(self.doc, f)
            companion.sync(self.doc, f)
            back = vnd.read(f)
            self.assertFalse(any(S2.is_outline(it) for x in back.layers for it in x.items))   # le VND l'oublie
            companion.apply(back, f)
        M = next(x for x in back.layers if x.id == L.id)
        outl = [it for it in M.items if S2.is_outline(it)]
        self.assertEqual(len(outl), n)                                            # plus usiné
        self.assertTrue(all(it.locked for it in outl))
        self.assertEqual(len(M.items) - len(outl), 1)                             # la gravure, elle, non


@unittest.skipUnless(__import__('vectordrive.core.solids', fromlist=['x']).available(), 'manifold3d absent')
class TestWindow(unittest.TestCase):
    setUp, tearDown, names = R657.TestWindow.setUp, R657.TestWindow.tearDown, R657.TestWindow.names

    def test_list_kept_on_recompute(self):
        cp = self.cp
        te = model.Toolpath('', '', [model.Move('feed', 0, 0, 0)], name='TE')
        te.shown = True
        cp.display([tp for tp in cp.toolpaths if tp.moves] + [te])
        self.assertEqual(self.names(cp.toolpaths), ['Un', 'Deux', '—'])
        cp.paths.setCurrentRow(1)
        cp.move_path(-1)                                                          # Deux d'abord
        cp.paths.setCurrentRow(0)
        cp.reverse_path()                                                         # à l'envers
        cp.paths.setCurrentRow(1)
        cp.remove_path()                                                          # Un retiré
        self.assertEqual(self.names(cp.toolpaths), ['Deux', '—'])
        out = cp._recompute(dates=False)
        self.assertEqual(self.names(out), ['Un', 'Deux', '—'])
        un, deux = out[0], out[1]
        self.assertFalse(un.shown)                                                # retiré : revient décoché
        self.assertTrue(getattr(deux, 'reversed', False))
        self.assertIs(out[2], te)
        self.assertEqual(self.names(cp._writable(out)), ['Deux', '—'])
        s = cp.setup()
        s.operations.append(model.Operation(kind='gravure', name='Trois', tool_id=self.t.id, items=[self.m1.id],
                                            depth=0.1))
        cp.save(s)
        out = cp._recompute(dates=False)
        trois = next(tp for tp in out if self.names([tp]) == ['Trois'])
        self.assertTrue(trois.shown)                                              # nouvelle : cochée
        self.assertFalse(next(tp for tp in out if self.names([tp]) == ['Un']).shown)

    def test_last_surface_deleted(self):
        cp, doc = self.cp, self.doc
        path = self.p.machining_path()
        L = S2.add_layer(doc, S2.pose(doc, path, [faces(path)['x20']]))
        L.items.append(rect(2, 2, 2, 1, tool=L.tool))
        cp.compute()
        self.assertNotEqual(cp._memo('_surface_states'), ())
        doc.layers.remove(L)
        with mock.patch.object(cp, 'compute', wraps=cp.compute) as comp:
            cp.current_paths(dates=False)
        self.assertEqual(comp.call_count, 1)                                      # recalculés
        self.assertEqual(cp._memo('_surface_states'), ())

    def test_no_dates_on_recompute(self):
        cp = self.cp
        with mock.patch.object(cp, 'refresh_dates', return_value=0) as rd:
            cp._recompute(dates=False)
            cp.current_paths(dates=False)
        rd.assert_not_called()

    def test_compute_button(self):
        from PySide6.QtWidgets import QAbstractButton
        from vectordrive.i18n import tr
        cp = self.cp
        cp.clear()
        self.assertFalse([b for b in cp.findChildren(QAbstractButton) if b.text() == tr('Calculer')])
        cp.compute()                                     # round 1002 : « Calculer » n'est plus au panneau (ruban FAO)
        self.assertEqual(self.names(cp.toolpaths), ['Un', 'Deux'])


if __name__ == '__main__':
    unittest.main()
