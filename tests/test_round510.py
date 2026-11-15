"""Round 510 : vignettes de l'explorateur Windows aussi pour les programmes machine (G-code, et les
langages des plugins : SimPL…), parcours vu de dessus comme dans la boîte Ouvrir."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from vectordrive import thumbshell as TS

app = QApplication.instance() or QApplication([])
GCODE = 'G21 G90\nG0 Z5\nG0 X0 Y0\nG1 Z-0.5 F300\nG1 X30 Y0 F1200\nG1 X30 Y10\nG1 X0 Y10\nG1 X0 Y0\nG0 Z5\n'
PROGRAM = (r'C:\VD\VectorDrive.exe', [])


class TestProgramThumbnails(unittest.TestCase):
    def test_exts(self):
        exts = TS.all_exts()
        self.assertEqual(exts[:len(TS.EXTS)], TS.EXTS)
        for e in ('.nc', '.tap', '.gcode'):
            self.assertIn(e, exts)
        for e in ('.iso', '.h', '.txt'):                       # trop communes ailleurs
            self.assertNotIn(e, exts)
        from vectordrive.plugins import REGISTRY
        REGISTRY.nc_readers.append(('Essai', ('.essai',), lambda text, name: None, None))
        try:
            self.assertIn('.essai', TS.all_exts())
        finally:
            REGISTRY.nc_readers.pop()

    def test_render_program(self):
        f = pathlib.Path(tempfile.mkdtemp()) / 'cadre.nc'
        f.write_text(GCODE)
        png = TS.render(f'VIGNETTE\t96\t{f}'.encode('utf-8'))
        self.assertTrue(png.startswith(b'\x89PNG'))
        self.assertEqual(QImage.fromData(png).width(), 96)

    def test_install_and_remove_programs(self):
        reg = {}

        def write(key, values):
            reg.setdefault(key, {}).update(values)

        def delete(key):
            gone = [k for k in reg if k == key or k.startswith(key + '\\')]
            for k in gone:
                del reg[k]
            return bool(gone)
        import pathlib as _p
        taken, left = TS.install(TS.all_exts(), write=write, program=PROGRAM, dll=_p.Path(r'C:\VD\v.dll'))
        self.assertIn('.nc', taken)
        read = lambda k, n: reg.get(k, {}).get(n)                  # noqa: E731
        self.assertIn('.gcode', TS.installed_exts(read))
        TS.uninstall(delete=delete, read=read)
        self.assertEqual(reg, {})


if __name__ == '__main__':
    unittest.main()
