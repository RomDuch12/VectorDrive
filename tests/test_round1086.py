"""Round 1086 (demande du 18/11 soir) : « fao : modifier un dessin qui sert à un parcours -> popup dupliquer dessin (pour
garder l'utile) ou mettre à jour les parcours concernés »."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1086.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Shape  # noqa: E402

BEFORE = 'avant : la forme clignotait seulement, rien n’était proposé'
KEY = 'fao/formes_parcours'


class Ask(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.addCleanup(self.clean)
        self.w.settings.remove(KEY)                                          # d'office : demander
        self.p = self.w.cam_panel

    def clean(self):
        g = self.w.fao_guard
        if hasattr(g, 'close_box'):
            g.close_box()
        self.w.settings.remove(KEY)
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()

    def machined(self):
        sh = Shape(path=geom.Path([geom.rect(0, 0, 20, 10)]), tool=0)
        self.w.canvas.doc.add(sh)
        self.w.canvas.select([sh])
        op = self.p.new_operation('decoupe', exec_dialog=False)
        self.assertEqual([t.op_id for t in self.p.toolpaths], [op.id])
        return sh, op

    def move(self, sh, dx=5.0):
        self.w.push_undo('Déplacer')
        sh.path = sh.path.transformed(geom.Affine.translation(dx, 0.0))
        self.w.canvas.invalidate()
        self.w.canvas.documentChanged.emit()
        app.processEvents()

    def shapes(self):
        return [it for L in self.w.canvas.doc.layers for it in L.items if isinstance(it, Shape)]

    def test_the_window_is_offered(self):
        sh, _op = self.machined()
        self.move(sh)
        box = self.w.fao_guard.box
        self.assertIsNotNone(box, BEFORE)
        self.assertFalse(box.isModal())                                      # elle ne bloque rien
        texts = [b.text() for b in box.buttons()]
        self.assertIn('Dupliquer le dessin', texts)
        self.assertIn('Mettre à jour les parcours', texts)
        self.assertTrue(self.w.canvas.flash_paths)                           # et le contour clignote

    def test_duplicate_keeps_the_original_for_the_toolpath(self):
        sh, op = self.machined()
        sid = sh.id
        self.move(sh)
        self.assertTrue(self.w.fao_guard.duplicate(self.w.fao_guard.flagged, self.w._undo[-1],
                                                   self.w._undo_pushes))
        got = self.shapes()
        self.assertEqual(len(got), 2)
        orig = next(s for s in got if s.id == sid)
        copy = next(s for s in got if s.id != sid)
        self.assertEqual(round(orig.path.bbox()[0], 6), 0.0)                 # l'original, pour le parcours
        self.assertEqual(round(copy.path.bbox()[0], 6), 5.0)                 # la forme modifiée, à part
        self.assertIn(sid, op.items)
        self.assertNotIn(copy.id, op.items)
        app.processEvents()
        self.assertIsNone(self.w.fao_guard.before)                           # pas de nouvelle alarme
        self.w.undo()                                                        # un pas : la copie repart
        got = self.shapes()
        self.assertEqual([(s.id, round(s.path.bbox()[0], 6)) for s in got], [(sid, 5.0)])

    def test_duplicate_refused_after_another_change(self):
        sh, _op = self.machined()
        self.move(sh)
        top, mark = self.w._undo[-1], self.w._undo_pushes
        self.w.push_undo('Autre')                                            # une autre commande depuis
        self.assertFalse(self.w.fao_guard.duplicate([sh.id], top, mark))
        self.assertEqual(len(self.shapes()), 1)

    def test_update_recomputes_the_toolpaths(self):
        sh, op = self.machined()
        before = self.p.toolpaths[0]
        self.move(sh)
        self.assertEqual(self.w.fao_guard.update_paths([sh.id]), 1)
        after = next(t for t in self.p.toolpaths if t.op_id == op.id)
        self.assertIsNot(after, before)
        xs = [m.x for m in after.moves if m.kind != 'rapid']
        self.assertGreater(max(xs), 24.0)                                    # le parcours suit la forme déplacée

    def test_never_ask_again(self):
        from PySide6.QtWidgets import QMessageBox
        sh, _op = self.machined()
        self.move(sh)
        box = self.w.fao_guard.box
        box.checkBox().setChecked(True)
        leave = next(b for b in box.buttons() if box.buttonRole(b) == QMessageBox.ButtonRole.RejectRole)
        leave.click()
        app.processEvents()
        self.assertEqual(self.w.settings.value(KEY), 'clignoter')


    def test_a_colour_operation_keeps_only_the_original(self):
        from vectordrive.cam import strategies as S
        sh, op = self.machined()
        s = self.p.setup()
        for o in s.operations:
            o.items, o.sources = [], [0]                                     # par couleur
        self.p.save(s)
        op = s.operations[0]
        self.assertIsNotNone(self.p.compute_op(op))
        app.processEvents()
        sid = sh.id
        self.move(sh)
        self.assertTrue(self.w.fao_guard.duplicate(self.w.fao_guard.flagged, self.w._undo[-1], self.w._undo_pushes))
        op = next(o for o in self.p.setup().operations if o.id == op.id)
        self.assertEqual(op.items, [sid], 'avant : la copie, de la même couleur, entrait dans le parcours')
        self.assertEqual([it.id for it in S.source_items(self.w.canvas.doc, op)], [sid])
        self.w.undo()                                                        # le réglage FAO revient aussi
        op = next(o for o in self.p.setup().operations if o.id == op.id)
        self.assertFalse(op.items)

    def test_in_a_group_the_copy_goes_out(self):
        from vectordrive.cam import strategies as S
        from vectordrive.core.document import Group
        a = Shape(path=geom.Path([geom.rect(0, 0, 20, 10)]), tool=0)
        b = Shape(path=geom.Path([geom.rect(0, 20, 20, 10)]), tool=0)
        g = Group(children=[a, b])
        self.w.canvas.doc.add(g)
        self.w.canvas.select([g])
        op = self.p.new_operation('decoupe', exec_dialog=False)
        self.assertEqual(op.items, [g.id])
        self.move(a)
        self.assertIn(a.id, self.w.fao_guard.flagged)
        self.assertTrue(self.w.fao_guard.duplicate(self.w.fao_guard.flagged, self.w._undo[-1], self.w._undo_pushes))
        top = [it for L in self.w.canvas.doc.layers for it in L.items]
        group = next(it for it in top if isinstance(it, Group))
        self.assertEqual([round(c.path.bbox()[0], 6) for c in group.children], [0.0, 0.0])    # l'original, dans le groupe
        loose = [it for it in top if isinstance(it, Shape)]
        self.assertEqual([round(c.path.bbox()[0], 6) for c in loose], [5.0])                   # la copie, hors du groupe
        self.assertEqual(top.index(loose[0]), top.index(group) + 1)
        self.assertNotIn(loose[0].id, {it.id for it in S.source_items(self.w.canvas.doc, op)})

    def test_refused_when_the_undone_step_is_not_the_alarm(self):
        sh, _op = self.machined()
        self.move(sh)
        self.assertFalse(self.w.fao_guard.duplicate([sh.id], self.w._undo[-1], self.w._undo_pushes,
                                                    {sh.id: 'une autre empreinte'}))
        self.assertEqual([round(s.path.bbox()[0], 6) for s in self.shapes()], [5.0])

    def test_the_window_keeps_the_keys_and_goes_away(self):
        from PySide6.QtCore import Qt
        sh, _op = self.machined()
        self.move(sh)
        box = self.w.fao_guard.box
        self.assertTrue(box.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating))
        self.assertTrue(box.testAttribute(Qt.WidgetAttribute.WA_DeleteOnClose))
        box.checkBox().setChecked(True)
        box.close()                                                          # la croix : « Ne plus demander » gardé
        app.processEvents()
        self.assertIsNone(self.w.fao_guard.box)
        self.assertEqual(self.w.settings.value(KEY), 'clignoter')
        self.assertEqual(len(self.shapes()), 1)

if __name__ == '__main__':
    unittest.main()
