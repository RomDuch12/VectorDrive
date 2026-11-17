"""Round 1067 : atelier SimPL, phase 2 — une partie de l'onglet Programme ouverte à la demande d'un plugin (le bouton
« Opérations NeoDrive » du ruban FAO ouvre l'onglet Programme sur ses opérations)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1067.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from vectordrive import plugins  # noqa: E402
from vectordrive.cam import post  # noqa: E402

app = QApplication.instance() or QApplication([])

BEFORE = 'avant : un plugin ne peut pas ouvrir une partie de l’onglet Programme'


def ops(win):
    return QLabel('opérations de la machine')


def writer(toolpaths, setup, *, title='', machine=None, stem='p', box_mm=None, machine_dir=''):
    return post.PostResult('', [], '.txt')


def spin(n=3):
    for _ in range(n):
        app.processEvents()


class Opened(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.assertTrue(hasattr(MainWindow, 'show_program_part'), BEFORE)
        r = plugins.REGISTRY
        self.saved = (dict(r.posts), list(r.post_providers), list(r.actions), list(r.panels), list(r.post_hooks),
                      dict(r.post_exports))
        self.addCleanup(self.restore)
        api = plugins.Api(r, plugins.PluginInfo('essai', 'essai'))
        api.add_post('essai_ops', 'Machine d’essai', writer)
        api.add_panel('essai_ops', 'ESSAI — Opérations', ops, posts=('essai_ops',), host='programme')
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

    def test_the_part_is_shown_unfolded_in_the_program_window(self):
        w, p = self.w, self.p
        w.show()
        p.fold_section('essai_ops', True)
        self.assertEqual(p.sections_shown(), [])                            # sa machine n'est pas choisie
        self.assertTrue(w.show_program_part('essai_ops'))
        spin()
        self.assertEqual(p.sections_shown(), ['essai_ops'])                 # demandée : montrée…
        self.assertFalse(p.hosted['essai_ops'][2].isHidden())               # … dépliée
        self.assertFalse(w.dock_program.isHidden())                         # la fenêtre Programme ouverte
        self.assertFalse(w.show_program_part('inconnue'))
        w.cam_panel.set_post('iso')                                          # une autre machine : recachée
        spin()
        self.assertEqual(p.sections_shown(), [])

    def test_in_the_centre_the_text_alone_once_the_part_is_opened(self):
        w, p = self.w, self.p
        w.show()
        w.program_center(True)                                               # tout le panneau au centre
        spin()
        self.assertIs(w._program_part, p)
        w.show_program_part('essai_ops')
        spin()
        self.assertTrue(w.program_centered())
        self.assertIs(p.viewer.parentWidget(), w.stage.currentWidget())     # le texte seul au centre
        self.assertIs(w.dock_program.widget(), p)                           # la partie dans la fenêtre, ouverte
        self.assertFalse(w.dock_program.isHidden())

    def test_opening_the_part_does_not_rewrite_the_whole_program(self):
        calls = []
        self.p.refresh = lambda *a, **k: calls.append(1) or ''
        self.w.show_program_part('essai_ops')
        self.assertEqual(calls, [])                 # pas réécrit d'office : la fenêtre montrée suit « en direct »,
        #                                             avec ses garde-fous (`_live_refresh`, après l'affichage)


if __name__ == '__main__':
    unittest.main()
