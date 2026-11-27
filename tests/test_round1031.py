"""Round 1031 : demandes du 15/11 — « Jamais de flèches pour les champs de valeur dans toute l'appli » ; « Champ des
form de parcours outil : pas de flèche pas de "celle de l'outil" dans le champ et un click dans un champ sélectionne sa
valeur pour qu'elle soit prête à modifier » ; « Aide VD Développé par RomDuch with Claude romduch@gmail.com »."""
import inspect
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1031.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtGui import QDoubleValidator  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import (QAbstractSpinBox, QApplication, QDoubleSpinBox, QLabel, QLineEdit,  # noqa: E402
                               QSpinBox, QVBoxLayout, QWidget)

app = QApplication.instance() or QApplication([])

from vectordrive.cam import model  # noqa: E402
from vectordrive.i18n import tr  # noqa: E402
from vectordrive.ui import cam_panel as CP  # noqa: E402
from vectordrive.ui import fields  # noqa: E402

NO = QAbstractSpinBox.ButtonSymbols.NoButtons


def host(*widgets):
    w = QWidget()
    lay = QVBoxLayout(w)
    first = QLineEdit('ailleurs')                    # le focus est d'abord ici
    lay.addWidget(first)
    for x in widgets:
        lay.addWidget(x)
    w.show()
    QTest.qWait(20)
    first.setFocus()
    QTest.qWait(10)
    w.first = first
    return w


class NoArrows(unittest.TestCase):

    def setUp(self):
        fields.install()                             # comme au lancement (MainWindow)

    def test_value_fields_have_no_arrows(self):
        d, i = QDoubleSpinBox(), QSpinBox()
        d.setRange(0, 100)
        d.setValue(10.0)
        w = host(d, i)
        self.addCleanup(w.deleteLater)
        self.assertEqual(d.buttonSymbols(), NO)    # avant : les flèches ▲▼
        self.assertEqual(i.buttonSymbols(), NO)
        d.setFocus()
        QTest.keyClick(d, Qt.Key.Key_Up)             # ↑ ↓ : d'un champ à l'autre, plus la valeur (0.907.0)
        self.assertEqual(d.value(), 10.0)
        QTest.keyClick(d, Qt.Key.Key_PageUp)         # Page précédente la change toujours
        self.assertGreater(d.value(), 10.0)

    def test_in_the_operation_form(self):
        tool = model.CamTool(name='Cyl 2', diameter=2.0, feed=750.0, number=1)
        op = model.Operation(kind='poche', tool_id=tool.id)
        dlg = CP.FieldsDialog(None, 'essai', op, tools=[tool])
        self.addCleanup(dlg.deleteLater)
        dlg.show()
        QTest.qWait(30)
        spins = [w for w in dlg.widgets.values() if isinstance(w, QAbstractSpinBox)]
        self.assertTrue(spins)
        self.assertEqual([w for w in spins if w.buttonSymbols() != NO], [])


class ClickSelects(unittest.TestCase):

    def setUp(self):
        fields.install()

    def click(self, le):
        QTest.mouseClick(le, Qt.MouseButton.LeftButton, pos=QPoint(4, le.height() // 2))

    def test_a_click_selects_the_whole_value(self):
        d = QDoubleSpinBox()
        d.setDecimals(2)
        d.setRange(0, 1000)
        d.setValue(125.5)
        w = host(d)
        self.addCleanup(w.deleteLater)
        le = d.lineEdit()
        self.click(le)
        self.assertTrue(d.hasFocus() or le.hasFocus())
        self.assertEqual(le.selectedText(), le.text())          # avant : le curseur posé, rien de choisi
        QTest.keyClicks(d, '42')
        self.assertEqual(d.value(), 42.0)                       # prête à être remplacée
        self.click(le)                                          # déjà dedans : le clic place le curseur
        self.assertEqual(le.selectedText(), '')

    def test_focus_from_the_wheel_is_not_a_click(self):
        """Relecture : la molette donne le focus « souris » sans relâché ; le clic suivant place le curseur."""
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QWheelEvent
        d = QDoubleSpinBox()
        d.setRange(0, 1000)
        d.setValue(10.0)
        w = host(d)
        self.addCleanup(w.deleteLater)
        le = d.lineEdit()
        d.setFocus(Qt.FocusReason.MouseFocusReason)             # comme Qt le fait pour la molette
        QApplication.sendEvent(le, QWheelEvent(QPointF(4, 5), QPointF(le.mapToGlobal(QPoint(4, 5))), QPoint(0, 0),
                                               QPoint(0, 120), Qt.MouseButton.NoButton,
                                               Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False))
        self.click(le)
        self.assertEqual(le.selectedText(), '')

    def test_numeric_line_and_a_dragged_part(self):
        le = QLineEdit('3,75')
        le.setValidator(QDoubleValidator())
        w = host(le)
        self.addCleanup(w.deleteLater)
        self.click(le)
        self.assertEqual(le.selectedText(), '3,75')
        w.first.setFocus()                                      # sorti puis revenu en glissant sur une partie
        QTest.qWait(10)
        QTest.mousePress(le, Qt.MouseButton.LeftButton, pos=QPoint(2, le.height() // 2))
        le.setSelection(0, 1)
        QTest.mouseRelease(le, Qt.MouseButton.LeftButton, pos=QPoint(8, le.height() // 2))
        self.assertEqual(le.selectedText(), '3')                # la partie choisie est gardée

    def test_the_tool_value_is_selected_too(self):
        tool = model.CamTool(name='Cyl 2', diameter=2.0, feed=750.0, number=1)
        op = model.Operation(kind='poche', tool_id=tool.id)
        dlg = CP.FieldsDialog(None, 'essai', op, tools=[tool])
        self.addCleanup(dlg.deleteLater)
        dlg.show()
        QTest.qWait(30)
        feed = dlg.widgets['feed']
        le = feed.lineEdit()
        self.click(le)
        self.assertTrue(feed.hasFocus() or le.hasFocus())
        self.assertEqual(le.selectedText(), '750')              # la valeur de l'outil, prête à être remplacée


class ToolValueInTheField(unittest.TestCase):

    def test_only_the_value_and_its_unit(self):
        tool = model.CamTool(name='Cyl 2', diameter=2.0, feed=750.0, plunge=150.0, spindle=18000.0, step_down=0.3,
                             stepover=0.5, number=1)
        self.assertEqual(CP.tool_value_text('feed', tool), '750')               # round 1183 : sans « mm/min »
        self.assertEqual(CP.tool_value_text('spindle', tool), '18000')
        self.assertTrue(CP.tool_value_text('stepover_mm', tool).startswith('≈ 1 mm'))
        self.assertEqual(CP.tool_value_text('feed', None), '—')
        vee = model.CamTool(name='V 30', kind='conique', diameter=3.175, angle=30.0, stepover=0.4, feed=0.0, number=3)
        self.assertEqual(CP.tool_value_text('feed', vee), '—')
        self.assertEqual(CP.tool_value_text('stepover_mm', vee), tr('auto'))
        for t in (tool, vee, None):
            for name in CP.ZERO_IS_TOOL:
                self.assertNotIn('outil', CP.tool_value_text(name, t), name)

    def test_the_explanation_in_the_tooltip(self):
        tool = model.CamTool(name='Cyl 2', diameter=2.0, feed=750.0, number=1)
        op = model.Operation(kind='poche', tool_id=tool.id)
        dlg = CP.FieldsDialog(None, 'essai', op, tools=[tool])
        self.addCleanup(dlg.deleteLater)
        feed = dlg.widgets['feed']
        self.assertEqual(feed.specialValueText(), '750')
        self.assertIn(tr('{0} {1} (outil)').format('750', 'mm/min'), feed.toolTip())
        own = CP.FieldsDialog(None, 'essai', model.Operation(kind='poche', tool_id=tool.id, feed=999.0), tools=[tool])
        self.addCleanup(own.deleteLater)
        self.assertEqual(own.widgets['feed'].value(), 999.0)
        self.assertNotIn('outil', own.widgets['feed'].text())


class DevelopedBy(unittest.TestCase):

    def test_in_the_about_box(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        self.addCleanup(self.close, w)
        self.assertIsNone(w.ribbon.findChild(QLabel, 'creditLabel'))   # dans À propos seulement (round 1041)
        self.assertIn('Développé par RomDuch with Claude — romduch@gmail.com', inspect.getsource(MainWindow.about))

    def close(self, w):
        w.modified = False
        for t in getattr(w, 'docks', []):
            t.modified = False
        w.close()
        app.processEvents()


if __name__ == '__main__':
    unittest.main()
