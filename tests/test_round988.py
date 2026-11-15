"""Round 988 : textes modifiables dans TypeEdit d'office — l'enregistrement en VND écrit les textes en textes TypeEdit
(CParagraphe) sans option à cocher, une fois même pour qui l'avait laissée décochée ; l'export aussi, son dernier
choix et ses modèles d'avant. Un texte dont TypeEdit ne trouverait pas la police (police de VectorDrive, police SVG ou
non installée dans Windows) reste en courbes — TypeEdit n'ouvre un fichier qu'une fois ses polices installées — et le
compte rendu dit combien et pourquoi ; les symboles suivent les mêmes règles."""
import json
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r988.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

from vectordrive.core import fonts as F  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core import text as TX  # noqa: E402
from vectordrive.core.document import Document, Shape, Text  # noqa: E402
from vectordrive.core.geom import Affine  # noqa: E402
from vectordrive.io import smb, vnd  # noqa: E402
from vectordrive.io import vnd_write as W  # noqa: E402

app = QApplication.instance() or QApplication([])
KEYS = ('vnd/textes_vivants', 'vnd/textes_vivants_988')
OWN = 'VD Géo'                                                 # police intégrée de VectorDrive


def text(s, font='Arial', **kw):
    t = Text(text=s, font=font, size=8, matrix=Affine.translation(20, 50), **kw)
    t.outline = TX.outline_for(t)
    return t


def doc(*texts):
    d = Document()
    d.add(Shape(path=geom.Path([geom.rect(10, 10, 100, 60)])))
    for t in texts:
        d.add(t)
    return d


def paragraphs(data) -> int:
    root, _ = vnd.parse(data)
    n = 0

    def walk(o):
        nonlocal n
        n += o.cls.name == 'CParagraphe'
        for c in o.children:
            walk(c)
    walk(root)
    return n


def make_font(path: pathlib.Path, family: str) -> pathlib.Path:
    """Petite police TrueType (A et l'espace), écrite là où on la veut."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    def box():
        p = TTGlyphPen(None)
        p.moveTo((100, 0))
        p.lineTo((100, 700))
        p.lineTo((500, 700))
        p.lineTo((500, 0))
        p.closePath()
        return p.glyph()
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(['.notdef', 'A', 'space'])
    fb.setupCharacterMap({0x41: 'A', 0x20: 'space'})
    fb.setupGlyf({'.notdef': box(), 'A': box(), 'space': TTGlyphPen(None).glyph()})
    fb.setupHorizontalMetrics({'.notdef': (600, 100), 'A': (600, 100), 'space': (300, 0)})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({'familyName': family, 'styleName': 'Regular'})
    fb.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200, sCapHeight=700)
    fb.setupPost()
    path.parent.mkdir(parents=True, exist_ok=True)
    fb.save(str(path))
    return path


def prefs(**values):
    """Les réglages avant d'ouvrir la fenêtre : ceux du premier lancement de cette version (rien), ou ceux donnés."""
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


class OnByDefault(unittest.TestCase):

    def tearDown(self):
        prefs()

    def test_option_and_export_are_on(self):
        from vectordrive.ui import export_dialog as E
        from vectordrive.ui import options as O
        o = O.BY_KEY['vnd/textes_vivants']
        self.assertIs(o.default, True)
        self.assertNotIn('expérimental', o.label)
        _key, label, default = next(x for x in E.OPTIONS if x[0] == 'vnd_textes_vivants')
        self.assertIs(default, True)
        self.assertNotIn('expérimental', label)

    def test_turned_on_once_even_if_left_off(self):
        from vectordrive.ui.options import value
        prefs(vnd__textes_vivants=False)                   # décochée avant cette version
        w = window()
        try:
            self.assertTrue(value(w.settings, 'vnd/textes_vivants'))
            self.assertEqual(str(w.settings.value('vnd/textes_vivants_988')), '1')
            w.settings.setValue('vnd/textes_vivants', False)   # décochée ensuite : elle le reste
        finally:
            close(w)
        w = window()
        try:
            self.assertFalse(value(w.settings, 'vnd/textes_vivants'))
        finally:
            close(w)

    def test_save_as_vnd_writes_editable_text(self):
        prefs()
        w = window()
        try:
            w.canvas.doc.active_layer.items.append(text('Plaque 12'))
            path = os.path.join(tempfile.mkdtemp(), 'plaque.vnd')
            self.assertTrue(w._write(path))
            self.assertEqual(paragraphs(pathlib.Path(path).read_bytes()), 1)
        finally:
            close(w)


class ExportChoices(unittest.TestCase):

    def setUp(self):
        prefs()
        self.w = window()
        self.st = self.w.settings

    def tearDown(self):
        from vectordrive.ui import export_dialog as E
        self.st.remove(E.LAST_CHOICE_KEY)
        self.st.remove('export/modeles')
        close(self.w)

    def checked(self):
        from vectordrive.ui import export_dialog as E
        d = E.ExportDialog(self.w, False)
        try:
            return d.fields['vnd_textes_vivants'].isChecked()
        finally:
            d.deleteLater()

    def test_dialog_and_last_choice(self):
        from vectordrive.ui import export_dialog as E
        self.st.remove(E.LAST_CHOICE_KEY)
        self.assertTrue(self.checked())
        self.st.setValue(E.LAST_CHOICE_KEY, json.dumps({'format': 'vnd', 'options': {'vnd_textes_vivants': False}}))
        self.assertTrue(self.checked())                    # dernier export d'avant : coché
        E.save_last_choice(self.st, {'format': 'vnd', 'options': {'vnd_textes_vivants': False}})
        self.assertFalse(self.checked())                   # décoché depuis : gardé
        self.st.setValue(E.LAST_CHOICE_KEY, json.dumps({'format': 'vnd'}))
        self.assertTrue(self.checked())                    # sans réglages : d'office

    def test_templates_saved_before(self):
        from vectordrive.ui import export_dialog as E
        self.st.setValue('export/modeles', json.dumps([
            {'nom': 'Ancien', 'format': 'vnd', 'options': {'vnd_textes_vivants': False, 'dpi': 150.0}},
            {'nom': 'Neuf', 'v': 2, 'format': 'vnd', 'options': {'vnd_textes_vivants': False}}]))
        got = {t['nom']: t for t in E.load_templates(self.st)}
        self.assertTrue(got['Ancien']['options']['vnd_textes_vivants'])
        self.assertEqual(got['Ancien']['options']['dpi'], 150.0)
        self.assertFalse(got['Neuf']['options']['vnd_textes_vivants'])
        E.save_templates(self.st, list(got.values()))      # réenregistrés : version 2, le choix tient
        again = {t['nom']: t for t in E.load_templates(self.st)}
        self.assertTrue(again['Ancien']['options']['vnd_textes_vivants'])
        self.assertEqual(again['Ancien']['v'], 2)


class FontsTypeEditFinds(unittest.TestCase):

    def test_own_font_stays_curves_and_is_reported(self):
        self.assertIsNotNone(F.builtin_named(OWN))
        data, rep = W.write_document(doc(text('Plaque', font=OWN), text('Plaque 12')), live_texts=True)
        self.assertEqual(paragraphs(data), 1)              # Arial : modifiable ; VD Géo : en courbes
        self.assertNotIn(OWN, vnd.font_table(data)[1])     # TypeEdit ne cherche pas une police qu'il n'a pas
        self.assertIn('1 texte(s) écrit(s) en texte TypeEdit modifiable', rep)
        line = next((r for r in rep if r.startswith('1 texte(s) en courbes : ')), '')
        self.assertIn('police que TypeEdit ne trouve pas', line)
        self.assertFalse([r for r in rep if 'expérimental' in r], rep)

    @unittest.skipUnless(os.environ.get('VECTORDRIVE_CACHE'), 'dossier de polices des essais (package tests)')
    def test_font_only_in_vectordrive_folder_stays_curves(self):
        name = 'Essai Dossier Neuf'
        path = make_font(F.user_font_dir() / 'essai_988.ttf', name)
        F.refresh()
        try:
            self.assertTrue(F.is_available(name))
            data, rep = W.write_document(doc(text('AA A', font=name)), live_texts=True)
            self.assertEqual(paragraphs(data), 0)
            self.assertFalse(F.installed(name))
            self.assertTrue(F.installed('Arial'))
        finally:
            path.unlink()
            F.refresh()

    @unittest.skipUnless(os.environ.get('VECTORDRIVE_CACHE'), 'inventaire des polices des essais (package tests)')
    def test_installed_font_also_in_an_added_folder_stays_editable(self):
        folder = pathlib.Path(tempfile.mkdtemp(prefix='vd988_'))
        make_font(folder / 'arial_copie.ttf', 'Arial')          # même famille qu'une police de Windows
        F.add_font_dir(folder)                                   # Options › dossiers de polices : cherché d'abord
        try:
            self.assertEqual(pathlib.Path(F.find_font('Arial')[0]).parent, folder)
            self.assertTrue(F.installed('Arial'))
            data, rep = W.write_document(doc(text('AA A')), live_texts=True)
            self.assertEqual(paragraphs(data), 1)                # TypeEdit trouve l'Arial de Windows
        finally:
            F.FONT_DIRS.remove(folder)
            F.refresh()

    def test_reasons_counted(self):
        italic = text('Penchée')
        italic.extra['italic'] = True
        stretched = text('Large')
        stretched.matrix = Affine(2, 0, 0, 1, 20, 50)
        stretched.outline = TX.outline_for(stretched)
        data, rep = W.write_document(doc(italic, stretched, text('A', font=OWN), text('B', font=OWN)),
                                     live_texts=True)
        self.assertEqual(paragraphs(data), 0)
        line = next(r for r in rep if 'en courbes : ' in r)
        self.assertTrue(line.startswith('4 texte(s) en courbes : police que TypeEdit ne trouve pas'), line)
        self.assertIn('(2)', line)
        self.assertIn(W.WHY_STYLE, line)
        self.assertIn(W.WHY_SHAPE, line)

    def test_text_edited_after_reopening_is_rewritten(self):
        from vectordrive.core.document import drop_source_object
        folder = pathlib.Path(tempfile.mkdtemp(prefix='vd988_'))
        p = folder / 'plaque.vnd'
        p.write_bytes(W.write_document(doc(text('Plaque 12')), live_texts=True)[0])
        d = vnd.read(str(p))
        t = next(it for it in d.iter_leaves() if isinstance(it, Text))
        drop_source_object(t)                                    # le texte refait par VectorDrive (compagnon .vdz)
        t.text = 'Plaque 13'
        t.outline = TX.outline_for(t)
        root, _ = vnd.parse(W.write_document(d, live_texts=True)[0])
        found = []

        def walk(o):
            if o.cls.name == 'CParagraphe':
                found.append(vnd.paragraph_text(o))
            for c in o.children:
                walk(c)
        walk(root)
        self.assertEqual(found, ['Plaque 13'])                   # même structure : l'ancien texte restait
        unchanged = vnd.read(str(p))
        self.assertEqual(W.write_document(unchanged, live_texts=True)[0], p.read_bytes())   # inchangé : à l'octet

    def test_batch_conversion_follows_the_setting(self):
        from vectordrive.io import batch, native
        folder = pathlib.Path(tempfile.mkdtemp(prefix='vd988_'))
        native.write(doc(text('Plaque 12')), folder / 'plaque.vdz')
        res = batch.convert([folder / 'plaque.vdz'], folder / 'sortie', 'vnd', live_texts=True)
        self.assertEqual(len(res.done), 1, res.errors)
        self.assertEqual(paragraphs((folder / 'sortie' / 'plaque.vnd').read_bytes()), 1)

    def test_symbols_follow_the_same_rules(self):
        self.assertIn(b'CParagraphe', smb.build([text('Plaque 12')], live_texts=True))
        self.assertNotIn(b'CParagraphe', smb.build([text('Plaque', font=OWN)], live_texts=True))
        italic = text('Penchée')
        italic.extra['italic'] = True
        self.assertNotIn(b'CParagraphe', smb.build([italic], live_texts=True))


if __name__ == '__main__':
    unittest.main()
