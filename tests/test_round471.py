"""Round 471 : 3D — barre qui passe à la ligne (un gros programme n'élargit plus la fenêtre), plaque
masquable, brut et durée machine d'un programme lu, chemin passé aux lecteurs des plugins, visualiseur
qui ne lit le programme qu'une fois."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from vectordrive.cam import model as M, ncread, relief, timing
from vectordrive.core.document import Document

app = QApplication.instance() or QApplication([])

HH = """0 BEGIN PGM A MM
1 BLK FORM 0.1 Z X+0 Y+0 Z-20
2 BLK FORM 0.2 X+100 Y+60 Z+0
3 TOOL CALL 1 Z S10000
4 L X+10 Y+10 Z+2 FMAX
5 L Z-1 F200
6 L X+50 F800
7 END PGM A MM
"""


class TestFlow(unittest.TestCase):
    def test_wraps(self):
        from vectordrive.ui.flow import FlowLayout
        w = QWidget()
        lay = FlowLayout(w)
        for i in range(8):
            b = QPushButton(f'Bouton {i}')
            b.setFixedSize(100, 20)
            lay.addWidget(b)
        self.assertLessEqual(lay.minimumSize().width(), 140)                  # pas la somme des largeurs
        self.assertGreater(lay.heightForWidth(250), lay.heightForWidth(2000))  # à la ligne quand c'est étroit
        w.deleteLater()

    def test_elide(self):
        from vectordrive.ui.flow import ElideLabel
        lab = ElideLabel('')
        lab.setText('x' * 2000)
        self.assertEqual(lab.minimumSizeHint().width(), 0)
        self.assertEqual(lab.toolTip(), 'x' * 2000)


class TestPanel(unittest.TestCase):
    def test_narrow_and_plate(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.set_view_mode('3d')
            p3 = w.panel3d
            p3.info.setText('trajectoires — ' * 200)
            p3.player.label.setText('mouvements ' * 200)
            self.assertLess(p3.minimumSizeHint().width(), 800)
            self.assertTrue(p3.view.show_plate)
            p3.plate.setChecked(False)
            self.assertFalse(p3.view.show_plate)
        finally:
            w.modified = False
            w.close()

    def test_viewer_reads_once(self):
        from vectordrive.ui.main_window import MainWindow
        f = pathlib.Path(tempfile.mkdtemp()) / 'a.h'
        f.write_text(HH, encoding='ascii')
        w = MainWindow()
        try:
            real = ncread.read
            with mock.patch.object(ncread, 'read', side_effect=real) as rd:
                tp = w.view_nc_program(str(f))
            self.assertEqual(rd.call_count, 1)
            self.assertEqual(rd.call_args.kwargs.get('path'), str(f))
            self.assertEqual(tp.stock, (0.0, 0.0, -20.0, 100.0, 60.0, 0.0))
            self.assertEqual(w.panel3d.relief.plate[:4], (0.0, 0.0, 100.0, 60.0))   # le brut, pas la plaque
        finally:
            w.modified = False
            w.close()


class TestStock(unittest.TestCase):
    def test_relief_plate(self):
        tp = ncread.read(HH, 'a.h')
        r = relief.from_paths(Document(), [tp], cut=False)
        self.assertEqual(r.plate, (0.0, 0.0, 100.0, 60.0, 20.0))

    def test_machine_time_legend(self):
        from vectordrive.ui import view3d as V
        tp = ncread.read(HH, 'a.h')
        tp.machine_seconds = 3 * 3600 + 6 * 60
        v = V.View3D()
        v.set_relief(relief.from_paths(Document(), [tp], cut=False))
        self.assertTrue(any('3 h 06 min' in t for t, _c in v.overlay_lines()))
        v.deleteLater()

    def test_plugin_reader_gets_path(self):
        from vectordrive.plugins import REGISTRY
        seen = {}

        def rd(text, name, path=None):
            seen['path'] = path
            return M.Toolpath(op_id='', tool_id='', moves=[M.Move('rapid', 0, 0, 5), M.Move('feed', 1, 0, 0)])
        REGISTRY.nc_readers.append(('Essai471', ['.e471'], rd, None))
        try:
            ncread.read('x', 'p.e471', path='C:/p.e471')
        finally:
            REGISTRY.nc_readers.pop()
        self.assertEqual(seen['path'], 'C:/p.e471')

    def test_cumulative_arc_exact(self):
        moves = [M.Move('feed', 10, 0, 0), M.Move('arc_ccw', -10, 0, 0, 0, 0)]
        tp = M.Toolpath(op_id='', tool_id='', moves=moves)
        tp.feeds = [600.0, 600.0]
        t = timing.cumulative([tp], M.CamSetup())
        self.assertAlmostEqual(t[-1], 3.14159265 * 10 / 10.0, places=4)        # demi-cercle à 10 mm/s


if __name__ == '__main__':
    unittest.main()
