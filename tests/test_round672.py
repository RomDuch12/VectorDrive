"""Round 672 : rubans « FAO 2D » (l'onglet FAO d'avant) et « FAO 3D » — les
fonctions des menus déroulants de la vue 3D (usinage 3D, corps, couleurs,
mode de clic) en boutons, la barre de la vue 3D sans eux ; FAO 2D en 3D
montre FAO 3D, et l'inverse ; commandes sans pièce ou sans sélection :
dites, rien de fait."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QApplication

from vectordrive.core import solids as SO
from tests.test_round596 import two_boxes_stl

app = QApplication.instance() or QApplication([])

CAM3D = ('cam3d_stock', 'cam3d_clamping', 'cam3d_to_volumes', 'cam3d_pick_faces', 'cam3d_pick_contours',
         'cam3d_pick_off', 'cam3d_clear', 'cam3d_auto', 'cam3d_rough', 'cam3d_sweep', 'cam3d_levels',
         'cam3d_pocket', 'cam3d_holes', 'cam3d_contours', 'cam3d_zone', 'cam3d_rest', 'cam3d_face_up',
         'cam3d_body', 'cam3d_surface2d', 'cam3d_bodies', 'cam3d_show_bodies', 'cam3d_body_colors',
         'cam3d_mechanisms', 'cam3d_part_color', 'cam3d_edge_color', 'cam3d_reset_colors')


SAMPLE = 'Ébauche 3D Balayage 3D Niveaux constants Poche jusqu au fond Corps et couleurs'


def full_hd() -> int:
    """Largeur utile d'un écran de 1920 px sous Windows (Segoe UI 9 : SAMPLE fait 435 px), à l'échelle de
    la police du moment (hors écran, la police de remplacement est deux fois plus large)."""
    return int(1900 * QFontMetrics(QApplication.font()).horizontalAdvance(SAMPLE) / 435)


def tab_index(r, title):
    return next(i for i in range(r.count()) if r.tabText(i) == title)


class TestRibbons(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_tabs(self):
        r = self.w.ribbon
        titles = [r.tabText(i) for i in range(r.count())]
        self.assertIn('FAO 2D', titles)
        self.assertNotIn('FAO', titles)
        self.assertLess(titles.index('FAO 2D'), titles.index('FAO 3D'))
        page = r.page(tab_index(r, 'FAO 3D'))
        self.assertEqual([g.title.text() for g in page.groups()],
                         ['Pièce 3D', 'Clic dans la vue', 'Usinage 3D', 'Usinages', 'Poser', 'Corps et couleurs',
                          'Calculer et voir'])
        for k in CAM3D:
            self.assertIn(k, self.w.A)
        acts = [b.defaultAction() for g in page.groups() for b in g.buttons()]
        self.assertEqual(len(acts), len(set(map(id, acts))))           # rien en double
        A = self.w.A
        for k in ('place_model3d', 'cam_compute', 'cam_paths_3d', 'cam_sim_3d'):
            self.assertIn(A[k], acts, k)
        self.assertNotIn(A['view_3d'], acts)                             # bouton 3D : onglet Vue
        fao2d = r.page(tab_index(r, 'FAO 2D'))
        acts2 = [b.defaultAction() for g in fao2d.groups() for b in g.buttons()]
        self.assertIn(A['cam_compute'], acts2)                           # Calculer dans les deux
        self.assertNotIn(A['cam_sim_3d'], acts2)
        self.assertIsNotNone(self.w.A['cam3d_zone'].menu())

    def test_plugin_tab_before_fao(self):
        r = self.w.ribbon
        page = r.add_tab('Atelier')                                     # onglet d'un plugin
        titles = [r.tabText(i) for i in range(r.count())]
        self.assertEqual(titles.index('FAO 3D'), titles.index('FAO 2D') + 1)     # FAO 2D et 3D côte à côte
        self.assertLess(titles.index('Atelier'), titles.index('FAO 2D'))
        r.removeTab(titles.index('Atelier'))
        page.deleteLater()

    def test_full_hd(self):
        r = self.w.ribbon
        for title in ('FAO 2D', 'FAO 3D'):
            page = r.page(tab_index(r, title))
            self.assertTrue(page.fit(full_hd()), title)                 # tient en 1920 (sans défiler, 1094)

    def test_ribbon_follows_view(self):
        w, r = self.w, self.w.ribbon
        r.setCurrentIndex(tab_index(r, 'FAO 2D'))
        w.set_view_mode('3d')
        self.assertEqual(r.tabText(r.currentIndex()), 'FAO 3D')
        w.set_view_mode('2d')
        self.assertEqual(r.tabText(r.currentIndex()), 'FAO 2D')
        r.setCurrentIndex(tab_index(r, 'Vue'))
        w.set_view_mode('3d')
        self.assertEqual(r.tabText(r.currentIndex()), 'Vue')            # un autre onglet : il reste

    def test_without_part(self):
        w = self.w
        self.assertIsNone(w._cam3d('machine3d', 'ebauche3d'))          # dessin vide : dit, rien de fait
        self.assertIn('Pas de pièce 3D', w.panel3d.info.text())
        self.assertEqual(w.cam_panel.setup().operations, [])
        for what in ('auto3d', 'to_volumes', 'show_all_bodies', 'mechanisms'):
            w.panel3d.info.setText('')
            self.assertIsNone(w._cam3d('with_part', what), what)
            self.assertIn('Pas de pièce 3D', w.panel3d.info.text(), what)

    def test_hidden_fao_tab_migrated(self):
        from vectordrive.ui import ribbon_editor as RE
        RE.set_hidden(self.w.settings, ['FAO'])                           # masqué avant les deux rubans
        try:
            self.assertEqual(RE.hidden(self.w.settings), ['FAO', 'FAO 2D', 'FAO 3D'])
        finally:
            RE.set_hidden(self.w.settings, [])

    def test_menu_actions_open_their_menu(self):
        w = self.w
        for k in ('cam3d_zone', 'cam3d_bodies'):                         # Chercher une commande : le menu
            w.A[k].trigger()
            m = w.A[k].menu()
            self.assertTrue(m.isVisible(), k)
            m.hide()


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestCam3dCommands(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.open_path(two_boxes_stl())
        self.w.set_view_mode('3d')
        self.p = self.w.panel3d

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_bar_without_menus(self):
        p = self.p
        self.assertIsNotNone(p.view.model)
        for wdg in (p.select, p.use, p.color_btn, p.bodies):
            self.assertFalse(wdg.isVisibleTo(p))
        self.assertTrue(p._has_part())

    def test_pick_modes(self):
        w, p = self.w, self.p
        off = w.A['cam3d_pick_off']
        self.assertIs(off.actionGroup().checkedAction(), off)
        off.trigger()                                                    # recliqué : reste coché
        self.assertTrue(off.isChecked())
        w.A['cam3d_pick_faces'].trigger()
        self.assertEqual(p.view.select_mode, 'faces')
        self.assertFalse(off.isChecked())
        p.select.setCurrentIndex(p.select.findData('contours'))       # et l'inverse
        self.assertTrue(w.A['cam3d_pick_contours'].isChecked())
        self.assertFalse(w.A['cam3d_pick_faces'].isChecked())
        self.assertIs(off.actionGroup().checkedAction(), w.A['cam3d_pick_contours'])
        w.A['cam3d_pick_contours'].trigger()                             # le mode montré recliqué : reste
        self.assertTrue(w.A['cam3d_pick_contours'].isChecked())
        self.assertEqual(p.view.select_mode, 'contours')

    def test_rough_whole_or_selection(self):
        w, p = self.w, self.p
        o = p.machine3d('ebauche3d', exec_dialog=False)                # rien de choisi : toute la pièce
        self.assertEqual(o.kind, 'ebauche3d')
        self.assertEqual((o.faces3d, o.contours3d), ([], []))
        self.assertIsNone(p.machine3d('niveaux3d', True, exec_dialog=False))   # parois : à choisir
        self.assertIn('Choisir d\'abord', p.info.text())
        self.assertIsNone(p.pocket_to_floor())
        self.assertIsNone(p.selection_to_drawing())

    def test_menus(self):
        from PySide6.QtWidgets import QMenu
        p = self.p
        m = QMenu()
        p.fill_zone_menu(m)
        self.assertEqual([a.text() for a in m.actions()], ['Aucun usinage 3D'])
        p.fill_bodies_list(m)
        self.assertEqual(len([a for a in m.actions() if a.isCheckable()]), 3)   # 2 corps et « couleur par corps »
        p.machine3d('ebauche3d', exec_dialog=False)
        for _ in range(3):                                               # rouvert : rien ne reste d'avant
            p.fill_zone_menu(m)
        self.assertEqual(m.findChildren(QMenu), [])
        texts = [a.text() for a in m.actions() if not a.isSeparator()]
        self.assertEqual(len(texts), 2)
        self.assertTrue(texts[0].startswith('Remplacer la zone de « ') and texts[1].startswith('Montrer'))
        self.assertFalse(m.actions()[0].isEnabled())                     # rien de choisi : rien à remplacer
        self.assertFalse(p.replace_zone(self.w.cam_panel.ops_3d()[0].id))
        self.assertIn('Choisir d\'abord', p.info.text())

    def test_menus_of_the_shown_drawing(self):
        w = self.w
        w.set_view_mode('2d')
        w.modified = False
        w.new_document()                                                 # un autre dessin, vue 3D d'avant
        m = w.A['cam3d_bodies'].menu()
        m.aboutToShow.emit()
        self.assertEqual([a for a in m.actions() if a.isCheckable() and 'triangles' in a.text()], [])
        self.assertEqual(w.view_mode(), '3d')

    def test_part_after_toolpaths(self):
        w, p = self.w, self.p
        w.show_toolpaths('3d')                                           # trajectoires : la pièce n'est plus montrée
        self.assertEqual(p.source.currentData(), 'parcours')
        o = w._cam3d('machine3d', 'ebauche3d', False, False)             # commande du ruban : la pièce remontrée
        self.assertEqual(o.kind, 'ebauche3d')
        self.assertEqual(p.source.currentData(), 'auto')

    def test_to_volumes_needs_a_file(self):
        w, p = self.w, self.p
        shapes, _failed = w._cam3d('with_part', 'to_volumes', False)    # le STL : deux volumes
        self.assertEqual(len(shapes), 2)
        p.set_source('volumes')
        self.assertTrue(p.volumes_shown)
        self.assertEqual(w._cam3d('with_part', 'to_volumes', False), ([], []))   # les volumes : pas en double
        self.assertIn('En volumes', p.info.text())
        self.assertEqual(len(SO.doc_solids(w.canvas.doc)), 2)

    def test_body_colors_synced(self):
        w, p = self.w, self.p
        w.A['cam3d_body_colors'].trigger()
        self.assertTrue(p.view.body_colors)
        p.set_body_colors(False)
        self.assertFalse(w.A['cam3d_body_colors'].isChecked())

    def test_holes_only_drawing_setup(self):
        from vectordrive.ui.view3d import ALL_SETUPS
        p = self.p
        p.setup_view.setCurrentIndex(p.setup_view.findData(ALL_SETUPS))
        self.assertEqual(p.holes3d(), ([], []))                          # « Toutes » : la pièce comme le dessin
        p.part_tabs.setCurrentIndex(p._tab_keys['part'].index(1))
        self.assertIsNone(p.holes3d())
        self.assertIn('Comme le dessin', p.info.text())

    def test_place_body_of_tab(self):
        p = self.p
        p.part_tabs.setCurrentIndex(p._tab_keys['part'].index(1))
        self.assertEqual(p.current_part(), 1)
        from unittest import mock
        with mock.patch.object(type(p), 'place_body', lambda self, b=None, **k: ('corps', b)):
            self.assertEqual(p.place_selected_body(), ('corps', 1))


if __name__ == '__main__':
    unittest.main()
