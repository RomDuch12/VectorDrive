"""Round 919 : VD Géo — ƒ, ℮ et les accents isolés ˆ ˜ ˘ ˙ ˚ ˝ ˇ ˛ : tout Windows-1252 est dessiné."""
import unittest

from vectordrive.core import strokegeo as sg


def box(ch):
    return sg.glyph(ch)[0].bbox()


class Windows1252(unittest.TestCase):

    def test_every_printable_character(self):
        chars = set(sg.characters())
        for b in list(range(0x20, 0x7F)) + list(range(0x80, 0x100)):
            try:
                ch = bytes([b]).decode('cp1252')
            except UnicodeDecodeError:                                  # 81, 8D, 8F, 90, 9D : non attribués
                continue
            if ch in ' \xa0\xad':
                continue
            with self.subTest(ch=f'U+{ord(ch):04X}'):
                self.assertTrue(sg.has(ch))
                self.assertIn(ch, chars)
                self.assertTrue(sg.glyph(ch)[0])


class Shapes(unittest.TestCase):

    def test_florin(self):
        x0, y0, x1, y1 = box('ƒ')
        self.assertAlmostEqual(y1, sg.ASC, places=6)                     # comme le f en haut
        self.assertLess(y0, -0.25)                                        # sous la ligne, comme un jambage
        self.assertEqual(len(sg.glyph('ƒ')[0].contours), 2)             # fût et crochets d'un trait, la barre
        self.assertAlmostEqual(box('f')[3], y1, places=6)

    def test_estimated_sign(self):
        x0, y0, x1, y1 = box('℮')
        ex0, ey0, ex1, ey1 = box('e')
        self.assertGreater(y1 - y0, (ey1 - ey0) * 1.1)                   # plus grand qu'un e
        self.assertLess(y1, 1.0)
        self.assertEqual(len(sg.glyph('℮')[0].contours), 1)

    def test_spacing_accents_are_the_marks(self):
        for spacing, letter, base in (('ˆ', 'ê', 'e'), ('˜', 'ñ', 'n'), ('ˇ', 'č', 'c'), ('˘', 'ă', 'a'),
                                      ('˚', 'å', 'a'), ('˙', 'ż', 'z'), ('˝', 'ő', 'o')):
            with self.subTest(ch=spacing):
                n = len(sg.glyph(letter)[0].contours) - len(sg.glyph(base)[0].contours)
                self.assertEqual(len(sg.glyph(spacing)[0].contours), n)
                self.assertGreater(box(spacing)[1], sg.XH)               # au-dessus de la hauteur d'x
        self.assertLess(box('˛')[3], 0.05)                                # l'ogonek : au pied
