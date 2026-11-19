"""Round 1000 : trois réponses du 14/11 — les symboles créés ont leurs textes TypeEdit modifiables d'office (16) ; à
l'écriture d'un VND, la copie en VD Géo d'un calque dont la police manque passe derrière son calque d'origine, que
TypeEdit ouvre (17 ; depuis le round 1099, elle est écrite à sa place, pas en plus) ; la liste « Imprimer » dans
l'ordre sélection, page BAT, plaque, tout (18)."""
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


def pair(name='Plan 1'):
    """(original caché, sa copie en VD Géo montrée, marquée comme `copy_layers` la marque)."""
    orig, copy = Layer(name=name), Layer(name=name + MF.SUFFIX)
    orig.items.append(text('Plaque 12', MISSING))
    orig.visible = False
    copy.items.append(text('Plaque 12', MF.FONT))
    copy.extra = {MF.MARK: {'de': orig.id, 'polices': [MISSING],
                            MF.OBJECTS: {copy.items[0].id: [orig.items[0].id, MF.signature(copy.items[0])]}}}
    return orig, copy


def planes(data):
    """[(nom, (verrouillé, courant, outil, visible), nombre d'objets)] des plans d'un VND."""
    root, _ = vnd.parse(data)
    return [(c.fields['layer_name'], flags(c), len(c.children)) for c in root.children if c.cls.name == 'CCalque']


def doc_of(*layers):
    d = Document()
    d.layers = list(layers)
    return d


class CopyMerged(unittest.TestCase):
    """Round 1099 (demande du 19/11 : « ouverture TE produit un calque dupliqué VD géo… peut-on éviter cela ? ») : la
    copie n'est plus écrite derrière son calque, mais à sa place."""

    def test_the_copy_written_in_place_of_its_original(self):
        orig, copy = pair()
        d = doc_of(copy, orig)
        data, report = W.write_document(d)
        (name, f, n), = planes(data)
        self.assertEqual((name, f[1], f[3], n), (orig.name, 1, 1, 1))     # un plan, sous le nom d'origine, montré
        self.assertTrue(any('VD Géo' in r and f'« {orig.name} »' in r and "1 objet(s) TypeEdit d'origine" in r
                            for r in report), report)
        self.assertEqual([L.name for L in d.layers], [copy.name, orig.name])   # le dessin n'a pas changé
        self.assertEqual((copy.visible, orig.visible), (True, False))
        layers, info = MF.for_vnd(d.layers)
        self.assertEqual(len(layers), 1)
        self.assertIs(layers[0].items[0], orig.items[0])                    # l'objet d'origine, resté tel que copié
        self.assertEqual(layers[0].id, orig.id)
        (p,) = info.values()
        self.assertEqual((p['sorte'], p['repris']), ('fusion', 1))

    def test_modified_or_added_written_as_shown(self):
        orig, copy = pair()
        copy.items[0].matrix = Affine.translation(30, 50)                  # déplacé dans VectorDrive
        copy.items.append(rect())                                           # ajouté
        layers, _info = MF.for_vnd([copy, orig])
        self.assertIs(layers[0].items[0], copy.items[0])
        self.assertIs(layers[0].items[1], copy.items[1])
        _data, report = W.write_document(doc_of(copy, orig))
        self.assertTrue(any('2 modifié(s) ou ajouté(s)' in r for r in report), report)

    def test_hidden_copy_not_written(self):
        orig, copy = pair()
        orig.visible, copy.visible = True, False                            # la police est là : l'original montré
        layers, info = MF.for_vnd([copy, orig])
        self.assertEqual(layers, [orig])
        self.assertEqual([p['sorte'] for p in info.values()], ['cachee'])   # le compagnon la rendra
        data, report = W.write_document(doc_of(copy, orig))
        self.assertEqual([p[0] for p in planes(data)], [orig.name])
        self.assertFalse([r for r in report if 'VD Géo' in r], report)

    def test_found_by_its_name_alone(self):
        orig, copy = pair()
        copy.extra = {}                                                     # VND relu sans son compagnon : plus de marque
        layers, _info = MF.for_vnd([copy, orig])
        self.assertEqual([(L.name, L.visible) for L in layers], [(orig.name, True), (copy.name, False)])
        self.assertIs(layers[0].items, orig.items)          # sans correspondance : comme avant, l'original devant

    def test_other_layers_keep_their_place(self):
        orig, copy = pair()
        other, hidden = Layer(name='Autre'), Layer(name='Cachée')
        other.items.append(rect())
        hidden.items.append(rect())
        hidden.visible = False
        data, report = W.write_document(doc_of(hidden, other, copy, orig))
        p = planes(data)
        self.assertEqual([x[0] for x in p], ['Cachée', 'Autre', orig.name])  # l'ordre du dessin (round 1099)
        self.assertEqual([x[1][3] for x in p], [0, 1, 1])
        self.assertEqual([x[1][1] for x in p], [1, 0, 0])
        self.assertTrue(any('masqué' in r and 'page blanche' in r for r in report), report)

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
            doc = w.canvas.doc
            self.assertEqual([L.name.endswith(MF.SUFFIX) for L in doc.layers], [True, False])
            cl = doc.layers[0]
            k = next(i for i, it in enumerate(cl.items) if isinstance(it, Shape))
            x0 = cl.items[k].bbox()[0]
            cl.items[k] = cl.items[k].transformed(Affine.translation(5, 0))   # modifié dans VectorDrive
            out = tmp / 'reecrit.vnd'
            self.assertTrue(w._write(str(out)))
            (name, f, n), = planes(out.read_bytes())                       # un seul plan : pas de calque en double
            self.assertEqual((name, f[3], n), ('Plan 1', 1, 2))
            for companion in (True, False):
                if not companion:
                    from vectordrive.io import companion as C
                    C.companion_path(out).unlink()
                self.assertTrue(w.open_path(str(out)))
                doc = w.canvas.doc
                by = {L.name.endswith(MF.SUFFIX): L for L in doc.layers}
                self.assertEqual(len(doc.layers), 2, companion)
                self.assertEqual((by[True].visible, by[False].visible), (True, False), companion)   # la copie montrée
                self.assertEqual([it.font for it in by[True].items if isinstance(it, Text)], [MF.FONT], companion)
                self.assertEqual([it.font for it in by[False].items if isinstance(it, Text)], [MISSING], companion)
                self.assertTrue(all(it.extra.get('vnd_obj') is not None for it in by[False].items if isinstance(it, Text)))
                moved = [it.bbox()[0] for it in by[True].items if isinstance(it, Shape)]
                self.assertTrue(any(abs(x - (x0 + 5)) < 1e-3 for x in moved), (companion, moved, x0))
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
            self.assertTrue(t0 and all(t.extra.get('vnd_obj') is not None for t in t0), name)   # l'objet TypeEdit lui-même
            self.assertEqual([t.font for t in copy.items if isinstance(t, Text)], [MF.FONT], name)
        self.assertFalse([r for r in doc.report if 'maintenant installée' in r], doc.report)

    def names(self, path):
        return [p[0] for p in planes(path.read_bytes())]

    def test_the_pair_behind_another_layer(self):
        w = self.w
        self.assertTrue(w.open_path(str(self.source())))
        other = Layer(name='Autre')
        other.items.append(rect())
        w.canvas.doc.layers.insert(0, other)                        # [autre, copie, original]
        out = self.tmp / 'trois.vnd'
        self.assertTrue(w._write(str(out)))
        self.assertEqual(self.names(out), ['Autre', 'Plan 1'])      # la copie à la place de son calque
        self.assertTrue(w.open_path(str(out)))
        self.assertEqual([L.name for L in w.canvas.doc.layers][0], 'Autre')
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
        self.assertEqual(self.names(out), ['Plan 1', 'Plan 2'])
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

    def test_vnd_retouched_in_typeedit(self):
        from vectordrive.io import companion as C
        w = self.w
        self.assertTrue(w.open_path(str(self.source())))
        out = self.tmp / 'retouche.vnd'
        self.assertTrue(w._write(str(out)))
        with mock.patch.object(C, '_sha', return_value='0' * 64):   # le VND a changé depuis : il fait foi
            self.assertTrue(w.open_path(str(out)))
        doc = w.canvas.doc
        self.assertTrue([r for r in doc.report if 'a changé' in r], doc.report)
        self.assertEqual(len(doc.layers), 2)                        # la copie refaite à l'ouverture
        self.check(doc, 1)


class Order(unittest.TestCase):

    def test_the_order_of_the_drawing(self):
        other, hidden = Layer(name='Autre'), Layer(name='Cachée')
        other.items.append(rect())
        hidden.items.append(rect())
        hidden.visible = False
        self.assertEqual(W.write_order([hidden, other]), [0, 1])                # l'ordre du dessin (round 1099)
        self.assertEqual(W.write_order([hidden, other], None, True), [1, 0])    # réglage : le montré devant
        from vectordrive.io import companion
        self.assertEqual(companion._in_vnd_order([hidden, other], [hidden, other], 'dessin'), [0, 1])
        self.assertEqual(companion._in_vnd_order([other, hidden], [hidden, other], 'premier'), [1, 0])

    def test_companions_written_before_still_read(self):
        orig, copy = pair()
        other = Layer(name='Autre')
        other.items.append(rect())
        order, behind = W.layer_order([other, copy, orig])                  # l'ordre d'avant 0.956.0
        self.assertEqual((order, behind), ([0, 2, 1], {copy.id: orig.id}))
        o2, c2 = pair('Plan 2')
        self.assertEqual(W.layer_order([copy, orig, c2, o2])[0], [1, 0, 3, 2])
        from vectordrive.io import companion
        self.assertEqual(companion._in_vnd_order([other, orig, copy], [other, copy, orig]), [0, 2, 1])
        self.assertEqual(companion._in_vnd_order([orig, copy, o2, c2], [copy, orig, c2, o2]), [1, 0, 3, 2])

    def test_report_lines(self):
        other, hidden = Layer(name='Autre'), Layer(name='Cachée')
        other.items.append(rect())
        hidden.items.append(rect())
        hidden.visible = False
        report = []
        out = W._calques([hidden, other], report)
        self.assertEqual(out[0].fields['layer_name'], 'Cachée')
        self.assertTrue([r for r in report if 'masqué' in r and 'page blanche' in r], report)
        report = []
        out = W._calques([hidden, other], report, True)
        self.assertEqual(out[0].fields['layer_name'], 'Autre')
        self.assertTrue([r for r in report if 'écrit en premier' in r], report)
        report = []
        W._calques([other, hidden], report)
        self.assertEqual(report, [])

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
