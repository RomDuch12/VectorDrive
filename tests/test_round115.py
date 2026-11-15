"""Round 115 : traitement par lots (conversion de dessins et de dossiers,
BAT au choix, arborescence gardée, fichiers abîmés signalés)."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Document, Shape
from vectordrive.io import batch, registry
from vectordrive.ui import progress as UP


def make_tree():
    root = pathlib.Path(tempfile.mkdtemp())
    (root / 'sous').mkdir()
    for name in ('a.vdz', 'sous/b.vdz'):
        d = Document()
        d.add(Shape(path=geom.Path([geom.rect(0, 0, 10, 5)])))
        registry.save_document(d, root / name)
    (root / 'abime.dxf').write_text('pas un dxf', encoding='utf-8')
    (root / 'notes.txt').write_text('ignoré', encoding='utf-8')
    return root


class TestBatch(unittest.TestCase):
    def test_collect(self):
        root = make_tree()
        files = batch.collect([root, root / 'a.vdz'])
        self.assertEqual(sorted(f.name for f in files), ['a.vdz', 'abime.dxf', 'b.vdz'])
        self.assertEqual(len(batch.collect([root], recursive=False)), 2)

    def test_convert_tree_and_errors(self):
        QApplication.instance() or QApplication([])
        root = make_tree()
        out = pathlib.Path(tempfile.mkdtemp())
        res = batch.convert(batch.collect([root]), out, 'dxf', keep_tree_from=root, proof=True)
        self.assertEqual(len(res.done), 2)
        self.assertEqual(len(res.errors), 1)
        self.assertTrue((out / 'a.dxf').is_file())
        self.assertTrue((out / 'sous' / 'b.dxf').is_file())
        self.assertTrue((out / 'a_BAT.pdf').is_file())
        back = registry.open_document(out / 'sous' / 'b.dxf')
        self.assertEqual(len(list(back.iter_leaves())), 1)
        again = batch.convert(batch.collect([root]), out, 'dxf', keep_tree_from=root)
        self.assertEqual(len(again.skipped), 2)                            # déjà là
        self.assertIn('converti', again.summary())

    def test_cancel(self):
        QApplication.instance() or QApplication([])
        root = make_tree()
        UP.AUTO_CANCEL_AFTER_MS = 0
        try:
            import shutil
            for i in range(150):                    # fichiers distincts (un doublon de sortie est ignoré d'avance)
                shutil.copyfile(root / 'a.vdz', root / f'copie{i:03d}.vdz')
            files = batch.collect([root])
            with self.assertRaises(UP.Cancelled):
                UP.run(None, 'essai', batch.convert, files, tempfile.mkdtemp(), 'svg', overwrite=True)
        finally:
            UP.AUTO_CANCEL_AFTER_MS = None

    def test_dialog(self):
        QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            dlg = w.batch_dialog(exec_dialog=False)
            root = make_tree()
            dlg.add_paths([str(root)])
            dlg.add_paths([str(root)])
            self.assertEqual(dlg.list.count(), 1)
            dlg.out.setText(tempfile.mkdtemp())
            dlg.fmt.setCurrentIndex(dlg.fmt.findData('svg'))
            res = dlg.run()
            self.assertEqual(len(res.done), 2)
            self.assertIn('2 converti', dlg.report.toPlainText())
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
