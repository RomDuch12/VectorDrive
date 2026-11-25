"""Round 256 : BAT — coloriage (formes fermées remplies d'une teinte claire
de leur outil, comme « Remplissage » à l'écran) ; fichier déjà là ou pris
par un autre programme : un autre nom proposé (« (2) »)."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


def doc():
    from vectordrive.core import geom
    from vectordrive.core.document import Document, Shape
    d = Document()
    d.add(Shape(path=geom.Path([geom.rect(0, 0, 40, 20)]), tool=1))
    d.add(Shape(path=geom.Path([geom.polyline([(0, 30), (40, 30)])]), tool=1))      # trait ouvert
    return d


class TestFill(unittest.TestCase):
    def test_closed_shapes_tinted(self):
        from vectordrive.io import proof
        d = doc()
        info = proof.ProofInfo(fill=True, fill_mode='teinte', title_block=False, dims=False, legend=False)
        prims, _w, _h = proof.build(d, info)
        filled = [p for p in prims if p.fill_color is not None]
        self.assertEqual(len(filled), 1)                                 # le rectangle, pas le trait
        self.assertTrue(all(c > 0.5 for c in filled[0].fill_color))      # teinte claire
        self.assertEqual(filled[0].width, 0.2)                           # trait gardé
        none = proof.build(d, proof.ProofInfo(fill=False, title_block=False, dims=False, legend=False))[0]
        self.assertFalse(any(p.fill_color for p in none))                # pas de coloriage
        mono = proof.build(d, proof.ProofInfo(fill=True, fill_mode='teinte', mono=True, title_block=False, dims=False,
                                              legend=False))[0]
        self.assertEqual([p.fill_color for p in mono if p.fill_color], [(0.82, 0.82, 0.82)])
        f = pathlib.Path(tempfile.mkdtemp()) / 'bat.pdf'
        proof.write(d, f, info)
        import zlib
        raw = f.read_bytes()
        body = zlib.decompress(raw[raw.index(b'stream') + 7:raw.index(b'endstream')].strip(b'\r\n'))
        self.assertIn(b'B*', body)                                       # rempli et tracé

    def test_follows_screen(self):
        from vectordrive.ui import batdialog
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.settings.remove('bat/fill')                                  # round 1153 : tant qu'aucun BAT n'est validé
            w.A['fill'].setChecked(True)
            seen = []

            def fake_exec(dlg):
                seen.append(dlg.checks['fill'].isChecked())
                return 0
            with mock.patch.object(batdialog.BatDialog, 'exec', fake_exec):
                w._proof_info()
            self.assertEqual(seen, [True])
        finally:
            w.A['fill'].setChecked(False)
            w.modified = False
            w.close()


class TestNames(unittest.TestCase):
    def test_free_name(self):
        from vectordrive.io import proof
        d = pathlib.Path(tempfile.mkdtemp())
        self.assertEqual(proof.free_name(d / 'BAT n1.pdf').name, 'BAT n1.pdf')
        (d / 'BAT n1.pdf').write_bytes(b'x')
        self.assertEqual(proof.free_name(d / 'BAT n1.pdf').name, 'BAT n1 (2).pdf')
        (d / 'BAT n1 (2).pdf').write_bytes(b'x')
        self.assertEqual(proof.free_name(d / 'BAT n1.pdf').name, 'BAT n1 (3).pdf')
        self.assertEqual(proof.free_name(d / 'BAT n1 (2).pdf').name, 'BAT n1 (3).pdf')

    def test_locked_file_saved_under_new_name(self):
        from vectordrive.io import proof
        from vectordrive.ui.main_window import MainWindow
        d = pathlib.Path(tempfile.mkdtemp())
        target = d / 'BAT n1.pdf'
        target.write_bytes(b'ouvert dans le lecteur')
        real = proof.write

        def locked(doc_, path, info=None, items=None):
            if pathlib.Path(path) == target:
                raise PermissionError(13, 'Permission denied')
            return real(doc_, path, info, items)
        w = MainWindow()
        try:
            with mock.patch.object(proof, 'write', locked):
                got = w.write_proof(target, proof.ProofInfo(), ask=lambda q, alt: True)
                self.assertEqual(pathlib.Path(got).name, 'BAT n1 (2).pdf')
                self.assertIsNone(w.write_proof(target, proof.ProofInfo(), ask=lambda q, alt: False))
            self.assertEqual(target.read_bytes(), b'ouvert dans le lecteur')
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
