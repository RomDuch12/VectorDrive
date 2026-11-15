"""Round 1040 : demande du 15/11 ~10 h 45 — toute fenêtre en plein écran a un bouton de fermeture."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1040.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QPoint, QRect, Qt  # noqa: E402
from PySide6.QtWidgets import (QAbstractButton, QAbstractSlider, QAbstractSpinBox, QApplication, QComboBox,  # noqa: E402
                               QDialog, QLineEdit, QTabBar, QToolButton, QWidget)

app = QApplication.instance() or QApplication([])
NAME = 'vd_fullscreen_close'
FULL = Qt.WindowState.WindowFullScreen
BUSY = (QAbstractButton, QComboBox, QLineEdit, QAbstractSpinBox, QAbstractSlider, QTabBar)


def close_button(w):
    return w.findChild(QToolButton, NAME, Qt.FindChildOption.FindDirectChildrenOnly)


def covered(w, b):
    """Les boutons, champs, listes… de la fenêtre `w` que le ✕ `b` couvre."""
    out = []
    for c in w.findChildren(QWidget):
        if c is b or not isinstance(c, BUSY) or c.window() is not w or not c.isVisibleTo(w):
            continue
        if QRect(c.mapTo(w, QPoint(0, 0)), c.size()).intersects(b.geometry()):
            out.append(f'{type(c).__name__} {getattr(c, "text", lambda: "")()}')
    return out


class Settings(dict):
    def value(self, k, d=None):
        return self.get(k, d)

    def setValue(self, k, v):                                                # noqa: N802
        self[k] = v


def settle():
    """La fenêtre montrée, retaillée, mise en page ; le ✕ placé ensuite (minuterie à 0)."""
    for _ in range(3):
        app.processEvents()


class Base(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.win = MainWindow()                                               # pose les filtres de l'application

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.close()
        cls.win.deleteLater()


class CloseButton(Base):

    def test_a_full_screen_dialog_gets_a_close_button(self):
        dlg = QDialog(self.win)
        dlg.setWindowState(Qt.WindowState.WindowFullScreen)
        dlg.show()
        settle()
        b = close_button(dlg)
        self.assertIsNotNone(b, 'avant : pas de bouton, ni de barre de titre')
        self.assertTrue(b.isVisible())
        self.assertGreater(b.x(), dlg.width() - 3 * b.width())               # en haut à droite
        self.assertLess(b.y(), b.height())
        b.click()
        settle()
        self.assertFalse(dlg.isVisible())                                    # fermée, comme par Échap
        self.assertEqual(dlg.result(), QDialog.DialogCode.Rejected)
        dlg.deleteLater()

    def test_hidden_out_of_full_screen_and_other_windows(self):
        w = QWidget(None, Qt.WindowType.Window)
        w.show()
        settle()
        self.assertTrue(close_button(w) is None or not close_button(w).isVisible())   # fenêtre normale : rien
        w.setWindowState(Qt.WindowState.WindowFullScreen)
        settle()
        b = close_button(w)
        self.assertIsNotNone(b)
        self.assertTrue(b.isVisible())
        w.setWindowState(Qt.WindowState.WindowMaximized)                     # sortie du plein écran : caché
        settle()
        self.assertFalse(b.isVisible())
        w.setWindowState(Qt.WindowState.WindowFullScreen)
        settle()
        self.assertTrue(b.isVisible())
        w.resize(500, 400)                                                   # suit la taille de la fenêtre
        settle()
        self.assertEqual(b.x() + b.width() + 6, w.width())
        b.click()
        settle()
        self.assertFalse(w.isVisible())
        w.deleteLater()

    def test_it_does_not_cover_a_button_in_the_corner(self):
        from PySide6.QtWidgets import QHBoxLayout, QPushButton, QTextEdit, QVBoxLayout
        dlg = QDialog(self.win)
        lay = QVBoxLayout(dlg)
        row = QHBoxLayout()
        row.addStretch(1)
        full = QPushButton('⛶')                                              # seul à droite de sa ligne
        row.addWidget(full)
        lay.addLayout(row)
        lay.addWidget(QTextEdit(), 1)
        dlg.setWindowState(Qt.WindowState.WindowFullScreen)
        dlg.show()
        settle()
        settle()
        b = close_button(dlg)
        self.assertIsNotNone(b)
        self.assertTrue(b.isVisible())
        self.assertFalse(b.geometry().intersects(full.geometry()), (b.geometry(), full.geometry()))
        self.assertGreater(b.x(), dlg.width() // 2)                          # toujours en haut à droite
        dlg.reject()
        dlg.deleteLater()

    def test_a_window_with_its_own_button_is_left_alone(self):
        from vectordrive.ui.panel_window import PanelWindow
        for w in (QWidget(None, Qt.WindowType.Window), PanelWindow('essai')):   # la fenêtre d'un panneau : son ✕
            if not isinstance(w, PanelWindow):
                w.vd_own_close = True
            w.setWindowState(Qt.WindowState.WindowFullScreen)
            w.show()
            settle()
            self.assertIsNone(close_button(w))
            w.close()
            w.deleteLater()
        dlg = QDialog(self.win)                                              # (le test échoue avant : pas de ✕)
        dlg.setWindowState(Qt.WindowState.WindowFullScreen)
        dlg.show()
        settle()
        self.assertIsNotNone(close_button(dlg))
        dlg.reject()
        dlg.deleteLater()
        self.win.setWindowState(FULL)                                        # la fenêtre principale : ses boutons
        settle()                                                             # sont dans le ruban
        self.assertIsNone(close_button(self.win))
        self.win.setWindowState(Qt.WindowState.WindowNoState)
        settle()


class NeverOverAControl(Base):
    """Sans place libre dans la bande du haut, la fenêtre se resserre à droite : le ✕ ne couvre rien."""

    def show_full(self, dlg, half=False):
        dlg.setWindowState(FULL)
        dlg.show()
        settle()
        settle()
        b = close_button(dlg)
        self.assertIsNotNone(b, 'avant : pas de ✕')
        self.assertTrue(b.isVisible())
        if half:                                     # place libre dans la bande du haut : dans sa moitié droite
            self.assertGreaterEqual(b.x(), dlg.width() // 2)
        else:
            self.assertGreater(b.x(), dlg.width() - 3 * b.width())           # en haut à droite
        self.assertEqual(covered(dlg, b), [])
        return b

    def test_no_free_place_the_layout_makes_room(self):
        from PySide6.QtWidgets import QHBoxLayout, QPushButton, QTextEdit, QVBoxLayout
        dlg = QDialog(self.win)
        lay = QVBoxLayout(dlg)
        row = QHBoxLayout()
        row.addWidget(QLineEdit(), 1)                                        # un champ sur toute la largeur,
        row.addWidget(QPushButton('⛶'))                                      # puis un bouton tout à droite
        lay.addLayout(row)
        lay.addWidget(QTextEdit(), 1)
        before = lay.contentsMargins().right()
        self.show_full(dlg)
        self.assertGreater(lay.contentsMargins().right(), before)
        dlg.setWindowState(Qt.WindowState.WindowNoState)                     # hors plein écran : comme avant
        settle()
        self.assertEqual(lay.contentsMargins().right(), before)
        dlg.reject()
        dlg.deleteLater()

    def test_the_tool_picker_and_the_tool_library(self):
        from vectordrive.cam import model
        from vectordrive.ui.tool_picker import ToolPickerDialog
        from vectordrive.ui.toollib_dialog import ToolLibraryDialog
        t = model.CamTool(name='Cyl 1040', diameter=2.0, number=7)
        picker = ToolPickerDialog(None, [], {t.id: t}, settings=Settings())  # plein écran d'office
        self.assertTrue(picker.windowState() & FULL)
        self.show_full(picker)
        picker.reject()
        picker.deleteLater()
        lib = ToolLibraryDialog(self.win, path=os.path.join(tempfile.mkdtemp(), 'tools.json'))
        self.show_full(lib, half=True)               # (1043 : plus de liste des bibliothèques en haut)
        lib.reject()
        lib.deleteLater()


if __name__ == '__main__':
    unittest.main()
