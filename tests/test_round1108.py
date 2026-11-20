"""Round 1108 : un résultat validé vide (Braille sans texte, esquisse contrainte vide ou vidée, courbe sans point, trame
blanche reprise) levait TypeError sur une boîte None. Il ne pose rien, le dit, et l'objet repris reste tel qu'il était.
Vrai `exec()` validé par minuterie (accept() : OK est désactivé à la souris pour Braille et esquisse vides)."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1108.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

app = QApplication.instance() or QApplication([])


class TestEmptyResult(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        cls.w.show()
        app.processEvents()
        cls.before_accept = None
        cls.timer = QTimer()
        cls.timer.timeout.connect(cls._close_modal)
        cls.timer.start(30)

    @classmethod
    def tearDownClass(cls):
        cls.timer.stop()
        cls.w.modified = False
        for t in getattr(cls.w, 'docs', []):
            t.modified = False
        cls.w.close()
        cls.w.deleteLater()

    @classmethod
    def _close_modal(cls):
        m = app.activeModalWidget()
        if m is None or isinstance(m, QMessageBox):
            return
        if cls.before_accept is not None:
            cls.before_accept(m)
        m.accept()

    def setUp(self):
        c = self.w.canvas
        c.doc.layers[0].items.clear()
        c.selection = []
        type(self).before_accept = None
        p = mock.patch.object(QMessageBox, 'information', staticmethod(lambda *a, **k: self.said.append(a[2])))
        self.said = []
        p.start()
        self.addCleanup(p.stop)

    def items(self):
        return self.w.canvas.doc.layers[0].items

    def test_braille_without_text(self):
        def clear(m):
            m.text.setPlainText('')
        type(self).before_accept = clear
        self.w.new_braille()                                      # avant : TypeError 'NoneType' object is not subscriptable
        self.assertEqual(self.items(), [])
        self.assertEqual(len(self.said), 1)
        type(self).before_accept = lambda m: m.text.setPlainText('ab')
        self.w.new_braille()                                      # un texte : posé comme avant
        self.assertEqual(len(self.items()), 1)
        self.assertIn('braille', self.items()[0].extra)

    def test_braille_emptied_keeps_object(self):
        from vectordrive.core import braille as BR
        g = BR.build(BR.BrailleSpec(text='ab'))
        self.w.canvas.doc.add(g)
        type(self).before_accept = lambda m: m.text.setPlainText(' ')
        self.w.edit_braille(g)
        self.assertEqual(self.items(), [g])                       # rien d'effacé
        self.assertEqual(len(self.said), 1)

    def test_empty_sketch_blank_page(self):
        r = self.w.sketch_edit()                                  # page blanche validée : avant TypeError (list(None))
        self.assertIsNone(r)
        self.assertEqual(self.items(), [])
        self.assertEqual(len(self.said), 1)

    def test_sketch_done_empty_keeps_replaced(self):
        from vectordrive.core import geom, sketch as SK
        from vectordrive.core.document import Shape
        s = Shape(path=geom.Path([geom.rect(0, 0, 20, 10)]))
        self.w.canvas.doc.add(s)
        self.assertIsNone(self.w.sketch_done(SK.Sketch(), [s]))
        self.assertEqual(self.items(), [s])
        sk = SK.Sketch()
        for k in sk.add_rect(0, 0, 10, 5):                        # rien que de la construction : vide aussi
            sk.lines[k]['construction'] = True
        self.assertIsNone(self.w.sketch_done(sk, [s]))
        self.assertEqual(self.items(), [s])

    def test_edit_sketch_emptied_keeps_object(self):
        from vectordrive.core import sketch as SK
        sk = SK.Sketch()
        sk.add_rect(0, 0, 30, 20)
        shape = self.w.sketch_done(sk)
        self.assertIsNotNone(shape)
        type(self).before_accept = lambda m: setattr(m, 'sketch', SK.Sketch())
        self.assertIsNone(self.w.edit_sketch(shape))
        self.assertEqual(self.items(), [shape])
        self.assertIn('sketch', shape.extra)
        self.assertEqual(len(self.said), 1)

    def test_history_sketch_emptied_keeps_volume(self):
        from vectordrive.core import sketch as SK
        sk = SK.Sketch()
        sk.add_rect(0, 0, 30, 20)
        shape = self.w.sketch_done(sk)
        self.w.canvas.select([shape])
        it = self.w.solid_extrude(params={'height': 10.0})[0]
        before = list(self.items())
        self.assertIsNone(self.w.history_set_sketch(it, (0, 0), SK.Sketch()))   # avant : TypeError (list(None))
        self.assertEqual(self.items(), before)
        self.assertEqual(len(self.said), 1)

    def test_place_curve_empty(self):
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        s = Shape(path=geom.Path([geom.rect(0, 0, 20, 10)]))
        self.w.canvas.doc.add(s)
        self.w.canvas.selection = [s]
        self.assertIsNone(self.w._place_curve(geom.Path([])))     # avant : TypeError, puis la forme choisie rendue
        self.assertEqual(self.items(), [s])
        self.assertEqual(len(self.said), 1)

    def test_halftone_emptied_keeps_object(self):
        from vectordrive.core.document import Group
        from vectordrive.core import braille as BR
        g = BR.build(BR.BrailleSpec(text='ab'))
        self.w.canvas.doc.add(g)
        self.w._replace_keep_corner(g, Group(children=[]))       # une trame reprise toute blanche
        self.assertEqual(self.items(), [g])
        self.assertEqual(len(self.said), 1)


if __name__ == '__main__':
    unittest.main()
