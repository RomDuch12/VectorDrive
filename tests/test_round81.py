"""Round 81 : recherche de commande (Ctrl+K)."""
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')


class TestCommandSearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_fold_and_rank(self):
        from PySide6.QtGui import QAction
        from vectordrive.ui.command_search import fold, rank
        self.assertEqual(fold('Décaler & Poinçonner'), 'decaler  poinconner')
        acts = []
        for key, text, tip in (('offset', 'Décaler', 'Décalage des contours'),
                               ('shadow', 'Ombrage', 'Ombre pleine'),
                               ('hatch', 'Hachures', 'Remplir les contours fermés'),
                               ('close', 'Fermer', 'Fermer les contours ouverts')):
            a = QAction(text)
            a.setToolTip(tip)
            acts.append((key, a))
        self.assertEqual([k for k, _a in rank('decal', acts)], ['offset'])
        self.assertEqual([k for k, _a in rank('OMBR', acts)], ['shadow'])
        r = [k for k, _a in rank('contours', acts)]                     # dans les bulles
        self.assertEqual(set(r), {'offset', 'hatch', 'close'})
        self.assertEqual([k for k, _a in rank('fer cont', acts)][0], 'close')
        self.assertEqual(len(rank('', acts)), 4)

    def test_window_runs_command(self):
        from vectordrive.ui import command_search
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            dlg = command_search.CommandSearch(w, w.A)
            dlg.edit.setText('symétrique dessin')
            self.assertEqual(dlg.list.currentItem().data(0x0100), 'sym_draw')
            orig = command_search.CommandSearch.exec

            def fake_exec(self):
                self.edit.setText('dessin symetrique')
                self.run_current()
                return True
            command_search.CommandSearch.exec = fake_exec
            try:
                w.search_command()
            finally:
                command_search.CommandSearch.exec = orig
            self.assertTrue(w.canvas.symmetric)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
