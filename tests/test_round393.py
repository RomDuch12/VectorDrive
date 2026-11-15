"""Round 393 : pontets posés à la main (TypeEdit : ajouter des ponts) —
clic sur le contour, pris par le détourage, suivent la forme."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.cam import model as M, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape
from vectordrive.core.geom import Affine

app = QApplication.instance() or QApplication([])


def run_with(shape, **kw):
    d = Document()
    d.plate = None
    d.add(shape)
    setup = M.setup_of(d)
    t = M.CamTool(name='F', kind='droite', diameter=2)
    setup.tools = [t]
    return S.compute(d, setup, M.Operation(kind='contour', depth=1, step_down=1, tool_id=t.id, side='exterieur',
                                           tab_width=2.0, tab_height=0.5, **kw))


class TestManualTabs(unittest.TestCase):
    def test_intervals(self):
        sq = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        iv = S.manual_tab_intervals(sq, [(5, -0.5), (50, 50)], 2.0, 1.0)
        self.assertEqual(iv, [(4.0, 6.0)])                           # le repère lointain est ignoré
        self.assertIsNone(S.manual_tab_intervals(sq, [(50, 50)], 2.0, 1.0))

    def test_contour(self):
        s = Shape(path=geom.Path([geom.rect(0, 0, 20, 10)]), tool=1)
        plain = run_with(s)
        self.assertEqual({round(m.z, 4) for m in plain.moves if m.kind == 'feed'}, {-1.0})
        s.extra['tabs_xy'] = [[10.0, 0.0]]                           # un pontet au milieu du bas
        tp = run_with(s)
        lifted = [m for m in tp.moves if m.kind == 'feed' and abs(m.z + 0.5) < 1e-9]
        self.assertTrue(lifted)
        self.assertTrue(all(abs(m.y + 1.0) < 1e-6 for m in lifted))  # seulement sur le côté bas (décalé de 1)
        moved = s.transformed(Affine.translation(5, 0))
        self.assertEqual(moved.extra['tabs_xy'], [[15.0, 0.0]])

    def test_window_toggle(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            s = Shape(path=geom.Path([geom.rect(0, 0, 20, 10)]))
            w.canvas.doc.add(s)
            tol = 1.0 / max(w.canvas.scale, 1e-9)
            self.assertTrue(w.canvas.toggle_tab((10.0, -tol)))
            self.assertEqual(len(s.extra['tabs_xy']), 1)
            self.assertAlmostEqual(s.extra['tabs_xy'][0][1], 0.0, 6)  # posé sur le contour
            self.assertFalse(w.canvas.toggle_tab((10.0, 0.0)))         # ôté
            self.assertNotIn('tabs_xy', s.extra)
            self.assertIsNone(w.canvas.toggle_tab((500.0, 500.0)))
            w.set_tool('tabs')
            self.assertIsNotNone(w.canvas.tool_obj)
        finally:
            w.set_tool('select')
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
