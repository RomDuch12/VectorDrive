"""Round 44 : alignement des textes TypeEdit lu dans les lignes ; textes
vivants (CParagraphe) écrits dans les symboles (expérimental)."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import text as TX
from vectordrive.core.document import Text
from vectordrive.core.geom import Affine
from vectordrive.io import paragraph as PG
from vectordrive.io import smb, vnd, vnd_write
from vectordrive.io.mfc import Archive
from tests.corpus import corpus


def text(txt, font='Arial', align='left', m=None, size=4.0):
    t = Text(text=txt, font=font, size=size, align=align, matrix=m or Affine())
    t.outline = TX.outline_for(t)
    return t


class TestParagraphWriter(unittest.TestCase):
    def roundtrip(self, t):
        o = PG.build(t, 0)
        self.assertIsNotNone(o)
        w = vnd_write.MfcWriter()
        w.write_object(o)
        data = bytes(w.buf)
        ar = Archive(data, 0, vnd.READERS)
        back = ar.read_object()
        self.assertEqual(ar.pos, len(data))
        return back

    def test_layout_reproduced(self):
        for t in (text('AVATAR gravé', align='center', m=Affine.translation(10, 20)),
                  text('Deux\nlignes', align='right', m=Affine.rotation(30)),
                  text('Ligne simple')):
            with self.subTest(t.text):
                back = self.roundtrip(t)
                txt, font, h, outline = vnd.layout_paragraph(back, [t.font])
                self.assertEqual(txt, t.text)
                self.assertAlmostEqual(h, t.size, places=6)
                a, b = t.outline.bbox(), outline.bbox()
                self.assertLess(max(abs(x - y) for x, y in zip(a, b)), 1e-3)

    def test_records(self):
        self.assertEqual(len(PG.PARA_TEMPLATE), 52)
        self.assertEqual(len(PG.CHAR_TEMPLATE), 204)
        self.assertEqual(len(PG.line_record('center', 0.0, 0.01)), 68)
        rec = PG.char_record(65, 2, 0.004, 0.72)
        a = vnd.char_attrs(rec)
        self.assertEqual((a['code'], a['font'], a['height'], a['ratio']), (65, 2, 0.004, 0.72))

    def test_refused_cases(self):
        t = text('Penché', m=Affine(1, 0, 0.3, 1, 0, 0))
        self.assertIsNone(PG.build(t, 0))                     # cisaillé : écrit en courbes
        self.assertIsNone(PG.build(text('   '), 0))


class TestSymbolLiveTexts(unittest.TestCase):
    def test_symbol(self):
        items = [text('Texte vivant', align='center'), text('Second', m=Affine.translation(0, -8))]
        with tempfile.TemporaryDirectory() as tmp:
            f = pathlib.Path(tmp) / 's.smb'
            smb.write(items, f, live_texts=True)
            data = f.read_bytes()
            root, fonts, _ = smb.parse(data)
            self.assertEqual(fonts, ['Arial'])
            self.assertEqual(smb.rewrite(data), data)
            back = [t for t in smb.read(f).iter_leaves() if isinstance(t, Text)]
            self.assertEqual([t.text for t in back], ['Texte vivant', 'Second'])
            self.assertEqual(back[0].align, 'center')
            g = pathlib.Path(tmp) / 'c.smb'
            smb.write(items, g)                                 # par défaut : courbes, table vide
            self.assertEqual(smb.parse(g.read_bytes())[1], [])

    def test_alignment_read_from_line_flags(self):
        f = corpus('smb_textes') if corpus('smb_textes').exists() else None
        if f is None:
            self.skipTest('symbole absent')
        t = next(t for t in smb.read(f).iter_leaves() if isinstance(t, Text) and t.text == 'Lame')
        self.assertEqual(t.align, 'center')


if __name__ == '__main__':
    unittest.main()
