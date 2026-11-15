"""Round 231 : champs de valeur — double-clic sélectionne toute la valeur,
virgule / point / point du pavé numérique acceptés comme séparateur décimal."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QEvent, QLocale, QPointF, Qt
from PySide6.QtGui import QDoubleValidator, QKeyEvent, QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDoubleSpinBox, QLineEdit, QSpinBox

app = QApplication.instance() or QApplication([])


def key(w, k, text, mods=Qt.KeyboardModifier.NoModifier):
    app.sendEvent(w, QKeyEvent(QEvent.Type.KeyPress, k, mods, text))


class TestNumericFields(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui import fields
        fields.install(app)

    def test_double_click_selects_all(self):
        sb = QDoubleSpinBox()
        sb.setDecimals(3)
        sb.setLocale(QLocale(QLocale.Language.French, QLocale.Country.France))
        sb.setValue(123.456)
        sb.show()
        QTest.qWait(10)
        le = sb.lineEdit()
        pos = QPointF(le.width() - 6, le.height() / 2)          # sur les décimales
        for t in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonDblClick):
            app.sendEvent(le, QMouseEvent(t, pos, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                                          Qt.KeyboardModifier.NoModifier))
        QTest.qWait(20)
        self.assertEqual(le.selectedText(), le.text())           # toute la valeur, pas seulement « 456 »
        sb.close()

    def test_comma_and_period_both_decimal(self):
        for lang in (QLocale(QLocale.Language.French, QLocale.Country.France),
                     QLocale(QLocale.Language.English, QLocale.Country.UnitedKingdom)):
            sb = QDoubleSpinBox()
            sb.setLocale(lang)
            sb.setDecimals(2)
            sb.setRange(0, 1000)
            sb.show()
            le = sb.lineEdit()
            le.selectAll()
            for k, txt in ((Qt.Key.Key_1, '1'), (Qt.Key.Key_2, '2'), (Qt.Key.Key_Period, '.'), (Qt.Key.Key_5, '5')):
                key(le, k, txt)
            sb.interpretText()
            self.assertAlmostEqual(sb.value(), 12.5, msg=lang.name())
            le.selectAll()
            for k, txt in ((Qt.Key.Key_3, '3'), (Qt.Key.Key_Comma, ','), (Qt.Key.Key_7, '7')):
                key(le, k, txt)
            sb.interpretText()
            self.assertAlmostEqual(sb.value(), 3.7, msg=lang.name())
            le.selectAll()
            for k, txt in ((Qt.Key.Key_4, '4'), (Qt.Key.Key_Period, '.'), (Qt.Key.Key_Period, '.'), (Qt.Key.Key_1, '1')):
                key(le, k, txt, Qt.KeyboardModifier.KeypadModifier)   # point du pavé numérique, pas deux fois
            sb.interpretText()
            self.assertAlmostEqual(sb.value(), 4.1, msg=lang.name())
            sb.close()

    def test_integer_box_ignores_decimal_point(self):
        sb = QSpinBox()
        sb.setRange(0, 100)
        sb.show()
        le = sb.lineEdit()
        le.selectAll()
        for k, txt in ((Qt.Key.Key_4, '4'), (Qt.Key.Key_Period, '.'), (Qt.Key.Key_2, '2')):
            key(le, k, txt)
        sb.interpretText()
        self.assertEqual(sb.value(), 42)
        sb.close()

    def test_plain_line_edit_with_validator(self):
        le = QLineEdit()
        le.setValidator(QDoubleValidator(0.0, 100.0, 3))
        le.setLocale(QLocale(QLocale.Language.French, QLocale.Country.France))
        le.show()
        for k, txt in ((Qt.Key.Key_2, '2'), (Qt.Key.Key_Period, '.'), (Qt.Key.Key_5, '5')):
            key(le, k, txt)
        self.assertEqual(le.text(), '2,5')                       # point tapé → virgule du poste
        le.close()
        other = QLineEdit()                                      # champ texte ordinaire : rien ne change
        other.show()
        for k, txt in ((Qt.Key.Key_A, 'a'), (Qt.Key.Key_Period, '.'), (Qt.Key.Key_B, 'b')):
            key(other, k, txt)
        self.assertEqual(other.text(), 'a.b')
        other.close()


if __name__ == '__main__':
    unittest.main()
