"""Round 509 : BAT plus rapide — glyphes des polices gardés pour la séance (les cotes de milliers de
gravures relisaient chaque chiffre dans la police), flux du PDF compressé au niveau 6."""
import os
import tempfile
import unittest
import zlib

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import fonts, geom, text
from vectordrive.core.document import Document, Shape
from vectordrive.io import proof as P


class TestGlyphCache(unittest.TestCase):
    def test_cached_and_unchanged(self):
        ff = fonts.find_font(P.FONT) or fonts.find_font('Arial')
        self.assertTrue(ff)
        a = fonts.glyph(ff[0], ff[1], '7')
        b = fonts.glyph(ff[0], ff[1], '7')
        self.assertIs(a, b)                                    # même objet : lu une fois
        lbl = text.layout('12,5', P.FONT, 2.2, align='center')
        moved = lbl.transformed(geom.Affine.translation(10, 0))
        self.assertEqual(fonts.glyph(ff[0], ff[1], '7'), a)    # transformer ne touche pas au glyphe gardé
        self.assertNotEqual(moved.bbox(), lbl.bbox())

    def test_bat_written(self):
        doc = Document()
        for i in range(30):
            doc.add(Shape(path=geom.Path([geom.rect(12 * (i % 6), 8 * (i // 6), 10, 6)])))
        out = os.path.join(tempfile.mkdtemp(), 'bat.pdf')
        P.write(doc, out, P.ProofInfo(reference='essai'))
        data = open(out, 'rb').read()
        self.assertTrue(data.startswith(b'%PDF'))
        start = data.index(b'stream') + len(b'stream\r\n') if b'stream\r\n' in data else data.index(b'stream') + 7
        self.assertIn(b' m', zlib.decompressobj().decompress(data[start:start + 200000]))


if __name__ == '__main__':
    unittest.main()
