"""Round 702 : police monotrait intégrée « VD Trait » (d'après CADCraft
Stroke) — toujours là, traits ouverts gravés en un passage, lettres
accentuées composées (é è ê ë à ç ñ œ…), en tête de la liste des polices."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import fonts
from vectordrive.core import strokefont as SF
from vectordrive.core import text as T


class TestGlyphs(unittest.TestCase):
    def test_base_glyphs(self):
        p, adv = SF.glyph('A')
        self.assertAlmostEqual(adv, (4.0 + 1.6) / 6)
        self.assertEqual(len(p.contours), 2)                                       # deux traits
        self.assertAlmostEqual(p.bbox()[3], 1.0)                                   # hauteur des capitales 1
        o, _a = SF.glyph('O')
        self.assertTrue(o.contours[0].closed)                                      # boucle refermée
        self.assertFalse(SF.glyph('L')[0].contours[0].closed)
        self.assertEqual(SF.glyph(' '), (SF.glyph(' ')[0], (2.4 + 1.6) / 6))
        self.assertFalse(SF.glyph(' ')[0].contours)

    def test_accents_composed(self):
        e, _a = SF.glyph('e')
        ea, adv = SF.glyph('é')
        self.assertEqual(adv, SF.glyph('e')[1])
        self.assertEqual(len(ea.contours), len(e.contours) + 1)
        self.assertTrue(0.8 < ea.bbox()[3] < 1.1)                                 # au-dessus des minuscules
        cap = SF.glyph('É')[0].bbox()[3]
        self.assertTrue(1.05 < cap <= SF.ASCENT)                                   # serré au-dessus des capitales
        self.assertLess(SF.glyph('ç')[0].bbox()[1], 0)                             # cédille sous la ligne
        self.assertEqual(len(SF.glyph('î')[0].contours), 2)                        # i sans point + circonflexe
        self.assertEqual(len(SF.glyph('ï')[0].contours), 3)
        for ch in 'àâäçéèêëîïôöùûüÿœæÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŸŒÆñÑß€«»’²¿¡':
            self.assertTrue(SF.has(ch), ch)
            self.assertTrue(SF.glyph(ch)[0].contours, ch)

    def test_missing_and_extras(self):
        p, adv = SF.glyph('漢')
        self.assertFalse(p.contours)
        self.assertAlmostEqual(adv, (4.0 + 1.6) / 6)                               # la place d'une lettre
        self.assertLess(SF.glyph('²')[0].bbox()[3] - SF.glyph('²')[0].bbox()[1], 0.6)
        self.assertGreater(SF.glyph('²')[0].bbox()[1], 0.5)                        # exposant
        self.assertLess(SF.glyph('¿')[0].bbox()[1], 0)                             # point d'interrogation renversé
        chars = SF.characters()
        self.assertGreater(len(chars), 250)
        self.assertIn('ŝ', chars)
        self.assertNotIn('\t', chars)


class TestFonts(unittest.TestCase):
    def test_found_by_name(self):
        for name in ('VD Trait', 'vd trait', 'VDTrait'):
            self.assertTrue(fonts.is_available(name))
            self.assertEqual(fonts.find_font(name), (SF.PATH, 0))
        self.assertEqual(fonts.metrics(SF.PATH, 0)['cap'], 1.0)
        self.assertIn('é', fonts.characters('VD Trait'))
        self.assertEqual(fonts.glyph(SF.PATH, 0, 'é')[1], SF.glyph('é')[1])

    def test_layout(self):
        p = T.layout('Été', 'VD Trait', 10.0)
        bb = p.bbox()
        self.assertAlmostEqual(bb[1], 0.0)
        self.assertTrue(10.5 < bb[3] < 13.0)                                       # capitale de 10 mm, accent dessus
        self.assertTrue(all(not c.closed for c in p.contours if len(c.segments) == 1))
        w = T.advance('Été', 'VD Trait', 10.0)
        self.assertAlmostEqual(w, (4.0 + 3.0 + 4.0 + 3 * 1.6) / 6 * 10, places=6)  # É t é, sans crénage
        self.assertEqual(T.layout('Été', 'VD Trait', 10.0, kerning=False).bbox(), bb)


class TestFontBox(unittest.TestCase):
    def test_first_in_list(self):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        from vectordrive.ui.dialogs import FontBox
        box = FontBox()
        self.assertEqual(box.itemText(0), 'VD Trait')
        self.assertTrue(box.itemData(0, Qt.ItemDataRole.ToolTipRole))
        box.setCurrentFont('VD Trait')
        self.assertEqual(box.currentIndex(), 0)
        self.assertEqual(box.currentFont().family(), 'VD Trait')


if __name__ == '__main__':
    unittest.main()
