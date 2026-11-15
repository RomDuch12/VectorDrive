"""Round 976 : la molette ne change pas une liste déroulante au simple survol ; l'événement remonte au panneau, qui
défile ; les autres champs (nombres) et la liste dépliée ne sont pas touchés."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r976.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QWheelEvent  # noqa: E402
from PySide6.QtWidgets import (QApplication, QComboBox, QFontComboBox, QScrollArea, QSpinBox, QVBoxLayout,  # noqa: E402
                               QWidget)

app = QApplication.instance() or QApplication([])


def wheel(widget, steps=-1):
    """Un cran de molette (vers le bas) adressé au widget, par le chemin des vrais événements."""
    pos = QPointF(widget.rect().center())
    ev = QWheelEvent(pos, QPointF(widget.mapToGlobal(pos.toPoint())), QPoint(0, 0), QPoint(0, 120 * steps),
                     Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(widget, ev)
    return ev.isAccepted()


class ComboWheel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def panel(self):
        area = QScrollArea()
        inner = QWidget()
        lay = QVBoxLayout(inner)
        combo, fonts, spin = QComboBox(), QFontComboBox(), QSpinBox()
        combo.addItems(['un', 'deux', 'trois'])
        for x in (combo, fonts, spin):
            lay.addWidget(x)
        for _ in range(40):
            lay.addWidget(QComboBox())
        area.setWidget(inner)
        area.resize(300, 200)
        area.show()
        app.processEvents()
        return area, combo, fonts, spin

    def test_the_wheel_leaves_a_hovered_list_alone(self):
        area, combo, fonts, spin = self.panel()
        self.addCleanup(area.close)
        font_before = fonts.currentIndex()
        taken = wheel(combo)
        self.assertEqual(combo.currentIndex(), 0)                    # avant : passait à « deux »
        self.assertFalse(taken)                                      # refusé : Qt le propose au panneau, qui défile
        self.assertFalse(wheel(fonts))
        self.assertEqual(fonts.currentIndex(), font_before)

    def test_numbers_and_the_open_list_still_follow_the_wheel(self):
        from vectordrive.ui import wheelguard
        self.assertIs(wheelguard.install(app), wheelguard.install(app))      # posé une fois
        area, combo, _fonts, spin = self.panel()
        self.addCleanup(area.close)
        spin.setValue(5)
        wheel(spin, steps=1)
        self.assertEqual(spin.value(), 6)                            # un champ de nombre garde la molette
        combo.showPopup()
        app.processEvents()
        view = combo.view()
        self.assertTrue(view.isVisible())
        guard = wheelguard.install(app)
        ev = QWheelEvent(QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(0, -120), Qt.MouseButton.NoButton,
                         Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
        self.assertFalse(guard.eventFilter(view.viewport(), ev))     # la liste dépliée : pas filtrée
        self.assertTrue(guard.eventFilter(combo, ev))
        combo.hidePopup()


if __name__ == '__main__':
    unittest.main()
