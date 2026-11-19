"""Round 1085 (demande du 18/11 soir) : « raccourci O origine : pour contour ouvert : définit point de départ usinage (à
l'atelier ma spirale ne pouvait pas etre usinée depuis l'extérieur malgré orignie à l'exté) »."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1085.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

from vectordrive.cam import model as M  # noqa: E402
from vectordrive.cam import strategies as S  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Layer, Plate, Shape  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : un trait partait toujours du bout le plus proche de l\'outil'


def spiral():
    """Une spirale ouverte dessinée du centre (50, 50) vers l'extérieur."""
    import math
    pts = [(50 + 0.5 * t * math.cos(t), 50 + 0.5 * t * math.sin(t)) for t in [k * 0.2 for k in range(0, 160)]]
    return geom.polyline(pts)


def first_cut(tp):
    m = next(m for m in tp.moves if m.kind != 'rapid')
    return round(m.x, 6), round(m.y, 6)


def toolpath(shapes, kind='gravure', here=(0.0, 0.0), **params):
    doc = Document()
    doc.plate = Plate(width=200.0, height=200.0)
    doc.layers = [Layer(name='A', items=list(shapes))]
    setup = M.setup_of(doc)
    tool = M.CamTool(name='F', diameter=1.0)
    setup.tools.append(tool)
    op = M.Operation(kind=kind, tool_id=tool.id)
    op.depth = 0.2
    for k, v in params.items():
        setattr(op, k, v)
    setup.operations.append(op)
    M.store(doc, setup)
    return S.compute(doc, setup, op, here)


class Cam(unittest.TestCase):

    def test_the_chosen_end_of_an_open_contour(self):
        sp = spiral()
        outer = tuple(round(v, 6) for v in sp.segments[-1].end[:2])
        rev = sp.reversed()                                                  # O au bout extérieur : le dessin retourné
        self.assertEqual(first_cut(toolpath([Shape(path=geom.Path([rev]))], here=(50.0, 50.0))), (50.0, 50.0))
        mark = {'open_start': [[outer[0], outer[1], 50.0, 50.0]]}
        got = first_cut(toolpath([Shape(path=geom.Path([rev]), extra=dict(mark))], here=(50.0, 50.0)))
        self.assertEqual(got, outer, BEFORE)
        # puis Inverser le sens : le dessin repart du centre, l'usinage aussi (même loin de l'outil)
        got = first_cut(toolpath([Shape(path=geom.Path([sp]), extra=dict(mark))], here=outer))
        self.assertEqual(got, (50.0, 50.0))

    def test_the_mark_follows_the_shape(self):
        s = Shape(path=geom.Path([geom.polyline([(0.0, 0.0), (10.0, 0.0)])]), extra={'open_start': [[0.0, 0.0, 10.0, 0.0]]})
        t = s.transformed(geom.Affine.translation(5.0, 7.0))
        self.assertEqual(t.extra['open_start'], [[5.0, 7.0, 15.0, 7.0]])

    def test_drawing_start_keeps_the_drawn_direction(self):
        line = geom.polyline([(100.0, 0.0), (10.0, 0.0)])                 # dessinée de droite à gauche
        s = Shape(path=geom.Path([line]))
        self.assertEqual(first_cut(toolpath([s])), (10.0, 0.0))              # au plus près
        self.assertEqual(first_cut(toolpath([s], start_policy='dessin')), (100.0, 0.0), BEFORE)
        self.assertEqual(first_cut(toolpath([s], kind='laser', start_policy='dessin')), (100.0, 0.0))

    def test_only_the_chosen_trait_of_a_v(self):
        a = [(10.0, 0.0), (0.0, 10.0)]                                       # V : deux traits dessinés depuis la pointe
        b = [(10.0, 0.0), (20.0, 10.0)]
        chains = [(a[::-1], False), (b[::-1], False)]                        # tous deux retournés au plus près
        got = S.keep_drawn_direction(chains, [(a, False), (b, False)], [((10.0, 0.0), (20.0, 10.0))], 0.01)
        self.assertEqual(got, [(a[::-1], False), (b, False)])

    def test_closed_contours_as_before(self):
        ring = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)]
        line = [(10.0, 10.0), (30.0, 10.0)]                                  # un trait qui part du même point
        chains, fixed = S.apply_starts([(ring, True), (line, False)], [(10.0, 10.0)], 1.0)
        self.assertEqual(chains[0][0][0], (10.0, 10.0))                      # le contour fermé garde sa marque
        self.assertEqual(chains[1][0], line)
        chains, fixed = S.apply_starts([(line[::-1], False)], [(10.0, 10.0)], 1.0)
        self.assertEqual(chains[0][0], line[::-1])                           # un trait : pas par les marques des fermés


class Window(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.resize(1200, 800)
        self.w.show()
        app.processEvents()
        self.addCleanup(self.close)
        self.info = mock.patch('vectordrive.ui.main_window.QMessageBox.information')
        self.said = self.info.start()
        self.addCleanup(self.info.stop)

    def close(self):
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()

    def add(self, c):
        s = Shape(path=geom.Path([c]), tool=0)
        self.w.canvas.doc.add(s)
        return s

    def test_o_is_the_start_point(self):
        self.assertIn('O', [k.toString() for k in self.w.A['node_start'].shortcuts()])

    def test_node_mode_on_an_open_contour(self):
        w = self.w
        s = self.add(geom.polyline([(0, 0), (10, 0), (20, 5)]))
        w.canvas.select([s])
        w.A['tool_node'].trigger()
        tool = w.canvas.tool_obj
        tool.sel.clear()
        tool.sel.add((0, 2))                                                 # la dernière extrémité
        w.node_start()
        self.assertFalse(self.said.called, 'avant : « Le contour est ouvert » et rien')
        c = s.path.contours[0]
        self.assertEqual(tuple(c.segments[0].start[:2]), (20.0, 5.0))       # le sens retourné
        self.assertEqual(s.extra['open_start'], [[20.0, 5.0, 0.0, 0.0]])
        self.assertNotIn('start_xy', s.extra)
        self.assertEqual(tool.sel, {(0, 0)})
        tool.sel.clear()
        tool.sel.add((0, 1))                                                 # un point du milieu : refusé
        w.node_start()
        self.assertTrue(self.said.called)
        w.undo()
        back = [x for L in w.canvas.doc.layers for x in L.items if isinstance(x, Shape)]
        self.assertEqual([tuple(x.path.contours[0].segments[0].start[:2]) for x in back], [(0.0, 0.0)])

    def test_the_mouse_tool(self):
        from vectordrive.ui import tools as T
        w = self.w
        sp = self.add(geom.polyline([(0, 0), (40, 0), (40, 40)]))
        ring = self.add(geom.rect(100, 100, 20, 20))
        w.set_tool('select')
        w.node_start()                                                       # O hors du Mode Point : l'outil
        tool = w.canvas.tool_obj
        self.assertIsInstance(tool, T.StartPointTool)
        tool.press(None, (40, 38), None)                                     # près du bout (40, 40)
        self.assertEqual(tuple(sp.path.contours[0].segments[0].start[:2]), (40.0, 40.0))
        self.assertEqual(sp.extra['open_start'], [[40.0, 40.0, 0.0, 0.0]])
        tool.press(None, (119, 101), None)                                   # près du coin (120, 100)
        self.assertEqual(tuple(ring.path.contours[0].segments[0].start[:2]), (120.0, 100.0))
        self.assertEqual(w.canvas.tool, 'start_point')                       # l'outil reste
        w.canvas.toolExitRequested.emit()
        self.assertEqual(w.canvas.tool, 'select')


if __name__ == '__main__':
    unittest.main()
