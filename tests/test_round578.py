"""Round 578 : 10 outils comme TypeEdit — couleurs lues regroupées en 10 outils au plus ; un dessin qui emploie
un outil au-delà du 10e garde ses couleurs dans le compagnon .vdz du VND."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import geom
from vectordrive.core.document import Document, Shape
from vectordrive.io import colors, companion


class TestTenTools(unittest.TestCase):
    def test_cap(self):
        tc = colors.ToolColors(Document())
        made = {tc.tool(colors.hex_of(r, g, b)) for r in (0, 120, 250) for g in (0, 120, 250) for b in (0, 120, 250)}
        self.assertLessEqual(max(made), 9)

    def test_companion_reason(self):
        d = Document()
        d.add(Shape(path=geom.Path([geom.rect(0, 0, 1, 1)]), tool=3))
        self.assertFalse([r for r in companion.reasons(d) if 'outil' in r])
        d.add(Shape(path=geom.Path([geom.rect(0, 0, 1, 1)]), tool=12))
        self.assertTrue([r for r in companion.reasons(d) if 'au-delà du 10e' in r])


if __name__ == '__main__':
    unittest.main()
