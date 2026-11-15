"""Round 999 : la saisie de texte dans le dessin a une sélection (demande du 14/11) — double clic : le mot ; triple :
la ligne ; quadruple : tout le texte ; glisser, Maj+clic, Maj+flèches l'étendent ; la frappe, Coller, Suppr et Retour
arrière la remplacent ou la retirent ; Ctrl+C la copie, Ctrl+X la coupe ; un clic dans la boîte du texte (creux,
espace, bout de ligne) reste dans le texte."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r999.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from vectordrive.core import text as TX  # noqa: E402
from vectordrive.core.document import Text  # noqa: E402
from vectordrive.core.geom import Affine  # noqa: E402

FONT = 'VD Trait'
SHIFT, CTRL = Qt.KeyboardModifier.ShiftModifier, Qt.KeyboardModifier.ControlModifier
K = Qt.Key


def key(k, text='', mods=Qt.KeyboardModifier.NoModifier):
    return QKeyEvent(QEvent.Type.KeyPress, k, mods, text)


class Held:
    """Un mouvement de souris, bouton gauche tenu ou non ; un clic avec Maj."""

    def __init__(self, left=True, shift=False):
        self.left, self.shift = left, shift

    def buttons(self):
        return Qt.MouseButton.LeftButton if self.left else Qt.MouseButton.NoButton

    def modifiers(self):
        return SHIFT if self.shift else Qt.KeyboardModifier.NoModifier


class Spans(unittest.TestCase):

    def test_the_word_of_the_clicked_character(self):
        s = 'Plaque 12, atelier'
        self.assertEqual(TX.char_span(s, 2), (0, 6))
        self.assertEqual(TX.char_span(s, 6), (6, 7))                # l'espace cliquée : elle
        self.assertEqual(TX.char_span(s, 9), (9, 10))               # la virgule seule
        self.assertEqual(TX.char_span(s, 7), (7, 9))
        self.assertEqual(TX.char_span(s, 18), (11, 18))             # au-delà de la ligne : son dernier mot
        self.assertEqual(TX.char_span('été à', 1), (0, 3))          # les lettres accentuées sont du mot
        self.assertEqual(TX.char_span('A   B', 2), (1, 4))          # les espaces ensemble
        self.assertEqual(TX.char_span('A' + TX.SPRING + TX.SPRING + ' B', 2), (1, 4))   # ressorts : des espaces

    def test_the_word_at_the_caret(self):
        s = 'Plaque 12, atelier'
        self.assertEqual(TX.word_span(s, 6), (0, 6))                # juste après le mot : lui
        self.assertEqual(TX.word_span(s, 7), (7, 9))                # … le mot d'après d'abord
        self.assertEqual(TX.word_span('A ... B', 3), (2, 5))

    def test_never_past_the_line(self):
        s = 'AB\nCD\n\nEF'
        self.assertEqual(TX.char_span(s, 2), (0, 2))                # sur le saut de ligne : le mot d'avant
        self.assertEqual(TX.char_span(s, 3), (3, 5))
        self.assertEqual(TX.char_span(s, 6), (6, 6))                # ligne vide : rien
        self.assertEqual(TX.line_span(s, 4), (3, 5))
        self.assertEqual(TX.line_span(s, 6), (6, 6))
        self.assertEqual(TX.line_span(s, 9), (7, 9))
        self.assertEqual(TX.line_span('', 0), (0, 0))


class Selecting(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui import text_presets as TP
        from vectordrive.ui import tools as T
        cls.TP, cls.T = TP, T
        cls.w = MainWindow()
        cls.w.canvas.resize(600, 400)

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def setUp(self):
        self.w.set_tool('select')
        self.w.modified = False
        self.w.new_document()
        self.w._undo.clear()
        self.TP.set_new_text_format(self.w.settings, {'attrs': {'font': FONT, 'size': 4.0}, 'extra': {}}, '')
        self.w.next_text_fit = None
        window = mock.patch('vectordrive.ui.dialogs.TextDialog.exec', return_value=0)
        window.start()
        self.addCleanup(window.stop)
        if hasattr(self.T.TextTool, 'CLICK_S'):
            slow = mock.patch.object(self.T.TextTool, 'CLICK_S', 60.0)      # les clics des essais : toujours « à la suite »
            slow.start()
            self.addCleanup(slow.stop)

    def editing(self, s='AB CD\nEF', caret=None):
        t = Text(text=s, font=FONT, size=5.0, matrix=Affine.translation(10.0, 20.0))
        t.outline = TX.outline_for(t)
        self.w.canvas.doc.layers[0].items.append(t)
        self.w.set_tool('text')
        tool = self.w.canvas.tool_obj
        tool.edit(t, caret=caret)
        return t, tool

    def at(self, t, i, shift=0.25, up=2.5):
        """Le point de l'écran de la position `i` (un peu après, à mi-hauteur)."""
        x, y = TX.caret_points(t)[i]
        return self.w.canvas.view().map(QPointF(x + shift, y + up))

    def between(self, t, i, j):
        """Le point de l'écran au milieu des positions `i` et `j` de la même ligne, à mi-hauteur."""
        pts = TX.caret_points(t)
        return self.w.canvas.view().map(QPointF((pts[i][0] + pts[j][0]) / 2, pts[i][1] + 2.5))

    def click(self, tool, sp, n=1):
        """`n` clics à la suite comme Qt les envoie : appui, double clic, appui, double clic."""
        for i in range(n):
            (tool.double if i % 2 else tool.press)(sp, self.w.canvas.to_doc(sp), None)

    def test_double_the_word_triple_the_line_quadruple_all(self):
        t, tool = self.editing()
        sp = self.at(t, 3)                                          # dans « CD »
        self.click(tool, sp)
        self.assertIsNone(tool.selection())
        self.assertEqual(tool.caret, 3)
        tool.double(sp, self.w.canvas.to_doc(sp), None)
        self.assertEqual((tool.selection(), tool.selected_text()), ((3, 5), 'CD'))
        tool.press(sp, self.w.canvas.to_doc(sp), None)
        self.assertEqual((tool.selection(), tool.selected_text()), ((0, 5), 'AB CD'))
        tool.double(sp, self.w.canvas.to_doc(sp), None)
        self.assertEqual(tool.selection(), (0, 8))
        self.assertIs(tool.item, t)                                 # toujours le même texte, rien de fini
        self.assertEqual(t.text, 'AB CD\nEF')

    def test_the_clicked_character_decides(self):
        t, tool = self.editing('AB, CD')
        for (i, j), want in (((2, 3), ','), ((3, 4), ' '), ((1, 2), 'AB'), ((4, 5), 'CD')):
            n, when, where = tool._clicks
            tool._clicks = (0, 0.0, None)                           # une suite neuve à chaque fois
            sp = self.between(t, i, j)                              # au milieu du caractère de rang i
            self.click(tool, sp, 2)
            self.assertEqual(tool.selected_text(), want, (i, j))
            self.assertIs(tool.item, t)

    def test_clicks_off_the_ink_stay_in_the_text(self):
        t, tool = self.editing()
        c = self.w.canvas
        was = c.scale
        self.addCleanup(setattr, c, 'scale', was)
        c.scale = 40.0                                              # de près : l'espace est large, sans trait autour
        space = self.between(t, 2, 3)                               # sur l'espace entre « AB » et « CD »
        self.assertIsNone(self.w.canvas.pick(space))                # aucun trait là
        tool.press(space, self.w.canvas.to_doc(space), None)
        self.assertIs(tool.item, t)                                 # la saisie continue
        self.assertIn(tool.caret, (2, 3))
        tool.double(space, self.w.canvas.to_doc(space), None)
        self.assertEqual(tool.selected_text(), ' ')
        tool._clicks = (0, 0.0, None)
        tool.caret = 0
        past = self.at(t, 5, shift=2.0)                             # après la dernière lettre de la 1re ligne
        tool.press(past, self.w.canvas.to_doc(past), Held(shift=True))
        self.assertIs(tool.item, t)
        self.assertEqual(tool.selected_text(), 'AB CD')             # Maj+clic : jusqu'au bout de la ligne
        tool._clicks = (0, 0.0, None)
        far = self.at(t, 0, shift=-60.0)                            # loin du texte : il est fini
        tool.press(far, self.w.canvas.to_doc(far), None)
        self.assertIsNot(tool.item, t)

    def test_slow_or_distant_clicks_are_single(self):
        t, tool = self.editing()
        sp = self.at(t, 3)
        self.click(tool, sp)
        self.assertIs(tool.item, t)
        n, when, where = tool._clicks
        tool._clicks = (n, when - 500.0, where)                     # bien plus tard
        tool.press(sp, self.w.canvas.to_doc(sp), None)
        self.assertIs(tool.item, t)
        self.assertIsNone(tool.selection())
        other = self.at(t, 0)
        tool.press(other, self.w.canvas.to_doc(other), None)        # tout de suite, mais ailleurs
        self.assertIs(tool.item, t)
        self.assertIsNone(tool.selection())
        self.assertEqual(tool.caret, 0)

    def test_typing_replaces_the_selection(self):
        t, tool = self.editing()
        tool.select(3, 5)
        self.assertTrue(tool.key(key(K.Key_X, 'x')))
        self.assertEqual((t.text, tool.caret, tool.selection()), ('AB x\nEF', 4, None))
        tool.select(0, 2)
        self.assertTrue(tool.key(key(K.Key_Return)))
        self.assertEqual(t.text, '\n x\nEF')
        self.assertEqual(len(self.w._undo), 1)                      # toujours un seul pas pour la saisie

    def test_erase_removes_the_selection_only(self):
        for k in (K.Key_Backspace, K.Key_Delete):
            self.setUp()
            t, tool = self.editing()
            tool.select(5, 2)                                       # tirée de droite à gauche
            self.assertEqual(tool.selection(), (2, 5))
            self.assertTrue(tool.key(key(k)))
            self.assertEqual((t.text, tool.caret, tool.selection()), ('AB\nEF', 2, None), k)

    def test_copy_cut_paste(self):
        t, tool = self.editing()
        tool.select(0, 2)
        self.assertTrue(tool.wants_key(key(K.Key_C, '\x03', CTRL)))
        self.assertTrue(tool.wants_key(key(K.Key_X, '\x18', CTRL)))
        self.assertFalse(tool.wants_key(key(K.Key_C, '\x03', CTRL | SHIFT)))   # « copier avec point de base » : la fenêtre
        QApplication.clipboard().setText('')
        self.assertTrue(tool.key(key(K.Key_C, '\x03', CTRL)))
        self.assertEqual(QApplication.clipboard().text(), 'AB')
        self.assertEqual((t.text, tool.selection()), ('AB CD\nEF', (0, 2)))
        tool.select(3, 5)
        self.assertTrue(tool.key(key(K.Key_X, '\x18', CTRL)))
        self.assertEqual((QApplication.clipboard().text(), t.text), ('CD', 'AB \nEF'))
        tool.select(0, 2)
        QApplication.clipboard().setText('xyz')
        self.assertTrue(tool.key(key(K.Key_V, '\x16', CTRL)))
        self.assertEqual((t.text, tool.caret), ('xyz \nEF', 3))
        tool.select(0, 3)
        self.assertTrue(tool.key(key(K.Key_Insert, '', CTRL)))      # Ctrl+Inser copie
        self.assertEqual(QApplication.clipboard().text(), 'xyz')
        self.assertTrue(tool.key(key(K.Key_Delete, '', SHIFT)))     # Maj+Suppr coupe
        self.assertEqual(t.text, ' \nEF')

    def test_cut_again_does_not_delete_the_text_object(self):
        t, tool = self.editing()
        tool.select(3, 5)
        QApplication.clipboard().setText('')
        self.assertTrue(tool.key(key(K.Key_X, '\x18', CTRL)))
        again = key(K.Key_X, '\x18', CTRL)                          # la touche tenue : plus de sélection
        self.assertTrue(tool.wants_key(again))                      # toujours pour le texte, pas pour « Couper » l'objet
        self.assertTrue(tool.key(again))
        self.assertEqual((t.text, QApplication.clipboard().text()), ('AB \nEF', 'CD'))
        self.assertIn(t, self.w.canvas.doc.layers[0].items)
        self.assertTrue(tool.wants_key(key(K.Key_C, '\x03', CTRL)))
        tool.finish()
        self.assertFalse(tool.wants_key(key(K.Key_C, '\x03', CTRL)))   # hors saisie : la copie d'objets

    def test_copy_and_cut_of_the_window_take_the_text_selection(self):
        t, tool = self.editing()
        tool.select(0, 2)
        QApplication.clipboard().setText('')
        self.w.copy()                                               # Copier du menu, de la barre
        self.assertEqual(QApplication.clipboard().text(), 'AB')
        self.w.cut()
        self.assertEqual(t.text, ' CD\nEF')
        self.assertIn(t, self.w.canvas.doc.layers[0].items)         # le texte n'est pas coupé avec

    def test_selection_dropped_when_the_text_changes_elsewhere(self):
        t, tool = self.editing('AB CD')
        tool.select(3, 5)
        t.text = 'ABCDEFG CD'                                       # Rechercher / remplacer, casse…
        t.outline = TX.outline_for(t)
        self.assertIsNone(tool.selection())
        self.assertEqual(tool.selection_quads(), [])
        tool.insert('x')
        self.assertEqual(t.text.count('x'), 1)
        self.assertEqual(len(t.text), 11)                           # rien d'autre n'a été remplacé

    def test_shift_arrows_extend_and_plain_arrows_drop(self):
        t, tool = self.editing(caret=1)
        self.assertTrue(tool.wants_key(key(K.Key_Right, '', SHIFT)))
        for _ in range(3):
            self.assertTrue(tool.key(key(K.Key_Right, '', SHIFT)))
        self.assertEqual((tool.selection(), tool.caret), ((1, 4), 4))
        tool.key(key(K.Key_Left, '', SHIFT))
        self.assertEqual(tool.selection(), (1, 3))
        tool.key(key(K.Key_Left))                                   # sans Maj : au début de la sélection
        self.assertEqual((tool.selection(), tool.caret), (None, 1))
        tool.key(key(K.Key_End, '', SHIFT))
        self.assertEqual(tool.selected_text(), 'B CD')
        tool.key(key(K.Key_Right))                                  # … à sa fin
        self.assertEqual((tool.selection(), tool.caret), (None, 5))
        tool.key(key(K.Key_Home, '', SHIFT))
        self.assertEqual(tool.selection(), (0, 5))
        tool.caret = 1
        tool.key(key(K.Key_Down, '', SHIFT))                        # la ligne d'en dessous
        self.assertEqual(tool.selected_text(), 'B CD\nE')
        tool.key(key(K.Key_Up, '', SHIFT))                          # revenue au départ : plus de sélection
        self.assertIsNone(tool.selection())
        self.assertEqual(t.text, 'AB CD\nEF')

    def test_dragging_selects(self):
        t, tool = self.editing()
        a, b = self.at(t, 1), self.at(t, 4)
        tool.press(a, self.w.canvas.to_doc(a), None)
        tool.move(b, self.w.canvas.to_doc(b), Held(left=False))     # sans bouton : rien
        self.assertIsNone(tool.selection())
        tool.move(b, self.w.canvas.to_doc(b), Held())
        self.assertEqual((tool.selection(), tool.caret), ((1, 4), 4))
        tool.move(a, self.w.canvas.to_doc(a), Held())               # revenu au départ
        self.assertIsNone(tool.selection())
        tool.move(b, self.w.canvas.to_doc(b), Held())
        tool.release(b, self.w.canvas.to_doc(b), None)
        zero = self.at(t, 0)
        tool.move(zero, self.w.canvas.to_doc(zero), Held())         # bouton relâché : elle ne bouge plus
        self.assertEqual(tool.selection(), (1, 4))

    def test_shift_click_extends(self):
        t, tool = self.editing(caret=1)
        sp = self.at(t, 4)
        tool.press(sp, self.w.canvas.to_doc(sp), Held(shift=True))
        self.assertEqual((tool.selection(), tool.caret), ((1, 4), 4))
        sp = self.at(t, 7)
        tool._clicks = (0, 0.0, None)
        tool.press(sp, self.w.canvas.to_doc(sp), Held(shift=True))  # encore : du même départ
        self.assertEqual(tool.selection(), (1, 7))

    def test_double_click_with_the_selection_tool(self):
        t = Text(text='AB CD\nEF', font=FONT, size=5.0, matrix=Affine.translation(10.0, 20.0))
        t.outline = TX.outline_for(t)
        self.w.canvas.doc.layers[0].items.append(t)
        sp = self.at(t, 3)
        self.w.canvas.last_double = None
        with mock.patch.object(self.w, '_cursor_doc', return_value=self.w.canvas.to_doc(sp)):
            self.w._item_double_clicked(t)
        tool = self.w.canvas.tool_obj
        self.assertIs(tool.item, t)
        self.assertEqual(tool.selected_text(), 'CD')                # le mot double-cliqué
        tool.press(sp, self.w.canvas.to_doc(sp), None)              # 3e clic : la ligne
        self.assertEqual(tool.selected_text(), 'AB CD')
        tool.double(sp, self.w.canvas.to_doc(sp), None)             # 4e : tout
        self.assertEqual(tool.selection(), (0, 8))

    def test_through_the_view(self):
        t = Text(text='AB CD\nEF', font=FONT, size=5.0, matrix=Affine.translation(10.0, 20.0))
        t.outline = TX.outline_for(t)
        c = self.w.canvas
        c.doc.layers[0].items.append(t)
        c.invalidate()
        left, none = Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier
        sp = self.at(t, 3).toPoint()
        with mock.patch.object(self.w, '_cursor_doc', side_effect=AssertionError('le point du double clic, pas la souris')):
            QTest.mouseClick(c, left, none, sp)                     # outil Sélection : le texte choisi
            QTest.mouseDClick(c, left, none, sp)                    # … double-cliqué : repris, son mot sélectionné
            QTest.mouseRelease(c, left, none, sp)
        tool = c.tool_obj
        self.assertEqual(c.tool, 'text')
        self.assertIs(tool.item, t)
        self.assertEqual(tool.selected_text(), 'CD')
        QTest.mouseClick(c, left, none, sp)                         # 3e clic : la ligne
        self.assertEqual(tool.selected_text(), 'AB CD')
        QTest.mouseDClick(c, left, none, sp)                        # 4e : tout
        QTest.mouseRelease(c, left, none, sp)
        self.assertEqual(tool.selection(), (0, 8))
        tool._clicks = (0, 0.0, None)
        a, b = self.at(t, 1).toPoint(), self.at(t, 4).toPoint()
        QTest.mousePress(c, left, none, a)                          # glisser, par la vue
        QTest.mouseMove(c, b)
        app.processEvents()
        if tool.selection() is None:                                # (hors écran, le mouvement peut arriver sans bouton)
            tool.move(QPointF(b), c.to_doc(QPointF(b)), Held())
        QTest.mouseRelease(c, left, none, b)
        self.assertEqual(tool.selection(), (1, 4))

    def test_selection_shown_line_by_line(self):
        t, tool = self.editing()
        self.assertEqual(tool.selection_quads(), [])
        tool.select(1, 7)                                           # « B CD », le saut de ligne, « E »
        quads = tool.selection_quads()
        self.assertEqual(len(quads), 3)                             # la ligne, le saut de ligne, la ligne d'après
        pts = TX.caret_points(t)
        (x0, y0), (x1, y1) = quads[0][0], quads[0][1]
        self.assertAlmostEqual(x0, pts[1][0])
        self.assertAlmostEqual(x1, pts[5][0])
        self.assertLess(y0, pts[1][1])                              # de sous la ligne de base…
        self.assertGreater(quads[0][2][1], pts[1][1] + 2.9)         # … vers le haut des capitales
        self.assertAlmostEqual(quads[1][0][0], pts[5][0])           # le saut de ligne : étroit, en bout de ligne
        self.assertGreater(quads[1][1][0], pts[5][0])
        self.assertLess(quads[1][1][0] - quads[1][0][0], 2.0)
        self.assertAlmostEqual(quads[2][0][0], pts[6][0])
        self.assertAlmostEqual(quads[2][1][0], pts[7][0])
        self.assertLessEqual(quads[2][2][1], quads[0][0][1] + 1e-6)  # les deux lignes ne se recouvrent pas
        tool.select(5, 6)                                           # le saut de ligne seul : il se voit
        self.assertEqual(len(tool.selection_quads()), 1)
        tool.select(1, 7)
        from PySide6.QtGui import QImage, QPainter
        img = QImage(600, 400, QImage.Format.Format_ARGB32)
        img.fill(0)
        p = QPainter(img)
        tool.lit = False
        tool.paint(p)                                               # curseur éteint : la sélection reste peinte
        p.end()
        mid = self.w.canvas.view().map(QPointF((x0 + x1) / 2, pts[1][1] + 2.0)).toPoint()
        out = self.w.canvas.view().map(QPointF(pts[0][0] - 3.0, pts[1][1] + 2.0)).toPoint()
        self.assertTrue(img.rect().contains(mid) and img.rect().contains(out), (mid, out))
        self.assertGreater(img.pixelColor(mid).alpha(), 0)
        self.assertEqual(img.pixelColor(out).alpha(), 0)            # hors de la sélection : rien

    def test_vertical_text(self):
        self.w.new_text(10.0, 10.0)
        tool = self.w.canvas.tool_obj
        tool.insert('AB CD')
        t = tool.item
        self.w.toggle_vertical_text()
        tool.edit(t)
        tool.select(1, 3)
        self.assertEqual(tool.selected_text(), 'B ')
        self.assertEqual(len(tool.selection_quads()), 2)            # une lettre par ligne
        pts = TX.caret_points(t)                                    # « D », la 5e lettre : positions 8 et 9
        sp = self.w.canvas.view().map(QPointF((pts[8][0] + pts[9][0]) / 2, pts[8][1] + 2.0))
        tool._clicks = (0, 0.0, None)
        self.click(tool, sp, 2)
        self.assertEqual(tool.selected_text(), 'CD')                # double clic sur une lettre : son mot
        tool.insert('x')
        self.assertEqual(t.extra['vertical']['text'], 'AB x')

    def test_ending_drops_the_selection(self):
        t, tool = self.editing()
        tool.select(0, 2)
        tool.finish()
        self.assertIsNone(tool.anchor)
        self.assertIsNone(tool.selection())
        tool.edit(t, caret=1)
        self.assertIsNone(tool.selection())
        tool.insert('x')
        self.assertEqual(t.text, 'AxB CD\nEF')
        tool.finish()
        tool = self.T.TextTool(self.w.canvas, None)                 # sans fenêtre : un double clic demande une fois
        asked = []
        self.w.canvas.textRequested.connect(lambda x, y: asked.append((x, y)))
        sp = QPointF(50, 50)
        tool.press(sp, (1.0, 2.0), None)
        tool.double(sp, (1.0, 2.0), None)
        self.assertEqual(asked, [(1.0, 2.0)])


if __name__ == '__main__':
    unittest.main()
