"""Round 1099 (demande du 19/11, 16 h 37) : la copie en VD Géo d'un calque dont la police manque n'est plus écrite en
plus de lui dans le VND (« ouverture TE produit un calque dupliqué VD géo… peut-on éviter cela ? ») ; les calques du
VND dans l'ordre du dessin (« Respecter l'ordre des calques TE-VD »), l'ancien premier plan montré en tête en
réglage. Les cas d'ouverture et de réécriture sont dans `test_round1000`."""
import json
import os
import pathlib
import tempfile
import unittest
import zipfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1099.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from vectordrive.core import geom  # noqa: E402
from vectordrive.core import missing_fonts as MF  # noqa: E402
from vectordrive.core import text as TX  # noqa: E402
from vectordrive.core.document import Document, Layer, Shape, Text, struct_copy  # noqa: E402
from vectordrive.core.geom import Affine  # noqa: E402
from vectordrive.io import companion, native, vnd, vnd_write as W  # noqa: E402

MISSING = 'Police Absente 1099'


def rect(x=10):
    return Shape(path=geom.Path([geom.rect(x, 10, 30, 20)]))


def text(s, font):
    t = Text(text=s, font=font, size=8, matrix=Affine.translation(20, 50))
    t.outline = TX.outline_for(t)
    return t


def names(data):
    root, _ = vnd.parse(data)
    return [c.fields['layer_name'] for c in root.children if c.cls.name == 'CCalque']


class Signature(unittest.TestCase):

    def test_same_after_a_copy_and_a_vdz(self):
        t = text('Plaque', MF.FONT)
        s = MF.signature(t)
        self.assertEqual(MF.signature(struct_copy(t)), s)                  # Annuler, copies de travail
        d = Document()
        d.layers[0].items.append(t)
        back = native.from_dict(json.loads(json.dumps(native.to_dict(d))))
        self.assertEqual(MF.signature(back.layers[0].items[0]), s)          # enregistré en VDZ puis relu
        t2 = struct_copy(t)
        t2.outline = None                                                   # tracé recalculé : pas une modification
        self.assertEqual(MF.signature(t2), s)
        t2.extra = {**t2.extra, 'vnd_obj': object()}
        self.assertEqual(MF.signature(t2), s)
        t2.text = 'Plaque 2'
        self.assertNotEqual(MF.signature(t2), s)

    def test_copy_layers_marks_each_object(self):
        d = Document()
        r, t = rect(), text('Plaque', MISSING)
        t.outline = None                                                    # texte sans tracé : passe en VD Géo
        d.layers[0].items += [r, t]
        n, _names, made, _back = MF.copy_layers(d)
        self.assertEqual(n, 1)
        c, = made
        objs = c.extra[MF.MARK][MF.OBJECTS]
        self.assertEqual([objs[it.id][0] for it in c.items], [r.id, t.id])
        self.assertEqual([objs[it.id][1] for it in c.items], [MF.signature(it) for it in c.items])
        layers, info = MF.for_vnd(d.layers)
        self.assertEqual(layers[0].items, [r, t])                           # rien de modifié : les objets d'origine


class Setting(unittest.TestCase):

    def test_option_and_document_flag(self):
        from vectordrive.ui import options
        opt = next(o for _page, opts in options.SPEC for o in opts if o.key == 'vnd/premier_plan_montre')
        self.assertIs(opt.default, False)                                   # décoché d'office : l'ordre du dessin
        d = Document()
        self.assertFalse(W.first_shown_of(d))
        d.extra['vnd_premier_plan'] = True
        self.assertTrue(W.first_shown_of(d))

    def test_written_in_the_order_of_the_drawing(self):
        empty, a = Layer(name='Vide'), Layer(name='A', items=[rect()])
        d = Document()
        d.layers = [empty, a]
        self.assertEqual(names(W.write_document(d)[0]), ['Vide', 'A'])
        d.extra['vnd_premier_plan'] = True
        self.assertEqual(names(W.write_document(d)[0]), ['A', 'Vide'])

    def test_main_window_passes_the_setting(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            d = Document()
            w.settings.setValue('vnd/premier_plan_montre', True)
            w._vnd_options(d)
            self.assertTrue(d.extra['vnd_premier_plan'])
            w.settings.setValue('vnd/premier_plan_montre', False)
            w._vnd_options(d)
            self.assertFalse(d.extra['vnd_premier_plan'])
        finally:
            w.settings.remove('vnd/premier_plan_montre')
            w.modified = False
            w.close()
            app.processEvents()


class Link(unittest.TestCase):

    def test_counts_of_the_written_layers(self):
        orig, copy = Layer(name='Plan 1'), Layer(name='Plan 1' + MF.SUFFIX)
        orig.items.append(text('Plaque', MISSING))
        orig.visible = False
        copy.items += [text('Plaque', MF.FONT), rect()]
        copy.extra = {MF.MARK: {'de': orig.id, 'polices': [MISSING],
                                MF.OBJECTS: {copy.items[0].id: [orig.items[0].id, MF.signature(copy.items[0])]}}}
        d = Document()
        d.layers = [copy, orig]
        tmp = pathlib.Path(tempfile.mkdtemp(prefix='vd1099_'))
        path = tmp / 'a.vnd'
        path.write_bytes(W.write_document(d)[0])
        cp, why = companion.sync(d, path)
        self.assertIsNotNone(cp)
        with zipfile.ZipFile(cp) as z:
            link = json.loads(z.read(companion.LINK).decode('utf-8'))
            comp = json.loads(z.read('document.json').decode('utf-8'))
        self.assertEqual(link['ordre'], 'dessin')
        self.assertEqual(link['compteurs'], [2])                            # un plan écrit, ses deux objets
        self.assertEqual(len(comp['layers']), 2)                            # le compagnon garde les deux calques
        back = vnd.read(path) if hasattr(vnd, 'read') else None
        if back is not None:
            msgs = companion.apply(back, path)
            self.assertEqual([L.name for L in back.layers], [copy.name, orig.name], msgs)
            self.assertEqual([L.id for L in back.layers], [copy.id, orig.id])
            self.assertTrue(any('VD Géo repris' in m for m in msgs), msgs)


def pair(objects=True):
    orig, copy = Layer(name='Plan 1'), Layer(name='Plan 1' + MF.SUFFIX)
    orig.items.append(text('Plaque', MISSING))
    orig.visible = False
    copy.items.append(text('Plaque', MF.FONT))
    mark = {'de': orig.id, 'polices': [MISSING]}
    if objects:
        mark[MF.OBJECTS] = {copy.items[0].id: [orig.items[0].id, MF.signature(copy.items[0])]}
    copy.extra = {MF.MARK: mark}
    return orig, copy


class Review(unittest.TestCase):
    """Relecture : copie sans correspondance, les deux montrés, copie cachée gardée, objets TypeEdit gardés."""

    def test_copy_without_objects_written_behind(self):
        orig, copy = pair(objects=False)                    # marquée avant 0.956.0, ou retrouvée par son nom
        layers, info = MF.for_vnd([copy, orig])
        self.assertEqual([(L.name, L.visible) for L in layers], [(orig.name, True), (copy.name, False)])
        self.assertIs(layers[0].items, orig.items)          # les textes TypeEdit d'origine, jamais en courbes
        self.assertEqual(sorted(p['sorte'] for p in info.values()), ['derriere', 'devant'])
        self.assertEqual((orig.visible, copy.visible), (False, True))     # le dessin n'a pas changé
        data, report = W.write_document(Document(layers=[copy, orig]))
        self.assertEqual(names(data), [orig.name, copy.name])
        self.assertTrue(any('écrite derrière lui' in r for r in report), report)

    def test_both_shown_both_written(self):
        orig, copy = pair()
        orig.visible = True
        layers, info = MF.for_vnd([copy, orig])
        self.assertEqual((layers, info), ([copy, orig], {}))

    def test_hidden_copy_kept_by_the_companion(self):
        from unittest import mock
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        tmp = pathlib.Path(tempfile.mkdtemp(prefix='vd1099_'))
        d = Document()
        d.layers[0].items += [rect(), text('Plaque', MISSING)]
        with mock.patch.object(W, 'curves_reason', return_value=None):   # comme TypeEdit l'écrirait
            src = tmp / 'source.vnd'
            src.write_bytes(W.write_document(d, live_texts=True)[0])
        w = MainWindow()
        try:
            self.assertTrue(w.open_path(str(src)))
            copy = next(L for L in w.canvas.doc.layers if L.name.endswith(MF.SUFFIX))
            added = rect(60)
            copy.items.append(added)                          # dessiné dans la copie
            out = tmp / 'cachee.vnd'
            self.assertTrue(w._write(str(out)))
            with mock.patch.object(MF, 'absent', return_value=[]):        # la police installée : la copie cachée
                self.assertTrue(w.open_path(str(out)))
                self.assertTrue(w._write(str(out)))
                self.assertEqual(names(out.read_bytes()), ['Plan 1'])   # pas écrite
                self.assertTrue(w.open_path(str(out)))
            doc = w.canvas.doc
            self.assertEqual(len(doc.layers), 2)                          # revenue du compagnon
            c = next(L for L in doc.layers if L.name.endswith(MF.SUFFIX))
            self.assertFalse(c.visible)
            self.assertIn(added.id, [it.id for it in c.items])
            orig = next(L for L in doc.layers if not L.name.endswith(MF.SUFFIX))
            self.assertTrue([t for t in orig.items if isinstance(t, Text) and t.extra.get('vnd_obj') is not None])
        finally:
            w.modified = False
            w.close()
            app.processEvents()

    def test_typeedit_objects_kept_over_two_saves(self):
        from unittest import mock
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        tmp = pathlib.Path(tempfile.mkdtemp(prefix='vd1099_'))
        d = Document()
        d.layers[0].items += [rect(), text('Plaque', MISSING)]
        with mock.patch.object(W, 'curves_reason', return_value=None):
            src = tmp / 'source.vnd'
            src.write_bytes(W.write_document(d, live_texts=True)[0])
        root, _ = vnd.parse(src.read_bytes())
        first = [ch.cls.name for c in root.children if c.cls.name == 'CCalque' for z in c.children for ch in z.children]
        w = MainWindow()
        try:
            self.assertTrue(w.open_path(str(src)))
            out = tmp / 'deux.vnd'
            for _ in range(2):                                            # enregistré, rouvert, deux fois
                self.assertTrue(w._write(str(out)))
                self.assertTrue(w.open_path(str(out)))
            self.assertTrue(w._write(str(out)))
            root, _ = vnd.parse(out.read_bytes())
            again = [ch.cls.name for c in root.children if c.cls.name == 'CCalque' for z in c.children
                     for ch in z.children]
            self.assertEqual(again, first)                                # le paragraphe TypeEdit, pas des courbes
        finally:
            w.modified = False
            w.close()
            app.processEvents()

    def test_export_and_batch_follow_the_setting(self):
        import inspect
        from vectordrive.io import batch
        from vectordrive.ui import export_dialog
        self.assertIn("vnd_premier_plan", inspect.getsource(export_dialog.export_items))
        self.assertIn("vnd_premier_plan", inspect.getsource(batch._convert_one))


if __name__ == '__main__':
    unittest.main()
