"""Round 583 : couleurs lues — le noir (ou le blanc des DAO), s'il est employé, prend l'outil 1 (celui que les
modèles de FAO usinent d'office), même s'il n'apparaît pas en premier ; un fichier d'une seule couleur reste
à l'outil 1."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import ezdxf

from vectordrive.io import registry, svg


def leaves(items):
    return [x for c in items for x in (leaves(c.children) if hasattr(c, 'children') else [c])]


class TestBlackFirst(unittest.TestCase):
    def test_dxf(self):
        d = ezdxf.new('R2010')
        msp = d.modelspace()
        msp.add_line((0, 0), (5, 0), dxfattribs={'color': 30})                 # orange d'abord
        msp.add_line((0, 1), (5, 1), dxfattribs={'color': 7})                  # puis le blanc des DAO
        msp.add_line((0, 2), (5, 2), dxfattribs={'color': 5})                  # bleu
        f = pathlib.Path(tempfile.mkdtemp()) / 'c.dxf'
        d.saveas(f)
        r = registry.open_document(f)
        items = leaves([it for L in r.layers for it in L.items])
        self.assertEqual(items[1].tool, 0)                                     # le noir : outil 1
        self.assertEqual(r.tool_color(0), '#000000')
        self.assertNotEqual(r.tool_color(items[0].tool), '#000000')            # l'orange garde sa couleur
        self.assertNotEqual(items[0].tool, 0)
        self.assertEqual(len({it.tool for it in items}), 3)

    def test_single_color(self):
        r = svg.read_data(b'<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm" viewBox="0 0 10 10">'
                          b'<rect width="2" height="2" stroke="red" fill="none"/></svg>')
        items = leaves([it for L in r.layers for it in L.items])
        self.assertEqual({it.tool for it in items}, {0})
        self.assertEqual(r.tool_color(0), '#ff0000')


if __name__ == '__main__':
    unittest.main()
