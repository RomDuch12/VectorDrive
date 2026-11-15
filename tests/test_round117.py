"""Round 117 : temps d'usinage estimé (accélération en trapèze, plongées,
rapides, changements d'outil), notes déplacées à la souris."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from vectordrive.cam import model, timing as TM


def setup_with(feed=600.0, plunge=100.0):
    s = model.CamSetup()
    t = model.CamTool(name='F2', diameter=2.0, feed=feed, plunge=plunge, number=1)
    s.tools = [t]
    op = model.Operation(kind='gravure', depth=0.5, tool_id=t.id)
    s.operations = [op]
    return s, t, op


class TestTiming(unittest.TestCase):
    def test_run_time(self):
        self.assertAlmostEqual(TM.run_time(100, 10, 1e9), 10, places=3)          # accélération infinie
        self.assertAlmostEqual(TM.run_time(100, 10, 100), 10.1, places=6)       # trapèze : + v/a
        self.assertAlmostEqual(TM.run_time(0.25, 10, 100), 0.1, places=6)       # triangle : 2·√(L/a)
        self.assertEqual(TM.run_time(0, 10, 100), 0.0)

    def test_straight_line_and_plunge(self):
        s, t, op = setup_with()
        tp = model.Toolpath(op.id, t.id)
        tp.moves = [model.Move('rapid', 0, 0, 2), model.Move('plunge', 0, 0, -0.5),
                    model.Move('feed', 100, 0, -0.5), model.Move('rapid', 100, 0, 2)]
        spec = TM.TimingSpec(rapid=6000, accel=1e9)
        sec = TM.path_seconds(tp, s, spec)
        expect = 2.5 / (100 / 60) + 100 / (600 / 60) + 2.5 / (6000 / 60)
        self.assertAlmostEqual(sec, expect, places=3)

    def test_arc_not_stopped_at_each_facet(self):
        s, t, op = setup_with(feed=1200)
        tp = model.Toolpath(op.id, t.id)
        n = 360
        pts = [(10 * math.cos(2 * math.pi * k / n), 10 * math.sin(2 * math.pi * k / n)) for k in range(n + 1)]
        tp.moves = [model.Move('feed', x, y, -0.1) for x, y in pts]
        smooth = TM.path_seconds(tp, s, TM.TimingSpec(accel=500))
        stop_everywhere = TM.path_seconds(tp, s, TM.TimingSpec(accel=500, corner=0.0))
        ideal = 2 * math.pi * 10 / 20
        self.assertLess(smooth, ideal * 1.05)
        self.assertGreater(stop_everywhere, smooth * 1.5)

    def test_tool_changes_and_format(self):
        s, t, op = setup_with()
        t2 = model.CamTool(name='F1', diameter=1.0, number=2)
        s.tools.append(t2)
        a = model.Toolpath(op.id, t.id, moves=[model.Move('feed', 0, 0, 0), model.Move('feed', 10, 0, 0)])
        b = model.Toolpath(op.id, t2.id, moves=[model.Move('feed', 0, 0, 0), model.Move('feed', 10, 0, 0)])
        est = TM.estimate([a, b, a], s, TM.TimingSpec(tool_change=8))
        self.assertEqual(est['changes'], 3)
        self.assertAlmostEqual(est['change_s'], 24)
        self.assertEqual(TM.format_duration(3725), '1 h 02 min')
        self.assertEqual(TM.format_duration(125), '2 min 05 s')
        self.assertEqual(TM.format_duration(9.4), '9 s')

    def test_spec_from_settings_and_plugin(self):
        from PySide6.QtCore import QSettings
        from vectordrive import plugins
        st = QSettings(os.path.join(tempfile.mkdtemp(), 's.ini'), QSettings.Format.IniFormat)
        plugins.REGISTRY.defaults['timing'] = {'rapid': 20000, 'accel': 2000}
        try:
            spec = TM.spec_from_settings(st)
            self.assertEqual((spec.rapid, spec.accel, spec.tool_change), (20000, 2000, 10.0))
            st.setValue('fao/vitesse_rapide', 9000)
            self.assertEqual(TM.spec_from_settings(st).rapid, 9000)
        finally:
            plugins.REGISTRY.defaults.pop('timing', None)


class TestNoteDrag(unittest.TestCase):
    def test_drag(self):
        QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        w.resize(900, 700)
        try:
            c = w.canvas
            c.fit((0, 0, 100, 100))
            w.add_note('Essai', at=(20, 20))
            r = c._note_rect(c.notes()[0])
            a = r.center()
            b = a + QPointF(c.scale * 10, -c.scale * 5)

            def ev(kind, p, buttons):
                return QMouseEvent(kind, p, p, Qt.MouseButton.LeftButton, buttons, Qt.KeyboardModifier.NoModifier)
            c.mousePressEvent(ev(QEvent.Type.MouseButtonPress, a, Qt.MouseButton.LeftButton))
            c.mouseMoveEvent(ev(QEvent.Type.MouseMove, b, Qt.MouseButton.LeftButton))
            c.mouseReleaseEvent(ev(QEvent.Type.MouseButtonRelease, b, Qt.MouseButton.NoButton))
            n = c.notes()[0]
            self.assertAlmostEqual(n['x'], 30, places=3)
            self.assertAlmostEqual(n['y'], 25, places=3)
            w.undo()
            self.assertAlmostEqual(w.canvas.notes()[0]['x'], 20, places=3)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
