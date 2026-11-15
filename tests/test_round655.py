"""Round 655 : arrêts entre les prises ajoutés en un clic — instruction
« Retournement de la pièce » avant chaque usinage de la pièce tournée
autrement, depuis la vérification avant l'écriture ; vérification coupée,
l'arrêt qui manque est quand même signalé."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from tests.test_round596 import two_boxes_stl
from tests.test_round649 import rect
from vectordrive.cam import model, preflight
from vectordrive.core.document import Document

app = QApplication.instance() or QApplication([])


class TestAddStops(unittest.TestCase):
    def setUp(self):
        self.path = two_boxes_stl()
        self.doc = Document()
        self.doc.source_path = self.path
        self.tool = model.CamTool(kind='fraise', diameter=1.0, name='F1', spindle=10000)

    def run_ops(self, *ops):
        s = model.CamSetup(tools=[self.tool], operations=list(ops))
        tps = [model.Toolpath(o.id, '', [], name=o.name) if o.kind == 'instruction' else       # arrêts écrits aussi
               model.Toolpath(o.id, self.tool.id, [model.Move('feed', 1, 1, -0.5)], name=o.name) for o in ops]
        return s, tps

    def op(self, name, face='', body=-1):
        return model.Operation(kind='gravure', name=name, tool_id=self.tool.id, setup_face=face, body3d=body,
                               model_path=self.path)

    def test_inserted_before_turned(self):
        a, b, c = self.op('A'), self.op('B', '-Z'), self.op('C', '+X')
        s, tps = self.run_ops(a, b, c)
        added = preflight.add_stops(self.doc, s, tps)
        self.assertEqual(len(added), 2)
        self.assertEqual([o.name for o in s.operations],
                         ['A', 'Poser la pièce : dessous vers l\'outil', 'B', 'Poser la pièce : côté +X vers l\'outil', 'C'])
        self.assertTrue(all(o.instruction == 'retournement' and o.params['park'] for o in added))
        _s, tps = self.run_ops(*s.operations)                                  # parcours des arrêts calculés
        self.assertEqual(preflight.setup_changes(self.doc, s, tps), [])
        self.assertEqual(preflight.add_stops(self.doc, s, tps), [])            # déjà là : rien de plus

    def test_texts(self):
        a, b, back = self.op('A'), self.op('B', '-Z'), self.op('C')
        s, tps = self.run_ops(a, b, back)
        self.assertEqual([o.name for o in preflight.add_stops(self.doc, s, tps)],
                         ['Poser la pièce : dessous vers l\'outil', 'Poser la pièce comme le dessin'])
        from vectordrive.cam import auto3d as A
        self.assertEqual(A.pose_text('la pièce', 'n:0.6,0,0.8'), 'Poser la pièce sur sa face d\'appui choisie')

    def test_blocking_first(self):
        r = preflight.Report()
        r.notes = [(preflight.INFO, 'pour information'), (preflight.BLOQUANT, 'arrêt qui manque')]
        h = preflight.summary_html(r)
        self.assertLess(h.index('arrêt qui manque'), h.index('pour information'))
        self.assertLess(h.index('pour information'), h.index('<table>'))     # avant les chiffres
        from PySide6.QtWidgets import QLabel
        from vectordrive.ui.preflight_dialog import PreflightDialog
        dlg = PreflightDialog(None, r)
        self.assertIsNone(dlg.stops_btn)
        self.assertIn('1 point(s) bloquant(s)', ' '.join(w.text() for w in dlg.findChildren(QLabel)))

    def test_body_and_kept(self):
        a, e = self.op('A'), self.op('E', '-Z', 0)
        s, tps = self.run_ops(a, e)
        self.assertEqual([o.params['message'] for o in preflight.add_stops(self.doc, s, tps)],
                         ['Poser le corps 1 : dessous vers l\'outil'])
        c = self.op('C', '', 1)                                                 # autre corps, même face : laissé
        s, tps = self.run_ops(a, c)
        self.assertEqual(preflight.add_stops(self.doc, s, tps), [])
        self.assertEqual(len(s.operations), 2)
        off = self.op('B', '-Z')
        off.enabled = False                                                     # désactivée : pas d'arrêt
        s, tps = self.run_ops(a, off)
        self.assertEqual(preflight.add_stops(self.doc, s, tps), [])


class TestWindow(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.settings.setValue('fao/verifier', True)                 # quel que soit l'essai d'avant
        self.w.open_path(two_boxes_stl())
        cp = self.cp = self.w.cam_panel
        doc = self.w.canvas.doc
        ground = doc.layers[0]
        m1, m2 = rect(1, 1, 5, 3, tool=ground.tool), rect(8, 1, 4, 2, tool=ground.tool)
        ground.items += [m1, m2]
        s = cp.setup()
        t = model.CamTool(kind='fraise', diameter=1.0, name='F1', number=1, spindle=10000)
        s.tools.append(t)
        s.operations = [model.Operation(kind='gravure', name='Dessus', tool_id=t.id, items=[m1.id], depth=0.2),
                        model.Operation(kind='gravure', name='Dessous', tool_id=t.id, items=[m2.id], depth=0.2,
                                        setup_face='-Z')]
        cp.save(s)
        self.tps = cp.compute()
        self.assertEqual(len([tp for tp in self.tps if tp.moves]), 2)

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_button(self):
        cp = self.cp
        self.assertTrue(cp.preflight(self.tps, exec_dialog=False))
        dlg = cp.last_preflight
        self.assertIsNotNone(dlg.stops_btn)
        dlg.stops_btn.click()
        self.assertEqual(len(dlg.stops_added), 1)
        ops = cp.setup().operations
        self.assertEqual([o.kind for o in ops], ['gravure', 'instruction', 'gravure'])
        self.assertIn(ops[1].id, {tp.op_id for tp in cp.checked_paths()})      # écrit au prochain programme
        self.assertEqual(preflight.setup_changes(cp.doc, cp.setup(), cp.checked_paths()), [])
        cp.preflight(cp.checked_paths(), exec_dialog=False)
        self.assertIsNone(cp.last_preflight.stops_btn)                          # plus rien ne manque
        self.w.undo()
        self.assertEqual(len(cp.setup().operations), 2)                         # annulable

    def test_guard_when_off(self):
        cp = self.cp
        self.w.settings.setValue('fao/verifier', False)
        try:
            cp.last_guard = None
            self.assertTrue(cp.preflight(self.tps, exec_dialog=False))
            box = cp.last_guard
            self.assertIsNotNone(box)
            self.assertIn('Ajouter les arrêts', [b.text() for b in box.buttons()])
            self.assertEqual(cp.add_stops(), [cp.setup().operations[1]])
            cp.last_guard = None
            cp.preflight(cp.checked_paths(), exec_dialog=False)
            self.assertIsNone(cp.last_guard)                                # rien ne manque : pas d'alerte
        finally:
            self.w.settings.setValue('fao/verifier', True)


if __name__ == '__main__':
    unittest.main()
