"""Round 1097 (demande du 19/11, 16 h 37) : le Mode Point montre son onglet du ruban, l'onglet d'avant revient en
sortant ; les favoris dans une fenêtre (ajouter, retirer, ranger), et le clic droit sur leur barre."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1097.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QToolButton

app = QApplication.instance() or QApplication([])


class Win(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        cls.w.show()
        app.processEvents()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()


class PointModeRibbon(Win):

    def setUp(self):
        self.w.set_tool('select')
        self.w.settings.remove('vue/ruban_mode_point')
        self.r = self.w.ribbon
        self.home = next(i for i in range(self.r.count()) if self.r.tabText(i) == 'Fichier')
        self.r.setCurrentIndex(self.home)

    def test_enter_shows_the_tab_leave_gives_back(self):
        i = self.w._point_tab()
        self.assertGreaterEqual(i, 0)
        self.assertNotEqual(i, self.home)
        self.w.set_tool('node')
        self.assertEqual(self.r.currentIndex(), i)
        self.w.set_tool('select')
        self.assertEqual(self.r.currentIndex(), self.home)

    def test_p_key_toggle(self):
        i = self.w._point_tab()
        self.w.A['tool_node'].trigger()                          # P, ou le bouton
        self.assertEqual(self.w.canvas.tool, 'node')
        self.assertEqual(self.r.currentIndex(), i)
        self.w.A['tool_node'].trigger()                          # second appui : la sélection
        self.assertEqual(self.w.canvas.tool, 'select')
        self.assertEqual(self.r.currentIndex(), self.home)

    def test_other_tab_chosen_meanwhile_stays(self):
        self.w.set_tool('node')
        other = next(k for k in range(self.r.count()) if self.r.tabText(k) == 'Aide')
        self.r.setCurrentIndex(other)
        self.w.set_tool('select')
        self.assertEqual(self.r.currentIndex(), other)

    def test_setting_off(self):
        self.w.settings.setValue('vue/ruban_mode_point', False)
        self.w.set_tool('node')
        self.assertEqual(self.r.currentIndex(), self.home)
        self.w.set_tool('select')
        self.assertEqual(self.r.currentIndex(), self.home)

    def test_folded_ribbon_unchanged(self):
        self.r.set_collapsed(True)
        try:
            self.w.set_tool('node')
            self.assertEqual(self.r.currentIndex(), self.home)
        finally:
            self.w.set_tool('select')
            self.r.set_collapsed(False)

    def test_entered_from_its_own_tab_stays(self):
        i = self.w._point_tab()
        aide = next(k for k in range(self.r.count()) if self.r.tabText(k) == 'Aide')
        self.r.setCurrentIndex(aide)
        self.r.setCurrentIndex(i)                                # Aide, puis CAD, puis P
        self.w.set_tool('node')
        self.w.set_tool('select')
        self.assertEqual(self.r.currentIndex(), i)                # pas Aide : rien à rendre

    def test_tool_of_the_point_tab_keeps_it(self):
        i = self.w._point_tab()
        self.w.set_tool('node')
        self.w.set_tool('start_point')                            # Point de départ à la souris, dans le groupe
        self.assertEqual(self.r.currentIndex(), i)
        self.w.set_tool('select')
        self.assertEqual(self.r.currentIndex(), self.home)

    def test_pick_point_in_between(self):
        self.w.set_tool('node')
        self.w.canvas.tool = 'pick_point'                          # une commande qui demande un point
        self.w.set_tool('select')
        self.assertEqual(self.r.currentIndex(), self.home)

    def test_deleted_page_no_crash(self):
        from PySide6.QtWidgets import QWidget
        from shiboken6 import delete
        self.w.set_tool('node')
        gone = QWidget()
        delete(gone)                                              # un onglet défait (disposition changée)
        self.w._point_back = (gone, False)
        self.w.set_tool('select')
        self.assertEqual(self.w.canvas.tool, 'select')
        self.assertEqual(self.w._point_tab(), self.r.currentIndex())

    def test_typeedit_context_tab(self):
        from vectordrive.ui.shortcuts import TE_ACTIONS
        from vectordrive.ui.typeedit_layout import TELayout, TEPanel, TETab
        w = self.w
        cmd = next(c for c, k in TE_ACTIONS.items() if k == 'node_delete')
        lay = TELayout(tabs=[TETab('CAD', [TEPanel('Essai', [(cmd, True)])])],
                       contexts={'1000': TETab('Mode Point', [TEPanel('Mode Point', [(cmd, True)])], '1000'),
                                 '1003': TETab('Alignement', [TEPanel('Alignement', [(cmd, True)])], '1003')})
        w.layout_active, w._te_layout = True, lay
        w._build_te_tabs(lay)
        try:
            r = w.ribbon
            ctx = {str(r.widget(k).property('te_context')): k for k in range(r.count())
                   if r.widget(k).property('te_context')}
            cad = next(k for k in range(r.count()) if r.tabText(k) == 'CAD' and r.isTabVisible(k))
            r.setCurrentIndex(cad)
            w.show_te_context('1003')                            # un autre onglet contextuel ouvert
            r.setCurrentIndex(cad)
            w.set_tool('node')
            self.assertEqual(w._point_tab(), ctx['1000'])
            self.assertEqual(r.currentIndex(), ctx['1000'])
            self.assertTrue(r.isTabVisible(ctx['1000']))
            self.assertFalse(r.isTabVisible(ctx['1003']))
            w.set_tool('select')
            self.assertEqual(r.currentIndex(), cad)
            self.assertFalse(r.isTabVisible(ctx['1000']))         # l'onglet contextuel refermé
        finally:
            w.layout_active = False
            w.apply_ribbon_layout()


class Favorites(Win):

    def setUp(self):
        self.w._save_favorites(['zoom_fit', 'undo'])

    def tearDown(self):
        self.w._save_favorites([])

    def test_dialog_add_move_remove(self):
        dlg = self.w.favorites_dialog(exec_dialog=False)
        self.addCleanup(dlg.deleteLater)
        self.assertEqual(dlg.keys(), ['zoom_fit', 'undo'])
        dlg.favs.setCurrentRow(1)
        self.assertTrue(dlg.add('redo'))                          # après le favori choisi
        self.assertFalse(dlg.add('redo'))                         # déjà là
        self.assertEqual(dlg.keys(), ['zoom_fit', 'undo', 'redo'])
        dlg.favs.setCurrentRow(2)
        self.assertTrue(dlg.move(-2))
        self.assertEqual(dlg.keys(), ['redo', 'zoom_fit', 'undo'])
        self.assertFalse(dlg.move(-1))
        dlg.favs.setCurrentRow(1)
        self.assertTrue(dlg.remove())
        dlg.labels.setChecked(True)
        dlg.apply()
        self.assertEqual(self.w.favorite_keys(), ['redo', 'undo'])
        from vectordrive.ui import fav_bar
        self.assertTrue(fav_bar.labels_on(self.w.settings))
        self.w.favorite_labels(False)

    def test_search_and_absent_plugin_kept(self):
        self.w.settings.setValue(self.w.FAV_KEY, ['zoom_fit', 'plugin_absent_aujourdhui'])
        dlg = self.w.favorites_dialog(exec_dialog=False)
        self.addCleanup(dlg.deleteLater)
        dlg.find.setText('TOUT VOIR')
        shown = [dlg.all.item(i).data(0x0100) for i in range(dlg.all.count()) if not dlg.all.isRowHidden(i)]
        acts = [self.w.A[k] for k in shown]                       # une ligne par commande (deux clés, une action)
        self.assertIn(self.w.A['zoom_fit'], acts)
        self.assertNotIn(self.w.A['undo'], acts)
        dlg.apply()
        self.assertEqual(self.w._stored_favorites(), ['zoom_fit', 'plugin_absent_aujourdhui'])

    def test_same_command_under_two_keys_once(self):
        by = {}
        for k, act in self.w.A.items():
            by.setdefault(id(act), []).append(k)
        pair = next((v for v in by.values() if len(v) > 1), None)
        if pair is None:
            self.skipTest('aucune commande sous deux clés')
        self.w._save_favorites([pair[1]])
        dlg = self.w.favorites_dialog(exec_dialog=False)
        self.addCleanup(dlg.deleteLater)
        self.assertFalse(dlg.add(pair[0]))
        self.assertEqual(dlg.keys(), [pair[1]])

    def test_menus_offer_the_window(self):
        m = self.w._fav_bar_menu(QPoint(0, 0), exec_menu=False)
        self.addCleanup(m.deleteLater)
        self.assertIn('Gérer les favoris…', [a.text() for a in m.actions()])
        b = QToolButton()
        b.setDefaultAction(self.w.A['zoom_fit'])
        self.addCleanup(b.deleteLater)
        m = self.w._ribbon_button_menu(b, QPoint(0, 0), exec_menu=False)
        self.addCleanup(m.deleteLater)
        self.assertIn('Gérer les favoris…', [a.text() for a in m.actions()])
        self.assertIn('favorites', self.w.A)

    def test_right_click_on_the_bar(self):
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QContextMenuEvent
        bar = self.w.fav_bar
        self.assertIsNotNone(bar)
        seen = []
        self.w._fav_bar_menu = lambda pos, exec_menu=True: seen.append(pos)
        try:
            ev = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(1, 1), QPoint(5, 5))
            self.assertTrue(self.w.eventFilter(bar, ev))
            self.assertEqual(ev.type(), QEvent.Type.ContextMenu)
            self.assertEqual(seen, [QPoint(5, 5)])
        finally:
            del self.w._fav_bar_menu


if __name__ == '__main__':
    unittest.main()
