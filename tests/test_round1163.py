"""Round 1163 (demandes du 25/11) :
(d) « A partir d'une forme sélectionnée, calculer le parcours se fait avec un double clic sur le parcours
sélectionné; » ;
(a) « Plan du programme = colonne repli/dépliable. Parcours calculés : différencier oeil (dessin) et bouton on/off qui
remplace la case à cocher et concerne le simpl. »"""
import gzip
import json
import os
import struct
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1163.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QShortcut  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QStyleOptionViewItem  # noqa: E402

from tests import _posts  # noqa: E402

app = QApplication.instance() or QApplication([])

KEYS = ('fao/programme_plan', 'fao/programme_plan_largeur', 'fao/programme_direct', 'fao/palette/famille_dernier',
        'fao/palette/unifiee', 'fenetre/geometrie', 'fenetre/plein_ecran', 'vue/panneau_fao')


def named(toolpaths, setup, *, title: str = '', machine=None, stem: str = 'programme', box_mm=None):
    """Post-processeur d'essai : le nom de chaque parcours en commentaire, puis ses mouvements."""
    from vectordrive.cam.post import PostResult
    lines = ['%']
    for k, tp in enumerate(toolpaths):
        lines.append(f'N{10 * (k + 1)} T{k + 1} M6 ({tp.name})')
        for m in tp.moves:
            lines.append(f'{"G0" if m.kind == "rapid" else "G1"} X{m.x:.3f} Y{m.y:.3f} Z{m.z:.3f}')
    lines.append('M30')
    return PostResult('\n'.join(lines) + '\n', [], '.nc', 'utf-8')


def forget():
    from vectordrive.portable import settings
    st = settings()
    for k in list(st.allKeys()):
        if k.startswith('panneaux_colonnes/') or k in KEYS:
            st.remove(k)
    st.sync()


def option(view, index):
    """L'option de peinture d'une case de `view`, à sa place dans la vue."""
    opt = QStyleOptionViewItem()
    view.initViewItemOption(opt)
    opt.rect = view.visualRect(index)
    return opt


def release(view, pt):
    return QMouseEvent(QEvent.Type.MouseButtonRelease, QPointF(pt), QPointF(view.viewport().mapToGlobal(pt)),
                       Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)


def greens(delegate, view, index) -> int:
    """Le nombre de points verts (bouton en marche) peints par `delegate` à la place de la case."""
    opt = option(view, index)
    box = delegate.check_rect(opt, index)
    img = QImage(opt.rect.size(), QImage.Format.Format_ARGB32)
    img.fill(QColor('white'))
    p = QPainter(img)
    p.translate(-opt.rect.topLeft())
    delegate.paint(p, opt, index)
    p.end()
    n = 0
    for x in range(box.left(), box.right() + 1):
        for y in range(box.top(), box.bottom() + 1):
            c = img.pixelColor(x - opt.rect.left(), y - opt.rect.top())
            n += c.green() > c.red() + 40 and c.green() > c.blue() + 30
    return n


class Base(unittest.TestCase):
    """Une fenêtre montrée, deux formes, deux gravures (« Plaque avant », « Détourage été »), le post d'essai."""

    def setUp(self):
        from vectordrive.cam import model
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        from vectordrive.ui.main_window import MainWindow
        forget()
        self.addCleanup(forget)
        self.posts = _posts.registered('essai', named)
        self.posts.__enter__()
        self.addCleanup(self.posts.__exit__, None, None, None)
        self.w = MainWindow()
        self.w.resize(1400, 900)
        self.w.show()
        app.processEvents()
        self.addCleanup(self.close)
        self.p, self.prog, self.pal = self.w.cam_panel, self.w.program_panel, self.w.cam_palette
        self.addCleanup(self.w.settings.remove, self.p.LAST_KEY)
        doc = self.w.canvas.doc
        self.shapes = []
        for r in ((0, 0, 20, 14), (30, 0, 12, 8)):
            sh = Shape(path=geom.Path([geom.rect(*r)]), tool=0)
            doc.add(sh)
            self.shapes.append(sh)
        s = self.p.setup()
        self.tool = model.CamTool(name='Cyl 2', diameter=2.0, number=1, cut_length=7, step_down=1.0, spindle=20000)
        s.tools = [self.tool]
        s.post = 'essai'
        s.operations = [model.Operation(name=n, kind='gravure', tool_id=self.tool.id, items=[sh.id], depth=0.2)
                        for n, sh in zip(('Plaque avant', 'Détourage été'), self.shapes)]
        self.p._fill_posts()
        self.p.save(s)

    def close(self):
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()

    def program(self) -> str:
        return ''.join(text for _n, text in self.p.program_preview()['files'])


# --- (d) la palette « Créer un parcours » ---------------------------------------------------------------------------
class Palette(Base):

    def row(self, key):
        return self.pal.items[f'cam_new_{key}']

    def family(self, fam):
        from vectordrive.ui.cam_palette import ROLE_FAMILY, ROLE_GROUP
        t = self.pal.tree
        base = next(t.topLevelItem(i) for i in range(t.topLevelItemCount())
                    if t.topLevelItem(i).data(0, ROLE_GROUP) == 'type')
        return next(base.child(i) for i in range(base.childCount()) if base.child(i).data(0, ROLE_FAMILY) == fam)

    def test_a_click_only_chooses(self):
        self.w.canvas.select([self.shapes[0]])
        with mock.patch.object(self.p, 'new_operation') as op, mock.patch.object(self.p, 'new_family') as fam, \
                mock.patch.object(self.p, 'apply_template') as tpl:
            self.pal.tree.itemClicked.emit(self.row('gravure'), 0)
            self.pal.tree.itemClicked.emit(self.family('trous'), 0)
        op.assert_not_called()                                               # avant : le formulaire, dès le clic
        fam.assert_not_called()
        tpl.assert_not_called()

    def test_a_double_click_creates_and_computes(self):
        from vectordrive.ui import cam_panel as CP
        self.w.canvas.select([self.shapes[1]])
        n = len(self.p.setup().operations)
        with mock.patch.object(CP.FieldsDialog, 'exec', return_value=1) as shown:
            self.pal.tree.itemDoubleClicked.emit(self.row('gravure'), 0)
        shown.assert_called_once()                                           # le formulaire, comme avant
        ops = self.p.setup().operations
        self.assertEqual(len(ops), n + 1, 'avant : le double clic ne faisait rien')
        self.assertEqual(ops[-1].items, [self.shapes[1].id])                 # la forme sélectionnée
        self.assertTrue([tp for tp in self.p.toolpaths if tp.op_id == ops[-1].id and tp.moves])   # calculé

    def test_a_double_click_without_selection_says_so(self):
        from vectordrive.ui import cam_panel as CP
        self.w.canvas.select([])
        self.p.info.setText('')
        n = len(self.p.setup().operations)
        with mock.patch.object(CP.FieldsDialog, 'exec', return_value=1) as shown:
            self.pal.tree.itemDoubleClicked.emit(self.row('gravure'), 0)
        shown.assert_not_called()
        self.assertEqual(len(self.p.setup().operations), n)
        self.assertIn('Sélectionnez d\'abord les contours à usiner', self.p.info.text())

    def test_enter_does_the_same(self):
        keys = {sc.key().toString(): sc for sc in self.pal.tree.findChildren(QShortcut)}
        self.assertIn('Return', keys, 'avant : Entrée ne créait rien')
        self.assertIn('Enter', keys)
        row = self.row('gravure')
        self.pal.tree.setCurrentItem(row)
        with mock.patch.object(self.pal, 'activate') as act:
            keys['Return'].activated.emit()
        act.assert_called_once_with(row)
        self.w.canvas.select([self.shapes[0]])
        o = self.pal.activate(row, exec_dialog=False)                        # (sans le formulaire)
        self.assertIsNotNone(o)
        self.assertTrue([tp for tp in self.p.toolpaths if tp.op_id == o.id])

    def test_a_folder_opens_once_on_a_double_click(self):
        from vectordrive.ui.cam_palette import ROLE_GROUP
        self.w.show_cam_palette() if hasattr(self.w, 'show_cam_palette') else None
        t = self.pal.tree
        top = next(t.topLevelItem(i) for i in range(t.topLevelItemCount()) if t.topLevelItem(i).data(0, ROLE_GROUP))
        t.scrollToTop()
        top.setExpanded(False)
        app.processEvents()
        pt = t.visualItemRect(top).center()
        with mock.patch.object(self.p, 'new_operation') as op:
            QTest.mouseClick(t.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pt)
            QTest.mouseDClick(t.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pt)
            app.processEvents()
        self.assertTrue(top.isExpanded(), 'avant : déplié au clic, replié au second')
        op.assert_not_called()

    def test_a_family_with_children_opens_on_a_click(self):
        fam = self.family('trous')
        self.assertGreater(fam.childCount(), 0)
        fam.setExpanded(False)
        with mock.patch.object(self.p, 'new_family') as made:
            self.pal.tree.itemClicked.emit(fam, 0)
        self.assertTrue(fam.isExpanded(), 'avant : un clic sur la famille ne la dépliait pas')
        made.assert_not_called()                                             # rien de créé
        self.pal.tree.itemClicked.emit(fam, 0)
        self.assertFalse(fam.isExpanded())                                   # comme un dossier

    def test_the_help_says_double_click(self):
        self.assertIn('double clic', self.pal.hint.text())
        from vectordrive.ui import cam_palette
        self.assertIn('double clic', cam_palette.__doc__)


# --- (a.6) le plan du programme en colonne repliable ------------------------------------------------------------
class Outline(Base):

    def setUp(self):
        super().setUp()
        self.p.compute()
        self.w.show_program()
        app.processEvents()
        self.prog.refresh()

    def test_folded_is_a_narrow_band_and_the_text_widens(self):
        fold = getattr(self.prog, 'fold_outline', None)
        self.assertIsNotNone(fold, 'avant : le plan se cachait, sans colonne repliée')
        fold(False)
        app.processEvents()
        wide = self.prog.text.width()
        fold(True)
        app.processEvents()
        self.assertTrue(self.prog.outline.isHidden())
        self.assertFalse(self.prog.plan_col.isHidden())                      # la bande reste
        self.assertLessEqual(self.prog.plan_col.width(), 24)
        self.assertGreater(self.prog.plan_col.width(), 0)
        self.assertEqual(self.prog.plan_head.text(), '▸')
        self.assertGreater(self.prog.text.width(), wide)                     # le texte prend la place
        self.assertTrue(self.prog.outline_folded())

    def test_the_unfolded_width_comes_back(self):
        from vectordrive.ui import program_window as PW
        self.prog.fold_outline(False)
        app.processEvents()
        total = sum(self.prog.split.sizes())
        self.prog.split.setSizes([260, total - 260])
        self.prog.split.splitterMoved.emit(260, 1)
        self.assertAlmostEqual(int(self.w.settings.value(PW.OUTLINE_WIDTH_KEY)), 260, delta=3)
        self.prog.fold_outline(True)
        app.processEvents()
        self.prog.fold_outline(False)
        app.processEvents()
        self.assertAlmostEqual(self.prog.split.sizes()[0], 260, delta=3)
        self.assertTrue(self.prog.plan_head.text().startswith('▾'))
        self.w.settings.setValue(PW.OUTLINE_WIDTH_KEY, 10)                   # trop étroit : de quoi lire ses lignes
        self.prog.fold_outline(True)
        self.prog.fold_outline(False)
        app.processEvents()
        self.assertGreaterEqual(self.prog.split.sizes()[0], PW.OUTLINE_MIN - 2)

    def test_kept_from_one_session_to_the_next(self):
        from vectordrive.ui.main_window import MainWindow
        self.prog.fold_outline(True)
        self.assertIn(self.w.settings.value('fao/programme_plan'), (False, 'false'))   # la clé garde son sens
        w2 = MainWindow()
        self.addCleanup(lambda: (setattr(w2, 'modified', False), w2.close(), w2.deleteLater()))
        p2 = w2.program_panel
        self.assertTrue(p2.outline_folded())
        self.assertFalse(p2.buttons['outline'].isChecked())
        self.assertFalse(p2.plan_col.isHidden())

    def test_the_burger_and_the_view_menu_fold_and_unfold(self):
        b = self.prog.buttons['outline']
        self.assertTrue(b.isChecked())
        b.click()
        self.assertTrue(self.prog.outline.isHidden())
        self.assertFalse(getattr(self.prog, 'plan_col', self.prog.outline).isHidden(), 'avant : caché tout entier')
        self.prog._fill_view_menu()
        a = next(x for x in self.prog.view_menu.actions() if x.text() == 'Plan du programme')
        self.assertFalse(a.isChecked())
        a.trigger()                                                          # déplié par le menu Vue
        self.assertFalse(self.prog.outline.isHidden())
        self.assertTrue(b.isChecked())
        self.prog.plan_head.click()                                          # l'en-tête replie
        self.assertTrue(self.prog.outline_folded())
        self.assertFalse(b.isChecked())
        self.prog.plan_head.click()                                          # la bande déplie
        self.assertFalse(self.prog.outline_folded())

    def test_folded_with_the_text_in_its_column_or_at_the_center(self):
        from vectordrive.ui import program_window as PW
        self.prog.fold_outline(True)
        if getattr(self.w, 'dock_program_text', None) is not None:
            with mock.patch.object(self.prog, 'split_wanted', return_value=True):
                self.assertEqual(self.prog.place_viewer(), 'colonne')       # le texte dans sa colonne à part
                app.processEvents()
                self.assertTrue(self.prog.outline_folded())
                self.assertLessEqual(self.prog.plan_col.width(), 24)
                self.w.dock_program_text.resize(260, 400)                    # une colonne étroite
                app.processEvents()
                self.prog.fold_outline(False)
                app.processEvents()
                sizes = self.prog.split.sizes()
                self.assertGreater(sizes[0], PW.OUTLINE_BAND)
                self.assertGreater(sizes[1], 0)                              # le texte garde sa place
            self.prog.place_viewer()
            app.processEvents()
        self.prog.fold_outline(True)
        self.w.program_center(True)
        app.processEvents()
        try:
            self.assertTrue(self.w.program_centered())
            self.assertTrue(self.prog.outline_folded())
            self.assertFalse(self.prog.plan_col.isHidden())
            self.assertLessEqual(self.prog.plan_col.width(), 24)
        finally:
            self.w.program_center(False)
            app.processEvents()


# --- (a.7) l'œil (affichage) et le bouton marche/arrêt (le programme) ------------------------------------------------
class Provider:
    """Un plugin d'essai qui tient ses opérations (comme celles d'une machine)."""
    label = 'Essai'
    posts = ()
    KEY = 'essai_1163'

    def __init__(self):
        self.calls = []

    def rows(self, doc):
        return [{'ref': o['id'], 'label': o['label'], 'tool': 'T9', 'enabled': o.get('on', True)}
                for o in doc.extra.get(self.KEY, [])]

    def set_enabled(self, doc, ref, on):
        self.calls.append(('set_enabled', ref, on))
        for o in doc.extra.get(self.KEY, []):
            if o['id'] == ref:
                o['on'] = on


class OnOff(Base):

    def setUp(self):
        super().setUp()
        self.p.compute()
        self.assertEqual([tp.name for tp in self.p.toolpaths], ['Plaque avant', 'Détourage été'])

    def drawn(self):
        return [tp.name for tp, _c in self.w.canvas.toolpaths]

    def test_the_eye_only_hides(self):
        self.p.toggle_op_paths(1, False)
        self.assertFalse(self.p.toolpaths[1].shown)
        self.assertEqual(self.drawn(), ['Plaque avant'])                     # le dessin le cache…
        self.assertIn('(Détourage été)', self.program(), 'avant : fermer l’œil retirait le parcours du programme')
        self.assertEqual([tp.name for tp in self.p.current_paths(dates=False)], ['Plaque avant', 'Détourage été'])
        self.assertEqual([tp.name for tp in self.p.checked_paths()], ['Plaque avant', 'Détourage été'])

    def test_the_power_button_replaces_the_checkbox(self):
        from vectordrive.ui.eye import IconCheckDelegate
        t = self.p.ops
        d = t.itemDelegateForColumn(0)
        self.assertIsInstance(d, IconCheckDelegate)
        idx = t.model().index(1, 0)
        self.assertGreater(greens(d, t, idx), 3)                             # en marche : le bouton vert
        opt = option(t, idx)
        box = d.check_rect(opt, idx)
        self.assertIn('Dans le programme (SimPL) : oui', d.tip_at(opt, idx, box.center()))
        self.assertTrue(d.editorEvent(release(t, box.center()), t.model(), opt, idx))   # un clic sur le bouton
        o = self.p.setup().operations[1]
        self.assertFalse(o.enabled)
        self.assertEqual(greens(d, t, t.model().index(1, 0)), 0)             # à l'arrêt : gris
        self.assertIn('non', d.tip_at(option(t, t.model().index(1, 0)), t.model().index(1, 0), box.center()))
        self.assertIn('Détourage été', self.drawn())                         # toujours montré…
        self.assertNotIn('(Détourage été)', self.program())                  # … mais hors du programme
        self.assertIn('(Plaque avant)', self.program())

    def test_no_more_hidden_warning(self):
        self.assertFalse(hasattr(self.p, 'hidden_active_ops'), 'avant : « opération cachée : hors du programme »')
        self.p.toggle_op_paths(0, False)
        self.p.toggle_op_paths(1, False)
        self.p._report()
        self.assertNotIn('⚠', self.p.info.text())
        self.w.show_program()
        app.processEvents()
        self.prog.refresh()
        self.assertNotIn('⚠', self.prog.status.text())
        self.assertFalse(self.prog.buttons['all'].isVisibleTo(self.prog))    # rien à remettre en marche
        self.assertIn('(Détourage été)', self.prog.text.toPlainText())

    def test_the_toolpath_list_has_both(self):
        from vectordrive.ui.eye import IconCheckDelegate
        lst = self.p.paths
        d = lst.itemDelegate()
        self.assertIsInstance(d, IconCheckDelegate)
        idx = lst.model().index(1, 0)
        opt = option(lst, idx)
        on = d.extra_rect(opt, idx)                                          # l'icône de la ligne : marche/arrêt
        self.assertFalse(on.isEmpty())
        self.assertIn('Dans le programme (SimPL) : oui', d.tip_at(opt, idx, on.center()))
        self.assertIn('Parcours affiché', d.tip_at(opt, idx, d.check_rect(opt, idx).center()))   # la case : l'œil
        self.assertTrue(d.editorEvent(release(lst, on.center()), lst.model(), opt, idx))
        self.assertFalse(self.p.toolpaths[1].on)
        self.assertTrue(self.p.toolpaths[1].shown)
        self.assertEqual(lst.item(1).checkState(), Qt.CheckState.Checked)    # l'œil n'a pas bougé
        self.assertIn('Détourage été', self.drawn())
        self.assertNotIn('(Détourage été)', self.program())
        self.assertTrue(self.p.set_path_on(1, True))
        self.assertIn('(Détourage été)', self.program())
        lst.item(1).setCheckState(Qt.CheckState.Unchecked)                   # l'œil fermé : caché, pas retiré
        self.assertNotIn('Détourage été', self.drawn())
        self.assertIn('(Détourage été)', self.program())

    def test_all_off_writes_nothing(self):
        self.p.set_path_on(0, False)
        self.p.set_path_on(1, False)
        with mock.patch.object(self.p, 'compute', wraps=self.p.compute) as again:
            self.assertEqual(self.p.current_paths(dates=False), [])
        again.assert_not_called()                                            # pas un calcul qui les remettrait

    def test_layers_follow_the_eye_only(self):
        from vectordrive.ui.layers import TRAJ, TRAJ_PATH
        lp = self.w.layers_panel
        lp.refresh()

        def row(i):
            t = lp.tree
            traj = next(t.topLevelItem(k) for k in range(t.topLevelItemCount())
                        if t.topLevelItem(k).data(lp.COL_NAME, Qt.ItemDataRole.UserRole) == TRAJ)
            return next(traj.child(k) for k in range(traj.childCount())
                        if traj.child(k).data(lp.COL_NAME, Qt.ItemDataRole.UserRole) == TRAJ_PATH
                        and traj.child(k).data(lp.COL_NAME, Qt.ItemDataRole.UserRole + 1) == i)
        self.assertTrue(self.p.set_path_on(1, False))
        lp.refresh()
        self.assertEqual(row(1).checkState(lp.COL_VIS), Qt.CheckState.Checked)   # arrêté : toujours montré
        row(1).setCheckState(lp.COL_VIS, Qt.CheckState.Unchecked)            # caché d'ici : l'œil seulement
        self.assertFalse(self.p.toolpaths[1].shown)
        self.assertFalse(self.p.toolpaths[1].on)
        self.p.set_path_on(1, True)
        self.assertFalse(self.p.toolpaths[1].shown)
        self.assertIn('(Détourage été)', self.program())

    def test_simulation_follows_the_power_button_not_the_eye(self):
        self.p.toggle_op_paths(0, False)                                     # caché : simulé quand même
        self.p.set_path_on(1, False)                                         # arrêté : pas simulé
        with mock.patch('vectordrive.ui.sim_dialog.SimDialog') as dlg:
            self.p.simulate(exec_dialog=False)
        self.assertEqual([tp.name for tp in dlg.call_args[0][1]], ['Plaque avant'])
        self.p.set_path_on(1, True)
        self.p.ops.selectRow(1)
        with mock.patch.object(self.w, 'show_toolpaths'):
            self.p.simulate_op('sim2d')                                      # une seule opération : la sienne
        self.assertEqual([tp.name for tp in self.p.sim_paths(self.p.checked_paths())], ['Détourage été'])
        self.p.set_path_on(0, True)                                          # (rien n'a changé : déjà en marche)
        self.p.toggle_op_paths(0, True)                                      # un œil touché : de nouveau tous
        self.assertEqual(len(self.p.sim_paths(self.p.checked_paths())), 2)

    def test_external_operations_are_told(self):
        from vectordrive import plugins
        from vectordrive.ui.eye import IconCheckDelegate
        pr = Provider()
        plugins.Api(plugins.REGISTRY, None).add_operation_provider(Provider.KEY, pr)
        self.addCleanup(lambda: getattr(plugins.REGISTRY, 'op_providers', {}).pop(Provider.KEY, None))
        self.w.canvas.doc.extra[Provider.KEY] = [{'id': 'a', 'label': 'Op A'}]
        self.p.refresh()
        t = self.p.ops
        r = next(r for r in range(t.rowCount()) if t.item(r, 0).text().startswith('Op A'))
        d = t.itemDelegateForColumn(0)
        self.assertIsInstance(d, IconCheckDelegate)
        idx = t.model().index(r, 0)
        opt = option(t, idx)
        d.editorEvent(release(t, d.check_rect(opt, idx).center()), t.model(), opt, idx)
        self.assertIn(('set_enabled', 'a', False), pr.calls)

    def test_kept_by_the_session_and_the_tabs(self):
        from vectordrive.ui import session
        tps = self.p.toolpaths
        self.p.set_path_on(1, False)
        self.p.toggle_op_paths(0, False)
        back = session.paths_from_bytes(session.paths_bytes(tps))
        self.assertEqual([(tp.shown, tp.on) for tp in back], [(False, True), (True, False)])
        key = session.paths_key(tps)
        self.p.set_path_on(1, True)
        self.assertNotEqual(session.paths_key(tps), key)                     # la session le réécrit
        self.p.set_path_on(1, False)
        self.w.new_document()
        self.w.switch_tab(0)
        self.assertEqual([getattr(tp, 'on', True) for tp in self.p.toolpaths], [True, False])

    def test_a_hidden_toolpath_from_before_stays_out_of_the_program(self):
        from vectordrive.ui import session
        tps = self.p.toolpaths
        tps[1].shown = False
        raw = gzip.decompress(session.paths_bytes(tps))
        (n,) = struct.unpack_from('<I', raw, 4)
        heads = json.loads(raw[8:8 + n].decode('utf-8'))
        for h in heads:
            h.pop('on', None)                                                # écrit avant ce round
        head = json.dumps(heads, ensure_ascii=False).encode('utf-8')
        old = gzip.compress(raw[:4] + struct.pack('<I', len(head)) + head + raw[8 + n:])
        back = session.paths_from_bytes(old)
        self.assertEqual([getattr(tp, 'on', None) for tp in back], [True, False])
        self.assertEqual([tp.shown for tp in back], [True, False])
        older = gzip.compress(json.dumps([{'name': 'Lu', 'shown': False, 'moves': []}]).encode('utf-8'))
        self.assertIs(getattr(session.paths_from_bytes(older)[0], 'on', None), False)

    def test_the_checks_follow_the_power_button(self):
        from vectordrive.cam import preflight, strategies
        tps = self.p.toolpaths
        s = self.p.setup()
        tps[1].shown = False                                                 # caché : rien à dire
        r = preflight.inspect(self.w.canvas.doc, s, tps, all_paths=tps)
        self.assertFalse(any('« Détourage été »' in t for _lv, t in r.notes), 'avant : « parcours décoché »')
        tps[1].on = False
        r = preflight.inspect(self.w.canvas.doc, s, [tps[0]], all_paths=tps)
        self.assertTrue(any('« Détourage été » : parcours à l\'arrêt' in t for _lv, t in r.notes))
        strategies.apply_faced_all(s, tps)                                   # (l'arrêté ne compte pas : sans erreur)

    # --- relecture : le bouton de l'opération suit ses parcours ; un recalcul les garde à l'arrêt ; mineurs
    def test_the_operation_button_follows_its_paths(self):
        t = self.p.ops
        d = t.itemDelegateForColumn(0)
        self.p.set_path_on(1, False)
        self.assertEqual(t.item(1, 0).checkState(), Qt.CheckState.PartiallyChecked, 'avant : toujours « en marche »')
        o = self.p.setup().operations[1]
        self.assertTrue(o.enabled)                                           # active : rien n'a changé pour elle
        idx = t.model().index(1, 0)
        opt = option(t, idx)
        box = d.check_rect(opt, idx)
        self.assertEqual(greens(d, t, idx), 0)                               # mi-teinte, pas vert
        self.assertIn('tous ses parcours à l’arrêt', d.tip_at(opt, idx, box.center()))
        self.assertIn('⚠', self.p.info.text())                               # le compte rendu le dit
        self.assertIn('à l’arrêt : hors du programme', self.p.info.text())
        self.w.show_program()
        app.processEvents()
        self.prog.refresh()
        self.assertIn('⚠', self.prog.status.text())                          # la fenêtre Programme aussi
        self.assertTrue(self.prog.buttons['all'].isVisibleTo(self.prog))
        self.assertTrue(d.editorEvent(release(t, box.center()), t.model(), opt, idx))   # un clic : rallumée
        self.assertTrue(self.p.toolpaths[1].on)
        self.assertTrue(self.p.setup().operations[1].enabled)
        self.assertEqual(t.item(1, 0).checkState(), Qt.CheckState.Checked)
        self.assertGreater(greens(d, t, t.model().index(1, 0)), 3)
        self.assertNotIn('⚠', self.p.info.text())
        self.assertIn('(Détourage été)', self.program())

    def test_partly_stopped_and_switched_back_on(self):
        import copy
        t = self.p.ops
        d = t.itemDelegateForColumn(0)
        twin = copy.copy(self.p.toolpaths[1])                                # une seconde passe de la même opération
        self.p.display(self.p.toolpaths + [twin])
        self.p.set_path_on(1, False)
        idx = t.model().index(1, 0)
        opt = option(t, idx)
        self.assertEqual(t.item(1, 0).checkState(), Qt.CheckState.PartiallyChecked)
        self.assertIn('En partie hors du programme', d.tip_at(opt, idx, d.check_rect(opt, idx).center()))
        self.assertNotIn('⚠', self.p.info.text())                            # une passe en marche : pas d'avis
        t.item(1, 0).setCheckState(Qt.CheckState.Unchecked)                  # éteinte, puis rallumée : tout repart
        self.assertFalse(self.p.setup().operations[1].enabled)
        self.assertEqual(t.item(1, 0).checkState(), Qt.CheckState.Unchecked)
        t.item(1, 0).setCheckState(Qt.CheckState.Checked)
        self.assertEqual([tp.on for tp in self.p.toolpaths], [True, True, True])
        self.assertEqual(t.item(1, 0).checkState(), Qt.CheckState.Checked)

    def test_a_recompute_keeps_it_stopped(self):
        s = self.p.setup()
        self.p.set_path_on(1, False)
        old = self.p.toolpaths[1]
        s.operations[1].depth = 0.3                                          # retouchée (formulaire, OK)
        self.p.save(s)
        self.p.compute_op(self.p.setup().operations[1])
        self.assertIsNot(self.p.toolpaths[1], old)                           # un parcours neuf…
        self.assertFalse(self.p.toolpaths[1].on, 'avant : remis en marche par le recalcul')   # … toujours à l'arrêt
        self.assertTrue(self.p.toolpaths[0].on)
        self.assertNotIn('(Détourage été)', self.program())
        s = self.p.setup()
        s.operations[1].depth = 0.4
        self.p.save(s)
        self.p.compute()                                                     # « Calculer »
        self.assertEqual([tp.on for tp in self.p.toolpaths], [True, False])
        self.assertEqual(self.p.ops.item(1, 0).checkState(), Qt.CheckState.PartiallyChecked)
        self.assertNotIn('(Détourage été)', self.program())

    def test_the_single_simulation_ends(self):
        self.p.ops.selectRow(1)
        with mock.patch.object(self.w, 'show_toolpaths'):
            self.p.simulate_op('sim2d')
        self.assertEqual([tp.name for tp in self.p.sim_paths(self.p.checked_paths())], ['Détourage été'])
        self.p.compute()                                                     # un calcul : de nouveau tous
        self.assertEqual(len(self.p.sim_paths(self.p.checked_paths())), 2)
        with mock.patch.object(self.w, 'show_toolpaths'):
            self.p.simulate_op('sim2d')
        self.p.toolpaths[1].on = False                                       # (à l'arrêt sans passer par le bouton)
        self.w.statusBar().clearMessage()
        self.assertEqual([tp.name for tp in self.p.sim_paths(self.p.checked_paths())], ['Plaque avant'])
        self.assertIn('tous les parcours en marche sont simulés', self.w.statusBar().currentMessage())
        self.p.toolpaths[1].on = True
        with mock.patch.object(self.w, 'show_toolpaths'):
            self.p.simulate_op('sim2d')
        self.w.new_document()                                                # un autre onglet : plus d'opération
        self.assertEqual(self.p.sim_paths(['a', 'b']), ['a', 'b'])           # seule
        self.w.switch_tab(0)
        self.assertEqual(len(self.p.sim_paths(self.p.checked_paths())), 2)
        self.p.ops.selectRow(1)
        with mock.patch.object(self.w, 'show_toolpaths'):
            self.p.simulate_op('sim2d')
        self.p.ops.selectRow(1)
        self.p.remove_op()                                                   # retirée : finie
        self.assertEqual(self.p._sim_only, '')

    def test_the_3d_view_follows_the_eye_only(self):
        p3 = self.w._ensure_panel3d()
        self.p.set_path_on(1, False)                                         # à l'arrêt : toujours montré en 3D
        self.assertEqual([tp.name for tp in p3._shown_paths(self.p)], ['Plaque avant', 'Détourage été'])
        self.p.toggle_op_paths(0, False)                                     # l'œil fermé : plus montré
        self.assertEqual([tp.name for tp in p3._shown_paths(self.p)], ['Détourage été'])
        self.p.toggle_op_paths(1, False)
        p3.source.blockSignals(True)
        p3.source.setCurrentIndex(p3.source.findData('parcours'))
        p3.source.blockSignals(False)
        with mock.patch.object(p3, '_model_source', lambda: None), mock.patch.object(self.w, 'view_mode', lambda: '3d'):
            self.assertFalse(p3.refresh())
        self.assertIn('leur œil est fermé', p3.info.text())

    def test_the_time_counts_running_paths_only(self):
        self.p._report()
        whole = self.p.last_estimate['total']
        self.p.set_path_on(1, False)
        self.assertLess(self.p.last_estimate['total'], whole, 'avant : le parcours arrêté comptait')
        self.assertIn('Détourage été : à l’arrêt, hors du programme et du temps estimé', self.p.info.text())

    def press(self, widget, key, mods):
        from PySide6.QtGui import QKeyEvent
        ev = QKeyEvent(QEvent.Type.KeyPress, key, mods)
        app.sendEvent(widget, ev)
        return ev

    def test_ctrl_space_switches_the_chosen_path(self):
        from PySide6.QtGui import QAction
        from vectordrive.ui import shortcuts
        lst = self.p.paths
        lst.setCurrentRow(1)
        self.press(lst, Qt.Key.Key_Space, Qt.KeyboardModifier.ControlModifier)
        self.assertFalse(self.p.toolpaths[1].on, 'avant : pas de touche pour marche/arrêt')
        self.assertTrue(self.p.toolpaths[1].shown)                           # (Espace : l'œil)
        self.press(lst, Qt.Key.Key_Space, Qt.KeyboardModifier.ControlModifier)
        self.assertTrue(self.p.toolpaths[1].on)
        used = [sc for sc in self.w.findChildren(QShortcut) if sc.key().toString() == 'Ctrl+Space']
        used += [a for a in self.w.findChildren(QAction) if any(q.toString() == 'Ctrl+Space' for q in a.shortcuts())]
        self.assertEqual(used, [])                                           # pas un raccourci : rien d'ambigu
        self.assertTrue(any(k == 'Ctrl + Espace' for _w, k, _e in shortcuts.FIXED_KEYS))   # dans la liste F10
        self.assertEqual(shortcuts.fixed_keys_in('Ctrl+Space'), 'Ctrl + Espace')
        idx = lst.model().index(1, 0)
        opt = option(lst, idx)
        self.assertIn('(Ctrl+Espace)', lst.itemDelegate().tip_at(opt, idx, lst.itemDelegate().extra_rect(opt, idx)
                                                                 .center()))

    def test_a_user_shortcut_on_ctrl_space_wins(self):
        from PySide6.QtGui import QAction, QKeySequence
        hit = []
        a = QAction('essai', self.w)
        a.setShortcut(QKeySequence('Ctrl+Space'))
        a.triggered.connect(lambda _=False: hit.append(1))
        self.w.addAction(a)
        self.p.paths_group.show()
        self.w.raise_()
        self.w.activateWindow()
        QApplication.setActiveWindow(self.w)
        if not QTest.qWaitForWindowActive(self.w, 2000) or not self.w.isActiveWindow():
            self.skipTest('fenêtre pas active (plateforme sans gestion des fenêtres)')
        self.p.paths.setFocus()
        self.p.paths.setCurrentRow(1)
        app.processEvents()
        QTest.keyClick(self.p.paths, Qt.Key.Key_Space, Qt.KeyboardModifier.ControlModifier)
        app.processEvents()
        self.assertEqual(hit, [1], 'avant (QShortcut) : ambigu, ni l’un ni l’autre')   # sa commande, une fois…
        self.assertTrue(self.p.toolpaths[1].on)                                  # … et pas marche/arrêt en plus

    def test_a_removed_path_does_not_come_back(self):
        self.p.paths.setCurrentRow(1)
        self.p.remove_path()                                                 # retiré par ✕
        self.assertEqual([tp.name for tp in self.p.toolpaths], ['Plaque avant'])
        self.p.set_path_on(0, False)
        with mock.patch.object(self.p, '_inputs_changed', return_value=False), \
                mock.patch.object(self.p, 'compute_op', side_effect=AssertionError('recalculé')):
            self.assertEqual(self.p.current_paths(dates=False), [], 'avant : le parcours retiré revenait en marche')
        self.assertEqual([tp.name for tp in self.p.toolpaths], ['Plaque avant'])

    def test_all_stopped_after_a_drawing_change_and_no_active_operation(self):
        self.p.set_path_on(0, False)
        self.p.set_path_on(1, False)
        with mock.patch.object(self.p, '_inputs_changed', return_value=True):  # le dessin a changé : recalculés
            self.assertEqual(self.p.current_paths(dates=False), [])
        self.assertEqual([tp.on for tp in self.p.toolpaths], [False, False])
        self.assertIn('Tous les parcours sont à l’arrêt', self.p.info.text())
        s = self.p.setup()
        for o in s.operations:
            o.enabled = False
        self.p.save(s)
        self.assertEqual(self.p.program_preview(recompute=False)['note'], 'Aucune opération active')

    # --- 2e relecture : l'état réel (opération désactivée ou retirée), le calcul des opérations neuves, mineurs
    def test_the_button_says_what_is_really_written(self):
        from vectordrive.ui.eye import power_pixmap
        lst = self.p.paths
        d = lst.itemDelegate()
        s = self.p.setup()
        s.operations[1].enabled = False                                      # désactivée : pas écrite
        self.p.save(s)
        idx = lst.model().index(1, 0)
        opt = option(lst, idx)
        self.assertIn('opération est désactivée', d.tip_at(opt, idx, d.extra_rect(opt, idx).center()),
                      'avant : « Dans le programme : oui »')
        fmt = QImage.Format.Format_ARGB32
        self.assertEqual(lst.item(1).icon().pixmap(18, 18).toImage().convertToFormat(fmt),
                         power_pixmap(None).toImage().convertToFormat(fmt))  # mi-teinte, pas vert
        self.p._report()
        self.assertIn('Détourage été : opération désactivée, hors du programme et du temps estimé', self.p.info.text())
        whole = self.p.last_estimate['total']
        s = self.p.setup()
        s.operations[1].enabled = True
        self.p.save(s)
        self.p._report()
        self.assertGreater(self.p.last_estimate['total'], whole)             # le temps : ce qui est écrit
        s = self.p.setup()
        del s.operations[1]                                                  # retirée (Annuler…) : son parcours
        self.p.save(s)                                                       # devient une ligne sans opération
        t = self.p.ops
        r = next(r for r in range(t.rowCount()) if t.item(r, 0) is not None and t.item(r, 0).text() == 'Détourage été')
        idx = t.model().index(r, 0)
        opt = option(t, idx)
        dd = t.itemDelegateForColumn(0)
        self.assertIn('opération a été retirée', dd.tip_at(opt, idx, dd.check_rect(opt, idx).center()))
        self.assertEqual(greens(dd, t, idx), 0)                              # pas le vert « écrit »
        self.assertNotIn('(Détourage été)', self.program())

    def test_all_stopped_but_a_new_operation_is_computed(self):
        from vectordrive.cam import model
        s = self.p.setup()
        sh = self.shapes[0]
        s.operations.append(model.Operation(name='Neuve', kind='gravure', tool_id=self.tool.id, items=[sh.id],
                                            depth=0.1))
        self.p.save(s)
        self.p.set_path_on(0, False)
        self.p.set_path_on(1, False)
        with mock.patch.object(self.p, '_inputs_changed', return_value=False), \
                mock.patch.object(self.p, 'compute', side_effect=AssertionError('tout recalculé')):
            got = self.p.current_paths(dates=False)
        self.assertEqual([tp.name for tp in got], ['Neuve'], 'avant : rien, sans avis')
        self.assertEqual([tp.on for tp in self.p.toolpaths], [False, False, True])   # les arrêtés le restent
        with mock.patch.object(self.p, '_inputs_changed', return_value=False):
            self.p.set_path_on(2, False)
            self.assertEqual(self.p.current_paths(dates=False), [])          # tous calculés, tous à l'arrêt : rien
        self.assertIn('à l’arrêt', self.p.info.text())
        self.assertIn('à l’arrêt', self.p.program_preview()['note'])          # pas « Mettre à jour les calcule »

    def test_the_3d_view_hides_disabled_operations(self):
        p3 = self.w._ensure_panel3d()
        s = self.p.setup()
        s.operations[0].enabled = False
        self.p.save(s)
        self.assertEqual([tp.name for tp in p3._shown_paths(self.p)], ['Détourage été'])
        self.p.toggle_op_paths(1, False)
        p3.source.blockSignals(True)
        p3.source.setCurrentIndex(p3.source.findData('parcours'))
        p3.source.blockSignals(False)
        with mock.patch.object(p3, '_model_source', lambda: None), mock.patch.object(self.w, 'view_mode', lambda: '3d'):
            self.assertFalse(p3.refresh())
        self.assertIn('désactivées ou supprimées', p3.info.text())          # pas « changement du dessin »
        self.assertNotIn('changement du dessin', p3.info.text())


class Startup(Base):

    def test_a_folded_outline_at_startup_writes_no_width(self):
        from vectordrive.ui import program_window as PW
        from vectordrive.ui.main_window import MainWindow
        self.w.settings.setValue(PW.OUTLINE_KEY, False)
        self.w.settings.remove(PW.OUTLINE_WIDTH_KEY)
        w2 = MainWindow()
        self.addCleanup(lambda: (setattr(w2, 'modified', False), w2.close(), w2.deleteLater()))
        self.assertTrue(w2.program_panel.outline_folded())
        self.assertIsNone(w2.settings.value(PW.OUTLINE_WIDTH_KEY), 'avant : écrite au démarrage')


if __name__ == '__main__':
    unittest.main()
