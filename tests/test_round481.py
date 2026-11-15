"""Round 481 : documentation — vue 3D (plaque, finesse, brut), catalogues d'opérations, Finition 2,5D."""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class TestDocs(unittest.TestCase):
    def test_pages(self):
        readme = (ROOT / 'README.md').read_text(encoding='utf-8')
        self.assertIn('docs/catalogues_fao.md', readme)
        cat = (ROOT / 'docs' / 'catalogues_fao.md').read_text(encoding='utf-8')
        for word in ('add_instruction_catalog', 'Finition 2,5D', 'décalage en XY', 'Options'):
            self.assertIn(word, cat)
        v3d = (ROOT / 'docs' / 'vue_3d.md').read_text(encoding='utf-8')
        for word in ('Finesse', 'Plaque', 'BLK FORM'):
            self.assertIn(word, v3d)


if __name__ == '__main__':
    unittest.main()
