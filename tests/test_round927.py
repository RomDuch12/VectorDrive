"""Round 927 : défauts trouvés en relisant les rounds 922 à 926 — l'outil Texte et la souris, le curseur quand le
texte change sans la frappe, la saisie close au changement d'onglet de dessin, le pas d'annulation d'un texte écrit
puis effacé, le focus des champs de Mise en forme, la largeur imposée remise à libre, l'onglet d'avant Mise en forme,
les lecteurs de polices des plugins en défaut et le cache des polices."""
import math
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r927.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ.setdefault('VECTORDRIVE_CACHE', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from vectordrive.core import fonts  # noqa: E402
from vectordrive.core import text as TX  # noqa: E402
from vectordrive.core.document import Text  # noqa: E402
from vectordrive.core.geom import Contour, Line, Path  # noqa: E402

FONT = 'VD Trait'


def key(k, text='', mods=Qt.KeyboardModifier.NoModifier):
    return QKeyEvent(QEvent.Type.KeyPress, k, mods, text)


class Typing(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui import text_presets as TP
        cls.TP = TP
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.finish_typing()
        cls.w.modified = False
        for t in cls.w.docs:
            t.modified = False
        cls.w.close()

    def setUp(self):
        w = self.w
        w.set_tool('select')
        w.modified = False
        w.new_document()
        w._undo.clear()
        self.TP.set_new_text_format(w.settings, {'attrs': {'font': FONT, 'size': 4.0}, 'extra': {}}, '')
        w.next_text_fit = None
        window = mock.patch('vectordrive.ui.dialogs.TextDialog.exec', return_value=0)
        window.start()
        self.addCleanup(window.stop)

    def texts(self, doc=None):
        doc = doc or self.w.canvas.doc
        return [it for L in doc.layers for it in L.items if isinstance(it, Text)]

    def typing(self, s='', at=(10.0, 10.0)):
        self.w.new_text(*at)
        tool = self.w.canvas.tool_obj
        if s:
            tool.insert(s)
        return tool

    def index(self, title):
        r = self.w.ribbon
        return next(i for i in range(r.count()) if r.tabText(i) == title)

    # --- l'outil Texte et la souris ----------------------------------------------------------------------------
    def test_mouse_moves_over_the_drawing_with_the_text_tool(self):
        tool = self.typing('Ab')
        tool.move(QPointF(40.0, 30.0), (12.0, 8.0), None)          # le mouvement de souris de tous les outils
        self.assertEqual(tool.caret, 2)
        self.assertTrue(tool.key(key(Qt.Key.Key_Left)))
        self.assertTrue(tool.key(key(Qt.Key.Key_X, 'x')))
        self.assertEqual(tool.source(), 'Axb')

    # --- le curseur quand le texte change sans la frappe ---------------------------------------------------------
    def test_caret_follows_a_text_shortened_elsewhere(self):
        tool = self.typing('Bonjour monde')
        tool.item.text = 'Bonjour'                                  # Rechercher / remplacer pendant la saisie
        tool.erase(-1)
        self.assertEqual(tool.source(), 'Bonjou')
        tool.insert('r!')
        self.assertEqual(tool.source(), 'Bonjour!')
        tool.item.text = 'Ok'
        tool.key(key(Qt.Key.Key_Left))
        tool.insert('-')
        self.assertEqual(tool.source(), 'O-k')

    # --- touches -----------------------------------------------------------------------------------------------
    def test_non_breaking_spaces_and_shift_tab_are_typed(self):
        tool = self.typing('a')
        for ch in ('\xa0', ' '):
            ev = key(Qt.Key.Key_Space, ch)
            self.assertTrue(tool.wants_key(ev), repr(ch))
            self.assertTrue(tool.key(ev))
        ev = key(Qt.Key.Key_Backtab, '', Qt.KeyboardModifier.ShiftModifier)
        self.assertTrue(tool.wants_key(ev))                         # le focus ne quitte pas le dessin
        self.assertTrue(tool.key(ev))
        self.assertEqual(tool.source(), 'a\xa0 ' + TX.SPRING)

    # --- saisie close au changement d'onglet de dessin ------------------------------------------------------------
    def test_switching_drawing_tab_finishes_the_text(self):
        w = self.w
        self.typing('X').finish()
        tool = self.typing('A')
        tool.erase(-1)                                              # vidé : il s'en va à la fin de la saisie
        doc, first = w.canvas.doc, w.doc_index
        w.new_document()
        self.assertNotEqual(w.doc_index, first)
        self.assertEqual([t.text for t in self.texts(doc)], ['X'])
        self.typing('B')
        doc2 = w.canvas.doc
        w.switch_tab(first)
        self.assertIsNone(w.typing_tool())
        self.assertEqual([t.text for t in self.texts(doc2)], ['B'])
        self.assertEqual([t.text for t in self.texts(doc)], ['X'])

    def test_closing_a_tab_finishes_the_text(self):
        w = self.w
        self.typing('X').finish()
        a = w.doc_index
        w.new_document()
        b = w.doc_index
        w.switch_tab(a)
        tool = self.typing('Y')
        tool.erase(-1)
        doc = w.canvas.doc
        self.assertTrue(w.close_tab(b))
        self.assertIsNone(w.typing_tool())
        self.assertEqual([t.text for t in self.texts(doc)], ['X'])

    # --- annulation ----------------------------------------------------------------------------------------------
    def test_text_typed_then_erased_leaves_no_undo_step(self):
        w = self.w
        before = len(w._undo)
        tool = self.typing('a')
        self.assertEqual(len(w._undo), before + 1)
        tool.erase(-1)
        tool.finish()
        self.assertEqual(self.texts(), [])
        self.assertEqual(len(w._undo), before)
        self.assertFalse(w.modified)
        tool = self.typing('ab')                                    # gardé : son pas reste
        tool.finish()
        self.assertEqual(len(w._undo), before + 1)
        t, = self.texts()
        w.type_in_text(t)                                           # repris puis effacé : ça s'annule
        tool = w.canvas.tool_obj
        tool.erase(-1)
        tool.erase(-1)
        tool.finish()
        self.assertEqual(self.texts(), [])
        self.assertEqual(len(w._undo), before + 2)
        w.undo()
        self.assertEqual([x.text for x in self.texts()], ['ab'])

    # --- focus des champs de Mise en forme -----------------------------------------------------------------------
    def test_field_validated_by_clicking_another_field_keeps_it(self):
        w = self.w
        w.resize(3000, 1000)                                        # tout le formulaire à l'écran
        w.show()
        w.activateWindow()
        self.addCleanup(w.hide)
        app.processEvents()
        self.typing('A')
        tb = w.textbar
        r = w.ribbon
        r.setCurrentIndex(self.index(w.text_tab_title))
        for _ in range(3):
            app.processEvents()
        r.fit_current()
        app.processEvents()
        tb.size.setFocus()
        app.processEvents()
        if QApplication.focusWidget() is not tb.size:
            self.skipTest('pas de focus clavier sur cette plateforme')
        tb.size.lineEdit().selectAll()
        tb.size.lineEdit().insert('6')
        tb.width.setFocus()                                         # clic dans Largeur : Hauteur est validée
        app.processEvents()
        self.assertAlmostEqual(w.typing_tool().item.size, 6.0)
        self.assertIs(QApplication.focusWidget(), tb.width)
        tb.width.lineEdit().selectAll()
        tb.width.lineEdit().insert('90')
        from PySide6.QtTest import QTest
        QTest.keyClick(tb.width, Qt.Key.Key_Return)                 # Entrée : la frappe revient au dessin
        app.processEvents()
        self.assertIs(QApplication.focusWidget(), w.canvas)
        self.assertAlmostEqual(w.typing_tool().item.width_ratio, 0.9)

    # --- largeur imposée remise à libre -----------------------------------------------------------------------
    def test_free_width_gives_the_font_back(self):
        w = self.w
        tool = self.typing('A')
        tool.finish()
        t, = self.texts()
        w.canvas.select([t])
        w.textbar.set_fit(30.0, 'spacing')
        self.assertNotAlmostEqual(t.width_ratio, 1.0)              # une lettre seule s'étire
        w.textbar.set_fit(0.0)
        self.assertEqual((t.spacing, t.width_ratio), (0.0, 1.0))

    def test_free_width_keeps_spacing_with_springs(self):
        w = self.w
        tool = self.typing('A' + TX.SPRING + 'B')
        tool.finish()
        t, = self.texts()
        w.canvas.select([t])
        t.spacing = 0.5
        w.textbar.set_fit(40.0, 'spacing')
        self.assertAlmostEqual(t.spacing, 0.5)                      # les ressorts prennent la largeur
        w.textbar.set_fit(0.0)
        self.assertAlmostEqual(t.spacing, 0.5)

    # --- l'onglet d'avant Mise en forme ---------------------------------------------------------------------
    def test_back_to_the_tab_mise_en_forme_was_opened_from(self):
        w, r = self.w, self.w.ribbon
        tab = self.index(w.text_tab_title)
        others = [i for i in range(r.count()) if i != tab and r.isTabVisible(i)]
        a, b = others[1], others[2]
        r.setCurrentIndex(a)
        tool = self.typing('ab')                                    # l'outil Texte depuis l'onglet a
        self.assertEqual(r.currentIndex(), tab)
        tool.finish()
        w.set_tool('select')
        t, = self.texts()
        self.assertTrue(r.isTabVisible(tab))                        # le texte reste sélectionné
        r.setCurrentIndex(b)
        w.canvas.select([])
        w._on_selection()
        self.assertFalse(r.isTabVisible(tab))
        w.canvas.select([t])
        w._on_selection()
        r.setCurrentIndex(tab)                                      # ouverte à la main depuis l'onglet b
        w.canvas.select([])
        w._on_selection()
        self.assertEqual(r.currentIndex(), b)


def write_font(d, stem, ext):
    p = pathlib.Path(d) / f'{stem}{ext}'
    p.write_bytes(b'TRAIT927\n' + stem.encode('utf-8'))
    return p


def font_name(path):
    b = pathlib.Path(path).read_bytes()
    return 'Casse ' + b[9:].decode('utf-8') if b.startswith(b'TRAIT927\n') else None


def good_glyph(ch):
    return Path([Contour([Line((0.0, 0.0), (0.5, 1.0)), Line((0.5, 1.0), (1.0, 0.0))])]), 1.0


class PluginReaders(unittest.TestCase):

    def setUp(self):
        from vectordrive import plugins
        from vectordrive.core import fontformats
        self.ff, self.plugins = fontformats, plugins
        self.dir = tempfile.mkdtemp()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        for fmt in self.ff.registered():
            if fmt.extensions[0].endswith('927'):
                self.ff.unregister(fmt)
        self.plugins.REGISTRY.font_formats[:] = [f for f in self.plugins.REGISTRY.font_formats
                                                 if not f[1][0].endswith('927')]
        if pathlib.Path(self.dir) in fonts.FONT_DIRS:
            fonts.FONT_DIRS.remove(pathlib.Path(self.dir))

    def api(self, version='1.0'):
        return self.plugins.Api(self.plugins.REGISTRY, self.plugins.PluginInfo('essai927', 'Essai 927', version))

    def test_a_failing_reader_does_not_break_the_layout(self):
        def glyph(path, ch):
            if ch == 'B':
                raise ValueError('glyphe abîmé')
            if ch == 'C':
                return Path([Contour([Line((0.0, 0.0), (math.nan, 1.0))])]), 1.0
            if ch == 'D':
                return Path(), math.inf
            return good_glyph(ch)

        def kerning(path, a, b):
            if (a, b) == ('A', 'E'):
                raise ValueError('crénage abîmé')
            return math.nan

        write_font(self.dir, 'glyphes', '.g927')
        self.api().add_font_format('Essai 927', ('.g927',), font_name=font_name, glyph=glyph, kerning=kerning,
                                   metrics=lambda p: {'upem': 1.0, 'ascent': 1.25, 'descent': 0.75, 'cap': 1.0},
                                   dirs=[self.dir])
        path = TX.layout('ABCDAE', 'Casse glyphes', 10)
        self.assertEqual(len(path.contours), 3)                     # A, A, E ; B, C, D vides
        x0, _y0, x1, _y1 = path.bbox()
        self.assertTrue(all(math.isfinite(v) for v in path.bbox()))
        self.assertGreater(x1 - x0, 20)

    def test_failing_metrics_fall_back(self):
        def metrics(path):
            raise OSError('lecture impossible')

        write_font(self.dir, 'mesures', '.m927')
        self.api().add_font_format('Essai 927 m', ('.m927',), font_name=font_name, metrics=metrics,
                                   glyph=lambda p, ch: good_glyph(ch), dirs=[self.dir])
        path = TX.layout('AA', 'Casse mesures', 10)
        _x0, y0, _x1, y1 = path.bbox()
        self.assertAlmostEqual(y1 - y0, 10.0, places=3)              # hauteur 1 : la hauteur de capitales demandée
        bad = {'upem': math.nan, 'ascent': 1, 'descent': 1, 'cap': 1}
        fmt = self.ff.of(write_font(self.dir, 'autre', '.m927'))
        fmt.metrics = lambda p: bad
        self.assertEqual(self.ff.read_metrics(fmt, 'x.m927')['upem'], 1.0)

    def test_font_inventory_follows_the_reader_version(self):
        write_font(self.dir, 'version', '.v927')
        kw = dict(font_name=font_name, glyph=lambda p, ch: good_glyph(ch),
                  metrics=lambda p: {'upem': 1.0, 'ascent': 1.25, 'descent': 0.75, 'cap': 1.0}, dirs=[self.dir])
        self.api('1.0').add_font_format('Essai 927 v', ('.v927',), **kw)
        sig1 = fonts._signature()
        self.ff.unregister(self.ff.of('x.v927'))
        self.api('1.1').add_font_format('Essai 927 v', ('.v927',), **kw)
        self.assertNotEqual(fonts._signature(), sig1)               # plugin mis à jour : inventaire refait


if __name__ == '__main__':
    unittest.main()
