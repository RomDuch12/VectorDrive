"""Round 1174 (demandes du 26/11) : « Enregistrement en vnl : toutes les couleurs différentes sur le même calque; » ;
« pour le vnd aussi on veut pouvoir avoir plusieurs couleurs dans le même calque; »."""
import itertools
import json
import os
import pathlib
import shutil
import struct
import tempfile
import unittest
import zipfile
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'rvnl.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtGui import QColor, QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import OWN_COLOR, Document, Group, Image, Layer, Plate, Shape  # noqa: E402
from vectordrive.io import companion, registry, vnd, vnd_write  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : le calque était éclaté en un calque par outil (« Gravure », « Gravure (1) »…)'
RED, BLACK, BLUE, GREEN = '#ff0000', '#000000', '#0000ff', '#00a000'      # outils 1, 0, 3, 2 d'office
USINE = 'TypeEdit usine toutes les courbes d’un calque avec l’outil du calque'


def square(x, tool, y=0.0):
    return Shape(path=geom.Path([geom.rect(x, y, 10, 10)]), tool=tool)


def three_colours() -> Document:
    """Un calque, trois objets de trois couleurs : rouge (outil 1) d'abord, puis noir (outil 0), puis bleu (outil 3)."""
    d = Document()
    d.plate = Plate(width=100, height=40)
    d.layers[0].name = 'Gravure'
    d.layers[0].items += [square(0, 1), square(20, 0), square(40, 3)]
    return d


def calques(path) -> list:
    """[(nom, outil, nombre d'objets, couleurs des fins de courbe)] des calques du fichier, dans son ordre."""
    root, _ar = vnd.parse(pathlib.Path(path).read_bytes())
    out = []

    def colours(o, acc):
        if o is None:
            return
        if o.cls.name == 'CCourbe':
            acc.append(vnd.colorref_hex(struct.unpack_from('<I', o.fields['trailer'], 8)[0]))
            return
        for ch in o.fields.get('slots', o.children) or []:
            colours(ch, acc)
    for c in root.children:
        acc = []
        colours(c, acc)
        out.append((c.fields['layer_name'], vnd.calque_tool(c), len(c.children), acc))
    return out


def fixed_guids():
    """Les GUID des objets écrits, numérotés de 0 (d'office : tirés au hasard) : deux écritures comparables."""
    n = itertools.count()
    return mock.patch.object(vnd_write, '_guid', lambda: f'{next(n):032x}')


def shown(doc, layer) -> list:
    """Les couleurs que VectorDrive montre aux objets du calque relu."""
    return [doc.item_color(it) for it in layer.items]


def tools(doc) -> list:
    return [[it.tool for it in L.items] for L in doc.layers]


def save(d, f, mode='besoin'):
    """Enregistre comme la fenêtre : le fichier, puis son compagnon ; rend (compagnon, raisons)."""
    registry.save_document(d, f)
    return companion.sync(d, f, mode=mode)


def reopen(f, apply=True):
    """Le fichier rouvert, son compagnon appliqué (comme à l'ouverture dans la fenêtre)."""
    back = registry.open_document(f)
    if apply:
        companion.apply(back, f)
    return back


class OneLayer(unittest.TestCase):

    def test_vnl_three_colours_on_one_layer_tools_back_by_the_companion(self):
        d = three_colours()
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'gravure.vnl')
            cp, why = save(d, f)
            got = calques(f)
            self.assertEqual(len(got), 1, BEFORE)
            self.assertEqual(got[0], ('Gravure', 1, 3, [RED, BLACK, BLUE]))   # outil le plus courant : le premier
            self.assertIn('outils des objets d\'un calque de plusieurs couleurs', why)
            self.assertEqual(tools(reopen(f, apply=False)), [[1, 1, 1]])   # le fichier seul : l'outil du calque
            back = reopen(f)
            self.assertEqual([L.name for L in back.layers], ['Gravure'])
            self.assertEqual(tools(back), [[1, 0, 3]])                     # le compagnon : chacun le sien
            self.assertEqual(shown(back, back.layers[0]), [RED, BLACK, BLUE])
            again = os.path.join(tmp, 'encore.vnl')
            registry.save_document(back, again)                             # relu puis réenregistré : le même fichier
            self.assertEqual(pathlib.Path(again).read_bytes(), pathlib.Path(f).read_bytes())

    def test_vnd_and_template_keep_their_colours_on_one_layer(self):
        """Seconde demande : le VND aussi ; le modèle de dessin (.vnm) suit la même règle."""
        for ext in ('.vnd', '.vnm'):
            with tempfile.TemporaryDirectory() as tmp:
                f = os.path.join(tmp, 'piece' + ext)
                save(three_colours(), f)
                self.assertEqual(calques(f), [('Gravure', 1, 3, [RED, BLACK, BLUE])], BEFORE)
                back = reopen(f)
                self.assertEqual(tools(back), [[1, 0, 3]])
                self.assertEqual(shown(back, back.layers[0]), [RED, BLACK, BLUE])
        _data, report = vnd_write.write_document(three_colours())
        self.assertIn(USINE, ' | '.join(report))
        old, _r = vnd_write.write_document(three_colours(), split_tools=True)   # l'écriture d'avant, en option
        with tempfile.TemporaryDirectory() as tmp:
            pathlib.Path(tmp, 'ancien.vnd').write_bytes(old)
            self.assertEqual([g[0] for g in calques(os.path.join(tmp, 'ancien.vnd'))],
                             ['Gravure', 'Gravure (1)', 'Gravure (4)'])

    def test_drawing_layers_stay_layers(self):
        """Plusieurs calques : chacun reste un calque (réponse de l'utilisateur : « un dessin qui a plusieurs calques
        garde ses calques dans le .vnl »), dans l'ordre du dessin, avec toutes ses couleurs ; un calque vide reste."""
        d = Document()
        d.layers[0].name = 'Gravure'
        d.layers[0].items += [square(0, 1), square(20, 3)]
        d.layers.append(Layer(name='Vide'))
        d.layers.append(Layer(name='Découpe', items=[square(0, 2, 30), square(20, 1, 30), square(40, 2, 30)]))
        for ext in ('.vnl', '.vnd'):
            with tempfile.TemporaryDirectory() as tmp:
                f = os.path.join(tmp, 'plaque' + ext)
                save(d, f)
                got = calques(f)
                self.assertEqual([(g[0], g[1], g[2]) for g in got],
                                 [('Gravure', 1, 2), ('Vide', 0, 0), ('Découpe', 2, 3)], BEFORE)
                self.assertEqual([g[3] for g in got], [[RED, BLUE], [], [GREEN, RED, GREEN]])
                back = reopen(f)
                self.assertEqual([L.name for L in back.layers], ['Gravure', 'Vide', 'Découpe'])
                self.assertEqual(tools(back), [[1, 3], [], [2, 1, 2]])
                self.assertEqual([shown(back, L) for L in back.layers], [[RED, BLUE], [], [GREEN, RED, GREEN]])

    def test_single_tool_layers_written_as_before(self):
        """Des calques d'un seul outil chacun : le même dessin qu'avec l'écriture par outil, octet pour octet ; pas de
        remarque, pas de compagnon."""
        d = Document()
        d.layers[0].items += [square(0, 2), square(20, 2)]
        d.layers.append(Layer(name='Rouge', items=[square(0, 1, 30)]))
        d.layers.append(Layer(name='Noir', items=[square(0, 0, 50)]))
        d.layers.append(Layer(name='Mixte', items=[square(0, 3, 70), square(20, 1, 70)]))
        with fixed_guids():
            new, report = vnd_write.write_document(d)
        with fixed_guids():
            old, _r = vnd_write.write_document(d, split_tools=True)
        self.assertEqual(len([r for r in report if USINE in r]), 1, BEFORE)
        d.layers.pop()
        with fixed_guids():
            new, report = vnd_write.write_document(d)
        with fixed_guids():
            old, _r = vnd_write.write_document(d, split_tools=True)
        start = vnd.archive_start(new)
        self.assertEqual(new[start:], old[start:])
        self.assertNotIn(USINE, ' | '.join(report))
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(save(d, os.path.join(tmp, 'a.vnd')), (None, []))

    def test_report_names_the_machining_tool_and_counts_the_others(self):
        """La remarque pour chaque calque de plusieurs outils (outil numéroté comme dans VectorDrive : l'outil 0 est
        l'« Outil 1 ») ; le nombre d'objets d'un autre outil. Rien pour un calque d'un seul outil."""
        d = three_colours()
        d.layers[0].items.append(square(60, 3))                            # deux bleus : l'outil 3 l'emporte
        d.layers.append(Layer(name='Seul', items=[square(0, 2, 30), square(20, 2, 30)]))
        _data, report = vnd_write.write_document(d)
        said = [r for r in report if USINE in r]
        self.assertEqual(said, ['plan « Gravure » : ' + USINE
                               + ' (outil 4) ; les couleurs ne servent qu’à l’affichage'],
                         BEFORE)
        self.assertIn('plan « Gravure » : 2 objet(s) d’un autre outil que le calque', ' | '.join(report))
        self.assertNotIn('« Seul »', ' | '.join(report))


class Companion(unittest.TestCase):

    def test_typeedit_curve_keeps_its_tool_whatever_its_colour(self):
        """Une courbe lue dans TypeEdit garde sa fin de courbe, de couleur libre (rouge sur un calque de l'outil 2) :
        réenregistrée avec un autre calque de plusieurs couleurs, puis rouverte, elle reste à l'outil 2 (aucun outil
        n'est déduit d'une couleur)."""
        src = Document()
        src.layers[0].name = 'TE'
        red = square(0, 2)
        red.extra[OWN_COLOR] = RED
        src.layers[0].items.append(red)
        for ext in ('.vnd', '.vnl'):
            with tempfile.TemporaryDirectory() as tmp:
                f0 = os.path.join(tmp, 'typeedit' + ext)
                registry.save_document(src, f0)                             # comme un fichier de TypeEdit
                doc = registry.open_document(f0)
                self.assertIn('vnd_source', doc.extra)
                curve = doc.layers[0].items[0]
                self.assertEqual((curve.tool, curve.extra['te_color']), (2, [RED, 2]))
                doc.layers.append(Layer(name='Mixte', items=[square(0, 1, 30), square(20, 3, 30)]))
                f = os.path.join(tmp, 'repris' + ext)
                save(doc, f)
                self.assertEqual(len(calques(f)), 2, BEFORE)
                for back in (reopen(f, apply=False), reopen(f)):
                    self.assertEqual(back.layers[0].items[0].tool, 2)      # avant (couleur → outil) : l'outil 1
                    self.assertEqual(shown(back, back.layers[0]), [RED])
                self.assertEqual(tools(back), [[2], [1, 3]])

    def test_no_valid_companion_keeps_the_layer_tool(self):
        """Compagnon d'un autre fichier, compagnon renommé avec le fichier, mode « jamais » : chaque objet garde
        l'outil du calque."""
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'piece.vnl')
            save(three_colours(), f)
            g = os.path.join(tmp, 'copie.vnl')
            shutil.copyfile(f, g)
            shutil.copyfile(f + '.vdz', g + '.vdz')                         # renommés : le lien nomme encore piece.vnl
            self.assertEqual(tools(reopen(g)), [[1, 1, 1]], BEFORE)
            other = three_colours()
            other.layers[0].items.append(square(60, 3))
            registry.save_document(other, f)                                # un autre dessin : plus son empreinte
            self.assertEqual(tools(reopen(f)), [[3, 3, 3, 3]])                 # deux bleus : l’outil 3
            h = os.path.join(tmp, 'jamais.vnd')
            self.assertEqual(save(three_colours(), h, mode='jamais'), (None, []))
            self.assertFalse(os.path.exists(os.path.join(tmp, 'jamais.vdz')))
            self.assertEqual(tools(reopen(h)), [[1, 1, 1]])

    def test_old_companion_of_a_file_split_by_tool(self):
        """Un VND d'avant (un calque par outil) et son compagnon sans la marque : l'image tournée revient toujours
        (calques du compagnon partagés par outil) ; avec la marque, les calques du compagnon sont ceux du fichier."""
        im, d = turned_image_drawing()
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'ancien.vnd')
            old, _r = vnd_write.write_document(d, split_tools=True)
            pathlib.Path(f).write_bytes(old)
            companion.sync(d, f)
            cp = companion.companion_path(f)
            with zipfile.ZipFile(cp) as z:
                parts = {n: z.read(n) for n in z.namelist()}
            link = json.loads(parts[companion.LINK].decode('utf-8'))
            self.assertEqual(link.pop(companion.MULTI), 1, BEFORE)
            parts[companion.LINK] = json.dumps(link).encode('utf-8')
            with zipfile.ZipFile(cp, 'w') as z:
                for n, b in parts.items():
                    z.writestr(n, b)
            back = reopen(f)
            self.assertEqual([L.name for L in back.layers], ['Plan', 'Plan (2)', 'Plan (4)'])
            ims = [it for L in back.layers for it in L.items if isinstance(it, Image)]
            self.assertEqual(ims[0].data, im.data, 'l’image tournée d’un ancien VND ne revient plus')

    def test_turned_image_comes_back_to_the_single_layer(self):
        """Le compagnon d'un .vnl rend l'image tournée à son calque, qui n'est plus partagé par outil."""
        from vectordrive.io import raster
        im, d = turned_image_drawing()
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'logo.vnl')
            save(d, f)
            back = registry.open_document(f)
            self.assertEqual([L.name for L in back.layers], ['Plan'], BEFORE)
            companion.apply(back, f)
            ims = [it for it in back.layers[0].items if isinstance(it, Image)]
            self.assertEqual(len(ims), 1)
            self.assertEqual(ims[0].data, im.data, 'l’image tournée n’est pas revenue du compagnon')
            self.assertEqual(raster.qimage_of(ims[0]).width(), 6)
            self.assertEqual(tools(back), [[0, 1, 3]])                      # l'objet masqué n'est pas écrit


class Review(unittest.TestCase):
    """Troisième relecture : ordre `_tools_back` puis `_outlines`, remarque quand les outils ne sont pas rétablis,
    résumé en fin de compte rendu."""

    def test_outlines_see_the_restored_tools(self):
        """`_outlines` reconnaît le contour d'une surface à son outil : il passe après les outils rendus."""
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'piece.vnl')
            save(three_colours(), f)
            back = registry.open_document(f)
            seen = []
            with mock.patch.object(companion, '_outlines', lambda L, C: seen.append([it.tool for it in L.items])):
                companion.apply(back, f)
            self.assertEqual(seen, [[1, 0, 3]], 'avant : `_outlines` voyait l’outil du calque partout')

    def test_a_remark_when_the_tools_are_not_restored(self):
        """Fichier retouché depuis son compagnon (marqué MULTI) : la remarque nomme le calque dont les objets gardent
        l'outil du calque ; aucune quand les outils sont rendus."""
        said = 'outils des objets non rétablis par le compagnon'
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'piece.vnd')
            save(three_colours(), f)
            self.assertNotIn(said, ' | '.join(companion.apply(registry.open_document(f), f)))
            other = three_colours()
            other.layers[0].items.append(square(60, 3))
            registry.save_document(other, f)                                # retouché : plus la même empreinte
            msgs = companion.apply(registry.open_document(f), f)
            self.assertIn('calque(s) de plusieurs couleurs (Gravure) : ' + said + ' ; chaque objet a l’outil de son '
                          'calque, comme dans TypeEdit', msgs)

    def test_summary_line_ends_the_report(self):
        d = three_colours()
        d.layers[0].items.append(square(60, 3))                            # 4 objets, outil 3 : 2 autres
        d.layers.append(Layer(name='Découpe', items=[square(0, 2, 30), square(20, 1, 30)]))   # outil 2 : 1 autre
        d.layers.append(Layer(name='Seul', items=[square(0, 2, 50)]))
        _data, report = vnd_write.write_document(d)
        self.assertEqual(report[-1], 'en résumé : 2 calque(s) de plusieurs couleurs ; 3 objet(s) usiné(s) dans '
                                     'TypeEdit avec l’outil de leur calque, pas le leur')
        d.layers[:2] = []
        self.assertFalse([r for r in vnd_write.write_document(d)[1] if r.startswith('en résumé')])


class Flows(unittest.TestCase):
    """Les flux qui lisent un fichier TypeEdit sans la fenêtre appliquent son compagnon, comme l'ouverture."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.f = os.path.join(self.tmp, 'piece.vnl')
        save(three_colours(), self.f)
        self.assertEqual(len(calques(self.f)), 1, BEFORE)                  # un calque de trois couleurs

    def test_open_document(self):
        doc = companion.open_document(self.f)
        self.assertEqual(tools(doc), [[1, 0, 3]])
        self.assertTrue(any('compagnon' in r for r in doc.report))

    def test_cam_series(self):
        from types import SimpleNamespace
        from vectordrive.cam import series
        seen = []

        def setup_for(doc, *_a):
            seen.append(tools(doc))
            return SimpleNamespace(operations=[])
        with mock.patch.object(series, 'setup_for', setup_for):
            kind = series.program_one(self.f, os.path.join(self.tmp, 'prog'))[0]
        self.assertEqual((kind, seen), ('ignoré', [[[1, 0, 3]]]), 'avant : la série lisait l’outil du calque')

    def test_batch_conversion_reads_and_writes_the_companion(self):
        from vectordrive.io import batch, native
        dst = os.path.join(self.tmp, 'vdz', 'piece.vdz')
        self.assertEqual(batch._convert_one(self.f, dst, True, False)[0], 'fait')
        self.assertEqual(tools(native.read(dst)), [[1, 0, 3]], 'avant : outil du calque partout')
        dst = os.path.join(self.tmp, 'sortie', 'piece.vnd')
        self.assertEqual(batch._convert_one(self.f, dst, True, False)[0], 'fait')
        self.assertTrue(companion.companion_path(dst).is_file(), 'avant : VND du lot sans compagnon')
        self.assertEqual(tools(reopen(dst)), [[1, 0, 3]])

    def test_vdconvert(self):
        from vectordrive import vdconvert
        seen = []
        with mock.patch.object(registry, 'save_document', lambda doc, dest: seen.append(tools(doc))):
            vdconvert.convert(self.f, 'dxf', self.tmp)
        self.assertEqual(seen, [[[1, 0, 3]]], 'avant : la conversion lisait l’outil du calque')

    def test_symbols(self):
        from vectordrive.ui import symbols
        g = symbols.file_as_group(self.f)
        self.assertEqual([c.tool for c in g.children], [1, 0, 3], 'avant : le symbole avait l’outil du calque')
        leaves, _doc = symbols._leaves_of(self.f)
        self.assertEqual([it.tool for it in leaves], [1, 0, 3])

    def test_proof_logo(self):
        """Logo du BAT : le carré noir (outil 0) d'un calque de l'outil 1 ; relu sans compagnon, sa fin de courbe noire
        ne compte pas (TypeEdit écrit du noir sans couleur propre) : il prenait le rouge de l'outil du calque."""
        from vectordrive.io import proof
        closed = proof.logo_vector(self.f)[0]
        self.assertEqual([col for _c, col in closed], [(1.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0)])


def nested_tools(doc) -> list:
    """Outils des objets de chaque calque, un groupe en liste de ceux de ses enfants."""
    def one(it):
        return [one(c) for c in it.children] if isinstance(it, Group) else it.tool
    return [[one(it) for it in L.items] for L in doc.layers]


def plate_drawing() -> Document:
    """Trois couleurs, plus une plaque de reprise posée (gardée par le compagnon seul, round 908)."""
    from vectordrive.cam import fixture
    d = three_colours()
    plate = Shape(path=geom.Path([geom.rect(-50, -50, 300, 200)]), tool=0)
    d.layers.append(Layer(name='Plaque de reprise', items=[plate], extra={fixture.PLATE_LAYER: True}))
    return d


class Review4(unittest.TestCase):
    """Quatrième relecture."""

    def test_text_and_cut_contour_on_one_layer(self):
        """Le cas de l'utilisateur : texte gravé (outil 0) et contour découpé (outil 3) sur un même calque. Le texte
        VectorDrive revient en courbe : l'outil du contour revient quand même."""
        from vectordrive.core import text as TX
        from vectordrive.core.document import Text
        from vectordrive.core.geom import Affine
        t = Text(text='AB', font='VD Géo', size=8, matrix=Affine.translation(0, 20), tool=0)
        t.outline = TX.outline_for(t)
        d = Document()
        d.layers[0].name = 'Plaque'
        d.layers[0].items += [t, square(30, 3)]
        for ext in ('.vnl', '.vnd'):
            with tempfile.TemporaryDirectory() as tmp:
                f = os.path.join(tmp, 'plaque' + ext)
                save(d, f)
                self.assertEqual(len(calques(f)), 1, BEFORE)
                back = registry.open_document(f)
                msgs = ' | '.join(companion.apply(back, f))
                self.assertEqual(tools(back), [[0, 3]], 'avant : contour resté à l’outil du calque')
                self.assertNotIn('non rétablis', msgs)
                self.assertIn('1 outil(s) d’objet rétabli(s)', msgs)

    def test_groups_of_one_object(self):
        """Un groupe d'un seul objet revient en cet objet ; un groupe d'un groupe de deux, en groupe de deux."""
        d = Document()
        d.layers[0].name = 'Groupes'
        d.layers[0].items += [square(0, 1), Group(children=[square(20, 3)]),
                              Group(children=[Group(children=[square(40, 3), square(60, 2)])])]
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'groupes.vnd')
            save(d, f)
            self.assertEqual(nested_tools(reopen(f, apply=False)), [[3, 3, [3, 3]]], BEFORE)
            self.assertEqual(nested_tools(reopen(f)), [[1, 3, [3, 2]]], 'avant : outils jamais rétablis')

    def test_tools_counted_apart(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'piece.vnl')
            save(three_colours(), f)
            msgs = ' | '.join(companion.apply(registry.open_document(f), f))
            self.assertIn('(2 outil(s) d’objet rétabli(s))', msgs, BEFORE)
            self.assertNotIn('objet(s) VectorDrive repris', msgs)

    def test_plates_stay_out_of_symbols_and_logos(self):
        from vectordrive.io import proof
        from vectordrive.ui import symbols
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'bride.vnl')
            save(plate_drawing(), f)
            self.assertEqual(len(calques(f)), 1, BEFORE)                   # la plaque n'est pas dans le fichier
            self.assertEqual(len(companion.open_document(f).layers), 2)    # la fenêtre la remet, comme avant
            g = symbols.file_as_group(f)
            self.assertEqual([c.tool for c in g.children], [1, 0, 3], 'la plaque dans le symbole posé')
            self.assertEqual(len(symbols._leaves_of(f)[0]), 3)
            box = proof.logo_vector(f)[2]
            self.assertEqual([round(v, 6) for v in box], [0.0, 0.0, 50.0, 10.0], 'la plaque dans le logo')

    def test_batch_follows_the_companion_setting(self):
        import inspect
        from vectordrive.io import batch
        from vectordrive.ui import batch_dialog
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'piece.vnl')
            save(three_colours(), f)
            out = os.path.join(tmp, 'sortie')
            dst = os.path.join(out, 'piece.vnd')
            self.assertEqual(len(batch.convert([f], out, 'vnd').done), 1)
            self.assertTrue(companion.companion_path(dst).is_file(), BEFORE)
            res = batch.convert([f], out, 'vnd', overwrite=True, companion_mode='jamais')
            self.assertEqual(len(res.done), 1)
            self.assertFalse(companion.companion_path(dst).exists())       # « jamais » : retiré
            self.assertEqual(tools(reopen(dst)), [[1, 1, 1]])
        self.assertIn("companion_mode=value(st, 'vnd/compagnon')", inspect.getsource(batch_dialog))

    def test_batch_foreign_vdz_noted_and_proof_written(self):
        from vectordrive.io import batch, native
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'piece.vnl')
            save(three_colours(), f)
            out = pathlib.Path(tmp, 'sortie')
            out.mkdir()
            native.write(Document(), out / 'piece.vdz')                     # un VDZ à lui, pas un compagnon
            res = batch.convert([f], out, 'vnd', proof=True)
            self.assertEqual((len(res.done), len(res.errors)), (1, 0), res.errors)
            self.assertEqual(res.done[0], (f, str(out / 'piece.vnd')))
            self.assertIn('n\'est pas un compagnon', res.notes[0][1])
            self.assertTrue((out / 'piece_BAT.pdf').is_file())
            self.assertFalse(companion.is_companion(out / 'piece.vdz'))

    def test_batch_vdz_without_the_companion_mark(self):
        from vectordrive.io import batch, native
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'piece.vnl')
            save(three_colours(), f)
            dst = os.path.join(tmp, 'vdz', 'piece.vdz')
            self.assertEqual(batch._convert_one(f, dst, True, False)[0], 'fait')
            back = native.read(dst)
            self.assertEqual(tools(back), [[1, 0, 3]], BEFORE)
            self.assertNotIn('compagnon', back.extra)

    def test_series_shows_the_companion_remarks(self):
        from types import SimpleNamespace
        from vectordrive.cam import series
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'piece.vnl')
            save(three_colours(), f)
            other = three_colours()
            other.layers[0].items.append(square(60, 3))
            registry.save_document(other, f)                                # retouché depuis son compagnon
            with mock.patch.object(series, 'setup_for', lambda *a: SimpleNamespace(operations=[])):
                kind, _src, _info, warnings = series.program_one(f, os.path.join(tmp, 'prog'))
        said = ' | '.join(warnings)
        self.assertEqual(kind, 'ignoré')
        self.assertIn('a changé depuis son compagnon', said, 'avant : remarques du compagnon jamais montrées')
        self.assertIn('outils des objets non rétablis', said)
        self.assertNotIn(' relu', said)


def turned_image_drawing():
    """(image, dessin) : un calque « Plan » avec une image tournée (outil 0), deux carrés des outils 1 et 3, et un
    carré masqué (pas écrit : `apply` ne reprend pas les objets riches de ce calque, `_images_back` le fait)."""
    from vectordrive.core.geom import Affine
    q = QImage(6, 3, QImage.Format.Format_RGB32)
    q.fill(QColor('#ff0000'))
    path = os.path.join(tempfile.mkdtemp(), 'logo.png')
    q.save(path, 'PNG')
    im = Image(data=pathlib.Path(path).read_bytes(), fmt='png',
               matrix=Affine.translation(60, 20) @ Affine.rotation(30) @ Affine(12, 0, 0, -6, 0, 6))
    hidden = square(80, 1)
    hidden.visible = False
    d = Document()
    d.layers[0].name = 'Plan'
    d.layers[0].items += [im, square(0, 1), square(20, 3), hidden]
    return im, d


if __name__ == '__main__':
    unittest.main()
