"""Round 143 : un bouton de plugin se place juste après un bouton existant
du ruban (`after`), comme le Devis du plugin BFM à côté du BAT ; ID_FILE_COST
de TypeEdit relié au devis ; P (Mode Point) en bascule."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))


class TestRibbon(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_insert_after(self):
        from PySide6.QtGui import QAction
        from PySide6.QtWidgets import QToolButton
        from vectordrive.ui.ribbon import RibbonGroup
        g = RibbonGroup('Essai')
        a, b, c, other = QAction('A'), QAction('B'), QAction('C'), QAction('X')
        g.add(a)
        g.add(b)
        self.assertIsNotNone(g.insert_after(a, c))
        acts = [g._row.itemAt(i).widget().defaultAction() for i in range(g._row.count())
                if isinstance(g._row.itemAt(i).widget(), QToolButton)]
        self.assertEqual(acts, [a, c, b])
        self.assertIsNone(g.insert_after(other, QAction('Y')))

    def test_plugin_action_after(self):
        from vectordrive.plugins import ActionSpec, REGISTRY
        spec = ActionSpec('essai_apres', 'Essai', lambda win: None, 'Fichier', 'Import / export', '', '', '', True,
                          'essai', 'proof')
        REGISTRY.actions.append(spec)
        try:
            from PySide6.QtWidgets import QToolButton
            from vectordrive.ui.main_window import MainWindow
            from vectordrive.ui.ribbon import RibbonGroup
            w = MainWindow()
            try:
                ok = False
                for g in w.ribbon.findChildren(RibbonGroup):
                    acts = [g._row.itemAt(i).widget().defaultAction() for i in range(g._row.count())
                            if isinstance(g._row.itemAt(i).widget(), QToolButton)]
                    if w.A['proof'] in acts:
                        ok = acts[acts.index(w.A['proof']) + 1] is w.A['essai_apres']
                        break
                self.assertTrue(ok)
            finally:
                w.modified = False
                w.close()
        finally:
            REGISTRY.actions.remove(spec)

    def test_node_mode_toggles(self):
        from PySide6.QtWidgets import QApplication
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            node = w.A['tool_node']
            node.trigger()                                   # P : entrer en Mode Point
            QApplication.processEvents()
            self.assertEqual(w.canvas.tool, 'node')
            self.assertTrue(node.isChecked())
            node.trigger()                                   # P encore : sortir
            QApplication.processEvents()
            self.assertEqual(w.canvas.tool, 'select')
            self.assertTrue(w.A['tool_select'].isChecked())
            node.trigger()                                   # et de nouveau entrer
            QApplication.processEvents()
            self.assertEqual(w.canvas.tool, 'node')
            w.set_tool('select')
            w.set_tool('node')                               # entrée par programme
            QApplication.processEvents()
            node.trigger()                                   # le premier appui suivant en sort
            QApplication.processEvents()
            self.assertEqual(w.canvas.tool, 'select')
        finally:
            w.modified = False
            w.close()

    def test_p_key_with_atelier_shortcuts(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertEqual(TE_ACTIONS['ID_COMPO_SHOWPALPOINT'], 'tool_node')
        w = MainWindow()
        try:
            w.A['tool_node'].setShortcut('P')
            w.show()
            w.canvas.setFocus()
            QApplication.processEvents()
            QTest.keyClick(w.canvas, Qt.Key.Key_P)
            QApplication.processEvents()
            self.assertEqual(w.canvas.tool, 'node')
            QTest.keyClick(w.canvas, Qt.Key.Key_P)
            QApplication.processEvents()
            self.assertEqual(w.canvas.tool, 'select')
        finally:
            w.modified = False
            w.close()

    def test_link_typeedit_command(self):
        from vectordrive.plugins import Api
        from vectordrive.ui.shortcuts import TE_ACTIONS
        api = Api.__new__(Api)
        saved = dict(TE_ACTIONS)
        try:
            TE_ACTIONS.pop('ID_ESSAI_PLUGIN', None)
            api.link_typeedit_command('ID_ESSAI_PLUGIN', 'devis_essai')
            self.assertEqual(TE_ACTIONS['ID_ESSAI_PLUGIN'], 'devis_essai')
            api.link_typeedit_command('ID_FILE_SAVE', 'autre')          # déjà relié par VectorDrive : inchangé
            self.assertEqual(TE_ACTIONS['ID_FILE_SAVE'], saved['ID_FILE_SAVE'])
        finally:
            TE_ACTIONS.clear()
            TE_ACTIONS.update(saved)


if __name__ == '__main__':
    unittest.main()
