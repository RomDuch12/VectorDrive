"""Round 25 : fichiers abîmés (fuzzing) et vérification du dessin avant
gravure."""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import check as CK
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape, Text
from vectordrive.core.geom import Contour, Line, Path
from vectordrive.io import registry

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'outils'))


def shape(*contours, tool=0):
    return Shape(path=Path(list(contours)), tool=tool)


def almost_closed(gap=0.05):
    return Contour([Line((0, 0), (10, 0)), Line((10, 0), (10, 10)), Line((10, 10), (0, gap))], False)


def sample_doc():
    d = Document()
    d.plate = Plate(100, 50)
    d.add(shape(geom.rect(10, 10, 20, 10)))                     # correct
    d.add(shape(geom.circle((98, 25), 5)))                      # dépasse
    d.add(shape(almost_closed()))                                # presque fermé
    d.add(shape(geom.rect(50, 30, 0.01, 0.01)))                 # poussière
    d.add(shape(geom.rect(60, 5, 10, 10)))
    d.add(shape(geom.rect(60, 5, 10, 10)))                       # doublon
    d.add(Text(text='ABC', outline=None))                        # sans glyphes
    d.add(shape(geom.rect(40, 40, 5, 5), tool=99))               # outil absent
    hidden = shape(geom.rect(1, 1, 2, 2))
    hidden.visible = False
    d.add(hidden)
    d.layers.append(Layer(name='vide'))
    return d


class TestMutations(unittest.TestCase):
    def test_reproducible(self):
        import fuzz
        data = bytes(range(256)) * 8
        for seed in range(10):
            self.assertEqual(fuzz.mutate(data, seed), fuzz.mutate(data, seed))
        self.assertNotEqual(fuzz.mutate(data, 0), data)

    def test_damaged_files_fail_cleanly(self):
        d = Document()
        d.add(shape(geom.rect(0, 0, 40, 20, 3)))
        d.add(shape(geom.circle((20, 10), 5)))
        with tempfile.TemporaryDirectory() as tmp:
            files = []
            for ext in ('.svg', '.dxf', '.vdz'):
                f = pathlib.Path(tmp) / f'f{ext}'
                registry.save_document(d, f)
                files.append(str(f))
            r = subprocess.run([sys.executable, str(ROOT / 'outils' / 'fuzz.py'), '--n', '15', '--timeout', '20',
                                *files], capture_output=True, text=True, encoding='utf-8', timeout=300)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('0 problème(s)', r.stdout)


class TestCheck(unittest.TestCase):
    def test_issues(self):
        issues = {i.code: i for i in CK.check(sample_doc())}
        self.assertEqual(set(issues), {'texte_vide', 'outil_absent', 'hors_plaque', 'presque_ferme', 'poussiere',
                                       'doublon', 'masque', 'calque_vide'})
        self.assertEqual(issues['doublon'].count, 1)
        self.assertEqual(issues['hors_plaque'].count, 1)
        self.assertEqual(issues['masque'].count, 1)
        self.assertTrue(issues['presque_ferme'].fixable)
        self.assertFalse(issues['hors_plaque'].fixable)
        sev = [i.severity for i in CK.check(sample_doc())]
        self.assertEqual(sev, sorted(sev, key=CK.SEVERITIES.index))
        self.assertEqual(issues['presque_ferme'].text(), 'Contour presque fermé (écart ≤ 0.1 mm) : à fermer (1)')

    def test_clean_drawing(self):
        d = Document()
        d.plate = Plate(100, 50)
        d.add(shape(geom.rect(10, 10, 20, 10)))
        self.assertEqual(CK.check(d), [])

    def test_fixes(self):
        s = CK.fix_item(shape(almost_closed()), 'presque_ferme')
        self.assertTrue(s.path.contours[0].closed)
        self.assertEqual(len(s.path.contours[0].segments), 4)
        self.assertIsNone(CK.fix_item(shape(geom.rect(0, 0, 0.01, 0.01)), 'poussiere'))
        mixed = CK.fix_item(shape(geom.rect(0, 0, 0.01, 0.01), geom.rect(5, 5, 5, 5)), 'poussiere')
        self.assertEqual(len(mixed.path.contours), 1)
        far = shape(Contour([Line((0, 0), (10, 0)), Line((10, 0), (10, 10)), Line((10, 10), (0, 2))], False))
        self.assertFalse(CK.fix_item(far, 'presque_ferme').path.contours[0].closed)


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_dialog_fix(self):
        from vectordrive.ui.checkdlg import CheckDialog
        w = self.w
        w._add_items([shape(almost_closed()), shape(geom.rect(0, 0, 0.01, 0.01))])
        dlg = CheckDialog(w)
        codes = [i.code for i in dlg.issues]
        self.assertIn('presque_ferme', codes)
        dlg.list.setCurrentRow(codes.index('presque_ferme'))
        dlg.select()
        self.assertEqual(len(w.canvas.selection), 1)
        dlg.fix()
        codes = [i.code for i in dlg.issues]
        self.assertNotIn('presque_ferme', codes)
        dlg.list.setCurrentRow(codes.index('poussiere'))
        dlg.fix()
        self.assertNotIn('poussiere', [i.code for i in dlg.issues])
        w.undo()
        self.assertIn('poussiere', [i.code for i in CK.check(w.canvas.doc)])

    def test_machine_export_confirmation(self):
        w = self.w
        w._add_items([shape(geom.rect(10, 10, 5, 5))])
        self.assertTrue(w._confirm_machine_export())


if __name__ == '__main__':
    unittest.main()
