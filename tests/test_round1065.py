"""Round 1065 : réponse du 17/11, 0 h 15 — « Un dessin déplacé ou modifié alors qu'il est à la base d'un calcul fao doit
emettre un warning visuel (par exemple clignotement 2s de son contour user pourra alors faire ctrlZ ou parametrer
bloquer formes, ou pas d'alarme (mode fao de TE) »."""
import importlib.util
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1065.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Shape  # noqa: E402

BEFORE = 'avant : une forme d’un parcours calculé se déplace sans rien dire'
KEY = 'fao/formes_parcours'


class Guarded(unittest.TestCase):

    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('vectordrive.ui.fao_guard'), BEFORE)
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.addCleanup(self.clean)
        self.w.settings.remove(KEY)
        self.p = self.w.cam_panel

    def clean(self):
        self.w.settings.remove(KEY)
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()

    def shape(self, x=0.0):
        sh = Shape(path=geom.Path([geom.rect(x, 0, 20, 10)]), tool=0)
        self.w.canvas.doc.add(sh)
        self.w.canvas.select([sh])
        return sh

    def machined(self):
        sh = self.shape()
        op = self.p.new_operation('decoupe', exec_dialog=False)
        self.assertEqual([t.op_id for t in self.p.toolpaths], [op.id])
        return sh

    def move(self, sh, dx=5.0):
        """Ce que fait une commande : un pas d'annulation, la modification, le dessin prévenu."""
        self.w.push_undo('Déplacer')
        sh.path = sh.path.transformed(geom.Affine.translation(dx, 0.0))
        self.w.canvas.invalidate()
        self.w.canvas.documentChanged.emit()
        app.processEvents()

    def x0(self, sh):
        return round(sh.path.bbox()[0], 6)


class Flash(Guarded):

    def test_a_moved_shape_of_a_toolpath_flashes(self):
        sh = self.machined()
        self.move(sh)
        self.assertEqual(self.w.fao_guard.flagged, [sh.id])
        self.assertTrue(self.w.canvas.flash_paths)                          # son contour clignote
        self.assertEqual(self.x0(sh), 5.0)                                  # la modification reste (Ctrl+Z la défait)
        self.assertIn('Ctrl+Z', self.w.statusBar().currentMessage())
        self.w.undo()
        app.processEvents()
        self.assertEqual(self.w.fao_guard.flagged, [sh.id])                 # défaire ne signale rien de plus
        self.assertFalse(self.w.fao_guard.before)

    def test_the_flash_stops_after_two_seconds(self):
        c = self.w.canvas
        c.flash([geom.Path([geom.rect(0, 0, 5, 5)])], 2000)
        self.assertTrue(c._flash_on)
        for _ in range(8):                                                   # 8 × 250 ms
            c._flash_tick()
        self.assertFalse(c.flash_paths)
        self.assertFalse(c._flash_on)

    def test_other_shapes_and_shapes_without_toolpath_do_not_flash(self):
        self.machined()
        other = self.shape(50.0)                                            # pas usinée
        self.move(other)
        self.assertEqual(self.w.fao_guard.flagged, [])
        self.assertFalse(getattr(self.w.canvas, 'flash_paths', None))

    def test_no_alarm_mode_like_typeedit(self):
        self.w.settings.setValue(KEY, 'rien')
        sh = self.machined()
        self.move(sh)
        self.assertFalse(getattr(self.w.canvas, 'flash_paths', None))
        self.assertEqual(self.x0(sh), 5.0)

    def test_a_shape_added_after_the_computation_is_not_watched(self):
        self.w.cam_palette.set_mode('couleur')
        self.addCleanup(self.w.cam_palette.set_mode, 'selection')
        sh = self.shape()
        self.w.canvas.select([])
        op = self.p.new_operation('trace', exec_dialog=False)               # par couleur : toute la couleur
        self.assertEqual([t.op_id for t in self.p.toolpaths], [op.id])
        self.w.push_undo('Ajouter')                                          # dessinée après le calcul, même couleur
        new = Shape(path=geom.Path([geom.rect(60, 0, 10, 10)]), tool=sh.tool)
        self.w.canvas.doc.add(new)
        self.w.canvas.documentChanged.emit()
        app.processEvents()
        self.move(new)
        self.assertEqual(self.w.fao_guard.flagged, [])                     # pas à la base du parcours
        self.move(sh)
        self.assertEqual(self.w.fao_guard.flagged, [sh.id])

    def test_nothing_is_compared_during_a_computation(self):
        sh = self.machined()
        self.p._computing = True
        self.addCleanup(setattr, self.p, '_computing', False)
        self.move(sh)
        self.assertFalse(getattr(self.w.canvas, 'flash_paths', None))      # pas pendant le calcul…
        self.p._computing = False
        self.assertEqual(self.w.fao_guard.check(), [sh.id])                 # … à la fin

    def test_the_next_command_does_not_hide_the_previous_change(self):
        sh = self.machined()
        self.w.push_undo('Déplacer')
        sh.path = sh.path.transformed(geom.Affine.translation(5.0, 0.0))
        self.w.canvas.documentChanged.emit()                                # comparaison pas encore faite…
        self.w.push_undo('Autre commande')                                  # … faite avant le pas suivant
        self.assertEqual(self.w.fao_guard.flagged, [sh.id])

    def test_after_a_selection_computation_a_new_toolpath_watches_its_own_shapes(self):
        a = self.machined()
        self.w.canvas.select([a])
        self.p.compute()                                                     # mode sélection : A seulement
        b = self.shape(40.0)
        self.p.new_operation('decoupe', exec_dialog=False)                  # calculée seule, sur B
        self.move(b)
        self.assertEqual(self.w.fao_guard.flagged, [b.id])

    def test_another_colour_takes_a_shape_out_of_its_toolpath(self):
        sh = self.machined()
        self.w.push_undo('Couleur')
        sh.tool = sh.tool + 1
        self.w.canvas.documentChanged.emit()
        app.processEvents()
        self.assertEqual(self.w.fao_guard.flagged, [sh.id])

    def test_two_steps_before_the_comparison_keep_the_oldest_state(self):
        sh = self.machined()
        self.w.push_undo('Commande')
        sh.path = sh.path.transformed(geom.Affine.translation(5.0, 0.0))
        self.w.push_undo('Remplacer la sélection')                           # un second pas, dessin pas encore prévenu
        self.w.canvas.documentChanged.emit()
        app.processEvents()
        self.assertEqual(self.w.fao_guard.flagged, [sh.id])

    def test_undo_stops_the_flash(self):
        sh = self.machined()
        self.move(sh)
        self.assertTrue(self.w.canvas.flash_paths)
        self.w.undo()
        self.assertFalse(self.w.canvas.flash_paths)                         # rien ne clignote à l'ancienne place


class Block(Guarded):

    def test_blocked_shapes_come_back_and_cannot_be_redone(self):
        self.w.settings.setValue(KEY, 'bloquer')
        sh = self.machined()
        steps = len(self.w._undo)
        self.move(sh)
        back = next(it for L in self.w.canvas.doc.layers for it in L.items if it.id == sh.id)
        self.assertEqual(self.x0(back), 0.0)                                # défaite aussitôt
        self.assertEqual(len(self.w._undo), steps)
        self.assertFalse(self.w._redo)                                      # pas à refaire par Ctrl+Y
        self.assertTrue(self.w.canvas.flash_paths)
        self.assertIn('annulée', self.w.statusBar().currentMessage())

    def test_blocking_never_undoes_another_command(self):
        self.w.settings.setValue(KEY, 'bloquer')
        sh = self.machined()
        other = self.shape(60.0)
        self.move(other)                                                     # une commande sur une autre forme
        steps = len(self.w._undo)
        sh.path = sh.path.transformed(geom.Affine.translation(5.0, 0.0))    # puis un changement sans pas d'annulation
        self.w.canvas.documentChanged.emit()
        app.processEvents()
        self.assertEqual(self.x0(other), 65.0)                              # la commande d'avant reste
        self.assertEqual(len(self.w._undo), steps)

    def test_the_option_is_in_f10(self):
        from vectordrive.ui import options
        o = options.BY_KEY[KEY]
        self.assertEqual(o.default, 'clignoter')
        self.assertEqual([k for k, _t in o.choices], ['clignoter', 'bloquer', 'rien'])


if __name__ == '__main__':
    unittest.main()
