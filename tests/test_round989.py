"""Round 989 : polices, retours de l'atelier — un dessin ouvert dont des textes sont dans une police absente du poste :
ces textes passent en VD Géo dans une copie de leur calque, placée devant lui, l'original caché et intact (réglage) ;
réenregistré en VND et rouvert, avec ou sans son compagnon, le dessin garde ses deux calques ; une police installée
VectorDrive ouvert est trouvée sans le redémarrer (au retour dans la fenêtre, à l'ouverture d'une liste de polices), les
textes qui l'attendaient se redessinent ; la liste des polices montre aussi les TrueType arrivées depuis. Le compagnon
d'un VND retrouve ses calques par leur nom quand l'écriture du VND a passé un calque devant."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r989.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from vectordrive.core import fonts as F  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core import text as TX  # noqa: E402
from vectordrive.core.document import Document, Group, Layer, Shape, Text  # noqa: E402
from vectordrive.core.geom import Affine  # noqa: E402
from vectordrive.io import companion  # noqa: E402
from vectordrive.io import vnd  # noqa: E402
from vectordrive.io import vnd_write as W  # noqa: E402

app = QApplication.instance() or QApplication([])
MISSING = 'Police Absente 989'


def text(s, font='Arial', x=20, y=50):
    t = Text(text=s, font=font, size=8, matrix=Affine.translation(x, y))
    t.outline = TX.outline_for(t)
    return t


def te(t):
    """Texte lu d'un VND : son objet TypeEdit d'origine (dessiné à la lecture, police de remplacement)."""
    t.extra['vnd_obj'] = object()
    return t


def rect():
    return Shape(path=geom.Path([geom.rect(10, 10, 100, 60)]))


def make_font(path: pathlib.Path, family: str, width: int = 1000) -> pathlib.Path:
    """Petite police TrueType (A rectangle, de chasse `width` sur 1000, et l'espace)."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    def box():
        p = TTGlyphPen(None)
        p.moveTo((width // 10, 0))
        p.lineTo((width // 10, 700))
        p.lineTo((width - width // 10, 700))
        p.lineTo((width - width // 10, 0))
        p.closePath()
        return p.glyph()
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(['.notdef', 'A', 'space'])
    fb.setupCharacterMap({0x41: 'A', 0x20: 'space'})
    fb.setupGlyf({'.notdef': box(), 'A': box(), 'space': TTGlyphPen(None).glyph()})
    fb.setupHorizontalMetrics({'.notdef': (width, width // 10), 'A': (width, width // 10), 'space': (300, 0)})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({'familyName': family, 'styleName': 'Regular'})
    fb.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200, sCapHeight=700)
    fb.setupPost()
    path.parent.mkdir(parents=True, exist_ok=True)
    fb.save(str(path))
    return path


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


def walk(o):
    yield o
    for c in o.children:
        yield from walk(c)


def leaves(items):
    for it in items:
        yield it
        yield from leaves(getattr(it, 'children', None) or ())


class CopyLayers(unittest.TestCase):

    def test_copy_in_vd_geo_before_the_untouched_original(self):
        from vectordrive.core import missing_fonts as MF
        d = Document()
        L = d.layers[0]
        kept, gone = te(text('Gardée')), te(text('Absente', MISSING))
        mixed = te(text('Mixte'))
        TX.set_char_fx(mixed, {1: {'font': MISSING}})                  # une lettre dans la police absente
        g = Group(children=[te(text('Dans le groupe', MISSING, y=30)), rect()])
        L.items += [kept, gone, mixed, g]
        before = list(L.items)
        n, names, made, back = MF.copy_layers(d)
        self.assertEqual((n, names, back), (3, [MISSING], []))
        self.assertEqual([x.name for x in d.layers], [f'{L.name} — VD Géo', L.name])   # la copie devant
        copy = d.layers[0]
        self.assertFalse(L.visible)
        self.assertTrue(copy.visible)
        self.assertTrue(all(a is b for a, b in zip(L.items, before)) and len(L.items) == 4)
        self.assertEqual((gone.font, g.children[0].font, TX.char_fx(mixed)[1]['font']), (MISSING,) * 3)
        texts = [it for it in leaves(copy.items) if isinstance(it, Text)]
        self.assertEqual([it.font for it in texts], ['Arial', 'VD Géo', 'Arial', 'VD Géo'])
        self.assertEqual(TX.char_fx(texts[2])[1]['font'], 'VD Géo')
        self.assertTrue(all(it.outline and it.outline.contours for it in texts))
        self.assertFalse({it.id for it in leaves(copy.items)} & {it.id for it in leaves(L.items)})   # objets neufs
        self.assertIs(d.active_layer, copy)                  # sans calque actif : le premier, donc sa copie
        self.assertEqual(MF.copy_layers(d)[0], 0)             # pas deux fois

    def test_copy_drops_typeedit_objects(self):
        from vectordrive.core import missing_fonts as MF
        d = Document()
        t, s = te(text('Absente', MISSING)), rect()
        s.extra['vnd_obj'] = object()
        d.layers[0].items += [t, s]
        MF.copy_layers(d)
        self.assertTrue(all('vnd_obj' in it.extra for it in d.layers[1].items))
        self.assertFalse([it for it in d.layers[0].items if 'vnd_obj' in it.extra])

    def test_text_read_with_its_outline_stays(self):
        from vectordrive.core import missing_fonts as MF
        d = Document()
        d.layers[0].items.append(text('Absente', MISSING))     # relu d'un VDZ : son tracé tel qu'écrit
        self.assertEqual(MF.copy_layers(d)[0], 0)
        self.assertEqual(len(d.layers), 1)
        bare = Text(text='Sans tracé', font=MISSING, size=8)
        d.layers[0].items.append(bare)
        self.assertEqual(MF.copy_layers(d)[0], 1)

    def test_operations_and_linked_copies_follow(self):
        from vectordrive.core import missing_fonts as MF
        d = Document()
        t, r = te(text('Absente', MISSING)), rect()
        lk = rect()
        lk.extra['link'] = {'master': r.id}
        d.layers[0].items += [t, r, lk]
        d.extra['fao'] = {'operations': [{'items': [t.id, r.id]}, {'items': ['autre']}]}
        MF.copy_layers(d)
        ct, cr, clk = d.layers[0].items
        self.assertEqual(clk.extra['link'], {'master': cr.id})              # la copie liée suit son modèle copié
        self.assertEqual(lk.extra['link'], {'master': r.id})
        ops = d.extra['fao']['operations']
        self.assertEqual(ops[0]['items'], [t.id, r.id, ct.id, cr.id])        # le calque caché ne s'usine pas
        self.assertEqual(ops[1]['items'], ['autre'])

    def test_copy_found_by_name_only_one_shown(self):
        from vectordrive.core import missing_fonts as MF
        d = Document()
        L = d.layers[0]
        L.items.append(te(text('Absente', MISSING)))
        c = Layer(name=L.name + MF.SUFFIX)
        c.items.append(text('Absente', 'VD Géo'))
        d.layers.insert(0, c)                               # VND relu sans son compagnon : tous ses calques montrés
        self.assertEqual(MF.copy_layers(d)[0], 0)           # pas de deuxième copie
        self.assertEqual((c.visible, L.visible), (True, False))
        L.items[0].font = 'Arial'                           # sur un poste où la police est installée
        L.visible = True
        del c.extra[MF.MARK]
        d.active = c.id
        n, names, made, back = MF.copy_layers(d)
        self.assertEqual((c.visible, L.visible, back), (False, True, [c.name]))   # pas usiné deux fois
        self.assertIs(d.active_layer, L)

    def test_surface_layer_left_alone(self):
        from vectordrive.core import missing_fonts as MF
        d = Document()
        L = d.layers[0]
        L.extra['surface2d'] = {'face': 'F1', 'z': -2.0}    # ses opérations n'usinent que lui
        L.items.append(te(text('Absente', MISSING)))
        self.assertEqual(MF.copy_layers(d)[0], 0)
        self.assertEqual(len(d.layers), 1)
        self.assertTrue(L.visible)


class OpenFile(unittest.TestCase):

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix='vd989_'))
        d = Document()
        d.add(rect())
        d.add(text('Plaque 12', MISSING))
        with mock.patch.object(W, 'curves_reason', return_value=None):      # comme TypeEdit l'écrirait
            data = W.write_document(d, live_texts=True)[0]
        self.assertIn(MISSING, vnd.font_table(data)[1])
        self.vnd = self.tmp / 'plaque.vnd'
        self.vnd.write_bytes(data)

    def tearDown(self):
        from vectordrive.portable import settings
        settings().remove('ouvrir/police_absente')

    def check(self, doc, marked=True):
        from vectordrive.core import missing_fonts as MF
        self.assertEqual(len(doc.layers), 2, [L.name for L in doc.layers])
        copy, orig = sorted(doc.layers, key=lambda L: not L.name.endswith(MF.SUFFIX))   # round 1000 : un VND réécrit
        # a la copie derrière son calque d'origine
        self.assertEqual(copy.name, orig.name + ' — VD Géo')
        self.assertEqual((copy.visible, orig.visible), (True, False))
        t0 = next(it for it in orig.items if isinstance(it, Text))
        self.assertEqual(t0.font, MISSING)
        self.assertIn('vnd_obj', t0.extra)
        self.assertEqual(MF.MARK in copy.extra, marked)
        return copy, orig

    def test_open_save_as_vnd_and_reopen(self):
        w = window()
        try:
            self.assertTrue(w.open_path(str(self.vnd)))
            doc = w.canvas.doc
            copy, orig = self.check(doc)
            t1 = next(it for it in copy.items if isinstance(it, Text))
            self.assertEqual(t1.font, 'VD Géo')
            self.assertNotIn('vnd_obj', t1.extra)
            self.assertIs(doc.active_layer, copy)
            self.assertTrue(doc.report[0].startswith(f'1 texte(s) en police absente ({MISSING})'), doc.report[0])
            out = self.tmp / 'reecrit.vnd'
            self.assertTrue(w._write(str(out)))
            root, _ = vnd.parse(out.read_bytes())
            objs = list(walk(root))
            self.assertEqual(sum(o.cls.name == 'CParagraphe' for o in objs), 1)   # celui d'origine, tel quel
            guids = [o.fields['guid'] for o in objs if o.fields.get('guid')]
            self.assertEqual(len(guids), len(set(guids)))                        # aucun objet en double
            self.assertTrue(companion.companion_path(out).exists())
            self.assertTrue(w.open_path(str(out)))                              # avec son compagnon
            copy, orig = self.check(w.canvas.doc)
            self.assertEqual([it.font for it in copy.items if isinstance(it, Text)], ['VD Géo'])
            companion.companion_path(out).unlink()
            self.assertTrue(w.open_path(str(out)))                              # sans : la copie trouvée par son nom
            self.check(w.canvas.doc)
        finally:
            close(w)

    def test_copy_in_the_typeedit_boxes(self):
        from vectordrive.core import missing_fonts as MF
        d = Document()
        d.add(text('PLAQUE GRAVEE 1234', MISSING))
        with mock.patch.object(W, 'curves_reason', return_value=None):
            data = W.write_document(d, live_texts=True)[0]
        p = self.tmp / 'boites.vnd'
        p.write_bytes(data)
        doc = vnd.read(p)
        MF.copy_layers(doc)
        copy, orig = doc.layers
        t0 = next(it for it in orig.items if isinstance(it, Text))
        t1 = next(it for it in copy.items if isinstance(it, Text))
        a, b = t0.outline.bbox(), t1.outline.bbox()
        self.assertAlmostEqual((a[0] + a[2]) / 2, (b[0] + b[2]) / 2, delta=0.3)   # VD Géo dans les boîtes de TypeEdit
        c = TX.outline_for(t1).bbox()
        self.assertAlmostEqual(c[2] - c[0], b[2] - b[0], delta=0.3)              # modifié : la même largeur
        self.assertAlmostEqual((c[0] + c[2]) / 2, (b[0] + b[2]) / 2, delta=0.3)

    def test_option_keeps_the_replacement_font(self):
        from vectordrive.portable import settings
        w = window()
        try:
            settings().setValue('ouvrir/police_absente', 'remplacement')
            w.settings.setValue('ouvrir/police_absente', 'remplacement')
            self.assertTrue(w.open_path(str(self.vnd)))
            self.assertEqual(len(w.canvas.doc.layers), 1)
            self.assertTrue(w.canvas.doc.layers[0].visible)
            w.settings.remove('ouvrir/police_absente')
            self.assertTrue(w.open_path(str(self.vnd)))
            self.assertEqual(len(w.canvas.doc.layers), 2)                    # d'office : la copie
        finally:
            close(w)


class CompanionOrder(unittest.TestCase):

    def test_hidden_first_layer_reopened(self):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix='vd989_'))
        w = window()
        try:
            doc = w.canvas.doc
            a, b = Layer(name='Cachée'), Layer(name='Montrée')
            a.items.append(rect())
            a.visible = False
            b.items.append(text('Texte'))
            doc.layers[:] = [a, b]
            doc.active = b.id
            out = tmp / 'ordre.vnd'
            self.assertTrue(w._write(str(out)))
            self.assertTrue(companion.companion_path(out).exists())
            self.assertTrue(w.open_path(str(out)))
            d2 = w.canvas.doc
            self.assertEqual([L.name for L in d2.layers], ['Montrée', 'Cachée'])   # le VND : le calque montré devant
            self.assertEqual([L.visible for L in d2.layers], [True, False])
            self.assertEqual([L.id for L in d2.layers], [b.id, a.id])               # repris du compagnon
            self.assertIsInstance(d2.layers[0].items[0], Text)
            self.assertIsInstance(d2.layers[1].items[0], Shape)
        finally:
            close(w)

    def test_two_layers_with_the_same_name(self):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix='vd989_'))
        w = window()
        try:
            doc = w.canvas.doc
            a, b, c = Layer(name='Plan'), Layer(name='Plan'), Layer(name='Fin')
            a.items.append(rect())
            a.visible = False
            b.items.append(text('Texte'))
            c.items.append(rect())
            doc.layers[:] = [a, b, c]
            doc.active = b.id
            out = tmp / 'memes_noms.vnd'
            self.assertTrue(w._write(str(out)))
            self.assertTrue(w.open_path(str(out)))
            d2 = w.canvas.doc
            self.assertEqual([L.id for L in d2.layers], [b.id, a.id, c.id])         # pas échangés
            self.assertEqual([L.visible for L in d2.layers], [True, False, True])
            self.assertIsInstance(d2.layers[0].items[0], Text)
        finally:
            close(w)


@unittest.skipUnless(os.environ.get('VECTORDRIVE_CACHE'), 'dossier de polices des essais (package tests)')
class InstalledWhileOpen(unittest.TestCase):

    def setUp(self):
        F.families()
        F.rescan()                                            # l'inventaire à jour avant l'essai
        self.paths = []

    def tearDown(self):
        for p in self.paths:
            p.unlink(missing_ok=True)
        F.rescan()

    def install(self, name, file, width=1000):
        p = make_font(F.user_font_dir() / file, name, width)
        self.paths.append(p)
        return p

    def test_typeedit_text_redrawn_in_its_boxes(self):
        name = 'Essai Etroite 989'
        d = Document()
        d.add(text('AAAA', name))
        with mock.patch.object(W, 'curves_reason', return_value=None):
            data = W.write_document(d, live_texts=True)[0]
        p = pathlib.Path(tempfile.mkdtemp(prefix='vd989_')) / 'etroite.vnd'
        p.write_bytes(data)
        w = window()
        try:
            self.assertTrue(w.open_path(str(p)))
            orig = w.canvas.doc.layers[1]
            t = next(it for it in orig.items if isinstance(it, Text))
            boxes = t.extra['vnd_obj'].fields['boxes']
            centres = [sum(bx[k] for k in (0, 2, 4, 6)) / 4 * vnd.M_TO_MM for bx in boxes]
            self.install(name, 'essai_etroite_989.ttf', width=500)       # étroite : la moitié de la chasse
            self.assertEqual(w.fonts_rescan(force=True), 1)

            def mids(path):
                return sorted((geom.Path([c]).bbox()[0] + geom.Path([c]).bbox()[2]) / 2 for c in path.contours)
            self.assertEqual(len(mids(t.outline)), 4)
            for got, want in zip(mids(t.outline), centres):
                self.assertAlmostEqual(got, want, delta=0.05)                # chaque lettre dans sa boîte
            for got, want in zip(mids(TX.outline_for(t)), centres):
                self.assertAlmostEqual(got, want, delta=0.3)                 # modifié : l'interlettrage suit
        finally:
            close(w)

    def test_undo_keeps_the_new_outline(self):
        name = 'Essai Annuler 989'
        w = window()
        try:
            t = text('AAAA', name)
            w.canvas.doc.active_layer.items.append(t)
            before = [round(v, 3) for v in t.outline.bbox()]
            w.push_undo('essai')
            w.canvas.doc.active_layer.items.append(rect())
            self.install(name, 'essai_annuler_989.ttf')
            self.assertEqual(w.fonts_rescan(force=True), 1)
            new = [round(v, 3) for v in t.outline.bbox()]
            self.assertNotEqual(new, before)
            w.undo()
            back = next(it for it in w.canvas.doc.active_layer.items if isinstance(it, Text))
            self.assertEqual([round(v, 3) for v in back.outline.bbox()], new)   # pas le tracé de remplacement
        finally:
            close(w)

    def test_option_folders_are_not_installed_fonts(self):
        from vectordrive.portable import settings
        folder = pathlib.Path(tempfile.mkdtemp(prefix='vd989_dossier_'))
        make_font(folder / 'essai_dossier_989.ttf', 'Essai Dossier 989')
        settings().setValue('polices/dossiers', str(folder))
        w = None
        try:
            w = window()
            self.assertTrue(F.is_available('Essai Dossier 989'))
            self.assertEqual(w.fonts_rescan(force=True), -1)        # au lancement : pas « installée », aucun message
        finally:
            settings().remove('polices/dossiers')
            if w is not None:
                close(w)
            if folder in F.FONT_DIRS:
                F.FONT_DIRS.remove(folder)
            F.refresh()

    def test_texts_redrawn_and_ribbon_list(self):
        name = 'Essai Arrivee 989'
        w = window()
        try:
            t = text('AAAA', name)
            lt = text('AAAA')
            TX.set_char_fx(lt, {2: {'font': name}})              # une lettre qui l'attend
            w.canvas.doc.active_layer.items += [t, lt]
            self.assertFalse(F.is_available(name))
            before = t.outline.bbox()
            self.assertIsNone(F.rescan())                      # rien de nouveau
            self.install(name, 'essai_989.ttf')
            self.assertEqual(w.fonts_rescan(force=True), 2)
            self.assertNotEqual([round(v, 3) for v in t.outline.bbox()], [round(v, 3) for v in before])
            box = w.textbar.font
            self.assertIn(name, [box.itemText(i) for i in range(box.count())])
            self.assertEqual(w.fonts_rescan(force=True), -1)   # rien de plus
        finally:
            close(w)

    def test_found_after_another_refresh(self):
        name = 'Essai Rafraichi 989'
        self.install(name, 'essai_rafraichi_989.ttf')
        F.refresh()                                           # inventaire refait par un autre chemin
        self.assertTrue(F.is_available(name))
        self.assertEqual(list((F.rescan() or {}).values()), [name])

    def test_font_list_refills_on_opening(self):
        from vectordrive.ui.dialogs import FontBox
        name = 'Essai Liste 989'
        box = FontBox()
        self.assertNotIn(name, [box.itemText(i) for i in range(box.count())])
        box.setCurrentFont('Arial')
        self.install(name, 'essai_liste_989.ttf')
        box.showPopup()
        try:
            self.assertIn(name, [box.itemText(i) for i in range(box.count())])
            self.assertEqual(box.currentText(), 'Arial')        # le choix reste
        finally:
            box.hidePopup()
            box.deleteLater()

    def test_coming_back_to_the_window_looks(self):
        w = window()
        try:
            with mock.patch.object(w, 'fonts_rescan') as look, mock.patch.object(w, 'isActiveWindow', return_value=True):
                w.changeEvent(QEvent(QEvent.Type.ActivationChange))
                app.processEvents()
            look.assert_called()
        finally:
            close(w)


if __name__ == '__main__':
    unittest.main()
