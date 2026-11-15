"""Round 907 : colonnes du panneau des calques réglables en largeur (glisser un bord ; double-clic sur un titre : la
largeur de son contenu ; largeurs retenues d'un lancement à l'autre). Disposition TypeEdit 13 : les deux boutons
« Rapido » de l'onglet Texte deviennent « Texte » et « Texte vertical », chacun avec son icône, et l'onglet
contextuel « Rapido » devient « Mise en forme »."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r907.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QHeaderView, QToolButton

app = QApplication.instance() or QApplication([])

from vectordrive.ui import typeedit_layout as TL  # noqa: E402

SCRIPT = """' onglet Texte et onglet Rapido de TypeEdit 13 (script synthétique, même syntaxe)
set categoryCAD = configProduct.AddCategoryFromID(307)
set panelMode = categoryCAD.AddPanelFromID(506)
cmd = "ID_OPEN_PAL_TEXT"
set buttonText = panelMode.AddButton(cmd,true,false)
buttonText.SetContextID(idContextText)
set categoryText = configProduct.AddContextCategoryFromID(330,-1,idContextText)
set panelBackT = categoryText.AddPanelFromID(599)
cmd = "ID_BACKTO"
set buttonBackT = panelBackT.AddButton(cmd,true,false)
buttonBackT.SetTypeExitContextCategory(true)
set panelText = categoryText.AddPanelFromID(330)
cmd = "ID_COMPO_TEXTLIBRE"
set buttonFree = panelText.AddButton(cmd,true,false)
buttonFree.SetContextID(idContextRapido)
cmd = "ID_COMPO_TEXTVERTICAL"
set buttonVert = panelText.AddButton(cmd,true,false)
buttonVert.SetContextID(idContextRapido)
set categoryRapido = configProduct.AddContextCategoryFromID(331,-1,idContextRapido)
set panelBackR = categoryRapido.AddPanelFromID(599)
cmd = "ID_BACKTO"
set buttonBackR = panelBackR.AddButton(cmd,true,false)
buttonBackR.SetTypeExitContextCategory(true)
set panelRapido = categoryRapido.AddPanelFromID(331)
cmd = "ID_RAPIDO_CHAR_PBMAJ_DLL"
panelRapido.AddButton cmd,true,false
"""
STRINGS = {307: 'TypeEdit', 330: 'Texte', 331: 'Rapido', 506: 'Mode', 599: 'Retour'}


def image(ic):
    return ic.pixmap(32, 32).toImage()


class Base(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.lp = self.w.layers_panel

    def tearDown(self):
        self.w.modified = False
        self.w.close()


class Columns(Base):

    def test_columns_are_adjustable(self):
        h = self.lp.tree.header()
        for c in (self.lp.COL_NAME, self.lp.COL_TOOL):
            self.assertEqual(h.sectionResizeMode(c), QHeaderView.ResizeMode.Interactive)
        self.assertTrue(h.stretchLastSection())
        h.resizeSection(self.lp.COL_NAME, 137)
        self.assertEqual(h.sectionSize(self.lp.COL_NAME), 137)

    def test_widths_are_kept(self):
        h = self.lp.tree.header()
        h.resizeSection(self.lp.COL_NAME, 141)
        h.resizeSection(self.lp.COL_TOOL, 77)
        self.assertEqual(self.w.settings.value(self.lp.WIDTHS_KEY), '141,77')
        self.w.settings.sync()
        from vectordrive.ui.main_window import MainWindow
        other = MainWindow()
        try:
            oh = other.layers_panel.tree.header()
            self.assertEqual((oh.sectionSize(self.lp.COL_NAME), oh.sectionSize(self.lp.COL_TOOL)), (141, 77))
        finally:
            other.modified = False
            other.close()
            self.w.settings.remove(self.lp.WIDTHS_KEY)

    def test_double_click_on_a_title_fits_its_content(self):
        doc = self.w.canvas.doc
        doc.active_layer.name = 'Calque au nom vraiment très long, pour la colonne 907'
        self.lp.refresh()
        self.w.resize(1400, 900)
        self.w.show()
        app.processEvents()
        h = self.lp.tree.header()
        c = self.lp.COL_NAME
        h.resizeSection(c, 30)
        x = h.sectionViewportPosition(c) + 12
        QTest.mouseDClick(h.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                          QPoint(x, h.height() // 2))
        want = self.lp.tree.fontMetrics().horizontalAdvance(doc.active_layer.name)
        self.assertGreaterEqual(h.sectionSize(c), want)
        self.w.settings.remove(self.lp.WIDTHS_KEY)


class TypeEditText(Base):

    def setUp(self):
        super().setUp()
        self.w.settings.setValue('vue/disposition', 'typeedit13')
        with mock.patch.object(TL, 'installed', return_value=TL.parse(SCRIPT, STRINGS)):
            self.assertTrue(self.w.apply_ribbon_layout())

    def tearDown(self):
        self.w.settings.remove('vue/disposition')
        super().tearDown()

    def page(self, key):
        r = self.w.ribbon
        i = next(i for i in range(r.count()) if r.widget(i).property('te_context') == key)
        return i, r.widget(i)

    def test_text_and_vertical_text_not_rapido(self):
        _i, w = self.page('idContextText')
        buttons = {' '.join(b.text().split()): b for b in w.findChildren(QToolButton)}
        self.assertIn('Texte', buttons)
        self.assertIn('Texte vertical', buttons)
        self.assertFalse([t for t in buttons if 'Rapido' in t])
        from vectordrive.ui.icons import icon
        self.assertEqual(image(buttons['Texte'].icon()), image(icon('text_horizontal')))
        self.assertEqual(image(buttons['Texte vertical'].icon()), image(icon('text_vertical')))
        self.assertNotEqual(image(icon('text_horizontal')), image(icon('text_vertical')))

    def test_the_rapido_tab_is_the_formatting_tab(self):
        i, w = self.page('idContextRapido')
        self.assertEqual(self.w.ribbon.tabText(i), 'Mise en forme')
        from vectordrive.ui.ribbon import RibbonGroup
        titles = [g.title.text() for g in w.findChildren(RibbonGroup)]
        self.assertIn('Mise en forme', titles)
        self.assertNotIn('Rapido', titles)

    def test_vertical_text_has_its_own_icon(self):
        from vectordrive.ui.icons import icon
        self.assertEqual(image(self.w.A['text_vertical'].icon()), image(icon('text_vertical')))


if __name__ == '__main__':
    unittest.main()
