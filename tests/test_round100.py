"""Round 100 : cœur libre et plugins (chargement, points d'extension,
erreurs sans conséquence), cœur neutre sans plugin."""
import os
import pathlib
import tempfile
import re
import textwrap
import unittest
import zipfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive import plugins

ROOT = pathlib.Path(__file__).resolve().parents[1]

ESSAI = textwrap.dedent('''
    PLUGIN = {'nom': 'Essai', 'version': '0.1', 'api': 1, 'licence': 'MIT'}

    def ecrire(toolpaths, setup, *, title='', machine=None, stem='p', box_mm=None):
        from vectordrive.cam.post import PostResult
        return PostResult(text='ESSAI ' + str(len(toolpaths)), extension='.ess')

    def strategie(doc, setup, op, tool, tp, em, here):
        em.travel(1.0, 2.0)
        em.plunge(-0.1)
        em.feed(3.0, 2.0, -0.1)

    def register(api):
        api.add_shortcut_scheme('essai', 'Jeu essai', [('ID_PALETTE_RECTANGLE', 'R')], default=True)
        api.add_post('essai', 'Post essai', ecrire)
        api.add_strategy('essai', 'Stratégie essai', strategie)
        api.add_cam_preset('essai', 'Bouton essai', 'essai', {'depth': 0.1}, 'fraise')
        api.add_action('essai_action', 'Action essai', lambda win: win.setProperty('essai', 1),
                       tab='FAO', group='Essai')
        api.add_translations('en', {'Action essai': 'Test action'})
        api.add_autotest('essai', lambda: 'ok')
        api.add_about('ligne essai')
        api.set_defaults('cljob', {'tool_number': 7})
        api.add_templates('montage', {'M1': {'postes': ['A', 'B']}})
''')


def app():
    return QApplication.instance() or QApplication([])


class TestLoader(unittest.TestCase):
    def setUp(self):
        plugins.reset()
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)
        self.off = os.environ.pop(plugins.ENV_OFF, None)          # ces essais chargent des plugins

    def tearDown(self):
        plugins.reset()
        self.tmp.cleanup()
        if self.off is not None:
            os.environ[plugins.ENV_OFF] = self.off

    def write(self, name, body):
        d = self.dir / name
        d.mkdir()
        (d / '__init__.py').write_text(body, encoding='utf-8')
        return d

    def test_load_folder_and_extension_points(self):
        self.write('vd_essai_a', ESSAI)
        infos = plugins.load([self.dir], force=True)
        self.assertEqual([(i.name, i.version, i.error) for i in infos], [('Essai', '0.1', '')])
        r = plugins.REGISTRY
        self.assertEqual(r.default_scheme, 'essai')
        from vectordrive.cam import model, post, strategies
        from vectordrive.core import geom
        from vectordrive.core.document import Document, Shape
        self.assertIn('essai', post.posts())
        self.assertEqual(post.run('essai', [], model.CamSetup()).text, 'ESSAI 0')
        self.assertIn('essai', model.op_kinds())
        d = Document()
        d.add(Shape(path=geom.Path([geom.rect(0, 0, 5, 5)])))
        s = model.CamSetup(tools=[model.CamTool()])
        tp = strategies.compute(d, s, model.Operation(kind='essai', tool_id=s.tools[0].id))
        self.assertEqual([round(m.x, 3) for m in tp.moves if m.kind == 'feed'], [3.0])
        self.assertEqual(r.defaults['cljob']['tool_number'], 7)              # réglages repris par le plugin Cielle
        self.assertEqual(r.templates['montage']['M1']['postes'], ['A', 'B'])
        self.assertEqual(r.autotests[0][1](), 'ok')

    def test_window_gets_actions_presets_and_translations(self):
        app()
        self.write('vd_essai_b', ESSAI)
        plugins.load([self.dir], force=True)
        from vectordrive import i18n
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            self.assertIn('essai_action', w.A)
            w.A['essai_action'].trigger()
            self.assertEqual(w.property('essai'), 1)
            tabs = [w.ribbon.tabText(i) for i in range(w.ribbon.count())]
            self.assertEqual(tabs.count('FAO 2D'), 1)                   # onglet existant réutilisé (l'onglet
            self.assertNotIn('FAO', tabs)                                # « FAO » d'avant : FAO 2D)
            self.assertIn('cam_new_essai', w.A)
            self.assertIn('cam_new_essai', w.cam_panel.palette_buttons)
            self.assertEqual(w.A['tool_rect'].shortcuts()[0].toString(), 'R')
            i18n.set_language('en')
            self.assertEqual(i18n.tr('Action essai'), 'Test action')
        finally:
            i18n.set_language('fr')
            w.modified = False
            w.close()

    def test_broken_plugins_never_stop_the_app(self):
        self.write('vd_essai_casse', "PLUGIN = {'nom': 'Cassé'}\ndef register(api):\n    raise RuntimeError('boum')\n")
        self.write('vd_essai_api', "PLUGIN = {'nom': 'Futur', 'api': 99}\ndef register(api):\n    pass\n")
        self.write('vd_essai_vide', "PLUGIN = {'nom': 'Vide'}\n")
        infos = {i.name: i.error for i in plugins.load([self.dir], force=True)}
        self.assertIn('boum', infos['Cassé'])
        self.assertIn('API 99', infos['Futur'])
        self.assertIn('register', infos['Vide'])

    def test_zip_and_switch_off(self):
        z = self.dir / 'paquet.zip'
        with zipfile.ZipFile(z, 'w') as f:
            f.writestr('vd_essai_zip/__init__.py', ESSAI)
        self.assertEqual([i.name for i in plugins.load([self.dir], force=True)], ['Essai'])
        plugins.reset()
        os.environ[plugins.ENV_OFF] = '1'
        try:
            self.assertEqual(plugins.load([self.dir], force=True), [])
        finally:
            del os.environ[plugins.ENV_OFF]

    def test_env_paths(self):
        d = self.write('vd_essai_env', ESSAI)
        os.environ[plugins.ENV_PATHS] = str(d)
        try:
            self.assertIn(d, plugins.search_dirs())
            self.assertEqual([i.name for i in plugins.load(force=True)], ['Essai'])
        finally:
            del os.environ[plugins.ENV_PATHS]


class TestNeutralCore(unittest.TestCase):
    def setUp(self):
        plugins.reset()

    def test_no_workshop_data_in_core(self):
        """Ni chemins, ni données, ni outils d'atelier dans le code du cœur."""
        bad = []
        for f in (ROOT / 'vectordrive').rglob('*.py'):
            t = f.read_text(encoding='utf-8')
            for m in re.finditer(r'[A-Z]:[/\\\\]+Documents', t):        # chemins d'un poste
                bad.append(f'{f.name} : {m.group()}')
        self.assertEqual(bad, [])
        for gone in ('core/quote.py', 'ui/quote_dialog.py', 'cam/post/datron.py',
                     # post-processeurs et fichiers machine : dans le plugin de l'atelier (round 218)
                     'cam/post/gcode.py', 'cam/post/iso.py', 'cam/post/mah.py', 'cam/post/cielle.py',
                     'cam/post/dxfpost.py', 'io/simpl.py', 'io/cljob.py'):
            self.assertFalse((ROOT / 'vectordrive' / gone).exists(), gone)
        tpl = (ROOT / 'vectordrive' / 'ressources' / 'vnd_modele.vnd').read_bytes()
        self.assertNotIn(b'Datron', tpl)

    def test_without_plugin(self):
        app()
        from vectordrive.cam import post
        from vectordrive.io import registry
        from vectordrive.ui.main_window import MainWindow
        self.assertEqual(post.posts(), {})                                 # aucun post-processeur sans plugin
        with self.assertRaises(post.PostError):
            post.run('datron', [], None)
        self.assertIsNone(registry.by_extension('a.simpl'))               # ni programme machine
        self.assertNotIn('cljob', plugins.REGISTRY.defaults)
        w = MainWindow()
        try:
            self.assertNotIn('quote', w.A)
        finally:
            w.modified = False
            w.close()

    def test_licence_files(self):
        self.assertIn('MIT OR Apache-2.0', (ROOT / 'LICENSE').read_text(encoding='utf-8'))
        self.assertIn('Permission is hereby granted', (ROOT / 'LICENSE-MIT').read_text(encoding='utf-8'))
        self.assertIn('Version 2.0, January 2004', (ROOT / 'LICENSE-APACHE').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
