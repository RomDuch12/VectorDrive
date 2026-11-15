"""Round 670 : parcours d'avant une modification du dessin ou des outils
(objet déplacé après « Calculer », outil retouché) refaits avant
l'écriture, comme ceux d'avant un placement de la pièce 3D ; pas pour un
autre post-processeur ; formulaire validé après une retouche : les autres
parcours refaits aussi ; session : à jour ou non, selon le dessin d'alors. Relecture : opération
retouchée hors de son formulaire (elle seule refaite), ajoutée (prise),
outil ajouté sans servir et opération désactivée (rien) ; empreinte
illisible : toujours refaits ; traits de « Parcours en dessin » usinés
seulement choisis, sans rendre les parcours périmés."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.cam import model, strategies
from vectordrive.core import forms as F
from vectordrive.core import geom

app = QApplication.instance() or QApplication([])


def xs(tp):
    return round(min(m.x for m in tp.moves), 3), round(max(m.x for m in tp.moves), 3)


class TestInputsChanged(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.cp = self.w.cam_panel
        self.a = F.make(F.Rect(cx=20, cy=20, width=10, height=10))
        self.b = F.make(F.Rect(cx=60, cy=20, width=10, height=10))
        self.w.canvas.doc.add(self.a)
        self.w.canvas.doc.add(self.b)
        s = self.cp.setup()
        s.tools = [model.CamTool(kind='fraise', diameter=2)]
        s.operations = [model.Operation(kind='contour', tool_id=s.tools[0].id, depth=1, items=[self.a.id]),
                        model.Operation(kind='contour', tool_id=s.tools[0].id, depth=1, items=[self.b.id])]
        self.cp.save(s)
        self.tps = self.cp.compute(dates=False)
        self.assertEqual([xs(t) for t in self.tps], [(14, 26), (54, 66)])

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def move(self, it, dx):
        self.w.canvas.select([it])
        self.w.move_by(dx, 0)

    def test_moved_object(self):
        self.assertFalse(self.cp.outdated())
        self.move(self.a, 50)
        self.assertTrue(self.cp.outdated())                                   # vue 3D : pas montrés
        tps = self.cp.current_paths(dates=False)
        self.assertEqual([xs(t) for t in tps], [(64, 76), (54, 66)])
        self.assertIn('objets', self.w.statusBar().currentMessage())
        self.assertFalse(self.cp.outdated())

    def test_undone(self):
        self.move(self.a, 50)
        self.w.undo()
        self.assertFalse(self.cp.outdated())                                  # comme au calcul
        self.assertIs(self.cp.current_paths(dates=False)[0], self.tps[0])

    def test_tool_changed_not_post(self):
        s = self.cp.setup()
        s.post = 'autre'
        s.arc_fit = 0.0
        self.cp.save(s)
        self.assertFalse(self.cp.outdated())                                  # programme seul
        s.tools[0].diameter = 4
        self.cp.save(s)
        self.assertTrue(self.cp.outdated())
        tps = self.cp.current_paths(dates=False)
        self.assertEqual([xs(t) for t in tps], [(13, 27), (53, 67)])

    def test_form_after_change(self):
        self.move(self.b, 50)
        op = self.cp.setup().operations[0]
        self.cp.compute_op(op)                                                # formulaire de la 1re validé
        self.assertTrue(self.cp.outdated())                                   # la 2e reste d'avant
        tps = self.cp.current_paths(dates=False)
        self.assertEqual([xs(t) for t in tps], [(14, 26), (104, 116)])

    def test_form_without_change(self):
        op = self.cp.setup().operations[0]
        self.cp.compute_op(op)
        self.assertFalse(self.cp.outdated())

    def test_session_memo(self):
        doc = self.w.canvas.doc
        self.assertEqual(self.cp.memo_of(doc)['_inputs_states'], 'ok')
        self.move(self.a, 50)
        memo = self.cp.memo_of(doc)
        self.assertEqual(memo['_inputs_states'], '?')
        self.cp.restore_memo(memo)
        self.assertTrue(self.cp.outdated())
        self.cp.restore_memo(dict(memo, _inputs_states='ok'))                 # à jour quand gardée : relue
        self.assertFalse(self.cp.outdated())
        old = {k: v for k, v in memo.items() if k != '_inputs_states'}
        self.cp.restore_memo(old)                                             # version d'avant : refaits
        self.assertTrue(self.cp.outdated())

    def test_op_changed_outside_form(self):
        s = self.cp.setup()
        s.operations[1].offset_add = 1.0                                      # sans compute_op (ex. habillage)
        self.cp.save(s)
        self.assertTrue(self.cp.outdated())
        tps = self.cp.current_paths(dates=False)
        self.assertEqual(strategies.LAST_RUN, {'reused': 1, 'computed': 1})   # elle seule (la dernière)
        self.assertEqual(tps[0].moves, self.tps[0].moves)
        self.assertNotEqual(xs(tps[1]), (54, 66))

    def test_unused_tool_disabled_op(self):
        s = self.cp.setup()
        s.tools.append(model.CamTool(kind='fraise', diameter=6))              # ajouté depuis un formulaire
        s.operations[1].enabled = False
        s.operations[0].name = 'Autre nom'
        self.cp.save(s)
        self.assertFalse(self.cp.outdated())
        self.assertIs(self.cp.current_paths(dates=False)[0], self.tps[0])
        s.operations[1].enabled = True                                        # réactivée : calculée avant
        self.cp.save(s)
        self.assertEqual(len(self.cp.current_paths(dates=False)), 2)
        self.assertIs(self.cp.current_paths(dates=False)[1], self.tps[1])

    def test_new_op_written(self):
        s = self.cp.setup()
        s.operations.append(model.Operation(kind='contour', tool_id=s.tools[0].id, depth=2, items=[self.a.id]))
        self.cp.save(s)
        self.assertFalse(self.cp.outdated())                                  # vue 3D : les autres montrés
        self.assertTrue(self.cp.memo_of(self.w.canvas.doc)['_inputs_states'] == '?')
        tps = self.cp.current_paths(dates=False)
        self.assertEqual(len(tps), 3)

    def test_unreadable_always_redone(self):
        self.w.canvas.doc.extra['x'] = lambda: 0                              # empreinte impossible
        self.cp.compute(dates=False)
        self.assertTrue(self.cp.outdated())
        self.assertNotEqual(self.cp._inputs_state(), self.cp._inputs_state())

    def test_tools_without_id(self):
        fao = self.w.canvas.doc.extra['fao']
        for t in fao['tools']:
            t.pop('id', None)
        self.assertEqual(self.cp._inputs_state(), self.cp._inputs_state())   # stable

    def test_drawn_paths_not_machined(self):
        s = self.cp.setup()
        s.operations.append(model.Operation(kind='contour', tool_id=s.tools[0].id, depth=1))   # toutes couleurs
        self.cp.save(s)
        tps = self.cp.compute(dates=False)
        n = len(tps[2].drawing())
        shapes = self.w.cam_to_drawing()
        self.assertTrue(shapes and all(strategies.is_drawn_path(sh) for sh in shapes))
        self.assertFalse(self.cp.outdated())
        self.assertIs(self.cp.current_paths(dates=False)[2], tps[2])          # pas refaits pour eux
        self.move(self.a, 200)                                                # loin de b
        tps = self.cp.current_paths(dates=False)
        self.assertEqual(len(tps[2].drawing()), n)                            # traits repris pas usinés
        s = self.cp.setup()
        s.operations[2].items = [shapes[0].id]                                # choisis : usinés
        self.cp.save(s)
        self.assertEqual(strategies.source_items(self.w.canvas.doc, self.cp.setup().operations[2]), [shapes[0]])


class TestContourDigest(unittest.TestCase):
    def test_digest(self):
        a = geom.Contour([geom.Line((0, 0), (1, 0)), geom.Line((1, 0), (1, 1))])
        b = geom.Contour([geom.Line((0, 0), (1, 0)), geom.Line((1, 0), (1, 1))])
        self.assertEqual(a.digest(), b.digest())
        self.assertNotEqual(a.digest(), geom.Contour(list(a.segments), True).digest())
        self.assertEqual(geom.Path([a]).digest(), geom.Path([b]).digest())


if __name__ == '__main__':
    unittest.main()
