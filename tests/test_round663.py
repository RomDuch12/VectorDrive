"""Round 663 : relecture de 662. Pièce 3D placée autrement depuis le calcul
(elle a suivi la plaque, replacée) : parcours refaits avant l'écriture.
Contours de sa vue groupés : ils la suivent aussi. L'ajustement de la
composition ne laisse sa vue à la pièce que si elle suit la plaque (sinon,
comme avant : la vue du STEP sert aussi de dessin). Lecture annulée : dit.
Sélection vidée. Opérations regroupées par outil : leurs parcours aussi."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_CAM_TEMPLATES', os.path.join(tempfile.mkdtemp(), 'modeles_fao'))

from PySide6.QtWidgets import QApplication

from tests import test_round657 as R657
from tests.test_round649 import rect
from vectordrive.cam import model
from vectordrive.core import placement3d as P3
from vectordrive.core.document import Group, Plate
from vectordrive.core.geom import Affine

app = QApplication.instance() or QApplication([])


def view(x=10, y=10):
    v = rect(x, y, 5, 5)
    v.extra = {'step': True}                                                      # objet de la vue STEP
    return v


@unittest.skipUnless(__import__('vectordrive.core.solids', fromlist=['x']).available(), 'manifold3d absent')
class TestWindow(unittest.TestCase):
    setUp, tearDown, names = R657.TestWindow.setUp, R657.TestWindow.tearDown, R657.TestWindow.names

    def find(self, item):
        def walk(items):
            for it in items:
                if it.id == item.id:
                    return it
                hit = walk(getattr(it, 'children', ()))
                if hit is not None:
                    return hit
            return None
        return next(hit for L in self.doc.layers for hit in [walk(L.items)] if hit is not None)

    def centred(self):
        self.doc.plate = Plate(x=0, y=0, width=100, height=100)
        self.w.place_model3d(placement=P3.Placement('+Z', 0.0, 'centre'))

    def test_paths_redone_after_follow(self):
        cp = self.cp
        self.centred()
        cp.compute()
        calls = []
        with mock.patch.object(cp, '_recompute', lambda dates=True: calls.append(1) or []):
            cp.current_paths(dates=False)
            self.assertEqual(calls, [])                                           # rien n'a bougé
            self.w.apply_plate(Plate(x=20, y=0, width=100, height=100))
            cp.current_paths(dates=False)
        self.assertEqual(calls, [1])                                              # la pièce a suivi : refaits

    def test_grouped_view_follows(self):
        self.centred()
        a, b, d = view(10, 10), view(20, 10), rect(40, 40, 4, 4)
        whole, mixed = Group(children=[a, b]), Group(children=[view(30, 30), d])
        self.doc.layers[0].items += [whole, mixed]
        part = mixed.children[0]
        self.w.apply_plate(Plate(x=0, y=0, width=200, height=200), Affine(2, 0, 0, 2, 0, 0))
        for v in (a, b, part):                                                    # déplacés avec la pièce
            got = self.find(v).bbox()
            self.assertAlmostEqual(got[0] - v.bbox()[0], 50.0, delta=1e-6)
            self.assertAlmostEqual(got[2] - got[0], 5.0, delta=1e-6)
        got = self.find(d).bbox()                                                 # le dessin : ajusté
        self.assertAlmostEqual(got[2] - got[0], 8.0, delta=1e-6)

    def test_adjust_moves_view_when_part_stays(self):
        self.doc.plate = Plate(x=0, y=0, width=100, height=100)
        v = view()
        self.doc.layers[0].items.append(v)                                        # position « fichier »
        self.w.apply_plate(Plate(x=0, y=0, width=200, height=200), Affine(2, 0, 0, 2, 0, 0))
        got = self.find(v).bbox()
        self.assertAlmostEqual(got[2] - got[0], 10.0, delta=1e-6)

    def test_cancelled_reading_said(self):
        from vectordrive.ui.progress import Cancelled
        self.centred()
        dx = P3.of(self.doc).dx

        def cancel(*a, **k):
            raise Cancelled()
        with mock.patch('vectordrive.ui.progress.run', cancel):
            self.w.apply_plate(Plate(x=0, y=0, width=200, height=100))
        self.assertIn('annulée', self.w.statusBar().currentMessage())
        self.assertEqual(P3.of(self.doc).dx, dx)

    def test_selection_cleared(self):
        self.centred()
        v = view()
        self.doc.layers[0].items.append(v)
        self.w.canvas.selection = [v]
        self.w.apply_plate(Plate(x=0, y=0, width=200, height=100))
        self.assertEqual(self.w.canvas.selection, [])

    def test_merged_ops_paths_follow(self):
        cp = self.cp
        s = cp.setup()
        t2 = model.CamTool(kind='fraise', diameter=2.0, name='F2', number=2, spindle=10000)
        s.tools.append(t2)
        s.operations[1].tool_id = t2.id
        s.operations.append(model.Operation(kind='gravure', name='Trois', tool_id=self.t.id, items=[self.m1.id],
                                            depth=0.1))
        cp.save(s)
        cp.compute()
        cp.merge_tool_ops(all_tools=True)
        ops = [o.name for o in cp.setup().operations]
        self.assertEqual(ops, ['Un', 'Trois', 'Deux'])
        self.assertEqual(self.names(cp.toolpaths), ops)
        self.w.undo()                                                             # fusion annulée : les
        ops = [o.name for o in cp.setup().operations]                             # parcours reviennent aussi
        self.assertEqual(ops, ['Un', 'Deux', 'Trois'])
        self.assertEqual(self.names(cp.current_paths(dates=False)), ops)

    def test_body_centred_counts_plate(self):
        cp = self.cp
        self.doc.plate = Plate(x=0, y=0, width=100, height=100)
        P3.set_body(self.doc, 1, P3.Placement('+Z', 0.0, 'centre'))              # corps posé à part, centré
        cp.compute()
        calls = []
        with mock.patch.object(cp, '_recompute', lambda dates=True: calls.append(1) or list(cp.toolpaths)):
            self.w.apply_plate(Plate(x=50, y=0, width=100, height=100))
            cp.current_paths(dates=False)
        self.assertEqual(calls, [1])
        self.assertIn('Parcours recalculés', self.w.statusBar().currentMessage())

    def test_first_compute_op_reference(self):
        cp = self.cp
        cp._remember('_placement_states', None)                                   # rien de calculé en entier
        cp.compute_op(cp.setup().operations[0])
        self.assertEqual(cp._memo('_placement_states'), cp._placement_state())

    def test_selection_mode_recompute_keeps_objects(self):
        cp = self.cp
        cp.set_selection_mode(True)
        try:
            self.w.canvas.selection = [self.m1]
            cp.compute()
            self.assertEqual(self.names([tp for tp in cp.toolpaths if tp.moves]), ['Un'])
            cp.compute_op(cp.setup().operations[1])                               # « Deux » sur tous ses objets
            self.w.canvas.selection = []                                          # sélection perdue depuis
            P3.set_body(self.doc, 1, P3.Placement('+Z', 0.0, 'libre', 3.0, 0.0))  # la pièce a bougé
            tps = cp.current_paths(dates=False)
            self.assertEqual(self.names([tp for tp in tps if tp.moves]), ['Un', 'Deux'])
        finally:
            cp.set_selection_mode(False)                                          # réglage gardé : remis

    def test_without_view_in_groups(self):
        from vectordrive.ui.main_window import MainWindow
        d = rect(0, 0, 1, 1)
        only, mixed = Group(children=[view(), view()]), Group(children=[view(), d])
        out = MainWindow._without_view([view(), only, mixed, d])
        self.assertEqual(len(out), 2)
        self.assertEqual([c.id for c in out[0].children], [d.id])                 # le groupe mêlé garde le dessin
        self.assertEqual(len(mixed.children), 2)                                  # sans le modifier en place


if __name__ == '__main__':
    unittest.main()
