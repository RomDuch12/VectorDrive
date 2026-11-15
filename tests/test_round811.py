"""Round 811 : imbrication, essayer plusieurs rangements et garder le meilleur."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication

from vectordrive.core import nesting as N
from vectordrive.core.document import Layer, Plate, Shape
from vectordrive.core.geom import Path, rect
from vectordrive.ui.copy_nest_dialog import CopyNestDialog

app = QApplication.instance() or QApplication([])
PLATE = Plate(width=100.0, height=100.0)


def box(w, h):
    return Shape(path=Path([rect(0, 0, w, h)]))


def mixed():
    sizes = [(62, 30), (38, 45), (38, 25), (62, 20), (30, 30), (32, 25), (20, 20), (18, 40), (45, 15), (25, 35),
             (40, 22), (15, 15), (33, 18), (27, 27), (12, 44), (50, 12)]
    return [box(w, h) for w, h in sizes]


def placed_boxes(res):
    out = []
    for (it, m), k in zip(res.placed, res.sheets):
        b = it.transformed(m).bbox()
        out.append((k, b))
    return out


def overlapping(res, gap=0.0):
    rows = placed_boxes(res)
    for i, (k, a) in enumerate(rows):
        for l, b in rows[i + 1:]:
            if k == l and a[0] < b[2] - 1e-6 and b[0] < a[2] - 1e-6 and a[1] < b[3] - 1e-6 and b[1] < a[3] - 1e-6:
                return True
    return False


class Ordered(unittest.TestCase):
    def test_zero_keeps_the_order(self):
        self.assertEqual(N._ordered([3, 1, 2], 0, lambda j: (j, j)), [3, 1, 2])

    def test_area_height_width(self):
        jobs = [(1, 9), (5, 5), (9, 1)]
        self.assertEqual(N._ordered(jobs, 1, lambda j: j)[0], (5, 5))
        self.assertEqual(N._ordered(jobs, 2, lambda j: j)[0], (1, 9))
        self.assertEqual(N._ordered(jobs, 3, lambda j: j)[0], (9, 1))

    def test_shuffle_is_repeatable_and_keeps_everything(self):
        jobs = list(range(50))
        a, b = N._ordered(jobs, 7, lambda j: (1, 1)), N._ordered(jobs, 7, lambda j: (1, 1))
        self.assertEqual(a, b)
        self.assertEqual(sorted(a), jobs)
        self.assertNotEqual(a, jobs)
        self.assertNotEqual(a, N._ordered(jobs, 8, lambda j: (1, 1)))


class Best(unittest.TestCase):
    def spec(self, **kw):
        return N.NestSpec(margin=0.0, gap=0.0, allow_rotate=False, **kw)

    def test_default_is_one_try_without_report(self):
        res = N.nest(mixed(), PLATE, self.spec())
        self.assertEqual(res.best, {})

    def test_one_try_same_as_before(self):
        items = mixed()
        one = N.nest(items, PLATE, self.spec())
        again = N._nest_once(items, PLATE, self.spec())
        self.assertEqual([m.to_tuple() for _i, m in one.placed], [m.to_tuple() for _i, m in again.placed])

    def test_never_worse_than_any_single_try(self):
        items = mixed()
        best = N.nest(items, PLATE, self.spec(tries=12, both_ways=True))
        self.assertEqual(best.best['tries'], 12)
        for vertical in (False, True):
            for order in range(6):
                res = N._nest_once(items, PLATE, self.spec(vertical=vertical, order=order))
                self.assertLessEqual(N._score(best), N._score(res))

    def test_it_really_gains_something_here(self):
        items = mixed()
        first = N._nest_once(items, PLATE, self.spec())
        best = N.nest(items, PLATE, self.spec(tries=40, both_ways=True))
        self.assertLess(N._score(best), N._score(first))

    def test_result_is_valid(self):
        items = mixed()
        best = N.nest(items, PLATE, self.spec(tries=20, both_ways=True))
        self.assertEqual(len(best.placed), len(items))
        self.assertFalse(overlapping(best))
        pitch = PLATE.width + N.PLATE_GAP
        for k, b in placed_boxes(best):
            self.assertGreaterEqual(b[0], k * pitch - 1e-6)
            self.assertLessEqual(b[2], k * pitch + PLATE.width + 1e-6)
            self.assertGreaterEqual(b[1], -1e-6)
            self.assertLessEqual(b[3], PLATE.height + 1e-6)

    def test_repeatable(self):
        a = N.nest(mixed(), PLATE, self.spec(tries=15, both_ways=True))
        b = N.nest(mixed(), PLATE, self.spec(tries=15, both_ways=True))
        self.assertEqual([m.to_tuple() for _i, m in a.placed], [m.to_tuple() for _i, m in b.placed])

    def test_items_untouched(self):
        items = mixed()
        before = [it.bbox() for it in items]
        N.nest(items, PLATE, self.spec(tries=5, both_ways=True))
        self.assertEqual([it.bbox() for it in items], before)

    def test_both_directions_are_tried_even_with_one_try(self):
        res = N.nest(mixed(), PLATE, self.spec(both_ways=True))
        self.assertEqual(res.best['tries'], 2)

    def test_time_limit_still_tries_both_directions(self):
        res = N.nest(mixed(), PLATE, self.spec(tries=50, both_ways=True, max_seconds=0.0))
        self.assertEqual(res.best['tries'], 2)
        res = N.nest(mixed(), PLATE, self.spec(tries=50, max_seconds=0.0))
        self.assertEqual(res.best['tries'], 1)

    def test_stops_at_the_wanted_gain(self):
        # le plus petit gain : arrêté dès la première amélioration, ou au bout des essais s'il n'y en a pas
        res = N.nest(mixed(), PLATE, self.spec(tries=50, min_gain=0.001))
        full = N.nest(mixed(), PLATE, self.spec(tries=50))
        self.assertLessEqual(res.best['tries'], full.best['tries'])
        self.assertGreaterEqual(res.best['filled'], 0.0)

    def test_filled_and_direction_are_reported(self):
        res = N.nest(mixed(), PLATE, self.spec(tries=4, both_ways=True))
        self.assertIn(res.best['vertical'], (True, False))
        self.assertGreater(res.best['filled'], 0.0)
        self.assertGreater(res.best['first_filled'], 0.0)

    def test_chosen_direction_matches_the_result(self):
        items = mixed()
        res = N.nest(items, PLATE, self.spec(tries=8, both_ways=True))
        again = N._nest_once(items, PLATE, self.spec(vertical=res.best['vertical'], order=res.best['order']))
        self.assertEqual([m.to_tuple() for _i, m in res.placed], [m.to_tuple() for _i, m in again.placed])

    def test_fill_keeps_the_fullest_plate(self):
        items = [box(30, 20)]
        h = N._nest_once(items, Plate(width=100.0, height=95.0), self.spec(copies=0))
        v = N._nest_once(items, Plate(width=100.0, height=95.0), self.spec(copies=0, vertical=True))
        best = N.nest(items, Plate(width=100.0, height=95.0), self.spec(copies=0, both_ways=True))
        self.assertEqual(len(best.placed), max(len(h.placed), len(v.placed)))

    def test_nothing_fits(self):
        res = N.nest([box(500, 500)], PLATE, self.spec(tries=3, both_ways=True))
        self.assertEqual(res.placed, [])
        self.assertEqual(len(res.unplaced), 1)

    def test_empty_selection(self):
        res = N.nest([], PLATE, self.spec(tries=3))
        self.assertEqual(res.placed, [])

    def test_shapes(self):
        items = mixed()[:6]
        spec = N.NestSpec(margin=1.0, gap=1.0, shape=True, tries=5, both_ways=True, precision=1.0)
        res = N.nest(items, PLATE, spec)
        self.assertEqual(len(res.placed), 6)
        self.assertLess(res.best['tries'], 6)
        self.assertGreater(res.usage, 0.0)
        self.assertFalse(overlapping(res))

    def test_a_region_stays_a_single_try(self):
        region = Path([rect(0, 0, 100, 100)])
        res = N.nest([box(10, 10)], PLATE, N.NestSpec(shape=True, region=region, tries=9, both_ways=True, copies=1))
        self.assertEqual(res.best, {})


class Windows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.close()
        cls.win.deleteLater()

    def setUp(self):
        self.doc = self.win.canvas.doc
        self.doc.layers[:] = [Layer(name='Plan 1')]
        self.doc.active = self.doc.layers[0].id
        self.doc.plate = Plate(width=100.0, height=100.0)
        self.win._undo.clear()
        for k in ('essais', 'deux_sens', 'duree', 'gain'):
            self.addCleanup(self.win.settings.remove, f'imbrication/{k}')

    def test_dialog_carries_the_settings(self):
        spec = N.NestSpec(tries=7, both_ways=True, max_seconds=12.0, min_gain=3.0)
        d = CopyNestDialog(None, [box(10, 10)], spec)
        self.addCleanup(d.deleteLater)
        out = d.result_params()['spec']
        self.assertEqual((out.tries, out.both_ways, out.max_seconds, out.min_gain), (7, True, 12.0, 3.0))

    def test_settings_are_remembered(self):
        spec = self.win._nest_spec()
        self.assertEqual((spec.tries, spec.both_ways), (1, False))
        it = box(10, 10)
        self.doc.layers[0].items.append(it)
        self.win.canvas.select([it])
        res = self.win.copy_nest({'spec': N.NestSpec(tries=3, both_ways=True, counts=[2], max_seconds=5.0, min_gain=1.0),
                                  'per_plane': True})
        self.assertEqual(res.best['tries'], 3)
        spec = self.win._nest_spec()
        self.assertEqual((spec.tries, spec.both_ways, spec.max_seconds, spec.min_gain), (3, True, 5.0, 1.0))

    def test_status_says_the_direction(self):
        it = box(10, 10)
        self.doc.layers[0].items.append(it)
        self.win.canvas.select([it])
        self.win.copy_nest({'spec': N.NestSpec(tries=2, both_ways=True, counts=[2]), 'per_plane': True})
        self.assertIn('2', self.win.statusBar().currentMessage())

    def test_one_try_message_is_unchanged(self):
        it = box(10, 10)
        self.doc.layers[0].items.append(it)
        self.win.canvas.select([it])
        self.win.copy_nest({'spec': N.NestSpec(counts=[2]), 'per_plane': True})
        self.assertNotIn('essai', self.win.statusBar().currentMessage())


if __name__ == '__main__':
    unittest.main()
