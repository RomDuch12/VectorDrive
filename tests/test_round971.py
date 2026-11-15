"""Round 971 : STEP — les courbes libres d'un « fil de fer » (GEOMETRIC_CURVE_SET, sans une face) sont lues, en
courbes exactes ; un tel fichier s'ouvrait vide."""
import math
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r971.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from vectordrive.core.geom import Conic, Cubic, Line  # noqa: E402
from vectordrive.io import step  # noqa: E402

HEAD = """ISO-10303-21;
HEADER;
FILE_DESCRIPTION((''),'2;1');
FILE_NAME('essai','2026-11-11T00:00:00',(''),(''),'','','');
FILE_SCHEMA(('CONFIG_CONTROL_DESIGN'));
ENDSEC;
DATA;
"""
UNIT = "#900=(LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.{0}.,.METRE.));\n"
TAIL = "ENDSEC;\nEND-ISO-10303-21;\n"


def point(n, x, y, z=0.0):
    return f"#{n}=CARTESIAN_POINT('',({x:.6f},{y:.6f},{z:.6f}));\n"


def read(body: str, unit: str = 'MILLI'):
    path = pathlib.Path(tempfile.mkdtemp()) / 'fil.step'
    path.write_text(HEAD + body + UNIT.format(unit) + TAIL, encoding='latin-1')
    return step.read(path)


def shapes(doc):
    return [it for L in doc.layers if L.name == 'STEP courbes' for it in L.items]


def told(doc):
    return [([type(s).__name__ for s in c.segments], c.closed) for it in shapes(doc) for c in it.path.contours]


class Wire(unittest.TestCase):

    def test_bsplines_of_a_curve_set_are_read_exactly(self):
        body = (point(1, 0, 0) + point(2, 10, 20) + point(3, 30, 20) + point(4, 40, 0)
                + "#10=B_SPLINE_CURVE_WITH_KNOTS('',3,(#1,#2,#3,#4),.UNSPECIFIED.,.F.,.U.,(4,4),(0.,1.),.UNSPECIFIED.);\n"
                + point(11, 50, 0) + point(12, 70, 0) + point(13, 70, 20) + point(14, 50, 20) + point(15, 50, 0)
                + "#20=B_SPLINE_CURVE_WITH_KNOTS('',1,(#11,#12,#13,#14,#15),.UNSPECIFIED.,.T.,.U.,(2,1,1,1,2),"
                  "(0.,1.,2.,3.,4.),.UNSPECIFIED.);\n"
                + point(21, 110, 0) + point(22, 110, 10) + point(23, 100, 10)
                + "#30=(BOUNDED_CURVE() B_SPLINE_CURVE(2,(#21,#22,#23),.UNSPECIFIED.,.F.,.U.) "
                  "B_SPLINE_CURVE_WITH_KNOTS((3,3),(0.,1.),.UNSPECIFIED.) CURVE() GEOMETRIC_REPRESENTATION_ITEM() "
                  "RATIONAL_B_SPLINE_CURVE((1.,0.707106781186548,1.)) REPRESENTATION_ITEM(''));\n"
                + "#70=GEOMETRIC_CURVE_SET('',(#10,#20,#30));\n")
        doc = read(body)
        self.assertEqual(told(doc), [(['Cubic'], False), (['Line'] * 4, True), (['Conic'], False)])   # avant : rien
        cubic = shapes(doc)[0].path.contours[0].segments[0]
        self.assertIsInstance(cubic, Cubic)
        self.assertEqual([tuple(round(v, 6) for v in p) for p in (cubic.p0, cubic.p1, cubic.p2, cubic.p3)],
                         [(0, 0), (10, 20), (30, 20), (40, 0)])
        arc = shapes(doc)[2].path.contours[0].segments[0]
        self.assertIsInstance(arc, Conic)
        mid = arc.point(0.5)
        self.assertAlmostEqual(math.hypot(mid[0] - 100, mid[1]), 10.0, places=6)        # un vrai quart de cercle
        self.assertTrue(any('3 courbe(s) libre(s)' in r for r in doc.report), doc.report)
        box = read(body, 'CENTI').bbox(include_plate=False)                             # les unités du fichier
        self.assertAlmostEqual(box[2] - box[0], 1100.0, places=4)

    def test_lines_circles_polylines_and_composites(self):
        body = (point(31, 0, 30) + point(32, 10, 40) + point(33, 20, 30) + "#40=POLYLINE('',(#31,#32,#33));\n"
                + point(41, 0, 50) + "#42=DIRECTION('',(1.,0.,0.));\n#43=VECTOR('',#42,1.);\n#44=LINE('',#41,#43);\n"
                + point(45, 0, 50) + point(46, 25, 50) + "#50=TRIMMED_CURVE('',#44,(#45),(#46),.T.,.CARTESIAN.);\n"
                + point(51, 60, 60) + "#53=DIRECTION('',(0.,0.,1.));\n#54=DIRECTION('',(1.,0.,0.));\n"
                + "#52=AXIS2_PLACEMENT_3D('',#51,#53,#54);\n#55=CIRCLE('',#52,8.);\n"
                + point(56, 90, 60) + "#57=AXIS2_PLACEMENT_3D('',#56,#53,#54);\n#58=CIRCLE('',#57,5.);\n"
                + "#60=TRIMMED_CURVE('',#58,(PARAMETER_VALUE(0.)),(PARAMETER_VALUE(3.14159265358979)),.T.,.PARAMETER.);\n"
                + "#61=ELLIPSE('',#52,8.,4.);\n"
                + point(62, 120, 30) + point(63, 140, 30) + point(64, 140, 50)
                + "#65=POLYLINE('',(#62,#63));\n#66=POLYLINE('',(#64,#63));\n"
                + "#67=COMPOSITE_CURVE_SEGMENT(.CONTINUOUS.,.T.,#65);\n#68=COMPOSITE_CURVE_SEGMENT(.CONTINUOUS.,.F.,#66);\n"
                + "#69=COMPOSITE_CURVE('',(#67,#68),.F.);\n"
                + "#70=GEOMETRIC_SET('',(#40,#50,#55,#60,#61,#69,#31));\n")
        doc = read(body)
        self.assertEqual(told(doc), [(['Line', 'Line'], False),           # polyligne
                                     (['Line'], False),                  # droite bornée par deux points
                                     (['Conic'] * 4, True),              # cercle entier
                                     (['Conic'] * 2, False),             # demi-cercle borné par ses angles
                                     (['Line', 'Line'], False)])         # composite : le second morceau retourné
        half = shapes(doc)[3].path.contours[0]
        self.assertEqual([round(v, 6) for v in (*half.start, *half.end)], [95, 60, 85, 60])
        self.assertAlmostEqual(half.segments[0].point(0.5)[1], 60 + 5 * math.sin(math.pi / 4), places=6)   # par le haut
        line = shapes(doc)[1].path.contours[0].segments[0]
        self.assertIsInstance(line, Line)
        self.assertEqual((line.p0, line.p1), ((0.0, 50.0), (25.0, 50.0)))
        comp = shapes(doc)[4].path.contours[0]
        self.assertEqual((comp.start, comp.end), ((120.0, 30.0), (140.0, 50.0)))
        self.assertTrue(any('1 courbe(s) libre(s) d’un type non lu' in r for r in doc.report), doc.report)   # l'ellipse
        alone = read(point(1, 0, 0) + point(2, 10, 0) + "#40=POLYLINE('',(#1,#2));\n")   # une courbe hors de tout jeu
        self.assertEqual(shapes(alone), [])
        self.assertFalse(any('libre' in r for r in alone.report), alone.report)


if __name__ == '__main__':
    unittest.main()
