"""Round 195 : fusionner les parcours du même outil (TypeEdit)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.cam import model


def ops(spec):
    """'A1 B2 A3 I4 B5' : lettre = outil (I = instruction), chiffre = repère."""
    out = []
    for w in spec.split():
        if w[0] == 'I':
            out.append(model.Operation(name=w, kind='instruction'))
        else:
            out.append(model.Operation(name=w, kind='gravure', tool_id=w[0]))
    return out


def names(lst):
    return ' '.join(o.name for o in lst)


class TestGroup(unittest.TestCase):
    def test_anchor(self):
        o = ops('A1 B2 A3 C4 A5')
        self.assertEqual(names(model.group_by_tool(o, 0)), 'A1 A3 A5 B2 C4')
        self.assertEqual(names(model.group_by_tool(o, 2)), 'A1 B2 A3 A5 C4')       # seules les suivantes
        self.assertEqual(model.tool_changes(o), 5)
        self.assertEqual(model.tool_changes(model.group_by_tool(o, 0)), 3)
        i = ops('I0 A1')
        self.assertEqual(names(model.group_by_tool(i, 0)), 'I0 A1')                # instruction : rien

    def test_all_tools_keep_instructions(self):
        o = ops('A1 B2 I3 A4 C5 B6')
        self.assertEqual(names(model.group_by_tool(o)), 'A1 I3 A4 B2 B6 C5')        # I3 reste devant A4
        o[1].enabled = False
        self.assertEqual(model.tool_changes(ops('A1 A2 B3')), 2)


class TestPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_merge_and_undo(self):
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertEqual(TE_ACTIONS['ID_CMD_MERGETP'], 'cam_merge')
        w = MainWindow()
        try:
            panel = w.cam_panel
            s = model.CamSetup()
            s.tools = [model.CamTool(name='A', id='A'), model.CamTool(name='B', id='B')]
            s.operations = ops('A1 B2 A3')
            model.store(w.canvas.doc, s)
            panel.refresh()
            self.assertEqual(panel.merge_tool_ops(), 0)                             # rien de choisi
            panel.ops.selectRow(0)
            self.assertEqual(panel.merge_tool_ops(), 1)
            self.assertEqual(names(model.setup_of(w.canvas.doc).operations), 'A1 A3 B2')
            panel.ops.selectRow(0)
            self.assertEqual(panel.merge_tool_ops(), 0)                             # déjà regroupées
            w.undo()
            self.assertEqual(names(model.setup_of(w.canvas.doc).operations), 'A1 B2 A3')
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
