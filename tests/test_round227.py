"""Round 227 : les textes des SVG deviennent des textes vivants (position,
corps, police, ancrage, lignes des <tspan>) au lieu d'une remarque."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="60mm" viewBox="0 0 100 60">
  <rect x="1" y="1" width="98" height="58" fill="none" stroke="black"/>
  <text x="10" y="20" font-size="10" font-family="Arial" id="t1">Bonjour</text>
  <text x="50" y="40" style="font-size:5px;font-family:'Police Inconnue', sans-serif;text-anchor:middle">Centre</text>
  <g transform="translate(0,10)">
    <text x="10" y="40" font-size="4" font-family="Arial"><tspan x="10" y="40">Ligne 1</tspan><tspan x="10" y="46">Ligne 2</tspan></text>
  </g>
  <text x="5" y="55" font-size="3" font-family="Arial">   </text>
</svg>'''


class TestSvgTexts(unittest.TestCase):
    def test_texts_become_live(self):
        from vectordrive.core import fonts
        from vectordrive.core.document import Text
        from vectordrive.io import registry
        p = pathlib.Path(tempfile.mkdtemp()) / 'textes.svg'
        p.write_text(SVG, encoding='utf-8')
        d = registry.open_document(str(p))
        texts = {t.text: t for t in d.iter_leaves() if isinstance(t, Text)}
        self.assertEqual(set(texts), {'Bonjour', 'Centre', 'Ligne 1\nLigne 2'})          # le texte vide est ignoré
        b = texts['Bonjour']
        m = fonts.metrics(*fonts.find_font('Arial'))
        self.assertEqual((b.font, b.align, b.name), ('Arial', 'left', 't1'))
        self.assertAlmostEqual(b.size, 10.0 * m['cap'] / m['upem'], 3)             # corps 10 mm → hauteur des capitales
        x, y = b.matrix.apply((0.0, 0.0))
        self.assertAlmostEqual((x, y), (10.0, 40.0))                                # y SVG 20 → 60 − 20, ligne de base
        c = texts['Centre']
        self.assertEqual((c.font, c.align), ('Arial', 'center'))                    # police absente : Arial, notée
        self.assertAlmostEqual(c.matrix.apply((0.0, 0.0))[0], 50.0)
        self.assertAlmostEqual(c.size, 5.0 * m['cap'] / m['upem'], 3)
        L = texts['Ligne 1\nLigne 2']
        x, y = L.matrix.apply((0.0, 0.0))
        self.assertAlmostEqual((x, y), (10.0, 60.0 - 50.0))                          # translate(0,10) appliqué
        self.assertTrue(any('3 texte(s) SVG repris' in r for r in d.report), d.report)
        self.assertTrue(any('Police Inconnue' in r for r in d.report), d.report)
        self.assertFalse(any('non vectorisé' in r for r in d.report))
        from vectordrive.core import text as TX
        bb = TX.outline_for(b).bbox()
        self.assertAlmostEqual(bb[3], 40.0 + b.size, delta=0.3)                      # haut des capitales au-dessus de la ligne de base
        self.assertLess(bb[1], 40.0)                                                 # le « j » descend sous la ligne
        self.assertGreater(bb[2] - bb[0], 20.0)


if __name__ == '__main__':
    unittest.main()
