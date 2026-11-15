"""Round 737 : Dupliquer sur courbe par écart (d'après ARRAYPATH de
CADCraft) — un exemplaire tous les X mm le long de la courbe ; panneau FAO :
la ligne choisie par programme remplace la sélection, Ctrl enfoncé ou non."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import duplicate as D
from vectordrive.core.document import Shape
from vectordrive.core.geom import Path, circle, polyline, rect


def _dot():
    return Shape(path=Path([circle((0, 0), 1)]))


def _centres(items):
    out = []
    for it in items:
        bb = it.bbox()
        out.append((round((bb[0] + bb[2]) / 2, 6), round((bb[1] + bb[3]) / 2, 6)))
    return out


class TestAlongSpacing(unittest.TestCase):
    def test_open_curve(self):
        line = polyline([(0, 0), (100, 0)])
        got = _centres(D.along([_dot()], line, 3, spacing=25))
        self.assertEqual(got, [(0, 0), (25, 0), (50, 0), (75, 0), (100, 0)])     # bout compris s'il tombe juste
        got = _centres(D.along([_dot()], line, 3, spacing=30))
        self.assertEqual([p[0] for p in got], [0, 30, 60, 90])                  # le reste de la courbe vide

    def test_closed_curve(self):
        sq = rect(0, 0, 40, 20)                                                 # 120 mm de tour
        got = D.along([_dot()], sq, 1, spacing=30, rotate=False)
        self.assertEqual(len(got), 4)                                           # pas de copie doublée au retour
        self.assertEqual(len(D.along([_dot()], sq, 1, spacing=35)), 4)          # 0, 35, 70, 105

    def test_count_unchanged_and_limit(self):
        line = polyline([(0, 0), (100, 0)])
        self.assertEqual(len(D.along([_dot()], line, 6)), 6)                   # par le nombre, comme avant
        self.assertEqual(len(D.along([_dot()], line, 6, spacing=0)), 6)
        with self.assertRaises(ValueError):
            D.along([_dot()], line, 1, spacing=0.001)
        self.assertEqual(len(D.along([_dot()], line, 1, spacing=200)), 1)        # plus long que la courbe : une


class TestDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def test_dialog_and_window(self):
        from PySide6.QtWidgets import QMessageBox
        from unittest import mock
        from vectordrive.ui.dialogs import DuplicateDialog
        w, c = self.w, self.w.canvas
        dlg = DuplicateDialog(w, center=(0, 0), settings=w.settings)
        dlg.tabs.setCurrentIndex(3)
        dlg.al_sp.setValue(20)
        self.assertFalse(dlg.al_n.isEnabled())                                  # l'écart commande
        v = dlg.values()
        self.assertEqual((v['mode'], v['al_sp']), ('along', 20))
        self.assertEqual(float(w.settings.value('dupliquer/al_sp')), 20)
        dot, line = _dot(), Shape(path=Path([polyline([(0, 0), (60, 0)])]))
        c.doc.active_layer.items = [dot, line]
        c.select([dot, line])
        new = w.duplicate(v)
        self.assertEqual([p[0] for p in _centres(new)], [0, 20, 40, 60])
        c.select([dot, line])
        with mock.patch.object(QMessageBox, 'information') as info:
            self.assertEqual(w.duplicate(dict(v, al_sp=0.001)), [])
        self.assertIn('10000', info.call_args[0][2])


from tests.test_round699 import Base  # noqa: E402  (fenêtre avec deux opérations liées)


class TestCtrlHeld(Base):
    def test_move_keeps_one_row(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from vectordrive.cam import model
        s = self.p.setup()
        s.operations.append(model.Operation(name='C', kind='contour', tool_id=self.cyl.id))
        self.p.save(s)
        self.p._select_row(self.p.ops, 2)
        QTest.keyPress(self.p.ops, Qt.Key.Key_Control, Qt.KeyboardModifier.ControlModifier)
        try:
            self.p.move_op(-1)                                  # Ctrl tenu : C passe au-dessus du bloc lié…
            self.assertEqual(self.names(), ['C', 'Ébauche', 'Gravure'])
            self.assertEqual(sorted({i.row() for i in self.p.ops.selectedIndexes()}), [0])   # …et reste seule choisie
            self.p.move_op(1)
            self.assertEqual(self.names(), ['Ébauche', 'Gravure', 'C'])
        finally:
            QTest.keyRelease(self.p.ops, Qt.Key.Key_Control)    # pas de Ctrl laissé aux essais suivants


if __name__ == '__main__':
    unittest.main()
