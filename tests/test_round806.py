"""Round 806 : les lettres d'un texte, à la souris sur le dessin."""
import math
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QApplication

from vectordrive.core import text as TX
from vectordrive.core.document import Text
from vectordrive.core.geom import Affine, circle, Contour, Line
from vectordrive.ui import tools as T

app = QApplication.instance() or QApplication([])
FONT = 'Arial'


class Event:
    def __init__(self, key=None, mods=Qt.KeyboardModifier.NoModifier):
        self._key, self._mods = key, mods

    def key(self):
        return self._key

    def modifiers(self):
        return self._mods


def make(s='HIH', **kw):
    kw.setdefault('size', 10.0)
    t = Text(text=s, font=FONT, **kw)
    t.outline = TX.outline_for(t)
    return t


def centre(path):
    b = path.bbox()
    return (b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0


class Letters(unittest.TestCase):
    def test_every_drawn_letter_with_its_position(self):
        t = make('AB C\nD')
        got = TX.letter_outlines(t)
        self.assertEqual([i for i, _p in got], [0, 1, 3, 5])        # ni l'espace ni le saut de ligne

    def test_they_make_up_the_text(self):
        t = make('HIH')
        got = TX.letter_outlines(t)
        self.assertEqual(sum(len(p.contours) for _i, p in got), len(t.outline.contours))
        whole = t.outline.bbox()
        boxes = [p.bbox() for _i, p in got]
        self.assertAlmostEqual(min(b[0] for b in boxes), whole[0], places=6)
        self.assertAlmostEqual(max(b[2] for b in boxes), whole[2], places=6)

    def test_with_a_matrix(self):
        m = Affine.translation(50, 20) @ Affine.rotation(30)
        t = make('HIH', matrix=m)
        got = TX.letter_outlines(t)
        whole = t.outline.bbox()
        self.assertAlmostEqual(max(p.bbox()[2] for _i, p in got), whole[2], places=6)

    def test_italic_and_baseline_too(self):
        t = make('HIH')
        t.extra['italic'] = 12.0
        t.outline = TX.outline_for(t)
        self.assertAlmostEqual(max(p.bbox()[2] for _i, p in TX.letter_outlines(t)), t.outline.bbox()[2], places=6)

    def test_letters_follow_their_settings(self):
        t = make('HIH')
        before = centre(TX.letter_outlines(t)[1][1])
        TX.set_char_fx(t, {1: {'dy': 50.0}})
        t.outline = TX.outline_for(t)
        after = centre(TX.letter_outlines(t)[1][1])
        self.assertAlmostEqual(after[1] - before[1], 5.0, places=6)
        self.assertAlmostEqual(after[0], before[0], places=6)

    def test_springs_keep_their_positions(self):
        t = make('A' + TX.SPRING + 'B')
        self.assertEqual([i for i, _p in TX.letter_outlines(t)], [0, 2])

    def test_only_straight_text(self):
        t = make('HIH')
        self.assertTrue(TX.straight(t))
        for key, value in (('rtl', True), ('arc', {'center': (0, 0), 'radius': 5}),
                           ('arc_warp', {'center': (0, 0), 'radius': 5}), ('on_path', Contour([Line((0, 0), (9, 0))], False))):
            t = make('HIH')
            t.extra[key] = value
            self.assertFalse(TX.straight(t), key)
            self.assertEqual(TX.letter_outlines(t), [])

    def test_the_old_callers_are_unchanged(self):
        self.assertEqual(TX._placed('AB', FONT, 10.0, 'left', 0.0, 1.2, 1.0, True)[0][1].e, 0.0)


class Tool(unittest.TestCase):
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
        self.c = self.win.canvas
        self.doc = self.c.doc
        self.doc.layers[0].items = []
        self.c.selection = []
        self.win._undo.clear()
        self.c.scale = 4.0
        self.c.ox, self.c.oy = 100.0, 400.0
        self.win.set_tool('letters')
        self.tool = self.c.tool_obj
        self.addCleanup(self.win.set_tool, 'select')

    def add(self, s='HIH', **kw):
        t = make(s, **kw)
        self.doc.add(t)
        self.c.select([t])
        return t

    def at(self, t, i):
        """Le milieu de la lettre, sur le dessin et à l'écran."""
        p = dict(TX.letter_outlines(t))[i]
        d = centre(p)
        return d, self.c.to_screen(*d)

    def click(self, t, i, mods=Qt.KeyboardModifier.NoModifier):
        d, sp = self.at(t, i)
        ev = Event(mods=mods)
        self.tool.press(sp, d, ev)
        self.tool.release(sp, d, ev)

    def drag(self, t, i, ddx, ddy):
        d, sp = self.at(t, i)
        self.tool.press(sp, d, Event())
        end = (d[0] + ddx, d[1] + ddy)
        send = self.c.to_screen(*end)
        self.tool.move(send, end, Event())
        self.tool.release(send, end, Event())

    def test_is_the_active_tool(self):
        self.assertIsInstance(self.tool, T.LetterTool)

    def test_finds_the_letter_under_the_pointer(self):
        t = self.add()
        for i in range(3):
            self.assertEqual(self.tool.letter_at(self.at(t, i)[0]), i)
        self.assertIsNone(self.tool.letter_at((500.0, 500.0)))

    def test_click_chooses(self):
        t = self.add()
        self.click(t, 1)
        self.assertEqual(self.tool.picked, {1})
        self.click(t, 2)
        self.assertEqual(self.tool.picked, {2})

    def test_ctrl_adds_and_removes(self):
        t = self.add()
        self.click(t, 0)
        self.click(t, 2, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.tool.picked, {0, 2})
        self.click(t, 0, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.tool.picked, {2})

    def test_click_on_a_text_not_selected_takes_it(self):
        t = self.add()
        self.c.select([])
        d, sp = self.at(t, 0)
        ring = t.outline.contours[0].segments[0].start
        with mock.patch.object(self.c, 'pick', return_value=t):
            self.tool.press(self.c.to_screen(*ring), ring, Event())
        self.assertEqual(self.c.selection, [t])
        self.assertIsNotNone(self.tool.drag)

    def test_click_elsewhere_lets_go(self):
        t = self.add()
        self.click(t, 0)
        self.tool.press(QPointF(1000, 5), self.c.to_doc(QPointF(1000, 5)), Event())
        self.tool.release(QPointF(1000, 5), self.c.to_doc(QPointF(1000, 5)), Event())
        self.assertEqual(self.tool.picked, set())
        self.assertEqual(self.c.selection, [])

    def test_a_small_shake_is_only_a_click(self):
        t = self.add()
        d, sp = self.at(t, 1)
        self.tool.press(sp, d, Event())
        near = QPointF(sp.x() + 1, sp.y())
        self.tool.move(near, self.c.to_doc(near), Event())
        self.tool.release(near, self.c.to_doc(near), Event())
        self.assertEqual(TX.char_fx(t), {})
        self.assertEqual(self.tool.picked, {1})

    def test_drag_moves_the_letter(self):
        t = self.add()
        before = self.at(t, 1)[0]
        other = self.at(t, 2)[0]
        self.drag(t, 1, 3.0, 2.0)
        after = self.at(t, 1)[0]
        self.assertAlmostEqual(after[0] - before[0], 3.0, places=6)
        self.assertAlmostEqual(after[1] - before[1], 2.0, places=6)
        self.assertAlmostEqual(self.at(t, 2)[0][0], other[0], places=6)        # les autres ne bougent pas
        self.assertAlmostEqual(TX.char_fx(t)[1]['dy'], 20.0, places=6)

    def test_drag_moves_every_chosen_letter(self):
        t = self.add()
        self.click(t, 0)
        self.click(t, 2, Qt.KeyboardModifier.ControlModifier)
        self.drag(t, 2, 0.0, 1.0)
        self.assertEqual(set(TX.char_fx(t)), {0, 2})

    def test_drag_on_a_turned_text(self):
        t = self.add(matrix=Affine.translation(30, 30) @ Affine.rotation(90))
        before = self.at(t, 1)[0]
        self.drag(t, 1, 2.0, 3.0)
        after = self.at(t, 1)[0]
        self.assertAlmostEqual(after[0] - before[0], 2.0, places=5)
        self.assertAlmostEqual(after[1] - before[1], 3.0, places=5)

    def test_drag_on_a_squeezed_text(self):
        t = self.add(width_ratio=0.5)
        before = self.at(t, 1)[0]
        self.drag(t, 1, 2.0, 0.0)
        self.assertAlmostEqual(self.at(t, 1)[0][0] - before[0], 2.0, places=5)

    def test_drag_on_a_slanted_text(self):
        t = make('HIH')
        t.extra['italic'] = 15.0
        t.outline = TX.outline_for(t)
        self.doc.add(t)
        self.c.select([t])
        before = self.at(t, 1)[0]
        self.drag(t, 1, 1.0, 2.0)
        after = self.at(t, 1)[0]
        self.assertAlmostEqual(after[0] - before[0], 1.0, places=5)
        self.assertAlmostEqual(after[1] - before[1], 2.0, places=5)

    def test_one_undo_for_a_drag(self):
        t = self.add()
        d, sp = self.at(t, 1)
        self.tool.press(sp, d, Event())
        for k in range(1, 4):
            end = (d[0] + k, d[1])
            self.tool.move(self.c.to_screen(*end), end, Event())
        self.tool.release(self.c.to_screen(*end), end, Event())
        self.assertEqual(len(self.win._undo), 1)
        self.win.undo()
        items = [it for it in self.doc.layers[0].items if isinstance(it, Text)]
        self.assertEqual(TX.char_fx(items[0]), {})

    def test_arrows(self):
        t = self.add()
        self.click(t, 1)
        self.assertTrue(self.tool.wants_key(Event(Qt.Key.Key_Left)))
        self.assertTrue(self.tool.key(Event(Qt.Key.Key_Up)))
        self.assertEqual(TX.char_fx(t)[1]['dy'], 1.0)
        self.tool.key(Event(Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier))
        self.assertEqual(TX.char_fx(t)[1]['dx'], 5.0)
        self.tool.key(Event(Qt.Key.Key_Down))
        self.assertNotIn('dy', TX.char_fx(t)[1])                # revenu à zéro : plus de réglage

    def test_alt_arrows_kern(self):
        t = self.add()
        self.click(t, 1)
        third = self.at(t, 2)[0][0]
        self.tool.key(Event(Qt.Key.Key_Right, Qt.KeyboardModifier.AltModifier))
        self.assertEqual(TX.char_fx(t)[1]['kern'], 1.0)
        self.assertAlmostEqual(self.at(t, 2)[0][0] - third, 0.1, places=5)         # 1 % de 10 mm, et ce qui suit bouge

    def test_size_and_rotation(self):
        t = self.add()
        self.click(t, 1)
        h0 = dict(TX.letter_outlines(t))[1].bbox()
        self.tool.key(Event(Qt.Key.Key_Plus))
        self.assertEqual(TX.char_fx(t)[1]['h'], 105.0)
        self.assertGreater(dict(TX.letter_outlines(t))[1].bbox()[3] - dict(TX.letter_outlines(t))[1].bbox()[1], h0[3] - h0[1])
        self.tool.key(Event(Qt.Key.Key_PageUp))
        self.assertEqual(TX.char_fx(t)[1]['rot'], 5.0)
        self.tool.key(Event(Qt.Key.Key_PageDown))
        self.assertNotIn('rot', TX.char_fx(t)[1])

    def test_size_stays_above_zero(self):
        t = self.add()
        self.click(t, 1)
        for _ in range(30):
            self.tool.key(Event(Qt.Key.Key_Minus))
        self.assertGreaterEqual(TX.char_fx(t)[1]['h'], 1.0)

    def test_delete_resets_the_chosen_ones(self):
        t = self.add()
        TX.set_char_fx(t, {0: {'dy': 10.0}, 1: {'dy': 20.0}})
        t.outline = TX.outline_for(t)
        self.click(t, 1)
        self.tool.key(Event(Qt.Key.Key_Delete))
        self.assertEqual(set(TX.char_fx(t)), {0})

    def test_keys_are_left_alone_without_a_letter(self):
        self.add()
        self.assertFalse(self.tool.wants_key(Event(Qt.Key.Key_Left)))
        self.assertFalse(self.tool.key(Event(Qt.Key.Key_Left)))

    def test_escape(self):
        t = self.add()
        self.click(t, 1)
        self.assertTrue(self.tool.key(Event(Qt.Key.Key_Escape)))
        self.assertEqual(self.tool.picked, set())
        self.assertFalse(self.tool.key(Event(Qt.Key.Key_Escape)))

    def test_curved_text_says_so(self):
        t = make('HIH')
        t.extra['on_path'] = Contour([Line((0, 0), (50, 0))], False)
        t.outline = TX.outline_for(t)
        self.doc.add(t)
        self.c.select([])
        self.assertEqual(self.tool.letters(t), [])
        with mock.patch.object(self.c, 'pick', return_value=t):
            self.tool.press(QPointF(120, 380), self.c.to_doc(QPointF(120, 380)), Event())
        self.assertIn('courbe', self.win.statusBar().currentMessage())
        self.assertIsNone(self.tool.drag)

    def test_double_click_opens_the_window_on_that_letter(self):
        t = self.add()
        d, sp = self.at(t, 2)
        with mock.patch('vectordrive.ui.letters_dialog.LettersDialog.exec', lambda dlg: 0) as _m:
            captured = {}
            real = self.win.text_letters_dialog

            def spy(exec_dialog=True, letter=None):
                captured['dlg'] = real(exec_dialog, letter)
                return captured['dlg']
            self.tool.open_dialog = spy
            self.tool.double(sp, d, Event())
        self.assertEqual(captured['dlg'].indices(), [2])

    def test_memo_follows_the_text(self):
        t = self.add()
        rows = self.tool.letters()
        self.assertIs(self.tool.letters(), rows)
        self.click(t, 1)
        self.tool.key(Event(Qt.Key.Key_Up))
        self.assertIsNot(self.tool.letters(), rows)

    def test_paints_without_a_fuss(self):
        from PySide6.QtGui import QImage, QPainter
        t = self.add()
        self.click(t, 1)
        self.tool.hover = 0
        img = QImage(200, 200, QImage.Format.Format_RGB32)
        p = QPainter(img)
        self.tool.paint(p)
        p.end()

    def test_ribbon(self):
        action = self.win.A['tool_letters']
        found = [b for i in range(self.win.ribbon.count()) for g in self.win.ribbon.page(i).groups()
                 for b in g.buttons() if b.defaultAction() is action]
        self.assertEqual(len(found), 1)


if __name__ == '__main__':
    unittest.main()
