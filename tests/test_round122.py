"""Round 122 : cadrans et règles graduées TypeEdit (CObCadran) lus,
affichés par leur dessin, réécrits tels quels et translatés comme TypeEdit."""
import os
import struct
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from tests.corpus import corpus
from vectordrive.core.document import Group
from vectordrive.core.geom import Affine
from vectordrive.io import vnd
from vectordrive.io.mfc import Archive, MfcClass, MfcObject
from vectordrive.io import vnd_write as W


def vernier_raw(schema=5, graduations=b'0222212222', police=b'Arial', centre=(0.0, 0.0)):
    """Réglages synthétiques d'un cadran (CGVernier), au format lu par TypeEdit."""
    head = bytearray(0x70)
    struct.pack_into('<4I', head, 0, 2, 0, 0, 0)
    struct.pack_into('<2d', head, 0x10, *centre)
    out = struct.pack('<I', 1) + bytes(head) + bytes(36)
    if schema >= 6:
        police = police.decode('ascii').encode('utf-16-le')
    out += struct.pack('<i', len(police)) + police + bytes(40)
    out += struct.pack('<i', 0) + bytes(8)
    out += struct.pack('<i', 3) + b'REF'
    n = len(graduations)
    g = graduations if schema < 6 else graduations.decode('ascii').encode('utf-16-le')
    out += struct.pack('<i', n) + g + bytes(48 * n)
    out += struct.pack('<I', 0)
    out += struct.pack('<I', 5) + bytes(200)            # CTxtAttrChar v5
    out += struct.pack('<I', 1) + bytes(44)             # CTxtAttrLine v1
    out += struct.pack('<I', 1) + bytes(20)             # CTxtAttrPara v1
    return out


def cadran(schema=5, **kw):
    o = MfcObject(MfcClass('CObCadran', schema))
    o.fields = W._obdao_fields((0.0, 0.0, 0.0, 0.02, 0.01, 0.0))
    raw = vernier_raw(schema, **kw)
    name = b'REF' if schema < 6 else 'REF'.encode('utf-16-le')
    o.fields.update(has_courbe=0, courbe=None, has_zone=0, zone=None, c250=0xff0000, c254=0,
                    name_n=3, name=name, has_var=0, var=None, has_vernier=1,
                    vernier=vnd._cadran_vernier(Archive(raw, 0, vnd.READERS), schema),
                    prop_a=W._property_extend(), prop_b=W._property_extend(), d_f8=0.25)
    if schema >= 6:
        o.fields['name_extra'] = bytes(18)
    return o


def roundtrip(o):
    w = W.MfcWriter()
    W.w_cadran(w, o)
    back = MfcObject(MfcClass('CObCadran', o.cls.schema))
    ar = Archive(bytes(w.buf), 0, vnd.READERS)
    vnd.read_cadran(ar, back)
    return back, ar.pos == len(w.buf)


class TestCadran(unittest.TestCase):
    def test_roundtrip_schema5_and_6(self):
        for schema in (5, 6):
            back, complete = roundtrip(cadran(schema))
            self.assertTrue(complete, schema)
            self.assertEqual(vnd.cadran_name(back), 'REF')
            ver = back.fields['vernier']
            self.assertEqual(vnd.cadran_text(ver['graduations'], schema), '0222212222')
            self.assertEqual(vnd.cadran_text(ver['police'], schema), 'Arial')
            self.assertEqual(back.fields['d_f8'], 0.25)

    def test_translation_moves_centre(self):
        o = cadran(centre=(0.01, 0.02))
        t = W.translated_object(o, 0.005, -0.001)
        x, y = struct.unpack_from('<2d', t.fields['vernier']['raw'], 4 + 0x10)
        self.assertAlmostEqual(x, 0.015)
        self.assertAlmostEqual(y, 0.019)
        self.assertAlmostEqual(t.fields['bbox'][0], 0.005)
        self.assertEqual(struct.unpack_from('<2d', o.fields['vernier']['raw'], 4 + 0x10), (0.01, 0.02))

    @unittest.skipUnless(corpus('vnm_codebarre').is_file(), 'modèle TypeEdit avec cadrans absent')
    def test_typeedit_model_with_dials(self):
        src = corpus('vnm_codebarre')
        d = vnd.read(src)
        dials = [it for it in d.iter_items() if isinstance(it, Group) and 'typeedit_cadran' in it.extra]
        self.assertEqual(len(dials), 2)
        self.assertTrue(all(g.children for g in dials))                    # dessin généré par TypeEdit
        self.assertIn('0222212222', [g.extra['typeedit_cadran']['graduations'] for g in dials])
        self.assertFalse(any('CObCadran' in r for r in d.report))
        data, _rep = W.write_document(d)
        self.assertEqual(data, src.read_bytes())                           # réécrit à l'octet près
        # déplacé : dessin, boîte et centre des réglages suivent
        for L in d.layers:
            L.items = [it.transformed(Affine(1, 0, 0, 1, 10, 5)) if 'typeedit_cadran' in it.extra else it
                       for it in L.items]
        out = os.path.join(tempfile.mkdtemp(), 'deplace.vnd')
        W.write(d, out)
        d2 = vnd.read(out)
        moved = [it for it in d2.iter_items() if 'typeedit_cadran' in it.extra]
        self.assertEqual(len(moved), 2)
        for a, b in zip(dials, moved):
            self.assertAlmostEqual(b.bbox()[0] - a.bbox()[0], 10, places=4)
            self.assertAlmostEqual(b.bbox()[1] - a.bbox()[1], 5, places=4)
            c0 = struct.unpack_from('<2d', a.extra['vnd_obj'].fields['vernier']['raw'], 4 + 0x10)
            c1 = struct.unpack_from('<2d', b.extra['vnd_obj'].fields['vernier']['raw'], 4 + 0x10)
            self.assertAlmostEqual(c1[0] - c0[0], 0.01)
            self.assertAlmostEqual(c1[1] - c0[1], 0.005)


if __name__ == '__main__':
    unittest.main()
