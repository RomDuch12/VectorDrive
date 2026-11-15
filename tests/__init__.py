"""Tests de VectorDrive. Les fenêtres créées par les tests utilisent un
fichier de réglages temporaire, jamais le profil de l'utilisateur."""
import atexit
import os
import shutil
import tempfile

_dir = tempfile.mkdtemp(prefix='vd_tests_')
# tous les fichiers temporaires des essais (mkdtemp, TemporaryDirectory…) et
# des processus qu'ils lancent vont dans ce dossier, supprimé à la fin : rien
# ne s'accumule dans le Temp de Windows, même avec « python -m unittest »
tempfile.tempdir = _dir
for _k in ('TMP', 'TEMP', 'TMPDIR'):
    os.environ[_k] = _dir
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(_dir, 'reglages.ini'))


def seed_settings(path) -> None:
    """Fichier de réglages d'essais : l'accrochage, actif d'office depuis le round 986, y reste éteint (les essais d'avant
    l'attendent ; ceux qui le veulent l'allument)."""
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write('[options]\naccrochage=false\naccrochage_986=1\n')


seed_settings(os.environ['VECTORDRIVE_SETTINGS'])
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
# bibliotheque (touche B) : jamais celle du poste
os.environ.setdefault('VECTORDRIVE_BIBLIOTHEQUE', os.path.join(_dir, 'bibliotheque'))
# carnet de clients du BAT : jamais celui du poste
os.environ.setdefault('VECTORDRIVE_CLIENTS', os.path.join(_dir, 'clients'))
atexit.register(shutil.rmtree, _dir, True)


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
    fermées sont détruites, comme le ferait l'application."""
    import unittest.suite
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication
    previous = unittest.suite.TestSuite._tearDownPreviousClass

    def tear_down_then_destroy(self, test, result):
        before = getattr(result, '_previousTestClass', None)
        previous(self, test, result)
        app = QApplication.instance()
        if not isinstance(app, QApplication) or before is None or (test is not None and test.__class__ is before):
            return                                   # pas d'application, ou QGuiApplication seule (sans widgets)
        for w in app.topLevelWidgets():
            if not w.isVisible():
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
