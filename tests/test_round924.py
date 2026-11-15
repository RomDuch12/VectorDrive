"""Round 924 : le cœur ne lit plus les polices de TypeEdit ; un plugin apporte un format de polices
(`Api.add_font_format`) que le cœur lit comme les autres : listes de polices, mise en page, crénage, caractères,
inventaire en cache, éditeur de polices. Les polices SVG sont lues directement (`svgfonts`)."""
import importlib.util
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r924.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ.setdefault('VECTORDRIVE_CACHE', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from vectordrive.core import fonts, svgfonts
from vectordrive.core import text as T
from vectordrive.core.geom import Contour, Line, Path

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAGIC = b'TRAIT924\n'
LABEL = 'Police d’essai 924'


def write_font(d, name='Trait Neuf', stem='trait', ext='.essai924'):
    p = pathlib.Path(d) / f'{stem}{ext}'
    p.write_bytes(MAGIC + name.encode('utf-8'))
    return p


def font_name(path):
    b = pathlib.Path(path).read_bytes()
    return b[len(MAGIC):].decode('utf-8') if b.startswith(MAGIC) else None


def glyph(path, ch):
    if ch.isspace():
        return Path(), 0.5
    return Path([Contour([Line((0.0, 0.0), (0.5, 1.0)), Line((0.5, 1.0), (1.0, 0.0))])]), 1.2


def metrics(path):
    return {'upem': 1.0, 'ascent': 1.25, 'descent': 0.75, 'cap': 1.0}


def kerning(path, a, b):
    return -0.2 if (a, b) == ('A', 'V') else 0.0


def characters(path):
    return [ord(c) for c in 'WAV ']


def broken_name(path):
    raise ValueError('lecteur en défaut')


class PluginFormat(unittest.TestCase):

    def setUp(self):
        from vectordrive import plugins
        from vectordrive.core import fontformats
        self.ff = fontformats
        self.dir = tempfile.mkdtemp()
        self.path = write_font(self.dir)
        self.cleared = []
        self.api = plugins.Api(plugins.REGISTRY, plugins.PluginInfo('essai924', 'Essai 924'))
        self.api.add_font_format(LABEL, ('.ESSAI924',), font_name=font_name, glyph=glyph, metrics=metrics,
                                 kerning=kerning, characters=characters, clear=lambda: self.cleared.append(1),
                                 dirs=[self.dir])
        self.fmt = fontformats.of(self.path)

    def tearDown(self):
        from vectordrive import plugins
        for fmt in self.ff.registered():
            if fmt.extensions[0] in ('.essai924', '.casse924'):
                self.ff.unregister(fmt)
        plugins.REGISTRY.font_formats[:] = [f for f in plugins.REGISTRY.font_formats if f[0] != LABEL]
        if pathlib.Path(self.dir) in fonts.FONT_DIRS:
            fonts.FONT_DIRS.remove(pathlib.Path(self.dir))
        fonts.refresh()
        fonts.glyph.cache_clear()
        fonts.metrics.cache_clear()

    def test_registered(self):
        from vectordrive import plugins
        self.assertIsNotNone(self.fmt)
        self.assertEqual(self.fmt.extensions, ('.essai924',))
        self.assertIn((LABEL, ('.essai924',)), plugins.REGISTRY.font_formats)
        self.assertIn(pathlib.Path(self.dir), fonts.FONT_DIRS)
        self.assertIn('.essai924', fonts._font_ext())

    def test_listed_as_a_plugin_font(self):
        self.assertIn('Trait Neuf', fonts.plugin_families())
        self.assertEqual(fonts.PLUGIN_FONTS['Trait Neuf'], str(self.path))
        self.assertNotIn('Trait Neuf', fonts.svg_families())
        self.assertTrue(fonts.is_available('Trait Neuf'))
        self.assertEqual(fonts.find_font('Trait Neuf')[0], str(self.path))

    def test_layout_uses_the_reader(self):
        bb = T.layout('A', 'Trait Neuf', 10).bbox()
        self.assertAlmostEqual(bb[3], 10.0, places=6)               # hauteur 10 : le sommet du glyphe à 1
        self.assertAlmostEqual(bb[2] - bb[0], 10.0, places=6)
        self.assertEqual(fonts.metrics(str(self.path))['cap'], 1.0)

    def test_kerning_from_the_reader(self):
        plain = T.layout('AV', 'Trait Neuf', 10, kerning=False).bbox()
        kerned = T.layout('AV', 'Trait Neuf', 10).bbox()
        self.assertAlmostEqual(plain[2] - kerned[2], 2.0, places=6)    # −0,2 de la hauteur

    def test_characters_from_the_reader(self):
        self.assertEqual(fonts.characters('Trait Neuf'), (' ', 'A', 'V', 'W'))

    def test_font_box_tooltip_is_the_format_label(self):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
        from vectordrive.ui.dialogs import FontBox
        _app = QApplication.instance() or QApplication([])
        box = FontBox()
        i = box.findText('Trait Neuf')
        self.assertGreaterEqual(i, 0)
        self.assertEqual(box.itemData(i, Qt.ItemDataRole.ToolTipRole), LABEL)

    def test_font_editor_follows_the_format(self):
        from vectordrive.core import fontedit as FE
        self.assertFalse(FE.can_clone('Trait Neuf'))
        self.fmt.clonable = True
        self.assertTrue(FE.can_clone('Trait Neuf'))

    def test_font_changed_clears_the_reader(self):
        fonts.font_changed()
        self.assertEqual(self.cleared, [1])

    def test_inventory_follows_the_formats(self):
        self.assertTrue(fonts.is_available('Trait Neuf'))
        cache = fonts.cache_file()
        self.assertTrue(cache.exists())
        self.ff.unregister(self.fmt)                                # le plugin parti : le fichier n'est plus lu
        self.assertFalse(fonts.is_available('Trait Neuf'))
        self.assertNotIn('Trait Neuf', fonts.plugin_families())
        self.ff.register(self.fmt)
        self.assertTrue(fonts.is_available('Trait Neuf'))

    def test_broken_reader_keeps_the_file_name(self):
        write_font(self.dir, stem='cassee', ext='.casse924')
        self.api.add_font_format('Casse', ('.casse924',), font_name=broken_name, glyph=glyph, metrics=metrics)
        self.assertTrue(fonts.is_available('cassee'))
        self.assertTrue(fonts.is_available('Trait Neuf'))
        self.assertNotIn('cassee', fonts.plugin_families())


class CoreWithoutTypeEditFonts(unittest.TestCase):

    def test_no_reader_in_the_core(self):
        self.assertIsNone(importlib.util.find_spec('vectordrive.core.gfonts'))
        self.assertEqual(fonts.FONT_EXT, ('.ttf', '.otf', '.ttc', '.svg'))
        self.assertFalse(hasattr(fonts, 'gravotech_families'))
        self.assertFalse(hasattr(fonts, 'GRAVOTECH'))
        src = (ROOT / 'vectordrive' / 'core' / 'fonts.py').read_text(encoding='utf-8')
        self.assertNotIn('ProgramData/Gravotech', src)

    def test_unknown_files_are_not_fonts(self):
        from vectordrive.core import fontformats
        d = tempfile.mkdtemp()
        write_font(d, name='Pas Lue', stem='paslue', ext='.essai924b')
        self.assertIsNone(fontformats.of(pathlib.Path(d) / 'paslue.essai924b'))
        fonts.add_dirs([d])
        try:
            self.assertFalse(fonts.is_available('paslue'))
            self.assertFalse(fonts.is_available('Pas Lue'))
        finally:
            fonts.FONT_DIRS.remove(pathlib.Path(d))
            fonts.refresh()

    def test_svg_fonts_read_directly(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, 'casse.svg')
        pathlib.Path(p).write_text('<svg><font>', encoding='utf-8')
        self.assertEqual(svgfonts.metrics(p), {'upem': 1.0, 'ascent': 1.25, 'descent': 0.75, 'cap': 1.0})
        self.assertEqual(svgfonts.glyph(p, 'A'), (Path(), 0.0))
        self.assertEqual(svgfonts.kerning(p, 'A', 'V'), 0.0)
        self.assertEqual(fonts.metrics(p)['ascent'], 1.25)

    def test_autotest_spec_and_docs(self):
        launcher = (ROOT / 'VectorDrive.py').read_text(encoding='utf-8')
        self.assertNotIn('gravotech_families', launcher)
        self.assertNotIn('.vnf', launcher)
        spec = (ROOT / 'VectorDrive.spec').read_text(encoding='utf-8')
        self.assertIn("'vectordrive.core.fontformats'", spec)
        self.assertNotIn('gfonts', spec)
        readme = (ROOT / 'README.md').read_text(encoding='utf-8')
        self.assertNotIn('.vnf', readme)
        self.assertIn('add_font_format', readme)
        self.assertIn('add_font_format', (ROOT / 'docs' / 'ARCHITECTURE.md').read_text(encoding='utf-8'))
        self.assertFalse((ROOT / 'docs' / 'formats' / 'polices_gravotech.md').exists())


if __name__ == '__main__':
    unittest.main()
