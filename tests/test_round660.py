"""Round 660 : « Ajuster la composition » avec une pièce 3D — la fenêtre de
la plaque dit ce que l'ajustement fera au dessin posé sur la pièce (elle ne
change pas de taille ; sauf centrée sur la plaque, elle ne suit pas), et la
barre d'état le redit une fois la plaque changée. Relecture de 659 : une
question après un arrêt ajouté ne cache plus une prise différente ; un
parcours refait reprend sa place (ce qui le suivait le suit) ; parcours sans
opération à remettre à sa place (« Ajouter les arrêts » pas proposé pour
rien) ; surface rapportée à une pièce d'un autre contenu, ou plus rapportée
du tout : signalée ; objets du dernier calcul gardés (mode sélection)."""
import os
import shutil
import tempfile
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
from vectordrive.core.geom import Affine

app = QApplication.instance() or QApplication([])


class TestSurfaceNotes(unittest.TestCase):
    def test_other_part_and_unknown(self):
        src = two_boxes_stl()
        with tempfile.TemporaryDirectory() as tmp:
            f1, f2 = os.path.join(tmp, 'F1'), os.path.join(tmp, 'F2')
            os.makedirs(f1)
            os.makedirs(f2)
            old, part = os.path.join(f1, 'piece.stl'), os.path.join(f2, 'piece.stl')
            shutil.copy(src, part)
            doc = Document()
            doc.source_path, doc.source_format = part, 'stl'
            L = S2.add_layer(doc, S2.pose(doc, part, [faces(part)['x20']]))
            L.items.append(rect(2, 2, 2, 1, tool=L.tool))
            s = model.CamSetup()
            self.assertEqual(preflight.surface_notes(doc, s), [])
            with open(old, 'wb') as fh:
                fh.write(b'autre revision')                                       # même nom, autre contenu
            L.extra = {**L.extra, S2.KEY: {**S2.of_layer(L), 'path': old}}
            notes = preflight.surface_notes(doc, s)
            self.assertEqual([lv for lv, _t in notes], [preflight.ATTENTION])
            self.assertIn('pas le même contenu', notes[0][1])
            other = os.path.join(f2, 'autre.stl')
            shutil.copy(src, other)
            L.extra = {**L.extra, S2.KEY: {**S2.of_layer(L), 'path': other}}    # plus la pièce du dessin
            notes = preflight.surface_notes(doc, s)
            self.assertTrue(any('autre pièce que celle du dessin' in t for _lv, t in notes))


class TestLooseText(unittest.TestCase):
    def test_loose_text(self):
        doc = Document()
        doc.source_path = two_boxes_stl()
        t = model.CamTool(kind='fraise', diameter=1.0, name='F1')
        b = model.Operation(kind='gravure', name='B', tool_id=t.id, setup_face='-Z', model_path=doc.source_path)
        s = model.CamSetup(tools=[t], operations=[b])
        tb = model.Toolpath(b.id, t.id, [model.Move('feed', 1, 1, -0.5)], name='B')
        te = model.Toolpath('', '', [model.Move('feed', 0, 0, 0)], name='TE')
        notes = preflight.setup_changes(doc, s, [tb, te])
        self.assertIn('le remettre dans la liste avant', notes[0][1])


@unittest.skipUnless(__import__('vectordrive.core.solids', fromlist=['x']).available(), 'manifold3d absent')
class TestPanel(unittest.TestCase):
    setUp, tearDown = R657.TestWindow.setUp, R657.TestWindow.tearDown

    def test_recomputed_op_keeps_place(self):
        cp = self.cp
        te = model.Toolpath('', '', [model.Move('feed', 0, 0, 0)], name='TE')
        te.shown = True
        un, deux = [tp for tp in cp.toolpaths if tp.moves]
        cp.display([un, te, deux])
        cp.compute_op(cp.setup().operations[0])                                   # « Un » validé de nouveau
        self.assertEqual([tp.name if not tp.op_id else 'op' for tp in cp.toolpaths], ['op', 'TE', 'op'])
        self.assertEqual(cp.toolpaths[0].op_id, un.op_id)

    def test_no_useless_add_button(self):
        cp = self.cp
        s = cp.setup()
        s.operations[1].setup_face = '-Z'                                         # « Deux » sur la pièce retournée
        cp.save(s)
        tps = cp.compute()
        te = model.Toolpath('', '', [model.Move('feed', 0, 0, 0)], name='TE')
        te.shown = True
        stop = model.Operation(name='Poser', kind='instruction', instruction='retournement', params={'message': 'p'})
        s = cp.setup()
        s.operations.insert(1, stop)
        cp.save(s)
        tstop = model.Toolpath(stop.id, '', [], name='Poser')
        tstop.shown = True
        live = [tps[0], tstop, tps[1], te]                                        # TE après la prise retournée
        self.assertTrue(any('le remettre dans la liste' in t for t in preflight.safety(self.doc, s, live)))
        cp.preflight(live, exec_dialog=False)
        self.assertIsNone(cp.last_preflight.stops_btn)                            # il n'en ajouterait aucun

    def test_only_remembered(self):
        cp = self.cp
        self.assertEqual(cp._memo('_only'), ('couleur', None))


class TestNote(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_no_part(self):
        self.assertIsNone(self.w.adjust_part_note())

    def test_modes(self):
        w = self.w
        w.open_path(two_boxes_stl())
        doc = w.canvas.doc
        self.assertIn('ne suit pas', w.adjust_part_note())                       # position du fichier
        doc.extra[P3.KEY] = P3.to_dict(P3.Placement('+Z', 0.0, 'coin'))
        self.assertIn('suit la plaque', w.adjust_part_note())                    # 661 : elle suit vraiment
        doc.extra[P3.KEY] = P3.to_dict(P3.Placement('+Z', 0.0, 'centre'))
        self.assertIn('ne change pas de taille', w.adjust_part_note())

    def test_dialog_and_status(self):
        from vectordrive.ui.main_window import PlateDialog
        w = self.w
        w.open_path(two_boxes_stl())
        doc = w.canvas.doc
        doc.plate = Plate(x=0, y=0, width=100, height=100)
        dlg = PlateDialog(doc.plate, w, settings=w.settings, drawing_bbox=doc.bbox(),
                          part_note=w.adjust_part_note())
        self.assertIsNotNone(dlg.part_note)
        self.assertFalse(dlg.part_note.isVisibleTo(dlg))                        # rien tant qu'on n'ajuste pas
        dlg.adjust.setChecked(True)
        self.assertTrue(dlg.part_note.isVisibleTo(dlg))
        self.assertIsNone(PlateDialog(doc.plate, w, settings=w.settings).part_note)
        w.apply_plate(Plate(x=0, y=0, width=200, height=200), Affine(2, 0, 0, 2, 0, 0))
        self.assertIn('ne suit pas', w.statusBar().currentMessage())


if __name__ == '__main__':
    unittest.main()
