"""Round 1180 (demandes du 27/11) : « import depuis ancienne version attention à garder bibliothèque et parcours à
calculer » ; retour terrain « reprendre ses réglages oublie éléments sus-mentionnés et dossiers favoris » ;
« ajouter boutons exports/imports configuration/réglages » ; « param onglets épinglés + labels ».

Une version portable neuve reprend une ancienne : sa session passe comme une mise à jour (onglets, parcours, mémo ;
jamais un verrou), ses réglages (dossiers favoris compris), données et bibliothèque fichier par fichier avec un
bilan ; plusieurs versions posées à côté : on choisit ; l'ancienne encore ouverte : détectée sans toucher à son
verrou, et le lancement n'est plus renvoyé vers elle ; F10 › Mises à jour › Configuration ; .vdparam complet
(bibliothèque, polices, scripts, assistant, onglets épinglés, données déclarées par les plugins, jamais de jeton).
1re relecture : reprise coupée terminée au lancement suivant, Annuler entre deux fichiers, rien de déjà là remplacé
(« Mes outils » fusionnés), secrets sans faux positifs, présélection par édition et usage réel, un seul lancement
pose la question, Échap = Réessayer, verrou du processus courant écarté, ancienne ouverte vue par son processus.

Tout se passe dans des dossiers temporaires ; aucune vraie boîte n'est ouverte (fenêtres construites sans `exec`,
`QMessageBox.exec` remplacé par un clic) ; un seul processus lancé, le temps de laisser un vrai verrou Qt mort (il
s'arrête de lui-même) ; le seul canal ouvert porte un nom tiré au hasard."""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
import zipfile
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ.setdefault('VECTORDRIVE_KEYS_MEMORY', '1')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'radopt.ini'))

from PySide6.QtCore import QLockFile, QSettings, QSysInfo  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive import app_update as AU  # noqa: E402
from vectordrive import portable as P  # noqa: E402

BEFORE = 'avant : la reprise d’une ancienne version copiait sa session telle quelle, sans bilan ni choix'
EMPTY_INI = '; VectorDrive portable : réglages enregistrés ici\n'
ED = 'B' + 'FM'
SETTINGS_ENV = os.environ['VECTORDRIVE_SETTINGS']


def need(obj, *names):
    for n in names:
        if not hasattr(obj, n):
            raise AssertionError(f'{BEFORE} ({n} absent)')


def make_version(box, name, keys=None, files=None) -> pathlib.Path:
    """Une version portable décompressée : box/name/VectorDrive/ avec l'exe, l'ini, des fichiers."""
    app_dir = pathlib.Path(box) / name / 'VectorDrive'
    app_dir.mkdir(parents=True)
    (app_dir / 'VectorDrive.exe').write_bytes(b'MZ')
    (app_dir / P.INI).write_text(EMPTY_INI, encoding='utf-8')
    if keys:
        s = QSettings(str(app_dir / P.INI), QSettings.Format.IniFormat)
        for k, v in keys.items():
            s.setValue(k, v)
        s.sync()
    for rel, text in (files or {}).items():
        f = app_dir / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(text if isinstance(text, bytes) else text.encode('utf-8'))
    return app_dir


def keys_of(app_dir) -> dict:
    s = QSettings(str(pathlib.Path(app_dir) / P.INI), QSettings.Format.IniFormat)
    return {k: s.value(k) for k in s.allKeys()}


def listed(v) -> list:
    return [] if v in (None, '') else list(v) if isinstance(v, (list, tuple)) else [v]


def toolpath():
    from vectordrive.cam.model import Move, Toolpath
    return Toolpath(op_id='op1', tool_id='t1', name='Contour', moves=[Move('rapid', 0, 0, 5), Move('plunge', 0, 0, -1),
                                                                     Move('feed', 10, 0, -1)])


def square_doc():
    from vectordrive.core import geom
    from vectordrive.core.document import Document, Shape
    doc = Document()
    doc.add(Shape(path=geom.Path([geom.rect(0, 0, 20, 8)])))
    return doc


def write_old_session(app_dir, box) -> dict:
    """La session d'une ancienne version écrite par `session.write` : un dessin jamais enregistré, épinglé et renommé,
    avec un parcours calculé et le mémo de son calcul ; un dessin enregistré (fichier .vdz réel), l'onglet actif."""
    from vectordrive.io import native, registry
    from vectordrive.ui import session
    saved = pathlib.Path(box) / 'dessins' / 'plaque enregistrée.vdz'
    saved.parent.mkdir(parents=True, exist_ok=True)
    registry.save_document(square_doc(), saved)
    memo = {'_computed': ['op1']}
    e1 = {'path': None, 'modified': True, 'view': None, 'source': None, 'file': None, 'paths': None,
          'current': False, 'uid': 'u1', 'title': 'Plaque client', 'pinned': True, 'cam': memo}
    e2 = {'path': str(saved), 'modified': False, 'view': None, 'source': None, 'file': None, 'paths': None,
          'current': True, 'uid': 'u2', 'title': '', 'pinned': False}
    folder = pathlib.Path(app_dir) / 'donnees' / 'session'
    session.write({'docs': [(e1, native.snapshot(square_doc()), [toolpath()]), (e2, None, None)], 'written': {}},
                  folder)
    return {'saved': saved, 'memo': memo, 'folder': folder}


def foreign_lock(lock: pathlib.Path) -> bytes:
    """Un verrou de session tenu par un autre processus vivant (le parent de cet essai) : l'ancienne version ouverte.
    Jamais celui de ce processus-ci, que `session_held` écarte (numéro repris)."""
    pid = os.getppid()
    alive, exe = P._process(pid)
    if not alive:
        raise unittest.SkipTest('processus parent introuvable')
    data = f'{pid}\n{exe or "sh"}\n{QSysInfo.machineHostName()}\n'.encode('utf-8')
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_bytes(data)
    return data


def vectordrive_main():
    """`VectorDrive.py` de cet arbre, chargé comme un module (rien n'y est lancé)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('vectordrive_main_radopt',
                                                  pathlib.Path(__file__).resolve().parents[1] / 'VectorDrive.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def qt_dead_lock(box, lock: pathlib.Path) -> bytes:
    """Un vrai verrou écrit par Qt dans un autre processus, arrêté net : le fichier reste, mort. Rend son contenu."""
    script = pathlib.Path(box) / 'verrou_mort.py'
    script.write_text('import os, sys\nfrom PySide6.QtCore import QLockFile\nlock = QLockFile(sys.argv[1])\n'
                      'lock.tryLock(0)\nos._exit(0)\n', encoding='utf-8')
    subprocess.run([sys.executable, '-I', str(script), str(lock)], check=True, timeout=120)
    assert lock.is_file()
    return lock.read_bytes()


def direct(fn):
    """Les copies d'une reprise sans fenêtre de progression."""
    return fn()


class Killed(BaseException):
    """Le processus arrêté net pendant la copie."""


def tree_of(folder) -> dict:
    """Chaque fichier d'un dossier : ses octets et sa date (rien de changé : identique)."""
    return {p.relative_to(folder).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in pathlib.Path(folder).rglob('*') if p.is_file()}


def handovers(app_dir) -> list:
    return AU.pending_handovers(AU.handover_root(app_dir))


class Base(unittest.TestCase):
    """Une nouvelle version portable (`self.new`, VectorDrive.ini vide) posée à côté d'anciennes."""

    def setUp(self):
        self.box = pathlib.Path(tempfile.mkdtemp(prefix='radopt_'))
        self.env = mock.patch.dict(os.environ, {})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.addCleanup(shutil.rmtree, self.box, True)
        self.new = make_version(self.box, f'VectorDrive-{ED}-9.9.9-portable')
        os.environ['VECTORDRIVE_PORTABLE_DIR'] = str(self.new)   # jamais le registre du poste
        os.environ.pop('VECTORDRIVE_SETTINGS', None)
        P.LAST = None
        P.WAITED = False
        for name, value in (('BUSY', False), ('FORCED', False), ('WAIT_END', '')):
            if hasattr(P, name):
                setattr(P, name, value)

    def old(self, name=f'VectorDrive-{ED}-1.29.0-portable', keys=None, files=None):
        return make_version(self.box, name, keys or {'options/decimales': 3}, files)


# --- 1. le verrou, la session passée comme une mise à jour ----------------------------------------------------
class Lock(Base):

    def test_lock_and_temporary_files_never_copied_session_passed(self):
        need(AU, 'pending_handovers')
        old = self.old(files={'donnees/outils/verrou.lock': 'x', 'bibliotheque/a.lock': 'x'})
        info = write_old_session(old, self.box)
        (info['folder'] / 'session.lock').write_text(f'999999\npython\n{QSysInfo.machineHostName()}\n',
                                                     encoding='utf-8')          # verrou mort (version arrêtée net)
        (info['folder'] / 'session.json.tmp').write_text('{}', encoding='utf-8')
        (info['folder'] / 'parcours_u9.vdp.tmp').write_bytes(b'x')
        self.assertEqual(P.offer_previous(lambda name: True), old)
        self.assertEqual([p for p in self.new.rglob('*') if p.name.lower().endswith('.lock')], [])
        self.assertFalse((self.new / 'donnees' / 'session').exists())        # sa propre session : jamais remplie
        passed = AU.pending_handovers(AU.handover_root(self.new))
        self.assertEqual(len(passed), 1, BEFORE)
        names = sorted(p.name for p in passed[0].iterdir())
        self.assertIn('dessin_0.vdz', names)
        self.assertIn('parcours_u1.vdp', names)
        self.assertFalse([n for n in names if n.endswith('.tmp')])
        self.assertEqual(P.LAST.tabs, 2)

    def test_new_version_takes_its_own_session_while_old_is_open(self):
        from vectordrive.ui.main_window import MainWindow
        old = self.old()
        write_old_session(old, self.box)
        lock = old / 'donnees' / 'session' / 'session.lock'
        held = foreign_lock(lock)                                           # l'ancienne, ouverte
        asked = []

        def ask(name, held=False):
            asked.append(held)
            return True                                                     # « Reprendre sans attendre »
        try:
            P.offer_previous(ask)
        except TypeError:
            raise AssertionError(BEFORE) from None
        self.assertEqual(asked, [True], BEFORE)
        os.environ['VECTORDRIVE_SETTINGS'] = SETTINGS_ENV
        w = MainWindow()
        self.addCleanup(w.close)
        self.assertTrue(w.start_session(self.new / 'donnees' / 'session'))   # aucun verrou de l'ancienne ici
        self.assertEqual(lock.read_bytes(), held)                           # le sien, intact

    def test_old_folder_identical_byte_for_byte_with_a_real_session(self):
        old = self.old(files={'bibliotheque/Logos BAT/l.svg': '<svg/>', 'donnees/outils/tools.json': '{}'})
        info = write_old_session(old, self.box)
        mine = QLockFile(str(info['folder'] / 'session.lock'))              # tenu par cet essai pendant la reprise
        self.assertTrue(mine.tryLock(0))
        self.addCleanup(mine.unlock)
        self.assertTrue([p for p in info['folder'].iterdir() if p.suffix == '.vdp'])
        before = tree_of(old)
        self.assertEqual(P.offer_previous(lambda name, held=False: True), old)
        self.assertEqual(P.LAST.tabs, 2)
        self.assertEqual(tree_of(old), before)                              # octet pour octet, dates comprises
        P.adopt(old, keep=True, progress=direct)                            # une 2e fois, à la main
        self.assertEqual(tree_of(old), before)


# --- 2. l'ancienne session rouverte, parcours et mémo compris ------------------------------------------------
class Session(Base):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        for t in cls.w.docs:
            t.modified = False
        cls.w.modified = False
        cls.w.close()
        cls.w.deleteLater()
        app.processEvents()

    def test_old_tabs_reopen_with_toolpaths_and_memo(self):
        from vectordrive.ui.doctabs import same_file
        need(AU, 'pending_handovers')
        old = self.old()
        info = write_old_session(old, self.box)
        P.offer_previous(lambda name: True)
        passed = AU.pending_handovers(AU.handover_root(self.new))
        self.assertEqual(len(passed), 1, BEFORE)
        index = json.loads((passed[0] / 'session.json').read_text(encoding='utf-8'))
        self.assertEqual(index['docs'][0]['cam'], info['memo'])               # le mémo du calcul, passé
        w = self.w
        n = w.reopen_after_update()
        self.assertEqual(n, 2)
        tab = next(t for t in w.docs if t.title == 'Plaque client')
        self.assertTrue(tab.pinned)
        self.assertTrue(tab.modified)
        self.assertTrue(same_file(w.docs[w.doc_index].path, str(info['saved'])))     # l'onglet actif
        w.switch_tab(w.docs.index(tab))
        self.assertEqual([len(tp.moves) for tp in w.cam_panel.toolpaths], [3])         # le parcours calculé
        self.assertEqual(AU.pending_handovers(AU.handover_root(self.new)), [])       # rouvert une fois

    def test_unreadable_index_or_session_off_passes_nothing(self):
        need(P, 'adoption_pending')
        old = self.old(files={'donnees/session/session.json': 'pas un index', 'donnees/session/dessin_0.vdz': 'x'})
        P.offer_previous(lambda name: True)
        self.assertEqual(AU.pending_handovers(AU.handover_root(self.new)), [])
        self.assertFalse((self.new / 'donnees' / 'session').exists())
        self.assertEqual(len(P.LAST.failed), 1)                             # dit, jamais en silence
        self.assertIn('session illisible', P.LAST.failed[0])
        self.assertEqual(P.LAST.tabs, 0)
        new2 = make_version(self.box / 'b', 'VectorDrive-9.9.8-portable')
        off = make_version(self.box / 'b', 'VectorDrive-1.0.0-portable', {'options/session': False})
        write_old_session(off, self.box)
        res = P.adopt(off, new2)
        self.assertEqual((res.tabs, res.handover), (0, None))               # session d'autrefois : jamais rouverte
        self.assertTrue(old.is_dir())


# --- 2 bis. reprise coupée, annulée, session enregistrée pendant la copie -----------------------------------
class Interrupted(Base):

    def test_killed_during_the_copy_is_finished_at_the_next_launch(self):
        need(P, 'ADOPTING')
        old = self.old(keys={'navigateur/favoris': ['P:\\a'], 'options/decimales': 3},
                       files={'bibliotheque/Logos BAT/l.svg': 'x', 'donnees/modeles_fao/alu.json': '{}'})
        write_old_session(old, self.box)
        with mock.patch.object(AU, 'carry_settings', side_effect=Killed()):
            with self.assertRaises(Killed):
                P.offer_previous(lambda name: True, progress=direct)
        self.assertTrue((self.new / P.ADOPTING).is_file())                  # la marque reste
        self.assertEqual(keys_of(self.new), {})                             # réglages : en dernier, pas encore
        self.assertEqual(len(handovers(self.new)), 1)                       # la session : passée d'abord
        self.assertTrue(P.adoption_pending())
        got = P.offer_previous(lambda *a, **k: self.fail('déjà acceptée'), progress=direct)
        self.assertEqual(got, old)
        self.assertEqual(len(handovers(self.new)), 1)                       # jamais doublée
        self.assertEqual(P.LAST.tabs, 2)
        self.assertEqual(listed(keys_of(self.new)['navigateur/favoris']), ['P:\\a'])
        self.assertTrue((self.new / 'bibliotheque/Logos BAT/l.svg').is_file())
        self.assertFalse((self.new / P.ADOPTING).exists())
        self.assertFalse(P.adoption_pending())

    def test_cancel_stops_between_files_settings_still_taken(self):
        from vectordrive.core.progress import Cancelled
        old = self.old(keys={'navigateur/favoris': ['P:\\a', 'P:\\b']}, files={'bibliotheque/a.svg': 'x'})
        write_old_session(old, self.box)
        with mock.patch.object(AU, 'carry_settings', side_effect=Cancelled()):
            P.offer_previous(lambda name: True, progress=direct)
        self.assertTrue(P.LAST.stopped)
        self.assertEqual(P.LAST.tabs, 2)                                    # la session, passée avant
        self.assertEqual(len(listed(keys_of(self.new)['navigateur/favoris'])), 2)
        self.assertFalse((self.new / P.ADOPTING).exists())
        self.assertFalse((self.new / 'bibliotheque').exists())
        from vectordrive.ui.main_window import MainWindow
        self.assertIn('Copie arrêtée', MainWindow.adoption_text(None, P.LAST))

    def test_progress_window_by_default(self):
        old = self.old(files={'bibliotheque/a.svg': 'x'})
        seen = []
        real = P.run_with_progress

        def spy(fn, parent=None):
            seen.append(parent)
            return real(fn, parent)
        with mock.patch.object(P, 'run_with_progress', spy):
            self.assertEqual(P.offer_previous(lambda name: True), old)
        self.assertEqual(seen, [None])                                      # avant la fenêtre principale
        self.assertTrue((self.new / 'bibliotheque/a.svg').is_file())

    def test_session_never_passed_twice_and_given_up_after_two_tries(self):
        need(AU, 'ADOPT_TRIES')
        old = self.old(keys={'options/decimales': 3}, files={'bibliotheque/a.svg': 'x'})
        write_old_session(old, self.box)
        for n in (1, 2):                                                    # tuée deux fois pendant la copie
            with mock.patch.object(AU, 'carry_settings', side_effect=Killed()):
                with self.assertRaises(Killed):
                    P.offer_previous(lambda *a, **k: n == 1, progress=direct)
            mark = P.adoption_mark(self.new)
            self.assertEqual((mark['tries'], mark['session']), (n, True))
            self.assertEqual(len(handovers(self.new)), 1)                   # la session : une seule fois
        with mock.patch.object(AU, 'carry_settings', side_effect=AssertionError('jamais une 3e copie')):
            P.offer_previous(lambda *a, **k: self.fail('déjà acceptée'), progress=direct)
        self.assertIn('abandonnée', ' '.join(P.LAST.failed))                # dit dans le bilan
        self.assertEqual(P.LAST.tabs, 2)                                    # le passage déjà fait : compté
        self.assertEqual(P.LAST.handover, handovers(self.new)[0])
        self.assertEqual(str(keys_of(self.new)['options/decimales']), '3')  # les réglages, posés quand même
        self.assertIsNone(P.adoption_mark(self.new))
        self.assertFalse(P.adoption_pending())
        self.assertEqual(len(handovers(self.new)), 1)

    def test_half_written_copies_swept_when_a_cut_adoption_resumes(self):
        need(AU, 'sweep_parts')
        self.old(files={'bibliotheque/a.svg': 'x'})
        with mock.patch.object(AU, 'carry_settings', side_effect=Killed()):
            with self.assertRaises(Killed):
                P.offer_previous(lambda *a, **k: True, progress=direct)
        rels = ('bibliotheque/b.svg.vd_copie', 'donnees/outils/tools.json.vd_copie',
                'donnees/session/session.json.vd_copie', 'donnees/session_maj/p1/session.json.vd_copie')
        for rel in rels:
            (self.new / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.new / rel).write_text('moitié', encoding='utf-8')
        P.offer_previous(lambda *a, **k: self.fail('déjà acceptée'), progress=direct)
        self.assertFalse((self.new / rels[0]).exists())
        self.assertFalse((self.new / rels[1]).exists())
        self.assertTrue((self.new / rels[2]).exists())                      # celle de la fenêtre : jamais touchée
        self.assertTrue((self.new / rels[3]).exists())                      # un passage : jamais touché
        self.assertTrue((self.new / 'bibliotheque' / 'a.svg').is_file())

    def test_cancel_wait_never_freezes_the_window(self):
        import inspect
        import threading
        from PySide6.QtCore import QTimer
        need(AU, 'wait_done')
        done = threading.Event()
        later = threading.Timer(0.4, done.set)
        later.start()
        self.addCleanup(later.join)
        ticks = []
        timer = QTimer()
        timer.timeout.connect(lambda: ticks.append(1))
        timer.start(20)
        self.assertTrue(AU.wait_done(done, 10))
        timer.stop()
        self.assertGreater(len(ticks), 3)                                   # la boucle d'évènements a tourné
        self.assertFalse(AU.wait_done(threading.Event(), 0.2))              # borné
        self.assertIn('wait_done(done, STOP_WAIT_S)', inspect.getsource(AU.adopt_previous))

    def test_cancel_waits_for_the_file_in_progress_window_alive(self):
        import threading
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QProgressDialog
        from vectordrive.core.progress import Cancelled
        old = self.old(files={f'bibliotheque/s{i}.svg': 'x' for i in range(3)})
        real = shutil.copy2
        started, release = threading.Event(), threading.Event()

        def slow_copy(src, dst, *a, **k):                                   # le fichier en cours, long
            started.set()
            release.wait(10)
            return real(src, dst, *a, **k)

        def progress(fn):                                                   # comme `ui.progress.run` : la copie
            threading.Thread(target=fn, daemon=True).start()                # dans un fil, Annuler rend la main
            started.wait(10)                                                # aussitôt
            raise Cancelled()
        seen = {}

        def poke():                                                         # pendant l'attente : la fenêtre vit
            boxes = [b for b in QApplication.topLevelWidgets() if isinstance(b, QProgressDialog) and b.isVisible()]
            seen['shown'] = [b.labelText() for b in boxes]
            for b in boxes:
                b.reject()
                b.close()                                                   # Échap, la croix : rien
            seen['still'] = bool(boxes) and all(b.isVisible() for b in boxes)
            release.set()
        QTimer.singleShot(200, poke)
        with mock.patch.object(AU.shutil, 'copy2', slow_copy):
            res = P.adopt(old, progress=progress)
        self.assertEqual(seen['shown'], ['Fin du fichier en cours…'])
        self.assertTrue(seen['still'])
        self.assertTrue(res.stopped)
        self.assertNotIn('provisoire', ' '.join(res.failed))                # fini avant le bilan
        on_disk = len(list((self.new / 'bibliotheque').iterdir()))
        self.assertEqual(res.copied, 1 + on_disk)                           # le bilan dit ce qui est là

    def test_error_during_the_copy_is_said_and_the_adoption_finishes(self):
        old = self.old(files={'bibliotheque/a.svg': 'x'})
        with mock.patch.object(AU, 'merge_tools', side_effect=RuntimeError('disque plein')):
            self.assertEqual(P.offer_previous(lambda name: True, progress=direct), old)
        self.assertIn('disque plein', ' '.join(P.LAST.failed))
        self.assertIsNone(P.adoption_mark(self.new))
        self.assertFalse(P.adoption_pending())

    def test_mark_that_cannot_be_erased_no_longer_counts(self):
        old = self.old()
        with mock.patch.object(P, 'drop_adoption_mark'):                    # effacement raté
            P.offer_previous(lambda name: True, progress=direct)
        self.assertTrue((self.new / P.ADOPTING).is_file())
        self.assertEqual(keys_of(self.new)[P.DONE_KEY], json.loads((self.new / P.ADOPTING).read_text(
            encoding='utf-8'))['tag'])
        self.assertFalse(P.adoption_pending())                              # la note de l'INI suffit
        self.assertIsNone(P.adoption_mark(self.new))
        self.assertFalse((self.new / P.ADOPTING).exists())
        self.assertTrue(old.is_dir())

    def test_cancel_counts_what_was_really_copied(self):
        from vectordrive.core import progress as CP
        old = self.old(files={f'bibliotheque/s{i}.svg': 'x' for i in range(6)})
        real = shutil.copy2

        def cancelling(fn):
            task = CP.Task('essai')
            token = CP.attach(task)
            n = [0]

            def copy(src, dst, *a, **k):
                n[0] += 1
                if n[0] == 2:
                    task.cancel()                                           # Annuler pendant le 2e fichier
                return real(src, dst, *a, **k)
            try:
                with mock.patch.object(AU.shutil, 'copy2', copy):
                    return fn()
            finally:
                CP.detach(token)
        res = P.adopt(old, progress=cancelling)
        self.assertTrue(res.stopped)
        on_disk = len(list((self.new / 'bibliotheque').iterdir()))
        self.assertEqual(on_disk, 2)                                        # le fichier en cours fini, rien après
        self.assertEqual(res.copied, 1 + on_disk)                           # réglages + ce qui est vraiment là

    def test_language_of_the_old_version_said_for_the_next_launch(self):
        self.old(keys={'options/langue': 'en'})
        P.offer_previous(lambda name: True, progress=direct)
        self.assertEqual(P.LAST.language, 'en')
        from vectordrive.ui.main_window import MainWindow
        self.assertIn('prochain lancement', MainWindow.adoption_text(None, P.LAST))

    def test_session_saved_during_the_copy_is_copied_again_once(self):
        old = self.old()
        info = write_old_session(old, self.box)
        index = info['folder'] / 'session.json'
        real = AU._copy_in
        calls = []

        def autosave(src, dst, every=False):
            if not calls or every:                                          # l'ancienne enregistre sa session
                data = json.loads(index.read_text(encoding='utf-8'))
                data['docs'][0]['title'] = f'Plaque client {len(calls)}'
                index.write_text(json.dumps(data), encoding='utf-8')
            calls.append(src)
            return real(src, dst)
        with mock.patch.object(AU, '_copy_in', autosave):
            res = P.adopt(old, progress=direct)
        self.assertEqual(res.failed, [])
        self.assertEqual(len(handovers(self.new)), 1)                       # la 1re copie, effacée
        title = json.loads((res.handover / 'session.json').read_text(encoding='utf-8'))['docs'][0]['title']
        self.assertEqual(title, 'Plaque client 0')
        new2 = make_version(self.box / 'b', 'VectorDrive-9.9.8-portable')
        with mock.patch.object(AU, '_copy_in', lambda s, d: autosave(s, d, every=True)):
            res = P.adopt(old, new2, progress=direct)
        self.assertEqual(len(res.failed), 1)                                # deux fois : dit
        self.assertIn('pendant la copie', res.failed[0])
        self.assertEqual(len(handovers(new2)), 1)


# --- 3. l'ancienne version encore ouverte --------------------------------------------------------------------
class Held(Base):

    def test_held_detected_without_touching_the_lock(self):
        need(P, 'session_held')
        old = self.old()
        lock = old / 'donnees' / 'session' / 'session.lock'
        lock.parent.mkdir(parents=True)
        self.assertFalse(P.session_held(old))
        held = foreign_lock(lock)                                           # un autre processus, vivant
        self.assertTrue(P.session_held(old))
        self.assertEqual(lock.read_bytes(), held)
        lock.unlink()
        mine = QLockFile(str(lock))                                         # celui de ce processus : numéro repris
        self.assertTrue(mine.tryLock(0))
        try:
            before = lock.read_bytes()
            self.assertFalse(P.session_held(old))
            self.assertEqual(lock.read_bytes(), before)
        finally:
            mine.unlock()
        dead = f'999999\npython\n{QSysInfo.machineHostName()}\n'.encode('utf-8')
        lock.write_bytes(dead)                                              # mort : ne compte pas, reste tel quel
        self.assertFalse(P.session_held(old))
        self.assertEqual(lock.read_bytes(), dead)
        lock.unlink()
        written = qt_dead_lock(self.box, lock)                              # un vrai QLockFile, processus arrêté
        self.assertFalse(P.session_held(old))                               # tel que Qt l'écrit (COMPUTERNAME)
        self.assertEqual(lock.read_bytes(), written)
        host = 'POSTE-NOM-LONG'                                             # NetBIOS ≠ nom DNS du poste
        lock.write_bytes(f'999999\nVectorDrive\n{host}\nx\n\n'.encode('utf-8'))
        with mock.patch.dict(os.environ, {'COMPUTERNAME': host}):
            self.assertFalse(P.session_held(old))                           # ce poste : mort, ne compte pas
        with mock.patch.dict(os.environ, {'COMPUTERNAME': 'AUTRE'}):
            self.assertTrue(P.session_held(old))                            # un autre poste : compté tenu

    def test_open_with_its_session_off_is_seen_by_its_window(self):
        need(P, 'running_from')
        old = self.old(keys={'options/session': False})                    # sa session coupée : aucun verrou
        exe = str(old / 'VectorDrive.exe')
        procs = [(11, 'C:\\Windows\\explorer.exe'), (22, exe.upper()), (33, exe)]
        with mock.patch.object(P, '_processes', return_value=procs), \
                mock.patch.object(P, '_windowed_pids', return_value={11, 22}):
            self.assertTrue(P.session_held(old))                            # aucun session.lock : sa fenêtre
        with mock.patch.object(P, '_processes', return_value=procs), \
                mock.patch.object(P, '_windowed_pids', return_value={11, 33 + 1}):
            self.assertFalse(P.session_held(old))                           # sans fenêtre (--mcp, vignettes)
        with mock.patch.object(P, '_processes', side_effect=OSError('refusé')):
            self.assertFalse(P.running_from(old))                           # jamais bloquant
        self.assertFalse(P.running_from(old))                               # le vrai poste : rien depuis ce dossier

    def test_process_list_is_real(self):
        need(P, '_image_paths')
        alive, parent = P._process(os.getppid())
        if not alive or not parent:
            raise unittest.SkipTest('processus parent illisible')
        stems = {pathlib.PureWindowsPath(p).stem.lower() for p in P._image_paths()}
        self.assertIn(parent.lower(), stems)                                # le parent de cet essai y figure
        self.assertNotIn(os.getpid(), {pid for pid, _i in P._processes()})  # jamais celui-ci
        self.assertIsInstance(P._windowed_pids(), set)

    def test_retry_then_closed_proceeds(self):
        need(P, 'RETRY')
        old = self.old()
        lock = old / 'donnees' / 'session' / 'session.lock'
        foreign_lock(lock)
        asked = []

        def ask(name, held=False):
            asked.append((name, held))
            lock.unlink()                                                   # l'utilisateur la ferme, puis Réessayer
            return P.RETRY
        self.assertEqual(P.offer_previous(ask, progress=direct), old)
        self.assertEqual(asked, [(f'VectorDrive-{ED}-1.29.0-portable', True)])
        self.assertEqual(str(keys_of(self.new)['options/decimales']), '3')

    def test_held_start_from_scratch(self):
        need(P, 'RETRY')
        old = self.old(files={'bibliotheque/a.svg': '<svg/>'})
        foreign_lock(old / 'donnees' / 'session' / 'session.lock')
        self.assertIsNone(P.offer_previous(lambda name, held=False: False))
        self.assertEqual(keys_of(self.new), {P.ADOPTED_KEY: 'non'})
        self.assertFalse((self.new / 'bibliotheque').exists())

    def test_held_question_buttons(self):
        need(P, 'RETRY')
        seen = {}

        def click(text):
            def fake_exec(box):
                seen['text'] = box.text()
                seen['buttons'] = sorted(b.text() for b in box.buttons())
                seen['default'] = box.defaultButton().text()
                seen['escape'] = box.escapeButton().text() if box.escapeButton() else ''
                next(b for b in box.buttons() if b.text() == text).click()
                return 0
            return fake_exec
        with mock.patch.object(QMessageBox, 'exec', click('Reprendre sans attendre')):
            self.assertIs(P._ask_adopt('VectorDrive-1.29.0', True, path='D:\\VD\\ancienne'), True)
        self.assertIn('encore ouverte', seen['text'])
        self.assertIn('D:\\VD\\ancienne', seen['text'])
        self.assertEqual(seen['buttons'], ['Partir de zéro', 'Plus tard', 'Reprendre sans attendre', 'Réessayer'])
        self.assertEqual(seen['default'], 'Réessayer')
        self.assertEqual(seen['escape'], 'Réessayer')                       # Échap : jamais « Partir de zéro »
        with mock.patch.object(QMessageBox, 'exec', click('Plus tard')):
            self.assertEqual(P._ask_adopt('VectorDrive-1.29.0', True), P.LATER)
        with mock.patch.object(QMessageBox, 'exec', click('Annuler')):      # F10 : « Annuler », sans « Plus tard »
            self.assertIs(P._ask_adopt('VectorDrive-1.29.0', True, manual=True), False)
        self.assertEqual(seen['buttons'], ['Annuler', 'Reprendre sans attendre', 'Réessayer'])

        def escape(box):
            box.escapeButton().click()                                      # ce que fait Échap ou la croix
            return 0
        with mock.patch.object(QMessageBox, 'exec', escape):
            self.assertEqual(P._ask_adopt('VectorDrive-1.29.0', True), P.RETRY)
        with mock.patch.object(QMessageBox, 'exec', click('Réessayer')):
            self.assertEqual(P._ask_adopt('VectorDrive-1.29.0', True), P.RETRY)
        with mock.patch.object(QMessageBox, 'exec', click('Partir de zéro')):
            self.assertIs(P._ask_adopt('VectorDrive-1.29.0', True), False)
        with mock.patch.object(QMessageBox, 'exec', click('Reprendre ses réglages')):
            self.assertIs(P._ask_adopt('VectorDrive-1.29.0', path='D:\\VD\\x'), True)
        self.assertIn('D:\\VD\\x', seen['text'])


# --- 4. pas de renvoi vers la fenêtre ouverte quand une reprise attend --------------------------------------
class Forward(Base):

    def test_adoption_pending(self):
        need(P, 'adoption_pending')
        self.assertFalse(P.adoption_pending())                              # seule
        self.old()
        self.assertTrue(P.adoption_pending())
        os.environ['VECTORDRIVE_SETTINGS'] = SETTINGS_ENV
        self.assertFalse(P.adoption_pending())                              # essais : jamais
        os.environ.pop('VECTORDRIVE_SETTINGS')
        P.offer_previous(lambda name: False)
        self.assertFalse(P.adoption_pending())                              # répondu : plus jamais

    def test_launch_not_forwarded_when_adoption_waits_lots_untouched(self):
        from vectordrive.ui import instance
        need(P, 'launch_adopting')
        need(instance, 'forward_allowed')

        def decide(new_window=False, lots=None):                            # ce que fait VectorDrive.main
            adopting = P.launch_adopting(new_window, lots)
            return adopting, instance.forward_allowed(new_window, lots, adopting)
        self.assertEqual(decide(), (False, True))                           # seule : passé à la fenêtre ouverte
        self.old()
        self.assertEqual(decide(), (True, False))                           # une reprise attend : jamais renvoyé
        self.assertEqual(decide(lots=['a.vdz']), (False, False))            # lots : leur chemin à eux, tel quel
        self.assertEqual(decide(new_window=True), (False, False))
        with mock.patch.object(P, 'adoption_pending', side_effect=OSError('panne')):
            self.assertEqual(decide(), (False, True))                       # une erreur n'empêche aucun lancement
        P.offer_previous(lambda name: False)
        self.assertEqual(decide(), (False, True))                           # répondu : comme avant
        src = (pathlib.Path(__file__).resolve().parents[1] / 'VectorDrive.py').read_text(encoding='utf-8')
        self.assertIn('adopting = portable.launch_adopting(args.new_window, args.lots)', src)
        self.assertIn("instance.forward_allowed(args.new_window, args.lots, adopting) and instance.forward(", src)
        self.assertLess(src.index('w.reopen_after_update()'), src.index('w.tell_adoption(portable.LAST)'))

    def test_forward_waiting(self):
        from PySide6.QtWidgets import QWidget
        from vectordrive.ui import instance
        need(instance, 'forward_waiting')
        os.environ['VECTORDRIVE_INSTANCE'] = 'radopt-' + uuid.uuid4().hex[:8]
        self.assertFalse(instance.forward_waiting('', wait_s=0.3, step_s=0.1))      # personne n'écoute
        win = QWidget()
        self.addCleanup(win.deleteLater)
        server = instance.serve(win)
        self.addCleanup(server.close)
        with mock.patch.object(instance, 'forward', side_effect=[False, False, True]) as fw:
            self.assertTrue(instance.forward_waiting('a.vdz', wait_s=5, step_s=0.01))
        self.assertEqual(fw.call_count, 3)

    def test_second_launch_waits_for_the_question(self):
        import threading
        need(P, 'ADOPT_LOCK')
        old = self.old()
        first = QLockFile(str(self.new / P.ADOPT_LOCK))                     # le premier lancement pose la question
        self.assertTrue(first.tryLock(0))
        self.addCleanup(first.unlock)
        no = lambda *a, **k: self.fail('jamais deux questions')            # noqa: E731
        self.assertIsNone(P.offer_previous(no, wait_ms=300))
        self.assertFalse(P.WAITED)                                          # trop long : lancement sans reprise
        self.assertEqual(keys_of(self.new), {})

        def answered():                                                     # le premier : « Partir de zéro »
            (self.new / P.INI).write_text('[portable]\nreprise=non\n', encoding='utf-8')
            first.unlock()
        t = threading.Timer(0.3, answered)
        t.start()
        self.addCleanup(t.join)
        self.assertIsNone(P.offer_previous(no, wait_ms=10000))
        self.assertTrue(P.WAITED)                                           # son fichier ira à l'autre fenêtre
        self.assertTrue(old.is_dir())
        self.assertFalse((self.new / P.ADOPT_LOCK).exists())

    def test_second_launch_default_wait_is_bounded(self):
        need(P, 'ADOPT_WAIT_MS')
        self.old()
        first = QLockFile(str(self.new / P.ADOPT_LOCK))
        self.assertTrue(first.tryLock(0))
        self.addCleanup(first.unlock)
        clock = [1000.0]

        def monotonic():                                                    # temps simulé : 30 s par lecture
            clock[0] += 30.0
            return clock[0]
        with mock.patch('time.monotonic', monotonic):
            self.assertIsNone(P.offer_previous(lambda *a, **k: self.fail('demandé')))   # la vraie valeur d'office
        self.assertEqual(P.ADOPT_WAIT_MS, 180_000)
        self.assertGreaterEqual(clock[0] - 1000.0, P.ADOPT_WAIT_MS / 1000)
        self.assertLess(clock[0] - 1000.0, P.ADOPT_WAIT_MS / 1000 + 120)
        self.assertFalse(P.WAITED)
        self.assertTrue(P.BUSY)                                             # tenu par un vivant : jamais 2 fenêtres

    def test_stale_lock_of_another_computer_or_a_dead_process_is_taken(self):
        need(P, '_free_stale')
        lock = self.new / P.ADOPT_LOCK
        lock.write_text('999999\nVectorDrive\nAUTRE-POSTE-USB\n', encoding='utf-8')   # reprise coupée ailleurs
        got = P._adoption_lock(self.new)
        self.assertIsNotNone(got)
        got.unlock()
        host = os.environ.get('COMPUTERNAME') or QSysInfo.machineHostName()
        lock.write_text(f'999999\nVectorDrive\n{host}\n', encoding='utf-8')            # ce poste, processus mort
        got = P._adoption_lock(self.new)
        self.assertIsNotNone(got)
        got.unlock()
        qt_dead_lock(self.box, lock)                                        # tel que Qt l'écrit, processus arrêté
        got = P._adoption_lock(self.new)
        self.assertIsNotNone(got)
        got.unlock()
        data = foreign_lock(lock)                                           # ce poste, vivant : il finit d'abord
        self.assertIsNone(P._adoption_lock(self.new, 300))
        self.assertEqual(P.WAIT_END, 'delai')
        self.assertEqual(lock.read_bytes(), data)
        lock.unlink()
        if sys.platform == 'win32':                                         # autre poste, encore ouvert (partage) :
            lock.write_text('4242\nVectorDrive\nAUTRE-POSTE\n', encoding='utf-8')     # l'effacement échoue
            with open(lock, 'rb'):
                self.assertIsNone(P._adoption_lock(self.new, 300))
            self.assertTrue(lock.is_file())
            lock.unlink()
        old = self.old()
        lock.write_text('999999\nVectorDrive\nAUTRE-POSTE-USB\n', encoding='utf-8')
        no_wait = lambda: self.fail('attendu un verrou mort')              # noqa: E731
        self.assertEqual(P.offer_previous(lambda name: True, progress=direct, waiting=no_wait), old)
        self.assertFalse(P.WAITED)
        self.assertFalse(lock.exists())

    def test_timeout_while_the_other_still_copies_never_two_windows(self):
        import time
        need(P, 'BUSY')
        self.old()
        first = QLockFile(str(self.new / P.ADOPT_LOCK))                     # l'autre lancement copie encore
        self.assertTrue(first.tryLock(0))
        self.addCleanup(first.unlock)
        no = lambda *a, **k: self.fail('jamais deux questions')            # noqa: E731
        self.assertIsNone(P.offer_previous(no, wait_ms=300, waiting=lambda: time.sleep(0.05) or True))
        self.assertTrue(P.BUSY)
        self.assertFalse(P.WAITED)
        P.BUSY = False                                                      # un script : ni attente ni BUSY
        self.assertIsNone(P.offer_previous(no, wait_ms=60000, waiting=lambda: self.fail('attendu'), busy=False))
        self.assertFalse(P.BUSY)
        P.BUSY = True
        vd = vectordrive_main()                                             # la vraie suite de VectorDrive.main
        src = pathlib.Path(vd.__file__).read_text(encoding='utf-8')
        body = src[src.index('\ndef main('):]
        self.assertLess(body.index('code = after_offer(args, adopting, instance, portable)'),
                        body.index('w = MainWindow()'))
        self.assertIn('portable.offer_previous(busy=not args.script)', body)
        from vectordrive.ui import instance
        seen = {}

        def tell(names):
            seen['names'] = names
            return False                                                    # « Fermer »
        args = vd.make_parser().parse_args(['D:\\plaque.vdz'])
        with mock.patch.object(instance, 'forward', return_value=False), \
                mock.patch.object(P, 'tell_busy', tell):
            self.assertEqual(vd.after_offer(args, True, instance, P), 0)    # jamais deux fenêtres
        self.assertEqual(seen['names'], ['D:\\plaque.vdz'])
        with mock.patch.object(instance, 'forward', return_value=True):
            self.assertEqual(vd.after_offer(args, True, instance, P), 0)    # passé à l'autre fenêtre
        lots = vd.make_parser().parse_args(['--lots', 'a.vdz', 'b.vdz'])
        with mock.patch.object(instance, 'forward_lots', return_value=False) as fl, \
                mock.patch.object(P, 'tell_busy', tell):
            self.assertEqual(vd.after_offer(lots, False, instance, P), 0)
        fl.assert_called_once_with(['a.vdz', 'b.vdz'])
        self.assertEqual(seen['names'], ['a.vdz', 'b.vdz'])                 # le lot nommé
        with mock.patch.object(instance, 'forward', return_value=False), \
                mock.patch.object(P, 'tell_busy', return_value=True):
            self.assertIsNone(vd.after_offer(args, True, instance, P))      # « Ouvrir quand même »
        self.assertTrue(P.FORCED)
        P.BUSY = False
        self.assertIsNone(vd.after_offer(args, True, instance, P))          # rien en cours : sa fenêtre
        seen.clear()

        def click(text):
            def fake_exec(box):
                seen['text'] = box.text() + '\n' + box.informativeText()
                next(b for b in box.buttons() if b.text() == text).click()
                return 0
            return fake_exec
        with mock.patch.object(QMessageBox, 'exec', click('Fermer')):
            self.assertFalse(P.tell_busy(['D:\\plaque.vdz']))
        self.assertIn('D:\\plaque.vdz', seen['text'])
        self.assertIn('sur ce poste ou un autre', seen['text'])
        with mock.patch.object(QMessageBox, 'exec', click('Ouvrir quand même')):
            self.assertTrue(P.tell_busy('D:\\plaque.vdz'))

    def test_open_anyway_while_waiting(self):
        from PySide6.QtWidgets import QLabel, QPushButton
        need(P, '_WaitBox')
        self.old()
        first = QLockFile(str(self.new / P.ADOPT_LOCK))
        self.assertTrue(first.tryLock(0))
        self.addCleanup(first.unlock)
        calls = []

        def waiting():
            calls.append(1)
            return len(calls) < 3                                           # « Ouvrir quand même » au 3e tour
        self.assertIsNone(P.offer_previous(lambda *a, **k: self.fail('demandé'), wait_ms=60000, waiting=waiting))
        self.assertTrue(P.FORCED)
        self.assertFalse(P.BUSY)
        src = (pathlib.Path(__file__).resolve().parents[1] / 'VectorDrive.py').read_text(encoding='utf-8')
        self.assertIn('not portable.FORCED', src[src.index('w.reopen_after_update()') - 200:
                                                 src.index('w.reopen_after_update()')])
        box = P._WaitBox()                                                  # la vraie petite fenêtre
        self.assertTrue(box())
        self.assertTrue(box.dialog.isVisible())
        self.assertIn('en cours, sur ce poste ou un autre', ' '.join(
            lb.text() for lb in box.dialog.findChildren(QLabel)))
        box.dialog.reject()                                                 # Échap : on attend toujours
        self.assertTrue(box.dialog.isVisible())
        box.dialog.findChild(QPushButton, 'adoptOpenAnyway').click()
        self.assertFalse(box())
        box.close()
        self.assertIsNone(box.dialog)

    def test_after_waiting_never_asks_again_even_after_later(self):
        import threading
        import time
        self.old()
        first = QLockFile(str(self.new / P.ADOPT_LOCK))                     # le 1er : « Plus tard » (Échap)
        self.assertTrue(first.tryLock(0))
        t = threading.Timer(0.3, first.unlock)
        t.start()
        self.addCleanup(t.join)
        no = lambda *a, **k: self.fail('redemandé après l’attente')        # noqa: E731
        self.assertIsNone(P.offer_previous(no, no, wait_ms=10000, waiting=lambda: time.sleep(0.05) or True))
        self.assertTrue(P.WAITED)
        self.assertEqual(keys_of(self.new), {})

    def test_later_sets_nothing_then_the_window_settings_end_the_question(self):
        from PySide6.QtWidgets import QDialog
        from vectordrive.ui.main_window import MainWindow
        need(P, 'LATER')
        self.old()
        self.assertIsNone(P.offer_previous(lambda name: P.LATER))
        self.assertEqual(keys_of(self.new), {})                             # rien de posé par la question
        self.assertTrue(P.adoption_pending())
        st = QSettings(str(self.new / P.INI), QSettings.Format.IniFormat)   # ce qu'écrit la fenêtre qui s'ouvre
        st.setValue(MainWindow.TASKBAR_KEY, False)
        st.sync()
        self.assertFalse(P.adoption_pending())                              # assumé : plus de question (F10)
        self.assertIsNone(P.offer_previous(lambda *a, **k: self.fail('redemandé')))
        (self.new / P.INI).write_text('', encoding='utf-8')
        seen = {}

        def escape(box):
            seen['info'] = box.informativeText()
            seen['buttons'] = sorted(b.text() for b in box.buttons() if not b.isHidden())
            box.escapeButton().click()
            return 0
        with mock.patch.object(QMessageBox, 'exec', escape):
            self.assertEqual(P._ask_adopt('VectorDrive-1.29.0'), P.LATER)
        self.assertIn('Plus tard : F10 › Mises à jour › « Reprendre d’une ancienne version… »', seen['info'])
        self.assertEqual(seen['buttons'], ['Partir de zéro', 'Plus tard', 'Reprendre ses réglages'])
        cands = P.previous_portables(self.new)
        with mock.patch.object(QDialog, 'exec', lambda dlg: 0):             # Échap, croix
            self.assertEqual(P._choose_previous(cands), P.LATER)

        def zero(dlg):
            dlg.findChild(QPushButton, 'adoptZero').click()
            return 0
        from PySide6.QtWidgets import QPushButton
        with mock.patch.object(QDialog, 'exec', zero):
            self.assertIsNone(P._choose_previous(cands))                    # « Partir de zéro »
        self.old(f'VectorDrive-{ED}-1.30.0-portable')
        self.assertIsNone(P.offer_previous(choose=lambda c: P.LATER))
        self.assertEqual(keys_of(self.new), {})

    def test_ini_not_writable_is_never_pending(self):
        import stat
        need(P, 'adoption_pending')
        self.old()
        ini = self.new / P.INI
        os.chmod(ini, stat.S_IREAD)
        self.addCleanup(os.chmod, ini, stat.S_IREAD | stat.S_IWRITE)
        self.assertFalse(P.adoption_pending())                              # sinon : une fenêtre à chaque lancement
        self.assertIsNone(P.offer_previous(lambda *a, **k: self.fail('demandé')))

    def test_channel_taken_when_the_old_window_closes(self):
        from PySide6.QtWidgets import QWidget
        from vectordrive.ui import instance
        need(instance, 'serve_when_free')
        os.environ['VECTORDRIVE_INSTANCE'] = 'radopt-' + uuid.uuid4().hex[:8]
        win = QWidget()
        self.addCleanup(win.deleteLater)
        win._instance_server = None
        answers = [True, False]
        timer = instance.serve_when_free(win, probe=lambda: answers.pop(0), every_ms=60000)
        timer.timeout.emit()
        self.assertIsNone(win._instance_server)                             # encore tenu : jamais deux fenêtres
        timer.timeout.emit()
        self.assertIsNotNone(win._instance_server)
        self.assertTrue(win._instance_server.isListening())
        self.assertFalse(timer.isActive())
        win._instance_server.close()

    def test_channel_free_but_not_taken_is_retried(self):
        from PySide6.QtWidgets import QWidget
        from vectordrive.ui import instance
        need(instance, 'SERVE_TRIES')
        os.environ['VECTORDRIVE_INSTANCE'] = 'radopt-' + uuid.uuid4().hex[:8]
        win = QWidget()
        self.addCleanup(win.deleteLater)
        win._instance_server = None
        real = instance.serve
        with mock.patch.object(instance, 'serve', side_effect=[None, None, real(win)]):
            timer = instance.serve_when_free(win, probe=lambda: False, every_ms=60000)
            timer.timeout.emit()
            self.assertIsNone(win._instance_server)
            self.assertTrue(timer.isActive())                               # retentée
            timer.timeout.emit()
            timer.timeout.emit()
        self.assertTrue(win._instance_server.isListening())
        self.assertFalse(timer.isActive())
        win._instance_server.close()
        win2 = QWidget()
        self.addCleanup(win2.deleteLater)
        win2._instance_server = None
        with mock.patch.object(instance, 'serve', return_value=None):
            timer = instance.serve_when_free(win2, probe=lambda: False, every_ms=60000)
            for _ in range(instance.SERVE_TRIES):
                timer.timeout.emit()
        self.assertFalse(timer.isActive())                                  # bornée


# --- 4 bis. bibliothèque, données, favoris, bilan ------------------------------------------------------------
class Library(Base):

    FILES = {'bibliotheque/Logos BAT/logo.svg': '<svg>ancien</svg>', 'bibliotheque/Favoris/plaque.vdz': 'vdz',
             'bibliotheque/Mes symboles/étoile.smb': 'smb', 'donnees/outils/tools.json': '{"outils": 3}',
             'donnees/modeles_fao/alu.json': '{"m": 1}', 'donnees/polices/Ma police.svg': '<svg/>',
             'donnees/clients/Durand/fiche.json': '{}', 'donnees/plugins/donnees_plugin.json': '{"p": 1}',
             'donnees/assistant/memoire.md': 'mémoire', 'donnees/recuperation/r.vdz': 'non'}

    def test_library_and_data_all_carried_never_overwritten(self):
        old = self.old(files=self.FILES)
        mine = {'bibliotheque/Logos BAT/logo.svg': '<svg>le mien</svg>', 'donnees/modeles_fao/alu.json': '{"mien": 1}'}
        for rel, text in mine.items():
            (self.new / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.new / rel).write_text(text, encoding='utf-8')
        res = P.adopt(old)
        need(res, 'copied')
        for rel, text in self.FILES.items():
            got = self.new / rel
            if rel in mine:
                self.assertEqual(got.read_text(encoding='utf-8'), mine[rel])     # jamais écrasé
            elif 'recuperation' in rel:
                self.assertFalse(got.exists())
            else:
                self.assertEqual(got.read_text(encoding='utf-8'), text, rel)
        self.assertEqual(len(res.skipped), 2)
        self.assertEqual(res.copied, 1 + len(self.FILES) - 3)               # réglages + fichiers repris
        self.assertEqual(res.failed, [])

    def test_failed_copy_is_reported_and_the_rest_continues(self):
        old = self.old(files=self.FILES)
        real = shutil.copy2

        def copy(src, dst, *a, **kw):
            if 'étoile' in str(src):
                raise PermissionError(13, 'accès refusé')
            return real(src, dst, *a, **kw)
        with mock.patch.object(AU.shutil, 'copy2', copy):
            res = P.adopt(old)
        need(res, 'failed')
        self.assertEqual(len(res.failed), 1)
        self.assertIn('étoile.smb', res.failed[0])
        self.assertTrue((self.new / 'bibliotheque/Favoris/plaque.vdz').is_file())
        self.assertFalse(list(self.new.rglob('*.vd_copie')))                # aucune copie à moitié laissée
        from vectordrive.ui.main_window import MainWindow
        text = MainWindow.adoption_text(None, res)
        self.assertIn('Échecs', text)
        self.assertIn('étoile.smb', text)

    def test_favorites_and_bibli_folders_come_back_identical(self):
        favs = ['P:\\Partage\\Fichiers Clients', 'D:\\Dessins accentués\\été 2026, lot 2']
        keys = {'navigateur/favoris': favs, 'navigateur/dossiers': ['C:\\Un seul dossier'],
                'symboles/favoris': 'D:\\a, b', 'options/decimales': 3}
        old = self.old(keys=keys)
        P.offer_previous(lambda name: True)
        got = keys_of(self.new)
        before = keys_of(old)
        for k in keys:
            self.assertEqual([str(x) for x in listed(got[k])], [str(x) for x in listed(before[k])], k)
        self.assertEqual(listed(got['navigateur/favoris']), favs)
        self.assertEqual(listed(got['navigateur/dossiers']), ['C:\\Un seul dossier'])
        need(P.LAST, 'favorites')
        self.assertEqual((P.LAST.favorites, P.LAST.bibli), (2, 1))
        from vectordrive.ui.main_window import MainWindow
        text = MainWindow.adoption_text(None, P.LAST)
        self.assertIn(str(old), text)                                       # le dossier source
        self.assertIn('2 dossier(s) favori(s)', text)
        self.assertIn('1 dossier(s) de la bibli', text)

    def test_favorites_are_not_local_keys(self):
        from vectordrive.ui.main_window import MainWindow
        for k in ('navigateur/favoris', 'navigateur/dossiers'):
            self.assertFalse(k.startswith(MainWindow.LOCAL_KEYS), k)


# --- choisir entre plusieurs versions posées à côté (retour terrain) -----------------------------------------
class Choice(Base):

    def setUp(self):
        super().setUp()
        self.daily = self.old(keys={f'k/{i}': i for i in range(40)} | {'navigateur/favoris': ['P:\\a', 'P:\\b']},
                              files={'bibliotheque/Logos BAT/l1.svg': 'x', 'bibliotheque/Logos BAT/l2.svg': 'x'})
        write_old_session(self.daily, self.box)
        self.trial = self.old(f'VectorDrive-{ED}-1.32.0-portable', keys={'fenetre/x': 1, 'vue/theme': 'clair'})
        later = (self.daily / P.INI).stat().st_mtime + 3600
        os.utime(self.trial / P.INI, (later, later))                        # lancée une fois, après

    def test_daily_version_preselected_over_a_recent_trial(self):
        need(P, 'previous_portables')
        found = P.previous_portables(self.new)
        self.assertEqual([c.app for c in found], [self.daily, self.trial])
        self.assertEqual(P.previous_portable(self.new), self.daily)
        c = found[0]
        self.assertEqual((c.version, c.tabs, c.library, c.favorites), ('1.29.0', 2, 2, 2))

    def test_several_ask_to_choose(self):
        need(P, 'previous_portables')
        seen = []
        got = P.offer_previous(lambda name: self.fail('une seule question'),
                               choose=lambda cands: seen.append([c.app for c in cands]) or cands[1])
        self.assertEqual(got, self.trial)
        self.assertEqual(seen, [[self.daily, self.trial]])
        self.assertEqual(keys_of(self.new)['vue/theme'], 'clair')

    def test_choice_refused_starts_from_scratch(self):
        need(P, 'previous_portables')
        self.assertIsNone(P.offer_previous(lambda name: True, choose=lambda cands: None))
        self.assertEqual(keys_of(self.new), {P.ADOPTED_KEY: 'non'})

    def test_preselection_edition_real_use_and_close_contents(self):
        need(AU, 'real_use')
        full = self.old(f'VectorDrive-{ED}-1.20.0-portable', keys={f'k/{i}': i for i in range(60)},
                        files={f'bibliotheque/s{i}.svg': 'x' for i in range(40)})
        write_old_session(full, self.box)
        recent = self.old(f'VectorDrive-{ED}-1.28.0-portable', keys={f'k/{i}': i for i in range(12)})
        write_old_session(recent, self.box)
        other = self.old('VectorDrive-AUTRE-1.30.0-portable', keys={f'k/{i}': i for i in range(80)},
                         files={f'bibliotheque/s{i}.svg': 'x' for i in range(90)})
        write_old_session(other, self.box)
        long_ago = (recent / P.INI).stat().st_mtime - 30 * 86400
        for p in (full / P.INI, full / 'donnees/session/session.json', self.daily / P.INI,
                  self.daily / 'donnees/session/session.json'):
            os.utime(p, (long_ago, long_ago))
        order = [c.app for c in P.previous_portables(self.new)]
        self.assertEqual(order[0], recent)                                  # la plus récente qui a vraiment servi
        self.assertEqual(order[-1], other)                                  # une autre édition : en dernier
        self.assertLess(order.index(full), order.index(self.trial))
        self.assertIn('édition AUTRE', P.candidate_text(AU.describe(other)))
        c = AU.Candidate
        near_old = c(self.box / 'a', 'a', '', 100.0, 0, 10, 0, 0, 3, 0, ED)
        near_new = c(self.box / 'b', 'b', '', 200.0, 0, 11, 0, 0, 3, 0, ED)
        far = c(self.box / 'c', 'c', '', 50.0, 0, 100, 0, 0, 3, 0, ED)
        self.assertEqual([x.name for x in AU.preferred([near_old, near_new, far], ED)], ['c', 'b', 'a'])

    def test_held_among_several(self):
        need(P, 'RETRY')
        foreign_lock(self.daily / 'donnees' / 'session' / 'session.lock')
        asked, seen = [], []

        def ask(name, held=False):
            asked.append((name, held))
            return True                                                     # « Reprendre sans attendre »
        got = P.offer_previous(ask, choose=lambda cands: seen.append(len(cands)) or cands[0], progress=direct)
        self.assertEqual(got, self.daily)
        self.assertEqual(seen, [2])
        self.assertEqual(asked, [(f'VectorDrive-{ED}-1.29.0-portable', True)])
        self.assertEqual(P.LAST.tabs, 2)

    def test_choice_window_lists_and_shows_the_full_path(self):
        need(P, '_choose_dialog')
        cands = P.previous_portables(self.new)
        dlg, lst, where = P._choose_dialog(cands)
        self.addCleanup(dlg.deleteLater)
        self.assertEqual(lst.count(), 2)
        first = lst.item(0).text()
        for part in ('1.29.0', '2 onglet(s)', '2 fichier(s) de bibliothèque', '2 dossier(s) favori(s)'):
            self.assertIn(part, first)
        self.assertIn(str(self.daily), where.text())
        lst.setCurrentRow(1)
        self.assertIn(str(self.trial), where.text())


# --- 5. reprise à la main : F10 › Mises à jour › Configuration -----------------------------------------------
class Manual(Base):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        for t in cls.w.docs:
            t.modified = False
        cls.w.modified = False
        cls.w.close()
        cls.w.deleteLater()
        app.processEvents()

    def setUp(self):
        super().setUp()
        os.environ['VECTORDRIVE_SETTINGS'] = SETTINGS_ENV
        self.keep = self.w.settings
        self.w.settings = QSettings(str(self.box / 'fenetre.ini'), QSettings.Format.IniFormat)
        self.w.settings.setValue('vue/theme', 'mien')
        self.w.settings.sync()
        self.addCleanup(setattr, self.w, 'settings', self.keep)
        s = QSettings(str(self.new / P.INI), QSettings.Format.IniFormat)
        s.setValue('portable/reprise', 'non')
        s.setValue('vue/theme', 'mien')
        s.sync()

    def test_group_buttons_and_disabled_outside_portable(self):
        w = self.w
        dlg = w.options_dialog(exec_dialog=False, page='Mises à jour')
        self.addCleanup(dlg.deleteLater)
        need(dlg, 'config_group')
        self.assertEqual([dlg.config_export_button.text(), dlg.config_import_button.text(), dlg.adopt_button.text()],
                         ['Exporter la configuration…', 'Importer une configuration…',
                          'Reprendre d’une ancienne version…'])
        self.assertTrue(dlg.adopt_button.isEnabled())                       # portable
        with mock.patch.object(w, 'export_params_dialog') as ex:
            dlg.config_export_button.click()
        ex.assert_called_once_with()
        with mock.patch.object(w, 'import_params_dialog', return_value={'reglages': 2}), \
                mock.patch.object(dlg, 'reject') as rej:
            dlg.config_import_button.click()
        rej.assert_called_once_with()                                       # ses champs ne réécrivent rien
        with mock.patch.object(w, 'adopt_previous_version', return_value={'etat': 'repris'}) as ad, \
                mock.patch.object(dlg, 'reject') as rej:
            dlg.adopt_button.click()
        ad.assert_called_once_with()
        rej.assert_called_once_with()
        os.environ.pop('VECTORDRIVE_PORTABLE_DIR')
        dlg2 = w.options_dialog(exec_dialog=False, page='Mises à jour')
        self.addCleanup(dlg2.deleteLater)
        self.assertFalse(dlg2.adopt_button.isEnabled())
        self.assertIn('portable', dlg2.adopt_button.toolTip())
        self.assertEqual(w.adopt_previous_version({'dossier': str(self.box)}, exec_dialog=False)['etat'],
                         'non_portable')

    def test_manual_adoption_takes_everything_and_reopens_the_tabs(self):
        w = self.w
        need(w, 'adopt_previous_version')
        from vectordrive.cam import toollib
        from vectordrive.cam.model import CamTool
        a, b = CamTool(name='Fraise A', diameter=2.0), CamTool(name='Gravure B', kind='conique', angle=30.0)
        mine_tool = CamTool(name='Ajoutée ici', diameter=6.0)
        w.settings.setValue('navigateur/favoris', ['D:\\Ajouté ici', 'p:\\partage\\fichiers clients'])
        w.settings.setValue('polices/dossiers', 'D:\\Polices')
        w.settings.sync()
        old = self.old(keys={'navigateur/favoris': ['P:\\Partage\\Fichiers Clients', 'P:\\Ancien'],
                             'navigateur/dossiers': ['C:\\Bibli'], 'polices/dossiers': 'D:\\polices;E:\\Autres',
                             'vue/theme': 'ancien', 'options/decimales': 4},
                       files={'bibliotheque/Logos BAT/l.svg': 'x', 'donnees/modeles_fao/alu.json': '{"ancien": 1}',
                              'donnees/outils/tools.json': toollib.to_json([a, b])})
        for rel, text in {'donnees/modeles_fao/alu.json': '{"mien": 1}',
                          'donnees/outils/tools.json': toollib.to_json([a, mine_tool])}.items():
            (self.new / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.new / rel).write_text(text, encoding='utf-8')
        later = (old / 'donnees/modeles_fao/alu.json').stat().st_mtime + 3600
        os.utime(old / 'donnees/modeles_fao/alu.json', (later, later))     # plus récent là-bas : gardé ici quand même
        info = write_old_session(old, self.box)
        own = self.new / 'donnees' / 'session'
        own.mkdir(parents=True)
        (own / 'session.json').write_text('{"version": 1, "docs": []}', encoding='utf-8')
        before_own = (own / 'session.json').read_bytes()
        starts = []
        r = w.adopt_previous_version({'choisir': lambda start: starts.append(start) or str(old.parent), 'ok': True},
                                     exec_dialog=False)
        self.assertEqual(r['etat'], 'repris', r.get('message'))
        self.assertEqual(starts, [old])                                     # proposé : la version posée à côté
        self.assertEqual(w.settings.value('vue/theme'), 'mien')             # déjà posé ici : gardé
        self.assertEqual(str(w.settings.value('options/decimales')), '4')   # absent ici : repris
        self.assertEqual(listed(w.settings.value('navigateur/favoris')),    # réunis, ceux d'ici d'abord
                         ['D:\\Ajouté ici', 'p:\\partage\\fichiers clients', 'P:\\Ancien'])
        self.assertEqual(listed(w.settings.value('navigateur/dossiers')), ['C:\\Bibli'])
        self.assertEqual(w.settings.value('polices/dossiers'), 'D:\\Polices;E:\\Autres')
        self.assertIn('1 réglage(s) déjà posé(s) ici gardé(s)', r['message'])
        backup = pathlib.Path(w.settings.fileName() + AU.BACKUP)
        self.assertIn('mien', backup.read_text(encoding='utf-8'))           # copie de secours d'abord
        self.assertTrue((self.new / 'bibliotheque/Logos BAT/l.svg').is_file())
        self.assertEqual((own / 'session.json').read_bytes(), before_own)   # sa propre session : jamais touchée
        self.assertEqual(r['rouverts'], 2)
        self.assertTrue(any(t.title == 'Plaque client' and t.pinned for t in w.docs))
        self.assertIn(str(old), r['message'])
        self.assertTrue(info['saved'].is_file())
        self.assertEqual((self.new / 'donnees/modeles_fao/alu.json').read_text(encoding='utf-8'), '{"mien": 1}')
        tools = toollib.load(self.new / 'donnees/outils/tools.json')        # fusionnés : rien de perdu, sans doublon
        self.assertEqual(sorted(t.name for t in tools), ['Ajoutée ici', 'Fraise A', 'Gravure B'])
        self.assertTrue((self.new / ('donnees/outils/tools.json' + AU.BACKUP)).is_file())
        self.assertIn('tools.json → tools.json' + AU.BACKUP, r['message'])  # remplacé : dit, avec sa copie
        self.assertIn('fenetre.ini → fenetre.ini' + AU.BACKUP, r['message'])

    def test_manual_refusals(self):
        w = self.w
        need(w, 'adopt_previous_version')
        self.assertEqual(w.adopt_previous_version(exec_dialog=False)['etat'], 'annule')      # jamais de vraie boîte
        self.assertEqual(w.adopt_previous_version({'dossier': str(self.box / 'rien')}, exec_dialog=False)['etat'],
                         'erreur')
        self.assertEqual(w.adopt_previous_version({'dossier': str(self.new)}, exec_dialog=False)['etat'], 'erreur')
        old = self.old()
        self.assertEqual(w.adopt_previous_version({'dossier': str(old)}, exec_dialog=False)['etat'], 'refuse')
        vd = self.box / 'VD'
        other = make_version(vd, f'VectorDrive-{ED}-1.20.0', {'a': 1})
        make_version(vd, f'VectorDrive-{ED}-1.10.0', {'a': 1})
        shutil.rmtree(old.parent)
        w.settings.setValue('maj/dossier_vd', str(vd))
        self.assertEqual(w.adopt_previous_version(exec_dialog=False)['propose'], other)  # la plus récente du dossier VD

    def test_f10_adoption_and_a_launch_never_run_together(self):
        import time
        w = self.w
        old = self.old(files={'bibliotheque/a.svg': 'x'})
        first = QLockFile(str(self.new / P.ADOPT_LOCK))                     # une reprise tient déjà le verrou
        self.assertTrue(first.tryLock(0))
        self.addCleanup(first.unlock)
        r = w.adopt_previous_version({'dossier': str(old), 'ok': True, 'progression': direct}, exec_dialog=False)
        self.assertEqual(r['etat'], 'en_cours')                             # rien fait
        self.assertIn('déjà en cours', r['message'])
        self.assertFalse((self.new / 'bibliotheque' / 'a.svg').exists())
        P.write_adoption_mark(self.new, old, 'f10')                         # la reprise F10 en cours : sa marque,
        part = self.new / 'bibliotheque' / 'b.svg.vd_copie'                 # une copie à moitié écrite
        part.parent.mkdir(parents=True, exist_ok=True)
        part.write_text('moitié', encoding='utf-8')
        os.environ.pop('VECTORDRIVE_SETTINGS', None)                        # un double clic pendant ce temps
        self.assertTrue(P.adoption_pending())
        self.assertIsNone(P.offer_previous(lambda *a, **k: self.fail('demandé'),
                                           progress=lambda fn: self.fail('copié'), wait_ms=300,
                                           waiting=lambda: time.sleep(0.05) or True))
        self.assertTrue(P.BUSY)
        self.assertTrue(part.is_file())                                     # rien balayé
        self.assertFalse((self.new / 'bibliotheque' / 'a.svg').exists())   # rien copié
        self.assertEqual(handovers(self.new), [])
        first.unlock()
        os.environ['VECTORDRIVE_SETTINGS'] = SETTINGS_ENV
        r = w.adopt_previous_version({'dossier': str(old), 'ok': True, 'progression': direct}, exec_dialog=False)
        self.assertEqual(r['etat'], 'repris')                               # libre : faite, verrou rendu
        self.assertTrue((self.new / 'bibliotheque' / 'a.svg').is_file())
        self.assertFalse(part.exists())                                     # sa propre reprise coupée : balayée
        self.assertFalse((self.new / P.ADOPT_LOCK).exists())


# --- configuration exportée / importée (.vdparam) ------------------------------------------------------------
class Union(unittest.TestCase):

    def test_paths_compared_without_case_commands_as_they_are(self):
        need(AU, 'UNION_NOT_PATHS')
        self.assertEqual(AU._union('ruban/favoris', ['Copier'], ['copier', 'Copier']), ['Copier', 'copier'])
        self.assertIsNone(AU._union('ruban/favoris', ['Copier'], ['Copier']))
        if sys.platform == 'win32':
            self.assertIsNone(AU._union('navigateur/favoris', ['C:\\Clients'], ['c:/clients']))
            self.assertEqual(AU._union('polices/dossiers', 'C:\\Polices', 'c:\\polices;D:\\Autres'),
                             'C:\\Polices;D:\\Autres')


class Config(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        for t in cls.w.docs:
            t.modified = False
            t.pinned = False
        cls.w.modified = False
        cls.w.close()
        cls.w.deleteLater()
        app.processEvents()

    def setUp(self):
        self.box = pathlib.Path(tempfile.mkdtemp(prefix='radopt_cfg_'))
        self.addCleanup(shutil.rmtree, self.box, True)

    def env(self, root):
        root = pathlib.Path(root)
        app_dir = root / 'app'
        app_dir.mkdir(parents=True, exist_ok=True)
        (app_dir / P.INI).write_text(EMPTY_INI, encoding='utf-8')
        return mock.patch.dict(os.environ, {
            'VECTORDRIVE_PORTABLE_DIR': str(app_dir),             # données : root/app/donnees
            'VECTORDRIVE_TOOLS': str(root / 'outils' / 'tools.json'),
            'VECTORDRIVE_CAM_TEMPLATES': str(root / 'modeles_fao'),
            'VECTORDRIVE_DOC_TEMPLATES': str(root / 'modeles_dessin'),
            'VECTORDRIVE_THEMES': str(root / 'themes'),
            'VECTORDRIVE_BIBLIOTHEQUE': str(root / 'bibli'),
            'VECTORDRIVE_CACHE': str(root / 'cache'),
            'VECTORDRIVE_SCRIPTS': str(root / 'scripts'),
            'VECTORDRIVE_ASSISTANT_DIR': str(root / 'assistant')})

    @staticmethod
    def put(root, files):
        for rel, text in files.items():
            f = pathlib.Path(root) / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(text if isinstance(text, bytes) else text.encode('utf-8'))

    def test_complete_configuration_round_trip(self):
        from vectordrive.io import params
        from vectordrive.ui.main_window import MainWindow
        need(params, 'secret_key')
        src, dst = self.box / 'a', self.box / 'b'
        self.put(src, {'bibli/Logos BAT/logo.svg': '<svg>a</svg>', 'bibli/Favoris/plaque.vdz': 'vdz',
                       'cache/VectorDrive/polices/Ma police.svg': '<svg/>', 'cache/VectorDrive/polices/f.ttf': 'ttf',
                       'cache/VectorDrive/polices/te.vnf': 'TypeEdit', 'scripts/cadre.vds': 'cadre()',
                       'assistant/memoire.md': 'notes', 'assistant/memoires/t.json': '{}',
                       'assistant/copies/dessin.vdz': 'copie', 'assistant/copies.json': '{}',
                       'assistant/jeton.txt': 'secret'})
        st = QSettings(str(self.box / 'a.ini'), QSettings.Format.IniFormat)
        st.setValue('navigateur/favoris', ['P:\\Partage\\Fichiers Clients', 'D:\\été'])
        st.setValue('navigateur/dossiers', ['C:\\Un seul'])
        st.setValue('agent/jeton', 'abc123')
        st.setValue('fichiers/recents', ['C:/x.vdz'])
        out = self.box / ('c' + params.EXT)
        with self.env(src):
            counts = params.export(out, st, local_keys=MainWindow.LOCAL_KEYS)
        self.assertEqual({k: counts[k] for k in ('bibliotheque', 'polices', 'scripts', 'assistant')},
                         {'bibliotheque': 2, 'polices': 2, 'scripts': 1, 'assistant': 2})
        names = zipfile.ZipFile(out).namelist()
        for n in ('bibliotheque/Logos BAT/logo.svg', 'polices/Ma police.svg', 'scripts/cadre.vds',
                  'assistant/memoire.md'):
            self.assertIn(n, names)
        for n in ('polices/te.vnf', 'assistant/copies/dessin.vdz', 'assistant/copies.json', 'assistant/jeton.txt'):
            self.assertNotIn(n, names)
        ini = zipfile.ZipFile(out).read(params.SETTINGS_INI).decode('utf-8')
        self.assertNotIn('abc123', ini)                                     # jamais un jeton
        self.assertNotIn('recents', ini)
        self.put(dst, {'bibli/Logos BAT/logo.svg': '<svg>le mien</svg>', 'cache/VectorDrive/polices/f.ttf': 'mienne'})
        st2 = QSettings(str(self.box / 'b.ini'), QSettings.Format.IniFormat)
        st2.setValue('agent/jeton', 'le mien')
        with self.env(dst):
            got, _bk = params.import_(out, st2, local_keys=MainWindow.LOCAL_KEYS, backup_dir=self.box / 'bk')
        self.assertEqual((dst / 'bibli/Logos BAT/logo.svg').read_text(encoding='utf-8'), '<svg>le mien</svg>')
        self.assertEqual((dst / 'cache/VectorDrive/polices/f.ttf').read_text(encoding='utf-8'), 'mienne')
        self.assertEqual(got['gardes'], 2)
        self.assertTrue((dst / 'bibli/Favoris/plaque.vdz').is_file())
        self.assertTrue((dst / 'scripts/cadre.vds').is_file())
        self.assertEqual(listed(st2.value('navigateur/favoris')), ['P:\\Partage\\Fichiers Clients', 'D:\\été'])
        self.assertEqual(listed(st2.value('navigateur/dossiers')), ['C:\\Un seul'])
        self.assertEqual(st2.value('agent/jeton'), 'le mien')

    def test_secrets_filtered_without_false_positives_and_reported(self):
        from vectordrive.io import params
        need(params, 'SECRET_KEYS')
        src = self.box / 'a'
        self.put(src, {'bibli/Jeton caddie.svg': '<svg/>', 'modeles_fao/jeton laiton.json': '{}',
                       'themes/secret garden.json': '{}', 'assistant/memoire.md': 'notes',
                       'assistant/mdp.txt': 'x', 'assistant/cle.pem': 'x', 'assistant/jetons_de_presence.md': 'x'})
        st = QSettings(str(self.box / 'a.ini'), QSettings.Format.IniFormat)
        for k in ('dessin/cercle_tangent', 'galbe/passes', 'symboles/tokenizer', 'agent/jeton', 'mistral/api_key',
                  'compte/mdp', 'compte/mot_de_passe', 'service/token'):
            st.setValue(k, 'v')
        out = self.box / ('s' + params.EXT)
        with self.env(src):
            params.export(out, st)
        names = zipfile.ZipFile(out).namelist()
        for n in ('bibliotheque/Jeton caddie.svg', 'modeles_fao/jeton laiton.json', 'themes/secret garden.json',
                  'assistant/memoire.md'):
            self.assertIn(n, names)                                         # jamais une sous-chaîne quelconque
        for n in ('assistant/mdp.txt', 'assistant/cle.pem', 'assistant/jetons_de_presence.md'):
            self.assertNotIn(n, names)
        ini = zipfile.ZipFile(out).read(params.SETTINGS_INI).decode('utf-8')
        for k in ('cercle_tangent', 'passes', 'tokenizer'):
            self.assertIn(k, ini)
        for k in ('jeton', 'api_key', 'mdp', 'mot_de_passe', 'token='):
            self.assertNotIn(k, ini)
        said = ' '.join(params.last_errors)
        for what in ('agent/jeton', 'mistral/api_key', 'compte/mdp', 'compte/mot_de_passe', 'service/token',
                     'mdp.txt', 'cle.pem', 'jetons_de_presence.md'):
            self.assertIn(what, said)                                       # tout ce qui est laissé : dit
        self.assertEqual(len(params.last_errors), 8)

    def test_old_file_still_readable_and_unsafe_names_never_written(self):
        from vectordrive.io import params
        old = self.box / 'ancien.vdparam'
        with zipfile.ZipFile(old, 'w') as z:
            z.writestr('manifeste.json', '{"format": "vectordrive-parametres", "version": 1}')
            z.writestr('themes/perso.json', '{}')
        self.assertEqual(params.contents(old), {'themes': 1})
        evil = self.box / 'evil.vdparam'
        with zipfile.ZipFile(evil, 'w') as z:
            z.writestr('manifeste.json', json.dumps({'format': 'vectordrive-parametres', 'plugins': {
                'plugin:x': {'label': 'X', 'files': ['donnees/plugins/x/__init__.py', 'donnees/../evil.json',
                                                     'donnees/ok.json', 'donnees/outils/tools.json',
                                                     'donnees/x/jetons/acces.json']}}}))
            z.writestr('donnees/outils/tools.json', '{"outils": []}')        # plugin absent : jamais au cœur
            z.writestr('donnees/x/jetons/acces.json', '{}')
            z.writestr('bibliotheque/../evil.svg', 'x')
            z.writestr('polices/C:/evil.ttf', 'x')
            z.writestr('donnees/plugins/x/__init__.py', 'import os')
            z.writestr('donnees/../evil.json', 'x')
            z.writestr('donnees/ok.json', '{}')
        st = QSettings(str(self.box / 's.ini'), QSettings.Format.IniFormat)
        root = self.box / 'u'
        with self.env(root):
            self.assertEqual(params.contents(evil).get('plugin:x'), 1)
            params.import_(evil, st, backup_dir=self.box / 'bk')
        self.assertFalse((root / 'evil.svg').exists())
        self.assertFalse((self.box / 'evil.svg').exists())
        self.assertFalse([p for p in self.box.rglob('evil.*') if p.suffix != '.vdparam'])
        self.assertFalse((root / 'app' / 'donnees' / 'plugins').exists())   # jamais du code
        self.assertTrue((root / 'app' / 'donnees' / 'ok.json').is_file())
        self.assertFalse((root / 'app' / 'donnees' / 'outils').exists())    # dossier du cœur : refusé, dit
        self.assertIn('donnees/outils/tools.json', ' '.join(params.last_errors))
        self.assertFalse((root / 'app' / 'donnees' / 'x').exists())         # tout le chemin dit un secret

    def test_locked_file_at_export_is_said_and_no_tmp_left(self):
        from vectordrive.io import params
        src = self.box / 'a'
        self.put(src, {'bibli/a.svg': '<svg/>', 'bibli/tenu.svg': '<svg/>', 'scripts/s.vds': 'x'})
        st = QSettings(str(self.box / 's.ini'), QSettings.Format.IniFormat)
        real = zipfile.ZipFile.write

        def write(z, f, name=None, *a, **k):
            if str(f).endswith('tenu.svg'):
                raise PermissionError(13, 'fichier verrouillé')
            return real(z, f, name, *a, **k)
        out = self.box / ('v' + params.EXT)
        with self.env(src), mock.patch.object(zipfile.ZipFile, 'write', write):
            counts = params.export(out, st)
        self.assertEqual(counts['bibliotheque'], 1)
        self.assertIn('tenu.svg', ' '.join(params.last_errors))
        self.assertTrue(out.is_file())
        def boom(tmp, *a):
            pathlib.Path(tmp).write_bytes(b'moitie')                       # archive à moitié écrite, puis panne
            raise RuntimeError('panne')
        with self.env(src), mock.patch.object(params, '_export_into', boom):
            with self.assertRaises(RuntimeError):
                params.export(self.box / ('w' + params.EXT), st)
        self.assertEqual(list(self.box.glob('*.tmp')), [])                  # jamais un .tmp laissé

    def test_locked_file_at_import_is_said_and_the_import_continues(self):
        from vectordrive.io import params
        src, dst = self.box / 'a', self.box / 'b'
        self.put(src, {'bibli/a.svg': '<svg/>', 'bibli/tenu.svg': '<svg/>'})
        st = QSettings(str(self.box / 's.ini'), QSettings.Format.IniFormat)
        out = self.box / ('v' + params.EXT)
        with self.env(src):
            params.export(out, st, ['bibliotheque'])
        real = os.replace

        def replace(a, b, *r, **k):
            if str(b).endswith('tenu.svg'):
                raise PermissionError(13, 'fichier verrouillé')
            return real(a, b, *r, **k)
        with self.env(dst), mock.patch('os.replace', replace):
            got, _bk = params.import_(out, st, ['bibliotheque'], backup_dir=self.box / 'bk')
        self.assertEqual(got['bibliotheque'], 1)                            # le reste continue
        self.assertIn('tenu.svg', ' '.join(params.last_errors))
        self.assertTrue((dst / 'bibli' / 'a.svg').is_file())
        self.assertEqual(list(dst.rglob('*.vd_copie')), [])                 # jamais de copie à moitié laissée

    def test_loaded_plugin_never_exports_or_imports_into_core_folders(self):
        from vectordrive import plugins
        from vectordrive.io import params
        api = plugins.Api(plugins.REGISTRY, plugins.PluginInfo('faux_plugin'))
        src, dst = self.box / 'a', self.box / 'b'

        def files():
            d = src / 'app' / 'donnees'
            return [d / 'outils' / 'tools.json', d / 'faux' / 'ok.json']
        api.add_config_data('faux', 'Données du faux plugin', files)
        self.addCleanup(lambda: plugins.REGISTRY.config_data.clear())
        self.put(src / 'app' / 'donnees', {'outils/tools.json': '{"outils": []}', 'faux/ok.json': '{}'})
        st = QSettings(str(self.box / 's.ini'), QSettings.Format.IniFormat)
        out = self.box / ('p' + params.EXT)
        with self.env(src):
            counts = params.export(out, st, ['plugin:faux'])
        self.assertEqual(counts['plugin:faux'], 1)
        self.assertNotIn('donnees/outils/tools.json', zipfile.ZipFile(out).namelist())
        self.assertIn('tools.json', ' '.join(params.last_errors))           # dit
        forged = self.box / ('f' + params.EXT)                              # un fichier fabriqué, plugin chargé
        with zipfile.ZipFile(forged, 'w') as z:
            z.writestr('manifeste.json', json.dumps({'format': 'vectordrive-parametres', 'plugins': {
                'plugin:faux': {'label': 'X', 'files': ['donnees/outils/tools.json', 'donnees/faux/ok.json']}}}))
            z.writestr('donnees/outils/tools.json', '{"outils": []}')
            z.writestr('donnees/faux/ok.json', '{}')
        with self.env(dst):
            self.assertEqual(params.contents(forged)['plugin:faux'], 1)
            params.import_(forged, st, ['plugin:faux'], backup_dir=self.box / 'bk')
        self.assertFalse((dst / 'app' / 'donnees' / 'outils').exists())
        self.assertTrue((dst / 'app' / 'donnees' / 'faux' / 'ok.json').is_file())
        self.assertIn('donnees/outils/tools.json', ' '.join(params.last_errors))

    def test_plugin_config_data(self):
        from vectordrive import plugins
        from vectordrive.io import params
        need(plugins.Api, 'add_config_data')
        api = plugins.Api(plugins.REGISTRY, plugins.PluginInfo('faux_plugin'))
        src = self.box / 'a'
        outside = self.box / 'dehors.json'
        outside.write_text('{}', encoding='utf-8')

        def files():
            d = src / 'app' / 'donnees'
            return [d / 'faux' / 'reglages.json', d / 'faux' / 'absent.json', outside, d / 'faux',
                    d / 'plugins' / 'x.py']
        api.add_config_data('faux', 'Données du faux plugin', files)
        self.addCleanup(lambda: plugins.REGISTRY.config_data.clear())
        self.put(src / 'app' / 'donnees', {'faux/reglages.json': '{"a": 1}', 'plugins/x.py': 'code'})
        st = QSettings(str(self.box / 's.ini'), QSettings.Format.IniFormat)
        out = self.box / 'p.vdparam'
        with self.env(src):
            self.assertEqual(params.available(st)['plugin:faux'], 1)
            counts = params.export(out, st)
        self.assertEqual(counts['plugin:faux'], 1)
        self.assertIn('donnees/faux/reglages.json', zipfile.ZipFile(out).namelist())
        self.assertEqual(len(params.last_errors), 3)                        # dehors, dossier, code : dits
        dst = self.box / 'b'
        self.put(dst / 'app' / 'donnees', {'faux/reglages.json': '{"le mien": 1}'})
        with self.env(dst):
            got, bk = params.import_(out, st, ['plugin:faux'], backup_dir=self.box / 'bk')
        self.assertEqual(got, {'plugin:faux': 1})
        self.assertEqual((dst / 'app/donnees/faux/reglages.json').read_text(encoding='utf-8'), '{"a": 1}')
        self.assertEqual((bk / 'donnees/faux/reglages.json').read_text(encoding='utf-8'), '{"le mien": 1}')

        def boom():
            raise RuntimeError('panne du plugin')
        api.add_config_data('faux', 'Données du faux plugin', boom)
        with self.env(src):
            counts = params.export(self.box / 'q.vdparam', st)
        self.assertEqual(counts['plugin:faux'], 0)                          # l'export se fait quand même
        self.assertIn('panne du plugin', ' '.join(params.last_errors))
        plugins.REGISTRY.config_data.clear()                                # le plugin absent de ce poste
        labels = params.file_labels(out)
        self.assertEqual(labels, {'plugin:faux': 'Données du faux plugin'})
        self.assertEqual(params.contents(out)['plugin:faux'], 1)
        self.assertIn('plugin absent', dict(params.categories(labels))['plugin:faux'])
        with mock.patch('vectordrive.i18n.tr', side_effect=lambda s: 'EN:' + s):
            self.assertTrue(dict(params.categories(labels))['plugin:faux'].startswith('EN:Données du faux plugin'))
            api.add_config_data('faux', 'Données du faux plugin', files)
            self.assertEqual(dict(params.categories())['plugin:faux'], 'EN:Données du faux plugin')
            plugins.REGISTRY.config_data.clear()
        dlg, boxes = self.w._params_choice('Importer', params.contents(out), 'À reprendre :', labels,
                                           exec_dialog=False)
        self.addCleanup(dlg.deleteLater)
        self.assertTrue(boxes['plugin:faux'].isChecked())                   # proposée quand même

    def test_pinned_tabs_with_their_name(self):
        from vectordrive.io import params, registry
        from vectordrive.ui.doctabs import same_file
        need(params, 'PINNED')
        w = self.w
        saved = self.box / 'plaque.vdz'
        registry.save_document(square_doc(), saved)
        self.assertTrue(w.open_path(str(saved)))
        w.pin_tab(on=True)
        w.rename_tab(name='Plaque Durand')
        w.new_document()
        w.canvas.doc.add(square_doc().layers[0].items[0])
        w.pin_tab(on=True)
        w.rename_tab(name='Brouillon client')
        st = QSettings(str(self.box / 's.ini'), QSettings.Format.IniFormat)
        out = self.box / 'onglets.vdparam'
        counts = params.export(out, st, [params.PINNED], window=w)
        self.assertEqual(counts[params.PINNED], 2)
        self.assertIn(params.PINNED + '/dessin_1.vdz', zipfile.ZipFile(out).namelist())   # jamais enregistré
        self.assertEqual(params.contents(out)[params.PINNED], 2)
        n_before = len(w.docs)
        got, _bk = params.import_(out, st, [params.PINNED], window=w)
        self.assertEqual(got[params.PINNED], 2)
        self.assertEqual(sum(1 for t in w.docs if same_file(t.path, str(saved))), 1)   # pas doublé
        self.assertEqual(len(w.docs), n_before)                              # le brouillon, déjà là : retrouvé
        draft = next(t for t in w.docs if t.title == 'Brouillon client')
        draft.pinned = False
        w.close_tab(w.docs.index(draft), answer='non')                       # fermé : il revient, une fois
        n_closed = len(w.docs)
        for _ in range(2):                                                   # importé deux fois : jamais doublé
            got, _bk = params.import_(out, st, [params.PINNED], window=w)
            self.assertEqual(len(w.docs), n_closed + 1)
        self.assertEqual(sum(1 for t in w.docs if t.title == 'Brouillon client'), 1)
        self.assertTrue(all(t.pinned for t in w.docs if t.title in ('Plaque Durand', 'Brouillon client')))
        moved = self.box / 'ailleurs.vdz'
        idx = next(k for k, t in enumerate(w.docs) if same_file(t.path, str(saved)))
        w.docs[idx].pinned = False
        w.close_tab(idx, answer='non')
        saved.rename(moved)
        got, _bk = params.import_(out, st, [params.PINNED], window=w)
        self.assertEqual(got.get('introuvables'), 1)
        self.assertIn('introuvable', ' '.join(params.last_errors))


if __name__ == '__main__':
    unittest.main()
