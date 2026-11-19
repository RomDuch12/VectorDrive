"""Round 1096 (demande du 19/11, 16 h 37) : clic droit sur un calque = lui seul visible et actif ; calques en onglets
= panneau Calques masqué ; icône propre à la Bibliothèque ; Cadre englobant dans Manipulation ; Combiner ne remplit
plus un contour combiné avec un texte, et Décombiner ne remplit pas un contour ouvert."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1096.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication, QDockWidget, QToolButton

app = QApplication.instance() or QApplication([])


def rect(x=0, y=0, w=10, h=10, filled=False):
    from vectordrive.core import geom
    from vectordrive.core.document import Shape
    return Shape(path=geom.Path([geom.rect(x, y, w, h)]), filled=filled)


class Win(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        cls.w.show()
        app.processEvents()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()


class LayerSolo(Win):

    def setUp(self):
        from vectordrive.core.document import Layer
        doc = self.w.canvas.doc
        doc.layers[:] = [Layer(name='A', items=[rect()]), Layer(name='B', items=[rect(20)]),
                         Layer(name='C', items=[rect(40)], visible=False)]
        doc.active = doc.layers[0].id
        self.w.layers_panel.refresh()
        self.doc = doc

    def test_right_click_shows_it_alone_then_gives_back(self):
        p = self.w.layers_panel
        A, B, C = self.doc.layers
        item = p.tree.topLevelItem(1)
        pos = p.tree.visualItemRect(item).center()
        p.tree.customContextMenuRequested.emit(pos)                # le clic droit sur « B »
        self.assertEqual([L.visible for L in self.doc.layers], [False, True, False])
        self.assertIs(self.doc.active_layer, B)
        self.assertTrue(p.tree.topLevelItem(1).font(p.COL_NAME).bold())
        self.assertIsNone(QApplication.activePopupWidget())       # pas de menu
        p.tree.customContextMenuRequested.emit(p.tree.visualItemRect(p.tree.topLevelItem(1)).center())
        self.assertEqual([L.visible for L in self.doc.layers], [True, True, False])    # la visibilité d'avant
        self.assertIs(self.doc.active_layer, B)

    def test_another_layer_after_solo(self):
        p = self.w.layers_panel
        A, B, C = self.doc.layers
        p.solo(A.id)
        self.assertTrue(p.solo(C.id))                             # un calque masqué : montré seul, actif
        self.assertEqual([L.visible for L in self.doc.layers], [False, False, True])
        self.assertIs(self.doc.active_layer, C)
        self.assertFalse(p.solo('inconnu'))

    def test_empty_place_does_nothing(self):
        p = self.w.layers_panel
        before = [L.visible for L in self.doc.layers]
        from PySide6.QtCore import QPoint
        p._solo_at(QPoint(5, 100000))                             # sous les lignes
        self.assertEqual([L.visible for L in self.doc.layers], before)


class LayerTabsHidePanel(Win):

    def dock(self):
        return self.w.findChild(QDockWidget, 'layers')

    def tearDown(self):
        self.w.A['layer_tabs'].setChecked(False)

    def test_tabs_hide_the_panel_and_give_it_back(self):
        d = self.dock()
        d.setVisible(True)
        self.w.A['layer_tabs'].setChecked(True)
        self.assertTrue(d.isHidden())
        self.w.A['layer_tabs'].setChecked(False)
        self.assertFalse(d.isHidden())

    def test_closed_panel_stays_closed(self):
        d = self.dock()
        d.setVisible(False)
        self.w.A['layer_tabs'].setChecked(True)
        self.w.A['layer_tabs'].setChecked(False)
        self.assertTrue(d.isHidden())                             # ce n'étaient pas les onglets
        d.setVisible(True)

    def test_shown_by_hand_while_tabs_stays(self):
        d = self.dock()
        d.setVisible(True)
        self.w.A['layer_tabs'].setChecked(True)
        d.setVisible(True)                                        # remontré à la main
        self.w._layers_follow_tabs()
        self.assertFalse(d.isHidden())

    def test_not_back_into_a_hidden_column(self):
        d = self.dock()
        d.setVisible(True)
        self.w.A['layer_tabs'].setChecked(True)
        cols = self.w.columns
        side = cols.side(d)
        real = cols.shown
        cols.shown = lambda s: False if s == side else real(s)          # la colonne masquée entre-temps
        try:
            self.w.A['layer_tabs'].setChecked(False)
            self.assertTrue(d.isHidden())
        finally:
            cols.shown = real
            d.setVisible(True)

    def test_session_restore_hides_it_again(self):
        d = self.dock()
        d.setVisible(True)
        self.w.A['layer_tabs'].setChecked(True)
        d.setVisible(True)                                        # une session d'avant le montrait
        self.w._columns_restored()
        self.assertTrue(d.isHidden())


class LibraryIcon(Win):

    def test_own_icon(self):
        from vectordrive.ui.icons import icon
        img = lambda ic: ic.pixmap(32, 32).toImage()
        self.assertNotEqual(img(self.w.A['symbols'].icon()), img(icon('group')))
        self.assertEqual(img(self.w.A['symbols'].icon()), img(icon('library')))
        self.assertEqual(img(self.w.A['library_big'].icon()), img(icon('library')))
        self.assertNotEqual(img(icon('library')), img(icon('ungroup')))


class BoundingFrame(Win):

    def test_vectordrive_layout_transformation(self):
        r = self.w.ribbon
        found = False
        for i in range(r.count()):
            for g in r.page(i).groups() if hasattr(r, 'page') else []:
                if g.title.text() == 'Transformation':
                    acts = [b.defaultAction() for b in g.findChildren(QToolButton)]
                    found = found or self.w.A['bbox_frame'] in acts
        self.assertTrue(found)
        self.assertIn('bbox_frame', self.w.PALETTES['palette_transform'][1])
        for i in range(r.count()):                                # plus dans Mesure : une commande une fois
            for g in r.page(i).groups():
                if g.title.text() == 'Mesure':
                    self.assertNotIn(self.w.A['bbox_frame'], [b.defaultAction() for b in g.findChildren(QToolButton)])

    def test_typeedit_manipulation_context(self):
        from vectordrive.ui.shortcuts import TE_ACTIONS
        from vectordrive.ui.typeedit_layout import TELayout, TEPanel, TETab
        w = self.w
        trim = next(c for c, k in TE_ACTIONS.items() if k == 'tool_trim')
        lay = TELayout(tabs=[TETab('CAD', [TEPanel('Essai', [(trim, True)])])],
                       contexts={'1002': TETab('Manipulation', [TEPanel('Retour', [('ID_RETOUR_ESSAI', True)]),
                                                                TEPanel('Manipulation', [(trim, True)])],
                                               '1002', 'ID_RETOUR_ESSAI'),
                                 '1004': TETab('Transformation', [TEPanel('Transformation', [(trim, True)])], '1004')})
        w.layout_active, w._te_layout = True, lay
        w._build_te_tabs(lay)
        try:
            r = w.ribbon
            pages = {str(r.widget(i).property('te_context')): r.page(i) for i in range(r.count())
                     if r.widget(i).property('te_context')}
            groups = {g.title.text(): g for g in pages['1002'].groups()}
            self.assertEqual(set(groups), {'Retour', 'Manipulation'})
            self.assertNotIn(w.A['bbox_frame'],
                             [b.defaultAction() for b in groups['Retour'].findChildren(QToolButton)])
            acts = [b.defaultAction() for b in groups['Manipulation'].findChildren(QToolButton)]
            self.assertIn(w.A['bbox_frame'], acts)
            self.assertIn(w.A['bbox_frame_options'], acts)
            self.assertEqual(acts.count(w.A['bbox_frame']), 1)
            other = [b.defaultAction() for b in pages['1004'].groups()[0].findChildren(QToolButton)]
            self.assertNotIn(w.A['bbox_frame'], other)
        finally:
            w.layout_active = False
            w.apply_ribbon_layout()


class CombineFill(unittest.TestCase):

    def text(self):
        from vectordrive.core import geom
        from vectordrive.core.document import Text
        t = Text(text='A', font='VD Géo', size=10)
        t.outline = geom.Path([geom.rect(50, 0, 5, 8)])
        return t

    def test_text_does_not_fill_a_contour(self):
        from vectordrive.core import combine as C
        sh = C.combine([rect(), self.text()])
        self.assertFalse(sh.filled)
        self.assertFalse(any(s.filled for s in C.uncombine(sh)))        # rien de plein en décombinant
        self.assertTrue(C.combine([rect(filled=True), self.text()]).filled)
        self.assertTrue(C.combine([rect(filled=True), rect(20, filled=True)]).filled)
        self.assertFalse(C.combine([rect(filled=True), rect(20)]).filled)
        self.assertTrue(all(not s.filled for s in C.combine_nested([rect(0, 0, 30, 30), rect(5, 5, 5, 5, True)])))

    def test_nested_open_contour_never_filled(self):
        from vectordrive.core import combine as C
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        sh = Shape(path=geom.Path([geom.rect(0, 0, 5, 5), geom.rect(20, 0, 5, 5),
                                   geom.polyline([(40, 0), (50, 0), (50, 9)], closed=False)]), filled=True)
        parts = C.combine_nested([sh])
        self.assertEqual(sorted(p.filled for p in parts), [False, True, True])
        self.assertFalse(next(p for p in parts if not p.path.contours[0].closed).filled)

    def test_open_contour_never_filled(self):
        from vectordrive.core import combine as C
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        line = geom.polyline([(0, 0), (10, 0), (10, 10)], closed=False)
        sh = Shape(path=geom.Path([geom.rect(20, 0, 5, 5), line]), filled=True)
        parts = C.uncombine(sh)
        self.assertEqual([p.filled for p in parts], [True, False])


if __name__ == '__main__':
    unittest.main()
