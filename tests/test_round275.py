"""Round 275 : gravure sur le trait, traits ouverts en plusieurs passes —
aller-retour, aller simple (même sens, retour au départ), aller simple
puis retour à la dernière passe ; TPP SPECIALTRACE ModeTrace."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model as M, strategies as S, tpp
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def directions(mode):
    d = Document()
    d.plate = None
    d.add(Shape(path=geom.Path([geom.polyline([(0, 0), (10, 0)])]), tool=1))
    setup = M.setup_of(d)
    t = M.CamTool(name='V', diameter=1)
    setup.tools = [t]
    tp = S.compute(d, setup, M.Operation(kind='gravure', depth=0.3, step_down=0.1, tool_id=t.id, trace_mode=mode))
    return [round(b.x - a.x) for a, b in zip(tp.moves, tp.moves[1:]) if b.kind == 'feed' and abs(b.x - a.x) > 1]


class TestTrace(unittest.TestCase):
    def test_modes(self):
        self.assertEqual(directions('aller_retour'), [10, -10, 10])
        self.assertEqual(directions('aller_simple'), [10, 10, 10])
        self.assertEqual(directions('dernier_ar'), [10, 10, 10, -10])

    def test_typeedit(self):
        for v, want in (('1', 'simple'), ('2', 'ar'), ('3', 'dernier')):
            p = tpp.Preset(name='t', kind='CP_Plotting', sections={'SPECIALTRACE': {'ModeTrace': v}})
            self.assertEqual(tpp.to_template(p)['operations'][0]['trace_mode'], want)


if __name__ == '__main__':
    unittest.main()
