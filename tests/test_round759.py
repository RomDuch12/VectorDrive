"""Round 759 : bruts des ensembles : définis sur un objet ou un groupe, dessinés et cotés à part sur le BAT ; ni gravés,
ni usinés, ni exportés."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import brut as BR
from vectordrive.core import geom
from vectordrive.core.document import Document, Group, Layer, Plate, Shape
from vectordrive.core.geom import Affine
from vectordrive.io import native, proof

app = QApplication.instance() or QApplication([])


def square(x=20.0, y=20.0, side=20.0):
    return Shape(path=geom.Path([geom.rect(x, y, side, side)]))


def doc_of(*items, plate=None):
    d = Document()
    d.plate = plate
    d.layers = [Layer(name='A', items=list(items))]
    return d


def spoken(doc, inf, items=None):
    """Tous les textes écrits sur la page."""
    seen = []
    real = proof.text.layout

    def spy(s, *a, **kw):
        seen.append(s.replace(',', '.'))
        return real(s, *a, **kw)
    with mock.patch.object(proof.text, 'layout', spy):
        prims = proof.build(doc, inf, items)[0]
    return seen, prims


class TestBrut(unittest.TestCase):
    def test_make_centered(self):
        s = square()
        b = BR.make(s, 40, 30)
        self.assertEqual(BR.bbox(b), (10.0, 15.0, 50.0, 45.0))
        self.assertEqual(BR.size(b), (40.0, 30.0))

    def test_offset(self):
        s = square()
        b = BR.make(s, 40, 30, dx=5, dy=-2)
        self.assertEqual(BR.center_offset(s, b), (5.0, -2.0))

    def test_of(self):
        s = square()
        self.assertIsNone(BR.of(s))
        BR.make(s, 40, 30)
        self.assertIsNotNone(BR.of(s))
        s.extra['brut'] = {'corners': [[0, 0]]}
        self.assertIsNone(BR.of(s))                                           # abîmé : ignoré
        s.extra['brut'] = 'x'
        self.assertIsNone(BR.of(s))

    def test_remove(self):
        s = square()
        BR.make(s, 40, 30)
        self.assertTrue(BR.remove(s))
        self.assertFalse(BR.remove(s))

    def test_refused(self):
        with self.assertRaises(ValueError):
            BR.make(square(), 0, 30)
        with self.assertRaises(ValueError):
            BR.make(Group(children=[]), 10, 10)

    def test_unknown_cotes(self):
        self.assertEqual(BR.make(square(), 40, 30, cotes='?')['cotes'], 'les_deux')

    def test_walk_nested(self):
        a, b = square(), square(50)
        BR.make(a, 30, 30)
        g = Group(children=[a, b])
        BR.make(g, 100, 60)
        hidden = square(90)
        BR.make(hidden, 30, 30)
        hidden.visible = False
        self.assertEqual([it for it, _b in BR.walk([g, hidden])], [g, a])


class TestFollows(unittest.TestCase):
    def test_translation(self):
        s = square()
        BR.make(s, 40, 30)
        t = s.transformed(Affine.translation(100, 200))
        self.assertEqual(BR.bbox(BR.of(t))[0], 110.0)
        self.assertEqual(BR.bbox(BR.of(s))[0], 10.0)                          # l'original n'a pas bougé

    def test_rotation_keeps_size(self):
        s = square()
        BR.make(s, 40, 30)
        t = s.transformed(Affine.rotation(30))
        w, h = BR.size(BR.of(t))
        self.assertAlmostEqual(w, 40)
        self.assertAlmostEqual(h, 30)

    def test_scale(self):
        s = square()
        BR.make(s, 40, 30)
        self.assertAlmostEqual(BR.size(BR.of(s.transformed(Affine.scaling(2))))[0], 80)

    def test_group(self):
        g = Group(children=[square()])
        BR.make(g, 40, 30)
        self.assertEqual(BR.bbox(BR.of(g.transformed(Affine.translation(1, 0))))[0], 11.0)

    def test_clone_keeps_it(self):
        s = square()
        BR.make(s, 40, 30)
        self.assertIsNotNone(BR.of(s.clone()))

    def test_saved(self):
        s = square()
        BR.make(s, 40, 30, thickness=3, name='Plaque', cotes='brut')
        got = BR.of(native.from_dict(native.to_dict(doc_of(s))).layers[0].items[0])
        self.assertEqual((got['thickness'], got['name'], got['cotes']), (3, 'Plaque', 'brut'))
        self.assertEqual(BR.size(got), (40.0, 30.0))


class TestNotCut(unittest.TestCase):
    def test_not_in_the_svg_or_vnd(self):
        from vectordrive.io import svg, vnd, vnd_write
        s = square()
        BR.make(s, 40, 30)
        self.assertEqual(svg.to_string(doc_of(s), include_plate=False).count('<path'),
                         svg.to_string(doc_of(square()), include_plate=False).count('<path'))
        p = os.path.join(tempfile.mkdtemp(), 'a.vnd')
        vnd_write.write(doc_of(s), p)
        leaves = [x for L in vnd.read(p).layers for x in L.items]
        self.assertEqual(len(leaves), 1)
        self.assertAlmostEqual(leaves[0].bbox()[0], 20, places=6)

    def test_not_machined(self):
        from vectordrive.cam import strategies as S
        from vectordrive.cam.model import CamSetup, CamTool, Operation
        s = square()
        BR.make(s, 40, 30)
        d = doc_of(s)
        setup = CamSetup(tools=[CamTool(id='f', name='F', kind='fraise', diameter=2.0)])
        tp = S.compute(d, setup, Operation(name='c', kind='contour', tool_id='f', depth=1.0))
        xs = [m.x for m in tp.moves]
        self.assertGreaterEqual(min(xs), 17.0)                                # pas à 10, le bord du brut

    def test_bbox_unchanged(self):
        s = square()
        BR.make(s, 40, 30)
        self.assertEqual(tuple(s.bbox()), (20.0, 20.0, 40.0, 40.0))


class TestPage(unittest.TestCase):
    def info(self, **k):
        base = dict(title_block=False, legend=False, prices=False, scale_mode='reelle')
        base.update(k)
        return proof.ProofInfo(**base)

    def outlines(self, prims):
        return [p for p in prims if p.color == proof.BRUT_COLOR and p.width == 0.3]

    def test_frame_includes_the_brut(self):
        s = square()
        BR.make(s, 100, 80)
        g = proof._geometry(doc_of(s), self.info())
        self.assertEqual((g['FW'], g['FH']), (100.0, 80.0))

    def test_outline_drawn_at_scale(self):
        s = square()
        BR.make(s, 100, 80)
        got = self.outlines(proof.build(doc_of(s), self.info())[0])
        self.assertEqual(len(got), 1)
        bb = got[0].path.bbox()
        self.assertAlmostEqual(bb[2] - bb[0], 100)
        self.assertAlmostEqual(bb[3] - bb[1], 80)

    def test_dims_apart(self):
        s = square()
        BR.make(s, 100.5, 80)
        seen, _p = spoken(doc_of(s), self.info())
        self.assertIn('100.5', seen)                                          # le brut
        self.assertIn('80', seen)
        self.assertIn('20', seen)                                             # l'ensemble lui-même

    def test_only_brut(self):
        s = square()
        BR.make(s, 100, 80, cotes='brut')
        seen, _p = spoken(doc_of(s), self.info())
        self.assertIn('100', seen)
        self.assertNotIn('20', seen)

    def test_only_the_set(self):
        s = square()
        BR.make(s, 100, 80, cotes='ensemble')
        seen, _p = spoken(doc_of(s), self.info())
        self.assertIn('20', seen)
        self.assertNotIn('100', seen)

    def test_no_dims(self):
        s = square()
        BR.make(s, 100, 80, cotes='aucune')
        seen, prims = spoken(doc_of(s), self.info(dims=False))
        self.assertNotIn('100', seen)
        self.assertEqual(len(self.outlines(prims)), 1)                        # dessiné quand même

    def test_name_and_thickness(self):
        s = square()
        BR.make(s, 100, 80, name='Laiton', thickness=3)
        seen, _p = spoken(doc_of(s), self.info())
        self.assertTrue(any(t.startswith('Brut Laiton') and '3' in t for t in seen))

    def test_precision_applies(self):
        s = square()
        BR.make(s, 33.333, 80)
        seen, _p = spoken(doc_of(s), self.info(decimals=1))
        self.assertIn('33.3', seen)

    def test_each_set_has_its_own(self):
        a, b = square(0, 0), square(100, 0, 30)
        BR.make(a, 40, 40)
        BR.make(b, 50, 50)
        seen, prims = spoken(doc_of(a, b), self.info())
        self.assertIn('40', seen)
        self.assertIn('50', seen)
        self.assertEqual(len(self.outlines(prims)), 2)

    def test_overall_dims_dropped(self):
        s = square()
        BR.make(s, 100, 80)
        d = doc_of(s)
        self.assertTrue(proof.unit_dims(d, self.info()))
        s2 = square()
        BR.make(s2, 100, 80, cotes='aucune')
        self.assertFalse(proof.unit_dims(doc_of(s2), self.info()))

    def test_switched_off(self):
        s = square()
        BR.make(s, 100, 80)
        seen, prims = spoken(doc_of(s), self.info(show_bruts=False))
        self.assertEqual(self.outlines(prims), [])
        self.assertNotIn('80', seen)
        self.assertEqual(proof._geometry(doc_of(s), self.info(show_bruts=False))['FW'], 20.0)

    def test_selection_only(self):
        a, b = square(0, 0), square(100, 0)
        BR.make(a, 40, 40)
        BR.make(b, 50, 50)
        seen, prims = spoken(doc_of(a, b), self.info(), items=[b])
        self.assertIn('50', seen)
        self.assertNotIn('40', seen)
        self.assertEqual(len(self.outlines(prims)), 1)

    def test_hidden_layer(self):
        s = square()
        BR.make(s, 100, 80)
        d = doc_of(s)
        d.layers[0].visible = False
        self.assertEqual(proof.bruts_on_page(d, self.info()), [])

    def test_nested(self):
        a = square()
        BR.make(a, 30, 30)
        g = Group(children=[a, square(60)])
        self.assertEqual(len(proof.bruts_on_page(doc_of(g), self.info())), 1)

    def test_rotated_brut_dim(self):
        s = square()
        BR.make(s, 100, 40)
        t = s.transformed(Affine.rotation(30))
        seen, prims = spoken(doc_of(t), self.info())
        self.assertIn('100', seen)
        self.assertIn('40', seen)
        got = self.outlines(prims)[0].path.bbox()
        self.assertGreater(got[3] - got[1], 40)                               # penché

    def test_upside_down_never(self):
        for a in (0, 30, 90, 120, 180, 210, 270, 300):
            s = square()
            BR.make(s, 100, 40)
            spoken(doc_of(s.transformed(Affine.rotation(a))), self.info())    # aucune erreur à aucun angle

    def test_title_block_size(self):
        s = square()
        BR.make(s, 100, 80, thickness=3)
        seen, _p = spoken(doc_of(s), proof.ProofInfo(legend=False, prices=False))
        self.assertTrue(any('100 × 80 mm' in t for t in seen))
        self.assertTrue(any(t.endswith('ép. 3') or 'ép. 3' in t for t in seen))

    def test_theme(self):
        s = square()
        BR.make(s, 100, 80)
        col = proof._rgb('#2e7d32')
        prims = proof.build(doc_of(s), self.info(title_color='#2e7d32', theme_all=True))[0]
        self.assertEqual([p for p in prims if p.width == 0.3 and p.color == col][0].path.bbox()[2] -
                         [p for p in prims if p.width == 0.3 and p.color == col][0].path.bbox()[0], 100)

    def test_pdf(self):
        s = square()
        BR.make(s, 100, 80, name='Laiton', thickness=3)
        p = os.path.join(tempfile.mkdtemp(), 'bat.pdf')
        proof.write(doc_of(s), p, proof.ProofInfo())
        self.assertGreater(os.path.getsize(p), 500)


class TestWindow(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()

    def tearDown(self):
        for t in self.w.docs:
            t.modified = False
        self.w.modified = False
        self.w.close()

    def put(self, *items):
        self.w.canvas.doc.layers[0].items.extend(items)
        self.w.canvas.selection = list(items)
        return items

    def test_nothing_selected(self):
        self.w.canvas.selection = []
        self.assertIsNone(self.w.set_brut(dict(width=10, height=10)))
        self.assertIn('Sélectionnez', self.w.statusBar().currentMessage())

    def test_defaults_from_the_set(self):
        s, = self.put(square())
        self.assertIs(self.w.set_brut({}), s)                                 # 5 mm autour, par défaut
        self.assertEqual(BR.size(BR.of(s)), (30.0, 30.0))

    def test_given(self):
        s, = self.put(square())
        self.w.set_brut(dict(width=100, height=50, dx=5, dy=1, thickness=2, cotes='brut', name='A'))
        b = BR.of(s)
        self.assertEqual(BR.size(b), (100.0, 50.0))
        self.assertEqual((b['cotes'], b['name'], b['thickness']), ('brut', 'A', 2.0))
        self.assertEqual(BR.center_offset(s, b), (5.0, 1.0))

    def test_several_become_a_set(self):
        a, b = self.put(square(), square(60))
        g = self.w.set_brut(dict(width=100, height=50))
        self.assertIsInstance(g, Group)
        self.assertEqual(g.children, [a, b])
        top = self.w.canvas.doc.layers[0].items
        self.assertIs(top[-1], g)
        self.assertNotIn(a, top)
        self.assertEqual(self.w.canvas.selection, [g])

    def test_one_undo(self):
        self.put(square(), square(60))
        n = len(self.w.canvas.doc.layers[0].items)
        self.w.set_brut(dict(width=100, height=50))
        self.w.undo()
        items = self.w.canvas.doc.layers[0].items
        self.assertEqual(len(items), n)
        self.assertFalse(any(isinstance(x, Group) for x in items))

    def test_remove(self):
        s, = self.put(square())
        self.w.set_brut(dict(width=100, height=50))
        self.assertIs(self.w.set_brut(dict(remove=True)), s)
        self.assertIsNone(BR.of(s))
        self.assertIsNone(self.w.set_brut(dict(remove=True)))

    def test_edit_starts_from_current(self):
        s, = self.put(square())
        self.w.set_brut(dict(width=100, height=50, dx=3, name='N', thickness=4))
        self.w.set_brut({})
        b = BR.of(s)
        self.assertEqual(BR.size(b), (100.0, 50.0))
        self.assertEqual((b['name'], b['thickness']), ('N', 4.0))

    def test_zero_refused(self):
        s, = self.put(square())
        self.assertIsNone(self.w.set_brut(dict(width=0, height=50)))
        self.assertIsNone(BR.of(s))

    def test_too_small_warned(self):
        self.put(square())
        self.w.set_brut(dict(width=5, height=5))
        self.assertIn('plus petit', self.w.statusBar().currentMessage())

    def test_moves_with_the_selection(self):
        s, = self.put(square())
        self.w.set_brut(dict(width=100, height=50))
        before = BR.bbox(BR.of(self.w.canvas.selection[0]))
        self.w.canvas.transform_selection(Affine.translation(7, 0))
        moved = BR.bbox(BR.of(self.w.canvas.selection[0]))
        self.assertAlmostEqual(moved[0], before[0] + 7)

    def test_painted(self):
        s, = self.put(square())
        self.w.set_brut(dict(width=100, height=50))
        self.w.canvas.resize(400, 300)
        self.w.canvas.fit()
        pm = self.w.canvas.grab()
        self.assertFalse(pm.isNull())

    def test_on_the_ribbon(self):
        from PySide6.QtGui import QAction
        self.assertTrue([a for a in self.w.findChildren(QAction) if a.text() == 'Brut de l\'ensemble…'])


class TestDialog(unittest.TestCase):
    def test_check(self):
        from vectordrive.ui.batdialog import BatDialog
        dlg = BatDialog(None, doc_of(square()), proof.ProofInfo())
        try:
            dlg.checks['show_bruts'].setChecked(False)
            self.assertFalse(dlg.result_info().show_bruts)
        finally:
            dlg.deleteLater()

    def test_option(self):
        from vectordrive.ui.options import BY_KEY, default_of
        self.assertTrue(default_of(BY_KEY['bat/show_bruts']))
        self.assertIn('show_bruts', proof.LAYOUT_FIELDS)


if __name__ == '__main__':
    unittest.main()
