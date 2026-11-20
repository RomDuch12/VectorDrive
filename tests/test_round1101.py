"""Round 1101 : le compte rendu de lecture ne dit le relief « gardé tel quel » que si c'est vrai — un relief avec
historique d'édition arrête la lecture (dessin partiel) et sera réenregistré comme image."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1101.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from vectordrive.core.document import Group, Image  # noqa: E402
from vectordrive.io import vnd, vnd_write as W  # noqa: E402
from tests.test_round1100 import doc_with, image_of, objects, relief  # noqa: E402


def read_back(data):
    with tempfile.TemporaryDirectory() as tmp:
        p = pathlib.Path(tmp) / 'r.vnd'
        p.write_bytes(data)
        return vnd.read(p)


class TestReliefReport(unittest.TestCase):
    def test_kept_said(self):
        data, _ = W.write_document(doc_with(image_of(relief())), allow_foreign=True)
        d = read_back(data)
        self.assertTrue(any('gardé(s) tel(s) quel(s)' in r for r in d.report), d.report)
        self.assertFalse(any('comme image' in r for r in d.report), d.report)

    def test_history_stops_reading_and_says_image(self):
        o = relief()
        o.fields['histo'] = {'version': 3, 'n': 1, 'current': 0}   # historique d'édition : pas lu par VectorDrive
        data, _ = W.write_document(doc_with(image_of(o)), allow_foreign=True)
        d = read_back(data)
        self.assertIn('vnd_partial', d.extra)
        self.assertFalse(any('tel quel' in r or 'tel(s) quel(s)' in r for r in d.report), d.report)
        self.assertTrue(any('comme image' in r for r in d.report), d.report)
        again, _ = W.write_document(d)
        self.assertEqual(objects(again, 'CVbitmap'), [])
        self.assertEqual(len(objects(again, 'CVnImage')), 1)

    def test_no_relief_no_line(self):
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        data, _ = W.write_document(doc_with(Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]))))
        d = read_back(data)
        self.assertFalse(any('relief' in r for r in d.report), d.report)

    def test_relief_in_group_counted(self):
        a, b = image_of(relief()), image_of(relief())
        b.extra['vnd_obj'] = relief()
        g = Group(children=[a, b])
        data, _ = W.write_document(doc_with(g), allow_foreign=True)
        d = read_back(data)
        n = sum(1 for L in d.layers for it in L.items for x in ([it] + list(getattr(it, 'children', [])))
                if isinstance(x, Image))
        self.assertEqual(n, 2)
        self.assertTrue(any(r.startswith('2 relief(s) gardé') for r in d.report), d.report)


if __name__ == '__main__':
    unittest.main()
