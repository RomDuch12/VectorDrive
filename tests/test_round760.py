"""Round 760 : BAT : les cotes de brut se lisent comme les autres, à tous les angles."""
import math
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import brut as BR
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Shape
from vectordrive.core.geom import Affine
from vectordrive.io import proof

app = QApplication.instance() or QApplication([])


def direction(deg):
    return math.cos(math.radians(deg)), math.sin(math.radians(deg))


class TestAngle(unittest.TestCase):
    def test_vertical_reads_upward_both_ways(self):
        self.assertAlmostEqual(proof.readable_angle(0, 1), 90)
        self.assertAlmostEqual(proof.readable_angle(0, -1), 90)

    def test_horizontal_both_ways(self):
        self.assertAlmostEqual(proof.readable_angle(1, 0), 0)
        self.assertAlmostEqual(abs(proof.readable_angle(-1, 0)), 0, places=6)

    def test_never_upside_down(self):
        for deg in range(-360, 361, 5):
            a = proof.readable_angle(*direction(deg))
            self.assertGreater(a, -90.0001, deg)
            self.assertLessEqual(a, 90.0001, deg)

    def test_same_line_same_angle(self):
        """Une cote se lit pareil, dans quelque sens que ses points soient donnés."""
        for deg in range(-85, 90, 5):
            self.assertAlmostEqual(proof.readable_angle(*direction(deg)), proof.readable_angle(*direction(deg + 180)),
                                   places=6)


class TestPage(unittest.TestCase):
    def angles(self, deg):
        """Angles employés pour écrire les cotes d'un brut tourné de `deg`."""
        s = Shape(path=geom.Path([geom.rect(20, 20, 20, 20)]))
        BR.make(s, 100, 40, cotes='brut')
        d = Document()
        d.plate = None
        d.layers = [Layer(name='A', items=[s.transformed(Affine.rotation(deg))])]
        got = []
        real = proof.readable_angle

        def spy(ux, uy):
            got.append(real(ux, uy))
            return got[-1]
        with mock.patch.object(proof, 'readable_angle', spy):
            proof.build(d, proof.ProofInfo(title_block=False, legend=False, prices=False))
        return got

    def test_written_angles(self):
        for deg in (0, 30, 90, 120, 180, 210, 270, 300):
            got = self.angles(deg)
            self.assertEqual(len(got), 2, deg)                                # largeur et hauteur passent bien par là
            for a in got:
                self.assertGreater(a, -90.0001, deg)
                self.assertLessEqual(a, 90.0001, deg)

    def test_straight_brut(self):
        self.assertEqual([round(a) for a in self.angles(0)], [0, 90])


if __name__ == '__main__':
    unittest.main()
