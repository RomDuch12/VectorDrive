"""Round 39 : textes TypeEdit sur plusieurs lignes (alignement,
interligne) recalculés sur place."""
import pathlib
import unittest

from vectordrive.core import text as TX
from vectordrive.core.document import Text
from tests.corpus import corpus

SYMBOLS = corpus('symboles_perso')


def texts_of(name):
    from vectordrive.io import smb
    f = corpus(name) if corpus(name).exists() else None
    if f is None:
        raise unittest.SkipTest(f'{name} absent')
    return [t for t in smb.read(f).iter_leaves() if isinstance(t, Text)]


class TestMultiline(unittest.TestCase):
    def check(self, name, start, align):
        t = next((t for t in texts_of(name) if t.text.startswith(start)), None)
        if t is None:
            self.skipTest(f'{start} absent')
        self.assertIn('\n', t.text)
        self.assertEqual(t.align, align)
        a, b = t.outline.bbox(), TX.outline_for(t).bbox()
        self.assertLess(max(abs(x - y) for x, y in zip(a, b)), 0.01 * t.size)
        return t

    def test_centered(self):
        t = self.check('smb_centre', 'Beijing', 'center')
        self.assertGreater(t.line_spacing, 1.0)

    def test_alignment_from_typeedit_flags(self):
        t = next((t for t in texts_of('smb_montage') if t.text.startswith('X -237.5')), None)
        if t is None:
            self.skipTest('texte absent')
        # TypeEdit le dit centré (drapeaux de ligne) ; l'espace final de la
        # 1re ligne le fait paraître aligné à droite
        self.assertEqual(t.align, 'center')


if __name__ == '__main__':
    unittest.main()
