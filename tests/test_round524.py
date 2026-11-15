"""Round 524 : outils/tests_paralleles.py — Temp des essais dans un dossier à part, supprimé à la fin
(les essais laissaient des dizaines de milliers de dossiers dans le Temp de Windows)."""
import os
import pathlib
import sys
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'outils'))

import tests_paralleles as TP  # noqa: E402


class FakeProc:
    seen = []

    def __init__(self, cmd, cwd=None, env=None, stdout=None, stderr=None):
        FakeProc.seen.append(env)
        pathlib.Path(env['TMP'], 'trace.txt').write_text('x')       # un essai qui laisse un fichier
        stdout.write('Ran 1 test in 0.001s\nOK\n')

    def wait(self):
        return 0


class TestScratch(unittest.TestCase):
    def test_scratch_removed(self):
        FakeProc.seen = []
        with mock.patch.object(TP.subprocess, 'Popen', FakeProc):
            self.assertEqual(TP.main(['--processus', '2']), 0)
        self.assertEqual(len(FakeProc.seen), 2)
        tmp = FakeProc.seen[0]['TMP']
        self.assertEqual(FakeProc.seen[0]['TEMP'], tmp)
        self.assertIn('vd_essais_', tmp)
        self.assertFalse(os.path.exists(tmp))                          # supprimé avec ce qu'il contenait


if __name__ == '__main__':
    unittest.main()
