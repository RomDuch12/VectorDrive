"""Round 860 : simulation 2D : profondeur de la vue, contour théorique, en fond, hors matière, zoom (manuel de TE, pages 760 à 762)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', os.path.join(tempfile.mkdtemp(), 'session'))
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')

import numpy as np
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from vectordrive.cam import model as M
from vectordrive.cam import simulate
from vectordrive.cam import strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape
from vectordrive.ui.sim_dialog import SimDialog

app = QApplication.instance() or QApplication([])

SQUARE = geom.rect(10, 10, 20, 20)


def paths():
    """Une poche conique dans un carré : deux profondeurs, un chemin d'outil."""
    doc = Document()
    doc.plate = Plate(width=60.0, height=60.0)
    doc.layers = [Layer(name='A', items=[Shape(path=geom.Path([SQUARE]))])]
    setup = M.setup_of(doc)
    tool = M.CamTool(name='F', diameter=2.0)
    setup.tools.append(tool)
    op = M.Operation(kind='poche', tool_id=tool.id, depth=1.0)
    setup.operations.append(op)
    M.store(doc, setup)
    return S.compute(doc, setup, op, (0.0, 0.0)), setup


def steps():
    """Un résultat de simulation à deux profondeurs : 0,5 à gauche, 1 à droite."""
    H = np.zeros((100, 100))
    H[20:80, 20:50] = -0.5
    H[20:80, 50:80] = -1.0
    return simulate.SimResult(H=H, x0=0.0, y0=0.0, res=0.1, deepest=-1.0)


def red(c):
    return c.red() > 180 and c.green() < 90 and c.blue() < 90


def blue(c):
    return c.blue() > 120 and c.red() < 80


def line_blue(c):
    return c.blue() > 170 and c.green() > 90 and c.red() < 90


def orange(c):
    return c.red() > 150 and 60 < c.green() < 150 and c.blue() < 60


def count(image, test):
    return sum(1 for y in range(0, image.height(), 2) for x in range(0, image.width(), 2) if test(image.pixelColor(x, y)))


class Base(unittest.TestCase):

    def setUp(self):
        simulate._SIM_CACHE.clear()
        self.tp, self.setup_doc = paths()
        self.dlg = SimDialog(None, [self.tp], self.setup_doc, None, [[(s.start[0], s.start[1]) for s in SQUARE.segments]
                                                                     + [tuple(SQUARE.segments[0].start[:2])]])

    def tearDown(self):
        self.dlg.done(0)


class TestLevel(Base):

    def test_the_range_is_the_depth(self):
        self.assertAlmostEqual(self.dlg.level.minimum(), -1.0, places=3)
        self.assertEqual(self.dlg.level.maximum(), 0.0)

    def test_the_slider_and_the_field_follow_each_other(self):
        self.dlg.level_slider.setValue(500)
        self.assertAlmostEqual(self.dlg.level.value(), -0.5, places=3)
        self.dlg.level.setValue(-0.25)
        self.assertEqual(self.dlg.level_slider.value(), 250)

    def test_a_level_shows_what_is_removed(self):
        self.dlg.result = steps()
        self.dlg.level.setRange(-1.0, 0.0)
        self.dlg.level.setValue(-0.75)
        image = self.dlg.image
        w = image.width()
        self.assertFalse(blue(image.pixelColor(w * 35 // 100, w // 2)))      # creusé à 0,5 seulement
        self.assertTrue(blue(image.pixelColor(w * 65 // 100, w // 2)))       # creusé à 1

    def test_it_does_not_simulate_again(self):
        was = self.dlg.result
        self.dlg.level.setValue(-0.5)
        self.assertIs(self.dlg.result, was)

    def test_render_level(self):
        sim = steps()
        shallow = simulate.render(sim, 100, level=-0.25)
        deep = simulate.render(sim, 100, level=-0.75)
        below = simulate.render(sim, 100, level=-5.0)                  # rien à cette cote
        self.assertGreater(count(shallow, blue), count(deep, blue))
        self.assertGreater(count(deep, blue), 0)
        self.assertEqual(count(below, blue), 0)


class TestOptions(Base):

    def test_no_red_by_default(self):
        self.assertEqual(count(self.dlg.image, red), 0)

    def test_theory_in_red(self):
        self.dlg.show_theory.setChecked(True)
        self.assertGreater(count(self.dlg.image, red), 0)

    def test_theory_is_on_the_contour(self):
        self.dlg.show_theory.setChecked(True)
        r = self.dlg.result
        image = self.dlg.image
        k = image.width() / r.H.shape[1] / r.res
        x, y = round((10.0 - r.x0) * k), round(image.height() - (20.0 - r.y0) * k)     # le milieu du côté gauche
        self.assertTrue(any(red(image.pixelColor(x + d, y)) for d in range(-3, 4)))

    def test_theory_is_off_without_contours(self):
        dlg = SimDialog(None, [self.tp], self.setup_doc)
        self.assertFalse(dlg.show_theory.isEnabled())
        dlg.done(0)

    def test_bottom_in_orange(self):
        self.assertEqual(count(self.dlg.image, orange), 0)
        self.dlg.show_bottom.setChecked(True)
        self.assertGreater(count(self.dlg.image, orange), 0)

    def test_moves_in_blue(self):
        self.assertEqual(count(self.dlg.image, line_blue), 0)
        self.dlg.show_moves.setChecked(True)
        self.assertGreater(count(self.dlg.image, line_blue), 0)

    def test_tool_lines_include_the_arcs(self):
        tp = M.Toolpath('', '')
        tp.moves = [M.Move('feed', 10.0, 0.0, -1.0), M.Move('arc_ccw', 0.0, 10.0, -1.0, 0.0, 0.0)]
        dlg = SimDialog(None, [self.tp], self.setup_doc)
        dlg.toolpaths = [tp]
        pts = dlg._tool_lines()[0]
        self.assertGreater(len(pts), 5)
        self.assertAlmostEqual(pts[-1][1], 10.0, places=6)
        dlg.done(0)

    def test_the_saved_image_has_the_overlays(self):
        self.dlg.show_theory.setChecked(True)
        path = os.path.join(tempfile.mkdtemp(), 's.png')
        self.dlg.save_image(path)
        from PySide6.QtGui import QImage
        self.assertGreater(count(QImage(path), red), 0)


class TestZoom(Base):

    def press(self, shift=False):
        return QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(50, 50), QPointF(50, 50), Qt.MouseButton.RightButton,
                           Qt.MouseButton.RightButton,
                           Qt.KeyboardModifier.ShiftModifier if shift else Qt.KeyboardModifier.NoModifier)

    def width(self):
        return self.dlg.view.pixmap().width()

    def test_right_click_enlarges(self):
        self.assertEqual(self.width(), SimDialog.VIEW_WIDTH)
        QApplication.sendEvent(self.dlg.view, self.press())
        self.assertEqual((self.dlg.zoom, self.width()), (2, 2 * SimDialog.VIEW_WIDTH))

    def test_shift_reduces(self):
        QApplication.sendEvent(self.dlg.view, self.press())
        QApplication.sendEvent(self.dlg.view, self.press(True))
        self.assertEqual((self.dlg.zoom, self.width()), (1, SimDialog.VIEW_WIDTH))

    def test_it_stops_at_both_ends(self):
        QApplication.sendEvent(self.dlg.view, self.press(True))
        self.assertEqual(self.dlg.zoom, 1)
        for _ in range(6):
            QApplication.sendEvent(self.dlg.view, self.press())
        self.assertEqual(self.dlg.zoom, SimDialog.ZOOMS[-1])

    def test_the_zoom_survives_the_options(self):
        QApplication.sendEvent(self.dlg.view, self.press())
        self.dlg.show_bottom.setChecked(True)
        self.assertEqual(self.width(), 2 * SimDialog.VIEW_WIDTH)


class TestPanel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.close()

    def test_the_panel_gives_the_contours(self):
        w = self.win
        doc = w.canvas.doc
        s = Shape(path=geom.Path([SQUARE]))
        layer = Layer(name='Plan 1', items=[s])
        doc.layers[:] = [layer]
        doc.active = layer.id
        doc.plate = Plate(width=60.0, height=60.0)
        w.canvas.select([s])
        panel = w.cam_panel
        setup = panel.setup()
        setup.operations[:] = []
        panel.save(setup)
        op = panel.new_operation('gravure', exec_dialog=False)
        lines = panel._theory_lines([t for t in panel.toolpaths if t.op_id == op.id] or [M.Toolpath(op.id, op.tool_id)])
        self.assertEqual(len(lines), 1)
        self.assertEqual(tuple(lines[0][0][:2]), (10.0, 10.0))

    def test_paths_without_operation(self):
        self.assertEqual(self.win.cam_panel._theory_lines([M.Toolpath('rien', '')]), [])


if __name__ == '__main__':
    unittest.main()
