"""Round 866 : les modes de tracé, relevés dans TypeEdit 13 sur un carré de 10 mm et un trait de 20 mm, deux passes."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', os.path.join(tempfile.mkdtemp(), 'session'))
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')

from vectordrive.cam import model as M
from vectordrive.cam import strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape

A = (10.0, 10.0)
B = (20.0, 10.0)
C = (20.0, 20.0)
D = (10.0, 20.0)
L0 = (30.0, 10.0)
L1 = (50.0, 10.0)


def run(shape, **kw):
    doc = Document()
    doc.plate = Plate(width=100.0, height=50.0)
    doc.layers = [Layer(name='A', items=[shape])]
    setup = M.setup_of(doc)
    tool = M.CamTool(name='V', diameter=1.0)
    setup.tools.append(tool)
    op = M.Operation(kind='gravure', tool_id=tool.id, depth=2.0, step_down=1.0, **kw)
    setup.operations.append(op)
    M.store(doc, setup)
    return S.compute(doc, setup, op, (0.0, 0.0))


def square(**kw):
    return run(Shape(path=geom.Path([geom.polyline([A, B, C, D], closed=True)])), **kw)


def line(**kw):
    return run(Shape(path=geom.Path([geom.polyline([L0, L1])])), **kw)


def cuts(tp):
    """Sous la surface : (x, y, z) arrondis, sans répéter un point."""
    out = []
    for m in tp.moves:
        p = (round(m.x, 6), round(m.y, 6), round(m.z, 6))
        if m.z >= 0:
            continue
        if not out or out[-1] != p:
            out.append(p)
    return out


def at(z, *pts):
    return [(p[0], p[1], z) for p in pts]


class TestLikeTypeEdit(unittest.TestCase):
    """Les listes de points attendues sont celles des fichiers de parcours écrits par TypeEdit 13."""

    def test_a_square_one_way(self):
        self.assertEqual(cuts(square(trace_mode='simple')), at(-1.0, A, B, C, D, A) + at(-2.0, A, B, C, D, A))

    def test_a_line_one_way_changes_direction_without_lifting(self):
        tp = line(trace_mode='simple')
        self.assertEqual(cuts(tp), at(-1.0, L0, L1) + at(-2.0, L1, L0))
        low = [m for m in tp.moves if m.z < 0]
        self.assertFalse(any(m.kind == 'rapid' for m in low))

    def test_a_square_back_and_forth(self):
        self.assertEqual(cuts(square(trace_mode='ar')),
                         at(-1.0, A, B, C, D, A, D, C, B, A) + at(-2.0, A, B, C, D, A, D, C, B, A))

    def test_a_line_back_and_forth(self):
        self.assertEqual(cuts(line(trace_mode='ar')), at(-1.0, L0, L1, L0) + at(-2.0, L0, L1, L0))

    def test_a_square_back_on_the_last_pass(self):
        self.assertEqual(cuts(square(trace_mode='dernier')), at(-1.0, A, B, C, D, A) + at(-2.0, A, B, C, D, A, D, C, B, A))

    def test_a_line_back_on_the_last_pass(self):
        self.assertEqual(cuts(line(trace_mode='dernier')), at(-1.0, L0, L1) + at(-2.0, L0, L1, L0))

    def test_a_back_and_forth_does_not_lift_between_passes(self):
        tp = square(trace_mode='ar')
        first = next(i for i, m in enumerate(tp.moves) if m.z < 0)
        self.assertFalse(any(m.kind == 'rapid' for m in tp.moves[first:] if m.z < 0))
        self.assertEqual(sum(1 for m in tp.moves[first:-1] if m.kind == 'rapid'), 0)


class TestOldNames(unittest.TestCase):

    def test_the_old_default_keeps_its_path(self):
        self.assertEqual(M.Operation(trace_mode='aller_retour').trace_mode, 'simple')
        self.assertEqual(cuts(line(trace_mode='aller_retour')), cuts(line(trace_mode='simple')))

    def test_the_old_one_way(self):
        self.assertEqual(M.Operation(trace_mode='aller_simple').trace_mode, 'meme_sens')
        self.assertEqual(cuts(line(trace_mode='aller_simple')), at(-1.0, L0, L1) + at(-2.0, L0, L1))

    def test_the_old_last_return(self):
        self.assertEqual(M.Operation(trace_mode='dernier_ar').trace_mode, 'dernier')

    def test_the_default(self):
        self.assertEqual(M.Operation().trace_mode, 'simple')

    def test_a_saved_operation(self):
        d = M.Operation(trace_mode='ar').to_dict()
        self.assertEqual(M.Operation.from_dict(d).trace_mode, 'ar')
        d['trace_mode'] = 'aller_retour'
        self.assertEqual(M.Operation.from_dict(d).trace_mode, 'simple')


class TestBackWithTabs(unittest.TestCase):

    def test_the_way_back_passes_over_the_same_tab(self):
        tp = line(trace_mode='ar', tabs=1, tab_width=2.0, tab_height=0.5)
        low = [m for m in tp.moves if m.z == -1.0 or m.z == -2.0]
        self.assertTrue(low)
        for z in (-1.0, -2.0):
            xs = [m.x for m in tp.moves if m.z == z]
            self.assertAlmostEqual(min(xs), 30.0, places=6)
            self.assertAlmostEqual(max(xs), 50.0, places=6)
        # le retour remonte aussi sur le pontet : autant de passages hauts à l'aller qu'au retour
        top = [m for m in tp.moves if abs(m.z + 1.5) < 1e-6]
        self.assertEqual(len(top) % 2, 0)

    def test_a_ramp_then_back(self):
        got = cuts(line(trace_mode='ar', ramp=True))
        self.assertEqual(got[-1], (30.0, 10.0, -2.0))


if __name__ == '__main__':
    unittest.main()
