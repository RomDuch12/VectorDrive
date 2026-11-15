"""Round 14 : corrections tirées du corpus réel (vieux symboles, cycles
SimPl, DXF non conformes)."""
import math
import pathlib
import tempfile
import unittest

from vectordrive.io import registry, smb
from tests.corpus import corpus

SYM = corpus('symboles')


class TestOldSymbols(unittest.TestCase):
    """Conteneurs ancien format : un entier de fin, longtemps non lu — le
    reste du dessin passait pour une « queue » recopiée telle quelle."""

    def check(self, name, min_contours):
        f = next(SYM.rglob(name), None) if SYM.is_dir() else None
        if f is None:
            self.skipTest(f'{name} absent')
        data = f.read_bytes()
        root, _fonts, ar = smb.parse(data)
        self.assertEqual(ar.pos, len(data))                      # tout est lu
        self.assertEqual(smb.rewrite(data), data)
        self.assertGreaterEqual(registry.open_document(f).stats()['contours'], min_contours)

    def test_pears(self):
        self.check('20011.smb', 7)                               # 1 seul contour avant

    def test_subd(self):
        self.check('subd_15_f_f.smb', 50)

    def test_star(self):
        self.check('star.smb', 1)


class TestRawDxf(unittest.TestCase):
    """DXF sans marqueurs de sous-classe : refusé par ezdxf, lu en secours."""

    def test_fallback(self):
        ents = ['LWPOLYLINE', '8', 'Gravure', '90', '3', '70', '1',
                '10', '0', '20', '0', '42', '1', '10', '10', '20', '0', '10', '10', '20', '10',
                '0', 'LINE', '8', '0', '10', '0', '20', '20', '11', '30', '21', '20',
                '0', 'CIRCLE', '8', '0', '10', '50', '20', '50', '40', '5',
                '0', 'ARC', '8', '0', '10', '0', '20', '0', '40', '10', '50', '0', '51', '90']
        lines = ['0', 'SECTION', '2', 'ENTITIES', '0'] + ents + ['0', 'ENDSEC', '0', 'EOF']
        with tempfile.TemporaryDirectory() as t:
            f = pathlib.Path(t) / 'abime.dxf'
            f.write_text('\n'.join(lines) + '\n', encoding='ascii')
            d = registry.open_document(f)
        self.assertEqual(d.stats()['contours'], 4)
        self.assertIn('Gravure', [L.name for L in d.layers])
        lengths = sorted(round(s.path.length(), 6) for L in d.layers for s in L.items)
        # quart d'arc r 10 ; segment ; cercle r 5 ; polyligne fermée à bulge 1
        # (demi-cercle sur 10 mm, côté de 10, fermeture de 10√2)
        want = sorted(round(v, 6) for v in (5 * math.pi, 30.0, 10 * math.pi, 5 * math.pi + 10 + 10 * math.sqrt(2)))
        self.assertEqual(lengths, want)
        self.assertTrue(any('secours' in r for r in d.report))


if __name__ == '__main__':
    unittest.main()
