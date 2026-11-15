"""Round 966 : la raison du compagnon dit vrai pour des contours simplement colorés (« contour(s) de couleur propre »,
plus « objet(s) paramétrique(s) »)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r966.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import OWN_COLOR, Document, Group, Shape  # noqa: E402
from vectordrive.io import companion  # noqa: E402


def shape(color=None, **extra):
    s = Shape(path=geom.Path([geom.rect(0, 0, 10, 5)]))
    if color:
        s.extra[OWN_COLOR] = color
    s.extra.update(extra)
    return s


class Reason(unittest.TestCase):

    def test_coloured_contours_are_named_for_what_they_are(self):
        d = Document()
        d.layers[0].items += [shape('#ff0000'), shape('#0000ff'), shape(), Group(children=[shape('#00a000'), shape()])]
        self.assertEqual(companion.reasons(d), ['3 contour(s) de couleur propre'])    # avant : « 3 objet(s) paramétrique(s)… »
        d.layers[0].items.append(shape('#ff8800', forme={'genre': 'etoile'}))         # coloré ET paramétrique
        d.layers[0].items.append(shape(forme={'genre': 'etoile'}))
        self.assertEqual(companion.reasons(d), ['3 contour(s) de couleur propre',
                                                '2 objet(s) paramétrique(s) ou groupe(s) avec textes'])
        plain = Document()
        plain.layers[0].items.append(shape())
        self.assertEqual(companion.reasons(plain), [])


if __name__ == '__main__':
    unittest.main()
