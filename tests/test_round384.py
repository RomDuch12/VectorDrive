"""Round 384 : calcul dans les champs de valeur (touche =, core.calc)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication, QDoubleSpinBox, QSpinBox

from vectordrive.core.calc import evaluate
from vectordrive.ui import fields

app = QApplication.instance() or QApplication([])


class TestCalc(unittest.TestCase):
    def test_evaluate(self):
        self.assertAlmostEqual(evaluate('25,4*3/2'), 38.1)
        self.assertAlmostEqual(evaluate('(120-2*5)/7'), 110 / 7)
        self.assertAlmostEqual(evaluate('sqrt(2)*10'), 14.142135623730951)
        self.assertAlmostEqual(evaluate('50*tan(45)'), 50.0)
        self.assertAlmostEqual(evaluate('2^3 + min(2, 5)'), 10.0)
        self.assertAlmostEqual(evaluate('pi*10'), 31.41592653589793)
        self.assertAlmostEqual(evaluate('-3 × 2 ÷ 4'), -1.5)
        for bad in ('__import__("os")', 'open("x")', '1/0', '', 'a+1', '10**1000', '(1).real'):
            with self.assertRaises(ValueError, msg=bad):
                evaluate(bad)

    def test_fields(self):
        d = QDoubleSpinBox()
        d.setRange(-1000, 1000)
        d.setDecimals(3)
        self.assertAlmostEqual(fields.calculate(d.lineEdit(), '10/4+1'), 3.5)
        self.assertAlmostEqual(d.value(), 3.5)
        i = QSpinBox()
        i.setRange(0, 100)
        fields.calculate(i.lineEdit(), '7*3')
        self.assertEqual(i.value(), 21)
        self.assertIsNone(fields.calculate(d.lineEdit(), 'x*2'))
        self.assertAlmostEqual(d.value(), 3.5)                       # valeur gardée si le calcul est refusé


if __name__ == '__main__':
    unittest.main()
