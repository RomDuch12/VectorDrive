"""Round 105 : tout calcul a une barre de progression avec Annuler
(core.progress + ui.progress.run, calculs FAO, imbrication, vérification
instrumentés)."""
import os
import tempfile
import threading
import time
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QProgressDialog, QWidget

from vectordrive.cam import model, strategies
from vectordrive.core import check, geom, nesting
from vectordrive.core import progress as P
from vectordrive.core.document import Document, Plate, Shape
from vectordrive.ui import progress as UP


def app():
    return QApplication.instance() or QApplication([])


def doc_rects(n):
    d = Document()
    d.plate = Plate(300, 200)
    for k in range(n):
        d.layers[0].items.append(Shape(path=geom.Path([geom.rect(10 + 12 * k, 10, 8, 8)]), tool=1))
    return d


def setup(n_ops):
    s = model.CamSetup()
    s.tools = [model.CamTool(name='F2', diameter=2.0, step_down=0.5, number=1)]
    for k in range(n_ops):
        s.operations.append(model.Operation(name=f'op{k}', kind='gravure', depth=0.5, tool_id=s.tools[0].id))
    return s


class Recorder(P.Task):
    """Tâche qui garde chaque avancement (essais dans le fil courant)."""

    def __init__(self):
        super().__init__('essai')
        self.seen = []

    def report(self, fraction, text=None):
        super().report(fraction, text)
        self.seen.append((round(self.fraction, 4), self.text))


def tracked(task, fn, *a, **kw):
    tok = P.attach(task)
    try:
        return fn(*a, **kw)
    finally:
        P.detach(tok)


class TestCore(unittest.TestCase):
    def test_untracked_is_noop(self):
        self.assertIsNone(P.current())
        P.step(3, 10, 'x {0}')
        P.check()
        with P.span(0.2, 0.4):
            P.step(1, 2)

    def test_step_text_and_fraction(self):
        t = Recorder()
        tracked(t, P.step, 1, 4, 'Objet {0} sur {1}')
        self.assertEqual(t.seen[-1], (0.25, 'Objet 2 sur 4'))

    def test_nested_spans(self):
        t = Recorder()

        def work():
            with P.span(0.5, 1.0):
                with P.span(0.0, 0.5):
                    P.step(1, 2)
        tracked(t, work)
        self.assertAlmostEqual(t.seen[-1][0], 0.625)
        self.assertEqual(t._span, (0.0, 1.0))

    def test_cancel_raises_at_next_checkpoint(self):
        t = P.Task()
        t.cancel()
        with self.assertRaises(P.Cancelled):
            tracked(t, P.check)
        with self.assertRaises(P.Cancelled):
            tracked(t, P.step, 0, 1)


class TestInstrumented(unittest.TestCase):
    def test_compute_all_reports_each_operation(self):
        t = Recorder()
        tps = tracked(t, strategies.compute_all, doc_rects(3), setup(2))
        self.assertEqual(len(tps), 2)
        texts = [x for _, x in t.seen]
        self.assertIn('Parcours 1 sur 2', texts)
        self.assertIn('Parcours 2 sur 2', texts)
        fr = [f for f, _ in t.seen]
        self.assertEqual(fr, sorted(fr))
        self.assertLessEqual(max(fr), 1.0)

    def test_compute_all_cancelled(self):
        t = P.Task()
        t.cancel()
        with self.assertRaises(P.Cancelled):
            tracked(t, strategies.compute_all, doc_rects(2), setup(1))

    def test_check_and_nesting_have_checkpoints(self):
        d = doc_rects(10)
        t = Recorder()
        tracked(t, check.check, d)
        self.assertTrue(any('Vérification' in x for _, x in t.seen))
        t = Recorder()
        items = list(d.layers[0].items)
        tracked(t, nesting.nest, items, d.plate, nesting.NestSpec())
        self.assertTrue(any('Imbrication' in x for _, x in t.seen))


class TestRun(unittest.TestCase):
    def setUp(self):
        app()
        UP.AUTO_CANCEL_AFTER_MS = None

    def tearDown(self):
        UP.AUTO_CANCEL_AFTER_MS = None

    def test_result_and_worker_thread(self):
        main = threading.get_ident()
        res = UP.run(None, 'essai', lambda a, b=0: (a + b, threading.get_ident()), 2, b=3)
        self.assertEqual(res[0], 5)
        self.assertNotEqual(res[1], main)
        self.assertIsNone(QApplication.overrideCursor())

    def test_error_is_reraised(self):
        def bad():
            raise ValueError('mauvais')
        with self.assertRaisesRegex(ValueError, 'mauvais'):
            UP.run(None, 'essai', bad)
        self.assertIsNone(QApplication.overrideCursor())

    def test_cancel_stops_the_worker(self):
        UP.AUTO_CANCEL_AFTER_MS = 100
        state = {'stopped': False}

        def endless():
            try:
                for i in range(10_000):
                    P.step(i, 10_000, 'Objet {0} sur {1}')
                    time.sleep(0.005)
            except P.Cancelled:
                state['stopped'] = True
                raise
        t0 = time.monotonic()
        with self.assertRaises(UP.Cancelled):
            UP.run(None, 'essai', endless)
        self.assertLess(time.monotonic() - t0, 5)
        for _ in range(100):
            if state['stopped']:
                break
            time.sleep(0.01)
        self.assertTrue(state['stopped'])
        self.assertIsNone(QApplication.overrideCursor())

    def test_progress_dialog_shown_for_long_work(self):
        old = UP.SHOW_MS
        UP.SHOW_MS = 0
        seen = []
        try:
            def slow():
                for i in range(10):
                    P.step(i, 10)
                    time.sleep(0.03)
                    seen.extend(UP._DIALOGS)
            UP.run(None, 'essai', slow)
        finally:
            UP.SHOW_MS = old
        self.assertTrue(seen)
        self.assertIsInstance(seen[0], QProgressDialog)
        self.assertEqual(UP._DIALOGS, [])

    def test_input_guard_blocks_all_but_progress_dialog(self):
        other = QWidget()
        other.show()
        dlg = QProgressDialog('x', 'Annuler', 0, 10)
        dlg.show()
        UP._DIALOGS.append(dlg)
        try:
            g = UP._InputGuard()
            ev = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(1, 1), QPointF(1, 1),
                             Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            self.assertTrue(g.eventFilter(other, ev))
            self.assertTrue(g.eventFilter(other.windowHandle(), ev))
            self.assertFalse(g.eventFilter(dlg, ev))
            self.assertFalse(g.eventFilter(dlg.windowHandle(), ev))
            button = dlg.findChildren(QWidget)[0]
            self.assertFalse(g.eventFilter(button, ev))
            paint = QEvent(QEvent.Type.Paint)
            self.assertFalse(g.eventFilter(other, paint))
        finally:
            UP._DIALOGS.remove(dlg)
            dlg.close()
            other.close()


class TestCallers(unittest.TestCase):
    def setUp(self):
        app()

    def tearDown(self):
        UP.AUTO_CANCEL_AFTER_MS = None

    def test_cam_compute_cancelled(self):
        from vectordrive.ui.main_window import MainWindow
        win = MainWindow()
        try:
            d = win.canvas.doc
            d.layers[0].items.append(Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]), tool=1))
            model.store(d, setup(1))
            panel = win.cam_panel
            orig = strategies.compute_all

            def slow(doc, s):
                for i in range(1000):
                    P.step(i, 1000)
                    time.sleep(0.005)
                return orig(doc, s)
            strategies.compute_all = slow
            UP.AUTO_CANCEL_AFTER_MS = 60
            try:
                tps = panel.compute()
            finally:
                strategies.compute_all = orig
            self.assertEqual(tps, [])
            self.assertIn('annulé', panel.info.text())
            UP.AUTO_CANCEL_AFTER_MS = None
            self.assertTrue(panel.compute())
        finally:
            win.modified = False
            win.close()


if __name__ == '__main__':
    unittest.main()
