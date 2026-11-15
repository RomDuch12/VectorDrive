"""Round 985 : retours de l'atelier — zoom de la molette inversable (F5) ; le rectangle de sélection garde son coin de
départ dans le dessin quand on zoome en le tirant ; la double flèche d'une poignée ne reste pas après Suppr ; les
onglets de calques se ferment (F10 tout de suite, bouton ×, Ctrl+Tab ne les rouvre plus) ; double-clic sur le nom
d'un calque pour le renommer."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r985.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent, QWheelEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QAbstractItemView, QApplication, QLineEdit, QStyleOptionViewItem  # noqa: E402

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Layer, Shape  # noqa: E402

app = QApplication.instance() or QApplication([])


def window():
    from vectordrive.ui.main_window import MainWindow
    w = MainWindow()
    w.settings.setValue('fenetre/plein_ecran', False)
    w.resize(1200, 800)
    w.show()
    app.processEvents()
    return w


def close(w):
    w.A['layer_tabs'].setChecked(False)
    w.modified = False
    for t in getattr(w, 'docs', []):
        t.modified = False
    w.close()
    app.processEvents()


def mouse(kind, pos, button=Qt.MouseButton.NoButton, buttons=Qt.MouseButton.NoButton):
    p = QPointF(pos)
    return QMouseEvent(kind, p, p, button, buttons, Qt.KeyboardModifier.NoModifier)


def wheel(pos, up=True):
    p = QPointF(pos)
    return QWheelEvent(p, p, QPoint(0, 0), QPoint(0, 120 if up else -120), Qt.MouseButton.NoButton,
                       Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)


class Wheel(unittest.TestCase):

    def test_wheel_zoom_can_be_inverted(self):
        """F5 : « Inverser le zoom de la molette » — gardé, appliqué : la molette vers l'avant éloigne."""
        w = window()
        try:
            c = w.canvas
            w.mouse_settings({'wheel': 'zoom', 'invert': False, 'right': 'aucun'})
            s = c.scale
            c.wheelEvent(wheel(QPointF(300, 300)))
            self.assertGreater(c.scale, s)                                  # d'office : vers l'avant, rapprocher
            w.mouse_settings({'wheel': 'zoom', 'invert': True, 'right': 'aucun'})
            self.assertIn(w.settings.value('souris/molette_inverse'), (True, 'true'))
            s = c.scale
            c.wheelEvent(wheel(QPointF(300, 300)))
            self.assertLess(c.scale, s)                                     # inversé : éloigner
            c.wheel_invert = False
            w.apply_mouse_settings()                                        # relu des réglages (relance)
            self.assertTrue(c.wheel_invert)
            w.mouse_settings({'wheel': 'zoom', 'invert': False, 'right': 'aucun'})
        finally:
            close(w)


class Band(unittest.TestCase):

    def test_band_corner_stays_in_the_drawing_while_zooming(self):
        """Bouton gauche tenu, la molette zoome plusieurs fois depuis plusieurs centres : le coin de départ du
        rectangle reste au même point du dessin ; la sélection est celle du rectangle tiré dans le dessin."""
        w = window()
        try:
            c, d = w.canvas, w.canvas.doc
            a = Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]))
            b = Shape(path=geom.Path([geom.rect(40, 0, 10, 10)]))
            d.add(a)
            d.add(b)
            c.invalidate()
            c.scale, c.ox, c.oy = 3.0, 100.0, 500.0
            start = c.to_screen(-5, 15)                                     # au-dessus à gauche de a
            c.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, start, Qt.MouseButton.LeftButton,
                                    Qt.MouseButton.LeftButton))
            self.assertEqual(c._drag['kind'], 'band')
            for f, at in ((2.0, QPointF(400, 300)), (1.5, QPointF(200, 150)), (0.7, QPointF(600, 450))):
                c.zoom_at(f, at)
            end = c.to_screen(15, -5)                                       # en dessous à droite de a, avant b
            c.mouseMoveEvent(mouse(QEvent.Type.MouseMove, end, buttons=Qt.MouseButton.LeftButton))
            c.grab()                                                        # le rectangle peint
            sx, sy = c.to_doc(c._drag['start'])
            self.assertAlmostEqual(sx, -5, places=6)
            self.assertAlmostEqual(sy, 15, places=6)
            c.mouseReleaseEvent(mouse(QEvent.Type.MouseButtonRelease, end, Qt.MouseButton.LeftButton))
            self.assertEqual(c.selection, [a])
        finally:
            close(w)


class Cursor(unittest.TestCase):

    def test_handle_cursor_reset_after_delete(self):
        """Le pointeur montre la double flèche sur le coin d'une forme choisie ; Suppr : il redevient celui de
        l'outil, sans bouger la souris ; sans sélection, le survol ne garde pas la double flèche."""
        w = window()
        try:
            c, d = w.canvas, w.canvas.doc
            s = Shape(path=geom.Path([geom.rect(0, 0, 30, 20)]))
            d.add(s)
            c.select([s])
            c.update()
            bb = c.selection_bbox()
            corner = c.to_screen(*c.doc_handles(bb)[0])
            c.mouseMoveEvent(mouse(QEvent.Type.MouseMove, corner))
            self.assertIn(c.cursor().shape(), (Qt.CursorShape.SizeFDiagCursor, Qt.CursorShape.SizeBDiagCursor))
            w.A['delete'].trigger()
            app.processEvents()
            self.assertEqual(d.layers[0].items, [])
            self.assertEqual(c.cursor().shape(), Qt.CursorShape.ArrowCursor)
            # le pointeur resté sur une poignée sans que la sélection change de signal : le survol le rend
            c.setCursor(Qt.CursorShape.SizeFDiagCursor)
            c.mouseMoveEvent(mouse(QEvent.Type.MouseMove, corner + QPointF(5, 5)))
            self.assertEqual(c.cursor().shape(), Qt.CursorShape.ArrowCursor)
        finally:
            close(w)

    def test_new_selection_handle_gets_its_own_cursor_and_leave_forgets(self):
        """La sélection change et une poignée reste sous le pointeur : il prend la flèche de cette poignée ; le
        pointeur sorti de la vue, la position survolée est oubliée."""
        w = window()
        try:
            c, d = w.canvas, w.canvas.doc
            s = Shape(path=geom.Path([geom.rect(0, 0, 30, 20)]))
            d.add(s)
            c.select([s])
            corner = c.to_screen(*c.doc_handles(c.selection_bbox())[0])
            c.mouseMoveEvent(mouse(QEvent.Type.MouseMove, corner))
            want = c.cursor().shape()
            self.assertIn(want, (Qt.CursorShape.SizeFDiagCursor, Qt.CursorShape.SizeBDiagCursor))
            c.setCursor(Qt.CursorShape.SizeHorCursor)                       # la flèche d'une autre poignée
            c.select([s])
            self.assertEqual(c.cursor().shape(), want)
            c.leaveEvent(QEvent(QEvent.Type.Leave))
            self.assertIsNone(c._hover_pos)
            c.select([])
            self.assertEqual(c.cursor().shape(), Qt.CursorShape.ArrowCursor)
        finally:
            close(w)


class LayerTabs(unittest.TestCase):

    def setUp(self):
        self.w = window()
        d = self.w.canvas.doc
        d.layers.append(Layer(name='Fine', tool=2))
        self.w.layers_panel.refresh()

    def tearDown(self):
        close(self.w)

    def test_ctrl_tab_does_not_reopen_the_tabs(self):
        w, d = self.w, self.w.canvas.doc
        w.A['layer_tabs'].setChecked(False)
        self.assertIs(d.active_layer, d.layers[0])
        w.A['layer_next'].trigger()
        self.assertFalse(w.A['layer_tabs'].isChecked())
        self.assertFalse(w.layer_bar.isVisibleTo(w))
        self.assertIs(d.active_layer, d.layers[1])                          # le calque suivant, actif

    def test_ctrl_tab_skips_hidden_and_locked_layers(self):
        """Onglets fermés, Ctrl+Tab passe les calques cachés ou verrouillés : on ne dessine pas dedans."""
        w, d = self.w, self.w.canvas.doc
        d.layers.append(Layer(name='Cachée', tool=3, visible=False))
        d.layers.append(Layer(name='Fermée', tool=4, locked=True))
        d.layers.append(Layer(name='Libre', tool=5))
        w.layers_panel.refresh()
        w.A['layer_tabs'].setChecked(False)
        d.active = d.layers[1].id
        w.A['layer_next'].trigger()
        self.assertIs(d.active_layer, d.layers[4])
        w.A['layer_next'].trigger()
        self.assertIs(d.active_layer, d.layers[0])                          # le tour recommence

    def test_f10_option_and_close_button(self):
        w = self.w
        w.settings.setValue('vue/onglets_calques', True)
        w.apply_options()                                                    # F10 › Affichage, validé
        self.assertTrue(w.A['layer_tabs'].isChecked())
        self.assertTrue(w.layer_bar.isVisibleTo(w))
        w.layer_tabs_close.click()                                          # le × de la barre
        self.assertFalse(w.A['layer_tabs'].isChecked())
        self.assertFalse(w.layer_bar.isVisibleTo(w))
        self.assertIsNone(w.canvas.solo_layer)
        self.assertIn(w.settings.value('vue/onglets_calques'), (False, 'false'))
        w.settings.setValue('vue/onglets_calques', True)
        w.apply_options()
        w.settings.setValue('vue/onglets_calques', False)
        w.apply_options()
        self.assertFalse(w.layer_bar.isVisibleTo(w))


class LayerRename(unittest.TestCase):

    def test_double_click_renames_a_layer(self):
        """Double-clic sur le nom d'un calque (même pas encore actif) : il se renomme ; seul le nom s'édite."""
        w = window()
        try:
            d = w.canvas.doc
            d.layers.append(Layer(name='Fine', tool=2))
            lp = w.layers_panel
            lp.refresh()
            tree = lp.tree
            item = tree.topLevelItem(1)
            first = item
            x = sum(tree.header().sectionSize(k) for k in range(lp.COL_NAME)) + 8
            pt = QPoint(x, tree.visualItemRect(item).center().y())
            QTest.mouseClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=pt)
            self.assertIs(d.active_layer, d.layers[1])
            self.assertIs(tree.topLevelItem(1), first)                      # la liste n'est pas refaite au clic
            self.assertTrue(first.font(lp.COL_NAME).bold())
            QTest.mouseDClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=pt)
            app.processEvents()
            self.assertEqual(tree.state(), QAbstractItemView.State.EditingState)
            editors = [e for e in tree.viewport().findChildren(QLineEdit) if e.isVisible()]
            self.assertEqual(len(editors), 1)
            editors[0].setText('Gravure fine')
            QTest.keyClick(editors[0], Qt.Key.Key_Return)
            app.processEvents()
            self.assertEqual(d.layers[1].name, 'Gravure fine')
            model = tree.model()
            for col in (lp.COL_TOOL, lp.COL_N):
                self.assertIsNone(tree.itemDelegate().createEditor(tree.viewport(), QStyleOptionViewItem(),
                                                                   model.index(0, col)))
        finally:
            close(w)

    def test_locked_layer_renames_without_the_padlock(self):
        """Un calque verrouillé se renomme : le champ montre son nom, sans le cadenas, et le nom reste propre."""
        w = window()
        try:
            d = w.canvas.doc
            d.layers.append(Layer(name='Fine', tool=2, locked=True))
            lp = w.layers_panel
            lp.refresh()
            tree = lp.tree
            item = tree.topLevelItem(1)
            self.assertIn('🔒', item.text(lp.COL_NAME))
            tree.editItem(item, lp.COL_NAME)
            app.processEvents()
            editors = [e for e in tree.viewport().findChildren(QLineEdit) if e.isVisible()]
            self.assertEqual(len(editors), 1)
            self.assertEqual(editors[0].text(), 'Fine')
            editors[0].setText('Fine 🔒')                                    # même collé avec le cadenas
            QTest.keyClick(editors[0], Qt.Key.Key_Return)
            app.processEvents()
            self.assertEqual(d.layers[1].name, 'Fine')
        finally:
            close(w)


if __name__ == '__main__':
    unittest.main()
