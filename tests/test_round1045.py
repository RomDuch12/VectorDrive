"""Round 1045 : demande du 15/11, 20 h 50 — barre des favoris : clic droit sur un de ses boutons, « Afficher les
libellés » (retenu, toute la barre) et « Retirer des favoris » ; un mode d'agencement où l'on range les boutons en les
glissant à la souris ; l'ordre est retenu."""
import importlib.util
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1045.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QDropEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QToolBar, QToolButton  # noqa: E402

app = QApplication.instance() or QApplication([])

LABELS = 'Afficher les libellés'
ARRANGE = 'Agencer les favoris à la souris'
REMOVE = 'Retirer des favoris (barre du haut)'
DONE = 'Terminer l’agencement'
MIME = 'application/x-vectordrive-favorite'


def forget():
    from vectordrive import portable
    s = portable.settings()
    for k in ('ruban/favoris', 'ruban/favoris_libelles', 'vue/mode'):
        s.remove(k)
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
    bar = getattr(w, 'fav_bar', None)                    # avant 0.902.0 : la barre gardait ses commandes et sa
    if bar is not None and isValid(bar):                 # destruction faisait planter Python, une fois sur trois
        bar.clear()


def fav_button(w, key, bar=None):
    bar = bar or w.fav_bar
    return next(b for b in bar.findChildren(QToolButton) if b.defaultAction() is w.A[key] and b.isVisible())


def menu(w, b):
    m = w._ribbon_button_menu(b, QPoint(0, 0), exec_menu=False)
    return {a.text(): a for a in m.actions() if a.text()}, m


def drop(w, bar, key, x):
    """Un favori déposé en `x` sur la barre : l'événement passe par le filtre de l'agencement (hors d'un vrai glisser,
    Qt ne livre pas un dépôt envoyé à la main)."""
    mime = QMimeData()
    mime.setData(MIME, key.encode('utf-8'))
    ev = QDropEvent(QPointF(x, bar.height() / 2), Qt.DropAction.MoveAction, mime, Qt.MouseButton.LeftButton,
                    Qt.KeyboardModifier.NoModifier)
    arranger = getattr(w, '_fav_arranger', None)
    if arranger is not None:
        arranger.eventFilter(bar, ev)
    for _ in range(3):                                   # le rangement (au tour suivant), puis la barre refaite
        app.processEvents()
    return ev


class FavBar(unittest.TestCase):

    def setUp(self):
        forget()
        self.addCleanup(forget)

    def three(self):
        w = window()
        self.addCleanup(close, w)
        for k in ('zoom_fit', 'undo', 'redo'):
            w.add_favorite(k)
        app.processEvents()
        return w

    def test_right_click_menu_of_a_favorite(self):
        w = self.three()
        acts, m = menu(w, fav_button(w, 'undo'))
        self.addCleanup(m.deleteLater)
        self.assertIn(LABELS, acts, 'avant : pas de « Afficher les libellés »')
        self.assertIn(ARRANGE, acts)
        self.assertIn(REMOVE, acts)
        self.assertTrue(acts[LABELS].isCheckable() and acts[ARRANGE].isCheckable())
        self.assertFalse(acts[LABELS].isChecked())
        names = [a.text() for a in m.actions()]
        self.assertLess(names.index(ARRANGE), names.index(REMOVE))           # juste avant « Retirer »
        ribbon = next(b for b in w.ribbon.findChildren(QToolButton) if b.defaultAction() is w.A['undo'])
        racts, rm = menu(w, ribbon)                                          # sur le ruban : pas ces deux-là
        self.addCleanup(rm.deleteLater)
        self.assertNotIn(LABELS, racts)
        self.assertNotIn(ARRANGE, racts)

    def test_labels_for_the_whole_bar_kept(self):
        w = self.three()
        acts, m = menu(w, fav_button(w, 'zoom_fit'))
        self.addCleanup(m.deleteLater)
        self.assertIn(LABELS, acts, 'avant : pas de libellés')
        acts[LABELS].setChecked(True)
        app.processEvents()
        for k in ('zoom_fit', 'undo', 'redo'):
            self.assertEqual(fav_button(w, k).toolButtonStyle(), Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        ribbon = next(b for b in w.ribbon.findChildren(QToolButton) if b.defaultAction() is w.A['undo'])
        self.assertNotEqual(ribbon.toolButtonStyle(), Qt.ToolButtonStyle.ToolButtonTextBesideIcon)  # le ruban, non
        w.add_favorite('zoom_in' if 'zoom_in' in w.A else 'copy')           # barre refaite : toujours là
        app.processEvents()
        for b in w.fav_bar.findChildren(QToolButton):
            if b.defaultAction() is not None and b.isVisible():
                self.assertEqual(b.toolButtonStyle(), Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        w.settings.sync()
        close(w)
        w = window()                                                         # au lancement suivant
        self.addCleanup(close, w)
        self.assertEqual(fav_button(w, 'undo').toolButtonStyle(), Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        acts, m = menu(w, fav_button(w, 'undo'))
        self.addCleanup(m.deleteLater)
        self.assertTrue(acts[LABELS].isChecked())
        acts[LABELS].setChecked(False)
        app.processEvents()
        self.assertEqual(fav_button(w, 'undo').toolButtonStyle(), w.fav_bar.toolButtonStyle())

    def test_arrange_by_drag_and_drop_kept(self):
        w = self.three()
        self.assertIsNotNone(getattr(w, 'move_favorite', None), 'avant : pas de rangement des favoris')
        w.arrange_favorites(True)
        app.processEvents()
        bar = w.fav_bar
        self.assertTrue(bar.acceptDrops())
        self.assertIn(DONE, [a.text() for a in bar.actions()])
        fired = []
        w.A['zoom_fit'].triggered.connect(lambda *_: fired.append(1))
        QTest.mouseClick(fav_button(w, 'zoom_fit'), Qt.MouseButton.LeftButton)
        app.processEvents()
        self.assertEqual(fired, [])                                          # un appui ne lance pas la commande
        from PySide6.QtGui import QMouseEvent
        b = fav_button(w, 'undo')
        right = QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(3, 3), b.mapToGlobal(QPointF(3, 3)),
                            Qt.MouseButton.RightButton, Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier)
        self.assertFalse(w._fav_arranger.eventFilter(b, right))             # clic droit : laissé (menu des favoris)
        done = bar.widgetForAction(next(a for a in bar.actions() if a.text() == DONE))
        self.assertEqual(done.contextMenuPolicy(), Qt.ContextMenuPolicy.CustomContextMenu)
        drop(w, bar, 'redo', fav_button(w, 'zoom_fit').geometry().left() + 1)   # tout à gauche
        self.assertEqual(w.favorite_keys(), ['redo', 'zoom_fit', 'undo'])
        drop(w, w.fav_bar, 'redo', w.fav_bar.width() - 1)                    # au bout
        self.assertEqual(w.favorite_keys(), ['zoom_fit', 'undo', 'redo'])
        drop(w, w.fav_bar, 'undo', fav_button(w, 'zoom_fit').geometry().center().x() - 1)
        self.assertEqual(w.favorite_keys(), ['undo', 'zoom_fit', 'redo'])
        bar = w.fav_bar
        self.assertEqual([a for a in bar.actions() if a.text() != DONE][:3],
                         [w.A['undo'], w.A['zoom_fit'], w.A['redo']])
        self.assertTrue(fav_button(w, 'undo').property('vd_fav_arranging'))  # toujours en agencement
        w.arrange_favorites(False)
        app.processEvents()
        self.assertNotIn(DONE, [a.text() for a in w.fav_bar.actions()])
        self.assertFalse(w.fav_bar.acceptDrops())
        QTest.mouseClick(fav_button(w, 'zoom_fit'), Qt.MouseButton.LeftButton)
        app.processEvents()
        self.assertEqual(fired, [1])                                         # la commande, de nouveau
        w.settings.sync()
        close(w)
        w = window()
        self.addCleanup(close, w)
        self.assertEqual(w.favorite_keys(), ['undo', 'zoom_fit', 'redo'])   # ordre retenu
        self.assertEqual(w.fav_bar.actions(), [w.A['undo'], w.A['zoom_fit'], w.A['redo']])

    def test_menu_toggles_arranging_and_typeedit_bar(self):
        spec = importlib.util.find_spec('vectordrive.ui.fav_bar')
        self.assertIsNotNone(spec, 'avant : pas de module fav_bar')
        w = window()
        self.addCleanup(close, w)
        te = QToolBar('Accès rapide')                                        # comme celle de TypeEdit 13
        te.addAction(w.A['undo'])
        w.menuWidget().layout().insertWidget(0, te)
        w.te_quickbar = te
        self.addCleanup(lambda: (setattr(w, 'te_quickbar', None), te.setParent(None), te.deleteLater()))
        for k in ('undo', 'zoom_fit', 'redo'):
            w.add_favorite(k)
        app.processEvents()
        acts, m = menu(w, fav_button(w, 'zoom_fit', te))
        self.addCleanup(m.deleteLater)
        acts[ARRANGE].setChecked(True)                                       # le menu lance l'agencement
        app.processEvents()
        self.assertTrue(w._fav_arranging)
        self.assertTrue(fav_button(w, 'zoom_fit', te).property('vd_fav_arranging'))
        self.assertFalse(fav_button(w, 'undo', te).property('vd_fav_arranging'))   # de TypeEdit : reste en place
        drop(w, te, 'redo', fav_button(w, 'zoom_fit', te).geometry().left() + 1)
        self.assertEqual(w.favorite_keys(), ['undo', 'redo', 'zoom_fit'])
        acts = [a for a in te.actions() if not a.isSeparator() and a.text() != DONE]
        self.assertEqual(acts, [w.A['undo'], w.A['redo'], w.A['zoom_fit']])
        done = next(a for a in te.actions() if a.text() == DONE)
        done.trigger()                                                       # « Terminer l'agencement »
        app.processEvents()
        self.assertFalse(w._fav_arranging)
        self.assertNotIn(DONE, [a.text() for a in te.actions()])
        w.remove_favorite('redo')
        w.remove_favorite('zoom_fit')
        w.remove_favorite('undo')
        self.assertEqual([a for a in te.actions() if not a.isSeparator()], [w.A['undo']])


class Closing(unittest.TestCase):
    """La barre des favoris porte les commandes de la fenêtre : détruite avec elles, elle faisait planter Python, une
    fois sur trois environ (fin des essais, fin de l'application). À la fermeture, elle les rend."""

    def setUp(self):
        forget()
        self.addCleanup(forget)

    def test_the_bar_lets_go_of_the_commands_when_the_window_closes(self):
        from shiboken6 import isValid
        w = window()
        for k in ('zoom_fit', 'undo'):
            w.add_favorite(k)
        if hasattr(w, 'arrange_favorites'):
            w.arrange_favorites(True)                    # en plein agencement : rendu aussi
        app.processEvents()
        bar = w.fav_bar
        self.assertTrue(bar.actions())
        w.modified = False
        for t in getattr(w, 'docks', []):
            t.modified = False
        w.close()
        app.processEvents()
        left = list(bar.actions()) if isValid(bar) else []
        if isValid(bar):
            bar.clear()                                  # sans planter la suite, même avant
        self.assertEqual(left, [], 'avant : la barre gardait les commandes')
        self.assertEqual(w._stored_favorites(), ['zoom_fit', 'undo'])        # les favoris, eux, restent


if __name__ == '__main__':
    unittest.main()
