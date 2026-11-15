"""Round 776 : polices SVG."""
import json
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())

from PySide6.QtWidgets import QApplication, QMessageBox

from vectordrive.core import fonts, svgfonts
from vectordrive.core import text as TX
from vectordrive.core.document import Text
from vectordrive.io import vnd

SVG = """<?xml version="1.0" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg" version="1.1">
<defs>
<font id="Essai" horiz-adv-x="600">
  <font-face font-family="Trait Essai" units-per-em="1000" ascent="800" descent="-200" cap-height="650"/>
  <missing-glyph horiz-adv-x="500"/>
  <glyph unicode=" " glyph-name="space" horiz-adv-x="300"/>
  <glyph unicode="H" glyph-name="H" horiz-adv-x="700" d="M100 0 L100 700 M600 0 L600 700 M100 350 L600 350"/>
  <glyph unicode="O" glyph-name="O" d="M100 0 L500 0 L500 700 L100 700 Z"/>
  <glyph unicode="&#xE9;" glyph-name="eacute" horiz-adv-x="500" d="M100 0 L400 0"/>
  <glyph unicode="fi" glyph-name="f_i" horiz-adv-x="500" d="M0 0 L100 100"/>
  <hkern u1="H" u2="O" k="100"/>
  <hkern g1="O" g2="eacute" k="-50"/>
  <hkern u1="U+0041-0043" u2="H" k="10"/>
</font>
</defs>
</svg>
"""


def write(folder, name='essai.svg', text=SVG):
    p = pathlib.Path(folder) / name
    p.write_text(text, encoding='utf-8')
    return str(p)


class Reading(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = write(self.dir)
        self.font = svgfonts.SvgFont(self.path)

    def test_name(self):
        self.assertEqual(svgfonts.font_name(self.path), 'Trait Essai')
        self.assertEqual(self.font.name, 'Trait Essai')

    def test_name_from_the_file_when_undeclared(self):
        p = write(self.dir, 'sans_nom.svg', '<svg><font><glyph unicode="A" d="M0 0 L1 1"/></font></svg>')
        self.assertEqual(svgfonts.font_name(p), 'sans_nom')

    def test_ordinary_svg_is_not_a_font(self):
        p = write(self.dir, 'dessin.svg', '<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0 L1 1"/><text font-family="Arial">a</text></svg>')
        self.assertIsNone(svgfonts.font_name(p))

    def test_missing_file(self):
        self.assertIsNone(svgfonts.font_name(os.path.join(self.dir, 'absent.svg')))

    def test_metrics_in_em(self):
        self.assertAlmostEqual(self.font.ascent, 0.8)
        self.assertAlmostEqual(self.font.descent, 0.2)

    def test_cap_height_measured_on_h(self):
        self.assertAlmostEqual(self.font.cap, 0.7)

    def test_cap_height_declared_when_no_h(self):
        p = write(self.dir, 'c.svg', '<svg><font><font-face units-per-em="100" cap-height="60"/><glyph unicode="A" d="M0 0 L1 1"/></font></svg>')
        self.assertAlmostEqual(svgfonts.SvgFont(p).cap, 0.6)

    def test_open_strokes_stay_open(self):
        path, adv = self.font.glyph(ord('H'))
        self.assertAlmostEqual(adv, 0.7)
        self.assertEqual(len(path.contours), 3)
        self.assertTrue(all(not c.closed for c in path.contours))

    def test_closed_contour(self):
        path, _adv = self.font.glyph(ord('O'))
        self.assertTrue(path.contours[0].closed)

    def test_default_advance(self):
        self.assertAlmostEqual(self.font.glyph(ord('O'))[1], 0.6)

    def test_y_points_up(self):
        path, _adv = self.font.glyph(ord('H'))
        b = path.bbox()
        self.assertAlmostEqual(b[1], 0.0)
        self.assertAlmostEqual(b[3], 0.7)

    def test_empty_glyph(self):
        path, adv = self.font.glyph(ord(' '))
        self.assertEqual(path.contours, [])
        self.assertAlmostEqual(adv, 0.3)

    def test_ligature_not_listed(self):
        self.assertNotIn(ord('f'), self.font.index)
        self.assertEqual(sorted(self.font.index), sorted([ord(' '), ord('H'), ord('O'), 0xE9]))

    def test_missing_glyph_gives_its_advance(self):
        path, adv = self.font.glyph(ord('Z'))
        self.assertEqual(path.contours, [])
        self.assertAlmostEqual(adv, 0.5)

    def test_no_missing_glyph(self):
        p = write(self.dir, 'n.svg', '<svg><font><glyph unicode="A" d="M0 0 L1 1"/></font></svg>')
        self.assertIsNone(svgfonts.SvgFont(p).glyph(ord('Z')))

    def test_kerning_by_char_by_name_by_range(self):
        self.assertAlmostEqual(self.font.kerning(ord('H'), ord('O')), -0.1)
        self.assertAlmostEqual(self.font.kerning(ord('O'), 0xE9), 0.05)
        self.assertAlmostEqual(self.font.kerning(ord('B'), ord('H')), -0.01)
        self.assertEqual(self.font.kerning(ord('H'), ord('H')), 0.0)

    def test_no_font_raises(self):
        p = write(self.dir, 'x.svg', '<svg><path d="M0 0"/></svg>')
        with self.assertRaises(ValueError):
            svgfonts.SvgFont(p)

    def test_font_without_chars_raises(self):
        p = write(self.dir, 'x2.svg', '<svg><font><font-face units-per-em="1000"/></font></svg>')
        with self.assertRaises(ValueError):
            svgfonts.SvgFont(p)

    def test_bad_numbers_fall_back(self):
        p = write(self.dir, 'b.svg', '<svg><font horiz-adv-x="xx"><font-face units-per-em="0" ascent="nan" descent="inf"/><glyph unicode="A" d="M0 0 L1 1"/></font></svg>')
        f = svgfonts.SvgFont(p)
        self.assertEqual(f.upem, 1000.0)
        self.assertGreater(f.cap, 0.0)


class Routing(unittest.TestCase):
    """`fonts` lit les polices SVG (round 924 : directement, `svgfonts`) : tout ce qui passe par `fonts` et `text` en
    profite."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = write(self.dir)
        svgfonts.load.cache_clear()
        svgfonts.glyph.cache_clear()
        fonts.glyph.cache_clear()
        fonts.metrics.cache_clear()

    def test_is_a_font_file(self):
        self.assertIn('.svg', fonts._font_ext())

    def test_glyph(self):
        path, adv = fonts.glyph(self.path, 0, 'H')
        self.assertEqual(len(path.contours), 3)
        self.assertAlmostEqual(adv, 0.7)

    def test_metrics(self):
        m = fonts.metrics(self.path, 0)
        self.assertEqual(m['upem'], 1.0)
        self.assertAlmostEqual(m['cap'], 0.7)
        self.assertAlmostEqual(m['ascent'], 0.8)

    def test_broken_font_keeps_defaults(self):
        p = write(self.dir, 'casse.svg', '<svg><font>')
        self.assertEqual(svgfonts.metrics(p)['cap'], 1.0)
        self.assertEqual(svgfonts.glyph(p, 'A'), (svgfonts.Path(), 0.0))
        self.assertEqual(svgfonts.kerning(p, 'A', 'B'), 0.0)

    def test_font_name_dispatch(self):
        self.assertEqual(svgfonts.font_name(self.path), 'Trait Essai')


class Inventory(unittest.TestCase):
    def setUp(self):
        self.cache = tempfile.mkdtemp()
        self.env = mock.patch.dict(os.environ, {'VECTORDRIVE_CACHE': self.cache})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.addCleanup(fonts.refresh)
        self.dirs = mock.patch.object(fonts, 'FONT_DIRS', [])
        self.dirs.start()
        self.addCleanup(self.dirs.stop)
        self.folder = fonts.user_font_dir()
        self.folder.mkdir(parents=True)
        write(self.folder)
        write(self.folder, 'dessin.svg', '<svg><path d="M0 0 L1 1"/></svg>')
        fonts.refresh()

    def test_user_folder_follows_the_test_cache(self):
        self.assertTrue(str(self.folder).startswith(self.cache))

    def test_found_by_name(self):
        self.assertTrue(fonts.is_available('Trait Essai'))
        self.assertEqual(pathlib.Path(fonts.find_font('Trait Essai')[0]).name, 'essai.svg')

    def test_found_by_file_name(self):
        self.assertTrue(fonts.is_available('essai'))

    def test_ordinary_svg_ignored(self):
        self.assertFalse(fonts.is_available('dessin'))

    def test_listed_apart_from_plugin_fonts(self):
        self.assertEqual(fonts.svg_families(), ['Trait Essai'])
        self.assertNotIn('Trait Essai', fonts.plugin_families())

    def test_characters(self):
        self.assertEqual(set(fonts.characters('Trait Essai')), {' ', 'H', 'O', 'é'})

    def test_inventory_cache_keeps_svg_fonts(self):
        fonts.families()
        data = json.loads(fonts.cache_file().read_text(encoding='utf-8'))
        self.assertEqual(data['version'], fonts.CACHE_VERSION)
        self.assertEqual(list(data['svg']), ['Trait Essai'])
        fonts.SVG_FONTS.clear()
        fonts.families.cache_clear()
        self.assertEqual(fonts.svg_families(), ['Trait Essai'])

    def test_text_in_this_font(self):
        svgfonts.load.cache_clear()
        fonts.metrics.cache_clear()
        fonts.glyph.cache_clear()
        t = Text(text='HH', font='Trait Essai', size=7.0)
        o = TX.outline_for(t)
        self.assertEqual(len(o.contours), 6)
        self.assertTrue(all(not c.closed for c in o.contours))
        b = o.bbox()
        self.assertAlmostEqual(b[3] - b[1], 7.0, delta=1e-6)     # hauteur de capitales

    def test_kerning_in_text(self):
        svgfonts.load.cache_clear()
        fonts.metrics.cache_clear()
        fonts.glyph.cache_clear()
        with_kern = TX.outline_for(Text(text='HO', font='Trait Essai', size=7.0)).bbox()
        apart = TX.outline_for(Text(text='HH', font='Trait Essai', size=7.0)).bbox()
        self.assertLess(with_kern[2], apart[2])

    def test_written_to_vnd_as_curves(self):
        from vectordrive.core.document import Document, Layer
        from vectordrive.io import registry
        svgfonts.load.cache_clear()
        fonts.metrics.cache_clear()
        fonts.glyph.cache_clear()
        t = Text(text='HH', font='Trait Essai', size=7.0)
        p = os.path.join(self.cache, 'b.vnd')
        registry.save_document(Document(layers=[Layer(items=[t])]), p)
        back = vnd.read(p)
        self.assertTrue(any(L.items for L in back.layers))


class SavedThroughTheRegistry(unittest.TestCase):
    """Un texte jamais affiché : l'enregistrement (`registry.save_document`) calcule son contour avant d'écrire."""

    def _doc(self):
        from vectordrive.core.document import Document, Layer
        t = Text(text='HH', font='VD Trait', size=7.0)
        self.assertIsNone(t.outline)
        return Document(layers=[Layer(items=[t])])

    def test_vnd(self):
        from vectordrive.io import registry
        p = os.path.join(tempfile.mkdtemp(), 'b.vnd')
        registry.save_document(self._doc(), p)
        self.assertEqual(sum(len(L.items) for L in vnd.read(p).layers), 1)

    def test_svg(self):
        from vectordrive.io import registry
        p = os.path.join(tempfile.mkdtemp(), 'a.svg')
        registry.save_document(self._doc(), p)
        with open(p, encoding='utf-8') as fh:
            self.assertRegex(fh.read(), r'<path')

    def test_dxf(self):
        from vectordrive.io import dxf, registry
        p = os.path.join(tempfile.mkdtemp(), 'a.dxf')
        registry.save_document(self._doc(), p)
        self.assertTrue(any(L.items for L in dxf.read(p).layers))


class Command(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.close()

    def setUp(self):
        self.cache = tempfile.mkdtemp()
        self.src = tempfile.mkdtemp()
        env = mock.patch.dict(os.environ, {'VECTORDRIVE_CACHE': self.cache})
        env.start()
        self.addCleanup(env.stop)
        self.addCleanup(fonts.refresh)
        dirs = mock.patch.object(fonts, 'FONT_DIRS', [])
        dirs.start()
        self.addCleanup(dirs.stop)
        self.addCleanup(self.win.settings.remove, 'dossiers/police')
        fonts.refresh()

    def test_add(self):
        name = self.win.add_svg_font(write(self.src))
        self.assertEqual(name, 'Trait Essai')
        self.assertTrue((fonts.user_font_dir() / 'essai.svg').is_file())
        self.assertTrue(fonts.is_available('Trait Essai'))
        self.assertIn('4', self.win.statusBar().currentMessage())

    def test_original_stays(self):
        p = write(self.src)
        self.win.add_svg_font(p)
        self.assertTrue(os.path.isfile(p))

    def test_already_in_the_folder(self):
        folder = fonts.user_font_dir()
        folder.mkdir(parents=True)
        p = write(folder)
        self.assertEqual(self.win.add_svg_font(p), 'Trait Essai')

    def test_ordinary_svg_refused(self):
        p = write(self.src, 'dessin.svg', '<svg><path d="M0 0 L1 1"/></svg>')
        with mock.patch.object(QMessageBox, 'information') as info:
            self.assertIsNone(self.win.add_svg_font(p))
        info.assert_called_once()
        self.assertFalse((fonts.user_font_dir() / 'dessin.svg').exists())

    def test_broken_font_refused(self):
        p = write(self.src, 'casse.svg', '<svg><font><glyph')
        with mock.patch.object(QMessageBox, 'information') as info:
            self.assertIsNone(self.win.add_svg_font(p))
        info.assert_called_once()

    def test_cancelled(self):
        from vectordrive.ui import main_window as MW
        with mock.patch.object(MW.QFileDialog, 'getOpenFileName', return_value=('', '')):
            self.assertIsNone(self.win.add_svg_font())

    def test_ribbon(self):
        found = [b for i in range(self.win.ribbon.count()) for g in self.win.ribbon.page(i).groups() for b in g.buttons()
                 if b.defaultAction() is self.win.A['add_svg_font']]
        self.assertEqual(len(found), 1)

    def test_font_list_offers_it(self):
        from vectordrive.ui.dialogs import FontBox
        self.win.add_svg_font(write(self.src))
        combo = FontBox()
        self.assertGreaterEqual(combo.findText('Trait Essai'), 0)


if __name__ == '__main__':
    unittest.main()
