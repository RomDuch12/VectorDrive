"""Round 98 : outils des parcours TypeEdit lus dans le VND (CToolPath :
fichier, libellé, outil complet avec avances et régimes)."""
import os
import pathlib
import struct
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model, tooldb, typeedit


def cstr(s: str) -> bytes:
    b = s.encode('cp1252')
    return bytes([len(b)]) + b


def fake_vnd(folder: pathlib.Path) -> model.CamTool:
    """VND factice : un CToolPath tel que TypeEdit l'écrit (après l'en-tête
    CObDao), et le fichier de parcours à côté."""
    tool = model.CamTool(name='30° 0.2 Datron', kind='conique', diameter=6, angle=30, tip=0.2, number=5,
                         feed=500, plunge=250, spindle=40000, step_down=0.1)
    rec = (cstr('piece.004') + cstr('30° 0.2') + struct.pack('<II', 0, 5) + struct.pack('<i', 2)
           + cstr(tool.name) + tooldb._tool_block(tool) + struct.pack('<I', 0))
    (folder / 'piece.vnd').write_bytes(b'\x73\x11\x21\x00' + bytes(200) + b'CToolPath' + bytes(40) + rec + bytes(64))
    tp = model.Toolpath(op_id='', tool_id='', name='CP_Finishing')
    tp.moves = [model.Move('rapid', 0, 0, 1), model.Move('feed', 0, 0, -0.1), model.Move('feed', 10, 0, -0.1)]
    typeedit.write(tp, folder / 'piece.004', comment='CP_Finishing[Vecto]')
    return tool


class TestVndTools(unittest.TestCase):
    def test_tool_found_with_feeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = pathlib.Path(tmp)
            src = fake_vnd(folder)
            tools = typeedit.vnd_tools(folder / 'piece.vnd')
            self.assertEqual(list(tools), ['piece.004'])
            t = tools['piece.004']
            for k in ('diameter', 'angle', 'tip', 'feed', 'plunge', 'spindle'):
                self.assertAlmostEqual(getattr(t, k), getattr(src, k), places=6)
            self.assertEqual((t.kind, t.name), ('conique', '30° 0.2 Datron'))
            self.assertEqual(typeedit.read(folder / 'piece.004').file, 'piece.004')

    def test_no_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = pathlib.Path(tmp)
            (folder / 'x.vnd').write_bytes(bytes(500))
            (folder / 'x.000').write_bytes(typeedit.write_bytes(model.Toolpath(op_id='', tool_id='')))
            self.assertEqual(typeedit.vnd_tools(folder / 'x.vnd'), {})


class TestPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_import_uses_vnd_feeds(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                fake_vnd(pathlib.Path(tmp))
                tps = w.cam_panel.import_typeedit([os.path.join(tmp, 'piece.vnd')])
            t = w.cam_panel.setup().tool(tps[0].tool_id)
            self.assertEqual((t.feed, t.spindle), (500.0, 40000.0))
            self.assertFalse(any('non lus' in x for x in tps[0].warnings))
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
