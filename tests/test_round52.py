"""Round 52 : analyse statique — aucun nom indéfini dans le code."""
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class TestStatic(unittest.TestCase):
    def test_no_undefined_names(self):
        try:
            import pyflakes  # noqa: F401
        except ImportError:
            self.skipTest('pyflakes absent (requirements-dev.txt)')
        r = subprocess.run([sys.executable, '-m', 'pyflakes', 'vectordrive', 'VectorDrive.py', 'outils'],
                           cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace')
        bad = [ln for ln in r.stdout.splitlines()
               if 'undefined name' in ln or 'syntax error' in ln.lower() or 'undefined local' in ln]
        self.assertEqual(bad, [])


if __name__ == '__main__':
    unittest.main()
