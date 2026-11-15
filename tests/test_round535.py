"""Round 535 : processus des vignettes lentes rendus après une minute sans travail (et par « Vider les
mémoires ») — ils ne restent pas en mémoire jusqu'à la fermeture."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.ui import symbols as SY

app = QApplication.instance() or QApplication([])


class TestReleaseProcesses(unittest.TestCase):
    def test_release(self):
        pool = SY.preview_processes()
        self.assertIsNotNone(pool)
        self.assertEqual(pool.submit(abs, -3).result(timeout=120), 3)
        self.assertFalse(SY.release_preview_processes())              # servi à l'instant : gardés
        with mock.patch.object(SY, 'PROC_IDLE_S', 0.0):
            self.assertTrue(SY.release_preview_processes())
        self.assertIsNone(SY._PROC_POOL)
        self.assertFalse(SY.release_preview_processes(force=True))    # plus rien
        SY.preview_processes()
        from vectordrive.ui import resources
        resources.clear_all()                                          # « Vider les mémoires »
        self.assertIsNone(SY._PROC_POOL)


if __name__ == '__main__':
    unittest.main()
