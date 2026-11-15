"""Round 934 : glisser la sélection du dessin dans la Bibliothèque — un déplacement qui sort de la vue et arrive sur une
Bibliothèque montrée devient un glisser-déposer ; lâchée sur la liste : ajoutée au dossier affiché ; sur un dossier : à
ce dossier (pas sur Récents ni Favoris) ; revenue dans la vue : déplacée là (Maj : copie). Ailleurs hors de la vue : le
déplacement comme avant."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r934.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QMimeData, QPoint, QPointF, QSettings, Qt
from PySide6.QtGui import QDrag, QDragEnterEvent, QDropEvent, QMouseEvent
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Shape  # noqa: E402


def mime():
    from vectordrive.ui.canvas import SELECTION_MIME, selection_token
    m = QMimeData()
    m.setData(SELECTION_MIME, selection_token())
    return m


def drop(widget, pos=QPointF(5, 5), data=None, mods=Qt.KeyboardModifier.NoModifier):
    data = data or mime()                                                     # gardées en vie le temps de l'appel
    ev = QDropEvent(pos, Qt.DropAction.CopyAction, data, Qt.MouseButton.LeftButton, mods)
    widget.dropEvent(ev)
    app.processEvents()                                                       # l'ajout suit le glisser-déposer
    return ev.isAccepted()


def enter(widget):
    data = mime()
    ev = QDragEnterEvent(QPoint(5, 5), Qt.DropAction.CopyAction, data, Qt.MouseButton.LeftButton,
                         Qt.KeyboardModifier.NoModifier)
    widget.dragEnterEvent(ev)
    return ev.isAccepted()


def move_event(pos):
    return QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(pos), QPointF(pos), Qt.MouseButton.NoButton,
                       Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)


class Canvas(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.canvas import Canvas as C
        self.c = C()
        self.c.resize(800, 600)
        self.c.snap.enabled = False
        self.sh = Shape(path=geom.Path([geom.rect(0, 0, 20, 10)]))
        self.c.doc.add(self.sh)
        self.c.select([self.sh])
        self.addCleanup(self.c.deleteLater)

    def box(self, i=0):
        return self.c.doc.layers[0].items[i].path.bbox()                      # la forme du dessin (un déplacement la remplace)

    def start_move(self):
        start = self.c.to_screen(5, 5)
        self.c._drag = {'kind': 'move', 'start': start, 'delta': (0.0, 0.0), 'grab': self.c.to_doc(start),
                        'was_selected': True, 't0': 0.0, 'armed': True}
        return start

    def test_reaching_a_library_starts_a_drag(self):
        seen = []
        self.c.drag_out_ok = lambda gp: seen.append(gp) or True
        self.start_move()
        with mock.patch.object(QDrag, 'exec', return_value=Qt.DropAction.CopyAction) as run:
            self.c.mouseMoveEvent(move_event(QPoint(900, 300)))             # hors de la vue, sur la Bibliothèque
        run.assert_called_once()
        self.assertEqual(len(seen), 1)                                        # le point écran demandé
        self.assertIsNone(self.c._drag)
        self.assertEqual(tuple(self.box()[:2]), (0, 0))                       # rien n'a bougé
        self.assertIsNone(self.c._out_grab)
        self.c.drag_out_ok = lambda gp: False                                 # ailleurs (règle, hors de la fenêtre…)
        start = self.start_move()
        with mock.patch.object(QDrag, 'exec') as run:
            self.c.mouseMoveEvent(move_event(QPoint(int(start.x()) + 900, int(start.y()))))
        run.assert_not_called()
        self.assertGreater(self.c._drag['delta'][0], 100)                    # le déplacement continue

    def test_back_in_the_view_moves_or_copies_there(self):
        self.c.drag_out_ok = lambda gp: True
        start = self.start_move()
        self.c.drag_selection_out(self.c._drag, exec_drag=False)
        self.assertTrue(enter(self.c))
        self.assertTrue(drop(self.c, QPointF(start.x() + 30 * self.c.scale, start.y())))
        x0, y0 = self.box()[:2]
        self.assertAlmostEqual(x0, 30, 6)
        self.assertAlmostEqual(y0, 0, 6)
        self.assertIsNone(self.c._out_grab)
        drop(self.c, QPointF(start.x() + 60 * self.c.scale, start.y()))     # un dépôt d'ailleurs : rien
        self.assertAlmostEqual(self.box()[0], 30, 6)
        self.start_move()
        self.c.drag_selection_out(self.c._drag, exec_drag=False)
        drop(self.c, QPointF(start.x() + 50 * self.c.scale, start.y()), mods=Qt.KeyboardModifier.ShiftModifier)
        self.assertAlmostEqual(self.box()[0], 30, 6)                         # Maj : l'original reste
        self.assertEqual(len(self.c.doc.layers[0].items), 2)                  # et une copie


class Library(unittest.TestCase):

    def test_list_and_folder_take_the_selection(self):
        from vectordrive.ui import symbols as SY
        s = QSettings(os.path.join(tempfile.mkdtemp(), 's.ini'), QSettings.Format.IniFormat)
        p = SY.SymbolPanel(s)
        self.addCleanup(p.deleteLater)
        self.assertTrue(p.list.acceptDrops())
        folder = pathlib.Path(tempfile.mkdtemp())
        (folder / 'Sous934').mkdir()
        p.show_folder(folder)
        got = []
        p.addSelectionRequested.connect(got.append)
        self.assertTrue(enter(p.list))
        self.assertTrue(drop(p.list))
        self.assertEqual(got, [p.target_folder()])
        self.assertEqual(pathlib.Path(got[0]), folder)
        with mock.patch.object(p.tree, '_target', return_value=str(folder / 'Sous934')):
            self.assertTrue(drop(p.tree))
        self.assertEqual(pathlib.Path(got[1]), folder / 'Sous934')
        for virtual in SY.VIRTUAL:                                            # Récents, Favoris : pas des dossiers
            with mock.patch.object(p.tree, '_target', return_value=virtual):
                self.assertFalse(drop(p.tree))
        other = QMimeData()
        other.setText('rien')
        self.assertFalse(drop(p.list, data=other))                            # autre chose : refusé, comme avant
        self.assertEqual(len(got), 2)

    def test_window_only_over_a_shown_library(self):
        from vectordrive.ui import main_window as MW
        w = MW.MainWindow()
        try:
            ok = w.canvas.drag_out_ok
            gp = QPoint(10, 10)
            self.assertTrue(callable(ok))
            with mock.patch.object(QApplication, 'widgetAt', return_value=w.symbols.list):
                with mock.patch.object(w.symbols, 'isVisible', return_value=True):
                    self.assertTrue(ok(gp))                                   # sur le panneau montré
                with mock.patch.object(w.symbols, 'isVisible', return_value=False):
                    self.assertFalse(ok(gp))
            with mock.patch.object(QApplication, 'widgetAt', return_value=w.canvas), \
                    mock.patch.object(w.symbols, 'isVisible', return_value=True):
                self.assertFalse(ok(gp))                                      # ailleurs : non
            w.library_window(show=False)
            big = w._library_window
            with mock.patch.object(QApplication, 'widgetAt', return_value=big.panel.list), \
                    mock.patch.object(type(big.panel), 'isVisible', return_value=True):
                self.assertTrue(ok(gp))
                with mock.patch.object(type(big), 'isMinimized', return_value=True):
                    self.assertFalse(ok(gp))                                  # réduite : non
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
