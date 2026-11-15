"""Round 993 : impression, retour de l'atelier — « Ctrl+P imprimer : selection, plaque, certains calques ou tout, fit A4
avec zoom conseillé ou A6 A5 A3 A2 A1 ou pdf taille réelle ou zoom au choix ». Ctrl+P ouvre la fenêtre Imprimer ; le
BAT PDF passe à Ctrl+Maj+P."""
import os
import pathlib
import re
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Layer, Plate, Shape  # noqa: E402
from vectordrive.core.geom import Path  # noqa: E402
from vectordrive.ui import printing  # noqa: E402

app = QApplication.instance() or QApplication([])
PT = 72 / 25.4


def rect(x, y, w, h):
    return Shape(path=Path([geom.rect(x, y, w, h)]))


def media_box(pdf: bytes):
    m = re.search(rb'/MediaBox \[\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\]', pdf)
    return tuple(float(v) for v in m.groups())


class Scales(unittest.TestCase):

    def test_advised_and_sheets(self):
        self.assertEqual(printing.advised_scale(0.923), 0.5)
        self.assertEqual(printing.advised_scale(1.0), 1.0)
        self.assertEqual(printing.advised_scale(3.7), 2.0)
        self.assertEqual(printing.advised_scale(0.0001), 0.01)
        self.assertEqual(printing.advised_scale(0.45), 0.4)                    # 1:2,5, comme le BAT
        self.assertEqual(printing.advised_scale(0.045), 0.04)
        for fmt, size in (('A6', (105, 148)), ('A2', (420, 594)), ('A1', (594, 841))):
            w, h = printing.sheet_mm(fmt, 'portrait')
            self.assertEqual((round(w), round(h)), size)
        self.assertEqual(tuple(round(v) for v in printing.sheet_mm('A4', 'auto', (0, 0, 300, 150))), (297, 210))
        k, asked, tiles = printing.fit_scale({'echelle': 'conseillee', 'marge': 10.0}, (0, 0, 300, 150), 297, 210)
        self.assertEqual((k, asked, tiles), (0.5, None, None))


class Extent(unittest.TestCase):

    def test_plate_layers_selection(self):
        d = Document()
        d.plate = Plate(width=100.0, height=60.0)
        inside, outside = rect(10, 10, 20, 20), rect(150, 10, 20, 20)
        d.layers[0].items += [inside, outside]
        self.assertEqual(printing.extent(d, {'quoi': 'plaque'})[0], (0.0, 0.0, 100.0, 60.0))   # coupé au bord
        self.assertEqual(printing.extent(d, {'quoi': 'tout'})[0], (0.0, 0.0, 170.0, 60.0))
        self.assertEqual(printing.extent(d, {'quoi': 'selection'}, [outside]), ((150, 10, 170, 30), False))
        self.assertEqual(printing.extent(d, {'quoi': 'calques'}, [outside])[0], (0.0, 0.0, 170.0, 60.0))
        d.plate.visible = False
        self.assertFalse(printing.extent(d, {'quoi': 'plaque'})[1])            # plaque cachée : pas de pointillés

    def test_override_alone(self):
        from vectordrive.ui.print_dialog import override_for
        o = override_for({'quoi': 'tout', 'format': 'A4', 'echelle': 'zoom', 'zoom': 400.0, 'marge': 'x'})
        self.assertEqual((o['echelle'], o['marge'], o['mosaique'], o['reduire']), ('4.0', 10.0, False, True))
        real = override_for({'quoi': 'tout', 'format': 'reelle', 'echelle': 'ajuster', 'marge': -3})
        self.assertEqual((real['echelle'], real['marge'], real['reduire'], real['orientation']), ('1', 0.0, False, 'auto'))
        # F10 réglé en mosaïque : la fenêtre l'emporte (l'échelle montrée est celle imprimée)
        f10 = dict(printing.PRINT_DEFAULTS, mosaique=True)
        k, asked, tiles = printing.fit_scale(dict(f10, **o), (0, 0, 300, 150), 297, 210)
        self.assertIsNone(tiles)
        self.assertLess(k, 4.0)


class Window(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.close()
        cls.win.deleteLater()

    def setUp(self):
        self.doc = self.win.canvas.doc
        self.a, self.b = Layer(name='Gravure'), Layer(name='Découpe')
        self.doc.layers[:] = [self.a, self.b]
        self.doc.active = self.a.id
        self.doc.plate = Plate(width=300.0, height=150.0)
        self.r1, self.r2 = rect(10, 10, 50, 30), rect(200, 50, 80, 80)
        self.a.items[:] = [self.r1]
        self.b.items[:] = [self.r2]
        self.win.canvas.select([])
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix='vd993_'))

    def tearDown(self):
        for k in ('fenetre', 'format', 'echelle', 'quoi'):
            self.win.settings.remove(f'impression/{k}')

    def test_shortcuts(self):
        from vectordrive.ui import shortcuts as SC
        keys = SC.effective(self.win._default_shortcuts, 'vectordrive')      # le jeu VectorDrive, TE installé ou non
        self.assertEqual(keys['print'], ['Ctrl+P'])
        self.assertEqual(keys['proof'], ['Ctrl+Shift+P'])
        with mock.patch.object(type(self.win), 'print_choose', return_value=False) as choose:
            self.win.A['print'].trigger()
        choose.assert_called_once()

    def test_first_time_from_f10(self):
        from vectordrive.ui.print_dialog import PrintDialog
        for k in ('fenetre', 'format', 'orientation', 'marge', 'plaque', 'echelle', 'quoi'):
            self.win.settings.remove(f'impression/{k}')
        self.assertEqual(self.win._print_seed(), {})                          # rien réglé : tout d'office
        self.win.settings.setValue('impression/format', 'A3')
        self.win.settings.setValue('impression/echelle', '0.5')
        self.win.settings.setValue('impression/quoi', 'dessin')
        seed = self.win._print_seed()
        self.assertEqual((seed['format'], seed['echelle'], seed['zoom'], seed['quoi']), ('A3', 'zoom', 50.0, 'tout'))
        dlg = PrintDialog(None, self.doc, [], seed)
        self.assertEqual((dlg.values()['format'], dlg.values()['quoi']), ('A3', 'tout'))
        dlg.close()

    def test_saved_choices_of_another_drawing(self):
        from vectordrive.ui.print_dialog import PrintDialog
        self.b.visible = False
        dlg = PrintDialog(None, self.doc, [], {'quoi': 'calques', 'calques': ['autre-dessin'], 'zoom': 'abc',
                                               'marge': None})
        self.assertEqual(dlg.values()['calques'], [self.a.id])                # ses calques visibles, pas aucun
        self.assertEqual((dlg.values()['zoom'], dlg.values()['marge']), (100.0, 10.0))
        dlg.close()
        self.b.visible = True
        self.doc.plate = None
        dlg = PrintDialog(None, self.doc, [], {'quoi': 'plaque'})
        self.assertEqual(dlg.what.findData('plaque'), -1)                     # pas de plaque : pas proposée
        self.assertEqual(dlg.values()['quoi'], 'tout')
        dlg.close()
        self.win.settings.setValue('impression/fenetre', '{abîmé')
        with mock.patch('vectordrive.ui.print_dialog.PrintDialog.exec', return_value=0):
            self.assertFalse(self.win.print_choose())                         # réglage abîmé : la fenêtre s'ouvre

    def test_locked_pdf_written_beside(self):
        out = self.tmp / 'ouvert.pdf'
        out.write_bytes(b'%PDF-1.4 ancien')
        real_open = open

        def locked(f, mode='r', *a, **kw):
            if isinstance(f, (str, os.PathLike)) and mode == 'r+b' and pathlib.Path(f) == out:
                raise PermissionError(13, 'ouvert ailleurs')
            return real_open(f, mode, *a, **kw)
        params = {'quoi': 'tout', 'sortie': 'pdf', 'format': 'A4', 'orientation': 'auto', 'echelle': 'conseillee',
                  'zoom': 100.0, 'marge': 10.0, 'plaque': True, 'calques': [], 'fichier': str(out)}
        with mock.patch('builtins.open', locked):
            self.assertTrue(self.win.print_choose(dict(params)))
        self.assertEqual(out.read_bytes(), b'%PDF-1.4 ancien')                # pas touché
        beside = self.tmp / 'ouvert (2).pdf'
        self.assertTrue(beside.exists() and beside.stat().st_size > 0)
        self.assertIn('ouvert (2).pdf', self.win.statusBar().currentMessage())
        with mock.patch.object(type(self.win), 'print_dialog', return_value=True):   # rien écrit : dit, pas réussi
            self.assertFalse(self.win.print_choose(dict(params, fichier=str(self.tmp / 'jamais.pdf'))))
        self.assertIn('PDF non écrit', self.win.statusBar().currentMessage())

    def test_dialog(self):
        from vectordrive.ui.print_dialog import PrintDialog
        dlg = PrintDialog(None, self.doc, [])
        self.assertEqual(dlg.values()['quoi'], 'plaque')                       # sans sélection : la plaque
        self.assertIn('1:2 (50 %)', dlg.info.text())                           # 300 × 150 sur A4 : 1:2 conseillé
        self.assertIn('A4 paysage', dlg.info.text())
        dlg.format.setCurrentIndex(dlg.format.findData('reelle'))
        self.assertEqual(dlg.values()['sortie'], 'pdf')                        # la taille réelle : en PDF
        self.assertFalse(dlg.scale.isEnabled())
        self.assertIn('320 × 170 mm', dlg.info.text())
        dlg.output.setCurrentIndex(dlg.output.findData('imprimante'))
        self.assertEqual(dlg.values()['format'], 'A4')
        dlg.scale.setCurrentIndex(dlg.scale.findData('zoom'))
        dlg.zoom.setValue(25.0)
        self.assertIn('1:4 (25 %)', dlg.info.text())
        dlg.what.setCurrentIndex(dlg.what.findData('calques'))
        self.assertTrue(dlg.layers.isEnabled())
        dlg.layers.item(0).setCheckState(Qt.CheckState.Unchecked)
        self.assertEqual(dlg.values()['calques'], [self.b.id])
        dlg.close()
        sel = PrintDialog(None, self.doc, [self.r1])
        self.assertEqual(sel.values()['quoi'], 'selection')
        sel.close()

    def test_pdf_real_size_and_layers(self):
        out = self.tmp / 'reelle.pdf'
        ok = self.win.print_choose({'quoi': 'tout', 'sortie': 'pdf', 'format': 'reelle', 'orientation': 'auto',
                                    'echelle': 'conseillee', 'zoom': 100.0, 'marge': 10.0, 'plaque': True,
                                    'calques': [], 'fichier': str(out)})
        self.assertTrue(ok)
        x0, y0, x1, y1 = media_box(out.read_bytes())
        self.assertAlmostEqual((x1 - x0) / PT, 320.0, delta=0.6)
        self.assertAlmostEqual((y1 - y0) / PT, 170.0, delta=0.6)
        self.assertAlmostEqual(printing.LAST['scale'], 1.0, places=3)             # à 1:1, sur sa feuille
        seen = {}
        real = printing.print_drawing

        def spy(doc, printer, opts=None, items=None):
            seen['items'], seen['opts'] = items, opts
            return real(doc, printer, opts, items)
        with mock.patch.object(printing, 'print_drawing', spy):
            self.assertTrue(self.win.print_choose({'quoi': 'calques', 'calques': [self.b.id], 'sortie': 'pdf',
                                                   'format': 'A5', 'orientation': 'auto', 'echelle': 'zoom',
                                                   'zoom': 50.0, 'marge': 5.0, 'plaque': False,
                                                   'fichier': str(self.tmp / 'calque.pdf')}))
        self.assertEqual(seen['items'], [self.r2])
        self.assertEqual((seen['opts']['echelle'], seen['opts']['format']), ('0.5', 'A5'))
        x0, y0, x1, y1 = media_box((self.tmp / 'calque.pdf').read_bytes())
        self.assertEqual(sorted((round((x1 - x0) / PT), round((y1 - y0) / PT))), [148, 210])
        self.assertIn('"quoi": "calques"', str(self.win.settings.value('impression/fenetre')))   # retenu

    def test_nothing_chosen(self):
        self.assertFalse(self.win.print_choose({'quoi': 'calques', 'calques': [], 'sortie': 'pdf', 'format': 'A4',
                                                'fichier': str(self.tmp / 'vide.pdf')}))
        self.assertFalse((self.tmp / 'vide.pdf').exists())


if __name__ == '__main__':
    unittest.main()
