"""Round 736 : calcul des champs — calculs précédents gardés et dernier
résultat « ans », d'une séance à l'autre (d'après CADCraft)."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core.calc import evaluate


class TestAns(unittest.TestCase):
    def test_core(self):
        self.assertEqual(evaluate('ans*2', 21), 42)
        self.assertEqual(evaluate('ANS + 1', 2.5), 3.5)
        with self.assertRaises(ValueError):
            evaluate('ans*2')                                   # pas encore de résultat
        with self.assertRaises(ValueError):
            evaluate('answer', 3)


class TestHistory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from vectordrive import portable
        self.ini = os.path.join(tempfile.mkdtemp(), 'calc.ini')
        self.env = mock.patch.dict(os.environ, {'VECTORDRIVE_SETTINGS': self.ini})
        self.env.start()
        self.st = portable.settings

    def tearDown(self):
        self.env.stop()

    def box(self, v=0.0):
        from PySide6.QtWidgets import QDoubleSpinBox
        b = QDoubleSpinBox()
        b.setRange(-1e6, 1e6)
        b.setDecimals(3)
        b.setValue(v)
        return b

    def test_kept_and_ans(self):
        from vectordrive.ui import fields
        b = self.box()
        self.assertEqual(fields.calculate(b.lineEdit(), '25,4*2'), 50.8)
        self.assertEqual(fields.calculate(b.lineEdit(), 'ans/4'), 12.7)
        self.assertEqual(fields.calculate(b.lineEdit(), '7'), 7)                # un simple nombre : pas gardé
        self.assertEqual(fields.calculate(b.lineEdit(), '25,4*2'), 50.8)        # revient en tête, une fois
        hist, ans = fields.history(self.st())                                   # relu : d'une séance à l'autre
        self.assertEqual(hist, ['25,4*2', 'ans/4'])
        self.assertEqual(ans, 50.8)
        self.assertIsNone(fields.calculate(b.lineEdit(), 'x*2'))               # refusé : rien ne change
        self.assertEqual(fields.history(self.st()), (hist, ans))
        for i in range(30):
            fields.calculate(b.lineEdit(), f'{i}+1')
        self.assertEqual(len(fields.history(self.st())[0]), fields.HISTORY_MAX)
        self.assertEqual(fields.history(self.st())[0][0], '29+1')

    def test_dialog_offers_history(self):
        from PySide6.QtWidgets import QInputDialog
        from vectordrive.ui import fields
        b = self.box(3)
        fields.calculate(b.lineEdit(), '2*3')
        fields.calculate(b.lineEdit(), '10/4')
        cur = b.text().strip()                                  # 2,5 tel que le champ l'affiche
        seen = {}

        def get_item(parent, title, label, items, current, editable):
            seen.update(items=list(items), editable=editable, label=label)
            return 'ans*4', True
        with mock.patch.object(QInputDialog, 'getItem', side_effect=get_item):
            self.assertEqual(fields.calculate(b.lineEdit()), 10)
        self.assertEqual(seen['items'], [cur, '10/4', '2*3'])    # la valeur du champ, puis les calculs
        self.assertTrue(seen['editable'])
        self.assertIn('ans', seen['label'])
        self.assertEqual(b.value(), 10)
        with mock.patch.object(QInputDialog, 'getItem', return_value=('', False)):
            self.assertIsNone(fields.calculate(b.lineEdit()))


if __name__ == '__main__':
    unittest.main()
