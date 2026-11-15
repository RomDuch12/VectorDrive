"""Round 832 : Textes sur arcs multiples : quatre cases, réglages relus, aperçu."""
import os
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core import text as TX
from vectordrive.core.document import Layer, Plate, Shape, Text
from vectordrive.core.geom import Path
from vectordrive.ui.dialogs import TextArcsDialog
from vectordrive.ui.main_window import MainWindow

app = QApplication.instance() or QApplication([])


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.close()
        cls.win.deleteLater()

    def setUp(self):
        self.doc = self.win.canvas.doc
        self.layer = Layer(name='Plan 1')
        self.doc.layers[:] = [self.layer]
        self.doc.active = self.layer.id
        self.doc.plate = Plate(width=200.0, height=100.0)
        self.win._undo.clear()
        self.a, self.b, self.c = self.text('Première'), self.text('Seconde'), self.text('Troisième')
        self.texts = [self.a, self.b, self.c]
        self.win.canvas.select(self.texts)

    def text(self, s):
        t = Text(text=s, font='Arial', size=4.0)
        t.outline = TX.outline_for(t)
        self.layer.items.append(t)
        return t


class Boxes(Base):
    def dialog(self):
        return self.win.text_arcs_dialog(exec_dialog=False)

    def test_first_time_the_lines_are_staggered(self):
        d = self.dialog()
        radii = [r[0] for r in d.rows()]
        self.assertGreater(radii[0], radii[1])
        self.assertGreater(radii[1], radii[2])
        self.assertEqual({r[1] for r in d.rows()}, {90.0})

    def test_same_radius_only_touches_the_radius(self):
        d = self.dialog()
        d.widgets[1][1].setValue(45.0)
        d.same_radius.setChecked(True)
        d.widgets[0][0].setValue(77.0)
        rows = d.rows()
        self.assertEqual([r[0] for r in rows], [77.0, 77.0, 77.0])
        self.assertEqual(rows[1][1], 45.0)
        self.assertFalse(d.widgets[1][0].isEnabled())
        self.assertTrue(d.widgets[0][0].isEnabled())
        self.assertTrue(d.widgets[1][1].isEnabled())

    def test_same_angle(self):
        d = self.dialog()
        d.widgets[0][1].setValue(180.0)
        d.widgets[2][0].setValue(33.0)
        d.same_angle.setChecked(True)
        rows = d.rows()
        self.assertEqual([r[1] for r in rows], [180.0, 180.0, 180.0])
        self.assertEqual(rows[2][0], 33.0)

    def test_same_direction(self):
        d = self.dialog()
        d.widgets[1][1].setValue(10.0)
        d.same_direction.setChecked(True)
        d.widgets[0][2].setChecked(False)
        rows = d.rows()
        self.assertEqual([r[2] for r in rows], [False, False, False])
        self.assertEqual(rows[1][1], 10.0)

    def test_same_type(self):
        d = self.dialog()
        d.same_type.setChecked(True)
        d.widgets[0][3].setCurrentIndex(d.widgets[0][3].findData('incline'))
        self.assertEqual([r[3] for r in d.rows()], ['incline'] * 3)

    def test_unchecking_gives_the_line_back(self):
        d = self.dialog()
        d.same_radius.setChecked(True)
        d.same_radius.setChecked(False)
        self.assertTrue(d.widgets[2][0].isEnabled())
        d.widgets[2][0].setValue(5.0)
        self.assertEqual(d.rows()[2][0], 5.0)

    def test_rotation_adds_to_every_line(self):
        d = self.dialog()
        d.widgets[0][1].setValue(30.0)
        d.rotation.setValue(15.0)
        self.assertEqual(d.rows()[0][1], 45.0)
        self.assertEqual(d.rows()[1][1], 105.0)


class Reopen(Base):
    def test_settings_come_back(self):
        rows = [(50.0, 180.0, True, 'simple'), (75.0, 120.0, False, 'radial'), (100.0, 60.0, True, 'incline')]
        self.win.text_arcs(self.texts, (125.0, 100.0), rows)
        d = self.win.text_arcs_dialog(exec_dialog=False)
        self.assertEqual(d.center(), (125.0, 100.0))
        self.assertEqual(d.rows(), rows)
        self.assertEqual(d.rotation.value(), 0.0)

    def test_a_turn_too_many_is_folded(self):
        self.win.text_arcs(self.texts, (0.0, 0.0), [(50.0, 400.0, True, 'simple')] * 3)
        d = self.win.text_arcs_dialog(exec_dialog=False)
        self.assertAlmostEqual(d.rows()[0][1], 40.0)

    def test_a_mix_of_placed_and_new_texts(self):
        self.win.text_arcs([self.b], (10.0, 20.0), [(60.0, 45.0, False, 'radial')])
        d = self.win.text_arcs_dialog(exec_dialog=False)
        self.assertEqual(d.center(), (10.0, 20.0))
        self.assertEqual(d.rows()[1], (60.0, 45.0, False, 'radial'))
        self.assertEqual(d.rows()[0][1], 90.0)

    def test_a_selected_circle_wins_over_the_old_center(self):
        self.win.text_arcs(self.texts, (10.0, 20.0), [(50.0, 90.0, True, 'simple')] * 3)
        circle = Shape(path=Path([geom.circle((70.0, 40.0), 5.0)]))
        self.layer.items.append(circle)
        self.win.canvas.select(self.texts + [circle])
        d = self.win.text_arcs_dialog(exec_dialog=False)
        self.assertAlmostEqual(d.center()[0], 70.0)
        self.assertAlmostEqual(d.center()[1], 40.0)


class Preview(Base):
    def test_cancel_after_preview_changes_nothing(self):
        before = self.a.outline.bbox()
        seen = []

        def fake_exec(dlg):
            dlg.widgets[0][0].setValue(40.0)
            dlg.b_preview.click()
            seen.append(self.a.extra['arc_warp']['radius'])
            seen.append(self.a.outline.bbox())
            return 0
        n = len(self.win._undo)
        with mock.patch.object(TextArcsDialog, 'exec', fake_exec):
            self.win.text_arcs_dialog()
        self.assertEqual(seen[0], 40.0)
        self.assertNotEqual(seen[1], before)
        self.assertNotIn('arc_warp', self.a.extra)
        self.assertEqual(self.a.outline.bbox(), before)
        self.assertEqual(len(self.win._undo), n)

    def test_ok_after_preview_is_one_undo(self):
        def fake_exec(dlg):
            dlg.widgets[0][0].setValue(40.0)
            dlg.preview_now()
            return 1
        n = len(self.win._undo)
        with mock.patch.object(TextArcsDialog, 'exec', fake_exec):
            self.win.text_arcs_dialog()
        self.assertEqual(self.a.extra['arc_warp']['radius'], 40.0)
        self.assertEqual(len(self.win._undo), n + 1)
        self.win.undo()
        self.assertNotIn('arc_warp', self.doc.layers[0].items[0].extra)

    def test_previous_arc_comes_back_on_cancel(self):
        self.win.text_arcs(self.texts, (0.0, 0.0), [(50.0, 90.0, True, 'simple')] * 3)
        old = dict(self.a.extra['arc_warp'])

        def fake_exec(dlg):
            dlg.widgets[0][0].setValue(90.0)
            dlg.preview_now()
            return 0
        with mock.patch.object(TextArcsDialog, 'exec', fake_exec):
            self.win.text_arcs_dialog()
        self.assertEqual(self.a.extra['arc_warp'], old)

    def test_without_callback_the_button_is_off(self):
        d = TextArcsDialog(None, self.texts, (0.0, 0.0))
        self.assertFalse(d.b_preview.isEnabled())
        d.preview_now()
        d.deleteLater()


if __name__ == '__main__':
    unittest.main()
