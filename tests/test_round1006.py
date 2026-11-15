"""Round 1006 : reconnaître une police depuis une image (demande du 14/11) — la commande « Reconnaître une police… »
du ruban compare aux polices du poste les lettres en courbes sélectionnées ou celles d'une image : la dernière capture
d'écran d'office, l'image du presse-papiers, un fichier ; elle explique le premier calcul ; la police choisie va aux
textes sélectionnés, sinon aux prochains textes."""
import os
import pathlib
import tempfile
import time
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1006.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

import numpy as np  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QTransform  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.core import fontmatch as FM  # noqa: E402
from vectordrive.core import fonts as F  # noqa: E402
from vectordrive.core import text as TX  # noqa: E402
from vectordrive.core.document import Group, Shape, Text  # noqa: E402
from vectordrive.core.geom import Affine  # noqa: E402

FONTS = ('Arial', 'Times New Roman', 'Courier New')
HAVE = all(F.is_available(n) for n in FONTS)


def picture(text='Plaque', font='Arial', size=70.0, white_on_black=False, transparent=False) -> QImage:
    """Une « capture d'écran » : le texte dessiné plein, noir sur blanc (ou l'inverse, ou sans fond)."""
    from vectordrive.ui.canvas import to_qpath
    t = Text(text=text, font=font, size=size, matrix=Affine.translation(0.0, 0.0))
    t.outline = TX.outline_for(t)
    x0, y0, x1, y1 = t.outline.bbox()
    img = QImage(int(x1 - x0) + 60, int(y1 - y0) + 60,
                 QImage.Format.Format_ARGB32 if transparent else QImage.Format.Format_RGB32)
    img.fill(Qt.GlobalColor.transparent if transparent else QColor('black' if white_on_black else 'white'))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setTransform(QTransform(1, 0, 0, -1, 30 - x0, 30 + y1))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor('white' if white_on_black else 'black'))
    qp = to_qpath(t.outline)
    qp.setFillRule(Qt.FillRule.OddEvenFill)
    p.drawPath(qp)
    p.end()
    return img


def curves(text='Plaque gravee', font='Arial', size=20.0) -> Shape:
    """Des lettres en courbes."""
    return Shape(path=TX.outline_for(Text(text=text, font=font, size=size, matrix=Affine.translation(0, 0))))


class ImagePaths(unittest.TestCase):

    def test_dark_shapes_become_contours(self):
        g = np.ones((40, 60), np.float32)
        g[4:14, 5:25] = 0.0                                         # un rectangle plein, en haut de l'image
        g[10:30, 35:55] = 0.0                                       # un anneau carré
        g[15:25, 40:50] = 1.0
        g[2, 58] = 0.0                                              # une poussière
        paths = FM.image_paths(g)
        self.assertEqual(len(paths), 1)
        cs = paths[0].contours
        self.assertEqual(len(cs), 3)                                # le rectangle, l'anneau et son trou ; pas la poussière
        self.assertTrue(all(c.closed for c in cs))
        boxes = [c.bbox() for c in cs]
        top = next(b for b in boxes if abs(b[2] - b[0] - 20) < 1.5 and abs(b[3] - b[1] - 10) < 1.5)
        self.assertAlmostEqual(top[1], 26, delta=1.5)               # y vers le haut : le haut de l'image reste en haut
        self.assertAlmostEqual(top[3], 36, delta=1.5)
        self.assertEqual(len(FM.letters(paths)), 2)                 # deux « lettres » : le trou va avec son anneau
        self.assertEqual(len(FM.image_paths(1.0 - g)[0].contours), 3)   # clair sur sombre : pareil
        self.assertEqual(FM.image_paths(np.ones((30, 30), np.float32)), [])
        self.assertEqual(FM.image_paths(None), [])

    def test_the_largest_shapes_are_kept(self):
        g = np.ones((60, 80), np.float32)
        for k in range(6):                                          # des taches en haut de l'image (menus, icônes)
            g[2:5, 4 + 10 * k:8 + 10 * k] = 0.0
        g[30:50, 10:30] = 0.0                                       # deux grandes formes plus bas
        g[30:50, 45:70] = 0.0
        self.assertEqual(len(FM.image_paths(g)[0].contours), 8)
        with mock.patch.object(FM, 'MAX_CONTOURS', 2):              # trop de formes : les plus grandes, pas le haut
            cs = FM.image_paths(g)[0].contours
        self.assertEqual(len(cs), 2)
        self.assertTrue(all(c.bbox()[3] - c.bbox()[1] > 15 for c in cs))

    @unittest.skipUnless(HAVE, 'polices Arial, Times New Roman, Courier New absentes')
    def test_the_font_of_a_picture_is_found(self):
        from vectordrive.ui.font_recognize import gray_of
        for font in FONTS:
            paths = FM.image_paths(gray_of(picture('Plaque gravee', font)))
            self.assertGreaterEqual(len(FM.letters(paths)), 10, font)
            got = FM.rank(paths, list(FONTS), 3)
            self.assertEqual(got[0][0], font, got)
        paths = FM.image_paths(gray_of(picture('Plaque gravee', 'Times New Roman', white_on_black=True)))
        self.assertEqual(FM.rank(paths, list(FONTS), 1)[0][0], 'Times New Roman')
        # un texte à la taille d'un écran (lettres d'une vingtaine de pixels)
        paths = FM.image_paths(gray_of(picture('Plaque gravee', 'Courier New', size=28.0)))
        self.assertEqual(FM.rank(paths, list(FONTS), 1)[0][0], 'Courier New')

    @unittest.skipUnless(HAVE, 'polices Arial, Times New Roman, Courier New absentes')
    def test_a_picture_without_background(self):
        from vectordrive.ui.font_recognize import gray_of
        g = gray_of(picture('Plaque gravee', 'Arial', transparent=True))    # PNG détouré : pas « tout noir »
        self.assertGreater(float(g.mean()), 0.5)
        self.assertEqual(FM.rank(FM.image_paths(g), list(FONTS), 1)[0][0], 'Arial')
        self.assertIsNone(gray_of(QImage()))


class Screenshots(unittest.TestCase):

    def setUp(self):
        self.dir = pathlib.Path(tempfile.mkdtemp(prefix='vd1006_'))
        env = mock.patch.dict(os.environ, {'VECTORDRIVE_SCREENSHOTS': str(self.dir)})
        env.start()
        self.addCleanup(env.stop)

    def test_the_latest_picture(self):
        from vectordrive.ui import font_recognize as R
        self.assertIsNone(R.last_screenshot())
        (self.dir / 'notes.txt').write_text('x', encoding='utf-8')
        self.assertIsNone(R.last_screenshot())                      # pas une image
        now = time.time()
        for k, name in enumerate(('ancienne.png', 'recente.PNG', 'entre.jpg')):
            f = self.dir / name
            picture('A').save(str(f))
            os.utime(f, (now - 100 * (3 - k) + (150 if name == 'recente.PNG' else 0),) * 2)
        self.assertEqual(R.last_screenshot().name, 'recente.PNG')
        self.assertEqual(R.screenshot_dirs(), [self.dir])


@unittest.skipUnless(HAVE, 'polices Arial, Times New Roman, Courier New absentes')
class Dialog(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui import text_presets as TP
        from vectordrive.ui.main_window import MainWindow
        self.dir = pathlib.Path(tempfile.mkdtemp(prefix='vd1006_'))
        env = mock.patch.dict(os.environ, {'VECTORDRIVE_SCREENSHOTS': str(self.dir)})
        env.start()
        self.addCleanup(env.stop)
        self.w = MainWindow()
        self.addCleanup(self.close)
        fmt = TP.new_text_format(self.w.settings)                   # le format des prochains textes : remis à la fin
        self.addCleanup(lambda: TP.set_new_text_format(self.w.settings, fmt, ''))
        QGuiApplication.clipboard().clear()

    def close(self):
        self.w.modified = False
        self.w.close()

    def dialog(self, names=FONTS, **kw):
        d = self.w.font_recognize_dialog(exec_dialog=False, **kw)
        self.addCleanup(d.deleteLater)
        if names:
            d.names = lambda: list(names)                           # trois polices : l'essai reste court
        return d

    def capture(self, font='Times New Roman', name='capture.png'):
        picture('Plaque gravee', font).save(str(self.dir / name))
        return self.dir / name

    def test_the_command_is_in_the_ribbons_and_in_simple_mode(self):
        from vectordrive.ui import modes
        from vectordrive.ui.ribbon import RibbonGroup
        a = self.w.A['font_recognize']
        self.assertIn('font_recognize', modes.SIMPLE)
        self.assertNotEqual(a.icon().cacheKey(), self.w.A['char_map'].icon().cacheKey())    # son icône à elle
        groups = [g for g in self.w.ribbon.findChildren(RibbonGroup)
                  if any(b.defaultAction() is a for b in g.buttons())]
        self.assertEqual(len(groups), 2)                            # CAD › Texte, et le ruban du texte (Mise en forme)
        self.assertEqual(sorted(len(g.buttons()) == 1 for g in groups), [False, True])   # 1030 : un bouton à part

    def test_the_fonts_compared_are_those_of_the_font_list(self):
        d = self.dialog(names=None)
        box = self.w.textbar.font
        for n in FONTS:                                             # hors écran, Qt peut ne pas lister les polices
            if box.findText(n) < 0:                                 # du poste : la liste les montre comme à l'écran
                box.addItem(n)
        names = d.names()
        self.assertEqual(names, [box.itemText(i) for i in range(box.count()) if box.itemText(i)])
        for n in FONTS:                                             # leur nom affiché, pas une clé « timesnewroman »
            self.assertIn(n, names)
        self.assertNotIn('timesnewroman', names)

    def test_it_points_at_the_last_screenshot(self):
        self.capture()
        d = self.dialog()
        self.assertEqual(d.source.currentData(), 'image')           # rien de sélectionné : la dernière capture
        self.assertEqual(pathlib.Path(d.path.text()).name, 'capture.png')
        self.assertFalse(d.preview.pixmap().isNull())
        self.assertTrue(d.go.isDefault())                           # Entrée : reconnaître, pas « Dernière capture »
        self.assertFalse(d.last_button.autoDefault())
        self.assertFalse(d.browse_button.autoDefault())
        self.assertTrue(d.advice.text())
        d.recognize(wait=True)
        self.assertEqual(d.results[0][0], 'Times New Roman')
        self.assertEqual(d.list.count(), min(3, d.count.value()))
        self.assertIn('%', d.list.item(0).text())
        self.assertTrue(d.apply_button.isEnabled())

    def test_applied_to_the_selected_texts_or_to_the_next_ones(self):
        from vectordrive.ui import text_presets as TP
        self.capture('Courier New')
        t = Text(text='Essai', font='Arial', size=8, matrix=Affine.translation(10, 10))
        t.outline = TX.outline_for(t)
        self.w.canvas.doc.add(t)
        d = self.dialog(start='image')
        d.recognize(wait=True)
        self.assertEqual(d.chosen(), 'Courier New')
        self.assertEqual(d.apply(), 0)                              # aucun texte sélectionné : pour les prochains
        self.assertIn('prochains', d.status.text())
        self.assertEqual(TP.new_text_format(self.w.settings)['attrs'].get('font'), 'Courier New')
        self.assertEqual(self.w.textbar.font.currentText(), 'Courier New')      # la barre de texte la montre
        self.assertEqual(t.font, 'Arial')
        self.w.canvas.select([t])
        undo = len(self.w._undo)
        self.assertEqual(d.apply(), 1)
        self.assertEqual(t.font, 'Courier New')
        self.assertEqual(len(self.w._undo), undo + 1)
        self.assertEqual(d.apply(), 0)                              # déjà cette police : dit, sans parler des prochains
        self.assertIn('déjà', d.status.text())
        self.assertEqual(len(self.w._undo), undo + 1)

    def test_the_selection_or_the_clipboard(self):
        self.capture()
        sh = curves()
        self.w.canvas.doc.add(sh)
        self.w.canvas.select([sh])
        d = self.dialog()
        self.assertEqual(d.source.currentData(), 'selection')       # des lettres en courbes : elles d'abord
        self.assertEqual(pathlib.Path(d.path.text()).name, 'capture.png')   # … et la capture reste à portée
        d.recognize(wait=True)
        self.assertEqual(d.results[0][0], 'Arial')
        QGuiApplication.clipboard().setImage(picture('Plaque gravee', 'Courier New'))
        d.source.setCurrentIndex(d.source.findData('presse-papiers'))
        d.recognize(wait=True)
        self.assertEqual(d.results[0][0], 'Courier New')
        d.source.setCurrentIndex(d.source.findData('image'))        # passé à l'image : la dernière capture
        d.recognize(wait=True)
        self.assertEqual(d.results[0][0], 'Times New Roman')

    def test_a_group_of_curves_counts_and_a_text_does_not(self):
        g = Group(children=[curves('Plaque', 'Times New Roman'), curves('gravee', 'Times New Roman')])
        self.w.canvas.doc.add(g)
        self.w.canvas.select([g])
        d = self.dialog()
        self.assertEqual(d.source.currentData(), 'selection')       # un groupe de lettres en courbes : ouvert
        self.assertEqual(len(d.selection_paths()), 2)
        d.recognize(wait=True)
        self.assertEqual(d.results[0][0], 'Times New Roman')
        t = Text(text='Essai', font='Arial', size=8, matrix=Affine.translation(10, 10))
        t.outline = TX.outline_for(t)
        self.w.canvas.doc.add(t)
        self.w.canvas.select([t])                                   # un texte : sa police est connue, on vise l'image
        d2 = self.dialog()
        self.assertEqual(d2.source.currentData(), 'image')
        self.assertEqual(d2.selection_paths(), [])

    def test_nothing_to_read_is_said(self):
        d = self.dialog(start='image')                              # pas de capture, pas de presse-papiers
        self.assertEqual(d.source.currentData(), 'image')
        self.assertIn('Parcourir', d.status.text())
        d.path.setText(str(self.dir / 'absente.png'))
        d.recognize(wait=True)
        self.assertEqual(d.results, [])
        self.assertIn('illisible', d.status.text())
        (self.dir / 'faux.png').write_bytes(b'pas une image')
        d.path.setText(str(self.dir / 'faux.png'))
        d.recognize(wait=True)
        self.assertIn('illisible', d.status.text())
        blank = QImage(80, 40, QImage.Format.Format_RGB32)
        blank.fill(QColor('white'))
        blank.save(str(self.dir / 'vide.png'))
        d.path.setText(str(self.dir / 'vide.png'))
        d.recognize(wait=True)
        self.assertEqual(d.results, [])
        self.assertIn('Aucune forme', d.status.text())
        self.assertFalse(d.apply_button.isEnabled())
        self.capture()
        d.path.setText(str(self.dir / 'capture.png'))
        with mock.patch.object(FM, 'image_paths', side_effect=ValueError('image trop détaillée')):
            d.recognize(wait=True)                                  # photo, trame : dit, sans exception
        self.assertIn('trop chargée', d.status.text())
        self.assertEqual(d.go.text(), 'Reconnaître')

    def test_stopped_while_running(self):
        self.capture()
        d = self.dialog()
        d.recognize(wait=True)
        self.assertEqual(d.list.count(), 3)
        d.recognize()                                               # relancée : la liste d'avant s'en va
        self.assertEqual(d.go.text(), 'Arrêter')
        self.assertEqual(d.list.count(), 0)
        self.assertFalse(d.apply_button.isEnabled())
        d._go_or_stop()                                             # arrêtée : son résultat ne viendra pas
        self.assertIn('arrêtée', d.status.text())
        d._thread.join(60)
        app.processEvents()
        self.assertEqual((d.results, d.list.count(), d.go.text()), ([], 0, 'Reconnaître'))
        d.recognize()
        d.close()                                                   # fermée pendant le calcul : rien ne casse
        d._thread.join(60)
        app.processEvents()
        self.assertIsNone(d._token)

    def test_the_first_time_is_explained(self):
        empty = pathlib.Path(tempfile.mkdtemp(prefix='vd1006_'))
        with mock.patch.object(FM, 'cache_dir', return_value=empty):
            d = self.dialog(start='image')
        self.assertIn('première fois', d.explain.text())
        self.assertIn('bold', d.explain.styleSheet())               # rien de gardé encore : mise en avant
        (empty / 'x.npz').write_bytes(b'x')
        with mock.patch.object(FM, 'cache_dir', return_value=empty):
            d2 = self.dialog(start='image')
        self.assertNotIn('bold', d2.explain.styleSheet())
        self.assertTrue(d2.explain.text())


if __name__ == '__main__':
    unittest.main()
