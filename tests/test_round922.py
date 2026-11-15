"""Round 922 : le texte s'écrit dans le dessin (outil Texte : un clic, la frappe ; double-clic : repris à l'endroit
cliqué) ; la fenêtre Texte est dans le ruban — l'onglet Mise en forme, formulaire en deux rangées comme le Rapido de
TypeEdit 13, paraît avec l'outil Texte ; Ressort : petit bouton et touche Tab."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r922.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from vectordrive.core import text as TX  # noqa: E402
from vectordrive.core.document import Text  # noqa: E402
from vectordrive.core.geom import Affine  # noqa: E402

FONT = 'VD Trait'


def key(k, text='', mods=Qt.KeyboardModifier.NoModifier):
    return QKeyEvent(QEvent.Type.KeyPress, k, mods, text)


class Caret(unittest.TestCase):

    def text(self, s, align='left'):
        t = Text(text=s, font=FONT, size=5.0, align=align, matrix=Affine.translation(10.0, 20.0))
        t.outline = TX.outline_for(t)
        return t

    def test_one_point_per_position_on_the_baseline(self):
        t = self.text('AB\nC')
        pts = TX.caret_points(t)
        self.assertEqual(len(pts), len(t.text) + 1)
        self.assertEqual(pts[0], (10.0, 20.0))
        self.assertLess(pts[0][0], pts[1][0])
        self.assertLess(pts[1][0], pts[2][0])                       # fin de la 1re ligne
        self.assertAlmostEqual(pts[3][0], 10.0)                     # début de la 2e ligne
        self.assertLess(pts[3][1], 20.0)                            # plus bas
        bb = t.outline.bbox()
        self.assertTrue(bb[2] - 0.01 <= pts[2][0] <= bb[2] + 2.0)   # la fin de « AB » : son bord droit, avec l'approche

    def test_centered_and_right(self):
        c = TX.caret_points(self.text('ABC', 'center'))
        self.assertAlmostEqual((c[0][0] + c[-1][0]) / 2, 10.0)
        r = TX.caret_points(self.text('ABC', 'right'))
        self.assertAlmostEqual(r[-1][0], 10.0)

    def test_springs_share_the_line(self):
        t = self.text('A' + TX.SPRING + 'B\nAAAAAAAA')
        pts = TX.caret_points(t)
        self.assertAlmostEqual(pts[3][0], pts[-1][0], delta=0.01)   # « B » au bout de la plus longue ligne

    def test_nearest_position(self):
        t = self.text('ABCD')
        pts = TX.caret_points(t)
        self.assertEqual(TX.caret_index(t, (pts[2][0] + 0.1, 22.0)), 2)
        self.assertEqual(TX.caret_index(t, (500.0, 20.0)), 4)


class Typing(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui import text_presets as TP
        cls.TP = TP
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def setUp(self):
        self.w.set_tool('select')
        self.w.modified = False
        self.w.new_document()
        self.w._undo.clear()
        fmt = {'attrs': {'font': FONT, 'size': 4.0}, 'extra': {}}
        self.TP.set_new_text_format(self.w.settings, fmt, '')
        self.w.next_text_fit = None
        from unittest import mock
        window = mock.patch('vectordrive.ui.dialogs.TextDialog.exec', return_value=0)   # code d'avant : sans attente
        window.start()
        self.addCleanup(window.stop)

    def texts(self):
        return [it for L in self.w.canvas.doc.layers for it in L.items if isinstance(it, Text)]

    def typing(self, at=(10.0, 10.0)):
        self.w.new_text(*at)
        return self.w.canvas.tool_obj

    def test_letters_appear_as_they_are_typed(self):
        tool = self.typing()
        self.assertEqual(self.texts(), [])                          # rien avant la première lettre
        tool.key(key(Qt.Key.Key_A, 'A'))
        t, = self.texts()
        self.assertEqual((t.text, t.font, t.size), ('A', FONT, 4.0))
        self.assertEqual(self.w.canvas.selection, [t])
        for k, s in ((Qt.Key.Key_B, 'b'), (Qt.Key.Key_Return, ''), (Qt.Key.Key_C, 'c'), (Qt.Key.Key_Tab, ''),
                     (Qt.Key.Key_D, 'd'), (Qt.Key.Key_Backspace, ''), (Qt.Key.Key_Left, ''), (Qt.Key.Key_E, 'é')):
            self.assertTrue(tool.key(key(k, s)), k)
        self.assertEqual(t.text, 'Ab\n' + 'cé' + TX.SPRING)
        self.assertTrue(t.outline.contours)
        self.assertEqual(len(self.w._undo), 1)                      # toute la saisie : un pas
        self.assertTrue(tool.key(key(Qt.Key.Key_Escape)))
        self.assertFalse(tool.active())
        self.assertFalse(tool.key(key(Qt.Key.Key_Escape)))          # 2e Échap : pour la fenêtre (Sélection)
        self.w.undo()
        self.assertEqual(self.texts(), [])

    def test_shortcuts_pass_and_altgr_types(self):
        tool = self.typing()
        ctrl, alt = Qt.KeyboardModifier.ControlModifier, Qt.KeyboardModifier.AltModifier
        self.assertTrue(tool.wants_key(key(Qt.Key.Key_A, 'a')))
        self.assertTrue(tool.wants_key(key(Qt.Key.Key_Delete)))
        self.assertFalse(tool.wants_key(key(Qt.Key.Key_Z, '\x1a', ctrl)))
        self.assertTrue(tool.wants_key(key(Qt.Key.Key_V, '\x16', ctrl)))
        self.assertFalse(tool.wants_key(key(Qt.Key.Key_F, 'f', alt)))
        self.assertTrue(tool.wants_key(key(Qt.Key.Key_E, '€', ctrl | alt)))
        tool.finish()
        self.assertFalse(tool.wants_key(key(Qt.Key.Key_A, 'a')))

    def test_undo_while_typing_ends_it(self):
        tool = self.typing()
        tool.insert('ABC')
        self.w.undo()
        self.assertFalse(tool.active())
        self.assertEqual(self.texts(), [])

    def test_a_text_typed_empty_goes_away(self):
        tool = self.typing()
        tool.insert('A')
        tool.erase(-1)
        tool.finish()
        self.assertEqual(self.texts(), [])

    def test_fields_apply_to_the_text_being_typed(self):
        tool = self.typing()
        tool.insert('AB')
        t, = self.texts()
        self.w.textbar.size.setValue(9.0)
        self.assertEqual(t.size, 9.0)
        self.assertTrue(tool.active())
        tool.insert('C')
        self.assertEqual((t.text, t.size), ('ABC', 9.0))

    def test_double_click_types_in_the_text(self):
        t = Text(text='ABC', font=FONT, size=5.0, matrix=Affine.translation(0.0, 0.0))
        t.outline = TX.outline_for(t)
        self.w.canvas.doc.layers[0].items.append(t)
        from unittest import mock
        with mock.patch('vectordrive.ui.dialogs.TextDialog.exec', side_effect=AssertionError('fenêtre')):
            self.w._item_double_clicked(t)
        tool = self.w.canvas.tool_obj
        self.assertEqual(self.w.canvas.tool, 'text')
        self.assertIs(tool.item, t)
        tool.caret = 1
        tool.insert('x')
        self.assertEqual(t.text, 'AxBC')
        tool.finish()
        self.w.undo()
        self.assertEqual(self.w.canvas.doc.layers[0].items[0].text, 'ABC')

    def test_click_on_a_text_with_the_tool_resumes_it(self):
        t = Text(text='ABCD', font=FONT, size=5.0, matrix=Affine.translation(0.0, 0.0))
        t.outline = TX.outline_for(t)
        self.w.canvas.doc.layers[0].items.append(t)
        tool = self.typing((50.0, 50.0))
        pts = TX.caret_points(t)
        sp = self.w.canvas.view().map(__import__('PySide6.QtCore', fromlist=['QPointF']).QPointF(pts[2][0], 1.5))
        tool.press(sp, self.w.canvas.to_doc(sp), None)
        self.assertIs(tool.item, t)
        self.assertEqual(tool.caret, 2)

    def test_vertical_text_keeps_typing(self):
        tool = self.typing()
        tool.insert('AB')
        t, = self.texts()
        self.w.toggle_vertical_text()
        self.assertEqual(t.text, 'A\nB')
        tool.edit(t)
        tool.insert('C')
        self.assertEqual((t.extra['vertical']['text'], t.text), ('ABC', 'A\nB\nC'))

    def test_spring_button(self):
        self.assertFalse(self.w.insert_spring())                    # sans saisie : dit comment faire
        tool = self.typing()
        tool.insert('A')
        self.assertTrue(self.w.insert_spring())
        tool.insert('B')
        self.assertEqual(self.texts()[0].text, 'A' + TX.SPRING + 'B')

    def test_forced_width_from_the_ribbon(self):
        bar = self.w.textbar
        self.assertEqual(bar.set_fit(60.0, 'ratio'), 0)              # sans sélection : le prochain texte
        tool = self.typing()
        tool.insert('ABC')
        t, = self.texts()
        self.assertEqual(t.extra.get('fit'), {'width': 60.0, 'mode': 'ratio'})
        pts = TX.caret_points(t)
        self.assertAlmostEqual(pts[-1][0] - pts[0][0], 60.0, delta=0.01)   # la ligne fait la largeur imposée
        self.assertEqual(bar.set_fit(0.0), 1)
        self.assertNotIn('fit', t.extra)
        self.assertEqual(t.width_ratio, 1.0)


class Ribbon(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def tab(self):
        r = self.w.ribbon
        return next(i for i in range(r.count()) if r.tabText(i) == self.w.text_tab_title)

    def test_the_form_in_two_rows(self):
        r = self.w.ribbon
        page = r.page(self.tab())
        titles = [g.title.text() for g in page.groups()]
        for t in ('Texte', 'Général', 'Position du texte', 'Ligne de base', 'Largeur imposée', 'Préréglages'):
            self.assertIn(t, titles)
        general = page.groups()[titles.index('Général')]
        self.assertEqual(general.rows, 2)
        shown = {id(b.defaultAction()) for g in page.groups() for b in g.buttons()}
        A = self.w.A
        for k in ('text_back', 'tool_text', 'text_spring', 'text_align_center', 'case_upper', 'text_on_baseline'):
            self.assertIn(id(A[k]), shown, k)
        self.assertFalse(A['text_spring'].icon().isNull())

    def test_the_tab_comes_with_the_text_tool(self):
        if getattr(self.w, 'layout_active', False):
            self.skipTest('disposition TypeEdit 13')
        r = self.w.ribbon
        self.w.set_tool('select')
        self.w.canvas.select([])
        self.w._on_selection()
        before = r.currentIndex()
        self.assertFalse(r.isTabVisible(self.tab()))
        self.w.A['tool_text'].trigger()
        self.assertEqual(self.w.canvas.tool, 'text')
        self.assertTrue(r.isTabVisible(self.tab()))
        self.assertEqual(r.currentIndex(), self.tab())
        self.w.A['text_back'].trigger()
        self.assertEqual(self.w.canvas.tool, 'select')
        self.assertFalse(r.isTabVisible(self.tab()))
        self.assertEqual(r.currentIndex(), before)                  # l'onglet d'avant revient

    def test_the_text_window_spring_is_small(self):
        from PySide6.QtWidgets import QPushButton, QSizePolicy
        from vectordrive.ui.dialogs import TextDialog
        d = TextDialog(None, text='x')
        b = next(b for b in d.findChildren(QPushButton) if TX.SPRING in b.text())
        self.assertEqual(b.text(), 'Ressort ' + TX.SPRING)
        self.assertEqual(b.sizePolicy().horizontalPolicy(), QSizePolicy.Policy.Fixed)


if __name__ == '__main__':
    unittest.main()
