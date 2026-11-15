"""Round 311 : tri des petites pièces (TypeEdit, Mode Expert) — selon
l'aire, le périmètre ou le cercle inscrit."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model as M, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def first_x(by):
    d = Document()
    d.plate = None
    d.add(Shape(path=geom.Path([geom.rect(0, 0, 30, 2)]), tool=1))      # longue et étroite : aire 60, périmètre 64
    d.add(Shape(path=geom.Path([geom.rect(60, 0, 10, 10)]), tool=1))    # carrée : aire 100, périmètre 40
    d.add(Shape(path=geom.Path([geom.rect(80, 0, 12, 12)]), tool=1))    # aire 144, périmètre 48
    setup = M.setup_of(d)
    t = M.CamTool(name='F', kind='droite', diameter=1)
    setup.tools = [t]
    tp = S.compute(d, setup, M.Operation(kind='contour', depth=1, step_down=1, tool_id=t.id, side='exterieur',
                                         small_first=True, small_first_by=by))
    return next(m.x for m in tp.moves if m.kind == 'plunge')


class TestSmallFirst(unittest.TestCase):
    def test_criteria(self):
        self.assertLess(first_x('aire'), 31)                           # la longue (60 mm²)
        self.assertGreater(first_x('perimetre'), 59)                   # la carrée de 10 (40 mm)
        self.assertLess(first_x('perimetre'), 71)
        self.assertLess(first_x('cercle'), 31)                         # la longue (cercle inscrit 1 mm)

    def test_size(self):
        from shapely.geometry import box
        self.assertAlmostEqual(S.piece_size(box(0, 0, 40, 2), 'cercle'), 1.0, 2)
        self.assertAlmostEqual(S.piece_size(box(0, 0, 40, 2), 'perimetre'), 84.0, 6)


if __name__ == '__main__':
    unittest.main()
