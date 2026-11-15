"""Round 763 : F2 : point de référence à 9 positions ; répéter la transformation ; transformer chaque objet."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', os.path.join(tempfile.mkdtemp(), 'session'))
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Group, Shape
from vectordrive.core.geom import Affine
from vectordrive.ui.main_window import MainWindow, ReferenceGrid

app = QApplication.instance() or QApplication([])


def rect(x, y, w=20.0, h=10.0):
    return Shape(path=geom.Path([geom.rect(x, y, w, h)]))


class Base(unittest.TestCase):
    def setUp(self):
        self.w = MainWindow()
        self.c = self.w.canvas
        self.a = rect(10, 20)
        self.w.settings.remove('f2/reference')
        self.w.dims.anchor.set_point((0.5, 0.5))
        self.c.doc.layers[0].items[:] = [self.a]
        self.c.invalidate()
        self.c.select([self.a])

    def tearDown(self):
        self.w.settings.remove('f2/reference')           # les essais suivants repartent du centre
        self.w.modified = False
        self.w.close()

    def items(self):
        return self.c.doc.layers[0].items


class TestReference(Base):
    def pick(self, pt):
        self.w.dims.anchor.buttons[pt].click()

    def test_nine_points(self):
        self.assertEqual(len(self.w.dims.anchor.buttons), 9)
        self.assertEqual(len(ReferenceGrid.POINTS), 9)
        self.assertEqual(self.w.dims.anchor.point(), (0.5, 0.5))

    def test_only_one_at_a_time(self):
        self.pick((0.0, 0.0))
        self.pick((1.0, 1.0))
        self.assertEqual([p for p, b in self.w.dims.anchor.buttons.items() if b.isChecked()], [(1.0, 1.0)])

    def test_position_read_at_the_point(self):
        d = self.w.dims
        d.refresh()
        self.assertAlmostEqual(d.fields['x'].value(), 20.0)              # centre, comme avant
        self.assertAlmostEqual(d.fields['y'].value(), 25.0)
        self.pick((0.0, 0.0))
        self.assertAlmostEqual(d.fields['x'].value(), 10.0)
        self.assertAlmostEqual(d.fields['y'].value(), 20.0)
        self.pick((1.0, 1.0))
        self.assertAlmostEqual(d.fields['x'].value(), 30.0)
        self.assertAlmostEqual(d.fields['y'].value(), 30.0)

    def test_type_a_corner_position(self):
        d = self.w.dims
        self.pick((0.0, 0.0))
        d.fields['x'].setValue(0.0)
        d.fields['y'].setValue(0.0)
        d.apply()
        bb = self.c.selection_bbox()
        self.assertAlmostEqual(bb[0], 0.0)
        self.assertAlmostEqual(bb[1], 0.0)
        self.assertAlmostEqual(bb[2], 20.0)                              # la taille n'a pas bougé

    def test_width_grows_from_the_point(self):
        d = self.w.dims
        d.keep.setChecked(False)
        self.pick((0.0, 0.0))
        d.fields['w'].setValue(40.0)
        d.apply()
        bb = self.c.selection_bbox()
        self.assertAlmostEqual(bb[0], 10.0)                              # le bord gauche reste
        self.assertAlmostEqual(bb[2], 50.0)
        self.assertAlmostEqual(bb[1], 20.0)

    def test_centre_still_grows_both_ways(self):
        d = self.w.dims
        d.keep.setChecked(False)
        d.refresh()
        d.fields['w'].setValue(40.0)
        d.apply()
        bb = self.c.selection_bbox()
        self.assertAlmostEqual(bb[0], 0.0)
        self.assertAlmostEqual(bb[2], 40.0)

    def test_rotation_around_the_point(self):
        d = self.w.dims
        self.pick((0.0, 0.0))
        d.rot.setValue(90.0)
        d._rotate()
        bb = self.c.selection_bbox()
        self.assertAlmostEqual(bb[2], 10.0)                              # le coin (10, 20) n'a pas bougé
        self.assertAlmostEqual(bb[1], 20.0)
        self.assertAlmostEqual(bb[0], 0.0)
        self.assertAlmostEqual(bb[3], 40.0)

    def test_scale_around_the_point(self):
        d = self.w.dims
        self.pick((1.0, 1.0))
        d.scale.setValue(50.0)
        d._scale()
        bb = self.c.selection_bbox()
        self.assertAlmostEqual(bb[2], 30.0)
        self.assertAlmostEqual(bb[3], 30.0)
        self.assertAlmostEqual(bb[0], 20.0)

    def test_remembered(self):
        self.pick((0.0, 1.0))
        self.assertEqual(self.w.settings.value('f2/reference'), '0.0,1.0')
        self.assertEqual(self.w.dims._saved_reference(), (0.0, 1.0))

    def test_bad_saved_value(self):
        self.w.settings.setValue('f2/reference', 'n,importe')
        self.assertEqual(self.w.dims._saved_reference(), (0.5, 0.5))
        self.w.dims.anchor.set_point((3.0, 3.0))                         # valeur hors grille : le centre
        self.assertEqual(self.w.dims.anchor.point(), (0.5, 0.5))

    def test_buttons_do_not_take_the_keyboard(self):
        from PySide6.QtCore import Qt
        for b in self.w.dims.anchor.buttons.values():
            self.assertEqual(b.focusPolicy(), Qt.FocusPolicy.NoFocus)


class TestAgain(Base):
    def test_nothing_yet(self):
        self.c.last_transform = None
        self.assertFalse(self.w.transform_again())
        self.assertEqual(self.c.selection_bbox()[0], 10.0)

    def test_repeat_a_move(self):
        self.c.transform_selection(Affine.translation(5, 1))
        self.assertTrue(self.w.A['transform_again'].isEnabled())
        self.w.A['transform_again'].trigger()
        bb = self.c.selection_bbox()
        self.assertAlmostEqual(bb[0], 20.0)
        self.assertAlmostEqual(bb[1], 22.0)

    def test_repeat_a_rotation_same_pivot(self):
        m = Affine.rotation(90, (0.0, 0.0))
        self.c.transform_selection(m)
        self.w.transform_again()
        bb = self.c.selection_bbox()
        self.assertAlmostEqual(bb[0], -30.0)                             # 180° au total autour de l'origine
        self.assertAlmostEqual(bb[3], -20.0)

    def test_undo(self):
        self.c.transform_selection(Affine.translation(5, 0))
        self.w.transform_again()
        self.assertAlmostEqual(self.items()[0].bbox()[0], 20.0)
        self.w.undo()
        self.assertAlmostEqual(self.items()[0].bbox()[0], 15.0)

    def test_needs_a_selection(self):
        self.c.transform_selection(Affine.translation(5, 0))
        self.c.select([])
        self.assertFalse(self.w.transform_again())

    def test_copy_leaves_the_original(self):
        self.c.transform_selection(Affine.translation(30, 0))
        before = self.items()[0]
        self.assertTrue(self.w.transform_again(copy=True))
        self.assertEqual(len(self.items()), 2)
        self.assertIs(self.items()[0], before)
        self.assertAlmostEqual(self.items()[0].bbox()[0], 40.0)
        self.assertAlmostEqual(self.items()[1].bbox()[0], 70.0)
        self.assertIs(self.c.selection[0], self.items()[1])

    def test_copy_chain(self):
        self.c.transform_selection(Affine.translation(30, 0))
        for _ in range(3):
            self.w.A['transform_again_copy'].trigger()
        self.assertEqual([round(it.bbox()[0]) for it in self.items()], [40, 70, 100, 130])

    def test_copy_has_its_own_id(self):
        self.c.transform_selection(Affine.translation(30, 0))
        self.w.transform_again(copy=True)
        self.assertNotEqual(self.items()[0].id, self.items()[1].id)

    def test_copy_undone_at_once(self):
        self.c.transform_selection(Affine.translation(30, 0))
        self.w.transform_again(copy=True)
        self.w.undo()
        self.assertEqual(len(self.items()), 1)
        self.assertAlmostEqual(self.items()[0].bbox()[0], 40.0)

    def test_copy_does_not_change_what_is_repeated(self):
        m = Affine.translation(30, 0)
        self.c.transform_selection(m)
        self.w.transform_again(copy=True)
        self.assertIs(self.c.last_transform, m)

    def test_copy_keeps_the_order_of_several(self):
        b = rect(10, 50)
        self.items().append(b)
        self.c.invalidate()
        self.c.select([self.items()[0], b])
        self.c.transform_selection(Affine.translation(30, 0))
        self.w.transform_again(copy=True)
        self.assertEqual(len(self.items()), 4)
        self.assertEqual(len(self.c.selection), 2)
        bb = [it.bbox() for it in self.c.selection]
        self.assertEqual(sorted(round(x[1]) for x in bb), [20, 50])
        self.assertEqual({round(x[0]) for x in bb}, {70})


class TestEach(Base):
    def setUp(self):
        super().setUp()
        self.b = rect(100, 100)
        self.items().append(self.b)
        self.c.invalidate()
        self.c.select([self.a, self.b])

    def run_each(self, **k):
        p = dict(dx=0.0, dy=0.0, sx=100.0, sy=100.0, angle=0.0, anchor='0.5,0.5')
        p.update(k)
        return self.w.transform_each(params=p)

    def centers(self):
        return [((b[0] + b[2]) / 2, (b[1] + b[3]) / 2) for b in (it.bbox() for it in self.items())]

    def test_turns_each_about_itself(self):
        self.assertEqual(self.run_each(angle=90.0), 2)
        for (cx, cy), (ex, ey) in zip(self.centers(), [(20.0, 25.0), (110.0, 105.0)]):
            self.assertAlmostEqual(cx, ex)
            self.assertAlmostEqual(cy, ey)
        bb = self.items()[0].bbox()
        self.assertAlmostEqual(bb[2] - bb[0], 10.0)                      # 20 x 10 devenu 10 x 20
        self.assertAlmostEqual(bb[3] - bb[1], 20.0)

    def test_scale_each_about_itself(self):
        self.run_each(sx=50.0, sy=200.0)
        for (cx, cy), (ex, ey) in zip(self.centers(), [(20.0, 25.0), (110.0, 105.0)]):
            self.assertAlmostEqual(cx, ex)
            self.assertAlmostEqual(cy, ey)
        bb = self.items()[1].bbox()
        self.assertAlmostEqual(bb[2] - bb[0], 10.0)
        self.assertAlmostEqual(bb[3] - bb[1], 20.0)

    def test_move_each(self):
        self.run_each(dx=5.0, dy=-2.0)
        self.assertAlmostEqual(self.items()[0].bbox()[0], 15.0)
        self.assertAlmostEqual(self.items()[1].bbox()[1], 98.0)

    def test_chosen_point(self):
        self.run_each(angle=90.0, anchor='0.0,0.0')
        bb = self.items()[0].bbox()
        self.assertAlmostEqual(bb[2], 10.0)
        self.assertAlmostEqual(bb[1], 20.0)

    def test_undo_all_at_once(self):
        self.run_each(angle=45.0)
        self.w.undo()
        self.assertAlmostEqual(self.items()[0].bbox()[0], 10.0)
        self.assertAlmostEqual(self.items()[1].bbox()[0], 100.0)

    def test_stays_selected(self):
        self.run_each(angle=45.0)
        self.assertEqual({id(x) for x in self.c.selection}, {id(x) for x in self.items()})

    def test_others_untouched(self):
        o = rect(300, 300)
        self.items().append(o)
        self.run_each(dx=5.0)
        self.assertIs(self.items()[2], o)

    def test_group_moves_as_one(self):
        g = Group(children=[rect(0, 0), rect(40, 0)])
        self.items()[:] = [g]
        self.c.invalidate()
        self.c.select([g])
        self.run_each(angle=180.0)
        bb = self.items()[0].bbox()
        self.assertAlmostEqual(bb[0], 0.0)
        self.assertAlmostEqual(bb[2], 60.0)

    def test_zero_scale_refused(self):
        self.assertEqual(self.run_each(sx=0.0), 0)
        self.assertAlmostEqual(self.items()[0].bbox()[0], 10.0)

    def test_nothing_selected(self):
        self.c.select([])
        self.assertEqual(self.run_each(angle=10.0), 0)

    def test_does_not_replace_what_is_repeated(self):
        self.c.last_transform = None
        self.run_each(angle=10.0)
        self.assertIsNone(self.c.last_transform)


class TestRibbon(Base):
    def test_in_the_ribbon_once(self):
        for k in ('transform_again', 'transform_again_copy', 'transform_each'):
            self.assertFalse(self.w.A[k].icon().isNull(), k)
            self.assertTrue(self.w.A[k].toolTip(), k)
            pages = [self.w.ribbon.page(i) for i in range(self.w.ribbon.count())]
            n = sum(1 for page in pages if page for g in page.groups() for b in g.buttons()
                    if b.defaultAction() is self.w.A[k])
            self.assertEqual(n, 1, k)

    def test_shortcuts_are_free(self):
        seen = {}
        for k, act in self.w.A.items():
            for s in act.shortcuts():
                seen.setdefault(s.toString(), []).append(k)
        self.assertEqual(seen['Ctrl+Alt+T'], ['transform_again'])
        self.assertEqual(seen['Ctrl+Alt+Shift+T'], ['transform_again_copy'])


if __name__ == '__main__':
    unittest.main()
