"""Round 707 : Comparer deux dessins (comme COMPARE en DAO, d'après CADCraft) —
ajouté, enlevé, modifié (géométrie ou propriétés), zones en ordre de
lecture, surimpression du canevas, commandes du ruban."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import compare as CM
from vectordrive.core import geom
from vectordrive.core.document import Document, Group, Layer, Shape, Text
from vectordrive.core.geom import Affine, Path


def sq(x, y, s=10.0, tool=0, **kw):
    return Shape(path=Path([geom.rect(x, y, s, s)]), tool=tool, **kw)


def doc_of(*items, layer='Plan 1'):
    return Document(layers=[Layer(name=layer, items=list(items))])


class TestCompare(unittest.TestCase):
    def test_same_and_differences(self):
        a1, a2, a3 = sq(0, 0), sq(20, 0), sq(40, 0)
        t = Text(text='Plaque', font='VD Trait', size=5, matrix=Affine.translation(0, 30))
        here = doc_of(a1, a2, a3, t)
        b1 = sq(0, 0)                                      # identique (autre identifiant)
        b2 = sq(20, 0, tool=2)                             # même géométrie, autre outil
        b4 = sq(0, 60)                                     # seulement dans l'autre
        bt = Text(text='Plaque', font='VD Trait', size=5, matrix=Affine.translation(0, 30))
        bt.id = t.id
        bt.text = 'Plaque 2'                               # même identifiant, autre texte
        res = CM.compare(here, doc_of(b1, Group(children=[b2, b4]), bt), 'v2')
        self.assertEqual(res.common, 1)
        self.assertEqual(res.added, [a3])
        self.assertEqual(res.removed, [b4])
        what = {id(a): w for a, _b, w in res.changed}
        self.assertEqual(what[id(a2)], ['outil'])
        self.assertEqual(what[id(t)], ['texte'])
        self.assertEqual(res.differences(), 4)

    def test_micron_and_layer(self):
        here = doc_of(sq(0, 0))
        self.assertEqual(CM.compare(here, doc_of(sq(0.0002, 0))).differences(), 0)      # au micron près
        self.assertEqual(len(CM.compare(here, doc_of(sq(0.01, 0))).added), 1)
        res = CM.compare(here, doc_of(sq(0, 0), layer='Découpe'))
        self.assertEqual(res.changed[0][2], ['calque'])

    def test_regions_reading_order(self):
        here = doc_of(sq(0, 0), sq(100, 100), sq(0, 100), sq(2, 2, 3))
        res = CM.compare(here, Document())
        self.assertEqual(len(res.regions), 3)
        self.assertEqual(res.regions[0][:2], (0.0, 100.0))         # en haut à gauche d'abord
        self.assertEqual(res.regions[1][:2], (100.0, 100.0))
        self.assertEqual(res.regions[2], (0.0, 0.0, 10.0, 10.0))   # boîtes voisines réunies
        self.assertEqual(res.step(1), res.regions[0])
        self.assertEqual(res.step(-1), res.regions[2])             # en boucle
        self.assertEqual(CM.compare(Document(), Document()).regions, [])


class TestCommands(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        cls.w.resize(1200, 800)

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def test_compare_overlay_and_close(self):
        w, c = self.w, self.w.canvas
        for it in (sq(0, 0), sq(50, 0)):
            c.doc.add(it)
        other = doc_of(sq(0, 0), sq(50, 40))
        self.assertFalse(w.A['compare_next'].isEnabled())
        res = w.compare_with(other, 'autre.vdz')
        self.assertIs(c.compare, res)
        self.assertEqual((len(res.added), len(res.removed)), (1, 1))
        self.assertTrue(w.A['compare_next'].isEnabled())
        self.assertEqual(res.at, 0)
        img = c.grab().toImage()                                   # la surimpression se dessine
        self.assertFalse(img.isNull())
        self.assertIsNotNone(w.compare_step(1))
        self.assertEqual(res.at, 1)
        self.assertTrue(w.compare_close())
        self.assertIsNone(c.compare)
        self.assertFalse(w.A['compare_close'].isEnabled())
        self.assertFalse(w.compare_close())

    def test_actions(self):
        from vectordrive.ui import icons
        for k in ('compare', 'compare_next', 'compare_prev', 'compare_close'):
            self.assertIn(k, icons.ICONS)
            self.assertFalse(self.w.A[k].icon().isNull())


if __name__ == '__main__':
    unittest.main()
