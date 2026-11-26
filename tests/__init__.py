"""Tests de VectorDrive. Les fenêtres créées par les tests utilisent un
fichier de réglages temporaire, jamais le profil de l'utilisateur."""
import atexit
import os
import shutil
import sys
import tempfile

_dir = tempfile.mkdtemp(prefix='vd_tests_')
# tous les fichiers temporaires des essais (mkdtemp, TemporaryDirectory…) et
# des processus qu'ils lancent vont dans ce dossier, supprimé à la fin : rien
# ne s'accumule dans le Temp de Windows, même avec « python -m unittest »
tempfile.tempdir = _dir
for _k in ('TMP', 'TEMP', 'TMPDIR'):
    os.environ[_k] = _dir
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(_dir, 'reglages.ini'))
# les clés d'API de l'assistant IA : en mémoire, jamais dans le gestionnaire d'identifiants de Windows du poste
os.environ['VECTORDRIVE_KEYS_MEMORY'] = '1'
# le dossier des données de VectorDrive (`portable.data_dir` : journal des erreurs, onglets gardés, session, index
# des polices, plugins, sauvegardes…) et tout ce que le code range sous %LOCALAPPDATA% : dans le dossier des essais,
# jamais dans le profil de l'utilisateur (round 1165 ; avant, les essais écrivaient — et effaçaient — son erreurs.txt)
REAL_LOCALAPPDATA = os.environ.get('LOCALAPPDATA', '')
if sys.platform == 'win32':
    os.environ['LOCALAPPDATA'] = os.path.join(_dir, 'LocalAppData')


def seed_settings(path) -> None:
    """Fichier de réglages d'essais : l'accrochage, actif d'office depuis le round 986, y reste éteint (les essais d'avant
    l'attendent ; ceux qui le veulent l'allument) ; les accrochages laissés par une fenêtre ne sont pas repris par la
    suivante (round 1153 : les essais partagent ce fichier et attendent l'état d'office)."""
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write('[options]\naccrochage=false\naccrochage_986=1\n[accrochage]\nretenir=false\n')


seed_settings(os.environ['VECTORDRIVE_SETTINGS'])
SNAP_STATE = ('accrochage/actif', 'accrochage/modes', 'accrochage/reperage', 'accrochage/polaire')


def reseed() -> None:
    """La graine de `seed_settings`, remise dans le fichier de réglages du moment entre deux classes d'essais (round
    1159) : un essai qui retire les réglages d'options, ou dont la fenêtre retient ses accrochages, changeait l'état
    de départ des essais suivants du même processus, selon leur ordre (rounds 1153 et 1158). Passe avant le
    `setUpModule` et le `setUpClass` de la classe suivante : ce qu'ils posent est gardé ; ce qu'un `setUpModule` pose
    ne vaut donc que pour la première classe de son module. Le fichier n'est réécrit que s'il diffère de la graine."""
    path = os.environ.get('VECTORDRIVE_SETTINGS')
    if not path:
        return
    try:
        from PySide6.QtCore import QSettings
        st = QSettings(path, QSettings.Format.IniFormat)
        changed = False
        for key, want in (('options/accrochage', 'false'), ('options/accrochage_986', '1'),
                          ('accrochage/retenir', 'false')):
            if str(st.value(key)).lower() != want:
                st.setValue(key, False if want == 'false' else want)
                changed = True
        for key in SNAP_STATE:
            if st.contains(key):
                st.remove(key)
                changed = True
        if changed:
            st.sync()
    except Exception:
        pass


os.environ.setdefault('VECTORDRIVE_CACHE', _dir)
# Mes outils : jamais la bibliothèque de l'utilisateur (le panneau FAO y prend des outils)
os.environ.setdefault('VECTORDRIVE_TOOLS', os.path.join(_dir, 'outils', 'tools.json'))
# modèles d'usinage et de dessin : jamais ceux de l'utilisateur
os.environ.setdefault('VECTORDRIVE_CAM_TEMPLATES', os.path.join(_dir, 'modeles_fao'))
os.environ.setdefault('VECTORDRIVE_DOC_TEMPLATES', os.path.join(_dir, 'modeles_dessin'))
# espaces de travail (étaux, mandrins) : jamais ceux de l'utilisateur
os.environ.setdefault('VECTORDRIVE_WORKSPACES', os.path.join(_dir, 'espaces_de_travail'))
# session jetable par fenêtre : fermée sans question, comme la fenêtre de tous les jours ; jamais celle de l'utilisateur
os.environ.setdefault('VECTORDRIVE_SESSION_TEMP', os.path.join(_dir, 'sessions'))
os.environ.setdefault('VECTORDRIVE_SESSION', os.path.join(_dir, 'session'))
# onglets gardés à leur fermeture : jamais ceux de l'utilisateur
os.environ.setdefault('VECTORDRIVE_CLOSED_TABS', os.path.join(_dir, 'onglets_fermes'))
# bibliotheque (touche B) : jamais celle du poste
os.environ.setdefault('VECTORDRIVE_BIBLIOTHEQUE', os.path.join(_dir, 'bibliotheque'))
# carnet de clients du BAT : jamais celui du poste
os.environ.setdefault('VECTORDRIVE_CLIENTS', os.path.join(_dir, 'clients'))
# copies de l'assistant IA et leur registre : jamais celles du poste
os.environ.setdefault('VECTORDRIVE_ASSISTANT_DIR', os.path.join(_dir, 'assistant'))
# mise à jour de l'application par dossier : jamais les Documents, le partage ni les raccourcis du poste ; ni
# PowerShell ni exécutable lancés, ni le canal d'instance interrogé
os.environ.setdefault('VECTORDRIVE_APP_UPDATE', os.path.join(_dir, 'maj_application'))
atexit.register(shutil.rmtree, _dir, True)

#: dossiers de données de VectorDrive du profil de l'utilisateur (casse et chemin normalisés) : aucun essai n'y écrit
REAL_DATA: list = []
#: les dossiers refusés par le garde-fou pendant les essais (dits à la fin)
REFUSED: list = []


def is_real(path) -> bool:
    """`path` est-il (dans) un dossier de données de VectorDrive du profil de l'utilisateur ?"""
    p = os.path.normcase(os.path.abspath(str(path)))
    return any(p == r or p.startswith(r + os.sep) for r in REAL_DATA)


def _guard_data_dir():
    """Garde-fou (round 1165) : `portable.data_dir()` qui rendrait un dossier du profil de l'utilisateur (variable
    d'isolement retirée par un essai, repli sur le dossier personnel…) lève une AssertionError, dite aussi sur la
    sortie d'erreur et à la fin des essais : l'essai échoue au lieu d'écrire chez l'utilisateur. Hors de Windows
    (macOS, Linux : le dossier personnel, sans variable à rediriger), il rend le dossier des données des essais."""
    import pathlib
    from vectordrive import portable
    home = pathlib.Path.home()
    real = [home / 'VectorDrive', home / 'Library' / 'Application Support' / 'VectorDrive']
    if REAL_LOCALAPPDATA:
        real.append(pathlib.Path(REAL_LOCALAPPDATA) / 'VectorDrive')
    REAL_DATA[:] = [os.path.normcase(os.path.abspath(str(p))) for p in real]
    original = portable.data_dir

    def data_dir() -> pathlib.Path:
        d = original()
        if not is_real(d):
            return d
        if sys.platform != 'win32':
            return pathlib.Path(_dir) / 'donnees'
        msg = f'essai : écriture dans le vrai dossier de VectorDrive refusée ({d}) — une variable d’isolement retirée ?'
        REFUSED.append(str(d))
        if sys.__stderr__ is not None:
            sys.__stderr__.write('\n' + msg + '\n')
        raise AssertionError(msg)
    data_dir.__doc__ = original.__doc__
    portable.data_dir = data_dir


def _tell_refused():
    if REFUSED and sys.__stderr__ is not None:
        sys.__stderr__.write(f'\nESSAIS : {len(REFUSED)} écriture(s) refusée(s) dans le vrai dossier de VectorDrive '
                             f'({sorted(set(REFUSED))})\n')


_guard_data_dir()
atexit.register(_tell_refused)


def _clear_clipboard():
    """Le greffon Qt « offscreen » plante à la sortie s'il garde des données
    dans le presse-papiers (l'application réelle sous Windows, non)."""
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            app.clipboard().clear()
    except Exception:
        pass


# PySide6 enregistre son propre nettoyage à l'import : l'importer d'abord
# pour que le vidage du presse-papiers passe avant lui (atexit : dernier
# enregistré, premier exécuté)
import PySide6.QtWidgets  # noqa: E402,F401

atexit.register(_clear_clipboard)


def _no_modal_boxes():
    """Une boîte QMessageBox modale (information, warning, critical,
    question) attendrait sans fin hors écran et bloquerait toute la suite :
    elle fait échouer l'essai à la place. Les essais qui en attendent une la
    remplacent (mock.patch.object) le temps du bloc."""
    from PySide6.QtWidgets import QMessageBox

    def refuse(name):
        def box(*args, **kwargs):
            text = next((a for a in args[1:4] if isinstance(a, str)), '')
            raise AssertionError(f'QMessageBox.{name} modale dans un essai : {text[:160]!r}')
        return staticmethod(box)

    for name in ('information', 'warning', 'critical', 'question'):
        setattr(QMessageBox, name, refuse(name))


_no_modal_boxes()


def _close_windows_between_classes():
    """Les fenêtres fermées par les essais restaient en vie (près de 12 000
    widgets après 100 essais, 65 000 après 400) : chaque essai suivant
    ralentissait (thèmes : jusqu'à 280 s) et, vers le millième, la première
    boucle imbriquée (celle de `progress.run`, dans test_round92) bloquait
    la suite entière (round 218). Entre deux classes d'essais, les fenêtres
    fermées sont détruites, comme le ferait l'application.

    Seulement les fenêtres sans parent (round 1165) : une fenêtre de premier
    niveau qui a un parent appartient à celui-ci, qui la détruira avec lui —
    et parfois la garde par un pointeur nu. Le menu du bouton d'extension
    (») d'une QToolBar posée hors d'une QMainWindow (barre d'accès rapide de
    TypeEdit 13, barre des favoris) est un QMenu caché, enfant de ce bouton : détruit
    ici, la barre restait en vie avec son adresse ; à la destruction de la
    fenêtre qui la porte, chaque commande retirée de la barre l'était aussi
    de ce menu détruit — violation d'accès, rare (selon ce que la mémoire
    libérée était devenue), après test_round1155.Rebuild entre autres."""
    import unittest.suite
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication
    previous = unittest.suite.TestSuite._tearDownPreviousClass

    def tear_down_then_destroy(self, test, result):
        before = getattr(result, '_previousTestClass', None)
        previous(self, test, result)
        if before is not None and (test is None or test.__class__ is not before):
            reseed()                                 # l'état de départ des réglages, pour la classe suivante
        app = QApplication.instance()
        if not isinstance(app, QApplication) or before is None or (test is not None and test.__class__ is before):
            return                                   # pas d'application, ou QGuiApplication seule (sans widgets)
        for w in app.topLevelWidgets():
            if not w.isVisible() and w.parentWidget() is None:   # un enfant part avec son parent (round 1165)
                w.deleteLater()
        loop = QEventLoop()                          # dans une boucle : Qt détruit ce qui attend
        QTimer.singleShot(0, loop.quit)
        loop.exec()

    unittest.suite.TestSuite._tearDownPreviousClass = tear_down_then_destroy


_close_windows_between_classes()


def _release_keys_after_each_test():
    """`QTest.keyClick` ou `mouseClick` avec Ctrl, Maj ou Alt laisse Qt croire la touche enfoncée : hors écran, aucun
    clavier ne le dément. L'essai suivant qui lit `QApplication.keyboardModifiers()` se trompait — l'outil Marqueur
    ouvrait sa fenêtre de réglages (Ctrl sur l'outil) et la suite attendait sans fin, selon l'ordre des essais
    (round 932). Après chaque essai, les touches sont relâchées."""
    import unittest
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QWidget

    class Sink(QWidget):
        def keyReleaseEvent(self, ev):
            ev.accept()

    previous = unittest.TestCase.run

    def run_then_release(self, result=None):
        try:
            return previous(self, result)
        finally:
            app = QApplication.instance()
            if isinstance(app, QApplication) and QApplication.keyboardModifiers() != Qt.KeyboardModifier.NoModifier:
                sink = Sink()                        # un relâchement sans modificateur : Qt les oublie
                QTest.keyRelease(sink, Qt.Key.Key_Control)
                sink.deleteLater()

    unittest.TestCase.run = run_then_release


_release_keys_after_each_test()
