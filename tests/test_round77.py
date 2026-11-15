"""Round 77 : Vérifier signale les petites boucles d'auto-intersection."""
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import check, geom
from vectordrive.core.document import Document, Shape
from vectordrive.core.geom import Contour, Line, Path


def looped():
    # trait qui fait une petite boucle de 1,5 mm avant de repartir
    return Contour([Line((0, 0), (10, 0)), Line((10, 0), (10, 0.5)), Line((10, 0.5), (9.5, 0.5)),
                    Line((9.5, 0.5), (9.5, -3))], False)


class TestLoops(unittest.TestCase):
    def test_small_loops(self):
        self.assertEqual(check.small_loops(looped()), 1)
        self.assertEqual(check.small_loops(geom.rect(0, 0, 5, 5)), 0)
        big8 = Contour([Line((0, 0), (20, 20)), Line((20, 20), (20, 0)), Line((20, 0), (0, 20)), Line((0, 20), (0, 0))], True)
        self.assertEqual(check.small_loops(big8), 0)                 # huit voulu : boucles de plus de 2 mm

    def test_check_and_fix(self):
        d = Document()
        sh = Shape(path=Path([looped()]))
        d.layers[0].items.append(sh)
        codes = {i.code: i for i in check.check(d)}
        self.assertIn('boucle', codes)
        self.assertTrue(codes['boucle'].fixable)
        fixed = check.fix_item(sh, 'boucle')
        self.assertEqual(check.small_loops(fixed.path.contours[0]), 0)
        self.assertAlmostEqual(fixed.path.contours[0].length(), 12.5, places=9)    # (0,0)→(9,5,0)→(9,5,−3)

    def test_texts_not_checked(self):
        from vectordrive.core import text as TX
        from vectordrive.core.document import Text
        d = Document()
        t = Text(text='BFM', font='Arial', size=5)
        t.outline = TX.outline_for(t)
        d.layers[0].items.append(t)
        self.assertNotIn('boucle', [i.code for i in check.check(d)])


if __name__ == '__main__':
    unittest.main()
