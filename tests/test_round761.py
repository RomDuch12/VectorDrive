"""Round 761 : VND : relu avant d'aller sur le disque, écrit d'un seul coup. Un enregistrement raté ne laisse ni fichier
vide ni fichier coupé, et l'ancien reste intact."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import geom
from vectordrive.core.document import Document, Group, Image, Layer, Plate, Shape
from vectordrive.io import vnd, vnd_write


def square(x=10.0):
    return Shape(path=geom.Path([geom.rect(x, 10, 20, 20)]))


def doc_of(*layers):
    d = Document()
    d.plate = Plate(100, 80)
    d.layers = list(layers)
    return d


class TestExpected(unittest.TestCase):
    def test_counts_what_is_written(self):
        hidden = square()
        hidden.visible = False
        d = doc_of(Layer(name='A', items=[square(), hidden, Group(children=[square()]), Group(children=[hidden]),
                                          Image(data=b'', fmt='png')]))
        self.assertEqual(vnd_write._expected_items(d), 2)


class TestCheck(unittest.TestCase):
    def test_good_file(self):
        d = doc_of(Layer(name='A', items=[square()]))
        data, _r = vnd_write.write_document(d)
        self.assertEqual(vnd_write.check_written(d, data), [])

    def test_empty_drawing_is_allowed(self):
        d = doc_of(Layer(name='A', items=[]))
        data, _r = vnd_write.write_document(d)
        self.assertEqual(vnd_write.check_written(d, data), [])

    def test_only_hidden_objects_is_allowed(self):
        s = square()
        s.visible = False
        d = doc_of(Layer(name='A', items=[s]))
        data, _r = vnd_write.write_document(d)
        self.assertEqual(vnd_write.check_written(d, data), [])

    def test_unreadable_refused(self):
        d = doc_of(Layer(name='A', items=[square()]))
        with self.assertRaises(vnd_write.VndWriteError):
            vnd_write.check_written(d, b'rien du tout')

    def test_empty_file_refused(self):
        """Le défaut à ne jamais revoir : un dessin plein, un fichier vide."""
        full = doc_of(Layer(name='A', items=[square()]))
        data, _r = vnd_write.write_document(doc_of(Layer(name='A', items=[])))
        with self.assertRaises(vnd_write.VndWriteError) as ctx:
            vnd_write.check_written(full, data)
        self.assertIn('vide', str(ctx.exception))

    def test_first_plan_empty_told(self):
        d = doc_of(Layer(name='A', items=[square()]))
        root = mock.Mock()
        first = mock.Mock(children=[])
        first.cls.name = 'CCalque'
        second = mock.Mock(children=[mock.Mock(children=[])])
        second.cls.name = 'CCalque'
        second.children[0].cls.name = 'CZone'
        root.children = [first, second]
        root.fields = {}
        with mock.patch.object(vnd, 'parse', return_value=(root, None)):
            notes = vnd_write.check_written(d, b'')
        self.assertTrue(any('premier plan' in n for n in notes))

    def test_read_back_problem_told_not_fatal(self):
        d = doc_of(Layer(name='A', items=[square()]))
        data, _r = vnd_write.write_document(d)
        real = vnd.parse

        def partial(*a, **k):
            root, ar = real(*a, **k)
            root.fields['partial_error'] = 'fin inconnue'
            return root, ar
        with mock.patch.object(vnd, 'parse', partial):
            notes = vnd_write.check_written(d, data)
        self.assertTrue(any('incomplète' in n for n in notes))


class TestWrite(unittest.TestCase):
    def setUp(self):
        self.dir = pathlib.Path(tempfile.mkdtemp())
        self.path = self.dir / 'dessin.vnd'

    def leftovers(self):
        return [p.name for p in self.dir.iterdir() if p.name != 'dessin.vnd']

    def test_normal_write(self):
        d = doc_of(Layer(name='A', items=[square()]))
        vnd_write.write(d, self.path)
        again = vnd.read(self.path)
        self.assertEqual(len([x for L in again.layers for x in L.items]), 1)
        self.assertEqual(self.leftovers(), [])

    def test_refused_keeps_the_old_file(self):
        self.path.write_bytes(b'ancien')
        d = doc_of(Layer(name='A', items=[square()]))
        empty, _r = vnd_write.write_document(doc_of(Layer(name='A', items=[])))
        with mock.patch.object(vnd_write, 'write_document', return_value=(empty, [])):
            with self.assertRaises(vnd_write.VndWriteError):
                vnd_write.write(d, self.path)
        self.assertEqual(self.path.read_bytes(), b'ancien')
        self.assertEqual(self.leftovers(), [])

    def test_failure_during_write_keeps_the_old_file(self):
        self.path.write_bytes(b'ancien')
        with mock.patch('os.replace', side_effect=PermissionError('tenu ouvert')):
            with self.assertRaises(PermissionError):
                vnd_write.write_atomic(self.path, b'nouveau')
        self.assertEqual(self.path.read_bytes(), b'ancien')
        self.assertEqual(self.leftovers(), [])

    def test_failure_of_the_disk_keeps_the_old_file(self):
        self.path.write_bytes(b'ancien')
        with mock.patch('os.fsync', side_effect=OSError('disque plein')):
            with self.assertRaises(OSError):
                vnd_write.write_atomic(self.path, b'nouveau')
        self.assertEqual(self.path.read_bytes(), b'ancien')
        self.assertEqual(self.leftovers(), [])

    def test_overwrites(self):
        self.path.write_bytes(b'ancien')
        vnd_write.write_atomic(self.path, b'nouveau')
        self.assertEqual(self.path.read_bytes(), b'nouveau')

    def test_remarks_reach_the_document(self):
        d = doc_of(Layer(name='A', items=[square()]))
        with mock.patch.object(vnd_write, 'check_written', return_value=['une remarque']):
            vnd_write.write(d, self.path)
        self.assertIn('une remarque', d.report)

    def test_accented_folder(self):
        sub = self.dir / 'Dépôt é è'
        sub.mkdir()
        p = sub / 'plaque n°1 é.vnd'
        vnd_write.write(doc_of(Layer(name='A', items=[square()])), p)
        self.assertEqual(len(vnd.read(p).layers), 1)


if __name__ == '__main__':
    unittest.main()
