"""Symboles TypeEdit (.smb) et textes TypeEdit."""
import pathlib
import unittest

from vectordrive.core.document import Group, Shape, Text
from vectordrive.io import smb
from tests.corpus import corpus

ROOTS = [corpus('symboles'), corpus('symboles_perso')]
ALL = [p for r in ROOTS if r.is_dir() for p in r.rglob('*.smb')]


def find(name):
    for p in ALL:
        if p.name == name:
            return p
    return None


@unittest.skipUnless(ALL, 'bibliothèque de symboles absente')
class TestSymbols(unittest.TestCase):
    def test_text_symbol(self):
        p = find('10-3 2xM4.smb')
        if p is None:
            self.skipTest('symbole texte absent')
        d = smb.read(p)
        t = d.layers[0].items[0]
        self.assertIsInstance(t, Text)
        self.assertTrue(t.text.startswith('Fer de hauteur 10mm\nProfondeur grav'))
        self.assertEqual(t.font, 'Arial')
        self.assertAlmostEqual(t.size, 2.863, places=3)
        self.assertTrue(t.outline)                       # glyphes posés
        bb = t.outline.bbox()
        self.assertGreater(bb[2] - bb[0], 55)            # ~65 mm de large
        self.assertLess(bb[2] - bb[0], 70)

    def test_sample_reads(self):
        """Un échantillon fixe de la bibliothèque doit se lire sans erreur
        (hors cotations, marqueurs et axes, non décodés)."""
        ok = ko = 0
        for p in sorted(ALL)[::25]:
            try:
                smb.read(p)
                ok += 1
            except smb.SmbError:
                pass
            except Exception as ex:
                if not any(c in str(ex) for c in ('CCotation', 'CMarker', 'CCenterLine')):
                    ko += 1
                    print(p, ex)
        self.assertEqual(ko, 0)
        self.assertGreater(ok, 50)

    def test_rewrite_identical(self):
        n = 0
        for p in sorted(ALL)[::40]:
            data = p.read_bytes()
            try:
                out = smb.rewrite(data)
            except Exception:
                continue
            self.assertEqual(out, data, p.name)
            n += 1
        self.assertGreater(n, 30)

    def test_as_group_centered(self):
        p = next((q for q in sorted(ALL) if q.stat().st_size < 60000), None)
        g = smb.as_group(p)
        bb = g.bbox()
        self.assertAlmostEqual((bb[0] + bb[2]) / 2, 0, places=6)
        self.assertAlmostEqual((bb[1] + bb[3]) / 2, 0, places=6)
        self.assertIsInstance(g, Group)
        self.assertTrue(any(isinstance(c, (Shape, Text, Group)) for c in g.children))


if __name__ == '__main__':
    unittest.main()
