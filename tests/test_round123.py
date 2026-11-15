"""Round 123 : codes-barres de TypeEdit V15 (CObNewBCode1D / CObNewBCode2D)
lus, affichés par leur dessin et réécrits tels quels ; commandes TypeEdit
« décalage multiple » et « effet ombrage » reliées."""
import os
import struct
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import geom
from vectordrive.core.document import Group, Shape
from vectordrive.io import vnd
from vectordrive.io import vnd_write as W
from vectordrive.io.mfc import Archive, ArchiveError, MfcClass, MfcObject

NORME = struct.pack('<I', 6) + b'*DLSOFT*2D*3' + bytes(8)


def new_bcode(cls='CObNewBCode2D', schema=2, data='SN-0042', var=None, zone=None):
    o = MfcObject(MfcClass(cls, schema))
    o.fields = W._obdao_fields((0.0, 0.0, 0.0, 0.01, 0.01, 0.0))
    o.fields.update(has_zone=1 if zone is not None else 0, zone=zone, norme_len=4 + len(NORME), norme=NORME,
                    data=data, var_flag=1 if var else 0, adv_var=0, i128=3, var=var, d140=0.125)
    if schema > 1:
        o.fields.update(b198=bytes(range(0x58)), b148=bytes(0x50))
    return o


def roundtrip(o):
    w = W.MfcWriter()
    W.WRITERS[o.cls.name](w, o)
    back = MfcObject(MfcClass(o.cls.name, o.cls.schema))
    ar = Archive(bytes(w.buf), 0, vnd.READERS)
    vnd.READERS[o.cls.name](ar, back)
    return back, ar.pos == len(w.buf), bytes(w.buf)


class TestNewBarcodes(unittest.TestCase):
    def test_roundtrip_1d_2d(self):
        for cls in ('CObNewBCode1D', 'CObNewBCode2D'):
            for schema in (1, 2):
                back, complete, raw = roundtrip(new_bcode(cls, schema, var='serie' if schema == 2 else None))
                self.assertTrue(complete, (cls, schema))
                self.assertEqual(back.fields['data'], 'SN-0042')
                self.assertEqual(vnd.bcode_norm(back), '*DLSOFT*2D*3')
                self.assertEqual(back.fields['d140'], 0.125)
                if schema == 2:
                    self.assertEqual(back.fields['var'], 'serie')
                    self.assertEqual(back.fields['b198'], bytes(range(0x58)))
                # relu puis réécrit : mêmes octets
                self.assertEqual(roundtrip(back)[2], raw)

    def test_unicode_data(self):
        back, complete, _ = roundtrip(new_bcode(data='Réf. Ø12 – €'))
        self.assertTrue(complete)
        self.assertEqual(back.fields['data'], 'Réf. Ø12 – €')

    def test_bad_norme_block_raises(self):
        o = new_bcode()
        w = W.MfcWriter()
        W.w_new_bcode(w, o)
        buf = bytearray(w.buf)
        i = bytes(buf).index(struct.pack('<I', o.fields['norme_len']) + NORME)
        struct.pack_into('<I', buf, i, 10 ** 7)                       # longueur absurde
        ar = Archive(bytes(buf), 0, vnd.READERS)
        with self.assertRaises(ArchiveError):
            vnd.read_new_bcode(ar, MfcObject(MfcClass('CObNewBCode2D', 2)))

    def test_shown_by_its_drawing(self):
        sq = Shape(path=geom.Path([geom.rect(0, 0, 8, 8)]))
        back, complete, _ = roundtrip(new_bcode(zone=W._node(sq)))
        self.assertTrue(complete)
        report = []
        items = vnd._to_items(back, report)
        self.assertEqual(len(items), 1)
        g = items[0]
        self.assertIsInstance(g, Group)
        self.assertEqual(g.name, 'Code-barres : SN-0042')
        self.assertEqual(g.extra['typeedit_barcode']['famille'], '2D')
        self.assertIs(g.extra['vnd_obj'], back)
        self.assertEqual(len(g.children), 1)
        bb = g.bbox()
        self.assertAlmostEqual(bb[2] - bb[0], 8, places=6)
        self.assertFalse(report)
        # sans dessin : groupe vide, signalé, gardé pour la réécriture
        items = vnd._to_items(roundtrip(new_bcode())[0], report)
        self.assertEqual(items[0].children, [])
        self.assertTrue(report)

    def test_moved_barcode_written_as_drawing(self):
        # position gardée dans le bloc du moteur de codes : pas de translation sûre
        self.assertIsNone(W.translated_object(new_bcode(), 0.01, 0.0))


class TestTypeEditCommands(unittest.TestCase):
    def test_new_links(self):
        from vectordrive.ui import shortcuts as S
        self.assertEqual(S.TE_ACTIONS['ID_COMPO_OFFSET_A_SUIVRE'], 'offset')
        self.assertEqual(S.TE_ACTIONS['ID_COMPO_CHISEL_EFFECT'], 'shadow')


if __name__ == '__main__':
    unittest.main()
