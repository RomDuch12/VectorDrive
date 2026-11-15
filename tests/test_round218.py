"""Round 218 : le cœur ne contient plus aucun post-processeur ni fichier
machine — ils viennent des plugins (`add_post`, `add_post_provider`,
`add_format`) ; sans eux, le panneau FAO le dit."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive import plugins

app = QApplication.instance() or QApplication([])


class FakeMachine(dict):
    """Fiche machine d'essai (un plugin lit les vraies)."""


class Provider:
    def posts(self, folder):
        return {f'fiche:{folder}/a': 'Fiche A'}

    def resolve(self, key):
        if not key.startswith('fiche:'):
            return None
        from tests._posts import write
        return write, FakeMachine(Mset40='1' if key.endswith('rot') else '0')


class TestCore(unittest.TestCase):
    def setUp(self):
        self._saved = plugins.REGISTRY
        plugins.REGISTRY = plugins.Registry()
        import vectordrive.cam.post as P
        self.P = P

    def tearDown(self):
        plugins.REGISTRY = self._saved

    def api(self):
        return plugins.Api(plugins.REGISTRY, plugins.PluginInfo('essai', 'Essai'))

    def test_nothing_without_plugins(self):
        P = self.P
        self.assertEqual(P.BUILTIN, {})
        self.assertEqual(P.posts('C:/machines'), {})
        self.assertFalse(P.has_machine_files())
        with self.assertRaises(P.PostError):
            P.run('gcode', [], None)
        from vectordrive.io import registry
        self.assertIsNone(registry.by_extension('x.simpl'))
        for gone in ('gcode', 'iso', 'mah', 'cielle', 'dxfpost'):
            with self.assertRaises(ImportError):
                __import__(f'vectordrive.cam.post.{gone}')

    def test_provider(self):
        from vectordrive.cam import model, strategies as S
        from vectordrive.core import geom
        from vectordrive.core.document import Document, Shape
        P = self.P
        self.api().add_post_provider(Provider())
        self.assertTrue(P.has_machine_files())
        self.assertEqual(P.posts('D:/m'), {'fiche:D:/m/a': 'Fiche A'})
        d = Document()
        d.add(Shape(path=geom.Path([geom.rect(0, 0, 10, 5)]), tool=0))
        s = model.CamSetup(tools=[model.CamTool(name='F1', diameter=1)])
        op = model.Operation(kind='gravure', tool_id=s.tools[0].id, wrap='cylindre_y', wrap_radius=20)
        s.operations = [op]
        tps = S.compute_all(d, s)
        res = P.run('fiche:D:/m/a', tps, s, stem='p')                # 3 axes : écrit
        self.assertTrue(res.files and 'M30' in res.text)
        refused = P.run('fiche:D:/m/rot', tps, s, stem='p')           # axe rotatif + parcours enroulé : refusé
        self.assertEqual(refused.files, [])
        self.assertTrue(refused.warnings[0].startswith('export refusé'))

    def test_format(self):
        from vectordrive.io import registry
        got = []
        self.api().add_format('essai', 'Programme d\'essai', ('ess',), read=None,
                              write=lambda doc, path: got.append(('write', path)),
                              export=lambda win, path: got.append(('export', path)), machine=True)
        f = registry.by_extension('C:/a.ESS')
        self.assertEqual((f.key, f.machine), ('essai', True))
        self.assertIn('*.ess', registry.filter_string(write=True))
        self.assertNotIn('*.ess', registry.filter_string(write=False))     # pas de lecture
        from vectordrive.core.document import Document
        registry.save_document(Document(), 'C:/b.ess')
        self.assertEqual(got, [('write', 'C:/b.ess')])


class TestWindow(unittest.TestCase):
    def test_panel_without_posts_and_plugin_export(self):
        saved = plugins.REGISTRY
        plugins.REGISTRY = plugins.Registry()
        try:
            from vectordrive.ui.main_window import MainWindow
            w = MainWindow()
            p = w.cam_panel
            self.assertEqual((p.post.count(), p.post.itemData(0)), (1, ''))   # « aucun : un plugin en apporte »
            self.assertFalse(p.machines_btn.isVisibleTo(p))
            from vectordrive.core import geom
            from vectordrive.core.document import Shape
            sh = Shape(path=geom.Path([geom.rect(0, 0, 10, 5)]), tool=0)
            w.canvas.doc.add(sh)
            w.canvas.select([sh])
            p.new_operation('trace', exec_dialog=False)
            with mock.patch('vectordrive.ui.cam_panel.QMessageBox.information') as info:
                p.post_process()
            self.assertIn('Aucun post-processeur', info.call_args[0][2])
            seen = []
            plugins.Api(plugins.REGISTRY, plugins.PluginInfo('essai', 'Essai')).add_format(
                'essai', 'Essai', ('.ess',), write=lambda d, f: None,
                export=lambda win, path: seen.append((win, path)), machine=True)
            out = os.path.join(tempfile.mkdtemp(), 'x.ess')
            with mock.patch('vectordrive.ui.main_window.QFileDialog.getSaveFileName', return_value=(out, '')), \
                    mock.patch.object(w, '_confirm_machine_export', return_value=True) as conf:
                w.export_whole_dialog()                 # export de tout, par l'extension (round 232 : Maj+E = fenetre)
            self.assertEqual(seen, [(w, out)])                                 # fenêtre de réglages du plugin
            conf.assert_called_once()                                          # programme machine : dessin vérifié
            w.close()
        finally:
            plugins.REGISTRY = saved


if __name__ == '__main__':
    unittest.main()
