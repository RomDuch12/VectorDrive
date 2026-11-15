"""Round 659 : relecture de 658. Pièce 3D d'à côté prise puis enregistrée :
les surfaces posées restent sur elle (leur contenu ne suit plus un
placement par défaut) ; pièce qui n'est plus celle du dessin : rien ne
bouge ; opération sur un autre fichier du même nom pas remise sur la pièce
du dessin ; modèle de dessin sans surfaces posées ; un contour remarqué par
contour au retour d'un VND ; parcours sans opération (TypeEdit) sur la
prise du dessin pour les arrêts, gardés à leur place quand un arrêt est
ajouté ; arrêt fait à la main respecté."""
import copy
import os
import shutil
import tempfile
import unittest
import weakref
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_CAM_TEMPLATES', os.path.join(tempfile.mkdtemp(), 'modeles_fao'))

from PySide6.QtWidgets import QApplication

from tests import test_round657 as R657
from tests.test_round596 import two_boxes_stl
from tests.test_round649 import rect
from tests.test_round653 import Base, faces
from vectordrive.cam import model, preflight
from vectordrive.core import placement3d as P3
from vectordrive.core import surface2d as S2
from vectordrive.core.document import Document, Plate
from vectordrive.io import model3d, native

app = QApplication.instance() or QApplication([])


class TestPart(Base):
    def posed(self, part):
        doc = Document()
        doc.source_path, doc.source_format = part, 'stl'
        doc.extra[P3.KEY] = P3.to_dict(P3.Placement('-Z', 90.0, 'centre'))
        doc.plate = Plate(x=0, y=0, width=100, height=100)
        L = S2.add_layer(doc, S2.pose(doc, part, [faces(part)['x20']]))
        L.items.append(rect(2, 2, 2, 1, tool=L.tool))
        return doc, L

    def test_relinked_part_saved(self):
        with tempfile.TemporaryDirectory() as tmp:
            f1 = os.path.join(tmp, 'F1')
            os.makedirs(f1)
            part = os.path.join(f1, 'piece.stl')
            shutil.copy(self.path, part)
            doc, L = self.posed(part)
            native.write_atomic(doc, os.path.join(f1, 'd.vdz'))
            f2 = os.path.join(tmp, 'F2')
            shutil.copytree(f1, f2)                                               # dossier de travail copié
            a = native.read(os.path.join(f2, 'd.vdz'))
            self.assertTrue(model3d.twin_note(a))
            native.write_atomic(a, os.path.join(f2, 'd.vdz'))                    # enregistré : garde F2
            b = native.read(os.path.join(f2, 'd.vdz'))
            self.assertIsNone(model3d.twin_note(b))
            M = next(x for x in b.layers if x.id == L.id)
            d = S2.of_layer(M)
            self.assertTrue(os.path.normcase(d['path']).startswith(os.path.normcase(f1)))   # chemin gardé : l'ancien
            self.assertEqual(S2.part_of(b, d), model3d.source_of(b))
            self.assertEqual(S2.placement_of(b, d), S2.placement_of(doc, S2.of_layer(L)))
            self.assertFalse(S2.stale(b, M))
            self.assertEqual(S2.follow(b), 0)                                     # le contenu ne bouge pas
            self.assertEqual(S2.layer_key(b, M), S2.layer_key(doc, L))

    def test_other_part_does_not_move(self):
        with tempfile.TemporaryDirectory() as tmp:
            part = os.path.join(tmp, 'piece.stl')
            shutil.copy(self.path, part)
            doc, L = self.posed(part)
            other = os.path.join(tmp, 'autre.stl')
            shutil.copy(self.path, other)
            L.extra = {**L.extra, S2.KEY: {**S2.of_layer(L), 'path': other}}    # plus la pièce du dessin
            self.assertIsNone(S2.placement_of(doc, S2.of_layer(L)))
            doc.plate = Plate(x=0, y=0, width=200, height=100)
            self.assertEqual(S2.follow(doc), 0)

    def test_template_without_surfaces(self):
        from vectordrive.io import doc_templates as DT
        L, _e = self.surface('x20')
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {'VECTORDRIVE_DOC_TEMPLATES': tmp}):
            back = native.read(str(DT.save(self.doc, 'modèle')))
        M = next(x for x in back.layers if x.id == L.id)
        self.assertIsNone(S2.of_layer(M))
        self.assertEqual([x.id for x in S2.lost(back)], [L.id])                   # signalé, pas usiné à côté
        self.assertIsNotNone(S2.of_layer(L))                                      # le dessin garde la sienne

    def test_companion_one_for_one(self):
        from vectordrive.io import companion, vnd
        from vectordrive.io.vnd_write import write
        L, _e = self.surface('x20')
        outline = next(it for it in L.items if S2.is_outline(it))
        cut = copy.deepcopy(outline)                                              # détourage tracé sur le bord
        cut.id, cut.extra, cut.locked = 'detourage658', {}, False
        L.items.append(cut)
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'p.vnd')
            write(self.doc, f)
            companion.sync(self.doc, f)
            back = vnd.read(f)
            companion.apply(back, f)
        M = next(x for x in back.layers if x.id == L.id)
        self.assertEqual(len([it for it in M.items if S2.is_outline(it)]), 1)
        self.assertEqual(len([it for it in M.items if not S2.is_outline(it)]), 2)   # gravure et détourage


class TestLoose(unittest.TestCase):
    def setUp(self):
        self.path = two_boxes_stl()
        self.doc = Document()
        self.doc.source_path = self.path
        self.tool = model.CamTool(kind='fraise', diameter=1.0, name='F1', spindle=10000)

    def op(self, name, face='', body=-1):
        return model.Operation(kind='gravure', name=name, tool_id=self.tool.id, setup_face=face, body3d=body,
                               model_path=self.path)

    def tp(self, o):
        if o.kind == 'instruction':
            return model.Toolpath(o.id, '', [], name=o.name)
        return model.Toolpath(o.id, self.tool.id, [model.Move('feed', 1, 1, -0.5)], name=o.name)

    def te(self):
        return model.Toolpath('', '', [model.Move('feed', 0, 0, 0)], name='TE')

    def stop(self, face, body=-1):
        return model.Operation(name='Poser', kind='instruction', instruction='retournement',
                               params={'message': 'Poser', 'park': True, 'setup': [face, body]})

    def test_loose_is_drawing_setup(self):
        b = self.op('B', '-Z')
        s = model.CamSetup(tools=[self.tool], operations=[b])
        notes = preflight.setup_changes(self.doc, s, [self.tp(b), self.te()])
        self.assertEqual([lv for lv, _t in notes], [preflight.BLOQUANT])
        self.assertIn('« TE »', notes[0][1])
        self.assertEqual(preflight.add_stops(self.doc, model.CamSetup.from_dict(s.to_dict()),
                                             [self.tp(b), self.te()]), [])         # à remettre à la main

    def test_loose_after_stop(self):
        a, b = self.op('A'), self.op('B', '-Z')
        st = self.stop('-Z')
        s = model.CamSetup(tools=[self.tool], operations=[a, st, b])
        notes = preflight.stop_notes(self.doc, s, [self.tp(a), self.tp(st), self.te(), self.tp(b)])
        self.assertEqual([lv for lv, _t in notes], [preflight.BLOQUANT])
        self.assertIn('« TE »', notes[0][1])

    def test_hand_stop_after(self):
        a, c = self.op('A'), self.op('C', '+X')
        st = self.stop('-Z')
        hand = model.Operation(name='Main', kind='instruction', instruction='retournement', params={'message': 'm'})
        s = model.CamSetup(tools=[self.tool], operations=[a, st, hand, c])
        self.assertEqual(preflight.stop_notes(self.doc, s, [self.tp(o) for o in s.operations]), [])
        q = model.Operation(name='Question', kind='instruction', instruction='question', params={'message': '?'})
        s = model.CamSetup(tools=[self.tool], operations=[a, st, q, c])                # 660 : une question
        notes = preflight.stop_notes(self.doc, s, [self.tp(o) for o in s.operations])  # ne pose pas la pièce
        self.assertEqual([lv for lv, _t in notes], [preflight.BLOQUANT])

    def test_body_only(self):
        a, b = self.op('A'), self.op('B', '-Z')
        st = self.stop('-Z', 1)
        s = model.CamSetup(tools=[self.tool], operations=[a, st, b])
        notes = preflight.stop_notes(self.doc, s, [self.tp(o) for o in s.operations])
        self.assertEqual([lv for lv, _t in notes], [preflight.ATTENTION])

    def test_bad_setup_param(self):
        a, b = self.op('A'), self.op('B', '-Z')
        for bad in (None, 'x', ['-Z'], ['-Z', float('inf')], {'a': 1}):
            st = self.stop('-Z')
            st.params['setup'] = bad
            s = model.CamSetup(tools=[self.tool], operations=[a, st, b])
            self.assertEqual(preflight.stop_notes(self.doc, s, [self.tp(o) for o in s.operations]), [])
        st.params = ['pas un dict']
        self.assertEqual(preflight.stop_notes(self.doc, s, [self.tp(o) for o in s.operations]), [])


@unittest.skipUnless(__import__('vectordrive.core.solids', fromlist=['x']).available(), 'manifold3d absent')
class TestWindow(unittest.TestCase):
    setUp, tearDown = R657.TestWindow.setUp, R657.TestWindow.tearDown

    def labels(self):
        ops = {o.id: o for o in self.cp.setup().operations}
        return [('ARRÊT' if ops[tp.op_id].kind == 'instruction' else ops[tp.op_id].name) if tp.op_id else tp.name
                for tp in self.cp.toolpaths]

    def test_stop_lands_after_loose(self):
        cp = self.cp
        te = model.Toolpath('', '', [model.Move('feed', 0, 0, 0)], name='TE')
        te.shown = True
        un, deux = [tp for tp in cp.toolpaths if tp.moves]
        cp.display([un, te, deux])
        s = cp.setup()
        st = model.Operation(name='Poser', kind='instruction', instruction='retournement', params={'message': 'p'})
        s.operations.insert(1, st)
        cp.save(s)
        cp.compute_op(st)
        self.assertEqual(self.labels(), ['Un', 'TE', 'ARRÊT', 'Deux'])          # le parcours TypeEdit avant

    def test_memo_other_document(self):
        cp = self.cp
        self.assertIsNotNone(cp._memo('_computed'))
        other = Document()
        cp._computed = {id(cp.doc): (weakref.ref(other), {'x'})}                  # adresse resservie
        self.assertIsNone(cp._memo('_computed'))


if __name__ == '__main__':
    unittest.main()
