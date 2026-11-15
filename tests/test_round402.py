"""Round 402 : graduations — chiffres inclinés et chiffres sous la règle
(TypeEdit : labels inclinés, perpendiculaires aux graduations)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import fonts, graduation as G


def numbers(g):
    return next(c for c in g.children if c.name == 'nombres').path.bbox()


@unittest.skipUnless(fonts.find_font('Arial'), 'police Arial absente')
class TestLabels(unittest.TestCase):
    def test_angle_and_below(self):
        base = G.GraduationSpec(divisions=20, step=1.0, major_every=10, value_step=100.0)
        flat = numbers(G.build(base))
        self.assertGreater(flat[1], base.major_len)                       # au-dessus des grands traits
        up = numbers(G.build(G.GraduationSpec(**{**base.__dict__, 'label_angle': 90.0})))
        self.assertGreater(up[3] - up[1], 1.5 * (flat[3] - flat[1]))     # « 200 » debout : plus haut
        self.assertLess(up[2] - up[0], flat[2] - flat[0])                 # et plus étroit
        below = numbers(G.build(G.GraduationSpec(**{**base.__dict__, 'labels_below': True})))
        self.assertLess(below[3], 0.0)                                    # sous le trait de base
        both = numbers(G.build(G.GraduationSpec(**{**base.__dict__, 'labels_below': True, 'label_angle': 90.0})))
        self.assertLess(both[3], 0.0)


if __name__ == '__main__':
    unittest.main()
