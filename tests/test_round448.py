"""Round 448 : visualiseur de programmes — ISO (arcs G18 / G19 en 3D), Heidenhain texte clair,
lecteurs des plugins ; montré seul en 3D filaire."""
import math
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import ncread
from vectordrive.cam.model import Move, Toolpath

HH = """0 BEGIN PGM TEST MM
1 BLK FORM 0.1 Z X+0 Y+0 Z-5
3 TOOL CALL 1 Z S12000
4 L X+0 Y+0 Z+5 FMAX
5 L Z-1 F200
6 L X+10 F600
7 CC X+10 Y+5
8 C X+10 Y+10 DR+
9 CR X+0 Y+10 R+5 DR-
10 L IX-2 IY-3
11 END PGM TEST MM
"""


class TestDialects(unittest.TestCase):
    def test_heidenhain(self):
        self.assertEqual(ncread.dialect(HH, 'a.h'), 'heidenhain')
        tp = ncread.read(HH, 'a.h')
        kinds = [m.kind for m in tp.moves]
        self.assertEqual(kinds, ['rapid', 'plunge', 'feed', 'arc_ccw', 'arc_cw', 'feed'])
        arc = tp.moves[3]
        self.assertEqual((arc.cx, arc.cy), (10.0, 5.0))
        self.assertAlmostEqual(tp.moves[-1].x, -2.0)
        self.assertAlmostEqual(tp.moves[-1].y, 7.0)
        self.assertAlmostEqual(tp.moves[-1].z, -1.0)

    def test_iso_xz_arc(self):
        tp = ncread.read('G21 G90\nG0 X0 Y0 Z0\nG18\nG2 X10 Z0 I5 K0\n', 'a.nc')
        self.assertEqual(ncread.dialect('G0 X0', 'a.nc'), 'iso')
        zs = [m.z for m in tp.moves if m.kind == 'feed']
        self.assertGreater(len(zs), 8)
        self.assertAlmostEqual(max(abs(v) for v in zs), 5.0, places=1)      # demi-cercle de rayon 5 en Z
        last = tp.moves[-1]
        self.assertAlmostEqual(math.hypot(last.x - 10, last.z), 0.0, places=6)
        self.assertFalse(any('ligne droite' in w for w in tp.warnings))

    def test_plugin_reader(self):
        from vectordrive.plugins import REGISTRY

        def fake(text, name):
            tp = Toolpath(op_id='', tool_id='', name=name)
            tp.moves = [Move('rapid', 0, 0, 5), Move('feed', 1, 2, -1)]
            return tp
        REGISTRY.nc_readers.append(('Essai', ('.ess',), fake, lambda t: t.startswith('ESSAI')))
        try:
            self.assertEqual(ncread.dialect('ESSAI\n', 'x.txt'), 'Essai')
            self.assertEqual(ncread.dialect('rien', 'x.ess'), 'Essai')
            tp = ncread.read('ESSAI\n', 'x.txt')
            self.assertEqual((len(tp.moves), tp.source), (2, 'nc'))
        finally:
            REGISTRY.nc_readers.pop()


class TestViewer(unittest.TestCase):
    def test_view_in_3d(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])                  # noqa: F841
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            p = pathlib.Path(tempfile.mkdtemp()) / 'prog.h'
            p.write_text(HH, encoding='utf-8')
            tp = w.view_nc_program(str(p))
            self.assertIsNotNone(tp)
            self.assertEqual(w.view_mode(), '3d')
            self.assertEqual(list(w.cam_panel.toolpaths), [tp])
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
