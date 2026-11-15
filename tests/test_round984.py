"""Round 984 : relecture des rounds 976 à 983 — la fenêtre d'un panneau survit à F12 et à la réduction de la fenêtre
principale ; un lancement en plein écran remet les panneaux de la session ; l'œil des opérations ne relit le réglage
FAO qu'une fois ; la liste des parcours reparaît pour un ordre réglé à la main ; une liste déroulante ne prend pas le
clavier au passage de la molette ; journal des erreurs ; `release` posé deux fois."""
import os
import tempfile
import threading
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r984.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import Qt, QTimer  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QDockWidget, QLabel  # noqa: E402

app = QApplication.instance() or QApplication([])


def close(w):
    w.modified = False
    for t in getattr(w, 'docs', []):
        t.modified = False
    w.close()
    app.processEvents()


class PanelWindowStays(unittest.TestCase):

    def test_panel_window_survives_f12_and_minimize(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        w.settings.setValue('fenetre/plein_ecran', False)
        w.show()
        app.processEvents()
        dock = QDockWidget('Essai', w)
        dock.setObjectName('essai_r984')
        dock.setWidget(QLabel('x'))
        w.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        for k in ('en_fenetre', 'plein_ecran', 'geometrie'):
            w.settings.remove(f'r984/fenetre/{k}')
        host = w.dock_as_window(dock, 'r984/fenetre')
        win = host.to_window(full_screen=False)
        try:
            app.processEvents()
            w.cycle_full_screen()                                              # F12
            QTest.qWait(80)
            self.assertTrue(host.in_window() and win.isVisible())              # avant : rendu au panneau, caché
            w.cycle_full_screen()
            w.cycle_full_screen()
            QTest.qWait(80)
            self.assertTrue(host.in_window() and win.isVisible())
            w.showMinimized()                                                  # réduite
            QTest.qWait(80)
            self.assertTrue(host.in_window() and win.isVisible())
            w.showNormal()
            QTest.qWait(40)
            close(w)                                                           # fermée pour de bon : la fenêtre aussi
            QTest.qWait(40)
            self.assertFalse(host.in_window())
            self.assertFalse(win.isVisible())
            self.assertIn(w.settings.value('r984/fenetre/en_fenetre'), (True, 'true'))   # et rouvrira dans sa fenêtre
        finally:
            for k in ('en_fenetre', 'plein_ecran', 'geometrie'):
                w.settings.remove(f'r984/fenetre/{k}')
            w.settings.setValue('fenetre/plein_ecran', False)
            if host.in_window():
                host.to_dock(show=False)
            close(w)


class FullScreenStart(unittest.TestCase):

    def test_full_screen_start_restores_session_panels(self):
        from vectordrive.ui.main_window import MainWindow
        folder = tempfile.mkdtemp()
        w = MainWindow()
        w.settings.setValue('fenetre/plein_ecran', False)
        w.start_session(folder)
        w.show()
        app.processEvents()
        layers = w.findChild(QDockWidget, 'layers')
        self.assertIsNotNone(layers)
        w.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, layers)          # les calques mis à gauche
        app.processEvents()
        w.save_session()
        w._session_lock.unlock()
        w._session_lock, w.session_dir = None, None
        w.settings.setValue('fenetre/plein_ecran', True)                       # fermée en plein écran
        close(w)
        w2 = MainWindow()
        try:
            w2.start_session(folder)
            got = w2.show_at_start(True)
            app.processEvents()
            self.assertEqual(got, 'full')
            area = w2.dockWidgetArea(w2.findChild(QDockWidget, 'layers'))
            self.assertEqual(area, Qt.DockWidgetArea.LeftDockWidgetArea)       # avant : à droite, place d'office
        finally:
            if getattr(w2, '_session_lock', None) is not None:
                w2._session_lock.unlock()
                w2._session_lock = None
            w2.session_dir = None
            w2.settings.setValue('fenetre/plein_ecran', False)
            if w2.is_full_screen():
                w2.set_full_screen(False)
            close(w2)


class CamEyes(unittest.TestCase):

    def setUp(self):
        from vectordrive.cam import model
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.p = self.w.cam_panel
        doc = self.w.canvas.doc
        ids = []
        for k in range(12):
            sh = Shape(path=geom.Path([geom.rect(k * 15.0, 0, 10, 8)]), tool=0)
            doc.add(sh)
            ids.append(sh.id)
        s = self.p.setup()
        t = model.CamTool(name='Cyl 2', diameter=2.0, number=1, cut_length=7, step_down=1.0)
        s.tools = [t]
        s.operations = [model.Operation(name=f'Op {k}', kind='gravure', tool_id=t.id, items=[i], depth=0.2)
                        for k, i in enumerate(ids)]
        self.p.save(s)
        self.p.compute()

    def tearDown(self):
        close(self.w)

    def test_eyes_read_the_setup_once(self):
        p = self.p
        self.assertGreaterEqual(len(p.toolpaths), 12)
        real, calls = p.setup, []

        def counted():
            calls.append(1)
            return real()
        with mock.patch.object(p, 'setup', counted):
            p._sync_eyes()
        self.assertLessEqual(len(calls), 2)                                    # avant : une fois par ligne (12)
        self.assertTrue(all(p.ops.item(r, p.EYE_COL).data(Qt.ItemDataRole.UserRole) is True for r in range(12)))

    def test_paths_list_shown_for_a_hand_set_order(self):
        p = self.p
        self.assertTrue(p.paths_group.isHidden())                              # dans l'ordre des opérations
        p.display(list(reversed(p.toolpaths)))                                 # ordre d'écriture réglé à la main
        self.assertFalse(p.paths_group.isHidden())                             # avant : invisible, rien ne le montrait
        p.display(list(reversed(p.toolpaths)))
        self.assertTrue(p.paths_group.isHidden())


class ComboFocus(unittest.TestCase):

    def test_a_hovered_combo_does_not_take_the_keyboard(self):
        from vectordrive.ui import wheelguard
        wheelguard.install(app)
        c = QComboBox()
        c.addItems(['a', 'b', 'c'])
        c.show()
        app.processEvents()
        self.assertEqual(c.focusPolicy(), Qt.FocusPolicy.StrongFocus)          # avant : WheelFocus
        c.close()


class Journal(unittest.TestCase):

    def setUp(self):
        from vectordrive import journal
        self.j = journal
        self.log = journal.path()
        if self.log.exists():
            self.log.unlink()

    def tearDown(self):
        if self.log.exists():
            self.log.unlink()

    def boom(self, msg):
        try:
            raise ValueError(msg)
        except ValueError as ex:
            return type(ex), ex, ex.__traceback__

    def test_cut_keeps_whole_characters(self):
        self.log.parent.mkdir(parents=True, exist_ok=True)
        self.log.write_bytes(('é' * (self.j.MAX_BYTES // 2 + 1000)).encode('utf-8') + b'x')   # coupe au milieu d'un é
        self.j.record(*self.boom('r984 coupe'))
        text = self.log.read_text(encoding='utf-8')                            # avant : UnicodeDecodeError
        self.assertIn('r984 coupe', text)
        self.assertLess(self.log.stat().st_size, self.j.MAX_BYTES)

    def test_a_repeated_error_is_written_once(self):
        err = self.boom('r984 répétée')
        for _ in range(5):
            self.j.record(*err)
        self.assertEqual(self.log.read_text(encoding='utf-8').count('r984 répétée'), 1)   # avant : 5
        self.j.record(*self.boom('r984 autre'))
        self.assertIn('r984 autre', self.log.read_text(encoding='utf-8'))

    def test_previous_thread_hook_is_kept(self):
        seen = []
        saved, saved_sys = threading.excepthook, __import__('sys').excepthook
        self.j.uninstall()
        threading.excepthook = lambda args: seen.append(str(args.exc_value))
        try:
            self.j.install()

            def fail():
                raise RuntimeError('r984 fil')
            t = threading.Thread(target=fail, name='essai984')
            t.start()
            t.join()
            self.assertEqual(seen, ['r984 fil'])                               # avant : le crochet d'avant perdu
            self.assertIn('essai984', self.log.read_text(encoding='utf-8'))
        finally:
            self.j.uninstall()
            threading.excepthook = saved
            import sys
            sys.excepthook = saved_sys


class ReleaseTwice(unittest.TestCase):

    def test_release_twice_keeps_the_dialog_for_its_caller(self):
        from vectordrive.ui import fit
        d = QDialog()
        box = QComboBox(d)
        box.addItems(['a', 'b'])
        box.setCurrentIndex(1)
        fit.release(d)
        fit.release(d)
        QTimer.singleShot(0, d.accept)
        d.exec()
        QTest.qWait(120)                                                       # une autre boîte : la boucle tourne
        try:
            read = box.currentIndex()
        except RuntimeError as ex:                                             # avant : fenêtre déjà détruite
            read = str(ex)
        self.assertEqual(read, 1)


if __name__ == '__main__':
    unittest.main()
