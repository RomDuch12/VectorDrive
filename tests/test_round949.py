"""Round 949 : BAT — carnet de clients (nom et logo de tout format, copié dans le carnet), préréglages de
l'utilisateur, logo de tout format que VectorDrive lit."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r949.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ.setdefault('VECTORDRIVE_CLIENTS', os.path.join(tempfile.mkdtemp(), 'clients'))
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Shape  # noqa: E402
from vectordrive.io import proof, registry  # noqa: E402


def logo_file(folder, name):
    """Un petit dessin (deux rectangles) écrit dans le format de `name`."""
    d = Document()
    d.layers[0].items += [Shape(path=geom.Path([geom.rect(0, 0, 30, 12)])),
                          Shape(path=geom.Path([geom.rect(4, 3, 8, 6)]))]
    f = os.path.join(folder, name)
    registry.save_document(d, f)
    return f


class Book(unittest.TestCase):

    def test_client_book_keeps_names_and_logos(self):
        import importlib
        try:
            CL = importlib.import_module('vectordrive.io.clients')
        except ImportError:
            self.fail('pas de carnet de clients')                           # avant
        with tempfile.TemporaryDirectory() as tmp:
            book = os.path.join(tmp, 'carnet')
            c = CL.add(book, 'Dupont SA', logo_file(tmp, 'marque.svg'))
            self.assertEqual(c['logo'], 'logos/Dupont_SA.svg')              # copié dans le carnet, au nom du client
            self.assertTrue(os.path.isfile(CL.logo_path(book, c)))
            CL.add(book, 'Albert', '')
            self.assertEqual([x['nom'] for x in CL.load(book)], ['Albert', 'Dupont SA'])
            c = CL.add(book, 'dupont sa', logo_file(tmp, 'marque.dxf'))     # même client, logo d'un autre format
            self.assertEqual(len(CL.load(book)), 2)
            self.assertEqual(sorted(os.listdir(os.path.join(book, 'logos'))), ['dupont_sa.dxf'])
            self.assertEqual(CL.find(book, 'DUPONT SA')['logo'], 'logos/dupont_sa.dxf')
            self.assertTrue(CL.remove(book, 'Dupont SA'))
            self.assertFalse(CL.remove(book, 'Dupont SA'))
            self.assertEqual(os.listdir(os.path.join(book, 'logos')), [])
            self.assertEqual([x['nom'] for x in CL.load(book)], ['Albert'])
        self.assertEqual(str(CL.folder()), os.environ['VECTORDRIVE_CLIENTS'])  # essais : jamais le carnet du poste

    def test_any_drawing_vectordrive_reads_is_a_logo(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = logo_file(tmp, 'marque.plt')                                # HPGL : pas dans la liste d'avant
            vec = proof.logo_vector(f)
            self.assertIsNotNone(vec)                                       # avant : logo ignoré
            self.assertEqual(len(vec[0]), 2)
            plain, _w, _h = proof.build(Document(), proof.ProofInfo())
            with_logo, _w, _h = proof.build(Document(), proof.ProofInfo(logo2=f))
            self.assertGreater(len(with_logo), len(plain))


class Dialog(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def dialog(self, **kw):
        from vectordrive.ui.batdialog import BatDialog
        dlg = BatDialog(self.w, self.w.canvas.doc, proof.ProofInfo(**kw))
        self.addCleanup(dlg.close)
        return dlg

    def test_user_presets(self):
        dlg = self.dialog(company='ACME')
        save = getattr(dlg, 'save_preset', None)
        self.assertIsNotNone(save, 'pas de préréglages')                    # avant
        dlg.page.setCurrentIndex(dlg.page.findData('A3'))
        dlg.watermark.setChecked(True)
        dlg.margin.setValue(15)
        self.assertEqual(save('Grand format'), 'Grand format')
        other = self.dialog()                                               # un autre BAT, réglages d'office
        self.assertEqual((other.result_info().page, other.result_info().watermark), ('A4', False))
        k = other.preset.findData('Grand format')
        self.assertGreater(k, 0)                                            # retenu d'une fenêtre à l'autre
        other.preset.setCurrentIndex(k)
        other._preset_chosen(k)
        i = other.result_info()
        self.assertEqual((i.page, i.watermark, i.margin, i.company), ('A3', True, 15.0, 'ACME'))
        other.remove_preset()
        self.assertEqual(other.preset.count(), 1)
        self.assertLess(self.dialog().preset.findData('Grand format'), 0)

    def test_clients_in_the_window(self):
        from vectordrive.io import clients as CL
        dlg = self.dialog()
        with tempfile.TemporaryDirectory() as tmp:
            dlg.edits['client'].setText('Martin')
            dlg.set_logo(dlg.logo2, logo_file(tmp, 'martin.svg'))
            self.assertEqual(dlg.save_client(), 'Martin')
        book = CL.folder(self.w.settings)
        self.assertTrue(os.path.isfile(os.path.join(book, 'logos', 'Martin.svg')))     # la copie : l'original a disparu
        other = self.dialog()
        k = other.client_book.findData('Martin')
        self.assertGreater(k, 0)
        other.client_book.setCurrentIndex(k)
        other._client_chosen(k)
        i = other.result_info()
        self.assertEqual(i.client, 'Martin')
        self.assertEqual(pathlib.Path(i.logo2), pathlib.Path(book) / 'logos' / 'Martin.svg')
        self.assertIsNotNone(proof.logo_vector(i.logo2))
        other.remove_client()
        self.assertEqual(CL.load(book), [])


if __name__ == '__main__':
    unittest.main()
