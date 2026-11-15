"""Round 962 : HPGL — un contour plus petit qu'un demi-pas du traceur n'est pas perdu par l'allégement des tracés."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r962.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Shape  # noqa: E402
from vectordrive.io import hpgl  # noqa: E402


class Tiny(unittest.TestCase):

    def test_a_contour_smaller_than_half_a_step_is_still_written(self):
        d = Document()
        # un grand cadre (il fixe l'origine du tracé) et un point de 0,4 µm à cheval sur une limite de pas (10,0125 mm)
        tiny = geom.polyline([(10.0123, 5.0), (10.0127, 5.0), (10.0125, 5.0003)], closed=True)
        d.layers[0].items += [Shape(path=geom.Path([geom.rect(0, 0, 20, 10)])), Shape(path=geom.Path([tiny]))]
        text, _images = hpgl.write_text(d)
        strokes = [c for c in text.replace('\n', '').split(';') if c.startswith('PD') and len(c) > 2]
        self.assertEqual(len(strokes), 2)                                   # avant : 1 — le petit contour sautait
        self.assertIn('PU400,200', text)                                    # il part de son pas…
        self.assertIn('PD401,200', strokes[1])                              # … et fait un pas, comme avant le round 961


if __name__ == '__main__':
    unittest.main()
