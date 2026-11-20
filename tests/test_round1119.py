"""Round 1119 : un bouton Mode du ruban TypeEdit dont la commande est une palette (Manipulation, Alignement…) ouvre son
onglet sans la fenêtre flottante au pointeur (demande du 20/11)."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1119.ini'))
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.ui import typeedit_layout as TL  # noqa: E402

SCRIPT = """' script de ruban synthétique (même syntaxe que TypeEdit)
set categoryCAD = configProduct.AddCategoryFromID(307)
set panelMode = categoryCAD.AddPanelFromID(506)
cmd = "ID_COMPO_SHOWPALTRANSFORMATION"
set b1 = panelMode.AddButton(cmd,true,false)
b1.SetContextID(1002)
cmd = "ID_COMPO_SHOWPALALIGN"
set b2 = panelMode.AddButton(cmd,true,false)
b2.SetContextID(1003)
cmd = "ID_COMPO_SHOWPALSHAPE"
set b3 = panelMode.AddButton(cmd,true,false)
b3.SetContextID(1001)
cmd = "ID_COMPO_SHOWPALDUPLICATION"
set b4 = panelMode.AddButton(cmd,true,false)
b4.SetContextID(1006)
cmd = "ID_COMPO_SHOWPALPOINT"
set b5 = panelMode.AddButton(cmd,true,false)
b5.SetContextID(1009)
cmd = "ID_COMPO_ENVELOPPE"
set b6 = panelMode.AddButton(cmd,true,false)
b6.SetContextID(1007)
cmd = "ID_COMPO_CHISEL_EFFECT"
set b7 = panelMode.AddButton(cmd,true,false)
b7.SetContextID(1008)
set c1 = configProduct.AddContextCategoryFromID(316,-1,1001)
set s1 = c1.AddPanelFromID(599)
cmd = "ID_BACKTO"
set k1 = s1.AddButton(cmd,true,false)
k1.SetTypeExitContextCategory(true)
set p1 = c1.AddPanelFromID(316)
cmd = "ID_COMPO_RECTANGLE"
p1.AddButton cmd,true,false
set c2 = configProduct.AddContextCategoryFromID(317,-1,1002)
set s2 = c2.AddPanelFromID(599)
cmd = "ID_BACKTO"
set k2 = s2.AddButton(cmd,true,false)
k2.SetTypeExitContextCategory(true)
set p2 = c2.AddPanelFromID(317)
cmd = "ID_COMPO_RECTANGLE"
p2.AddButton cmd,true,false
set c3 = configProduct.AddContextCategoryFromID(318,-1,1003)
set s3 = c3.AddPanelFromID(599)
cmd = "ID_BACKTO"
set k3 = s3.AddButton(cmd,true,false)
k3.SetTypeExitContextCategory(true)
set p3 = c3.AddPanelFromID(318)
cmd = "ID_COMPO_RECTANGLE"
p3.AddButton cmd,true,false
set c4 = configProduct.AddContextCategoryFromID(319,-1,1006)
set s4 = c4.AddPanelFromID(599)
cmd = "ID_BACKTO"
set k4 = s4.AddButton(cmd,true,false)
k4.SetTypeExitContextCategory(true)
set p4 = c4.AddPanelFromID(319)
cmd = "ID_COMPO_DUPSURCOURBE"
p4.AddButton cmd,true,false
set c5 = configProduct.AddContextCategoryFromID(320,-1,1009)
set s5 = c5.AddPanelFromID(599)
cmd = "ID_BACKTO"
set k5 = s5.AddButton(cmd,true,false)
k5.SetTypeExitContextCategory(true)
set p5 = c5.AddPanelFromID(320)
cmd = "ID_RETOUCHE_STARTPOINT"
p5.AddButton cmd,true,false
set c6 = configProduct.AddContextCategoryFromID(321,-1,1007)
set p6 = c6.AddPanelFromID(321)
cmd = "ID_REGLAGE_INCONNU_ENVELOPPE"
p6.AddButton cmd,true,false
set c7 = configProduct.AddContextCategoryFromID(322,-1,1008)
set s7 = c7.AddPanelFromID(599)
cmd = "ID_BACKTO"
set k7 = s7.AddButton(cmd,true,false)
k7.SetTypeExitContextCategory(true)
set p7 = c7.AddPanelFromID(322)
cmd = "ID_REGLAGE_INCONNU_OMBRAGE"
p7.AddButton cmd,true,false
"""
STRINGS = {307: 'TypeEdit', 316: 'Formes géométriques', 317: 'Manipulation', 318: 'Alignement', 319: 'Duplication', 320: 'Point', 321: 'Enveloppe', 322: 'Ombrage', 506: 'Mode', 599: 'Retour'}


def palettes():
    return [w for w in QApplication.topLevelWidgets()
            if isinstance(w, QWidget) and w.objectName() == 'tePalette' and w.isVisible()]


class ModeButtons(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        TL._cache.clear()
        cls.patcher = mock.patch.object(TL, 'installed', return_value=TL.parse(SCRIPT, STRINGS))
        cls.patcher.start()
        cls.w = MainWindow()
        cls.w.set_theme('typeedit13')

    @classmethod
    def tearDownClass(cls):
        cls.w.set_theme('clair')                         # (le thème est retenu : les essais suivants)
        cls.patcher.stop()
        TL._cache.clear()
        cls.w.modified = False
        cls.w.close()

    def setUp(self):
        for p in palettes():
            p.close()

    def mode(self, text):
        return next(a for a in self.w._te_actions if a.text() == text)

    def test_family_opens_its_tab_without_floating_window(self):
        r = self.w.ribbon
        for name in ('Manipulation', 'Alignement', 'Formes géométriques'):
            self.mode(name).trigger()
            app.processEvents()
            self.assertEqual(r.tabText(r.currentIndex()), name)
            self.assertEqual(palettes(), [], f'{name} : avant, une palette flottante paraissait au pointeur')
            self.w.close_te_contexts()

    def test_family_launches_no_command(self):
        fired = []
        self.w.A['duplicate'].triggered.connect(lambda *_: fired.append(1))
        self.mode('Duplication').trigger()
        app.processEvents()
        self.assertEqual(self.w.ribbon.tabText(self.w.ribbon.currentIndex()), 'Duplication')
        self.assertEqual(fired, [], 'avant : la boîte Dupliquer (ou « Sélectionnez au moins un objet ») au clic')
        self.w.close_te_contexts()

    def test_tool_family_keeps_its_tool(self):
        fired = []
        self.w.A['tool_node'].triggered.connect(lambda *_: fired.append(1))
        self.mode('Point').trigger()
        app.processEvents()
        self.assertEqual(fired, [1], 'Point : l\'outil pris, comme dans TypeEdit')
        self.w.close_te_contexts()

    def tab_actions(self, name):
        r = self.w.ribbon
        page = next(r.widget(i) for i in range(r.count()) if r.tabText(i) == name and r.widget(i).property('te_context'))
        from vectordrive.ui.ribbon import RibbonGroup
        out = {}
        for g in page.findChildren(RibbonGroup):
            out[g.title.text()] = [b.defaultAction() for b, _big in g._entries if hasattr(b, 'defaultAction')]
        return out

    def test_tab_gets_the_rest_of_its_palette(self):
        acts = self.tab_actions('Manipulation')
        self.assertIn('VectorDrive', acts, 'les commandes de la palette qui manquaient à l\'onglet')
        self.assertIn(self.w.A['rot90'], acts['VectorDrive'])
        self.assertIn(self.w.A['sym_point'], acts['VectorDrive'])
        every = [a for v in acts.values() for a in v]
        self.assertEqual(len(every), len(set(map(id, every))), 'aucune commande en double')
        align = self.tab_actions('Alignement')
        self.assertIn(self.w.A['space_h'], align['VectorDrive'])

    def test_family_command_in_its_tab(self):
        dup = self.tab_actions('Duplication')
        every = [a for v in dup.values() for a in v]
        self.assertEqual(every.count(self.w.A['duplicate']), 1, 'Dupliquer : déjà dans son onglet, pas en double')
        shade = self.tab_actions('Ombrage')
        self.assertIn(self.w.A['shadow'], shade['VectorDrive'], 'un onglet de réglages de TypeEdit seulement')

    def test_family_without_tab_keeps_its_command(self):
        r = self.w.ribbon
        self.assertFalse(any(r.tabText(i) == 'Enveloppe' and r.widget(i).property('te_context')
                             for i in range(r.count())), 'rien de connu dans son onglet : retiré')
        with mock.patch.object(self.w, 'show_te_context') as show:
            self.mode('Enveloppe').trigger()
        self.assertEqual(show.call_count, 1)
        self.assertIs(show.call_args[0][1], self.w.A['envelope'], 'sans onglet, le bouton lance sa commande')

    def test_tooltip_without_palette_name(self):
        tip = self.mode('Alignement').toolTip()
        self.assertTrue(tip.startswith('Alignement'))
        self.assertNotIn(' — ', tip)

    def test_palette_shortcut_still_opens_its_window(self):
        self.w.A['palette_align'].trigger()              # son raccourci, Chercher une commande : la palette reste
        app.processEvents()
        pals = palettes()
        self.assertEqual(len(pals), 1)
        self.assertTrue(pals[0].windowFlags() & Qt.WindowType.Tool)
        pals[0].close()


if __name__ == '__main__':
    unittest.main()
