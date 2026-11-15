"""Round 495 : vignettes des dessins dans l'explorateur Windows (thumbshell) — clés posées sous
HKEY_CURRENT_USER seulement, retrait de nos seules clés, serveur de vignettes (PNG), fournisseur compilé."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive import thumbshell as TS
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape
from vectordrive.io import registry

app = QApplication.instance() or QApplication([])
PROGRAM = (r'C:\VD\VectorDrive.exe', [])
DLL = pathlib.Path(r'C:\VD\vignettes\VectorDriveVignettes.dll')


class TestThumbShell(unittest.TestCase):
    def test_plan(self):
        keys = dict(TS.plan(DLL, ('.vnd', '.dxf'), PROGRAM))
        inproc = keys[rf'Software\Classes\CLSID\{TS.CLSID}\InprocServer32']
        self.assertEqual(inproc['CodeBase'], 'file:///C:/VD/vignettes/VectorDriveVignettes.dll')
        self.assertEqual(inproc['Class'], TS.CLASS)
        self.assertEqual(keys[TS.SETTINGS_KEY], {'Programme': PROGRAM[0], 'Arguments': TS.SERVER_ARG})
        self.assertEqual(keys[TS.ext_key('.vnd')], {'': TS.CLSID})
        self.assertTrue(all(k.startswith('Software\\') for k in keys))            # sous HKEY_CURRENT_USER
        self.assertIn(TS.CLSID[1:-1], TS.source().read_text(encoding='utf-8'))      # même identifiant que le C#

    def test_install_uninstall(self):
        reg = {}

        def write(key, values):
            reg.setdefault(key, {}).update(values)

        def read(key, name):
            return reg.get(key, {}).get(name)

        def delete(key):                                 # clé et sous-clés, comme le registre
            gone = [k for k in reg if k == key or k.startswith(key + '\\')]
            for k in gone:
                del reg[k]
            return bool(gone)
        taken, left = TS.install(write=write, program=PROGRAM, dll=DLL)
        self.assertEqual((taken, left), (list(TS.EXTS), []))
        self.assertEqual(TS.installed_exts(read), list(TS.EXTS))
        reg[TS.ext_key('.pdf')] = {'': '{AUTRE-LOGICIEL}'}                         # repris par un autre logiciel
        TS.uninstall(delete=delete, read=read)
        self.assertEqual(reg, {TS.ext_key('.pdf'): {'': '{AUTRE-LOGICIEL}'}})        # le sien reste

    def test_check(self):
        reg = {}
        for k, v in TS.plan(pathlib.Path(__file__), ('.dxf',), PROGRAM):
            reg[k] = v
        ok, why = TS.check(lambda k, n: reg.get(k, {}).get(n), PROGRAM)
        self.assertTrue(ok, why)
        ok, why = TS.check(lambda k, n: reg.get(k, {}).get(n), (r'C:\Autre\VectorDrive.exe', []))
        self.assertFalse(ok)

    def test_render(self):
        d = pathlib.Path(tempfile.mkdtemp())
        doc = Document()
        doc.add(Shape(path=geom.Path([geom.circle((0, 0), 10)])))
        f = d / 'rond.dxf'
        registry.save_document(doc, f)
        png = TS.render(f'VIGNETTE\t96\t{f}'.encode('utf-8'))
        self.assertTrue(png.startswith(b'\x89PNG'))
        from PySide6.QtGui import QImage
        self.assertEqual(QImage.fromData(png).width(), 96)
        (d / 'note.txt').write_text('x')
        self.assertEqual(TS.render(f'VIGNETTE\t96\t{d / "note.txt"}'.encode('utf-8')), b'')    # format refusé
        self.assertEqual(TS.render(b'AUTRE\t96\tx'), b'')

    @unittest.skipUnless(os.name == 'nt' and TS.compiler() is not None, 'csc de .NET Framework 4 (Windows)')
    def test_build(self):
        out = TS.build(pathlib.Path(tempfile.mkdtemp()))
        self.assertGreater(out.stat().st_size, 4000)

    def test_command(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            with mock.patch.object(TS, 'install', return_value=(['.vnd', '.dxf'], ['.pdf'])) as inst:
                self.assertTrue(w.toggle_shell_thumbs(True, confirm=False))
            inst.assert_called_once()
            self.assertIn('VND, DXF', w.statusBar().currentMessage())
            with mock.patch.object(TS, 'uninstall', return_value=3):
                self.assertFalse(w.toggle_shell_thumbs(False, confirm=False))
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
