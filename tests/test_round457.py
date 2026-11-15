"""Round 457 : bibliothèque — « Récents » : les derniers fichiers posés, en tête de l'arbre."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

DXF = ("0\nSECTION\n2\nENTITIES\n0\nLINE\n8\n0\n10\n0\n20\n0\n11\n10\n21\n5\n0\nENDSEC\n0\nEOF\n")


class TestRecents(unittest.TestCase):
    def test_remember_and_show(self):
        from vectordrive.ui import symbols as S
        root = pathlib.Path(tempfile.mkdtemp())
        files = []
        for n in ('a', 'b', 'c'):
            f = root / f'{n}.dxf'
            f.write_text(DXF, encoding='ascii')
            files.append(f)
        st = QSettings(os.path.join(tempfile.mkdtemp(), 'r.ini'), QSettings.Format.IniFormat)
        for f in files + [files[0]]:                                           # a reposé : en tête, sans doublon
            S.remember_recent(st, f)
        self.assertEqual([p.name for p in S.recent_files(st)], ['a.dxf', 'c.dxf', 'b.dxf'])
        files[2].unlink()                                                       # disparu : plus proposé
        self.assertEqual([p.name for p in S.recent_files(st)], ['a.dxf', 'b.dxf'])
        st.setValue('symboles/dossiers', [str(root)])
        p = S.SymbolPanel(st)
        top = p.tree.topLevelItem(0)
        self.assertEqual(top.data(0, Qt.ItemDataRole.UserRole), S.RECENTS)
        p._folder_clicked(top)
        self.assertEqual([p.list.item(i).text() for i in range(p.list.count())], ['a', 'b'])
        self.assertIn('Récents', p.where.text())
        p.size.setValue(120)                                                    # taille changée : toujours les récents
        self.assertEqual(p.list.count(), 2)
        p.deleteLater()

    def test_insert_remembers(self):
        from vectordrive.ui import symbols as S
        from vectordrive.ui.main_window import MainWindow
        f = pathlib.Path(tempfile.mkdtemp()) / 'pose.dxf'
        f.write_text(DXF, encoding='ascii')
        w = MainWindow()
        try:
            w.insert_symbol(str(f))
            self.assertEqual(S.recent_files(w.settings)[0], f)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
