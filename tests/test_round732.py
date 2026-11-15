"""Round 732 : DXF — maillages 3D (polyface, polymesh, MESH, 3DFACE) repris
en volumes, un objet chacun (d'après CADCraft) ; maillage ouvert : son
contour vu de dessus."""
import os
import tempfile
import unittest

import ezdxf

from vectordrive.core import solids as SO
from vectordrive.io import dxf as DX

CUBE_V = [(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0), (0, 0, 10), (10, 0, 10), (10, 10, 10), (0, 10, 10)]
CUBE_F = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]


def _cube(dx=0.0, dy=0.0, k=1.0):
    return [[((x * k + dx), (y * k + dy), z * k) for x, y, z in (CUBE_V[i] for i in f)] for f in CUBE_F]


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestDxfMeshes(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def _write(self, fill, units=4):
        d = ezdxf.new('R2010')
        d.header['$INSUNITS'] = units
        fill(d, d.modelspace())
        path = os.path.join(self.dir, 'maillages.dxf')
        d.saveas(path)
        return DX.read(path)

    def test_polyface_mesh_faces(self):
        def fill(d, msp):
            pf = msp.add_polyface(dxfattribs={'layer': 'PF'})
            for f in _cube():
                pf.append_face(f)
            m = msp.add_mesh(dxfattribs={'layer': 'ME'})
            with m.edit_data() as md:
                md.vertices = [(x + 20, y, z) for x, y, z in CUBE_V]
                md.faces = CUBE_F
            for f in _cube(40, 0, 0.5):                      # un cube de 3DFACE : un seul volume
                msp.add_3dface(f, dxfattribs={'layer': 'F3'})
            msp.add_3dface([(0, 30, 0), (10, 30, 0), (10, 40, 2), (0, 40, 2)], dxfattribs={'layer': 'OUV'})
            pm = msp.add_polymesh((3, 3), dxfattribs={'layer': 'PM'})
            for i in range(3):
                for j in range(3):
                    pm.set_mesh_vertex((i, j), (60 + 5 * i, 5 * j, (i * j) % 2))
            msp.add_line((0, -5), (10, -5))
        doc = self._write(fill)
        by = {L.name: L.items for L in doc.layers}
        self.assertAlmostEqual(SO.of_item(by['PF'][0]).volume(), 1000.0, places=6)
        self.assertAlmostEqual(SO.of_item(by['ME'][0]).volume(), 1000.0, places=6)
        self.assertEqual(SO.of_item(by['ME'][0]).bounds()[0], 20.0)
        self.assertEqual(len(by['F3']), 1)
        self.assertAlmostEqual(SO.of_item(by['F3'][0]).volume(), 125.0, places=6)
        for k in ('OUV', 'PM'):                              # ouverts : contour vu de dessus, pas un volume
            self.assertFalse(SO.is_solid(by[k][0]))
        self.assertEqual([round(v, 6) for v in by['OUV'][0].path.bbox()], [0, 30, 10, 40])
        self.assertEqual([round(v, 6) for v in by['PM'][0].path.bbox()], [60, 0, 70, 10])
        self.assertTrue(by['OUV'][0].path.contours[0].closed)
        rep = ' '.join(doc.report)
        self.assertIn('3 maillage(s) 3D', rep)
        self.assertIn('2 maillage(s) 3D ouvert(s)', rep)
        self.assertNotIn('non pris en charge', rep)

    def test_blocks_units_hidden(self):
        def fill(d, msp):
            blk = d.blocks.new('CUBE')
            pf = blk.add_polyface()
            for f in _cube():
                pf.append_face(f)
            msp.add_blockref('CUBE', (100, 50), dxfattribs={'layer': 'B'})
            d.layers.add('ETEINT').off()
            pf2 = msp.add_polyface(dxfattribs={'layer': 'ETEINT'})
            for f in _cube():
                pf2.append_face(f)
        doc = self._write(fill, units=5)                     # cm : × 10
        s = SO.of_item(next(L for L in doc.layers if L.name == 'B').items[0])
        self.assertAlmostEqual(s.volume(), 1000.0 * 1000, places=3)
        self.assertEqual([round(v, 6) for v in s.bounds()], [1000, 500, 0, 1100, 600, 100])
        self.assertFalse(any(L.name == 'ETEINT' and L.items for L in doc.layers))


if __name__ == '__main__':
    unittest.main()
