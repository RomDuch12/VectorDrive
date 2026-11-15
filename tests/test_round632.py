"""Round 632 : contrôle du programme écrit — relu (cam.ncread) et comparé aux
parcours dans les deux sens ; un arc dans le mauvais sens ou un mouvement
perdu est signalé avec sa position ; contrôle sauté quand la relecture ne peut
pas être exacte (cycles de la machine, axe rotatif, laser en morceaux)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import arcfit, model, postcheck, strategies
from vectordrive.cam.post import shifted
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def paths():
    d = Document()
    d.plate = None
    d.add(Shape(path=geom.Path([geom.rect(0, 0, 30, 15, 4)]), tool=0))
    d.add(Shape(path=geom.Path([geom.circle((45, 7), 5)]), tool=0))
    s = model.CamSetup()
    t = model.CamTool(name='F1', diameter=1, number=1, cut_length=10, step_down=0.5)
    s.tools = [t]
    s.operations = [model.Operation(kind='contour', tool_id=t.id, sources=[0], depth=1.0)]
    return s, strategies.compute_all(d, s)


def gcode(tps, origin=None):
    """Petit post G-code (I J relatifs) des parcours ajustés en arcs."""
    out = ['%', 'G90 G21']
    src = shifted(tps, origin) if origin else tps
    prev = None
    for tp in arcfit.fit_toolpaths(src, 0.01):
        for m in tp.moves:
            g = {'rapid': 'G0', 'feed': 'G1', 'plunge': 'G1', 'arc_cw': 'G2', 'arc_ccw': 'G3'}[m.kind]
            line = f'{g} X{m.x:.3f} Y{m.y:.3f} Z{m.z:.3f}'
            if m.is_arc:
                line += f' I{m.cx - prev[0]:.3f} J{m.cy - prev[1]:.3f}'
            out.append(line)
            prev = (m.x, m.y)
    return '\n'.join(out + ['M30', '%']) + '\n'


class TestVerify(unittest.TestCase):
    def setUp(self):
        self.s, self.tps = paths()

    def test_good_program(self):
        self.assertEqual(postcheck.verify([('p.nc', gcode(self.tps))], self.tps, self.s), [])
        g = gcode(self.tps, (10.0, -3.0))
        self.assertEqual(postcheck.verify([('p.nc', g)], self.tps, self.s, origin=(10.0, -3.0)), [])
        self.assertTrue(postcheck.verify([('p.nc', g)], self.tps, self.s))          # sans l'origine : écart

    def test_faults_found(self):
        good = gcode(self.tps)
        self.assertIn('G2 ', good)
        w = postcheck.verify([('p.nc', good.replace('G2 ', 'G3 ', 2))], self.tps, self.s)
        self.assertTrue(w and all('CONTRÔLE' in x for x in w))
        lines = good.splitlines()
        k = next(i for i, ln in enumerate(lines) if ln.startswith('G1 ') and i > 20)
        w = postcheck.verify([('p.nc', '\n'.join(lines[:k] + lines[k + 1:]))], self.tps, self.s)
        self.assertTrue(any('absent' in x or 'coupe à' in x for x in w))
        x = w[0].split('(X ')[1].split(' Y')[0].replace(',', '.')
        self.assertTrue(math.isfinite(float(x)))                                    # la position est dite

    def test_skips_and_non_programs(self):
        g = gcode(self.tps)
        self.assertIn('sauté', postcheck.verify([('p.nc', g + 'G81 X1 Y1 Z-1 R1\n')], self.tps, self.s)[0])
        self.assertIn('rotatif', postcheck.verify([('p.nc', g.replace('G1 X', 'G1 A12. X', 1))], self.tps,
                                                  self.s)[0])
        self.s.laser_tiles = True
        self.assertIn('morceaux', postcheck.verify([('p.nc', g)], self.tps, self.s)[0])
        self.s.laser_tiles = False
        xml = '<LISTA_LAVORI><INGOMBRO_TARGA_X1>0</INGOMBRO_TARGA_X1></LISTA_LAVORI>'
        self.assertEqual(postcheck.verify([('p.CLJOB', xml), ('p.nc', g)], self.tps, self.s), [])   # XML ignoré
        self.assertEqual(postcheck.verify([('p.CLJOB', xml)], self.tps, self.s), [])
        self.assertTrue(postcheck.is_program('P_01.U00') and not postcheck.is_program('p_consignes.txt'))


if __name__ == '__main__':
    unittest.main()
