"""Round 640 : rubans en Full HD — libellés des grands boutons sur deux lignes ;
petits boutons en icônes seules avant tout repli en famille, libellés rendus
quand la place revient ; commandes en double retirées du ruban, homonymes
d'un même onglet renommés ; icône de « Quitter »."""
import os
import tempfile
import unittest
from collections import Counter

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from tests.test_round212 import ribbon_with
from vectordrive.ui import ribbon as R

app = QApplication.instance() or QApplication([])


class TestLabels(unittest.TestCase):
    def test_two_lines(self):
        r, page, acts = ribbon_with([('Groupe', 1)])
        fm = page.groups()[0].buttons()[0].fontMetrics()
        cut = R.two_lines('Calculer les parcours', fm)
        self.assertEqual(cut.count('\n'), 1)
        self.assertEqual(cut.replace('\n', ' '), 'Calculer les parcours')
        a, b = cut.split('\n')
        self.assertLess(max(fm.horizontalAdvance(a), fm.horizontalAdvance(b)),
                        fm.horizontalAdvance('Calculer les parcours'))
        self.assertEqual(R.two_lines('Bibliothèque', fm), 'Bibliothèque')         # un seul mot
        self.assertEqual(R.two_lines('Cote', fm), 'Cote')
        r.deleteLater()

    def test_big_button_keeps_two_lines(self):
        r, page, acts = ribbon_with([('Groupe', 2)])
        b = page.groups()[0].buttons()[0]
        acts[0].setText('Créer un parcours en plein écran')
        self.assertIn('\n', b.text())                                              # recoupé après le changement
        self.assertEqual(acts[0].text(), 'Créer un parcours en plein écran')      # l'action garde son texte
        small = page.groups()[0].buttons()[1]
        self.assertNotIn('\n', small.text())
        r.deleteLater()


class TestIconic(unittest.TestCase):
    def test_icons_before_families(self):
        r, page, _a = ribbon_with([('Un', 10), ('Deux', 10), ('Trois', 4)])
        gs = page.groups()
        page.fit(100000)
        self.assertFalse(any(g.iconic for g in gs))
        full = sum(g.expanded_width() for g in gs)
        b = gs[0].buttons()[3]
        self.assertEqual(b.toolButtonStyle(), Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.assertEqual(page.fit(full - 20), [])                                 # rien replié…
        self.assertTrue(gs[0].iconic or gs[1].iconic)                             # … les plus larges en icônes
        iconic = [g for g in gs if g.iconic][0]
        self.assertEqual(iconic.buttons()[3].toolButtonStyle(), Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.assertTrue(iconic.buttons()[0].toolButtonStyle(), Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        folded = page.fit(10)
        self.assertEqual(len(folded), 3)
        self.assertFalse(any(g.iconic for g in gs))                               # barre déroulée : avec libellés
        page.fit(100000)
        self.assertFalse(any(g.iconic or g.collapsed for g in gs))                # place revenue : tout rendu
        r.deleteLater()


class TestMainRibbon(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def tabs(self):
        r = self.w.ribbon
        for i in range(r.count()):
            p = r.page(i)
            if p is not None and r.tabText(i) != self.w.text_tab_title:
                yield r.tabText(i), p

    def test_no_duplicates(self):
        seen = Counter()
        for title, p in self.tabs():
            acts = [b.defaultAction() for g in p.groups() for b in g.buttons()]
            texts = Counter(a.text().replace('&', '') for a in acts)
            self.assertEqual([t for t, n in texts.items() if n > 1], [], title)  # pas d'homonymes dans un onglet
            seen.update(id(a) for a in acts)
        A = self.w.A
        both = ('tool_select', 'cam_compute', 'cam3d_pick_faces', 'cam3d_clear')
        twice = [k for k, a in A.items() if seen[id(a)] > 1 and k not in both]
        self.assertEqual(twice, [])                                               # chaque commande une fois
        self.assertEqual(seen[id(A['cam_compute'])], 2)                           # Calculer : FAO 2D et FAO 3D
        for k in ('cam3d_pick_faces', 'cam3d_clear'):                             # faces : FAO 3D et Design STEP
            self.assertEqual(seen[id(A[k])], 2, k)
        for k in ('export_stl', 'galbe', 'galbe_smooth', 'place_model3d', 'cam_sim_3d', 'cam_paths_3d', 'dims'):
            self.assertEqual(seen[id(A[k])], 1, k)                                # toujours dans le ruban
        self.assertEqual(seen[id(A['view_toggle'])], 0)                           # round 903 : la rangée des onglets
        self.assertIs(self.w.ribbon.view_button.defaultAction(), A['view_toggle'])
        r = self.w.ribbon
        text = r.page(next(i for i in range(r.count()) if r.tabText(i) == self.w.text_tab_title))
        shown = {id(b.defaultAction()) for g in text.groups() for b in g.buttons()}
        self.assertTrue({id(A['case_upper']), id(A['text_on_baseline'])} <= shown)   # casse : Mise en forme

    def test_renamed_and_icons(self):
        A = self.w.A
        self.assertEqual(A['node_arc'].text(), 'Portion en arc')
        self.assertEqual(A['node_on_curve'].text(), 'Point sur courbe')
        self.assertEqual(A['cad_measure'].text(), 'Mesurer (repères)')
        self.assertFalse(A['quit'].icon().isNull())
        missing = [b.defaultAction().text() for _t, p in self.tabs() for g in p.groups() for b in g.buttons()
                   if b.defaultAction().icon().isNull()]
        self.assertEqual(missing, [])                                             # tout bouton a son icône


if __name__ == '__main__':
    unittest.main()
