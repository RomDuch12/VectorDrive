"""Round 847 : un nom ne doit pas en cacher un autre. Le round 843 avait défini une seconde méthode `open_contours` : Python
garde la dernière sans rien dire, et la commande Ouvrir marquait les contours ouverts au lieu d'ouvrir les fermés."""
import ast
import os
import pathlib
import re
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

import vectordrive
from vectordrive.core import geom
from vectordrive.core.document import Layer, Plate, Shape
from vectordrive.ui.main_window import MainWindow

ROOT = pathlib.Path(vectordrive.__file__).resolve().parent
#: décorateurs qui redéfinissent un nom pour de bon
LEGAL = {'setter', 'getter', 'deleter', 'overload', 'register'}


def twice(body, where=''):
    seen, out = set(), []
    for n in body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            deco = {getattr(d, 'attr', getattr(d, 'id', '')) for d in getattr(n, 'decorator_list', [])}
            if n.name in seen and not deco & LEGAL:
                out.append(f'{where}{n.name}')
            seen.add(n.name)
        if isinstance(n, ast.ClassDef):
            out += twice(n.body, f'{n.name}.')
    return out


class TestNames(unittest.TestCase):

    def test_nothing_is_defined_twice_in_the_same_place(self):
        found = {}
        for f in ROOT.rglob('*.py'):
            names = twice(ast.parse(f.read_text(encoding='utf-8')).body)
            if names:
                found[str(f.relative_to(ROOT))] = names
        self.assertEqual(found, {})

    def test_no_command_key_is_used_twice(self):
        source = (ROOT / 'ui' / 'main_window.py').read_text(encoding='utf-8')
        keys = re.findall(r"^\s+a\('([a-z0-9_]+)',", source, flags=re.M)
        self.assertGreater(len(keys), 100)
        self.assertEqual(sorted({k for k in keys if keys.count(k) > 1}), [])


class TestCommands(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.close()
        cls.win.deleteLater()

    def setUp(self):
        self.doc = self.win.canvas.doc
        self.layer = Layer(name='Plan 1')
        self.doc.layers[:] = [self.layer]
        self.doc.active = self.layer.id
        self.doc.plate = Plate(width=200.0, height=100.0)
        self.win._undo.clear()

    def test_the_command_opens_closed_contours(self):
        sh = Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]))
        self.layer.items.append(sh)
        self.win.canvas.select([sh])
        self.win.A['open_contour'].trigger()
        self.assertFalse(self.layer.items[0].path.contours[0].closed)

    def test_ctrl_on_intersections_marks_the_open_ones(self):
        sh = Shape(path=geom.Path([geom.polyline([(0, 0), (10, 0)])]))
        self.layer.items.append(sh)
        self.win.canvas.select([])
        with mock.patch.object(MainWindow, '_ctrl_held', staticmethod(lambda: True)):
            self.win.intersections(exec_dialog=False)
        self.assertEqual(len(self.win.canvas.cross_marks), 2)


if __name__ == '__main__':
    unittest.main()
