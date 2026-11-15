"""Round 954 : STEP, STL et 3D XML s'écrivent — le dessin en volume (formes fermées tirées de l'épaisseur de la
plaque, volumes, reliefs). En STEP : de vrais solides, un cylindre par arc de cercle. Ils entrent dans « Enregistrer
sous » et « Exporter »."""
import math
import os
import pathlib
import tempfile
import unittest
import zipfile
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r954.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

import numpy as np  # noqa: E402
from PySide6.QtWidgets import QApplication, QFileDialog  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Plate, Shape  # noqa: E402
from vectordrive.core.geom import Contour, Cubic, Line  # noqa: E402
from vectordrive.io import companion, mesh3d, registry  # noqa: E402
from vectordrive.io import model3d as M  # noqa: E402

AREA = 40 * 20 - math.pi * 16                    # la plaquette percée d'un trou de 8


def shape(*contours):
    return Shape(path=geom.Path(list(contours)))


def drawing(thickness=5.0):
    """Une plaquette percée d'un trou rond, et une goutte (deux courbes de Bézier) à côté."""
    d = Document()
    d.plate = Plate(width=120, height=60, thickness=thickness)
    drop = Contour([Cubic((70.0, 10.0), (90.0, 10.0), (90.0, 30.0), (70.0, 30.0)),
                    Cubic((70.0, 30.0), (62.0, 30.0), (62.0, 10.0), (70.0, 10.0))], True)
    d.layers[0].items += [shape(geom.rect(10, 10, 40, 20)), shape(geom.circle((30.0, 20.0), 4.0)), shape(drop)]
    return d


def volume(tris) -> float:
    t = np.asarray(tris, np.float64).reshape(-1, 3, 3)
    return abs(float(np.einsum('ij,ij->i', t[:, 0], np.cross(t[:, 1], t[:, 2])).sum()) / 6)


def area(contour) -> float:
    return abs(contour.signed_area())


def top_area(m) -> float:
    """Aire des faces du dessus (Z 0) du modèle relu : celle du dessin, quel que soit le sens des triangles."""
    t = np.asarray(m.triangles, np.float64).reshape(-1, 3, 3)
    t = t[np.abs(t[:, :, 2]).max(axis=1) < 1e-6]
    return float(np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1).sum() / 2)


def writes(ext: str) -> bool:
    f = registry.writer_for('piece' + ext)
    return f is not None and f.writer is not None


class Step(unittest.TestCase):

    def test_step_is_a_real_solid(self):
        self.assertTrue(writes('.step') and writes('.stp'), 'le STEP n\'est que lu')           # avant
        d = drawing()
        drop = area(d.layers[0].items[2].path.contours[0])
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'piece.step')
            registry.save_document(d, f)
            text = pathlib.Path(f).read_text(encoding='ascii')
            self.assertEqual(text.count('MANIFOLD_SOLID_BREP'), 2)          # la plaquette et son trou ; la goutte
            self.assertEqual(text.count('CYLINDRICAL_SURFACE'), 4)          # le trou rond : quatre quarts de cylindre
            self.assertEqual(text.count('SURFACE_OF_LINEAR_EXTRUSION'), 2)  # les deux courbes de la goutte
            self.assertEqual(text.count("PLANE('"), 4 + 2 * 2)              # quatre flancs droits, dessus et dessous
            m = M.load(f)
            T = np.asarray(m.triangles, float).reshape(-1, 3)
            self.assertTrue(np.allclose([T[:, 2].min(), T[:, 2].max()], [-5.0, 0.0], atol=1e-6))   # dessus à Z 0
            self.assertTrue(np.allclose([T[:, 0].min(), T[:, 1].min()], [10.0, 10.0], atol=1e-3))
            self.assertAlmostEqual(top_area(m), AREA + drop, delta=(AREA + drop) * 0.004)     # le trou est un trou
            self.assertEqual(len(set(m.body_ids().tolist())), 2)
            self.assertTrue(any('en volume' in r and '5 mm' in r for r in d.report))

    def test_touching_or_crossing_contours_are_merged_first(self):
        self.assertTrue(writes('.step'), 'le STEP n\'est que lu')                              # avant
        d = Document()                                    # sans épaisseur de plaque : 3 mm
        d.layers[0].items += [shape(geom.rect(0, 0, 30, 20)), shape(geom.rect(20, 10, 30, 20))]
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'croix.stp')
            registry.save_document(d, f)
            text = pathlib.Path(f).read_text(encoding='ascii')
            self.assertEqual(text.count('MANIFOLD_SOLID_BREP'), 2)          # pair-impair : la partie commune est vide
            m = M.load(f)
            self.assertAlmostEqual(top_area(m), 2 * 600 - 2 * 100, delta=0.5)
            self.assertAlmostEqual(float(np.asarray(m.triangles)[..., 2].min()), -3.0, places=6)
        from vectordrive.io import write3d
        empty = Document()
        empty.layers[0].items.append(shape(Contour([Line((0.0, 0.0), (10.0, 5.0))], False)))
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(write3d.Nothing3D):
            registry.save_document(empty, os.path.join(tmp, 'rien.step'))   # un trait ouvert : rien à tirer

    def test_volumes_go_as_they_are(self):
        self.assertTrue(writes('.step'), 'le STEP n\'est que lu')                              # avant
        from vectordrive.core import solids as SO
        if not SO.available():
            self.skipTest('manifold3d absent')
        d = Document()
        d.layers[0].items.append(SO.make_shape(SO.box(0, 0, 0, 10, 20, 30)))
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('bloc.step', 'bloc.stl', 'bloc.3dxml'):
                f = os.path.join(tmp, name)
                registry.save_document(d, f)
                self.assertAlmostEqual(volume(M.load(f).triangles), 6000.0, delta=1.0, msg=name)


class Meshes(unittest.TestCase):

    def test_stl_and_3dxml(self):
        self.assertTrue(writes('.stl') and writes('.3dxml'), 'STL et 3D XML ne sont que lus')    # avant
        d = drawing()
        drop = area(d.layers[0].items[2].path.contours[0])
        want = (AREA + drop) * 5.0
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'piece.stl')
            registry.save_document(d, f)
            T = mesh3d.read_stl(f)
            self.assertAlmostEqual(volume(T), want, delta=want * 0.002)
            self.assertAlmostEqual(float(T[:, :, 2].max()), 0.0, places=6)
            g = os.path.join(tmp, 'piece.3dxml')
            registry.save_document(d, g)
            with zipfile.ZipFile(g) as z:
                names = z.namelist()
                self.assertEqual(names[0], 'Manifest.xml')
                self.assertIn(b'<Root>piece.3dxml</Root>', z.read('Manifest.xml'))
                self.assertIn(b'PolygonalRepType', z.read('piece.3DRep'))
            X = mesh3d.read_3dxml(g)
            self.assertEqual(len(X), len(T))
            self.assertAlmostEqual(volume(X), want, delta=want * 0.002)
            back = registry.open_document(f)                                # relu : la vue de dessus de la pièce
            self.assertTrue(any(L.items for L in back.layers))
            cp, why = companion.sync(d, f)                                  # le dessin lui-même : dans le compagnon
            self.assertEqual(cp.name, 'piece.stl.vdz')
            self.assertIn('volume', ' '.join(why))


class Window(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def test_save_as_and_export_offer_the_3d_formats(self):
        from vectordrive.ui import export_dialog as E
        w = self.w
        w.new_document()
        for it in drawing().layers[0].items:
            w.canvas.doc.add(it)
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, 'plaquette.step')
            with mock.patch.object(QFileDialog, 'getSaveFileName', return_value=(out, '')) as ask:
                w.save_as()
            offered = ask.call_args[0][3]
            self.assertIn('STEP (le dessin en volume) (*.stp *.step)', offered)                # avant : pas proposé
            self.assertIn('STL / 3D XML (le dessin en volume) (*.stl *.3dxml)', offered)
            self.assertIn('IGES (*.igs *.iges)', offered)                   # avant : « IGES (vue de dessus) »
            self.assertNotIn('vue de dessus', offered)
            self.assertTrue(os.path.isfile(out))
            self.assertTrue(companion.is_companion(out + '.vdz'))
            self.assertIn('en volume', w.statusBar().currentMessage())
            ok, report = E.verify_export(out, expected=3)                   # avant : « 1 objet relu sur 3 »
            self.assertTrue(ok, report)
            self.assertIn('triangles', report)
        self.assertIn('step', [f.key for f in E.formats()])
        w.modified = False


if __name__ == '__main__':
    unittest.main()
