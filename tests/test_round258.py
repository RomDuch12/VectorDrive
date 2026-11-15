"""Round 258 : Mode Point (P) — points en courbe et hors courbe visibles,
sélectionnables (clic, Maj, rectangle, tout), déplacés ensemble ; en
courbe ⇄ hors courbe ; attributs du point au double-clic."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom, nodes as N
from vectordrive.core.document import Shape
from vectordrive.core.geom import Conic, Contour, Cubic, Line

app = QApplication.instance() or QApplication([])


def square():
    return Contour([Line((0, 0), (10, 0)), Line((10, 0), (10, 10)), Line((10, 10), (0, 10)), Line((0, 10), (0, 0))],
                   True)


def wave():
    """Ouvert : droite puis cubique."""
    return Contour([Line((0, 0), (10, 0)), Cubic((10, 0), (15, 0), (20, 5), (20, 10))], False)


def continuous(c):
    segs = c.segments
    for a, b in zip(segs, segs[1:] + (segs[:1] if c.closed else [])):
        if geom.dist(a.end, b.start) > 1e-9:
            return False
    return True


class TestNodes(unittest.TestCase):
    def test_on_to_off_and_back(self):
        c = square()
        for k in range(4):
            o = N.node_to_off(c, k)
            self.assertEqual(len(o.segments), 3)
            self.assertTrue(continuous(o))
            conics = [s for s in o.segments if isinstance(s, Conic)]
            self.assertEqual(len(conics), 1)
            self.assertEqual(conics[0].p1, N.node_point(c, k))                  # le nœud devient contrôle
        off = N.node_to_off(c, 1)
        seg = next(i for i, s in enumerate(off.segments) if isinstance(s, Conic))
        back = N.handle_to_on(off, seg, 1)
        self.assertEqual(len(back.segments), 4)
        self.assertTrue(all(isinstance(s, Line) for s in back.segments))      # repassé en courbe : deux droites
        w = wave()
        self.assertEqual(N.node_to_off(w, 0), w)                                 # bout d'un contour ouvert
        self.assertEqual(N.node_to_off(w, 2), w)
        o = N.node_to_off(w, 1)
        self.assertEqual(len(o.segments), 1)
        self.assertIsInstance(o.segments[0], Cubic)
        self.assertEqual(o.segments[0].p1, (10, 0))                              # droite + cubique

    def test_cubic_handles(self):
        w = wave()
        a = N.handle_to_on(w, 1, 1)
        self.assertEqual([type(s) for s in a.segments], [Line, Line, Conic])
        self.assertEqual(a.segments[1].end, (15, 0))                             # passe par le point
        b = N.handle_to_on(w, 1, 2)
        self.assertEqual([type(s) for s in b.segments], [Line, Conic, Line])
        self.assertTrue(continuous(a) and continuous(b))
        self.assertIsInstance(N.remove_handles(w, [(1, 1)]).segments[1], Conic)
        self.assertIsInstance(N.remove_handles(w, [(1, 1), (1, 2)]).segments[1], Line)
        self.assertEqual(N.handle_node(w, 1, 1), 1)
        self.assertEqual(N.handle_node(w, 1, 2), 2)
        self.assertTrue(N.is_smooth(w, 1))                                       # tangentes alignées
        self.assertFalse(N.is_smooth(square(), 0))                               # angle


class Win(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.c = self.w.canvas
        self.sh = Shape(path=geom.Path([wave()]))
        self.c.doc.add(self.sh)
        self.c.select([self.sh])
        self.w.set_tool('node')
        self.t = self.c.tool_obj

    def tearDown(self):
        self.w.modified = False
        self.w.close()


class TestTool(Win):
    def test_select_all_band_and_move_together(self):
        t = self.t
        self.assertEqual(t.select_all_nodes(), 3 + 2)                           # 3 en courbe + 2 hors courbe
        t.sel, t.hsel = set(), set()
        q = self.c.to_screen(15, 0)                                              # rectangle autour de la poignée
        band = t.handles_in_rect(QPointF(q.x() - 5, q.y() - 5), QPointF(q.x() + 5, q.y() + 5))
        self.assertEqual(band, {(0, 1, 1)})
        t.sel, t.hsel = {(0, 1)}, {(0, 1, 1), (0, 1, 2)}
        t._translate_selected(1.0, 0.0)
        s = self.sh.path.contours[0].segments[1]
        self.assertEqual(s.p0, (11, 0))
        self.assertEqual(s.p1, (16, 0))                                          # attachée au nœud : une fois
        self.assertEqual(s.p2, (21, 5))                                          # l'autre : déplacée aussi
        self.assertEqual(s.p3, (20, 10))
        t.hsel = {(0, 1, 2)}
        t.sel = set()
        t.delete_selected()
        self.assertIsInstance(self.sh.path.contours[0].segments[1], Conic)       # point hors courbe supprimé

    def test_click_selects_handle(self):
        from PySide6.QtCore import QEvent, Qt
        from PySide6.QtGui import QMouseEvent
        t = self.t
        sp = self.c.to_screen(15, 0)
        ev = QMouseEvent(QEvent.Type.MouseButtonPress, sp, sp, Qt.MouseButton.LeftButton,
                         Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        t.press(sp, (15, 0), ev)
        self.assertEqual((t.sel, t.hsel), (set(), {(0, 1, 1)}))
        t.release(sp, (15, 0), ev)
        self.assertFalse(self.w.grab().isNull())                                 # points peints
        seen = []
        self.c.point_dialog_fn = seen.append
        sp = self.c.to_screen(15, 0)                                             # la vue a pu changer au rendu
        t.double(sp, (15, 0), ev)
        self.assertEqual(seen, [('handle', 0, 1, 1)])                           # double-clic : attributs


class TestCommands(Win):
    def test_off_on_commands_and_attrs(self):
        t = self.t
        t.sel, t.hsel = {(0, 1)}, set()
        self.assertEqual(self.w.node_attr('off'), 1)
        self.assertEqual(len(self.sh.path.contours[0].segments), 1)
        t.sel, t.hsel = set(), {(0, 0, 1)}
        self.assertEqual(self.w.node_attr('on'), 1)
        self.assertEqual(len(self.sh.path.contours[0].segments), 2)
        self.c.set_origin(5, 0)
        self.assertTrue(self.w.point_attrs(('node', 0, 0), 0.0, 1.0, True))     # X, Y depuis l'origine
        self.assertEqual(N.node_point(self.sh.path.contours[0], 0), (5.0, 1.0))
        self.c.set_origin(0, 0)
        c = self.sh.path.contours[0]
        si = next(i for i, s in enumerate(c.segments) if isinstance(s, (Conic, Cubic)))
        self.sh.path = geom.Path([Contour([Conic((0, 0), (5, 5), (10, 0), 1.0)], False)])
        self.assertTrue(self.w.point_attrs(('handle', 0, 0, 1), 5.0, 5.0, False, 0.7071))
        self.assertAlmostEqual(self.sh.path.contours[0].segments[0].w, 0.7071)  # poids W
        self.assertGreaterEqual(si, 0)

    def test_line_from_handle(self):
        t = self.t
        t.sel, t.hsel = set(), {(0, 1, 2)}
        self.w.node_edit('node_line')
        self.assertIsInstance(self.sh.path.contours[0].segments[1], Line)       # En droite


if __name__ == '__main__':
    unittest.main()
