"""Round 212 : ruban sans défilement horizontal — groupes repliés en
familles (de la droite vers la gauche, selon la place, ou toujours), un clic
sur une famille déroule sa barre."""
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
    def test_right_to_left(self):
        r, page, _a = ribbon_with([('Un', 7), ('Deux', 7), ('Trois', 7)])
        gs = page.groups()
        page.fit(100000)                                                            # libellés partout
        full = sum(g.expanded_width() for g in gs)
        self.assertEqual(page.fit(full + 100), [])                                  # tout tient
        self.assertEqual(page.fit(full - 10), [])                                    # icônes seules d'abord (640)
        self.assertTrue(any(g.iconic for g in gs))
        for g in gs:
            g.set_iconic(True)
        lean = sum(g.expanded_width() for g in gs)
        self.assertEqual([g.title.text() for g in page.fit(lean - 10)], ['Trois'])  # puis le dernier replié
        self.assertTrue(gs[2].collapsed and not gs[0].collapsed)
        folded = page.fit(10)
        self.assertEqual(len(folded), 3)                                              # rien ne tient : tout replié
        self.assertEqual(len(page.fit(10, always=True)), 3)
        self.assertEqual(page.fit(full + 100), [])                                  # place revenue : dépliés
        self.assertFalse(any(g.collapsed for g in gs))
        r.deleteLater()

    def test_big_group_folded_others_back(self):
        r, page, _a = ribbon_with([('Grand', 30), ('Petit', 1), ('Moyen', 2)])
        gs = page.groups()
        avail = gs[1].expanded_width() + gs[2].expanded_width() + gs[0].collapsed_width() + 30
        folded = page.fit(avail)
        self.assertEqual([g.title.text() for g in folded], ['Grand'])                # les petits redépliés
        r.deleteLater()

    def test_family_unrolls_and_closes(self):
        r, page, acts = ribbon_with([('Famille', 5)])
        g = page.groups()[0]
        page.fit(10)
        self.assertTrue(g.collapsed)
        self.assertTrue(g.family.isVisibleTo(g) and not g.title.isVisibleTo(g))
        self.assertIn('Famille commande 3', g.family.toolTip())
        self.assertEqual(len(g.buttons()), 5)                                       # boutons dans la barre déroulée
        self.assertIs(g.body.parent(), g.popup)
        g.unroll()
        self.assertTrue(g.popup.isVisible())
        g.buttons()[2].click()                                                      # une commande : barre refermée
        self.assertFalse(g.popup.isVisible())
        page.fit(10000)
        self.assertIs(g.body.parent(), g)                                           # déplié : contenu revenu
        self.assertFalse(g.family.isVisibleTo(g))
        r.deleteLater()

    def test_captions_follow(self):
        r, page, _a = ribbon_with([('A', 3), ('B', 3)])
        r.configure(captions=False, families='toujours')
        r.fit_current()
        g = page.groups()[0]
        self.assertTrue(g.collapsed)
        self.assertFalse(g.popup.title.isVisibleTo(g.popup))
        r.configure(captions=True, families='place')
        r.resize(4000, 200)
        r.fit_current()
        self.assertFalse(g.collapsed)
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

    def test_no_horizontal_scroll(self):
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
                self.assertLessEqual(r.page(i).sizeHint().width(), sc.viewport().width())

    def test_menus_and_option(self):
        from vectordrive.ui.options import BY_KEY
        self.assertEqual(BY_KEY['vue/ruban_familles'].default, 'place')
        r = self.w.ribbon
        self.w.settings.setValue('vue/ruban_familles', 'toujours')
        self.w._apply_ribbon_options()
        r.fit_current()
        page = r.page(r.currentIndex())
        self.assertTrue(all(g.collapsed for g in page.groups() if g.buttons()))
        titles = [t for t, _g in self.w._vd_tab_menus()]
        self.assertIn(r.tabText(r.currentIndex()), titles)                           # actions toujours trouvées
        self.w.settings.setValue('vue/ruban_familles', 'place')
        self.w._apply_ribbon_options()


if __name__ == '__main__':
    unittest.main()
