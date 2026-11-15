"""BAT : le nom d'un brut ne chevauche plus les cotes ou le cadre d'un voisin."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import brut as BR
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Shape
from vectordrive.core.geom import IDENTITY
from vectordrive.io import proof

app = QApplication.instance() or QApplication([])


def square(x, y, side=10.0):
    return Shape(path=geom.Path([geom.rect(x, y, side, side)]))


def doc_of(*items):
    d = Document()
    d.plate = None
    d.layers = [Layer(name='A', items=list(items))]
    return d


def fmt(v):
    return f'{v:g}'


def dims_and_names(doc, info=None):
    """Tout ce que pose `_engraving_dims` sur une page à l'échelle 1, et à part les noms des bruts."""
    info = info or proof.ProofInfo(legend=False, prices=False, dims_each=False)
    names = []
    real = proof._label

    def spy(s, *a, **kw):
        p = real(s, *a, **kw)
        if s.startswith('Brut') or s.startswith('Raw'):
            names.append(p)
        return p
    with mock.patch.object(proof, '_label', spy):
        out = proof._engraving_dims(doc, info, None, IDENTITY, fmt)
    placed = [p for p in out if any(p is n for n in names)]
    return out, placed


class TestLabel(unittest.TestCase):
    def assertFree(self, out, name):
        box = name.path.bbox()
        for p in out:
            if p is name:
                continue
            other = p.path.bbox()
            self.assertFalse(proof._overlap(box, other, 0.0), f'{box} chevauche {other}')

    def test_alone_it_stays_above(self):
        s = square(0, 0)
        BR.make(s, 40, 30, name='A')
        out, (name,) = dims_and_names(doc_of(s))
        box = name.path.bbox()
        top = BR.bbox(BR.of(s))[3]
        self.assertGreater(box[1], top)
        self.assertAlmostEqual((box[0] + box[2]) / 2, 5.0, delta=0.5)

    def test_neighbour_above_pushes_it_away(self):
        low, high = square(0, 0), square(0, 38)
        BR.make(low, 40, 30, name='BAS')
        BR.make(high, 40, 30, name='HAUT')                                    # 8 mm au-dessus : les cotes du haut sont là
        out, names = dims_and_names(doc_of(low, high))
        self.assertEqual(len(names), 2)
        for name in names:
            self.assertFree(out, name)
        self.assertLess(names[0].path.bbox()[3], BR.bbox(BR.of(low))[1])      # passé sous son brut

    def test_neighbour_frame_counts(self):
        low, high = square(0, 0), square(0, 34)
        BR.make(low, 40, 30)
        BR.make(high, 40, 30, cotes='aucune')                                 # sans cotes, mais son cadre est là
        out, (name,) = dims_and_names(doc_of(low, high))
        box = name.path.bbox()
        self.assertFalse(proof._overlap(box, BR.bbox(BR.of(high))))

    def test_neighbours_all_around(self):
        items = []
        for x, y in ((0, 0), (0, 42), (50, 0), (-50, 0), (0, -42)):
            s = square(x, y)
            BR.make(s, 40, 30)
            items.append(s)
        out, names = dims_and_names(doc_of(*items))
        self.assertEqual(len(names), 5)                                       # rien de libre : au moins, il reste écrit

    def test_two_names_not_on_each_other(self):
        a, b = square(0, 0), square(0, 0)
        BR.make(a, 40, 30, name='A')
        BR.make(b, 40, 30, name='B')
        _out, (na, nb) = dims_and_names(doc_of(a, b))
        self.assertFalse(proof._overlap(na.path.bbox(), nb.path.bbox(), 0.0))

    def test_no_dims_no_name(self):
        s = square(0, 0)
        BR.make(s, 40, 30, cotes='ensemble')
        _out, names = dims_and_names(doc_of(s))
        self.assertEqual(names, [])

    def test_full_page_still_builds(self):
        low, high = square(0, 0), square(0, 42)
        BR.make(low, 40, 30)
        BR.make(high, 40, 30)
        prims = proof.build(doc_of(low, high), proof.ProofInfo(legend=False))[0]
        self.assertTrue(prims)

    def test_overlap_helper(self):
        self.assertTrue(proof._overlap((0, 0, 1, 1), (0.5, 0.5, 2, 2)))
        self.assertFalse(proof._overlap((0, 0, 1, 1), (2, 2, 3, 3)))
        self.assertTrue(proof._overlap((0, 0, 1, 1), (1.2, 0, 2, 1)))         # dans la marge
        self.assertFalse(proof._overlap((0, 0, 1, 1), (1.2, 0, 2, 1), 0.0))


if __name__ == '__main__':
    unittest.main()
