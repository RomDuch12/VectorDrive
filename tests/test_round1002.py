"""Round 1002 : panneau FAO épuré (demande du 14/11) — plus de liste « toutes les opérations / objets sélectionnés »
ni de boutons Calculer, Simuler, 2D / 3D, « Ne plus afficher », Parcours TypeEdit, détacher, plein écran : un bouton
« Parcours 3D » calcule les opérations choisies dans la liste (aucune : toutes les actives) et montre leurs parcours,
eux seuls, en 3D dans le calque Trajectoires."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1002.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QItemSelectionModel, Qt  # noqa: E402
from PySide6.QtWidgets import QAbstractButton, QApplication, QComboBox  # noqa: E402

from vectordrive.i18n import tr  # noqa: E402

app = QApplication.instance() or QApplication([])


class Base(unittest.TestCase):

    def setUp(self):
        from vectordrive.cam import model
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.settings.remove('fao/mode_calcul')
        self.p = self.w.cam_panel
        doc = self.w.canvas.doc
        ids = []
        for r in ((0, 0, 20, 14), (30, 0, 12, 8), (50, 0, 10, 10)):
            sh = Shape(path=geom.Path([geom.rect(*r)]), tool=0)
            doc.add(sh)
            ids.append(sh.id)
        s = self.p.setup()
        self.tool = model.CamTool(name='Cyl 2', diameter=2.0, number=1, cut_length=7, step_down=1.0)
        s.tools = [self.tool]
        s.operations = [model.Operation(name=n, kind='gravure', tool_id=self.tool.id, items=[i], depth=0.2)
                        for n, i in zip(('Un', 'Deux', 'Trois'), ids)]
        self.p.save(s)
        self.shown3d = mock.patch.object(self.w, 'show_toolpaths')
        self.show = self.shown3d.start()
        self.addCleanup(self.shown3d.stop)

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def select(self, *rows):
        t = self.p.ops
        f = QItemSelectionModel.SelectionFlag
        t.clearSelection()
        for r in rows:
            t.selectionModel().select(t.model().index(r, 0), f.Select | f.Rows)

    def eye(self, r):
        cell = self.p.ops.item(r, self.p.EYE_COL)
        return None if cell is None else cell.data(Qt.ItemDataRole.UserRole)


class Panel(Base):

    def test_the_buttons_left(self):
        p = self.p
        texts = [b.text() for b in p.findChildren(QAbstractButton) if not b.isHidden() or b.text()]
        for gone in (tr('Calculer'), tr('Simuler…'), tr('Parcours TypeEdit…'), tr('2D'), tr('3D'), '⧉', '⛶'):
            self.assertNotIn(gone, texts, gone)
        self.assertNotIn(tr('Ne plus afficher les parcours'), [b.toolTip() for b in p.findChildren(QAbstractButton)])
        for kept in (tr('Parcours 3D'), '📂', tr('Réglage…'), tr('Rapides')):
            self.assertIn(kept, texts, kept)
        self.assertEqual(p.view3d_button.text(), tr('Parcours 3D'))

    def test_no_more_all_or_selection_list(self):
        p = self.p
        shown = [c for c in p.findChildren(QComboBox) if c.findData('selection') >= 0 and not c.isHidden()]
        self.assertEqual(shown, [])
        self.assertFalse(p.selection_mode())
        self.w.settings.setValue('fao/mode_calcul', 'selection')    # retenu par une version d'avant
        from vectordrive.ui.cam_panel import CamPanel
        other = CamPanel(self.w)
        self.assertFalse(other.selection_mode())                    # plus repris : la liste n'est plus montrée
        other.deleteLater()
        for key in ('cam_compute', 'cam_simulate', 'cam_typeedit', 'cam_clear', 'cam_paths_3d', 'cam_sim_3d'):
            self.assertIn(key, self.w.A)                            # ce qui a quitté le panneau reste au ruban
        self.assertFalse(p.toolpaths)
        self.w.A['cam_compute'].trigger()
        self.assertEqual([tp.name for tp in p.toolpaths], ['Un', 'Deux', 'Trois'])


class Chosen(Base):

    def test_none_chosen_means_all_active(self):
        p = self.p
        self.select()
        self.assertEqual([o.name for o in p.chosen_ops()], ['Un', 'Deux', 'Trois'])
        s = p.setup()
        s.operations[1].enabled = False
        p.save(s)
        self.select()
        self.assertEqual([o.name for o in p.chosen_ops()], ['Un', 'Trois'])
        self.select(1, 2)
        self.assertEqual([o.name for o in p.chosen_ops()], ['Trois'])
        self.select(1)                                              # la seule choisie est désactivée : rien, et c'est dit
        self.assertEqual(p.chosen_ops(), [])
        self.assertEqual(p.show_chosen_3d(), [])
        self.assertIn(tr('Aucune opération active parmi celles choisies dans la liste'), p.info.text())
        self.show.assert_not_called()

    def test_the_button_computes_and_shows_the_chosen_ones(self):
        p = self.p
        self.select(1)
        p.view3d_button.click()
        self.assertEqual([tp.name for tp in p.toolpaths], ['Un', 'Deux', 'Trois'])   # calculés
        self.assertEqual([tp.shown for tp in p.toolpaths], [False, True, False])     # la choisie seule montrée
        self.assertEqual([self.eye(r) for r in range(3)], [False, True, False])
        self.assertEqual([tp.name for tp in p.checked_paths()], ['Un', 'Deux', 'Trois'])   # cachés : toujours au
        self.show.assert_called_once_with('3d')                                      # programme (round 1163)
        self.assertNotIn('⚠', p.info.text())                                         # rien à signaler
        p.set_path_on(0, False)                                                      # à l'arrêt : c'est dit
        p.set_path_on(2, False)
        self.assertEqual([o.name for o in p.stopped_active_ops()], ['Un', 'Trois'])
        self.assertIn('2 ', p.info.text().split('⚠')[1])
        self.assertEqual(p.all_paths_on(), 2)                                        # tout en marche : plus d'avis
        self.assertEqual([tp.on for tp in p.toolpaths], [True, True, True])
        self.assertNotIn('⚠', p.info.text())
        self.select(1)
        p.show_chosen_3d()
        self.select(0, 2)
        out = p.show_chosen_3d()
        self.assertEqual([tp.name for tp in out], ['Un', 'Trois'])
        self.assertEqual([tp.shown for tp in p.toolpaths], [True, False, True])
        self.select()
        with mock.patch.object(p, 'display', wraps=p.display) as shown:
            p.show_chosen_3d()
        self.assertEqual(shown.call_count, 1)                                        # un seul réaffichage, pas un par parcours
        self.assertEqual([tp.shown for tp in p.toolpaths], [True, True, True])       # aucune choisie : toutes
        self.assertEqual(self.show.call_count, 4)

    def test_recomputed_when_the_drawing_changed(self):
        from vectordrive.core import geom
        p = self.p
        self.select(0)
        p.show_chosen_3d()
        before = p.toolpaths[0].lengths()[0]
        sh = self.w.canvas.doc.layers[0].items[0]
        sh.path = geom.Path([geom.rect(0, 0, 40, 28)])              # l'objet de « Un », deux fois plus grand
        self.w.canvas.invalidate()
        out = p.show_chosen_3d()
        self.assertEqual([tp.name for tp in out], ['Un'])
        self.assertGreater(out[0].lengths()[0], before * 1.5)
        self.assertEqual([tp.shown for tp in p.toolpaths], [True, False, False])

    def test_an_operation_added_since(self):
        import copy
        from vectordrive.cam import model
        p = self.p
        self.select(0)
        p.show_chosen_3d()
        read = copy.copy(p.toolpaths[0])                            # un parcours sans opération (programme lu, TypeEdit)
        read.op_id, read.name, read.shown = '', 'Lu', True
        p.display(p.toolpaths + [read])
        s = p.setup()
        s.operations.append(model.Operation(name='Quatre', kind='gravure', tool_id=self.tool.id,
                                            items=list(s.operations[2].items), depth=0.3))
        p.save(s)
        self.select(3)
        out = p.show_chosen_3d()
        self.assertEqual([tp.name for tp in out], ['Quatre'])
        self.assertIn('Lu', [tp.name for tp in p.toolpaths])        # le parcours lu n'a pas disparu
        self.assertEqual(sorted(tp.name for tp in p.toolpaths if tp.shown), ['Lu', 'Quatre'])   # montrés

    def test_nothing_active_and_nothing_shown_when_cancelled(self):
        p = self.p
        with mock.patch.object(p, 'current_paths', side_effect=lambda **k: setattr(p, '_cancelled', True) or []):
            self.assertEqual(p.show_chosen_3d(), [])
        self.show.assert_not_called()
        self.assertEqual([tp.name for tp in p.show_chosen_3d()], ['Un', 'Deux', 'Trois'])   # la fois d'après : ça marche
        self.assertEqual(self.show.call_count, 1)
        s = p.setup()
        for o in s.operations:
            o.enabled = False
        p.save(s)
        self.assertEqual(p.show_chosen_3d(), [])
        self.assertIn(tr('Aucune opération active'), p.info.text())
        self.assertEqual(self.show.call_count, 1)                   # rien de plus n'a été montré


if __name__ == '__main__':
    unittest.main()
