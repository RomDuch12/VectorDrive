"""Édition : booléens, offset, nœuds, congés, texte."""
import math
import unittest

from vectordrive.core import geom, nodes, pathops, text
from vectordrive.core.geom import Path


def sq(x, y, w):
    return Path([geom.rect(x, y, w, w)])


class TestPathops(unittest.TestCase):
    def test_engine(self):
        self.assertIn(pathops.available(), ('vectorcraft-pathops', 'shapely'))

    def test_booleans_area(self):
        a, b = sq(0, 0, 10), sq(5, 5, 10)
        self.assertAlmostEqual(pathops.area(pathops.boolean(a, b, 'union')), 175, places=6)
        self.assertAlmostEqual(pathops.area(pathops.boolean(a, b, 'intersect')), 25, places=6)
        self.assertAlmostEqual(pathops.area(pathops.boolean(a, b, 'difference')), 75, places=6)
        self.assertAlmostEqual(pathops.area(pathops.boolean(a, b, 'xor')), 150, places=6)

    def test_boolean_with_circle(self):
        c = Path([geom.circle((0, 0), 10)])
        r = Path([geom.rect(0, -20, 20, 40)])
        half = pathops.boolean(c, r, 'intersect')
        self.assertAlmostEqual(pathops.area(half), math.pi * 100 / 2, delta=1e-3)

    def test_offset_round(self):
        out = pathops.offset(sq(0, 0, 10), 1.0, 'round')
        self.assertAlmostEqual(pathops.area(out), 144 - 4 + math.pi, delta=1e-3)
        inner = pathops.offset(sq(0, 0, 10), -1.0, 'miter')
        self.assertAlmostEqual(pathops.area(inner), 64, delta=1e-6)

    def test_normalize_bowtie(self):
        bow = Path([geom.polyline([(0, 0), (10, 10), (10, 0), (0, 10)], closed=True)])
        n = pathops.normalize(bow)
        self.assertAlmostEqual(pathops.area(n), 50, delta=1e-6)


class TestNodes(unittest.TestCase):
    def test_move_node(self):
        c = geom.rect(0, 0, 10, 10)
        c2 = nodes.move_node(c, 0, (12, 0))
        self.assertEqual(nodes.node_point(c2, 0), (12, 0))
        self.assertEqual(len(c2.segments), 4)

    def test_insert_then_delete(self):
        c = geom.rect(0, 0, 10, 10)
        c2 = nodes.insert_node(c, 0, 0.5)
        self.assertEqual(nodes.node_count(c2), 5)
        self.assertEqual(nodes.node_point(c2, 0), (5, 0))
        c3 = nodes.delete_node(c2, 0)
        self.assertAlmostEqual(c3.length(), 40)

    def test_split_conic_exact(self):
        arc = geom.arc_conics((0, 0), 10, 10, 0, 90)[0]
        a, b = nodes.split_segment(arc, 0.3)
        for s in (a, b):
            for t in (0.2, 0.5, 0.8):
                self.assertAlmostEqual(math.hypot(*s.point(t)), 10, places=9)
        self.assertAlmostEqual(a.length() + b.length(), arc.length(), places=9)

    def test_break_and_join(self):
        c = geom.rect(0, 0, 10, 10)
        (o,) = nodes.break_at(c, 1)
        self.assertFalse(o.closed)
        self.assertAlmostEqual(o.length(), 40)
        p1, p2 = nodes.break_at(geom.polyline([(0, 0), (5, 0), (10, 0)]), 1)
        j = nodes.join(p1, p2)
        self.assertAlmostEqual(j.length(), 10)

    def test_fillet_on_selected_node(self):
        c = geom.rect(0, 0, 10, 10)
        f = geom.corner_contour(c, 2, 'fillet', only={0})
        self.assertAlmostEqual(f.length(), 40 - 4 + math.pi, places=9)


class TestText(unittest.TestCase):
    def test_cap_height(self):
        p = text.layout('H', 'Arial', 10.0)
        if not p:
            self.skipTest('Arial absente')
        bb = p.bbox()
        self.assertAlmostEqual(bb[3] - bb[1], 10.0, places=3)     # hauteur des capitales
        self.assertAlmostEqual(bb[1], 0.0, places=6)              # posé sur la ligne de base

    def test_alignment(self):
        left = text.layout('ABC', 'Arial', 5.0, align='left').bbox()
        right = text.layout('ABC', 'Arial', 5.0, align='right').bbox()
        if not left:
            self.skipTest('Arial absente')
        self.assertLess(right[2], 0.5)
        self.assertGreater(left[0], -0.5)

    def test_multiline(self):
        p = text.layout('A\nB', 'Arial', 5.0, line_spacing=2.0)
        if not p:
            self.skipTest('Arial absente')
        bb = p.bbox()
        self.assertLess(bb[1], -5.0)


class TestDimensionAndPathText(unittest.TestCase):
    def test_dimension_value(self):
        parts = geom.dimension((0, 0), (37.5, 0), 8)
        if not parts[2]:
            self.skipTest('Arial absente')
        self.assertEqual(len(parts[0].contours), 3)        # 2 attaches + ligne de cote
        self.assertEqual(len(parts[1].contours), 2)        # 2 flèches
        self.assertTrue(all(c.closed for c in parts[1].contours))

    def test_text_on_arc_radius(self):
        arc = geom.arc((0, 0), 30, 180, -180)
        p = text.on_path('ABC', 'Arial', 5, arc, align='center')
        if not p:
            self.skipTest('Arial absente')
        import math
        for c in p.contours:
            for pt in c.nodes():
                self.assertGreater(math.hypot(*pt), 29.5)     # au-dessus de l'arc
                self.assertLess(math.hypot(*pt), 37)


if __name__ == '__main__':
    unittest.main()
