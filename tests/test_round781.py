"""Round 781 : copies liées."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())

import numpy as np
from PySide6.QtWidgets import QApplication

from vectordrive.core import linked as LK
from vectordrive.core.document import Document, Group, Layer, Shape, Text
from vectordrive.core.geom import Affine, Path, circle, polyline, rect


def square(x=0.0, y=0.0, s=10.0):
    return Shape(path=Path([rect(x, y, s, s)]))


def center(it):
    b = it.bbox()
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


def size(it):
    b = it.bbox()
    return b[2] - b[0], b[3] - b[1]


class Base(unittest.TestCase):
    def setUp(self):
        self.master = square()
        self.layer = Layer(items=[self.master])
        self.doc = Document(layers=[self.layer])
        self.cache = {}

    def add_copy(self, dx=50.0, dy=0.0):
        c = LK.make(self.master, dx, dy)
        self.layer.items.append(c)
        return c

    def edit_master(self, path):
        LK.prime(self.doc, self.cache)
        i = self.layer.items.index(self.master)
        new = Shape(id=self.master.id, path=path, tool=self.master.tool, extra=dict(self.master.extra))
        self.layer.items[i] = new
        self.master = new
        return LK.sync(self.doc, self.cache)

    def current(self, c):
        return next(it for it in self.layer.items if it.id == c.id)


class Fit(unittest.TestCase):
    PTS = np.array([[0, 0], [10, 0], [10, 5], [0, 7]], dtype=float)

    def _apply(self, m):
        return np.array([m.apply(tuple(p)) for p in self.PTS])

    def test_translation(self):
        a = LK.fit(self.PTS, self.PTS + [3, 4])
        self.assertAlmostEqual(a.apply((1, 1))[0], 4.0)

    def test_rotation_and_scale(self):
        m = Affine.translation(5, 6) @ Affine.rotation(30) @ Affine.scaling(2.0)
        a = LK.fit(self.PTS, self._apply(m))
        for p in ((1.0, 2.0), (-3.0, 8.0)):
            self.assertAlmostEqual(a.apply(p)[0], m.apply(p)[0], places=6)
            self.assertAlmostEqual(a.apply(p)[1], m.apply(p)[1], places=6)

    def test_different_shapes(self):
        other = self.PTS.copy()
        other[2] += 3
        self.assertIsNone(LK.fit(self.PTS, other))

    def test_different_counts(self):
        self.assertIsNone(LK.fit(self.PTS, self.PTS[:3]))

    def test_aligned_points(self):
        src = np.array([[0, 0], [10, 0]], dtype=float)
        a = LK.fit(src, np.array([[1, 1], [1, 21]], dtype=float))
        self.assertAlmostEqual(a.apply((5, 0))[1], 11.0)
        self.assertAlmostEqual(a.apply((5, 0))[0], 1.0)

    def test_aligned_points_stay_a_similarity(self):
        src = np.array([[0, 0], [10, 0]], dtype=float)
        a = LK.fit(src, np.array([[1, 1], [1, 21]], dtype=float))
        self.assertAlmostEqual(a.apply((0, 5))[0], -9.0)
        self.assertAlmostEqual(a.apply((0, 5))[1], 1.0)

    def test_points_of_a_group_and_text(self):
        g = Group(children=[square(), Text(text='H', font='VD Trait', size=5.0)])
        self.assertGreater(len(LK.points(g)), 8)


class Make(Base):
    def test_copy_is_marked(self):
        c = self.add_copy()
        self.assertTrue(LK.is_copy(c))
        self.assertEqual(c.extra[LK.KEY]['master'], self.master.id)
        self.assertNotEqual(c.id, self.master.id)
        self.assertFalse(LK.is_copy(self.master))
        self.assertEqual(c.bbox()[0], 50.0)

    def test_copy_of_a_copy_points_to_the_original(self):
        c = self.add_copy()
        self.assertEqual(LK.make(c).extra[LK.KEY]['master'], self.master.id)

    def test_unlink(self):
        c = self.add_copy()
        self.assertTrue(LK.unlink(c))
        self.assertFalse(LK.is_copy(c))
        self.assertFalse(LK.unlink(c))

    def test_extra_of_the_original_stays_free(self):
        c = self.add_copy()
        self.assertNotIn(LK.KEY, self.master.extra)
        self.assertIsNot(c.extra, self.master.extra)


class Sync(Base):
    def test_no_copy_nothing_happens(self):
        self.assertEqual(LK.sync(self.doc, self.cache), [])

    def test_shape_change_reaches_the_copy(self):
        c = self.add_copy()
        self.edit_master(Path([circle((5, 5), 5)]))
        now = self.current(c)
        self.assertAlmostEqual(center(now)[0], 55.0)
        self.assertEqual(len(now.path.contours[0].segments), len(self.master.path.contours[0].segments))
        self.assertTrue(LK.is_copy(now))
        self.assertEqual(now.id, c.id)

    def test_every_copy_follows(self):
        a, b = self.add_copy(50), self.add_copy(100)
        done = self.edit_master(Path([circle((5, 5), 5)]))
        self.assertEqual(len(done), 2)
        self.assertAlmostEqual(center(self.current(a))[0], 55.0)
        self.assertAlmostEqual(center(self.current(b))[0], 105.0)

    def test_moving_the_original_leaves_the_copy(self):
        c = self.add_copy()
        done = self.edit_master(self.master.path.transformed(Affine.translation(30, 30)))
        self.assertEqual(done, [])
        self.assertIs(self.current(c), c)

    def test_moved_copy_keeps_its_place(self):
        c = self.add_copy()
        LK.prime(self.doc, self.cache)
        moved = c.transformed(Affine.translation(200, 80))
        self.layer.items[self.layer.items.index(c)] = moved
        LK.sync(self.doc, self.cache)
        self.edit_master(Path([circle((5, 5), 5)]))
        self.assertAlmostEqual(center(self.current(c))[0], 255.0)
        self.assertAlmostEqual(center(self.current(c))[1], 85.0)

    def test_scaled_copy_stays_scaled(self):
        c = self.add_copy()
        LK.prime(self.doc, self.cache)
        here = center(c)
        big = c.transformed(Affine.translation(*here) @ Affine.scaling(3.0) @ Affine.translation(-here[0], -here[1]))
        self.layer.items[self.layer.items.index(c)] = big
        LK.sync(self.doc, self.cache)
        self.edit_master(Path([circle((5, 5), 10)]))
        self.assertAlmostEqual(size(self.current(c))[0], 60.0, places=4)

    def test_rotated_copy_stays_rotated(self):
        c = self.add_copy()
        LK.prime(self.doc, self.cache)
        here = center(c)
        turned = c.transformed(Affine.translation(*here) @ Affine.rotation(90) @ Affine.translation(-here[0], -here[1]))
        self.layer.items[self.layer.items.index(c)] = turned
        LK.sync(self.doc, self.cache)
        self.edit_master(Path([rect(0, 0, 40, 10)]))
        w, h = size(self.current(c))
        self.assertAlmostEqual(w, 10.0, places=4)
        self.assertAlmostEqual(h, 40.0, places=4)

    def test_scaling_the_original_scales_the_copy(self):
        c = self.add_copy()
        m = Affine.translation(5, 5) @ Affine.scaling(2.0) @ Affine.translation(-5, -5)
        self.edit_master(self.master.path.transformed(m))
        now = self.current(c)
        self.assertAlmostEqual(size(now)[0], 20.0)
        self.assertAlmostEqual(center(now)[0], 55.0)

    def test_nodes_edited_on_the_copy_detach_it(self):
        c = self.add_copy()
        LK.prime(self.doc, self.cache)
        changed = Shape(id=c.id, path=Path([polyline([(0, 0), (9, 0), (9, 9)], True)]), extra=dict(c.extra))
        self.layer.items[self.layer.items.index(c)] = changed
        self.edit_master(Path([circle((5, 5), 5)]))
        now = self.current(c)
        self.assertFalse(LK.is_copy(now))
        self.assertEqual(len(now.path.contours[0].segments), 3)

    def test_deleted_original_frees_the_copies(self):
        c = self.add_copy()
        LK.prime(self.doc, self.cache)
        self.layer.items.remove(self.master)
        LK.sync(self.doc, self.cache)
        self.assertFalse(LK.is_copy(c))

    def test_tool_follows_unless_the_copy_has_its_own(self):
        a, b = self.add_copy(50), self.add_copy(100)
        b.tool = 7
        LK.prime(self.doc, self.cache)
        self.master.tool = 3
        LK.sync(self.doc, self.cache)
        self.assertEqual(a.tool, 3)
        self.assertEqual(b.tool, 7)

    def test_tool_kept_when_the_shape_changes(self):
        a = self.add_copy(50)
        a.tool = 7
        self.edit_master(Path([circle((5, 5), 5)]))
        self.assertEqual(self.current(a).tool, 7)

    def test_copy_in_another_layer(self):
        other = Layer(name='B')
        self.doc.layers.append(other)
        c = LK.make(self.master, 50, 0)
        other.items.append(c)
        self.edit_master(Path([circle((5, 5), 5)]))
        self.assertEqual(len(other.items), 1)
        self.assertEqual(len(other.items[0].path.contours[0].segments), len(self.master.path.contours[0].segments))
        self.assertEqual(other.items[0].id, c.id)

    def test_first_look_changes_nothing(self):
        c = self.add_copy()
        self.assertEqual(LK.sync(self.doc, self.cache), [])
        self.assertIs(self.current(c), c)

    def test_text_change_reaches_the_copy(self):
        t = Text(text='AB', font='VD Trait', size=5.0)
        from vectordrive.core.text import outline_for
        t.outline = outline_for(t)
        self.layer.items = [t]
        c = LK.make(t, 50, 0)
        self.layer.items.append(c)
        LK.prime(self.doc, self.cache)
        t2 = t.transformed(Affine.translation(0, 0))
        t2.id = t.id
        t2.text = 'ABCD'
        t2.outline = outline_for(t2)
        self.layer.items[0] = t2
        LK.sync(self.doc, self.cache)
        now = next(i for i in self.layer.items if i.id == c.id)
        self.assertEqual(now.text, 'ABCD')
        self.assertGreater(size(now)[0], size(c)[0])

    def test_group_copy(self):
        g = Group(children=[square(), square(20)])
        self.layer.items = [g]
        c = LK.make(g, 100, 0)
        self.layer.items.append(c)
        LK.prime(self.doc, self.cache)
        g2 = Group(id=g.id, children=[square(), square(20), square(40)])
        self.layer.items[0] = g2
        LK.sync(self.doc, self.cache)
        now = next(i for i in self.layer.items if i.id == c.id)
        self.assertEqual(len(now.children), 3)
        self.assertNotEqual(now.children[0].id, g2.children[0].id)


class Together(Base):
    """L'original et ses copies transformés par la même opération."""

    def _both(self, c, m):
        LK.prime(self.doc, self.cache)
        i = self.layer.items.index(self.master)
        self.master = self.master.transformed(m)
        self.layer.items[i] = self.master
        self.layer.items[self.layer.items.index(c)] = c.transformed(m)
        return LK.sync(self.doc, self.cache)

    def test_scaled_together_not_twice(self):
        c = self.add_copy()
        self.assertEqual(self._both(c, Affine.scaling(2.0)), [])
        self.assertAlmostEqual(size(self.current(c))[0], 20.0)
        self.assertTrue(LK.is_copy(self.current(c)))

    def test_rotated_together_not_twice(self):
        c = self.add_copy()
        self.assertEqual(self._both(c, Affine.rotation(45)), [])
        self.assertAlmostEqual(size(self.current(c))[0], 10.0 * math.sqrt(2), places=4)

    def test_moved_together(self):
        c = self.add_copy()
        self.assertEqual(self._both(c, Affine.translation(9, 9)), [])
        self.assertAlmostEqual(self.current(c).bbox()[0], 59.0)

    def test_link_still_works_afterwards(self):
        c = self.add_copy()
        self._both(c, Affine.scaling(2.0))
        self.edit_master(Path([circle((10, 10), 10)]))
        now = self.current(c)
        self.assertAlmostEqual(size(now)[0], 20.0, places=4)
        self.assertEqual(len(LK.points(now)), len(LK.points(self.master)))


class Nodes(Base):
    def test_unchanged_nodes_stay_on_the_copy(self):
        self.master = Shape(id=self.master.id, path=Path([polyline([(0, 0), (10, 0), (10, 10), (0, 10)], True)]))
        self.layer.items = [self.master]
        c = self.add_copy(50, 0)
        LK.prime(self.doc, self.cache)
        self.edit_master(Path([polyline([(0, 0), (30, 0), (10, 10), (0, 10)], True)]))
        now = self.current(c)
        self.assertAlmostEqual(now.bbox()[0], 50.0)
        self.assertAlmostEqual(now.bbox()[2], 80.0)

    def test_copy_edited_is_freed_at_once(self):
        c = self.add_copy()
        LK.sync(self.doc, self.cache)
        LK.prime(self.doc, self.cache)
        i = self.layer.items.index(c)
        self.layer.items[i] = Shape(id=c.id, path=Path([polyline([(0, 0), (9, 0), (9, 9)], True)]), extra=dict(c.extra))
        LK.sync(self.doc, self.cache)
        self.assertFalse(LK.is_copy(self.layer.items[i]))

    def test_moved_copy_is_not_freed(self):
        c = self.add_copy()
        LK.sync(self.doc, self.cache)
        i = self.layer.items.index(c)
        self.layer.items[i] = c.transformed(Affine.translation(7, 7))
        LK.sync(self.doc, self.cache)
        self.assertTrue(LK.is_copy(self.layer.items[i]))


class InGroups(Base):
    def test_original_in_a_group_stays_tracked(self):
        c = self.add_copy()
        LK.sync(self.doc, self.cache)
        g = Group(children=[self.master, square(200)])
        self.layer.items[0] = g
        LK.sync(self.doc, self.cache)
        self.assertTrue(LK.is_copy(self.current(c)))
        g.children[0] = Shape(id=self.master.id, path=Path([circle((5, 5), 5)]))
        LK.sync(self.doc, self.cache)
        self.assertEqual(len(LK.points(self.current(c))), len(LK.points(g.children[0])))

    def test_copy_in_a_group_follows(self):
        c = self.add_copy()
        LK.sync(self.doc, self.cache)
        g = Group(children=[c, square(200)])
        self.layer.items[1] = g
        LK.sync(self.doc, self.cache)
        self.edit_master(Path([circle((5, 5), 5)]))
        self.assertEqual(g.children[0].id, c.id)
        self.assertIsNot(g.children[0], c)
        self.assertEqual(len(LK.points(g.children[0])), len(LK.points(self.master)))

    def test_inside_of_a_group_copy_is_left_alone(self):
        g = Group(children=[square(), square(20)])
        self.layer.items = [g]
        c = LK.make(g, 100, 0)
        self.layer.items.append(c)
        linked, every = LK._scan(self.doc)
        self.assertEqual(list(linked), [g.id])
        self.assertNotIn(c.children[0].id, every)


class Commands(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.close()

    def setUp(self):
        doc = self.win.canvas.doc
        doc.layers = [Layer(name='Plan 1')]
        doc.active = doc.layers[0].id
        self.win._links_cache = {}
        self.master = square()
        doc.layers[0].items = [self.master]
        self.win.canvas.select([self.master])

    @property
    def items(self):
        return self.win.canvas.doc.layers[0].items

    def _edit_master(self, path):
        self.win.push_undo()
        i = next(k for k, it in enumerate(self.items) if it.id == self.master.id)
        new = Shape(id=self.master.id, path=path, extra=dict(self.items[i].extra))
        self.items[i] = new
        self.win._on_doc_changed()
        return new

    def test_ribbon(self):
        for k in ('link_copy', 'link_cut', 'link_master'):
            found = [b for i in range(self.win.ribbon.count()) for g in self.win.ribbon.page(i).groups() for b in g.buttons()
                     if b.defaultAction() is self.win.A[k]]
            self.assertEqual(len(found), 1, k)

    def test_shortcut(self):
        self.assertEqual(self.win._default_shortcuts['link_copy'], ['Alt+D'])   # le jeu TE du poste peut la reprendre

    def test_copy_selected(self):
        out = self.win.link_copy()
        self.assertEqual(len(out), 1)
        self.assertEqual(self.win.canvas.selection, out)
        self.assertEqual(len(self.items), 2)
        self.assertTrue(LK.is_copy(out[0]))

    def test_nothing_selected(self):
        self.win.canvas.select([])
        self.assertEqual(self.win.link_copy(), [])
        self.assertEqual(self.win.link_cut(), 0)
        self.assertIsNone(self.win.link_select_master())

    def test_editing_the_original_updates_the_copy(self):
        c = self.win.link_copy(50, 0)[0]
        self._edit_master(Path([circle((5, 5), 5)]))
        now = next(i for i in self.items if i.id == c.id)
        self.assertAlmostEqual(center(now)[0], 55.0)
        self.assertEqual(len(LK.points(now)), len(LK.points(next(i for i in self.items if i.id == self.master.id))))
        self.assertIsNot(now, c)

    def test_selection_follows_the_replacement(self):
        c = self.win.link_copy(50, 0)[0]
        self.win.canvas.select([c])
        self._edit_master(Path([circle((5, 5), 5)]))
        now = next(i for i in self.items if i.id == c.id)
        self.assertEqual(self.win.canvas.selection, [now])

    def test_undo_brings_both_back(self):
        c = self.win.link_copy(50, 0)[0]
        self._edit_master(self.master.path.transformed(Affine.scaling(3.0)))
        self.assertAlmostEqual(size(next(i for i in self.items if i.id == c.id))[0], 30.0)
        self.win.undo()
        self.assertAlmostEqual(size(next(i for i in self.items if i.id == c.id))[0], 10.0)
        self.assertAlmostEqual(size(next(i for i in self.items if i.id == self.master.id))[0], 10.0)

    def test_edit_after_undo(self):
        c = self.win.link_copy(50, 0)[0]
        self._edit_master(self.master.path.transformed(Affine.scaling(3.0)))
        self.win.undo()
        self._edit_master(self.master.path.transformed(Affine.scaling(2.0)))
        now = next(i for i in self.items if i.id == c.id)
        self.assertAlmostEqual(size(now)[0], 20.0)
        self.assertAlmostEqual(center(now)[0], 55.0)

    def test_redo(self):
        c = self.win.link_copy(50, 0)[0]
        self._edit_master(self.master.path.transformed(Affine.scaling(3.0)))
        self.win.undo()
        self.win.redo()
        self.assertAlmostEqual(size(next(i for i in self.items if i.id == c.id))[0], 30.0)

    def test_unlink_stops_following(self):
        c = self.win.link_copy(50, 0)[0]
        self.assertEqual(self.win.link_cut(), 1)
        self.assertFalse(LK.is_copy(c))
        self._edit_master(Path([circle((5, 5), 5)]))
        self.assertAlmostEqual(size(next(i for i in self.items if i.id == c.id))[0], 10.0)

    def test_unlink_undo(self):
        c = self.win.link_copy(50, 0)[0]
        self.win.link_cut()
        self.win.undo()
        self.assertTrue(LK.is_copy(next(i for i in self.items if i.id == c.id)))

    def test_select_master(self):
        self.win.link_copy(50, 0)
        self.assertEqual(self.win.link_select_master(), [self.master])
        self.assertEqual(self.win.canvas.selection, [self.master])

    def test_saved_and_reopened(self):
        from vectordrive.io import native, registry
        c = self.win.link_copy(50, 0)[0]
        p = os.path.join(tempfile.mkdtemp(), 'l.vdz')
        registry.save_document(self.win.canvas.doc, p)
        back = native.read(p)
        self.assertEqual(back.layers[0].items[1].extra[LK.KEY]['master'], self.master.id)
        self.assertEqual(back.layers[0].items[1].id, c.id)
        self.assertEqual(back.layers[0].items[0].id, self.master.id)

    def test_first_edit_after_opening_a_file(self):
        from vectordrive.io import native, registry
        c = self.win.link_copy(50, 0)[0]
        p = os.path.join(tempfile.mkdtemp(), 'l.vdz')
        registry.save_document(self.win.canvas.doc, p)
        back = native.read(p)
        self.win.canvas.doc.layers = back.layers
        self.win._links_cache = {}
        self._edit_master(Path([circle((5, 5), 5)]))
        now = next(i for i in self.items if i.id == c.id)
        self.assertLess(abs(size(now)[0] - 10.0), 1e-6)
        self.assertEqual(len(LK.points(now)), len(LK.points(next(i for i in self.items if i.id == self.master.id))))
        self.assertNotEqual(len(LK.points(now)), len(LK.points(c)))

    def test_written_as_ordinary_object(self):
        from vectordrive.io import registry, vnd
        self.win.link_copy(50, 0)
        p = os.path.join(tempfile.mkdtemp(), 'l.vnd')
        registry.save_document(self.win.canvas.doc, p)
        self.assertEqual(sum(len(L.items) for L in vnd.read(p).layers), 2)

    def test_drawing_without_copy_is_not_slowed(self):
        cache = self.win._links_state()
        self.win._on_doc_changed()
        self.assertEqual(cache, {})


if __name__ == '__main__':
    unittest.main()
