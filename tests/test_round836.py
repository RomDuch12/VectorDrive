"""Round 836 : Rogner, Poinçonner, Ajuster : le cadre d'abord, comme TE ; Ctrl pour le type."""
import os
import types
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core import text as TX
from vectordrive.core.document import Group, Layer, Plate, Shape, Text
from vectordrive.core.geom import Path
from vectordrive.ui.main_window import MainWindow

app = QApplication.instance() or QApplication([])
KEYS = ('rogner/type', 'rogner/garder', 'poinconner/type', 'poinconner/garder')


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
        self.c = self.win.canvas
        self.doc = self.c.doc
        self.layer = Layer(name='Plan 1')
        self.doc.layers[:] = [self.layer]
        self.doc.active = self.layer.id
        self.doc.plate = Plate(width=200.0, height=100.0)
        self.win._undo.clear()
        self.frame = self.rect(0.0, 0.0, 20.0, 20.0)

    def tearDown(self):
        for k in KEYS:
            self.win.settings.remove(k)

    def add(self, path, **kw):
        s = Shape(path=path, **kw)
        self.layer.items.append(s)
        return s

    def rect(self, x, y, w, h, **kw):
        return self.add(Path([geom.rect(x, y, w, h)]), **kw)

    def line(self, x0, y0, x1, y1):
        return self.add(Path([geom.polyline([(x0, y0), (x1, y1)])]))

    def others(self):
        return [i for i in self.layer.items if i is not self.frame]

    def with_ctrl(self, mode=None, keep=True):
        answer = types.SimpleNamespace(mode=mode, keep=keep)
        fake = mock.MagicMock()
        fake.return_value.exec.return_value = bool(mode)
        fake.return_value.result_params.return_value = answer
        return mock.patch.object(MainWindow, '_ctrl_held', staticmethod(lambda: True)), mock.patch('vectordrive.ui.dialogs.ParamsDialog', fake), fake


class Order(Base):
    def test_first_closed_is_the_frame(self):
        inner = self.rect(5.0, 5.0, 30.0, 5.0)
        self.c.select([self.frame, inner])
        self.win.clip_items()
        b = self.others()[0].path.bbox()
        self.assertLessEqual(b[2], 20.0 + 1e-6)
        self.assertEqual(self.frame.path.bbox(), (0.0, 0.0, 20.0, 20.0))

    def test_the_other_order_cuts_the_other_way(self):
        other = self.rect(5.0, 5.0, 30.0, 5.0)
        self.c.select([other, self.frame])
        self.win.clip_items()
        self.assertEqual(other.path.bbox(), (5.0, 5.0, 35.0, 10.0))
        b = next(i for i in self.layer.items if i is not other).path.bbox()
        self.assertEqual((b[1], b[3]), (5.0, 10.0))

    def test_open_first_falls_back_on_the_last(self):
        line = self.line(-10.0, 10.0, 30.0, 10.0)
        self.c.select([line, self.frame])
        self.win.clip_items()
        self.assertAlmostEqual(self.others()[0].path.length(), 20.0, places=6)

    def test_group_of_closed_contours_is_a_frame(self):
        g = Group(children=[Shape(path=Path([geom.rect(0.0, 0.0, 10.0, 10.0)])), Shape(path=Path([geom.rect(20.0, 0.0, 10.0, 10.0)]))])
        self.layer.items.remove(self.frame)
        self.layer.items.append(g)
        line = self.line(-5.0, 5.0, 35.0, 5.0)
        self.c.select([g, line])
        self.win.clip_items()
        cut = next(i for i in self.layer.items if isinstance(i, Shape))
        self.assertAlmostEqual(cut.path.length(), 20.0, places=6)

    def test_text_is_not_a_frame(self):
        t = Text(text='A', font='Arial', size=5.0)
        t.outline = TX.outline_for(t)
        self.layer.items.append(t)
        self.assertIsNone(self.win._closed_path(t))

    def test_no_closed_object_says_so(self):
        self.layer.items.remove(self.frame)
        a, b = self.line(190.0, 5.0, 210.0, 5.0), self.line(190.0, 9.0, 210.0, 9.0)
        self.c.select([a, b])
        self.win.clip_items()
        self.assertIn('plaque', self.win.statusBar().currentMessage())
        self.assertAlmostEqual(self.layer.items[0].path.length(), 10.0, places=6)

    def test_punch_takes_the_first(self):
        line = self.line(-10.0, 10.0, 30.0, 10.0)
        self.c.select([self.frame, line])
        self.win.punch_items()
        self.assertAlmostEqual(self.others()[0].path.length(), 20.0, places=6)
        self.assertEqual(len(self.others()[0].path.contours), 2)

    def test_punch_without_a_closed_shape_explains(self):
        self.layer.items.remove(self.frame)
        a, b = self.line(0.0, 0.0, 1.0, 1.0), self.line(2.0, 2.0, 3.0, 3.0)
        self.c.select([a, b])
        with mock.patch('vectordrive.ui.main_window.QMessageBox.information') as say:
            self.win.punch_items()
        say.assert_called_once()

    def test_fit_takes_the_first(self):
        logo = self.rect(50.0, 50.0, 4.0, 4.0)
        self.c.select([self.frame, logo])
        out = self.win.fit_into_frame(1.0, False)
        self.assertEqual(out, self.c.selection)
        self.assertEqual(self.frame.path.bbox(), (0.0, 0.0, 20.0, 20.0))
        b = out[0].path.bbox()
        self.assertAlmostEqual(b[2] - b[0], 18.0, places=6)

    def test_fit_with_an_open_frame_still_works(self):
        self.layer.items.remove(self.frame)
        logo = self.line(0.0, 0.0, 2.0, 2.0)
        bar = self.line(50.0, 50.0, 70.0, 70.0)
        self.c.select([logo, bar])
        out = self.win.fit_into_frame(0.0, False)
        b = out[0].path.bbox()
        self.assertAlmostEqual(b[2] - b[0], 20.0, places=6)


class Types(Base):
    def setUp(self):
        super().setUp()
        self.inside = self.line(5.0, 5.0, 15.0, 5.0)
        self.across = self.line(10.0, 10.0, 40.0, 10.0)
        self.outside = self.line(50.0, 5.0, 60.0, 5.0)
        self.targets = [self.inside, self.across, self.outside]

    def run_clip(self, mode, keep=True):
        held, dlg, _fake = self.with_ctrl(mode, keep)
        self.c.select([self.frame] + self.targets)
        with held, dlg:
            self.win.clip_items()

    def lengths(self):
        return sorted(round(i.path.length(), 6) for i in self.others())

    def test_standard_cuts_what_touches(self):
        self.run_clip('standard')
        self.assertEqual(self.lengths(), [10.0, 10.0])

    def test_strict_removes_what_touches(self):
        self.run_clip('strict')
        self.assertEqual(self.lengths(), [10.0])

    def test_touching_keeps_it_whole(self):
        self.run_clip('touching')
        self.assertEqual(self.lengths(), [10.0, 30.0])

    def test_frame_can_go(self):
        self.run_clip('standard', keep=False)
        self.assertNotIn(self.frame, self.layer.items)
        self.assertEqual(self.lengths(), [10.0, 10.0])

    def test_frame_goes_even_when_nothing_changes(self):
        held, dlg, _fake = self.with_ctrl('standard', False)
        self.c.select([self.frame, self.inside])
        with held, dlg:
            self.win.clip_items()
        self.assertNotIn(self.frame, self.layer.items)

    def test_cancel_changes_nothing(self):
        held, dlg, _fake = self.with_ctrl(None)
        self.c.select([self.frame] + self.targets)
        n = len(self.win._undo)
        with held, dlg:
            self.win.clip_items()
        self.assertEqual(len(self.layer.items), 4)
        self.assertEqual(len(self.win._undo), n)

    def test_choices_are_kept(self):
        self.run_clip('strict', keep=False)
        self.assertEqual(self.win.settings.value('rogner/type'), 'strict')

    def test_plain_click_stays_standard(self):
        self.run_clip('strict')
        self.win.undo()
        self.c.select([self.doc.layers[0].items[0]] + self.doc.layers[0].items[1:])
        self.win.clip_items()
        self.assertEqual(sorted(round(i.path.length(), 6) for i in self.doc.layers[0].items[1:]), [10.0, 10.0])

    def test_combined_shape_judged_contour_by_contour(self):
        both = self.add(Path([geom.polyline([(5.0, 15.0), (15.0, 15.0)]), geom.polyline([(10.0, 18.0), (40.0, 18.0)])]))
        held, dlg, _fake = self.with_ctrl('strict')
        self.c.select([self.frame, both])
        with held, dlg:
            self.win.clip_items()
        kept = next(i for i in self.layer.items if i not in (self.frame, self.inside, self.across, self.outside))
        self.assertEqual(len(kept.path.contours), 1)
        self.assertAlmostEqual(kept.path.length(), 10.0, places=6)

    def test_text_judged_as_one_block(self):
        t = Text(text='AB', font='Arial', size=5.0, matrix=geom.Affine.translation(18.0, 5.0))
        t.outline = TX.outline_for(t)
        self.layer.items.append(t)
        held, dlg, _fake = self.with_ctrl('strict')
        self.c.select([self.frame, t])
        with held, dlg:
            self.win.clip_items()
        self.assertNotIn(t, self.layer.items)

    def test_punch_strict_keeps_only_the_far_ones(self):
        held, dlg, fake = self.with_ctrl('strict')
        self.c.select([self.frame] + self.targets)
        with held, dlg:
            self.win.punch_items()
        self.assertEqual(self.lengths(), [10.0])
        self.assertIn(self.outside, self.layer.items)
        self.assertEqual(fake.call_args[0][1], 'Type de perforage')

    def test_punch_touching_keeps_it_whole(self):
        held, dlg, _fake = self.with_ctrl('touching')
        self.c.select([self.frame] + self.targets)
        with held, dlg:
            self.win.punch_items()
        self.assertEqual(self.lengths(), [10.0, 30.0])

    def test_undo_brings_all_back(self):
        self.run_clip('strict', keep=False)
        self.win.undo()
        self.assertEqual(len(self.doc.layers[0].items), 4)


if __name__ == '__main__':
    unittest.main()
