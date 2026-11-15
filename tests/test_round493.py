"""Round 493 : libellés du navigateur Ouvrir traduits."""
import json
import pathlib
import unittest

import vectordrive


class TestBrowserTranslations(unittest.TestCase):
    def test_labels(self):
        t = json.loads((pathlib.Path(vectordrive.__file__).parent / 'ressources' / 'i18n' / 'en.json')
                       .read_text(encoding='utf-8'))
        from vectordrive.ui.file_browser import FILTERS
        for label, _e in FILTERS:
            self.assertIn(label, t)
        self.assertIn('Boîte de Windows…', t)


if __name__ == '__main__':
    unittest.main()
