"""Round 969 : EPS, PostScript, Illustrator ancien — un tracé rempli est lu en contour fermé (le remplissage ferme
chaque tracé de lui-même) ; un tracé seulement tiré garde ses bouts."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r969.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from vectordrive.io import postscript  # noqa: E402

HEAD = b'%!PS-Adobe-2.0 EPSF-1.2\n%%BoundingBox: 0 0 200 100\n%%EndComments\n%%EndProlog\n'


def contours(body: str):
    items, _report = postscript.read_bytes(HEAD + body.encode('latin-1') + b'\n%%EOF\n')
    return [(len(c.segments), c.closed) for it in items for c in it.path.contours]


class Filled(unittest.TestCase):

    def test_a_filled_path_is_a_closed_contour(self):
        # à la manière des EPS en surfaces (Illustrator ancien) : « F » après le dernier point
        back = '10 10 m 50 10 l 50 40 l 10 40 l 10 10 l F'                 # revient à son départ
        short = '60 10 m 100 10 l 100 40 l 60 40 l F'                      # ne revient pas : le remplissage ferme
        self.assertEqual(contours(back), [(4, True)])                      # avant : (4, False)
        self.assertEqual(contours(short), [(4, True)])                     # avant : (3, False)
        for op in ('f', 'F', 'b', 'B', 'fill', 'eofill'):
            self.assertEqual(contours(f'0 0 moveto 10 0 lineto 10 10 lineto {op}'), [(3, True)], op)
        two = '0 0 m 10 0 l 10 10 l 20 0 m 30 0 l 30 10 l F'               # deux tracés d'une même surface
        self.assertEqual(contours(two), [(3, True), (3, True)])

    def test_a_stroked_path_keeps_its_ends(self):
        self.assertEqual(contours('110 10 m 150 40 l 190 10 l S'), [(2, False)])
        self.assertEqual(contours('0 0 moveto 10 0 lineto 10 10 lineto stroke'), [(2, False)])
        self.assertEqual(contours('110 10 m 150 40 l 190 10 l s'), [(3, True)])    # « s » ferme, comme avant
        self.assertEqual(contours('0 0 m 5 5 l F'), [(1, False)])           # un trait droit rempli reste un trait
        self.assertEqual(contours('0 0 m 5 5 l 9 0 l F'), [(3, True)])      # (ce qui distingue l'essai de l'ancien code)


if __name__ == '__main__':
    unittest.main()
