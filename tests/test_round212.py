"""Round 212 : ruban ajusté à la largeur. Depuis le round 1094, plus de groupe replié en familles (sa barre
déroulée passait pour un menu du clic droit) : trop étroit, l'onglet défile de côté."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QScrollArea

app = QApplication.instance() or QApplication([])


def _icon():
    pm = QPixmap(16, 16)
    pm.fill()
    return QIcon(pm)


def ribbon_with(groups: list[tuple[str, int]]):
    from vectordrive.ui.ribbon import Ribbon
    r = Ribbon()
    page = r.add_tab('Essai')
    acts = []
    for title, n in groups:
        g = page.group(title)
        for i in range(n):
            a = QAction(_icon(), f'{title} commande {i}', r)               # icône : petits boutons sans libellé possibles
            acts.append(a)
            g.add(a, big=i == 0)
    r.finalize()
    return r, page, acts


class TestFit(unittest.TestCase):
    def test_never_folds(self):
        r, page, _a = ribbon_with([('Un', 7), ('Deux', 7), ('Trois', 7)])
        gs = page.groups()
        page.fit(100000)                                                            # libellés partout
        full = sum(g.expanded_width() for g in gs)
        self.assertTrue(page.fit(full + 100))                                       # tout tient
        self.assertFalse(any(g.iconic for g in gs))
        page.fit(full - 10)                                                         # icônes seules d'abord (640)
        self.assertTrue(any(g.iconic for g in gs))
        self.assertFalse(page.fit(10))                                              # rien ne tient : la page défile
        for g in gs:
            self.assertIs(g.body.parent(), g)                                       # aucun groupe replié (1094)
            self.assertTrue(g.title.isVisibleTo(g))
        self.assertTrue(page.fit(full + 100))                                       # place revenue : libellés
        self.assertFalse(any(g.iconic for g in gs))
        r.deleteLater()

    def test_captions_follow(self):
        r, page, _a = ribbon_with([('A', 3), ('B', 3)])
        r.configure(captions=False)
        r.fit_current()
        g = page.groups()[0]
        self.assertFalse(g.title.isVisibleTo(g))
        r.configure(captions=True)
        r.resize(4000, 200)
        r.fit_current()
        self.assertTrue(g.title.isVisibleTo(g))
        r.deleteLater()


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        cls.w.resize(1600, 900)
        cls.w.show()
        app.processEvents()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def test_fits_or_scrolls(self):
        r = self.w.ribbon
        for i in range(r.count()):
            if not r.isTabVisible(i) or r.page(i) is None:
                continue
            r.setCurrentIndex(i)
            r.fit_current()
            app.processEvents()
            sc = r.widget(i)
            self.assertIsInstance(sc, QScrollArea)
            with self.subTest(onglet=r.tabText(i)):
                over = r.page(i).sizeHint().width() - sc.viewport().width()   # trop large : il défile (1094)
                self.assertEqual(sc.horizontalScrollBar().maximum(), max(0, over))
                self.assertTrue(all(g.body.parent() is g for g in r.page(i).groups()))

    def test_menus(self):
        titles = [t for t, _g in self.w._vd_tab_menus()]
        self.assertTrue({'Edition', 'CAD'} <= set(titles))                            # actions toujours trouvées


if __name__ == '__main__':
    unittest.main()
