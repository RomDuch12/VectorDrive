"""Round 127 : variables TypeEdit (CVariable) des réglages du document
décodées — la fin de document se relit, la plaque et les outils sont
gardés quand on modifie un dessin qui a des variables."""
import os
import struct
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from tests.corpus import corpus
from vectordrive.core.geom import Affine
from vectordrive.io import vnd
from vectordrive.io import vnd_write as W
from vectordrive.io.mfc import Archive, ArchiveError, MfcClass, MfcObject


def ustr(s: str) -> bytes:
    """CVnStringUnicode : longueur, UTF-16, nul ; vide : la longueur seule."""
    if not s:
        return struct.pack('<I', 0)
    return struct.pack('<I', len(s)) + s.encode('utf-16-le') + b'\0\0'


def variable_bytes(lists, last=7) -> bytes:
    out = struct.pack('<I', len(lists))
    for vals in lists:
        out += struct.pack('<I', len(vals)) + b''.join(ustr(v) for v in vals)
    return out + struct.pack('<I', last)


def read_var(raw):
    o = MfcObject(MfcClass('CVariable', 2))
    ar = Archive(raw, 0, vnd.READERS)
    vnd._read_variable(ar, o)
    return o, ar.pos == len(raw)


class TestVariables(unittest.TestCase):
    def test_empty(self):
        o, complete = read_var(variable_bytes([], last=0))
        self.assertTrue(complete)
        self.assertEqual(o.fields['variables'], [])

    def test_lists_with_empty_strings(self):
        lists = [['REF', 'H/F', '', '', 'Série n°'], ['Name'], ['', 'NUM']]
        o, complete = read_var(variable_bytes(lists))
        self.assertTrue(complete)
        self.assertEqual(o.fields['variables'], lists)
        self.assertEqual(o.fields['f18'], 7)

    def test_bad_terminator_raises(self):
        raw = bytearray(variable_bytes([['AB']]))
        raw[4 + 4 + 4 + 4] = 0x41                                     # nul final abîmé
        with self.assertRaises(ArchiveError):
            read_var(bytes(raw))


@unittest.skipUnless(corpus('vnm_codebarre').is_file(), 'modèle TypeEdit avec variables absent')
class TestModelWithVariables(unittest.TestCase):
    def test_settings_read(self):
        d = vnd.read(corpus('vnm_codebarre'))
        self.assertFalse([r for r in d.report if 'réglages' in r])
        self.assertEqual([v for v in d.extra['typeedit_variables'][0] if v], ['REF', 'H/F', 'W/R', 'P/K'])
        self.assertEqual((d.plate.width, d.plate.height), (100.0, 80.0))
        self.assertTrue(d.tools)

    def test_moved_drawing_keeps_plate_and_settings(self):
        d = vnd.read(corpus('vnm_codebarre'))
        for L in d.layers:
            L.items = [it.transformed(Affine.translation(10, 0)) for it in L.items]
        data, rep = W.write_document(d)
        self.assertFalse([r for r in rep if 'réglages du modèle' in r or 'non relus' in r], rep)
        out = os.path.join(tempfile.mkdtemp(), 'deplace.vnd')
        with open(out, 'wb') as fh:
            fh.write(data)
        back = vnd.read(out)
        self.assertEqual((back.plate.width, back.plate.height), (100.0, 80.0))
        self.assertEqual([v for v in back.extra['typeedit_variables'][0] if v], ['REF', 'H/F', 'W/R', 'P/K'])
        self.assertEqual(W.v13_issues(vnd.parse(data)[0]), [])


if __name__ == '__main__':
    unittest.main()
