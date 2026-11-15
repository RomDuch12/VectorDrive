"""Round 645 : chaque prise tenue à sa façon — un espace de travail par prise
(pièce retournée, corps posé seul) : gardé avec le dessin, montré dans la
vue 3D de cette prise, ses parcours vérifiés contre lui (fenêtre et
contrôle avant écriture), l'usinage auto au-dessus de ses mors."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from tests.test_round637 import path, vise
from vectordrive.cam import auto3d as A
from vectordrive.cam import model, preflight
from vectordrive.core import solids as SO
from vectordrive.core import workspace as WS
from vectordrive.core.document import Document

app = QApplication.instance() or QApplication([])

DEEP = [('rapid', -10, -5, 5), ('feed', -10, -5, -9), ('feed', 50, -5, -9)]   # dans le mors à Y -5


class TestStore(unittest.TestCase):
    def test_per_setup(self):
        doc = Document()
        main = WS.Workspace(elements=[vise()])
        WS.store(doc, main)
        self.assertEqual(len(WS.of(doc).elements), 1)
        self.assertEqual(WS.of(doc, '', 1).elements, [])                       # corps seul sans pièce : repère inconnu
        self.assertEqual(WS.of(doc, '-Z', -1).elements, [])                    # retournée : plus dans l'étau
        self.assertFalse(WS.own(doc, '-Z', -1))
        down = WS.Workspace(elements=[WS.Element('mandrin'), WS.Element('table')])
        WS.store(doc, down, '-Z', -1)
        self.assertTrue(WS.own(doc, '-Z', -1))
        self.assertEqual([e.kind for e in WS.of(doc, '-Z', -1).elements], ['mandrin', 'table'])
        self.assertEqual(list(doc.extra[WS.KEY_SETUPS]), ['-Z|-1'])
        self.assertEqual(len(WS.of(doc).elements), 1)                          # celui du dessin intact
        WS.store(doc, WS.Workspace(elements=[WS.Element('bloc')]), '', 1)
        self.assertEqual([e.kind for e in WS.of(doc, '', 1).elements], ['bloc'])
        WS.store(doc, WS.Workspace(), '-Z', -1)
        WS.store(doc, WS.Workspace(), '', 1)
        self.assertNotIn(WS.KEY_SETUPS, doc.extra)                              # vides : retirés
        self.assertEqual(WS.op_setup(model.Operation(setup_face='+X', body3d=2)), ('+X', 2))
        self.assertEqual(WS.op_setup(None), ('', -1))


class TestCollisions(unittest.TestCase):
    def setUp(self):
        self.mill = model.CamTool(kind='fraise', diameter=6, name='Fraise 6')
        self.setup = model.CamSetup(tools=[self.mill], operations=[model.Operation(id='a'),
                                                                   model.Operation(id='b', setup_face='-Z')])
        self.tps = [path(DEEP, self.mill, 'Dessus', 'a'), path(DEEP, self.mill, 'Dessous', 'b')]

    def names(self, doc):
        return sorted(h.path for h in WS.collisions_all(self.tps, self.setup, doc))

    def test_each_setup_its_own(self):
        doc = Document()
        self.assertEqual(self.names(doc), [])
        WS.store(doc, WS.Workspace(elements=[vise()]))
        self.assertEqual(self.names(doc), ['Dessus'])                           # la prise du dessin seule
        WS.store(doc, WS.Workspace(elements=[vise()]), '-Z', -1)
        self.assertEqual(self.names(doc), ['Dessous', 'Dessus'])
        WS.store(doc, WS.Workspace())
        self.assertEqual(self.names(doc), ['Dessous'])
        only = WS.collisions(self.tps, self.setup, WS.Workspace(elements=[vise()]), only=('-Z', -1))
        self.assertEqual([h.path for h in only], ['Dessous'])
        r = preflight.inspect(doc, self.setup, self.tps)
        self.assertTrue(any('Espace de travail' in t and 'Dessous' in t for t in r.blocking()), r.notes)


class TestPlan(unittest.TestCase):
    def test_floors(self):
        tools = [model.CamTool(kind='fraise', diameter=6, cut_length=30)]
        seq = A.Sequence(steps=[A.Step(kind='surface3d', tool_kind='fraise', rule='gros')])
        info = A.PartInfo(40, 20, 10, 0, 20, floor=6.0)
        out = A.plan_all(seq, tools, [], {-1: info}, groups=[(-1, ['', '-Z', '+X'])], floors={('-Z', -1): 4.0})
        ops = [(p.op.setup_face, p.jaws) for p in out if p.tool is not None]
        self.assertEqual(ops, [('', 6.0), ('-Z', 4.0), ('+X', 0.0)])            # chacune ses mors, ou aucun
        self.assertEqual(info.floor, 6.0)


class TestReview(unittest.TestCase):
    """Relecture indépendante : face du dessin, corps seul, broche, mandrin
    tourné, prises non vérifiées, STEP."""

    def setUp(self):
        from tests.test_round596 import two_boxes_stl
        self.doc = Document()
        self.doc.source_path = two_boxes_stl()               # deux corps : hauts à Z 6 et 4
        self.mill = model.CamTool(kind='fraise', diameter=6, name='Fraise 6')

    def test_drawing_face(self):
        from vectordrive.core import placement3d as P3
        doc = self.doc
        up = model.Operation(id='u', setup_face='+Z')                          # « dessus » = la prise du dessin
        self.assertEqual(WS.op_setup(up, doc), ('', -1))
        self.assertEqual(WS.op_setup(up), ('+Z', -1))                          # sans le dessin : telle quelle
        WS.store(doc, WS.Workspace(elements=[vise()]))
        self.assertEqual(len(WS.of(doc, '+Z', -1).elements), 1)
        setup = model.CamSetup(tools=[self.mill], operations=[up])
        hits = WS.collisions_all([path(DEEP, self.mill, 'Dessus', 'u')], setup, doc)
        self.assertEqual([h.path for h in hits], ['Dessus'])                   # vérifié contre l'étau
        doc.extra[P3.KEY] = P3.to_dict(P3.Placement('-Z'))                     # pièce posée retournée dans le dessin
        self.assertEqual(WS.op_setup(up, doc), ('+Z', -1))
        self.assertEqual(WS.op_setup(model.Operation(setup_face='-Z'), doc), ('', -1))
        self.assertEqual(WS.op_setup(up, Document()), ('', -1))                # volumes du dessin : « dessus »

    def test_body_frame(self):
        doc = self.doc
        main = WS.Workspace(elements=[vise()])
        WS.store(doc, main)
        z = main.elements[0].z
        self.assertAlmostEqual(WS.of(doc, '', 0).elements[0].z, z)             # corps aussi haut que la pièce
        self.assertAlmostEqual(WS.of(doc, '', 1).elements[0].z, z + 2.0)       # 2 mm plus bas : l'étau 2 mm plus haut
        f, el = WS.jaw_floor(WS.of(doc, '', 1))
        self.assertAlmostEqual(f, WS.jaw_floor(main)[0] - 2.0)
        self.assertFalse(WS.own(doc, '', 1))
        from tests.test_round596 import FakeDoc
        lost = FakeDoc(os.path.join(tempfile.mkdtemp(), 'absent.stl'))
        WS.store(lost, main)
        self.assertEqual(WS.of(lost, '', 1).elements, [])                       # repère inconnu : rien de faux

    def test_spindle_nut(self):
        sp = WS.Element('broche')
        t = model.CamTool(kind='fraise', diameter=6, stickout=20.0)
        rings = WS._rings(t, (20.0, 0.0), sp)
        self.assertIn(('broche', sp.p('nut_d') / 2, 20.0), rings)              # l'écrou de pince
        self.assertEqual(WS._rings(t, (0.0, 0.0), sp), [('outil', 3.0, 0.0)])

    def test_turned_chuck(self):
        from vectordrive.core import stock3d
        box = stock3d.StockBox(-30, -20, 30, 20, 0, -20)
        ch = WS.Element('mandrin', params={'jaws': 4})
        self.assertEqual((WS.clamp_stock(ch, box, 5).p('clamp'), WS.clamp_stock(ch, box, 5).p('clamp2')), (40, 60))
        ch.rot = 90.0
        e = WS.clamp_stock(ch, box, 5)
        self.assertEqual((e.p('clamp'), e.p('clamp2')), (60, 40))              # mors « Y » du mandrin tourné : en X

    def test_unchecked(self):
        doc = self.doc
        setup = model.CamSetup(tools=[self.mill], operations=[model.Operation(id='a'),
                                                              model.Operation(id='b', setup_face='-Z')])
        tps = [path(DEEP, self.mill, 'Dessus', 'a'), path(DEEP, self.mill, 'Dessous', 'b')]
        self.assertEqual(WS.unchecked(tps, setup, doc), [])                     # aucun espace : rien à dire
        WS.store(doc, WS.Workspace(elements=[vise(), WS.Element('broche')]))
        notes = WS.unchecked(tps, setup, doc)
        self.assertEqual(len(notes), 2, notes)
        self.assertIn('dessous', notes[1])
        self.assertIn('Fraise 6', notes[0])                                     # broche : dépassement inconnu
        r = preflight.inspect(doc, setup, tps)
        self.assertTrue(any('sans matériel' in t for lv, t in r.notes if lv == preflight.ATTENTION), r.notes)

    def test_step_vectors(self):
        import re
        from vectordrive.io import step_solids
        text = step_solids.step_text([{'kind': 'box', 'corners': [(0, 0), (10, 0), (10, 5), (0, 5)], 'z0': 0,
                                       'z1': 3, 'name': 'a\\b'}], 'essai')
        self.assertFalse(re.search(r"LINE\('',#\d+,VECTOR", text))              # VECTOR : entité à part
        self.assertTrue(re.search(r"LINE\('',#\d+,#\d+\)", text))


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestWindow(unittest.TestCase):
    def setUp(self):
        from tests.test_round591 import pocket_stl
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.open_path(pocket_stl())
        self.w._ensure_panel3d()
        self.p = self.w.panel3d
        self.p.refresh()
        self.cp = self.w.cam_panel

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_dialog_and_view(self):
        from vectordrive.core import stock3d
        cp, p = self.cp, self.p
        cp.set_stock(stock3d.Stock3D('bloc', sx=50, sy=30, sz=14, top=1))
        s = cp.setup()
        s.operations.append(model.Operation(kind='surface3d', setup_face='-Z', id='dessous'))
        cp.save(s)
        cp.toolpaths = [path(DEEP, self.mill(), 'Dessous', 'dessous'), path(DEEP, self.mill(), 'Dessus', 'x')]
        for t in cp.toolpaths:
            t.shown = True                                                     # cochés dans la liste
        p.refresh()
        p.setup_view.setCurrentIndex(p.setup_view.findData('-Z|-1'))
        self.assertEqual(p.view.fixture, (None, None))                         # retournée : sans matériel
        dlg = cp.workspace_dialog(exec_dialog=False)                           # la prise montrée
        self.assertIn('dessous', dlg.windowTitle())
        self.assertEqual([t.name for t in dlg.toolpaths], ['Dessous'])         # ses parcours seulement
        self.assertIsNotNone(dlg.box)
        dlg.add_element('etau')
        cp.set_workspace(dlg.value(), dlg.setup_key)
        self.assertEqual(list(self.w.canvas.doc.extra[WS.KEY_SETUPS]), ['-Z|-1'])
        self.assertNotIn(WS.KEY, self.w.canvas.doc.extra)                      # le dessin : rien
        self.assertIsNotNone(p.view.fixture[0])                                # montré sur cette prise
        p.setup_view.setCurrentIndex(0)
        self.assertEqual(p.view.fixture, (None, None))                         # pas sur celle du dessin
        main = cp.workspace_dialog(exec_dialog=False, setup=('', -1))
        self.assertEqual(main.windowTitle(), 'Espace de travail')
        self.assertEqual(main.ws.elements, [])
        up = cp.workspace_dialog(exec_dialog=False, setup=('+Z', -1))         # « dessus » : la prise du dessin
        self.assertEqual(up.windowTitle(), 'Espace de travail')
        self.assertEqual(up.setup_key, ('', -1))
        other = cp.workspace_dialog(exec_dialog=False, setup=('-X', -1))
        cp.set_workspace(other.value(), other.setup_key)                       # rien changé : pas de copie gardée
        self.assertEqual(list(self.w.canvas.doc.extra[WS.KEY_SETUPS]), ['-Z|-1'])

    def mill(self):
        t = model.CamTool(kind='fraise', diameter=6, name='Fraise 6')
        s = self.cp.setup()
        if not any(x.id == t.id for x in s.tools):
            s.tools.append(t)
            self.cp.save(s)
        return t


if __name__ == '__main__':
    unittest.main()
