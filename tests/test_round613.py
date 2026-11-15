"""Round 613 : STEP — surface extrudée (SURFACE_OF_LINEAR_EXTRUSION) maillée sur toute sa hauteur : le vecteur
d'extrusion n'en donne que l'unité, la plage vient du contour de la face (avant : faces de plus de 3 fois le
vecteur laissées vides, des trous dans la pièce usinée)."""
import pathlib
import tempfile
import unittest

import numpy as np

from vectordrive.io.neostep import step3d

#: une face extrudée de 10 mm de haut, sur une courbe B-spline (arc parabolique de 0 à 20 en X), vecteur 1 mm
STEP_EXTRUSION = """ISO-10303-21;
HEADER;
FILE_DESCRIPTION((''),'2;1');
FILE_NAME('extrusion.stp','',(''),(''),'','','');
FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));
ENDSEC;
DATA;
#1=CARTESIAN_POINT('',(0.,0.,0.));
#2=CARTESIAN_POINT('',(10.,10.,0.));
#3=CARTESIAN_POINT('',(20.,0.,0.));
#4=CARTESIAN_POINT('',(0.,0.,{h}));
#5=CARTESIAN_POINT('',(10.,10.,{h}));
#6=CARTESIAN_POINT('',(20.,0.,{h}));
#10=B_SPLINE_CURVE_WITH_KNOTS('',2,(#1,#2,#3),.UNSPECIFIED.,.F.,.F.,(3,3),(0.,1.),.UNSPECIFIED.);
#11=B_SPLINE_CURVE_WITH_KNOTS('',2,(#4,#5,#6),.UNSPECIFIED.,.F.,.F.,(3,3),(0.,1.),.UNSPECIFIED.);
#20=DIRECTION('',(0.,0.,1.));
#21=VECTOR('',#20,1.);
#22=LINE('',#1,#21);
#23=LINE('',#3,#21);
#30=VERTEX_POINT('',#1);
#31=VERTEX_POINT('',#3);
#32=VERTEX_POINT('',#6);
#33=VERTEX_POINT('',#4);
#40=EDGE_CURVE('',#30,#31,#10,.T.);
#41=EDGE_CURVE('',#31,#32,#23,.T.);
#42=EDGE_CURVE('',#33,#32,#11,.T.);
#43=EDGE_CURVE('',#30,#33,#22,.T.);
#50=ORIENTED_EDGE('',*,*,#40,.T.);
#51=ORIENTED_EDGE('',*,*,#41,.T.);
#52=ORIENTED_EDGE('',*,*,#42,.F.);
#53=ORIENTED_EDGE('',*,*,#43,.F.);
#60=EDGE_LOOP('',(#50,#51,#52,#53));
#61=FACE_OUTER_BOUND('',#60,.T.);
#70=SURFACE_OF_LINEAR_EXTRUSION('',#10,#21);
#71=ADVANCED_FACE('',(#61),#70,.T.);
#80=OPEN_SHELL('',(#71));
#81=SHELL_BASED_SURFACE_MODEL('',(#80));
#82=AXIS2_PLACEMENT_3D('',#1,$,$);
#83=( LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.) );
#84=( GEOMETRIC_REPRESENTATION_CONTEXT(3) GLOBAL_UNIT_ASSIGNED_CONTEXT((#83)) REPRESENTATION_CONTEXT('','') );
#85=MANIFOLD_SURFACE_SHAPE_REPRESENTATION('',(#81,#82),#84);
ENDSEC;
END-ISO-10303-21;
"""


def curve_length(n=20000):
    t = np.linspace(0, 1, n)[:, None]
    P = (1 - t) ** 2 * np.array([0, 0]) + 2 * t * (1 - t) * np.array([10, 10]) + t ** 2 * np.array([20, 0])
    return float(np.linalg.norm(np.diff(P, axis=0), axis=1).sum())


class TestExtrusion(unittest.TestCase):
    def read(self, h):
        f = pathlib.Path(tempfile.mkdtemp()) / 'extrusion.stp'
        f.write_text(STEP_EXTRUSION.replace('{h}', f'{h:.1f}'), encoding='latin-1')
        return step3d.lire_modele(str(f))

    def test_tall_face_meshed(self):
        for h in (10.0, 80.0):
            m = self.read(h)
            self.assertEqual((m.n_faces, m.n_faces_maillees), (1, 1), m.notes)
            z = m.triangles[:, :, 2]
            self.assertAlmostEqual(float(z.min()), 0.0, 6)
            self.assertAlmostEqual(float(z.max()), h, 6)
            self.assertAlmostEqual(m.aire(), curve_length() * h, delta=0.002 * curve_length() * h)

    def test_range(self):
        C = np.array([[0, 0, 0.0], [20, 0, 0]])
        D = np.array([0, 0, 2.0])
        v0, v1 = step3d._plage_extrusion(C, D, [(np.array([[0, 0, -4.0], [20, 0, 30]]), True)])
        self.assertLess(v0, -2.0)                                           # −4 mm = −2 vecteurs
        self.assertGreater(v1, 15.0)
        self.assertLess(v1, 17.0)
        self.assertEqual(step3d._plage_extrusion(C, D, None), (-2.0, 3.0))  # sans contour : comme avant


if __name__ == '__main__':
    unittest.main()
