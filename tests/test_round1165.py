"""Round 1165 : plantage rare des essais (« Windows fatal exception: access violation », sortie 139) dans
`tests/__init__.py`, à la destruction des fenêtres fermées entre deux classes d'essais. Le balayage détruisait aussi
les fenêtres de premier niveau qui ont un parent, dont le menu caché du bouton d'extension (») d'une QToolBar posée
hors d'une QMainWindow (barre d'accès rapide de TypeEdit 13, barre des favoris) : la barre gardait son adresse, et
la destruction de la fenêtre qui la porte y retirait ses commandes — après test_round1155.Rebuild, entre autres."""
import os
import pathlib
import sys
import tempfile
import unittest
import unittest.suite
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1165.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ.setdefault('VECTORDRIVE_KEYS_MEMORY', '1')

from PySide6.QtGui import QAction  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QMenu, QToolBar, QVBoxLayout, QWidget  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : détruite par le balayage alors que son parent vit encore'


def sweep(test):
    """Le passage de tests/__init__ entre deux classes d'essais, comme si une autre classe venait de finir."""
    class Finished(unittest.TestCase):
        pass
    result = unittest.TestResult()
    result._previousTestClass = Finished
    unittest.suite.TestSuite()._tearDownPreviousClass(test, result)


def watch(obj) -> list:
    """Une liste qui reçoit un élément à la destruction de `obj` (côté Qt : sûr même pour un objet créé par Qt)."""
    dead = []
    obj.destroyed.connect(lambda *_a: dead.append(1))
    return dead


class Sweep(unittest.TestCase):
    def test_extension_menu_of_a_living_toolbar_survives(self):
        holder = QWidget()                               # une barre dans une mise en page, hors d'une QMainWindow
        lay = QVBoxLayout(holder)
        bar = QToolBar()
        lay.addWidget(bar)
        acts = [QAction(f'Commande {i}', holder) for i in range(4)]     # après la barre : détruites après elle
        for a in acts:
            bar.addAction(a)
        holder.show()
        app.processEvents()
        menus = [m for m in bar.findChildren(QMenu) if m.isWindow() and not m.isVisible()]
        self.assertEqual(len(menus), 1, 'le menu caché du bouton d’extension de la barre')
        self.assertIn(menus[0], app.topLevelWidgets())
        menu_dead = watch(menus[0])
        alone = QWidget()                                # fenêtre cachée sans parent : toujours détruite (round 218)
        alone_dead = watch(alone)
        try:
            sweep(self)
            self.assertEqual(alone_dead, [1], 'une fenêtre fermée, sans parent, reste détruite')
            self.assertEqual(menu_dead, [], 'avant : le menu de la barre détruit, la barre gardait son adresse')
            for a in acts:                               # ce que fait la destruction de la fenêtre : sûr, le menu vit
                bar.removeAction(a)
            self.assertEqual(bar.actions(), [])
        finally:
            if not menu_dead:                            # (avant : barre et commandes laissées telles quelles — retirer
                holder.close()                           # une commande y lirait le menu détruit)
            holder.deleteLater()
        holder_dead = watch(holder)
        sweep(self)
        self.assertEqual(holder_dead, [1])

    def test_hidden_child_window_goes_with_its_parent(self):
        parent = QWidget()
        parent.show()
        dlg = QDialog(parent)                            # une fenêtre de dialogue fermée, sa fenêtre encore ouverte
        dlg.show()
        dlg.close()
        app.processEvents()
        self.assertIn(dlg, app.topLevelWidgets())
        dlg_dead, parent_dead = watch(dlg), watch(parent)
        sweep(self)
        self.assertEqual(dlg_dead, [], BEFORE)
        parent.close()                                   # la fenêtre fermée : détruite avec ses enfants
        sweep(self)
        self.assertEqual(parent_dead, [1])
        self.assertEqual(dlg_dead, [1])


class UserProfile(unittest.TestCase):
    """Extension : le dossier des données de VectorDrive (journal des erreurs, onglets gardés, session, polices…)
    restait celui du profil de l'utilisateur pendant les essais — test_round1072 y écrivait erreurs.txt, 979 et 984
    l'effaçaient."""

    def test_data_folders_are_in_the_test_folder(self):
        from vectordrive import journal, portable
        from vectordrive.core import fonts
        from vectordrive.ui import closed_store, session
        here = os.path.normcase(os.path.abspath(tempfile.gettempdir()))         # le dossier des essais
        from vectordrive import thumbshell
        for p in (portable.data_dir(), journal.path(), closed_store.folder(), session.default_dir(),
                  fonts.cache_file(), thumbshell.dll_dir()):
            got = os.path.normcase(os.path.abspath(str(p)))
            self.assertTrue(got.startswith(here + os.sep), f'avant : {p} dans le profil de l’utilisateur')

    @unittest.skipUnless(sys.platform == 'win32', 'Windows : %LOCALAPPDATA%')
    def test_the_real_folder_is_refused(self):
        import tests
        from vectordrive import portable
        real = getattr(tests, 'REAL_LOCALAPPDATA', None) or os.environ.get('LOCALAPPDATA', '')
        self.assertTrue(real)
        with mock.patch.dict(os.environ, {'LOCALAPPDATA': real}), \
                mock.patch.object(portable, 'is_portable', return_value=False), \
                mock.patch.object(sys, '__stderr__', None):      # (rien n'est écrit : un chemin ; refus voulu, tu)
            with self.assertRaises(AssertionError, msg='avant : le vrai dossier rendu, les essais y écrivaient') as cm:
                portable.data_dir()
        self.assertIn('vrai dossier de VectorDrive', str(cm.exception))
        self.assertIn(os.path.normcase(str(pathlib.Path(real) / 'VectorDrive')), os.path.normcase(str(cm.exception)))
        tests.REFUSED.clear()                            # (refus voulu : pas dit à la fin des essais)


if __name__ == '__main__':
    unittest.main()
