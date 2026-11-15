"""Round 13 : braille français, photo tramée."""
import math
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import numpy as np

from vectordrive.core import braille as BR
from vectordrive.core import halftone as HT


class TestBraille(unittest.TestCase):
    def test_transcriptions(self):
        cases = {
            'bonjour': '⠃⠕⠝⠚⠕⠥⠗',
            'Paris': '⠨⠏⠁⠗⠊⠎',
            'SORTIE': '⠨⠨⠎⠕⠗⠞⠊⠑',               # mot en capitales : signe double
            'Salle 12': '⠨⠎⠁⠇⠇⠑ ⠠⠡⠣',          # signe numérique + notation Antoine
            '3,5 kg': '⠠⠩⠂⠱ ⠅⠛',               # virgule décimale
            '1.000': '⠠⠡⠄⠼⠼⠼',                  # séparateur de milliers
            'Élève': '⠨⠿⠇⠮⠧⠑',
            'ça': '⠯⠁',
            '⠃⠋⠍': '⠃⠋⠍',                        # braille Unicode recopié
        }
        for text, want in cases.items():
            with self.subTest(text=text):
                self.assertEqual(BR.unicode_braille(text), want)

    def test_unknown_character(self):
        with self.assertRaises(BR.BrailleError):
            BR.cells('#')

    def test_geometry(self):
        spec = BR.BrailleSpec('ab\nc', dot=1.5, dot_pitch=2.5, cell_pitch=6, line_pitch=10)
        self.assertEqual(BR.dots(spec), [(0, 0), (6, 0), (6, -2.5), (0, -10), (2.5, -10)])
        g = BR.build(spec, tool=2)
        self.assertEqual(len(g.children[0].path.contours), 5)
        self.assertAlmostEqual(g.children[0].path.contours[0].length(), math.pi * 1.5, places=9)
        self.assertEqual(BR.BrailleSpec.from_dict(g.extra['braille']), spec)


class TestHalftone(unittest.TestCase):
    def setUp(self):
        self.img = np.tile(np.linspace(1, 0, 400), (200, 1))          # dégradé blanc → noir

    def test_dots_area_follows_density(self):
        spec = HT.HalftoneSpec(width=40, pitch=1.0, style='dots', min_size=0)
        p = HT.paths(self.img, spec)
        k = HT.density(self.img, spec)
        circles = sum(c.signed_area() for c in p.contours)            # aire de chaque point
        self.assertAlmostEqual(circles / (k.sum() * 1.0), 1.0, delta=2e-3)

    def test_lines_coverage(self):
        from vectordrive.core import pathops
        spec = HT.HalftoneSpec(width=40, pitch=1.0, style='lines')
        p = HT.paths(self.img, spec)
        k = HT.density(self.img, spec)
        self.assertAlmostEqual(pathops.area(p) / k.size, k.mean(), delta=0.01)

    def test_options(self):
        white = np.ones((50, 50))
        self.assertEqual(len(HT.paths(white, HT.HalftoneSpec(width=10, pitch=1)).contours), 0)
        inv = HT.paths(white, HT.HalftoneSpec(width=10, pitch=1, invert=True))
        self.assertEqual(len(inv.contours), 100)
        light = HT.density(self.img, HT.HalftoneSpec(width=40, pitch=1, gamma=2)).mean()
        self.assertLess(light, HT.density(self.img, HT.HalftoneSpec(width=40, pitch=1)).mean())

    def test_load_image(self):
        from PySide6.QtGui import QColor, QImage
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        from vectordrive.ui.dialogs import load_gray
        img = QImage(30, 20, QImage.Format.Format_ARGB32)
        img.fill(QColor(0, 0, 0, 0))                                   # transparent = blanc
        for x in range(10):
            for y in range(20):
                img.setPixelColor(x, y, QColor('black'))
        with tempfile.TemporaryDirectory() as t:
            f = str(pathlib.Path(t) / 'i.png')
            img.save(f)
            g = load_gray(f)
        self.assertEqual(g.shape, (20, 30))
        self.assertAlmostEqual(g[:, :10].mean(), 0.0)
        self.assertAlmostEqual(g[:, 10:].mean(), 1.0)


if __name__ == '__main__':
    unittest.main()
