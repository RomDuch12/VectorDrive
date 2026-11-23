"""Round 1029 : demande du 15/11, 8 h 40 — clic droit sur un bouton du ruban : le placer dans les favoris, la barre
tout en haut (au-dessus du ruban, la première rangée en plein écran) ; retenu ; le même clic droit l'en retire."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1029.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtGui import QContextMenuEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QToolBar, QToolButton  # noqa: E402

app = QApplication.instance() or QApplication([])

ADD = 'Ajouter aux favoris (barre du haut)'
REMOVE = 'Retirer des favoris (barre du haut)'


def forget():
    from vectordrive import portable
    s = portable.settings()
    s.remove('ruban/favoris')
    s.remove('vue/mode')
    s.sync()


def window():
    from vectordrive.ui.main_window import MainWindow
    w = MainWindow()
    w.settings.setValue('fenetre/plein_ecran', False)
    w.show()
    app.processEvents()
    return w


def close(w):
    from shiboken6 import isValid
    if not isValid(w):
        return
    w.modified = False
    for t in getattr(w, 'docks', []):
        t.modified = False
    w.close()
    app.processEvents()


def ribbon_button(w, key):
    return next(b for b in w.ribbon.findChildren(QToolButton) if b.defaultAction() is w.A[key])


def menu_texts(w, b):
    m = w._ribbon_button_menu(b, QPoint(0, 0), exec_menu=False)
    return {a.text(): a for a in m.actions() if a.text()}, m


class Favorites(unittest.TestCase):

    def setUp(self):
        forget()
        self.addCleanup(forget)

    def test_right_click_adds_to_the_top_bar_kept_at_relaunch(self):
        w = window()
        self.addCleanup(close, w)
        box = w.menuWidget().layout()
        self.assertEqual(box.count(), 1)                                      # sans favoris : pas de barre
        acts, m = menu_texts(w, ribbon_button(w, 'zoom_fit'))
        self.addCleanup(m.deleteLater)
        self.assertIn(ADD, acts)
        acts[ADD].trigger()
        bar = w.fav_bar
        self.assertIsInstance(bar, QToolBar)
        self.assertIs(box.itemAt(0).widget(), bar)                            # tout en haut, au-dessus du ruban
        self.assertLess(box.indexOf(bar), box.indexOf(w.ribbon))
        self.assertIn(w.A['zoom_fit'], bar.actions())
        self.assertEqual(w.favorite_keys(), ['zoom_fit'])
        self.assertFalse(w.add_favorite('zoom_fit'))                          # pas deux fois
        self.assertTrue(w.add_favorite('undo'))
        self.assertEqual(bar.actions(), [w.A['zoom_fit'], w.A['undo']])       # dans l'ordre d'ajout
        w.settings.sync()
        close(w)
        w = window()                                                          # au lancement suivant
        self.addCleanup(close, w)
        self.assertEqual(w.fav_bar.actions(), [w.A['zoom_fit'], w.A['undo']])

    def test_right_click_on_a_favorite_removes_it(self):
        w = window()
        self.addCleanup(close, w)
        w.add_favorite('zoom_fit')
        b = next(x for x in w.fav_bar.findChildren(QToolButton) if x.defaultAction() is w.A['zoom_fit'])
        ev = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(2, 2), b.mapToGlobal(QPoint(2, 2)))
        with mock.patch.object(type(w), '_ribbon_button_menu') as bm:
            self.assertTrue(w.eventFilter(b, ev))                             # le menu du ruban, sur les favoris
            bm.assert_called_once()
        acts, m = menu_texts(w, b)
        self.addCleanup(m.deleteLater)
        self.assertNotIn(ADD, acts)
        acts[REMOVE].trigger()
        self.assertEqual(w.favorite_keys(), [])
        self.assertIsNone(w.fav_bar)                                          # plus de favoris : plus de barre
        self.assertEqual(w.menuWidget().layout().count(), 1)

    def test_shape_tool_keeps_its_settings_and_shift_gives_the_menu(self):
        w = window()
        self.addCleanup(close, w)
        rect = next((b for b in w.ribbon.findChildren(QToolButton) if b.defaultAction() is w.A.get('tool_rect')),
                    None)
        if rect is None:
            self.skipTest('pas de bouton Rectangle dans ce ruban')
        acts, m = menu_texts(w, rect)                                         # Maj + clic droit : ce menu
        self.addCleanup(m.deleteLater)
        self.assertIn(ADD, acts)
        at = QPoint(2, 2)
        plain = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, at, rect.mapToGlobal(at))
        with mock.patch.object(type(w), 'tool_form_dialog') as fd, \
                mock.patch.object(type(w), '_ribbon_button_menu') as bm:
            self.assertTrue(w.eventFilter(rect, plain))                       # clic droit : le menu, ses réglages
            bm.assert_called_once()                                           # en tête (round 1141)
            fd.assert_not_called()
            self.assertIsNotNone(bm.call_args.kwargs['settings'])
        shift = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, at, rect.mapToGlobal(at),
                                  Qt.KeyboardModifier.ShiftModifier)
        with mock.patch.object(type(w), 'tool_form_dialog') as fd, \
                mock.patch.object(type(w), '_ribbon_button_menu') as bm:
            self.assertTrue(w.eventFilter(rect, shift))                       # Maj + clic droit : le menu
            bm.assert_called_once()
            fd.assert_not_called()

    def test_an_absent_command_stays_in_the_favorites(self):
        w = window()
        self.addCleanup(close, w)
        w.settings.setValue('ruban/favoris', ['plugin_absent', 'undo'])        # un plugin pas chargé aujourd'hui
        self.assertEqual(w.favorite_keys(), ['undo'])
        w.add_favorite('zoom_fit')
        self.assertEqual(w._stored_favorites(), ['plugin_absent', 'undo', 'zoom_fit'])   # pas perdu

    def test_after_the_typeedit_quick_bar_without_duplicates(self):
        w = window()
        self.addCleanup(close, w)
        te = QToolBar('Accès rapide')                                         # comme celle de TypeEdit 13
        te.addAction(w.A['undo'])
        w.menuWidget().layout().insertWidget(0, te)
        w.te_quickbar = te
        w.add_favorite('undo')
        w.add_favorite('zoom_fit')
        self.assertIsNone(w.fav_bar)                                          # pas de 2e barre
        acts = [a for a in te.actions() if not a.isSeparator()]
        self.assertEqual(acts, [w.A['undo'], w.A['zoom_fit']])               # rien en double
        b = next(x for x in te.findChildren(QToolButton) if x.defaultAction() is w.A['zoom_fit'])
        self.assertTrue(w._is_favorite_button(b))
        u = next(x for x in te.findChildren(QToolButton) if x.defaultAction() is w.A['undo'])
        self.assertTrue(w._is_favorite_button(u))                             # déjà là, et favori : son menu
        w.remove_favorite('zoom_fit')
        w.remove_favorite('undo')
        self.assertEqual([a for a in te.actions() if not a.isSeparator()], [w.A['undo']])
        self.assertEqual([a for a in te.actions() if a.isSeparator()], [])
        w.te_quickbar = None
        te.setParent(None)
        te.deleteLater()


if __name__ == '__main__':
    unittest.main()
