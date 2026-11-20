"""Round 1102 : un lecteur verrouillé par BitLocker faisait échouer « Ouvrir » — Python 3.13 lève une exception dans
`Path.is_dir` / `exists` / `is_file` pour cette erreur Windows. Pris pour « absent » ; pas les erreurs réseau passagères
(un fichier partagé lu « absent » pendant une coupure serait recréé et écraserait l'original)."""
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1102.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from vectordrive import winpaths  # noqa: E402

LOCKED = -2144272384                                     # FVE_E_LOCKED_VOLUME


def failing_stat(prefix, winerror):
    real = os.stat

    def stat(path, *a, **k):
        if os.fspath(path).upper().startswith(prefix):
            raise OSError(None, 'lecteur qui ne répond pas', os.fspath(path), winerror)
        return real(path, *a, **k)
    return stat


@unittest.skipUnless(sys.platform == 'win32', 'erreurs Windows')
class TestUnreachable(unittest.TestCase):
    def test_codes_added(self):
        from pathlib import _abc
        self.assertTrue(winpaths.tolerant())
        for e in (LOCKED, 1005, 1112, 21, 123, 1921):
            self.assertIn(e, _abc._IGNORED_WINERRORS)
        for e in (59, 64, 1231):                                   # réseau passager : pas « absent »
            self.assertNotIn(e, _abc._IGNORED_WINERRORS)
        n = len(_abc._IGNORED_WINERRORS)
        winpaths.tolerant()
        self.assertEqual(len(_abc._IGNORED_WINERRORS), n)              # pas de doublons

    def test_locked_drive_absent(self):
        for code in winpaths.UNREACHABLE_WINERRORS:
            with self.subTest(code=code), mock.patch('os.stat', failing_stat('Q:', code)):
                p = pathlib.Path('Q:/dossier/plan.vnd')
                self.assertFalse(p.exists())
                self.assertFalse(p.parent.is_dir())
                self.assertFalse(p.is_file())

    def test_other_errors_still_raise(self):
        for code in (5, 59, 64, 1231):                            # accès refusé, réseau passager : une erreur
            with self.subTest(code=code), mock.patch('os.stat', failing_stat('Q:', code)):
                with self.assertRaises(OSError):
                    pathlib.Path('Q:/x').is_dir()

    def test_file_browser_drives(self):
        # liste des lecteurs et dossiers ajoutés : `os.path.isdir` (jamais d'erreur), pas `Path.is_dir`
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        from vectordrive.ui import file_browser

        class Drive:
            def __init__(self, p):
                self.p = p

            def absoluteFilePath(self):
                return self.p
        real_isdir = os.path.isdir
        asked = []

        def isdir(p):
            asked.append(os.fspath(p))
            return False if os.fspath(p).upper().startswith('Q:') else real_isdir(p)

        def no_is_dir(self, *a, **k):
            raise OSError(None, 'verrouillé', str(self), 5)
        with (tempfile.TemporaryDirectory() as tmp,
              mock.patch('PySide6.QtCore.QDir.drives', staticmethod(lambda: [Drive('Q:/'), Drive(tmp)])),
              mock.patch('os.path.isdir', isdir), mock.patch.object(pathlib.Path, 'is_dir', no_is_dir)):
            roots = file_browser.system_roots()
            self.assertNotIn(pathlib.Path('Q:/'), roots)
            self.assertIn(pathlib.Path(tmp), roots)
            self.assertTrue(any(a.upper().startswith('Q:') for a in asked))
            panel = file_browser.FileBrowserPanel.__new__(file_browser.FileBrowserPanel)
            st = mock.Mock()
            st.value = lambda key, default=None: ['Q:/partage', tmp]
            got = file_browser.FileBrowserPanel._initial_roots(panel, st)
            self.assertNotIn(pathlib.Path('Q:/partage'), got)
            self.assertIn(pathlib.Path(tmp), got)

    def test_worker_processes_tolerant(self):
        # processus de calcul (spawn) : la liste élargie y est aussi
        import multiprocessing
        from concurrent.futures import ProcessPoolExecutor
        from vectordrive.core import workers
        with ProcessPoolExecutor(1, mp_context=multiprocessing.get_context('spawn'),
                                 initializer=workers._start_process, initargs=(False,)) as ex:
            got = ex.submit(eval, "__import__('pathlib._abc', fromlist=['x'])._IGNORED_WINERRORS").result(timeout=120)
        self.assertIn(LOCKED, got)

    def test_imported_by_window_and_launcher(self):
        import inspect
        from vectordrive.ui import main_window
        self.assertIs(main_window.winpaths, winpaths)
        launcher = pathlib.Path(__file__).resolve().parents[1] / 'VectorDrive.py'
        self.assertIn('from vectordrive import winpaths', launcher.read_text(encoding='utf-8'))
        self.assertTrue(inspect.getsource(winpaths).count('UNREACHABLE_WINERRORS'))


if __name__ == '__main__':
    unittest.main()
