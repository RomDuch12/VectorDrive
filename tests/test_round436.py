"""Round 436 : la liste « Outil » du formulaire suit la stratégie choisie ; filtres compacts ;
pas de clé en double dans les raccourcis TE."""
import ast
import os
import pathlib
import sys
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.cam import model, toolprefs

app = QApplication.instance() or QApplication([])
sys.path.insert(0, os.path.dirname(__file__))


class TestKindChange(unittest.TestCase):
    def test_refill(self):
        from test_round435 import Parent, Settings, library
        from vectordrive.ui.cam_panel import FieldsDialog
        s = Settings()
        toolprefs.save(s, {'gravure': {'rules': [{'type': 'nature', 'value': 'conique'}], 'mode': 'seuls'}})
        f2 = model.CamTool(name='F2', kind='fraise', diameter=2.0, number=1)
        v30 = model.CamTool(name='V30', kind='conique', diameter=3.0, number=2)
        op = model.Operation(kind='poche', tool_id=f2.id)
        self.parent = Parent(s)
        d = FieldsDialog(self.parent, 'essai', op, None, [f2, v30], library=library())
        c = d.widgets['tool_id']
        datas = lambda: [c.itemData(i) for i in range(c.count()) if c.itemData(i)]    # noqa: E731
        self.assertEqual(datas()[:2], [f2.id, v30.id])
        k = d.widgets['kind']
        k.setCurrentIndex(k.findData('gravure'))
        self.assertEqual(c.op_kind, 'gravure')
        self.assertEqual(datas()[0], v30.id)                       # conique d'abord
        self.assertIn(f2.id, datas())                              # l'outil choisi reste
        self.assertEqual(c.currentData(), f2.id)
        self.assertTrue(any(str(x).startswith('lib:') for x in datas()))     # Lib V60 proposé
        d.apply()
        self.assertEqual(op.tool_id, f2.id)


class TestCompact(unittest.TestCase):
    def test_filter_bar_width(self):
        from vectordrive.ui.tool_filters import FilterBar
        f = FilterBar()
        from PySide6.QtWidgets import QSizePolicy
        for c in (f.kind, f.vendor, f.op):                 # 1042 : réparties sur la largeur avec la recherche
            self.assertEqual(c.sizePolicy().horizontalPolicy(), QSizePolicy.Policy.Expanding)
        self.assertLessEqual(f.text.maximumWidth(), 460)    # la recherche ne prend plus toute la place

    def test_no_duplicate_te_keys(self):
        src = (pathlib.Path(__file__).resolve().parents[1] / 'vectordrive/ui/shortcuts.py').read_text(encoding='utf-8')
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Dict):
                keys = [k.value for k in node.keys if isinstance(k, ast.Constant)]
                self.assertEqual(len(keys), len(set(keys)), [k for k in keys if keys.count(k) > 1][:3])


if __name__ == '__main__':
    unittest.main()
