"""Round 644 : trajectoires 3D recomposées — celles de chaque prise (pièce
retournée) et de chaque corps usiné seul ramenées sur la pièce posée comme
le dessin ; prise « toutes » de la vue 3D."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from tests.test_round596 import FakeDoc, two_boxes_stl
from vectordrive.cam import mill3d, model
from vectordrive.cam import reassemble as RA
from vectordrive.core import placement3d as P3

app = QApplication.instance() or QApplication([])


def verts(doc, path, face, body):
    m = mill3d.load_model(doc, path, face, body)
    t = np.asarray(m.triangles, np.float64).reshape(-1, 3)
    return t - [0.0, 0.0, float(m.bounds()[5])]                 # repère de la FAO : haut à Z 0


class TestTransform(unittest.TestCase):
    def setUp(self):
        self.path = two_boxes_stl()
        self.ref = verts(FakeDoc(self.path), self.path, '', -1)

    def check(self, doc, face, body):
        op = model.Operation(kind='surface3d', setup_face=face, body3d=body, model_path=self.path)
        A, b = RA.transform(doc, op)
        here = verts(doc, self.path, face, body)
        ref = verts(doc, self.path, '', -1)
        if body >= 0:
            ref = ref.reshape(-1, 3, 3)[mill3d.raw_model(self.path).body_ids() == body].reshape(-1, 3)
        np.testing.assert_allclose(here @ A.T + b, ref, atol=1e-4)   # chaque sommet retombe sur la pièce

    def test_faces_and_bodies(self):
        doc = FakeDoc(self.path)
        for face in ('-Z', '+X', '-Y'):
            self.check(doc, face, -1)
        for face, body in (('', 1), ('-Z', 0), ('+Y', 1)):
            self.check(doc, face, body)

    def test_drawing_placement(self):
        doc = FakeDoc(self.path, P3.Placement('+Z', 90.0, 'centre'), plate=type('P', (), dict(
            x=0.0, y=0.0, width=200.0, height=100.0))())
        self.check(doc, '-Z', -1)
        self.check(doc, '-X', 0)

    def test_same_setup_untouched(self):
        op = model.Operation(kind='surface3d', model_path=self.path)
        self.assertIsNone(RA.transform(FakeDoc(self.path), op))

    def test_reassemble(self):
        doc = FakeDoc(self.path)
        down = model.Operation(kind='surface3d', setup_face='-Z', model_path=self.path)
        same = model.Operation(kind='surface3d', model_path=self.path)
        lost = model.Operation(kind='surface3d', setup_face='-Z', model_path=os.path.join(tempfile.mkdtemp(), 'x.stl'))
        tp = model.Toolpath(down.id, 't', [model.Move('rapid', 5, 3, 5), model.Move('feed', 5, 3, 0),
                                          model.Move('arc_ccw', 7, 5, 0, cx=7, cy=3)], name='dessous')
        keep = model.Toolpath(same.id, 't', [model.Move('feed', 1, 1, -1)])
        gone = model.Toolpath(lost.id, 't', [model.Move('feed', 1, 1, -1)])
        out = RA.reassemble(doc, [tp, keep, gone], [down, same, lost])
        self.assertEqual(len(out), 2)                                          # pièce illisible : laissée
        self.assertIs(out[1], keep)
        r = out[0]
        self.assertEqual(r.name, 'dessous')
        self.assertFalse(any(m.is_arc for m in r.moves))                      # arc aplati
        self.assertGreater(len(r.moves), 10)
        A, b = RA.transform(doc, down)
        np.testing.assert_allclose([r.moves[1].x, r.moves[1].y, r.moves[1].z], A @ [5, 3, 0] + b, atol=1e-9)
        self.assertAlmostEqual(r.moves[1].z, -6.0)                            # le dessus de la prise : le dessous
        self.assertEqual(len(tp.moves), 3)                                     # l'original intact


class TestView(unittest.TestCase):
    def test_all_setups(self):
        from vectordrive.ui import view3d as V3
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            path = two_boxes_stl()
            w.open_path(path)
            cp = w.cam_panel
            w._ensure_panel3d()
            p = w.panel3d
            p.refresh()
            s = cp.setup()
            down = model.Operation(kind='surface3d', setup_face='-Z', body3d=1)
            top = model.Operation(kind='surface3d')
            s.operations += [down, top]
            cp.save(s)
            tps = [model.Toolpath(down.id, '', [model.Move('feed', 45, 5, 0)], name='a'),
                   model.Toolpath(top.id, '', [model.Move('feed', 5, 5, 0)], name='b')]
            cp.checked_paths = lambda: list(tps)
            p.refresh()
            self.assertGreaterEqual(p.setup_view.findData(V3.ALL_SETUPS), 0)
            p.setup_view.setCurrentIndex(p.setup_view.findData('-Z|1'))
            self.assertEqual([t.name for t in p.view.model_paths], ['a'])      # la prise seule
            p.setup_view.setCurrentIndex(p.setup_view.findData(V3.ALL_SETUPS))
            self.assertTrue(p.all_setups())
            self.assertEqual(p.current_setup(), ('', -1))
            got = {t.name: t for t in p.view.model_paths}
            self.assertEqual(set(got), {'a', 'b'})                              # toutes
            self.assertIs(got['b'], tps[1])
            self.assertAlmostEqual(got['a'].moves[0].z, -6.0 + 0.0, places=4)   # dessous du corps (4 de haut)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
