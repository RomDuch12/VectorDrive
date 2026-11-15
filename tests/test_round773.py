"""Round 773 : copie imbriquée (exemplaires par objet, point de départ, direction, plans)."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())

from PySide6.QtWidgets import QApplication, QMessageBox
from shapely.geometry import Polygon

from vectordrive.core import nesting as N
from vectordrive.core.document import Group, Layer, Plate, Shape, Text
from vectordrive.core.geom import Path, polyline, rect
from vectordrive.ui import shortcuts as S


def box(w=20.0, h=10.0, x=0.0, y=0.0, name=''):
    return Shape(path=Path([rect(x, y, w, h)]), name=name)


def ell(s=30.0, a=8.0):
    return Shape(path=Path([polyline([(0, 0), (s, 0), (s, a), (a, a), (a, s), (0, s)], True)]))


def plate(w=100.0, h=100.0):
    return Plate(x=0.0, y=0.0, width=w, height=h)


def boxes(res):
    return [it.transformed(m).bbox() for it, m in res.placed]


def disjoint(boxes_, gap=0.0):
    for i, a in enumerate(boxes_):
        for b in boxes_[i + 1:]:
            if a[0] < b[2] + gap - 1e-6 and b[0] < a[2] + gap - 1e-6 and a[1] < b[3] + gap - 1e-6 and b[1] < a[3] + gap - 1e-6:
                return False
    return True


class Counts(unittest.TestCase):
    def test_rectangles_one_count_per_object(self):
        a, b = box(name='a'), box(10, 10, name='b')
        res = N.nest([a, b], plate(), N.NestSpec(counts=[3, 2], margin=0.0, gap=1.0))
        self.assertEqual(sum(1 for it, _m in res.placed if it is a), 3)
        self.assertEqual(sum(1 for it, _m in res.placed if it is b), 2)
        self.assertEqual(res.unplaced, [])
        self.assertTrue(disjoint(boxes(res), 1.0))

    def test_shapes_one_count_per_object(self):
        a, b = ell(), box(10, 10)
        res = N.nest([a, b], plate(), N.NestSpec(counts=[2, 4], shape=True, margin=0.0, gap=1.0, precision=1.0))
        self.assertEqual(sum(1 for it, _m in res.placed if it is a), 2)
        self.assertEqual(sum(1 for it, _m in res.placed if it is b), 4)

    def test_zero_means_no_copy_and_not_too_large(self):
        a, b = box(), box(10, 10)
        for shape in (False, True):
            res = N.nest([a, b], plate(), N.NestSpec(counts=[0, 2], shape=shape, precision=1.0))
            self.assertEqual({id(it) for it, _m in res.placed}, {id(b)})
            self.assertEqual(res.unplaced, [])

    def test_all_zero_places_nothing(self):
        res = N.nest([box()], plate(), N.NestSpec(counts=[0]))
        self.assertEqual(res.placed, [])
        self.assertEqual(res.plates, 0)

    def test_missing_count_means_none(self):
        a, b = box(), box(10, 10)
        res = N.nest([a, b], plate(), N.NestSpec(counts=[2]))
        self.assertEqual(len(res.placed), 2)
        self.assertTrue(all(it is a for it, _m in res.placed))

    def test_negative_count_is_none(self):
        self.assertEqual(N.nest([box()], plate(), N.NestSpec(counts=[-3])).placed, [])

    def test_counts_win_over_copies_zero(self):
        """Exemplaires 0 remplit la plaque, sauf si le nombre est donné objet par objet."""
        res = N.nest([box()], plate(), N.NestSpec(copies=0, counts=[2]))
        self.assertEqual(len(res.placed), 2)

    def test_counts_over_several_sheets(self):
        res = N.nest([box(60, 60)], plate(), N.NestSpec(counts=[3], margin=0.0, gap=0.0))
        self.assertEqual(res.plates, 3)
        self.assertEqual(sorted(res.sheets), [0, 1, 2])

    def test_too_large_is_reported(self):
        res = N.nest([box(500, 500)], plate(), N.NestSpec(counts=[1]))
        self.assertEqual(len(res.unplaced), 1)

    def test_shape_sheets_recorded(self):
        res = N.nest([box(60, 60)], plate(), N.NestSpec(counts=[2], shape=True, margin=0.0, gap=0.0, precision=1.0))
        self.assertEqual(res.plates, 2)
        self.assertEqual(sorted(res.sheets), [0, 1])

    def test_old_behaviour_without_counts(self):
        res = N.nest([box()], plate(), N.NestSpec(copies=3))
        self.assertEqual(len(res.placed), 3)
        self.assertEqual(res.sheets, [0, 0, 0])

    def test_fill_records_sheets(self):
        res = N.nest([box(40, 40)], plate(), N.NestSpec(copies=0, margin=0.0, gap=0.0))
        self.assertEqual(len(res.placed), 4)
        self.assertEqual(res.sheets, [0, 0, 0, 0])


class Corner(unittest.TestCase):
    def _first(self, corner, shape=False):
        res = N.nest([box(20, 10)], plate(), N.NestSpec(counts=[1], margin=5.0, gap=1.0, corner=corner, shape=shape,
                                                        allow_rotate=False, precision=1.0))
        return boxes(res)[0]

    def test_rectangles(self):
        self.assertAlmostEqual(self._first('haut_gauche')[0], 5.0)
        self.assertAlmostEqual(self._first('haut_gauche')[3], 95.0)
        self.assertAlmostEqual(self._first('haut_droit')[2], 95.0)
        self.assertAlmostEqual(self._first('haut_droit')[3], 95.0)
        self.assertAlmostEqual(self._first('bas_gauche')[0], 5.0)
        self.assertAlmostEqual(self._first('bas_gauche')[1], 5.0)
        self.assertAlmostEqual(self._first('bas_droit')[2], 95.0)
        self.assertAlmostEqual(self._first('bas_droit')[1], 5.0)

    def test_shapes(self):
        for corner, xi, x, yi, y in (('haut_gauche', 0, 5.0, 3, 95.0), ('haut_droit', 2, 95.0, 3, 95.0),
                                     ('bas_gauche', 0, 5.0, 1, 5.0), ('bas_droit', 2, 95.0, 1, 5.0)):
            b = self._first(corner, shape=True)
            self.assertAlmostEqual(b[xi], x, delta=1.01, msg=corner)
            self.assertAlmostEqual(b[yi], y, delta=1.01, msg=corner)

    def test_rectangles_with_rotation_stay_on_the_plate(self):
        res = N.nest([box(90, 10)], plate(), N.NestSpec(counts=[9], margin=0.0, gap=1.0, corner='bas_droit'))
        for b in boxes(res):
            left = (b[0] + 1e-6) // (100 + N.PLATE_GAP) * (100 + N.PLATE_GAP)
            self.assertGreaterEqual(b[0], left - 1e-6)
            self.assertLessEqual(b[2], left + 100 + 1e-6)
        self.assertTrue(disjoint(boxes(res), 1.0))

    def test_interlocked_shapes_do_not_overlap_from_any_corner(self):
        for corner in N.CORNERS:
            res = N.nest([ell()], plate(), N.NestSpec(counts=[8], shape=True, margin=0.0, gap=1.0, precision=0.5, corner=corner))
            polys = [Polygon(it.transformed(m).path.contours[0].flatten(0.05)) for it, m in res.placed]
            for i, a in enumerate(polys):
                for b in polys[i + 1:]:
                    self.assertLess(a.intersection(b).area, 1e-6, corner)

    def test_shapes_stay_on_the_plate_from_any_corner(self):
        for corner in N.CORNERS:
            res = N.nest([ell()], plate(), N.NestSpec(counts=[5], shape=True, margin=2.0, gap=1.0, corner=corner))
            for b in boxes(res):
                self.assertGreaterEqual(b[0], 2.0 - 1e-6)
                self.assertGreaterEqual(b[1], 2.0 - 1e-6)
                self.assertLessEqual(b[2], 98.0 + 1e-6)
                self.assertLessEqual(b[3], 98.0 + 1e-6)

    def test_next_plates_still_to_the_right(self):
        res = N.nest([box(60, 60)], plate(), N.NestSpec(counts=[2], margin=0.0, gap=0.0, corner='bas_droit'))
        bs = sorted(boxes(res))
        self.assertAlmostEqual(bs[1][2], 100 + N.PLATE_GAP + 100)


class Direction(unittest.TestCase):
    def _spread(self, vertical, shape=False, corner='haut_gauche'):
        res = N.nest([box(20, 20)], plate(), N.NestSpec(counts=[3], margin=0.0, gap=0.0, vertical=vertical, shape=shape,
                                                        allow_rotate=False, precision=1.0, corner=corner))
        bs = boxes(res)
        return max(b[2] for b in bs) - min(b[0] for b in bs), max(b[3] for b in bs) - min(b[1] for b in bs)

    def test_rows_grow_sideways(self):
        w, h = self._spread(False)
        self.assertAlmostEqual(w, 60.0)
        self.assertAlmostEqual(h, 20.0)

    def test_columns_grow_downwards(self):
        w, h = self._spread(True)
        self.assertAlmostEqual(w, 20.0)
        self.assertAlmostEqual(h, 60.0)

    def test_shape_rows_and_columns(self):
        w, h = self._spread(False, shape=True)
        self.assertGreater(w, 55.0)
        self.assertLess(h, 25.0)
        w, h = self._spread(True, shape=True)
        self.assertLess(w, 25.0)
        self.assertGreater(h, 55.0)

    def test_columns_from_the_bottom_right(self):
        res = N.nest([box(20, 20)], plate(), N.NestSpec(counts=[2], margin=0.0, gap=0.0, vertical=True, allow_rotate=False,
                                                        corner='bas_droit'))
        bs = sorted(boxes(res), key=lambda b: b[1])
        self.assertAlmostEqual(bs[0][1], 0.0)
        self.assertAlmostEqual(bs[0][2], 100.0)
        self.assertAlmostEqual(bs[1][1], 20.0)

    def test_columns_with_rotation_fit_a_narrow_plate(self):
        """Haut et étroit : l'objet ne tient qu'en quart de tour, le rangement en colonnes aussi."""
        res = N.nest([box(90, 10)], Plate(x=0, y=0, width=20, height=100), N.NestSpec(counts=[2], margin=0.0, gap=0.0, vertical=True))
        self.assertEqual(res.rotated, 2)
        self.assertEqual(res.unplaced, [])
        self.assertTrue(disjoint(boxes(res)))

    def test_fill_in_columns(self):
        res = N.nest([box(40, 40)], plate(), N.NestSpec(copies=0, margin=0.0, gap=0.0, vertical=True, allow_rotate=False))
        self.assertEqual(len(res.placed), 4)
        self.assertTrue(disjoint(boxes(res)))

    def test_fill_shapes_in_columns(self):
        res = N.nest([box(40, 40)], plate(), N.NestSpec(copies=0, margin=0.0, gap=0.0, vertical=True, shape=True, precision=1.0))
        self.assertGreaterEqual(len(res.placed), 3)
        self.assertTrue(disjoint(boxes(res)))


class Command(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls._clean()
        cls.win.close()

    @classmethod
    def _clean(cls):
        for k in ('coin', 'vertical', 'plans', 'exemplaires', 'marge', 'ecart', 'rotation', 'forme', 'pas_angle', 'trous', 'precision'):
            cls.win.settings.remove(f'imbrication/{k}')

    def setUp(self):
        self._clean()
        doc = self.win.canvas.doc
        doc.plate = plate()
        doc.layers = [Layer(name='Plan 1')]
        doc.active = doc.layers[0].id
        self.a = box(60, 60, name='a')
        self.b = box(10, 10, x=200.0, name='b')
        doc.layers[0].items = [self.a, self.b]
        self.win.canvas.select([self.a, self.b])

    def _params(self, counts, per_plane=True, names=None, **kw):
        kw.setdefault('margin', 0.0)
        kw.setdefault('gap', 0.0)
        return {'spec': N.NestSpec(counts=counts, **kw), 'per_plane': per_plane, 'names': names or {}}

    def test_ribbon_and_te_command(self):
        self.assertEqual(S.TE_ACTIONS['ID_COMPO_MULTICOPYINTEL'], 'copy_nest')
        found = [b for i in range(self.win.ribbon.count()) for g in self.win.ribbon.page(i).groups() for b in g.buttons()
                 if b.defaultAction() is self.win.A['copy_nest']]
        self.assertEqual(len(found), 1)

    def test_commands_under_another_name(self):
        for cmd, key in (('ID_COMPO_CORORTHO', 'spell_check'), ('ID_TART_PLANREF', 'relief_level'), ('ID_RAPIDO_Kernel', 'text_kern_cycle'),
                         ('IDB_RAPIDO_HAUTEUR_CARACTERE', 'text_letters'), ('ID_RAPIDO_CHAR_PBINDICE_DLL', 'text_letters')):
            self.assertEqual(S.TE_ACTIONS[cmd], key)
            self.assertIn(key, self.win.A)

    def test_counts_per_object(self):
        res = self.win.copy_nest(self._params([1, 3]))
        self.assertEqual(len(res.placed), 4)
        self.assertEqual(sum(1 for it in self.win.canvas.doc.layers[0].items), 4)

    def test_one_plane_per_plate(self):
        res = self.win.copy_nest(self._params([3, 0]))
        doc = self.win.canvas.doc
        self.assertEqual(res.plates, 3)
        self.assertEqual(len(doc.layers), 3)
        self.assertEqual([L.name for L in doc.layers], ['Plan 1', 'Plan 2', 'Plan 3'])
        for L in doc.layers[1:]:
            self.assertEqual(len(L.items), 1)
            b = L.items[0].bbox()
            self.assertGreaterEqual(b[0], -1e-6)
            self.assertLessEqual(b[2], 100.0 + 1e-6)          # sur la plaque, pas à droite

    def test_plates_to_the_right_without_planes(self):
        self.win.copy_nest(self._params([3, 0], per_plane=False))
        doc = self.win.canvas.doc
        self.assertEqual(len(doc.layers), 1)
        self.assertGreater(max(it.bbox()[2] for it in doc.layers[0].items), 200.0)

    def test_zero_count_object_stays_where_it_is(self):
        self.win.copy_nest(self._params([1, 0]))
        self.assertIn(self.b, self.win.canvas.doc.layers[0].items)
        self.assertAlmostEqual(self.b.bbox()[0], 200.0)

    def test_first_copy_is_the_original_kept_in_first_plane_when_placed_elsewhere(self):
        # 2 grands sur 2 plaques : le premier reste sur le plan 1, l'autre sur le plan 2
        self.win.copy_nest(self._params([2, 0]))
        doc = self.win.canvas.doc
        self.assertEqual(sum(1 for it in doc.layers[0].items if it.name == 'a'), 1)
        self.assertEqual(sum(1 for it in doc.layers[1].items if it.name == 'a'), 1)

    def test_names_and_undo(self):
        self.win.copy_nest(self._params([1, 1], names={id(self.a): 'pomme'}))
        doc = self.win.canvas.doc
        self.assertIn('pomme', {it.name for it in doc.layers[0].items})
        self.win.undo()
        doc = self.win.canvas.doc
        self.assertEqual(len(doc.layers), 1)
        self.assertEqual(sorted(it.name for it in doc.layers[0].items), ['a', 'b'])

    def test_undo_removes_the_new_planes(self):
        self.win.copy_nest(self._params([3, 0]))
        self.win.undo()
        self.assertEqual(len(self.win.canvas.doc.layers), 1)
        self.assertEqual(len(self.win.canvas.doc.layers[0].items), 2)

    def test_plane_names_stay_unique(self):
        self.win.canvas.doc.layers[0].name = 'Plan 2'
        self.win.copy_nest(self._params([2, 0]))
        names = [L.name for L in self.win.canvas.doc.layers]
        self.assertEqual(len(names), len(set(names)))

    def test_needs_plate_and_selection(self):
        self.win.canvas.select([])
        with mock.patch.object(QMessageBox, 'information') as info:
            self.assertIsNone(self.win.copy_nest(self._params([1, 1])))
        info.assert_called_once()

    def test_settings_remembered(self):
        self.win.copy_nest(self._params([1, 1], corner='bas_droit', vertical=True, per_plane=False))
        s = self.win.settings
        self.assertEqual(str(s.value('imbrication/coin')), 'bas_droit')
        self.assertIn(s.value('imbrication/vertical'), (True, 'true'))
        self.assertIn(s.value('imbrication/plans'), (False, 'false'))
        spec = self.win._nest_spec()
        self.assertEqual(spec.corner, 'bas_droit')
        self.assertTrue(spec.vertical)

    def test_bad_corner_in_settings(self):
        self.win.settings.setValue('imbrication/coin', 'ailleurs')
        self.assertEqual(self.win._nest_spec().corner, N.CORNERS[0])

    def test_text_stays_a_text(self):
        t = Text(text='AB', font='Arial', size=8.0)
        self.win.canvas.doc.layers[0].items = [t]
        self.win.canvas.select([t])
        self.win.copy_nest(self._params([3]))
        items = self.win.canvas.doc.layers[0].items
        self.assertEqual(len(items), 3)
        self.assertTrue(all(isinstance(i, Text) for i in items))

    def test_group_stays_a_group(self):
        g = Group(children=[box(), box(5, 5, x=30.0)])
        self.win.canvas.doc.layers[0].items = [g]
        self.win.canvas.select([g])
        self.win.copy_nest(self._params([2]))
        self.assertTrue(all(isinstance(i, Group) for i in self.win.canvas.doc.layers[0].items))


class Dialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _dlg(self, **kw):
        from vectordrive.ui.copy_nest_dialog import CopyNestDialog
        self.a, self.b = box(name='a'), Text(text='Bonjour\nmonde', font='Arial', size=5.0)
        self.c = box()
        return CopyNestDialog(None, [self.a, self.b, self.c], N.NestSpec(), **kw)

    def test_names_shown(self):
        d = self._dlg()
        self.assertEqual(d.names()[0], 'a')
        self.assertEqual(d.names()[1], 'Bonjour')
        self.assertIn('3', d.names()[2])

    def test_same_count(self):
        d = self._dlg(count=4)
        self.assertEqual(d.counts(), [4, 4, 4])
        self.assertTrue(all(not sp.isEnabled() for sp in d.spins))
        self.assertIn('12', d.summary.text())

    def test_one_count_each(self):
        d = self._dlg()
        d.same.setChecked(False)
        self.assertTrue(all(sp.isEnabled() for sp in d.spins))
        d.spins[0].setValue(5)
        d.spins[1].setValue(0)
        self.assertEqual(d.counts()[:2], [5, 0])
        self.assertIn(str(5 + 0 + d.spins[2].value()), d.summary.text())
        self.assertEqual(d.result_params()['spec'].counts, d.counts())

    def test_only_changed_names_returned(self):
        d = self._dlg()
        d.table.item(0, 0).setText('pomme')
        names = d.result_params()['names']
        self.assertEqual(names, {id(self.a): 'pomme'})

    def test_blank_name_ignored(self):
        d = self._dlg()
        d.table.item(0, 0).setText('   ')
        self.assertEqual(d.result_params()['names'], {})

    def test_result(self):
        d = self._dlg(per_plane=False)
        d.corner.setCurrentIndex(3)
        d.direction.setCurrentIndex(1)
        d.margin.setValue(7.0)
        r = d.result_params()
        self.assertEqual(r['spec'].corner, 'bas_droit')
        self.assertTrue(r['spec'].vertical)
        self.assertEqual(r['spec'].margin, 7.0)
        self.assertFalse(r['per_plane'])

    def test_shape_settings_follow_the_checkbox(self):
        d = self._dlg()
        self.assertFalse(d.precision.isEnabled())
        d.shape.setChecked(True)
        self.assertTrue(d.precision.isEnabled())

    def test_starts_from_given_settings(self):
        from vectordrive.ui.copy_nest_dialog import CopyNestDialog
        d = CopyNestDialog(None, [box()], N.NestSpec(corner='haut_droit', vertical=True, gap=3.0, shape=True))
        self.assertEqual(d.corner.currentData(), 'haut_droit')
        self.assertTrue(d.direction.currentData())
        self.assertEqual(d.gap.value(), 3.0)
        self.assertTrue(d.shape.isChecked())


if __name__ == '__main__':
    unittest.main()
