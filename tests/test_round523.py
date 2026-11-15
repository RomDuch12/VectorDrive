"""Round 523 : outils/tests_paralleles.py — la suite répartie en morceaux (chaque module dans un seul
morceau, tous couverts) ; fin_de_round.sh s'en sert."""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'outils'))

import tests_paralleles as TP  # noqa: E402


class TestPieces(unittest.TestCase):
    def test_partition(self):
        mods = TP.modules()
        self.assertIn('tests.test_round523', mods)
        n = 4
        pieces = [mods[k::n] for k in range(n)]
        flat = [m for p in pieces for m in p]
        self.assertEqual(sorted(flat), mods)
        self.assertEqual(len(flat), len(set(flat)))

    def test_script_used(self):
        text = (ROOT / 'outils' / 'fin_de_round.sh').read_text(encoding='utf-8')
        self.assertIn('outils/tests_paralleles.py', text)


if __name__ == '__main__':
    unittest.main()
