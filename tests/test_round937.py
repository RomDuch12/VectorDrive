"""Round 937 : corrections de relecture (rounds 932 à 934) — la sélection lâchée sur la liste de la Bibliothèque
arrive (événements acheminés comme Qt le fait : à la fenêtre, puis au widget sous le point qui accepte les dépôts) ;
le glisser part aussi par-dessus la vue ; celui d'une autre instance est refusé ; curseurs de copie et de déplacement ;
repère d'accrochage ; dossier illisible ; fichier des associations dans un autre codage."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r937.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QEvent, QMimeData, QPoint, QPointF, QSettings, Qt
from PySide6.QtGui import QDrag, QDragEnterEvent, QDragLeaveEvent, QDragMoveEvent, QDropEvent, QMouseEvent
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Shape  # noqa: E402

BOTH = Qt.DropAction.CopyAction | Qt.DropAction.MoveAction
NONE = Qt.KeyboardModifier.NoModifier
LEFT = Qt.MouseButton.LeftButton


def mime(token=None):
    from vectordrive.ui import canvas as CV
    m = QMimeData()
    own = getattr(CV, 'selection_token', lambda: b'1')()                      # avant ce round : sans instance
    m.setData(CV.SELECTION_MIME, own if token is None else token)
    return m


def routed_drop(widget, local=QPoint(40, 40), data=None, mods=NONE):
    """Le glisser-déposer comme Qt l'achemine : les événements vont à la fenêtre, qui les donne au widget sous le
    point qui accepte les dépôts. Rend (entrée acceptée, dépôt accepté, action du dépôt)."""
    data = data or mime()                                                     # gardées en vie le temps de l'appel
    win = widget.window()
    handle = win.windowHandle()
    assert handle is not None, 'fenêtre non montrée'
    pos = widget.mapTo(win, local)
    enter = QDragEnterEvent(pos, BOTH, data, LEFT, mods)
    QApplication.sendEvent(handle, enter)
    move = QDragMoveEvent(pos, BOTH, data, LEFT, mods)
    QApplication.sendEvent(handle, move)
    if not move.isAccepted():
        QApplication.sendEvent(handle, QDragLeaveEvent())
        return enter.isAccepted(), False, None
    ev = QDropEvent(QPointF(pos), BOTH, data, LEFT, mods)
    QApplication.sendEvent(handle, ev)
    app.processEvents()                                                       # l'ajout suit le glisser-déposer
    return enter.isAccepted(), ev.isAccepted(), ev.dropAction()


class Library(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui import symbols as SY
        s = QSettings(os.path.join(tempfile.mkdtemp(), 's.ini'), QSettings.Format.IniFormat)
        self.p = SY.SymbolPanel(s)
        self.p.resize(600, 500)
        self.p.show()
        app.processEvents()
        self.addCleanup(self.p.deleteLater)
        self.addCleanup(self.p.close)
        self.folder = pathlib.Path(tempfile.mkdtemp())
        (self.folder / 'Sous937').mkdir()
        self.p.show_folder(self.folder)
        app.processEvents()
        self.got = []
        self.p.addSelectionRequested.connect(self.got.append)

    def test_the_drop_reaches_the_list(self):
        self.assertTrue(self.p.list.viewport().acceptDrops())                 # avant : faux (setMovement(Static))
        entered, dropped, action = routed_drop(self.p.list.viewport())
        self.assertTrue(entered)                                              # avant : curseur d'interdiction
        self.assertTrue(dropped)
        self.assertEqual(action, Qt.DropAction.CopyAction)
        self.assertEqual([pathlib.Path(f) for f in self.got], [self.folder])

    def test_the_drop_reaches_a_folder_of_the_tree_as_a_copy(self):
        with mock.patch.object(self.p.tree, '_target', return_value=str(self.folder / 'Sous937')):
            entered, dropped, action = routed_drop(self.p.tree.viewport(), QPoint(20, 20),
                                                   mods=Qt.KeyboardModifier.ShiftModifier)
        self.assertTrue(entered and dropped)
        self.assertEqual(action, Qt.DropAction.CopyAction)                    # avant : Maj proposait « déplacer »
        self.assertEqual([pathlib.Path(f) for f in self.got], [self.folder / 'Sous937'])

    def test_a_drag_from_another_instance_is_refused(self):
        other = mime(b'999999999')                                            # le glisser d'une autre instance
        entered, dropped, _a = routed_drop(self.p.list.viewport(), data=other)
        self.assertFalse(entered or dropped)
        with mock.patch.object(self.p.tree, '_target', return_value=str(self.folder / 'Sous937')):
            entered, dropped, _a = routed_drop(self.p.tree.viewport(), QPoint(20, 20), data=other)
        self.assertFalse(dropped)                                             # avant : sa propre sélection enregistrée
        self.assertEqual(self.got, [])

    def test_an_unreadable_folder_is_no_target_at_all(self):
        self.assertEqual(self.p.target_folder(), self.folder)
        self.p.show_folder(self.folder / 'disparu937')
        self.assertIsNone(self.p.target_folder())                             # avant : le dossier de l'arbre, ou le premier
        self.p.show_folder(self.folder)
        self.assertEqual(self.p.target_folder(), self.folder)


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

    def start_move(self):
        start = self.c.to_screen(5, 5)
        self.c._drag = {'kind': 'move', 'start': start, 'delta': (0.0, 0.0), 'grab': self.c.to_doc(start),
                        'was_selected': True, 't0': 0.0, 'armed': True}
        return start

    def test_the_drag_starts_over_the_view_too(self):
        self.c.drag_out_ok = lambda gp: True                                  # la grande fenêtre recouvre la vue
        self.start_move()
        inside = QPointF(400, 300)
        ev = QMouseEvent(QEvent.Type.MouseMove, inside, inside, Qt.MouseButton.NoButton, LEFT, NONE)
        with mock.patch.object(QDrag, 'exec', return_value=Qt.DropAction.CopyAction) as run:
            self.c.mouseMoveEvent(ev)
        run.assert_called_once()                                              # avant : un déplacement sous la fenêtre
        self.assertIsNone(self.c._drag)

    def test_the_cursor_says_move_or_copy(self):
        self.start_move()
        self.c.drag_selection_out(self.c._drag, exec_drag=False)
        data = mime()
        for mods, want in ((NONE, Qt.DropAction.MoveAction),
                           (Qt.KeyboardModifier.ShiftModifier, Qt.DropAction.CopyAction)):
            for kind in (QDragEnterEvent, QDragMoveEvent):
                ev = kind(QPoint(300, 300), BOTH, data, LEFT, mods)
                (self.c.dragEnterEvent if kind is QDragEnterEvent else self.c.dragMoveEvent)(ev)
                self.assertTrue(ev.isAccepted())
                self.assertEqual(ev.dropAction(), want, (mods, kind))         # avant : l'inverse
        other = mime(b'999999999')
        ev = QDragMoveEvent(QPoint(300, 300), BOTH, other, LEFT, NONE)
        ev.ignore()
        self.c.dragMoveEvent(ev)
        self.assertFalse(ev.isAccepted())                                     # d'une autre instance : refusé

    def test_the_snap_mark_goes_when_the_drag_leaves(self):
        self.start_move()
        self.c._snap_hit = ('fin', (0.0, 0.0))
        self.c.drag_selection_out(self.c._drag, exec_drag=False)
        self.assertIsNone(self.c._snap_hit)                                   # avant : le repère restait dessiné


class Aliases(unittest.TestCase):

    def test_a_file_in_another_encoding_is_damaged_not_fatal(self):
        from vectordrive.cam import ncread
        folder = pathlib.Path(tempfile.mkdtemp())
        for name, raw in (('ansi.json', '{"associations": [], "note": "outil gravé"}'.encode('cp1252')),
                          ('utf16.json', '{"associations": []}'.encode('utf-16'))):
            p = folder / name
            p.write_bytes(raw)
            self.assertEqual(ncread.load_aliases(p), [])                      # avant : UnicodeDecodeError
            with self.assertRaises(ValueError):
                ncread.load_aliases(p, strict=True)
            self.assertEqual(ncread._aliases_to_rewrite(p), [])               # mis de côté, pas écrasé
            self.assertFalse(p.exists())
            self.assertTrue((folder / (p.stem + '.abime.json')).exists())


if __name__ == '__main__':
    unittest.main()
