"""Round 1060 : réponse du 15/11 à la question 27 (« oui ») — les 22 parcours de la palette réunis en 9 familles ;
dans le formulaire, une liste fait la différence (« Type de trou », « Fond », « Étape »…)."""
import json
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1060.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.cam import model  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Shape  # noqa: E402
from vectordrive.ui import cam_panel as CP  # noqa: E402

BEFORE = 'avant : la palette n’a que ses 22 parcours, rangés en cinq dossiers'
KEYS = ('fao/palette/unifiee', 'fao/palette/famille_dernier')
NINE = ['Tracé', 'Trous', 'Découpe', 'Gravure', 'Reprise', 'Relief 3D', 'Gamme', 'Surfaçage', 'Machine']


class Table(unittest.TestCase):

    def setUp(self):
        self.assertTrue(hasattr(CP, 'UNIFIED'), BEFORE)

    def test_nine_families_hold_the_22_once_each(self):
        self.assertEqual([v[0] for v in CP.UNIFIED.values()], NINE)
        members = [k for _l, _w, ms in CP.UNIFIED.values() for k, _t in ms]
        self.assertEqual(sorted(members), sorted(CP.PRESETS))                # chacun des 22, une seule fois
        self.assertFalse(set(CP.UNIFIED) & set(CP.PRESETS))                  # une famille n'est pas un parcours
        for fam, (_label, box, ms) in CP.UNIFIED.items():
            self.assertEqual(bool(box), len(ms) > 1, fam)                    # une liste dès qu'il y a le choix
            for k, _t in ms:
                self.assertEqual(CP.family_of(k), fam)
        self.assertEqual(CP.family_of('parcours_d_un_plugin'), '')


class WithWindow(unittest.TestCase):

    def setUp(self):
        self.assertTrue(hasattr(CP, 'UNIFIED'), BEFORE)
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.addCleanup(self.clean)
        self.p = self.w.cam_panel
        self.pal = self.w.cam_palette
        if any(self.w.settings.contains(k) for k in KEYS):                   # laissé par un autre essai : d'office
            for k in KEYS:
                self.w.settings.remove(k)
            self.pal.refresh()

    def clean(self):
        for k in KEYS + (self.p.LAST_KEY,):                                  # les dernières valeurs d'un parcours aussi
            self.w.settings.remove(k)
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()

    def base(self):
        from vectordrive.ui.cam_palette import ROLE_GROUP
        return next(self.pal.tree.topLevelItem(i) for i in range(self.pal.tree.topLevelItemCount())
                    if self.pal.tree.topLevelItem(i).data(0, ROLE_GROUP) == 'type')

    def rows(self):
        b = self.base()
        return [b.child(i) for i in range(b.childCount())]

    def select_circle(self):
        it = Shape(path=geom.Path([geom.circle((10.0, 10.0), 2.0)]), tool=0)
        self.w.canvas.doc.add(it)
        self.w.canvas.invalidate()
        self.w.canvas.select([it])
        return it


class Palette(WithWindow):

    def test_nine_rows_under_parcours_type(self):
        from vectordrive.ui.cam_palette import ROLE_FAMILY, ROLE_KIND
        self.pal.refresh()
        rows = [r for r in self.rows() if r.data(0, ROLE_FAMILY) or r.data(0, ROLE_KIND)]
        self.assertEqual([r.text(0) for r in rows], NINE)
        trous = rows[1]
        self.assertEqual(trous.data(0, ROLE_FAMILY), 'trous')
        self.assertFalse(trous.isExpanded())                                 # ses parcours : dessous, repliés
        self.assertEqual([trous.child(i).data(0, ROLE_KIND) for i in range(trous.childCount())],
                         ['percage', 'percage_fraise', 'taraudage', 'chanfrein'])
        self.assertEqual((rows[4].data(0, ROLE_KIND), rows[4].data(0, ROLE_FAMILY)), ('reste', None))   # seul : lui-même
        for key in CP.PRESETS:                                               # les 22 restent là, chacun sa ligne
            self.assertIn(f'cam_new_{key}', self.pal.items)

    def test_back_to_the_22_and_again(self):
        from vectordrive.ui.cam_palette import ROLE_GROUP
        self.pal.set_unified(False)
        groups = [r.data(0, ROLE_GROUP) for r in self.rows() if r.data(0, ROLE_GROUP)]
        self.assertIn('fam:Usinage 2D', groups)                              # les dossiers d'avant
        self.assertFalse(self.pal.unified())
        self.assertIn(self.w.settings.value('fao/palette/unifiee'), (False, 'false'))
        self.pal.set_unified(True)
        self.assertNotIn('fam:Usinage 2D', [r.data(0, ROLE_GROUP) for r in self.rows()])
        self.assertTrue(self.pal.unified())

    def test_a_click_on_a_family_opens_its_form(self):
        from vectordrive.ui.cam_palette import ROLE_FAMILY
        self.pal.refresh()
        trous = next(r for r in self.rows() if r.data(0, ROLE_FAMILY) == 'trous')
        with mock.patch.object(self.p, 'new_family') as fam, mock.patch.object(self.p, 'new_operation') as op:
            self.pal.activate(trous)                                         # double clic (round 1163)
            fam.assert_called_once_with('trous')
            op.assert_not_called()
            self.pal.activate(trous.child(2))                                # un de ses parcours : le sien, direct
            self.assertEqual(op.call_args[0][0], 'taraudage')

    def test_the_machine_keeps_only_what_fits(self):
        self.w._machine_kind = 'laser'
        self.assertEqual(self.p.family_members('tracer'), ['laser'])
        self.assertEqual(self.p.family_members('trous'), [])
        self.assertEqual(self.p.family_members('machine'), ['instruction'])
        self.assertIsNone(self.p.new_family('trous', exec_dialog=False))
        self.pal.refresh()
        from vectordrive.ui.cam_palette import ROLE_FAMILY, ROLE_KIND
        shown = [r.text(0) for r in self.rows() if r.data(0, ROLE_FAMILY) or r.data(0, ROLE_KIND)]
        self.assertEqual(shown, ['Tracé', 'Découpe', 'Gravure', 'Machine'])  # un seul parcours chacune : sans liste
        self.w._machine_kind = 'fraiseuse'
        self.assertEqual(self.p.family_members('graver'), ['gravure', 'gravure3d', 'prismatique'])


class Family(WithWindow):

    def test_the_first_then_the_last_taken(self):
        self.select_circle()
        op = self.p.new_family('trous', exec_dialog=False)
        self.assertEqual(op.kind, 'percage')                                 # la première fois : le premier
        self.select_circle()
        op = self.p.new_family('trous', exec_dialog=False, member='taraudage')
        self.assertEqual(op.kind, 'taraudage')
        self.assertEqual(json.loads(self.w.settings.value('fao/palette/famille_dernier'))['trous'], 'taraudage')
        self.select_circle()
        self.assertEqual(self.p.new_family('trous', exec_dialog=False).kind, 'taraudage')   # ensuite : le dernier pris
        self.select_circle()
        self.assertEqual(self.p.new_operation('percage', exec_dialog=False).kind, 'percage')
        self.assertEqual(json.loads(self.w.settings.value('fao/palette/famille_dernier'))['trous'], 'taraudage')

    def test_the_list_of_the_family_in_the_form(self):
        members = self.p.family_members('trous')
        d = CP.FieldsDialog(None, 'essai', model.Operation(kind='percage'), preset='percage', family='trous',
                            members=members)
        self.addCleanup(d.deleteLater)
        box = d.family_box
        self.assertEqual([box.itemData(i) for i in range(box.count())], members)
        self.assertEqual(box.currentData(), 'percage')
        self.assertEqual(d.rows['family'][0].text(), 'Type de trou')
        self.assertFalse(d.rows['family'][1].isHidden())
        self.assertTrue(d.rows['kind_label'][1].isHidden())                  # la liste remplace « Type de parcours »
        d.choose_member('percage')                                           # le même : rien
        self.assertEqual(d.switch_to, '')
        d.choose_member('ailleurs')
        self.assertEqual(d.switch_to, '')
        d.choose_member('taraudage')
        self.assertEqual(d.switch_to, 'taraudage')
        alone = CP.FieldsDialog(None, 'essai', model.Operation(kind='reste'), preset='reste', family='reprise',
                                members=['reste'])
        self.addCleanup(alone.deleteLater)
        self.assertFalse(hasattr(alone, 'family_box'))                       # un seul parcours : pas de liste
        plain = CP.FieldsDialog(None, 'essai', model.Operation(kind='percage'), preset='percage')
        self.addCleanup(plain.deleteLater)
        self.assertFalse(hasattr(plain, 'family_box'))                       # hors famille : comme avant

    def test_choosing_in_the_list_reopens_the_form_of_that_toolpath(self):
        self.select_circle()
        seen = []

        def fake(dlg):
            seen.append((dlg.preset, dlg.family, list(dlg.members)))
            if len(seen) == 1:
                dlg.choose_member('taraudage')                               # choisi dans la liste : il se ferme
                return 0
            return 1                                                         # le second : validé
        before = len(self.p.setup().operations)
        with mock.patch.object(CP.FieldsDialog, 'exec', fake):               # (une fonction : liée au formulaire)
            op = self.p.new_family('trous')
        self.assertEqual([s[0] for s in seen], ['percage', 'taraudage'])
        self.assertEqual(seen[1][1:], ('trous', self.p.family_members('trous')))
        self.assertEqual(op.kind, 'taraudage')
        self.assertEqual(len(self.p.setup().operations), before + 1)         # un seul parcours ajouté

    def test_cancelling_adds_nothing_and_remembers_nothing(self):
        self.select_circle()
        before = len(self.p.setup().operations)
        with mock.patch.object(CP.FieldsDialog, 'exec', lambda dlg: 0):
            self.assertIsNone(self.p.new_family('trous', member='taraudage'))
        self.assertEqual(len(self.p.setup().operations), before)
        self.assertNotIn('trous', self.p._family_last())                     # annulé : la famille ne retient rien
        self.w.canvas.select([])                                             # rien de choisi : rien non plus
        self.assertIsNone(self.p.new_family('trous', exec_dialog=False, member='taraudage'))
        self.assertNotIn('trous', self.p._family_last())

    def test_a_sequence_with_its_own_window_never_holds_the_family(self):
        # « Gamme : ébauche et finition » ouvre sa propre fenêtre, sans la liste : retenue, la famille n'en sortirait plus
        self.select_circle()
        with mock.patch.object(self.p, 'new_relief_gamme', return_value=None) as gamme:
            self.p.new_family('relief3d', member='gamme_relief')
            gamme.assert_called_once()
        self.assertNotIn('relief3d', self.p._family_last())
        with mock.patch.object(self.p, 'new_operation') as op:
            self.p.new_family('relief3d')
            self.assertEqual(op.call_args[0][0], 'relief')                   # le clic suivant : le premier, pas la gamme

    def test_the_list_is_chosen_in_its_popup_never_by_a_stray_key(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        members = self.p.family_members('machine')
        d = CP.FieldsDialog(None, 'essai', model.Operation(kind='instruction'), preset='instruction',
                            family='machine', members=members)
        self.addCleanup(d.deleteLater)
        self.assertFalse(d.rows['family'][1].isHidden())                     # une instruction n'a presque aucun champ : la liste si
        box = d.family_box
        for key in (Qt.Key.Key_Up, Qt.Key.Key_End, Qt.Key.Key_PageDown, Qt.Key.Key_T):
            QTest.keyClick(box, key)
        self.assertEqual((box.currentData(), d.switch_to), ('instruction', ''))   # fermée : aucune touche ne choisit
        QTest.keyClick(box, Qt.Key.Key_Down)                                 # ↓ la déroule
        self.assertTrue(box.view().isVisible())
        box.hidePopup()
        self.assertEqual(d.switch_to, '')
        box.setCurrentIndex(1)                                               # choisi dans la liste déroulée
        box.activated.emit(1)
        self.assertEqual(d.switch_to, 'texte_machine')


if __name__ == '__main__':
    unittest.main()
