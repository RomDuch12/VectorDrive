"""Round 845 : un module du cœur ne doit jamais en remplacer un autre sans bruit.

Le round 839 avait écrasé core/envelope.py (les enveloppes de déformation) en y mettant le contour du trait : ses propres
essais passaient, seule la suite complète l'a vu, avant la publication.
"""
import importlib
import pkgutil
import unittest

import vectordrive.core


class TestCoreModules(unittest.TestCase):

    def test_every_core_module_imports(self):
        """Un nom importé par un autre module qui disparaît se voit ici, même si aucun essai n'appelle la fonction."""
        bad = {}
        for info in pkgutil.iter_modules(vectordrive.core.__path__):
            try:
                importlib.import_module(f'vectordrive.core.{info.name}')
            except ImportError as e:
                if 'vectordrive' in str(e):                 # une dépendance optionnelle absente n'est pas le sujet
                    bad[info.name] = str(e)
        self.assertEqual(bad, {})

    def test_the_envelopes_are_back(self):
        from vectordrive.core import envelope as E
        for name in ('KINDS', 'EnvelopeSpec', 'build', 'build_in_curves', 'mapping', 'map_segment', '_deriv'):
            self.assertTrue(hasattr(E, name), name)
        self.assertGreater(len(E.KINDS), 5)

    def test_the_stroke_has_its_own_module(self):
        from vectordrive.core import strokehull as H
        for name in ('stroke', 'envelope', 'concave', 'CORNERS', 'ENDS', 'ENVELOPES'):
            self.assertTrue(hasattr(H, name), name)

    def test_the_two_modules_do_not_share_a_name_by_accident(self):
        from vectordrive.core import envelope as E, strokehull as H
        self.assertIsNot(E, H)
        self.assertFalse(hasattr(E, 'stroke'))
        self.assertFalse(hasattr(H, 'build'))

    def test_path_bend_uses_the_real_envelope(self):
        from vectordrive.core import pathbend
        self.assertTrue(callable(pathbend.map_segment))


if __name__ == '__main__':
    unittest.main()
