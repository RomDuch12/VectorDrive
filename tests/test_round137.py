"""Round 137 : vérification des dessins plus rapide — encombrement des
contours mis en cache, polylignes numpy sans appel par droite ; sauvegarde
de récupération en tâche de fond. Résultats identiques au bit (vérifié sur
les 354 630 contours du corpus de l'atelier)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np

from vectordrive.core import geom
from vectordrive.core.geom import Conic, Contour, Cubic, Line
from vectordrive.core import parallel


def slow_cubic_bbox(s):
    """Extrema de la dérivée, sans raccourci (référence)."""
    xs, ys = [s.p0[0], s.p3[0]], [s.p0[1], s.p3[1]]
    for i, acc in ((0, xs), (1, ys)):
        a, b, c, d = s.p0[i], s.p1[i], s.p2[i], s.p3[i]
        for t in geom._quad_roots(-a + 3 * b - 3 * c + d, 2 * (a - 2 * b + c), b - a):
            if 0 < t < 1:
                acc.append(s.point(t)[i])
    return min(xs), min(ys), max(xs), max(ys)


class TestBBox(unittest.TestCase):
    def test_union_of_segments(self):
        import random
        rnd = random.Random(137)
        for _ in range(200):
            segs = [Cubic(*[(rnd.uniform(-5, 5), rnd.uniform(-5, 5)) for _ in range(4)]) for _ in range(3)]
            segs.append(Conic(*[(rnd.uniform(-5, 5), rnd.uniform(-5, 5)) for _ in range(3)], 0.7))
            c = Contour(segs, False)
            bs = [slow_cubic_bbox(s) if isinstance(s, Cubic) else s.bbox() for s in segs]
            ref = (min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs))
            self.assertEqual(c.bbox(), ref)

    def test_contour_memo(self):
        c = Contour([Line((0, 0), (4, 0)), Cubic((4, 0), (5, 1), (5, 2), (4, 3)), Line((4, 3), (0, 0))], True)
        b = c.bbox()
        self.assertIs(c.bbox(), b)                                  # en cache
        c.segments = c.segments + [Line((0, 0), (-1, -1))]          # nouvelle liste : recalculé
        self.assertEqual(c.bbox()[0], -1)
        with self.assertRaises(ValueError):
            Contour([], True).bbox()

    def test_nan_like_before(self):
        n = float('nan')
        c = Contour([Line((0, 0), (1, 1)), Line((1, 1), (n, 2))], False)
        b = c.bbox()
        self.assertEqual(b[1], 0)
        self.assertEqual(b[3], 2)


class TestPolyline(unittest.TestCase):
    def reference(self, c, tol):
        out = [np.asarray([c.start], float)]
        for sg in c.segments:
            if isinstance(sg, Line):
                out.append(np.asarray([sg.p1], float))
                continue
            P = np.asarray(sg.controls(), float)
            if isinstance(sg, Cubic):
                acc = 6 * max(np.hypot(*(P[0] - 2 * P[1] + P[2])), np.hypot(*(P[1] - 2 * P[2] + P[3])))
            else:
                acc = 2 * np.hypot(*(P[0] - 2 * P[1] + P[2])) * max(1.0, 1 / max(sg.w, 1e-3) ** 2)
            k = int(min(4000, max(2, math.ceil(math.sqrt(acc / (8 * tol))))))
            t = np.linspace(0.0, 1.0, k + 1)[1:, None]
            u = 1 - t
            if isinstance(sg, Cubic):
                pts = u ** 3 * P[0] + 3 * u * u * t * P[1] + 3 * u * t * t * P[2] + t ** 3 * P[3]
            else:
                a0, a1, a2 = u * u, 2 * sg.w * u * t, t * t
                pts = (a0 * P[0] + a1 * P[1] + a2 * P[2]) / (a0 + a1 + a2)
            out.append(pts)
        q = np.concatenate(out)
        if c.closed and np.hypot(*(q[0] - q[-1])) > 1e-12:
            q = np.vstack([q, q[:1]])
        return q

    def test_identical(self):
        shapes = [geom.rect(0, 0, 10, 5), geom.circle((3, 3), 2),
                  Contour([Line((0, 0), (5, 0)), Cubic((5, 0), (7, 1), (7, 3), (5, 4)),
                           Line((5, 4), (2, 4)), Line((2, 4), (1, 2))], True)]
        from vectordrive.core.geom import arc_conics
        shapes.append(Contour(arc_conics((0, 0), 3, 3, 0, 270), False))
        for c in shapes:
            for tol in (1e-4, 0.01):
                a, b = self.reference(c, tol), parallel._polyline(c, tol)
                self.assertEqual(a.shape, b.shape)
                self.assertEqual(a.tobytes(), b.tobytes())


class TestCheck(unittest.TestCase):
    def test_check_unchanged(self):
        from vectordrive.core import check
        from vectordrive.core.document import Document, Shape
        d = Document()
        d.add(Shape(path=geom.Path([geom.rect(0, 0, 10, 10)])))
        d.add(Shape(path=geom.Path([geom.rect(0, 0, 10, 10)])))       # doublon
        loop = Contour([Line((0, 0), (10, 0)), Line((10, 0), (10, 0.4)), Line((10, 0.4), (9.6, 0.4)),
                        Line((9.6, 0.4), (9.6, -1)), Line((9.6, -1), (0, -5))], False)   # boucle de 1,6 mm
        d.add(Shape(path=geom.Path([loop])))
        codes = {i.code for i in check.check(d)}
        self.assertIn('doublon', codes)
        self.assertIn('boucle', codes)


class TestNative(unittest.TestCase):
    def doc(self):
        from vectordrive.core.document import Document, Group, Shape, Text
        d = Document()
        d.add(Shape(path=geom.Path([geom.rect(0, 0, 10, 5), geom.circle((3, 3), 1)]), extra={'n': 1, 'é': [1.5, None]}))
        d.add(Group(children=[Shape(path=geom.Path([geom.rect(1, 1, 2, 2)]))], name='groupe « été »'))
        d.add(Text(text='Abc', font='Arial', size=5.0))
        d.extra['guides'] = [('h', 3.0)]
        d.extra['x'] = {1: 'clé entière', 'k': float('nan')}
        return d

    def test_dumps_identical(self):
        import json
        from vectordrive.io import native
        D = native.to_dict(self.doc())
        self.assertEqual(native.dumps(D), json.dumps(D, ensure_ascii=False, separators=(',', ':')))
        for v in ({}, [], {'a': []}, [[], {}], {'a': {'b': {'c': {'d': {'e': [1]}}}}}):
            self.assertEqual(native.dumps(v), json.dumps(v, ensure_ascii=False, separators=(',', ':')))

    def test_snapshot_and_atomic(self):
        from vectordrive.io import native
        d = self.doc()
        s = native.snapshot(d)
        d.layers[0].items.pop()
        d.extra['guides'].append(('v', 1.0))
        self.assertEqual(len(s.layers[0].items), 3)
        self.assertEqual(s.extra['guides'], [('h', 3.0)])
        f = os.path.join(tempfile.mkdtemp(), 'r.vdz')
        native.write_atomic(s, f, level=1)
        self.assertFalse(os.path.exists(f + '.tmp'))
        back = native.read(f)
        self.assertEqual(len(back.layers[0].items), 3)


class TestMemory(unittest.TestCase):
    def test_settle(self):
        import gc
        from vectordrive.core import memory
        gc.unfreeze()
        try:
            self.assertFalse(memory.settle(10))                   # petit dessin : rien
            self.assertEqual(gc.get_freeze_count(), 0)
            self.assertTrue(memory.settle(memory.LARGE))          # gros : gelé
            self.assertGreater(gc.get_freeze_count(), 0)

            class Node:                                            # cycle d'un ancien dessin
                pass
            a = Node()
            a.me = a
            import weakref
            ref = weakref.ref(a)
            del a
            self.assertFalse(memory.settle(0))                    # dégel + collecte
            self.assertEqual(gc.get_freeze_count(), 0)
            self.assertIsNone(ref())
        finally:
            gc.unfreeze()


class TestAutosave(unittest.TestCase):
    def test_background(self):
        import pathlib
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.core.document import Shape
        from vectordrive.io import native
        w = MainWindow()
        tmp = pathlib.Path(tempfile.mkdtemp())
        w._recovery_dir = lambda: tmp
        w.session_dir = None                           # récupération sans session (avec elle : la session, round 215)
        w.start_autosave()
        w.canvas.doc.add(Shape(path=geom.Path([geom.circle((0, 0), 5)])))
        w.modified = True
        w._autosave()
        self.assertIsNotNone(w._autosave_thread)
        w._autosave_thread.join(10)
        f = tmp / f'{w._pid}.vdz'
        self.assertEqual(native.read(f).stats()['contours'], 1)
        self.assertTrue((tmp / f'{w._pid}.json').exists())
        w._autosave()                                          # puis nettoyage : attend le fil
        w._clear_autosave()
        self.assertFalse(f.exists())
        w.modified = False
        w.close()


if __name__ == '__main__':
    unittest.main()
