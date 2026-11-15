"""Round 946 : mêmes formats pour ouvrir, importer, enregistrer et exporter. « Enregistrer sous » écrit dans tout
format qu'on sait écrire, avec un compagnon .vdz quand ce format ne garde pas tout ; le compagnon est relu à
l'ouverture et à l'import ; « Exporter » n'en écrit pas."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r946.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication, QFileDialog  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.cam import model  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core import text as T  # noqa: E402
from vectordrive.core.document import Document, Plate, Shape, Text  # noqa: E402
from vectordrive.core.geom import Affine  # noqa: E402
from vectordrive.io import companion, registry  # noqa: E402


def rect(x=10.0, y=10.0):
    return Shape(path=geom.Path([geom.rect(x, y, 40, 20)]))


def label():
    t = Text(text='BFM', font='Arial', size=8, matrix=Affine.translation(15, 15))
    t.outline = T.layout('BFM', 'Arial', 8).transformed(t.matrix)
    return t


def drawing(text=True):
    d = Document()
    d.layers[0].items.append(rect())
    if text:
        d.layers[0].items.append(label())
    return d


def texts(doc):
    return [it for L in doc.layers for it in L.items if isinstance(it, Text)]


class Companion(unittest.TestCase):

    def test_a_dxf_gets_its_own_companion(self):
        d = drawing()
        s = model.CamSetup(tools=[model.CamTool()])
        s.operations = [model.Operation(tool_id=s.tools[0].id)]
        model.store(d, s)
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'piece.dxf')
            registry.save_document(d, f)
            cp, why = companion.sync(d, f)
            self.assertEqual(cp.name, 'piece.dxf.vdz')                      # avant : piece.vdz, celui d'un VND
            self.assertEqual(companion.twin_of(cp), pathlib.Path(f))
            self.assertTrue(any('texte' in r for r in why) and any('FAO' in r for r in why))
            back = registry.open_document(f)
            self.assertEqual(texts(back), [])                               # le DXF seul : le texte en courbes
            msgs = companion.apply(back, f)
            self.assertIn('relu', msgs[0])
            self.assertEqual([t.text for t in texts(back)], ['BFM'])        # le dessin VectorDrive entier
            self.assertEqual(len(model.setup_of(back).operations), 1)
            # retouché dans un autre logiciel : le fichier fait foi, le réglage FAO est gardé
            other = Document()
            other.layers[0].items.append(rect(60.0, 40.0))
            registry.save_document(other, f)
            back = registry.open_document(f)
            msgs = companion.apply(back, f)
            self.assertIn('a changé', msgs[0])
            self.assertEqual(texts(back), [])
            self.assertEqual(len(model.setup_of(back).operations), 1)
            # un dessin que le DXF rend tel quel : pas de compagnon, l'ancien est retiré
            plain = drawing(text=False)
            registry.save_document(plain, f)
            self.assertEqual(companion.sync(plain, f), (None, []))
            self.assertFalse(cp.exists())
            # une plaque réglée : le DXF la garde lui-même (round 972), toujours sans compagnon
            plain.plate = Plate(width=80.0, height=45.0)
            registry.save_document(plain, f)
            self.assertEqual(companion.sync(plain, f), (None, []))
            back = registry.open_document(f)
            self.assertEqual((back.plate.width, back.plate.height), (80.0, 45.0))


class Window(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def test_save_as_writes_the_asked_format_and_its_companion(self):
        w = self.w
        w.new_document()
        w.canvas.doc.add(rect())
        w.canvas.doc.add(label())
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, 'plaque.dxf')
            with mock.patch.object(QFileDialog, 'getSaveFileName', return_value=(out, '')) as ask:
                w.save_as()
            self.assertTrue(os.path.isfile(out))                            # avant : plaque.dxf.vdz, un VDZ
            self.assertEqual(pathlib.Path(w.path).name, 'plaque.dxf')
            offered = ask.call_args[0][3]                                   # les filtres de la boîte
            for ext in ('*.vdz', '*.vnd', '*.dxf', '*.svg', '*.pdf', '*.eps', '*.png', '*.plt'):
                self.assertIn(ext, offered)
            self.assertNotIn('*.cdr', offered)                              # lu seulement : pas proposé
            self.assertTrue(companion.is_companion(out + '.vdz'))
            self.assertEqual(texts(registry.open_document(out)), [])
            # Ctrl+S : le même fichier, dans son format, et son compagnon
            w.canvas.doc.add(rect(70.0, 50.0))
            w.modified = True
            before = pathlib.Path(out).read_bytes()
            with mock.patch.object(QFileDialog, 'getSaveFileName', side_effect=AssertionError('pas de question')):
                w.save()
            self.assertNotEqual(pathlib.Path(out).read_bytes(), before)
            # rouvert : le compagnon rend le texte ; c'est un fichier de travail, Ctrl+S le réenregistre
            self.assertTrue(w.open_path(out))
            self.assertEqual([t.text for t in texts(w.canvas.doc)], ['BFM'])
            self.assertEqual(pathlib.Path(w.path).name, 'plaque.dxf')
            n = len(w.docs)
            self.assertTrue(w.open_path(out + '.vdz'))                      # ouvrir le compagnon : c'est le DXF qui s'ouvre
            self.assertEqual((len(w.docs), pathlib.Path(w.path).name), (n, 'plaque.dxf'))
            # exporter : sans compagnon ; un fichier sans compagnon (reçu) n'est pas écrasé par Ctrl+S
            from vectordrive.ui import export_dialog as ED
            exp = os.path.join(tmp, 'export.dxf')
            ED.export_items(w, [it for L in w.canvas.doc.layers for it in L.items], exp, {})
            self.assertTrue(os.path.isfile(exp))
            self.assertFalse(os.path.exists(exp + '.vdz'))
            self.assertTrue(w.open_path(exp))
            self.assertIsNone(w.path)
            w.modified = False

    def test_import_reads_the_companion(self):
        w = self.w
        w.new_document()
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'piece.svg')
            d = drawing()
            registry.save_document(d, f)
            companion.sync(d, f)
            with mock.patch.object(QFileDialog, 'getOpenFileName', return_value=(f, '')):
                w.import_dialog()
        self.assertEqual([t.text for t in texts(w.canvas.doc)], ['BFM'])    # avant : le texte en courbes
        w.modified = False


if __name__ == '__main__':
    unittest.main()
