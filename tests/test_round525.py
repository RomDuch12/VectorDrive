"""Round 525 : F10 › Performances — nombre de processus des longs travaux (lots, Décaler, vignettes)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import workers

app = QApplication.instance() or QApplication([])


class TestProcessLimit(unittest.TestCase):
    def tearDown(self):
        workers.set_processes(0)
        workers.set_count(0)

    def test_limit(self):
        workers.set_count(15)
        self.assertEqual(workers.process_limit(), workers.PROCESS_MAX)       # automatique
        self.assertEqual(workers.processes(100), workers.PROCESS_MAX)
        workers.set_processes(2)
        self.assertEqual(workers.processes(100), 2)
        self.assertEqual(workers.processes(3), 1)                            # petit travail : à la suite
        workers.set_processes(20)
        self.assertEqual(workers.processes(100), 20)                         # au-delà de 8 si demandé

    def test_option_applied(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.settings.setValue('perf/processus', 3)
            w.apply_options()
            self.assertEqual(workers.process_limit(), 3)
        finally:
            w.settings.setValue('perf/processus', 0)
            w.apply_options()
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
