"""Round 751 : un VND s'ouvre toujours sur un dessin dans TypeEdit 13, qui n'affiche à l'ouverture que son
premier plan : un premier plan vide ou masqué passe après le premier plan qui a quelque chose à montrer."""
import os
import struct
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape
from vectordrive.io import vnd, vnd_write


def rect(x, tool=0, **k):
    return Shape(path=geom.Path([geom.rect(x, 1, 5, 5)]), tool=tool, **k)


def written(layers):
    d = Document()
    d.plate = Plate(100, 50)
    d.layers = layers
    data, report = vnd_write.write_document(d)
    root, _ar = vnd.parse(data)
    plans = [(c.fields['layer_name'], struct.unpack_from('<IIII', c.fields['attrs']), len(c.children))
             for c in root.children]
    return plans, report


class TestFirstPlan(unittest.TestCase):
    def test_empty_first_plan(self):
        plans, report = written([Layer(name='Plan 1'), Layer(name='B', items=[rect(1, 2)], tool=2),
                                 Layer(name='C', items=[rect(9, 3)], tool=3)])
        self.assertEqual([p[0] for p in plans], ['B', 'Plan 1', 'C'])          # les autres gardent leur ordre
        self.assertEqual([p[1][1] for p in plans], [1, 0, 0])                  # un seul plan courant : le premier
        self.assertEqual([p[1][2] for p in plans], [2, 0, 3])                  # chacun garde son outil
        self.assertTrue(any('« B »' in r for r in report))

    def test_hidden_first_plan(self):
        hidden = Layer(name='Caché', items=[rect(1)], visible=False)
        plans, _r = written([hidden, Layer(name='B', items=[rect(9, 2)], tool=2)])
        self.assertEqual([p[0] for p in plans], ['B', 'Caché'])
        self.assertEqual(plans[1][1][3], 0)                                    # masqué aussi en multi-plans

    def test_hidden_objects_only(self):
        plans, _r = written([Layer(name='A', items=[rect(1, visible=False)]), Layer(name='B', items=[rect(9, 2)], tool=2)])
        self.assertEqual([p[0] for p in plans], ['B', 'A'])

    def test_nothing_to_move(self):
        plans, report = written([Layer(name='A', items=[rect(1)]), Layer(name='B'), Layer(name='C', items=[rect(9, 3)], tool=3)])
        self.assertEqual([p[0] for p in plans], ['A', 'B', 'C'])               # ordre du dessin gardé
        self.assertEqual([p[1][1] for p in plans], [1, 0, 0])
        self.assertFalse(any('premier' in r for r in report))

    def test_only_hidden_layers(self):
        plans, _r = written([Layer(name='Vide'), Layer(name='Caché', items=[rect(1)], visible=False)])
        self.assertEqual(plans[0][0], 'Caché')                                 # rien de mieux à montrer

    def test_empty_document(self):
        plans, report = written([Layer(name='Plan 1')])
        self.assertEqual([p[0] for p in plans], ['Plan 1'])
        self.assertEqual(plans[0][1][1], 1)
        self.assertEqual(report, [])

    def test_locked(self):
        plans, _r = written([Layer(name='A', items=[rect(1)], locked=True)])
        self.assertEqual(plans[0][1][0], 1)


if __name__ == '__main__':
    unittest.main()
