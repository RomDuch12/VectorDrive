"""Round 1107 : « En colonnes » levait NameError à chaque fois (champ `gutter` d'une classe locale qui lisait le paramètre
du même nom) ; Rechercher / remplacer et Orthographe restaient en mémoire après leur fermeture. Vrai `exec()`."""
import inspect
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1107.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QEvent, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])


class TestColumnsAndReleased(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        cls.w.show()
        app.processEvents()
        cls.answer = 'reject'
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
        if m is not None:
            getattr(m, cls.answer)()

    def text(self, s='un\ndeux\ntrois\nquatre'):
        from vectordrive.core.document import Text
        from vectordrive.core.geom import Affine
        c = self.w.canvas
        c.doc.layers[0].items.clear()
        t = Text(text=s, font='Arial', size=5.0, matrix=Affine.translation(10.0, 50.0))
        c.doc.add(t)
        c.selection = [t]
        return t

    def test_columns_real_dialog(self):
        from vectordrive.core.document import Group
        t = self.text()
        self.w.settings.setValue('colonnes/nombre', 2)            # (valeurs retenues : un autre essai a pu en poser)
        self.w.settings.setValue('colonnes/ecart', 5.0)
        type(self).answer = 'accept'                              # la fenêtre validée telle quelle (2 colonnes, 5 mm)
        try:
            self.w.text_columns()                                 # avant : NameError: name 'gutter' is not defined
        finally:
            type(self).answer = 'reject'
        items = self.w.canvas.doc.layers[0].items
        self.assertEqual(len(items), 1)
        self.assertIsInstance(items[0], Group)
        self.assertIsNot(items[0], t)
        self.assertEqual(items[0].extra['columns'], {'n': 2, 'gutter': 5.0})
        self.text()
        self.w.text_columns()                                     # annulée : rien de changé
        self.assertNotIsInstance(self.w.canvas.doc.layers[0].items[0], Group)

    def test_columns_dialog_values(self):
        type(self).answer = 'accept'
        try:
            self.assertEqual(self.w._columns_dialog(3, 2.5), (3, 2.5))
        finally:
            type(self).answer = 'reject'

    def test_released(self):
        from vectordrive.ui.find_replace_dialog import FindReplaceDialog
        from vectordrive.ui.spell_dialog import SpellDialog
        for c in (FindReplaceDialog, SpellDialog):
            self.assertIn('release(self)', inspect.getsource(c.__init__), c.__name__)
        self.text('Plaque')
        out = []
        for _ in range(4):
            self.w.find_replace_dialog()
            for _ in range(6):
                app.processEvents()
            app.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
            out.append(len(app.allWidgets()))
        self.assertEqual(out[-1], out[1], out)


if __name__ == '__main__':
    unittest.main()
