"""Round 466 : documentation — vue 3D, bibliothèque, outils par machine, citées dans le README."""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class TestDocs(unittest.TestCase):
    def test_pages(self):
        readme = (ROOT / 'README.md').read_text(encoding='utf-8')
        for name, word in (('vue_3d.md', 'Visualiser un programme'), ('bibliotheque.md', 'Favoris'),
                           ('outils_par_machine.md', 'Outil conseillé')):
            text = (ROOT / 'docs' / name).read_text(encoding='utf-8')
            self.assertIn(word, text)
            self.assertIn(f'docs/{name}', readme)


if __name__ == '__main__':
    unittest.main()
