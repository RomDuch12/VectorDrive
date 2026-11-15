"""Round 47 : réparation des SVG d'Illustrator mal formés."""
import unittest

from vectordrive.io import svg

ILLUSTRATOR = b'''<?xml version="1.0" encoding="utf-8"?>
<svg version="1.1" xmlns:x="&ns_extend;" xmlns:i="&ns_ai;" xmlns="http://www.w3.org/2000/svg"
     viewBox="0 0 20 20" width="20mm" height="20mm" width ="44" height = "44">
<circle fill="#6060F4" cx="10" cy="10" r="10"/>
<rect x="1" y="1" width="5" height="5" fill="none" stroke="#000" "/>
<rect x="2" y="2" width="3" height="3>
</rect>
</svg>'''


class TestSvgRepair(unittest.TestCase):
    def test_repaired(self):
        d = svg.read_data(ILLUSTRATOR)
        self.assertEqual(d.stats()['contours'], 3)
        self.assertTrue(d.report and d.report[0].startswith('SVG réparé'))
        self.assertIn('ns_extend', d.report[0])
        bb = d.bbox()
        self.assertAlmostEqual(bb[2] - bb[0], 20, places=6)          # première largeur gardée : 20 mm

    def test_valid_svg_untouched(self):
        ok = b'<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm" viewBox="0 0 10 10">' \
             b'<rect width="10" height="10"/></svg>'
        d = svg.read_data(ok)
        self.assertEqual(d.report, [])

    def test_hopeless(self):
        with self.assertRaises(svg.SvgError):
            svg.read_data(b'<svg><g></svg>')


if __name__ == '__main__':
    unittest.main()
