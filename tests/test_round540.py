"""Round 540 : lecture d'un programme pour le visualiseur et relecture de vérification après un export —
dans le fil de calcul (un gros fichier ne gèle plus la fenêtre)."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


class TestWorkerReads(unittest.TestCase):
    def test_program_read_in_worker(self):
        from vectordrive.ui import progress
        from vectordrive.ui.main_window import MainWindow
        f = pathlib.Path(tempfile.mkdtemp()) / 'p.nc'
        f.write_text('G21 G90\nG0 Z5\nG0 X0 Y0\nG1 Z-0.5\nG1 X10\nM30\n')
        w = MainWindow()
        try:
            real = progress.run
            with mock.patch.object(progress, 'run', side_effect=real) as r:
                tp = w.open_nc_program(str(f), add=False)
            self.assertTrue(r.called)
            self.assertGreater(len(tp.moves), 3)
        finally:
            w.modified = False
            w.close()

    def test_export_verified_in_worker(self):
        from PySide6.QtWidgets import QFileDialog
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        from vectordrive.ui import export_dialog as ED, progress
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.canvas.doc.add(Shape(path=geom.Path([geom.rect(0, 0, 5, 5)])))
            out = pathlib.Path(tempfile.mkdtemp()) / 'a.svg'
            calls = []
            real = progress.run

            def spy(parent, title, fn, *a, **k):
                calls.append(fn.__name__)
                return real(parent, title, fn, *a, **k)
            with mock.patch.object(ED.ExportDialog, 'exec', return_value=1), \
                    mock.patch.object(QFileDialog, 'getSaveFileName', return_value=(str(out), '')), \
                    mock.patch.object(ED.ExportDialog, 'current', return_value={'format': 'svg', 'options': {}}), \
                    mock.patch.object(progress, 'run', side_effect=spy):
                ED.run(w)
            self.assertIn('export_items', calls)
            self.assertIn('verify_export', calls)
            w._export_report.close()
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
