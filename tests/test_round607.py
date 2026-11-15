"""Round 607 : automatisme 3D — un outil à créer n'est proposé qu'une fois quand deux étapes le demandent ;
fenêtre : les anciens widgets du tableau sont cachés tout de suite quand il est rempli de nouveau."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.cam import auto3d as A

app = QApplication.instance() or QApplication([])


class TestShared(unittest.TestCase):
    def test_one_new_ball(self):
        seq = A.all_sequences()['Ébauche, reprise, finition des pentes et des parois'][1]
        out = A.plan(seq, [], [], A.PartInfo(80, 60, 15, 0.5, 60))
        balls = [p for p in out if p.tool.kind == 'boule']
        self.assertEqual(len(balls), 2)
        self.assertIs(balls[0].tool, balls[1].tool)                    # une seule boule à créer
        self.assertTrue(all(p.origin == 'nouveau' for p in out))
        mills = {id(p.tool) for p in out if p.tool.kind == 'fraise'}
        self.assertEqual(len(mills), 2)                                # Ø12 et Ø6 : deux fraises différentes


class TestTable(unittest.TestCase):
    def test_old_widgets_hidden(self):
        from vectordrive.core import solids as SO
        if not SO.available():
            self.skipTest('manifold3d absent')
        from tests.test_round591 import pocket_stl
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.open_path(pocket_stl())
            w._ensure_panel3d()
            w.panel3d.refresh()
            dlg = w.panel3d.auto3d(exec_dialog=False)
            old = dlg.table.cellWidget(0, 2)
            dlg.add_step()                                             # le tableau est rempli de nouveau
            self.assertTrue(old.isHidden())
            self.assertIn('outil(s) à créer', dlg.summary.text())
            created = [part for part in dlg.summary.text().split(' — ') if 'à créer' in part][0]
            self.assertEqual(created.count('Fraise boule Ø1'), 1)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
