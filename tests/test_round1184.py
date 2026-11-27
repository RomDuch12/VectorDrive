"""Round « formes » (demande du 27/11) : « Assistant IA possibilité d'accéder aux dossiers sélectionnés et les fichiers
pour des recherches de dessin. New fonction reconnaissance dessin/forme user_full_parametrable : Indexage manuel de
certains dossiers pour accélérer par la suite. Assistant IA peut accèder à cet index. »"""
import json
import os
import pathlib
import shutil
import tempfile
import threading
import time
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'rforme.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

import tests  # noqa: E402,F401
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Shape, Text  # noqa: E402
from vectordrive.core.geom import Affine  # noqa: E402

BEFORE = 'avant : ni reconnaissance de formes, ni index des dossiers, ni dossiers pour l’assistant'
L_PTS = [(0, 0), (30, 0), (30, 10), (10, 10), (10, 40), (0, 40)]
TOOLS = ('folders_allowed', 'folder_list', 'files_find', 'drawing_info', 'shape_search')


def shape(*contours):
    return Shape(path=geom.Path(list(contours)), tool=1)


def L_shape(m=None):
    s = shape(geom.polyline(L_PTS, True))
    return s.transformed(m) if m is not None else s


def SI():
    try:
        from vectordrive.core import shape_index
    except ImportError as ex:
        raise AssertionError(BEFORE) from ex
    return shape_index


def tmp(case) -> pathlib.Path:
    """Un dossier temporaire, effacé à la fin de l'essai."""
    d = pathlib.Path(tempfile.mkdtemp())
    case.addCleanup(shutil.rmtree, d, True)
    return d


def write_doc(path, *items):
    from vectordrive.io import registry
    doc = Document()
    for it in items:
        doc.add(it)
    registry.save_document(doc, str(path))
    return pathlib.Path(path)


def drawings(root):
    """Un petit arbre de dessins : un L (vdz), un cercle (dxf), un L tourné et agrandi (svg, sous-dossier), un DXF
    abîmé, un texte ignoré."""
    root = pathlib.Path(root)
    (root / 'sous').mkdir()
    write_doc(root / 'equerre.vdz', L_shape(),           # (le contour du texte donné : aucune police lue)
              Text(text='Plaque Dupont', size=2, outline=geom.Path([geom.rect(12, 20, 10, 2)])))
    write_doc(root / 'rond.dxf', shape(geom.circle((0, 0), 20)))
    write_doc(root / 'sous' / 'equerre_tournee.svg', L_shape(Affine.rotation(33) @ Affine.scaling(2.0)))
    (root / 'abime.dxf').write_bytes(b'\x00\x01 pas un dxf')
    (root / 'notes.txt').write_text('rien', encoding='utf-8')
    return root


class Signatures(unittest.TestCase):
    """Le calcul des signatures et la ressemblance, selon les réglages."""

    def setUp(self):
        self.S = SI()
        self.P = self.S.Params()
        self.sig = lambda *items: self.S.signature(list(items), self.P)

    def score(self, a, b, **match):
        return self.S.score(a, b, self.S.Match(**match))[0]

    def test_same_shape_found_turned_scaled_mirrored(self):
        ref = self.sig(L_shape())
        for m in (Affine.rotation(37), Affine.scaling(3.0), Affine.mirror_y(0), Affine.mirror_x(0),
                  Affine.translation(500, -200) @ Affine.rotation(120) @ Affine.scaling(0.4)):
            self.assertGreaterEqual(self.score(ref, self.sig(L_shape(m))), 95, m)

    def test_different_shapes_left_out(self):
        ref = self.sig(L_shape())
        th = self.S.Match().threshold
        for other in (shape(geom.circle((0, 0), 20)), shape(geom.star((0, 0), 20, 8, 5)),
                      shape(geom.circle((0, 0), 20), geom.circle((0, 0), 8)), shape(geom.rect(0, 0, 30, 30)),
                      shape(geom.polyline([(0, 0), (30, 0), (30, 20)], False))):
            self.assertLess(self.score(ref, self.sig(other)), th)

    def test_invariances_are_settings(self):
        ref = self.sig(L_shape())
        th = self.S.Match().threshold
        turned = self.sig(L_shape(Affine.rotation(90)))
        self.assertGreaterEqual(self.score(ref, turned), 95)
        self.assertLess(self.score(ref, turned, rotation=False), th, 'l’orientation compte')
        mirrored = self.sig(L_shape(Affine.mirror_y(0)))
        self.assertGreaterEqual(self.score(ref, mirrored), 95)
        self.assertLess(self.score(ref, mirrored, mirror=False, rotation=False), th, 'le sens compte')
        self.assertLess(self.score(ref, mirrored, mirror=False), self.score(ref, mirrored) - 5)
        big = self.sig(L_shape(Affine.scaling(3.0)))
        self.assertLess(self.score(ref, big, scale=False, w_size=10), th, 'la taille compte')
        moved = self.sig(L_shape(Affine.translation(300, 0)))
        self.assertLess(self.score(ref, moved, position=False, w_position=10), th, 'l’emplacement compte')
        self.assertGreaterEqual(self.score(ref, moved), 95, 'd’office, l’emplacement ne compte pas')

    def test_weights_severity_threshold(self):
        S = self.S
        sq, ci = self.sig(shape(geom.rect(0, 0, 30, 30))), self.sig(shape(geom.circle((0, 0), 20)))
        only_count = {('w_' + c): 0.0 for c in S.CRITERIA}
        only_count['w_count'] = 1.0
        self.assertEqual(self.score(sq, ci, **only_count), 100.0, 'un seul contour chacun')
        soft, hard = self.score(sq, ci, severity=1.0), self.score(sq, ci, severity=6.0)
        self.assertGreater(soft, hard, 'l’exigence écarte les formes voisines')
        m = S.Match(threshold=150, limit=0, w_contour=-3, severity=99).clean()
        self.assertEqual((m.threshold, m.limit, m.w_contour, m.severity), (100.0, 1, 0.0, 10.0), 'bornés')
        _s, sims = S.score(sq, ci, S.Match(scale=False, position=False))
        self.assertIn('size', sims)
        self.assertIn('position', sims)
        self.assertNotIn('size', S.score(sq, ci, S.Match())[1], 'la taille ne compte pas d’office')

    def test_min_size_texts_hidden(self):
        S = self.S
        big = shape(geom.rect(0, 0, 100, 100))
        tiny = shape(geom.circle((50, 50), 0.2))
        self.assertEqual(S.signature([big, tiny], S.Params())['n'], 1, 'petit contour ignoré')
        self.assertEqual(S.signature([big, tiny], S.Params(min_size=0, min_rel=0))['n'], 2)
        txt = Text(text='Ébène', outline=geom.Path([geom.rect(10, 10, 20, 20)]))
        self.assertEqual(S.signature([big, txt], S.Params())['n'], 1, 'textes non comptés d’office')
        self.assertEqual(S.signature([big, txt], S.Params(texts=True))['n'], 2)
        self.assertEqual(S.polylines([big, txt], S.Params())[1], ['Ébène'], 'ses mots retenus')
        self.assertNotIn('texts', S.signature([big, txt], S.Params()), 'pas en double dans la signature')
        long = S.clip_texts(['x' * 500, 'y  ' * 3] + ['z' * 150] * 100)
        self.assertEqual(len(long[0]), S.TEXT_CHARS, 'chaque texte borné')
        self.assertEqual(long[1], 'y y y', 'blancs réduits')
        self.assertLessEqual(sum(map(len, long)), S.TEXTS_CHARS, 'tous ensemble bornés')
        hidden = shape(geom.rect(200, 0, 50, 50))
        hidden.visible = False
        self.assertEqual(S.signature([big, hidden], S.Params())['n'], 1)
        self.assertEqual(S.signature([big, hidden], S.Params(hidden=True))['n'], 2)
        self.assertIsNone(S.signature([tiny], S.Params(min_size=5)), 'rien à comparer')
        washer = S.signature([shape(geom.circle((0, 0), 20), geom.circle((0, 0), 8))], S.Params())
        self.assertEqual(washer['holes'], 1)
        self.assertNotEqual(S.Params().digest(), S.Params(points=128).digest())
        self.assertEqual(S.Params().digest(), S.Params().digest())

    def test_degenerate_shapes(self):
        S = self.S
        P = S.Params(min_size=0, min_rel=0)
        point = shape(geom.polyline([(5, 5), (5, 5)], False))
        self.assertIsNone(S.signature([point], P), 'un point : rien à comparer')
        self.assertIsNone(S.signature([], P))
        seg = S.signature([shape(geom.polyline([(0, 0), (40, 0)], False))], P)
        self.assertEqual((seg['n'], seg['open'], seg['holes'], seg['fill']), (1, 1, 0, 0.0))
        self.assertGreaterEqual(S.score(seg, S.signature([shape(geom.polyline([(0, 0), (0, 90)], False))], P))[0],
                                95, 'un segment tourné et agrandi')
        txt = Text(text='Seul', outline=geom.Path([geom.rect(0, 0, 5, 5)]))
        self.assertIsNone(S.signature([txt], S.Params()), 'des textes seuls, non comptés')
        doc = Document()
        doc.add(txt)
        d = S.describe(doc, S.Params())
        self.assertIsNone(d['sig'])
        self.assertEqual(d['texts'], ['Seul'], 'ses mots retenus pour la recherche par texte')
        many = [shape(geom.circle((x * 3.0, y * 3.0), 1)) for x in range(40) for y in range(40)]
        many.append(shape(geom.rect(-5, -5, 130, 130)))
        t0 = time.monotonic()
        sig = S.signature(many, S.Params(min_size=0, min_rel=0, max_contours=5000))
        self.assertEqual(sig['holes'], 1600, 'milliers de contours : trous comptés')
        self.assertLess(time.monotonic() - t0, 60, '(filtre des encombrements)')
        layers = [type('L', (), {'name': 'calque ' + 'x' * 300, 'items': [1, 2]})() for _ in range(80)]
        got = S.clip_layers(layers)
        self.assertEqual(len(got), S.MAX_LAYERS, 'calques bornés en nombre')
        self.assertTrue(all(len(L['name']) == S.LAYER_CHARS and L['objects'] == 2 for L in got), 'et en longueur')


class Index(unittest.TestCase):
    """L'index manuel des dossiers : incrémental, illisibles écartés, annulation, recherche sans relire."""

    def setUp(self):
        self.S = SI()
        self.root = drawings(tmp(self))
        self.path = pathlib.Path(tmp(self)) / 'formes_index.json'
        self.idx = self.S.ShapeIndex(self.path)
        self.reads = []

    def reader(self, path):
        self.reads.append(os.path.basename(path))
        return self.S.read_drawing(path)

    def update(self, **kw):
        return self.idx.update([self.root], self.S.DEFAULT_EXTS, self.S.Params(), reader=self.reader, **kw)

    def test_incremental(self):
        st = self.update()
        self.assertEqual((st['lus'], st['gardes'], st['illisibles']), (4, 0, 1), st)
        self.assertNotIn('notes.txt', self.reads, 'format non indexé')
        self.assertTrue(self.path.is_file(), 'enregistré')
        rec = self.idx.files[self.S.key_of(self.root / 'abime.dxf')]
        self.assertIsNone(rec['sig'])
        self.assertIn('error', rec)
        self.reads.clear()
        st = self.update()
        self.assertEqual((st['lus'], st['gardes']), (0, 4), 'rien de relu : taille et date inchangées')
        self.assertEqual(self.reads, [])
        f = self.root / 'rond.dxf'
        write_doc(f, shape(geom.circle((0, 0), 20)), shape(geom.circle((0, 0), 5)))
        t = time.time() + 10
        os.utime(f, (t, t))
        st = self.update()
        self.assertEqual((st['lus'], self.reads), (1, ['rond.dxf']))
        os.remove(self.root / 'sous' / 'equerre_tournee.svg')
        st = self.update()
        self.assertEqual(st['oublies'], 1)
        again = self.S.ShapeIndex(self.path)
        self.assertEqual(set(again.files), set(self.idx.files), 'relu du disque')
        self.reads.clear()
        st = self.idx.update([self.root], self.S.DEFAULT_EXTS, self.S.Params(points=32), reader=self.reader)
        self.assertEqual(st['lus'], 3, 'réglages de l’indexation changés : relus')

    def test_search_without_reading(self):
        self.update()
        self.reads.clear()
        q = self.S.signature([L_shape(Affine.mirror_y(0))], self.S.Params())
        with mock.patch.object(self.S, 'read_drawing', side_effect=AssertionError('relu')):
            found = self.idx.search(q, self.S.Match())
        names = [os.path.basename(r['path']) for _s, r, _c in found]
        self.assertEqual(sorted(names), ['equerre.vdz', 'equerre_tournee.svg'])
        self.assertTrue(all(s >= 95 for s, _r, _c in found))
        self.assertEqual(self.idx.search(q, self.S.Match(limit=1)).__len__(), 1)
        none = self.idx.search(q, self.S.Match(rotation=False))
        self.assertEqual([os.path.basename(r['path']) for _s, r, _c in none], ['equerre.vdz'], 'tourné écarté')
        skip = self.idx.search(q, self.S.Match(), exclude=[self.root / 'equerre.vdz'])
        self.assertNotIn('equerre.vdz', [os.path.basename(r['path']) for _s, r, _c in skip])
        rec = self.idx.files[self.S.key_of(self.root / 'equerre.vdz')]
        self.assertEqual(rec['texts'], ['Plaque Dupont'])
        self.assertTrue(rec['sketch'] and all(0 <= v <= 255 for c in rec['sketch'] for v in c))
        self.assertEqual([os.path.basename(r['path']) for r in self.idx.find(text='dupont')], ['equerre.vdz'])
        self.assertEqual([os.path.basename(r['path']) for r in self.idx.find(width=(50, None))],
                         ['equerre_tournee.svg'])
        self.assertEqual([os.path.basename(r['path']) for r in self.idx.find(name='rond')], ['rond.dxf'])
        self.assertEqual(self.idx.find(contours=(5, None)), [])

    def test_unreachable_folder_kept_removed_folder_forgotten(self):
        self.update()
        n = len(self.idx.files)
        moved = pathlib.Path(str(self.root) + '_ailleurs')
        os.rename(self.root, moved)
        try:
            st = self.update()
        finally:
            os.rename(moved, self.root)
        self.assertEqual((st['oublies'], len(self.idx.files)), (0, n), 'dossier injoignable : son index gardé')
        self.assertEqual(st['injoignables'], [str(self.root)])
        other = tmp(self)
        st = self.idx.update([other], self.S.DEFAULT_EXTS, self.S.Params(), reader=self.reader)
        self.assertEqual((st['oublies'], len(self.idx.files)), (n, 0), 'dossier retiré de la liste : oublié')

    def test_cancel_keeps_what_is_read(self):
        S = self.S
        box = {}

        def reader(path):
            self.reads.append(path)
            if len(self.reads) == 2:
                box['job'].cancel()                      # Annuler pendant la lecture du deuxième fichier
            return S.read_drawing(path)
        job = box['job'] = S.IndexJob(self.idx, [self.root], S.DEFAULT_EXTS, S.Params(), reader=reader)
        job.start()
        self.assertTrue(job.wait(30))
        self.assertTrue(job.result['annule'])
        self.assertEqual(job.result['lus'], 2, 'le fichier en cours fini, les suivants laissés')
        self.assertEqual(len(S.ShapeIndex(self.path).files), 2, 'enregistré même après Annuler')
        self.reads.clear()
        st = self.update()
        self.assertEqual((st['lus'], st['gardes']), (2, 2), 'la suite reprise ensuite')

    def test_formats(self):
        S = self.S
        self.assertEqual(S.norm_exts(['DXF', '.svg', '.png', '.dwg', '.cdr', '.dxf', '']), ('.dxf', '.svg'),
                         'jamais les images ni les formats lus par un autre logiciel')

    def blocked_job(self):
        """Une mise à jour dont la lecture du 2e fichier attend `gate` ; rend (tâche, gate)."""
        S = self.S
        gate, entered = threading.Event(), threading.Event()

        def reader(path):
            self.reads.append(path)
            if len(self.reads) == 2:
                entered.set()
                gate.wait(30)
            return S.read_drawing(path)
        job = S.IndexJob(self.idx, [self.root], S.DEFAULT_EXTS, S.Params(), reader=reader).start()
        self.addCleanup(lambda: (gate.set(), job.cancel(), job.wait(30)))
        self.assertTrue(entered.wait(30))
        return job, gate

    def test_reads_never_wait_for_an_update(self):
        S = self.S
        job, gate = self.blocked_job()
        box = {}

        def reads():
            box['summary'] = self.idx.summary()
            box['find'] = self.idx.find(name='equerre')
            box['records'] = self.idx.records(S.Params())
            box['stale'] = self.idx.stale(S.Params(points=32))
            box['search'] = self.idx.search(S.signature([L_shape()], S.Params()), S.Match())
        t = threading.Thread(target=reads, daemon=True)
        t.start()
        t.join(20)
        self.assertFalse(t.is_alive(), 'avant : le verrou tenu pendant toute la mise à jour figeait l’appli')
        self.assertTrue(job.running, 'la lecture du 2e fichier attend encore')
        self.assertEqual(box['summary']['files'], 1, 'le 1er fichier lu est déjà dans l’index')
        with self.assertRaises(RuntimeError):            # une seule mise à jour à la fois
            self.idx.update([self.root], S.DEFAULT_EXTS, S.Params())
        gate.set()
        self.assertTrue(job.wait(30))
        self.assertEqual(job.result['lus'], 4)

    def test_saved_during_update(self):
        with mock.patch.object(self.S, 'SAVE_EVERY', 1):
            job, gate = self.blocked_job()
            self.assertEqual(len(self.S.ShapeIndex(self.path).files), 1, 'enregistré en cours de route')
            gate.set()
            self.assertTrue(job.wait(30))
        self.assertEqual(len(self.S.ShapeIndex(self.path).files), 4)
        self.assertEqual([p for p in self.path.parent.iterdir() if p.suffix == '.tmp'], [], 'aucun .tmp laissé')

    def test_unreadable_subfolder_keeps_its_records(self):
        S = self.S
        self.update()
        n = len(self.idx.files)
        real = os.scandir

        def scandir(path='.'):
            if os.path.basename(str(path)) == 'sous':
                raise PermissionError('refusé')
            return real(path)
        with mock.patch.object(S.os, 'scandir', scandir):
            st = self.update()
        self.assertEqual((st['oublies'], len(self.idx.files)), (0, n), 'momentanément illisible : gardé')

    def test_damaged_index_and_failed_save(self):
        S = self.S
        self.update()
        data = json.loads(self.path.read_text(encoding='utf-8'))
        keys = list(data['files'])
        data['files'][keys[0]]['sig'] = 'abîmée'
        data['files'][keys[1]]['size'] = None
        data['files'][keys[2]]['layers'] = [{'name': 'x' * 500, 'objects': 1}]
        data['files']['x'] = {'path': 'x'}
        data['removed'] = {'y': 'pas une date', 'z': 12.5}
        self.path.write_text(json.dumps(data), encoding='utf-8')
        again = S.ShapeIndex(self.path)
        self.assertEqual(len(again.files), len(keys) - 3, 'fiches abîmées écartées (calques compris)')
        self.assertEqual(again._tombs, {'z': 12.5})
        self.assertNotIn(keys[0], again.files)
        self.path.write_text('{pas du json', encoding='utf-8')
        self.assertEqual(S.ShapeIndex(self.path).files, {}, 'fichier abîmé : index vide, pas d’erreur')
        self.idx.dirty = True
        with mock.patch.object(S.os, 'replace', side_effect=PermissionError('verrouillé')):
            self.assertFalse(self.idx.save())
        self.assertIn('verrouillé', self.idx.error, 'échec dit, pas muet')
        self.assertTrue(self.idx.dirty, 'à réécrire')
        self.assertEqual([p for p in self.path.parent.iterdir() if p.suffix == '.tmp'], [])
        self.assertTrue(self.idx.save())
        self.assertEqual(self.idx.error, '')

    def test_two_instances_never_overwrite_blindly(self):
        S = self.S
        other = S.ShapeIndex(self.path)                  # une autre fenêtre, chargée avant
        self.update()
        self.assertEqual(len(other.files), 0)
        extra = tmp(self)
        write_doc(extra / 'carre.dxf', shape(geom.rect(0, 0, 10, 10)))
        st = other.update([extra], S.DEFAULT_EXTS, S.Params())
        self.assertEqual(st['lus'], 1)
        merged = S.ShapeIndex(self.path)
        self.assertEqual(len(merged.files), 5, 'les fiches de l’autre gardées')
        self.assertEqual(other._disk, other._stamp(), 'empreinte : celle du fichier qu’on vient d’écrire')

    def test_forgotten_elsewhere_never_comes_back(self):
        S = self.S
        self.update()
        other = S.ShapeIndex(self.path)                  # une autre fenêtre, qui retire le dossier
        extra = tmp(self)
        write_doc(extra / 'carre.dxf', shape(geom.rect(0, 0, 10, 10)))
        other.update([extra], S.DEFAULT_EXTS, S.Params())
        self.assertEqual(len(S.ShapeIndex(self.path).files), 1)
        self.idx.dirty = True                            # celle-ci enregistre ensuite (avant : ses 4 fiches revenaient)
        self.assertTrue(self.idx.save())
        self.assertEqual([pathlib.Path(r['path']).name for r in S.ShapeIndex(self.path).files.values()],
                         ['carre.dxf'], 'oubliées ailleurs : pas reprises')
        self.assertEqual(len(self.idx.files), 1, 'ni gardées ici')
        self.update()                                    # relues après l'oubli : la plus récente gagne
        self.assertEqual(len(S.ShapeIndex(self.path).files), 4)
        self.assertNotIn(S.key_of(extra / 'carre.dxf'), S.ShapeIndex(self.path).files)

    def test_save_never_blocks_reads(self):
        S = self.S
        self.update()
        gate, entered = threading.Event(), threading.Event()
        real = json.dumps

        def dumps(obj, *a, **kw):                        # une sérialisation lente (gros index)
            if isinstance(obj, dict) and 'removed' in obj:
                entered.set()
                gate.wait(30)
            return real(obj, *a, **kw)
        box = {}
        with mock.patch.object(S.json, 'dumps', dumps):
            self.idx.dirty = True
            saver = threading.Thread(target=lambda: box.setdefault('saved', self.idx.save()), daemon=True)
            saver.start()
            self.addCleanup(lambda: (gate.set(), saver.join(30)))
            self.assertTrue(entered.wait(30))

            def reads():
                box['snapshot'] = len(self.idx.snapshot())
                box['summary'] = self.idx.summary()['files']
            t = threading.Thread(target=reads, daemon=True)
            t.start()
            t.join(20)
            self.assertFalse(t.is_alive(), 'avant : json.dumps sous le verrou figeait la recherche')
            self.assertEqual((box['snapshot'], box['summary']), (4, 4))
            gate.set()
            saver.join(30)
        self.assertTrue(box['saved'])


class Window(unittest.TestCase):
    """La fenêtre « Dessins semblables », le ruban, l'option ; les outils de l'assistant."""

    @classmethod
    def setUpClass(cls):
        SI()
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        for t in cls.w.docs:
            t.modified = False
        cls.w.close()
        cls.w.deleteLater()
        app.processEvents()

    def setUp(self):
        from vectordrive.ui import shape_search as SS
        self.S = SI()
        self.SS = SS
        self.root = drawings(tmp(self))
        self.idx = self.S.ShapeIndex(pathlib.Path(tmp(self)) / 'formes_index.json')
        p = mock.patch.object(SS, 'index', lambda: self.idx)
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(self.forget)
        w = self.w
        w.new_document()
        self.mine = L_shape(Affine.rotation(200))
        w.canvas.doc.add(self.mine)
        w.canvas.invalidate()

    def forget(self):
        for k in (self.SS.KEY_FOLDERS, self.SS.KEY_EXTS, self.SS.KEY_PARAMS, self.SS.KEY_MATCH, self.SS.KEY_SOURCE,
                  self.SS.KEY_CRITERIA, 'assistant/outils_dossiers'):
            self.w.settings.remove(k)
        job = getattr(self.w, '_shape_job', None)
        if job is not None:
            job.cancel()
            job.wait(10)
            self.w._shape_job = None
        dlg = getattr(self.w, '_shape_dlg', None)
        from shiboken6 import isValid
        if dlg is not None and isValid(dlg):
            dlg.timer.stop()
            dlg.deleteLater()
        self.w._shape_dlg = None
        app.processEvents()

    def allow(self, *folders):
        self.SS.set_folders(self.w.settings, [str(f) for f in folders])

    def indexed(self):
        self.allow(self.root)
        self.idx.update([self.root], self.S.DEFAULT_EXTS, self.S.Params())

    # --- la fenêtre ---------------------------------------------------------------------------------------
    def test_ribbon_and_option(self):
        from vectordrive.ui import assistant_options as AO
        from vectordrive.ui.options import BY_KEY, value
        w = self.w
        for k in ('shape_search', 'shape_index'):
            self.assertIn(k, w.A, BEFORE)
        from PySide6.QtWidgets import QToolButton
        from vectordrive.ui.ribbon import RibbonGroup
        group = next(g for g in w.ribbon.findChildren(RibbonGroup) if g.title.text() == 'Formes')
        acts = [b.defaultAction() for b in group.findChildren(QToolButton)]
        self.assertIn(w.A['shape_search'], acts)
        self.assertIn(w.A['shape_index'], acts)
        self.assertIn('assistant/outils_dossiers', BY_KEY)
        self.assertTrue(value(w.settings, 'assistant/outils_dossiers'), 'permis d’office')
        self.assertEqual(AO.TOOL_GROUPS['assistant/outils_dossiers'], 'folders')
        with mock.patch.object(type(w), 'shape_search_dialog') as dlg:
            w.A['shape_index'].trigger()
        dlg.assert_called_once_with('index')

    def test_dialog_built_without_exec_and_settings_kept(self):
        w = self.w
        d = w.shape_search_dialog('index', exec_dialog=False)
        self.assertFalse(d.isVisible())
        self.assertEqual(d.tabs.count(), 3)
        self.assertEqual(d.tabs.currentIndex(), 2)
        self.assertIs(w.shape_search_dialog('recherche', exec_dialog=False), d, 'reprise')
        self.assertEqual(set(d.weights), set(self.S.CRITERIA), 'chaque poids réglable')
        self.assertEqual(set(d.inv), {'scale', 'rotation', 'mirror', 'position'})
        self.assertTrue(d.add_folder(str(self.root)))
        self.assertFalse(d.add_folder(str(self.root)), 'pas deux fois')
        d.inv['rotation'].setChecked(False)
        d.weights['holes'].setValue(7)
        d.threshold.setValue(55)
        d.limit.setValue(9)
        d.severity.setValue(3)
        d.p_min.setValue(2.5)
        d.p_texts.setChecked(True)
        d.p_points.setValue(96)
        d.formats.setText('.dxf .png svg')
        d.source.setCurrentIndex(d.source.findData('criteres'))
        d.c_text.setText('dupont')
        d.save()
        self.assertEqual(self.SS.folders(w.settings), [str(self.root)])
        m, p = self.SS.match(w.settings), self.SS.params(w.settings)
        self.assertEqual((m.rotation, m.w_holes, m.threshold, m.limit, m.severity), (False, 7.0, 55.0, 9, 3.0))
        self.assertEqual((p.min_size, p.texts, p.points), (2.5, True, 96))
        self.assertEqual(self.SS.exts(w.settings), ('.dxf', '.svg'))
        d.c_name.setText('plaque')
        d.done(0)                                        # fermée : tout retenu
        self.assertEqual(json.loads(w.settings.value(self.SS.KEY_CRITERIA))['nom'], 'plaque')
        w._shape_dlg = None                              # (détruite après la fermeture)
        d2 = w.shape_search_dialog(exec_dialog=False)
        self.assertIsNot(d2, d)
        self.assertFalse(d2.inv['rotation'].isChecked(), 'retenu')
        self.assertEqual(d2.weights['holes'].value(), 7)
        self.assertEqual(d2.source.currentData(), 'criteres')
        self.assertEqual(d2.c_text.text(), 'dupont')
        self.assertEqual(d2.current_folders(), [str(self.root)])
        d2.folder_list.setCurrentRow(-1)
        self.assertFalse(d2.remove_folder(), 'rien de choisi')
        d2.folder_list.setCurrentRow(0)
        self.assertTrue(d2.remove_folder())
        self.assertEqual(self.SS.folders(w.settings), [])

    def test_search_from_selection_and_open(self):
        w = self.w
        self.indexed()
        d = w.shape_search_dialog(exec_dialog=False)
        d.source.setCurrentIndex(d.source.findData('selection'))
        w.canvas.select([self.mine])
        rows = d.search()
        names = [pathlib.Path(r['path']).name for _s, r in rows]
        self.assertEqual(sorted(names), ['equerre.vdz', 'equerre_tournee.svg'])
        self.assertEqual(d.results.topLevelItemCount(), 2)
        top = d.results.topLevelItem(0)
        self.assertTrue(top.text(0).endswith('%'))
        self.assertFalse(top.icon(1).isNull(), 'croquis')
        self.assertIsNotNone(d.preview.pixmap())
        with mock.patch.object(w, 'open_path', return_value=True) as op:
            d.results.itemDoubleClicked.emit(top, 1)
        op.assert_called_once_with(top.data(0, Qt.ItemDataRole.UserRole))
        d.source.setCurrentIndex(d.source.findData('criteres'))
        d.c_text.setText('Dupont')
        rows = d.search()
        self.assertEqual([pathlib.Path(r['path']).name for _s, r in rows], ['equerre.vdz'])
        self.assertEqual(d.results.topLevelItem(0).text(0), '')
        d.source.setCurrentIndex(d.source.findData('fichier'))
        d.file.setText(str(self.root / 'equerre.vdz'))
        rows = d.search()
        self.assertEqual([pathlib.Path(r['path']).name for _s, r in rows], ['equerre_tournee.svg'], 'lui-même écarté')
        from vectordrive.i18n import decimal_sep
        self.assertIn(decimal_sep(), d.results.topLevelItem(0).text(2).split(' × ')[0], 'séparateur de la langue')
        d.source.setCurrentIndex(d.source.findData('selection'))
        d.p_points.setValue(32)                          # réglage de l'indexation changé, index pas encore refait
        self.assertEqual(d.search(), [])
        self.assertIn('à mettre à jour', d.status.text())
        d.p_points.setValue(self.S.Params().points)
        d.folder_list.clear()                            # dossier retiré : ses fiches ne sont plus montrées
        self.assertEqual(d.search(), [])
        self.assertIn('vide', d.status.text())

    def test_update_in_background_and_cancel(self):
        w = self.w
        self.allow(self.root)
        d = w.shape_search_dialog('index', exec_dialog=False)
        self.assertEqual(d.update_b.text(), 'Indexer maintenant')
        gate, entered = threading.Event(), threading.Event()

        def reader(path):
            entered.set()
            gate.wait(20)                                # un fichier qui se lit lentement
            return self.S.read_drawing(path)
        self.assertTrue(d.start_update(reader=reader))  # rendue alors que la lecture du 1er fichier est bloquée
        self.assertTrue(entered.wait(20))
        job = w._shape_job
        self.assertTrue(job.running)
        self.assertFalse(d.update_b.isEnabled())
        self.assertFalse(d.start_update(reader=reader), 'une seule à la fois')
        d.cancel_update()
        gate.set()
        self.assertTrue(job.wait(30))
        d._poll()
        self.assertTrue(job.result['annule'])
        self.assertEqual(job.result['lus'], 1)
        self.assertIn('Annulée', d.index_status.text())
        self.assertTrue(d.update_b.isEnabled())
        self.assertTrue(d.start_update())
        self.assertTrue(w._shape_job.wait(60))
        d._poll()
        self.assertFalse(w._shape_job.result['annule'])
        self.assertEqual(self.idx.summary()['files'], 4)
        self.assertEqual(d.update_b.text(), 'Mettre à jour l’index')

    # --- l'assistant ----------------------------------------------------------------------------------------
    def tools(self, **kw):
        from vectordrive.agent.tools import ToolSet
        return ToolSet(self.w, extended=True, **kw)

    def call(self, tool, **args):
        return json.loads(self.tools().call(tool, args)[0]['text'])

    def refused(self, tool, **args):
        from vectordrive.agent.protocol import ToolError
        with self.assertRaises(ToolError) as cm:
            self.tools().call(tool, args)
        return str(cm.exception)

    def test_tools_declared_and_grouped(self):
        from vectordrive.agent import chat
        from vectordrive.agent.tools import TOOL_GROUPS, ToolSet
        from vectordrive.ui import assistant_options as AO
        names = self.tools().names()
        for n in TOOLS:
            self.assertIn(n, names, BEFORE)
            self.assertEqual(TOOL_GROUPS[n], 'folders')
        specs = {s['name']: s for s in self.tools().specs()}
        self.assertTrue(all(specs[n]['annotations']['readOnlyHint'] for n in TOOLS), 'lecture seule')
        self.assertFalse(set(TOOLS) & set(self.tools(without=('folders',)).names()), 'retirés par l’option')
        self.assertFalse(set(TOOLS) & set(ToolSet(self.w).names()), 'pas sur le serveur local')
        from vectordrive.agent import ai_buttons as AB
        from vectordrive.ui import assistant_buttons as UB
        self.assertIn('folders', AB.GROUPS, 'un bouton IA les permet ou non')
        self.assertIn('folders', UB.GROUP_LABELS)
        self.assertNotIn('shape_search', chat.SYSTEM, 'cités seulement s’ils sont permis')
        self.assertIn(chat.FOLDERS_NOTE, AO.system_text(self.w.settings))
        self.assertNotIn(chat.FOLDERS_NOTE, AO.system_text(self.w.settings, removed=('folders',)))
        self.w.settings.setValue('assistant/outils_dossiers', False)
        self.assertIn('folders', AO.without(self.w.settings))
        self.assertNotIn(chat.FOLDERS_NOTE, AO.system_text(self.w.settings))

    def test_replies_bounded(self):
        from vectordrive.agent import folder_tools as FT
        big = tmp(self)
        for i in range(30):
            (big / f'f{i:02d}.dxf').write_bytes(b'0\nEOF\n')
        self.allow(big)
        with mock.patch.object(FT, 'MAX_SCAN', 10):
            got = self.call('files_find', extensions=['.dxf'])
            self.assertFalse(got['complete'])
            self.assertIn('partial', got['note'], 'plafond vérifié pendant la lecture du dossier')
            self.assertLessEqual(len(got['files']), 10)
            listed = self.call('folder_list', path=str(big))
            self.assertFalse(listed['complete'])
            self.assertEqual(listed['total'], 10)
        got = self.call('files_find', extensions=['.dxf'], limit=5)
        self.assertEqual(len(got['files']), 5, 'arrêt dès le nombre atteint')
        self.assertFalse(got['complete'])
        with mock.patch.object(FT, 'DEADLINE', -1.0):
            got = self.call('files_find', name='f')
            self.assertEqual((got['files'], got['complete']), ([], False), 'délai dépassé : résultat partiel dit')
        with mock.patch.object(FT, 'MAX_REPLY', 2000):
            got = self.call('files_find', extensions=['.dxf'])
            self.assertTrue(got['truncated'])
            self.assertLessEqual(len(json.dumps(got, ensure_ascii=False)), 2000)
        rec = {'path': 'x', 'texts': ['t' * 500] * 20}
        self.assertEqual([len(t) for t in FT._row(None, rec)['texts']], [FT.ROW_TEXT_CHARS] * FT.ROW_TEXTS)
        with mock.patch.object(FT, 'MAX_REPLY', 2000):
            got = FT._capped({'path': 'x', 'texts': [], 'layers': [{'name': 'c' * 80, 'objects': 1}] * 50}, 'texts')
            self.assertTrue(got['truncated'])
            self.assertLess(len(got['layers']), 50, 'les calques réduits aussi')
            self.assertLessEqual(len(json.dumps(got, ensure_ascii=False)), 2000)

    def test_busy_large_file_and_unreachable_folder(self):
        from vectordrive.agent import folder_tools as FT
        w = self.w
        self.allow(self.root)
        d = w.shape_search_dialog('index', exec_dialog=False)
        self.assertTrue(self.idx.updating.acquire(blocking=False))   # une mise à jour d'une autre fenêtre
        try:
            self.assertFalse(d.start_update())
            self.assertIn('déjà en cours', d.index_status.text(), 'dit en français, pas le message du cœur')
            job = self.S.IndexJob(self.idx, [self.root], self.S.DEFAULT_EXTS, self.S.Params()).start()
            self.assertTrue(job.wait(30))
            self.assertIsInstance(job.error, self.S.Busy)
            w._shape_job = job
            d._poll()
            self.assertIn('déjà en cours', d.index_status.text())
        finally:
            self.idx.updating.release()
        with mock.patch.object(FT, 'MAX_FILE_BYTES', 10):  # hors de l'index : refus clair au-delà de la taille
            self.assertIn('too large', self.refused('drawing_info', path=str(self.root / 'equerre.vdz')))
            self.idx.update([self.root], self.S.DEFAULT_EXTS, self.S.Params())
            self.assertTrue(self.call('drawing_info', path=str(self.root / 'equerre.vdz'))['from_index'],
                            'à jour dans l’index : rendu sans lire le fichier')
            (self.root / 'neuf.dxf').write_bytes((self.root / 'rond.dxf').read_bytes())
            self.assertIn('too large', self.refused('shape_search', source='file', path=str(self.root / 'neuf.dxf')))
        slow = tmp(self)                                 # un lecteur réseau déconnecté : ne répond pas
        gate = threading.Event()
        real = os.path.realpath

        def realpath(p, *a, **kw):
            if os.path.normcase(str(p)) == os.path.normcase(str(slow)):
                gate.wait(30)
            return real(p, *a, **kw)
        self.addCleanup(FT._REAL.clear)
        self.addCleanup(gate.set)
        self.allow(self.root, slow)
        with mock.patch.object(FT, 'REAL_WAIT', 0.2), mock.patch.object(FT.os.path, 'realpath', realpath):
            t0 = time.monotonic()
            got = self.call('folders_allowed')
            self.assertLess(time.monotonic() - t0, 15, 'jamais bloqué par le disque')
            self.assertEqual([f['reachable'] for f in got['folders']], [True, False])
            self.assertIn('not reachable', self.refused('folder_list', path=str(slow)))
            self.assertIn('rond.dxf', [e['name'] for e in self.call('folder_list', path=str(self.root))['entries']])
            gate.set()

    def test_paths_outside_refused(self):
        self.assertIn('Indexed folders', self.refused('folder_list', path=str(self.root)), 'aucun dossier choisi')
        self.assertIn('Indexed folders', self.refused('shape_search'))
        self.allow(self.root / 'sous')
        outside = tmp(self)
        (outside / 'secret.dxf').write_bytes(b'0\nEOF\n')
        self.assertIn('outside', self.refused('folder_list', path=str(outside)))
        self.assertIn('outside', self.refused('drawing_info', path=str(outside / 'secret.dxf')))
        self.assertIn('outside', self.refused('folder_list', path=str(self.root)), 'le dossier parent')
        self.assertIn('outside', self.refused('drawing_info', path=str(self.root / 'sous' / '..' / 'rond.dxf')))
        self.assertIn('absolute', self.refused('folder_list', path='sous'))
        self.assertIn('absolute', self.refused('drawing_info', path='..\\rond.dxf'))
        drive = os.path.splitdrive(str(self.root))[0].upper()
        other = 'Q:' if drive != 'Q:' else 'R:'
        self.assertIn('another drive', self.refused('folder_list', path=other + '\\dessins'))
        self.assertIn('outside', self.refused('files_find', folder=str(outside)))
        self.assertIn('outside', self.refused('shape_search', source='file', path=str(outside / 'secret.dxf')))
        link = self.root / 'sous' / 'lien'
        try:
            import _winapi
            _winapi.CreateJunction(str(outside), str(link))
        except (ImportError, OSError, AttributeError):
            try:
                os.symlink(outside, link, target_is_directory=True)
            except OSError:
                link = None
        if link is not None:                             # le lien retiré avant son dossier
            self.addCleanup(lambda: os.path.lexists(link) and os.rmdir(link))
        if os.name == 'nt':
            self.assertIsNotNone(link, 'une jonction se crée sans droits d’administrateur')
        if link is not None:
            self.assertIn('link', self.refused('folder_list', path=str(link)))
            self.assertIn('link', self.refused('drawing_info', path=str(link / 'secret.dxf')))
            listed = self.call('folder_list', path=str(self.root / 'sous'))
            self.assertNotIn('lien', [e['name'] for e in listed['entries']], 'liens jamais montrés')
            found = self.call('files_find', name='secret')
            self.assertEqual(found['files'], [], 'jamais suivis')

    def test_read_folders_and_drawings(self):
        self.allow(self.root)
        got = self.call('folders_allowed')
        self.assertEqual([f['path'] for f in got['folders']], [str(self.root)])
        listed = self.call('folder_list', path=str(self.root))
        self.assertEqual([e['name'] for e in listed['entries']][:1], ['sous'], 'dossiers d’abord')
        self.assertIn('rond.dxf', [e['name'] for e in listed['entries']])
        found = self.call('files_find', name='equerre')
        self.assertEqual(sorted(pathlib.Path(f['path']).name for f in found['files']),
                         ['equerre.vdz', 'equerre_tournee.svg'])
        found = self.call('files_find', extensions=['dxf'], recursive=False)
        self.assertEqual(sorted(pathlib.Path(f['path']).name for f in found['files']), ['abime.dxf', 'rond.dxf'])
        old = time.time() - 30 * 86400
        os.utime(self.root / 'rond.dxf', (old, old))
        found = self.call('files_find', extensions=['.dxf'], modified_after=time.strftime('%Y-%m-%d'))
        self.assertEqual([pathlib.Path(f['path']).name for f in found['files']], ['abime.dxf'])
        self.assertIn('date', self.refused('files_find', modified_after='hier'))
        self.assertEqual([pathlib.Path(f['path']).name for f in self.call('files_find', name='E*.SVG')['files']],
                         ['equerre_tournee.svg'], 'motif sans casse')
        info = self.call('drawing_info', path=str(self.root / 'equerre.vdz'))
        self.assertFalse(info['from_index'])
        self.assertAlmostEqual(info['width'], 30, places=3)
        self.assertEqual(info['texts'], ['Plaque Dupont'])
        self.assertIn('could not be read', self.refused('drawing_info', path=str(self.root / 'abime.dxf')))
        self.assertIn('format', self.refused('drawing_info', path=str(self.root / 'notes.txt')))
        self.idx.update([self.root], self.S.DEFAULT_EXTS, self.S.Params())
        info = self.call('drawing_info', path=str(self.root / 'equerre.vdz'))
        self.assertTrue(info['from_index'])

    def test_shape_search_tool(self):
        w = self.w
        self.allow(self.root)
        got = self.call('shape_search')
        self.assertEqual(got['results'], [])
        self.assertIn('empty', got['note'])
        self.idx.update([self.root], self.S.DEFAULT_EXTS, self.S.Params())
        w.canvas.select([self.mine])
        got = self.call('shape_search', source='selection')
        self.assertEqual(sorted(pathlib.Path(r['path']).name for r in got['results']),
                         ['equerre.vdz', 'equerre_tournee.svg'])
        self.assertTrue(all(r['score'] >= 95 and 'contour' in r['criteria'] for r in got['results']))
        got = self.call('shape_search', source='selection', rotation=False)
        self.assertEqual(got['results'], [], 'le L tourné de 200° : écarté si l’orientation compte')
        got = self.call('shape_search', source='file', path=str(self.root / 'rond.dxf'), threshold=0, limit=10)
        self.assertNotIn('rond.dxf', [pathlib.Path(r['path']).name for r in got['results']], 'lui-même écarté')
        got = self.call('shape_search', source='criteria', text='dupont')
        self.assertEqual([pathlib.Path(r['path']).name for r in got['results']], ['equerre.vdz'])
        got = self.call('shape_search', source='criteria', min_width=50)
        self.assertEqual([pathlib.Path(r['path']).name for r in got['results']], ['equerre_tournee.svg'])
        self.allow(self.root / 'sous')                   # l'index garde les autres : pas montrés
        got = self.call('shape_search', source='selection')
        self.assertEqual([pathlib.Path(r['path']).name for r in got['results']], ['equerre_tournee.svg'])
        self.assertIn('"source"', self.refused('shape_search', source='disque'))
        self.assertIn('threshold', self.refused('shape_search', threshold=500))
        self.w.settings.setValue(self.SS.KEY_PARAMS, json.dumps({'points': 32}))
        got = self.call('shape_search', source='selection')
        self.assertEqual(got['results'], [])
        self.assertIn('must be updated', got['note'], 'réglages de l’indexation changés : dit')


if __name__ == '__main__':
    unittest.main()
