"""Round 536 : les cartes graphiques sont lues en fond au démarrage (F10 s'ouvrait en 2,7 s la première
fois : PowerShell lu à l'ouverture de l'onglet Performances)."""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class TestPrefetch(unittest.TestCase):
    def test_started_in_background(self):
        text = (ROOT / 'VectorDrive.py').read_text(encoding='utf-8')
        start = text.index('def main(')
        body = text[start:]
        self.assertIn("threading.Thread(target=gpu.adapters", body)
        self.assertLess(body.index('from vectordrive import gpu'), body.index("threading.Thread(target=gpu.adapters"))

    def test_adapters_cached(self):
        from vectordrive import gpu
        old = gpu._ADAPTERS
        try:
            gpu._ADAPTERS = ['Carte A']
            self.assertEqual(gpu.adapters(), ['Carte A'])           # déjà lues : immédiat
        finally:
            gpu._ADAPTERS = old


if __name__ == '__main__':
    unittest.main()
