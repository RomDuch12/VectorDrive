"""Round 943 : une couleur propre par objet (trait et remplissage), indépendante de l'outil, gardée dans les fichiers,
montrée par Ctrl+8 ou Ctrl+_ ; épaisseur de la surbrillance de la sélection réglable (2 px par défaut)."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r943.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Shape  # noqa: E402
from vectordrive.io import registry  # noqa: E402

ORANGE = '#ff8800'


class Colours(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        cls.w.resize(900, 700)
        cls.w.show()
        app.processEvents()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def setUp(self):
        w = self.w
        w.new_document()
        self.a = Shape(path=geom.Path([geom.rect(0, 0, 40, 20)]))
        self.b = Shape(path=geom.Path([geom.circle((70.0, 10.0), 8.0)]))
        for it in (self.a, self.b):
            w.canvas.doc.add(it)
        w.canvas.select([self.b])

    def shape(self, i):
        return self.w.canvas.doc.layers[0].items[i]

    def test_an_object_takes_its_own_colour_whatever_its_tool(self):
        w, doc = self.w, self.w.canvas.doc
        tool_colour = doc.item_color(self.shape(1))
        self.assertEqual(w.set_selection_color(ORANGE, ask=False), 1)
        self.assertEqual(doc.item_color(self.shape(1)), ORANGE)
        self.assertEqual(doc.item_color(self.shape(0)), tool_colour)        # l'autre : la couleur de son outil
        self.shape(1).tool = 3                                              # changé d'outil : sa couleur reste
        self.assertEqual(doc.item_color(self.shape(1)), ORANGE)
        w.canvas.select([self.shape(1)])
        self.assertEqual(w.set_selection_color(None, ask=False), 1)         # « Couleur de l'outil » : retirée
        self.assertEqual(doc.item_color(self.shape(1)), doc.tool_color(3))
        w.undo()
        self.assertEqual(w.canvas.doc.item_color(w.canvas.doc.layers[0].items[1]), ORANGE)

    def test_the_colour_follows_in_the_files(self):
        w = self.w
        w.set_selection_color(ORANGE, ask=False)
        self.shape(1).filled = True
        folder = pathlib.Path(tempfile.mkdtemp())
        for name in ('a.vdz', 'a.vnd'):
            registry.save_document(w.canvas.doc, str(folder / name))
            back = registry.open_document(str(folder / name))
            got = sorted(back.item_color(it) for it in back.iter_leaves())
            self.assertIn(ORANGE, got, name)                                # avant : la couleur de l'outil seulement
        registry.save_document(w.canvas.doc, str(folder / 'a.svg'))
        self.assertIn('ff8800', (folder / 'a.svg').read_text(encoding='utf-8').lower())
        registry.save_document(w.canvas.doc, str(folder / 'a.pdf'))
        import zlib
        raw = (folder / 'a.pdf').read_bytes()
        body = raw[raw.index(b'stream') + len(b'stream'):raw.index(b'endstream')].strip(b'\r\n')
        self.assertTrue(b'1 0.5333 0 rg' in zlib.decompress(body))          # rempli de sa couleur
        import ezdxf
        registry.save_document(w.canvas.doc, str(folder / 'a.dxf'))
        colours = {e.dxf.color for e in ezdxf.readfile(str(folder / 'a.dxf')).modelspace()}
        self.assertEqual(len(colours), 2)                                   # le cercle n'a plus la couleur du rectangle

    def test_ctrl_8_or_underscore_shows_the_colours(self):
        act = self.w.A['tool_colors']
        keys = [s.toString() for s in act.shortcuts()]
        self.assertEqual(keys, ['Ctrl+8', 'Ctrl+_'])                        # « _ » : le 8 sans Maj d'un clavier français
        self.assertEqual([s.toString() for s in self.w.A['fill'].shortcuts()], ['Ctrl+9', 'Ctrl+Ç'])
        self.assertEqual([s.toString() for s in self.w.A['reference_7'].shortcuts()], ['Ctrl+Num+7'])
        from vectordrive.ui import shortcuts as SC
        self.assertEqual(SC.azerty_aliases({'a': ['Ctrl+6'], 'b': ['Ctrl+-'], 'c': ['Ctrl+Shift+8']}), {})   # déjà prise, ou avec Maj
        self.assertIn('contour_color', self.w.A)
        self.w.set_selection_color(ORANGE, ask=False)
        act.setChecked(False)
        img = self.w.canvas.grab().toImage()
        self.assertFalse(self.has(img, QColor(ORANGE)))
        act.setChecked(True)
        img = self.w.canvas.grab().toImage()
        self.w.canvas.select([])
        img = self.w.canvas.grab().toImage()
        self.assertTrue(self.has(img, QColor(ORANGE)))

    @staticmethod
    def has(img, colour, tol=40):
        for y in range(0, img.height(), 1):
            for x in range(0, img.width(), 2):
                c = img.pixelColor(x, y)
                if abs(c.red() - colour.red()) + abs(c.green() - colour.green()) + abs(c.blue() - colour.blue()) < tol:
                    return True
        return False

    @staticmethod
    def count(img, colour, tol=60):
        n = 0
        for y in range(img.height()):
            for x in range(img.width()):
                c = img.pixelColor(x, y)
                n += abs(c.red() - colour.red()) + abs(c.green() - colour.green()) + abs(c.blue() - colour.blue()) < tol
        return n

    def test_the_selection_highlight_width_is_an_option(self):
        from vectordrive.ui.theme import canvas_colors
        w = self.w
        sel = QColor(canvas_colors()['selection'])
        self.assertEqual(w.canvas.highlight_px, 2)
        w.canvas.select([self.shape(0)])
        w.A['zoom_sel'].trigger()
        app.processEvents()
        thin = self.count(w.canvas.grab().toImage(), sel, tol=1)
        w.settings.setValue('options/surbrillance', 6)
        w.apply_options()
        self.assertEqual(w.canvas.highlight_px, 6)
        app.processEvents()
        thick = self.count(w.canvas.grab().toImage(), sel, tol=1)
        w.settings.setValue('options/surbrillance', 2)
        w.apply_options()
        self.assertGreater(thick, thin * 4)                                 # avant : 2 px, sans réglage


if __name__ == '__main__':
    unittest.main()
