"""Round 219 : la fenêtre principale tient dans un écran de 1080 px quand
le panneau FAO est ouvert — la liste des opérations et parcours défile en
hauteur (`fit.VScroll`) au lieu d'imposer la sienne ; rien n'y défile ni
n'y est coupé en largeur."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

app = QApplication.instance() or QApplication([])

#: hauteur utile d'un écran 1920×1080 (barre des tâches et cadre de la fenêtre ôtés)
SCREEN_ROOM = 1000


class TestVScroll(unittest.TestCase):
    def test_minimum_then_room(self):
        from vectordrive.ui.fit import VScroll
        inner = QWidget()
        lay = QVBoxLayout(inner)
        for k in range(30):
            lay.addWidget(QLabel(f'ligne {k}'))
        sa = VScroll(inner)
        self.assertEqual(sa.horizontalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.assertLessEqual(sa.minimumSizeHint().height(), 160)                # la fenêtre garde sa hauteur
        self.assertGreater(sa.minimumSizeHint().width(), inner.minimumSizeHint().width())   # + barre verticale
        need = inner.minimumSizeHint().height()
        sa.resize(300, 200)
        sa.show()
        QTest.qWait(20)
        self.assertEqual(inner.height(), need)                                  # au plus serré : le reste défile
        self.assertGreater(sa.verticalScrollBar().maximum(), 0)
        self.assertEqual(inner.width(), sa.viewport().width())
        sa.resize(300, need + 300)
        QTest.qWait(20)
        self.assertEqual(inner.height(), sa.viewport().height())                # de la place : tout est vu
        self.assertEqual(sa.verticalScrollBar().maximum(), 0)
        for k in range(30):                                                     # le contenu grandit : suivi
            lay.addWidget(QLabel(f'encore {k}'))
        QTest.qWait(50)
        self.assertEqual(inner.height(), inner.minimumSizeHint().height())
        self.assertGreater(inner.height(), need)
        self.assertGreater(sa.verticalScrollBar().maximum(), 0)
        sa.close()


class TestWindow(unittest.TestCase):
    def test_fits_the_screen_with_cam_panel(self):
        from vectordrive.ui.fit import VScroll
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        w.resize(1600, 900)
        w.show()
        QTest.qWait(20)
        closed = w.minimumSizeHint().height()
        w.A['cam_panel'].setChecked(True)
        QTest.qWait(20)
        self.assertTrue(w.dock_paths.isVisible())
        sa = w.dock_paths.widget()
        self.assertIsInstance(sa, VScroll)
        self.assertIs(sa.widget(), w.cam_panel)
        self.assertLessEqual(w.minimumSizeHint().height(), SCREEN_ROOM)
        self.assertLessEqual(w.minimumSizeHint().height(), closed + 40)          # le panneau ne grandit pas la fenêtre
        self.assertEqual(w.height(), 900)
        self.assertGreaterEqual(sa.viewport().width(), w.cam_panel.minimumSizeHint().width())   # rien de coupé
        self.assertEqual(w.cam_panel.width(), sa.viewport().width())
        self.assertGreaterEqual(w.cam_panel.height(), w.cam_panel.minimumSizeHint().height())
        w.toggle_paths_window(True)                                             # fenêtre détachée : idem
        QTest.qWait(20)
        self.assertTrue(w.dock_paths.isFloating())
        self.assertGreaterEqual(w.cam_panel.height(), w.cam_panel.minimumSizeHint().height())
        w.toggle_paths_window(False)
        w.A['cam_panel'].setChecked(False)                                       # réglage partagé : remis
        w.close()


if __name__ == '__main__':
    unittest.main()
