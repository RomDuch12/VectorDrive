"""Round 109 : parité TypeEdit — commandes du ruban de TypeEdit reliées
(raccourcis), règle graduée et vernier, casse et rechercher / remplacer
dans les textes, points alignés, cercles reconnus, flèches, cercle par
trois points, alignement sur les bords de la plaque, zoom précédent et
zoom plaque, vider l'historique."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom, graduation as GR, shapes as SH, textops as TO
from vectordrive.core.document import Plate, Shape, Text
from vectordrive.core.geom import Line, Path


def app():
    return QApplication.instance() or QApplication([])


class TestTextOps(unittest.TestCase):
    def test_case(self):
        self.assertEqual(TO.change_case('plaque été', 'majuscules'), 'PLAQUE ÉTÉ')
        self.assertEqual(TO.change_case('PLAQUE ÉTÉ', 'minuscules'), 'plaque été')
        self.assertEqual(TO.change_case("l'atelier de saint-étienne 42", 'mots'), "L'atelier De Saint-Étienne 42")
        self.assertEqual(TO.change_case('BONJOUR\n12 RUE', 'phrase'), 'Bonjour\n12 Rue')

    def test_find_replace(self):
        self.assertEqual(TO.find_replace('Lot A, lot B', 'lot', 'Série'), ('Série A, Série B', 2))
        self.assertEqual(TO.find_replace('Lot A, lot B', 'lot', 'Série', case=True), ('Lot A, Série B', 1))
        self.assertEqual(TO.find_replace('pas passe', 'pas', 'x', whole=True), ('x passe', 1))
        self.assertEqual(TO.find_replace('a.b', '.', '-'), ('a-b', 1))               # pas d'expression régulière
        self.assertEqual(TO.find_replace('abc', '', 'x'), ('abc', 0))


class TestShapes(unittest.TestCase):
    def test_merge_collinear(self):
        c = geom.polyline([(0, 0), (5, 0), (10, 0), (10, 5), (10, 10), (0, 10)], closed=True)
        p, n = SH.merge_collinear(Path([c]))
        self.assertEqual(n, 2)
        self.assertEqual(len(p.contours[0].segments), 4)
        self.assertAlmostEqual(abs(p.contours[0].signed_area()), 100)
        # un aller-retour n'est pas fusionné
        back = geom.polyline([(0, 0), (5, 0), (2, 0)])
        self.assertEqual(SH.merge_collinear(Path([back]))[1], 0)

    def test_to_circles(self):
        poly = geom.polyline([(10 + 5 * math.cos(k * math.pi / 36), 5 * math.sin(k * math.pi / 36)) for k in range(72)],
                             closed=True)
        sq = geom.rect(0, 0, 4, 4)
        p, n = SH.to_circles(Path([poly, sq]), tol=0.02)
        self.assertEqual(n, 1)
        bb = p.contours[0].bbox()
        self.assertAlmostEqual(bb[2] - bb[0], 10, places=1)
        self.assertEqual(p.contours[1], sq)
        self.assertEqual(p.contours[0].signed_area() > 0, poly.signed_area() > 0)

    def test_arrow_and_circle3(self):
        a = SH.arrow(SH.ArrowSpec(length=40, shaft_width=6, head_length=12, head_width=16))
        self.assertTrue(a.closed)
        bb = a.bbox()
        self.assertAlmostEqual(bb[2] - bb[0], 40)
        self.assertAlmostEqual(bb[3] - bb[1], 16)
        d = SH.arrow(SH.ArrowSpec(double=True, angle=90))
        self.assertAlmostEqual(d.bbox()[3] - d.bbox()[1], 40)
        c, r = SH.circumcircle((0, 0), (10, 0), (5, 5))
        self.assertAlmostEqual(r, 5)
        self.assertIsNone(SH.circle_3points((0, 0), (1, 1), (2, 2)))


class TestGraduation(unittest.TestCase):
    def test_ruler_and_vernier(self):
        spec = GR.GraduationSpec(divisions=20, step=1.0, major_every=10, medium_every=5, vernier=10)
        kinds = [k for _x, k in GR.ticks(spec)]
        self.assertEqual(kinds.count('major'), 3)
        self.assertEqual(kinds.count('medium'), 2)
        vt = GR.vernier_ticks(spec)
        self.assertEqual(len(vt), 11)
        self.assertAlmostEqual(vt[-1][0], 9.0)                                # 10 divisions sur 9 pas
        g = GR.build(spec, (5, 5), tool=2)
        names = [c.name for c in g.children]
        self.assertIn('graduations', names)
        self.assertIn('vernier', names)
        self.assertIn('nombres', names)
        self.assertEqual(g.extra['graduation']['origin'], [5, 5])
        bb = g.children[0].bbox()
        self.assertAlmostEqual(bb[0], 5)
        self.assertAlmostEqual(bb[2], 25)
        filled = GR.build(GR.GraduationSpec(divisions=4, tick_width=0.3, numbers=False))
        self.assertTrue(filled.children[0].filled)


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app()
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        cls.w.resize(1000, 700)

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def setUp(self):
        self.w.modified = False                 # pas de « enregistrer ? » entre deux essais
        self.w.new_document()

    def test_typeedit_commands_linked(self):
        from vectordrive.ui import shortcuts as S
        missing = [c for c, k in S.TE_ACTIONS.items() if k not in self.w.A]
        self.assertEqual(missing, [])
        self.assertGreaterEqual(len(S.TE_ACTIONS), 170)

    def test_align_to_plate(self):
        w = self.w
        d = w.canvas.doc
        d.plate = Plate(width=100, height=50)
        s = Shape(path=Path([geom.rect(40, 20, 10, 10)]))
        d.layers[0].items.append(s)
        w.canvas.select([s])
        w.align_to_plate('left')
        w.align_to_plate('top')
        bb = w.canvas.selection_bbox()
        self.assertAlmostEqual(bb[0], 0)
        self.assertAlmostEqual(bb[3], 50)

    def test_zoom_previous_and_plate(self):
        w = self.w
        w.canvas.doc.plate = Plate(width=100, height=50)
        c = w.canvas
        c.fit()
        before = (c.scale, c.ox, c.oy)
        c._view_t = 0.0
        c.zoom_at(2.0, QPointF(10, 10))
        self.assertNotEqual(c.scale, before[0])
        w.zoom_previous()
        self.assertAlmostEqual(c.scale, before[0])
        w.zoom_plate()
        self.assertTrue(w.A['zoom_prev'].isEnabled())

    def test_text_case_and_find_replace(self):
        w = self.w
        t = Text(text='lot 12 / lot 13', font='Arial', size=5)
        w.canvas.doc.layers[0].items.append(t)
        self.assertEqual(w.find_replace('lot', 'Série'), 2)
        self.assertEqual(t.text, 'Série 12 / Série 13')
        self.assertTrue(t.outline is not None and t.outline.contours)
        self.assertEqual(w.change_text_case('upper'), 1)
        self.assertEqual(t.text, 'SÉRIE 12 / SÉRIE 13')
        w.undo()
        self.assertEqual(w.canvas.doc.layers[0].items[0].text, 'Série 12 / Série 13')

    def test_shape_ops_and_history(self):
        w = self.w
        poly = geom.polyline([(5 * math.cos(k * math.pi / 30), 5 * math.sin(k * math.pi / 30)) for k in range(60)],
                             closed=True)
        line = geom.polyline([(0, 20), (5, 20), (10, 20)])
        w.canvas.doc.layers[0].items += [Shape(path=Path([poly])), Shape(path=Path([line]))]
        w.convert_to_circles()
        w.remove_aligned_points()
        items = w.canvas.doc.layers[0].items
        self.assertEqual(len(items[1].path.contours[0].segments), 1)
        self.assertNotIsInstance(items[0].path.contours[0].segments[0], Line)
        self.assertTrue(w._undo)
        w.clear_history()
        self.assertFalse(w._undo)

    def test_graduation_edit_roundtrip(self):
        w = self.w
        g = GR.build(GR.GraduationSpec(divisions=10), (0, 0))
        w.canvas.doc.layers[0].items.append(g)
        spec = GR.GraduationSpec.from_dict(g.extra['graduation'])
        self.assertEqual(spec.divisions, 10)

    def test_circle3_tool(self):
        w = self.w
        w.set_tool('circle3')
        tool = w.canvas.tool_obj
        for p in ((0, 0), (10, 0), (5, 5)):
            tool.press(QPointF(), p, None)
        items = w.canvas.doc.layers[0].items
        self.assertEqual(len(items), 1)
        bb = items[0].bbox()
        self.assertAlmostEqual(bb[2] - bb[0], 10, places=3)
        w.set_tool('select')


if __name__ == '__main__':
    unittest.main()
