"""Round 959 : écriture en volume des dessins de milliers de contours — les doublons ne sont cherchés que parmi les
contours de même aire et de même encombrement, et les contours ne sont relevés qu'une fois par écriture."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r959.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from shapely.geometry.base import BaseGeometry  # noqa: E402

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Shape  # noqa: E402
from vectordrive.io import registry, write3d  # noqa: E402


def dots(n: int = 20, pitch: float = 0.6, r: float = 0.2):
    """Un motif de points identiques, serrés : n × n cercles de même aire."""
    d = Document()
    d.layers[0].items += [Shape(path=geom.Path([geom.circle((i * pitch, j * pitch), r)]))
                          for i in range(n) for j in range(n)]
    return d


class Fast(unittest.TestCase):

    def test_identical_dots_are_not_compared_one_to_one(self):
        d = dots()
        real = BaseGeometry.symmetric_difference
        calls = []

        def counted(self, other, *a, **k):
            calls.append(1)
            return real(self, other, *a, **k)
        with mock.patch.object(BaseGeometry, 'symmetric_difference', counted):
            loops = write3d.loops_of(d)
        self.assertEqual(len(loops), 400)
        self.assertEqual(len(calls), 0)                     # avant : des milliers (chaque point contre ses voisins)
        # un vrai doublon est toujours écarté — et lui seul est comparé finement
        d.layers[0].items.append(Shape(path=geom.Path([geom.circle((0.6, 1.2), 0.2)])))
        calls.clear()
        with mock.patch.object(BaseGeometry, 'symmetric_difference', counted):
            self.assertEqual(len(write3d.loops_of(d)), 400)
        self.assertEqual(len(calls), 1)

    def test_contours_are_collected_once_per_file(self):
        d = Document()                                      # deux rectangles qui se croisent : réunis en polygones
        d.layers[0].items += [Shape(path=geom.Path([geom.rect(0, 0, 30, 20)])),
                              Shape(path=geom.Path([geom.rect(20, 10, 30, 20)]))]
        real = write3d.loops_of
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(write3d, 'loops_of', side_effect=real) as seen:
            f = os.path.join(tmp, 'croix.step')
            registry.save_document(d, f)
            self.assertEqual(seen.call_count, 1)            # avant : 2 (une fois de plus pour les réunir)
            self.assertEqual(pathlib.Path(f).read_text(encoding='ascii').count('MANIFOLD_SOLID_BREP'), 2)


if __name__ == '__main__':
    unittest.main()
