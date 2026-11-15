"""Round 605 : guide de l'usinage 3D (docs/usinage_3d.md) — il nomme les commandes telles que l'interface
les affiche."""
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class TestGuide(unittest.TestCase):
    def test_names_match_interface(self):
        doc = (ROOT / 'docs' / 'usinage_3d.md').read_text(encoding='utf-8')
        en = json.loads((ROOT / 'vectordrive' / 'ressources' / 'i18n' / 'en.json').read_text(encoding='utf-8'))
        for label in ('Usinage 3D', 'Corps', 'Mécanismes', 'Convertir en volumes du dessin', 'Fermé', 'Ouvert',
                      'Contours dans le dessin', 'Remplacer la zone de', 'Montrer la zone de'):
            self.assertIn(label, en, label)                                  # un libellé de l'interface
            self.assertIn(label, doc, label)
        for kind in ('Ébauche 3D', 'Reprise 3D', 'Niveaux constants 3D', 'Surface 3D'):
            self.assertIn(kind, doc)


if __name__ == '__main__':
    unittest.main()
