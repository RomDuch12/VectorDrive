"""Round 1075 : réponse du 15/11 à la question 29 — « BaT + devis devient un pdf de 2 pages (technique séparé prix) ».
Un plugin donne la page des prix (`Api.add_bat_page`) : le BAT a deux pages, la page technique sans les prix. Données
synthétiques (deux carrés)."""
import io
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1075.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from pypdf import PdfReader  # noqa: E402

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Shape  # noqa: E402
from vectordrive.io import proof  # noqa: E402
from vectordrive.plugins import REGISTRY, Api, PluginInfo  # noqa: E402


def two_squares():
    d = Document()
    d.plate = None
    d.add(Shape(path=geom.Path([geom.rect(0, 0, 20, 20)])))
    d.add(Shape(path=geom.Path([geom.rect(40, 0, 20, 20)])))
    return d


def info(**kw):
    kw.setdefault('title_block', False)
    kw.setdefault('legend', False)
    return proof.ProofInfo(**kw)


class PricePage(unittest.TestCase):

    def setUp(self):
        self.calls = {'page': 0, 'price': 0}
        self.seen = []

        def page(doc, eng, inf):
            self.calls['page'] += 1
            self.seen.append(len(eng))
            return 'Devis', ['Gravure 1', '   Standard : 10,00 € HT', '', 'Total : 20,00 € HT']

        def price(objs):
            self.calls['price'] += 1
            return '10,00 € HT'
        self.page, self.price = page, price
        self.old = (list(REGISTRY.bat_pages), list(REGISTRY.bat_prices))
        self.folder = pathlib.Path(tempfile.mkdtemp())

    def tearDown(self):
        REGISTRY.bat_pages[:], REGISTRY.bat_prices[:] = self.old

    def pages(self, inf):
        p = self.folder / 'bat.pdf'
        proof.write(two_squares(), p, inf)
        return PdfReader(str(p), strict=True).pages

    def test_api_and_setting(self):
        self.assertTrue(proof.ProofInfo().price_page)                      # d'office : les prix à part
        self.assertIn('price_page', proof.LAYOUT_FIELDS)                   # gardé avec la mise en page
        api = Api(REGISTRY, PluginInfo('essai1075', name='Essai'))
        api.add_bat_page(self.page)
        self.assertIn(self.page, REGISTRY.bat_pages)

    def test_two_pages_and_the_technical_one_has_no_prices(self):
        REGISTRY.bat_prices.append(self.price)
        REGISTRY.bat_pages.append(self.page)
        pages = self.pages(info(dims_each=True))
        self.assertEqual(len(pages), 2)
        for pg in pages:
            self.assertIsNotNone(pg.get('/Resources'))                     # chaque page déclare ses ressources
        self.assertEqual(self.calls['price'], 0)                           # pas de prix sur la page technique
        self.assertEqual(self.seen, [2])                                   # les deux gravures données au plugin

    def test_unticked_one_page_with_prices_as_before(self):
        REGISTRY.bat_prices.append(self.price)
        REGISTRY.bat_pages.append(self.page)
        self.assertEqual(len(self.pages(info(dims_each=True, price_page=False))), 1)
        self.assertEqual(self.calls['page'], 0)
        self.assertGreater(self.calls['price'], 0)                         # les prix par gravure, comme avant
        self.calls['price'] = 0
        self.assertEqual(len(self.pages(info(dims_each=True, prices=False))), 1)   # aucun prix : aucune page
        self.assertEqual((self.calls['page'], self.calls['price']), (0, 0))

    def test_no_quote_or_failing_plugin_one_page(self):
        REGISTRY.bat_pages.append(lambda d, e, i: None)                    # pas de devis réglé
        self.assertEqual(len(self.pages(info())), 1)

        def broken(d, e, i):
            raise RuntimeError('devis en défaut')
        REGISTRY.bat_pages[:] = [broken]
        self.assertEqual(len(self.pages(info())), 1)                       # jamais d'erreur : la page technique
        self.assertEqual(proof.price_pages(two_squares(), info()), [])

    def test_without_plugin_the_pdf_is_unchanged(self):
        REGISTRY.bat_pages[:] = []
        raw = proof.pdf_bytes(['0 0 m 10 10 l S'], 100.0, 50.0, [], 'essai')
        self.assertIn(b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>', raw)
        self.assertFalse(proof.price_page_wanted(info()))

    def test_multipage_pdf_shares_images(self):
        img = (2, 1, __import__('zlib').compress(b'\x00\x00\x00\xff\xff\xff'), None)
        raw = proof.pdf_bytes(['q 1 0 0 1 0 0 cm /Im0 Do Q'], 100.0, 50.0, [img], 'essai',
                              more=[['0 0 m 10 10 l S'], ['q 1 0 0 1 0 0 cm /Im0 Do Q']])
        pages = PdfReader(io.BytesIO(raw), strict=True).pages
        self.assertEqual(len(pages), 3)
        for pg in pages:
            self.assertIn('/Im0', pg['/Resources']['/XObject'])           # l'image (le logo) sur chaque page
        self.assertEqual(raw.count(b'/Subtype /Image'), 1)                 # écrite une seule fois

    def test_long_price_list_continues_on_the_next_page(self):
        inf = info(client='Client 1', reference='R1')
        short = proof.price_page_prims(inf, 'Devis', ['ligne'], 210.0, 297.0)
        self.assertEqual(len(short), 1)
        long = proof.price_page_prims(inf, 'Devis', [f'ligne {k}' for k in range(150)], 210.0, 297.0)
        self.assertGreaterEqual(len(long), 3)                              # la suite sur les pages suivantes
        labels = 0
        for page in long:
            for pr in page:
                bb = pr.path.bbox() if pr.path is not None else None
                if bb:
                    self.assertGreaterEqual(bb[1], inf.margin - 0.5)       # rien sous la marge
            labels += len(page)
        self.assertGreater(labels, 150)                                    # aucune ligne perdue
        huge = proof.price_page_prims(inf, 'Devis', [f'ligne {k}' for k in range(5000)], 210.0, 297.0)
        self.assertEqual(len(huge), proof.PRICE_PAGES_MAX)                 # bornée
        lines = [f'ligne {k}' for k in range(150)]
        REGISTRY.bat_pages.append(lambda d, e, i: ('Devis', lines))
        _prims, PW, PH = proof.build(two_squares(), info())                # format de la page (paysage ici)
        want = len(proof.price_page_prims(info(), 'Devis', lines, PW, PH))
        self.assertGreater(want, 1)
        self.assertEqual(len(self.pages(info())), 1 + want)                # le PDF les écrit toutes

    def test_preview_has_no_prices_either(self):
        REGISTRY.bat_prices.append(self.price)
        REGISTRY.bat_pages.append(self.page)
        proof.build(two_squares(), info(dims_each=True))
        self.assertEqual(self.calls, {'page': 0, 'price': 0})              # aperçu : ni prix ni devis calculé


if __name__ == '__main__':
    unittest.main()
