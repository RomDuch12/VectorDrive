"""Round 527 : F10 › Performances — « Mesurer le poste » (géométrie sur 1 fil puis sur les fils de calcul,
lancement d'un processus) et conseil de réglage."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.ui import resources as R

app = QApplication.instance() or QApplication([])


class TestBenchmark(unittest.TestCase):
    def test_measure(self):
        r = R.benchmark()
        self.assertEqual(set(r), {'cores', 'one', 'many', 'threads', 'speedup', 'spawn', 'advice'})
        self.assertGreater(r['one'], 0)
        self.assertGreater(r['spawn'], 0)
        text = R.benchmark_text(r)
        self.assertIn('cœurs', text)
        slow = dict(r, speedup=1.0, threads=8, spawn=6.0, advice=['les fils de calcul aident peu sur ce poste : '
                                                                   '2 fils suffisent'])
        self.assertIn('Conseil', R.benchmark_text(slow))

    def test_button(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            dlg = w.options_dialog(exec_dialog=False, page='Performances')
            fake = {'cores': 4, 'one': 1.0, 'many': 0.5, 'threads': 3, 'speedup': 2.0, 'spawn': 1.0, 'advice': []}
            with mock.patch('vectordrive.ui.progress.run', return_value=fake):
                self.assertEqual(dlg.measure_machine(), fake)
            self.assertIn('4 cœurs', dlg.measure.text())
            self.assertIn('2,0', dlg.measure.text())
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
