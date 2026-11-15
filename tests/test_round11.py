"""Round 11 : création de symboles TypeEdit (.smb)."""
import os
import pathlib
import struct
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import codes, geom
from vectordrive.core import text as TX
from vectordrive.core.document import Document, Group, Shape, Text
from vectordrive.core.geom import Affine
from vectordrive.io import registry, smb
from tests.corpus import corpus

SYM = corpus('symboles')


def leaves(items):
    for it in items:
        if isinstance(it, Group):
            yield from leaves(it.children)
        else:
            yield it


def total_length(items):
    return sum((getattr(x, 'path', None) or x.outline).length() for x in leaves(items)
               if getattr(x, 'path', None) or getattr(x, 'outline', None))


def classes(o, seen=None):
    seen = seen if seen is not None else set()
    if o is None or id(o) in seen:
        return []
    seen.add(id(o))
    out = [o.cls.name]
    for c in o.children:
        out += classes(c, seen)
    return out


class TestBuild(unittest.TestCase):
    def items(self):
        t = Text(text='BFM', font='Arial', size=5, matrix=Affine.translation(15, 12))
        t.outline = TX.outline_for(t)
        return [Shape(path=geom.Path([geom.rect(10, 10, 40, 20, 3)])),
                Group(children=[Shape(path=geom.Path([geom.circle((30, 20), 5)]))]), t]

    def test_header_and_round_trip(self):
        items = self.items()
        data = smb.build(items)
        magic, start, ver = struct.unpack_from('<3I', data, 0)
        self.assertEqual((magic, start, ver), (smb.MAGIC, 11076, 1100))
        bih = struct.unpack_from('<IiiHHIIiiII', data, 12)
        self.assertEqual(bih[:5], (40, 100, 100, 1, 8))
        pal = data[52:52 + 1024]
        self.assertEqual(pal[:4], b'\0\0\0\0')                     # 0 = noir
        self.assertEqual(pal[1020:1024], b'\xff\xff\xff\0')        # 255 = blanc
        pix = data[12 + 40 + 1024:11076]
        self.assertGreater(pix.count(0), 100)                      # le dessin est tracé
        root, fonts, ar = smb.parse(data)
        self.assertEqual(fonts, [])
        self.assertEqual(ar.pos, len(data))
        self.assertEqual(smb.rewrite(data), data)
        with tempfile.TemporaryDirectory() as t:
            f = pathlib.Path(t) / 's.smb'
            f.write_bytes(data)
            d = registry.open_document(f)
        bb = d.bbox()
        self.assertAlmostEqual((bb[0] + bb[2]) / 2, 0, places=9)  # « sans coordonnées »
        self.assertAlmostEqual((bb[1] + bb[3]) / 2, 0, places=9)
        self.assertAlmostEqual(total_length(d.layers[0].items), total_length(items), places=6)

    def test_export_document(self):
        d = Document()
        d.add(codes.build(codes.BarcodeSpec('datamatrix', 'ABC', 0.5)))
        with tempfile.TemporaryDirectory() as t:
            f = pathlib.Path(t) / 'code.smb'
            registry.save_document(d, f)
            back = registry.open_document(f)
        self.assertEqual(back.stats()['contours'], d.stats()['contours'])

    @unittest.skipUnless(SYM.is_dir(), 'bibliothèque absente')
    def test_resave_library_symbol(self):
        src = corpus('smb_cote_laterale')
        if not src.exists():
            self.skipTest('symbole absent')
        d = registry.open_document(src)
        before = total_length(d.layers[0].items)
        data = smb.build(d.layers[0].items)
        root, _fonts, _ar = smb.parse(data)
        names = classes(root)
        self.assertNotIn('CCotationLaterale', names)               # cotes écrites comme dessin
        self.assertNotIn('CParagraphe', names)                     # textes en courbes
        self.assertTrue(any('vnd_obj' in x.extra for x in leaves(d.layers[0].items)))  # source intacte
        with tempfile.TemporaryDirectory() as t:
            f = pathlib.Path(t) / 'copie.smb'
            f.write_bytes(data)
            again = registry.open_document(f)
        self.assertAlmostEqual(total_length(again.layers[0].items), before, delta=1e-6 * before)


if __name__ == '__main__':
    unittest.main()
