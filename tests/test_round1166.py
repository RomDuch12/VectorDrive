"""Round 1166 (demande du 26/11 : « toutes les polices TE dans plugin BFM ont disparu ? tout rétablir avec filtre
associé dans la liste des polices. ») : un format de polices de plugin donne le libellé court de son filtre
(`filter_label`) ; la liste des polices a un filtre et une section à ce nom ; F10 › Police par défaut propose les
polices de VectorDrive. Polices fabriquées pour l'essai (format inventé), jamais celles du poste."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1166.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ.setdefault('VECTORDRIVE_KEYS_MEMORY', '1')

from PySide6.QtWidgets import QApplication, QFontComboBox  # noqa: E402

from vectordrive import plugins  # noqa: E402
from vectordrive.core import fontformats, fonts  # noqa: E402
from vectordrive.core.geom import Path  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : pas de filtre propre aux polices d’un format de plugin (TypeEdit), et F10 ne proposait que le système'

TE = ('Essai Trait 1L', 'Essai Gravure 2L')                # polices du format qui a son filtre (« TypeEdit »)
OTHER = ('Essai Autre',)                                   # police d'un format de plugin sans filtre


def font_name(path):
    return pathlib.Path(path).read_text(encoding='utf-8').strip() or None


def glyph(path, char):
    return Path(), 0.5


def metrics(path):
    return {'upem': 1.0, 'ascent': 1.25, 'descent': 0.75, 'cap': 1.0}


class Base(unittest.TestCase):
    """Un dossier de polices fabriquées, l'inventaire dans un cache d'essai, deux formats inventés."""
    other = True                                           # un format sans filtre aussi
    te = True                                              # le format qui a son filtre

    def setUp(self):
        self.folder = pathlib.Path(tempfile.mkdtemp())
        for i, n in enumerate(TE):
            (self.folder / f'te{i}.zte').write_text(n, encoding='utf-8')
        for i, n in enumerate(OTHER):
            (self.folder / f'au{i}.zau').write_text(n, encoding='utf-8')
        for p in (mock.patch.dict(os.environ, {'VECTORDRIVE_CACHE': tempfile.mkdtemp()}),
                  mock.patch.object(fonts, 'FONT_DIRS', []), mock.patch.dict(fontformats.FORMATS, clear=True)):
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(fonts.refresh)
        api = plugins.Api(plugins.Registry(), plugins.PluginInfo(module='essai_polices', version='1.0'))
        try:
            api.add_font_format('Police d’essai TypeEdit', ('.zte',) if self.te else ('.zzz',), font_name=font_name,
                                glyph=glyph, metrics=metrics, dirs=[self.folder], filter_label=' TypeEdit ')
        except TypeError as e:
            self.fail(f'{BEFORE} ({e})')
        if self.other:
            api.add_font_format('Police d’essai', ('.zau',), font_name=font_name, glyph=glyph, metrics=metrics)
        fonts.refresh()
        from vectordrive.ui import fontlist
        st = fontlist._settings()
        for k in (fontlist.FILTER_KEY, fontlist.FAVORITES_KEY):
            self.addCleanup(st.remove, k)

    def box(self, current=None):
        from vectordrive.ui.dialogs import FontBox
        b = FontBox()
        self.addCleanup(b.deleteLater)
        if current:
            b.setCurrentFont(current)
        return b

    def popup(self, current=None, saved=None):
        from vectordrive.ui import fontlist
        if saved:
            fontlist._settings().setValue(fontlist.FILTER_KEY, saved)
        b = self.box(current)
        p = fontlist.FontPopup(b)
        self.addCleanup(p.deleteLater)
        p.open_for()
        self.addCleanup(p.hide)
        return p

    def choose(self, p, key):
        p.filter_buttons[key].setChecked(True)
        p.refill()
        return p.shown()


class Format(Base):
    def test_filter_label_kept_by_the_format(self):
        fmt = fontformats.of(self.folder / 'te0.zte')
        self.assertEqual(fmt.filter_label, 'TypeEdit')
        self.assertEqual(fontformats.of(self.folder / 'au0.zau').filter_label, '')
        self.assertEqual(sorted(fonts.plugin_families()), sorted(TE + OTHER))

    def test_fontbox_marks_the_filter_of_each_font(self):
        from vectordrive.ui.fontlist import GROUP_ROLE, KIND_ROLE
        b = self.box()
        got = {b.itemText(i): (b.itemData(i, KIND_ROLE), b.itemData(i, GROUP_ROLE)) for i in range(b.count())}
        for n in TE:
            self.assertEqual(got[n], ('plugin', 'TypeEdit'))
        self.assertEqual(got[OTHER[0]][0], 'plugin')
        self.assertFalse(got[OTHER[0]][1])


class Popup(Base):
    def test_typeedit_filter_after_plugins(self):
        from vectordrive.ui.fontlist import GROUP_PREFIX
        p = self.popup()
        key = GROUP_PREFIX + 'TypeEdit'
        self.assertIn(key, p.filter_buttons, BEFORE)
        b = p.filter_buttons[key]
        self.assertEqual(b.text(), 'TypeEdit')
        self.assertTrue(b.isEnabled())
        row = p._filter_row
        self.assertEqual(row.indexOf(b), row.indexOf(p.filter_buttons['plugin']) + 1)
        self.assertEqual(sorted(self.choose(p, key)), sorted(TE))

    def test_plugins_filter_keeps_the_others(self):
        p = self.popup()
        self.assertFalse(p.filter_buttons['plugin'].isHidden())
        self.assertEqual(self.choose(p, 'plugin'), list(OTHER))

    def test_sections_named_after_the_filter(self):
        from vectordrive.ui.fontlist import NAME_ROLE
        p = self.popup()
        heads = [p.list.item(r).text() for r in range(p.list.count()) if p.list.item(r).data(NAME_ROLE) is None]
        self.assertIn('Polices TypeEdit', heads, BEFORE)
        self.assertIn('Lues par un plugin', heads)
        rows = [p.list.item(r).text() for r in range(p.list.count())]
        i = rows.index('Polices TypeEdit')
        self.assertEqual(sorted(rows[i + 1:i + 1 + len(TE)]), sorted(TE))

    def test_saved_filter_reopened(self):
        from vectordrive.ui.fontlist import GROUP_PREFIX
        key = GROUP_PREFIX + 'TypeEdit'
        p = self.popup(current=TE[0], saved=key)
        self.assertEqual(p.current_filter(), key, BEFORE)
        self.assertEqual(sorted(p.shown()), sorted(TE))

    def test_search_inside_the_filter(self):
        from vectordrive.ui.fontlist import GROUP_PREFIX
        p = self.popup()
        p.filter_buttons[GROUP_PREFIX + 'TypeEdit'].setChecked(True)
        p.search.setText('gravure')
        self.assertEqual(p.shown(), ['Essai Gravure 2L'])

    def test_recognition_compares_the_filter_only(self):
        from vectordrive.ui.fontlist import GROUP_PREFIX
        p = self.popup()
        p.filter_buttons[GROUP_PREFIX + 'TypeEdit'].setChecked(True)
        seen = {}

        def rank(paths, names, count, **kw):
            seen['names'] = list(names)
            return []
        from vectordrive.core import fontmatch
        with mock.patch.object(p, 'selection_paths', return_value=[Path()]), \
                mock.patch.object(fontmatch, 'selection_images', return_value=[1]), \
                mock.patch.object(fontmatch, 'rank', side_effect=rank):
            p.recognize()
            p._thread.join(10)
        self.assertEqual(sorted(seen['names']), sorted(TE))


class OnlyTypeEdit(Base):
    """Toutes les polices de plugin ont leur filtre : « Plugins » ferait double emploi."""
    other = False

    def test_plugins_button_hidden(self):
        from vectordrive.ui.fontlist import GROUP_PREFIX
        p = self.popup(current=TE[0], saved='plugin')
        self.assertTrue(p.filter_buttons['plugin'].isHidden(), BEFORE)
        self.assertEqual(p.current_filter(), GROUP_PREFIX + 'TypeEdit')   # « Plugins » retenu d'avant : TypeEdit
        self.assertEqual(sorted(p.shown()), sorted(TE))

    def test_format_gone_button_gone(self):
        from vectordrive.ui.fontlist import GROUP_PREFIX
        p = self.popup()
        fontformats.FORMATS.clear()
        fonts.refresh()
        p.box.reload()
        p.open_for()
        self.assertNotIn(GROUP_PREFIX + 'TypeEdit', p.filter_buttons)


class NoPluginFont(Base):
    """Aucune police de plugin ni filtre de format : « Plugins » reste, grisé, comme avant."""
    other = False
    te = False

    def test_plugins_button_greyed_not_hidden(self):
        from vectordrive.ui.fontlist import GROUP_PREFIX
        p = self.popup(saved='plugin')
        b = p.filter_buttons['plugin']
        self.assertFalse(b.isHidden())
        self.assertFalse(b.isEnabled())
        self.assertFalse([k for k in p.filter_buttons if k.startswith(GROUP_PREFIX)])
        self.assertEqual(p.current_filter(), 'toutes')


class Options(Base):
    def test_default_text_font_lists_plugin_fonts(self):
        from vectordrive.ui.dialogs import FontBox
        from vectordrive.ui.options import OptionsDialog
        from vectordrive import portable
        st = portable.settings()
        self.addCleanup(st.remove, 'texte/police')
        st.setValue('texte/police', TE[1])
        dlg = OptionsDialog(st)
        self.addCleanup(dlg.deleteLater)
        w = dlg.widgets['texte/police']
        self.assertIsInstance(w, FontBox, BEFORE)
        self.assertGreaterEqual(w.findText(TE[0]), 0)
        self.assertEqual(dlg.read('texte/police'), TE[1])
        w.setCurrentFont(TE[0])
        self.assertEqual(dlg.read('texte/police'), TE[0])
        self.assertIsInstance(dlg.widgets['vue/police_ui'], QFontComboBox)    # l'interface : le système seulement


if __name__ == '__main__':
    unittest.main()
