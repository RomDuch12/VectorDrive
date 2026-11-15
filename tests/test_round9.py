"""Round 9 : textes (largeur imposée, arc), duplication sur courbe."""
import math
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import duplicate, fonts, geom, text
from vectordrive.core.document import Document, Shape, Text
from vectordrive.core.geom import Affine, Path
from vectordrive.io import native, registry

HAS_ARIAL = fonts.find_font('Arial') is not None


def center(it):
    b = it.bbox()
    return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)


class TestWalker(unittest.TestCase):
    def test_circle(self):
        total, at = geom.walker(geom.circle((0, 0), 10))
        self.assertAlmostEqual(total, 2 * math.pi * 10, places=9)
        (x, y), ang = at(0)
        self.assertAlmostEqual(x, 10, places=6)
        self.assertAlmostEqual(math.degrees(ang) % 360, 90, delta=1e-3)
        for k in range(1, 12):                          # point sur le cercle exact, tangente exacte
            (x, y), ang = at(total * k / 12)
            self.assertAlmostEqual(math.hypot(x, y), 10, places=9)
            self.assertAlmostEqual(math.degrees(math.atan2(y, x)) % 360, 30 * k, delta=0.05)
            self.assertAlmostEqual((math.degrees(ang) - 30 * k - 90 + 180) % 360 - 180, 0, delta=1e-3)


@unittest.skipUnless(HAS_ARIAL, 'police Arial absente')
class TestTextFit(unittest.TestCase):
    def test_fit_width(self):
        for mode in ('spacing', 'ratio'):
            with self.subTest(mode=mode):
                f = text.fit_width('BFM GRAVURE', 'Arial', 5, 60, mode)
                w = text.line_widths('BFM GRAVURE', 'Arial', 5, spacing=f['spacing'],
                                     width_ratio=f['width_ratio'])[0]
                self.assertAlmostEqual(w, 60, places=6)

    def test_outline_for_fit(self):
        t = Text(text='ABC', font='Arial', size=5, matrix=Affine.translation(10, 20))
        t.extra['fit'] = {'width': 40, 'mode': 'ratio'}
        p = text.outline_for(t)
        self.assertGreater(t.width_ratio, 1)
        bb = p.bbox()
        self.assertGreater(bb[2] - bb[0], 35)
        self.assertLess(bb[2] - bb[0], 40.5)
        self.assertGreater(bb[0], 9.5)                  # approche du « A » : légèrement négative

    def test_arc_bands(self):
        r, h = 30.0, 5.0
        for pos in ('top', 'bottom'):
            for side in ('outside', 'inside'):
                with self.subTest(pos=pos, side=side):
                    t = Text(text='ABCDEF', font='Arial', size=h, align='center')
                    t.extra['arc'] = {'center': [100, 50], 'radius': r, 'position': pos, 'side': side}
                    p = text.outline_for(t)
                    rs = [math.hypot(x - 100, y - 50) for c in p.contours for x, y in c.flatten(0.05)]
                    lo, hi = (r, r + h) if side == 'outside' else (r - h, r)
                    self.assertGreater(min(rs), lo - 0.3)
                    self.assertLess(max(rs), hi + 0.3)
                    cy = center(Shape(path=p))[1]
                    self.assertEqual(cy > 50, pos == 'top')

    def test_arc_follows_translation(self):
        t = Text(text='AB', font='Arial', size=4, align='center')
        t.extra['arc'] = {'center': [0, 0], 'radius': 20, 'position': 'top', 'side': 'outside'}
        t.outline = text.outline_for(t)
        m = t.transformed(Affine.translation(5, 7))
        self.assertEqual(m.extra['arc']['center'], [5, 7])
        self.assertEqual(t.extra['arc']['center'], [0, 0])
        r = t.transformed(Affine.rotation(30))
        self.assertNotIn('arc', r.extra)
        self.assertIsNotNone(r.extra.get('on_path'))

    def test_native_round_trip(self):
        t = Text(text='AB', font='Arial', size=4, width_ratio=1.3)
        t.extra['fit'] = {'width': 25.0, 'mode': 'ratio'}
        t.outline = text.outline_for(t)
        d = Document()
        d.add(t)
        with tempfile.TemporaryDirectory() as tmp:
            f = pathlib.Path(tmp) / 't.vdz'
            native.write(d, f)
            back = registry.open_document(f).layers[0].items[0]
        self.assertAlmostEqual(back.width_ratio, t.width_ratio)
        self.assertEqual(back.extra['fit'], {'width': 25.0, 'mode': 'ratio'})


class TestAlong(unittest.TestCase):
    def test_open_line(self):
        sq = Shape(path=Path([geom.rect(-1, -1, 2, 2)]))
        out = duplicate.along([sq], geom.polyline([(0, 0), (100, 0)]), 3)
        xs = [round(center(o)[0], 6) for o in out]
        self.assertEqual(xs, [0, 50, 100])

    def test_circle_rotation(self):
        arrow = Shape(path=Path([geom.polyline([(0, 0), (4, 0)])]))         # horizontale
        out = duplicate.along([arrow], geom.circle((0, 0), 50), 4)
        self.assertEqual(len(out), 4)
        for o, ang in zip(out, (0, 90, 180, 270)):
            c = center(o)
            self.assertAlmostEqual(math.hypot(*c), 50, delta=0.01)
            seg = o.path.contours[0].segments[0]
            d = math.degrees(math.atan2(seg.end[1] - seg.start[1], seg.end[0] - seg.start[0]))
            self.assertAlmostEqual((d - (ang + 90) + 180) % 360 - 180, 0, delta=1e-3)  # tangente

    def test_window(self):
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            d = w.canvas.doc
            obj = d.add(Shape(path=Path([geom.rect(-1, -1, 2, 2)])))
            curve = d.add(Shape(path=Path([geom.circle((0, 0), 40)])))
            w.canvas.select([curve])
            self.assertEqual(w._circle_of_selection(), ((0.0, 0.0), 40.0))
            w.canvas.select([obj, curve])
            new = w.duplicate({'mode': 'along', 'al_n': 6, 'al_rot': True})
            self.assertEqual(len(new), 6)
            self.assertEqual(sum(1 for _ in d.iter_items()), 8)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
