"""Round 601 : la documentation de l'architecture décrit les fonctions propres à une machine (posts,
add_panel, on_post_changed, add_post_export, post_options, machine_dir) — et l'API les offre."""
import pathlib
import unittest

from vectordrive import plugins

ROOT = pathlib.Path(__file__).resolve().parents[1]


class TestDocumented(unittest.TestCase):
    def test_api_and_doc(self):
        doc = (ROOT / 'docs' / 'ARCHITECTURE.md').read_text(encoding='utf-8')
        for name in ('add_panel', 'on_post_changed', 'add_post_export'):
            self.assertTrue(hasattr(plugins.Api, name), name)
            self.assertIn(name, doc)
        for word in ('posts=', 'post_options', 'machine_dir', 'cam.post.family'):
            self.assertIn(word, doc)


if __name__ == '__main__':
    unittest.main()
