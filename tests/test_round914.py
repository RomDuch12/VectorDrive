"""Round 914 : crénage de la police VD Géo — table calculée sur le dessin (AV, To, LT, P., Vé…), jamais deux traits
à moins de 0,15 hauteur de capitale, rien après un chiffre ni une apostrophe ; appliquée à la mise en page avec
l'espacement crénelé ; VD Trait sans crénage."""
import math
import os
import tempfile
import unittest

import numpy as np

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r914.ini'))

from vectordrive.core import strokegeo as sg  # noqa: E402
from vectordrive.core import text as T  # noqa: E402

_PTS = {}


def points(ch):
    if ch not in _PTS:
        path, adv = sg.glyph(ch)
        out = []
        for poly in path.flatten(0.002):
            for i in range(1, len(poly)):
                (x0, y0), (x1, y1) = poly[i - 1], poly[i]
                n = max(1, int(math.dist((x0, y0), (x1, y1)) / 0.01))
                out += [(x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n) for k in range(n + 1)]
        _PTS[ch] = (np.array(out), adv)
    return _PTS[ch]


def gap(a, b, k):
    pa, adv = points(a)
    pb, _ = points(b)
    q = pb + np.array([adv + k, 0.0])
    return float(np.sqrt(((pa[:, None, :] - q[None, :, :]) ** 2).sum(-1)).min())


def width(text, font='VD Géo', kerning=True):
    x0, _y0, x1, _y1 = T.layout(text, font, 10.0, kerning=kerning).bbox()
    return x1 - x0


class Table(unittest.TestCase):

    def test_pairs(self):
        for p in ('AV', 'VA', 'AT', 'To', 'Ty', 'Yo', 'LT', 'LV', 'P.', 'F,', 'r.', 'Vé', 'Tô', 'L’'):
            self.assertLess(sg.kerning(*p), -0.02, p)
        for p in ('HH', 'nn', 'oo', 'OO', 'rn', '7.', '1.', '’a', '’é', "'A"):
            self.assertEqual(sg.kerning(*p), 0.0, p)

    def test_accented_left_like_its_base(self):
        self.assertEqual(sg.kerning('À', 'V'), sg.kerning('A', 'V'))      # ÀV comme AV
        self.assertEqual(sg.kerning('Ÿ', 'o'), sg.kerning('Y', 'o'))      # Ÿo comme Yo
        self.assertEqual(sg.kerning('Ą', 'V'), 0.0)                       # Ą (ogonek au pied) : pas de table

    def test_bounds_and_strokes_never_too_close(self):
        self.assertGreater(len(sg._KERN), 300)
        for p, k in sg._KERN.items():
            with self.subTest(p=p):
                self.assertEqual(len(p), 2)
                self.assertGreaterEqual(k, -0.15)
                self.assertLessEqual(k, 0.06)
                self.assertNotEqual(k, 0.0)
                self.assertFalse(p[0].isdigit() or p[0] in '\'"’”.,')
                self.assertGreaterEqual(gap(p[0], p[1], k), 0.15 - 5e-3, 'traits trop proches')


class Layout(unittest.TestCase):

    def test_kerning_in_layout(self):
        self.assertLess(width('AVATAR'), width('AVATAR', kerning=False) - 2.0)  # 10 mm : plus de 2 mm gagnés
        self.assertAlmostEqual(width('HOH'), width('HOH', kerning=False), places=9)
        self.assertAlmostEqual(width('7.5'), width('7.5', kerning=False), places=9)
        k = sg.kerning('T', 'o') * 10.0
        self.assertAlmostEqual(width('To'), width('To', kerning=False) + k, places=6)

    def test_vd_trait_unchanged(self):
        self.assertLess(width('AVATAR'), width('AVATAR', kerning=False))
        self.assertAlmostEqual(width('AVATAR', 'VD Trait'), width('AVATAR', 'VD Trait', kerning=False), places=9)

    def test_layout_bbox_matches(self):
        for text in ('AVATAR Tôle', 'L’atelier, P.T.T.'):
            a = T.layout(text, 'VD Géo', 5.0).bbox()
            b = T.layout_bbox(text, 'VD Géo', 5.0)
            self.assertTrue(all(abs(x - y) < 1e-9 for x, y in zip(a, b)), (text, a, b))
            c = T.layout_bbox(text, 'VD Géo', 5.0, kerning=False)
            self.assertLess(b[2] - b[0], c[2] - c[0])


if __name__ == '__main__':
    unittest.main()
