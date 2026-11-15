"""Round 912 : police VD Géo enrichie — alphabet grec (capitales communes avec le latin, accents monotoniques
composés, tonos des capitales à gauche), flèches, signes techniques, exposants, indices, fractions, virgule et point
souscrits (roumain), équivalents canoniques (Ω de l'ohm, Å de l'angström) ; tout tient dans la boîte des
caractères, d'un trait continu, sans droite repassée."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r912.ini'))

from vectordrive.core import strokegeo as sg  # noqa: E402
from vectordrive.core.geom import Line  # noqa: E402

GREEK = [chr(c) for c in range(0x391, 0x3AA) if c != 0x3A2] + [chr(c) for c in range(0x3B1, 0x3CA)]
TONOS = [chr(c) for c in (0x386, 0x388, 0x389, 0x38A, 0x38C, 0x38E, 0x38F, 0x390, 0x3AA, 0x3AB, 0x3AC, 0x3AD,
                          0x3AE, 0x3AF, 0x3B0, 0x3CA, 0x3CB, 0x3CC, 0x3CD, 0x3CE)]
ARROWS = '←↑→↓↔↕↖↗↘↙⇐⇒'
SIGNS = ('≤≥≠≈∞√∠⊥∥′″№℃℉✓✗'
         '⁄‐‑‒―Ω∆∑∅')
SUPSUB = '⁰⁴⁵⁶⁷⁸⁹' + ''.join(chr(0x2080 + i) for i in range(10))
FRACTIONS = '⅓⅔⅛⅜⅝⅞'
NEW = GREEK + TONOS + list(ARROWS + SIGNS + SUPSUB + FRACTIONS) + list('ȘșȚțạẹ')


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


def box(ch):
    return sg.glyph(ch)[0].bbox()


class Greek(unittest.TestCase):

    def test_alphabet(self):
        self.assertEqual(len(GREEK), 49)                                   # 24 capitales, 25 minuscules (ς)
        chars = set(sg.characters())
        for ch in GREEK:
            self.assertTrue(sg.has(ch), f'U+{ord(ch):04X}')
            self.assertIn(ch, chars, f'U+{ord(ch):04X}')
            self.assertTrue(sg.glyph(ch)[0], f'U+{ord(ch):04X}')

    def test_capitals_shared_with_latin(self):
        for gr, la in zip('ΑΒΕΗΟΧ', 'ABEHOX'):
            self.assertEqual(box(gr), box(la))
            self.assertEqual(sg.glyph(gr)[1], sg.glyph(la)[1])
        self.assertEqual(box('μ'), box('µ'))                     # μ grec, µ micro
        self.assertEqual(box('ο'), box('o'))

    def test_proportions(self):
        self.assertAlmostEqual(box('Ω')[3], 1.0, delta=0.012)          # Ω à la hauteur des capitales
        self.assertAlmostEqual(box('ω')[3], sg.XH, delta=0.012)        # ω à la hauteur d'x
        self.assertAlmostEqual(box('β')[1], sg.DSC, places=6)          # β, ρ, φ descendent
        self.assertAlmostEqual(box('ρ')[1], sg.DSC, places=6)
        self.assertLess(box('ς')[1], -0.2)                             # ς : la queue
        self.assertEqual(len(sg.glyph('Ω')[0].contours), 1)            # Ω, α, σ d'un seul trait
        self.assertEqual(len(sg.glyph('α')[0].contours), 1)
        self.assertEqual(len(sg.glyph('σ')[0].contours), 1)

    def test_monotonic_accents(self):
        chars = set(sg.characters())
        for ch in TONOS:
            self.assertTrue(sg.has(ch), f'U+{ord(ch):04X}')
            self.assertIn(ch, chars, f'U+{ord(ch):04X}')
        a, aa = sg.glyph('α'), sg.glyph('ά')                     # ά : α + accent au-dessus
        self.assertEqual(len(aa[0].contours), len(a[0].contours) + 1)
        self.assertGreater(aa[0].bbox()[3], sg.XH + 0.1)
        cap, tonos = sg.glyph('Α'), sg.glyph('Ά')                # Ά : tonos à gauche de la lettre
        mark = tonos[0].contours[-1]
        letter = [c for c in tonos[0].contours[:-1]]
        mx1 = max(p[0] for p in mark.flatten(0.002))
        lx0 = min(p[0] for c in letter for p in c.flatten(0.002))
        self.assertLess(mx1, lx0)
        self.assertLessEqual(tonos[0].bbox()[3], 1.02)                     # pas au-dessus de la capitale
        self.assertGreater(tonos[1], cap[1])                               # la place du tonos


class Signs(unittest.TestCase):

    def test_present(self):
        chars = set(sg.characters())
        for ch in ARROWS + SIGNS + SUPSUB + FRACTIONS:
            self.assertTrue(sg.has(ch), f'U+{ord(ch):04X}')
            self.assertIn(ch, chars, f'U+{ord(ch):04X}')

    def test_shapes(self):
        x0, y0, x1, y1 = box('→')                                     # →
        self.assertGreater(x1 - x0, 2 * (y1 - y0))
        x0, y0, x1, y1 = box('↑')                                     # ↑
        self.assertGreater(y1 - y0, 2 * (x1 - x0))
        self.assertEqual(len(sg.glyph('∞')[0].contours), 1)            # ∞ d'un trait
        self.assertAlmostEqual(box('√')[3], sg.ASC, places=6)          # √
        self.assertGreaterEqual(box('⁴')[1], 0.4)                      # ⁴ en exposant
        self.assertLess(box('₄')[1], -0.1)                             # ₄ en indice
        self.assertLess(box('₄')[3], 0.5)
        self.assertEqual(box('Ω'), box('Ω'))                      # ohm = oméga
        self.assertEqual(box('∑'), box('Σ'))

    def test_canonical_equivalents(self):
        for ch, same in (('Ω', 'Ω'), ('Å', 'Å'), (';', ';'), ('·', '·')):
            self.assertTrue(sg.has(ch), f'U+{ord(ch):04X}')
            self.assertEqual(box(ch), box(same))
        self.assertIn('Å', sg.characters())


class BelowMarks(unittest.TestCase):

    def test_romanian_comma(self):
        for comma, cedilla in (('Ș', 'Ş'), ('ș', 'ş'), ('Ț', 'Ţ'), ('ț', 'ţ')):
            self.assertTrue(sg.has(comma), f'U+{ord(comma):04X}')
            self.assertLess(box(comma)[1], -0.15)                          # la virgule descend
            self.assertNotEqual(box(comma), box(cedilla))                  # ce n'est pas la cédille

    def test_dot_below(self):
        self.assertTrue(sg.has('ạ'))                                   # ạ
        self.assertEqual(len(sg.glyph('ạ')[0].contours), len(sg.glyph('a')[0].contours) + 1)
        self.assertLess(box('ạ')[1], -0.1)


class Drawing(unittest.TestCase):

    def test_new_glyphs_are_clean(self):
        m = sg.metrics()
        self.assertEqual(sg._audit(), [])
        for ch in NEW:
            path, adv = sg.glyph(ch)
            with self.subTest(ch=f'U+{ord(ch):04X}'):
                self.assertTrue(path)
                x0, y0, x1, y1 = path.bbox()
                self.assertGreaterEqual(x0, -0.1)
                self.assertLessEqual(x1, adv + 1e-9)
                self.assertGreaterEqual(y0, -m['descent'] - 1e-9)
                self.assertLessEqual(y1, m['ascent'] + 1e-9)
                for c in path.contours:
                    for a, b in zip(c.segments, c.segments[1:]):
                        self.assertLessEqual(math.dist(a.end, b.start), 1e-9, 'trait discontinu')
                segs = [s for c in path.contours for s in c.segments if isinstance(s, Line)]
                worst = max((overlap(a, b) for i, a in enumerate(segs) for b in segs[i + 1:]), default=0.0)
                self.assertLess(worst, 1e-6, 'droite repassée')

    def test_charset_stays_in_the_box(self):
        m = sg.metrics()
        chars = sg.characters()
        self.assertEqual(list(chars), sorted(set(chars)))
        self.assertGreater(len(chars), 600)
        for ch in chars:
            if ch == ' ':
                continue
            x0, y0, x1, y1 = box(ch)
            self.assertGreaterEqual(y0, -m['descent'] - 1e-9, f'U+{ord(ch):04X}')
            self.assertLessEqual(y1, m['ascent'] + 1e-9, f'U+{ord(ch):04X}')
        self.assertTrue(sg.has('Ấ'))                                   # Ấ se dessine…
        self.assertNotIn('Ấ', chars)                                   # …mais sort de la boîte : pas proposé


class InTheApp(unittest.TestCase):

    def test_text_layout(self):
        from vectordrive.core import fonts
        from vectordrive.core import text as T
        self.assertIn('π', fonts.characters('VD Géo'))
        self.assertIn('≤', fonts.characters('VD Géo'))
        p = T.layout('π ≈ 3,14 — 4,7 kΩ → Δp', 'VD Géo', 10.0)
        x0, y0, x1, y1 = p.bbox()
        self.assertGreater(x1 - x0, 80.0)
        n = sum(len(sg.glyph(ch)[0].contours) for ch in 'π≈3,14—4,7kΩ→Δp')
        self.assertEqual(len(p.contours), n)                               # aucun caractère manquant


if __name__ == '__main__':
    unittest.main()
