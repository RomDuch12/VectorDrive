"""Round 124 : textes braille TypeEdit (CObBraille) lus, affichés par leur
dessin de points, réécrits tels quels et translatés comme TypeEdit."""
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

STYLE = (struct.pack('<I', 5) + bytes(200)          # CTxtAttrChar v5
         + struct.pack('<I', 1) + bytes(44)         # CTxtAttrLine v1
         + struct.pack('<I', 1) + bytes(20))        # CTxtAttrPara v1


def braille_bytes(schema, zone=None, text='Bonjour', pos=(0.01, 0.02)):
    """CObBraille écrit à la main d'après MaudeExt.dll (Serialize), sans
    passer par le lecteur de VectorDrive."""
    hdr = MfcObject(MfcClass('CObBraille', schema))
    hdr.fields = W._obdao_fields((0.0, 0.0, 0.0, 0.02, 0.01, 0.0))
    w = W.MfcWriter()
    W.w_obdao_fin(w, hdr)
    w.u32(0)                                        # pas de paragraphe
    w.u32(1 if zone is not None else 0)
    if zone is not None:
        w.write_object(zone)
    w.u32(7)

    def s(t):
        if schema >= 9:
            w.cstring(t)
        else:
            b = t.encode('cp1252')
            w.u32(len(b))
            w.raw(b)
    s(text)
    s('')
    for i in range(4):
        w.u32(i)
    w.raw(STYLE)
    for x in (*pos, 0.0):
        w.f64(x)
    w.u32(0), w.u32(0), w.u32(1), w.f64(0.002), w.f64(0.0)
    if schema >= 9:
        w.cstring(text), w.f64(0.5), w.u32(1), w.u32(2), w.u32(3)
        if schema == 10:
            w.f64(0.25), w.u32(4)
    elif schema > 2:
        s(text)
        if schema > 3:
            s('NH-Braille')
            if schema > 4:
                w.f64(0.5)
            for since in (6, 7, 8):
                if schema >= since:
                    w.u32(since)
    return bytes(w.buf)


def read(raw, schema):
    obj = MfcObject(MfcClass('CObBraille', schema))
    ar = Archive(raw, 0, vnd.READERS)
    vnd.read_braille(ar, obj)
    return obj, ar.pos == len(raw)


def rewrite(obj):
    w = W.MfcWriter()
    W.w_braille(w, obj)
    return bytes(w.buf)


class TestBraille(unittest.TestCase):
    def test_all_schemas_read_and_rewritten(self):
        for schema in range(1, 11):
            raw = braille_bytes(schema, text='Bonjour' if schema > 1 else 'Bonj')
            obj, complete = read(raw, schema)
            self.assertTrue(complete, schema)
            self.assertEqual(vnd.braille_text(obj), 'Bonjour' if schema > 1 else 'Bonj')
            if 3 < schema < 9:
                self.assertEqual(vnd.braille_text(obj, 'police'), 'NH-Braille')
            self.assertEqual(rewrite(obj), raw, schema)

    def test_unknown_schema_raises(self):
        with self.assertRaises(ArchiveError):
            read(braille_bytes(10), 11)

    def test_shown_by_its_dots_and_moved(self):
        dot = Shape(path=geom.Path([geom.circle((5, 5), 0.75)]))
        raw = braille_bytes(10, zone=W._node(dot), text='Salle 12')
        obj, complete = read(raw, 10)
        self.assertTrue(complete)
        report = []
        g = vnd._to_items(obj, report)[0]
        self.assertIsInstance(g, Group)
        self.assertEqual(g.name, 'Braille : Salle 12')
        self.assertEqual(g.extra['typeedit_braille']['texte'], 'Salle 12')
        self.assertEqual(len(g.children), 1)
        self.assertFalse(report)
        self.assertEqual(rewrite(obj), raw)
        # Deplace : dessin et position suivent, l'original ne bouge pas
        t = W.translated_object(obj, 0.01, -0.005)
        back, complete = read(rewrite(t), 10)
        self.assertTrue(complete)
        self.assertAlmostEqual(vnd.braille_field(back, 'pos_x'), 0.02)
        self.assertAlmostEqual(vnd.braille_field(back, 'pos_y'), 0.015)
        self.assertAlmostEqual(vnd.braille_field(obj, 'pos_x'), 0.01)
        moved = vnd._to_items(back, [])[0]
        self.assertAlmostEqual(moved.bbox()[0] - g.bbox()[0], 10, places=6)
        self.assertAlmostEqual(moved.bbox()[1] - g.bbox()[1], -5, places=6)

    def test_in_a_document(self):
        from vectordrive.core.document import Document
        from vectordrive.core.geom import Affine
        dot = Shape(path=geom.Path([geom.circle((5, 5), 0.75)]))
        obj, _ = read(braille_bytes(10, zone=W._node(dot), text='Accueil'), 10)
        d = Document()
        d.add(vnd._to_items(obj, [])[0])
        tmp = tempfile.mkdtemp()
        src = os.path.join(tmp, 'braille.vnd')
        with open(src, 'wb') as fh:
            fh.write(W.write_document(d, allow_foreign=True)[0])     # essai : objet venu d'ailleurs
        d2 = vnd.read(src)
        found = [it for it in d2.iter_items() if 'typeedit_braille' in it.extra]
        self.assertEqual([it.extra['typeedit_braille']['texte'] for it in found], ['Accueil'])
        with open(src, 'rb') as fh:
            self.assertEqual(W.write_document(d2)[0], fh.read())     # relu puis réécrit à l'identique
        for L in d2.layers:
            L.items = [it.transformed(Affine(1, 0, 0, 1, 3, 4)) if 'typeedit_braille' in it.extra else it
                       for it in L.items]
        out = os.path.join(tmp, 'deplace.vnd')
        W.write(d2, out)
        moved = [it for it in vnd.read(out).iter_items() if 'typeedit_braille' in it.extra][0]
        self.assertAlmostEqual(vnd.braille_field(moved.extra['vnd_obj'], 'pos_x'), 0.013)
        self.assertAlmostEqual(vnd.braille_field(moved.extra['vnd_obj'], 'pos_y'), 0.024)
        self.assertAlmostEqual(moved.bbox()[0] - found[0].bbox()[0], 3, places=6)

    def test_without_drawing_is_reported(self):
        obj, _ = read(braille_bytes(9), 9)
        report = []
        g = vnd._to_items(obj, report)[0]
        self.assertEqual(g.children, [])
        self.assertTrue(any('braille' in r for r in report))


if __name__ == '__main__':
    unittest.main()
