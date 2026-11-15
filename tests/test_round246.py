"""Round 246 : points d'intersection (TypeEdit : I) — détection exacte par
nature (boucle, entre contours, entre objets), repères sur le plan de
travail, méthodes de suppression (petites boucles, normaliser, surface
remplie, réunir, contour extérieur, couper)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


def shapes():
    from vectordrive.core import geom
    from vectordrive.core.document import Shape
    a = Shape(path=geom.Path([geom.rect(0, 0, 20, 10)]))
    b = Shape(path=geom.Path([geom.rect(10, 5, 20, 10)]))                     # croise a en deux points
    loop = Shape(path=geom.Path([geom.polyline([(0, 40), (30, 40), (30, 60), (15, 60), (15.8, 61), (14.2, 61),
                                                (15, 60), (0, 60)], closed=True)]))
    two = Shape(path=geom.Path([geom.rect(50, 0, 10, 10), geom.rect(55, 5, 10, 10)]))   # contours d'un objet
    return a, b, loop, two


class TestFind(unittest.TestCase):
    def test_kinds(self):
        from vectordrive.core import intersect as I
        a, b, loop, two = shapes()
        r = I.find([a, b, loop, two])
        got = sorted((c.kind, round(c.x, 6), round(c.y, 6)) for c in r.crossings)
        self.assertIn(('objets', 10.0, 10.0), got)
        self.assertIn(('objets', 20.0, 5.0), got)
        self.assertEqual(r.count('objets'), 2)
        self.assertEqual(r.count('contours'), 2)
        self.assertEqual(r.count('self'), 1)
        self.assertLess(r.crossings[0].loop if r.crossings[0].kind == 'self' else
                        next(c.loop for c in r.crossings if c.kind == 'self'), 5.0)
        self.assertEqual(I.find([a]).count(), 0)

    def test_methods(self):
        from vectordrive.core import intersect as I
        a, b, loop, two = shapes()
        new = I.apply('loops', [loop], limit=5.0)
        self.assertEqual(I.find(new).count(), 0)
        self.assertTrue(new[0].path.contours[0].closed)
        bb = new[0].path.bbox()
        self.assertAlmostEqual(bb[3], 60.0, 6)                              # la boucle (y = 61) est partie
        self.assertEqual(I.find(I.apply('loops', [loop], limit=1.0)).count(), 1)   # boucle plus longue : gardée
        u = I.apply('union', [a, b])
        self.assertEqual((len(u), len(u[0].path.contours), I.find(u).count()), (1, 1, 0))
        n = I.apply('normalize', [two])
        self.assertEqual(I.find(n).count('contours'), 0)
        s = I.apply('split', [a, b])
        self.assertTrue(all(not c.closed for x in s for c in x.path.contours))
        self.assertEqual(sum(len(x.path.contours) for x in s), 4)
        ring = __import__('vectordrive.core.document', fromlist=['Shape']).Shape(
            path=__import__('vectordrive.core.geom', fromlist=['x']).Path(
                [__import__('vectordrive.core.geom', fromlist=['x']).rect(0, 0, 40, 40),
                 __import__('vectordrive.core.geom', fromlist=['x']).rect(10, 10, 10, 10)]))
        o = I.apply('outer', [ring, a])
        self.assertEqual(len(o), 1)
        self.assertEqual(len(o[0].path.contours), 1)                       # le trou est parti


class TestDuplicates(unittest.TestCase):
    def test_double_drawn_contour(self):
        from vectordrive.core import geom
        from vectordrive.core import intersect as I
        from vectordrive.core.document import Shape
        c = geom.circle((0, 0), 10)
        one = Shape(path=geom.Path([c]))
        # le même cercle, redessiné à 0,01 mm près (aplati en polygone) : il recoupe l'autre partout
        pts = [(10.01 * __import__('math').cos(t / 50 * 6.2832), 10.01 * __import__('math').sin(t / 50 * 6.2832))
               for t in range(50)]
        two = Shape(path=geom.Path([geom.polyline(pts, closed=True)]))
        r = I.find([one, two])
        self.assertEqual((r.count('doublon'), r.count('objets')), (1, 0))   # un repère, pas des dizaines
        left = I.dedupe([one, two])
        self.assertEqual(len(left), 1)
        self.assertEqual(I.find(left).count(), 0)


class TestWindow(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.a, self.b, self.loop, self.two = shapes()
        self.w.canvas.doc.layers[0].items.extend([self.a, self.b, self.loop])

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_detect_mark_and_apply(self):
        w = self.w
        dlg = w.intersections(exec_dialog=False)
        self.assertEqual(len(w.canvas.cross_marks), 3)
        self.assertEqual(dlg.list.count(), 3)
        self.assertEqual(dlg.method(), 'union')                           # des objets se croisent
        w.canvas.grab()                                                   # repères dessinés
        dlg._goto(dlg.list.item(0))
        left = w.apply_intersections(dlg.report, 'union', 2.0)
        self.assertEqual(left, 0)
        items = w.canvas.doc.layers[0].items
        self.assertEqual(len(items), 2)                                   # a + b réunis ; la boucle à part
        self.assertEqual(w.canvas.cross_marks, [])
        w.undo()
        self.assertEqual(len(w.canvas.doc.layers[0].items), 3)
        dlg.deleteLater()

    def test_nothing_found(self):
        w = self.w
        w.canvas.select([self.a])
        self.assertIsNone(w.intersections(exec_dialog=False))
        self.assertEqual(w.canvas.cross_marks, [])


if __name__ == '__main__':
    unittest.main()
