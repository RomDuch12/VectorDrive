"""Round 1181 (demande du 27/11) : « mode point K selectionner toute la valeur du champ; » — K (Congé, raccourcis
TypeEdit ; Alt+K : Chanfrein) ouvre la fenêtre des congés le rayon au focus, toute sa valeur sélectionnée : la valeur
tapée le remplace, Entrée valide. Généralisé à l'ouverture des fenêtres de dialogue de l'application : leur premier
champ de saisie, sélectionné, quand elles n'ont pas choisi elles-mêmes leur champ.

Aucune vraie boîte bloquante : chaque `exec` est lu puis fermé par un QTimer (frappe et Entrée simulées)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'rfield.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ.setdefault('VECTORDRIVE_KEYS_MEMORY', '1')

from PySide6.QtCore import QEvent, Qt, QTimer  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import (QAbstractSpinBox, QApplication, QComboBox, QDialog, QDialogButtonBox,  # noqa: E402
                               QDoubleSpinBox, QFormLayout, QInputDialog, QLineEdit, QMessageBox, QSpinBox, QWidget)

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : la valeur du champ n’est pas sélectionnée à l’ouverture'


def selected(w) -> str:
    """Le texte sélectionné du champ `w` (numérique : dans sa ligne de saisie)."""
    le = w.lineEdit() if isinstance(w, QAbstractSpinBox) else w
    return le.selectedText()


def run_modal(start, look):
    """Lance `start()` (qui ouvre une fenêtre modale) ; `look(fenêtre)` y est appelé à l'ouverture, puis la fenêtre est
    fermée si elle ne l'est pas. Le résultat de `look` est rendu."""
    out = []

    def tick():
        m = QApplication.activeModalWidget()
        if m is None:
            QTimer.singleShot(10, tick)
            return
        try:
            out.append(look(m))
        finally:
            if m.isVisible():
                m.reject()
    QTimer.singleShot(0, tick)
    start()
    return out[0] if out else None


def without_filter(case) -> None:
    """Retire le filtre des champs de l'application pendant l'essai `case` (reposé ensuite)."""
    from vectordrive.ui import fields
    filt = fields._FILTER
    if filt is not None:
        app.removeEventFilter(filt)
        case.addCleanup(app.installEventFilter, filt)


class FakeShow:
    """Un événement d'ouverture lu par le filtre ; `spontaneous` : venu du système (fenêtre réduite qui revient)."""

    def __init__(self, spontaneous: bool):
        self._sp = spontaneous

    def type(self):
        return QEvent.Type.Show

    def spontaneous(self) -> bool:
        return self._sp


class Form(QDialog):
    """Une petite fenêtre de saisie de l'application : rayon, puis nom."""

    def __init__(self, parent=None, first=None):
        super().__init__(parent)
        form = QFormLayout(self)
        if first is not None:
            form.addRow('choix', first)
        self.spin = QDoubleSpinBox()
        self.spin.setRange(-1000, 1000)
        self.spin.setDecimals(3)
        self.spin.setSuffix(' mm')
        self.spin.setValue(12.5)
        self.name = QLineEdit('piece')
        form.addRow('Rayon', self.spin)
        form.addRow('Nom', self.name)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)


class Corner(unittest.TestCase):
    """K et Alt+K : la fenêtre des congés et des chanfreins."""

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.canvas.doc.modified = False
        cls.w.modified = False
        cls.w.close()
        cls.w.deleteLater()
        app.processEvents()

    def setUp(self):
        for k in ('coins/fillet', 'coins/chamfer'):
            self.w.settings.remove(k)
            self.addCleanup(self.w.settings.remove, k)

    def _type_and_enter(self, kind, text):
        """`corner_dialog(kind)` (K, Alt+K) : à l'ouverture, ce qui a le focus et ce qui est sélectionné ; puis
        `text` tapé, Entrée."""
        from vectordrive.ui.dialogs import CornerDialog
        seen = {}

        def look(dlg):
            self.assertIsInstance(dlg, CornerDialog)
            fw = dlg.focusWidget()
            seen['focus'] = fw is dlg.size
            seen['sel'] = selected(dlg.size)
            seen['text'] = dlg.size.cleanText()
            QTest.keyClicks(fw if fw is not None else dlg, text)
            QTest.keyClick(fw if fw is not None else dlg, Qt.Key.Key_Return)
            return seen
        run_modal(lambda: self.w.corner_dialog(kind), look)
        return seen

    def test_fillet_value_selected_typing_replaces(self):
        self.w.settings.setValue('coins/fillet', 2.0)
        seen = self._type_and_enter('fillet', '5')
        self.assertTrue(seen.get('focus'), BEFORE)
        self.assertEqual(seen['sel'], seen['text'], BEFORE)          # toute la valeur, sans « mm »
        self.assertTrue(seen['sel'])
        self.assertAlmostEqual(float(self.w.settings.value('coins/fillet')), 5.0, msg=BEFORE)   # 5 a remplacé 2

    def test_chamfer_value_selected_typing_replaces(self):
        self.w.settings.setValue('coins/chamfer', 1.5)
        seen = self._type_and_enter('chamfer', '3')
        self.assertTrue(seen.get('focus'), BEFORE)
        self.assertEqual(seen['sel'], seen['text'], BEFORE)
        self.assertAlmostEqual(float(self.w.settings.value('coins/chamfer')), 3.0, msg=BEFORE)

    def test_dialog_alone_selects_too(self):
        """Sans le filtre de l'application (retiré pendant l'essai) : la fenêtre elle-même sélectionne le rayon."""
        from vectordrive.ui.dialogs import CornerDialog
        without_filter(self)
        host = QWidget()
        self.addCleanup(host.deleteLater)
        for kind in ('fillet', 'chamfer'):
            dlg = CornerDialog(host, kind, 4.25)
            seen = run_modal(dlg.exec, lambda d: (d.focusWidget() is d.size, selected(d.size), d.size.cleanText()))
            self.assertTrue(seen[0], BEFORE)
            self.assertEqual(seen[1], seen[2], BEFORE)
            dlg.deleteLater()


class Generic(unittest.TestCase):
    """Les autres fenêtres de dialogue de l'application (filtre posé au lancement)."""

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui import fields
        fields.install()                                  # comme au lancement (MainWindow)
        cls.host = QWidget()

    @classmethod
    def tearDownClass(cls):
        cls.host.deleteLater()
        app.processEvents()

    def test_helper_exists(self):
        from vectordrive.ui import fields
        self.assertTrue(hasattr(fields, 'select_first_field'), BEFORE)

    def test_first_value_field_selected(self):
        dlg = Form(self.host)
        seen = run_modal(dlg.exec, lambda d: (d.focusWidget() is d.spin, selected(d.spin), d.spin.cleanText()))
        self.assertTrue(seen[0], BEFORE)
        self.assertEqual(seen[1], seen[2], BEFORE)

    def test_plain_qdialog_built_inline(self):
        """Une fenêtre bâtie sur place (`QDialog(self)` + formulaire) : de même."""
        dlg = QDialog(self.host)
        form = QFormLayout(dlg)
        spin = QSpinBox()
        spin.setRange(0, 999)
        spin.setValue(42)
        form.addRow('Nombre', spin)
        seen = run_modal(dlg.exec, lambda d: (d.focusWidget() is spin, selected(spin)))
        self.assertEqual(seen, (True, '42'), BEFORE)

    def test_first_text_field_selected(self):
        dlg = QDialog(self.host)
        form = QFormLayout(dlg)
        name = QLineEdit('Programme 1')
        form.addRow('Nom', name)
        seen = run_modal(dlg.exec, lambda d: (d.focusWidget() is name, name.selectedText()))
        self.assertEqual(seen, (True, 'Programme 1'), BEFORE)

    def test_typing_replaces_and_enter_accepts(self):
        dlg = Form(self.host)

        def look(d):
            target = d.focusWidget() or d                  # (avant : aucun champ au focus)
            QTest.keyClicks(target, '7')
            QTest.keyClick(target, Qt.Key.Key_Return)
            return d.result()
        res = run_modal(dlg.exec, look)
        self.assertAlmostEqual(dlg.spin.value(), 7.0, msg=BEFORE)
        self.assertEqual(res, QDialog.DialogCode.Accepted)

    def test_dialog_that_chose_its_field_is_kept(self):
        """La fenêtre a donné le focus à un autre champ avant de s'ouvrir : inchangé, rien de sélectionné en plus."""
        dlg = Form(self.host)
        dlg.name.setFocus()
        seen = run_modal(dlg.exec, lambda d: (d.focusWidget() is d.name, selected(d.spin)))
        self.assertEqual(seen, (True, ''))

    def test_dialog_starting_with_a_list_is_kept(self):
        """Premier élément : une liste (pas un champ de saisie) — rien de sélectionné."""
        combo = QComboBox()
        combo.addItems(['a', 'b'])
        dlg = Form(self.host, first=combo)
        seen = run_modal(dlg.exec, lambda d: (d.focusWidget() is d.spin, selected(d.spin)))
        self.assertEqual(seen, (False, ''))

    def test_embedded_dialog_does_not_take_focus(self):
        """Une fenêtre de dialogue posée dans un panneau (pas une fenêtre) : ne prend pas le focus. Seul `isWindow()`
        l'en empêche : la règle y trouverait bien un premier champ, et la fenêtre n'a choisi aucun champ."""
        from vectordrive.ui import fields
        panel = QWidget()
        self.addCleanup(panel.deleteLater)
        other = QLineEdit('x', panel)
        inner = Form(panel)
        inner.setWindowFlags(Qt.WindowType.Widget)
        other.setFocus()
        panel.show()
        inner.show()
        app.processEvents()
        self.assertEqual(selected(inner.spin), '')
        self.assertIs(panel.focusWidget(), other)
        self.assertIsNone(inner.focusWidget())                # (rien de choisi dans la fenêtre posée)
        self.assertIs(fields.first_field(inner), inner.spin)   # (la règle y trouverait le rayon)

    def test_spontaneous_show_selects_nothing(self):
        """Ouverture venue du système (fenêtre réduite qui revient), aucun champ choisi : rien de sélectionné."""
        from vectordrive.ui import fields
        filt = fields.install()
        dlg = Form(self.host)
        self.addCleanup(dlg.deleteLater)
        self.assertFalse(filt.eventFilter(dlg, FakeShow(True)))
        self.assertIsNone(dlg.focusWidget())
        self.assertEqual(selected(dlg.spin), '')
        self.assertFalse(filt.eventFilter(dlg, FakeShow(False)))   # (témoin : non spontanée, le rayon sélectionné)
        self.assertIs(dlg.focusWidget(), dlg.spin)
        self.assertEqual(selected(dlg.spin), dlg.spin.cleanText())

    def test_show_without_activating_selects_nothing(self):
        """Fenêtre montrée sans être activée (`WA_ShowWithoutActivating`) : ni focus pris, ni sélection."""
        dlg = Form(self.host)
        self.addCleanup(dlg.deleteLater)
        dlg.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        dlg.show()
        app.processEvents()
        self.assertEqual(selected(dlg.spin), '')
        dlg.hide()

    def test_qt_ready_made_boxes_and_subclasses_untouched(self):
        """Boîtes toutes faites de Qt et leurs sous-classes : jamais touchées, même avec un champ en premier."""
        from vectordrive.ui import fields

        class Box(QMessageBox):
            pass
        for cls in (QMessageBox, Box):
            box = cls(self.host)
            self.addCleanup(box.deleteLater)
            edit = QLineEdit('texte', box)
            box.layout().addWidget(edit)
            self.assertIs(fields.first_field(box), edit)       # (la règle y trouverait ce champ)
            box.show()
            app.processEvents()
            self.assertEqual(edit.selectedText(), '', cls.__name__)
            box.hide()

    def test_scroll_area_subclass_is_passed(self):
        """Formulaire dans une zone qui défile (sous-classe de QScrollArea, comme le volet `fit.VScroll`) : le premier
        champ de son contenu est sélectionné."""
        from PySide6.QtWidgets import QScrollArea, QVBoxLayout

        class Scroll(QScrollArea):
            pass
        dlg = QDialog(self.host)
        lay = QVBoxLayout(dlg)
        area = Scroll()
        area.setWidgetResizable(True)
        inner = QWidget()
        form = QFormLayout(inner)
        spin = QDoubleSpinBox()
        spin.setValue(3.5)
        form.addRow('Valeur', spin)
        area.setWidget(inner)
        lay.addWidget(area)
        self.assertTrue(area.focusPolicy() & Qt.FocusPolicy.TabFocus)   # (Qt donnerait le focus à la zone)
        seen = run_modal(dlg.exec, lambda d: (d.focusWidget() is spin, selected(spin), spin.cleanText()))
        self.assertTrue(seen[0], BEFORE)
        self.assertEqual(seen[1], seen[2], BEFORE)

    def test_filter_survives_destroyed_widget(self):
        """Un élément détruit côté Qt pendant la recherche du premier champ : le filtre ne lève rien."""
        from unittest import mock

        from vectordrive.ui import fields
        filt = fields.install()
        dlg = Form(self.host)
        self.addCleanup(dlg.deleteLater)
        with mock.patch.object(fields, 'select_first_field', side_effect=RuntimeError('détruit')):
            self.assertFalse(filt.eventFilter(dlg, FakeShow(False)))

    def test_select_first_field_rules(self):
        from vectordrive.ui import fields
        dlg = Form(self.host)
        self.assertIs(fields.first_field(dlg), dlg.spin)
        self.assertTrue(fields.select_first_field(dlg))
        self.assertEqual(selected(dlg.spin), dlg.spin.cleanText())
        ro = Form(self.host)
        ro.spin.setReadOnly(True)
        self.assertFalse(fields.select_first_field(ro))        # en lecture seule : pas un champ de saisie
        off = Form(self.host)
        off.spin.setEnabled(False)
        self.assertIs(fields.first_field(off), off.name)       # inactif : passé
        for d in (dlg, ro, off):
            d.deleteLater()

    def test_shown_again_keeps_its_field(self):
        """Une fenêtre qui se montre de nouveau, son champ déjà choisi : rien n'est resélectionné."""
        from PySide6.QtGui import QShowEvent
        dlg = Form(self.host)
        dlg.show()
        app.processEvents()
        dlg.spin.lineEdit().deselect()
        ev = QShowEvent()
        ev.setAccepted(True)
        QApplication.sendEvent(dlg, ev)                       # (non spontané, mais la fenêtre a déjà son champ)
        self.assertEqual(selected(dlg.spin), '')
        dlg.hide()
        dlg.deleteLater()


class InputDialogs(unittest.TestCase):
    """QInputDialog (Qt) : le faisait déjà — inchangé (garde-fou)."""

    def setUp(self):
        from vectordrive.ui import fields
        fields.install()
        self.host = QWidget()
        self.addCleanup(self.host.deleteLater)

    def _look(self, d):
        fw = d.focusWidget()
        if isinstance(fw, QComboBox):
            fw = fw.lineEdit()
        return selected(fw), (fw.lineEdit() if isinstance(fw, QAbstractSpinBox) else fw).text()

    def test_get_double_int_text_item(self):
        for start in (lambda: QInputDialog.getDouble(self.host, 't', 'v', 12.5, 0, 100, 3),
                      lambda: QInputDialog.getInt(self.host, 't', 'v', 7, 0, 100),
                      lambda: QInputDialog.getText(self.host, 't', 'v', text='abc'),
                      lambda: QInputDialog.getItem(self.host, 't', 'v', ['25,4*3', '2'], 0, True)):
            sel, text = run_modal(start, self._look)
            self.assertTrue(sel)
            self.assertEqual(sel, text)


if __name__ == '__main__':
    unittest.main()
