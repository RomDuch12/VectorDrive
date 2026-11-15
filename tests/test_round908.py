"""Round 908 : préréglages de texte et mise en forme complète des polices, comme TypeEdit 13. L'onglet Mise en forme a
l'inclinaison, l'espacement des lettres, l'italique, le souligné, les petites majuscules, les lettres, et un groupe
Préréglages (liste, Enregistrer…, gestionnaire). Un préréglage choisi va aux textes sélectionnés et aux nouveaux
textes ; sans texte sélectionné, les champs règlent les nouveaux textes. Le gestionnaire crée, modifie champ par champ,
renomme, duplique, supprime, importe et exporte. Disposition TypeEdit 13 : l'onglet Mise en forme des boutons Texte et
Texte vertical a les mêmes champs."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r908.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from vectordrive.core.document import Text  # noqa: E402
from vectordrive.ui import typeedit_layout as TL  # noqa: E402

KEYS = ('texte/styles', 'texte/format', 'texte/preset', 'texte/style_courant')

SCRIPT = """' onglet Texte et onglet Rapido de TypeEdit 13 (script synthétique, même syntaxe)
set categoryCAD = configProduct.AddCategoryFromID(307)
set panelMode = categoryCAD.AddPanelFromID(506)
cmd = "ID_OPEN_PAL_TEXT"
set buttonText = panelMode.AddButton(cmd,true,false)
buttonText.SetContextID(idContextText)
set categoryText = configProduct.AddContextCategoryFromID(330,-1,idContextText)
set panelText = categoryText.AddPanelFromID(330)
cmd = "ID_COMPO_TEXTLIBRE"
set buttonFree = panelText.AddButton(cmd,true,false)
buttonFree.SetContextID(idContextRapido)
set categoryRapido = configProduct.AddContextCategoryFromID(331,-1,idContextRapido)
set panelBackR = categoryRapido.AddPanelFromID(599)
cmd = "ID_BACKTO"
set buttonBackR = panelBackR.AddButton(cmd,true,false)
buttonBackR.SetTypeExitContextCategory(true)
set panelRapido = categoryRapido.AddPanelFromID(331)
cmd = "ID_RAPIDO_CHAR_PBMAJ_DLL"
panelRapido.AddButton cmd,true,false
"""
STRINGS = {307: 'TypeEdit', 330: 'Texte', 331: 'Rapido', 506: 'Mode', 599: 'Retour'}


class Base(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.new_document()
        for k in KEYS:
            self.w.settings.remove(k)

    def tearDown(self):
        for k in KEYS:
            self.w.settings.remove(k)
        self.w.modified = False
        self.w.close()

    def put(self, text='Abc', size=5.0, font='Arial'):
        from vectordrive.core import text as TX
        t = Text(text=text, font=font, size=size)
        t.outline = TX.outline_for(t)
        self.w.canvas.doc.layers[0].items.append(t)
        return t

    def select(self, items):
        self.w.canvas.select(items)
        self.w._on_selection()


class Module(unittest.TestCase):

    def test_fields_of_a_format(self):
        from vectordrive.ui import text_presets as TP
        fmt = {'attrs': {'font': 'Arial', 'size': 5.0, 'width_ratio': 1.0, 'spacing': 0.0, 'line_spacing': 1.2,
                         'align': 'left'}, 'extra': {}}
        f = TP.with_value(TP.with_value(fmt, 'width', 80), 'italic', 15)
        self.assertAlmostEqual(f['attrs']['width_ratio'], 0.8)
        self.assertEqual(f['extra']['italic'], 15.0)
        self.assertEqual(fmt['extra'], {})                                    # une copie
        self.assertNotIn('italic', TP.with_value(f, 'italic', 0)['extra'])
        self.assertNotIn('spacing_mode', TP.with_value(TP.with_value(f, 'spacing_mode', 'fixed'), 'spacing_mode',
                                                       'typo')['extra'])
        v = TP.values(TP.with_value(f, 'underline', True))
        self.assertEqual((v['width'], v['italic'], v['underline'], v['small_caps']), (80.0, 15.0, True, False))
        self.assertTrue(TP.same(f, TP.norm(f)))
        self.assertFalse(TP.same(f, fmt))
        self.assertIn('Arial', TP.describe(f))


class Ribbon(Base):

    def test_full_format_in_the_tab(self):
        from vectordrive.ui.ribbon import RibbonGroup
        t = self.put()
        self.select([t])
        bar = self.w.textbar
        bar.italic.setValue(15)
        self.assertEqual(t.extra['italic'], 15.0)
        bar.spacing_mode.setCurrentIndex(bar.spacing_mode.findData('fixed'))
        self.assertEqual(bar.apply('spacing_mode'), 1)
        self.assertEqual(t.extra['spacing_mode'], 'fixed')
        r = self.w.ribbon
        page = r.widget(next(i for i in range(r.count()) if r.tabText(i) == self.w.text_tab_title))
        groups = {g.title.text(): g for g in page.findChildren(RibbonGroup)}
        self.assertIn('Préréglages', groups)
        from PySide6.QtWidgets import QToolButton
        acts = {b.defaultAction() for b in page.findChildren(QToolButton)}
        for k in ('text_preset_save', 'text_styles'):
            self.assertIn(self.w.A[k], acts, k)
        for k in ('text_italic', 'text_letters', 'text_style_options'):                # dans CAD › Texte, une fois
            self.assertNotIn(self.w.A[k], acts, k)

    def test_save_and_choose_a_preset(self):
        from vectordrive.ui import text_presets as TP
        big = self.put(size=7.0)
        self.select([big])
        self.assertEqual(self.w.save_text_preset('Gros 908'), 'Gros 908')
        self.assertEqual(TP.load(self.w.settings)['Gros 908']['attrs']['size'], 7.0)
        bar = self.w.textbar
        self.assertEqual(bar.presets.currentData(), 'Gros 908')                # le texte a ce préréglage
        small = self.put(size=3.0)
        self.select([small])
        self.assertEqual(bar.presets.currentData(), '')
        self.assertEqual(bar._preset_chosen(bar.presets.findData('Gros 908')), 1)
        self.assertEqual(small.size, 7.0)
        self.assertEqual(TP.new_text_format(self.w.settings)['attrs']['size'], 7.0)   # et les nouveaux textes
        self.assertEqual(self.w.settings.value(TP.CURRENT), 'Gros 908')

    def test_without_selection_the_fields_set_new_texts(self):
        from vectordrive.ui import text_presets as TP
        self.select([])
        bar = self.w.textbar
        self.assertEqual(bar.apply('size', 12.5), 0)
        bar.italic.setValue(10)
        fmt = TP.new_text_format(self.w.settings)
        self.assertEqual((fmt['attrs']['size'], fmt['extra']['italic']), (12.5, 10.0))
        self.w.new_text(10.0, 10.0)                      # round 922 : le texte s'écrit dans le dessin
        self.w.canvas.tool_obj.insert('Abc')
        self.w.canvas.tool_obj.finish()
        t = next(it for it in self.w.canvas.doc.layers[0].items if isinstance(it, Text))
        self.assertEqual((t.size, t.extra.get('italic')), (12.5, 10.0))

    def test_no_selection_shows_the_new_text_values(self):
        from vectordrive.ui import text_presets as TP
        TP.set_new_text_format(self.w.settings, TP.with_value(TP.new_text_format(self.w.settings), 'size', 9.0))
        self.select([])
        self.assertEqual(self.w.textbar.size.value(), 9.0)


class Manager(Base):

    def test_commands(self):
        from vectordrive.ui import text_presets as TP
        dlg = self.w.text_presets_dialog(exec_dialog=False)
        self.assertIsInstance(dlg, TP.PresetsDialog)
        self.assertEqual(dlg.new_preset('A908'), 'A908')
        self.assertEqual(dlg.duplicate(), 'A908 (2)')
        self.assertEqual(dlg.rename('B908'), 'B908')
        self.assertEqual(sorted(TP.load(self.w.settings)), ['A908', 'B908'])
        dlg.w['size'].setValue(22.0)                                          # chaque champ : enregistré aussitôt
        dlg.w['underline'].setChecked(True)
        got = TP.load(self.w.settings)['B908']
        self.assertEqual((got['attrs']['size'], bool(got['extra'].get('underline'))), (22.0, True))
        path = os.path.join(tempfile.mkdtemp(), 'p908.json')
        self.assertEqual(dlg.export_file(path), 2)
        self.assertTrue(dlg.delete())
        self.assertEqual(list(TP.load(self.w.settings)), ['A908'])
        self.assertEqual(dlg.import_file(path), 2)
        self.assertEqual(TP.load(self.w.settings)['B908']['attrs']['size'], 22.0)
        self.assertGreater(self.w.textbar.presets.findData('B908'), 0)        # la liste du ruban suit

    def test_editing_the_preset_of_new_texts(self):
        from vectordrive.ui import text_presets as TP
        dlg = self.w.text_presets_dialog(exec_dialog=False)
        dlg.new_preset('C908')
        self.assertEqual(self.w.use_text_preset('C908'), 0)                   # rien de sélectionné : nouveaux textes
        dlg.refill('C908')
        dlg.w['italic'].setValue(20.0)
        self.assertEqual(TP.new_text_format(self.w.settings)['extra']['italic'], 20.0)
        self.assertEqual(self.w.textbar.italic.value(), 20.0)

    def test_the_action_opens_the_manager(self):
        from vectordrive.ui import text_presets as TP
        with mock.patch.object(TP.PresetsDialog, 'exec', return_value=0) as ex:
            self.w.A['text_styles'].trigger()
        self.assertEqual(ex.call_count, 1)
        self.assertEqual(self.w.A['text_styles'].text(), 'Préréglages de texte…')


class TypeEditFormat(Base):

    def setUp(self):
        super().setUp()
        self.w.settings.setValue('vue/disposition', 'typeedit13')
        with mock.patch.object(TL, 'installed', return_value=TL.parse(SCRIPT, STRINGS)):
            self.assertTrue(self.w.apply_ribbon_layout())

    def tearDown(self):
        self.w.settings.remove('vue/disposition')
        super().tearDown()

    def test_text_mode_tab_has_the_fields(self):
        from vectordrive.ui import text_presets as TP
        r = self.w.ribbon
        page = r.widget(next(i for i in range(r.count()) if r.widget(i).property('te_context') == 'idContextRapido'))
        bar = self.w.textbar_te
        self.assertIsNotNone(bar)
        for wid in (bar.font, bar.size, bar.width, bar.italic, bar.spacing, bar.spacing_mode, bar.presets):
            self.assertTrue(page.isAncestorOf(wid))
        TP.set_new_text_format(self.w.settings, TP.with_value(TP.new_text_format(self.w.settings), 'size', 6.5))
        self.select([])
        self.w.show_te_context('idContextRapido')
        self.assertEqual(bar.size.value(), 6.5)
        bar.apply('size', 8.5)                                                 # avant de cliquer : nouveaux textes
        self.assertEqual(TP.new_text_format(self.w.settings)['attrs']['size'], 8.5)
        self.assertEqual(self.w.textbar.size.value(), 8.5)

    def test_back_to_vectordrive_layout(self):
        self.assertIsNotNone(self.w.textbar_te)
        self.w.settings.remove('vue/disposition')
        self.assertFalse(self.w.apply_ribbon_layout())
        self.assertIsNone(self.w.textbar_te)
        self.select([])                                                       # sans erreur


if __name__ == '__main__':
    unittest.main()
