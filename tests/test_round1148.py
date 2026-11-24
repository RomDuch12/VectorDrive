"""Round 1148 (demande du 24/11) : « Tout onglet jamais enregistré (ou modifié non enregistré) à la fermeture l'est
silencieusement dans le dossier programme pour pouvoir etre réouvert (en silencieux, fichier toujours noté non
enregistré à l'ouverture), à la manière de npp »."""
import os
import pathlib
import shutil
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1148.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ.setdefault('VECTORDRIVE_CLOSED_TABS', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ.setdefault('VECTORDRIVE_KEYS_MEMORY', '1')

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : fermer un onglet modifié posait la question « Enregistrer ? », rien n’était gardé sur le disque'


def draw(w, x=0.0):
    from vectordrive.core import geom
    from vectordrive.core.document import Shape
    w.push_undo('essai')
    w.canvas.doc.add(Shape(path=geom.Path([geom.rect(x, 0, 10, 10)]), tool=1))
    w.canvas.invalidate()
    w._on_doc_changed()


class Closing(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui import closed_store
        self.store = pathlib.Path(closed_store.folder())
        shutil.rmtree(self.store, ignore_errors=True)
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        if not self.w.docs:
            self.w.new_document()
        self.w.settings.remove('options/garder_onglets')
        self.w.settings.remove('fichiers/onglets_fermes')
        self.ask = mock.patch.object(QMessageBox, 'exec', side_effect=AssertionError('question posée'))
        self.ask.start()
        self.addCleanup(self.ask.stop)

    def tearDown(self):
        for t in self.w.docs:
            t.modified = False
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()
        shutil.rmtree(self.store, ignore_errors=True)

    def test_never_saved_kept_without_question(self):
        w = self.w
        draw(w)
        self.assertTrue(w.modified)
        w.new_document()
        self.assertEqual(len(w.docs), 2)
        self.assertTrue(w.close_tab(0), BEFORE)                             # pas de question (exec refusé)
        self.assertEqual(len(w.docs), 1)
        files = list(self.store.glob('*.vdz'))
        self.assertEqual(len(files), 1, BEFORE)                             # écrit dans le dossier
        items = w.closed_tabs()
        self.assertEqual(len(items), 1)
        self.assertTrue(w.reopen_tab())
        self.assertEqual(len(w.docs), 1)                                    # à la place de l'onglet vide
        self.assertTrue(w.modified)                                         # toujours non enregistré
        self.assertIsNone(w.path)
        self.assertEqual(sum(len(L.items) for L in w.canvas.doc.layers), 1)
        self.assertEqual(list(self.store.glob('*.vdz')), [])                # repris : retiré du dossier
        self.assertEqual(w.closed_tabs(), [])

    def test_modified_file_kept_with_its_path(self):
        w = self.w
        from vectordrive.io import native
        p = os.path.join(tempfile.mkdtemp(), 'piece.vdz')
        draw(w)
        native.write(w.canvas.doc, p)
        w.new_document()
        self.assertTrue(w.open_path(p))
        before = pathlib.Path(p).read_bytes()
        draw(w, 20.0)                                                       # modifié, non enregistré
        self.assertTrue(w.close_tab(), BEFORE)
        self.assertEqual(pathlib.Path(p).read_bytes(), before)              # le fichier n'est jamais écrit
        items = w.closed_tabs()
        self.assertEqual(len(items), 1)
        self.assertNotIsInstance(items[0], str)                             # le dessin gardé, pas le fichier relu
        self.assertTrue(w.reopen_tab(items[0]))
        self.assertTrue(w.modified)
        self.assertEqual(pathlib.Path(w.path), pathlib.Path(p))             # Enregistrer : dans son fichier
        self.assertEqual(sum(len(L.items) for L in w.canvas.doc.layers), 2)  # avec la modification

    def test_kept_after_restart(self):
        w = self.w
        draw(w)
        w.new_document()
        w.close_tab(0)
        from vectordrive.ui.main_window import MainWindow
        w2 = MainWindow()                                                   # une autre séance
        try:
            items = w2.closed_tabs()
            self.assertEqual(len(items), 1)
            from PySide6.QtWidgets import QMenu
            menu = QMenu()
            sub = w2._reopen_menu(menu)
            self.assertTrue(any('non enregistré' in a.text() for a in sub.actions()))
            self.assertTrue(w2.reopen_tab())
            self.assertTrue(w2.modified)
        finally:
            for t in w2.docs:
                t.modified = False
            w2.modified = False
            w2.close()
            w2.deleteLater()

    def test_option_off_asks_again(self):
        w = self.w
        w.settings.setValue('options/garder_onglets', False)
        draw(w)
        w.new_document()
        with mock.patch.object(w, '_ask_save', return_value='discard') as ask:
            self.assertTrue(w.close_tab(0))
        self.assertEqual(ask.call_count, 1)
        self.assertEqual(list(self.store.glob('*.vdz')), [])

    def test_answer_given_keeps_old_way(self):
        w = self.w
        draw(w)
        w.new_document()
        self.assertTrue(w.close_tab(0, answer='discard'))
        self.assertEqual(list(self.store.glob('*.vdz')), [])

    def test_write_failure_falls_back_to_the_question(self):
        w = self.w
        draw(w)
        w.new_document()
        from vectordrive.ui import closed_store
        with mock.patch.object(closed_store, 'keep', side_effect=OSError('disque plein')), \
                mock.patch.object(w, '_ask_save', return_value='cancel') as ask:
            self.assertFalse(w.close_tab(0))
        self.assertEqual(ask.call_count, 1)
        self.assertEqual(len(w.docs), 2)

    def test_window_close_without_session(self):
        w = self.w
        draw(w)
        keep, w.session_dir = w.session_dir, None
        try:
            self.assertTrue(w._confirm_discard(), BEFORE)                   # pas de question
        finally:
            w.session_dir = keep
        self.assertEqual(len(list(self.store.glob('*.vdz'))), 1)
        self.assertEqual(w.closed_tabs(), [])                               # l'onglet est toujours ouvert

    def test_cancelled_window_close_forgets(self):
        w = self.w
        draw(w)
        w.new_document()
        draw(w, 30.0)
        keep, w.session_dir = w.session_dir, None
        from vectordrive.ui import closed_store
        real, calls = closed_store.keep, []

        def keep_once(*a, **k):                                             # le 2e ne s'écrit pas : la question
            calls.append(1)
            if len(calls) > 1:
                raise OSError('plein')
            return real(*a, **k)
        try:
            with mock.patch.object(closed_store, 'keep', side_effect=keep_once), \
                    mock.patch.object(w, '_ask_save', return_value='cancel'):
                self.assertFalse(w._confirm_discard())                       # le 2e : Annuler
        finally:
            w.session_dir = keep
        self.assertEqual(list(self.store.glob('*.vdz')), [])                # le 1er n'est plus gardé

    def test_saved_then_closed_not_offered(self):
        w = self.w
        draw(w)
        w.new_document()
        from vectordrive.ui import closed_store
        closed_store.keep(w.docs[0], 'vieux')                               # gardé plus tôt (mise à jour abandonnée)
        w.docs[0].modified = False
        w.docs[0].path = os.path.join(tempfile.mkdtemp(), 'x.vdz')          # enregistré depuis
        w.close_tab(0)
        self.assertFalse(any(getattr(e, 'title', '') == 'vieux' for e in w.closed_tabs()))
        self.assertEqual(list(self.store.glob('*.vdz')), [])

    def test_toolpaths_come_back(self):
        from vectordrive.cam.model import Move, Toolpath
        w = self.w
        draw(w)
        tp = Toolpath(op_id='o', tool_id='t', name='essai', moves=[Move('rapid', 0, 0, 5), Move('feed', 10, 0, -1)])
        w.cam_panel.display([tp])
        w.new_document()
        w.close_tab(0)
        self.assertTrue(list(self.store.glob('*.vdp')))
        self.assertTrue(w.reopen_tab())
        self.assertEqual([len(t.moves) for t in w.cam_panel.toolpaths], [2])

    def test_kept_file_hidden_while_open(self):
        w = self.w
        from vectordrive.io import native
        p = os.path.join(tempfile.mkdtemp(), 'b.vdz')
        draw(w)
        native.write(w.canvas.doc, p)
        w.new_document()
        w.open_path(p)
        draw(w, 20.0)
        w.close_tab()
        self.assertTrue(w.open_path(p))                                     # rouvert depuis le disque
        self.assertEqual(w.closed_tabs(), [])                               # pas un second onglet du même fichier
        self.assertEqual(w._closed_files(), [])                             # ni le fichier en double

    def test_file_saved_meanwhile_is_signalled(self):
        w = self.w
        from vectordrive.io import native
        p = os.path.join(tempfile.mkdtemp(), 'c.vdz')
        draw(w)
        native.write(w.canvas.doc, p)
        w.new_document()
        w.open_path(p)
        draw(w, 20.0)
        w.close_tab()                                                       # gardé
        draw(w, 50.0)
        native.write(w.canvas.doc, p)                                       # enregistré ailleurs depuis
        st = os.stat(p)
        os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
        item = next(e for e in w.closed_tabs() if not isinstance(e, str))
        self.assertTrue(w.reopen_tab(item))
        self.assertTrue(w.changed_on_disk(p))                               # « changé sur le disque » à Enregistrer

    def test_unchanged_file_not_kept(self):
        w = self.w
        from vectordrive.io import native
        p = os.path.join(tempfile.mkdtemp(), 'net.vdz')
        draw(w)
        native.write(w.canvas.doc, p)
        w.new_document()
        w.open_path(p)
        self.assertFalse(w.modified)
        w.close_tab()
        self.assertEqual(list(self.store.glob('*.vdz')), [])
        self.assertEqual([pathlib.Path(x).name for x in w.closed_tabs()], ['net.vdz'])


class Store(unittest.TestCase):
    def test_limit_and_order(self):
        from vectordrive.core.document import Document
        from vectordrive.ui import closed_store as CS
        from vectordrive.ui.doctabs import DocTab
        d = pathlib.Path(tempfile.mkdtemp())
        with mock.patch.object(CS, 'MAX', 3):
            tabs = [DocTab(Document()) for _ in range(5)]
            for t in tabs:
                CS.keep(t, 'x', where=d)
            got = CS.entries(d)
        self.assertEqual([k.uid for k in got], [t.uid for t in tabs[::-1][:3]])
        self.assertEqual(len(list(d.glob('*.vdz'))), 3)                     # les plus anciens effacés
        CS.keep(tabs[3], 'y', where=d)                                      # le même onglet : remplacé
        self.assertEqual(len(CS.entries(d)), 3)
        CS.drop(got[0])
        self.assertEqual(len(CS.entries(d)), 2)
        (d / CS.INDEX).write_text('{abîmé', encoding='utf-8')               # index illisible : rien d'effacé
        with self.assertRaises(OSError):
            CS.keep(tabs[0], 'z', where=d)
        self.assertEqual(len(list(d.glob('*.vdz'))), 3)

    def test_lock_held_elsewhere(self):
        from PySide6.QtCore import QLockFile
        from vectordrive.core.document import Document
        from vectordrive.ui import closed_store as CS
        from vectordrive.ui.doctabs import DocTab
        d = pathlib.Path(tempfile.mkdtemp())
        other = QLockFile(str(d / CS.LOCK))
        self.assertTrue(other.tryLock(0))
        try:
            with mock.patch.object(CS, 'LOCK_MS', 50):
                with self.assertRaises(OSError):
                    CS.keep(DocTab(Document()), 'x', where=d)
        finally:
            other.unlock()

    def test_unreadable_entry_dropped(self):
        from vectordrive.ui import closed_store as CS
        from vectordrive.ui.doctabs import DocTab
        from vectordrive.core.document import Document
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            k = CS.keep(DocTab(Document()), 'abîmé')
            (k.where / k.file).write_bytes(b'pas un zip')
            self.assertFalse(w.reopen_tab(k))
            self.assertEqual([e.uid for e in CS.entries()], [])
        finally:
            w.close()
            w.deleteLater()


if __name__ == '__main__':
    unittest.main()
