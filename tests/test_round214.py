"""Round 214 : fenêtres sans défilement horizontal — élargies à
l'ouverture (dans la limite de l'écran), place prise d'abord aux volets
voisins d'un séparateur ; colonnes des panneaux (calques, FAO) et de la
bibliothèque d'outils à la largeur ; éditeur du ruban sur plusieurs lignes."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel, QScrollArea, QSplitter, QTableWidget,
                               QVBoxLayout, QWidget)

app = QApplication.instance() or QApplication([])


def column(width: int) -> QScrollArea:
    holder = QWidget()
    holder.setMinimumWidth(width)
    QVBoxLayout(holder).addWidget(QLabel('x'))
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setWidget(holder)
    return sa


class TestFit(unittest.TestCase):
    def test_widen_to_content(self):
        from vectordrive.ui import fit
        d = QDialog()
        lay = QHBoxLayout(d)
        sa = column(500)
        lay.addWidget(sa)
        d.resize(300, 200)
        d.show()
        app.processEvents()
        self.assertGreater(fit.overflow(d), 0)
        added = fit.widen(d)
        self.assertGreater(added, 0)
        self.assertEqual(fit.overflow(d), 0)
        d.close()

    def test_screen_limit(self):
        from vectordrive.ui import fit
        d = QDialog()
        QHBoxLayout(d).addWidget(column(20000))
        d.resize(300, 200)
        d.show()
        app.processEvents()
        fit.widen(d)
        scr = d.screen().availableGeometry()
        self.assertLessEqual(d.width(), scr.width())                               # jamais plus large que l'écran
        d.close()

    def test_splitter_neighbours_give_room(self):
        from vectordrive.ui import fit
        d = QDialog()
        split = QSplitter()
        a, b = column(400), QLabel('aperçu')
        split.addWidget(a)
        split.addWidget(b)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        QHBoxLayout(d).addWidget(split)
        d.resize(900, 300)
        d.show()
        split.setSizes([200, 700])
        app.processEvents()
        self.assertGreater(fit.missing(a), 0)
        added = fit.widen(d)
        self.assertEqual(added, 0)                                                  # pris au volet voisin
        self.assertEqual(fit.missing(a), 0)
        d.close()

    def test_wanted_scroll_is_left_alone(self):
        from vectordrive.ui import fit
        d = QDialog()
        sa = column(3000)
        sa.setProperty('vd_hscroll_ok', True)
        QHBoxLayout(d).addWidget(sa)
        d.resize(300, 200)
        d.show()
        app.processEvents()
        self.assertEqual(fit.widen(d), 0)
        d.close()

    def test_on_show(self):
        from vectordrive.ui import fit
        d = QDialog()
        QHBoxLayout(d).addWidget(column(700))
        fit.no_hscroll(d)
        d.resize(300, 200)
        d.show()
        for _ in range(3):
            app.processEvents()
        self.assertGreater(d.property('vd_widened') or 0, 0)
        self.assertEqual(fit.overflow(d), 0)
        d.close()


class TestWindows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        cls.w.resize(1500, 900)
        cls.w.show()
        app.processEvents()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def test_panel_tables_fit(self):
        from PySide6.QtWidgets import QHeaderView
        p = self.w.cam_panel
        hh = p.tools.horizontalHeader()
        self.assertEqual(hh.sectionResizeMode(1), QHeaderView.ResizeMode.Stretch)
        self.assertEqual(hh.sectionResizeMode(4), QHeaderView.ResizeMode.ResizeToContents)
        lh = self.w.layers_panel.tree.header()
        # 907 : colonnes réglables (glisser, double-clic), la dernière va jusqu'au bord du panneau
        self.assertEqual(lh.sectionResizeMode(self.w.layers_panel.COL_TOOL), QHeaderView.ResizeMode.Interactive)
        self.assertTrue(lh.stretchLastSection())

    def test_dialogs_widen(self):
        from vectordrive.ui import fit
        for make in (lambda: self.w.options_dialog(exec_dialog=False),
                     lambda: self.w.cam_panel.tool_library(exec_dialog=False),
                     lambda: self.w.ribbon_editor(exec_dialog=False)):
            d = make()
            self.assertTrue(hasattr(d, '_vd_fitter'))
            d.show()
            for _ in range(3):
                app.processEvents()
            limit = d.screen().availableGeometry().width() - 2 * fit.SCREEN_MARGIN
            with self.subTest(fenetre=d.windowTitle()):
                # rien ne défile, sauf si l'écran (800 px hors écran, polices factices) est atteint
                self.assertTrue(fit.overflow(d) == 0 or d.width() >= limit - 2)
                # jamais poussée au-delà de l'écran (sa largeur minimale mise à part) ; F10 s'ouvre maximisée
                # (round 1161) : c'est sa taille normale, celle de la fenêtre restaurée, qui ne doit pas dépasser
                width = d.normalGeometry().width() if d.isMaximized() else d.width()
                self.assertLessEqual(width, max(limit + 2, d.minimumSizeHint().width()))
            d.close()
            d.deleteLater()

    def test_ribbon_editor_rows(self):
        from PySide6.QtWidgets import QGridLayout
        d = self.w.ribbon_editor(exec_dialog=False)
        grid = next(l for l in d.findChildren(QGridLayout))
        self.assertLessEqual(grid.columnCount(), 9)                                 # huit cases par ligne
        self.assertNotIn(self.w.text_tab_title, d.tab_checks)
        d.deleteLater()


if __name__ == '__main__':
    unittest.main()
