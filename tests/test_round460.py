"""Round 460 : 3D — échelle des couleurs de profondeur dans la légende ; bibliothèque — favoris
(fichiers et dossiers, clic droit)."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication

from vectordrive.cam.model import Move, Toolpath

app = QApplication.instance() or QApplication([])

DXF = "0\nSECTION\n2\nENTITIES\n0\nLINE\n8\n0\n10\n0\n20\n0\n11\n10\n21\n5\n0\nENDSEC\n0\nEOF\n"


class TestDepthLegend(unittest.TestCase):
    def test_scale(self):
        from vectordrive.cam import relief as RL
        from vectordrive.core.document import Document
        from vectordrive.ui import view3d as V
        tp = Toolpath(op_id='', tool_id='', name='a')
        tp.moves = [Move('rapid', 0, 0, 5), Move('plunge', 0, 0, -2.5), Move('feed', 10, 0, -2.5)]
        v = V.View3D()
        v.set_relief(RL.from_paths(Document(), [tp], cut=False))
        v.path_colors = 'profondeur'
        rows = v.overlay_lines()
        self.assertIn(('Surface : 0 mm', V.DEPTH_TOP), rows)
        self.assertIn(('Fond : -2,5 mm', V.DEPTH_BOTTOM), rows)
        v.path_colors = 'parcours'
        self.assertFalse(any(t.startswith('Fond') for t, _c in v.overlay_lines()))
        v.deleteLater()


class TestFavorites(unittest.TestCase):
    def test_toggle_and_show(self):
        from vectordrive.ui import symbols as S
        root = pathlib.Path(tempfile.mkdtemp())
        (root / 'Dossier').mkdir()
        f = root / 'plaque.dxf'
        f.write_text(DXF, encoding='ascii')
        st = QSettings(os.path.join(tempfile.mkdtemp(), 'r.ini'), QSettings.Format.IniFormat)
        self.assertTrue(S.toggle_favorite(st, f))
        self.assertTrue(S.toggle_favorite(st, root / 'Dossier'))
        self.assertEqual(S.favorite_paths(st), [f, root / 'Dossier'])
        st.setValue('symboles/dossiers', [str(root)])
        p = S.SymbolPanel(st)
        fav = p.tree.topLevelItem(1)
        self.assertEqual(fav.data(0, Qt.ItemDataRole.UserRole), S.FAVORITES)
        p._folder_clicked(fav)
        rows = [(p.list.item(i).text(), p.list.item(i).data(S.ROLE_KIND)) for i in range(p.list.count())]
        self.assertEqual(rows, [('Dossier', 'dir'), ('plaque', None)])
        p.toggle_favorites([f])                                                 # retiré
        self.assertEqual(S.favorite_paths(st), [root / 'Dossier'])
        self.assertEqual(p.list.count(), 1)
        p.deleteLater()


if __name__ == '__main__':
    unittest.main()
