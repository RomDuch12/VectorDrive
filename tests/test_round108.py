"""Round 108 : pièces 3D — STL, 3D XML (export ouvert de CATIA) en vue de
dessus (un calque par hauteur, silhouette), fichiers CATIA natifs par un
convertisseur désigné (sinon message explicatif)."""
import os
import pathlib
import struct
import sys
import tempfile
import unittest
import zipfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtCore import QSettings

from vectordrive.io import mesh3d as M
from vectordrive.io import registry


def quad(a, b, c, d):
    return [(a, b, c), (a, c, d)]


def block(x0, y0, x1, y1, z0, z1):
    """Pavé : triangles orientés vers l'extérieur."""
    P = {(i, j, k): (x1 if i else x0, y1 if j else y0, z1 if k else z0) for i in (0, 1) for j in (0, 1) for k in (0, 1)}
    t = []
    t += quad(P[0, 0, 1], P[1, 0, 1], P[1, 1, 1], P[0, 1, 1])        # dessus (z+)
    t += quad(P[0, 0, 0], P[0, 1, 0], P[1, 1, 0], P[1, 0, 0])        # dessous
    t += quad(P[0, 0, 0], P[1, 0, 0], P[1, 0, 1], P[0, 0, 1])
    t += quad(P[1, 0, 0], P[1, 1, 0], P[1, 1, 1], P[1, 0, 1])
    t += quad(P[1, 1, 0], P[0, 1, 0], P[0, 1, 1], P[1, 1, 1])
    t += quad(P[0, 1, 0], P[0, 0, 0], P[0, 0, 1], P[0, 1, 1])
    return t


def stepped():
    return block(0, 0, 10, 10, 0, 5) + block(10, 0, 20, 10, 0, 3)


def write_stl_binary(path, tris):
    with open(path, 'wb') as f:
        f.write(b'\0' * 80 + struct.pack('<I', len(tris)))
        for t in tris:
            f.write(struct.pack('<3f', 0, 0, 0))
            for v in t:
                f.write(struct.pack('<3f', *v))
            f.write(b'\0\0')


def write_stl_ascii(path, tris):
    lines = ['solid essai']
    for t in tris:
        lines.append(' facet normal 0 0 0\n  outer loop')
        lines += [f'   vertex {x} {y} {z}' for x, y, z in t]
        lines.append('  endloop\n endfacet')
    lines.append('endsolid essai')
    pathlib.Path(path).write_text('\n'.join(lines), encoding='ascii')


REP = """<?xml version="1.0" encoding="UTF-8"?>
<XMLRepresentation xmlns="http://www.3ds.com/xsd/3DXML" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
 <Root xsi:type="BagRepType" id="1">
  <Rep xsi:type="PolygonalRepType" id="2">
   <Faces>
    <Face triangles="0 1 2" strips="0 2 3"/>
   </Faces>
   <VertexBuffer><Positions>0 0 4,6 0 4,6 6 4,0 6 4</Positions></VertexBuffer>
  </Rep>
 </Root>
</XMLRepresentation>"""

PRODUCT = """<?xml version="1.0" encoding="UTF-8"?>
<Model_3dxml xmlns="http://www.3ds.com/xsd/3DXML">
 <ProductStructure root="1">
  <Reference3D id="1" name="Assemblage"/>
  <Reference3D id="2" name="Plaquette"/>
  <Instance3D id="3"><IsAggregatedBy>1</IsAggregatedBy><IsInstanceOf>2</IsInstanceOf>
   <RelativeMatrix>1 0 0 0 1 0 0 0 1 0 0 0</RelativeMatrix></Instance3D>
  <Instance3D id="4"><IsAggregatedBy>1</IsAggregatedBy><IsInstanceOf>2</IsInstanceOf>
   <RelativeMatrix>1 0 0 0 1 0 0 0 1 20 0 0</RelativeMatrix></Instance3D>
  <ReferenceRep id="5" format="TESSELLATED" associatedFile="urn:3DXML:Plaquette.3DRep"/>
  <InstanceRep id="6"><IsAggregatedBy>2</IsAggregatedBy><IsInstanceOf>5</IsInstanceOf></InstanceRep>
 </ProductStructure>
</Model_3dxml>"""


def write_3dxml(path):
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('Manifest.xml', '<Manifest><Root>Produit.3dxml</Root></Manifest>')
        z.writestr('Produit.3dxml', PRODUCT)
        z.writestr('Plaquette.3DRep', REP)


def layer_boxes(doc):
    return {L.name: tuple(round(v, 3) for v in L.items[0].bbox()) for L in doc.layers if L.items}


class TestStl(unittest.TestCase):
    def test_binary_and_ascii(self):
        d = tempfile.mkdtemp()
        for writer in (write_stl_binary, write_stl_ascii):
            f = os.path.join(d, f'{writer.__name__}.stl')
            writer(f, stepped())
            T = M.read_stl(f)
            self.assertEqual(T.shape, (24, 3, 3))
            doc = registry.open_document(f)
            boxes = layer_boxes(doc)
            self.assertEqual(list(boxes)[:2], ['Pz 5', 'Pz 3'])                 # la plus haute d'abord
            self.assertEqual(boxes['Pz 5'], (0, 0, 10, 10))
            self.assertEqual(boxes['Pz 3'], (10, 0, 20, 10))
            self.assertEqual(boxes['Silhouette'], (0, 0, 20, 10))
            self.assertIn('24 triangles', doc.report[0])

    def test_garbage(self):
        f = os.path.join(tempfile.mkdtemp(), 'x.stl')
        pathlib.Path(f).write_bytes(b'pas un stl')
        with self.assertRaises(ValueError):
            M.read_stl(f)


class Test3DXml(unittest.TestCase):
    def test_instances_placed(self):
        f = os.path.join(tempfile.mkdtemp(), 'piece.3dxml')
        write_3dxml(f)
        T = M.read_3dxml(f)
        self.assertEqual(T.shape, (4, 3, 3))                                    # 2 triangles × 2 instances
        self.assertAlmostEqual(float(T[:, :, 0].max()), 26.0)
        doc = registry.open_document(f)
        L = next(L for L in doc.layers if L.name == 'Pz 4')
        self.assertEqual(len(L.items[0].path.contours), 2)                      # deux plaquettes

    def test_strips_and_fans(self):
        import xml.etree.ElementTree as ET
        rep = ET.fromstring('<Rep xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="PolygonalRepType">'
                            '<Faces><Face fans="0 1 2 3"/></Faces><VertexBuffer><Positions>'
                            '0 0 0,1 0 0,1 1 0,0 1 0</Positions></VertexBuffer></Rep>')
        self.assertEqual(len(M._rep_triangles(rep)), 2)

    def test_matrix_columns(self):
        m = M._matrix('0 1 0 -1 0 0 0 0 1 5 6 7')                            # rotation de 90° autour de z
        p = m[:3, :3] @ np.array([1.0, 0, 0]) + m[:3, 3]
        self.assertTrue(np.allclose(p, (5, 7, 7)))


class TestCatia(unittest.TestCase):
    def settings(self, value):
        s = QSettings(os.path.join(tempfile.mkdtemp(), 's.ini'), QSettings.Format.IniFormat)
        s.setValue(M.CONVERTER_KEY, value)
        return s

    def test_without_converter_explains(self):
        f = os.path.join(tempfile.mkdtemp(), 'piece.CATPart')
        pathlib.Path(f).write_bytes(b'V5_CFV2')
        with self.assertRaises(ValueError) as cm:
            M.read_catia(f, self.settings(''))
        self.assertIn('STEP', str(cm.exception))
        self.assertIn('F10', str(cm.exception))
        self.assertEqual(registry.by_extension(f).key, 'catia')

    def test_command_template(self):
        args = M.convert_command('"C:\\Outils\\conv.exe" -i {entree} -o {sortie}', 'a b.CATPart', 'x.stp')
        self.assertEqual(args, ['C:\\Outils\\conv.exe', '-i', 'a b.CATPart', '-o', 'x.stp'])
        self.assertEqual(M.convert_command('conv.exe', 'a', 'b'), ['conv.exe', 'a', 'b'])

    def test_with_converter(self):
        """Un faux convertisseur (script Python) qui copie un STEP d'essai."""
        from vectordrive.cam import tooldraw
        d = tempfile.mkdtemp()
        stp = tooldraw.ecrire_step(os.path.join(d, 'cylindre.step'),
                                   [(0.0, 0.0), (3.0, 0.0), (3.0, 20.0), (0.0, 20.0)])
        script = os.path.join(d, 'conv.py')
        pathlib.Path(script).write_text(
            'import shutil, sys\nshutil.copy(sys.argv[1], sys.argv[2])\n', encoding='utf-8')
        src = os.path.join(d, 'piece.CATPart')
        import shutil
        shutil.copy(stp, src)
        tpl = f'"{sys.executable}" "{script}" {{entree}} {{sortie}}'
        doc = M.read_catia(src, self.settings(tpl))
        self.assertEqual(doc.source_format, 'catia')
        self.assertIn('CATIA converti', doc.report[0])


if __name__ == '__main__':
    unittest.main()
