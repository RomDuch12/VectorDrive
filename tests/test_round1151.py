"""Round 1151 (demande du 24/11) : « coloration active ou non à l'impression »."""
import json
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1151.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtGui import QColor, QImage, QPainter, QTransform  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import OWN_COLOR, Document, Shape  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : l’impression était toujours en noir'


def doc_with(color='#d01010', filled=True):
    d = Document()
    s = Shape(path=geom.Path([geom.rect(0, 0, 20, 20)]), tool=1, filled=filled)
    s.extra[OWN_COLOR] = color
    d.add(s)
    return d, s


def paint(doc, colors):
    """Le dessin peint comme sur la feuille (1 mm = 4 px), sur du blanc ; rend la couleur au milieu du carré."""
    from vectordrive.ui import printing
    img = QImage(120, 120, QImage.Format.Format_RGB32)
    img.fill(QColor('white'))
    p = QPainter(img)
    p.setTransform(QTransform.fromScale(4, 4) * QTransform.fromTranslate(10, 10))
    printing._paint_drawing(p, doc, list(doc.iter_items(visible_only=True)), False, 4.0, colors=colors)
    p.end()
    return img.pixelColor(50, 50)


class Colors(unittest.TestCase):
    def test_option_and_defaults(self):
        from vectordrive.ui import options, printing
        self.assertIn('impression/couleurs', options.BY_KEY, BEFORE)
        self.assertFalse(options.BY_KEY['impression/couleurs'].default)      # d'office : en noir, comme avant
        self.assertFalse(printing.PRINT_DEFAULTS['couleurs'])

    def test_black_or_tool_color(self):
        d, _s = doc_with()
        self.assertEqual(paint(d, False).name(), '#000000')                  # en noir
        got = paint(d, True)
        self.assertEqual(got.name(), '#d01010', BEFORE)                      # à la couleur de l'outil (la sienne)

    def test_too_light_for_paper_is_darkened(self):
        from vectordrive.ui import printing
        for light in ('#fffff0', '#ffff00'):                                 # blanc cassé, jaune
            d, s = doc_with(light)
            c = printing.print_color(d, s)
            self.assertLess(0.2126 * c.redF() + 0.7152 * c.greenF() + 0.0722 * c.blueF(), printing.PAPER_LIGHT)
            self.assertNotEqual(paint(d, True).name(), '#ffffff')            # visible sur le papier
        d, s = doc_with('#d01010')
        self.assertEqual(printing.print_color(d, s).name(), '#d01010')       # une couleur franche : telle quelle

    def test_printer_set_to_color(self):
        from PySide6.QtPrintSupport import QPrinter
        from vectordrive.ui import printing
        pr = QPrinter()
        pr.setColorMode(QPrinter.ColorMode.GrayScale)
        printing.setup_printer(pr, {'couleurs': True})
        self.assertEqual(pr.colorMode(), QPrinter.ColorMode.Color)

    def test_outline_only_stays_unfilled(self):
        d, _s = doc_with(filled=False)
        self.assertEqual(paint(d, True).name(), '#ffffff')                   # le milieu d'un contour : pas d'aplat

    def test_print_window_checkbox(self):
        from vectordrive.ui.print_dialog import PrintDialog, override_for
        d, _s = doc_with()
        dlg = PrintDialog(None, d, [], {})
        self.assertFalse(dlg.colors.isChecked())
        dlg.colors.setChecked(True)
        v = dlg.values()
        self.assertTrue(v['couleurs'])
        self.assertTrue(override_for(v)['couleurs'])
        dlg.deleteLater()
        again = PrintDialog(None, d, [], v)                                  # retenue
        self.assertTrue(again.colors.isChecked())
        again.what.setCurrentIndex(again.what.findData('bat'))
        self.assertFalse(again.colors.isEnabled())                           # la page BAT : ses couleurs à elle
        again.deleteLater()
        self.assertFalse(override_for({})['couleurs'])

    def test_print_to_pdf_with_colors(self):
        from PySide6.QtPrintSupport import QPrinter
        from vectordrive.ui import printing
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            if not w.docs:
                w.new_document()
            w.canvas.doc.add(Shape(path=geom.Path([geom.rect(0, 0, 20, 20)]), tool=1, filled=True))
            seen = []
            real = printing._paint_drawing

            def spy(*a, **kw):
                seen.append(kw.get('colors'))
                return real(*a, **kw)
            out = os.path.join(tempfile.mkdtemp(), 'essai.pdf')
            printing._paint_drawing = spy
            try:
                ok = w.print_choose({'quoi': 'tout', 'sortie': 'pdf', 'fichier': out, 'format': 'A4',
                                     'echelle': '1', 'marge': 10.0, 'plaque': False, 'couleurs': True},
                                    exec_dialog=False, printer=QPrinter())
            finally:
                printing._paint_drawing = real
            self.assertTrue(ok)
            self.assertEqual(seen, [True])
            self.assertTrue(json.loads(w.settings.value('impression/fenetre'))['couleurs'])   # retenue
            self.assertTrue(w._print_colors())                               # Imprimer la sélection la suit
            w.settings.setValue('impression/fenetre', json.dumps({'quoi': 'tout'}))   # retenue d'avant la case
            self.assertFalse(w._print_colors())
            w.settings.setValue('impression/couleurs', True)                 # … F10 alors
            self.assertTrue(w._print_colors())
            w.settings.remove('impression/fenetre')
            self.assertTrue(w._print_seed().get('couleurs'))                 # F10 : la première fois
        finally:
            w.settings.remove('impression/couleurs')
            w.settings.remove('impression/fenetre')
            for t in w.docs:
                t.modified = False
            w.modified = False
            w.close()
            w.deleteLater()
            app.processEvents()


if __name__ == '__main__':
    unittest.main()
