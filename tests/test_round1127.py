"""Round 1127 : aucun signal branché sur une fonction nommée dans le panneau de l'assistant (le Défaire d'un bouton
IA compris) : `clicked` lui passerait un booléen."""
import unittest

import tests  # noqa: F401
from tests.test_round144 import risky_connections


class Static(unittest.TestCase):

    def test_assistant_panel_connections(self):
        self.assertEqual([r for r in risky_connections() if r.startswith('assistant_panel.py')], [],
                         'avant : le Défaire du bouton IA branché sans lambda')


if __name__ == '__main__':
    unittest.main()
