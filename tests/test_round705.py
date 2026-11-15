"""Round 705 : unités et fractions dans les calculs des champs (touche =) —
mm, cm, dm, m, in ou ", ft ou ', pt → mm ; fractions et pieds-pouces comme
en DAO (d'après CADCraft) ; degrés minutes secondes avec « ° »."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core.calc import evaluate


class TestUnits(unittest.TestCase):
    def test_lengths_in_mm(self):
        for text, mm in (('1in', 25.4), ('1"', 25.4), ('5 in', 127.0), ('1ft', 304.8), ("1'", 304.8),
                         ('2,5cm', 25.0), ('3dm', 300.0), ('1m-20cm', 800.0), ('10pt', 25.4 * 10 / 72),
                         ('12mm', 12.0), ('1e3mm', 1000.0), ('2*3in', 152.4), ('(1+1)*2mm', 4.0),
                         ('10mm+5', 15.0), ('1.5IN', 38.1)):
            self.assertAlmostEqual(evaluate(text), mm, msg=text)

    def test_fractions_and_feet_inches(self):
        for text, inches in (('3/4"', 0.75), ('6 1/2in', 6.5), ("1'6\"", 18.0), ("1'-6 1/2\"", 18.5),
                             ("1' 6\"", 18.0), ('1′6″', 18.0)):
            self.assertAlmostEqual(evaluate(text), inches * 25.4, msg=text)
        self.assertAlmostEqual(evaluate('2ft-6in'), (24 - 6) * 25.4)            # en toutes lettres : une soustraction

    def test_degrees_minutes_seconds(self):
        self.assertAlmostEqual(evaluate("30°15'"), 30.25)
        self.assertAlmostEqual(evaluate('45°30\'36"'), 45.51)
        self.assertAlmostEqual(evaluate('30°'), 30.0)
        self.assertAlmostEqual(evaluate('90°-30°15\''), 59.75)

    def test_refused(self):
        for bad in ('1/0in', '1 0/0"', 'in', '5min', '2em', 'm', '__import__("os")'):
            with self.assertRaises(ValueError, msg=bad):
                evaluate(bad)
        self.assertAlmostEqual(evaluate('min(2, 5)'), 2.0)                       # les fonctions restent
        self.assertAlmostEqual(evaluate('2^3 + min(2, 5)'), 10.0)


class TestField(unittest.TestCase):
    def test_calculation_in_a_field(self):
        from PySide6.QtWidgets import QApplication, QDoubleSpinBox
        QApplication.instance() or QApplication([])
        from vectordrive.ui.fields import calculate
        box = QDoubleSpinBox()
        box.setRange(0, 10000)
        box.setDecimals(3)
        self.assertAlmostEqual(calculate(box.lineEdit(), "1'-6 1/2\""), 469.9)
        self.assertAlmostEqual(box.value(), 469.9)


if __name__ == '__main__':
    unittest.main()
