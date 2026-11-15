"""Round 968 : le noir d'un DXF écrit porte aussi sa couleur vraie (TypeEdit dessine en blanc le numéro 7 seul) ;
réglage F10 › Fichiers pour revenir au numéro 7 seul."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r968.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

import ezdxf  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import OWN_COLOR, Document, Shape  # noqa: E402
from vectordrive.io import colors, dxf  # noqa: E402


def drawing():
    d = Document()
    black = Shape(path=geom.Path([geom.rect(0, 0, 10, 5)]))
    red = Shape(path=geom.Path([geom.rect(20, 0, 10, 5)]))
    red.extra[OWN_COLOR] = '#ff0000'
    d.layers[0].items += [black, red]
    return d


def written(doc):
    path = pathlib.Path(tempfile.mkdtemp()) / 'noir.dxf'
    dxf.write(doc, path)
    ents = list(ezdxf.readfile(str(path)).modelspace())
    return path, [(e.dxf.color, e.dxf.get('true_color')) for e in ents]


class Black(unittest.TestCase):

    def test_black_carries_its_true_colour(self):
        path, told = written(drawing())
        self.assertEqual(told, [(7, 0), (1, 0xff0000)])            # avant : (7, None) — blanc sur blanc dans TypeEdit
        back = dxf.read(path)
        items = sorted((it for L in back.layers for it in L.items), key=lambda it: it.bbox()[0])
        self.assertEqual([back.item_color(it) for it in items], ['#000000', '#ff0000'])
        self.assertEqual(items[0].tool, 0)                         # relu : le noir reste le premier outil

    def test_the_setting_goes_back_to_number_7_alone(self):
        from vectordrive.ui import options
        from vectordrive.ui.main_window import MainWindow
        self.assertIs(options.default_of(options.BY_KEY['export/dxf_noir']), True)
        w = MainWindow()
        try:
            self.assertTrue(colors.DXF_BLACK_TRUE)
            w.settings.setValue('export/dxf_noir', False)
            w.apply_options()
            self.assertFalse(colors.DXF_BLACK_TRUE)
            self.assertEqual(written(drawing())[1], [(7, None), (1, 0xff0000)])
        finally:
            w.settings.setValue('export/dxf_noir', True)
            w.apply_options()
            w.modified = False
            w.close()
        self.assertTrue(colors.DXF_BLACK_TRUE)


if __name__ == '__main__':
    unittest.main()
