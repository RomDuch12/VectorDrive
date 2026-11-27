"""Round 1188 (demande du 27/11) : « bat possibilité de representer le dos gravure (brut rectangle renseigné couleur
laiton avec les taraudages et entraxe en noir si précisé dans le form, avec sauvegarde dans le carnet client »."""
import tests  # noqa: F401  (dossiers du poste redirigés)
import json
import os
import pathlib
import tempfile
import unittest
import zlib
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'rbatdos.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ.setdefault('VECTORDRIVE_KEYS_MEMORY', '1')

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Plate, Shape  # noqa: E402
from vectordrive.io import proof  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : le BAT ne savait pas représenter le dos de la gravure'
BRASS = (0.80, 0.66, 0.30)
BLACK = (0.0, 0.0, 0.0)
#: deux taraudages M4 sur l'axe, entraxe 80, sur un brut de 100 × 50, épaisseur 3
BACK = {'on': True, 'w': 100.0, 'h': 50.0, 'ep': 3.0, 'trous': '2h', 'filetage': 'M4', 'pos': 'entraxe', 'x': 80.0,
        'y': 0.0, 'dx': 0.0, 'dy': 0.0}


def doc_of(w=100.0, h=50.0, ep=3.0):
    d = Document()
    d.plate = Plate(width=w, height=h, thickness=ep)
    d.add(Shape(path=geom.Path([geom.rect(10, 10, 30, 20)]), tool=1))
    return d


def info(**kw):
    try:
        return proof.ProofInfo(scale_mode='vues', **kw)
    except TypeError:
        raise AssertionError(BEFORE)


def spec(**kw):
    if not hasattr(proof, 'back_spec'):
        raise AssertionError(BEFORE)
    return proof.back_spec(info(back=dict(BACK, **kw)))


def signature(prims):
    out = []
    for p in prims:
        b = p.path.bbox() if p.path is not None and p.path.contours else None
        out.append((tuple(round(v, 4) for v in b) if b else None, p.color, p.width, p.fill, p.fill_color, p.layer))
    return out


def brass(prims):
    return [p for p in prims if p.fill_color == BRASS]


def view(back, k=1.0):
    """La vue de dos seule, dans une place de 200 × 150 mm."""
    return proof.back_prims(back, (0.0, 0.0, 200.0, 150.0), k, proof.number_format(proof.ProofInfo()))


def center(p):
    b = p.path.bbox()
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


class Render(unittest.TestCase):
    """La page du BAT : sans dos, celle d'avant ; avec, la vue « Dos »."""

    def test_without_back_the_page_is_unchanged(self):
        d = doc_of()
        ref, PW, PH = proof.build(d, info())
        for back in (dict(BACK, on=False), dict(BACK, w=0.0), {}):
            got, PW2, PH2 = proof.build(d, info(back=back))
            self.assertEqual(signature(got), signature(ref), back)
            self.assertEqual((PW2, PH2), (PW, PH))
        self.assertFalse(brass(ref))
        off = proof._geometry(d, info(back=dict(BACK, on=False)))
        self.assertEqual(off['area'], proof._geometry(d, info())['area'])

    def test_back_view_beside_the_face_in_brass(self):
        d = doc_of()
        prims, PW, PH = proof.build(d, info(back=dict(BACK)))
        blank = brass(prims)
        self.assertEqual(len(blank), 1, BEFORE)
        b = blank[0].path.bbox()
        self.assertAlmostEqual(b[2] - b[0], 100.0, 3)                       # 1:1, comme la face
        self.assertAlmostEqual(b[3] - b[1], 50.0, 3)
        self.assertEqual(blank[0].layer, 'dessin')                          # (PDF en image : avec le dessin)
        plate = [p for p in prims if p.color == (0.45, 0.45, 0.45) and p.width == 0.35]
        self.assertEqual(len(plate), 1)
        self.assertGreater(b[0], plate[0].path.bbox()[2])                   # à droite de la face
        drills = [p for p in prims if p.color == BLACK and p.width == 0.3]
        self.assertEqual(len(drills), 2)

    def test_legend_says_dos(self):
        seen = []
        real = proof._label

        def spy(s, *a, **k):
            seen.append(s)
            return real(s, *a, **k)
        with mock.patch.object(proof, '_label', spy):
            view(spec())
            self.assertIn('Dos 1:1 — 2 × M4 — ép. 3', seen, BEFORE)
            seen.clear()
            view(spec(trous='', filetage='', ep=0.0))
            self.assertEqual(seen, ['Dos 1:1'])                              # rien d'inventé

    def test_holes_and_spacing_only_when_given(self):
        def black(**kw):
            return [p for p in view(spec(**kw)) if p.color == BLACK]
        self.assertEqual(black(trous=''), [], BEFORE)                        # pas de taraudage : rien en noir
        self.assertEqual(black(x=0.0), [])                                   # deux trous sans entraxe : aucun
        got = black()
        drills = [p for p in got if p.width == 0.3]
        arcs = [p for p in got if p.width == 0.15 and not p.fill]
        self.assertEqual(len(drills), 2)
        self.assertAlmostEqual(drills[0].path.bbox()[2] - drills[0].path.bbox()[0], 3.3, 2)     # foret M4 : 3,3
        self.assertTrue(any(not c.closed for p in arcs for c in p.path.contours))              # filetage : ¾ de cercle
        dims = [p for p in got if p.fill and p.width == 0]                   # flèches et valeur de la cote
        self.assertEqual(len(dims), 2)
        c = [center(p) for p in drills]
        self.assertAlmostEqual(abs(c[0][0] - c[1][0]), 80.0, 3)               # entraxe
        four = black(trous='4', y=30.0)
        self.assertEqual(len([p for p in four if p.width == 0.3]), 4)
        self.assertEqual(len([p for p in four if p.fill and p.width == 0]), 4)              # deux cotes
        self.assertEqual(len([p for p in black(trous='4') if p.width == 0.3]), 0)           # entraxe Y manquant
        plain = black(filetage='')
        self.assertEqual([p for p in plain if p.width == 0.3], [])           # sans filetage : une croix par trou
        self.assertEqual(len([p for p in plain if p.width == 0.15 and not p.fill]), 2 + 1)  # 2 croix + traits de cote
        edges = black(pos='bords', x=12.0)
        e = sorted(center(p)[0] for p in edges if p.width == 0.3)
        blank = brass(view(spec(pos='bords', x=12.0)))[0].path.bbox()
        self.assertAlmostEqual(e[0] - blank[0], 12.0, 3)                     # distance au bord
        self.assertAlmostEqual(blank[2] - e[1], 12.0, 3)

    def test_layouts_never_overlap(self):
        def boxes(d, i):
            prims, PW, PH = proof.build(d, i)
            g = proof._geometry(d, i)
            back = proof.back_prims(g['back'], g['back_area'], g['views'][0]['k'], proof.number_format(i))
            face = [p for p in prims if p.layer == 'dessin' and p.color in ((0.45, 0.45, 0.45), (0.1, 0.25, 0.55))]
            fb = geom.bbox_union([p.path.bbox() for p in face if p.path.contours])
            bb = geom.bbox_union([p.path.bbox() for p in back if p.path.contours])
            return fb, bb, brass(back)[0].path.bbox(), PH, i.margin
        side = boxes(doc_of(), info(back=dict(BACK, trous='4', y=30.0)))
        stack = boxes(doc_of(150.0, 60.0), info(orientation='portrait',
                                                back=dict(BACK, w=150.0, h=60.0, x=120.0, trous='4', y=40.0)))
        self.assertGreater(side[2][0], side[0][2], BEFORE)                   # côte à côte : le dos à droite
        self.assertLess(stack[2][3], stack[0][1])                            # l'un sur l'autre : le dos dessous
        for fb, bb, _b, PH, margin in (side, stack):
            self.assertFalse(proof._overlap(fb, bb, 0.0))                    # face et dos, cotes comprises
            self.assertLess(bb[3], PH - margin - 12.0)                       # jamais dans l'en-tête ni sur les logos
            self.assertGreater(bb[1], margin + 42.0)                         # ni dans le cartouche

    def test_hole_outside_the_blank_is_said_not_drawn(self):
        def drills(**kw):
            return [p for p in view(spec(**kw)) if p.color == BLACK and p.width == 0.3]

        def said(**kw):
            if not hasattr(proof, 'back_warnings'):
                self.fail(BEFORE)
            return proof.back_warnings(info(back=dict(BACK, **kw)))
        self.assertEqual(said(), [])
        self.assertEqual(said(on=False, x=500.0), [])                        # décoché : rien à dire
        self.assertEqual(drills(x=120.0), [])                                # entraxe 120 sur un brut de 100
        self.assertEqual(len(said(x=120.0)), 1)
        self.assertEqual(len(drills(dx=45.0)), 1)                            # le décalage en envoie un dehors
        self.assertEqual(len(said(dx=45.0)), 1)
        self.assertEqual(drills(pos='bords', x=60.0), [])                    # distance au bord ≥ moitié
        self.assertEqual(len(said(pos='bords', x=60.0)), 1)
        self.assertEqual(len(said(filetage='M8', x=6.0)), 1)                 # filetage plus grand que l'entraxe
        self.assertEqual(len(said(x=0.0)), 1)                                # cote manquante
        self.assertEqual(len(said(filetage='vis')), 1)                       # filetage illisible : des croix
        self.assertEqual(len(said(w=0.0)), 1)                                # brut à renseigner
        self.assertEqual(len(proof.back_warnings(info(back=dict(BACK)), doc_of(60.0, 30.0))), 1)  # autre brut

    def test_vertical_and_edge_dimensions(self):
        got = view(spec(trous='2v', pos='bords', x=0.0, y=12.0))
        b = brass(got)[0].path.bbox()
        ys = sorted(center(p)[1] for p in got if p.color == BLACK and p.width == 0.3)
        self.assertEqual(len(ys), 2, BEFORE)
        self.assertAlmostEqual(b[3] - ys[1], 12.0, 3)                        # du bord du haut au trou
        self.assertAlmostEqual(ys[0] - b[1], 12.0, 3)
        lines = [p for p in got if p.color == BLACK and p.width == 0.15 and not p.fill
                 and any(not c.closed for c in p.path.contours) and len(p.path.contours) == 3]
        self.assertEqual(len(lines), 1)
        self.assertLess(lines[0].path.bbox()[0], b[0])                       # cotée à gauche du brut
        got = view(spec(trous='2v', y=30.0))
        ys = sorted(center(p)[1] for p in got if p.color == BLACK and p.width == 0.3)
        self.assertAlmostEqual(ys[1] - ys[0], 30.0, 3)

    def test_back_survives_a_vdz_round_trip(self):
        from vectordrive.io import registry
        d = doc_of()
        if not hasattr(proof, 'doc_back'):
            self.fail(BEFORE)
        proof.keep_doc_fields(d, info(back=dict(BACK)))
        path = os.path.join(tempfile.mkdtemp(), 'plaque.vdz')
        registry.save_document(d, path)
        self.assertEqual(proof.doc_back(registry.open_document(path)), spec())

    def test_back_is_the_mirror_of_the_face(self):
        got = view(spec(x=60.0, dx=15.0))                                    # vu de face : décalé vers la droite
        blank = brass(got)[0].path.bbox()
        mid = (blank[0] + blank[2]) / 2
        holes = [center(p)[0] for p in got if p.color == BLACK and p.width == 0.3]
        self.assertAlmostEqual(sum(holes) / len(holes), mid - 15.0, 3, BEFORE)          # vu de dos : vers la gauche
        one = view(spec(trous='1', dx=20.0, dy=5.0))
        (x, y), = [center(p) for p in one if p.color == BLACK and p.width == 0.3]
        b = brass(one)[0].path.bbox()
        self.assertAlmostEqual(x, (b[0] + b[2]) / 2 - 20.0, 3)
        self.assertAlmostEqual(y, (b[1] + b[3]) / 2 + 5.0, 3)                # (le haut reste en haut)

    def test_pixels_brass_blank_and_black_threads(self):
        from vectordrive.ui.batdialog import render_page
        d = doc_of()
        i = info(back=dict(BACK))
        prims, PW, PH = proof.build(d, i)
        W, H = 1400, 1000
        img = render_page(d, i, W, H).toImage()
        k = min((W - 16) / PW, (H - 16) / PH)
        ox, oy = (W - PW * k) / 2, (H - PH * k) / 2

        def px(x, y):
            return ox + x * k, oy + (PH - y) * k
        bx, by = center(brass(prims)[0])
        c = img.pixelColor(*(round(v) for v in px(bx, by + 10)))             # le brut, entre les trous
        for got, want in zip((c.redF(), c.greenF(), c.blueF()), BRASS):
            self.assertAlmostEqual(got, want, delta=0.03)
        drill = next(p for p in prims if p.color == BLACK and p.width == 0.3)
        b = drill.path.bbox()
        x, y = px(b[2], (b[1] + b[3]) / 2)                                   # sur le cercle du foret
        dark = min(max(img.pixelColor(round(x) + i, round(y) + j).getRgb()[:3]) for i in range(-2, 3)
                   for j in range(-2, 3))
        self.assertLess(dark, 90)

    def test_pdf_and_print_with_the_back(self):
        d = doc_of()
        folder = pathlib.Path(tempfile.mkdtemp())

        def contents(path):
            raw = path.read_bytes()
            out = b''
            for part in raw.split(b'stream\n')[1:]:
                try:
                    out += zlib.decompress(part.split(b'\nendstream')[0])
                except zlib.error:
                    pass
            return out
        proof.write(d, folder / 'avec.pdf', info(back=dict(BACK)))
        proof.write(d, folder / 'sans.pdf', info())
        self.assertIn(b'0.8 0.66 0.3 rg', contents(folder / 'avec.pdf'), BEFORE)        # le brut couleur laiton
        self.assertNotIn(b'0.8 0.66 0.3 rg', contents(folder / 'sans.pdf'))
        from PySide6.QtPrintSupport import QPrinter
        from vectordrive.ui import printing
        printer = QPrinter()
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(str(folder / 'imprime.pdf'))
        seen = []
        with mock.patch.object(printing, 'paint_prims', lambda p, prims, tf, **k: seen.extend(prims)):
            printing.print_proof(d, info(back=dict(BACK)), printer)
        self.assertEqual(len(brass(seen)), 1)

    def test_thread_sizes_and_spec(self):
        if not hasattr(proof, 'thread_sizes'):
            self.fail(BEFORE)
        self.assertEqual(proof.thread_sizes('M4'), (4.0, 4.0 - 0.7))
        self.assertAlmostEqual(proof.thread_sizes('M2,5')[1], 2.05)
        self.assertEqual(proof.thread_sizes('M8x1'), (8.0, 7.0))
        self.assertEqual(proof.thread_sizes(' 4 '), (4.0, 4.0 - 0.7))
        self.assertIsNone(proof.thread_sizes('vis'))
        self.assertEqual(spec(on=False), {})
        self.assertEqual(spec(h=0.0), {})
        s = spec(trous='8', pos='?', x='12,5', dx='-3')
        self.assertEqual((s['trous'], s['pos'], s['x'], s['dx']), ('', 'entraxe', 12.5, -3.0))

    def test_back_kept_in_the_drawing(self):
        if not hasattr(proof, 'doc_back'):
            self.fail(BEFORE)
        d = doc_of()
        self.assertFalse(proof.keep_doc_fields(d, info(back=dict(BACK, on=False))))      # cartouche vide, sans dos
        self.assertNotIn('bat', d.extra)
        self.assertTrue(proof.keep_doc_fields(d, info(back=dict(BACK))))
        self.assertEqual(proof.doc_back(d), spec())
        self.assertNotIn('dos', proof.doc_fields(d))                         # les champs du cartouche : inchangés
        self.assertTrue(proof.keep_doc_fields(d, info()))                    # dos retiré : plus rien à garder
        self.assertEqual(proof.doc_back(d), {})


class Form(unittest.TestCase):
    """La fenêtre du BAT : le groupe du dos, construit sans exec, et le carnet de clients."""

    def setUp(self):
        env = mock.patch.dict(os.environ, {'VECTORDRIVE_CLIENTS': tempfile.mkdtemp()})
        env.start()
        self.addCleanup(env.stop)
        self.parent = QWidget()
        self.parent.settings = QSettings(os.path.join(tempfile.mkdtemp(), 'bat.ini'), QSettings.Format.IniFormat)
        self.addCleanup(self.parent.deleteLater)

    def dialog(self, doc=None, **kw):
        from vectordrive.ui.batdialog import BatDialog
        dlg = BatDialog(self.parent, doc or doc_of(), proof.ProofInfo(**kw))
        self.addCleanup(dlg.deleteLater)
        if not hasattr(dlg, 'back_box'):
            self.fail(BEFORE)
        return dlg

    def test_group_unchecked_with_the_plate_dimensions(self):
        dlg = self.dialog()
        self.assertTrue(dlg.back_box.isCheckable())
        self.assertFalse(dlg.back_box.isChecked())
        self.assertEqual((dlg.back_w.value(), dlg.back_h.value(), dlg.back_ep.value()), (100.0, 50.0, 3.0))
        i = dlg.result_info()
        self.assertFalse(i.back['on'])
        self.assertFalse(brass(proof.build(dlg.doc, i)[0]))
        self.assertEqual(self.dialog(Document()).back_w.value(), 0.0)        # rien de connu : rien proposé

    def test_checked_back_is_drawn(self):
        dlg = self.dialog()
        dlg.load_back({'on': True, 'trous': '2h', 'filetage': 'M4', 'x': 80.0})
        dlg.refresh()
        self.assertTrue(dlg.back_x.isEnabled())
        self.assertFalse(dlg.back_y.isEnabled())                             # deux trous sur l'axe : pas d'entraxe Y
        prims = proof.build(dlg.doc, dlg.result_info())[0]
        self.assertEqual(len(brass(prims)), 1)
        self.assertEqual(len([p for p in prims if p.color == BLACK and p.width == 0.3]), 2)

    def test_client_book_keeps_the_back(self):
        from vectordrive.io import clients as CL
        dlg = self.dialog()
        dlg.edits['client'].setText('Dupont')
        dlg.load_back({'on': True, 'trous': '2h', 'filetage': 'M4', 'x': 80.0})
        self.assertEqual(dlg.save_client(), 'Dupont')
        dlg.edits['client'].setText('Martin')
        dlg.load_back({'on': False})
        dlg.save_client()
        where = CL.folder()
        data = json.loads((where / CL.FILE).read_text(encoding='utf-8'))
        self.assertEqual(data['version'], 1)                                 # lisible d'une version d'avant
        book = {c['nom']: c for c in data['clients']}
        self.assertEqual(book['Dupont']['dos']['trous'], '2h', BEFORE)
        self.assertEqual(book['Dupont']['dos']['x'], 80.0)
        self.assertTrue(book['Dupont']['dos']['on'])
        self.assertNotIn('dos', book['Martin'])                              # jamais représenté : rien gardé
        other = self.dialog(doc_of(60.0, 30.0, 0.0))
        self.assertFalse(other.back_box.isChecked())
        self.assertEqual(other.back_w.value(), 60.0)
        other._client_chosen(other.client_book.findData('Dupont'))
        self.assertTrue(other.back_box.isChecked())
        self.assertEqual((other.back_w.value(), other.back_h.value()), (60.0, 30.0))     # le brut du dessin prime
        self.assertEqual(other.back_ep.value(), 3.0)                         # (le dessin ne dit pas l'épaisseur)
        self.assertEqual(other.back_holes.currentData(), '2h')
        self.assertEqual(other.back_thread.currentText(), 'M4')
        self.assertEqual(other.back_x.value(), 80.0)
        other._client_chosen(other.client_book.findData('Martin'))           # sans dos : celui de Dupont ne reste pas
        self.assertFalse(other.back_box.isChecked())
        self.assertEqual(other.back_holes.currentData(), '')
        self.assertEqual(other.back_w.value(), 60.0)                         # (le brut du dessin, lui, reste)
        other._client_chosen(other.client_book.findData('Dupont'))
        other.back_box.setChecked(False)                                     # décoché puis gardé : retenu décoché
        other.save_client()
        self.assertFalse(CL.find(where, 'Dupont')['dos']['on'])
        self.assertEqual(CL.find(where, 'Dupont')['dos']['x'], 80.0)

    def test_client_without_back_keeps_a_typed_or_drawing_back(self):
        from vectordrive.io import clients as CL
        CL.add(CL.folder(), 'Martin')                                        # un client sans dos
        CL.add(CL.folder(), 'Dupont', dos=dict(BACK, trous='4', y=30.0))
        typed = self.dialog()                                                # dos rempli à la main…
        typed.back_box.setChecked(True)
        typed.back_holes.setCurrentIndex(typed.back_holes.findData('2h'))
        typed.back_x.setValue(80.0)
        typed._client_chosen(typed.client_book.findData('Martin'))           # … puis le client choisi
        self.assertTrue(typed.back_box.isChecked(), BEFORE)
        self.assertEqual((typed.back_holes.currentData(), typed.back_x.value()), ('2h', 80.0))
        reopened = self.dialog(back=dict(BACK))                              # dos gardé dans le dessin rouvert
        reopened._client_chosen(reopened.client_book.findData('Martin'))
        self.assertTrue(reopened.back_box.isChecked())
        self.assertEqual(reopened.back_x.value(), 80.0)
        edited = self.dialog()                                               # dos du client A, retouché à la main
        edited._client_chosen(edited.client_book.findData('Dupont'))
        edited.back_y.setValue(25.0)
        edited._client_chosen(edited.client_book.findData('Martin'))
        self.assertEqual((edited.back_holes.currentData(), edited.back_y.value()), ('4', 25.0))
        picked = self.dialog()                                               # A avec dos puis B sans : vidé
        picked._client_chosen(picked.client_book.findData('Dupont'))
        picked._client_chosen(picked.client_book.findData('Martin'))
        self.assertFalse(picked.back_box.isChecked())
        self.assertEqual(picked.back_holes.currentData(), '')

    def test_client_typed_by_hand_keeps_its_back(self):
        from vectordrive.io import clients as CL
        dlg = self.dialog()
        dlg.edits['client'].setText('Dupont')
        dlg.load_back({'on': True, 'trous': '4', 'filetage': 'M3', 'x': 80.0, 'y': 30.0})
        dlg.save_client()
        typed = self.dialog()                                                # le nom tapé, sans choisir dans le carnet
        typed.edits['client'].setText('Dupont')
        self.assertFalse(typed.back_box.isChecked())
        typed.save_client()
        kept = CL.find(CL.folder(), 'Dupont')['dos']
        self.assertFalse(kept['on'], BEFORE)                                 # seule la case change…
        self.assertEqual((kept['trous'], kept['filetage'], kept['x'], kept['y']), ('4', 'M3', 80.0, 30.0))  # … le reste

    def test_unchecked_group_stays_grey_and_warnings(self):
        dlg = self.dialog()
        dlg.load_back({'trous': '4'})
        dlg.refresh()
        self.assertFalse(dlg.back_box.isChecked())
        self.assertFalse(dlg.back_x.isEnabled(), BEFORE)                     # décoché : rien ne se réactive
        self.assertEqual(dlg.back_note.text(), '')
        dlg.load_back({'on': True, 'trous': '2h', 'filetage': 'M4', 'x': 120.0})
        dlg.refresh()
        self.assertTrue(dlg.back_x.isEnabled())
        self.assertIn('2', dlg.back_note.text())                             # deux taraudages hors du brut : dit
        self.assertFalse([p for p in proof.build(dlg.doc, dlg.result_info())[0] if p.color == BLACK
                          and p.width == 0.3])                               # … et pas dessinés
        dlg.load_back({'x': 80.0, 'w': 120.0})                               # un autre brut que celui du dessin
        dlg.refresh()
        self.assertIn('100', dlg.back_note.text())
        bare = self.dialog(Document())                                       # rien de connu, coché sans brut
        bare.load_back({'on': True})
        bare.refresh()
        self.assertTrue(bare.back_note.text())

    def test_drawing_brut_wins_over_the_saved_one(self):
        dlg = self.dialog(doc_of(60.0, 30.0, 0.0), back=dict(BACK))         # BAT d'avant : brut 100 × 50
        self.assertEqual((dlg.back_w.value(), dlg.back_h.value()), (60.0, 30.0), BEFORE)
        self.assertEqual(dlg.back_x.value(), 80.0)
        dlg.refresh()
        self.assertTrue(dlg.back_note.text())                                # entraxe 80 sur 60 : dit


class Window(unittest.TestCase):
    """`_proof_info` : le dos gardé dans le dessin, jamais dans les réglages ; repris au BAT suivant."""

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        for t in cls.w.docs:
            t.modified = False
        cls.w.modified = False
        cls.w.close()
        cls.w.deleteLater()
        app.processEvents()

    def setUp(self):
        st = self.w.settings
        before = {k: st.value(k) for k in st.allKeys() if k.startswith('bat/')}

        def put_back():
            for k in st.allKeys():
                if k.startswith('bat/') and k not in before:
                    st.remove(k)
            for k, v in before.items():
                st.setValue(k, v)
            st.sync()
        self.addCleanup(put_back)
        env = mock.patch.dict(os.environ, {'VECTORDRIVE_CLIENTS': tempfile.mkdtemp()})
        env.start()
        self.addCleanup(env.stop)
        self.w.new_document()
        self.w.canvas.doc.add(Shape(path=geom.Path([geom.rect(0, 0, 20, 10)]), tool=1))

    def test_back_kept_in_the_drawing_and_proposed_again(self):
        from vectordrive.ui import batdialog
        seen = {}

        def fill(dlg):
            if not hasattr(dlg, 'load_back'):
                raise AssertionError(BEFORE)
            dlg.load_back(dict(BACK))
            return 1

        def look(dlg):
            seen.update(on=dlg.back_box.isChecked(), x=dlg.back_x.value(), holes=dlg.back_holes.currentData())
            return 0
        with mock.patch.object(batdialog.BatDialog, 'exec', fill):
            got = self.w._proof_info()
        self.assertTrue(got.back['on'])
        self.assertFalse(self.w.settings.contains('bat/back'))               # jamais dans les réglages
        self.assertEqual(proof.doc_back(self.w.canvas.doc)['trous'], '2h')
        with mock.patch.object(batdialog.BatDialog, 'exec', look):
            self.w._proof_info()
        self.assertEqual(seen, {'on': True, 'x': 80.0, 'holes': '2h'})
        self.w.new_document()                                                # un autre dessin : sans dos
        with mock.patch.object(batdialog.BatDialog, 'exec', look):
            self.w._proof_info()
        self.assertFalse(seen['on'])


if __name__ == '__main__':
    unittest.main()
