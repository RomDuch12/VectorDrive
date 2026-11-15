"""Round 835 : Geler devient étanche ; un objet gelé se désigne au clic et se dégèle seul."""
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QImage, QMouseEvent, QPainter
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Layer, Plate, Shape
from vectordrive.core.geom import Path
from vectordrive.ui.main_window import MainWindow

app = QApplication.instance() or QApplication([])
NONE = Qt.KeyboardModifier.NoModifier
CTRL = Qt.KeyboardModifier.ControlModifier


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.win = MainWindow()
        cls.win.resize(1200, 800)

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.close()
        cls.win.deleteLater()

    def setUp(self):
        self.c = self.win.canvas
        self.doc = self.c.doc
        self.layer = Layer(name='Plan 1')
        self.doc.layers[:] = [self.layer]
        self.doc.active = self.layer.id
        self.doc.plate = Plate(width=200.0, height=100.0)
        self.win._undo.clear()
        self.c.scale = 8.0
        self.c.move_delay_ms = 0
        self.win.set_tool('select')
        self.c.select([])
        self.a = self.rect(0.0, 0.0)
        self.b = self.rect(30.0, 0.0)
        self.ice = self.rect(60.0, 0.0)
        self.c.select([self.ice])
        self.win.freeze_selection()

    def rect(self, x, y, w=20.0, h=10.0):
        s = Shape(path=Path([geom.rect(x, y, w, h)]))
        self.layer.items.append(s)
        return s

    def mouse(self, kind, pos, mods=NONE):
        button = Qt.MouseButton.NoButton if kind == QEvent.Type.MouseMove else Qt.MouseButton.LeftButton
        buttons = Qt.MouseButton.NoButton if kind == QEvent.Type.MouseButtonRelease else Qt.MouseButton.LeftButton
        glob = QPointF(self.c.mapToGlobal(QPoint(int(pos.x()), int(pos.y()))))
        ev = QMouseEvent(kind, QPointF(pos), glob, button, buttons, mods)
        if kind == QEvent.Type.MouseButtonPress:
            self.c.mousePressEvent(ev)
        elif kind == QEvent.Type.MouseMove:
            self.c.mouseMoveEvent(ev)
        else:
            self.c.mouseReleaseEvent(ev)

    def click(self, x, y, mods=NONE):
        self.mouse(QEvent.Type.MouseButtonPress, self.c.to_screen(x, y), mods)
        self.mouse(QEvent.Type.MouseButtonRelease, self.c.to_screen(x, y), mods)

    def band(self, x0, y0, x1, y1):
        self.mouse(QEvent.Type.MouseButtonPress, self.c.to_screen(x0, y0))
        self.mouse(QEvent.Type.MouseMove, self.c.to_screen(x1, y1))
        self.mouse(QEvent.Type.MouseButtonRelease, self.c.to_screen(x1, y1))


class Sealed(Base):
    def test_rectangle_leaves_it_out(self):
        self.band(-5.0, -5.0, 90.0, 20.0)
        self.assertEqual(self.c.selection, [self.a, self.b])
        self.assertEqual(self.c.frozen_picked, [])

    def test_select_all_leaves_it_out(self):
        self.c.select_all()
        self.assertNotIn(self.ice, self.c.selection)

    def test_invert_leaves_it_out(self):
        self.c.select([self.a])
        self.c.invert_selection()
        self.assertEqual(self.c.selection, [self.b])

    def test_invert_leaves_hidden_objects_out(self):
        self.b.visible = False
        self.c.select([self.a])
        self.c.invert_selection()
        self.assertEqual(self.c.selection, [])

    def test_a_direct_request_does_not_select_it(self):
        self.c.select([self.a, self.ice])
        self.assertEqual(self.c.selection, [self.a])
        self.assertEqual(self.c.frozen_picked, [self.ice])

    def test_delete_does_not_touch_it(self):
        self.c.select([self.ice])
        self.win.A['delete'].trigger()
        self.assertIn(self.ice, self.layer.items)

    def test_move_does_not_touch_it(self):
        before = self.ice.path.bbox()
        self.c.select([self.ice])
        self.c.transform_selection(geom.Affine.translation(5.0, 0.0))
        self.assertEqual(self.ice.path.bbox(), before)
        self.assertEqual(self.c.selection, [])


class Pick(Base):
    def test_click_points_at_it(self):
        self.click(60.0, 5.0)
        self.assertEqual(self.c.selection, [])
        self.assertEqual(self.c.frozen_picked, [self.ice])

    def test_no_handles_on_it(self):
        self.click(60.0, 5.0)
        self.assertIsNone(self.c.selection_bbox())
        self.assertIsNone(self.c.handle_at(self.c.to_screen(60.0, 0.0)))

    def test_click_elsewhere_forgets_it(self):
        self.click(60.0, 5.0)
        self.click(150.0, 90.0)
        self.assertEqual(self.c.frozen_picked, [])

    def test_ctrl_adds_and_removes(self):
        other = self.rect(90.0, 0.0)
        self.c.select([other])
        self.win.freeze_selection()
        self.click(60.0, 5.0)
        self.click(90.0, 5.0, CTRL)
        self.assertEqual(self.c.frozen_picked, [self.ice, other])
        self.click(60.0, 5.0, CTRL)
        self.assertEqual(self.c.frozen_picked, [other])

    def test_an_object_on_top_wins(self):
        over = self.rect(60.0, 0.0)
        self.click(60.0, 5.0)
        self.assertEqual(self.c.selection, [over])
        self.assertEqual(self.c.frozen_picked, [])

    def test_a_drag_from_it_is_a_rectangle(self):
        before = self.ice.path.bbox()
        self.band(60.0, 5.0, 110.0, 40.0)
        self.assertEqual(self.ice.path.bbox(), before)
        self.assertEqual(self.c.selection, [])

    def test_it_is_drawn_in_its_own_color(self):
        self.click(60.0, 5.0)
        im = QImage(1200, 800, QImage.Format.Format_ARGB32)
        im.fill(0)
        p = QPainter(im)
        self.c._paint_frozen(p)
        p.end()
        q = self.c.to_screen(70.0, 0.0)
        self.assertEqual(im.pixelColor(int(q.x()), int(q.y())).name(), '#ff00ff')

    def test_a_removed_object_is_forgotten(self):
        self.click(60.0, 5.0)
        self.layer.items.remove(self.ice)
        self.assertEqual(self.c.frozen_selected(), [])


class Toggle(Base):
    def test_button_thaws_only_the_one_pointed_at(self):
        other = self.rect(90.0, 0.0)
        self.c.select([other])
        self.win.freeze_selection()
        self.click(60.0, 5.0)
        self.win.A['freeze'].trigger()
        self.assertFalse(self.ice.locked)
        self.assertTrue(other.locked)
        self.assertEqual(self.c.selection, [self.ice])

    def test_undo_freezes_it_again(self):
        self.click(60.0, 5.0)
        self.win.freeze_selection()
        self.win.undo()
        self.assertTrue(self.doc.layers[0].items[2].locked)

    def test_button_freezes_the_selection(self):
        self.c.select([self.a])
        self.win.A['freeze'].trigger()
        self.assertTrue(self.a.locked)
        self.assertEqual(self.c.selection, [])

    def test_nothing_chosen_changes_nothing(self):
        n = len(self.win._undo)
        self.c.select([])
        self.win.A['freeze'].trigger()
        self.assertEqual(len(self.win._undo), n)

    def test_thaw_all_still_works(self):
        self.win.unfreeze_all()
        self.assertFalse(self.ice.locked)
        self.assertEqual(self.c.selection, [self.ice])


if __name__ == '__main__':
    unittest.main()
