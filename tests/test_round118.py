"""Round 118 : vérification de dessins (lecture seule, rapport CSV, ligne de
commande --verifier) pour les fichiers nouveaux venus de l'atelier."""
import csv
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Document, Shape
from vectordrive.io import batch, registry

ROOT = pathlib.Path(__file__).resolve().parents[1]


def make_tree():
    root = pathlib.Path(tempfile.mkdtemp())
    d = Document()
    d.add(Shape(path=geom.Path([geom.rect(0, 0, 10, 5), geom.circle((20, 2), 2)])))
    registry.save_document(d, root / 'bon.vdz')
    (root / 'abime.dxf').write_text('pas un dxf', encoding='utf-8')
    return root


class TestCheck(unittest.TestCase):
    def setUp(self):
        QApplication.instance() or QApplication([])

    def test_check_and_csv(self):
        root = make_tree()
        rows = batch.check(batch.collect([root]))
        by = {pathlib.Path(r['fichier']).name: r for r in rows}
        self.assertTrue(by['bon.vdz']['lu'])
        self.assertEqual(by['bon.vdz']['contours'], 2)
        self.assertFalse(by['abime.dxf']['lu'])
        self.assertTrue(by['abime.dxf']['erreur'])
        self.assertIn('1 en erreur', batch.check_summary(rows))
        out = batch.write_csv(rows, root / 'rapport' / 'v.csv')
        with open(out, encoding='utf-8-sig', newline='') as fh:
            got = list(csv.DictReader(fh, delimiter=';'))
        self.assertEqual(len(got), 2)
        self.assertEqual({r['lu'] for r in got}, {'oui', 'non'})

    def test_dialog_check(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            dlg = w.batch_dialog(exec_dialog=False)
            root = make_tree()
            dlg.add_paths([str(root)])
            out = tempfile.mkdtemp()
            dlg.out.setText(out)
            rows = dlg.check()
            self.assertEqual(len(rows), 2)
            self.assertTrue((pathlib.Path(out) / 'verification.csv').is_file())
            self.assertIn('abime.dxf', dlg.report.toPlainText())
        finally:
            w.modified = False
            w.close()

    def test_command_line(self):
        root = make_tree()
        out = root / 'r.csv'
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen', PYTHONIOENCODING='utf-8')
        r = subprocess.run([sys.executable, str(ROOT / 'VectorDrive.py'), '--verifier', str(root), '--out', str(out)],
                           capture_output=True, text=True, encoding='utf-8', env=env, timeout=120)
        self.assertEqual(r.returncode, 1)                                 # un fichier en erreur
        self.assertIn('bon.vdz', r.stdout)
        self.assertIn('ERREUR', r.stdout)
        self.assertTrue(out.is_file())


if __name__ == '__main__':
    unittest.main()
