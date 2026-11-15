"""Round 852 : la 2D et la 3D par un seul bouton ; le bouton Animation ; un fichier 3D importé garde sa 3D."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton, QToolButton

from vectordrive.core import geom
from vectordrive.core import placement3d as P3
from vectordrive.core.document import Document, Layer, Plate, Shape
from vectordrive.io import model3d, registry
from vectordrive.ui.main_window import MainWindow


def box_tris(x0, y0, z0, x1, y1, z1):
    v = np.array([[x, y, z] for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)], dtype=float)
    quads = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    t = []
    for a, b, c, d in quads:
        t += [v[[a, b, c]], v[[a, c, d]]]
    return np.array(t)


def model_of(*parts):
    tris = np.concatenate(parts)
    body = np.concatenate([np.full(len(p), k) for k, p in enumerate(parts)])
    return model3d.Model3D(tris, np.ones((len(tris), 3)), np.zeros((0, 2, 3)), body_of=body,
                           body_names=[f'P{k}' for k in range(len(parts))])


def write_stl(path, tris):
    lines = ['solid piece']
    for t in tris:
        lines += ['facet normal 0 0 1', 'outer loop'] + [f'vertex {p[0]} {p[1]} {p[2]}' for p in t] + ['endloop', 'endfacet']
    lines.append('endsolid piece')
    pathlib.Path(path).write_text('\n'.join(lines), encoding='ascii')


class Base(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.win = MainWindow()
        cls.win.resize(1400, 900)
        cls.dir = pathlib.Path(tempfile.mkdtemp())

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.close()
        cls.win.deleteLater()

    def setUp(self):
        self.win.set_view_mode('2d')
        self.doc = self.win.canvas.doc
        self.doc.layers[:] = [Layer(name='Plan 1')]
        self.doc.active = self.doc.layers[0].id
        self.doc.plate = Plate(width=200.0, height=100.0)
        self.doc.source_path = ''
        self.doc.source_format = ''
        self.doc.extra.pop(model3d.SOURCE_KEY, None)
        self.doc.extra.pop(P3.KEY, None)
        self.win._undo.clear()

    def stl(self, name='piece.stl', tris=None):
        p = self.dir / name
        write_stl(p, box_tris(0, 0, 0, 40, 20, 10) if tris is None else tris)
        return str(p)

    def ribbon_buttons(self):
        r = self.win.ribbon
        for i in range(r.count()):
            p = r.page(i)
            if p is not None:
                for g in p.groups():
                    for b in g.buttons():
                        yield r.tabText(i), b.defaultAction()


class TestOneButton(Base):

    def test_the_button_goes_there_and_back(self):
        t = self.win.A['view_toggle']
        self.assertEqual(self.win.view_mode(), '2d')
        self.assertEqual(t.property('vd_mode'), '2d')
        t.trigger()
        self.assertEqual(self.win.view_mode(), '3d')
        self.assertEqual(t.property('vd_mode'), '3d')
        t.trigger()
        self.assertEqual(self.win.view_mode(), '2d')
        self.assertEqual(t.property('vd_mode'), '2d')

    def test_the_icon_follows_and_survives_a_theme_change(self):
        t = self.win.A['view_toggle']
        t.trigger()
        self.assertEqual(t.property('vd_icon'), 'view_2d')
        t.trigger()
        self.assertEqual(t.property('vd_icon'), 'view_3d')

    def test_the_other_buttons_are_gone(self):
        A = self.win.A
        shown = [a for _t, a in self.ribbon_buttons()]
        self.assertNotIn(A['view_2d'], shown)
        self.assertNotIn(A['view_3d'], shown)
        self.assertNotIn(A['view_toggle'], shown)                      # round 903 : dans la rangée des onglets seulement
        self.assertIs(self.win.ribbon.view_button.defaultAction(), A['view_toggle'])

    def test_no_back_button_on_the_3d_view(self):
        self.win.set_view_mode('3d')
        texts = [b.text() for b in self.win.panel3d.findChildren(QPushButton)]
        self.assertNotIn('Retour en 2D', texts)
        self.assertFalse(hasattr(self.win.panel3d, 'closed'))

    def test_always_in_sight(self):
        b = self.win.ribbon.view_button
        self.assertIsInstance(b, QToolButton)
        self.assertIs(b.defaultAction(), self.win.A['view_toggle'])
        r = self.win.ribbon
        self.assertIs(b.parent(), r.cornerWidget(Qt.Corner.TopRightCorner))
        at = r.currentIndex()
        for i in range(r.count()):
            r.setCurrentIndex(i)
            self.assertFalse(b.isHidden())
        r.setCurrentIndex(at)

    def test_the_view_keys_still_work_and_follow(self):
        A = self.win.A
        self.assertEqual(A['view_3d'].shortcut().toString(), 'Ctrl+6')
        self.assertEqual(A['view_2d'].shortcut().toString(), 'Ctrl+1')
        A['view_3d'].trigger()
        self.assertEqual(self.win.view_mode(), '3d')
        self.assertEqual(A['view_toggle'].property('vd_mode'), '3d')
        A['view_2d'].trigger()
        self.assertEqual(A['view_toggle'].property('vd_mode'), '2d')

    def test_a_chosen_view_follows_too(self):
        self.win.A['view_iso'].trigger()
        self.assertEqual(self.win.A['view_toggle'].property('vd_mode'), '3d')


class TestAnimation(Base):

    def panel(self, model):
        self.win.set_view_mode('3d')
        p = self.win.panel3d
        p.model = model
        p.view.set_model(model)
        self.addCleanup(self.reset, p)
        return p

    def reset(self, p):
        if p._anim_dlg is not None:
            p._anim_dlg.close()
            p._anim_dlg = None
        p.model = None
        p.view.set_model(None)
        p.stale = True

    def two(self):
        return model_of(box_tris(0, 0, 0, 10, 10, 5), box_tris(0, 0, 5, 10, 10, 10))

    def test_a_click_starts_it(self):
        p = self.panel(self.two())
        dlg = p.animate()
        self.assertIsNotNone(dlg)
        self.assertTrue(dlg.isVisible())
        self.assertTrue(dlg.play.isChecked())
        self.assertTrue(dlg.timer.isActive())

    def test_a_second_click_keeps_the_same_window(self):
        p = self.panel(self.two())
        self.assertIs(p.animate(), p.animate())

    def test_closing_puts_the_part_back(self):
        p = self.panel(self.two())
        dlg = p.animate()
        dlg.set_progress(1.0)
        self.assertTrue(p.view.body_moves)
        dlg.close()
        self.assertEqual(p.view.body_moves, {})
        self.assertFalse(dlg.timer.isActive())

    def test_after_closing_a_click_opens_it_again(self):
        p = self.panel(self.two())
        first = p.animate()
        first.close()
        again = p.animate()
        self.assertIsNot(first, again)
        self.assertTrue(again.isVisible())

    def test_another_part_opens_another_window(self):
        p = self.panel(self.two())
        first = p.animate()
        other = self.two()
        p.model = other
        p.view.set_model(other)
        self.assertIsNot(p.animate(), first)
        self.assertFalse(first.isVisible())

    def test_one_body_does_not_animate(self):
        p = self.panel(model_of(box_tris(0, 0, 0, 10, 10, 5)))
        self.assertIsNone(p.animate())

    def test_nothing_movable_opens_without_playing(self):
        p = self.panel(model_of(box_tris(0, 0, 0, 10, 10, 5), box_tris(100, 100, 100, 110, 110, 105)))
        dlg = p.animate()
        self.assertIsNotNone(dlg)
        self.assertEqual(dlg.play.isChecked(), bool(dlg.active()))

    def test_the_button_on_the_view(self):
        self.win.set_view_mode('3d')
        texts = [b.text() for b in self.win.panel3d.findChildren(QPushButton)]
        self.assertIn('Animation', texts)

    def test_the_command_goes_to_3d_and_says_why(self):
        self.assertIsNone(self.win.animate_parts())
        self.assertEqual(self.win.view_mode(), '3d')
        self.assertIn('plusieurs corps', self.win.statusBar().currentMessage())

    def test_in_the_ribbon(self):
        self.assertIn(self.win.A['anim_3d'], [a for _t, a in self.ribbon_buttons()])


class TestImportKeepsThe3D(Base):

    def imported(self, path):
        with mock.patch('vectordrive.ui.main_window.QFileDialog.getOpenFileName', return_value=(path, '')):
            self.win.import_dialog()

    def test_it_is_the_part_of_the_drawing(self):
        path = self.stl()
        self.imported(path)
        self.assertEqual(model3d.source_of(self.doc), os.path.abspath(path))

    def test_the_3d_view_shows_it(self):
        self.imported(self.stl())
        self.win.A['view_toggle'].trigger()
        m = self.win.panel3d.view.model
        self.assertIsNotNone(m)
        tris = np.asarray(m.triangles)
        self.assertEqual(len(tris), 12)
        self.assertAlmostEqual(float(tris[:, :, 2].max() - tris[:, :, 2].min()), 10.0, places=4)
        self.win.panel3d.stale = True

    def test_the_top_view_matches_the_part(self):
        self.imported(self.stl())
        self.win.A['view_toggle'].trigger()
        tris = np.asarray(self.win.panel3d.view.model.triangles)
        boxes = [it.bbox() for L in self.doc.layers for it in L.items]
        self.assertTrue(boxes)
        self.assertAlmostEqual(min(b[0] for b in boxes), float(tris[:, :, 0].min()), places=3)
        self.assertAlmostEqual(max(b[2] for b in boxes), float(tris[:, :, 0].max()), places=3)
        self.assertAlmostEqual(max(b[3] for b in boxes), float(tris[:, :, 1].max()), places=3)
        self.win.panel3d.stale = True

    def test_dropping_the_file_too(self):
        path = self.stl()
        self.win._file_dropped(path, 0.0, 0.0)
        self.assertEqual(model3d.source_of(self.doc), os.path.abspath(path))

    def test_undo_takes_the_part_away(self):
        self.imported(self.stl())
        self.win.undo()
        self.assertIsNone(model3d.source_of(self.win.canvas.doc))

    def test_a_flat_file_changes_nothing(self):
        d = Document()
        d.layers = [Layer(name='A', items=[Shape(path=geom.Path([geom.rect(0, 0, 5, 5)]))])]
        p = self.dir / 'plat.svg'
        registry.save_document(d, p)
        self.imported(str(p))
        self.assertIsNone(model3d.source_of(self.doc))
        self.assertNotIn(model3d.SOURCE_KEY, self.doc.extra)

    def test_a_second_part_is_refused_and_it_says_so(self):
        first = self.stl('a.stl')
        second = self.stl('b.stl', box_tris(0, 0, 0, 5, 5, 5))
        self.imported(first)
        self.imported(second)
        self.assertEqual(model3d.source_of(self.doc), os.path.abspath(first))
        msg = self.win.statusBar().currentMessage()
        self.assertIn('a.stl', msg)
        self.assertIn('b.stl', msg)

    def test_the_same_file_twice_says_nothing(self):
        path = self.stl('c.stl')
        self.imported(path)
        self.win.statusBar().clearMessage()
        self.imported(path)
        self.assertNotIn('garde sa pièce', self.win.statusBar().currentMessage())

    def test_an_opened_part_stays_the_part(self):
        first = self.stl('d.stl')
        self.doc.source_path, self.doc.source_format = first, 'stl'
        self.imported(self.stl('e.stl', box_tris(0, 0, 0, 5, 5, 5)))
        self.assertEqual(model3d.source_of(self.doc), first)

    def test_its_placement_comes_with_it(self):
        other = Document(source_path=self.stl(), source_format='stl')
        pl = P3.to_dict(P3.Placement('+X', 90.0))
        other.extra[P3.KEY] = pl
        self.win._adopt_part3d(other)
        self.assertEqual(self.doc.extra[P3.KEY], pl)
        self.assertIsNot(self.doc.extra[P3.KEY], pl)

    def test_a_saved_drawing_finds_it_again(self):
        path = self.stl()
        self.imported(path)
        saved = self.dir / 'dessin.vdz'
        registry.save_document(self.doc, saved)
        again = registry.open_document(str(saved))
        self.assertEqual(os.path.normcase(model3d.source_of(again)), os.path.normcase(os.path.abspath(path)))

    def test_a_saved_drawing_imported_brings_its_part(self):
        d = Document()
        d.layers = [Layer(name='A', items=[Shape(path=geom.Path([geom.rect(0, 0, 5, 5)]))])]
        d.extra[model3d.SOURCE_KEY] = self.stl('f.stl')
        self.win._adopt_part3d(d)
        self.assertEqual(os.path.normcase(model3d.source_of(self.doc)),
                         os.path.normcase(os.path.abspath(d.extra[model3d.SOURCE_KEY])))


if __name__ == '__main__':
    unittest.main()
