"""Round 1000 : trois réponses du 14/11 — les symboles créés ont leurs textes TypeEdit modifiables d'office (16) ; à
l'écriture d'un VND, la copie en VD Géo d'un calque dont la police manque passe derrière son calque d'origine, que
TypeEdit ouvre (17) ; la liste « Imprimer » dans l'ordre sélection, page BAT, plaque, tout (18)."""
import os
import pathlib
import struct
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1000.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication, QFileDialog  # noqa: E402

from vectordrive.core import geom  # noqa: E402
from vectordrive.core import missing_fonts as MF  # noqa: E402
from vectordrive.core import text as TX  # noqa: E402
from vectordrive.core.document import Document, Layer, Shape, Text  # noqa: E402
from vectordrive.core.geom import Affine  # noqa: E402
from vectordrive.io import vnd  # noqa: E402
from vectordrive.io import vnd_write as W  # noqa: E402

app = QApplication.instance() or QApplication([])
KEYS = ('symboles/textes_vivants', 'symboles/textes_vivants_1000')
MISSING = 'Police Absente 1000'


def text(s, font='Arial', x=20, y=50):
    t = Text(text=s, font=font, size=8, matrix=Affine.translation(x, y))
    t.outline = TX.outline_for(t)
    return t


def rect():
    return Shape(path=geom.Path([geom.rect(10, 10, 100, 60)]))


def prefs(**values):
    from vectordrive.portable import settings
    st = settings()
    for k in KEYS:
        st.remove(k)
    for k, v in values.items():
        st.setValue(k.replace('__', '/'), v)
    st.sync()


def window():
    from vectordrive.ui.main_window import MainWindow
    w = MainWindow()
    w.settings.setValue('fenetre/plein_ecran', False)
    w.resize(1200, 800)
    w.show()
    app.processEvents()
    return w


def close(w):
    w.modified = False
    for t in getattr(w, 'docs', []):
        t.modified = False
    w.close()
    app.processEvents()


def flags(c):
    """(verrouillé, courant, outil, visible) d'un calque écrit."""
    return struct.unpack('<IIII', c.fields['attrs'][:16])


class SymbolTexts(unittest.TestCase):

    def tearDown(self):
        prefs()

    def test_option_on_and_no_longer_experimental(self):
        from vectordrive.ui import options as O
        o = O.BY_KEY['symboles/textes_vivants']
        self.assertIs(o.default, True)
        self.assertNotIn('expérimental', o.label)

    def test_turned_on_once_even_if_left_off(self):
        from vectordrive.ui.options import value
        prefs(symboles__textes_vivants=False)
        w = window()
        try:
            self.assertTrue(value(w.settings, 'symboles/textes_vivants'))
            self.assertEqual(str(w.settings.value('symboles/textes_vivants_1000')), '1')
            w.settings.setValue('symboles/textes_vivants', False)       # décochée ensuite : elle le reste
        finally:
            close(w)
        w = window()
        try:
            self.assertFalse(value(w.settings, 'symboles/textes_vivants'))
        finally:
            close(w)

    def test_a_symbol_created_keeps_its_text(self):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix='vd1000_'))
        prefs()
        w = window()
        try:
            w.settings.remove('symboles/textes_vivants')                # jamais réglée : d'office
            w.canvas.doc.add(text('Plaque 12'))
            out = tmp / 'essai.smb'
            with mock.patch.object(QFileDialog, 'getSaveFileName', return_value=(str(out), '')):
                w.save_as_symbol()
            self.assertIn(b'CParagraphe', out.read_bytes())
            w.settings.setValue('symboles/textes_vivants', False)
            out2 = tmp / 'courbes.smb'
            with mock.patch.object(QFileDialog, 'getSaveFileName', return_value=(str(out2), '')):
                w.save_as_symbol()
            self.assertNotIn(b'CParagraphe', out2.read_bytes())
        finally:
            close(w)


class CopyBehind(unittest.TestCase):

    def layers(self):
        orig, copy = Layer(name='Plan 1'), Layer(name='Plan 1' + MF.SUFFIX)
        orig.items.append(text('Plaque 12', MISSING))
        orig.visible = False
        copy.items.append(text('Plaque 12', MF.FONT))
        copy.extra = {MF.MARK: {'de': orig.id, 'polices': [MISSING]}}
        return orig, copy

    def test_the_original_first_and_visible(self):
        orig, copy = self.layers()
        report = []
        out = W._calques([copy, orig], report)                      # dans le dessin : la copie devant, montrée
        self.assertEqual([c.fields['layer_name'] for c in out], [orig.name, copy.name])
        self.assertEqual((flags(out[0])[1], flags(out[0])[3]), (1, 1))      # courant, visible : celui que TypeEdit ouvre
        self.assertEqual((flags(out[1])[1], flags(out[1])[3]), (0, 0))      # la copie cachée
        self.assertTrue(any('VD Géo' in r and orig.name in r for r in report), report)
        self.assertEqual((orig.visible, copy.visible), (False, True))       # le dessin n'a pas changé

    def test_found_by_its_name_alone(self):
        orig, copy = self.layers()
        copy.extra = {}                                             # VND relu sans son compagnon : plus de marque
        out = W._calques([copy, orig], [])
        self.assertEqual([c.fields['layer_name'] for c in out], [orig.name, copy.name])
        self.assertEqual([flags(c)[3] for c in out], [1, 0])

    def test_other_layers_keep_their_place(self):
        orig, copy = self.layers()
        other, hidden = Layer(name='Autre'), Layer(name='Cachée')
        other.items.append(rect())
        hidden.items.append(rect())
        hidden.visible = False
        out = W._calques([hidden, other, copy, orig], [])
        self.assertEqual([c.fields['layer_name'] for c in out], ['Autre', 'Cachée', orig.name, copy.name])
        self.assertEqual([flags(c)[3] for c in out], [1, 0, 1, 0])
        self.assertEqual([flags(c)[1] for c in out], [1, 0, 0, 0])

    def test_only_a_shown_copy_with_its_original(self):
        orig, copy = self.layers()
        self.assertEqual([flags(c)[3] for c in W._calques([copy], [])], [1])   # sans son original : un calque comme un autre
        report = []
        W._calques([copy, orig], report)
        self.assertEqual(len([r for r in report if 'VD Géo' in r]), 1)         # dit une fois
        orig.visible, copy.visible = True, False                    # la police est là : l'original montré
        report = []
        out = W._calques([copy, orig], report)
        self.assertEqual([c.fields['layer_name'] for c in out], [orig.name, copy.name])   # le montré devant, comme avant
        self.assertEqual([flags(c)[3] for c in out], [1, 0])
        self.assertFalse([r for r in report if 'VD Géo' in r])

    def test_reread_shows_the_copy_again(self):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix='vd1000_'))
        d = Document()
        d.add(rect())
        d.add(text('Plaque 12', MISSING))
        with mock.patch.object(W, 'curves_reason', return_value=None):      # comme TypeEdit l'écrirait
            data = W.write_document(d, live_texts=True)[0]
        src = tmp / 'plaque.vnd'
        src.write_bytes(data)
        w = window()
        try:
            self.assertTrue(w.open_path(str(src)))
            self.assertEqual([L.name.endswith(MF.SUFFIX) for L in w.canvas.doc.layers], [True, False])
            out = tmp / 'reecrit.vnd'
            self.assertTrue(w._write(str(out)))
            root, _ = vnd.parse(out.read_bytes())
            cq = [c for c in root.children if c.cls.name == 'CCalque']
            self.assertEqual([c.fields['layer_name'].endswith(MF.SUFFIX) for c in cq], [False, True])
            self.assertEqual([flags(c)[3] for c in cq], [1, 0])
            for companion in (True, False):
                if not companion:
                    from vectordrive.io import companion as C
                    C.companion_path(out).unlink()
                self.assertTrue(w.open_path(str(out)))
                doc = w.canvas.doc
                by = {L.name.endswith(MF.SUFFIX): L for L in doc.layers}
                self.assertEqual(len(doc.layers), 2)
                self.assertEqual((by[True].visible, by[False].visible), (True, False), companion)   # la copie montrée
                if companion:                                # sans lui, le texte en VD Géo est relu en courbes
                    self.assertEqual([it.font for it in by[True].items if isinstance(it, Text)], [MF.FONT])
                self.assertEqual([it.font for it in by[False].items if isinstance(it, Text)], [MISSING])
                self.assertEqual(doc.active_layer.name, by[True].name, companion)   # pas le calque caché
        finally:
            close(w)


class Companion(unittest.TestCase):
    """Le compagnon retrouve ses calques quel que soit le rang de la paire, et ne croise jamais copie et original."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix='vd1000_'))
        self.w = window()
        self.addCleanup(close, self.w)

    def source(self, layers=1):
        d = Document()
        d.layers[0].items += [rect(), text('Plaque 12', MISSING)]
        for k in range(1, layers):
            L = Layer(name=f'Plan {k + 1}')
            L.items += [rect(), text(f'Texte {k + 1}', MISSING, y=30 + 20 * k)]
            d.layers.append(L)
        with mock.patch.object(W, 'curves_reason', return_value=None):      # comme TypeEdit l'écrirait
            data = W.write_document(d, live_texts=True)[0]
        src = self.tmp / 'source.vnd'
        src.write_bytes(data)
        return src

    def pairs(self, doc):
        out = {}
        for L in doc.layers:
            if L.name.endswith(MF.SUFFIX):
                out[L.name[:-len(MF.SUFFIX)]] = (L, next(x for x in doc.layers if x.name == L.name[:-len(MF.SUFFIX)]))
        return out

    def check(self, doc, n):
        pairs = self.pairs(doc)
        self.assertEqual(len(pairs), n)
        for name, (copy, orig) in pairs.items():
            self.assertEqual((copy.visible, orig.visible), (True, False), name)
            t0 = [it for it in orig.items if isinstance(it, Text)]
            self.assertEqual([t.font for t in t0], [MISSING], name)         # l'original garde son texte TypeEdit
            self.assertTrue(all('vnd_obj' in t.extra for t in t0), name)
            self.assertEqual([t.font for t in copy.items if isinstance(t, Text)], [MF.FONT], name)
        self.assertFalse([r for r in doc.report if 'maintenant installée' in r], doc.report)

    def test_the_pair_behind_another_layer(self):
        w = self.w
        self.assertTrue(w.open_path(str(self.source())))
        other = Layer(name='Autre')
        other.items.append(rect())
        w.canvas.doc.layers.insert(0, other)                        # [autre, copie, original]
        out = self.tmp / 'trois.vnd'
        self.assertTrue(w._write(str(out)))
        root, _ = vnd.parse(out.read_bytes())
        names = [c.fields['layer_name'] for c in root.children if c.cls.name == 'CCalque']
        self.assertEqual([n.endswith(MF.SUFFIX) for n in names], [False, False, True])
        self.assertEqual(names[0], 'Autre')
        self.assertTrue(w.open_path(str(out)))
        self.assertEqual(len(w.canvas.doc.layers), 3)
        self.check(w.canvas.doc, 1)
        self.assertTrue(w._write(str(out)))                         # réécrit puis relu : toujours intact
        self.assertTrue(w.open_path(str(out)))
        self.check(w.canvas.doc, 1)

    def test_two_pairs(self):
        w = self.w
        self.assertTrue(w.open_path(str(self.source(2))))
        self.assertEqual(len(w.canvas.doc.layers), 4)               # [copie A, A, copie B, B]
        out = self.tmp / 'deux.vnd'
        self.assertTrue(w._write(str(out)))
        root, _ = vnd.parse(out.read_bytes())
        names = [c.fields['layer_name'] for c in root.children if c.cls.name == 'CCalque']
        self.assertEqual([n.endswith(MF.SUFFIX) for n in names], [False, True, False, True])   # chaque original devant
        self.assertTrue(w.open_path(str(out)))
        self.assertEqual(len(w.canvas.doc.layers), 4)
        self.check(w.canvas.doc, 2)

    def test_the_font_arrived_shows_the_original_again(self):
        w = self.w
        self.assertTrue(w.open_path(str(self.source())))
        out = self.tmp / 'police.vnd'
        self.assertTrue(w._write(str(out)))
        with mock.patch.object(MF, 'absent', return_value=[]):      # la police installée entre-temps
            self.assertTrue(w.open_path(str(out)))                  # avec le compagnon : l'état est revu
        doc = w.canvas.doc
        (copy, orig), = self.pairs(doc).values()
        self.assertEqual((copy.visible, orig.visible), (False, True))
        self.assertIs(doc.active_layer, orig)
        self.assertTrue([r for r in doc.report if 'maintenant installée' in r], doc.report)


class Order(unittest.TestCase):

    def pair(self, name='Plan 1'):
        orig, copy = Layer(name=name), Layer(name=name + MF.SUFFIX)
        orig.items.append(text('Plaque 12', MISSING))
        orig.visible = False
        copy.items.append(text('Plaque 12', MF.FONT))
        copy.extra = {MF.MARK: {'de': orig.id, 'polices': [MISSING]}}
        return orig, copy

    def test_the_order_is_a_function_shared_with_the_companion(self):
        orig, copy = self.pair()
        other = Layer(name='Autre')
        other.items.append(rect())
        order, behind = W.layer_order([other, copy, orig])
        self.assertEqual((order, behind), ([0, 2, 1], {copy.id: orig.id}))
        o2, c2 = self.pair('Plan 2')
        self.assertEqual(W.layer_order([copy, orig, c2, o2])[0], [1, 0, 3, 2])
        hidden = Layer(name='Cachée')
        hidden.items.append(rect())
        hidden.visible = False
        self.assertEqual(W.layer_order([hidden, other])[0], [1, 0])        # comme avant : le montré devant
        from vectordrive.io import companion
        self.assertEqual(companion._in_vnd_order([other, orig, copy], [other, copy, orig]), [0, 2, 1])
        self.assertEqual(companion._in_vnd_order([orig, copy, o2, c2], [copy, orig, c2, o2]), [1, 0, 3, 2])

    def test_report_lines(self):
        orig, copy = self.pair()
        orig.items.clear()                                          # rien à écrire : TypeEdit ouvrirait une page blanche
        report = []
        out = W._calques([copy, orig], report)
        self.assertEqual(out[0].fields['layer_name'], copy.name)
        self.assertEqual(flags(out[0])[3], 1)                       # la copie reste en tête, visible
        self.assertFalse([r for r in report if 'ouvrira sur le plan' in r], report)
        orig, copy = self.pair()
        other = Layer(name='Autre')
        other.items.append(rect())
        report = []
        W._calques([other, copy, orig], report)                     # « Autre » en tête : TypeEdit ouvre sur lui
        self.assertTrue([r for r in report if 'écrite derrière lui' in r], report)
        self.assertFalse([r for r in report if 'ouvrira sur le plan' in r], report)
        copy.items.append(rect())                                   # dessiné après l'ouverture, dans la copie
        report = []
        W._calques([copy, orig], report)
        self.assertTrue([r for r in report if 'ne les montrera pas' in r], report)

    def test_export_as_a_symbol_follows_the_setting(self):
        from vectordrive.io import smb
        tmp = pathlib.Path(tempfile.mkdtemp(prefix='vd1000_'))
        d = Document()
        d.add(text('Plaque 12'))
        was = smb.LIVE_TEXTS
        self.addCleanup(setattr, smb, 'LIVE_TEXTS', was)
        smb.LIVE_TEXTS = True
        smb.write_document(d, tmp / 'vivant.smb')
        self.assertIn(b'CParagraphe', (tmp / 'vivant.smb').read_bytes())
        smb.LIVE_TEXTS = False
        smb.write_document(d, tmp / 'courbes.smb')
        self.assertNotIn(b'CParagraphe', (tmp / 'courbes.smb').read_bytes())


class PrintOrder(unittest.TestCase):

    def test_selection_bat_plate_all(self):
        from vectordrive.ui import options as O
        from vectordrive.ui import print_dialog as P
        self.assertEqual([k for k, _label in P.WHAT], ['selection', 'bat', 'plaque', 'tout', 'calques'])
        self.assertEqual([k for k, _label in O.BY_KEY['impression/quoi'].choices], ['demander', 'bat', 'dessin'])
        d = Document()
        d.add(rect())
        dlg = P.PrintDialog(None, d, [d.layers[0].items[0]])
        self.assertEqual([dlg.what.itemData(i) for i in range(dlg.what.count())],
                         ['selection', 'bat'] + (['plaque'] if d.plate is not None else []) + ['tout', 'calques'])
        self.assertEqual(dlg.what.currentData(), 'selection')
        dlg.deleteLater()


if __name__ == '__main__':
    unittest.main()
