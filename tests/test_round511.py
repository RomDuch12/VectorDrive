"""Round 511 : mémoire des parcours FAO — une opération dont ni elle, ni le réglage, ni le dessin, ni le
point de départ n'ont changé n'est pas recalculée ; les tracés s'enregistrent sans leurs valeurs en cache."""
import os
import pickle
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def setup_doc():
    d = Document()
    d.plate = None
    for i in range(3):
        d.add(Shape(path=geom.Path([geom.circle((10 * i, 0), 3)]), tool=0))
    s = model.CamSetup()
    f = model.CamTool(name='F', kind='fraise', diameter=1.0, feed=1000.0, stepover=0.4, step_down=0.5)
    v = model.CamTool(name='V', kind='conique', diameter=6.0, angle=60.0, tip=0.1, feed=1000.0, step_down=0.5)
    s.tools = [f, v]
    s.operations = [model.Operation(tool_id=f.id, kind='poche', depth=0.6),
                    model.Operation(tool_id=v.id, kind='gravure', depth=0.2)]
    return d, s


class TestToolpathCache(unittest.TestCase):
    def setUp(self):
        S.clear_toolpath_cache()

    def count_calls(self, d, s):
        real = S.compute
        with mock.patch.object(S, 'compute', side_effect=real) as c:
            out = S.compute_all(d, s)
        return out, c.call_count

    def test_reuse_and_invalidation(self):
        d, s = setup_doc()
        first, n1 = self.count_calls(d, s)
        self.assertEqual(n1, 2)
        again, n2 = self.count_calls(d, s)
        self.assertEqual(n2, 0)                                       # rien n'a changé
        self.assertEqual([len(t.moves) for t in again], [len(t.moves) for t in first])
        again[0].warnings.append('locale')                             # copie : la mémoire n'est pas touchée
        self.assertNotIn('locale', self.count_calls(d, s)[0][0].warnings)
        s.operations[1].depth = 0.3                                    # la gravure seule
        _out, n3 = self.count_calls(d, s)
        self.assertEqual(n3, 1)
        d.add(Shape(path=geom.Path([geom.rect(40, 0, 4, 4)]), tool=0))  # le dessin change : tout
        _out, n4 = self.count_calls(d, s)
        self.assertEqual(n4, 2)
        s.tolerance = 0.02                                             # le réglage change : tout
        _out, n5 = self.count_calls(d, s)
        self.assertEqual(n5, 2)

    def test_not_kept(self):
        d, s = setup_doc()
        s.operations = [model.Operation(kind='texte_machine', tool_id=s.tools[0].id)]
        self.assertIsNone(S._op_key('d', 's', s.operations[0], (0, 0), None))
        self.assertIsNotNone(S._op_key('d', 's', model.Operation(kind='poche'), (0, 0), None))

    def test_path_pickle_without_memo(self):
        p = geom.Path([geom.circle((0, 0), 2)])
        before = pickle.dumps(p)
        p.bbox()
        p.length()
        self.assertEqual(pickle.dumps(p), before)                      # même empreinte avec ou sans cache
        q = pickle.loads(before)
        self.assertEqual(q.bbox(), p.bbox())


if __name__ == '__main__':
    unittest.main()
