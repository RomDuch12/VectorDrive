"""Round 261 : retouches de relief TypeArt — recalage en Z, ajustement
dynamique, ajuster au volume, inverser, trancher, rehausser les détails,
bas-relief, remplir les trous, matrice/poinçon, adapter à un outil ; dans
une zone choisie ou partout."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from vectordrive.core import galbe as GB, geom, relief_ops as R
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


def block():
    """Carré de 10 mm, 3 mm de haut, avec une cuvette de 1 mm au centre (pas 0,1)."""
    H = np.zeros((200, 200))
    H[50:150, 50:150] = 3.0
    H[95:105, 95:105] = 1.0
    return H


class TestOps(unittest.TestCase):
    def test_levels(self):
        H = block()
        self.assertAlmostEqual(float(R.z_align(H, 'haut', 0.0).max()), 0.0)
        self.assertAlmostEqual(float(R.z_align(H, 'milieu', 0.0).min()), -1.5)
        self.assertAlmostEqual(float(R.z_align(H, 'valeur', 5.0, 1.0)[100, 100]), 5.0)
        d = R.dynamic(H, 6.0, 1.0)
        self.assertAlmostEqual(float(d.max()), 6.0)
        self.assertAlmostEqual(float(d[100, 100]), 2.0)                          # linéaire
        self.assertGreater(float(R.dynamic(H, 6.0, 0.5)[100, 100]), 2.0)        # γ < 1 : relève le bas
        v = R.to_volume(H, 1.0, 2.0)
        self.assertEqual((float(v.min()), float(v.max())), (1.0, 2.0))
        self.assertEqual(float(R.invert(H).min()), -3.0)
        s = R.slice_(H, 1.0, 2.0)
        self.assertEqual((float(s.min()), float(s.max())), (0.0, 1.0))

    def test_filters(self):
        H = block()
        F = R.fill_holes(H)
        self.assertEqual(float(F[100, 100]), 3.0)                                # cuvette comblée
        self.assertEqual(float(F[10, 10]), 0.0)                                  # le fond ouvert reste
        b = R.blur(H, 5)
        self.assertAlmostEqual(float(b.mean()), float(H.mean()), 2)
        r = R.raise_detail(H, 0.1, 1.0, 1.0)
        self.assertGreater(float(r[50, 100]), 3.0)                               # arête accentuée
        br = R.bas_relief(H, 0.1, 1.0)
        self.assertAlmostEqual(float(br.max() - br.min()), 1.0, 1)

    def test_punch_and_tool(self):
        from vectordrive.cam.model import CamTool
        H = block()
        punch, die = R.punch_die(H, 0.1, 0.2)
        self.assertTrue(np.array_equal(punch, H))
        self.assertEqual(float(die.max()), 0.0)                                  # fond de la matrice à 0
        self.assertAlmostEqual(float(die.min()), -3.0, 6)
        self.assertGreater(int((die < -2.9).sum()), int((H > 2.9).sum()))       # élargie du jeu
        v = CamTool(name='V', kind='conique', diameter=6, angle=30, tip=0.2)
        A = R.adapt_to_tool(H, 0.1, v)
        self.assertTrue((A >= H - 1e-9).all())                                   # jamais sous le relief
        self.assertGreater(float(A[100, 45]), 0.5)                               # paroi dépouillée
        self.assertGreater(float(A[100, 100]), 1.0)                              # cuvette trop fine : comblée


class TestWindow(unittest.TestCase):
    def test_ops_on_selection_and_zone(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            img = GB.encode(block(), 0.0, 20.0, 0.1, GB.GalbeSpec())
            zone = Shape(path=geom.Path([geom.rect(0, 0, 10, 20)]))                 # moitié gauche
            c.doc.add(img)
            c.doc.add(zone)
            c.select([img, zone])
            new = w.relief_op('relief_invert', {})
            H, *_ = GB.decode(new)
            self.assertAlmostEqual(float(H[100, 60]), -3.0, 3)                   # inversé à gauche
            self.assertAlmostEqual(float(H[100, 140]), 3.0, 3)                   # intact à droite
            c.select([new])
            die = w.relief_op('relief_punch', {'kind': 'les_deux', 'offset': 0.0})
            self.assertEqual(die.name, 'Matrice')
            self.assertIn(new, c.doc.layers[0].items)                            # le poinçon reste
            c.select([])
            self.assertIsNone(w.relief_op('relief_fill', {}))
            from vectordrive.ui import shortcuts as SC
            self.assertEqual(SC.TE_ACTIONS['ID_TART_FILLHOLES'], 'relief_fill')
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
