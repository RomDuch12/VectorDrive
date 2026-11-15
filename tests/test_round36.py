"""Round 36 : crénage OpenType (GPOS), vérifié contre HarfBuzz (Qt)."""
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import fonts as F
from vectordrive.core import text as T

SAMPLE = 'AVATAR Tour LT WAVE Yo'


class TestKerning(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def harfbuzz_width(self, ff, upem):
        from PySide6.QtGui import QFont, QFontDatabase, QFontMetricsF
        fid = QFontDatabase.addApplicationFont(ff[0])
        if fid < 0:
            self.skipTest('police non chargeable par Qt')
        f = QFont(QFontDatabase.applicationFontFamilies(fid)[0])
        f.setPixelSize(upem)
        f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        f.setKerning(True)
        return QFontMetricsF(f).horizontalAdvance(SAMPLE)

    def test_same_widths_as_harfbuzz(self):
        for name in ('Calibri', 'Segoe UI', 'Arial'):
            with self.subTest(name):
                ff = F.find_font(name)
                if not ff:
                    self.skipTest(f'{name} absente')
                m = F.metrics(*ff)
                ours = T.line_widths(SAMPLE, name, m['cap'])[0]   # corps = upem : 1 unité = 1 mm
                self.assertAlmostEqual(ours, self.harfbuzz_width(ff, m['upem']), delta=0.5)

    def test_gpos_only_pairs(self):
        ff = F.find_font('Calibri')
        if not ff:
            self.skipTest('Calibri absente')
        self.assertLess(T._kern(ff, 'A', 'V'), 0)
        self.assertEqual(T._kern(ff, 'A', 'B'), 0)
        fn = F.kerning(*ff)
        self.assertIs(fn, F.kerning(*ff))                   # en cache

    def test_no_kerning_option(self):
        a = T.line_widths('AV', 'Arial', 10)[0]
        b = T.line_widths('AV', 'Arial', 10, kerning=False)[0]
        self.assertLess(a, b)


if __name__ == '__main__':
    unittest.main()
