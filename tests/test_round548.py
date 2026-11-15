"""Round 548 : couleurs des DXF et SVG — écrites (couleur de l'outil : indexée la plus proche + couleur
vraie) et relues (une couleur = un outil, dans l'ordre d'apparition ; DUCALQUE, DUBLOC, blanc des DAO
= noir) ; réglage F10 › Fichiers pour tout garder à l'outil 1."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import ezdxf

from vectordrive.core import geom
from vectordrive.core.document import Document, Group, Shape, Tool
from vectordrive.io import colors, registry, svg


def colored() -> Document:
    d = Document()
    d.tools = [Tool(0, '#000000'), Tool(3, '#ff0000'), Tool(5, '#00a000')]
    d.layers[0].items = [Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]), tool=0),
                         Shape(path=geom.Path([geom.rect(20, 0, 10, 10)]), tool=3),
                         Shape(path=geom.Path([geom.circle((50, 5), 4)]), tool=5)]
    return d


def leaves(items):
    return [x for c in items for x in (leaves(c.children) if isinstance(c, Group) else [c])]


class TestColors(unittest.TestCase):
    def setUp(self):
        self.t = pathlib.Path(tempfile.mkdtemp())

    def roundtrip(self, ext):
        f = self.t / f'x.{ext}'
        registry.save_document(colored(), f)
        r = registry.open_document(f)
        items = leaves([it for L in r.layers for it in L.items])
        return r, items

    def test_dxf_roundtrip(self):
        r, items = self.roundtrip('dxf')
        self.assertEqual([it.tool for it in items], [0, 1, 2])
        self.assertEqual(r.tool_colors(items), {0: '#000000', 1: '#ff0000', 2: '#00a000'})

    def test_svg_roundtrip(self):
        r, items = self.roundtrip('svg')
        self.assertEqual(sorted(r.tool_colors(items).values()), ['#000000', '#00a000', '#ff0000'])

    def test_dxf_bylayer_byblock(self):
        d = ezdxf.new('R2010')
        d.layers.add('ROUGE', color=1)
        blk = d.blocks.new('B')
        blk.add_line((0, 0), (1, 0), dxfattribs={'color': 0})            # DUBLOC
        msp = d.modelspace()
        msp.add_line((0, 0), (5, 0), dxfattribs={'layer': 'ROUGE'})        # DUCALQUE : rouge
        msp.add_line((0, 1), (5, 1), dxfattribs={'color': 7})              # blanc des DAO : noir
        msp.add_blockref('B', (0, 5), dxfattribs={'color': 3})             # vert
        f = self.t / 'c.dxf'
        d.saveas(f)
        r = registry.open_document(f)
        items = leaves([it for L in r.layers for it in L.items])
        cols = [r.tool_color(it.tool) for it in items]
        self.assertEqual(cols, ['#ff0000', '#000000', '#00ff00'])

    def test_svg_inherited(self):
        r = svg.read_data(b'<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm" viewBox="0 0 10 10">'
                          b'<g stroke="blue" fill="none"><rect width="2" height="2"/>'
                          b'<rect x="3" width="2" height="2" style="stroke:#f00"/></g>'
                          b'<circle cx="8" cy="8" r="1"/></svg>')
        items = leaves([it for L in r.layers for it in L.items])
        self.assertEqual([r.tool_color(it.tool) for it in items], ['#0000ff', '#ff0000', '#000000'])

    def test_keep_off(self):
        colors.KEEP = False
        try:
            r, items = self.roundtrip('dxf')
            self.assertEqual({it.tool for it in items}, {0})
        finally:
            colors.KEEP = True

    def test_parse_and_aci(self):
        self.assertEqual(colors.parse_css('#F0a'), '#ff00aa')
        self.assertEqual(colors.parse_css('rgb(255, 0, 0)'), '#ff0000')
        self.assertEqual(colors.parse_css('rgb(100%,0%,0%)'), '#ff0000')
        self.assertIsNone(colors.parse_css('none'))
        self.assertIsNone(colors.parse_css('url(#g)'))
        self.assertEqual(colors.nearest_aci('#ff0000'), 1)
        self.assertEqual(colors.nearest_aci('#000000'), 7)

    def test_option(self):
        from vectordrive.ui import options
        self.assertTrue(options.BY_KEY['import/couleurs'].default)


if __name__ == '__main__':
    unittest.main()
