"""Round 252 : pièce STEP exploitable — placée comme sur la machine (face
tournée vers l'outil, rotation, position sur la plaque) ; le même placement
sert à la vue de dessus 2D, au modèle 3D et à l'usinage de surface 3D ;
le reste du dessin n'est pas touché, le placement s'annule."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
sys.path.insert(0, os.path.dirname(__file__))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


def box_file():
    from test_round130 import STEP_BOX                     # pavé 20 × 10 × 5
    f = os.path.join(tempfile.mkdtemp(), 'pave.stp')
    with open(f, 'w', encoding='ascii') as fh:
        fh.write(STEP_BOX)
    return f


class TestPlacement(unittest.TestCase):
    def test_faces_and_modes(self):
        import numpy as np
        from vectordrive.core import placement3d as P3
        for face, R in P3.FACES.items():
            self.assertAlmostEqual(abs(np.linalg.det(R)), 1.0, 9, face)
        p = P3.Placement('-Z', 0.0)
        self.assertEqual(p.apply([[1.0, 2.0, 3.0]]).tolist(), [[1.0, -2.0, -3.0]])
        p = P3.Placement('+Z', 90.0, 'libre', 5.0, 0.0)
        np.testing.assert_allclose(p.apply([[1.0, 0.0, 0.0]]), [[5.0, 1.0, 0.0]], atol=1e-12)
        b = (0.0, 0.0, 0.0, 20.0, 10.0, 5.0)
        self.assertEqual((P3.resolve(P3.Placement(mode='centre'), b, (0, 0, 100, 60)).dx,
                          P3.resolve(P3.Placement(mode='centre'), b, (0, 0, 100, 60)).dy), (40.0, 25.0))
        c = P3.resolve(P3.Placement(mode='coin'), b, (10, 10, 100, 60), margin=5)
        self.assertEqual((c.dx, c.dy), (15.0, 15.0))
        o = P3.resolve(P3.Placement(mode='origine'), b)
        self.assertEqual((o.dx, o.dy), (-10.0, -5.0))

    def test_2d_and_3d_agree(self):
        from vectordrive.core import placement3d as P3
        from vectordrive.io import model3d, step
        f = box_file()
        for pl in (P3.Placement('+X', 90.0), P3.Placement('-Z', 30.0, 'libre', 7.0, -3.0)):
            d = step.read(f, pl)
            m = model3d.load(f, pl)
            b2, b3 = d.bbox(), m.bounds()
            for a, b in zip(b2, (b3[0], b3[1], b3[3], b3[4])):
                self.assertAlmostEqual(a, b, 4)                         # modèle en float32
            self.assertTrue(all(it.extra.get('step') for L in d.layers for it in L.items))


class TestWindow(unittest.TestCase):
    def test_place_keeps_user_items_and_undo(self):
        from vectordrive.cam import advanced, model, strategies
        from vectordrive.core import geom, placement3d as P3
        from vectordrive.core.document import Plate, Shape
        from vectordrive.ui.main_window import MainWindow
        f = box_file()
        w = MainWindow()
        try:
            w.open_file(f) if hasattr(w, 'open_file') else w.open_path(f)
            doc = w.canvas.doc
            doc.plate = Plate(x=0, y=0, width=100, height=60)
            mine = Shape(path=geom.Path([geom.circle((90, 50), 3)]))
            doc.layers[0].items.append(mine)
            pl = w.place_model3d(placement=P3.Placement('-Z', 0.0, 'centre'))
            self.assertEqual((pl.dx, pl.dy), (40.0, 35.0))                    # retournée : Y inversé
            steps = [it for L in doc.layers for it in L.items if it.extra.get('step')]
            bb = geom.bbox_union(it.bbox() for it in steps) if hasattr(geom, 'bbox_union') else None
            if bb:
                self.assertAlmostEqual((bb[0] + bb[2]) / 2, 50.0, 6)       # centrée sur la plaque
            self.assertTrue(any(it is mine for L in doc.layers for it in L.items))   # le reste ne bouge pas
            self.assertEqual(P3.of(doc).face, '-Z')
            # usinage 3D : la pièce posée (retournée, centrée)
            s = model.CamSetup()
            t = model.CamTool(name='B2', kind='boule', diameter=2.0)
            s.tools = [t]
            tp = strategies.compute(doc, s, model.Operation(kind='surface3d', tool_id=t.id, depth=0.0,
                                                             resolution=0.5))
            xs = [m.x for m in tp.moves if m.kind != 'rapid']
            self.assertGreater(min(xs), 35.0)
            self.assertLess(max(xs), 65.0)
            w.undo()
            self.assertEqual(P3.of(doc).face, '+Z')
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
