"""Polices TypeEdit et LaserType (demande du 26/11 : « Je branche un dongle TE + LT +3D : toutes les polices TE et LT
doivent être intégrées dans plugin BFM; ») : les TrueType rangées dans les dossiers d'un format de plugin qui a son
filtre vont sous ce filtre (« TypeEdit ») dans la liste des polices ; une famille du système reste du système.
Polices fabriquées pour l'essai (format inventé, TrueType bâties par fontTools), jamais celles du poste."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'rpolLT.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ.setdefault('VECTORDRIVE_KEYS_MEMORY', '1')

from PySide6.QtWidgets import QApplication  # noqa: E402

from vectordrive import plugins  # noqa: E402
from vectordrive.core import fontformats, fonts  # noqa: E402
from vectordrive.core.geom import Path  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : les TrueType livrées avec TypeEdit / LaserType restaient parmi les polices du système'

LIVREE = 'Essai Filaire VN Open'                         # TrueType dans le dossier du format qui a son filtre
SYSTEME = 'Essai Systeme Livree'                         # même famille installée dans le système
HORS = 'Essai Hors TypeEdit'                             # TrueType d'un autre dossier
SANS = 'Essai Sans Filtre'                               # TrueType du dossier d'un format sans filtre
TE = 'Essai Trait 1L'                                    # police du format inventé


def make_ttf(path, family):
    """Une TrueType minimale (un « A ») au nom de famille donné."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(['.notdef', 'A'])
    fb.setupCharacterMap({65: 'A'})
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0))
    pen.lineTo((500, 700))
    pen.lineTo((1000, 0))
    pen.closePath()
    fb.setupGlyf({'.notdef': TTGlyphPen(None).glyph(), 'A': pen.glyph()})
    fb.setupHorizontalMetrics({'.notdef': (500, 0), 'A': (1000, 0)})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({'familyName': family, 'styleName': 'Regular'})
    fb.setupOS2()
    fb.setupPost()
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    fb.save(str(path))


def font_name(path):
    return pathlib.Path(path).read_text(encoding='utf-8').strip() or None


def glyph(path, char):
    return Path(), 0.5


def metrics(path):
    return {'upem': 1.0, 'ascent': 1.25, 'descent': 0.75, 'cap': 1.0}


class Base(unittest.TestCase):
    """Un « système » (dossier de polices du système fabriqué), un dossier TypeEdit (FONTS : police du format inventé,
    TTF\\ livrées), un dossier ordinaire, un format sans filtre et son dossier ; inventaire dans un cache d'essai."""

    def setUp(self):
        t = pathlib.Path(tempfile.mkdtemp())
        self.sys_dir, self.te, self.other, self.plain = t / 'Windows' / 'Fonts', t / 'TE' / 'FONTS', t / 'Autres', \
            t / 'SansFiltre'
        make_ttf(self.sys_dir / 'systeme.ttf', SYSTEME)
        (self.te / 'GII').mkdir(parents=True)
        (self.te / 'GII' / 'te.zte').write_text(TE, encoding='utf-8')
        make_ttf(self.te / 'TTF' / 'livree.ttf', LIVREE)
        make_ttf(self.te / 'TTF' / 'systeme.ttf', SYSTEME)
        make_ttf(self.other / 'hors.ttf', HORS)
        make_ttf(self.plain / 'sans.ttf', SANS)
        (self.plain / 'p.zsf').write_text('Essai Police Sans Filtre', encoding='utf-8')
        for p in (mock.patch.dict(os.environ, {'VECTORDRIVE_CACHE': tempfile.mkdtemp()}),
                  mock.patch.object(fonts, 'FONT_DIRS', [self.sys_dir]),
                  mock.patch.object(fonts, 'SYSTEM_FONT_DIRS', (self.sys_dir,)),
                  mock.patch.dict(fontformats.FORMATS, clear=True)):
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(fonts.refresh)
        fonts.add_dirs([self.other])
        fonts.add_font_dir(self.te)                      # lu AVANT le système : la copie TypeEdit de SYSTEME l'emporte
        api =plugins.Api(plugins.Registry(), plugins.PluginInfo(module='essai_polices_lt', version='1.0'))
        api.add_font_format('Police d’essai TypeEdit', ('.zte',), font_name=font_name, glyph=glyph, metrics=metrics,
                            dirs=[self.te], filter_label='TypeEdit')
        api.add_font_format('Police d’essai', ('.zsf',), font_name=font_name, glyph=glyph, metrics=metrics,
                            dirs=[self.plain])
        fonts.refresh()
        from vectordrive.ui import fontlist
        st = fontlist._settings()
        for k in (fontlist.FILTER_KEY, fontlist.FAVORITES_KEY):
            self.addCleanup(st.remove, k)

    def box(self):
        from vectordrive.ui.dialogs import FontBox
        b = FontBox()
        self.addCleanup(b.deleteLater)
        return b

    def items(self, b):
        from PySide6.QtCore import Qt
        from vectordrive.ui.fontlist import GROUP_ROLE, KIND_ROLE
        out = {}
        for i in range(b.count()):
            if b.itemText(i):
                out.setdefault(b.itemText(i), []).append((b.itemData(i, KIND_ROLE), b.itemData(i, GROUP_ROLE) or '',
                                                          str(b.itemData(i, Qt.ItemDataRole.ToolTipRole) or '')))
        return out


class Groupe(Base):
    def test_truetype_of_the_typeedit_folders_under_its_filter(self):
        self.assertTrue(hasattr(fonts, 'group_of'), BEFORE)
        self.assertEqual(fonts.group_of(LIVREE), 'TypeEdit')
        self.assertEqual(fonts.group_of(LIVREE.upper()), 'TypeEdit')          # par la clé, comme l'inventaire

    def test_others_keep_their_place(self):
        self.assertTrue(hasattr(fonts, 'group_of'), BEFORE)
        # l'inventaire a retenu la copie du dossier TypeEdit (lu en premier) : seule la garde SYSTEM_KEYS la rend au
        # système
        key = fonts._key(SYSTEME)
        self.assertTrue(fonts.families()[key][0].startswith(str(self.te)), fonts.families()[key])
        self.assertIn(key, fonts.SYSTEM_KEYS)
        self.assertEqual(fontformats.group_of_file(fonts.families()[key][0]), 'TypeEdit')
        self.assertEqual(fonts.group_of(SYSTEME), '')        # installée dans le système : du système
        self.assertEqual(fonts.group_of(HORS), '')           # autre dossier
        self.assertEqual(fonts.group_of(SANS), '')           # dossier d'un format sans filtre
        self.assertEqual(fonts.group_of(TE), '')             # lue par le plugin : son format a déjà son filtre
        self.assertEqual(fonts.group_of('Police Inexistante'), '')

    def test_file_compared_as_text(self):
        self.assertTrue(hasattr(fontformats, 'group_of_file'), BEFORE)
        self.assertEqual(fontformats.group_of_file(self.te / 'TTF' / 'livree.ttf'), 'TypeEdit')
        self.assertEqual(fontformats.group_of_file(str(self.te) + '2/x.ttf'), '')   # dossier voisin au nom proche
        self.assertEqual(fontformats.group_of_file(self.plain / 'sans.ttf'), '')
        with mock.patch.object(pathlib.Path, 'is_dir', side_effect=AssertionError('disque')), \
                mock.patch.object(os, 'stat', side_effect=AssertionError('disque')):
            self.assertEqual(fontformats.group_of_file('\\\\SRV-ESSAI\\Polices\\x.ttf'), '')


class Liste(Base):
    def test_fontbox_puts_them_with_the_typeedit_fonts(self):
        got = self.items(self.box())
        self.assertIn(LIVREE, got)
        self.assertEqual(len(got[LIVREE]), 1, got[LIVREE])                  # une fois
        kind, group, tip = got[LIVREE][0]
        self.assertEqual((kind, group), ('plugin', 'TypeEdit'), BEFORE)
        self.assertIn('TrueType', tip)
        self.assertEqual(got[TE][0][:2], ('plugin', 'TypeEdit'))
        for n in (HORS, SANS):                                              # les autres : polices du système
            self.assertEqual(got[n], [('systeme', '', '')], n)

    def test_typeedit_filter_shows_them(self):
        from vectordrive.ui import fontlist
        b = self.box()
        p = fontlist.FontPopup(b)
        self.addCleanup(p.deleteLater)
        p.open_for()
        self.addCleanup(p.hide)
        key = fontlist.GROUP_PREFIX + 'TypeEdit'
        p.filter_buttons[key].setChecked(True)
        p.refill()
        self.assertEqual(sorted(p.shown()), sorted([TE, LIVREE]), BEFORE)
        p.filter_buttons['systeme'].setChecked(True)
        p.refill()
        self.assertNotIn(LIVREE, p.shown())
        self.assertIn(HORS, p.shown())

    def test_order_with_the_plugin_fonts(self):
        b = self.box()
        names = [b.itemText(i) for i in range(b.count())]
        # dans le bloc des polices de plugin, avant le séparateur qui le ferme (triées ensemble, sans la casse)
        block = names[names.index(TE if TE.lower() < LIVREE.lower() else LIVREE):]
        block = block[:block.index('')]
        self.assertEqual(block, sorted([TE, LIVREE, 'Essai Police Sans Filtre'], key=str.lower), BEFORE)


if __name__ == '__main__':
    unittest.main()
