"""Round 225 : les textes des DXF (TEXT, MTEXT, ATTRIB) deviennent des textes
vivants — ils étaient laissés de côté avec une simple remarque (19 des 65 DXF
de l'atelier en ont)."""
import math
import os
import pathlib
import tempfile
import unittest

import ezdxf
from ezdxf.enums import TextEntityAlignment

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')


def sample(path: pathlib.Path) -> pathlib.Path:
    doc = ezdxf.new('R2010')
    doc.styles.new('ARIAL', dxfattribs={'font': 'arial.ttf'})
    doc.styles.new('SHX', dxfattribs={'font': 'txt.shx'})
    msp = doc.modelspace()
    msp.add_text('Gauche', dxfattribs={'insert': (10, 20), 'height': 5, 'rotation': 30, 'style': 'ARIAL',
                                       'width': 1.5, 'layer': 'TEXTES'})
    t = msp.add_text('Centre', dxfattribs={'height': 3, 'style': 'SHX'})
    t.set_placement((50, 50), align=TextEntityAlignment.MIDDLE_CENTER)
    msp.add_mtext('Ligne 1\\PLigne 2', dxfattribs={'char_height': 4, 'insert': (0, 100), 'attachment_point': 7,
                                                   'rotation': 0, 'style': 'ARIAL'})
    msp.add_line((0, 0), (1, 0))
    doc.saveas(str(path))
    return path


class TestDxfTexts(unittest.TestCase):
    def test_texts_become_live(self):
        from vectordrive.core.document import Text
        from vectordrive.io import registry
        d = registry.open_document(str(sample(pathlib.Path(tempfile.mkdtemp()) / 'textes.dxf')))
        texts = {t.text: t for t in d.iter_leaves() if isinstance(t, Text)}
        self.assertEqual(set(texts), {'Gauche', 'Centre', 'Ligne 1\nLigne 2'})
        g = texts['Gauche']
        self.assertEqual((g.font, g.size, g.align), ('Arial', 5.0, 'left'))
        self.assertAlmostEqual(g.width_ratio, 1.5)
        x, y = g.matrix.apply((0.0, 0.0))
        self.assertAlmostEqual((x, y), (10.0, 20.0))                          # ligne de base à l'insertion
        ux, uy = g.matrix.apply((1.0, 0.0))
        self.assertAlmostEqual(math.degrees(math.atan2(uy - y, ux - x)), 30.0, 3)
        self.assertEqual(next(L.name for L in d.layers if g in L.items), 'TEXTES')
        c = texts['Centre']
        self.assertEqual(c.align, 'center')
        x, y = c.matrix.apply((0.0, 0.0))
        self.assertAlmostEqual(x, 50.0)
        self.assertAlmostEqual(y, 50.0 - 1.5)                                 # milieu : ligne de base sous le point
        self.assertEqual(c.font, 'Arial')                                     # police SHX : remplacée
        m = texts['Ligne 1\nLigne 2']
        self.assertEqual((m.size, m.align), (4.0, 'left'))
        x, y = m.matrix.apply((0.0, 0.0))
        self.assertAlmostEqual(x, 0.0)
        self.assertGreater(y, 100.0)                                          # bas gauche : 1re ligne au-dessus
        self.assertTrue(any('texte' in r and 'repris' in r for r in d.report), d.report)
        self.assertTrue(any('txt' in r for r in d.report), d.report)         # police SHX signalée
        self.assertFalse(any('non vectorisé' in r for r in d.report))
        from vectordrive.core import text as TX
        bb = TX.outline_for(m).bbox()
        self.assertGreater(bb[3] - bb[1], 2 * 4.0)                            # deux lignes dessinées


if __name__ == '__main__':
    unittest.main()
