"""Round 491 : export de la sélection — calques (et leurs outils), origine et données du dessin gardés."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Group, Layer, Shape
from vectordrive.io import registry

app = QApplication.instance() or QApplication([])


def sq(x):
    return Shape(path=geom.Path([geom.rect(x, 0, 10, 10)]))


class TestExportSelection(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        doc = self.w.canvas.doc
        doc.layers = [Layer(name='Gravure', tool=0), Layer(name='Découpe', tool=3)]
        self.a, self.b, self.c = sq(0), sq(20), sq(40)
        self.b.tool = self.c.tool = 3
        self.inner = sq(60)
        self.inner.tool = 3
        doc.layers[0].items = [self.a]
        doc.layers[1].items = [self.b, self.c, Group(children=[self.inner])]
        doc.active = doc.layers[0].id
        doc.extra['origine'] = (5.0, 5.0)
        doc.extra['fao'] = {'operations': [{'name': 'x'}]}
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_document(self):
        from vectordrive.ui.export_dialog import selection_document
        d = selection_document(self.w.canvas.doc, [self.inner, self.a, self.b])
        self.assertEqual([(L.name, L.tool, len(L.items)) for L in d.layers], [('Gravure', 0, 1), ('Découpe', 3, 2)])
        self.assertEqual(d.extra.get('origine'), (5.0, 5.0))
        self.assertNotIn('fao', d.extra)
        self.assertIsNot(d.layers[0].items[0], self.a)               # copies : le dessin n'est pas touché
        self.assertEqual(len(self.w.canvas.doc.layers[1].items), 3)

    def test_vnd_like_full_save(self):
        from vectordrive.ui import export_dialog as ED
        full, part = os.path.join(self.dir, 'full.vnd'), os.path.join(self.dir, 'part.vnd')
        registry.save_document(self.w.canvas.doc, full)
        ED.export_items(self.w, [self.a, self.b], part, {})
        f, p = registry.open_document(full), registry.open_document(part)
        fl = {L.name: (L.tool, [tuple(round(v, 3) for v in it.bbox()) for it in L.items]) for L in f.layers}
        pl = {L.name: (L.tool, [tuple(round(v, 3) for v in it.bbox()) for it in L.items]) for L in p.layers if L.items}
        self.assertEqual(pl['Gravure'], fl['Gravure'])                # même place (origine) et même outil
        self.assertEqual(pl['Découpe'], (3, fl['Découpe'][1][:1]))


if __name__ == '__main__':
    unittest.main()
