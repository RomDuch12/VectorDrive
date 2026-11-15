"""Round 577 : symbole créé — son aperçu DIB (bibliothèque, TypeEdit) aux couleurs des outils, sur la
palette du fichier ; sans couleurs : en noir comme avant."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import geom
from vectordrive.core.document import Shape
from vectordrive.io import smb


def pixels(f) -> set:
    dib = smb.thumbnail_dib(pathlib.Path(f).read_bytes())
    return set(dib[40 + 1024:40 + 1024 + 10000])


class TestColoredThumb(unittest.TestCase):
    def test_colors(self):
        items = [Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]), tool=3),
                 Shape(path=geom.Path([geom.rect(20, 0, 10, 10)]), tool=0)]
        d = pathlib.Path(tempfile.mkdtemp())
        smb.write(items, d / 'c.smb', tools={3: '#ff0000', 0: '#000000'})
        pal = smb._palette_rgb()
        red = pal.index((255, 0, 0))
        self.assertTrue({0, red} <= pixels(d / 'c.smb'))                      # rouge et noir
        smb.write(items, d / 'n.smb')
        self.assertEqual(pixels(d / 'n.smb'), {0, 255})                       # sans couleurs : noir sur blanc


if __name__ == '__main__':
    unittest.main()
