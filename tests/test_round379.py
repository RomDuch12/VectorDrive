"""Round 379 : code-barres en négatif (TypeEdit : Inverser couleur) — le
fond autour des modules se grave."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import strategies as S
from vectordrive.core import codes, pathops


class TestNegative(unittest.TestCase):
    def test_datamatrix(self):
        spec = codes.BarcodeSpec(kind='datamatrix', text='VD379', module=0.5)
        pos, _ = codes.paths(spec)
        spec.invert = True
        neg, _ = codes.paths(spec)
        b = neg.bbox()
        w = pos.bbox()[2] - pos.bbox()[0]
        self.assertAlmostEqual(b[0], -0.5, 6)                         # marge d'un module
        self.assertAlmostEqual(b[2] - b[0], w + 1.0, 6)
        a_pos = S.region([pathops.normalize(pos)], 0.001).area
        a_neg = S.region([neg], 0.001).area
        self.assertAlmostEqual(a_pos + a_neg, (w + 1.0) * (pos.bbox()[3] - pos.bbox()[1] + 1.0), 4)   # complémentaires

    def test_linear(self):
        spec = codes.BarcodeSpec(kind='code128', text='ABC', module=0.3, height=8, invert=True, quiet=2)
        bars, txt = codes.paths(spec)
        b = bars.bbox()
        self.assertAlmostEqual(b[1], -0.6, 6)
        self.assertAlmostEqual(b[3], 8.6, 6)
        g = codes.build(spec)
        self.assertTrue(g.extra['barcode']['invert'])


if __name__ == '__main__':
    unittest.main()
