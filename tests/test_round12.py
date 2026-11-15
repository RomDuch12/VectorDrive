"""Round 12 : combiner, englobants/englobés, répartir, texte dans un cadre."""
import os
import pathlib
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import combine as C
from vectordrive.core import fonts, geom
from vectordrive.core import text as TX
from vectordrive.core.document import Group, Shape, Text
from vectordrive.core.geom import Affine, Path
from vectordrive.io import registry
from tests.corpus import corpus

DXF_REFERENCE = corpus('dxf_verite')


def shape(c):
    return Shape(path=Path([c]))


class TestNest(unittest.TestCase):
    def test_letter_o_island_open(self):
        cs = [geom.circle((0, 0), 2), geom.rect(30, -5, 10, 10), geom.circle((0, 0), 10),
              geom.circle((0, 0), 6), geom.polyline([(50, 0), (60, 5)])]
        groups = C.nest(cs)
        self.assertEqual(len(groups), 4)
        outer, holes = groups[0]
        self.assertAlmostEqual(abs(outer.signed_area()), 314.159, delta=0.05)    # aire de polygone inscrit
        self.assertGreater(outer.signed_area(), 0)                 # extérieur : trigo
        self.assertEqual(len(holes), 1)
        self.assertLess(holes[0].signed_area(), 0)                 # trou : horaire
        self.assertTrue(any(not o.closed for o, _h in groups))     # contour ouvert seul

    def test_combine_uncombine(self):
        items = [shape(geom.rect(0, 0, 10, 10)), Group(children=[shape(geom.circle((5, 5), 2))])]
        sh = C.combine(items)
        self.assertEqual(len(sh.path.contours), 2)
        parts = C.uncombine(sh)
        self.assertEqual(len(parts), 2)

    @unittest.skipUnless(DXF_REFERENCE.exists(), 'DXF de référence absent')
    def test_dxf_letters(self):
        d = registry.open_document(DXF_REFERENCE)
        items = [it for L in d.layers for it in L.items]
        n_in = sum(len(p.contours) for _it, p in C._leaf_paths(items))
        shapes = C.combine_nested(items)
        n_out = sum(len(s.path.contours) for s in shapes)
        self.assertEqual(n_in, n_out)                              # aucun contour perdu
        self.assertLess(len(shapes), n_in)                         # des trous rattachés
        for s in shapes:
            o = s.path.contours[0]
            if o.closed:
                self.assertGreaterEqual(o.signed_area(), 0)
                for h in s.path.contours[1:]:
                    self.assertLessEqual(h.signed_area(), 0)


class TestDistribute(unittest.TestCase):
    def test_gaps_and_centers(self):
        items = [shape(geom.rect(0, 0, 10, 10)), shape(geom.rect(30, 0, 5, 10)),
                 shape(geom.rect(13, 0, 2, 10)), shape(geom.rect(50, 0, 10, 10))]
        out = C.distribute(items, 'x', 'gaps')
        boxes = sorted(it.bbox() for it in out)
        gaps = [round(boxes[i + 1][0] - boxes[i][2], 9) for i in range(3)]
        self.assertEqual(gaps, [11.0, 11.0, 11.0])
        out = C.distribute(items, 'y', 'centers')
        self.assertEqual([it.bbox() for it in out], [it.bbox() for it in items])   # même hauteur
        tall = [shape(geom.rect(0, y, 4, 4)) for y in (0, 3, 40, 10)]
        out = C.distribute(tall, 'y', 'centers')
        cs = sorted((b[1] + b[3]) / 2 for b in (it.bbox() for it in out))
        self.assertEqual([round(c, 6) for c in cs], [2.0, 15.333333, 28.666667, 42.0])   # 2 et 42 fixes


@unittest.skipUnless(fonts.find_font('Arial'), 'Arial absente')
class TestTextBox(unittest.TestCase):
    def test_fits(self):
        for txt in ('BFM', 'Bgj\nGRAULHET 81300', 'A'):
            for stretch in (False, True):
                with self.subTest(txt=txt, stretch=stretch):
                    t = Text(text=txt, font='Arial', align='center')
                    t.extra['box'] = {'x0': 10, 'y0': 10, 'x1': 70, 'y1': 30, 'stretch': stretch}
                    bb = TX.outline_for(t).bbox()
                    self.assertGreaterEqual(bb[1], 10 - 0.05)
                    self.assertLessEqual(bb[3], 30 + 0.05)
                    w = max(TX.line_widths(t.text, t.font, t.size, width_ratio=t.width_ratio))
                    self.assertLessEqual(w, 60 + 1e-6)
                    if stretch:
                        self.assertAlmostEqual(w, 60, places=6)

    def test_box_follows(self):
        t = Text(text='AB', font='Arial')
        t.extra['box'] = {'x0': 0, 'y0': 0, 'x1': 20, 'y1': 10}
        t.outline = TX.outline_for(t)
        m = t.transformed(Affine.translation(5, 1))
        self.assertEqual((m.extra['box']['x0'], m.extra['box']['y1']), (5, 11))
        self.assertNotIn('box', t.transformed(Affine.rotation(10)).extra)


class TestWindow(unittest.TestCase):
    def test_commands(self):
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            d = w.canvas.doc
            a = d.add(shape(geom.circle((0, 0), 10)))
            b = d.add(shape(geom.circle((0, 0), 6)))
            w.canvas.select([a, b])
            w.combine_nested_items()
            self.assertEqual(len(d.layers[0].items), 1)
            self.assertEqual(len(d.layers[0].items[0].path.contours), 2)
            w.canvas.select(list(d.layers[0].items))
            w.uncombine_items()
            self.assertEqual(len(d.layers[0].items), 2)
            w.undo()
            self.assertEqual(len(w.canvas.doc.layers[0].items), 1)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
