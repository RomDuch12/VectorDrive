"""Round 130 : vrai mode 3D — le modèle 3D du fichier ouvert (STEP : toute la
pièce, faces, arêtes, couleurs ; STL / 3D XML : triangles et arêtes vives)
dans le plan de travail en mode 3D, pas seulement les calques de la vue de
dessus."""
import os
import pathlib
import struct
import tempfile
import unittest

import numpy as np

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from tests.corpus import corpus
from vectordrive.io import model3d as M
from vectordrive.ui import view3d as V3

CUBE_V = np.array([[x, y, z] for x in (0, 10) for y in (0, 10) for z in (0, 10)], float)
CUBE_F = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1),
          (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]


def cube_stl(path):
    tris = CUBE_V[np.array(CUBE_F)].astype(np.float32)
    with open(path, 'wb') as fh:
        fh.write(b'\0' * 80 + struct.pack('<I', len(tris)))
        for t in tris:
            fh.write(struct.pack('<3f', 0, 0, 0) + t.tobytes() + b'\0\0')


STEP_BOX = """ISO-10303-21;
HEADER;
FILE_DESCRIPTION((''),'2;1');
FILE_NAME('cube.stp','',(''),(''),'','','');
FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));
ENDSEC;
DATA;
#1=CARTESIAN_POINT('',(0.,0.,0.));
#2=CARTESIAN_POINT('',(20.,0.,0.));
#3=CARTESIAN_POINT('',(20.,10.,0.));
#4=CARTESIAN_POINT('',(0.,10.,0.));
#5=CARTESIAN_POINT('',(0.,0.,5.));
#6=CARTESIAN_POINT('',(20.,0.,5.));
#7=CARTESIAN_POINT('',(20.,10.,5.));
#8=CARTESIAN_POINT('',(0.,10.,5.));
#11=POLY_LOOP('',(#1,#4,#3,#2));
#12=POLY_LOOP('',(#5,#6,#7,#8));
#13=POLY_LOOP('',(#1,#2,#6,#5));
#14=POLY_LOOP('',(#2,#3,#7,#6));
#15=POLY_LOOP('',(#3,#4,#8,#7));
#16=POLY_LOOP('',(#4,#1,#5,#8));
#21=FACE_OUTER_BOUND('',#11,.T.);
#22=FACE_OUTER_BOUND('',#12,.T.);
#23=FACE_OUTER_BOUND('',#13,.T.);
#24=FACE_OUTER_BOUND('',#14,.T.);
#25=FACE_OUTER_BOUND('',#15,.T.);
#26=FACE_OUTER_BOUND('',#16,.T.);
#31=FACE('',(#21));
#32=FACE('',(#22));
#33=FACE('',(#23));
#34=FACE('',(#24));
#35=FACE('',(#25));
#36=FACE('',(#26));
#40=CLOSED_SHELL('',(#31,#32,#33,#34,#35,#36));
#41=FACETED_BREP('',#40);
#42=AXIS2_PLACEMENT_3D('',#1,$,$);
#43=( LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.) );
#44=( GEOMETRIC_REPRESENTATION_CONTEXT(3) GLOBAL_UNIT_ASSIGNED_CONTEXT((#43)) REPRESENTATION_CONTEXT('','') );
#45=FACETED_BREP_SHAPE_REPRESENTATION('',(#41,#42),#44);
ENDSEC;
END-ISO-10303-21;
"""


class TestModel(unittest.TestCase):
    def test_sharp_edges_of_a_cube(self):
        tris = CUBE_V[np.array(CUBE_F)]
        self.assertEqual(M.sharp_edges(tris).shape, (12, 2, 3))         # diagonales exclues
        flat = tris[:2]
        self.assertEqual(M.sharp_edges(flat).shape, (4, 2, 3))          # bords

    def test_stl_model(self):
        tmp = pathlib.Path(tempfile.mkdtemp()) / 'cube.stl'
        cube_stl(tmp)
        m = M.load(tmp)
        self.assertEqual(m.triangles.shape, (12, 3, 3))
        self.assertEqual(len(m.segments), 12)
        self.assertEqual(m.bounds(), (0.0, 0.0, 0.0, 10.0, 10.0, 10.0))
        self.assertIn('10.00 × 10.00 × 10.00 mm', m.summary())

    def test_step_model(self):
        tmp = pathlib.Path(tempfile.mkdtemp()) / 'pave.stp'
        tmp.write_text(STEP_BOX, encoding='latin-1')
        m = M.load(tmp)
        self.assertGreaterEqual(len(m.triangles), 12)
        self.assertEqual(tuple(round(v, 6) for v in m.bounds()), (0.0, 0.0, 0.0, 20.0, 10.0, 5.0))

    def test_arrays_for_opengl(self):
        tmp = pathlib.Path(tempfile.mkdtemp()) / 'cube.stl'
        cube_stl(tmp)
        tri, edge = V3.model_arrays(M.load(tmp))
        self.assertEqual(tri.shape, (36, 9))
        self.assertEqual(edge.shape, (24, 9))
        self.assertEqual(tri.dtype, np.float32)
        n = tri[:, 3:6]
        self.assertTrue(np.allclose(np.linalg.norm(n, axis=1), 1.0))    # normales unitaires

    @unittest.skipUnless((corpus('step') / 'Fix on wall' / 'base_wall_mount_vc.stp').is_file(),
                         'STEP d\'accroche murale absent')
    def test_wall_mount(self):
        m = M.load(corpus('step') / 'Fix on wall' / 'base_wall_mount_vc.stp')
        self.assertEqual(m.faces, 54)
        x0, y0, z0, x1, y1, z1 = m.bounds()
        self.assertAlmostEqual(x1 - x0, 35.0, places=3)
        self.assertAlmostEqual(z1 - z0, 8.0, places=3)


class TestPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_step_document_shows_model(self):
        from vectordrive.ui.main_window import MainWindow
        tmp = pathlib.Path(tempfile.mkdtemp()) / 'pave.stp'
        tmp.write_text(STEP_BOX, encoding='latin-1')
        w = MainWindow()
        try:
            self.assertTrue(w.open_path(str(tmp)))
            w.set_view_mode('3d')
            p = w.panel3d
            self.assertIsNotNone(p.view.model)                           # modèle, pas le relief
            self.assertIsNone(p.view.relief)
            self.assertIn('Modèle 3D', p.info.text())
            self.assertFalse(p.exag.isEnabled())
            self.assertEqual(tuple(round(v, 6) for v in p.view.bounds()), (0.0, 0.0, 0.0, 20.0, 10.0, 5.0))
            first = p.model
            p.stale = True
            p.refresh()
            self.assertIs(p.model, first)                                # pas relu : même fichier
            img = p.view.grab()                                          # sans OpenGL : arêtes projetées
            self.assertFalse(img.isNull())
            # source « dessin » : le relief revient
            i = p.source.findData('dessin')
            p.source.setCurrentIndex(i)
            self.assertIsNone(p.view.model)
            self.assertTrue(p.exag.isEnabled())
        finally:
            w.modified = False
            w.close()

    def test_drawing_without_3d_file(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.set_view_mode('3d')
            self.assertIsNone(w.panel3d.view.model)                      # relief du dessin, comme avant
            i = w.panel3d.source.findData('modele')
            w.panel3d.source.setCurrentIndex(i)
            self.assertIn('fichier 3D', w.panel3d.info.text())
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
