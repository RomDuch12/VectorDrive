"""Round 499 : carte graphique de la vue 3D (postes à deux cartes) — variable du processus avant Qt,
préférence de Windows pour l'exécutable installé seulement, option F10 › Affichage."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive import gpu

app = QApplication.instance() or QApplication([])
EXE = r'C:\VD\VectorDrive.exe'


class TestGpu(unittest.TestCase):
    def test_apply_and_read(self):
        reg = {}

        def write(name, data):
            if data is None:
                reg.pop(name, None)
            else:
                reg[name] = data
        self.assertEqual(gpu.apply('performance', write=write, progs=[EXE]), [EXE])
        self.assertEqual(reg, {EXE: 'GpuPreference=2;'})
        self.assertEqual(gpu.current(read=reg.get, progs=[EXE]), 'performance')
        gpu.apply('economie', write=write, progs=[EXE])
        self.assertEqual(gpu.current(read=reg.get, progs=[EXE]), 'economie')
        gpu.apply('auto', write=write, progs=[EXE])                     # Windows décide : valeur retirée
        self.assertEqual(reg, {})
        self.assertEqual(gpu.current(read=reg.get, progs=[EXE]), 'auto')
        with self.assertRaises(ValueError):
            gpu.apply('turbo', write=write, progs=[EXE])

    def test_python_not_touched(self):
        with mock.patch.object(gpu.sys, 'frozen', False, create=True):
            self.assertEqual(gpu.programs(), [])                          # python.exe : rien dans Windows

    def test_before_qt(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            for k in (gpu.SHIM, 'QT_OPENGL'):
                os.environ.pop(k, None)
            gpu.before_qt('performance')
            self.assertEqual(os.environ[gpu.SHIM], '0x800000001')
            os.environ.pop(gpu.SHIM)
            gpu.before_qt('logiciel')
            self.assertEqual(os.environ['QT_OPENGL'], 'software')
            self.assertNotIn(gpu.SHIM, os.environ)
            os.environ[gpu.SHIM] = 'mien'
            gpu.before_qt('economie')                                     # celle de l'utilisateur gardée
            self.assertEqual(os.environ[gpu.SHIM], 'mien')

    def test_option(self):
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.options import BY_KEY, OptionsDialog
        o = BY_KEY[gpu.SETTING]
        self.assertTrue(o.restart)
        self.assertEqual([c for c, _l in o.choices], [c for c, _l in gpu.CHOICES])
        old = gpu._ADAPTERS, gpu.RENDERER
        gpu._ADAPTERS, gpu.RENDERER = ['Intel(R) UHD Graphics', 'NVIDIA Quadro RTX 5000'], ''
        try:
            self.assertIn('NVIDIA Quadro RTX 5000', OptionsDialog._gpu_text())
            gpu.note_renderer('Quadro RTX 5000/PCIe/SSE2')
            self.assertIn('Quadro RTX 5000/PCIe/SSE2', OptionsDialog._gpu_text())
        finally:
            gpu._ADAPTERS, gpu.RENDERER = old
        w = MainWindow()
        try:
            with mock.patch.object(gpu, 'apply', return_value=[]) as ap:
                self.assertTrue(w.apply_gpu('performance'))
            ap.assert_called_once_with('performance')
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
