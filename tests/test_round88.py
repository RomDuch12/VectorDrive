"""Round 88 : table des polices des VND, en-tête préservé, réécriture
identique d'un VND inchangé, export d'un VND lu en partie."""
import os
import pathlib
import struct
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import geom
from vectordrive.core.document import Document, Shape
from vectordrive.io import registry, vnd, vnd_write


def with_fonts(base: bytes, names) -> bytes:
    """VND de modèle avec une table des polices comme TypeEdit V15 : u32 n à
    l'octet 10 854, n noms de 64 octets, puis l'archive."""
    a = vnd.archive_start(base)
    table = struct.pack('<I', len(names)) + b''.join(n.encode('cp1252').ljust(64, b'\0') for n in names)
    return base[:a - 4] + table + base[a:]


class TestFontTable(unittest.TestCase):
    def test_vnd_table_read(self):
        data = with_fonts(vnd_write.default_template(), ['Trait Essai 1L', 'Arial Gras'])
        pos, names = vnd.font_table(data)
        self.assertEqual(names, ['Trait Essai 1L', 'Arial Gras'])
        self.assertEqual(pos, 10854)
        self.assertEqual(vnd.archive_start(data), 10858 + 128)
        self.assertEqual(vnd.font_table(vnd_write.default_template())[1], [])

    def test_head_keeps_table_and_count(self):
        d = Document()
        d.layers[0].items.append(Shape(path=geom.Path([geom.rect(0, 0, 50, 50)])))
        base = with_fonts(vnd_write.default_template(), ['TRAIT ESSAI 1'])
        head = vnd_write._head(base, d)
        self.assertEqual(struct.unpack_from('<I', head, 10854)[0], 1)          # l'aperçu ne déborde pas
        self.assertEqual(bytes(head[10858:10858 + 13]), b'TRAIT ESSAI 1')
        new = vnd_write._head(vnd_write.default_template(), d)
        self.assertEqual(struct.unpack_from('<I', new, len(new) - 4)[0], 0)  # sans texte : compteur nul

    def test_unchanged_rewrite_is_identical(self):
        d = Document()
        d.layers[0].items.append(Shape(path=geom.Path([geom.rect(0, 0, 30, 20), geom.circle((15, 10), 4)])))
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'a.vnd')
            registry.save_document(d, f)
            raw = pathlib.Path(f).read_bytes()
            back = registry.open_document(f)
            out, _ = vnd_write.write_document(back)
            self.assertEqual(out, raw)


class TestPartialExportGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_refuses_overwriting_partial_source(self):
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        calls = []
        old_save, old_crit = QFileDialog.getSaveFileName, QMessageBox.critical
        try:
            with tempfile.TemporaryDirectory() as tmp:
                src = os.path.join(tmp, 'partiel.vnd')
                pathlib.Path(src).write_bytes(b'original')
                w.canvas.doc.source_path = src
                w.canvas.doc.extra['vnd_partial'] = 'classe inconnue « CObBrep »'
                QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (src, ''))
                QMessageBox.critical = staticmethod(lambda *a, **k: calls.append(a[2]))
                w.export_whole_dialog()                 # export de tout, par l'extension (round 232 : Maj+E = fenetre)
                self.assertEqual(pathlib.Path(src).read_bytes(), b'original')
                self.assertTrue(calls and 'CObBrep' in calls[0])
        finally:
            QFileDialog.getSaveFileName, QMessageBox.critical = old_save, old_crit
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
