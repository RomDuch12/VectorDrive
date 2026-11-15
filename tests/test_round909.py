"""Round 909 : police monotrait intégrée « VD Géo », linéale géométrique (dessin original : cercles, arcs d'ellipse,
droites) gravée en un passage ; toujours là, à côté de « VD Trait » dans les listes de polices. ASCII, Latin-1,
Latin étendu A et les signes courants ; arcs exacts ; aucun trait repassé."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r909.ini'))

from vectordrive.core import strokegeo as sg  # noqa: E402
from vectordrive.core.geom import Conic, Cubic, Line  # noqa: E402

SPACES = {' ', '\u00a0', '\u2009', '\u202f'}


def overlap(a, b, tol=1e-7) -> float:
    """Longueur commune de deux droites colinéaires (0 sinon)."""
    (x0, y0), (x1, y1) = a.start, a.end
    (u0, v0), (u1, v1) = b.start, b.end
    dx, dy = x1 - x0, y1 - y0
    n = math.hypot(dx, dy)
    if n < 1e-9 or math.hypot(u1 - u0, v1 - v0) < 1e-9:
        return 0.0
    if any(abs((px - x0) * dy - (py - y0) * dx) / n > tol for px, py in ((u0, v0), (u1, v1))):
        return 0.0
    s0 = ((u0 - x0) * dx + (v0 - y0) * dy) / n / n
    s1 = ((u1 - x0) * dx + (v1 - y0) * dy) / n / n
    return max(0.0, min(1.0, max(s0, s1)) - max(0.0, min(s0, s1))) * n


class Font(unittest.TestCase):

    def test_api(self):
        self.assertEqual(sg.NAME, 'VD Géo')
        self.assertTrue(sg.is_stroke(sg.PATH))
        self.assertFalse(sg.is_stroke('<vectordrive:trait>'))
        self.assertFalse(sg.is_stroke('C:/Windows/Fonts/arial.ttf'))
        m = sg.metrics()
        self.assertEqual((m['upem'], m['cap']), (1.0, 1.0))
        self.assertGreater(m['ascent'], 1.0)
        self.assertGreater(m['descent'], 0.3)

    def test_charset(self):
        chars = sg.characters()
        self.assertEqual(list(chars), sorted(set(chars)))
        want = [chr(c) for c in range(0x20, 0x7F)] + [chr(c) for c in range(0xA0, 0x180)]
        want += list('€‘’‚“”„†‡•…‰‹›−–—™⌀\u2009\u202f')
        for ch in want:
            self.assertTrue(sg.has(ch), f'U+{ord(ch):04X}')
            if ch not in SPACES:
                self.assertIn(ch, chars, f'U+{ord(ch):04X}')

    def test_glyphs(self):
        m = sg.metrics()
        for ch in sg.characters():
            path, adv = sg.glyph(ch)
            with self.subTest(ch=f'U+{ord(ch):04X}'):
                self.assertGreater(adv, 0)
                if ch == ' ':
                    self.assertFalse(path)
                    continue
                self.assertTrue(path, 'glyphe vide')
                x0, y0, x1, y1 = path.bbox()
                self.assertGreaterEqual(x0, -0.1)
                self.assertLessEqual(x1, adv + 1e-9)
                self.assertGreaterEqual(y0, -m['descent'] - 1e-9)
                self.assertLessEqual(y1, m['ascent'] + 1e-9)
                for c in path.contours:
                    for s in c.segments:
                        self.assertIsInstance(s, (Line, Conic, Cubic))
                    for a, b in zip(c.segments, c.segments[1:]):
                        self.assertLessEqual(math.dist(a.end, b.start), 1e-9, 'trait discontinu')

    def test_exact_arcs(self):
        self.assertEqual(sg._audit(), [])
        o = sg.glyph('O')[0]
        self.assertEqual(len(o.contours), 1)
        self.assertIsNotNone(o.contours[0].segments[0].circle_params())   # vrai cercle
        x0, y0, x1, y1 = o.bbox()
        self.assertAlmostEqual(x1 - x0, y1 - y0, places=9)

    def test_nothing_is_retraced(self):
        """Aucune droite repassée (un double passage marque au laser) : n, m, r, u en fût + arche."""
        for ch in sg.characters():
            segs = [s for c in sg.glyph(ch)[0].contours for s in c.segments if isinstance(s, Line)]
            worst = max((overlap(a, b) for i, a in enumerate(segs) for b in segs[i + 1:]), default=0.0)
            self.assertLess(worst, 1e-6, ch)
        self.assertEqual(len(sg.glyph('n')[0].contours), 2)

    def test_few_pen_lifts(self):
        for ch in 'abdegopqBCDGJLMNOSUVWZcsvwz0123456789':
            self.assertEqual(len(sg.glyph(ch)[0].contours), 1, ch)

    def test_proportions(self):
        def top(ch):
            return sg.glyph(ch)[0].bbox()[3]
        self.assertAlmostEqual(top('H'), 1.0, places=6)
        self.assertAlmostEqual(top('x'), 0.70, places=6)
        self.assertAlmostEqual(top('l'), 1.06, places=6)
        self.assertAlmostEqual(sg.glyph('p')[0].bbox()[1], -0.30, places=6)
        self.assertGreater(top('É'), top('E') + 0.1)
        self.assertEqual(len({sg.glyph(d)[1] for d in '0123456789'}), 1)   # chiffres tabulaires

    def test_composition(self):
        e, ea = sg.glyph('e'), sg.glyph('é')
        self.assertEqual(len(ea[0].contours), len(e[0].contours) + 1)
        self.assertAlmostEqual(ea[1], e[1])
        self.assertEqual(len(sg.glyph('ï')[0].contours), 3)                 # i sans point + tréma


class InTheApp(unittest.TestCase):

    def test_found_like_an_installed_font(self):
        from vectordrive.core import fonts
        for name in ('VD Géo', 'vd géo', 'VDGéo'):
            self.assertTrue(fonts.is_available(name), name)
            self.assertEqual(fonts.find_font(name), (sg.PATH, 0))
        self.assertIn('ŵ', fonts.characters('VD Géo'))
        self.assertEqual(fonts.metrics(sg.PATH)['cap'], 1.0)
        self.assertEqual(fonts.find_font('VD Trait')[0], '<vectordrive:trait>')   # l'autre reste là

    def test_text_layout(self):
        from vectordrive.core import text as T
        p = T.layout('Été 909', 'VD Géo', 10.0)
        x0, y0, x1, y1 = p.bbox()
        self.assertAlmostEqual(T.layout('H', 'VD Géo', 10.0).bbox()[3], 10.0, places=6)  # hauteur des capitales
        self.assertGreater(y1, 10.0)                                             # l'accent au-dessus
        self.assertLess(T.layout('AV', 'VD Géo', 10.0).bbox()[2], T.layout('AV', 'VD Géo', 10.0, kerning=False).bbox()[2])
        self.assertTrue(all(not c.closed or len(c.segments) > 1 for c in p.contours))

    def test_in_the_font_list(self):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        from vectordrive.ui.dialogs import FontBox
        box = FontBox()
        self.assertEqual((box.itemText(0), box.itemText(1)), ('VD Trait', 'VD Géo'))
        self.assertIn('géométrique', box.itemData(1, Qt.ItemDataRole.ToolTipRole))
        box.setCurrentFont('VD Géo')
        self.assertEqual(box.currentIndex(), 1)
        self.assertEqual(box.currentFont().family(), 'VD Géo')


if __name__ == '__main__':
    unittest.main()
