"""Round 549 : couleurs des PDF, EPS et AI relues (trait, sinon fond ; gris, RVB, CMJN ; état graphique
sauvé et rendu) — une couleur = un outil, comme les DXF et SVG."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import geom
from vectordrive.core.document import Document, Shape, Tool
from vectordrive.io import colors, postscript, registry


def colored() -> Document:
    d = Document()
    d.tools = [Tool(0, '#000000'), Tool(3, '#ff0000'), Tool(5, '#00a000')]
    d.layers[0].items = [Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]), tool=0),
                         Shape(path=geom.Path([geom.rect(20, 0, 10, 10)]), tool=3),
                         Shape(path=geom.Path([geom.circle((50, 5), 4)]), tool=5)]
    return d


class TestColors(unittest.TestCase):
    def test_roundtrips(self):
        for ext in ('pdf', 'eps', 'ai'):
            with self.subTest(ext=ext):
                f = pathlib.Path(tempfile.mkdtemp()) / f'x.{ext}'
                registry.save_document(colored(), f)
                r = registry.open_document(f)
                items = [it for L in r.layers for it in L.items]
                self.assertEqual(r.tool_colors(items), {0: '#000000', 1: '#ff0000', 2: '#00a000'})

    def test_operands(self):
        self.assertEqual(colors.from_operands([0.5]), '#808080')
        self.assertEqual(colors.from_operands([1, 0, 0]), '#ff0000')
        self.assertEqual(colors.from_operands([0, 1, 1, 0]), '#ff0000')          # CMJN
        self.assertIsNone(colors.from_operands([b'/CS0']))

    def test_postscript_states(self):
        ps = (b'%!PS-Adobe-3.0\n%%EndProlog\n'
              b'0 0 1 setrgbcolor gsave 1 0 0 setrgbcolor 0 0 moveto 10 0 lineto stroke grestore '
              b'0 5 moveto 10 5 lineto stroke '
              b'0 1 0 0 k 0 10 moveto 10 10 lineto 10 20 lineto f\n')
        f = pathlib.Path(tempfile.mkdtemp()) / 'p.eps'
        f.write_bytes(ps)
        r = postscript.read(f)
        items = r.layers[0].items
        self.assertEqual([r.tool_color(it.tool) for it in items], ['#ff0000', '#0000ff', '#ff00ff'])


if __name__ == '__main__':
    unittest.main()
