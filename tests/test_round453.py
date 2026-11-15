"""Round 453 : programme machine découpé par outil — ISO (T…, commentaire = nom), Heidenhain
(TOOL CALL), lecteurs des plugins (tool_changes ou parts) ; le visualiseur montre un parcours par outil."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import ncread
from vectordrive.cam.model import Move, Toolpath

ISO = """%
T1 M6 (FRAISE D2)
G0 X0 Y0 Z5
G1 Z-1
G1 X10
G0 Z5
T2 M6 (V30)
G0 X20 Y0
G1 Z-0.2
G1 X30
M30
"""
HH = """0 BEGIN PGM A MM
1 TOOL CALL 3 Z S12000
2 L X+0 Y+0 Z+5 FMAX
3 L Z-1 F200
4 L X+10
5 TOOL CALL 7 Z S20000
6 L X+20 Y+0 Z+5 FMAX
7 L Z-0.5 F100
8 END PGM A MM
"""


class TestSplit(unittest.TestCase):
    def test_iso(self):
        tp = ncread.read(ISO, 'p.nc')
        self.assertEqual(len(tp.moves), 7)                                       # le programme entier reste lu
        self.assertEqual([(p.name, len(p.moves)) for p in tp.parts],
                         [('p.nc — T1 FRAISE D2', 4), ('p.nc — T2 V30', 3)])

    def test_heidenhain(self):
        tp = ncread.read(HH, 'a.h')
        self.assertEqual([p.name for p in tp.parts], ['a.h — T3', 'a.h — T7'])
        self.assertEqual([len(p.moves) for p in tp.parts], [3, 2])

    def test_single_tool_not_split(self):
        self.assertEqual(ncread.read('T1 M6\nG0 X0 Y0 Z5\nG1 Z-1\nG1 X5\n', 'b.nc').parts, [])
        self.assertEqual(ncread.read('G0 X0 Y0 Z5\nG1 Z-1\n', 'c.nc').parts, [])

    def test_plugin_changes(self):
        from vectordrive.plugins import REGISTRY

        def rd(text, name):
            tp = Toolpath(op_id='', tool_id='', name=name)
            tp.moves = [Move('rapid', 0, 0, 5), Move('feed', 1, 0, -1), Move('rapid', 2, 0, 5), Move('feed', 3, 0, -1)]
            tp.tool_changes = [(0, 'Balay 14'), (2, 'V30')]
            return tp
        REGISTRY.nc_readers.append(('Essai', ('.ess',), rd, None))
        try:
            tp = ncread.read('x', 'p.ess')
            self.assertEqual([p.name for p in tp.parts], ['p.ess — Balay 14', 'p.ess — V30'])
        finally:
            REGISTRY.nc_readers.pop()


class TestViewer(unittest.TestCase):
    def test_parts_shown(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])                     # noqa: F841
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            p = pathlib.Path(tempfile.mkdtemp()) / 'p.nc'
            p.write_text(ISO, encoding='ascii')
            w.view_nc_program(str(p))
            self.assertEqual([t.name for t in w.cam_panel.toolpaths], ['p.nc — T1 FRAISE D2', 'p.nc — T2 V30'])
            legend = [t.split('  — ')[0] for t, c in w.panel3d.view.overlay_lines() if c is not None]
            self.assertEqual(legend, ['p.nc — T1 FRAISE D2', 'p.nc — T2 V30'])
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
