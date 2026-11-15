"""Round 929 : F2 (Dimensions) avec les pourcentages — « 120% », « 80% », « +20% », « -20% » dans Largeur et Hauteur, et
les champs « % » à côté —, le F2 suivant qui coche ou décoche « Conserver les proportions » (le premier n'y touche pas) ;
maintien avant déplacement à la souris de 0,25 s par défaut."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r929.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


class Dims(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def setUp(self):
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        w = self.w
        w.new_document()
        self.sh = Shape(path=geom.Path([geom.rect(0, 0, 20, 10)]))
        w.canvas.doc.add(self.sh)
        w.canvas.select([self.sh])
        w.dims.keep.setChecked(True)
        w.dims.refresh()

    def size(self):
        bb = self.w.canvas.selection_bbox()
        return round(bb[2] - bb[0], 6), round(bb[3] - bb[1], 6)

    def typed(self, key, text):
        f = self.w.dims.fields[key]
        f.lineEdit().setText(text)
        f.interpretText()
        self.w.dims.apply()
        self.w.dims.refresh()

    def test_percent_typed_in_width_and_height(self):
        self.typed('w', '150%')                                     # agrandir, la hauteur suit
        self.assertEqual(self.size(), (30.0, 15.0))
        self.typed('h', '-20 %')                                    # réduire de 20 %
        self.assertEqual(self.size(), (24.0, 12.0))
        self.w.dims.keep.setChecked(False)
        self.typed('w', '+50% mm')                                  # la largeur seule
        self.assertEqual(self.size(), (36.0, 12.0))
        self.typed('h', '0%')                                       # nul : rien
        self.assertEqual(self.size(), (36.0, 12.0))

    def test_percent_fields(self):
        d = self.w.dims
        d.pct['w'].setValue(50)
        d._percent('w')
        self.assertEqual(self.size(), (10.0, 5.0))
        self.assertEqual(d.pct['w'].value(), 100.0)                 # revient à 100 %
        d.keep.setChecked(False)
        d.pct['h'].setValue(200)
        d._percent('h')
        self.assertEqual(self.size(), (10.0, 10.0))

    def test_second_f2_toggles_the_proportions(self):
        w = self.w
        w.resize(1600, 1000)
        w.show()
        w.activateWindow()
        self.addCleanup(w.hide)
        app.processEvents()
        w.canvas.setFocus()
        app.processEvents()
        w.f2()                                                      # le premier : les dimensions, la case telle quelle
        app.processEvents()
        fw = QApplication.focusWidget()
        if fw is None or not w.dims.isAncestorOf(fw):
            self.skipTest('pas de focus clavier sur cette plateforme')
        self.assertTrue(w.dims.keep.isChecked())
        w.f2()
        self.assertFalse(w.dims.keep.isChecked())
        w.f2()
        self.assertTrue(w.dims.keep.isChecked())
        w.canvas.setFocus()                                         # retour au dessin : de nouveau un premier F2
        app.processEvents()
        w.f2()
        app.processEvents()
        self.assertTrue(w.dims.keep.isChecked())


class HoldDelay(unittest.TestCase):

    def test_quarter_second_by_default(self):
        from vectordrive.ui import options
        from vectordrive.ui.main_window import MainWindow
        self.assertEqual(options.BY_KEY['options/delai_deplacement'].default, 250)
        w = MainWindow()
        try:
            st = w.settings
            st.remove('options/delai_deplacement')
            w.apply_options()
            self.assertEqual(w.canvas.move_delay_ms, 250)
            st.setValue('options/delai_deplacement', 600)              # l'ancien défaut enregistré : 250, une fois
            st.remove('options/delai_deplacement_929')
            w.apply_options()
            self.assertEqual((w.canvas.move_delay_ms, int(st.value('options/delai_deplacement'))), (250, 250))
            st.setValue('options/delai_deplacement', 600)              # choisi ensuite : gardé
            w.apply_options()
            self.assertEqual(w.canvas.move_delay_ms, 600)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
