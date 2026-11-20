"""Round 1122 (demande du 20/11, 15 h 50) : « si un dessin servant de base à un parcours est modifié, on peut choisir de
le mettre à jour. OK. Si on Ctrl+Z retour dessin précédent il faut aussi une popup clignotement pour indiquer cela »."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1122.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Shape  # noqa: E402

BEFORE = 'avant : Ctrl+Z remettait l’ancienne forme sans rien dire, le parcours mis à jour ne la suivait plus'
KEY = 'fao/formes_parcours'


class UndoAfterUpdate(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.addCleanup(self.clean)
        self.w.settings.remove(KEY)                                          # d'office : demander
        self.p = self.w.cam_panel
        self.g = self.w.fao_guard

    def clean(self):
        self.g.close_box()
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
        return sh, op

    def move(self, sh, dx=5.0):
        self.w.push_undo('Déplacer')
        sh.path = sh.path.transformed(geom.Affine.translation(dx, 0.0))
        self.w.canvas.invalidate()
        self.w.canvas.documentChanged.emit()
        app.processEvents()

    def updated(self):
        """Une forme du parcours déplacée, les parcours mis à jour (le bouton de la fenêtre)."""
        sh, op = self.machined()
        self.move(sh)
        self.assertIsNotNone(self.g.box)
        self.assertEqual(self.g.update_paths(self.g.flagged), 1)
        self.g.close_box()
        self.w.canvas.flash([])
        app.processEvents()
        return sh, op

    def xmax(self, op):
        tp = next(t for t in self.p.toolpaths if t.op_id == op.id)
        return max(m.x for m in tp.moves if m.kind != 'rapid')

    def undo(self):
        self.w.undo()
        app.processEvents()

    def test_undo_after_update_warns(self):
        sh, op = self.updated()
        self.assertGreater(self.xmax(op), 24.0)
        self.undo()
        self.assertEqual(round(self.shape().path.bbox()[0], 6), 0.0)   # la forme d'avant
        box = self.g.box
        self.assertIsNotNone(box, BEFORE)
        self.assertFalse(box.isModal())
        texts = [b.text() for b in box.buttons()]
        self.assertIn('Mettre à jour les parcours', texts)
        self.assertNotIn('Dupliquer le dessin', texts, 'après Ctrl+Z : rien à dupliquer')
        self.assertIn('Défaire / refaire', box.text())
        self.assertTrue(self.w.canvas.flash_paths, 'et le contour clignote')
        self.assertEqual(self.g.flagged, [self.shape().id])

    def shape(self):
        return next(it for L in self.w.canvas.doc.layers for it in L.items if isinstance(it, Shape))

    def test_update_from_the_undo_window(self):
        _sh, op = self.updated()
        self.undo()
        box = self.g.box
        upd = next(b for b in box.buttons() if b.text() == 'Mettre à jour les parcours')
        upd.click()
        app.processEvents()
        self.assertLess(self.xmax(op), 21.0, 'le parcours suit le dessin remis')
        self.assertIsNone(self.g.box)

    def test_redo_back_to_the_computed_drawing_closes_it(self):
        self.updated()
        self.undo()
        self.assertIsNotNone(self.g.box)
        self.w.redo()
        app.processEvents()
        self.assertIsNone(self.g.box, 'Ctrl+Y : le dessin du calcul, rien à signaler')
        self.assertFalse(self.w.canvas.flash_paths)

    def test_undo_back_to_the_computed_drawing_says_nothing(self):
        sh, _op = self.machined()
        self.move(sh)
        self.g.close_box()                                                   # Laisser
        app.processEvents()
        self.undo()                                                          # Ctrl+Z pour revenir : la forme du calcul
        self.assertIsNone(self.g.box)
        self.assertFalse(self.w.canvas.flash_paths)

    def test_blink_only(self):
        self.w.settings.setValue(KEY, 'clignoter')
        sh, op = self.machined()
        self.move(sh)
        self.g.update_paths(self.g.flagged)
        self.w.canvas.flash([])
        self.undo()
        self.assertIsNone(self.g.box)
        self.assertTrue(self.w.canvas.flash_paths)

    def test_nothing_in_te_mode(self):
        self.w.settings.setValue(KEY, 'rien')
        sh, op = self.machined()
        self.move(sh)
        self.g.update_paths([sh.id])
        self.undo()
        self.assertIsNone(self.g.box)
        self.assertFalse(self.w.canvas.flash_paths)

    def test_block_mode_own_undo_not_reported(self):
        self.w.settings.setValue(KEY, 'bloquer')
        sh, _op = self.machined()
        self.move(sh)
        self.assertEqual(round(self.shape().path.bbox()[0], 6), 0.0)        # défait par l'alarme
        self.assertFalse(self.g.htimer.isActive(), 'son propre pas défait : pas signalé comme un Ctrl+Z')
        self.assertIsNone(self.g.box)

    def test_left_shape_not_reported_by_an_unrelated_undo(self):
        sh, _op = self.machined()
        self.move(sh)
        self.g.close_box()                                                   # Laisser
        self.w.canvas.flash([])
        other = Shape(path=geom.Path([geom.rect(50, 0, 5, 5)]), tool=0)
        self.w.push_undo('Rectangle')
        self.w.canvas.doc.add(other)
        self.w.canvas.documentChanged.emit()
        app.processEvents()
        self.undo()                                                          # le rectangle retiré : A pas en cause
        self.assertIsNone(self.g.box, 'Laisser vaut tant que la forme ne change pas')
        self.assertFalse(self.w.canvas.flash_paths)

    def test_modification_window_closes_when_undone(self):
        sh, _op = self.machined()
        self.move(sh)
        self.assertIsNotNone(self.g.box)                                     # Dupliquer / Mettre à jour / Laisser
        self.undo()                                                          # Ctrl+Z : la forme du calcul
        self.assertIsNone(self.g.box, 'la fenêtre n’a plus lieu')

    def test_reference_kept_in_te_mode(self):
        self.w.settings.setValue(KEY, 'rien')
        sh, _op = self.machined()
        self.move(sh)                                                        # aucune alarme
        self.assertIsNone(self.g.box)
        self.w.settings.setValue(KEY, 'demander')
        self.undo()                                                          # la forme du calcul revient
        self.assertIsNone(self.g.box, 'la référence : la forme du calcul, pas la forme déplacée')
        self.w.redo()                                                        # de nouveau déplacée
        app.processEvents()
        self.assertIsNotNone(self.g.box)

    def test_other_tab_drops_the_pending_check(self):
        self.updated()
        self.g.history_before()
        self.g.htimer.start(10000)
        self.g.drop_history()
        self.assertFalse(self.g.htimer.isActive())
        self.assertIsNone(self.g._hbefore)

    def test_several_steps_one_check(self):
        sh, op = self.updated()
        self.w.push_undo('Autre')
        self.w.canvas.doc.add(Shape(path=geom.Path([geom.rect(50, 0, 5, 5)]), tool=0))
        app.processEvents()
        self.w.undo_steps(2)                                                 # le rectangle, puis le déplacement
        app.processEvents()
        self.assertIsNotNone(self.g.box)
        self.assertEqual(self.g.flagged, [self.shape().id])

    def test_change_while_the_check_waits_is_not_the_undo(self):
        self.updated()
        self.w.undo()                                                        # comparaison en attente (pas encore lancée)
        self.assertIsNotNone(self.g._hbefore)
        self.g.close_box()
        self.move(self.shape(), 2.0)                                         # une modification : le Ctrl+Z comparé avant
        self.assertIsNone(self.g._hbefore)
        texts = [b.text() for b in self.g.box.buttons()]
        self.assertIn('Dupliquer le dessin', texts, 'la fenêtre de la modification, pas celle du Ctrl+Z')

    def test_never_ask_again_from_the_undo_window(self):
        self.updated()
        self.undo()
        box = self.g.box
        box.checkBox().setChecked(True)
        leave = next(b for b in box.buttons() if box.buttonRole(b) == QMessageBox.ButtonRole.RejectRole)
        leave.click()
        app.processEvents()
        self.assertEqual(self.w.settings.value(KEY), 'clignoter')


if __name__ == '__main__':
    unittest.main()
