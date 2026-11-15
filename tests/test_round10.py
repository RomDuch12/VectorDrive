"""Round 10 : performances (longueurs groupées, caches, annulation
structurelle, scène en cache, accrochage paresseux) — sans perte d'exactitude."""
import math
import os
import random
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import geom
from vectordrive.core.document import Group, Shape, Text, struct_copy, struct_copy_layers, Layer
from vectordrive.core.geom import Affine, Conic, Cubic, Line, Path
from vectordrive.core.snap import Snap


def random_path(n=300, seed=1):
    rnd = random.Random(seed)
    segs = []
    p = (0.0, 0.0)
    for _ in range(n):
        q = (rnd.uniform(-50, 50), rnd.uniform(-50, 50))
        k = rnd.random()
        if k < 0.3:
            segs.append(Line(p, q))
        elif k < 0.65:
            segs.append(Cubic(p, (rnd.uniform(-50, 50), 0), (0, rnd.uniform(-50, 50)), q))
        else:
            segs.append(Conic(p, (rnd.uniform(-50, 50), rnd.uniform(-50, 50)), q, rnd.uniform(0.2, 2)))
        p = q
    return Path([geom.Contour(segs, False), geom.circle((3, 4), 7)])


class TestBatchAndMemo(unittest.TestCase):
    def test_batch_equals_scalar(self):
        p = random_path()
        segs = [s for c in p.contours for s in c.segments]
        ref = [s.length() for s in segs]
        got = geom.batch_lengths(segs)
        self.assertLess(max(abs(a - b) for a, b in zip(ref, got)), 1e-9)
        self.assertAlmostEqual(p.length(), sum(ref), places=9)

    def test_memo_propagation(self):
        p = random_path(seed=2)
        L, bb = p.length(), p.bbox()
        for m, keeps_bbox in ((Affine.translation(5, -3), True), (Affine.rotation(33), False),
                              (Affine.mirror_x() if hasattr(Affine, 'mirror_x') else Affine(-1, 0, 0, 1, 0, 0), True),
                              (Affine.scaling(2), True)):
            q = p.transformed(m)
            memo = q.__dict__.get('_memo', {})
            self.assertIn('length', memo)                      # similitude : longueur reportée
            self.assertEqual('bbox' in memo, keeps_bbox)
            fresh = Path(list(q.contours))                     # même géométrie, sans cache
            self.assertAlmostEqual(q.length(), fresh.length(), places=6)
            for a, b in zip(q.bbox(), fresh.bbox()):
                self.assertAlmostEqual(a, b, places=9)
        shear = p.transformed(Affine(1, 0, 0.5, 1, 0, 0))
        self.assertNotIn('length', shear.__dict__.get('_memo', {}))   # pas une similitude


class TestStructCopy(unittest.TestCase):
    def test_paths_shared_extras_independent(self):
        s = Shape(path=random_path(20))
        t = Text(text='A')
        g = Group(children=[s, t])
        c = struct_copy(g)
        self.assertIsNot(c, g)
        self.assertIs(c.children[0].path, s.path)              # tracé partagé
        c.children[1].extra['fit'] = {'width': 3}
        self.assertNotIn('fit', t.extra)
        c.children[0].path = Path()
        self.assertTrue(s.path.contours)
        L = Layer('A', items=[g])
        L2 = struct_copy_layers([L])[0]
        L2.items.append(Shape())
        self.assertEqual(len(L.items), 1)


class TestCanvasCaches(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_scene_and_path_cache(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.resize(900, 600)
            w.show()
            self.app.processEvents()
            c = w.canvas
            sh = c.doc.add(Shape(path=Path([geom.rect(0, 0, 10, 10)])))
            c.fit((0, 0, 20, 20))
            c.repaint()
            scene = c._scene
            self.assertIsNotNone(scene)
            q = c._qpath(sh)
            c.overlay_update()
            c.repaint()
            self.assertIs(c._scene, scene)                     # surimpression : scène réutilisée
            c.update()
            c.repaint()
            self.assertIsNot(c._scene, scene)                  # mise à jour normale : recalcul
            # annuler / refaire : les copies partagent le tracé, donc le chemin Qt
            w.canvas.select([sh])
            w.mirror(True)
            w.undo()
            restored = c.doc.layers[0].items[0]
            self.assertIsNot(restored, sh)
            self.assertIs(c._qpath(restored), q)
            # tracé remplacé en place : nouveau chemin Qt
            w.canvas.select([restored])
            w.open_contours()
            self.assertIsNot(c._qpath(c.doc.layers[0].items[0]), q)
        finally:
            w.modified = False
            w.close()


class TestLazySnap(unittest.TestCase):
    def test_points_only_near_cursor(self):
        items = [Shape(path=Path([geom.rect(i * 100, 0, 10, 10)])) for i in range(200)]
        s = Snap(enabled=True)
        h = s.query(10.2, 10.1, 1.0, items)
        self.assertEqual((h.kind, h.x, h.y), ('node', 10, 10))
        self.assertLessEqual(len(s._cache), 2)


if __name__ == '__main__':
    unittest.main()
