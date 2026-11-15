"""Round 589 : les essais nettoient leurs fichiers temporaires — mkdtemp, TemporaryDirectory et les
processus lancés écrivent dans le dossier des essais, supprimé à la fin (plus de milliers de dossiers
tmp* dans le Temp de Windows, même avec « python -m unittest »)."""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import tests

ROOT = pathlib.Path(__file__).resolve().parents[1]


class TestTempDesEssais(unittest.TestCase):
    def test_mkdtemp_dans_le_dossier_des_essais(self):
        base = pathlib.Path(tests._dir).resolve()
        self.assertEqual(pathlib.Path(tempfile.gettempdir()).resolve(), base)
        d = pathlib.Path(tempfile.mkdtemp()).resolve()
        self.assertEqual(d.parent, base)
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(pathlib.Path(t).resolve().parent, base)

    def test_processus_lances(self):
        out = subprocess.run([sys.executable, '-c', 'import tempfile; print(tempfile.gettempdir())'],
                             capture_output=True, text=True, timeout=60).stdout.strip()
        self.assertEqual(pathlib.Path(out).resolve(), pathlib.Path(tests._dir).resolve())

    def test_dossier_supprime_a_la_fin(self):
        code = ('import tests, tempfile, pathlib; d = tempfile.mkdtemp(); '
                'pathlib.Path(d, "f.txt").write_text("x"); print(tests._dir)')
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
        out = subprocess.run([sys.executable, '-c', code], cwd=ROOT, env=env,
                             capture_output=True, text=True, timeout=120).stdout.strip().splitlines()[-1]
        self.assertTrue(out)
        self.assertFalse(os.path.exists(out))

    def test_autotest_supprime_son_dossier(self):
        src = (ROOT / 'VectorDrive.py').read_text(encoding='utf-8')
        i = src.index("mkdtemp(prefix='vd_autotest_')")
        self.assertIn('atexit.register(shutil.rmtree, _tmp, True)', src[i:i + 300])


if __name__ == '__main__':
    unittest.main()
