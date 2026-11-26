"""Round 1171 (demande du 26/11) : « couleurs : creer outil pinceau pour colorier manuellement les contours au
clic » — le pinceau de couleur du panneau Couleur."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'rpinceau.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Group, Shape  # noqa: E402

BEFORE = 'avant : pas de pinceau de couleur (le panneau Couleur ne colorait que la sélection)'
L, R = Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton
NO, SHIFT = Qt.KeyboardModifier.NoModifier, Qt.KeyboardModifier.ShiftModifier


class Brush(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.dock_color.show()
        self.w.show()
        app.processEvents()
        self.addCleanup(self.close)
        doc = self.w.canvas.doc
        self.a = Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]), tool=0)
        self.b = Shape(path=geom.Path([geom.rect(20, 0, 10, 10)]), tool=0)
        self.g = Group(children=[Shape(path=geom.Path([geom.rect(40, 0, 5, 5)]), tool=1),
                                 Shape(path=geom.Path([geom.rect(50, 0, 5, 5)]), tool=1)], tool=1)
        for it in (self.a, self.b, self.g):
            doc.add(it)
        self.w.canvas.invalidate()
        self.w.canvas.fit((-5.0, -10.0, 60.0, 20.0))
        app.processEvents()
        self.p = self.w.color_panel
        self.w.modified = False

    def close(self):
        if self.w.canvas.tool != 'select':
            self.w.set_tool('select')
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()

    # --- aides
    def at(self, x, y):
        q = self.w.canvas.to_screen(x, y).toPoint()
        self.assertTrue(self.w.canvas.rect().contains(q), (x, y, q))      # le point est bien à l'écran
        return q

    def click(self, x, y, button=L, mods=NO):
        QTest.mouseClick(self.w.canvas, button, mods, self.at(x, y))
        app.processEvents()

    def take_brush(self, colour=None):
        self.assertTrue('tool_color_brush' in self.w.A, BEFORE)
        if colour is not None:
            self.p.apply(colour)                         # sans sélection : la couleur courante seulement
        self.p.brush_button.click()
        app.processEvents()
        self.assertEqual(self.w.canvas.tool, 'color_brush')

    def leaves(self):
        """Les formes du dessin (après Ctrl+Z, des copies) dans l'ordre : a, b, puis les deux du groupe."""
        from vectordrive.ui.canvas import _leaves
        return list(_leaves(self.w.canvas.doc.active_layer.items))

    # --- essais
    def test_button_in_the_panel_brush_cursor(self):
        self.assertIsNotNone(getattr(self.p, 'brush_button', None), BEFORE)
        act = self.w.A['tool_color_brush']
        self.assertIs(self.p.brush_button.defaultAction(), act)
        self.assertEqual(self.p.brush_button.text(), 'Pinceau')
        self.assertFalse(act.icon().isNull())
        from vectordrive.ui import icons, tools
        self.assertIn('color_brush', icons.ICONS)
        self.take_brush()
        self.assertIsInstance(self.w.canvas.tool_obj, tools.ColorBrushTool)
        self.assertTrue(act.isChecked())
        self.assertEqual(self.w.canvas.cursor().shape(), Qt.CursorShape.BitmapCursor)   # le pinceau, pas la croix
        self.assertFalse(self.w.canvas.cursor().pixmap().isNull())
        self.assertIn('Pinceau', self.p.note.text())                      # le panneau dit ce que fait le pinceau

    def test_a_click_colours_the_contour_clicked_and_clicks_repeat(self):
        self.take_brush(3)
        self.click(0, 5)                                                     # le bord gauche de a
        self.assertEqual((self.a.tool, self.b.tool), (3, 0), BEFORE)
        self.assertTrue(self.w.modified)
        self.click(30, 5)                                                    # le bord droit de b : l'outil reste
        self.assertEqual((self.a.tool, self.b.tool), (3, 3))
        self.assertEqual(self.w.canvas.tool, 'color_brush')
        k0, k1 = self.g.children
        self.click(45, 2.5)                                                  # une forme du groupe : elle seule
        self.assertEqual((k0.tool, k1.tool, self.g.tool), (3, 1, 1))
        self.click(55, 2.5, mods=SHIFT)                                      # Maj : tout le groupe
        self.assertEqual((k0.tool, k1.tool, self.g.tool), (3, 3, 3))
        self.assertEqual(self.w.canvas.current_tool_index, 3)               # la couleur courante ne bouge pas

    def test_a_click_in_the_void_does_nothing(self):
        self.take_brush(2)
        steps = len(self.w._undo)
        self.assertIsNone(self.w.canvas.pick(self.at(15, 5)))
        self.click(15, 5)                                                    # entre a et b
        self.click(5, 5)                                                     # au milieu de a (vide : pas rempli)
        self.assertEqual([x.tool for x in self.leaves()], [0, 0, 1, 1])
        self.assertEqual((len(self.w._undo), self.w.modified), (steps, False))
        self.assertEqual(self.w.canvas.tool, 'color_brush')                 # l'outil reste pris
        self.click(10, 5)                                                    # le bord droit de a : 0 → 2
        self.assertEqual(self.a.tool, 2, BEFORE)
        self.click(10, 5)                                                    # déjà de cette couleur : aucun pas
        self.assertEqual(len(self.w._undo), steps + 1)

    def test_each_click_is_one_undo_step(self):
        self.take_brush(4)
        steps = len(self.w._undo)
        self.click(0, 5)
        self.click(20, 5)
        self.assertEqual(len(self.w._undo), steps + 2, BEFORE)
        self.assertEqual(self.w.undo_labels()[0], 'Pinceau de couleur')
        self.w.undo()                                                        # le dernier clic seulement
        self.assertEqual([x.tool for x in self.leaves()], [4, 0, 1, 1])
        self.w.undo()
        self.assertEqual([x.tool for x in self.leaves()], [0, 0, 1, 1])
        self.w.redo()
        self.assertEqual([x.tool for x in self.leaves()], [4, 0, 1, 1])

    def test_right_click_or_escape_quits(self):
        self.take_brush(5)
        self.click(0, 5, button=R)                                           # clic droit sur un contour : quitter
        self.assertEqual(self.w.canvas.tool, 'select', BEFORE)
        self.assertIsNone(self.w.canvas.tool_obj)
        self.assertFalse(self.w.A['tool_color_brush'].isChecked())
        self.assertEqual(self.a.tool, 0)                                     # sans rien colorier
        self.assertNotEqual(self.w.canvas.cursor().shape(), Qt.CursorShape.BitmapCursor)
        self.take_brush()
        self.w.canvas.setFocus()
        QTest.keyClick(self.w.canvas, Qt.Key.Key_Escape)
        app.processEvents()
        self.assertEqual(self.w.canvas.tool, 'select')
        self.click(0, 5)                                                     # après : un clic sélectionne
        self.assertEqual(self.a.tool, 0)

    def test_another_colour_in_the_panel_is_the_brush_colour(self):
        self.w.canvas.selection = [self.a]
        self.w._on_selection()
        self.take_brush()
        self.p.apply(4)                                                      # pendant l'outil : la couleur du pinceau
        self.assertEqual(self.a.tool, 0, 'la sélection n’est pas recolorée')
        self.assertEqual(self.w.canvas.current_tool_index, 4)
        self.assertEqual(self.w.canvas.tool, 'color_brush')
        self.assertEqual(self.w.canvas.tool_obj.color(), self.w.canvas.doc.tool_color(4))
        self.click(20, 5)
        self.assertEqual(self.b.tool, 4, BEFORE)
        self.p.apply(6)
        self.click(30, 5)
        self.assertEqual(self.b.tool, 6)
        self.w.set_tool('select')
        self.p.apply(2)                                                      # sans le pinceau : comme avant
        self.assertEqual(self.a.tool, 2)

    def test_in_favorites_and_f10_shortcuts_without_a_taken_key(self):
        self.assertTrue('tool_color_brush' in self.w.A, BEFORE)
        self.assertEqual(self.w._default_shortcuts['tool_color_brush'], [])   # aucune touche prise
        dlg = self.w.shortcuts_dialog(exec_dialog=False)
        self.addCleanup(dlg.deleteLater)
        self.assertTrue(dlg.select_key('tool_color_brush'))                  # F10 › Raccourcis : à régler
        fav = self.w.favorites_dialog(exec_dialog=False)
        self.addCleanup(fav.deleteLater)
        from vectordrive.ui.fav_dialog import KEY
        keys = [fav.all.item(i).data(KEY) for i in range(fav.all.count())]
        self.assertIn('tool_color_brush', keys)                              # à ajouter aux favoris

    def test_shape_under_a_group_taken_by_an_image_or_a_hidden_child(self):
        """Un groupe posé dessus, retenu sous le pointeur par son image (`pick_all`) mais sans contour visible
        touché : c'est la forme du dessous qui est coloriée. Une forme cachée d'un groupe, même là, n'est jamais
        coloriée (`pick_all` ne la voit pas : le groupe n'est pas retenu)."""
        from vectordrive.core.geom import Affine
        from vectordrive.core.document import Image
        doc = self.w.canvas.doc
        far = Shape(path=geom.Path([geom.rect(30, 12, 3, 3)]), tool=0)
        pic = Group(children=[Image(data=png(), fmt='png', matrix=Affine(4, 0, 0, 4, -2, 3)), far], tool=0)
        hidden = Shape(path=geom.Path([geom.rect(20, 0, 10, 10)]), tool=0, visible=False)
        veil = Group(children=[hidden, Shape(path=geom.Path([geom.rect(35, 12, 3, 3)]), tool=0)], tool=0)
        doc.add(pic)
        doc.add(veil)
        self.w.canvas.invalidate()
        app.processEvents()
        self.assertIs(self.w.canvas.pick(self.at(0, 5)), pic)              # l'image retient le groupe du dessus
        self.take_brush(3)
        self.click(0, 5)
        self.assertEqual((self.a.tool, far.tool, pic.tool), (3, 0, 0), 'la forme sous l’image')
        self.click(20, 5)
        self.assertEqual((self.b.tool, hidden.tool, veil.tool), (3, 0, 0), 'la forme sous le groupe')

    def test_locked_hidden_or_locked_layer_not_coloured(self):
        self.take_brush(3)
        steps = len(self.w._undo)
        self.a.locked = True                                                 # verrouillé
        self.b.visible = False                                               # caché
        self.w.canvas.invalidate()
        app.processEvents()
        self.click(0, 5)
        self.click(20, 5)
        self.assertEqual((self.a.tool, self.b.tool), (0, 0), BEFORE)
        self.w.canvas.doc.active_layer.locked = True                         # calque verrouillé
        self.w.canvas.invalidate()
        app.processEvents()
        self.click(45, 2.5)
        self.assertEqual([x.tool for x in self.g.children], [1, 1])
        self.assertEqual((len(self.w._undo), self.w.modified), (steps, False))
        self.assertEqual(self.w.canvas.tool, 'color_brush')

    def test_shift_shows_the_whole_group_without_moving(self):
        self.take_brush(3)
        tool = self.w.canvas.tool_obj
        self.w.canvas.setFocus()
        QTest.mouseMove(self.w.canvas, self.at(45, 2.5))
        app.processEvents()
        if tool.hover is None:                                               # sans suivi de la souris (offscreen)
            tool.move(self.at(45, 2.5), (45, 2.5), None)
        self.assertIs(tool.hover[1], self.g.children[0])
        self.assertFalse(tool.whole)
        QTest.keyPress(self.w.canvas, Qt.Key.Key_Shift)
        app.processEvents()
        self.assertTrue(tool.whole, 'avant : l’aperçu du groupe attendait un mouvement de la souris')
        QTest.keyRelease(self.w.canvas, Qt.Key.Key_Shift)
        app.processEvents()
        self.assertFalse(tool.whole)


def png() -> bytes:
    """Une petite image PNG (4 × 4 px, grise)."""
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice
    from PySide6.QtGui import QColor, QImage
    img = QImage(4, 4, QImage.Format.Format_RGB32)
    img.fill(QColor('#808080'))
    raw = QByteArray()
    buf = QBuffer(raw)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, 'PNG')
    buf.close()
    return bytes(raw.data())


if __name__ == '__main__':
    unittest.main()
