"""Round 735 : relèvements dans les calculs (d'après CADCraft) — « N45°E »,
« S30d15'W », un point cardinal seul, en degrés depuis l'est, sens
trigonométrique."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core.calc import bearing, evaluate


class TestBearings(unittest.TestCase):
    def test_cardinals(self):
        self.assertEqual([evaluate(t) for t in ('E', 'N', 'W', 'S', ' n ', 'w')], [0, 90, 180, 270, 90, 180])

    def test_bearings(self):
        for t, v in (('N45E', 45), ('N45°E', 45), ('n45de', 45), ('N30W', 120), ('S30E', 300), ('S30°W', 240),
                     ("S30d15'W", 239.75), ('N 12,5 W', 102.5), ('N0E', 90), ('N90E', 0), ('S90W', 180),
                     ('N45°30\'36"E', 44.49), ('N45d30′E', 44.5)):
            self.assertAlmostEqual(evaluate(t), v, 2, t)

    def test_not_a_bearing(self):
        self.assertIsNone(bearing('2*45'))
        self.assertIsNone(bearing('NE'))                        # pas d'angle : refusé comme le reste
        self.assertAlmostEqual(evaluate("30°15'"), 30.25)       # les calculs restent
        self.assertAlmostEqual(evaluate('2,5cm'), 25)
        for t in ('N95E', 'NE', 'E1', 'N45'):
            with self.assertRaises(ValueError, msg=t):
                evaluate(t)

    def test_angle_field(self):
        from PySide6.QtWidgets import QApplication, QDoubleSpinBox
        app = QApplication.instance() or QApplication([])
        from vectordrive.ui.fields import calculate
        box = QDoubleSpinBox()
        box.setRange(-360, 360)
        self.assertEqual(calculate(box.lineEdit(), 'S30°W'), 240)
        self.assertEqual(box.value(), 240)
        del app


if __name__ == '__main__':
    unittest.main()
