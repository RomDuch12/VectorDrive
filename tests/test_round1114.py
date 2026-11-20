"""Round 1114 (demande du 20/11) : « support complet dwg » — ODA File Converter (gratuit, installé sur le poste) ;
ouvrir / importer, enregistrer / exporter, lot et glisser-déposer. Ici un faux convertisseur (un script) tient sa place ;
un essai avec le vrai, s'il est sur le poste."""
import os
import pathlib
import shutil
import struct
import sys
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1114.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

import ezdxf  # noqa: E402
from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Layer, Shape  # noqa: E402
from vectordrive.io import dwg, registry  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : pas de DWG'

#: le faux ODA File Converter : mêmes arguments ; « DWG » ici = un DXF sous l'extension .dwg ; CASSE dedans : un .err
FAKE = '''import os, shutil, sys
in_dir, out_dir, version, kind, recurse, audit, name = sys.argv[1:8]
src = os.path.join(in_dir, name)
log = os.environ.get('FAKE_ODA_LOG')
if log:
    with open(log, 'a', encoding='utf-8') as f:
        f.write(' '.join([version, kind, recurse, audit, name]) + '\\n')
data = open(src, 'rb').read()
stem = os.path.splitext(name)[0]
if b'LENT' in data:
    import time
    time.sleep(60)
if b'CASSE' in data:
    open(os.path.join(out_dir, name + '.err'), 'w').write('Error: fichier abime (essai)\\n')
    sys.exit(0)
shutil.copyfile(src, os.path.join(out_dir, stem + '.' + kind.lower()))
'''


def fake_dwg(path, layer='Plan', text=None):
    d = ezdxf.new('R2010')
    d.layers.add(layer)
    msp = d.modelspace()
    msp.add_circle((10, 10), 5, dxfattribs={'layer': layer})
    msp.add_lwpolyline([(0, 0), (30, 0), (30, 20), (0, 20)], close=True, dxfattribs={'layer': layer})
    if text:
        msp.add_text(text, dxfattribs={'layer': layer})
    d.saveas(path)
    return path


class Fake(unittest.TestCase):
    """ODA File Converter remplacé par le script ; le réglage F10 le désigne."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.script = os.path.join(self.tmp, 'faux_oda.py')
        pathlib.Path(self.script).write_text(FAKE, encoding='utf-8')
        self.log = os.path.join(self.tmp, 'appels.txt')
        self.settings = QSettings(os.path.join(self.tmp, 'r.ini'), QSettings.Format.IniFormat)
        self.settings.setValue(dwg.SETTING, self.script)
        real = dwg.command
        script = self.script
        p1 = mock.patch.object(dwg, 'command', lambda exe, *a: [sys.executable, script] + real(exe, *a)[1:])
        p2 = mock.patch.object(dwg, '_settings', lambda s: s if s is not None else self.settings)
        p3 = mock.patch.dict(os.environ, {'FAKE_ODA_LOG': self.log})
        for p in (p1, p2, p3):
            p.start()
            self.addCleanup(p.stop)

    def calls(self):
        return pathlib.Path(self.log).read_text(encoding='utf-8').split('\n')[:-1] if os.path.exists(self.log) else []


class Registry(unittest.TestCase):
    def test_dwg_is_a_format(self):
        f = registry.by_extension('Plan.DWG')
        self.assertIsNotNone(f, BEFORE)
        self.assertEqual(f.key, 'dwg')
        self.assertIs(registry.writer_for('x.dwg'), f)
        self.assertIn(f, registry.save_formats())
        self.assertIn('*.dwg', registry.filter_string())
        self.assertIn('*.dwg', registry.filter_string(write=True))
        from vectordrive.ui import export_dialog, file_browser, symbols
        self.assertEqual(export_dialog.kind_of(f), 'dxf')              # un calque par outil : comme le DXF
        self.assertIn('.dwg', file_browser.BROWSER_EXT)
        self.assertIn(('DWG (AutoCAD)', ('.dwg',)), file_browser.FILTERS)   # son filtre (1115)
        self.assertIn('.dwg', symbols.LIBRARY_EXT)
        self.assertTrue(symbols.external_reader('a.dwg'))              # ni fiche ni lecture d'office

    def test_options(self):
        from vectordrive.ui import options
        opts = {o.key: o for _tab, os_ in options.SPEC for o in os_}
        self.assertEqual(opts['import/oda'].kind, 'file')
        self.assertTrue(opts['import/oda'].extra.get('open'))          # « … » : choisir un programme, pas enregistrer
        self.assertIn('ODAFileConverter', opts['import/oda'].extra.get('filter', ''))
        self.assertEqual(tuple(opts['export/dwg_version'].choices), dwg.VERSIONS)
        self.assertEqual(opts['export/dwg_version'].default, dwg.DEFAULT_VERSION)


class Find(unittest.TestCase):
    def test_setting_then_program_files_newest(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        for v in ('21.1.0', '25.12.0', '9.9.0'):
            d = pathlib.Path(tmp, 'ODA', f'ODAFileConverter {v}')
            d.mkdir(parents=True)
            (d / 'ODAFileConverter.exe').write_bytes(b'')
        s = QSettings(os.path.join(tmp, 'r.ini'), QSettings.Format.IniFormat)
        env = {'ProgramFiles': tmp, 'ProgramW6432': '', 'ProgramFiles(x86)': ''}
        with mock.patch.dict(os.environ, env), mock.patch.object(shutil, 'which', lambda n: None):
            self.assertTrue(dwg.find(s).endswith(os.path.join('ODAFileConverter 25.12.0', 'ODAFileConverter.exe')))
            mine = os.path.join(tmp, 'ailleurs.exe')
            pathlib.Path(mine).write_bytes(b'')
            s.setValue(dwg.SETTING, f'"{mine}"')                     # (des guillemets collés avec le chemin)
            self.assertEqual(dwg.find(s), mine)
            s.setValue(dwg.SETTING, os.path.join(tmp, 'absent.exe'))   # le réglage périmé : on cherche
            self.assertIn('25.12.0', dwg.find(s))
        with mock.patch.dict(os.environ, {'ProgramFiles': os.path.join(tmp, 'rien'), 'ProgramW6432': '',
                                          'ProgramFiles(x86)': ''}), mock.patch.object(shutil, 'which', lambda n: None):
            self.assertEqual(dwg.find(QSettings(os.path.join(tmp, 'v.ini'), QSettings.Format.IniFormat)), '')

    def test_missing_converter_says_what_to_do(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        src = fake_dwg(os.path.join(tmp, 'a.dwg'))
        with mock.patch.object(dwg, 'find', lambda s=None: ''):
            with self.assertRaises(dwg.ConverterMissing) as cm:
                registry.open_document(src)
            self.assertIsInstance(cm.exception, ValueError)
            self.assertIn('F10', str(cm.exception))
            with self.assertRaises(dwg.ConverterMissing):
                registry.save_document(Document(), os.path.join(tmp, 'b.dwg'))
        import pickle                                                   # (rendue par un processus de lecture)
        back = pickle.loads(pickle.dumps(dwg.ConverterMissing('x')))
        self.assertIsInstance(back, dwg.ConverterMissing)


class ReadWrite(Fake):
    def test_open(self):
        src = fake_dwg(os.path.join(self.tmp, 'plan été.dwg'))         # (accents et espace : nom simple au convertisseur)
        doc = registry.open_document(src)
        self.assertEqual(doc.source_format, 'dwg')
        self.assertEqual(doc.source_path, src)
        self.assertIn('Plan', [L.name for L in doc.layers])
        self.assertGreaterEqual(sum(len(L.items) for L in doc.layers), 2)
        self.assertTrue(any('ODA File Converter' in r for r in doc.report))
        self.assertEqual(self.calls(), ['ACAD2018 DXF 0 1 dessin.dwg'])

    def test_save_with_the_chosen_version(self):
        doc = Document(layers=[Layer(name='A', items=[Shape(path=geom.Path([geom.rect(0, 0, 40, 20)]))])])
        out = os.path.join(self.tmp, 'sortie.dwg')
        registry.save_document(doc, out)
        self.settings.setValue(dwg.VERSION_SETTING, 'ACAD2013')
        registry.save_document(doc, out)                               # réécrit par-dessus
        self.settings.setValue(dwg.VERSION_SETTING, 'n importe quoi')
        registry.save_document(doc, out)
        self.assertEqual(self.calls(), ['ACAD2018 DWG 0 1 dessin.dxf', 'ACAD2013 DWG 0 1 dessin.dxf',
                                        'ACAD2018 DWG 0 1 dessin.dxf'])
        back = ezdxf.readfile(out)                                       # (le faux : le DXF tel quel)
        self.assertEqual(len(back.modelspace()), 1)
        self.assertFalse(os.path.exists(out + '.tmp'))
        self.assertTrue(any('AutoCAD 2018' in r for r in doc.report))
        again = registry.open_document(out)                              # relu
        self.assertEqual(sum(len(L.items) for L in again.layers), 1)

    def test_converter_error_is_reported(self):
        src = fake_dwg(os.path.join(self.tmp, 'abime.dwg'), text='CASSE')
        with self.assertRaises(ValueError) as cm:
            registry.open_document(src)
        self.assertIn('fichier abime (essai)', str(cm.exception))
        self.assertNotIsInstance(cm.exception, dwg.ConverterMissing)

    def test_cancel_and_timeout_stop_the_converter(self):
        import time
        from vectordrive.core import progress
        src = fake_dwg(os.path.join(self.tmp, 'lent.dwg'), text='LENT')
        t = time.time()
        with self.assertRaises(ValueError) as cm:
            dwg.read(src, timeout=1.0)
        self.assertIn('ne répond pas', str(cm.exception))
        self.assertLess(time.time() - t, 20)
        calls = []

        class Stop(Exception):
            pass

        def check():
            calls.append(1)
            if len(calls) > 3:
                raise Stop()
        t = time.time()
        with mock.patch.object(progress, 'check', check), self.assertRaises(Stop):
            dwg.read(src)                                                # Annuler : arrêté, pas 300 s d'attente
        self.assertLess(time.time() - t, 20)

    def test_no_tmp_left_when_the_target_is_locked(self):
        doc = Document(layers=[Layer(name='A', items=[Shape(path=geom.Path([geom.rect(0, 0, 40, 20)]))])])
        out = os.path.join(self.tmp, 'verrou.dwg')
        real = os.replace

        def locked(a, b):
            if str(b) == out:
                raise PermissionError('ouvert dans AutoCAD')
            return real(a, b)
        with mock.patch.object(os, 'replace', locked), self.assertRaises(PermissionError):
            registry.save_document(doc, out)
        self.assertFalse(os.path.exists(out + '.tmp'))
        self.assertFalse(os.path.exists(out))

    def test_batch_to_dwg(self):
        from vectordrive.io import batch
        src = fake_dwg(os.path.join(self.tmp, 'lot.dxf'))
        dst = os.path.join(self.tmp, 'lot.dwg')
        state, _s, _d = batch._convert_one(src, dst, True, False)
        self.assertEqual(state, 'fait')
        self.assertTrue(os.path.isfile(dst))
        state, _s, _d = batch._convert_one(dst, os.path.join(self.tmp, 'retour.svg'), True, False)   # et de DWG
        self.assertEqual(state, 'fait')


def dwg_bytes(entries, version=b'AC1018'):
    """Un en-tête de DWG avec son bloc d'aperçu : `entries` = [(code, données)]."""
    head = bytearray(version + b'\0' * (0x80 - len(version)))
    addr = 0x80
    struct.pack_into('<I', head, 0x0D, addr)
    table_len = 16 + 4 + 1 + 9 * len(entries)
    start = addr + table_len
    table, blob = b'', b''
    for code, data in entries:
        table += struct.pack('<BII', code, start + len(blob), len(data))
        blob += data
    block = dwg._SENTINEL + struct.pack('<I', len(table) + len(blob) + 1) + bytes([len(entries)]) + table
    return bytes(head) + block + blob


def dib(w=4, h=2):
    row = (b'\x00\x00\xff' * w).ljust((w * 3 + 3) // 4 * 4, b'\0')
    return struct.pack('<IiiHHIIiiII', 40, w, h, 1, 24, 0, len(row) * h, 2835, 2835, 0, 0) + row * h


class Preview(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def put(self, name, data):
        p = os.path.join(self.tmp, name)
        pathlib.Path(p).write_bytes(data)
        return p

    def test_bmp_and_png(self):
        from PySide6.QtCore import QBuffer, QIODevice
        from PySide6.QtGui import QImage
        img = QImage(6, 3, QImage.Format.Format_RGB32)
        img.fill(0x00ff00)
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        img.save(buf, 'PNG')
        png = bytes(buf.data())
        p = self.put('a.dwg', dwg_bytes([(1, b'\0' * 80), (2, dib())]))
        self.assertEqual(dwg.preview(p), ('bmp', dib()))
        p2 = self.put('b.dwg', dwg_bytes([(1, b'\0' * 80), (2, dib()), (6, png)], b'AC1032'))
        self.assertEqual(dwg.preview(p2), ('png', png))               # 2013 et après : le PNG d'abord
        from vectordrive.ui import symbols
        q = symbols.preview_image(p, 64)
        self.assertIsNotNone(q, BEFORE)
        self.assertEqual((q.width(), q.height()), (64, 64))
        self.assertEqual(q.pixelColor(32, 32).red(), 255)              # le rouge de l'aperçu, au centre
        self.assertEqual(q.pixelColor(32, 2).name(), '#ffffff')         # (4 × 2 : bandes blanches dessus et dessous)
        self.assertIsNotNone(symbols.preview_image(p2, 48))

    def test_not_a_preview(self):
        self.assertIsNone(dwg.preview(self.put('c.dwg', b'AC1009' + b'\0' * 200)))       # R12 : pas d'aperçu
        self.assertIsNone(dwg.preview(self.put('d.dwg', b'pas un dwg')))
        bad = bytearray(dwg_bytes([(2, dib())]))
        bad[0x80] ^= 0xFF                                                                 # sentinelle abîmée
        self.assertIsNone(dwg.preview(self.put('e.dwg', bytes(bad))))
        cut = dwg_bytes([(2, dib())])[:-10]                                               # tronqué
        self.assertIsNone(dwg.preview(self.put('f.dwg', cut)))
        self.assertIsNone(dwg.preview(os.path.join(self.tmp, 'absent.dwg')))
        from vectordrive.ui import symbols
        self.assertIsNone(symbols.preview_image(self.put('g.dwg', b'AC1009' + b'\0' * 200), 64))


def action(box, pick):
    """Le bouton « Page de téléchargement » (pick faux) ou « Choisir ODAFileConverter.exe… » (pick vrai)."""
    acts = [b for b in box.buttons() if box.buttonRole(b) == QMessageBox.ButtonRole.ActionRole]
    return next(b for b in acts if ('ODAFileConverter' in b.text()) == pick)


class Window(unittest.TestCase):
    def test_missing_converter_offers_the_page(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            tmp = tempfile.mkdtemp()
            self.addCleanup(shutil.rmtree, tmp, True)
            src = fake_dwg(os.path.join(tmp, 'a.dwg'))
            shown, opened, critical = [], [], []
            with mock.patch.object(dwg, 'find', lambda s=None: ''), \
                    mock.patch.object(QMessageBox, 'exec', lambda self: shown.append(self.text()) or 0), \
                    mock.patch.object(QMessageBox, 'clickedButton', lambda self: action(self, False)), \
                    mock.patch.object(QMessageBox, 'critical', lambda *a, **k: critical.append(a)), \
                    mock.patch('PySide6.QtGui.QDesktopServices.openUrl', lambda u: opened.append(u.toString())):
                self.assertFalse(w.open_path(src))
                self.assertEqual(critical, [])
                self.assertEqual(len(shown), 1)
                self.assertIn('ODA File Converter', shown[0])
                self.assertEqual(opened, [dwg.URL])                     # « Page de téléchargement »
                self.assertFalse(w._offer_oda(ValueError('autre')))
                w._file_dropped(src, 0.0, 0.0)                         # glissé-déposé : de même
                self.assertEqual(len(shown), 2)
                self.assertEqual(critical, [])
                other = fake_dwg(os.path.join(tmp, 'b.dwg'))
                with mock.patch.object(w, 'open_path', lambda p, preread=None: w._offer_oda(dwg.ConverterMissing(p))
                                       and False):
                    w.open_paths([src, other])                         # plusieurs à la fois : une seule fenêtre
                self.assertEqual(len(shown), 3)
                self.assertIsNone(w._oda_shown)
            chosen = os.path.join(tmp, 'ODAFileConverter.exe')
            with mock.patch.object(QMessageBox, 'exec', lambda self: 0), \
                    mock.patch.object(QMessageBox, 'clickedButton', lambda self: action(self, True)), \
                    mock.patch('PySide6.QtWidgets.QFileDialog.getOpenFileName', lambda *a, **k: (chosen, '')):
                self.assertTrue(w._offer_oda(dwg.ConverterMissing('x')))
            self.assertEqual(w.settings.value(dwg.SETTING), chosen)   # « Choisir ODAFileConverter.exe… » : retenu
        finally:
            w.settings.remove(dwg.SETTING)
            w.modified = False
            w.close()
            w.deleteLater()


@unittest.skipUnless(dwg.find(), 'ODA File Converter absent du poste')
class RealConverter(unittest.TestCase):
    def test_round_trip(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        doc = Document(layers=[Layer(name='A', items=[Shape(path=geom.Path([geom.rect(0, 0, 40, 20)]))])])
        out = os.path.join(tmp, 'vrai.dwg')
        registry.save_document(doc, out)
        self.assertTrue(pathlib.Path(out).read_bytes().startswith(b'AC10'))
        back = registry.open_document(out)
        bb = back.bbox()
        self.assertAlmostEqual(bb[2] - bb[0], 40.0, 3)


if __name__ == '__main__':
    unittest.main()
