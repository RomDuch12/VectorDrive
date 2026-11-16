"""Round 1050 : réponse du 15/11 à la question 37 — plus de ↑ ↓ ni de molette pour changer une valeur ; les flèches
↑ ↓ passent d'un champ de valeur à l'autre en sélectionnant sa valeur, pour remplir un formulaire au clavier."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1050.ini'))

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QDoubleValidator, QWheelEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QLineEdit,  # noqa: E402
                               QPushButton, QScrollArea, QSpinBox, QTimeEdit, QVBoxLayout, QWidget)

from vectordrive.ui import fields  # noqa: E402

app = QApplication.instance() or QApplication([])


def wheel(w, dy=120):
    pos = QPointF(4, 5)
    QApplication.sendEvent(w, QWheelEvent(pos, QPointF(w.mapToGlobal(QPoint(4, 5))), QPoint(0, 0), QPoint(0, dy),
                                          Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                                          Qt.ScrollPhase.NoScrollPhase, False))


class Form(unittest.TestCase):
    """Profondeur, [nom], [case], Passe, [liste], Avance (ligne numérique), [bouton], Tours."""

    def setUp(self):
        fields.install()
        self.assertIsNotNone(getattr(fields, 'move_field', None), 'avant : ↑ ↓ changent la valeur du champ')
        self.w = QWidget()
        f = QFormLayout(self.w)
        self.depth, self.step, self.turns = QDoubleSpinBox(), QDoubleSpinBox(), QSpinBox()
        for d, v in ((self.depth, 3.0), (self.step, 0.5)):
            d.setRange(0, 100)
            d.setValue(v)
        self.turns.setRange(0, 60000)
        self.turns.setValue(24000)
        self.name = QLineEdit('Gravure')
        self.feed = QLineEdit('750')
        self.feed.setValidator(QDoubleValidator())
        self.combo = QComboBox()
        self.combo.addItems(['a', 'b', 'c'])
        self.rows = [self.depth, self.name, QCheckBox('x'), self.step, self.combo, self.feed, QPushButton('b'),
                     self.turns]
        for i, w in enumerate(self.rows):
            f.addRow(str(i), w)
        self.w.show()
        self.w.activateWindow()
        QTest.qWait(20)
        self.addCleanup(self.w.deleteLater)

    def focus(self):
        return QApplication.focusWidget()

    def on(self, field):
        return self.focus() is field or self.focus() is getattr(field, 'lineEdit', lambda: None)()

    def test_down_goes_to_the_next_value_field_selected(self):
        self.depth.setFocus()
        QTest.keyClick(self.focus(), Qt.Key.Key_Down)
        self.assertTrue(self.on(self.step), 'avant : ↓ changeait la valeur')   # le nom, la case : sautés
        self.assertEqual(self.depth.value(), 3.0)
        self.assertEqual(self.step.lineEdit().selectedText(), self.step.lineEdit().text())
        QTest.keyClick(self.focus(), Qt.Key.Key_Down)
        self.assertTrue(self.on(self.feed))                                    # une ligne numérique compte aussi
        self.assertEqual(self.feed.selectedText(), '750')
        QTest.keyClick(self.focus(), Qt.Key.Key_Down)
        self.assertTrue(self.on(self.turns))
        QTest.keyClick(self.focus(), Qt.Key.Key_Down)
        self.assertTrue(self.on(self.depth))                                   # après le dernier : le premier

    def test_up_goes_back(self):
        self.feed.setFocus()
        QTest.keyClick(self.focus(), Qt.Key.Key_Up)
        self.assertTrue(self.on(self.step))
        QTest.keyClick(self.focus(), Qt.Key.Key_Up)
        self.assertTrue(self.on(self.depth))
        self.assertEqual((self.depth.value(), self.step.value()), (3.0, 0.5))

    def test_the_typed_value_is_taken(self):
        self.depth.setFocus()
        self.depth.selectAll()
        QTest.keyClicks(self.focus(), '7')
        QTest.keyClick(self.focus(), Qt.Key.Key_Down)
        self.assertEqual(self.depth.value(), 7.0)                              # prise en quittant, comme avec Tab
        QTest.keyClicks(self.focus(), '2')                                     # la valeur sélectionnée : remplacée
        QTest.keyClick(self.focus(), Qt.Key.Key_Up)
        self.assertEqual(self.step.value(), 2.0)

    def test_page_keys_still_change_the_value(self):
        self.depth.setFocus()
        QTest.keyClick(self.focus(), Qt.Key.Key_PageUp)
        self.assertGreater(self.depth.value(), 3.0)
        self.assertTrue(self.on(self.depth))

    def test_a_text_field_and_a_list_keep_their_arrows(self):
        self.combo.setFocus()
        QTest.keyClick(self.combo, Qt.Key.Key_Down)
        self.assertEqual(self.combo.currentIndex(), 1)                         # une liste : ses flèches à elle
        self.name.setFocus()
        QTest.keyClick(self.name, Qt.Key.Key_Down)
        self.assertTrue(self.focus() is self.name)                             # (recherches : ↓ va dans leur liste)

    def test_a_single_field_keeps_its_value(self):
        solo = QDoubleSpinBox()
        solo.setValue(5.0)
        solo.show()
        self.addCleanup(solo.deleteLater)
        solo.activateWindow()
        solo.setFocus()
        QTest.qWait(10)
        QTest.keyClick(solo, Qt.Key.Key_Up)
        self.assertEqual(solo.value(), 5.0)                                    # pas d'autre champ : rien ne change

    def test_a_time_field_keeps_its_arrows(self):
        t = QTimeEdit()
        self.assertTrue(fields.keeps_arrows(t))
        d = QDoubleSpinBox()
        d.setProperty('vd_fleches', True)
        self.assertTrue(fields.keeps_arrows(d))
        self.assertFalse(fields.keeps_arrows(self.depth))


class Wheel(unittest.TestCase):

    def setUp(self):
        fields.install()
        self.assertIsNotNone(getattr(fields, 'move_field', None), 'avant : la molette change la valeur du champ')

    def test_the_wheel_never_changes_a_value(self):
        d = QDoubleSpinBox()
        d.setRange(0, 100)
        d.setValue(10.0)
        d.show()
        self.addCleanup(d.deleteLater)
        QTest.qWait(10)
        d.setFocus()
        wheel(d)
        wheel(d.lineEdit(), -120)
        self.assertEqual(d.value(), 10.0)
        self.assertNotEqual(d.focusPolicy(), Qt.FocusPolicy.WheelFocus)        # elle ne donne plus le focus

    def test_the_wheel_scrolls_the_form(self):
        area = QScrollArea()
        body = QWidget()
        lay = QVBoxLayout(body)
        spins = []
        for i in range(40):
            sp = QDoubleSpinBox()
            sp.setValue(i)
            spins.append(sp)
            lay.addWidget(sp)
        area.setWidget(body)
        area.resize(200, 150)
        area.show()
        self.addCleanup(area.deleteLater)
        QTest.qWait(20)
        self.assertEqual(area.verticalScrollBar().value(), 0)
        wheel(spins[1], -120)                                                  # la molette sur un champ
        self.assertGreater(area.verticalScrollBar().value(), 0)                # … fait défiler le formulaire
        self.assertEqual(spins[1].value(), 1.0)
        area.verticalScrollBar().setValue(0)
        area.activateWindow()
        spins[0].setFocus()
        QTest.qWait(10)
        for _ in range(25):                                                    # ↓ jusqu'à un champ hors de la vue
            QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Down)
        self.assertTrue(spins[25].hasFocus() or spins[25].lineEdit().hasFocus())
        self.assertGreater(area.verticalScrollBar().value(), 0)                # le formulaire a suivi
        self.assertFalse(spins[25].visibleRegion().isEmpty(), 'le champ atteint est hors de la vue')


if __name__ == '__main__':
    unittest.main()
