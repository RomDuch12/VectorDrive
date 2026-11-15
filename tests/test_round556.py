"""Round 556 : couleurs des fichiers lus — teintes voisines (PDF d'impression : #000000, #020203,
#1e1e1c…) en un seul outil, 16 outils créés au plus (au-delà : la couleur la plus proche)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core.document import Document
from vectordrive.io import colors


class TestNear(unittest.TestCase):
    def test_merge_near(self):
        tc = colors.ToolColors(Document())
        self.assertEqual(tc.tool('#000000'), 0)
        self.assertEqual(tc.tool('#020203'), 0)
        self.assertEqual(tc.tool('#1e1e1c'), 0)
        self.assertEqual(tc.tool('#ff0000'), 1)
        self.assertEqual(tc.tool('#f01010'), 1)
        self.assertEqual(tc.tool('#00a000'), 2)
        self.assertEqual(tc.doc.tool_color(0), '#000000')                    # la première teinte vue

    def test_cap(self):
        tc = colors.ToolColors(Document())
        made = {tc.tool(colors.hex_of(r, g, b)) for r in (0, 120, 250) for g in (0, 120, 250) for b in (0, 120, 250)}
        self.assertLessEqual(len(made), colors.MAX_TOOLS)
        self.assertEqual(colors.MAX_TOOLS, 10)                                 # comme TypeEdit (r578)
        self.assertEqual(tc.tool('#fafafa'), tc.tool('#f5f5f0'))                    # teintes voisines


if __name__ == '__main__':
    unittest.main()
