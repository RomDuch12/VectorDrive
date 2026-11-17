"""Round 1066 : atelier SimPL, phase 1 — demande du 17/11, 0 h 05 : « fusionner onglets_colonne Programme et Neodrive
(si postpro datron choisi) et la partie opération de l'onglet simpl, onglet simpl doit etre un viewer programme avec
pliages possibles, n°lignes, vue parametrable, fenetre à la place du dessin VD remplissant l'espace entre les colonnes
droite et gauche ». Côté cœur : un panneau de plugin peut être une partie de l'onglet Programme, montrée pour sa
machine ; au centre, le texte seul prend la place du dessin ; la vue du programme se règle."""
import inspect
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1066.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication, QLabel, QPlainTextEdit, QVBoxLayout, QWidget  # noqa: E402

from vectordrive import plugins  # noqa: E402
from vectordrive.cam import post  # noqa: E402

app = QApplication.instance() or QApplication([])

BEFORE = 'avant : un panneau de plugin ne peut pas être une partie de l’onglet Programme'
VIEW_BEFORE = 'avant : la vue du programme ne se règle pas'


def neo(win):
    """Le panneau d'une machine (comme NeoDrive) : un simple libellé."""
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.addWidget(QLabel('fonctions de la machine'))
    return w


def other(win):
    return QLabel('panneau ordinaire')


def writer(toolpaths, setup, *, title='', machine=None, stem='p', box_mm=None, machine_dir=''):
    return post.PostResult('', [], '.txt')


def spin(n=3):
    for _ in range(n):
        app.processEvents()


class Base(unittest.TestCase):

    def setUp(self):
        self.assertIn('host', inspect.signature(plugins.Api.add_panel).parameters, BEFORE)
        r = plugins.REGISTRY
        self.saved = (dict(r.posts), list(r.post_providers), list(r.actions), list(r.panels), list(r.post_hooks),
                      dict(r.post_exports))
        self.addCleanup(self.restore)
        api = plugins.Api(r, plugins.PluginInfo('essai', 'essai'))
        api.add_post('essai_simpl', 'Machine d’essai', writer)
        api.add_panel('essai_neo', 'ESSAI — Fonctions', neo, posts=('essai_simpl',), host='programme')
        api.add_panel('essai_autre', 'ESSAI — Ordinaire', other, posts=('essai_simpl',))
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.addCleanup(self.close)
        self.p = self.w.program_panel

    def restore(self):
        r = plugins.REGISTRY
        r.posts, r.post_providers, r.actions, r.panels, r.post_hooks, r.post_exports = self.saved

    def close(self):
        st = self.w.settings
        for key in ('fao/programme_vue', 'fao/programme_parties'):
            st.remove(key)
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        spin()

    def choose(self, key):
        self.w.cam_panel.set_post(key)
        spin()


class Hosted(Base):

    def test_the_panel_is_a_part_of_the_program_tab(self):
        self.assertNotIn('essai_neo', self.w.plugin_docks)                  # pas un panneau à part
        self.assertIn('essai_neo', self.p.hosted)
        self.assertIn('essai_autre', self.w.plugin_docks)                   # sans `host` : un panneau comme avant
        self.assertEqual(plugins.PanelSpec('k', 'Titre', neo).host, '')

    def test_shown_only_for_its_machine(self):
        self.assertEqual(self.p.sections_shown(), [])                       # sa machine n'est pas choisie
        self.assertTrue(self.p.sections_box.isHidden())
        self.choose('essai_simpl')
        self.assertEqual(self.p.sections_shown(), ['essai_neo'])
        self.assertFalse(self.p.sections_box.isHidden())
        self.choose('iso')
        self.assertEqual(self.p.sections_shown(), [])
        self.assertTrue(self.p.sections_box.isHidden())

    def test_a_part_folds_under_its_header_and_it_is_kept(self):
        self.choose('essai_simpl')
        frame, head, widget, _title = self.p.hosted['essai_neo']
        self.assertTrue(head.text().startswith('▾'))
        head.click()                                                         # replié sous son en-tête
        self.assertTrue(widget.isHidden())
        self.assertTrue(head.text().startswith('▸'))
        self.assertIn(self.w.settings.value('fao/programme_parties/essai_neo'), (False, 'false'))
        from vectordrive.ui.main_window import MainWindow
        w2 = MainWindow()                                                    # retenu
        self.addCleanup(lambda: (setattr(w2, 'modified', False), w2.close(), w2.deleteLater()))
        self.assertTrue(w2.program_panel.hosted['essai_neo'][2].isHidden())
        head.click()
        self.assertFalse(widget.isHidden())

    def test_in_the_centre_the_text_alone_takes_the_drawing_place(self):
        w, p = self.w, self.p
        w.show()
        self.choose('essai_simpl')
        w.show_program()
        spin()
        self.assertTrue(w.program_center(True))
        spin()
        self.assertTrue(w.program_centered())
        self.assertIs(w.stage.currentWidget(), p.viewer.parentWidget())     # le texte au centre…
        self.assertIs(w.dock_program.widget(), p)                           # … la machine et les parties restent
        self.assertFalse(w.dock_program.isHidden())                         # dans la colonne
        self.assertFalse(p.hosted['essai_neo'][0].isHidden())
        self.assertFalse(w.canvas.isVisible())
        w.dock_program.setVisible(True)                                      # sa fenêtre montrée : pas vide, il reste
        spin()
        self.assertTrue(w.program_centered())
        self.assertFalse(w.program_center(False))
        spin()
        self.assertIs(p.viewer.parentWidget(), p.vsplit)                    # de retour sous les parties
        self.assertTrue(w.canvas.isVisible())
        self.assertFalse(w.dock_program.isHidden())

    def test_without_parts_the_whole_panel_goes_to_the_centre_as_before(self):
        w, p = self.w, self.p
        w.show()
        self.assertTrue(w.program_center(True))
        spin()
        self.assertTrue(w.program_centered())
        spin()
        self.assertIs(w.stage.currentWidget(), p.parentWidget())
        self.assertTrue(w.dock_program.isHidden())
        w.program_center(False)
        spin()
        self.assertIs(w.dock_program.widget(), p)
        self.assertIs(p.viewer.parentWidget(), p.vsplit)


class Centred(Base):
    """Le texte seul au centre : il reste à jour, sa fenêtre se rouvre, la machine qui change refait le partage."""

    def centre_text(self):
        w = self.w
        w.show()
        self.choose('essai_simpl')
        w.show_program()
        spin()
        w.program_center(True)
        spin()
        self.assertIsNot(w._program_part, self.p)

    def test_live_while_its_window_is_closed(self):
        w, p = self.w, self.p
        self.centre_text()
        p.live.setChecked(True)
        w.dock_program.hide()                                                # sa fenêtre fermée, le texte au centre
        spin()
        self.assertTrue(w.dock_program.isHidden())
        self.assertFalse(p.isVisible())
        p.timer.stop()
        p.notify()
        self.assertTrue(p.timer.isActive())                                 # avant : plus de mise à jour en direct
        self.assertFalse(p.buttons['update_here'].isHidden())               # son propre ⟳ au centre
        w.show_program()                                                     # « Programme machine » : sa fenêtre
        spin()
        self.assertFalse(w.dock_program.isHidden())                         # rouverte (machine, parties)
        self.assertTrue(w.program_centered())

    def test_a_machine_change_while_centred_shares_again(self):
        w, p = self.w, self.p
        w.show()
        w.program_center(True)                                               # tout le panneau au centre…
        spin()
        self.assertIs(w._program_part, p)
        self.choose('essai_simpl')                                           # … sa machine a des parties : le texte
        self.assertTrue(w.program_centered())                               # seul au centre, les parties dans la
        self.assertIs(p.viewer.parentWidget(), w.stage.currentWidget())     # colonne
        self.assertIs(w.dock_program.widget(), p)
        self.choose('iso')                                                   # plus de parties : tout le panneau
        self.assertTrue(w.program_centered())
        self.assertIs(p.parentWidget(), w.stage.currentWidget())
        self.assertTrue(w.dock_program.isHidden())                          # jamais une fenêtre vide

    def test_its_window_is_ranged_like_the_others_and_no_full_screen_over_it(self):
        from vectordrive.ui import columns as C
        w = self.w
        self.centre_text()
        rows = C.PanelRows.__new__(C.PanelRows)
        rows.columns = w.columns
        self.assertFalse(rows._central(w.dock_program))                     # sa fenêtre n'est pas « au centre »
        w.columns.toggle_overlay(w.dock_program)                             # plein écran de sa fenêtre : le texte
        spin()                                                               # rentre d'abord
        self.assertFalse(w.program_centered())
        ov = w.columns.overlay(w.dock_program, create=False)
        if ov is not None and ov.active:
            w.columns.toggle_overlay(w.dock_program)
            spin()

    def test_the_original_text_size_is_the_application_one(self):
        size = QApplication.font().pointSizeF()
        if size > 0:
            self.assertEqual(self.p.text.font().pointSizeF(), size)        # avant : 12 points d'office


class View(Base):

    def setUp(self):
        super().setUp()
        self.assertTrue(hasattr(self.p, 'view'), VIEW_BEFORE)
        self.p.text.setPlainText('\n'.join(f'G1 X{k} Y{k}' for k in range(200)))

    def test_text_size(self):
        before = self.p.text.font().pointSizeF()
        self.assertEqual(self.p.zoom(1), round(before) + 1)
        self.assertGreater(self.p.text.font().pointSizeF(), before)
        self.p.zoom(-1)
        self.p.zoom(-1)
        self.assertLess(self.p.text.font().pointSizeF(), before)
        self.p.zoom(0)                                                       # taille d'origine
        self.assertEqual(self.p.text.font().pointSizeF(), before)
        for _ in range(60):
            self.p.zoom(1)
        self.assertEqual(self.p.text.font().pointSizeF(), 32)               # bornée

    def test_line_numbers_wrap_and_colours(self):
        t = self.p.text
        wide = t.gutter_width()
        self.p.set_view('numeros', False)
        self.assertLess(t.gutter_width(), wide)                             # les marques de repli seules
        self.assertFalse(t.numbers)
        self.p.set_view('retour', True)
        self.assertEqual(t.lineWrapMode(), QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.p.set_view('couleurs', False)
        self.assertIsNone(self.p.highlighter.document())
        self.p.set_view('couleurs', True)
        self.assertIs(self.p.highlighter.document(), t.document())

    def test_the_view_is_kept(self):
        self.p.set_view('numeros', False)
        self.p.set_view('retour', True)
        self.p.zoom(3)
        size = self.p.text.font().pointSizeF()
        from vectordrive.ui.main_window import MainWindow
        w2 = MainWindow()
        self.addCleanup(lambda: (setattr(w2, 'modified', False), w2.close(), w2.deleteLater()))
        p2 = w2.program_panel
        self.assertFalse(p2.text.numbers)
        self.assertEqual(p2.text.lineWrapMode(), QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.assertEqual(p2.text.font().pointSizeF(), size)

    def test_the_view_menu(self):
        self.p._fill_view_menu()
        names = [a.text() for a in self.p.view_menu.actions() if a.text()]
        for want in ('Agrandir le texte', 'Réduire le texte', 'Numéros de ligne', 'Retour à la ligne',
                     'Couleurs du langage', 'Plan du programme', 'Replier chaque parcours', 'Tout déplier'):
            self.assertIn(want, names)
        numbers = next(a for a in self.p.view_menu.actions() if a.text() == 'Numéros de ligne')
        numbers.toggle()
        self.assertFalse(self.p.text.numbers)
        self.assertIn('view', self.p.buttons)


if __name__ == '__main__':
    unittest.main()
