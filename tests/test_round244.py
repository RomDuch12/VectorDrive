"""Round 244 : Mode Point — rectangle de sélection des points de la forme
active, « Tout sélectionner » = tous ses points, congés (K) sur les points
choisis ; ruban : un long groupe passe en petits boutons sur trois rangées
avant de se replier (le Mode Point de TypeEdit tient en entier)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QAction, QMouseEvent
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


def mouse(kind, pos, mods=Qt.KeyboardModifier.NoModifier):
    return QMouseEvent(kind, QPointF(pos), QPointF(pos), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, mods)


class TestNodeBand(unittest.TestCase):
    def setUp(self):
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.resize(1200, 800)
        self.sh = Shape(path=geom.Path([geom.rect(0, 0, 40, 20)]))
        self.w.canvas.doc.layers[0].items.append(self.sh)
        self.w.canvas.select([self.sh])
        self.w.set_tool('node')
        self.w.canvas.zoom_fit() if hasattr(self.w.canvas, 'zoom_fit') else None
        self.tool = self.w.canvas.tool_obj

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_band_and_select_all(self):
        c, t = self.w.canvas, self.tool
        a = c.to_screen(-5, -5)
        b = c.to_screen(20, 25)                                   # les deux points de gauche
        t.press(a, c.to_doc(a), mouse(QEvent.Type.MouseButtonPress, a))
        t.move(b, c.to_doc(b), mouse(QEvent.Type.MouseMove, b))
        self.assertIsNotNone(t.band)
        t.release(b, c.to_doc(b), mouse(QEvent.Type.MouseButtonRelease, b))
        self.assertIsNone(t.band)
        pts = sorted(tuple(round(v, 6) for v in __import__('vectordrive.core.nodes', fromlist=['x']).node_point(
            self.sh.path.contours[ci], k)) for ci, k in t.sel)
        self.assertEqual(pts, [(0.0, 0.0), (0.0, 20.0)])
        # Maj : ajoute
        a2, b2 = c.to_screen(35, -5), c.to_screen(45, 5)
        shift = Qt.KeyboardModifier.ShiftModifier
        t.press(a2, c.to_doc(a2), mouse(QEvent.Type.MouseButtonPress, a2, shift))
        t.release(b2, c.to_doc(b2), mouse(QEvent.Type.MouseButtonRelease, b2, shift))
        self.assertEqual(len(t.sel), 3)
        self.w.select_all()                                       # Ctrl+A (jeu de l'atelier)
        self.assertEqual(len(t.sel), 4)
        self.assertEqual(c.selection, [self.sh])                  # la forme reste la seule sélection

    def test_fillet_selected_nodes(self):
        from unittest import mock
        from vectordrive.ui import dialogs
        t = self.tool
        t.sel = {(0, 0)}
        n_before = len(self.sh.path.contours[0].segments)
        with mock.patch.object(dialogs.CornerDialog, 'exec', lambda d: 1), \
                mock.patch.object(dialogs.CornerDialog, 'value', lambda d: 3.0):
            self.w.corner_dialog('fillet')                        # K (TypeEdit)
        self.assertEqual(len(self.sh.path.contours[0].segments), n_before + 1)   # un arc de plus


class TestCompactGroup(unittest.TestCase):
    def test_long_group_compacts_before_folding(self):
        from vectordrive.ui.ribbon import Ribbon
        r = Ribbon()
        page = r.add_tab('Essai')
        g = page.group('Mode Point')
        from vectordrive.ui.icons import icon
        acts = [QAction(icon('node'), f'Cmd {i}', r) for i in range(30)]
        for a in acts:
            g.add(a, big=True)
        r.configure(labels=False)                                # icônes seules (essai sans polices)
        g.set_collapsed(False)
        g.set_compact(False)
        full = g.expanded_width()
        g.set_compact(True)
        small = g.expanded_width()
        g.set_compact(False)
        self.assertLess(small, full / 2)
        page.fit((full + small) // 2)
        self.assertTrue(g.compact)
        self.assertFalse(g.collapsed)                             # pas replié en un seul bouton
        self.assertLess(g.expanded_width(), full)
        self.assertEqual(len(g.buttons()), 30)
        page.fit(full + 100)
        self.assertFalse(g.compact)                               # la place revenue : grands boutons
        page.fit(60)
        self.assertTrue(g.collapsed)                              # vraiment trop étroit : famille
        r.deleteLater()


if __name__ == '__main__':
    unittest.main()
