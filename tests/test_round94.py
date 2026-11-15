"""Round 94 : parcours 2,5D (gravure à l'outil conique) et 3D (relief
d'image, surface d'une pièce STEP) — jamais sous la surface demandée."""
import math
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import numpy as np
from shapely.geometry import Point

from vectordrive.cam import advanced, model, strategies
from vectordrive.core import geom
from vectordrive.core.document import Document, Image, Shape
from tests.corpus import corpus

STEP = corpus('step')


def vsetup(depth, tip=0.2, angle=60):
    s = model.CamSetup(tools=[model.CamTool(name='V', kind='conique', diameter=6, angle=angle, tip=tip,
                                            step_down=1, cut_length=10)])
    op = model.Operation(kind='vcarve', tool_id=s.tools[0].id, depth=depth, resolution=0.05)
    s.operations = [op]
    return s, op


class TestVcarve(unittest.TestCase):
    def check_no_gouge(self, d, tp, tip, angle):
        reg = strategies.region([it.path for it in d.layers[0].items], 0.01)
        t = math.tan(math.radians(angle) / 2)
        for m in tp.moves:
            if m.z < 0:
                inset = reg.exterior.distance(Point(m.x, m.y))
                for hole in getattr(reg, 'interiors', []):
                    inset = min(inset, hole.distance(Point(m.x, m.y)))
                self.assertGreaterEqual(m.z, -(max(0.0, inset - tip / 2)) / t - 1e-3)
                self.assertTrue(reg.buffer(1e-6).contains(Point(m.x, m.y)))

    def test_deep_v_follows_cone(self):
        d = Document()
        d.layers[0].items.append(Shape(path=geom.Path([geom.rect(0, 0, 10, 4)])))
        s, op = vsetup(depth=5)
        tp = strategies.compute(d, s, op)
        self.check_no_gouge(d, tp, 0.2, 60)
        zmin = min(m.z for m in tp.moves)
        self.assertAlmostEqual(zmin, -(2 - 0.1) / math.tan(math.radians(30)), delta=0.1)   # au milieu : le plus profond

    def test_flat_bottom_when_capped(self):
        d = Document()
        d.layers[0].items.append(Shape(path=geom.Path([geom.rect(0, 0, 20, 12), geom.circle((10, 6), 2)])))
        s, op = vsetup(depth=0.8)
        tp = strategies.compute(d, s, op)
        self.check_no_gouge(d, tp, 0.2, 60)
        zs = [m.z for m in tp.moves if m.z < 0]
        self.assertAlmostEqual(min(zs), -0.8, places=9)
        self.assertGreater(sum(1 for z in zs if abs(z + 0.8) < 1e-9), 20)   # fond plat vidé

    def test_needs_v_bit(self):
        d = Document()
        d.layers[0].items.append(Shape(path=geom.Path([geom.rect(0, 0, 10, 4)])))
        s, op = vsetup(depth=1)
        s.tools[0].kind = 'fraise'
        tp = strategies.compute(d, s, op)
        self.assertEqual(tp.moves, [])
        self.assertTrue(any('conique' in w for w in tp.warnings))


class TestCompensation(unittest.TestCase):
    def test_profiles(self):
        ball = model.CamTool(kind='boule', diameter=2)
        cone = model.CamTool(kind='conique', diameter=6, angle=90, tip=0.0)
        flat = model.CamTool(kind='fraise', diameter=2)
        d = np.array([0.0, 0.5, 1.0, 1.5])
        self.assertTrue(np.allclose(advanced.tool_profile(ball, d)[:3], [0, 1 - math.sqrt(0.75), 1]))
        self.assertTrue(np.isinf(advanced.tool_profile(ball, d)[3]))
        self.assertTrue(np.allclose(advanced.tool_profile(cone, d), [0, 0.5, 1.0, 1.5]))
        self.assertTrue(np.allclose(advanced.tool_profile(flat, d)[:3], 0))

    def test_flat_tool_cannot_enter_narrow_hole(self):
        H = np.zeros((21, 21))
        H[10, 10] = -5                                         # trou d'un point
        T = advanced.compensate(H, 0.1, model.CamTool(kind='fraise', diameter=1))
        self.assertEqual(T[10, 10], 0.0)
        # cône pointu à 90° : la pointe descend de 0,1 mm (voisins à 0,1 mm de l'axe)
        T = advanced.compensate(H, 0.1, model.CamTool(kind='conique', diameter=6, angle=90))
        self.assertAlmostEqual(T[10, 10], -0.1, places=9)

    def test_heightmap_from_mesh(self):
        A, B, C, D, E = (0, 0, 0), (20, 0, 0), (20, 20, 0), (0, 20, 0), (10, 10, 5)
        tris = np.array([[A, B, E], [B, C, E], [C, D, E], [D, A, E]], dtype=float)
        H = advanced.heightmap_from_triangles(tris, 0, 0, 21, 21, 1.0)
        self.assertEqual((H[10, 10], H[10, 5], H[0, 0]), (5.0, 2.5, 0.0))
        H = advanced.heightmap_from_triangles(tris, -5, -5, 31, 31, 1.0)
        self.assertTrue(np.isneginf(H[0, 0]))                    # hors de la pièce


class TestRelief(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def dome(self, invert=False):
        from PySide6.QtCore import QBuffer, QByteArray, QIODevice
        from PySide6.QtGui import QColor, QImage
        n = 100
        q = QImage(n, n, QImage.Format.Format_Grayscale8)
        for y in range(n):
            for x in range(n):
                r = math.hypot(x - n / 2, y - n / 2) / (n / 2)
                v = max(0.0, 1 - r)
                q.setPixelColor(x, y, QColor.fromRgbF(v, v, v))
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        q.save(buf, 'PNG')
        d = Document()
        d.layers[0].items.append(Image(data=bytes(ba), fmt='png', matrix=geom.Affine(20, 0, 0, -20, 0, 20)))
        return d

    def test_relief_never_below_surface(self):
        d = self.dome()
        for kind in ('boule', 'fraise', 'conique'):
            s = model.CamSetup(tools=[model.CamTool(kind=kind, diameter=2, angle=60, step_down=2, stepover=0.2,
                                                    cut_length=10)])
            op = model.Operation(kind='relief', tool_id=s.tools[0].id, depth=3, resolution=0.2)
            s.operations = [op]
            tp = strategies.compute(d, s, op)
            self.assertTrue(tp.moves, kind)
            for m in tp.moves:
                if m.kind != 'rapid':
                    surf = -(1 - max(0.0, 1 - math.hypot(m.x - 10, m.y - 10) / 10)) * 3
                    self.assertGreaterEqual(m.z, surf - 0.08, (kind, m))
            self.assertAlmostEqual(min(m.z for m in tp.moves), -3.0, places=6)
            self.assertGreater(max(m.z for m in tp.moves if m.kind != 'rapid'), -0.3)  # sommet du dôme

    def test_no_image(self):
        d = Document()
        d.layers[0].items.append(Shape(path=geom.Path([geom.rect(0, 0, 5, 5)])))
        s = model.CamSetup(tools=[model.CamTool(kind='boule', diameter=2)])
        op = model.Operation(kind='relief', tool_id=s.tools[0].id, depth=1)
        s.operations = [op]
        tp = strategies.compute(d, s, op)
        self.assertTrue(any('aucune image' in w for w in tp.warnings))

    @unittest.skipUnless(STEP.is_dir(), 'pièces STEP absentes')
    def test_step_surface(self):
        f = next(STEP.rglob('*.stp'), None)
        if f is None:
            self.skipTest('pas de .stp')
        s = model.CamSetup(tools=[model.CamTool(kind='boule', diameter=3, step_down=3, stepover=0.3,
                                                cut_length=20)])
        op = model.Operation(kind='surface3d', tool_id=s.tools[0].id, depth=4, resolution=0.3, model_path=str(f))
        s.operations = [op]
        tp = strategies.compute(Document(), s, op)
        self.assertTrue(tp.moves)
        self.assertAlmostEqual(min(m.z for m in tp.moves), -4.0, places=6)
        self.assertLessEqual(max(m.z for m in tp.moves if m.kind != 'rapid'), 1e-9)
        self.assertIsInstance(tp.moves[5].x, float)


if __name__ == '__main__':
    unittest.main()
