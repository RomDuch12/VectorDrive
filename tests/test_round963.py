"""Round 963 : vue de dessus d'une pièce maillée — les triangles sont donnés à shapely d'un seul coup (plus d'objet
Polygon fabriqué un par un), pour le même dessin."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r963.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

import numpy as np  # noqa: E402
import shapely.geometry  # noqa: E402

from vectordrive.io import mesh3d  # noqa: E402


def plate_with_step(n: int = 30):
    """Une plaque de 60 × 40 maillée fin (dessus à Z 5), une marche de 20 × 40 plus bas (Z 2), et leurs flancs."""
    tris = []

    def quad(x0, y0, x1, y1, z):
        tris.append([(x0, y0, z), (x1, y0, z), (x1, y1, z)])
        tris.append([(x0, y0, z), (x1, y1, z), (x0, y1, z)])
    for i in range(n):
        for j in range(n):
            quad(60 * i / n, 40 * j / n, 60 * (i + 1) / n, 40 * (j + 1) / n, 5.0)
    quad(60, 0, 80, 40, 2.0)
    tris.append([(60, 0, 2), (60, 40, 2), (60, 40, 5)])                    # le flanc de la marche, vu par la tranche
    tris.append([(60, 0, 2), (60, 40, 5), (60, 0, 5)])
    return np.array(tris, float)


class TopView(unittest.TestCase):

    def test_triangles_go_to_shapely_at_once(self):
        T = plate_with_step()
        made = []
        real = shapely.geometry.Polygon

        class Counted(real):
            def __new__(cls, *a, **k):
                made.append(1)
                return real.__new__(real, *a, **k)
        with mock.patch.object(shapely.geometry, 'Polygon', Counted):
            doc = mesh3d.top_view(T, 'essai')
        self.assertEqual(len(made), 0)                                      # avant : un Polygon par triangle (1 802)
        names = [L.name for L in doc.layers]
        self.assertEqual(names, ['Pz 5', 'Pz 2', 'Silhouette'])             # le même dessin
        box = {L.name: L.items[0].path.bbox() for L in doc.layers}
        self.assertEqual(tuple(round(v, 6) for v in box['Pz 5']), (0.0, 0.0, 60.0, 40.0))
        self.assertEqual(tuple(round(v, 6) for v in box['Pz 2']), (60.0, 0.0, 80.0, 40.0))
        self.assertEqual(tuple(round(v, 6) for v in box['Silhouette']), (0.0, 0.0, 80.0, 40.0))
        self.assertEqual([len(L.items[0].path.contours) for L in doc.layers], [1, 1, 1])
        self.assertEqual(len(doc.layers[0].items[0].path.contours[0].segments), 4)      # un rectangle, pas 1 800 triangles


if __name__ == '__main__':
    unittest.main()
