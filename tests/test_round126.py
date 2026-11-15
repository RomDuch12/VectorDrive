"""Round 126 : compatibilité TypeEdit 13 (version de l'atelier) — schémas
des classes relevés dans la V13, en-têtes d'objets V13 (CObDao 9, CObjGuid
2) à l'écriture, VND plus récent réécrit depuis le modèle, colonne
« typeedit13 » de la vérification de dessins."""
import os
import pathlib
import struct
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from tests.corpus import corpus
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape
from vectordrive.io import batch, vnd
from vectordrive.io import vnd_write as W
from vectordrive.io.mfc import Archive, MfcClass, MfcObject


def obj(name, schema, **fields):
    o = MfcObject(MfcClass(name, schema))
    o.fields = dict(fields)
    return o


def simple_vnd() -> bytes:
    d = Document()
    d.add(Shape(path=geom.Path([geom.rect(0, 0, 40, 20)])))
    return W.write_document(d)[0]


class TestIssues(unittest.TestCase):
    def test_v13_tree_is_clean(self):
        root = vnd.parse(simple_vnd())[0]
        self.assertEqual(W.v13_issues(root), [])

    def test_newer_schemas_and_headers(self):
        z = obj('CZone', 1, bbox=(0,) * 6, version=9, guid_ver=2)
        z.children = [obj('CContour', 2, bbox=(0,) * 6, version=10, guid_ver=3),
                      obj('CContour', 2, bbox=(0,) * 6, version=9, guid_ver=3),
                      obj('CObCadran', 7), obj('CZone', 2), obj('CObInconnu', 1)]
        root = obj('CTravail', 11)
        root.children = [obj('CCalque', 9), z]
        bad = ' | '.join(W.v13_issues(root))
        for part in ('CTravail : schéma 11 (TypeEdit 13 : 10)', 'CCalque : schéma 9', 'CObCadran : schéma 7',
                     'CZone : schéma 2 (TypeEdit 13 : 1)', 'CObInconnu : classe inconnue',
                     'en-tête de TypeEdit 14 ou plus (version 10)', 'identifiant de TypeEdit 14 ou plus (version 3)'):
            self.assertIn(part, bad)
        # versions plus anciennes : acceptées par la V13
        self.assertEqual(W.v13_issues(obj('CTravail', 9)), [])
        self.assertEqual(W.v13_issues(obj('CObBCode', 3)), [])

    def test_as_v13_header_roundtrip(self):
        o = obj('CContour', 2, bbox=(0.0, 0.0, 0.0, 0.001, 0.001, 0.0), flags=0x1000010, version=10, f88=0,
                f8c=0, f90=0, f94=0, guid_ver=3, guid='00' * 16, guid_props={'K': 'é'}, props={'NAME': 'Plan'},
                fin=0)
        c = W.as_v13(o)
        self.assertEqual((c.fields['version'], c.fields['guid_ver']), (9, 2))
        self.assertEqual((o.fields['version'], o.fields['guid_ver']), (10, 3))   # original intact
        self.assertIs(W.as_v13(c), c)
        w = W.MfcWriter()
        W.w_obdao(w, c)
        back = obj('CContour', 2)
        vnd.read_obdao(Archive(bytes(w.buf), 0, vnd.READERS), back)
        self.assertEqual(back.fields['version'], 9)
        self.assertEqual(back.fields['props'], {'NAME': 'Plan'})
        self.assertEqual(back.fields['guid_props'], {'K': 'é'})


class TestWriting(unittest.TestCase):
    def test_newer_vnd_rewritten_from_template(self):
        src = simple_vnd()
        tmp = pathlib.Path(tempfile.mkdtemp()) / 'recent.vnd'
        tmp.write_bytes(src)
        d = vnd.read(tmp)
        self.assertIn('vnd_source', d.extra)
        # la source passe pour « plus récente que TypeEdit 13 »
        with mock.patch.dict(W.V13_SCHEMAS, {'CTravail': 0x80000009}):
            data, rep = W.write_document(d)
        self.assertTrue(any('plus récent que TypeEdit 13' in r for r in rep))
        self.assertEqual(struct.unpack_from('<I', data, 0)[0], vnd.MAGIC)
        out = tmp.with_name('v13.vnd')
        out.write_bytes(data)
        self.assertEqual(len(list(vnd.read(out).iter_leaves())), 1)          # le dessin est gardé
        self.assertEqual(W.v13_issues(vnd.parse(data)[0]), [])

    def test_written_files_have_no_issue_reported(self):
        d = Document()
        d.add(Shape(path=geom.Path([geom.circle((10, 10), 5)])))
        _data, rep = W.write_document(d)
        self.assertFalse([r for r in rep if 'TypeEdit 13' in r])

    @unittest.skipUnless(corpus('dessins_gvt').is_dir(), 'dessins GVT absents')
    def test_gvt_saved_as_v13_vnd(self):
        n = 0
        for f in sorted(corpus('dessins_gvt').glob('*.gvt')):
            try:
                d = vnd.read(f)
            except vnd.VndError:
                continue
            data, rep = W.write_document(d)
            self.assertEqual(struct.unpack_from('<I', data, 0)[0], vnd.MAGIC, f.name)
            self.assertEqual(W.v13_issues(vnd.parse(data)[0]), [], f.name)
            self.assertFalse([r for r in rep if 'à vérifier dans TypeEdit 13' in r], f.name)
            n += 1
        self.assertGreater(n, 0)


class TestVerifier(unittest.TestCase):
    def test_column(self):
        self.assertIn('typeedit13', batch.CHECK_FIELDS)
        tmp = pathlib.Path(tempfile.mkdtemp())
        (tmp / 'neuf.vnd').write_bytes(simple_vnd())
        self.assertEqual(batch.typeedit13(tmp / 'neuf.vnd', 'vnd'), 'oui')
        self.assertTrue(batch.typeedit13(tmp / 'x.gvt', 'gvt').startswith('non : GVT'))
        self.assertEqual(batch.typeedit13(tmp / 'x.dxf', 'dxf'), '')
        with mock.patch.dict(W.V13_SCHEMAS, {'CCalque': 0x80000007}):
            self.assertTrue(batch.typeedit13(tmp / 'neuf.vnd', 'vnd').startswith('non : CCalque : schéma 8'))
        rows = batch.check([tmp / 'neuf.vnd'])
        self.assertEqual(rows[0]['typeedit13'], 'oui')


if __name__ == '__main__':
    unittest.main()
