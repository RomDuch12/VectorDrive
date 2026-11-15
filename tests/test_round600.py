"""Round 600 : réglages propres à un post-processeur gardés avec le dessin (CamSetup.post_options) — par
exemple la touche de fonction d'une machine."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model
from vectordrive.core.document import Document


class TestPostOptions(unittest.TestCase):
    def test_round_trip(self):
        s = model.CamSetup(post='essai', post_options={'essai': {'touche': 3, 'nom': 'x'}})
        d = Document()
        model.store(d, s)
        back = model.setup_of(d)
        self.assertEqual(back.post_options, {'essai': {'touche': 3, 'nom': 'x'}})
        self.assertEqual(model.CamSetup.from_dict({}).post_options, {})
        self.assertEqual(model.CamSetup.from_dict({'post_options': {'a': 'pas un dict'}}).post_options, {})


if __name__ == '__main__':
    unittest.main()
