"""Round 1176 (demande du 26/11 : « Ctrl+7 possibilité de masquer les n° contours, couleur ok »). « Numéros des
contours » montre ou cache le rang de chaque objet écrit par Ctrl+7 (Sens) ; les couleurs de sens ne changent pas."""
import os
import tempfile
import unittest

import tests  # noqa: F401  (réglages et dossiers des essais, jamais ceux du poste)

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'rnum.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from unittest import mock  # noqa: E402

from PySide6.QtCore import QPoint  # noqa: E402
from PySide6.QtWidgets import QApplication, QToolButton  # noqa: E402

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Shape  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : les numéros de Ctrl+7 ne se cachaient pas'
KEY = 'vue/sens_numeros'


def reverse(c):
    return geom.Contour([s.reversed() for s in reversed(c.segments)], c.closed)


def ccw_rect(x, y, w, h):
    c = geom.rect(x, y, w, h)
    return c if c.signed_area() > 0 else reverse(c)


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = w = MainWindow()
        c = w.canvas
        c.resize(700, 500)
        d = c.doc
        cls.items = [d.add(Shape(path=geom.Path([ccw_rect(0, 0, 20, 20)]))),
                     d.add(Shape(path=geom.Path([reverse(ccw_rect(40, 0, 20, 20))]))),
                     d.add(Shape(path=geom.Path([geom.Contour([geom.Line((80, 10), (110, 10))], False)])))]

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()
        cls.w.settings.remove(KEY)

    def setUp(self):
        w, c = self.w, self.w.canvas
        self.assertTrue(hasattr(c, 'show_order_numbers'), BEFORE)
        self.assertIn('direction_numbers', w.A, BEFORE)
        c.select([])
        c.show_fill = c.show_starts = c.show_nodes = False
        c.scale, c.ox, c.oy = 4.0, 20.5, 300.5
        if not w.A['direction_numbers'].isChecked():
            w.A['direction_numbers'].setChecked(True)
        w.settings.remove(KEY)

    def numbers(self, on: bool):
        a = self.w.A['direction_numbers']
        if a.isChecked() != on:
            a.trigger()                                                        # comme un clic sur le bouton

    def grab(self, direction=True):
        c = self.w.canvas
        c.show_direction = direction
        c.update()
        return c.grab().toImage()

    def boxes(self):
        """Là où Ctrl+7 écrit les rangs : à droite et au-dessus du départ de chaque objet (texte de 11 px)."""
        out = []
        for _n, (x, y) in self.w.canvas.order_marks():
            P = self.w.canvas.to_screen(x, y)
            out.append((P.x() + 2, P.y() - 22, P.x() + 32, P.y()))
        return out

    def ribbon_button(self, key):
        w = self.w
        return next(b for b in w.findChildren(QToolButton)
                    if b.defaultAction() is w.A[key] and w._in_ribbon(b))

    def menu_of(self, key):
        b = self.ribbon_button(key)
        return self.w._ribbon_button_menu(b, QPoint(), exec_menu=False, **(self.w._button_menu_args(b) or {}))


class Command(Base):
    def test_default_shown_and_checkable(self):
        w = self.w
        a = w.A['direction_numbers']
        self.assertTrue(a.isCheckable())
        self.assertTrue(a.isChecked())                                         # d'office : comme avant
        self.assertTrue(w.canvas.show_order_numbers)
        self.assertEqual(a.text(), 'Numéros des contours')
        self.assertEqual(a.property('vd_icon'), 'direction_numbers')

    def test_icon_drawn_and_own(self):
        from vectordrive.ui import icons
        self.assertIn('direction_numbers', icons.ICONS)
        a = icons.icon('direction_numbers').pixmap(32, 32).toImage()
        b = icons.icon('direction').pixmap(32, 32).toImage()
        self.assertGreater(sum(1 for x in range(32) for y in range(32) if a.pixelColor(x, y).alpha() > 128), 40)
        self.assertFalse(a == b)

    def test_in_ribbon_next_to_direction(self):
        b = self.ribbon_button('direction_numbers')
        page = b.parentWidget()
        while page is not None and not hasattr(page, 'groups'):
            page = page.parentWidget()
        self.assertIsNotNone(page)
        g = next(g for g in page.groups() if b in g.buttons())
        keys = [self.w._action_key(x.defaultAction()) for x in g.buttons()]
        self.assertIn('direction', keys)                                       # le groupe de Sens (Vue › Contours)
        self.assertIn('show_starts', keys)

    def test_setting_kept(self):
        from vectordrive.ui.main_window import MainWindow
        w = self.w
        self.numbers(False)
        self.assertFalse(w.canvas.show_order_numbers)
        self.assertIn(w.settings.value(KEY), (False, 'false'))
        w.settings.sync()
        w2 = MainWindow()                                                      # au lancement suivant : retenu
        try:
            self.assertFalse(w2.A['direction_numbers'].isChecked())
            self.assertFalse(w2.canvas.show_order_numbers)
        finally:
            w2.modified = False
            w2.close()
        self.numbers(True)
        self.assertTrue(w.canvas.show_order_numbers)
        self.assertIn(w.settings.value(KEY), (True, 'true'))

    def test_view_flag_per_tab(self):
        w = self.w
        self.assertEqual(w.VIEW_FLAGS.get('show_order_numbers'), 'direction_numbers')
        self.numbers(False)
        st = w._view_state()
        self.assertIs(st['flags']['show_order_numbers'], False)
        self.numbers(True)
        w._apply_view_state(st)                                                # l'onglet repris : caché
        self.assertFalse(w.canvas.show_order_numbers)
        self.assertFalse(w.A['direction_numbers'].isChecked())


class Painting(Base):
    def test_numbers_hidden_colors_kept(self):
        on = self.grab()
        self.numbers(False)
        off = self.grab()
        boxes = self.boxes()
        self.assertEqual(len(boxes), 3)
        diff = [(x, y) for x in range(on.width()) for y in range(on.height()) if on.pixel(x, y) != off.pixel(x, y)]
        self.assertGreater(len(diff), 10, BEFORE)                              # les rangs ôtés
        outside = [(x, y) for x, y in diff if not any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in boxes)]
        self.assertEqual(outside, [])                                          # rien d'autre : couleurs inchangées
        for x0, y0, x1, y1 in boxes:                                           # chaque rang ôté
            self.assertTrue(any(x0 <= x <= x1 and y0 <= y <= y1 for x, y in diff))

    def test_no_numbers_painted_when_off(self):
        c = self.w.canvas
        with mock.patch.object(type(c), '_paint_directions') as paint:
            self.grab()
            self.assertTrue(paint.called)
            paint.reset_mock()
            self.numbers(False)
            self.grab()
            self.assertFalse(paint.called, BEFORE)

    def test_without_ctrl7_nothing_changes(self):
        on = self.grab(direction=False)
        self.numbers(False)
        off = self.grab(direction=False)
        self.assertTrue(on == off)
        self.numbers(True)
        self.grab(direction=True)

    def test_selection_order_numbers(self):
        c = self.w.canvas
        c.select([self.items[2], self.items[0]])                               # rang de la sélection
        on = self.grab()
        self.numbers(False)
        off = self.grab()
        self.assertFalse(on == off)
        c.select([])


class ContextMenu(Base):
    def test_direction_button_menu(self):
        w = self.w
        m = self.menu_of('direction')
        self.assertIn(w.A['direction_numbers'], m.actions(), BEFORE)          # la même commande, cochée
        self.assertTrue(w.A['direction_numbers'].isChecked())
        w.A['direction_numbers'].trigger()                                     # décochée depuis le menu
        self.assertFalse(w.canvas.show_order_numbers)
        m.deleteLater()

    def test_other_buttons_without(self):
        w = self.w
        for key in ('fill', 'grid'):
            m = self.menu_of(key)
            self.assertNotIn(w.A['direction_numbers'], m.actions())
            m.deleteLater()


if __name__ == '__main__':
    unittest.main()
