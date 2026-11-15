"""Round 317 : plaque (TypeEdit : Surface active) — marges (zone gravable,
avertissement à la vérification, cadre affiché, enregistrées), ajuster la
composition à la nouvelle taille, proportions gardées ou non."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import check, geom
from vectordrive.core.document import Document, Plate, Shape
from vectordrive.io import native

app = QApplication.instance() or QApplication([])


class TestMargins(unittest.TestCase):
    def test_usable_and_check(self):
        d = Document()
        d.plate = Plate(100, 50, margins=[5, 5, 4, 4])
        self.assertEqual(d.plate.usable(), (5, 4, 95, 46))
        d.add(Shape(path=geom.Path([geom.rect(2, 10, 10, 10)])))            # dans la marge gauche
        d.add(Shape(path=geom.Path([geom.rect(20, 10, 10, 10)])))
        codes = [i.code for i in check.check(d)]
        self.assertIn('hors_marges', codes)
        self.assertNotIn('hors_plaque', codes)
        d.plate.margins = [0, 0, 0, 0]
        self.assertNotIn('hors_marges', [i.code for i in check.check(d)])

    def test_saved(self):
        d = Document()
        d.plate = Plate(100, 50, margins=[1, 2, 3, 4])
        back = native.from_dict(native.to_dict(d))
        self.assertEqual(back.plate.margins, [1, 2, 3, 4])
        raw = native.to_dict(d)
        raw['plate']['futur'] = 1                                            # champ d'une autre version
        self.assertEqual(native.from_dict(raw).plate.width, 100)

    def test_adjust(self):
        from vectordrive.ui.main_window import MainWindow, PlateDialog
        w = MainWindow()
        try:
            c = w.canvas
            c.doc.plate = Plate(100, 50)
            s = Shape(path=geom.Path([geom.rect(40, 20, 20, 10)]))           # au centre
            c.doc.add(s)
            dlg = PlateDialog(c.doc.plate, w, settings=w.settings, drawing_bbox=c.doc.bbox())
            dlg.w.setValue(200)
            dlg.adjust.setChecked(True)
            dlg.keep_ratio.setChecked(False)
            w.apply_plate(dlg.plate(), dlg.adjust_matrix())
            b = c.doc.layers[0].items[0].bbox()
            self.assertEqual(tuple(round(v, 6) for v in b), (80, 20, 120, 30))    # deux fois plus large
            dlg = PlateDialog(c.doc.plate, w, settings=w.settings, drawing_bbox=c.doc.bbox())
            dlg.h.setValue(100)
            dlg.w.setValue(200)
            dlg.adjust.setChecked(True)
            m = dlg.adjust_matrix()
            self.assertIsNotNone(m)                                          # proportions : × 1 en largeur
            dlg.adjust.setChecked(False)
            self.assertIsNone(dlg.adjust_matrix())
            w.undo()
            self.assertEqual(c.doc.plate.width, 100)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
