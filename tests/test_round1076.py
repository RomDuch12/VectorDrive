"""Round 1076 : demande du 17/11 soir — « Panneau couleur : double clic sur la couleur ouvre une fenetre de selection
beaucoup plus avancee que l'actuelle » (réponse : roue + curseurs RVB, TSV, CMJN, hexadécimal, aperçu avant/après)."""
import importlib.util
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1076.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QCoreApplication, QEvent  # noqa: E402
from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Shape  # noqa: E402

BEFORE = 'avant : la fenêtre de couleur de Qt (QColorDialog), et rien au double clic dans le panneau Couleur'


def flush():
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


def spins(p, group):
    from vectordrive.ui.color_picker import CHANNELS
    return tuple(p.spins[(group, k)].value() for k, *_ in CHANNELS[group])


class Picker(unittest.TestCase):

    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('vectordrive.ui.color_picker'), BEFORE)
        from vectordrive.ui.color_picker import ColorPicker
        self.p = ColorPicker('#336699', None, 'essai')
        self.addCleanup(self.p.deleteLater)

    def test_every_view_follows_the_colour(self):
        p = self.p
        self.assertEqual(p.name(), '#336699')
        self.assertEqual(spins(p, 'rvb'), (0x33, 0x66, 0x99))
        self.assertEqual(spins(p, 'tsv'), (210, 67, 60))
        self.assertEqual(spins(p, 'cmjn'), (67, 33, 0, 40))
        self.assertEqual(p.hex.text(), '#336699')
        self.assertEqual(p.sliders[('rvb', 'g')].value(), 0x66)              # le curseur et son champ ensemble
        self.assertIn('#336699', p.new_lbl.text())

    def test_each_input_changes_the_colour(self):
        p = self.p
        p.spins[('rvb', 'r')].setValue(255)                                 # RVB
        self.assertEqual(p.name(), '#ff6699')
        self.assertEqual(p.hex.text(), '#ff6699')
        self.assertEqual(p.sliders[('rvb', 'r')].value(), 255)
        p.sliders[('tsv', 'h')].setValue(120)                                # TSV
        self.assertEqual(spins(p, 'tsv')[0], 120)
        self.assertEqual(p.color().hue(), 120)
        p.hex.setText('#0f0')                                                # hexadécimal court
        p.hex.textEdited.emit('#0f0')
        self.assertEqual(p.name(), '#00ff00')
        p.hex.textEdited.emit('12345')                                       # incomplet : rien
        self.assertEqual(p.name(), '#00ff00')
        p.spins[('cmjn', 'k')].setValue(100)                                 # CMJN : le noir
        self.assertEqual(p.name(), '#000000')
        p.spins[('cmjn', 'k')].setValue(0)                                   # la teinte gardée au retour du noir
        self.assertEqual(p.color().hue(), 120)
        p.set_color('#123456')                                               # pas de dérive d'arrondi : les
        h, sat, v = p.h, p.s, p.v                                            # autres valeurs restent exactes
        p.spins[('tsv', 'h')].setValue(p.spins[('tsv', 'h')].value() + 1)
        self.assertEqual((p.s, p.v), (sat, v))
        p.set_color('#123456')
        p.spins[('rvb', 'b')].setValue(0x57)
        p.spins[('rvb', 'b')].setValue(0x56)
        self.assertEqual(p.name(), '#123456')
        c0 = QColor('#123456').getCmykF()
        p.spins[('cmjn', 'k')].setValue(p.spins[('cmjn', 'k')].value() + 1)
        c1 = p.color().getCmykF()
        for a, b in zip(c0[:3], c1[:3]):
            self.assertAlmostEqual(a, b, delta=0.006)                        # C, M, J non arrondis au pour cent

    def test_wheel_and_value_bar(self):
        p = self.p
        p.resize(600, 400)
        p.show()
        flush()
        w = p.wheel
        pt = w.point_of(200.0, 0.5)
        h, s = w.hs_at(pt.x(), pt.y())
        self.assertAlmostEqual(h, 200.0, places=6)
        self.assertAlmostEqual(s, 0.5, places=6)
        self.assertAlmostEqual(w.hs_at(-500, w.height() / 2)[1], 1.0)        # hors de la roue : sur le bord
        w.picked.emit(0.0, 1.0)                                              # un clic sur la roue
        self.assertEqual(p.color().hue(), 0)
        self.assertEqual(spins(p, 'tsv')[1], 100)
        b = p.bar
        self.assertAlmostEqual(b.value_at(0), 1.0)
        self.assertAlmostEqual(b.value_at(b.height() + 50), 0.0)
        b.picked.emit(0.5)
        self.assertEqual(spins(p, 'tsv')[2], 50)
        p.grab()                                                             # le dessin ne lève pas d'erreur
        p.hide()

    def test_before_after(self):
        p = self.p
        p.set_color('#ffffff')
        self.assertEqual(p.name(), '#ffffff')
        p.old_btn.click()                                                    # « Avant » : la couleur de départ
        self.assertEqual(p.name(), '#336699')
        self.assertIn('#336699', p.old_btn.styleSheet())


class GetColor(unittest.TestCase):

    def test_ok_cancel_and_no_dialog_left(self):
        from vectordrive.ui import color_picker as CP
        old = CP.ColorPicker.exec

        def ok(self):
            self.set_color('#abcdef')
            return QDialog.DialogCode.Accepted
        try:
            CP.ColorPicker.exec = ok
            self.assertEqual(CP.get_color('#000000').name(), '#abcdef')
            CP.ColorPicker.exec = lambda self: QDialog.DialogCode.Rejected
            self.assertIsNone(CP.get_color(QColor('red')))
        finally:
            CP.ColorPicker.exec = old
        flush()
        self.assertFalse([w for w in app.topLevelWidgets() if isinstance(w, CP.ColorPicker)])
        p = CP.ColorPicker('pas une couleur')                                # couleur illisible : le noir
        self.addCleanup(p.deleteLater)
        self.assertEqual(p.name(), '#000000')


class Uses(unittest.TestCase):
    """Le panneau Couleur (double clic, clic droit), le tableau des outils, Édition › Couleur… ouvrent le sélecteur."""

    def setUp(self):
        from vectordrive.ui import color_picker as CP
        self.CP = CP
        self.asked = []
        old = CP.get_color

        def fake(initial, parent=None, title=''):
            self.asked.append((QColor(initial).name(), title))
            return QColor('#123456')
        CP.get_color = fake
        self.addCleanup(setattr, CP, 'get_color', old)

    def test_double_click_in_the_colour_panel(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        self.addCleanup(self.close, w)
        w.canvas.doc.add(Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]), tool=1))
        p = w.color_panel
        p.sync(force=True)
        item = next(p.list.item(k) for k in range(p.list.count()) if int(p.list.item(k).data(256)) == 1)
        before = w.canvas.doc.tools[1].color
        p.list.itemDoubleClicked.emit(item)
        self.assertEqual(w.canvas.doc.tools[1].color, '#123456', BEFORE)
        self.assertEqual(self.asked[-1][0], QColor(before).name())          # la fenêtre part de la couleur de l'outil
        self.assertIn('1', self.asked[-1][1])
        w.undo()                                                             # un pas d'annulation
        self.assertEqual(w.canvas.doc.tools[1].color, before)
        self.assertIn('double clic', p.list.toolTip())

    def test_real_mouse_double_click_and_single_click(self):
        """Avec de vrais événements souris : le double clic ouvre la fenêtre sans recolorer la sélection ; le simple
        clic recolore après la durée d'un double clic."""
        from PySide6.QtCore import QElapsedTimer, Qt
        from PySide6.QtTest import QTest
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        self.addCleanup(self.close, w)
        s = Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]), tool=0)
        w.canvas.doc.add(s)
        w.canvas.selection = [s]
        w.dock_color.show()
        w.show()
        app.processEvents()
        p = w.color_panel
        p.sync(force=True)
        row = next(k for k in range(p.list.count()) if int(p.list.item(k).data(256)) == 2)
        pos = p.list.visualItemRect(p.list.item(row)).center()
        vp = p.list.viewport()
        L, N = Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier
        QTest.mouseClick(vp, L, N, pos)                                     # la suite d'un vrai double clic
        QTest.mouseDClick(vp, L, N, pos)
        QTest.mouseRelease(vp, L, N, pos)
        app.processEvents()
        self.assertEqual(len(self.asked), 1, 'le double clic ouvre la fenêtre')
        self.assertEqual(w.canvas.doc.tools[2].color, '#123456')
        t = QElapsedTimer()
        t.start()
        while t.elapsed() < QApplication.doubleClickInterval() + 200:
            app.processEvents()
        self.assertEqual(s.tool, 0, 'le double clic ne recolore pas la sélection')
        row = next(k for k in range(p.list.count()) if int(p.list.item(k).data(256)) == 3)
        pos = p.list.visualItemRect(p.list.item(row)).center()
        QTest.mouseClick(p.list.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
        t.restart()
        while t.elapsed() < QApplication.doubleClickInterval() + 200 and s.tool != 3:
            app.processEvents()
        self.assertEqual(s.tool, 3, 'le simple clic recolore')
        self.assertEqual(len(self.asked), 1)

    def test_tools_table_and_selection_colour(self):
        from vectordrive.core.document import Tool
        from vectordrive.ui.layers import ToolsDialog
        d = ToolsDialog([Tool(0, '#ff0000', 'Rouge', 0.0), Tool(1, '#00ff00', 'Vert', 0.0)])
        self.addCleanup(d.deleteLater)
        d._pick(1, 2)
        self.assertEqual(self.asked[-1][0], '#00ff00')
        self.assertEqual(d.tools()[1].color, '#123456')
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        self.addCleanup(self.close, w)
        s = Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]), tool=0)
        w.canvas.doc.add(s)
        w.canvas.selection = [s]
        self.assertEqual(w.set_selection_color(ask=True), 1)
        from vectordrive.core.document import own_color
        self.assertEqual(own_color(s), '#123456')

    @staticmethod
    def close(w):
        w.modified = False
        w.close()
        w.deleteLater()
        app.processEvents()


if __name__ == '__main__':
    unittest.main()
