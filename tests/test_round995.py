"""Round 995 : reconnaissance de police, retour de l'atelier — « moteur de reconnaissance de la sélection (avec 5
propositions par défaut, réglable user) ». Les lettres en courbes sélectionnées sont comparées aux polices du poste ; la
liste des polices montre les plus proches en tête (« Reconnaître la sélection »), leur nombre est réglable."""
import math
import os
import pathlib
import shutil
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from vectordrive import portable  # noqa: E402
from vectordrive.core import fontmatch as FM  # noqa: E402
from vectordrive.core import fonts as F  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core import text as TX  # noqa: E402
from vectordrive.core.document import Layer, Shape, Text  # noqa: E402
from vectordrive.core.geom import Affine, Contour, Line, Path  # noqa: E402

app = QApplication.instance() or QApplication([])
STYLES = {'Essai Carre 995': 'carre', 'Essai Rond 995': 'rond', 'Essai Barres 995': 'barres'}
NAMES = list(STYLES) + ['VD Trait', 'VD Géo']
TWIN = 'Essai Carre Bis 995'
SAMPLE = 'ABC abc 123'


def cache_file(name):
    path, index = F.find_font(name)
    return path, index, FM.cache_dir() / (FM._key(path, index) + '.npz')


def make_font(path: pathlib.Path, family: str, style: str) -> None:
    """Police TrueType d'essai : toutes les lettres de `FM.CHARS` dans un même style (cadres, octogones évidés ou
    peignes), leur largeur variant d'une lettre à l'autre."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    def poly(p, pts):
        p.moveTo(pts[0])
        for q in pts[1:]:
            p.lineTo(q)
        p.closePath()

    def glyph(i, ch):
        p = TTGlyphPen(None)
        w = 420 + 60 * (i % 4)
        h = 700 if (ch.isupper() or ch.isdigit()) else 500
        if style == 'carre':
            poly(p, [(50, 0), (50, h), (w - 50, h), (w - 50, 0)])
            poly(p, [(160, 110), (w - 160, 110), (w - 160, h - 110), (160, h - 110)])
        elif style == 'rond':
            cx, cy, rx, ry = w / 2, h / 2, w / 2 - 50, h / 2
            out = [(round(cx + rx * math.cos(a)), round(cy + ry * math.sin(a)))
                   for a in (k * math.pi / 4 + math.pi / 8 for k in range(8))]
            poly(p, out[::-1])
            inner = [(round(cx + (rx - 90) * math.cos(a)), round(cy + (ry - 90) * math.sin(a)))
                     for a in (k * math.pi / 4 + math.pi / 8 for k in range(8))]
            poly(p, inner)
        else:                                         # peigne d'un seul tenant : deux ou trois dents sur une barre
            n = 2 + i % 2
            xs = [round(50 + k * (w - 170) / (n - 1)) for k in range(n)]
            pts = [(50, 0), (w - 50, 0), (w - 50, h), (xs[-1], h), (xs[-1], 80)]
            for k in range(n - 2, -1, -1):
                pts += [(xs[k] + 70, 80), (xs[k] + 70, h), (xs[k], h)]
                if k:
                    pts.append((xs[k], 80))
            poly(p, pts[::-1])
        return p.glyph(), w

    names = ['.notdef', 'space']
    glyf = {'.notdef': TTGlyphPen(None).glyph(), 'space': TTGlyphPen(None).glyph()}
    hmtx = {'.notdef': (500, 0), 'space': (300, 0)}
    cmap = {0x20: 'space'}
    for i, ch in enumerate(FM.CHARS):
        g = f'g{i}'
        names.append(g)
        glyf[g], w = glyph(i, ch)
        hmtx[g] = (w, 0)
        cmap[ord(ch)] = g
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(names)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyf)
    fb.setupHorizontalMetrics(hmtx)
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({'familyName': family, 'styleName': 'Regular'})
    fb.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200, sCapHeight=700)
    fb.setupPost()
    fb.save(str(path))


DIR = None


def setUpModule():
    global DIR
    DIR = pathlib.Path(tempfile.mkdtemp(prefix='polices995_'))
    for i, (family, style) in enumerate(STYLES.items()):
        make_font(DIR / f'essai995_{i}.ttf', family, style)
    make_font(DIR / 'essai995_bis.ttf', TWIN, 'carre')                   # même dessin qu'« Essai Carre 995 »
    F.add_font_dir(DIR)


def tearDownModule():
    if DIR in F.FONT_DIRS:
        F.FONT_DIRS.remove(DIR)
    F.families.cache_clear()
    shutil.rmtree(DIR, ignore_errors=True)


def outline(s, font, size=8.0, x=10.0, y=20.0):
    t = Text(text=s, font=font, size=size, matrix=Affine.translation(x, y))
    return TX.outline_for(t)


def forget():
    s = portable.settings()
    for k in ('polices/favorites', 'polices/filtre', 'polices/propositions'):
        s.remove(k)
    s.sync()


class Letters(unittest.TestCase):

    def test_holes_dots_and_punctuation(self):
        i_stem, i_dot = geom.rect(0, 0, 2, 10), geom.rect(0, 12, 2, 2)
        o_out, o_in = geom.rect(4, 0, 6, 10), geom.rect(6, 2, 2, 6)
        period, ell = geom.rect(12, 0, 1, 1), geom.rect(15, 0, 2, 14)
        got = FM.letters([Path([ell, o_in, i_dot, period, o_out, i_stem])])
        self.assertEqual([len(p) for p, _b in got], [2, 2, 1])           # i (et son point), o (et son trou), l
        self.assertEqual([round(b[0]) for _p, b in got], [0, 4, 15])

    def test_image_even_odd_and_strokes(self):
        ring = FM.image([(geom.rect(0, 0, 10, 10).flatten(0.01), True), (geom.rect(3, 3, 4, 4).flatten(0.01), True)])
        c = FM.R // 2
        self.assertLess(float(ring[c, c]), 0.05)                          # le trou reste vide
        self.assertGreater(float(ring[c, 1]), 0.5)
        stroke = Contour([Line((0.0, 0.0), (0.0, 10.0))], False)          # trait ouvert d'une police monotrait
        im = FM.image([(stroke.flatten(0.01), False)])
        self.assertGreater(float(im[:, c].max()), 0.3)
        self.assertLess(float(im[:, 1].max()), 0.05)


    def test_frame_underline_and_far_object_left_out(self):
        p = outline(SAMPLE, 'Essai Carre 995')
        x0, y0, x1, y1 = p.bbox()
        base = [b for _p, b in FM.letters([p])]
        self.assertEqual(len(base), 9)
        h = y1 - y0
        frame = geom.rect(x0 - 3, y0 - 3, x1 - x0 + 6, y1 - y0 + 6)        # le cadre d'une plaque
        under = geom.rect(x0, y0 - 0.15 * h - 0.5, x1 - x0, 0.3 * h)       # un soulignement épais
        far = geom.rect(x0 + 1000, y0, 2, 2)                                # un petit objet à un mètre
        got = [b for _p, b in FM.letters([p, Path([frame, under])])]
        self.assertEqual(got, base)                                         # avant : une seule « lettre »
        got = [b for _p, b in FM.letters([p, Path([far])])]
        self.assertEqual(got[:9], base)                                     # avant : des lettres réunies
        self.assertEqual(len(got), 10)

    def test_empty_contour_and_nearly_closed_polyline(self):
        p = outline(SAMPLE, 'Essai Carre 995')
        self.assertEqual(len(FM.letters([Path(list(p.contours) + [Contour([], False)])])), 9)   # avant : erreur
        sq = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.02)]   # polyligne DXF non fermée
        opened = Contour([Line(a, b) for a, b in zip(sq, sq[1:])], False)
        im = FM.image([(opened.flatten(0.01), FM._is_closed(opened.flatten(0.01), False))])
        self.assertGreater(float(im[FM.R // 2, FM.R // 2]), 0.9)            # remplie, pas un trait fin

    def test_fonts_filled_non_zero(self):
        a, b = geom.rect(0, 0, 10, 10), geom.rect(5, 0, 10, 10)            # deux contours qui se chevauchent
        polys = [(a.flatten(0.01), True), (b.flatten(0.01), True)]
        c = FM.R // 2
        self.assertLess(float(FM.image(polys)[c, c]), 0.1)                  # pair-impair : le chevauchement vide
        self.assertGreater(float(FM.image(polys, nonzero=True)[c, c]), 0.9)
        self.assertGreater(float(FM.path_image(Path([a, b]))[c, c]), 0.9)   # une police : non nul


class Ranking(unittest.TestCase):

    def test_damaged_shapes_file_redone(self):
        FM.rank([outline(SAMPLE, 'Essai Barres 995')], ['Essai Barres 995'])
        _p, _i, f = cache_file('Essai Barres 995')
        self.assertTrue(f.exists())
        f.write_bytes(b'')                                                  # coupure pendant l'écriture
        FM._MEM.clear()
        self.assertEqual(FM.rank([outline(SAMPLE, 'Essai Barres 995')], NAMES)[0][0], 'Essai Barres 995')
        import numpy as np
        with np.load(f) as z:                                               # refait
            self.assertTrue(str(z['chars']))

    def test_unreadable_for_now_not_kept(self):
        path, index, f = cache_file('Essai Rond 995')
        f.unlink(missing_ok=True)
        FM._MEM.clear()
        with mock.patch.object(FM, '_glyphs', side_effect=PermissionError('tenu par un autre programme')):
            self.assertIsNone(FM.table(path, index))
        self.assertFalse(f.exists())
        self.assertIsNotNone(FM.table(path, index))                         # avant : vide pour toujours

    def test_same_drawing_proposed_once(self):
        got = [n for n, _p in FM.rank([outline(SAMPLE, 'Essai Carre 995')], ['Essai Carre 995', TWIN, 'VD Trait'],
                                      count=3)]
        self.assertEqual(got, ['Essai Carre 995', 'VD Trait'])

    def test_display_cache_untouched_shapes_kept_small(self):
        path, index, f = cache_file('VD Trait')
        f.unlink(missing_ok=True)
        FM._MEM.clear()
        F.glyph.cache_clear()
        self.assertIsNotNone(FM.table(path, index))
        self.assertEqual(F.glyph.cache_info().currsize, 0)                  # avant : 70 lettres de plus
        self.assertTrue(all(v[1].dtype.name == 'uint8' for v in FM._MEM.values()))

    def test_each_font_found_first(self):
        for name in NAMES:
            got = FM.rank([outline(SAMPLE, name)], NAMES)
            self.assertEqual(got[0][0], name, got)
            self.assertGreater(got[0][1], 0.9)                             # mêmes lettres : très proche

    def test_moved_and_enlarged_curves(self):
        p = outline(SAMPLE, 'Essai Rond 995').transformed(Affine.translation(300, -40) @ Affine.scaling(3.0))
        self.assertEqual(FM.rank([Shape(path=p).path], NAMES)[0][0], 'Essai Rond 995')

    def test_count_and_order(self):
        got = FM.rank([outline(SAMPLE, 'Essai Carre 995')], NAMES, count=2)
        self.assertEqual(len(got), 2)
        self.assertGreaterEqual(got[0][1], got[1][1])
        self.assertEqual(len(FM.rank([outline(SAMPLE, 'Essai Carre 995')], NAMES)), FM.DEFAULT_COUNT)

    def test_nothing_or_cancelled(self):
        self.assertEqual(FM.rank([], NAMES), [])
        self.assertEqual(FM.rank([outline(SAMPLE, 'VD Trait')], NAMES, cancel=lambda: True), [])
        self.assertEqual(FM.rank([outline(SAMPLE, 'VD Trait')], ['Police absente 995']), [])

    def test_shapes_kept_on_disk_and_redone_when_the_font_changes(self):
        FM.rank([outline(SAMPLE, 'Essai Barres 995')], NAMES)
        self.assertTrue(list(FM.cache_dir().glob('*.npz')))
        FM._MEM.clear()
        with mock.patch.object(FM, 'path_image', side_effect=AssertionError('relevée de nouveau')):
            self.assertEqual(FM.rank([outline(SAMPLE, 'Essai Barres 995')], NAMES)[0][0], 'Essai Barres 995')
        f = DIR / 'essai995_2.ttf'
        st = f.stat()
        os.utime(f, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
        FM._MEM.clear()
        with mock.patch.object(FM, 'path_image', wraps=FM.path_image) as seen:
            FM.rank([outline(SAMPLE, 'Essai Barres 995')], ['Essai Barres 995'])
        self.assertTrue(seen.called)


class InTheFontList(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        forget()
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()
        cls.w.deleteLater()
        forget()

    def setUp(self):
        from vectordrive.ui import fontlist
        forget()
        fontlist.set_favorites(NAMES)
        doc = self.w.canvas.doc
        self.layer = Layer(name='Plan 1')
        doc.layers[:] = [self.layer]
        doc.active = self.layer.id
        self.curves = Shape(path=outline(SAMPLE, 'Essai Rond 995'))
        self.other = Shape(path=outline(SAMPLE, 'Essai Carre 995', y=60))
        self.layer.items[:] = [self.curves, self.other]
        self.box = self.w.textbar.font
        self.addCleanup(self.box.hidePopup)

    def popup(self):
        self.box.showPopup()
        app.processEvents()
        pop = self.box._popup
        pop.filter_buttons['favorites'].click()
        return pop

    def run_it(self, pop):
        pop.recognize()
        if pop._thread is not None:
            pop._thread.join(120)
        for _ in range(5):
            app.processEvents()

    def test_recognize_the_selected_curves(self):
        self.w.canvas.select([self.curves])
        pop = self.popup()
        self.assertEqual(pop.count_box.value(), 5)                        # 5 d'office
        pop.count_box.setValue(3)
        self.assertEqual(int(portable.settings().value('polices/propositions')), 3)
        self.run_it(pop)
        self.assertEqual([n for n, _p in pop.proposals][:1], ['Essai Rond 995'])
        self.assertEqual(len(pop.proposals), 3)
        self.assertEqual(pop.list.item(0).text(), 'Proches de la sélection')
        self.assertEqual(pop.shown()[0], 'Essai Rond 995')
        self.assertIsNotNone(pop.list.item(1).data(Qt.ItemDataRole.UserRole + 2))
        QTest.keyClick(pop.search, Qt.Key.Key_Return)                    # la première proposée, choisie
        app.processEvents()
        self.assertEqual(self.box.currentText(), 'Essai Rond 995')

    def test_another_selection_drops_the_proposals(self):
        self.w.canvas.select([self.curves])
        pop = self.popup()
        self.run_it(pop)
        self.assertTrue(pop.proposals)
        self.box.hidePopup()
        self.box.showPopup()                                              # même sélection : gardées
        self.assertTrue(pop.proposals)
        self.box.hidePopup()
        self.w.canvas.select([self.other])
        self.box.showPopup()
        self.assertEqual(pop.proposals, [])

    def test_nothing_selected(self):
        self.w.canvas.select([])
        pop = self.popup()
        pop._thread = None
        pop.recognize()
        self.assertIsNone(pop._thread)
        self.assertIn('Sélectionnez', pop.status.text())

    def test_a_result_left_behind_is_ignored(self):
        self.w.canvas.select([self.curves])
        pop = self.popup()
        pop.stop()
        pop._done(object(), [('VD Trait', 1.0)])
        self.assertEqual(pop.proposals, [])

    def blocked(self):
        import threading
        ev = threading.Event()
        self.addCleanup(ev.set)
        p = mock.patch.object(FM, 'rank', side_effect=lambda *a, **k: (ev.wait(30), [('VD Trait', 1.0)])[1])
        p.start()
        self.addCleanup(p.stop)
        return ev

    def finish(self, pop, ev):
        ev.set()
        if pop._thread is not None:
            pop._thread.join(30)
        for _ in range(5):
            app.processEvents()

    def test_stop_button(self):
        self.w.canvas.select([self.curves])
        pop = self.popup()
        ev = self.blocked()
        pop.recognize()
        self.assertEqual(pop.recognize_button.text(), 'Arrêter')           # avant : grisé, rien pour arrêter
        pop.recognize_button.click()
        self.assertIn('arrêtée', pop.status.text())
        self.finish(pop, ev)
        self.assertEqual(pop.proposals, [])
        self.assertEqual(pop.recognize_button.text(), 'Reconnaître la sélection')

    def test_reopened_on_another_selection_stops(self):
        self.w.canvas.select([self.curves])
        pop = self.popup()
        ev = self.blocked()
        pop.recognize()
        self.box.hidePopup()
        self.w.canvas.select([self.other])
        self.box.showPopup()
        self.finish(pop, ev)
        self.assertEqual(pop.proposals, [])                                 # avant : le résultat de l'autre sélection

    def test_no_font_in_the_filter(self):
        from vectordrive.ui import fontlist
        self.w.canvas.select([self.curves])
        fontlist.set_favorites([])
        pop = self.popup()
        pop.recognize()
        self.assertIsNone(pop._token)
        self.assertIn('Aucune police à comparer', pop.status.text())       # avant : « aucune lettre reconnue »

    def test_count_in_the_options(self):
        from vectordrive.ui import options
        opt = next(o for _t, opts in options.SPEC for o in opts if o.key == 'polices/propositions')
        self.assertEqual((opt.default, opt.lo, opt.hi), (5, 1, 50))


if __name__ == '__main__':
    unittest.main()
