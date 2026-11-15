"""Round 409 : fichiers récents en grand menu, aperçus de séance."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication, QFileDialog

from vectordrive.core import geom
from vectordrive.core.document import Document, Shape
from vectordrive.io import registry
from vectordrive.ui import recent

app = QApplication.instance() or QApplication([])


def drawing(folder: pathlib.Path, name: str) -> str:
    d = Document()
    d.add(Shape(path=geom.Path([geom.rect(0, 0, 30, 10)])))
    p = folder / name
    registry.save_document(d, str(p))
    return str(p)


class TestRecent(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.a = drawing(self.tmp, 'a.vdz')
        self.b = str(self.tmp / 'parti.vdz')                     # disparu
        recent.set_previews(False)

    def tearDown(self):
        recent.set_previews(False)

    def test_details(self):
        d = recent.file_details(self.a)
        self.assertTrue(d['exists'])
        self.assertEqual(d['name'], 'a.vdz')
        self.assertEqual(d['folder'], str(self.tmp))
        self.assertTrue(d['size'] and d['modified'])
        self.assertFalse(recent.file_details(self.b)['exists'])
        self.assertEqual(recent.human_size(2048), '2,0 Ko')

    def test_panel(self):
        p = recent.RecentPanel([self.a, self.b])
        self.assertEqual(p.tree.topLevelItemCount(), 2)
        self.assertEqual(p.tree.topLevelItem(1).text(3), 'introuvable')
        self.assertFalse(p.preview.isVisibleTo(p))                # aperçus coupés par défaut
        got = []
        p.openRequested.connect(got.append)
        p.b_open.click()
        self.assertEqual(got, [self.a])
        with mock.patch('vectordrive.ui.reveal.reveal', return_value=True) as rv:
            self.assertTrue(p.reveal_current())
            rv.assert_called_once_with(self.a)
        p.b_previews.setChecked(True)                             # allumés pour la séance
        self.assertTrue(recent.previews_on())
        self.assertFalse(p.preview.pixmap().isNull())
        lists = []
        p.listChanged.connect(lists.append)
        p.tree.setCurrentItem(p.tree.topLevelItem(1))
        p.remove_current()
        self.assertEqual(lists[-1], [self.a])
        p.clear()
        self.assertEqual(lists[-1], [])

    def test_open_dialog(self):
        dlg = recent.open_file_dialog(None, 'Ouvrir', str(self.tmp), registry.filter_string())
        self.assertFalse(dlg.testOption(QFileDialog.Option.DontUseNativeDialog))     # coupés : boîte du système
        recent.set_previews(True)
        dlg = recent.open_file_dialog(None, 'Ouvrir', str(self.tmp), registry.filter_string())
        self.assertTrue(dlg.testOption(QFileDialog.Option.DontUseNativeDialog))
        dlg.preview_show(self.a)
        self.assertFalse(dlg.preview_label.pixmap().isNull())

    def test_main_window_menu(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.settings.setValue('fichiers/recents', [self.a, self.b])
            w._fill_recent()
            self.assertEqual(w.recent_panel.tree.topLevelItemCount(), 2)
            with mock.patch.object(w, 'open_path') as op:
                w.recent_panel.b_open.click()
                op.assert_called_once_with(self.a)
            w.recent_panel.tree.setCurrentItem(w.recent_panel.tree.topLevelItem(1))
            w.recent_panel.remove_current()
            self.assertEqual(w._recent(), [self.a])
            w.A['file_previews'].trigger()
            self.assertTrue(recent.previews_on())
            w._fill_recent()
            self.assertTrue(w.recent_panel.b_previews.isChecked())
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
