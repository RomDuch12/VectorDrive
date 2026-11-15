"""Round 96 : bases d'outils TypeEdit / LaserType (.Dbt) — lecture,
écriture, import dans la bibliothèque FAO ; symboles de l'atelier."""
import os
import pathlib
import struct
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model, tooldb
from tests.corpus import corpus

ATELIER = corpus('bases_outils')


def library():
    return [model.CamTool(name='Fraise 2', kind='fraise', diameter=2, number=3, feed=600, plunge=150,
                          spindle=24000, step_down=0.4, flutes=2, ref='0068419A', vendor='DATRON'),
            model.CamTool(name='V30 0,2', kind='conique', diameter=6, angle=30, tip=0.2, number=7, feed=800,
                          plunge=200, ramp_feed=300, spindle=30000),
            model.CamTool(name='Boule 1', kind='boule', diameter=1, number=9, feed=400, plunge=100, spindle=40000),
            model.CamTool(name='Laser', kind='laser', diameter=0.03, number=62, feed=2000, plunge=2000,
                          spindle=2000)]


class TestDbt(unittest.TestCase):
    def test_roundtrip(self):
        data = tooldb.write_bytes(library(), folder='Atelier')
        back = tooldb.read_bytes(data)
        self.assertEqual(len(back), 4)
        for a, e in zip(library(), back):
            b = e.tool
            self.assertEqual(e.path, ['Atelier'])
            self.assertEqual((b.name, b.kind, b.number), (a.name, a.kind, a.number))
            for k in ('diameter', 'angle', 'tip', 'feed', 'plunge', 'spindle', 'step_down'):
                self.assertAlmostEqual(getattr(b, k), getattr(a, k), places=6, msg=(a.name, k))
            self.assertEqual((b.ref, b.vendor), (a.ref, a.vendor))
        self.assertAlmostEqual(back[1].tool.ramp_feed, 300, places=6)
        self.assertEqual(back[0].tool.flutes, 2)
        # demi-angle en radians dans le fichier
        blk = back[1].raw
        self.assertAlmostEqual(struct.unpack_from('<d', blk, 0x10)[0], 0.2617993877991494, places=12)

    def test_not_a_tool_base(self):
        with self.assertRaises(tooldb.DbtError):
            tooldb.read_bytes(b'\x00\x01garbage')

    @unittest.skipUnless(ATELIER.is_dir(), 'bases d\'outils de l\'atelier absentes')
    def test_atelier_bases(self):
        total = 0
        for f in ATELIER.iterdir():
            tools = tooldb.read(f)
            self.assertTrue(tools, f.name)
            total += len(tools)
        self.assertGreater(total, 1000)
        fr = tooldb.read(ATELIER / 'TeToolDataBase_FR.Dbt')
        cone = next(e for e in fr if e.tool.ref == '23077')
        self.assertEqual((cone.tool.kind, cone.tool.angle, cone.tool.tip), ('conique', 120.0, 0.15))
        self.assertEqual(cone.path[:2], ['GV Percut Tools', 'Engraving tools'])


class TestPanelImport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_import_and_export(self):
        from PySide6.QtWidgets import QFileDialog
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                f = os.path.join(tmp, 'outils.Dbt')
                pathlib.Path(f).write_bytes(tooldb.write_bytes(library()))
                p = w.cam_panel

                def pick(dlg):
                    dlg.filter.setText('v30')
                    self.assertFalse(dlg.items[1].isHidden())
                    self.assertTrue(dlg.items[0].isHidden())
                    dlg.check({1, 2})
                    return True
                self.assertEqual(p.import_dbt(f, accept=pick), 2)
                names = [t.name for t in p.setup().tools]
                self.assertEqual(names, ['V30 0,2', 'Boule 1'])
                out = os.path.join(tmp, 'export.Dbt')
                old = QFileDialog.getSaveFileName
                QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (out, ''))
                try:
                    p.export_dbt()
                finally:
                    QFileDialog.getSaveFileName = old
                self.assertEqual([e.tool.name for e in tooldb.read(out)], names)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
