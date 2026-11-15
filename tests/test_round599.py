"""Round 599 : la machine choisie fait apparaître ses fonctions — API des plugins : actions et panneaux
montrés pour certaines machines, plugins prévenus quand la machine change, export propre à une machine ;
le post-processeur reçoit le dossier d'écriture tel que la machine le voit."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication, QLabel

from vectordrive import plugins
from vectordrive.cam import model, post
from vectordrive.cam.model import Move, Toolpath

app = QApplication.instance() or QApplication([])


def writer(toolpaths, setup, *, title='', machine=None, stem='p', box_mm=None, machine_dir=''):
    return post.PostResult(f'DIR={machine_dir}', [], '.txt')


class Provider:
    def posts(self, d):
        return {}

    def resolve(self, key):
        return ('essai_laser', {'fiche': key}) if key.startswith('fiche:') else None


class Fixture(unittest.TestCase):
    def setUp(self):
        r = plugins.REGISTRY
        self.saved = (dict(r.posts), list(r.post_providers), list(r.actions), list(r.panels), list(r.post_hooks),
                      dict(r.post_exports))
        self.api = plugins.Api(r, plugins.PluginInfo('essai', 'essai'))
        self.api.add_post('essai_laser', 'Laser d\'essai', writer)
        self.api.add_post_provider(Provider())

    def tearDown(self):
        r = plugins.REGISTRY
        r.posts, r.post_providers, r.actions, r.panels, r.post_hooks, r.post_exports = self.saved


class TestFamily(Fixture):
    def test_family(self):
        self.assertEqual(post.family('essai_laser'), 'essai_laser')
        self.assertEqual(post.family('fiche:Tau.MAH'), 'essai_laser')     # une fiche : la machine qu'elle désigne
        self.assertEqual(post.family('inconnu'), 'inconnu')
        self.assertEqual(post.family(''), '')

    def test_machine_dir(self):
        s = model.CamSetup()
        tp = Toolpath(op_id='', tool_id='', name='x')
        tp.moves = [Move('feed', 0, 0, 0)]
        with mock.patch('vectordrive.cam.ncpaths.mappings', lambda text=None: [('Z:', 'C:\\Travaux')]):
            r = post.run('essai_laser', [tp], s, out_dir='C:\\Travaux\\Lot 12')
            self.assertEqual(r.text, 'DIR=Z:\\Lot 12')                    # vu par la machine
            r = post.run('essai_laser', [tp], s, out_dir='D:\\Ailleurs')
            self.assertEqual(r.text, 'DIR=')                              # même chemin : noms seuls
        self.assertEqual(post.run('essai_laser', [tp], s).text, 'DIR=')


class TestWindow(Fixture):
    def test_actions_panels_hooks(self):
        seen = []
        self.api.add_action('essai_tau', 'Fonction laser', lambda win: None, tab='FAO', group='Essai',
                            posts=('essai_laser',))
        self.api.add_panel('essai_panneau', 'Panneau laser', lambda win: QLabel('laser'), posts=('essai_laser',))
        self.api.add_panel('essai_toujours', 'Toujours', lambda win: QLabel('x'))
        self.api.on_post_changed(lambda win, key: seen.append(key))
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            dock = w.plugin_docks['essai_panneau']
            self.assertFalse(dock.isVisibleTo(w))
            self.assertFalse(w.A['essai_tau'].isVisible())
            self.assertTrue(w.plugin_docks['essai_toujours'].isVisibleTo(w))
            w.cam_panel.set_post('essai_laser')
            self.assertTrue(dock.isVisibleTo(w))
            self.assertTrue(w.A['essai_tau'].isVisible())
            self.assertEqual(seen[-1], 'essai_laser')
            n = len(seen)
            w.cam_panel.refresh()
            self.assertEqual(len(seen), n)                                 # même machine : pas de nouvel appel
            w.cam_panel.set_post('fiche:Tau.MAH')
            self.assertTrue(dock.isVisibleTo(w))                          # même machine par sa fiche
            w.cam_panel.set_post('gcode')
            self.assertFalse(dock.isVisibleTo(w))
            self.assertEqual(seen[-1], 'gcode')
        finally:
            w.modified = False
            w.close()

    def test_post_export_replaces_dialog(self):
        done = []
        self.api.add_post_export('essai_laser', lambda cp, tps, s: done.append(len(tps)) or True)
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            cp = w.cam_panel
            cp.set_post('essai_laser')
            tp = Toolpath(op_id='', tool_id='', name='x')
            tp.moves = [Move('feed', 0, 0, 0), Move('feed', 1, 0, 0)]
            with mock.patch.object(cp, 'checked_paths', lambda: [tp]), \
                    mock.patch.object(cp, 'refresh_dates', lambda: 0), \
                    mock.patch.object(cp, 'preflight', lambda *a, **k: True), \
                    mock.patch('PySide6.QtWidgets.QFileDialog.getSaveFileName',
                               side_effect=AssertionError('pas de boîte ordinaire')):
                cp.post_process()
            self.assertEqual(done, [1])
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
