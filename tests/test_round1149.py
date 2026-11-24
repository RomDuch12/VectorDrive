"""Round 1149 (demande du 24/11) : « Outil lissage c-infini paramétrable »."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1149.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ.setdefault('VECTORDRIVE_KEYS_MEMORY', '1')

from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox, QToolButton  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : pas d’outil Lissage C∞ (seulement la commande Courbe lisse…, sur la sélection)'


def key(k):
    return QKeyEvent(QEvent.Type.KeyPress, k, Qt.KeyboardModifier.NoModifier)


class Smooth(unittest.TestCase):
    def setUp(self):
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        from vectordrive.ui.main_window import MainWindow
        self.w = w = MainWindow()
        if not w.docs:
            w.new_document()
        w.settings.remove('cad/courbe_lisse')
        self.addCleanup(w.settings.remove, 'cad/courbe_lisse')
        self.sq = Shape(path=geom.Path([geom.rect(0, 0, 20, 20)]), tool=1)
        self.other = Shape(path=geom.Path([geom.rect(40, 0, 20, 20)]), tool=1)
        w.canvas.doc.add(self.sq)
        w.canvas.doc.add(self.other)
        w.canvas.resize(800, 600)
        w.canvas.fit()
        w.canvas.invalidate()
        self.box = mock.patch.object(QMessageBox, 'information', side_effect=AssertionError('fenêtre'))
        self.box.start()
        self.addCleanup(self.box.stop)

    def tearDown(self):
        w = self.w
        w.set_tool('select')
        for t in w.docs:
            t.modified = False
        w.modified = False
        w.close()
        w.deleteLater()
        app.processEvents()

    def at(self, x, y):
        return self.w.canvas.to_screen(x, y) if hasattr(self.w.canvas, 'to_screen') else None

    def screen(self, x, y):
        from PySide6.QtCore import QPointF as P
        t = self.w.canvas.view()
        q = t.map(P(x, y))
        return QPointF(q.x(), q.y())

    def corners(self, shape):
        """Les tracés en Bézier de la forme : un carré lissé n'a plus que des courbes."""
        return [type(seg).__name__ for c in shape.path.contours for seg in c.segments]

    def test_tool_exists_next_to_smooth_curve(self):
        w = self.w
        self.assertIn('tool_smooth', w.A, BEFORE)
        self.assertIsNotNone(w._tool_settings(w.A['tool_smooth']))
        self.assertIsNotNone(w._tool_settings(w.A['smooth_curve']))
        btn = [b for b in w.ribbon.findChildren(QToolButton) if b.defaultAction() is w.A['tool_smooth']]
        self.assertTrue(btn)                                                # dans le ruban (groupe Contours)

    def test_hover_shows_and_click_smooths(self):
        from vectordrive.ui import tools as T
        w = self.w
        w.A['tool_smooth'].trigger()
        tool = w.canvas.tool_obj
        self.assertIsInstance(tool, T.SmoothTool)
        sp = self.screen(0.0, 10.0)                                         # sur le bord gauche du carré
        tool.move(sp, w.canvas.to_doc(sp), None)
        self.assertEqual(len(tool.shown), 1)                                # montré lissé
        n_undo = len(w._undo)
        tool.press(sp, w.canvas.to_doc(sp), None)
        top = [it for L in w.canvas.doc.layers for it in L.items]
        self.assertEqual(len(top), 2)
        smoothed = [it for it in top if it is not self.other]
        self.assertEqual(len(smoothed), 1)
        self.assertNotIn('Line', self.corners(smoothed[0]))                 # plus de segment droit : lissé
        self.assertIn(self.other, top)                                      # l'autre forme intacte
        self.assertEqual(len(w._undo), n_undo + 1)                          # un pas d'annulation
        self.assertIsInstance(w.canvas.tool_obj, T.SmoothTool)              # l'outil reste

    def test_click_on_selection_smooths_all(self):
        w = self.w
        w.canvas.select([self.sq, self.other])
        w.A['tool_smooth'].trigger()
        w.canvas.select([self.sq, self.other])
        tool = w.canvas.tool_obj
        sp = self.screen(0.0, 10.0)
        tool.press(sp, w.canvas.to_doc(sp), None)
        top = [it for L in w.canvas.doc.layers for it in L.items]
        self.assertTrue(all('Line' not in self.corners(it) for it in top))

    def test_keys_change_and_keep_the_settings(self):
        w = self.w
        w.A['tool_smooth'].trigger()
        tool = w.canvas.tool_obj
        self.assertTrue(tool.key(key(Qt.Key.Key_BracketRight)))
        self.assertAlmostEqual(tool.spec['length'], 2.5)
        self.assertTrue(tool.key(key(Qt.Key.Key_Tab)))
        self.assertEqual(tool.spec['sharpness'], 2.0)
        self.assertEqual(w.smooth_spec()['length'], 2.5)                    # retenus
        self.assertEqual(w.smooth_spec()['sharpness'], 2.0)
        for _ in range(3):
            tool.key(key(Qt.Key.Key_Tab))
        self.assertEqual(tool.spec['sharpness'], 1.0)                       # 4 puis 1

    def test_settings_by_right_click(self):
        w = self.w
        got = w.smooth_settings(params={'length': 5.0, 'sharpness': 9.0, 'tolerance': 0.0})
        self.assertEqual(got, {'length': 5.0, 'sharpness': 4.0, 'tolerance': 1e-4})
        self.assertEqual(w.smooth_spec(), got)
        w.A['tool_smooth'].trigger()
        self.assertEqual(w.canvas.tool_obj.spec['length'], 5.0)             # l'outil pris les suit
        w.smooth_settings(params={'length': 1.0, 'sharpness': 1.0, 'tolerance': 0.01})
        self.assertEqual(w.canvas.tool_obj.spec['length'], 1.0)             # … et l'outil en cours aussi
        self.assertEqual(self.corners(self.sq).count('Line'), 4)            # rien n'est lissé par les réglages

    def test_smooth_curve_dialog_still_works(self):
        w = self.w
        w.canvas.select([self.sq])
        worst = w.smooth_curve_dialog(params={'length': 2.0, 'sharpness': 1.0, 'tolerance': 0.01})
        self.assertIsNotNone(worst)
        self.assertGreater(worst, 0.0)

    def test_selection_kept_when_clicking_outside(self):
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        w = self.w
        third = Shape(path=geom.Path([geom.rect(0, 40, 20, 20)]), tool=1)
        w.canvas.doc.add(third)
        w.A['tool_smooth'].trigger()
        w.canvas.select([self.other, third])
        tool = w.canvas.tool_obj
        sp = self.screen(0.0, 10.0)                                         # le carré, hors de la sélection
        tool.press(sp, w.canvas.to_doc(sp), None)
        self.assertEqual(w.canvas.selection, [self.other, third])           # la sélection reste
        self.assertEqual(self.corners(self.other).count('Line'), 4)        # seul le carré cliqué est lissé

    def test_error_keeps_the_selection(self):
        w = self.w
        w.A['tool_smooth'].trigger()
        w.canvas.select([self.other])
        tool = w.canvas.tool_obj
        sp = self.screen(0.0, 10.0)
        with mock.patch.object(w, '_smooth_selection', side_effect=ValueError('dégénéré')):
            tool.press(sp, w.canvas.to_doc(sp), None)                       # attrapée, dite
        self.assertEqual(w.canvas.selection, [self.other])

    def test_groups_texts_images_untouched(self):
        from vectordrive.core.document import Group
        w = self.w
        L = w.canvas.doc.active_layer
        L.items = [it for it in L.items if it is not self.sq]
        g = Group(children=[self.sq])
        L.items.append(g)
        w.canvas.invalidate()
        w.A['tool_smooth'].trigger()
        tool = w.canvas.tool_obj
        sp = self.screen(0.0, 10.0)
        tool.move(sp, w.canvas.to_doc(sp), None)
        self.assertEqual(tool.shown, [])                                    # un groupe : rien de montré
        n = len(w._undo)
        tool.press(sp, w.canvas.to_doc(sp), None)
        self.assertEqual(len(w._undo), n)                                   # … ni de changé
        self.assertIn(g, L.items)

    def test_derived_data_dropped(self):
        w = self.w
        self.sq.extra = {'start_xy': [[0.0, 0.0]], 'vnd_obj': {'x': 1}, 'garde': 1}
        w.canvas.select([self.sq])
        w.smooth_curve_dialog(params={'length': 2.0, 'sharpness': 1.0, 'tolerance': 0.01})
        new = w.canvas.selection[0]
        self.assertEqual(new.extra, {'garde': 1})
        self.assertIn('vnd_obj', self.sq.extra)                             # l'original (annulation) intact

    def test_long_preview_skipped(self):
        from vectordrive.ui import tools as T
        w = self.w
        w.A['tool_smooth'].trigger()
        tool = w.canvas.tool_obj
        with mock.patch.object(T.SmoothTool, 'SPANS_MAX', 10):
            tool._key = None
            sp = self.screen(0.0, 10.0)
            tool.move(sp, w.canvas.to_doc(sp), None)
            self.assertEqual(tool.shown, [])                                # 80 mm / 2 mm > 10 : le clic seul

    def test_click_on_nothing(self):
        w = self.w
        w.A['tool_smooth'].trigger()
        tool = w.canvas.tool_obj
        sp = self.screen(30.0, 50.0)
        n = len(w._undo)
        tool.press(sp, w.canvas.to_doc(sp), None)
        self.assertEqual(len(w._undo), n)


if __name__ == '__main__':
    unittest.main()
