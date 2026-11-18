"""Round 1078 : demande du 18/11 — « gamme bug liste choix outils ». Dans la gamme multi-outils : « Ajouter un outil » ne
remet plus l'outil d'une ligne existante, deux lignes avec le même outil sont refusées ; la liste des outils est celle
du formulaire d'opération (outils du document, puis « Choisir un outil (Mes outils, bibliothèques)… »), un outil d'une
bibliothèque est copié dans le document quand la gamme est validée."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1078.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.cam import gamme, model  # noqa: E402

BEFORE = 'avant : « Ajouter un outil » remettait un outil déjà dans la gamme ; liste des seuls outils du document'


def setup_and_library():
    s = model.CamSetup(tools=[model.CamTool(name='Fraise 3', kind='fraise', diameter=3.0, number=1),
                              model.CamTool(name='V 60', kind='conique', diameter=6.0, angle=60.0, number=2),
                              model.CamTool(name='Laser', kind='laser', diameter=0.1, number=3)])
    lib = [model.CamTool(name='Fraise 1 atelier', kind='fraise', diameter=1.0, number=2, folder='Atelier'),
           model.CamTool(name='Fraise 3', kind='fraise', diameter=3.0, number=9),          # la même que le document
           model.CamTool(name='Laser lib', kind='laser', diameter=0.1, number=7)]
    return s, lib


def quiet(said=None):
    """QMessageBox.warning sans fenêtre ; `said` reçoit les textes."""
    return mock.patch.object(QMessageBox, 'warning',
                             staticmethod(lambda *a, **k: said.append(a[2]) if said is not None else None))


class Problem(unittest.TestCase):
    """`cam.gamme.problem` : une ligne sans outil, le même outil sur deux lignes."""

    def test_same_tool_twice_and_line_without_tool(self):
        s, _lib = setup_and_library()
        a, b = s.tools[0].id, s.tools[1].id
        self.assertEqual(gamme.problem(s, [gamme.Step(a), gamme.Step(b, 'contournage')], 0.5), '')
        self.assertIn('même outil', gamme.problem(s, [gamme.Step(a), gamme.Step(a)], 0.5), BEFORE)
        self.assertIn('chaque ligne', gamme.problem(s, [gamme.Step(a), gamme.Step('')], 0.5), BEFORE)
        self.assertIn('au moins un outil', gamme.problem(s, [], 0.5))        # comme avant


class Dialog(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui import gamme_dialog as G
        self.assertTrue(hasattr(G, 'tool_combo'), BEFORE)
        self.G = G
        self.s, self.lib = setup_and_library()
        self.d = G.GammeDialog(None, self.s, [gamme.Step(self.s.tools[0].id), gamme.Step(self.s.tools[1].id, 'contournage')],
                               0.5, library=self.lib)
        self.addCleanup(self.d.deleteLater)

    def combo(self, row):
        return self.d.table.cellWidget(row, 0)

    def test_the_list_of_the_operation_form(self):
        from vectordrive.cam import toollib
        from vectordrive.ui.tool_picker import PICK, ToolCombo
        w = self.combo(0)
        self.assertIsInstance(w, ToolCombo)
        texts = [w.itemText(i) for i in range(w.count())]
        self.assertEqual(texts[:2], [toollib.short_label(t) for t in self.s.tools[:2]])   # les outils du document
        self.assertFalse(any('Laser' in t for t in texts))                               # jamais un laser
        self.assertFalse(w.itemIcon(0).isNull())
        self.assertEqual(w.itemData(w.count() - 1), PICK)                                # « Choisir un outil… »
        self.assertEqual([st.tool_id for st in self.d.steps()], [self.s.tools[0].id, self.s.tools[1].id])
        self.assertNotIn(self.lib[2].id, self.d.library)                                 # ni dans les bibliothèques

    def test_a_new_row_never_repeats_a_tool(self):
        d, s = self.d, self.s
        d.add_step()                                                                     # les deux outils sont pris
        w = self.combo(2)
        self.assertEqual(self.G.chosen_key(w), '', BEFORE)                               # « — Choisir un outil — »
        self.assertIn('Choisir', w.currentText())
        said = []
        with quiet(said):
            d.accept()
        self.assertNotEqual(d.result(), d.DialogCode.Accepted)                           # une ligne sans outil : refusée
        self.assertIn('chaque ligne', said[0])
        w.set_key(s.tools[0].id)                                                         # le même que la ligne 1
        with quiet(said):
            d.accept()
        self.assertIn('même outil', said[-1], BEFORE)
        d2 = self.G.GammeDialog(None, s, [gamme.Step(s.tools[1].id)], 0.5)               # un outil libre : pris d'office
        self.addCleanup(d2.deleteLater)
        d2.add_step()
        self.assertEqual(d2.steps()[1].tool_id, s.tools[0].id)

    def test_a_library_tool_is_copied_into_the_document_once(self):
        w = self.combo(1)
        w.set_key('lib:' + self.lib[0].id)                                               # choisi dans Mes outils
        n = len(self.s.tools)
        steps = self.d.steps()
        self.assertEqual(len(self.s.tools), n + 1)
        copy = self.s.tools[-1]
        self.assertEqual(steps[1].tool_id, copy.id)
        self.assertNotEqual(copy.id, self.lib[0].id)
        self.assertEqual((copy.name, copy.diameter, copy.folder), ('Fraise 1 atelier', 1.0, ''))
        self.assertEqual(copy.number, 4)                                                 # le n° 2 est pris : un n° libre
        self.assertEqual(self.d.steps()[1].tool_id, copy.id)                             # une seule copie
        self.assertEqual(len(self.s.tools), n + 1)
        self.combo(0).set_key('lib:' + self.lib[1].id)                                   # le même que le document
        self.assertEqual(self.d.steps()[0].tool_id, self.s.tools[0].id)
        self.assertEqual(len(self.s.tools), n + 1)

    def test_a_refused_gamme_keeps_no_copy(self):
        d, s = self.d, self.s
        self.combo(1).set_key('lib:' + self.lib[0].id)
        d.w_depth.setValue(0.0)                                                          # profondeur nulle : refusée
        n = len(s.tools)
        with quiet():
            d.accept()
        self.assertEqual(len(s.tools), n, 'aucune copie d’outil gardée')
        d.w_depth.setValue(0.5)
        d.accept()
        self.assertEqual(d.result(), d.DialogCode.Accepted)
        self.assertEqual(len(s.tools), n + 1)
        self.assertEqual(d.steps()[1].tool_id, s.tools[-1].id)

    def test_the_choose_line_keeps_the_last_tool(self):
        from vectordrive.ui.tool_picker import PICK
        w = self.combo(0)
        w.blockSignals(True)                                                             # (la fenêtre ne s'ouvre pas)
        w.setCurrentIndex(w.findData(PICK))
        w.blockSignals(False)
        self.assertEqual(self.d.steps()[0].tool_id, self.s.tools[0].id)

    def test_the_tool_column_fits_its_longest_label(self):
        d, G = self.d, self.G
        d.show()
        app.processEvents()
        w = self.combo(0)
        widest = max(w.fontMetrics().horizontalAdvance(w.itemText(i)) for i in range(w.count()))
        self.assertGreaterEqual(d.table.columnWidth(0), max(G.TOOL_WIDTH, min(widest, G.TOOL_WIDTH_MAX)))
        self.assertGreaterEqual(w.view().minimumWidth(), widest)                         # dépliée : les noms entiers
        table, screen = d.table.horizontalHeader().length(), d.screen().availableGeometry().width()
        self.assertGreaterEqual(d.width(), min(table, screen - 80))          # toute la table, dans la limite de l'écran
        d.hide()

    def test_without_library_as_before(self):
        d = self.G.GammeDialog(None, self.s, [gamme.Step(self.s.tools[0].id)], 0.5)
        self.addCleanup(d.deleteLater)
        self.assertEqual(d.table.cellWidget(0, 0).count(), 2)
        self.assertEqual(d.steps()[0].tool_id, self.s.tools[0].id)


class Panel(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui import gamme_dialog as G
        from vectordrive.ui.main_window import MainWindow
        self.assertTrue(hasattr(G, 'tool_combo'), BEFORE)
        self.w = MainWindow()
        self.addCleanup(self.close)
        self.p = self.w.cam_panel

    def close(self):
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()

    def test_the_panel_gives_its_libraries(self):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QListWidget
        from vectordrive.ui.gamme_dialog import chosen_tool
        from vectordrive.ui.tool_picker import ToolCombo
        s, lib = setup_and_library()
        with mock.patch.object(self.p, 'pick_library', lambda: lib):
            d = self.p.gamme_dialog(s, [gamme.Step(s.tools[0].id)], 0.5)
            self.addCleanup(d.deleteLater)
            self.assertIn(lib[0].id, d.library)
            got = self.p._relief_gamme_dialog(s, 0.1, 0.0, run=False)                    # la gamme relief aussi
            self.assertEqual(got[1], '')                                                 # finition : aucune d'office
            dlg = self.p._gamme_dlg
            self.addCleanup(dlg.deleteLater)
            combos = dlg.findChildren(ToolCombo)
            self.assertEqual(len(combos), 2)                                             # ajouter une ébauche, finition
            fin = next(c for c in combos if c is not dlg.add_rough)
            fin.set_key('lib:' + lib[0].id)
            tid = chosen_tool(fin, s, {t.id: t for t in lib})
            self.assertEqual(s.tool(tid).name, 'Fraise 1 atelier')
            rough = dlg.findChild(QListWidget)
            n = rough.count()
            dlg.add_rough.set_key('lib:' + lib[1].id)                                    # déjà dans le document : cochée
            self.assertEqual(rough.count(), n)
            row = next(rough.item(i) for i in range(n) if rough.item(i).data(Qt.ItemDataRole.UserRole) == s.tools[0].id)
            self.assertEqual(row.checkState(), Qt.CheckState.Checked)
            dlg.add_rough.set_key('lib:' + lib[0].id)                                    # (copié par la finition) : sa ligne
            self.assertEqual(rough.count(), n + 1)
            self.assertEqual(rough.item(n).checkState(), Qt.CheckState.Checked)
            self.assertEqual(dlg.add_rough.currentIndex(), 0)                            # la liste revient à « Ajouter… »


if __name__ == '__main__':
    unittest.main()
