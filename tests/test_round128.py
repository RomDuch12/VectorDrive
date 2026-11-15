"""Round 128 : « Ouvrir le dossier » du programme machine écrit (message de
fin et bouton 📂 du panneau FAO), du dossier de sortie du traitement par
lots ; `ui.reveal`."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from vectordrive.core import geom
from vectordrive.core.document import Shape
from vectordrive.ui import reveal as RV


class TestReveal(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.f = self.tmp / 'prog.nc'
        self.f.write_text('M30')

    def test_file_selected_in_explorer(self):
        with mock.patch.object(RV.sys, 'platform', 'win32'), mock.patch.object(RV.subprocess, 'Popen') as po:
            self.assertTrue(RV.reveal(self.f))
        po.assert_called_once_with(f'explorer /select,"{self.f}"')
        with mock.patch.object(RV.sys, 'platform', 'darwin'), mock.patch.object(RV.subprocess, 'Popen') as po:
            self.assertTrue(RV.reveal(self.f))
        po.assert_called_once_with(['open', '-R', str(self.f)])

    def test_folder_and_missing(self):
        with mock.patch.object(RV.QDesktopServices, 'openUrl', return_value=True) as ou, \
                mock.patch.object(RV.subprocess, 'Popen') as po:
            self.assertTrue(RV.reveal(self.tmp))                        # dossier : ouvert tel quel
            self.assertTrue(RV.reveal(self.tmp / 'parti.nc'))           # fichier disparu : son dossier
            self.assertFalse(RV.reveal(self.tmp / 'x' / 'y' / 'z.nc'))  # rien n'existe
        self.assertEqual(ou.call_count, 2)
        po.assert_not_called()
        self.assertEqual(ou.call_args_list[0].args[0].toLocalFile(), str(self.tmp).replace('\\', '/'))


class TestCamPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.canvas.doc.add(Shape(path=geom.Path([geom.rect(0, 0, 20, 10)])))
        self.p = self.w.cam_panel

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_post_then_open_folder(self):
        p = self.p
        self.assertFalse(p.folder_btn.isEnabled())
        self.assertFalse(p.open_program_folder())                   # rien d'écrit
        p.ops_from_colors()
        p.compute()
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, 'p.nc')
            from tests._posts import registered                     # post-processeurs : plugins (round 218)
            with mock.patch.object(QFileDialog, 'getSaveFileName', return_value=(out, '')), registered():
                p.win.settings.setValue('fao/verifier', False)
                try:
                    p.post_process()
                finally:
                    p.win.settings.remove('fao/verifier')              # réglage remis pour les essais suivants
            self.assertTrue(p.folder_btn.isEnabled())
            self.assertEqual(p.last_program, pathlib.Path(out))
            self.assertIn(out, p.folder_btn.toolTip())
            box = p.done_box
            self.assertTrue(box.isVisible())                         # non bloquant
            self.assertIn(str(pathlib.Path(tmp)), box.text())
            btn = next(b for b in box.buttons() if b.text() == 'Ouvrir le dossier')
            with mock.patch('vectordrive.ui.reveal.reveal', return_value=True) as rv:
                btn.click()
                rv.assert_called_once_with(pathlib.Path(out))
            with mock.patch('vectordrive.ui.reveal.reveal', return_value=True) as rv:
                self.assertTrue(p.open_program_folder())
                rv.assert_called_once_with(pathlib.Path(out))
            with mock.patch('vectordrive.ui.reveal.reveal', return_value=False), \
                    mock.patch.object(QMessageBox, 'information') as info:
                self.assertFalse(p.open_program_folder())               # dossier effacé
                info.assert_called_once()

    def test_typeedit_export_remembered(self):
        p = self.p
        p.ops_from_colors()
        p.compute()
        with tempfile.TemporaryDirectory() as tmp:
            base = os.path.join(tmp, 'parcours.000')
            with mock.patch.object(QFileDialog, 'getSaveFileName', return_value=(base, '')):
                p.export_typeedit()
            self.assertEqual(p.last_program, pathlib.Path(tmp) / 'parcours.000')
            self.assertTrue(p.folder_btn.isEnabled())


class TestBatchDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_open_output_folder(self):
        from vectordrive.ui.batch_dialog import BatchDialog
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            d = BatchDialog(w)
            d.out.setText('')
            self.assertFalse(d.open_out.isEnabled())
            tmp = tempfile.mkdtemp()
            d.out.setText(tmp)
            self.assertTrue(d.open_out.isEnabled())
            with mock.patch('vectordrive.ui.reveal.reveal', return_value=True) as rv:
                self.assertTrue(d.reveal_out())
                rv.assert_called_once_with(tmp)
            d.out.setText(os.path.join(tmp, 'pas_encore'))
            self.assertFalse(d.open_out.isEnabled())
            d.close()
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
