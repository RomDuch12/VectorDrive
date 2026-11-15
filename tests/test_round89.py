"""Round 89 : fidélité des VND d'atelier — courbes réduites à un point,
contours corrompus (NaN), cotes de rayon, solides 3D (CObBrep), plaque à
1 nm près. Données synthétiques uniquement."""
import math
import os
import pathlib
import struct
import tempfile
import unittest

from vectordrive.core import geom
from vectordrive.core.document import Document, Group, Layer, Shape
from vectordrive.io import registry, vnd, vnd_write
from vectordrive.io.mfc import MfcClass, MfcObject


def point_contour(x_m, y_m, nan=False):
    """CContour d'un seul point (ou de points NaN), comme TypeEdit en laisse."""
    co = MfcObject(MfcClass('CContour', vnd_write.SCHEMAS['CContour']))
    co.fields = vnd_write._obdao_fields((x_m, y_m, 0.0, x_m, y_m, 0.0))
    co.fields['type'] = 1 if nan else 0
    v = float('nan') if nan else None
    co.fields['points'] = ([(v, v, 0.0, 1.0, 1)] * 4 if nan else [(x_m, y_m, 0.0, 1.0, 1)])
    co.fields['ext_obj'] = vnd_write._property_extend()
    return co


def reread(data: bytes):
    with tempfile.TemporaryDirectory() as tmp:
        f = os.path.join(tmp, 'a.vnd')
        pathlib.Path(f).write_bytes(data)
        return registry.open_document(f)


def leaves(doc):
    out = []

    def walk(xs):
        for x in xs:
            out.append(x)
            walk(getattr(x, 'children', []))
    for L in doc.layers:
        walk(L.items)
    return out


class TestPointCurves(unittest.TestCase):
    def doc(self):
        d = Document()
        d.layers[0].items.append(Shape(path=geom.Path([geom.rect(0, 0, 20, 10)])))
        pt = Shape(path=geom.Path([]))
        pt.extra['vnd'] = {'wraps': 1, 'empty_contours': [(0, point_contour(0.005, 0.004))], 'drawn_contours': 0}
        d.layers[0].items.append(pt)
        return d

    def test_written_read_and_rewritten(self):
        data, _ = vnd_write.write_document(self.doc())
        root, _ = vnd.parse(data)
        self.assertEqual(vnd.structure_signature(root).count('CCourbe'), 2)
        back = reread(data)
        pts = [x for x in leaves(back) if isinstance(x, Shape) and not x.path.contours]
        self.assertEqual(len(pts), 1)
        self.assertEqual(vnd_write.write_document(back)[0], data)          # réécrit à l'octet près

    def test_point_follows_transform(self):
        back = reread(vnd_write.write_document(self.doc())[0])
        L = back.layers[0]
        L.items = [it.transformed(geom.Affine.translation(10, 0)) for it in L.items]
        data, _ = vnd_write.write_document(back)
        root, _ = vnd.parse(data)
        pts = [o.fields['points'] for o in _walk(root) if o.cls.name == 'CContour' and len(o.fields['points']) == 1]
        self.assertEqual(len(pts), 1)
        self.assertAlmostEqual(pts[0][0][0], 0.015, places=12)               # 5 mm + 10 mm


def _walk(o):
    yield o
    for c in o.children:
        yield from _walk(c)


class TestCorruptContour(unittest.TestCase):
    def test_nan_contour_kept_not_drawn(self):
        d = Document()
        sh = Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]))
        sh.extra['vnd'] = {'wraps': 1, 'empty_contours': [(1, point_contour(0, 0, nan=True))], 'drawn_contours': 1}
        d.layers[0].items.append(sh)
        data, _ = vnd_write.write_document(d)
        back = reread(data)
        self.assertTrue(any('contour corrompu' in r for r in back.report), back.report)
        self.assertTrue(all(math.isfinite(v) for v in back.bbox()))
        self.assertEqual(vnd_write.write_document(back)[0], data)

    def test_thumbnail_ignores_nan(self):
        sh = Shape(path=geom.Path([geom.Contour([geom.Line((0, 0), (5, 5)), geom.Line((5, 5), (math.nan, 1))])]))
        px = vnd_write.ink_pixels([Shape(path=geom.Path([geom.rect(0, 0, 10, 10)])), sh])
        self.assertTrue(px)


class TestRadialDimension(unittest.TestCase):
    def test_declared(self):
        for name in ('CCotationRadial', 'CCotationDiameter'):
            self.assertIn(name, vnd.READERS)
            self.assertIn(name, vnd_write.WRITERS)

    def test_broken_dimension_hidden_but_kept(self):
        zone = MfcObject(MfcClass('CZone', vnd_write.SCHEMAS['CZone']))
        zone.children = [vnd_write._courbe(Shape(path=geom.Path([geom.rect(0, 0, 3, 3)])))]
        obj = MfcObject(MfcClass('CCotationRadial', 1))
        nan = float('nan')
        obj.fields = {'pts': (0.0176, 0.011, 0.0, nan, nan, nan, 0, 0, 0), 'zone': zone, 'text': (0, b'')}
        report = []
        items = vnd._to_items(obj, report, {})
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].children, [])
        self.assertIs(items[0].extra['vnd_obj'], obj)
        self.assertTrue(any('coordonnées invalides' in r for r in report))


#: flux SMLib factice : octets quelconques et un faux en-tête CObDao au milieu
FAKE_HEADER = struct.pack('<6d', 0, 0, 0, 0.01, 0.01, 0) + struct.pack('<II', 0x01001000, 9) + b'\x07' * 40
BREP_RAW = b'\x00\x48\xe8\x01' + bytes(range(256)) * 3 + FAKE_HEADER + b'generated cylinder\x1d%' + bytes(64)


def brep_object():
    o = MfcObject(MfcClass('CObBrep', 2))
    o.fields = vnd_write._obdao_fields((-0.005, -0.005, -0.1, 0.005, 0.005, -0.001))
    o.fields['brep_flag'] = 1
    o.fields['brep_raw'] = BREP_RAW
    return o


class TestBrep(unittest.TestCase):
    def doc(self):
        d = Document()
        g = Group(children=[], name='Solide 3D')
        g.extra['vnd'] = {'wraps': 1}
        g.extra['vnd_obj'] = brep_object()
        d.layers[0].items.append(g)
        d.layers.append(Layer(name='Gravure'))
        d.layers[1].items.append(Shape(path=geom.Path([geom.rect(0, 0, 30, 10)])))
        return d

    def test_end_found_and_rewritten(self):
        data, _ = vnd_write.write_document(self.doc(), allow_foreign=True)
        root, _ = vnd.parse(data)
        self.assertNotIn('partial_error', root.fields)
        brep = [o for o in _walk(root) if o.cls.name == 'CObBrep']
        self.assertEqual(len(brep), 1)
        self.assertEqual(brep[0].fields['brep_raw'], BREP_RAW)              # faux en-tête écarté
        back = reread(data)
        self.assertNotIn('vnd_partial', back.extra)
        self.assertEqual([len(L.items) for L in back.layers], [1, 1])
        self.assertTrue(any('solide 3D non affiché' in r for r in back.report), back.report)
        self.assertEqual(vnd_write.write_document(back)[0], data)

    def test_moved_solid_stays_in_place(self):
        back = reread(vnd_write.write_document(self.doc(), allow_foreign=True)[0])
        for L in back.layers:
            L.items = [it.transformed(geom.Affine.translation(4, 0)) for it in L.items]
        data, rep = vnd_write.write_document(back)
        self.assertTrue(any('laissé(s) à leur position' in r for r in rep), rep)
        root, _ = vnd.parse(data)
        brep = [o for o in _walk(root) if o.cls.name == 'CObBrep']
        self.assertEqual(len(brep), 1)
        self.assertEqual(brep[0].fields['bbox'][0], -0.005)

    def test_unknown_end_gives_partial_read(self):
        data, _ = vnd_write.write_document(self.doc(), allow_foreign=True)
        old = vnd.BREP_MAX_TRIES
        vnd.BREP_MAX_TRIES = 0
        try:
            root, _ = vnd.parse(data, partial=True)
        finally:
            vnd.BREP_MAX_TRIES = old
        self.assertIn('CObBrep', root.fields.get('partial_error', ''))


class TestPlateTolerance(unittest.TestCase):
    def test_rounding_noise_kept(self):
        base = vnd_write.default_template()
        root, _ = vnd.parse(base)
        tail = bytearray(base[root.fields['tail_offset']:])
        d = reread(base)
        z1 = struct.unpack_from('<d', tail, 40)[0]
        struct.pack_into('<d', tail, 40, z1 + 1.7e-11)                     # arrondi de TypeEdit
        self.assertEqual(vnd_write.set_plate(bytes(tail), d.plate), bytes(tail))


if __name__ == '__main__':
    unittest.main()
