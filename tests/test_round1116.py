"""Round 1116 — demande du 20/11 : « Colonne datron parametres programme trop courte : Scale Y possible et utilise
mieux l'espace en X, Simpl colonne supplémentaire (à droite si la colonne datron est à gauche, à gauche si la colonne
est à droite) en sus de la colonne standard … la colonne supplémentaire et détachable affiche le simpl ». Côté cœur :
des parties de plugin montrées, le texte du programme a sa colonne à part, du côté opposé ; les parties se partagent
la colonne à la souris, la colonne défile (pas une partie)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1116.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget  # noqa: E402

from vectordrive import plugins  # noqa: E402
from vectordrive.cam import post  # noqa: E402

app = QApplication.instance() or QApplication([])

BEFORE = 'avant : le texte du programme reste sous les parties de la machine, dans la même colonne'
KEY = 'fao/programme_texte_colonne'


def part(text, height=0):
    def make(win):
        w = QWidget()
        lay = QVBoxLayout(w)
        label = QLabel(text)
        if height:
            label.setMinimumHeight(height)
        lay.addWidget(label)
        return w
    return make


def writer(toolpaths, setup, *, title='', machine=None, stem='p', box_mm=None, machine_dir=''):
    return post.PostResult('', [], '.txt')


def x(w, dock):
    from PySide6.QtCore import QPoint
    return dock.mapTo(w, QPoint(0, 0)).x()


def spin(n=4):
    for _ in range(n):
        app.processEvents()


class Base(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.assertTrue(hasattr(MainWindow, '_program_text_shown'), BEFORE)
        r = plugins.REGISTRY
        self.saved = (dict(r.posts), list(r.post_providers), list(r.actions), list(r.panels), list(r.post_hooks),
                      dict(r.post_exports))
        self.addCleanup(self.restore)
        api = plugins.Api(r, plugins.PluginInfo('essai', 'essai'))
        api.add_post('essai_col', 'Machine d’essai', writer)
        api.add_panel('essai_params', 'ESSAI — Paramètres programme', part('paramètres', 300), posts=('essai_col',),
                      host='programme')
        api.add_panel('essai_ops', 'ESSAI — Opérations', part('opérations'), posts=('essai_col',), host='programme')
        self.w = MainWindow()
        self.addCleanup(self.close)
        self.p = self.w.program_panel
        self.w.settings.remove(KEY)

    def restore(self):
        r = plugins.REGISTRY
        r.posts, r.post_providers, r.actions, r.panels, r.post_hooks, r.post_exports = self.saved

    def close(self):
        st = self.w.settings
        for key in ('fao/programme_vue', 'fao/programme_parties', KEY):
            st.remove(key)
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        spin()

    def choose(self, key):
        self.w.cam_panel.set_post(key)
        spin()

    def opened(self, side='gauche'):
        w = self.w
        w.show()
        self.choose('essai_col')
        w.columns.move(w.dock_program, side)
        w.show_program(refresh=False)
        spin()
        return w, self.p, w.dock_program_text


class TextColumn(Base):

    def test_the_option_is_on_by_default(self):
        from vectordrive.ui import options
        self.assertIn(KEY, options.BY_KEY)
        self.assertTrue(options.value(self.w.settings, KEY))

    def test_with_parts_the_text_has_its_own_column_beside(self):
        w, p, d = self.opened('gauche')
        self.assertIs(d.widget(), p.viewer, 'avant : sous les parties')
        self.assertFalse(d.isHidden())
        self.assertEqual(w.columns.side(w.dock_program), 'gauche')
        self.assertEqual(w.columns.side(d), 'gauche')
        self.assertGreater(x(w, d), x(w, w.dock_program) + 40)              # à sa droite, côté dessin
        self.assertEqual(w.tabifiedDockWidgets(d), [])
        self.assertIs(w.dock_program.widget(), p)                           # les parties restent dans la leur
        self.assertFalse(p.hosted['essai_params'][0].isHidden())
        self.assertFalse(p.hosted['essai_ops'][0].isHidden())
        self.assertFalse(p.buttons['update_here'].isHidden())               # ⟳ avec le texte

    def test_program_window_on_the_right_puts_the_text_on_its_left(self):
        w, p, d = self.opened('droite')
        dp = w.dock_program
        self.assertEqual(w.columns.side(d), 'droite')
        self.assertLess(x(w, d) + 40, x(w, dp))                             # à sa gauche, côté dessin
        self.assertFalse(dp.isHidden())
        self.assertEqual(w.tabifiedDockWidgets(d), [])
        w.columns.move(dp, 'gauche')                                        # la fenêtre change de côté : le texte suit
        spin()
        self.assertEqual(w.columns.side(d), 'gauche')
        self.assertGreater(x(w, d), x(w, dp) + 40)

    def test_the_columns_never_put_it_in_tabs(self):
        w, p, d = self.opened('gauche')
        w.columns.move(d, 'droite')                                         # « Colonne droite » de son menu
        spin()
        self.assertEqual(w.columns.side(d), 'droite')
        self.assertEqual(w.tabifiedDockWidgets(d), [])
        self.assertFalse(d.isHidden())
        w.columns.toggle_floating(d)                                        # détachée puis ancrée : à côté du programme
        spin()
        w.columns.toggle_floating(d)
        spin()
        self.assertEqual(w.columns.side(d), 'gauche')
        self.assertEqual(w.tabifiedDockWidgets(d), [])
        self.assertFalse(w.settings.contains('panneaux_colonnes/place/programme_texte'))

    def test_not_laid_out_again_at_each_machine(self):
        w, p, d = self.opened('droite')
        calls = []
        orig = w.removeDockWidget
        w.removeDockWidget = lambda dk: (calls.append(dk), orig(dk))
        self.choose('iso')
        self.choose('essai_col')
        self.assertEqual(calls, [])                                         # déjà à sa place : rien de refait
        self.assertFalse(d.isHidden())
        self.assertEqual(w.columns.side(d), 'droite')

    def test_the_layout_before_cam_is_forgotten(self):
        w, p, d = self.opened('droite')
        w._docks_before_cam = b'avant'
        p._laid = None
        p.put_text_dock()
        self.assertIsNone(w._docks_before_cam)

    def test_a_hidden_text_column_stays_hidden(self):
        w, p, d = self.opened('gauche')
        d.close()                                                           # fermée par sa croix
        spin()
        w._program_window_shown()                                           # l'onglet Programme remis devant…
        spin()
        self.assertTrue(d.isHidden())                                       # … elle ne revient pas d'elle-même
        w.show_program(refresh=False)                                       # le bouton Programme la rouvre
        spin()
        self.assertFalse(d.isHidden())

    def test_hidden_right_panels_stay_in_one_column(self):
        w = self.w
        w.show()
        w.dock_program.setFloating(True)                                    # fenêtre Programme détachée (d'office)
        w.columns.set_shown('droite', False)                                # la colonne de droite cachée
        spin()
        self.choose('essai_col')
        w.show_program(refresh=False)                                       # fenêtre Programme détachée (d'office)
        spin()
        d = w.dock_program_text
        self.assertIs(d.widget(), self.p.viewer)
        w.columns.set_shown('droite', False)                                # cachée avec le texte, puis remontrée
        spin()
        w.columns.set_shown('droite', True)
        spin()
        shown = [k for k in w.columns.column('droite') if k is not d and not k.isHidden()]
        self.assertTrue(shown)
        self.assertFalse(d.isHidden())                                      # le texte revient avec elle
        self.assertEqual(w.columns.side(d), 'droite')
        self.assertEqual(len(w.columns.blocks('droite')), 2, 'avant : chaque panneau caché remis en colonne à part')
        self.assertLess(x(w, d), min(x(w, k) for k in shown if w.columns.in_front(k)))   # à leur gauche

    def test_option_applied_when_f10_closes(self):
        w, p, d = self.opened()
        w.settings.setValue(KEY, False)
        w.apply_options()
        spin()
        self.assertIs(p.viewer.parentWidget(), p.vsplit)
        self.assertTrue(d.isHidden())
        w.settings.setValue(KEY, True)
        w.apply_options()
        spin()
        self.assertIs(d.widget(), p.viewer)
        self.assertFalse(d.isHidden())

    def test_a_detached_text_column_stays_detached(self):
        w, p, d = self.opened('gauche')
        w.columns.toggle_floating(d)
        spin()
        self.assertTrue(d.isFloating())
        w.columns.move(w.dock_program, 'droite')
        spin()
        p.place_viewer()
        self.assertTrue(d.isFloating())
        self.assertIs(d.widget(), p.viewer)

    def test_without_parts_the_text_returns_under_them(self):
        w, p, d = self.opened()
        self.choose('iso')
        self.assertIs(p.viewer.parentWidget(), p.vsplit)
        self.assertTrue(d.isHidden())
        self.choose('essai_col')                                            # de retour
        self.assertIs(d.widget(), p.viewer)
        self.assertFalse(d.isHidden())

    def test_option_off_keeps_the_text_under_the_parts(self):
        self.w.settings.setValue(KEY, False)
        w, p, d = self.opened()
        self.assertIs(p.viewer.parentWidget(), p.vsplit)
        self.assertTrue(d.isHidden())

    def test_closing_the_program_window_closes_the_text_column(self):
        w, p, d = self.opened()
        w.dock_program.close()
        spin()
        self.assertTrue(d.isHidden())
        w.show_program(refresh=False)
        spin()
        self.assertFalse(d.isHidden())
        self.assertIs(d.widget(), p.viewer)

    def test_centred_and_back(self):
        w, p, d = self.opened()
        self.assertTrue(w.program_center(True))
        spin()
        self.assertIs(p.viewer.parentWidget(), w.stage.currentWidget())     # le texte au centre
        self.assertTrue(d.isHidden())                                       # sa colonne cachée pendant ce temps
        self.assertFalse(w.dock_program.isHidden())
        self.assertFalse(w.program_center(False))
        spin()
        self.assertIs(d.widget(), p.viewer)                                 # de retour dans sa colonne
        self.assertFalse(d.isHidden())
        self.assertTrue(w.canvas.isVisible())

    def test_an_empty_text_column_never_stays_shown(self):
        w = self.w
        w.show()
        d = w.dock_program_text
        d.setVisible(True)                                                  # une disposition remise, sans parties
        spin()
        self.assertTrue(d.isHidden())
        self.assertIs(self.p.viewer.parentWidget(), self.p.vsplit)

    def test_the_columns_know_it(self):
        from vectordrive.ui import columns
        w, d = self.w, self.w.dock_program_text
        self.assertEqual(d.objectName(), 'programme_texte')
        self.assertEqual(columns.short_title(d), 'Texte')
        self.assertIn('programme_texte', w.columns.placed())                # jamais le groupe d'onglets d'une colonne
        self.assertTrue(w.columns._gated(d))                                # pas montré d'office avec la colonne
        self.assertIn(d, w.columns.fao_docks())                             # rangé par l'onglet CAD


class Parts(Base):

    def test_the_parts_share_the_column_with_a_splitter(self):
        w, p, d = self.opened()
        sp = p.sections_split
        self.assertEqual(sp.count(), 2)
        self.assertIs(p.sections_scroll.widget(), p.sections_box)          # la colonne défile, pas une partie
        frame = p.hosted['essai_params'][0]
        self.assertGreaterEqual(frame.height(), 300)                        # dépliée : toute sa hauteur
        before = sp.sizes()
        sp.setSizes([before[0] + 80, max(1, before[1] - 80)])               # « Scale Y » : à la souris
        spin()
        self.assertNotEqual(sp.sizes(), before)

    def test_a_folded_part_keeps_only_its_header(self):
        w, p, d = self.opened()
        frame, head, widget, _t = p.hosted['essai_ops']
        head.click()
        spin()
        self.assertTrue(widget.isHidden())
        self.assertLessEqual(frame.height(), head.sizeHint().height() + 2)
        head.click()
        spin()
        self.assertGreater(frame.maximumHeight(), 10000)


if __name__ == '__main__':
    unittest.main()
