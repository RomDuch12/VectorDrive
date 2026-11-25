"""Round 1154 (demande du 24/11) : « Possibilité de renommer des onglets_fichiers même si non enregistrés, l'onglet se
nomme au nom du fichier lors de la sauvegarde, possibilité d'épingler les onglets_fichiers. Si on quitte alors que des
onglets sont non enregistrés, pas de popup enregistrement slencieux qui réapparait à la réouverture appli avec l'étoile
comme si ce n'était toujours pas sauvegardé; »."""
import os
import pathlib
import shutil
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1154.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ.setdefault('VECTORDRIVE_CLOSED_TABS', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ.setdefault('VECTORDRIVE_KEYS_MEMORY', '1')

from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox  # noqa: E402

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Shape  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : un onglet ne se renommait ni ne s’épinglait, et rien ne revenait seul au lancement sans la session'
KEY = 'fichiers/a_rouvrir'


def square(x=0.0):
    return Shape(path=geom.Path([geom.rect(x, 0, 10, 10)]), tool=1)


def draw(w, x=0.0):
    w.push_undo('essai')
    w.canvas.doc.add(square(x))
    w.canvas.invalidate()
    w._on_doc_changed()


def make_file(name='piece.vdz'):
    """Un vrai .vdz dans un dossier temporaire."""
    from vectordrive.io import native
    doc = Document()
    doc.add(square())
    p = os.path.join(tempfile.mkdtemp(), name)
    native.write(doc, p)
    return p


def count(w):
    return sum(len(L.items) for L in w.canvas.doc.layers)


class Base(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui import closed_store
        self.store = pathlib.Path(closed_store.folder())
        shutil.rmtree(self.store, ignore_errors=True)
        self.wins = []
        self.w = self.window()
        for k in ('options/garder_onglets', 'fichiers/onglets_fermes', KEY):
            self.w.settings.remove(k)
        self.ask = mock.patch.object(QMessageBox, 'exec', side_effect=AssertionError('question posée'))
        self.asked = self.ask.start()
        self.addCleanup(self.ask.stop)

    def window(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        if not w.docs:
            w.new_document()
        self.wins.append(w)
        return w

    def really_close(self, w):
        """La fenêtre fermée pour de bon, comme par l'utilisateur ; rend vrai si elle s'est fermée."""
        ok = w.close()
        if ok:
            self.wins.remove(w)
            w.deleteLater()
        return ok

    def without_session(self, w):
        """La fenêtre sans session silencieuse (l'option « tout rouvrir au démarrage » décochée)."""
        lock = getattr(w, '_session_lock', None)
        if lock is not None:
            lock.unlock()
            w._session_lock = None
        w.session_dir = None

    def tearDown(self):
        st = self.w.settings
        for w in self.wins:
            w.agent_lock(None)
            for t in w.docs:
                t.modified = False
            w.modified = False
            w.close()
            w.deleteLater()
        for k in ('options/garder_onglets', 'fichiers/onglets_fermes', KEY, 'dossier/enregistrer'):
            st.remove(k)
        app.processEvents()
        shutil.rmtree(self.store, ignore_errors=True)


class Rename(Base):
    def test_rename_a_never_saved_tab(self):
        w = self.w
        self.assertTrue(w.rename_tab(name='  Plaque   Dupont '), BEFORE)
        t = w.docs[w.doc_index]
        self.assertEqual(t.title, 'Plaque Dupont')
        self.assertEqual(t.label(), 'Plaque Dupont')
        self.assertEqual(w.doc_bar.tabs.tabText(w.doc_index), 'Plaque Dupont')
        self.assertTrue(w.windowTitle().startswith('Plaque Dupont — '), w.windowTitle())
        self.assertFalse(w.modified)                                        # un nom n'est pas une modification
        self.assertIsNone(w.path)                                           # ni un fichier
        draw(w)
        self.assertEqual(w.doc_bar.tabs.tabText(w.doc_index), 'Plaque Dupont *')
        self.assertTrue(w.windowTitle().startswith('Plaque Dupont * — '), w.windowTitle())
        self.assertFalse(t.pristine())                                      # pas remplacé par une ouverture

    def test_named_empty_tab_is_not_replaced(self):
        w = self.w
        w.rename_tab(name='À faire')
        self.assertTrue(w.open_path(make_file()))
        self.assertEqual([t.name() for t in w.docs], ['À faire', 'piece.vdz'], BEFORE)

    def test_save_offers_the_name_then_the_tab_takes_the_file_name(self):
        w = self.w
        recent = w.settings.value('fichiers/recents', [])
        self.addCleanup(lambda: w.settings.setValue('fichiers/recents', recent))
        draw(w)
        w.rename_tab(name='Plaque: Dupont / v2')
        out = os.path.join(tempfile.mkdtemp(), 'autre.vdz')
        with mock.patch.object(QFileDialog, 'getSaveFileName', return_value=(out, '')) as ask:
            w.save()                                                        # jamais enregistré : « Enregistrer sous »
        offered = pathlib.Path(ask.call_args[0][2]).name
        self.assertEqual(offered, 'Plaque_ Dupont _ v2', BEFORE)            # le nom donné, permis comme nom de fichier
        self.assertTrue(os.path.isfile(out))
        t = w.docs[w.doc_index]
        self.assertEqual(t.title, '')                                       # l'onglet prend le nom du fichier
        self.assertEqual(w.doc_bar.tabs.tabText(w.doc_index), 'autre.vdz')
        self.assertTrue(w.windowTitle().startswith('autre.vdz — '), w.windowTitle())
        self.assertEqual(pathlib.Path(w.path), pathlib.Path(out))

    def test_save_as_without_a_name_shows_the_file_name_at_once(self):
        w = self.w
        recent = w.settings.value('fichiers/recents', [])
        self.addCleanup(lambda: w.settings.setValue('fichiers/recents', recent))
        draw(w)
        out = os.path.join(tempfile.mkdtemp(), 'neuf.vdz')
        with mock.patch.object(QFileDialog, 'getSaveFileName', return_value=(out, '')):
            w.save_as()
        self.assertEqual(w.doc_bar.tabs.tabText(w.doc_index), 'neuf.vdz', BEFORE)
        self.assertTrue(w.windowTitle().startswith('neuf.vdz — '), w.windowTitle())

    def test_display_name_of_a_file_and_empty_name(self):
        w = self.w
        p = make_file('piece.vdz')
        before = pathlib.Path(p).read_bytes()
        self.assertTrue(w.open_path(p))
        self.assertTrue(w.rename_tab(name='Essai client'), BEFORE)
        self.assertEqual(w.doc_bar.tabs.tabText(w.doc_index), 'Essai client')
        self.assertEqual(pathlib.Path(w.path), pathlib.Path(p))             # le fichier n'est ni renommé ni écrit
        self.assertEqual(pathlib.Path(p).read_bytes(), before)
        self.assertFalse(w.modified)
        self.assertEqual(w.doc_bar.tabs.tabToolTip(w.doc_index), w.path)    # la bulle dit toujours le fichier
        self.assertTrue(w.reload_tab(confirm=False))                        # relu du disque : le nom reste
        self.assertEqual(w.docs[w.doc_index].title, 'Essai client')
        self.assertTrue(w.rename_tab(name='   '))                           # vide : le nom d'origine
        self.assertEqual(w.docs[w.doc_index].title, '')
        self.assertEqual(w.doc_bar.tabs.tabText(w.doc_index), 'piece.vdz')
        self.assertTrue(w.windowTitle().startswith('piece.vdz — '), w.windowTitle())
        w.rename_tab(name='piece.vdz')                                      # son propre nom : rien à retenir
        self.assertEqual(w.docs[w.doc_index].title, '')

    def test_double_click_asks_for_the_name(self):
        from vectordrive.ui.doctabs import DocTab, DocTabBar
        bar = DocTabBar()
        self.addCleanup(bar.deleteLater)
        bar.sync([DocTab(Document()), DocTab(Document(), title='Nommé')], 0)
        self.assertEqual(bar.tabs.tabText(1), 'Nommé')
        self.assertEqual(bar.tabs.tabToolTip(1), 'Nommé')
        got, new = [], []
        bar.renameRequested.connect(got.append)
        bar.newRequested.connect(lambda: new.append(1))
        bar.tabs.tabBarDoubleClicked.emit(1)                                # sur un onglet : le renommer
        bar.tabs.tabBarDoubleClicked.emit(-1)                               # à côté : un nouveau dessin, comme avant
        self.assertEqual((got, new), ([1], [1]))
        del got[:]
        bar.resize(400, 30)
        pos = QPointF(bar.tabs.tabRect(1).center())
        for button, want in ((Qt.MouseButton.MiddleButton, []), (Qt.MouseButton.LeftButton, [1])):
            QApplication.sendEvent(bar.tabs, QMouseEvent(QEvent.Type.MouseButtonDblClick, pos, pos, button, button,
                                                         Qt.KeyboardModifier.NoModifier))
            self.assertEqual(got, want)                                     # le bouton gauche seulement
        w = self.w
        draw(w)
        w.new_document()
        with mock.patch.object(w, 'rename_tab') as rename:                  # la fenêtre : sa fonction, sans fenêtre
            w.doc_bar.renameRequested.emit(0)                               # modale ici
            app.processEvents()
            rename.assert_called_once_with(0)
            rename.reset_mock()
            w.doc_bar.renameRequested.emit(1)
            self.assertTrue(w.close_tab(1, answer='discard'))               # fermé avant que la question s'ouvre
            app.processEvents()
            rename.assert_not_called()                                      # l'onglet resté n'est pas renommé pour lui

    def test_menu_has_rename_and_pin(self):
        w = self.w
        m = w.doc_tab_menu(w.doc_index, exec_menu=False)
        self.addCleanup(m.deleteLater)
        acts = {a.text(): a for a in m.actions()}
        self.assertIn('Renommer…', acts, BEFORE)
        self.assertIn('Épingler', acts)
        self.assertTrue(acts['Fermer'].isEnabled())
        acts['Épingler'].trigger()
        self.assertTrue(w.docs[w.doc_index].pinned)
        m2 = w.doc_tab_menu(w.doc_index, exec_menu=False)
        self.addCleanup(m2.deleteLater)
        acts = {a.text(): a for a in m2.actions()}
        self.assertNotIn('Épingler', acts)
        self.assertFalse(acts['Fermer'].isEnabled())                        # d'abord retirer l'épingle
        acts['Détacher l’épingle'].trigger()
        self.assertFalse(w.docs[w.doc_index].pinned)

    def test_duplicate_takes_the_name_not_the_pin(self):
        w = self.w
        draw(w)
        w.rename_tab(name='Modèle')
        w.pin_tab()
        w.duplicate_tab()
        self.assertEqual(len(w.docs), 2)
        t = w.docs[w.doc_index]
        self.assertEqual(t.title, 'Modèle (copie)', BEFORE)
        self.assertFalse(t.pinned)
        self.assertEqual([x.pinned for x in w.docs], [True, False])


class Pin(Base):
    def three(self):
        w = self.w
        draw(w)
        w.new_document()
        draw(w, 20.0)
        w.new_document()
        draw(w, 40.0)
        self.assertEqual(len(w.docs), 3)
        return w, list(w.docs)

    def texts(self):
        return [self.w.doc_bar.tabs.tabText(k) for k in range(self.w.doc_bar.tabs.count())]

    def test_pinned_tab_goes_left_and_stays_there(self):
        w, (a, b, c) = self.three()
        self.assertTrue(w.pin_tab(2), BEFORE)                               # le 3e, affiché
        self.assertEqual([t is x for t, x in zip(w.docs, (c, a, b))], [True] * 3)
        self.assertIs(w.docs[w.doc_index], c)                               # toujours l'onglet affiché
        self.assertEqual(count(w), 1)
        self.assertEqual(c.label(), '📌 ' + c.name() + ' *')
        self.assertEqual(self.texts(), [t.label() for t in w.docs])
        self.assertEqual(w.doc_bar.tabs.currentIndex(), 0)
        w.doc_bar.tabs.moveTab(0, 2)                                        # traîné après les autres : remis à gauche
        self.assertIs(w.docs[0], c)
        w.doc_bar.released.emit()                                           # souris relâchée : la barre d'accord
        self.assertEqual(self.texts(), [t.label() for t in w.docs])
        self.assertEqual(w.doc_bar.tabs.currentIndex(), w.doc_index)
        w.doc_bar.tabs.moveTab(2, 0)                                        # un libre traîné devant lui : posé au
        self.assertEqual([t is x for t, x in zip(w.docs, (c, b, a))], [True] * 3)     # plus près, premier des libres
        w.doc_bar.tabs.moveTab(1, 2)                                        # entre onglets libres : permis, comme avant
        self.assertEqual([t is x for t, x in zip(w.docs, (c, a, b))], [True] * 3)
        w.pin_tab(2)                                                        # un 2e épinglé : après le premier
        self.assertEqual([t is x for t, x in zip(w.docs, (c, b, a))], [True] * 3)
        self.assertFalse(w.pin_tab(0))                                      # épingle retirée : premier des libres
        self.assertEqual([t is x for t, x in zip(w.docs, (b, c, a))], [True] * 3)
        self.assertEqual(self.texts(), [t.label() for t in w.docs])
        self.assertEqual(c.label(), c.name() + ' *')

    def test_pinned_tab_does_not_close_by_mistake(self):
        w, (a, b, c) = self.three()
        w.pin_tab(0)
        self.assertFalse(w.close_tab(0, answer='discard'), BEFORE)          # la croix, le clic du milieu, Ctrl+F4
        self.assertEqual(len(w.docs), 3)
        self.assertIn('pingl', w.statusBar().currentMessage())
        w.doc_bar.closeRequested.emit(0)
        self.assertEqual(len(w.docs), 3)
        w.pin_tab(0, on=False)
        self.assertTrue(w.close_tab(0, answer='discard'))                   # épingle retirée : il se ferme
        self.assertEqual(len(w.docs), 2)
        self.assertFalse(any(t is a for t in w.docs))

    def test_pristine(self):
        from vectordrive.ui.doctabs import DocTab
        self.assertTrue(DocTab(Document()).pristine())
        self.assertFalse(DocTab(Document(), title='x').pristine(), BEFORE)
        self.assertFalse(DocTab(Document(), pinned=True).pristine())
        w = self.w
        w.pin_tab()                                                         # vide mais épinglé : pas remplacé
        w.new_document()
        self.assertEqual(len(w.docs), 2)

    def test_reload_keeps_the_pin(self):
        w = self.w
        p = make_file('fixe.vdz')
        self.assertTrue(w.open_path(p))
        w.pin_tab()
        self.assertTrue(w.reload_tab(confirm=False))
        self.assertEqual(len(w.docs), 1)
        self.assertTrue(w.docs[0].pinned, BEFORE)

    def test_assistant_tab_unchanged(self):
        w, (a, b, c) = self.three()
        w.agent_lock(c)                                                     # l'assistant tient le 3e
        self.addCleanup(w.agent_lock, None)
        w.rename_tab(2, name='Travail')
        w.pin_tab(2)
        self.assertIs(w.agent_tab(), c)                                     # déplacé à gauche : toujours le sien
        self.assertEqual(c.label(), '🔒 📌 Travail *', BEFORE)
        self.assertEqual(self.texts()[0], '🔒 📌 Travail *')
        self.assertFalse(w.close_tab(0, answer='discard'))                  # tenu : refusé, par l'assistant d'abord
        self.assertIn('assistant', w.statusBar().currentMessage())
        w.pin_tab(0, on=False)
        self.assertFalse(w.close_tab(0, answer='discard'))                  # sans épingle : toujours tenu
        self.assertEqual(len(w.docs), 3)
        w.agent_lock(None)
        self.assertEqual(c.label(), 'Travail *')


class Kept(Base):
    def test_store_keeps_name_and_pin(self):
        from vectordrive.ui import closed_store as CS
        from vectordrive.ui.doctabs import DocTab
        d = pathlib.Path(tempfile.mkdtemp())
        t = DocTab(Document(), title='Nom donné', pinned=True)
        CS.keep(t, t.name(), where=d)
        CS.keep(DocTab(Document()), 'Sans titre', where=d)
        named, plain = sorted(CS.entries(d), key=lambda k: k.when)
        self.assertEqual((named.custom, named.pinned, named.name()), ('Nom donné', True, 'Nom donné'), BEFORE)
        self.assertEqual((plain.custom, plain.pinned), ('', False))

    def test_closed_tab_comes_back_with_its_name(self):
        w = self.w
        draw(w)
        w.rename_tab(name='Brouillon')
        w.new_document()
        self.assertTrue(w.close_tab(0))                                     # gardé sans question
        self.assertFalse(self.asked.called)
        self.assertTrue(w.reopen_tab())
        t = w.docs[w.doc_index]
        self.assertEqual((t.title, t.label()), ('Brouillon', 'Brouillon *'), BEFORE)
        self.assertTrue(w.windowTitle().startswith('Brouillon * — '), w.windowTitle())

    def test_session_keeps_name_pin_and_star_without_question(self):
        """Session active (le réglage d'office) : quitter ne demande rien, tout revient, noms et épingles compris."""
        w = self.w
        d = tempfile.mkdtemp()
        self.assertTrue(w.start_session(d))
        p = make_file('ref.vdz')
        self.assertTrue(w.open_path(p))
        draw(w, 60.0)                                                       # un fichier modifié
        w.new_document()
        draw(w)
        w.rename_tab(name='Brouillon')                                      # jamais enregistré, nommé
        w.pin_tab()                                                         # épinglé : passe à gauche
        self.assertTrue(self.really_close(w))
        self.assertFalse(self.asked.called)                                 # aucune question
        w2 = self.window()
        self.assertTrue(w2.start_session(d))
        self.assertEqual(w2.restore_session(), 2)
        self.assertEqual([t.label() for t in w2.docs], ['📌 Brouillon *', 'ref.vdz *'], BEFORE)
        self.assertIsNone(w2.docs[0].path)
        self.assertIs(w2.docs[w2.doc_index], w2.docs[0])                    # l'onglet affiché à la fermeture
        self.assertTrue(w2.windowTitle().startswith('Brouillon * — '), w2.windowTitle())
        self.assertFalse(w2.settings.contains(KEY))                         # la session s'en charge : rien en plus
        self.assertEqual(w2.reopen_kept(), 0)

    def test_session_snapshot_of_a_named_empty_tab(self):
        from vectordrive.ui import session
        w = self.w
        w.rename_tab(name='Projet')
        w.new_document()
        self.assertEqual(len(w.docs), 2, BEFORE)
        entries = [e for e, _doc, _paths in session.snapshot(w)['docs']]
        self.assertEqual([(e['title'], e['pinned']) for e in entries], [('Projet', False)])

    def test_close_without_session_comes_back_at_next_launch(self):
        """Session inactive : la fenêtre se ferme sans question ; au lancement suivant, les onglets gardés à cette
        fermeture reviennent d'eux-mêmes — étoile, nom, épingle, parcours — pas ceux fermés un par un avant."""
        from vectordrive.cam.model import Move, Toolpath
        w = self.w
        self.without_session(w)
        draw(w, 80.0)
        w.new_document()
        self.assertTrue(w.close_tab(0))                                     # fermé à la main plus tôt : pas rouvert
        p = make_file('net.vdz')
        self.assertTrue(w.open_path(p))                                     # un fichier intact : rien à garder
        w.new_document()
        draw(w)
        draw(w, 20.0)
        w.rename_tab(name='Urgent')
        w.pin_tab()
        tp = Toolpath(op_id='o', tool_id='t', name='essai', moves=[Move('rapid', 0, 0, 5), Move('feed', 10, 0, -1)])
        w.cam_panel.display([tp])
        uid = w.docs[w.doc_index].uid
        self.assertTrue(self.really_close(w))
        self.assertFalse(self.asked.called)                                 # jamais de question
        self.assertEqual(len(list(self.store.glob('*.vdz'))), 2)
        w2 = self.window()                                                  # le lancement suivant
        self.assertEqual(w2.reopen_kept(), 1, BEFORE)
        self.assertEqual([t.label() for t in w2.docs], ['📌 Urgent *'])
        self.assertTrue(w2.modified)
        self.assertIsNone(w2.path)
        self.assertEqual(count(w2), 2)
        self.assertEqual([len(t.moves) for t in w2.cam_panel.toolpaths], [2])
        self.assertTrue(w2.windowTitle().startswith('Urgent * — '), w2.windowTitle())
        self.assertFalse(w2.settings.contains(KEY))                         # liste vidée
        self.assertEqual(w2.reopen_kept(), 0)
        self.assertEqual(len(w2.docs), 1)
        left = w2.closed_tabs()                                             # l'autre : toujours par Ctrl+Maj+T
        self.assertEqual(len(left), 1)
        self.assertNotIsInstance(left[0], str)
        self.assertNotEqual(left[0].uid, uid)
        # rouvert de lui-même, il reste en sûreté sur le disque sous son identifiant, jusqu'à son enregistrement
        self.assertEqual(w2.docs[0].uid, uid)
        entry = self.store / f'{uid}.vdz'
        self.assertTrue(entry.is_file())
        recent = w2.settings.value('fichiers/recents', [])
        self.addCleanup(lambda: w2.settings.setValue('fichiers/recents', recent))
        out = os.path.join(tempfile.mkdtemp(), 'urgent.vdz')
        with mock.patch.object(QFileDialog, 'getSaveFileName', return_value=(out, '')):
            w2.save_as()
        self.assertTrue(os.path.isfile(out))
        self.assertFalse(entry.is_file())                                   # enregistré : la copie périmée oubliée
        self.assertEqual([t.label() for t in w2.docs], ['📌 urgent.vdz'])

    def test_modified_file_comes_back_with_its_path(self):
        w = self.w
        self.without_session(w)
        p = make_file('plaque.vdz')
        before = pathlib.Path(p).read_bytes()
        self.assertTrue(w.open_path(p))
        draw(w, 30.0)
        self.assertTrue(self.really_close(w))
        self.assertEqual(pathlib.Path(p).read_bytes(), before)              # le fichier n'est jamais écrit
        w2 = self.window()
        self.assertEqual(w2.reopen_kept(), 1, BEFORE)
        self.assertEqual([t.label() for t in w2.docs], ['plaque.vdz *'])
        self.assertEqual(pathlib.Path(w2.path), pathlib.Path(p))
        self.assertEqual(count(w2), 2)

    def test_cancelled_close_reopens_nothing(self):
        from vectordrive.ui import closed_store
        w = self.w
        self.without_session(w)
        draw(w)
        w.new_document()
        draw(w, 30.0)
        real, calls = closed_store.keep, []

        def keep_once(*a, **k):                                             # le 2e ne s'écrit pas : la question
            calls.append(1)
            if len(calls) > 1:
                raise OSError('plein')
            return real(*a, **k)
        with mock.patch.object(closed_store, 'keep', side_effect=keep_once), \
                mock.patch.object(w, '_ask_save', return_value='cancel'):
            self.assertFalse(w.close())                                     # Annuler : la fenêtre reste
        self.assertFalse(w.settings.contains(KEY))
        w2 = self.window()
        self.assertEqual(w2.reopen_kept(), 0, BEFORE)
        self.assertTrue(w2.docs[0].pristine())

    def test_option_off_keeps_nothing_to_reopen(self):
        w = self.w
        self.without_session(w)
        w.settings.setValue('options/garder_onglets', False)
        draw(w)
        with mock.patch.object(w, '_ask_save', return_value='discard') as ask:
            self.assertTrue(self.really_close(w))
        self.assertEqual(ask.call_count, 1)                                 # la question, comme avant
        w2 = self.window()
        self.assertEqual(w2.reopen_kept(), 0, BEFORE)

    def test_unreadable_entry_is_skipped(self):
        w = self.w
        self.without_session(w)
        draw(w)
        w.rename_tab(name='Abîmé')
        w.new_document()
        draw(w, 30.0)
        w.rename_tab(name='Bon')
        bad = self.store / f'{w.docs[0].uid}.vdz'
        self.assertTrue(self.really_close(w))
        self.assertTrue(bad.is_file())
        bad.write_bytes(b'pas un dessin')
        w2 = self.window()
        self.assertEqual(w2.reopen_kept(), 1, BEFORE)                       # l'autre revient quand même
        self.assertEqual([t.label() for t in w2.docs], ['Bon *'])
        self.assertFalse(self.asked.called)
        self.assertTrue(bad.is_file())                                      # l'illisible n'est pas effacé
        self.assertIn('laissé', w2.statusBar().currentMessage())            # et compté dans le message
        self.assertEqual([k.uid for k in w2.closed_tabs()], [bad.stem])     # toujours dans « Rouvrir un onglet fermé »
        self.assertFalse(w2.settings.contains(KEY))

    def test_no_second_tab_of_a_file_already_open(self):
        w = self.w
        self.without_session(w)
        p = make_file('plaque.vdz')
        self.assertTrue(w.open_path(p))
        draw(w, 30.0)
        uid = w.docs[w.doc_index].uid
        self.assertTrue(self.really_close(w))
        pending = w.settings.value(KEY)
        w2 = self.window()
        self.assertTrue(w2.open_path(p))
        draw(w2, 50.0)                                                      # ouvert et modifié ici : l'entrée attend
        self.assertEqual(w2.reopen_kept(), 0, BEFORE)
        self.assertEqual([t.label() for t in w2.docs], ['plaque.vdz *'])
        self.assertEqual(count(w2), 2)
        self.assertTrue((self.store / f'{uid}.vdz').is_file())
        w2.settings.setValue(KEY, pending)
        w3 = self.window()
        self.assertTrue(w3.open_path(p))                                    # ouvert, intact : rouvert dans son onglet
        self.assertEqual(w3.reopen_kept(), 1)
        self.assertEqual([t.label() for t in w3.docs], ['plaque.vdz *'])
        self.assertEqual(count(w3), 2)                                      # le dessin gardé (carré ajouté à 30)
        self.assertEqual(w3.docs[0].uid, uid)

    def test_last_drawing_not_opened_twice_at_start(self):
        w = self.w
        self.without_session(w)
        recent = w.settings.value('fichiers/recents', [])
        self.addCleanup(lambda: w.settings.setValue('fichiers/recents', recent))
        self.addCleanup(w.settings.remove, 'options/ouvrir_dernier')
        p = make_file('dernier.vdz')
        self.assertTrue(w.open_path(p))                                     # déjà là (rouvert des onglets gardés)
        w.settings.setValue('options/ouvrir_dernier', True)
        with mock.patch.object(w, 'open_path') as again:
            w._startup_view()
            app.processEvents()
        again.assert_not_called()

    def test_launcher_reopens_at_start(self):
        src = (pathlib.Path(__file__).resolve().parents[1] / 'VectorDrive.py').read_text(encoding='utf-8')
        self.assertIn('    if not args.new_window and not args.script:', src, BEFORE)     # lancement normal seulement
        call = src.index('w.reopen_kept()')
        self.assertLess(src.index('w.restore_session()'), call)
        self.assertLess(src.index('if not args.new_window and not args.script:'), call)
        from vectordrive.ui.main_window import MainWindow
        self.assertTrue(KEY.startswith(MainWindow.LOCAL_KEYS))              # propre au poste : jamais exporté


if __name__ == '__main__':
    unittest.main()
