"""Round 661 : relecture de 660. Une question seule entre deux prises
différentes est signalée (elle ne dit pas de retourner la pièce) ; parcours
sans opération : le bon conseil ; un parcours recalculé garde l'ordre de la
liste, un arrêt ajouté va juste avant l'opération suivante ; une pièce 3D
centrée sur la plaque (ou dans son coin) la suit aussi pour la prise du
dessin ; pièce absente : une seule note ; copie d'une autre date : pas
« un autre contenu » ; opérations recalculées seules notées (mode
sélection)."""
import os
import shutil
import tempfile
import time
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_CAM_TEMPLATES', os.path.join(tempfile.mkdtemp(), 'modeles_fao'))

from PySide6.QtWidgets import QApplication

from tests import test_round657 as R657
from tests.test_round596 import two_boxes_stl
from tests.test_round649 import rect
from tests.test_round653 import faces
from vectordrive.cam import model, preflight
from vectordrive.core import placement3d as P3
from vectordrive.core import surface2d as S2
from vectordrive.core.document import Document, Plate

app = QApplication.instance() or QApplication([])


class TestStops(unittest.TestCase):
    def setUp(self):
        self.doc = Document()
        self.doc.source_path = two_boxes_stl()
        self.tool = model.CamTool(kind='fraise', diameter=1.0, name='F1')

    def op(self, name, face=''):
        return model.Operation(kind='gravure', name=name, tool_id=self.tool.id, setup_face=face,
                               model_path=self.doc.source_path)

    def tp(self, o):
        if o.kind == 'instruction':
            return model.Toolpath(o.id, '', [], name=o.name)
        return model.Toolpath(o.id, self.tool.id, [model.Move('feed', 1, 1, -0.5)], name=o.name)

    def te(self):
        return model.Toolpath('', '', [model.Move('feed', 0, 0, 0)], name='TE')

    def test_question_only(self):
        a, b = self.op('A'), self.op('B', '-Z')
        q = model.Operation(name='Contrôler ?', kind='instruction', instruction='question', params={'message': '?'})
        s = model.CamSetup(tools=[self.tool], operations=[a, q, b])
        tps = [self.tp(o) for o in s.operations]
        notes = preflight.setup_changes(self.doc, s, tps)
        self.assertEqual([lv for lv, _t in notes], [preflight.ATTENTION])
        self.assertIn('seulement une question', notes[0][1])
        self.assertEqual(preflight.add_stops(self.doc, model.CamSetup.from_dict(s.to_dict()), tps), [])
        self.assertEqual(preflight.safety(self.doc, s, tps), [])

    def test_loose_advice(self):
        a, b = self.op('A'), self.op('B', '-Z')
        s = model.CamSetup(tools=[self.tool], operations=[a, b])
        after = preflight.setup_changes(self.doc, s, [self.tp(a), self.tp(b), self.te()])
        self.assertTrue(any('le remettre dans la liste avant' in t for _lv, t in after))
        between = preflight.setup_changes(self.doc, s, [self.tp(a), self.te(), self.tp(b)])
        self.assertIn('Ajouter les arrêts', between[0][1])                       # à sa place : le bouton suffit


class TestNotes(unittest.TestCase):
    def test_missing_part_one_note(self):
        src = two_boxes_stl()
        with tempfile.TemporaryDirectory() as tmp:
            part = os.path.join(tmp, 'piece.stl')
            shutil.copy(src, part)
            doc = Document()
            doc.source_path, doc.source_format = part, 'stl'
            for face in ('x20', 'top2'):
                L = S2.add_layer(doc, S2.pose(doc, part, [faces(part)[face]]))
                L.items.append(rect(2, 2, 2, 1, tool=L.tool))
            os.remove(part)                                                       # pièce introuvable
            notes = [t for _lv, t in preflight.surface_notes(doc, model.CamSetup())]
        self.assertEqual(len([t for t in notes if 'introuvable' in t]), 1)

    def test_copy_with_other_date(self):
        src = two_boxes_stl()
        with tempfile.TemporaryDirectory() as tmp:
            f1, f2 = os.path.join(tmp, 'F1'), os.path.join(tmp, 'F2')
            os.makedirs(f1)
            os.makedirs(f2)
            old, part = os.path.join(f1, 'piece.stl'), os.path.join(f2, 'piece.stl')
            shutil.copy(src, old)
            shutil.copy(src, part)
            t = time.time() - 7200
            os.utime(part, (t, t))                                                # désarchivée, autre date
            doc = Document()
            doc.source_path, doc.source_format = part, 'stl'
            L = S2.add_layer(doc, S2.pose(doc, part, [faces(part)['x20']]))
            L.extra = {**L.extra, S2.KEY: {**S2.of_layer(L), 'path': old}}
            self.assertFalse(S2.other_part(doc, S2.of_layer(L)))


@unittest.skipUnless(__import__('vectordrive.core.solids', fromlist=['x']).available(), 'manifold3d absent')
class TestWindow(unittest.TestCase):
    setUp, tearDown = R657.TestWindow.setUp, R657.TestWindow.tearDown

    def test_manual_order_kept(self):
        cp = self.cp
        un, deux = [tp for tp in cp.toolpaths if tp.moves]
        cp.display([deux, un])                                                    # gravure avant découpe, à la main
        cp.compute_op(cp.setup().operations[0])
        self.assertEqual([tp.op_id for tp in cp.toolpaths], [deux.op_id, un.op_id])
        self.assertIn(un.op_id, cp._memo('_whole'))                               # calculée seule

    def test_centred_part_follows_plate(self):
        w = self.w
        doc = w.canvas.doc
        doc.plate = Plate(x=0, y=0, width=100, height=100)
        w.place_model3d(placement=P3.Placement('+Z', 0.0, 'centre'))
        dx0 = P3.of(doc).dx
        n = len(w._undo)
        w.apply_plate(Plate(x=0, y=0, width=200, height=100))
        self.assertAlmostEqual(P3.of(doc).dx - dx0, 50.0, delta=1e-6)             # la prise du dessin aussi
        self.assertIn('a suivi la plaque', w.statusBar().currentMessage())
        self.assertEqual(len(w._undo), n + 1)                                     # un seul pas d'annulation
        w.undo()
        self.assertAlmostEqual(P3.of(doc).dx, dx0, delta=1e-6)
        self.assertEqual(doc.plate.width, 100)


if __name__ == '__main__':
    unittest.main()
