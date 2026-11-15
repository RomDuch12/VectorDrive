"""Round 555 : programmes appelés — copie locale trouvée dans un dossier parent de l'appelant avec la fin
du chemin machine ; partage réseau injoignable sauté une minute (pas d'attente à chaque aperçu)."""
import os
import pathlib
import tempfile
import time
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import ncpaths


class TestLocalCopy(unittest.TestCase):
    def setUp(self):
        ncpaths._DOWN.clear()

    def test_parent_suffix(self):
        root = pathlib.Path(tempfile.mkdtemp()) / 'Programme Datron'
        (root / 'Tranch' / 'Autres').mkdir(parents=True)
        (root / 'Tranch' / 'Date.simpl').write_text('x', encoding='utf-8')
        caller = root / 'Tranch' / 'Autres' / 'EC045.simpl'
        got = ncpaths.resolve(r'network:T:\RomDuch\Tranch\Date.simpl', caller=str(caller), rules=[])
        self.assertEqual(pathlib.Path(got), root / 'Tranch' / 'Date.simpl')

    def test_unreachable_server_skipped(self):
        calls = []
        real = os.path.isfile

        def slow(p):
            calls.append(p)
            if str(p).startswith('\\\\'):
                t = time.monotonic()
                while time.monotonic() - t < ncpaths.SLOW_S + 0.05:
                    pass
                return False
            return real(p)
        rules = [('network:T:', r'\\absent\partage')]
        with mock.patch('os.path.isfile', side_effect=slow):
            self.assertIsNone(ncpaths.resolve(r'network:T:\a.simpl', rules=rules))
            self.assertIn('absent', ncpaths._DOWN)
            n = len(calls)
            t0 = time.monotonic()
            ncpaths.resolve(r'network:T:\b.simpl', rules=rules)
            self.assertLess(time.monotonic() - t0, ncpaths.SLOW_S)               # sauté, sans attente
            self.assertFalse(any(str(p).startswith('\\\\') for p in calls[n:]))


if __name__ == '__main__':
    unittest.main()
