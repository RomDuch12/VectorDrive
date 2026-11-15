"""Round 731 : analyse de surface de la pièce 3D — dépouille des faces vers
une direction de démoulage, faces atteintes le long d'une direction —
d'après SolidCraft."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np

from vectordrive.core import analysis3d as AN
from vectordrive.core import solids as SO
from vectordrive.core.geom import Path, rect


def _mushroom():
    """Un pied 10 × 10 × 20 sous un plateau 40 × 30 × 5 qui le déborde."""
    return SO.boolean('union', [SO.box(15, 10, 0, 10, 10, 20), SO.box(0, 0, 20, 40, 30, 5)])


class TestDraft(unittest.TestCase):
    def test_angles_and_classes(self):
        tri = np.array([[[0, 0, 0], [1, 0, 0], [0, 1, 0]],                      # dessus
                        [[0, 0, 0], [0, 1, 0], [1, 0, 0]],                      # dessous
                        [[0, 0, 0], [1, 0, 0], [0, 0, 1]]], dtype=float)        # paroi
        self.assertEqual(np.round(AN.draft_angles(tri, 'z+'), 6).tolist(), [90.0, -90.0, 0.0])
        self.assertEqual(AN.draft_classes(tri, 'z+', 1).tolist(), [0, 2, 1])
        self.assertEqual(AN.draft_classes(tri, 'z-', 1).tolist(), [2, 0, 1])
        self.assertEqual(AN.draft_classes(tri, 'y-', 1).tolist(), [1, 1, 0])
        self.assertEqual(AN.draft_classes(tri, 'z+', 0).tolist(), [0, 2, 0])  # 0° : une paroi suffit
        with self.assertRaises(ValueError):
            AN.unit((0, 0, 0))

    @unittest.skipUnless(SO.available(), 'manifold3d absent')
    def test_tapered(self):
        tap = SO.extrude(Path([rect(0, 0, 40, 30)]), 10, taper_deg=3).triangles()
        self.assertEqual(sorted(set(np.round(AN.draft_angles(tap), 3).tolist())), [-90.0, 3.0, 90.0])
        sh = AN.area_shares(tap, AN.draft_classes(tap, 'z+', 1), 3)
        self.assertAlmostEqual(sum(sh), 1.0, places=9)
        self.assertEqual(sh[1], 0.0)                                       # flancs à 3° : assez
        self.assertGreater(AN.area_shares(tap, AN.draft_classes(tap, 'z+', 5), 3)[1], 0.3)   # 5° demandés


class TestAccess(unittest.TestCase):
    def test_subdivide(self):
        tri = np.array([[[0, 0, 0], [10, 0, 0], [0, 4, 0]]], dtype=float)
        sub, parent = AN.subdivide(tri, 1.0)
        self.assertTrue(set(parent.tolist()) == {0} and len(sub) > 16)
        _n, a = AN.normals(sub)
        self.assertAlmostEqual(a.sum(), 20.0, places=9)                    # même aire
        self.assertTrue(np.allclose(AN.normals(sub)[0], [0, 0, 1]))        # même sens
        self.assertLessEqual(np.linalg.norm(np.roll(sub, -1, axis=1) - sub, axis=2).max(), 1.0 + 1e-9)
        self.assertEqual(len(AN.subdivide(tri, 1.0, max_tris=5)[0]), 4)    # plafond

    @unittest.skipUnless(SO.available(), 'manifold3d absent')
    def test_overhang(self):
        sub, _p = AN.subdivide(_mushroom().triangles(), 0.8)
        hidden = (40 * 30 - 100) + 4 * 10 * 20 + 100                       # dessous du plateau, pied
        total = 2 * (40 * 30 + 40 * 5 + 30 * 5) + 4 * 10 * 20
        top = AN.area_shares(sub, AN.access_classes(sub, 'z+'), 2)
        self.assertAlmostEqual(top[1], hidden / total, delta=0.01)
        below = AN.area_shares(sub, AN.access_classes(sub, 'z-'), 2)
        self.assertAlmostEqual(below[0], (100 + 1100 + 800 + 700) / total, delta=0.01)
        box = SO.box(0, 0, 0, 10, 10, 10).triangles()
        self.assertEqual(AN.area_shares(box, AN.access_classes(box, 'x+'), 2), [5 / 6, 1 / 6])
        self.assertEqual(len(AN.access_classes(np.zeros((0, 3, 3)))), 0)


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        cls.w.resize(1000, 700)

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def test_action(self):
        w = self.w
        self.assertEqual(w.solid_analysis({'mode': 'depouille', 'direction': 'z+', 'angle': 1}), [])   # rien
        w.set_view_mode('2d')
        w._add_items([SO.make_shape(_mushroom())])
        sh = w.solid_analysis({'mode': 'depouille', 'direction': 'z+', 'angle': 1})
        v = w.panel3d.view
        self.assertEqual(len(sh), 3)
        self.assertAlmostEqual(sum(sh), 1.0, places=6)
        self.assertEqual(v.analysis, ('depouille', 'z+', 1.0))
        self.assertNotEqual(v.display, 'filaire')
        shown, keep = v.shown_model()
        self.assertIsNone(keep)
        gap = np.abs(np.asarray(shown.colors)[:, None, :] - np.array(AN.DRAFT_COLORS)[None]).max(axis=2).min(axis=1)
        self.assertLess(gap.max(), 1e-6)                                   # couleurs de l'analyse seules
        self.assertIn('%', w.panel3d.info.text())
        sh = w.solid_analysis({'mode': 'acces', 'direction': 'z+', 'angle': 1})
        self.assertEqual(len(sh), 2)
        shown, keep = v.shown_model()
        self.assertEqual(len(keep), len(shown.triangles))                 # morceaux → triangle d'origine
        self.assertGreater(len(shown.triangles), len(v.model.triangles))
        self.assertTrue(np.all(keep < len(v.model.triangles)))
        self.assertIs(v.shown_model()[1], keep)                            # gardée en cache
        self.assertEqual(w.solid_analysis({'mode': 'aucune', 'direction': 'z+', 'angle': 1}), [])
        self.assertIsNone(v.analysis)
        self.assertIsNone(v.shown_model()[1])
        w.set_view_mode('2d')

    def test_ribbon_icon(self):
        from vectordrive.ui import icons
        self.assertIn('draft_analysis', icons.ICONS)
        self.assertFalse(self.w.A['solid_analysis'].icon().isNull())
        self.assertTrue(self.w.A['solid_analysis'].toolTip())


if __name__ == '__main__':
    unittest.main()
