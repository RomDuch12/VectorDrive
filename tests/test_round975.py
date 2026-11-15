"""Round 975 : DXF écrits — au choix, les courbes en arcs de cercle raccordés (droites et arcs : lus de même par
tous les logiciels) au lieu de SPLINE exactes ; réglage F10 › Fichiers, SPLINE d'office."""
import collections
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r975.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

import ezdxf  # noqa: E402
import shapely  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from shapely.geometry import LineString  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Shape  # noqa: E402
from vectordrive.core.geom import Contour, Cubic  # noqa: E402
from vectordrive.io import colors, dxf  # noqa: E402

BLOB = Contour([Cubic((20, 10), (45, 0), (60, 25), (50, 40)), Cubic((50, 40), (40, 55), (10, 50), (10, 30)),
                Cubic((10, 30), (10, 20), (12, 14), (20, 10))], True)
WAVE = Contour([Cubic((70, 15), (85, 45), (100, -15), (115, 15)), Cubic((115, 15), (125, 35), (135, 35), (145, 15))], False)


def drawing():
    d = Document()
    for c in (BLOB, WAVE, geom.circle((170.0, 25.0), 10.0), geom.rect(190, 10, 20, 30)):
        d.layers[0].items.append(Shape(path=geom.Path([c])))
    return d


def written():
    path = pathlib.Path(tempfile.mkdtemp()) / 'courbes.dxf'
    dxf.write(drawing(), path)
    kinds = collections.Counter(e.dxftype() for e in ezdxf.readfile(str(path)).modelspace())
    return path, dict(kinds)


class Curves(unittest.TestCase):

    def tearDown(self):
        colors.DXF_ARCS = False

    def test_arcs_are_lines_and_arcs_close_to_the_curves(self):
        colors.DXF_ARCS = True
        path, kinds = written()
        self.assertEqual(kinds, {'LWPOLYLINE': 3, 'CIRCLE': 1})            # avant : 2 SPLINE, quel que soit le réglage
        back = dxf.read(path)
        got = [c for L in back.layers for it in L.items for c in it.path.contours]
        self.assertEqual(sorted(c.closed for c in got), [False, True, True, True])
        for want in (BLOB, WAVE):
            line = LineString(want.flatten(0.0005))
            near = min(got, key=lambda c: abs(c.bbox()[0] - want.bbox()[0]) + abs(c.bbox()[1] - want.bbox()[1]))
            pts = shapely.points(near.flatten(0.0005))
            self.assertLess(float(max(shapely.distance(pts, line))), 0.008)         # à la tolérance des arcs
            self.assertAlmostEqual(LineString(near.flatten(0.0005)).length, line.length, delta=0.05)
            self.assertEqual(near.closed, want.closed)

    def test_splines_stay_the_default_and_the_setting_switches(self):
        from vectordrive.ui import options
        from vectordrive.ui.main_window import MainWindow
        self.assertEqual(written()[1], {'SPLINE': 2, 'CIRCLE': 1, 'LWPOLYLINE': 1})
        self.assertEqual(options.default_of(options.BY_KEY['export/dxf_courbes']), 'splines')
        w = MainWindow()
        try:
            self.assertFalse(colors.DXF_ARCS)
            w.settings.setValue('export/dxf_courbes', 'arcs')
            w.apply_options()
            self.assertTrue(colors.DXF_ARCS)
            self.assertNotIn('SPLINE', written()[1])
        finally:
            w.settings.setValue('export/dxf_courbes', 'splines')
            w.apply_options()
            w.modified = False
            w.close()
        self.assertFalse(colors.DXF_ARCS)


if __name__ == '__main__':
    unittest.main()
