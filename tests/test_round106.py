"""Round 106 : 30 thèmes (5 clairs, 25 sombres) dont TypeEdit (couleurs lues
dans son script de ruban), thèmes de l'utilisateur et des plugins, éditeur,
réglages d'apparence (accent, plan de travail, police, densité, ruban),
miroirs M / Maj+M comme TypeEdit."""
import json
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ['VECTORDRIVE_THEMES'] = os.path.join(tempfile.mkdtemp(), 'themes')

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from vectordrive.ui import theme as TH
from vectordrive.ui import themes as T

SCRIPT = """' Customization of the colors
set visualManager = configProduct.GetVisualManager
visualManager.SetColorRibbonPanelCaptionTopHighlightFromRGB 51,86,114
visualManager.SetColorRibbonPanelCaptionTopNoHighlightFromRGB 126,136,145
visualManager.SetColorRibbonPanelCaptionTextFromRGB 255,255,255
visualManager.SetColorRibbonButtonText(5066061)
visualManager.SetColorRibbonBarBackgroundFromRGB 156,164,167
' visualManager.SetColorRibbonBarBackgroundFromRGB 1,2,3
visualManager.SetColorRibbonCategoryTabTopHighlightFromRGB 51,86,114
visualManager.ModifyType3BrushFromRGB "COLOR_GRID_SELECTION_BG",102,151,49
visualManager.SetFontName "Segoe UI"
"""


def app():
    return QApplication.instance() or QApplication([])


def settings(**kw):
    s = QSettings(os.path.join(tempfile.mkdtemp(), 's.ini'), QSettings.Format.IniFormat)
    for k, v in kw.items():
        s.setValue(k.replace('__', '/'), v)
    return s


class TestColors(unittest.TestCase):
    def test_helpers(self):
        self.assertEqual(T.rgb('#0a0B0c'), (10, 11, 12))
        self.assertEqual(T.rgb('#fff'), (255, 255, 255))
        self.assertEqual(T.mix('#000000', '#ffffff', 0.5), '#808080')
        self.assertAlmostEqual(T.contrast('#000000', '#ffffff'), 21, places=1)
        self.assertEqual(T.readable('#ffff00'), '#000000')
        self.assertEqual(T.colorref(5066061), '#4d4d4d')
        self.assertTrue(T.is_fill('#111111;#222222'))
        self.assertFalse(T.is_color('rouge'))


class TestBuiltin(unittest.TestCase):
    def test_thirty_themes(self):
        self.assertEqual(len(T.BUILTIN), 30)
        self.assertEqual(len(T.LIGHT_KEYS), 5)
        self.assertEqual(len(T.DARK_KEYS), 25)
        self.assertEqual(len({t.name for t in T.BUILTIN.values()}), 30)
        for k in ('clair', 'sombre', 'typeedit', 'typeedit13', 'typeedit_sombre'):
            self.assertIn(k, T.BUILTIN)

    def test_every_theme_is_complete_and_readable(self):
        for k, t in T.BUILTIN.items():
            for role in T.COLOR_ROLES:
                v = t.colors.get(role, '')
                self.assertTrue(v == '' and role in T.OPTIONAL or T.is_fill(v), (k, role, v))
            for role in T.CANVAS_ROLES:
                v = t.canvas.get(role, '')
                self.assertTrue(role == 'grid' or v == '' and role in T.OPTIONAL or T.is_color(v), (k, role, v))
            c = t.colors
            for a, b, lim in (('window_text', 'window', 4.5), ('text', 'base', 4.5), ('button_text', 'button', 4.5),
                              ('highlighted_text', 'highlight', 3), ('tab_selected_text', 'tab_selected', 3)):
                self.assertGreaterEqual(T.contrast(c[a], c[b]), lim, (k, a, b))
            self.assertEqual(t.dark, T.luminance(c['window']) < 0.2, k)

    def test_clair_and_sombre_keep_their_look(self):
        self.assertEqual(T.BUILTIN['clair'].colors['window'], '#eef1f5')
        self.assertEqual(T.BUILTIN['clair'].canvas['bg'], '#5a6270')
        self.assertEqual(T.BUILTIN['sombre'].colors['base'], '#1d1f22')
        self.assertEqual(T.BUILTIN['sombre'].canvas['page'], '#2a2d33')
        self.assertIs(TH.CANVAS_DARK, T.BUILTIN['sombre'].canvas)


class TestTypeEdit(unittest.TestCase):
    def test_parse_script(self):
        v = T.parse_ribbon_script(SCRIPT)
        self.assertEqual(v['RibbonBarBackground'], '#9ca4a7')            # la ligne en commentaire est ignorée
        self.assertEqual(v['RibbonButtonText'], '#4d4d4d')                # COLORREF
        self.assertEqual(v['COLOR_GRID_SELECTION_BG'], '#669731')
        self.assertEqual(v['font'], 'Segoe UI')

    def test_read_utf16_and_theme(self):
        f = pathlib.Path(tempfile.mkdtemp()) / 'ScriptRibbonUI_TE.txt'
        f.write_bytes(SCRIPT.replace('156,164,167', '150,160,170').encode('utf-16'))
        v = T.read_ribbon_script(f)
        t = T.typeedit_theme(v)
        self.assertEqual(t.colors['ribbon'], '#96a0aa')
        self.assertEqual(t.captions, 'bandeau')
        self.assertEqual(t.colors['caption'], '#7e8891')
        self.assertEqual(t.colors['highlight'], '#669731')
        self.assertEqual(t.canvas['page'], '#ffffff')
        self.assertEqual(t.font, 'Segoe UI')
        self.assertEqual(t.source, 'TypeEdit')

    def test_classic_caption_gradient_and_readable_text(self):
        # round 125 : « TypeEdit classique » remplacé par « TypeEdit 13 », bandeaux bleus unis
        t = T.BUILTIN['typeedit13']
        self.assertEqual(t.colors['caption'], '#5a83b7')
        self.assertGreaterEqual(T.contrast(t.colors['caption_text'], t.colors['caption'].split(';')[0]), 2.5)
        cap = T.typeedit_theme(dict(T.TE_V13, RibbonPanelCaptionBottomNoHighlight='#f6e5bd'))
        self.assertIn(';', cap.colors['caption'])                     # un bandeau en dégradé reste possible
        self.assertIn('qlineargradient', T.stylesheet(cap))


class TestResolveAndFiles(unittest.TestCase):
    def setUp(self):
        for f in pathlib.Path(os.environ['VECTORDRIVE_THEMES']).glob('*.json'):
            f.unlink()

    def test_resolve_overrides(self):
        s = settings(vue__theme='foret', vue__accent='#ff0000', vue__c_fond='#123456', vue__c_grille='#00ff00')
        t = T.resolve(s)
        self.assertEqual(t.key, 'foret')
        self.assertEqual(t.colors['highlight'], '#ff0000')
        self.assertEqual(t.colors['checked_border'], '#ff0000')
        self.assertEqual(t.canvas['bg'], '#123456')
        self.assertEqual(t.canvas['grid'][:3], (0, 255, 0))
        self.assertEqual(T.BUILTIN['foret'].canvas['bg'], '#111a14')        # l'original n'est pas touché

    def test_system_mode_and_legacy(self):
        s = settings(vue__theme='systeme', vue__theme_clair='sable', vue__theme_sombre='ocean')
        self.assertEqual(T.chosen_key(s, False), 'sable')
        self.assertEqual(T.chosen_key(s, True), 'ocean')
        self.assertEqual(T.get('dark').key, 'sombre')
        self.assertEqual(T.get('inconnu').key, 'clair')

    def test_user_theme_roundtrip(self):
        t = T.BUILTIN['ambre'].copy(key=T.new_key('Mon ambre'), name='Mon ambre', source='utilisateur')
        t.colors['accent'] = '#00aa00'
        f = T.save_user(t)
        back = T.all_themes()[t.key]
        self.assertEqual(back.source, 'utilisateur')
        self.assertEqual(back.colors['accent'], '#00aa00')
        self.assertEqual(back.canvas['grid'], T.BUILTIN['ambre'].canvas['grid'])
        self.assertTrue(f.is_file())
        self.assertNotEqual(T.new_key('Mon ambre'), t.key)
        self.assertTrue(T.delete_user(t.key))
        self.assertNotIn(t.key, T.all_themes())

    def test_partial_file_is_completed(self):
        t = T.from_json({'key': 'x y', 'name': 'Partiel', 'dark': True,
                         'colors': {'window': '#202020', 'accent': '#ff8800', 'text': 'pas une couleur'}})
        self.assertEqual(t.key, 'x_y')
        self.assertEqual(t.colors['window'], '#202020')
        self.assertTrue(T.is_color(t.colors['text']))
        self.assertTrue(T.is_color(t.canvas['selection']))

    def test_plugin_theme(self):
        from vectordrive import plugins
        plugins.REGISTRY.themes.append({'key': 'atelier_test', 'name': 'Atelier', 'dark': False,
                                        'colors': {'window': '#dddddd', 'accent': '#aa0000'}})
        try:
            t = T.all_themes()['atelier_test']
            self.assertEqual(t.source, 'plugin')
            self.assertEqual(t.colors['highlight'], '#aa0000')
        finally:
            plugins.REGISTRY.themes.clear()

    def test_stylesheet_density_and_captions(self):
        t = T.BUILTIN['clair']
        compact = T.stylesheet(t, density='compacte')
        self.assertIn('padding: 1px', compact)
        self.assertIn('ribbonGroupTitle', T.stylesheet(t, captions='bandeau'))
        self.assertIn('background:', T.stylesheet(t, captions='bandeau').split('ribbonGroupTitle')[1])
        self.assertIn('QDockWidget::title', T.stylesheet(T.BUILTIN['typeedit']))


class TestApply(unittest.TestCase):
    def setUp(self):
        self.app = app()

    def tearDown(self):
        TH.apply_light(self.app)

    def test_palette_font_and_canvas(self):
        self.assertTrue(TH.apply_theme(self.app, 'minuit'))
        self.assertEqual(self.app.palette().window().color().name(), '#141b2d')
        self.assertIs(TH.canvas_colors(), T.BUILTIN['minuit'].canvas)
        self.assertFalse(TH.apply_theme(self.app, 'typeedit13'))
        self.assertEqual(self.app.font().family(), 'Segoe UI')
        TH.apply_theme(self.app, 'clair')
        self.assertNotEqual(TH.current().font, 'Segoe UI')

    def test_icons_follow_theme_ink(self):
        from vectordrive.ui import icons
        TH.apply_theme(self.app, 'clair')
        a = icons.icon('new').pixmap(32, 32).toImage()
        TH.apply_theme(self.app, 'contraste_sombre')
        b = icons.icon('new').pixmap(32, 32).toImage()
        self.assertNotEqual(a, b)


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app()
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        for k in ('vue/accent', 'vue/theme_clair', 'vue/theme_sombre', 'vue/ruban_reduit'):
            cls.w.settings.remove(k)
        cls.w.set_theme('clair')
        cls.w.modified = False
        cls.w.close()

    def test_set_theme_and_dark_toggle(self):
        w = self.w
        w.settings.remove('vue/theme_sombre')
        w.settings.remove('vue/theme_clair')
        w.set_theme('typeedit')
        self.assertEqual(w.settings.value('vue/theme'), 'typeedit')
        self.assertIn('ribbonGroupTitle', w.styleSheet())
        self.assertFalse(w.A['theme_dark'].isChecked())
        w.settings.setValue('vue/theme_sombre', 'lagon')
        try:
            w.A['theme_dark'].setChecked(True)
            self.assertEqual(w.settings.value('vue/theme'), 'lagon')
            self.assertTrue(TH.current().dark)
            w.A['theme_dark'].setChecked(False)
            self.assertEqual(w.settings.value('vue/theme'), 'clair')
        finally:
            w.settings.remove('vue/theme_sombre')

    def test_theme_menu(self):
        w = self.w
        w._fill_theme_menu(w.theme_menu)
        keys = [a.data() for a in w.theme_menu.actions() if a.data()]
        self.assertGreaterEqual(len(keys), 31)
        self.assertIn('systeme', keys)
        act = next(a for a in w.theme_menu.actions() if a.data() == 'polaire')
        act.trigger()
        self.assertEqual(TH.current().key, 'polaire')

    def test_ribbon_options(self):
        w = self.w
        from PySide6.QtWidgets import QToolButton
        w.settings.setValue('vue/ruban_icones', 'grandes')
        w.settings.setValue('vue/ruban_libelles', False)
        w._apply_ribbon_options()
        big = [b for b in w.ribbon.findChildren(QToolButton) if b.property('ribbon_big') is True]
        self.assertTrue(big)
        self.assertEqual(big[0].iconSize().width(), 36)
        self.assertEqual(big[0].toolButtonStyle().name, 'ToolButtonIconOnly')
        full = w.ribbon.height()
        w.A['ribbon_collapse'].setChecked(True)
        self.assertLess(w.ribbon.height(), full / 2)
        self.assertEqual(w.settings.value('vue/ruban_reduit') in (True, 'true'), True)
        w.ribbon._tab_clicked(w.ribbon.currentIndex())                  # un clic déplie le temps d'une commande
        self.assertEqual(w.ribbon.height(), full)
        w.ribbon._command_done()
        self.assertLess(w.ribbon.height(), full / 2)
        w.A['ribbon_collapse'].setChecked(False)
        for k in ('vue/ruban_icones', 'vue/ruban_libelles'):
            w.settings.remove(k)
        w._apply_ribbon_options()
        self.assertEqual(big[0].iconSize().width(), 28)

    def test_options_appearance_tab(self):
        w = self.w
        dlg = w.options_dialog(exec_dialog=False)
        titles = [dlg.tabs.tabText(i) for i in range(dlg.tabs.count())]
        self.assertIn('Apparence', titles)
        combo = dlg.widgets['vue/theme']
        self.assertGreaterEqual(combo.count(), 31)
        self.assertEqual(dlg.widgets['vue/theme_sombre'].count(), 25)
        dlg.widgets['vue/accent'].setValue('#336699')
        combo.setCurrentIndex(combo.findData('cafe'))
        dlg.accept()
        self.assertEqual(w.settings.value('vue/accent'), '#336699')
        w.set_theme(w.settings.value('vue/theme'))
        self.assertEqual(TH.current().key, 'cafe')
        self.assertEqual(TH.current().colors['accent'], '#336699')
        w.settings.setValue('vue/accent', '')

    def test_editor_duplicate_edit_export_import(self):
        w = self.w
        ed = w.theme_editor(exec_dialog=False)
        i = next(i for i in range(ed.list.count()) if ed.list.item(i).data(0x0100) == 'ardoise')
        ed.list.setCurrentRow(i)
        self.assertFalse(ed.b_save.isEnabled())                          # intégré : à dupliquer
        t = ed._duplicate('Ardoise atelier')
        self.assertEqual(ed.current_key(), t.key)
        self.assertTrue(ed.b_save.isEnabled())
        ed.color_edits[('canvas', 'bg')].setValue('#101010', emit=True)
        ed.save()
        self.assertEqual(T.all_themes()[t.key].canvas['bg'], '#101010')
        out = os.path.join(tempfile.mkdtemp(), 'x.json')
        ed.export_file(out)
        self.assertEqual(json.loads(pathlib.Path(out).read_text(encoding='utf-8'))['format'], 'vectordrive-theme')
        imp = ed.import_file(out)
        self.assertNotEqual(imp.key, t.key)                              # homonyme : nouvelle clé
        ed._delete(t.key)
        ed._delete(imp.key)
        self.assertNotIn(t.key, T.all_themes())


class TestMirrorKeys(unittest.TestCase):
    def test_m_is_left_right_like_typeedit(self):
        from vectordrive.ui import shortcuts as S
        self.assertEqual(S.TE_ACTIONS['ID_COMPO_MIROIRVERT'], 'mirror_h')
        self.assertEqual(S.TE_ACTIONS['ID_COMPO_MIROIRHORZ'], 'mirror_v')


if __name__ == '__main__':
    unittest.main()
