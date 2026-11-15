"""Round 890 : un dessin lu d'un VND garde son lien avec le fichier d'origine à travers un .vdz, la session et la
récupération. Réécrit en VND, il donne le même fichier qu'avant l'enregistrement : textes TypeEdit modifiables, fins de
courbe et propriétés des contours, fin de document de la source."""
import hashlib
import os
import pathlib
import shutil
import tempfile
import unittest
import zipfile
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', os.path.join(tempfile.mkdtemp(), 'session'))
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from vectordrive.core import geom
from vectordrive.core import text as TX
from vectordrive.core.document import Document, Group, Shape, Text, drop_source_object
from vectordrive.core.geom import Affine
from vectordrive.io import native, registry, vnd
from vectordrive.io import vnd_write as W
from vectordrive.ui import session


def paragraphs(data: bytes) -> int:
    root, _ = vnd.parse(data)
    n = 0
    stack = [root]
    while stack:
        o = stack.pop()
        n += o.cls.name == 'CParagraphe'
        stack.extend(o.children)
    return n


def source_drawing() -> Document:
    d = Document()
    d.add(Shape(path=geom.Path([geom.rect(10, 10, 100, 60)])))
    d.add(Shape(path=geom.Path([geom.rect(120, 10, 160, 40), geom.rect(125, 15, 155, 35)]), name='cadre'))
    t = Text(text='Plaque 12', font='Arial', size=8, matrix=Affine.translation(20, 50))
    t.outline = TX.outline_for(t)
    d.add(t)
    return d


def written(doc) -> bytes:
    """Le VND du dessin, les GUID des objets neufs numérotés dans l'ordre (sinon tirés au hasard à chaque écriture)."""
    n = iter(range(1, 1 << 30))
    with mock.patch.object(W, '_guid', lambda: f'{next(n):032x}'):
        return W.write_document(doc)[0]


def texts(doc):
    return [it for it in doc.iter_leaves() if isinstance(it, Text)]


def shapes(doc):
    return [it for it in doc.iter_leaves() if isinstance(it, Shape)]


class Base(unittest.TestCase):

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix='vd890_'))
        self.data = W.write_document(source_drawing(), live_texts=True)[0]
        self.assertEqual(paragraphs(self.data), 1)
        self.vnd = self.tmp / 'plaque.vnd'
        self.vnd.write_bytes(self.data)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def read(self):
        return vnd.read(str(self.vnd))

    def through_vdz(self, doc, name='plaque.vdz'):
        p = self.tmp / name
        native.write(doc, p)
        return native.read(p)

    def edit(self, doc):
        """La même retouche sur deux dessins : une courbe déplacée, le texte déplacé, une forme ajoutée."""
        L = doc.layers[0]
        k = next(i for i, it in enumerate(L.items) if isinstance(it, Shape) and it.name == 'cadre')
        L.items[k] = L.items[k].transformed(Affine.translation(5, 2))
        k = next(i for i, it in enumerate(L.items) if isinstance(it, Text))
        L.items[k] = L.items[k].transformed(Affine.translation(0, 7))
        doc.add(Shape(path=geom.Path([geom.rect(0, 70, 30, 90)])))


class TestVdz(Base):

    def test_the_source_travels_in_the_vdz(self):
        d1 = self.read()
        native.write(d1, self.tmp / 'a.vdz')
        with zipfile.ZipFile(self.tmp / 'a.vdz') as z:
            self.assertEqual(z.read(native.SOURCE_MEMBER), self.data)
            self.assertNotIn(b'vnd_source', z.read('document.json'))
        d2 = native.read(self.tmp / 'a.vdz')
        self.assertEqual(d2.extra['vnd_source'], self.data)
        self.assertEqual(d2.extra['vnd_signature'], d1.extra['vnd_signature'])

    def test_what_json_could_not_keep_comes_back(self):
        d1 = self.read()
        d2 = self.through_vdz(d1)
        t1, t2 = texts(d1)[0], texts(d2)[0]
        self.assertEqual(t2.extra['vnd_obj'].cls.name, 'CParagraphe')
        self.assertEqual(t2.extra['vnd_obj'].fields['guid'], t1.extra['vnd_obj'].fields['guid'])
        for s1, s2 in zip(shapes(d1), shapes(d2)):
            v1, v2 = s1.extra['vnd'], s2.extra['vnd']
            self.assertIsInstance(v2['props'], vnd.ContourProps)
            self.assertEqual(v2['props'].rows, v1['props'].rows)
            self.assertEqual(v2['trailer'], v1['trailer'])

    def test_unchanged_it_writes_the_original_file(self):
        d2 = self.through_vdz(self.read())
        self.assertEqual(W.write_document(d2)[0], self.data)

    def test_edited_it_writes_what_it_would_have_written_before(self):
        d1, d2 = self.read(), self.through_vdz(self.read())
        self.edit(d1)
        self.edit(d2)
        a, b = written(d1), written(d2)
        self.assertNotEqual(a, self.data)
        self.assertEqual(a, b)
        self.assertEqual(paragraphs(b), 1)                                   # le texte reste un texte TypeEdit

    def test_a_text_edited_after_is_drawn_as_before(self):
        d1, d2 = self.read(), self.through_vdz(self.read())
        for d in (d1, d2):
            t = texts(d)[0]
            drop_source_object(t)
            t.text = 'Plaque 13'
            t.outline = TX.outline_for(t)
        a, b = written(d1), written(d2)
        self.assertEqual(a, b)
        self.assertEqual(paragraphs(b), 0)

    def test_twice_through_vdz(self):
        d3 = self.through_vdz(self.through_vdz(self.read()), 'b.vdz')
        self.assertEqual(W.write_document(d3)[0], self.data)

    def test_a_drawing_without_source_is_written_as_before(self):
        d = source_drawing()
        native.write(d, self.tmp / 'n.vdz')
        with zipfile.ZipFile(self.tmp / 'n.vdz') as z:
            self.assertNotIn(native.SOURCE_MEMBER, z.namelist())
        self.assertNotIn('vnd_source', native.read(self.tmp / 'n.vdz').extra)

    def test_an_old_vdz_still_opens_texts_as_curves(self):
        d1 = self.read()
        d1.extra.pop('vnd_source')                                           # .vdz d'avant ce round
        d2 = self.through_vdz(d1)
        self.assertIsNone(texts(d2)[0].extra['vnd_obj'])
        data, report = W.write_document(d2)
        self.assertEqual(paragraphs(data), 0)
        self.assertTrue(any('comme dessin' in r for r in report))

    def test_a_damaged_source_is_ignored(self):
        native.write(self.read(), self.tmp / 'a.vdz')
        with zipfile.ZipFile(self.tmp / 'a.vdz') as z:
            members = {n: z.read(n) for n in z.namelist()}
        members[native.SOURCE_MEMBER] = b'pas un VND'
        with zipfile.ZipFile(self.tmp / 'a.vdz', 'w') as z:
            for n, b in members.items():
                z.writestr(n, b)
        d = native.read(self.tmp / 'a.vdz')
        self.assertNotIn('vnd_source', d.extra)
        self.assertEqual(paragraphs(W.write_document(d)[0]), 0)


class TestTemplate(Base):

    def test_a_template_does_not_take_the_vnd(self):
        from vectordrive.io import doc_templates
        d = self.read()
        with mock.patch.dict(os.environ, {'VECTORDRIVE_DOC_TEMPLATES': str(self.tmp / 'modeles')}):
            f = doc_templates.save(d, 'plaque')
        with zipfile.ZipFile(f) as z:
            self.assertNotIn(native.SOURCE_MEMBER, z.namelist())
        self.assertNotIn('vnd_signature', native.read(f).extra)
        self.assertEqual(d.extra['vnd_source'], self.data)                    # le dessin, lui, la garde


class TestRelink(Base):

    def fresh(self, guid=None):
        d = native.from_dict(native.to_dict(self.read()))                   # le dessin tel que le JSON le garde
        if guid is not None:
            texts(d)[0].extra['vnd']['guid'] = guid
        return d

    def test_counts_what_came_back(self):
        d = self.fresh()
        self.assertEqual(vnd.relink(d, self.data), 1 + len(shapes(d)))

    def test_an_unknown_guid_is_drawn(self):
        d = self.fresh('{inconnu}')
        vnd.relink(d, self.data)
        self.assertNotIn('vnd_obj', texts(d)[0].extra)

    def test_a_guid_of_another_kind_is_drawn(self):
        d = self.fresh()
        texts(d)[0].extra['vnd']['guid'] = shapes(d)[0].extra['vnd']['guid']   # celui d'une courbe
        vnd.relink(d, self.data)
        self.assertNotIn('vnd_obj', texts(d)[0].extra)

    def test_a_guid_found_twice_is_not_guessed(self):
        d = self.fresh()
        g = texts(d)[0].extra['vnd']['guid']
        real = vnd.parse

        def doubled(data, **kw):
            root, ar = real(data, **kw)
            calque = root.children[0]
            copy = vnd.MfcObject(calque.children[0].cls)
            copy.fields = {'guid': g}
            calque.children.append(copy)
            return root, ar
        with mock.patch.object(vnd, 'parse', doubled):
            vnd.relink(d, self.data)
        self.assertNotIn('vnd_obj', texts(d)[0].extra)

    def test_a_group_of_a_source_object_takes_only_its_kind(self):
        g = Group(children=[], name='Cote')
        self.assertFalse(vnd._source_kind_ok(g, vnd.MfcObject(vnd.MfcClass('CParagraphe', 0))))
        self.assertTrue(vnd._source_kind_ok(g, vnd.MfcObject(vnd.MfcClass('CCotationLaterale', 0))))
        self.assertTrue(vnd._source_kind_ok(Shape(), vnd.MfcObject(vnd.MfcClass('CTrou', 0))))
        self.assertFalse(vnd._source_kind_ok(Shape(), vnd.MfcObject(vnd.MfcClass('CCourbe', 0))))

    def test_unreadable_data_changes_nothing(self):
        d = self.fresh()
        self.assertIsNone(vnd.relink(d, b'abc'))
        self.assertIsNone(texts(d)[0].extra['vnd_obj'])


class TestSession(Base):

    def snap(self, *docs):
        out = []
        for i, d in enumerate(docs):
            e = {'path': str(self.vnd), 'modified': True, 'view': None, 'source': str(self.vnd), 'file': None,
                 'paths': None, 'current': i == 0, 'uid': f'u{i}'}
            out.append((e, native.snapshot(d), None))
        return {'docs': out, 'written': {}}

    def test_the_source_is_kept_beside_once(self):
        folder = self.tmp / 'session'
        d = self.read()
        session.write(self.snap(d), folder)
        index = session.load_index(folder)
        name = index['docs'][0]['vnd_source']
        self.assertEqual((folder / name).read_bytes(), self.data)
        with zipfile.ZipFile(folder / 'dessin_0.vdz') as z:
            self.assertNotIn(native.SOURCE_MEMBER, z.namelist())            # pas recopié à chaque sauvegarde
        self.assertIn('vnd_source', d.extra)                                 # le dessin ouvert garde sa source
        before = os.stat(folder / name).st_mtime_ns
        calls = []
        real = hashlib.sha1

        def sha1(*a):
            calls.append(1)
            return real(*a)
        with mock.patch.object(hashlib, 'sha1', sha1):
            session.write(self.snap(d), folder)
        self.assertEqual(calls, [])                                          # déjà nommé : pas relu
        self.assertEqual(os.stat(folder / name).st_mtime_ns, before)         # ni réécrit
        session.write({'docs': [], 'written': {}}, folder)                   # onglet fermé : fichier retiré
        self.assertFalse((folder / name).exists())

    def test_two_tabs_of_one_file_share_it(self):
        folder = self.tmp / 'session'
        session.write(self.snap(self.read(), self.read()), folder)
        names = [e['vnd_source'] for e in session.load_index(folder)['docs']]
        self.assertEqual(names[0], names[1])
        self.assertEqual(len(list(folder.glob('source_*.vnd'))), 1)

    def test_restored_it_writes_the_same_vnd(self):
        folder = self.tmp / 'session'
        d1 = self.read()
        self.edit(d1)
        session.write(self.snap(d1), folder)
        e = session.load_index(folder)['docs'][0]
        d2 = registry.open_document(str(folder / e['file']))
        session._attach_source(d2, folder, e)
        self.assertEqual(written(d2), written(d1))
        self.assertEqual(paragraphs(W.write_document(d2)[0]), 1)

    def test_a_missing_source_file_leaves_the_drawing_as_before(self):
        folder = self.tmp / 'session'
        session.write(self.snap(self.read()), folder)
        e = session.load_index(folder)['docs'][0]
        (folder / e['vnd_source']).unlink()
        d2 = registry.open_document(str(folder / e['file']))
        session._attach_source(d2, folder, e)
        self.assertNotIn('vnd_source', d2.extra)


class TestWindow(Base):

    def test_ctrl_s_after_a_restart_writes_the_same_vnd(self):
        from vectordrive.ui.main_window import MainWindow
        folder = self.tmp / 'session'
        w = MainWindow()
        try:
            self.assertTrue(w.open_path(str(self.vnd)))
            w.canvas.doc.add(Shape(path=geom.Path([geom.rect(0, 70, 30, 90)])))
            w.modified = True
            want = written(w.canvas.doc)
            session.save(w, folder)
        finally:
            w.modified = False
            w.close()
        w2 = MainWindow()
        try:
            self.assertEqual(session.restore(w2, folder), 1)
            got = written(w2.canvas.doc)
        finally:
            w2.modified = False
            w2.close()
        self.assertEqual(got, want)
        self.assertEqual(paragraphs(got), 1)


if __name__ == '__main__':
    unittest.main()
