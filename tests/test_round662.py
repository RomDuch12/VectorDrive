"""Round 662 : relecture de 661. Une pièce 3D centrée sur la plaque (ou
dans son coin) la suit sans relire le STEP : les objets de sa vue sont
déplacés, pas recréés (les opérations qui les désignent les gardent), et
l'ajustement de la composition ne les met plus à l'échelle ; message juste
(décalage, ou « Ajuster la composition à la nouvelle taille » si la plaque
garde sa taille), rien si elle n'a pas bougé. Compagnon : même outil
d'abord. Parcours sans opération avant une autre prise : le bon conseil.
Opération montée ou descendue : ses parcours la suivent. Pièce du dessin
illisible : dit comme tel."""
import os
import shutil
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

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
from vectordrive.core.geom import Affine
from vectordrive.io import companion

app = QApplication.instance() or QApplication([])


class TestCompanion(unittest.TestCase):
    def test_same_tool_first(self):
        contour, cut = rect(0, 0, 10, 10, tool=0), rect(0, 0, 10, 10, tool=3)
        contour.extra = {S2.OUTLINE: True}
        a, b = rect(0, 0, 10, 10, tool=3), rect(0, 0, 10, 10, tool=0)       # VND réordonné : détourage d'abord
        L = SimpleNamespace(items=[a, b])
        companion._outlines(L, SimpleNamespace(items=[contour, cut]))
        self.assertEqual([S2.is_outline(it) for it in L.items], [False, True])   # le détourage reste usiné
        self.assertTrue(b.locked)


class TestLoose(unittest.TestCase):
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

    def test_loose_before(self):
        a, b = self.op('A'), self.op('B', '-Z')
        r = model.Operation(name='Poser', kind='instruction', instruction='retournement', params={'message': 'p'})
        s = model.CamSetup(tools=[self.tool], operations=[a, r, b])
        notes = preflight.setup_changes(self.doc, s, [self.tp(a), self.tp(r), self.te(), self.tp(b)])
        self.assertEqual([lv for lv, _t in notes], [preflight.BLOQUANT])
        self.assertIn('si « TE » vient après un retournement', notes[0][1])     # pas « ajouter un arrêt avant B »
        alone = preflight.setup_changes(self.doc, model.CamSetup(tools=[self.tool], operations=[b]),
                                        [self.te(), self.tp(b)])
        self.assertIn('sinon à la main', alone[0][1])

    def test_loose_after(self):
        a, b = self.op('A'), self.op('B', '-Z')
        s = model.CamSetup(tools=[self.tool], operations=[a, b])
        notes = preflight.setup_changes(self.doc, s, [self.tp(a), self.tp(b), self.te()])
        self.assertTrue(any('juste avant lui' in t for _lv, t in notes))


class TestNotes(unittest.TestCase):
    def test_unreadable_part(self):
        src = two_boxes_stl()
        with tempfile.TemporaryDirectory() as tmp:
            part = os.path.join(tmp, 'piece.stl')
            shutil.copy(src, part)
            doc = Document()
            doc.source_path, doc.source_format = part, 'stl'
            L = S2.add_layer(doc, S2.pose(doc, part, [faces(part)['x20']]))
            L.items.append(rect(2, 2, 2, 1, tool=L.tool))
            with mock.patch.object(S2, 'placement_of', lambda doc, d: None):    # lecture de la pièce en échec
                notes = [t for _lv, t in preflight.surface_notes(doc, model.CamSetup())]
        self.assertTrue(any('pas pu être rapportée à la pièce du dessin' in t for t in notes))
        self.assertFalse(any('autre pièce' in t for t in notes))


@unittest.skipUnless(__import__('vectordrive.core.solids', fromlist=['x']).available(), 'manifold3d absent')
class TestWindow(unittest.TestCase):
    setUp, tearDown = R657.TestWindow.setUp, R657.TestWindow.tearDown

    def view(self):
        v = rect(10, 10, 5, 5)
        v.extra = {'step': True}                                                  # objet de la vue STEP
        self.doc.layers[0].items.append(v)
        return v

    def find(self, v):
        return next(it for L in self.doc.layers for it in L.items if it.id == v.id)

    def test_paths_follow_moved_op(self):
        cp = self.cp
        un, deux = [tp for tp in cp.toolpaths if tp.moves]
        te = model.Toolpath('', '', [model.Move('feed', 0, 0, 0)], name='TE')
        te.shown = True
        cp.display([un, te, deux])
        cp.ops.selectRow(0)
        cp.move_op(1)                                                             # « Un » descendue
        self.assertEqual([tp.op_id for tp in cp.toolpaths], [deux.op_id, '', un.op_id])

    def test_view_moved_not_reread(self):
        w, doc = self.w, self.doc
        doc.plate = Plate(x=0, y=0, width=100, height=100)
        w.place_model3d(placement=P3.Placement('+Z', 0.0, 'centre'))
        v = self.view()
        w.apply_plate(Plate(x=0, y=0, width=200, height=100))
        moved = self.find(v)                                                      # le même objet
        self.assertAlmostEqual(moved.bbox()[0] - v.bbox()[0], 50.0, delta=1e-6)
        self.assertIn('décalée de +50.00 mm en X', w.statusBar().currentMessage())
        w.undo()
        self.assertAlmostEqual(self.find(v).bbox()[0], v.bbox()[0], delta=1e-6)
        w.apply_plate(Plate(x=10, y=0, width=100, height=100))                   # même taille : l'ajustement suit
        self.assertIn('à la nouvelle taille', w.statusBar().currentMessage())

    def test_corner_widened_not_moved(self):
        w, doc = self.w, self.doc
        doc.plate = Plate(x=0, y=0, width=100, height=100)
        w.place_model3d(placement=P3.Placement('+Z', 0.0, 'coin'))
        before = P3.of(doc)
        w.statusBar().clearMessage()
        w.apply_plate(Plate(x=0, y=0, width=200, height=100))
        self.assertEqual((P3.of(doc).dx, P3.of(doc).dy), (before.dx, before.dy))
        self.assertNotIn('a suivi', w.statusBar().currentMessage())

    def test_adjust_leaves_view_to_part(self):
        w, doc = self.w, self.doc
        doc.plate = Plate(x=0, y=0, width=100, height=100)
        w.place_model3d(placement=P3.Placement('+Z', 0.0, 'centre'))
        v = self.view()
        w.apply_plate(Plate(x=0, y=0, width=200, height=200), Affine(2, 0, 0, 2, 0, 0))
        b0, b1 = v.bbox(), self.find(v).bbox()
        self.assertAlmostEqual(b1[2] - b1[0], b0[2] - b0[0], delta=1e-6)          # pas mis à l'échelle
        self.assertAlmostEqual(b1[0] - b0[0], 50.0, delta=1e-6)                   # déplacé avec la pièce


if __name__ == '__main__':
    unittest.main()
