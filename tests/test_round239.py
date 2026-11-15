"""Round 239 : choix de l'outil d'une opération par dossiers — la liste ne
montre que les outils du document ; Mes outils (des centaines) s'ouvrent
en arborescence avec recherche."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication, QDialog

app = QApplication.instance() or QApplication([])


def library():
    from vectordrive.cam.model import CamTool
    out = []
    for i in range(300):
        folder = ['Datron/Fraises', 'Datron/Coniques', 'Import TE/Laiton'][i % 3]
        kind = 'conique' if 'Coniques' in folder else 'fraise'
        out.append(CamTool(name=f'Outil {i}', kind=kind, diameter=1 + i % 7, angle=30.0 if kind == 'conique' else 0,
                           number=i + 1, ref=f'REF{i:04d}', folder=folder))
    return out


class TestToolPicker(unittest.TestCase):
    def setUp(self):
        from vectordrive.cam import model
        from vectordrive.ui.cam_panel import FieldsDialog
        self.lib = library()
        self.doc_tool = model.CamTool(name='Fraise du document', kind='fraise', diameter=2.0, number=1)
        self.op = model.Operation(kind='contour', tool_id=self.doc_tool.id)
        self.dlg = FieldsDialog(None, 'essai', self.op, None, [self.doc_tool], library=self.lib)
        self.combo = self.dlg.widgets['tool_id']

    def tearDown(self):
        self.dlg.deleteLater()

    def test_short_list(self):
        c = self.combo
        datas = [c.itemData(i) for i in range(c.count())]
        self.assertEqual([d for d in datas if d], [self.doc_tool.id, '__choisir__'])
        self.assertEqual(c.currentData(), self.doc_tool.id)

    def test_find_adds_library_tool(self):
        c = self.combo
        t = self.lib[42]
        i = c.findData('lib:' + t.id)
        self.assertGreaterEqual(i, 0)
        self.assertEqual(c.itemData(c.count() - 1), '__choisir__')        # toujours la dernière ligne
        self.assertEqual(c.findText(f'📁 {t.folder} — {t.name}'), i)
        c.setCurrentIndex(i)
        self.dlg.apply()
        self.assertEqual(self.dlg.new_tools[0].name, 'Outil 42')
        self.assertEqual(self.op.tool_id, self.dlg.new_tools[0].id)

    def test_picker_tree_and_search(self):
        from vectordrive.ui.tool_picker import ToolPickerDialog
        c = self.combo
        pick = c.choose(exec_dialog=False)
        self.assertIsInstance(pick, ToolPickerDialog)
        tops = [pick.tree.topLevelItem(i).text(0) for i in range(pick.tree.topLevelItemCount())]
        self.assertEqual(tops, ['Outils du document', '📁 Datron  (200)', '📁 Import TE  (100)'])
        pick.search.setText('REF0100')
        cur = pick.tree.currentItem()
        self.assertEqual(cur.text(0).split(' — ')[0], 'Outil 100')            # 1016 : le n° T dans sa colonne
        visible = [it for it in pick._items() if it.data(0, 0x0100) and not it.isHidden()]
        self.assertEqual(len(visible), 1)
        pick._pick(cur)
        self.assertEqual(pick.choice, 'lib:' + self.lib[100].id)
        pick.deleteLater()

    def test_choose_selects(self):
        from vectordrive.ui import tool_picker as TP
        target = 'lib:' + self.lib[7].id

        def fake_exec(d):
            d.choice = target
            return QDialog.DialogCode.Accepted
        with mock.patch.object(TP.ToolPickerDialog, 'exec', fake_exec):
            self.assertEqual(self.combo.choose(), target)
        self.assertEqual(self.combo.currentData(), target)
        self.assertEqual(self.dlg.current_tool().name, 'Outil 7')

        def cancel(d):
            return QDialog.DialogCode.Rejected
        self.combo.setCurrentIndex(self.combo.findData('__choisir__'))   # la ligne « Choisir… », puis annuler
        with mock.patch.object(TP.ToolPickerDialog, 'exec', cancel):
            self.assertIsNone(self.combo.choose())
        self.assertEqual(self.combo.currentData(), target)              # le choix d'avant revient


if __name__ == '__main__':
    unittest.main()
