"""Round 462 : programmes lus — l'outil de chaque parcours reconnu (Mes outils par référence ou nom,
sinon cotes du libellé), pris par la lecture pas à pas."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model, ncread


class TestGuess(unittest.TestCase):
    def test_guess(self):
        lib = [model.CamTool(name='Fraise 2 Datron', diameter=2, ref='0068432A'),
               model.CamTool(name='V30 pointe 0.2', kind='conique', diameter=3, angle=30)]
        self.assertIs(ncread.guess_tool('Operation_2 — 3__2_Z1_L4 (DATRON 0068432A)', lib), lib[0])
        self.assertIs(ncread.guess_tool('p.nc — T4 v30 pointe 0.2', lib), lib[1])            # par le nom
        g = ncread.guess_tool('T1 FRAISE Ø2,5')
        self.assertEqual((g.kind, g.diameter), ('fraise', 2.5))
        g = ncread.guess_tool('T2 V 60° D6')
        self.assertEqual((g.kind, g.diameter, g.angle), ('conique', 6.0, 60.0))
        self.assertIsNone(ncread.guess_tool('T1'))

    def test_read_sets_guess(self):
        lib = [model.CamTool(name='Fraise 2', diameter=2, ref='F2REF')]
        with mock.patch('vectordrive.cam.toollib.library', return_value=lib):
            tp = ncread.read('T1 M6 (F2REF)\nG0 X0 Y0 Z5\nG1 Z-1 F100\nT2 M6 (V 30° D3)\nG0 X10 Y0 Z5\nG1 Z-1\n', 'a.nc')
        self.assertIs(tp.parts[0].tool_guess, lib[0])
        self.assertEqual(tp.parts[1].tool_guess.angle, 30.0)

    def test_player_uses_guess(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])                     # noqa: F841
        from vectordrive.ui.main_window import MainWindow
        import pathlib
        w = MainWindow()
        try:
            p = pathlib.Path(tempfile.mkdtemp()) / 'p.nc'
            p.write_text('T1 M6 (FRAISE Ø4)\nG0 X0 Y0 Z5\nG1 Z-1 F100\nG1 X20\n', encoding='utf-8')
            w.view_nc_program(str(p))
            pl = w.panel3d.player
            pos, dia, kind, _a = pl.tool_at(len(pl.moves))
            self.assertEqual((dia, kind), (4.0, 'fraise'))
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
