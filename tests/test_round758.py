"""Round 758 : BAT : coloriage pair-impair dans la couleur des contours, précision des cotes réglable, thème de couleur,
logos dessinés et second logo."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtGui import QColor, QImage, QPainter, QTransform
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape, Tool
from vectordrive.io import proof

app = QApplication.instance() or QApplication([])
RED, BLUE = '#c00000', '#0000c0'
R, B = proof._rgb(RED), proof._rgb(BLUE)


def doc_of(*items):
    d = Document()
    d.plate = Plate(100, 80)
    d.tools = [Tool(index=1, name='Rouge', color=RED), Tool(index=2, name='Bleu', color=BLUE)]
    d.layers = [Layer(name='A', items=list(items))]
    return d


def square(cx, cy, side, tool=1):
    return Shape(path=geom.Path([geom.rect(cx - side / 2, cy - side / 2, side, side)]), tool=tool)


def info(**k):
    base = dict(fill=True, title_block=False, dims=False, legend=False, dims_each=False, prices=False,
                scale_mode='reelle')
    base.update(k)
    return proof.ProofInfo(**base)


def raster(prims, PW, PH, k=4.0):
    img = QImage(int(PW * k), int(PH * k), QImage.Format.Format_RGB32)
    img.fill(0xFFFFFFFF)
    p = QPainter(img)
    from vectordrive.ui.printing import paint_prims
    paint_prims(p, prims, QTransform(k, 0, 0, -k, 0, PH * k))
    p.end()
    return img, k


class Pixels:
    """La page peinte : la couleur d'un point du dessin, en coordonnées du dessin."""

    def __init__(self, doc, inf):
        self.prims, self.PW, self.PH = proof.build(doc, inf)
        self.img, self.k = raster(self.prims, self.PW, self.PH)
        g = proof._geometry(doc, inf)
        v = g['views'][0]
        ax0, ay0, ax1, ay1 = v['area']
        self.ox = ax0 + (ax1 - ax0 - g['FW'] * v['k']) / 2 - g['frame'][0] * v['k']
        self.oy = ay0 + (ay1 - ay0 - g['FH'] * v['k']) / 2 - g['frame'][1] * v['k']
        self.kv = v['k']

    def at(self, x, y):
        px = (self.ox + x * self.kv) * self.k
        py = (self.PH - (self.oy + y * self.kv)) * self.k
        c = QColor(self.img.pixel(int(px), int(py)))
        return c.red(), c.green(), c.blue()


def is_col(rgb, col):
    return all(abs(a - b * 255) < 40 for a, b in zip(rgb, col))


WHITE = (1, 1, 1)


class TestRegions(unittest.TestCase):
    def regions(self, *spec):
        return proof.even_odd_regions([(geom.rect(x, y, s, s), col) for x, y, s, col in spec])

    def test_alone(self):
        got = self.regions((0, 0, 10, R))
        self.assertEqual(len(got), 1)
        self.assertEqual(len(got[0][0].contours), 1)
        self.assertEqual(got[0][1], R)

    def test_hole(self):
        got = self.regions((0, 0, 30, R), (10, 10, 10, R))
        self.assertEqual(len(got), 1)                                         # un plein, avec son trou
        self.assertEqual(len(got[0][0].contours), 2)

    def test_island_in_a_hole(self):
        got = self.regions((0, 0, 30, R), (5, 5, 20, R), (10, 10, 10, R))
        self.assertEqual(len(got), 2)
        self.assertEqual([len(p.contours) for p, _c in got], [2, 1])

    def test_each_full_takes_its_colour(self):
        got = self.regions((0, 0, 30, R), (5, 5, 20, B), (10, 10, 10, B))
        self.assertEqual([c for _p, c in got], [R, B])
        self.assertEqual(len(got[0][0].contours), 2)                          # le contour bleu est bien un trou du rouge

    def test_side_by_side(self):
        got = self.regions((0, 0, 10, R), (20, 0, 10, B))
        self.assertEqual(len(got), 2)

    def test_two_holes(self):
        got = self.regions((0, 0, 30, R), (2, 2, 5, R), (20, 20, 5, R))
        self.assertEqual(len(got), 1)
        self.assertEqual(len(got[0][0].contours), 3)

    def test_same_contour_twice_stays_full(self):
        got = self.regions((0, 0, 10, R), (0, 0, 10, R))                      # tracé doublé : un accident, pas un trou
        self.assertTrue(got)
        self.assertTrue(all(len(p.contours) == 1 for p, _c in got))           # la pièce ne disparaît pas de l'épreuve

    def test_order_does_not_matter(self):
        a = self.regions((10, 10, 10, R), (0, 0, 30, R))
        self.assertEqual(len(a), 1)
        self.assertEqual(len(a[0][0].contours), 2)

    def test_too_many_falls_back(self):
        with mock.patch.object(proof, 'MAX_REGION_CONTOURS', 2):
            got = self.regions((0, 0, 10, R), (20, 0, 10, B), (40, 0, 10, R))
        self.assertEqual(len(got), 2)                                         # un chemin par couleur

    def test_degenerate_skipped(self):
        c = geom.polyline([(0, 0), (1, 1)], closed=True)
        self.assertEqual(len(proof.even_odd_regions([(geom.rect(0, 0, 5, 5), R), (c, R)])), 1)


class TestPage(unittest.TestCase):
    def test_default_mode(self):
        self.assertEqual(proof.ProofInfo().fill_mode, 'contour')

    def test_ring_is_painted_in_its_colour(self):
        px = Pixels(doc_of(square(50, 40, 40), square(50, 40, 20)), info())
        self.assertTrue(is_col(px.at(35, 40), R))                             # l'anneau : plein, rouge
        self.assertTrue(is_col(px.at(50, 40), WHITE))                         # le trou : vide
        self.assertTrue(is_col(px.at(10, 10), WHITE))

    def test_island(self):
        px = Pixels(doc_of(square(50, 40, 60), square(50, 40, 40), square(50, 40, 20, tool=2)), info())
        self.assertTrue(is_col(px.at(25, 40), R))
        self.assertTrue(is_col(px.at(35, 40), WHITE))
        self.assertTrue(is_col(px.at(50, 40), B))                             # l'îlot : la couleur de son contour

    def test_across_objects(self):
        one = square(50, 40, 40)
        two = square(50, 40, 20, tool=2)                                      # deux objets, deux outils : un trou quand même
        px = Pixels(doc_of(one, two), info())
        self.assertTrue(is_col(px.at(50, 40), WHITE))
        self.assertTrue(is_col(px.at(35, 40), R))

    def test_open_lines_not_filled(self):
        line = Shape(path=geom.Path([geom.polyline([(20, 20), (80, 20), (80, 60)], closed=False)]), tool=2)
        px = Pixels(doc_of(line), info())
        self.assertTrue(is_col(px.at(60, 35), WHITE))
        self.assertTrue(any(p.width > 0 and p.color == B and not p.fill for p in px.prims))

    def test_off(self):
        px = Pixels(doc_of(square(50, 40, 40)), info(fill=False))
        self.assertTrue(is_col(px.at(50, 40), WHITE))

    def test_black_mode_kept(self):
        px = Pixels(doc_of(square(50, 40, 40)), info(fill_mode='noir'))
        self.assertTrue(is_col(px.at(50, 40), (0, 0, 0)))

    def test_mono(self):
        px = Pixels(doc_of(square(50, 40, 40)), info(mono=True))
        self.assertTrue(is_col(px.at(50, 40), (0, 0, 0)))

    def test_pdf_written_even_odd(self):
        p = pathlib.Path(tempfile.mkdtemp()) / 'bat.pdf'
        proof.write(doc_of(square(50, 40, 40), square(50, 40, 20)), p, info())
        self.assertTrue(p.exists())
        import zlib
        raw = p.read_bytes()
        s = raw.index(b'stream\n') + 7
        ops = zlib.decompress(raw[s:raw.index(b'\nendstream', s)]).decode()
        self.assertIn('f*', ops)


class TestPrecision(unittest.TestCase):
    def fmt(self, **k):
        return proof.number_format(proof.ProofInfo(**k))

    def test_default_like_before(self):
        f = self.fmt()
        self.assertEqual(f(12.5).replace(',', '.'), '12.5')
        self.assertEqual(f(100.0), '100')
        self.assertEqual(f(12.3456).replace(',', '.'), '12.35')

    def test_decimals(self):
        self.assertEqual(self.fmt(decimals=0)(12.6), '13')
        self.assertEqual(self.fmt(decimals=3)(12.3456).replace(',', '.'), '12.346')

    def test_keep_zeros(self):
        self.assertEqual(self.fmt(keep_zeros=True)(12.5).replace(',', '.'), '12.50')
        self.assertEqual(self.fmt(keep_zeros=True, decimals=0)(12.0), '12')

    def test_never_minus_zero(self):
        self.assertEqual(self.fmt()(-0.001), '0')

    def test_bad_value(self):
        self.assertEqual(self.fmt(decimals='x')(1.5).replace(',', '.'), '1.5')

    def written(self, **k):
        seen = []
        real = proof.text.layout

        def spy(s, *a, **kw):
            seen.append(s)
            return real(s, *a, **kw)
        d = doc_of(square(50, 40, 33.333))
        d.plate = None
        with mock.patch.object(proof.text, 'layout', spy):
            proof.build(d, proof.ProofInfo(**k))
        return seen

    def test_on_the_overall_dims(self):
        got = [s.replace(',', '.') for s in self.written(decimals=3)]
        self.assertIn('33.333', got)
        got = [s.replace(',', '.') for s in self.written(decimals=1)]
        self.assertIn('33.3', got)

    def test_in_the_title_block(self):
        got = [s.replace(',', '.') for s in self.written(decimals=1, keep_zeros=True)]
        self.assertTrue(any('33.3 × 33.3 mm' in s for s in got))

    def test_on_each_engraving(self):
        seen = []
        real = proof.text.layout

        def spy(s, *a, **kw):
            seen.append(s.replace(',', '.'))
            return real(s, *a, **kw)
        with mock.patch.object(proof.text, 'layout', spy):
            proof.build(doc_of(square(30, 40, 11.11), square(70, 40, 22.22)), proof.ProofInfo(decimals=1))
        self.assertIn('11.1', seen)


def png(path, color, w=40, h=20):
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(QColor('white'))
    p = QPainter(img)
    p.fillRect(5, 5, w - 10, h - 10, QColor(color))
    p.end()
    img.save(str(path))
    return str(path)


def svg(path, fill='#0a8040'):
    pathlib.Path(path).write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="40mm" height="20mm" viewBox="0 0 40 20">'
        f'<path d="M2 2 H38 V18 H2 Z M10 6 H30 V14 H10 Z" fill="{fill}" stroke="{fill}"/></svg>', encoding='utf-8')
    return str(path)


class TestTheme(unittest.TestCase):
    def setUp(self):
        self.dir = pathlib.Path(tempfile.mkdtemp())

    def page(self, **k):
        return proof.build(doc_of(square(50, 40, 40)), proof.ProofInfo(**k))[0]

    def frame_color(self, prims):
        return prims[0].color

    def test_default_black_frame(self):
        self.assertEqual(self.frame_color(self.page(title_color='#2e7d32')), (0, 0, 0))

    def test_theme_frame(self):
        self.assertEqual(self.frame_color(self.page(title_color='#2e7d32', theme_all=True)), proof._rgb('#2e7d32'))

    def test_theme_dims(self):
        col = proof._rgb('#2e7d32')
        d = doc_of(square(50, 40, 40))
        d.plate = None
        self.assertTrue(any(p.color == col for p in proof.build(d, proof.ProofInfo(title_color='#2e7d32', theme_all=True,
                                                                                   title_block=False))[0]))

    def test_theme_never_in_mono(self):
        self.assertEqual(self.frame_color(self.page(title_color='#2e7d32', theme_all=True, mono=True)), (0, 0, 0))

    def test_color_from_png_logo(self):
        f = png(self.dir / 'l.png', '#c02010')
        c = QColor(proof.logo_color(f))
        self.assertGreater(c.red(), 150)
        self.assertLess(c.green(), 70)

    def test_color_from_grey_logo(self):
        self.assertEqual(proof.logo_color(png(self.dir / 'g.png', '#808080')), '')

    def test_color_from_vector_logo(self):
        self.assertEqual(proof.logo_color(svg(self.dir / 'l.svg')), '#0a8040')

    def test_theme_from_logo(self):
        f = png(self.dir / 'l.png', '#c02010')
        col = self.frame_color(self.page(title_color='logo', theme_all=True, logo=f))
        self.assertGreater(col[0], 0.6)

    def test_theme_from_no_logo(self):
        self.assertEqual(self.frame_color(self.page(title_color='logo', theme_all=True)), (0, 0, 0))

    def test_no_logo_file(self):
        self.assertEqual(proof.logo_color(''), '')
        self.assertEqual(proof.logo_color(str(self.dir / 'absent.png')), '')


class TestLogos(unittest.TestCase):
    def setUp(self):
        self.dir = pathlib.Path(tempfile.mkdtemp())

    def test_vector_logo_stays_vector(self):
        f = svg(self.dir / 'l.svg')
        prims = proof.build(doc_of(square(50, 40, 40)), proof.ProofInfo(logo=f))[0]
        self.assertFalse([p for p in prims if p.image is not None])
        green = proof._rgb('#0a8040')
        self.assertTrue([p for p in prims if p.fill and p.color == green])

    def test_vector_logo_fits_its_place(self):
        f = svg(self.dir / 'l.svg')
        prims, PW, PH = proof.build(doc_of(square(50, 40, 40)), proof.ProofInfo(logo=f))
        green = proof._rgb('#0a8040')
        bb = geom.bbox_union(p.path.bbox() for p in prims if p.color == green and p.path.contours)
        self.assertLessEqual(bb[2] - bb[0], proof.LOGO_W + 1e-6)
        self.assertLessEqual(bb[3] - bb[1], proof.LOGO_H + 0.2)
        self.assertLess(bb[0], PW / 2)                                        # à gauche

    def test_second_logo_on_the_right(self):
        f = svg(self.dir / 'l.svg')
        prims, PW, PH = proof.build(doc_of(square(50, 40, 40)), proof.ProofInfo(logo2=f))
        green = proof._rgb('#0a8040')
        bb = geom.bbox_union(p.path.bbox() for p in prims if p.color == green and p.path.contours)
        self.assertGreater(bb[0], PW / 2)
        self.assertLessEqual(bb[2], PW - 10 + 0.2)

    def test_second_image_logo(self):
        f = png(self.dir / 'r.png', '#c02010')
        prims, PW, PH = proof.build(doc_of(square(50, 40, 40)), proof.ProofInfo(logo2=f))
        im = [p for p in prims if p.image is not None]
        self.assertEqual(len(im), 1)
        self.assertGreater(im[0].matrix.e, PW / 2)

    def test_legend_under_the_second_logo(self):
        f = png(self.dir / 'r.png', '#c02010')

        def top_legend(**k):
            prims = proof.build(doc_of(square(50, 40, 40)), proof.ProofInfo(**k))[0]
            leg = [p for p in prims if p.fill and p.color == R and abs(p.path.bbox()[2] - p.path.bbox()[0] - 5) < 1e-6]
            return leg[0].path.bbox()[3]
        self.assertLess(top_legend(logo2=f), top_legend() - proof.LOGO_H + 0.5)

    def test_absent_or_bad_logo(self):
        bad = self.dir / 'mauvais.svg'
        bad.write_text('ceci n\'est pas un dessin', encoding='utf-8')
        for f in (str(bad), str(self.dir / 'absent.svg'), str(self.dir / 'absent.png')):
            proof.build(doc_of(square(50, 40, 40)), proof.ProofInfo(logo=f, logo2=f))

    def test_vector_logo_cached(self):
        f = svg(self.dir / 'l.svg')
        self.assertIs(proof.logo_vector(f), proof.logo_vector(f))

    def test_image_is_not_vector(self):
        self.assertIsNone(proof.logo_vector(png(self.dir / 'r.png', '#c02010')))

    def test_written_in_pdf(self):
        p = self.dir / 'bat.pdf'
        proof.write(doc_of(square(50, 40, 40)), p, proof.ProofInfo(logo=svg(self.dir / 'l.svg'),
                                                                   logo2=png(self.dir / 'r.png', '#c02010')))
        self.assertGreater(p.stat().st_size, 500)


class TestDialog(unittest.TestCase):
    def setUp(self):
        self.dir = pathlib.Path(tempfile.mkdtemp())

    def dialog(self, **k):
        from vectordrive.ui.batdialog import BatDialog
        return BatDialog(None, doc_of(square(50, 40, 40)), proof.ProofInfo(**k))

    def test_fields(self):
        dlg = self.dialog(fill=True)
        try:
            dlg.decimals.setValue(3)
            dlg.keep_zeros.setChecked(True)
            dlg.theme_all.setChecked(True)
            dlg.title_color.setCurrentIndex(dlg.title_color.findData('logo'))
            dlg.fill_mode.setCurrentIndex(dlg.fill_mode.findData('contour'))
            i = dlg.result_info()
            self.assertEqual((i.decimals, i.keep_zeros, i.theme_all, i.title_color, i.fill_mode),
                             (3, True, True, 'logo', 'contour'))
            dlg.refresh()
        finally:
            dlg.deleteLater()

    def test_logo_choice(self):
        f = svg(self.dir / 'l.svg')
        dlg = self.dialog()
        try:
            dlg.set_logo(dlg.logo2, f)
            self.assertEqual(dlg.result_info().logo2, f)
            dlg.set_logo(dlg.logo2, '')
            self.assertEqual(dlg.result_info().logo2, '')
        finally:
            dlg.deleteLater()

    def test_pending_choice_keeps_logo(self):
        f = svg(self.dir / 'l.svg')
        dlg = self.dialog(logo=f)
        try:
            dlg.logo.setCurrentIndex(dlg.logo.findData('?'))
            self.assertEqual(dlg.result_info().logo, f)                       # « Choisir un fichier… » pas encore répondu
        finally:
            dlg.deleteLater()

    def test_company_in_the_title_group(self):
        dlg = self.dialog(company='Atelier')
        try:
            self.assertEqual(dlg.edits['company'].text(), 'Atelier')
        finally:
            dlg.deleteLater()


class TestWindow(unittest.TestCase):
    def test_settings_round_trip(self):
        from vectordrive.ui.batdialog import BatDialog
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.settings.setValue('bat/decimals', '3')
            w.settings.remove('bat/logos')
            f = svg(pathlib.Path(tempfile.mkdtemp()) / 'l.svg')
            seen = {}

            def fake_exec(dlg):
                seen['decimals'] = dlg.info.decimals
                dlg.set_logo(dlg.logo, f)
                return 1
            with mock.patch.object(BatDialog, 'exec', fake_exec):
                got = w._proof_info()
            self.assertEqual(seen['decimals'], 3)
            self.assertIsInstance(got.decimals, int)
            self.assertEqual(got.logo, f)
            logos = w.settings.value('bat/logos')
            self.assertIn(f, [logos] if isinstance(logos, str) else list(logos))
        finally:
            w.settings.remove('bat/logos')
            w.settings.remove('bat/decimals')
            w.settings.remove('bat/logo')
            for t in w.docs:
                t.modified = False
            w.modified = False
            w.close()

    def test_options(self):
        from vectordrive.ui.options import BY_KEY, default_of
        self.assertEqual(default_of(BY_KEY['bat/decimals']), '2')
        self.assertFalse(default_of(BY_KEY['bat/theme_all']))
        self.assertIn('logo2', proof.LAYOUT_FIELDS)


if __name__ == '__main__':
    unittest.main()
