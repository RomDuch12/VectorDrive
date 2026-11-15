"""Round 133 : barre d'accès rapide de TypeEdit 13 (CONFIG/QATSettings_TE.INI
de l'utilisateur) dans la disposition TypeEdit 13 du ruban."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.ui import typeedit_layout as TL

QAT = """[QAT]
StateOnTop=1
NbCommand=4
QAT_CMD_0=ID_FILE_NEW
QAT_CMD_1=ID_EDIT_UNDO
QAT_CMD_2=ID_COMPO_SHOWPALSHAPE
QAT_CMD_3=ID_INCONNUE
QAT_CMD_4=ID_FILE_SAVE
"""

SCRIPT = """set categoryCAD = configProduct.AddCategoryFromID(307)
set panelMode = categoryCAD.AddPanelFromID(506)
cmd = "ID_COMPO_SHOWPALSHAPE"
set buttonShape = panelMode.AddButton(cmd,true,false)
buttonShape.SetContextID(1001)
set categoryShape = configProduct.AddContextCategoryFromID(316,-1,1001)
set panelShape = categoryShape.AddPanelFromID(316)
cmd = "ID_COMPO_RECTANGLE"
panelShape.AddButton cmd,true,false
"""


class TestQuickAccess(unittest.TestCase):
    def test_parse(self):
        cmds, top = TL.quick_access(QAT)
        self.assertEqual(cmds, ['ID_FILE_NEW', 'ID_EDIT_UNDO', 'ID_COMPO_SHOWPALSHAPE', 'ID_INCONNUE'])  # NbCommand
        self.assertTrue(top)
        self.assertEqual(TL.quick_access('[QAT]\nStateOnTop=0\nNbCommand=1\nQAT_CMD_0=ID_FILE_NEW')[1], False)
        self.assertEqual(TL.quick_access('rien'), ([], True))

    def test_window_bar(self):
        from vectordrive.ui.main_window import MainWindow
        lay = TL.parse(SCRIPT, {307: 'TypeEdit', 316: 'Formes géométriques', 506: 'Mode'})
        lay.quick, lay.quick_on_top = TL.quick_access(QAT)
        QApplication.instance() or QApplication([])
        with mock.patch.object(TL, 'installed', return_value=lay):
            w = MainWindow()
            try:
                w.set_theme('typeedit13')
                bar = w.te_quickbar
                self.assertIsNotNone(bar)
                texts = [a.text() for a in bar.actions()]
                self.assertEqual(texts[:2], [w.A['new'].text(), w.A['undo'].text()])
                self.assertIn('Formes géométriques', texts)               # bouton Mode : onglet contextuel
                self.assertEqual(len(texts), 3)                            # commande inconnue laissée de côté
                box = w.menuWidget().layout()                              # sous les onglets des dessins (215),
                self.assertIs(box.itemAt(box.indexOf(w.doc_bar) + 1).widget(), bar)   # au-dessus du ruban
                self.assertLess(box.indexOf(bar), box.indexOf(w.ribbon))
                w.set_theme('clair')
                self.assertIsNone(w.te_quickbar)                           # ruban de VectorDrive : pas de barre
            finally:
                w.set_theme('clair')
                w.modified = False
                w.close()

    def test_manipzone_is_selection(self):
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertEqual(TE_ACTIONS['ID_COMPO_MANIPZONE'], 'tool_select')


if __name__ == '__main__':
    unittest.main()
