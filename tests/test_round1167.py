"""Round correctif : origine du dessin et VND. Le VND est écrit avec l'origine pour zéro (`vnd_write.at_origin`) ;
relu avec son compagnon (qui remet l'origine), le dessin revient dans le repère de VectorDrive : enregistrer, relire,
enregistrer… ne le décale plus à chaque fois. VND relu et compagnon dans le même repère : les calques jumeaux sont
vérifiés par leurs boîtes et les images riches reviennent, origine posée ou non."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'rorig.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ.setdefault('VECTORDRIVE_CLOSED_TABS', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ.setdefault('VECTORDRIVE_KEYS_MEMORY', '1')

from PySide6.QtCore import QBuffer, QIODevice  # noqa: E402
from PySide6.QtGui import QColor, QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Image, Plate, Shape, Text  # noqa: E402
from vectordrive.core.geom import Affine  # noqa: E402

app = QApplication.instance() or QApplication([])
ORIGIN = (50.0, 25.0)
BEFORE = 'avant : le VND était décalé une fois de plus à chaque enregistrement'


def square(x=10.0):
    return Shape(path=geom.Path([geom.rect(x, 0, 10, 10)]), tool=0)     # l'outil du texte : un seul calque écrit


def drawing(origin=ORIGIN) -> Document:
    """Plaque 100 × 50 au zéro, carré à x = 10, texte modifiable à (20 ; 5), origine posée au centre de la plaque."""
    doc = Document()
    doc.plate = Plate(width=100.0, height=50.0, x=0.0, y=0.0, thickness=3.0)
    doc.layers[0].items += [square(), Text(text='A', font='Arial', size=8, matrix=Affine.translation(20, 5))]
    if origin is not None:
        doc.extra['origine'] = origin
    return doc


def shapes(doc):
    """Les carrés de 10 mm (pas le texte, écrit en courbes dans le VND)."""
    def is_square(it):
        x0, y0, x1, y1 = it.bbox()
        return abs(x1 - x0 - 10.0) < 1e-6 and abs(y1 - y0 - 10.0) < 1e-6
    return [it for L in doc.layers for it in L.items if isinstance(it, Shape) and is_square(it)]


def texts(doc):
    return [it for L in doc.layers for it in L.items if isinstance(it, Text)]


def save(doc, p) -> None:
    from vectordrive.io import companion, registry
    registry.save_document(doc, p)
    companion.sync(doc, p)


def vnd_only(p) -> Document:
    """Le VND tel que TypeEdit le voit : sans compagnon."""
    from vectordrive.io import registry
    return registry.open_document(p)


def reopen(p) -> tuple[Document, list]:
    from vectordrive.io import companion, registry
    doc = registry.open_document(p)
    return doc, companion.apply(doc, p)


def png_clear() -> bytes:
    q = QImage(4, 2, QImage.Format.Format_ARGB32)
    q.fill(QColor(0, 0, 255, 100))
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    assert q.save(buf, 'PNG')
    return bytes(buf.data())


def same_origin(o) -> bool:
    return o is not None and abs(float(o[0]) - ORIGIN[0]) < 1e-9 and abs(float(o[1]) - ORIGIN[1]) < 1e-9


class RoundTrips(unittest.TestCase):
    def test_saved_reread_saved_again_stays_put(self):
        from vectordrive.io import companion
        p = os.path.join(tempfile.mkdtemp(), 'origine.vnd')
        doc = drawing()
        for k in range(3):                                              # enregistrer → relire, trois fois
            save(doc, p)
            self.assertTrue(companion.companion_path(p).is_file())
            te = vnd_only(p)                                            # ce qu'ouvre TypeEdit
            self.assertAlmostEqual(shapes(te)[0].bbox()[0], -40.0, places=6, msg=(k, BEFORE))
            self.assertAlmostEqual(te.plate.x, -50.0, places=6, msg=k)  # la plaque centrée sur le zéro de TypeEdit
            self.assertAlmostEqual(te.plate.y, -25.0, places=6, msg=k)
            doc, _said = reopen(p)
            self.assertTrue(same_origin(doc.extra.get('origine')), k)   # l'origine est gardée
            self.assertAlmostEqual(shapes(doc)[0].bbox()[0], 10.0, places=6,
                                   msg=(k, 'avant : le dessin relu restait dans le repère du VND (-40)'))
            self.assertAlmostEqual(doc.plate.x, 0.0, places=6, msg=k)
            self.assertAlmostEqual(doc.plate.y, 0.0, places=6, msg=k)
            t = texts(doc)
            self.assertEqual(len(t), 1, k)                              # le texte modifiable repris du compagnon
            self.assertAlmostEqual(t[0].matrix.e, 20.0, places=6, msg=k)  # … dans le même repère que le carré
            self.assertAlmostEqual(t[0].matrix.f, 5.0, places=6, msg=k)
        # sans compagnon (supprimé, ou VND envoyé seul) : le zéro du VND est l'origine, rien ne bouge plus
        companion.companion_path(p).unlink()
        alone = vnd_only(p)
        self.assertNotIn('origine', alone.extra)
        for k in range(2):
            save(alone, p)
            alone = vnd_only(p)
            self.assertAlmostEqual(shapes(alone)[0].bbox()[0], -40.0, places=6, msg=('seul', k))

    def test_vnd_touched_in_typeedit_keeps_the_drawing_frame(self):
        """VND retouché ailleurs (empreinte changée) : il fait foi pour les objets, l'origine revient quand même du
        compagnon — le dessin relu est remis dans le repère de VectorDrive, l'enregistrer ne le décale pas."""
        from vectordrive.io import registry
        p = os.path.join(tempfile.mkdtemp(), 'retouche.vnd')
        save(drawing(), p)
        te = vnd_only(p)
        te.layers[0].items.append(square(-45.0))                        # ajouté dans TypeEdit, à x = -45 du zéro
        registry.save_document(te, p)                                   # le compagnon n'est pas mis à jour
        doc, said = reopen(p)
        self.assertTrue(any('a changé' in m for m in said))
        self.assertTrue(same_origin(doc.extra.get('origine')))
        xs = sorted(round(s.bbox()[0], 6) for s in shapes(doc))
        self.assertEqual(xs, [5.0, 10.0], 'avant : dessin relu dans le repère du VND, origine remise par-dessus')
        save(doc, p)
        xs = sorted(round(s.bbox()[0], 6) for s in shapes(vnd_only(p)))
        self.assertEqual(xs, [-45.0, -40.0], BEFORE)
        # origine invalide (écartée à l'écriture : VND pas décalé) : rien n'est décalé à la relecture non plus
        bad = drawing((float('inf'), 0.0))
        q = os.path.join(tempfile.mkdtemp(), 'invalide.vnd')
        save(bad, q)
        back, _said = reopen(q)
        self.assertAlmostEqual(shapes(back)[0].bbox()[0], 10.0, places=6)

    def test_turned_image_comes_back_with_an_origin(self):
        """Une image tournée et transparente (riche : le VND la pose droite) revient du compagnon, à sa place, même
        avec une origine posée (le round 1160 l'écartait : elle serait tombée à 50 mm de sa place)."""
        im = Image(data=png_clear(), fmt='png',
                   matrix=Affine.translation(60, 20) @ Affine.rotation(30) @ Affine(8, 0, 0, -4, 0, 4))
        doc = drawing()
        doc.layers[0].items.append(im)
        p = os.path.join(tempfile.mkdtemp(), 'image.vnd')
        for k in range(2):
            save(doc, p)
            doc, _said = reopen(p)
            ims = [it for L in doc.layers for it in L.items if isinstance(it, Image)]
            self.assertEqual([(i.data, i.matrix) for i in ims], [(im.data, im.matrix)],
                             (k, 'avant : l’image du VND (droite, sur fond blanc) gardée'))
            self.assertAlmostEqual(shapes(doc)[0].bbox()[0], 10.0, places=6, msg=k)


def rich_image(x=60.0, y=20.0) -> Image:
    """Une image tournée et transparente : riche, le VND la pose droite ; le compagnon la garde."""
    return Image(data=png_clear(), fmt='png',
                 matrix=Affine.translation(x, y) @ Affine.rotation(30) @ Affine(8, 0, 0, -4, 0, 4))


def images(doc):
    from vectordrive.io import companion
    return [it for L in doc.layers for it in companion._walk(L.items) if isinstance(it, Image)]


def marker(x=10.0, y=10.0):
    """Un point de construction TypeEdit d'origine, tel que `vnd.py` le lit (comme dans test_round1160)."""
    from vectordrive.core.document import Group
    from vectordrive.io.mfc import MfcClass, MfcObject
    from vectordrive.io.vnd_write import V13_SCHEMAS, _bbox_m, _obdao_fields
    o = MfcObject(MfcClass('CMarker', V13_SCHEMAS['CMarker']))
    o.fields = _obdao_fields(_bbox_m((x, y, x, y)))
    o.fields.update(pos=(x / 1000, y / 1000, 0.0), ints=[0] * 7)
    g = Group(children=[], name='Point de construction')
    g.extra['vnd'] = {'wraps': 0}
    g.extra['vnd_obj'] = o
    return g


def markers(doc):
    return [it for L in doc.layers for it in L.items
            if isinstance(it.extra, dict) and getattr(it.extra.get('vnd_obj'), 'cls', None) is not None
            and it.extra['vnd_obj'].cls.name == 'CMarker']


def save_te(doc, p) -> None:
    """Comme dans son propre VND TypeEdit (objets TypeEdit réécrits tels quels), puis le compagnon."""
    import pathlib
    from vectordrive.core.text import ensure_outlines
    from vectordrive.io import companion, vnd_write
    ensure_outlines(doc)
    data, _report = vnd_write.write_document(doc, allow_foreign=True)
    pathlib.Path(p).write_bytes(data)
    companion.sync(doc, p)


class MoreCases(unittest.TestCase):
    """Cas trouvés à la relecture du correctif."""

    def test_apply_twice_shifts_once(self):
        from vectordrive.io import companion, registry
        p = os.path.join(tempfile.mkdtemp(), 'deux.vnd')
        save(drawing(), p)
        doc = registry.open_document(p)
        for k in range(2):                                              # `apply` rappelé sur le même dessin
            companion.apply(doc, p)
            self.assertTrue(same_origin(doc.extra.get('origine')), k)
            self.assertAlmostEqual(shapes(doc)[0].bbox()[0], 10.0, places=6, msg=(k, 'avant : à -40'))
            self.assertAlmostEqual(doc.plate.x, 0.0, places=6, msg=k)
            self.assertEqual([(t.matrix.e, t.matrix.f) for t in texts(doc)], [(20.0, 5.0)], k)
        save(doc, p)
        self.assertAlmostEqual(shapes(vnd_only(p))[0].bbox()[0], -40.0, places=6, msg=BEFORE)

    def test_typeedit_object_with_an_origin_rewritten_as_is(self):
        """Un objet TypeEdit d'origine (point de construction) : écrit à −origine, relu, remis à sa place (sa
        translation cumulée, `vnd_shift`), puis réécrit tel quel, au même endroit, à chaque enregistrement."""
        p = os.path.join(tempfile.mkdtemp(), 'point.vnd')
        doc = drawing()
        doc.layers[0].items.append(marker(10.0, 10.0))
        save_te(doc, p)
        for k in range(3):
            te = markers(vnd_only(p))
            self.assertEqual(len(te), 1, k)
            pos = te[0].extra['vnd_obj'].fields['pos']
            self.assertAlmostEqual(pos[0], -0.040, places=9, msg=(k, BEFORE))      # (10 ; 10) − (50 ; 25), en m
            self.assertAlmostEqual(pos[1], -0.015, places=9, msg=(k, BEFORE))
            doc, _said = reopen(p)
            mk = markers(doc)
            self.assertEqual(len(mk), 1, k)
            shift = mk[0].extra.get('vnd_shift', (0.0, 0.0))
            self.assertAlmostEqual(shift[0], ORIGIN[0], places=6, msg=(k, 'avant : pas remis dans le repère du dessin'))
            self.assertAlmostEqual(shift[1], ORIGIN[1], places=6, msg=k)
            self.assertFalse(mk[0].extra.get('vnd_moved'), k)              # une translation : toujours lui-même
            save_te(doc, p)

    def test_page_of_a_vnd_without_settings_follows(self):
        from vectordrive.io import companion, registry
        p = os.path.join(tempfile.mkdtemp(), 'page.vnd')
        save(drawing(), p)
        doc = registry.open_document(p)
        doc.extra['page_mm'] = (-50.0, -25.0, -3.0, 50.0, 25.0, 0.0)    # comme un VND sans fin de document
        companion.apply(doc, p)
        for u, v in zip(doc.extra['page_mm'], (0.0, 0.0, -3.0, 100.0, 50.0, 0.0)):
            self.assertAlmostEqual(u, v, places=6, msg='avant : la page restait dans le repère du VND')

    def test_invalid_origins_shift_nothing_and_images_come_back(self):
        """Origine NaN, infinie ou hors bornes : écartée à l'écriture (VND pas décalé), rien de décalé à la relecture,
        l'image riche du compagnon revient (avant : toute origine illisible écartait les images)."""
        for o in ((float('nan'), float('nan')), (float('inf'), 0.0), (2e9, 0.0), (0.0, -5e9)):
            doc = drawing(o)
            im = rich_image()
            doc.layers[0].items.append(im)
            p = os.path.join(tempfile.mkdtemp(), 'invalide.vnd')
            save(doc, p)
            self.assertAlmostEqual(shapes(vnd_only(p))[0].bbox()[0], 10.0, places=6, msg=o)
            back, _said = reopen(p)
            self.assertAlmostEqual(shapes(back)[0].bbox()[0], 10.0, places=6, msg=o)
            self.assertAlmostEqual(back.plate.x, 0.0, places=6, msg=o)
            self.assertEqual([(i.data, i.matrix) for i in images(back)], [(im.data, im.matrix)],
                             (o, 'avant : l’image du compagnon écartée'))

    def test_laser_drawing_vnl_stays_put(self):
        from vectordrive.io import companion
        p = os.path.join(tempfile.mkdtemp(), 'laser.vnl')
        doc = drawing()
        for k in range(2):
            save(doc, p)
            self.assertTrue(companion.companion_path(p).is_file(), k)
            self.assertTrue(str(companion.companion_path(p)).endswith('laser.vnl.vdz'))
            self.assertAlmostEqual(shapes(vnd_only(p))[0].bbox()[0], -40.0, places=6, msg=(k, BEFORE))
            doc, _said = reopen(p)
            self.assertTrue(same_origin(doc.extra.get('origine')), k)
            self.assertAlmostEqual(shapes(doc)[0].bbox()[0], 10.0, places=6, msg=k)
            self.assertEqual([(t.matrix.e, t.matrix.f) for t in texts(doc)], [(20.0, 5.0)], k)

    def twins(self, origin=ORIGIN):
        """Deux calques « Plan 1 », le premier sans rien de montré (image masquée), le second avec une image tournée
        et un contour du même outil ; « premier calque montré en tête » : le VND les écrit inversés (round 989)."""
        from vectordrive.core.document import Layer
        turn = Affine.translation(20, 20) @ Affine.rotation(30)
        x = Image(data=png_clear(), fmt='png', matrix=turn @ Affine(8, 0, 0, -4, 0, 4))
        x.visible = False
        y = rich_image(40.0, 20.0)
        doc = drawing(origin)
        doc.layers[0].items[:] = [x]
        c = square(70.0)
        second = Layer(name=doc.layers[0].name, items=[y, c])
        doc.layers.append(second)
        doc.extra['vnd_premier_plan'] = True
        p = os.path.join(tempfile.mkdtemp(), 'jumeaux.vnd')
        save(doc, p)
        return doc, second, y, p

    def test_twin_layers_with_an_origin_checked_by_their_boxes(self):
        from vectordrive.io import companion, registry
        doc, second, y, p = self.twins()
        back, said = reopen(p)
        said = ' | '.join(said)
        self.assertNotIn('renommer', said)                              # ordre refait vérifié par les contenus
        self.assertEqual([L.id for L in back.layers], [second.id, doc.layers[0].id])
        self.assertEqual([(i.data, i.matrix) for i in images(back)], [(y.data, y.matrix)],
                         'avant : avec une origine, l’image du compagnon n’était pas reprise')
        self.assertAlmostEqual(shapes(back)[0].bbox()[0], 70.0, places=6)
        # la vérification compare les boîtes, origine posée ou non : un contour qui n'est pas à sa place (ordre
        # douteux) écarte les calques jumeaux (avant : avec une origine, les boîtes n'étaient pas comparées)
        back = registry.open_document(p)
        sq = shapes(back)[0]
        i = back.layers[0].items.index(sq)
        back.layers[0].items[i] = sq.transformed(Affine.translation(40, 0))
        said = ' | '.join(companion.apply(back, p))
        self.assertIn('renommer les calques', said, 'avant : dispense de la comparaison des boîtes avec une origine')
        self.assertFalse({L.id for L in back.layers} & {second.id, doc.layers[0].id})

    def test_fixture_plate_with_an_origin_stays_by_the_drawing(self):
        from vectordrive.cam import fixture
        from vectordrive.core.document import Layer
        doc = drawing()
        held = Layer(name='Plaque M4', items=[Shape(path=geom.Path([geom.rect(0, -10, 30, 30)]), tool=1)])
        held.extra[fixture.PLATE_LAYER] = {'fichier': 'plaque.dxf'}
        doc.layers.append(held)
        p = os.path.join(tempfile.mkdtemp(), 'reprise.vnd')
        for k in range(2):
            save(doc, p)
            self.assertAlmostEqual(shapes(vnd_only(p))[0].bbox()[0], -40.0, places=6, msg=(k, BEFORE))
            doc, _said = reopen(p)
            plates = [L for L in doc.layers if fixture.is_plate_layer(L)]
            self.assertEqual(len(plates), 1, k)
            self.assertAlmostEqual(plates[0].items[0].bbox()[0], 0.0, places=6, msg=k)
            self.assertAlmostEqual(shapes(doc)[0].bbox()[0], 10.0, places=6,
                                   msg=(k, 'avant : le dessin à -40, la plaque de reprise à sa place : 50 mm d’écart'))


class Window(unittest.TestCase):
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

    def test_ctrl_s_after_reopening_does_not_shift_again(self):
        w = self.w
        w.new_document()
        w.canvas.doc.add(square())
        w.canvas.set_origin(*ORIGIN)
        p = os.path.join(tempfile.mkdtemp(), 'fenetre.vnd')
        self.assertTrue(w._write(p))
        for k in range(2):
            self.assertTrue(w.open_path(p))
            self.assertEqual(w.canvas.origin, ORIGIN, k)
            self.assertAlmostEqual(shapes(w.canvas.doc)[0].bbox()[0], 10.0, places=6, msg=k)
            self.assertTrue(w._write(p))
            self.assertAlmostEqual(shapes(vnd_only(p))[0].bbox()[0], -40.0, places=6, msg=(k, BEFORE))


if __name__ == '__main__':
    unittest.main()
