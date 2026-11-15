"""Round 242 : Ctrl+1 à Ctrl+9 de TypeEdit (vues XY, YZ, ZX, graveur,
isométrique, dynamique ; sens, aperçu, remplissage) ; dans le ruban de
TypeEdit, onglets « TypeEdit » et « TypeArt » renommés 2.5D et 3D."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.ui import typeedit_layout as TL

app = QApplication.instance() or QApplication([])

SCRIPT = """set categoryCAD = configProduct.AddCategoryFromID(307)
set panelMode = categoryCAD.AddPanelFromID(506)
cmd = "ID_COMPO_SHOWPALSHAPE"
set buttonShape = panelMode.AddButton(cmd,true,false)
buttonShape.SetContextID(1001)
set categoryArt = configProduct.AddCategoryFromID(308)
set panelArt = categoryArt.AddPanelFromID(507)
cmd = "ID_GALBE_NEWGALBE"
panelArt.AddButton cmd,true,false
cmd = "ID_TART_EXTRUSION"
panelArt.AddButton cmd,true,false
cmd = "ID_TART_REVOLUTION"
panelArt.AddButton cmd,true,false
cmd = "ID_TART_SWEEPING"
panelArt.AddButton cmd,true,false
cmd = "ID_TART_WEAVE"
panelArt.AddButton cmd,true,false
cmd = "ID_SCULPT"
panelArt.AddButton cmd,true,false
set categoryShape = configProduct.AddContextCategoryFromID(316,-1,1001)
set panelShape = categoryShape.AddPanelFromID(316)
cmd = "ID_COMPO_RECTANGLE"
panelShape.AddButton cmd,true,false
"""


class TestKeys(unittest.TestCase):
    def test_ctrl_digits(self):
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.shortcuts import TE_ACTIONS
        w = MainWindow()
        try:
            keys = {w.A[k].shortcut().toString(): k for k in ('view_2d', 'view_yz', 'view_zx', 'view_engraver',
                                                              'view_iso', 'view_3d', 'direction',
                                                              'tool_colors', 'fill')}
            self.assertEqual([keys[f'Ctrl+{i}'] for i in range(1, 10)],
                             ['view_2d', 'view_yz', 'view_zx', 'view_engraver', 'view_iso', 'view_3d', 'direction',
                              'tool_colors', 'fill'])
            self.assertEqual((TE_ACTIONS['ID_AFFICHAGE_VUE3DGRAVEUR'], TE_ACTIONS['ID_AFFICHAGE_VUE3DISOMETRIQUE'],
                              TE_ACTIONS['ID_AFFICHAGE_DYNAMIC']), ('view_engraver', 'view_iso', 'view_3d'))
            w.A['view_engraver'].trigger()
            self.assertEqual(w.view_mode(), '3d')
            from vectordrive.ui.view3d import VIEWS
            v = w.panel3d.view
            self.assertEqual((v.yaw, v.pitch), VIEWS['graveur'])
            w.A['view_iso'].trigger()
            self.assertEqual((v.yaw, v.pitch), VIEWS['iso'])
            v.yaw = 123.0
            w.A['view_3d'].trigger()                                       # dynamique : l'angle reste
            self.assertEqual(v.yaw, 123.0)
            w.A['view_2d'].trigger()
            self.assertEqual(w.view_mode(), '2d')
        finally:
            w.modified = False
            w.close()


class TestTabs(unittest.TestCase):
    def test_tabs_renamed(self):
        from vectordrive.ui.main_window import MainWindow
        lay = TL.parse(SCRIPT, {307: 'TypeEdit', 308: 'TypeArt', 316: 'Formes géométriques', 506: 'Mode',
                                507: 'Outils'})
        with mock.patch.object(TL, 'installed', return_value=lay):
            w = MainWindow()
            try:
                w.set_theme('typeedit13')
                r = w.ribbon
                titles = [r.tabText(i) for i in range(r.count()) if r.isTabVisible(i)]
                self.assertIn('CAD', titles)                             # round 903 : « 2.5D » et « 3D » deviennent CAD
                self.assertNotIn('2.5D', titles)
                self.assertNotIn('3D', titles)
                self.assertNotIn('TypeEdit', titles)
                self.assertNotIn('TypeArt', titles)
                w.set_view_mode('3d')                                    # le CAD du mode 3D : l'ancien « TypeArt »
                titles = [r.tabText(i) for i in range(r.count()) if r.isTabVisible(i)]
                i = titles.index('CAD')
                page = [r.widget(k) for k in range(r.count()) if r.isTabVisible(k)][i]
                w.set_view_mode('2d')
                from PySide6.QtWidgets import QToolButton
                acts = {b.defaultAction() for b in page.findChildren(QToolButton)}
                self.assertIn(w.A['view_engraver'], acts)
                self.assertIn(w.A['galbe'], acts)
                self.assertTrue(r.widget(w._te_main_index()).property('te_main'))
            finally:
                w.set_theme('clair')
                w.modified = False
                w.close()


if __name__ == '__main__':
    unittest.main()
