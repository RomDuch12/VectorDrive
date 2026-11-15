"""Round 960 : BAT — « une cote par gravure » s'arrête à 40 gravures ; au-delà le dessin est coté comme un tout
(un motif de milliers d'objets recevait deux cotes par objet)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r960.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Plate, Shape  # noqa: E402
from vectordrive.io import proof  # noqa: E402

BLUE = (0.1, 0.25, 0.55)                                 # la couleur des cotes


def plate_of(n: int):
    """n petites gravures rangées sur une plaque."""
    d = Document()
    d.plate = Plate(width=200, height=120)
    d.layers[0].items += [Shape(path=geom.Path([geom.rect(5 + 12 * (k % 16), 5 + 9 * (k // 16), 8, 5)]))
                          for k in range(n)]
    return d


def dims(doc, info) -> int:
    return sum(1 for pr in proof.build(doc, info)[0] if tuple(pr.color) == BLUE)


class Engravings(unittest.TestCase):

    def test_a_drawing_of_many_objects_is_dimensioned_as_a_whole(self):
        limit = getattr(proof, 'MAX_ENGRAVINGS', None)
        self.assertIsNotNone(limit, 'pas de borne aux cotes par gravure')                     # avant
        info = proof.ProofInfo()
        few, many = plate_of(6), plate_of(limit + 20)
        self.assertTrue(proof.unit_dims(few, info))                         # six gravures : cotées une à une
        self.assertFalse(proof.unit_dims(many, info))                       # soixante : le dessin, comme un tout
        self.assertEqual(dims(few, info), 6 * 2 * 3)                        # deux cotes par gravure (trait, flèches, valeur)
        self.assertEqual(dims(many, info), 2 * 3)                           # avant : 360 — les deux cotes de l'ensemble
        at_limit = plate_of(limit)
        self.assertTrue(proof.unit_dims(at_limit, info))
        self.assertEqual(dims(at_limit, info), limit * 2 * 3)

    def test_the_dialog_says_so(self):
        if not hasattr(proof, 'MAX_ENGRAVINGS'):
            self.fail('pas de borne aux cotes par gravure')                                    # avant
        from vectordrive.ui.batdialog import BatDialog
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            d = BatDialog(w, w.canvas.doc, proof.ProofInfo())
            self.assertIn(str(proof.MAX_ENGRAVINGS), d.checks['dims_each'].toolTip())
            d.close()
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
