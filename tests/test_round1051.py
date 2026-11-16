"""Round 1051 : réponse du 15/11 à la question 35 — le calque d'une plaque de reprise posée n'est écrit que dans le
VDZ ; les autres formats ne le reçoivent pas, et leur compagnon .vdz le garde et le remet à l'ouverture."""
import json
import os
import pathlib
import tempfile
import unittest
import zipfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1051.ini'))

from PySide6.QtWidgets import QApplication  # noqa: E402

from vectordrive.cam import fixture as FX  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Layer, Shape  # noqa: E402
from vectordrive.io import companion, registry  # noqa: E402

app = QApplication.instance() or QApplication([])


def box(x, y, w=20.0, h=10.0):
    return Shape(path=geom.Path([geom.rect(x, y, w, h)]))


def drawing():
    """Dessin (2 objets), Plaque (3 trous, marquée), Repères (1 objet) : la plaque au milieu."""
    plate = Layer(name='Plaque', items=[box(0, 0, 4, 4), box(50, 0, 4, 4), box(100, 0, 4, 4)])
    plate.extra[FX.PLATE_LAYER] = {'fichier': 'x.dxf'}
    return Document(layers=[Layer(name='Dessin', items=[box(10, 10), box(40, 10)]), plate,
                            Layer(name='Repères', items=[box(10, 40)])])


def names(doc):
    return [L.name for L in doc.layers]


def count(doc):
    return sum(1 for _ in doc.iter_leaves())


class OnlyInTheVdz(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)

    def test_only_the_vdz_gets_the_plate(self):
        d = drawing()
        f = str(self.dir / 'piece.vdz')
        registry.save_document(d, f)
        back = registry.open_document(f)
        self.assertEqual(names(back), ['Dessin', 'Plaque', 'Repères'])       # le VDZ : tout, comme avant
        self.assertTrue(FX.is_plate_layer(back.layers[1]))
        for ext in ('.dxf', '.vnd', '.svg'):
            with self.subTest(format=ext):
                d = drawing()
                f = str(self.dir / ('piece' + ext))
                registry.save_document(d, f)
                back = registry.open_document(f)
                self.assertEqual(count(back), 3, 'avant : les trous de la plaque écrits avec le dessin')
                self.assertEqual(count(d), 6)                               # le dessin ouvert, lui, garde sa plaque

    def test_export_whole_drawing_and_explicit_selection(self):
        import types
        from vectordrive.ui import export_dialog as ED
        d = drawing()
        win = types.SimpleNamespace(canvas=types.SimpleNamespace(doc=d))
        every = [it for L in d.layers for it in L.items]
        f = str(self.dir / 'tout.dxf')
        ED.export_items(win, every, f)
        self.assertEqual(count(registry.open_document(f)), 3, 'avant : la plaque exportée avec le dessin')
        g = str(self.dir / 'choisie.dxf')
        ED.export_items(win, list(d.layers[1].items), g, selection=True)
        self.assertEqual(count(registry.open_document(g)), 3)               # la plaque choisie exprès : écrite

    def test_the_companion_keeps_it_and_says_so(self):
        d = drawing()
        f = str(self.dir / 'piece.vnd')
        registry.save_document(d, f)
        cp, why = companion.sync(d, f)
        self.assertIsNotNone(cp, 'avant : pas de compagnon pour une plaque')
        self.assertIn('plaque de reprise posée', why)
        with zipfile.ZipFile(cp) as z:
            link = json.loads(z.read(companion.LINK).decode('utf-8'))
        self.assertEqual(link.get('plaques'), [1])
        self.assertEqual(link['compteurs'], [2, 1])                         # les calques écrits seulement
        plain = Document(layers=[Layer(name='Dessin', items=[box(10, 10)])])
        g = str(self.dir / 'simple.dxf')
        registry.save_document(plain, g)
        self.assertEqual(companion.sync(plain, g), (None, []))              # sans plaque : rien de changé

    def test_reopened_vnd_gets_its_plate_back_in_place(self):
        d = drawing()
        f = str(self.dir / 'piece.vnd')
        registry.save_document(d, f)
        companion.sync(d, f)
        back = registry.open_document(f)
        self.assertEqual(count(back), 3)
        companion.apply(back, f)
        self.assertEqual(names(back), ['Dessin', 'Plaque', 'Repères'], 'avant : la plaque perdue, ou mêlée au dessin')
        self.assertTrue(FX.is_plate_layer(back.layers[1]))
        self.assertEqual([len(L.items) for L in back.layers], [2, 3, 1])
        self.assertEqual(back.layers[0].id, d.layers[0].id)                 # les calques écrits : repris comme avant

    def test_reopened_dxf_too(self):
        d = drawing()
        f = str(self.dir / 'piece.dxf')
        registry.save_document(d, f)
        companion.sync(d, f)
        back = registry.open_document(f)
        companion.apply(back, f)
        self.assertEqual(names(back), ['Dessin', 'Plaque', 'Repères'])
        self.assertTrue(FX.is_plate_layer(back.layers[1]))

    def test_file_changed_elsewhere_the_plate_still_comes_back(self):
        for ext in ('.vnd', '.dxf'):
            with self.subTest(format=ext):
                d = drawing()
                f = str(self.dir / ('autre' + ext))
                registry.save_document(d, f)
                companion.sync(d, f)
                other = Document(layers=[Layer(name='Dessin', items=[box(10, 10), box(40, 10), box(70, 10)]),
                                         Layer(name='Repères', items=[box(10, 40)])])
                registry.save_document(other, f)                            # retouché dans un autre logiciel
                back = registry.open_document(f)
                msgs = companion.apply(back, f)
                self.assertTrue(any('a changé' in m for m in msgs))
                plates = [L for L in back.layers if FX.is_plate_layer(L)]
                self.assertEqual(len(plates), 1, 'avant : la plaque perdue avec un fichier retouché')
                self.assertEqual(len(plates[0].items), 3)
                self.assertEqual(count(back), 4 + 3)                        # le dessin du fichier fait foi


if __name__ == '__main__':
    unittest.main()
