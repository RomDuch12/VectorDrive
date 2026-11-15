"""Round 490 : nettoyage (panneau FAO, traductions)."""
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class TestCleanup(unittest.TestCase):
    def test_translations(self):
        tr = json.loads((ROOT / 'vectordrive' / 'ressources' / 'i18n' / 'en.json').read_text(encoding='utf-8'))
        self.assertNotIn(' — rampe {0}° sur {1} mm', tr)
        self.assertIn('Rampe {0}° sur {1} mm par passe', tr)

    def test_no_unused_post_import(self):
        src = (ROOT / 'vectordrive' / 'ui' / 'cam_panel.py').read_text(encoding='utf-8')
        self.assertNotIn('import post as _post', src)


if __name__ == '__main__':
    unittest.main()
