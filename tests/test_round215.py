"""Round 215 : onglets de documents (comme un navigateur), session
silencieuse (fermeture sans question, tout rouvert au démarrage), une seule
fenêtre (un nouveau lancement ouvre un onglet)."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


def square(win, x=0.0, size=10.0):
    from vectordrive.core import geom
    from vectordrive.core.document import Shape
    win.push_undo('carré')
    sh = Shape(path=geom.Path([geom.rect(x, 0, size, size)]), tool=0)
    win.canvas.doc.active_layer.items.append(sh)
    win.canvas.invalidate()
    win._on_doc_changed()
    return sh


def saved_drawing(folder: pathlib.Path, name: str, n: int = 1) -> pathlib.Path:
    from vectordrive.core import geom
    from vectordrive.core.document import Document, Shape
    from vectordrive.io import native
    d = Document()
    for i in range(n):
        d.active_layer.items.append(Shape(path=geom.Path([geom.rect(i * 20, 0, 10, 10)]), tool=0))
    p = folder / name
    native.write_atomic(native.snapshot(d), p, level=1)
    return p


class TestTabs(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.tmp = pathlib.Path(tempfile.mkdtemp())

    def tearDown(self):
        for t in self.w.docs:
            t.modified = False
        self.w.modified = False
        self.w.close()

    def test_new_and_open_in_tabs(self):
        w = self.w
        self.assertEqual(len(w.docs), 1)
        w.new_document()                                             # onglet vide : réutilisé
        self.assertEqual(len(w.docs), 1)
        square(w)
        w.new_document()
        self.assertEqual(len(w.docs), 2)
        self.assertEqual(w.doc_index, 1)
        self.assertEqual(w.doc_bar.tabs.count(), 2)
        a = saved_drawing(self.tmp, 'a.vdz', 2)
        self.assertTrue(w.open_path(str(a)))                        # l'onglet vide le reçoit
        self.assertEqual(len(w.docs), 2)
        self.assertEqual(w.doc_bar.tabs.tabText(1), 'a.vdz')
        self.assertTrue(w.open_path(str(a)))                        # déjà ouvert : rien de plus
        self.assertEqual(len(w.docs), 2)
        b = saved_drawing(self.tmp, 'b.vdz', 3)
        w.open_path(str(b))
        self.assertEqual(len(w.docs), 3)
        self.assertEqual(sum(len(L.items) for L in w.canvas.doc.layers), 3)

    def test_switch_keeps_each_document(self):
        w = self.w
        square(w)
        first = w.canvas.doc
        w.new_document()
        square(w, 30)
        square(w, 60)
        self.assertEqual(len(w._undo), 2)
        w.switch_tab(0)
        self.assertIs(w.canvas.doc, first)
        self.assertEqual(len(w._undo), 1)                           # historique de cet onglet
        self.assertTrue(w.modified)
        self.assertEqual(w.doc_bar.tabs.tabText(0), 'Sans titre *')
        w.undo()
        self.assertEqual(sum(len(L.items) for L in w.canvas.doc.layers), 0)
        w.step_tab(1)
        self.assertEqual(sum(len(L.items) for L in w.canvas.doc.layers), 2)
        w.step_tab(1)                                                # en boucle
        self.assertEqual(w.doc_index, 0)

    def test_close(self):
        w = self.w
        square(w)
        w.new_document()
        square(w, 30)
        self.assertFalse(w.close_tab(answer='cancel'))
        self.assertEqual(len(w.docs), 2)
        self.assertTrue(w.close_tab(answer='discard'))
        self.assertEqual(len(w.docs), 1)
        self.assertEqual(w.doc_index, 0)
        self.assertTrue(w.close_tab(answer='discard'))              # le dernier : un dessin vide reste
        self.assertEqual(len(w.docs), 1)
        self.assertTrue(w.docs[0].pristine() or not w.modified)

    def test_moved_tab(self):
        w = self.w
        square(w)
        w.new_document()
        square(w, 30)
        cur = w.canvas.doc
        w.doc_bar.tabs.moveTab(1, 0)
        self.assertEqual(w.doc_index, 0)
        self.assertIs(w.docs[0].doc, cur)


class TestSession(unittest.TestCase):
    def test_round_trip(self):
        from vectordrive.cam.model import Move, Toolpath
        from vectordrive.ui import session
        from vectordrive.ui.main_window import MainWindow
        tmp = pathlib.Path(tempfile.mkdtemp())
        folder = tmp / 'session'
        a = saved_drawing(tmp, 'a.vdz', 2)
        w = MainWindow()
        self.assertTrue(w.start_session(folder))
        w.open_path(str(a))                                          # enregistré, intact
        w.new_document()
        square(w)
        square(w, 30)                                                # jamais enregistré, modifié
        tp = Toolpath('op', 'tool', [Move('rapid', 0, 0, 5), Move('feed', 10, 0, -0.1)], name='essai')
        w.cam_panel.display([tp])
        w.canvas.scale, w.canvas.ox, w.canvas.oy = 7.5, 12.0, 34.0
        w.close()                                                     # sans question
        self.assertTrue((folder / 'session.json').exists())
        index = session.load_index(folder)
        self.assertEqual(len(index['docs']), 2)
        self.assertIsNone(index['docs'][0]['file'])                  # rouvert depuis le disque
        self.assertTrue(index['docs'][1]['file'])                    # gardé dans la session
        self.assertTrue(a.exists())
        w2 = MainWindow()
        self.assertTrue(w2.start_session(folder))
        self.assertEqual(w2.restore_session(), 2)
        self.assertEqual(len(w2.docs), 2)
        self.assertEqual(w2.doc_index, 1)                            # l'onglet courant de la dernière fois
        self.assertTrue(w2.modified)
        self.assertEqual(sum(len(L.items) for L in w2.canvas.doc.layers), 2)
        self.assertEqual((w2.canvas.scale, w2.canvas.ox, w2.canvas.oy), (7.5, 12.0, 34.0))
        self.assertEqual([t.name for t in w2.cam_panel.toolpaths], ['essai'])
        self.assertEqual(len(w2.cam_panel.toolpaths[0].moves), 2)
        w2.switch_tab(0)
        self.assertEqual(pathlib.Path(w2.path), a)
        self.assertFalse(w2.modified)
        w3 = MainWindow()
        self.assertFalse(w3.start_session(folder))                  # session tenue par une autre fenêtre
        w3.close()
        for t in w2.docs:
            t.modified = False
        w2.modified = False
        w2.session_dir = None
        w2.close()

    def test_option_and_test_sessions(self):
        from vectordrive.ui import session
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.options import BY_KEY
        self.assertTrue(BY_KEY['options/session'].default)
        temp = pathlib.Path(os.environ['VECTORDRIVE_SESSION_TEMP']).resolve()
        self.assertTrue(str(session.default_dir()).startswith(str(pathlib.Path(tempfile.gettempdir()))))
        w = MainWindow()
        self.assertTrue(pathlib.Path(w.session_dir).resolve().is_relative_to(temp))   # jetable, jamais celle de l'utilisateur
        square(w)
        w.new_document()
        square(w, 40)
        w.close()                                                     # deux dessins modifiés : aucune question
        self.assertFalse(w.isVisible())
        self.assertIsNone(w.session_dir)


class TestInstance(unittest.TestCase):
    def test_forward_opens_tab(self):
        from vectordrive.ui import instance
        from vectordrive.ui.main_window import MainWindow
        os.environ['VECTORDRIVE_INSTANCE'] = 'vd-essai-' + os.urandom(4).hex()
        try:
            w = MainWindow()
            self.assertIsNotNone(instance.serve(w))
            tmp = pathlib.Path(tempfile.mkdtemp())
            square(w)
            p = saved_drawing(tmp, 'envoye.vdz', 4)
            import subprocess
            import sys
            import time
            root = str(pathlib.Path(__file__).resolve().parents[1])
            code = ('import sys; sys.path.insert(0, sys.argv[1]); from PySide6.QtCore import QCoreApplication; '
                    'app = QCoreApplication([]); from vectordrive.ui import instance; '
                    'sys.exit(0 if instance.forward(sys.argv[2]) else 3)')
            proc = subprocess.Popen([sys.executable, '-c', code, root, str(p)], env=dict(os.environ))
            t0 = time.monotonic()
            while time.monotonic() - t0 < 20 and (proc.poll() is None or len(w.docs) < 2):
                app.processEvents()
                time.sleep(0.01)
            self.assertEqual(proc.wait(10), 0)                           # un second lancement s'arrête
            for _ in range(20):
                app.processEvents()
            self.assertEqual(len(w.docs), 2)
            self.assertEqual(pathlib.Path(w.path).name, 'envoye.vdz')
            for t in w.docs:
                t.modified = False
            w.modified = False
            w.close()
        finally:
            os.environ.pop('VECTORDRIVE_INSTANCE', None)
        os.environ['VECTORDRIVE_INSTANCE'] = 'vd-absent-' + os.urandom(4).hex()
        try:
            self.assertFalse(instance.forward('x.vdz', timeout_ms=100))  # pas de fenêtre : on se lance
        finally:
            os.environ.pop('VECTORDRIVE_INSTANCE', None)


if __name__ == '__main__':
    unittest.main()
