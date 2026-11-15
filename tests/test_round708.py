"""Round 708 : Reproduire les propriétés (comme MATCHPROP en DAO, d'après
CADCraft) — outil, remplissage, calque et mise en forme des textes d'un objet
aux autres ; pinceau chargé avec un seul objet ; choix dans F10 › Dessin."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import geom
from vectordrive.core.document import Group, Layer, Shape, Text
from vectordrive.core.geom import Affine, Path


def sq(x, tool=0, filled=False):
    return Shape(path=Path([geom.rect(x, 0, 10, 10)]), tool=tool, filled=filled)


class TestMatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def setUp(self):
        for k, _n in self.w.MATCH_PROPS:
            self.w.settings.remove(k)
        doc = self.w.canvas.doc
        doc.layers = [Layer(name='Plan 1'), Layer(name='Découpe', tool=2)]
        doc.active = doc.layers[0].id
        self.w.canvas.selection = []

    def test_first_to_others(self):
        w, doc = self.w, self.w.canvas.doc
        src = sq(0, tool=3, filled=True)
        a, b = sq(20), Group(children=[sq(40), sq(60, tool=1)])
        doc.layers[1].items.append(src)
        doc.layers[0].items += [a, b]
        w.canvas.select([src, a, b])
        self.assertEqual(w.match_properties(), 2)
        self.assertEqual([x.tool for x in (a, b, *b.children)], [3, 3, 3, 3])
        self.assertTrue(a.filled and all(c.filled for c in b.children))
        self.assertEqual(doc.layers[1].items, [src, a, b])                 # calque de l'objet de départ
        self.assertEqual(doc.layers[0].items, [])
        self.assertEqual(w.match_properties(), 0)                           # déjà faites
        w.undo()
        self.assertEqual([it.tool for it in doc.layers[0].items], [0, 0])

    def test_brush_texts_and_options(self):
        w, doc = self.w, self.w.canvas.doc
        src = Text(text='A', font='VD Trait', size=8, tool=1, matrix=Affine.translation(0, 20))
        src.extra['italic'] = 12.0
        t = Text(text='B', font='Arial', size=3, matrix=Affine.translation(0, 40))
        s = sq(20)
        doc.layers[0].items += [src, t, s]
        w.settings.setValue('proprietes/calque', False)
        w.settings.setValue('proprietes/outil', False)
        w.canvas.select([src])
        self.assertEqual(w.match_properties(), 0)                           # pinceau chargé
        self.assertIsNotNone(w._props_brush)
        w.canvas.select([t])                                                # clic sur un texte : il reçoit
        self.assertIsNone(w._props_brush)
        self.assertEqual((t.font, t.size, t.extra.get('italic'), t.tool), ('VD Trait', 8, 12.0, 0))
        self.assertTrue(t.outline and t.outline.contours)                   # contour recalculé
        w.canvas.select([src, s])                                           # forme : seul le reste s'applique
        self.assertEqual(w.match_properties(), 0)
        w.settings.setValue('proprietes/outil', True)
        self.assertEqual(w.match_properties(), 1)
        self.assertEqual(s.tool, 1)

    def test_action_and_options(self):
        from vectordrive.ui import icons
        from vectordrive.ui.options import value
        self.assertIn('match_props', icons.ICONS)
        self.assertFalse(self.w.A['match_props'].icon().isNull())
        self.assertTrue(all(value(self.w.settings, k) for k, _n in self.w.MATCH_PROPS))
        self.w.canvas.select([])
        self.assertEqual(self.w.match_properties(), 0)


if __name__ == '__main__':
    unittest.main()
