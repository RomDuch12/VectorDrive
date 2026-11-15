"""Round 373 : compteur de temps de travail par document (TypeEdit :
Afficher le compteur) — ne compte que pendant le travail, gardé dans le
document."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


class TestWorkTime(unittest.TestCase):
    def test_counter(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.canvas.doc.extra.pop('work_time', None)
            w._work_last = w._work_tick_at = 1000.0
            self.assertAlmostEqual(w.work_tick(1060.0), 60.0)            # une minute de travail
            self.assertAlmostEqual(w.work_tick(1300.0), 300.0)           # 5 min après la dernière action : arrêt
            self.assertAlmostEqual(w.work_tick(2000.0), 300.0)           # pause : rien
            w._work_last = 2500.0                                         # reprise (action)
            w._work_tick_at = 2500.0
            self.assertAlmostEqual(w.work_tick(2620.0), 420.0)
            self.assertEqual(w.canvas.doc.extra['work_time'], 420.0)
            w.A['work_time'].setChecked(True)
            w._toggle_work_time(True)
            self.assertIn('0 h 07', w.lbl_work.text())
        finally:
            w.A['work_time'].setChecked(False)
            w._toggle_work_time(False)
            w.modified = False
            w.close()

    def test_saved(self):
        from vectordrive.core.document import Document
        from vectordrive.io import native
        d = Document()
        d.extra['work_time'] = 125.0
        path = os.path.join(tempfile.mkdtemp(), 't.vnd')
        native.write(d, path)
        self.assertEqual(native.read(path).extra.get('work_time'), 125.0)


if __name__ == '__main__':
    unittest.main()
