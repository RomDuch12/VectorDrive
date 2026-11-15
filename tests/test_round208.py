"""Round 208 : liste de validation sur machine présente et reliée."""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class TestDoc(unittest.TestCase):
    def test_document_and_link(self):
        doc = (ROOT / 'docs' / 'validation_machine.md').read_text(encoding='utf-8')
        for word in ('Enroulement', 'Projection parallèle', 'morceaux', 'axe rotatif', 'Galbe'):
            self.assertIn(word, doc)
        self.assertNotIn('Plugin', doc)                                           # le cœur ne parle pas du plugin
        self.assertIn('docs/validation_machine.md', (ROOT / 'README.md').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
