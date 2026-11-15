"""Round 392 : pontets incurvés (TypeEdit : Ponts incurvés) — montée et
descente en douceur au lieu de flancs verticaux."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from tests.test_round362 import run


def zs_on_last_pass(tp):
    return [round(m.z, 4) for m in tp.moves if m.kind == 'feed']


class TestCurvedTabs(unittest.TestCase):
    def test_shapes(self):
        kw = dict(tabs=2, tab_width=4.0, tab_height=0.5)
        flat = run(**kw)
        curved = run(tab_shape='incurve', **kw)
        zf, zc = set(zs_on_last_pass(flat)), set(zs_on_last_pass(curved))
        self.assertEqual(zf, {-1.0, -0.5})                            # droits : deux niveaux
        mids = {z for z in zc if -1.0 < z < -0.5}
        self.assertGreaterEqual(len(mids), 4)                         # incurvés : des niveaux intermédiaires
        self.assertEqual(max(zc), -0.5)                               # même hauteur de pontet
        self.assertEqual(min(zc), -1.0)

    def test_default(self):
        a = run(tabs=1, tab_width=3.0, tab_height=0.4)
        b = run(tabs=1, tab_width=3.0, tab_height=0.4, tab_shape='droit')
        self.assertEqual([(m.x, m.y, m.z) for m in a.moves], [(m.x, m.y, m.z) for m in b.moves])


if __name__ == '__main__':
    unittest.main()
