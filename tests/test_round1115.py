"""Round 1115 : le filtre DWG du navigateur de fichiers (suite de 1114, « support complet dwg »)."""
import json
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1115.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

import vectordrive  # noqa: E402
from vectordrive.ui import file_browser as FB  # noqa: E402


class Filter(unittest.TestCase):
    def test_dwg_has_its_filter(self):
        labels = [label for label, _e in FB.FILTERS]
        self.assertIn('DWG (AutoCAD)', labels, 'avant : les DWG dans « Autres dessins »')
        self.assertEqual(FB.FILTERS[-1], ('DWG (AutoCAD)', ('.dwg',)))       # à la fin : les filtres retenus gardent leur rang
        others = dict(FB.FILTERS)['Autres dessins (HPGL, EMF, WMF, CorelDRAW, Visio…)']
        self.assertNotIn('.dwg', others)
        self.assertIn('.emf', others)
        self.assertIn('.dwg', dict(FB.FILTERS)['Tous les dessins'])
        en = json.loads((pathlib.Path(vectordrive.__file__).parent / 'ressources' / 'i18n' / 'en.json')
                        .read_text(encoding='utf-8'))
        self.assertIn('DWG (AutoCAD)', en)


if __name__ == '__main__':
    unittest.main()
