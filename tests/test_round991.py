"""Round 991 : textes, retour de l'atelier — « Texte : selection multiple : formulaire commun pour modif tous ».
Double-clic sur un des textes sélectionnés : un formulaire commun ; les champs modifiés vont à tous, les autres restent
ceux de chaque texte (en gris quand ils diffèrent) ; un seul pas d'annulation."""
import os
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication  # noqa: E402

from vectordrive.core import text as TX  # noqa: E402
from vectordrive.core.document import Layer, Plate, Text  # noqa: E402
from vectordrive.core.geom import Affine  # noqa: E402
from vectordrive.ui import dialogs  # noqa: E402
from vectordrive.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


def text(s, font='VD Trait', size=5.0, y=10.0, **kw):
    t = Text(text=s, font=font, size=size, matrix=Affine.translation(10, y), **kw)
    t.outline = TX.outline_for(t)
    return t


class Base(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
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
        self.win._redo.clear()
        self.a = text('Alpha', 'VD Trait', 5.0, 10.0)
        self.b = text('Beta', 'VD Géo', 5.0, 30.0, spacing=0.5)
        self.c = text('Gamma', 'VD Trait', 5.0, 50.0)
        self.layer.items[:] = [self.a, self.b, self.c]

    def double_click(self, item, edit):
        seen = {}

        def fake_exec(dlg):
            seen['dlg'] = dlg
            edit(dlg)
            return True
        with mock.patch.object(dialogs.TextsDialog, 'exec', fake_exec):
            self.win._item_double_clicked(item)
        return seen.get('dlg')


class CommonForm(Base):

    def test_changed_fields_go_to_all_others_stay(self):
        self.win.canvas.select([self.a, self.b, self.c])
        before = [t.outline.bbox() for t in (self.a, self.b, self.c)]

        def edit(dlg):
            self.assertEqual(dlg.font_box.currentText(), 'VD Géo')       # celui double-cliqué, montré
            dlg.size_box.setValue(8.0)
            dlg.align.setCurrentIndex(dlg.align.findData('center'))
        dlg = self.double_click(self.b, edit)
        self.assertIsNotNone(dlg)
        self.assertEqual([t.size for t in (self.a, self.b, self.c)], [8.0, 8.0, 8.0])
        self.assertEqual({t.align for t in (self.a, self.b, self.c)}, {'center'})
        self.assertEqual([t.font for t in (self.a, self.b, self.c)], ['VD Trait', 'VD Géo', 'VD Trait'])   # pas touché
        self.assertEqual([t.spacing for t in (self.a, self.b, self.c)], [0.0, 0.5, 0.0])
        self.assertTrue(all(t.outline.bbox() != bb for t, bb in zip((self.a, self.b, self.c), before)))
        self.assertEqual(len(self.win._undo), 1)                     # un seul pas
        self.win.undo()
        texts = [it for it in self.win.canvas.doc.active_layer.items if isinstance(it, Text)]
        self.assertEqual([t.size for t in texts], [5.0, 5.0, 5.0])
        self.assertEqual({t.align for t in texts}, {'left'})

    def test_one_text_keeps_its_own_editing(self):
        self.win.canvas.select([self.a])
        with mock.patch.object(dialogs.TextsDialog, 'exec') as common, \
                mock.patch.object(MainWindow, 'type_in_text') as typing, \
                mock.patch.object(MainWindow, 'edit_text') as single:
            self.win._item_double_clicked(self.a)
        common.assert_not_called()
        self.assertTrue(typing.called or single.called)
        self.win.canvas.select([self.a, self.b])
        dlg = self.double_click(self.a, lambda d: d.fit_w.setValue(60.0))
        self.assertIsNotNone(dlg)
        self.assertEqual([(t.extra.get('fit') or {}).get('width') for t in (self.a, self.b, self.c)], [60.0, 60.0, None])

    def test_nothing_changed_no_step(self):
        self.win.canvas.select([self.a, self.c])
        dlg = self.double_click(self.a, lambda d: d.size_box.setValue(5.0))    # même valeur : rien ne change
        self.assertIsNotNone(dlg)
        self.assertEqual(len(self.win._undo), 0)
        dlg = self.double_click(self.a, lambda d: (d.size_box.setValue(6.0), d.size_box.setValue(5.0)))   # touché, revenu
        self.assertEqual(dlg.changes(), {'size': 5.0})
        self.assertEqual(len(self.win._undo), 0)                     # le pas posé est retiré
        self.assertEqual([t.size for t in (self.a, self.c)], [5.0, 5.0])


class Dialog(unittest.TestCase):

    def test_mixed_fields_and_changes(self):
        rows = [{'font': 'VD Trait', 'size': 5.0, 'width': 100.0, 'spacing': 0.0, 'line_spacing': 1.2, 'align': 'left',
                 'spacing_mode': 'typo', 'italic': 0.0, 'fit_width': 0.0, 'fit_mode': 'spacing'},
                {'font': 'VD Géo', 'size': 5.0, 'width': 100.0, 'spacing': 0.5, 'line_spacing': 1.2, 'align': 'left',
                 'spacing_mode': 'typo', 'italic': 0.0, 'fit_width': 0.0, 'fit_mode': 'spacing'}]
        d = dialogs.TextsDialog(None, rows)
        self.assertEqual(d.mixed, {'font', 'spacing'})
        self.assertEqual(d.font_box.styleSheet(), d.MIXED_STYLE)
        self.assertEqual(d.size_box.styleSheet(), '')
        self.assertEqual(d.changes(), {})
        d.width_box.setValue(80.0)
        d.spacing.setValue(1.0)
        self.assertEqual(d.spacing.styleSheet(), '')                    # touché : plus en gris
        self.assertEqual(d.changes(), {'width': 0.8, 'spacing': 1.0})
        self.assertEqual(d.font_box.currentText(), 'VD Trait')          # le premier, montré
        self.assertTrue(callable(d.width) and callable(d.size) and callable(d.font))   # méthodes de QWidget intactes


class OneUndo(Base):

    def test_nested_and_unused(self):
        w = self.win
        with w.one_undo('a') as outer:
            w.push_undo('ignoré')
            with w.one_undo('b') as inner:
                inner['used'] = False                    # imbriqué : ne retire pas le pas de l'extérieur
            outer['used'] = True
        self.assertEqual(len(w._undo), 1)
        with w.one_undo('c') as step:
            step['used'] = False
        self.assertEqual(len(w._undo), 1)
        w.push_undo('après')
        self.assertEqual(len(w._undo), 2)

    def test_unused_step_gives_back_redo_and_oldest(self):
        w = self.win
        w.push_undo('un')
        w.push_undo('deux')
        w.undo()
        self.assertEqual(len(w._redo), 1)
        pushes = w._undo_pushes
        with w.one_undo('rien') as step:
            step['used'] = False
        self.assertEqual((len(w._undo), len(w._redo), w._undo_pushes), (1, 1, pushes))   # rétablir reste possible
        first = w._undo[0]
        with mock.patch.object(w, 'undo_limit', 1, create=True):
            with w.one_undo('rien') as step:
                step['used'] = False
        self.assertEqual(len(w._undo), 1)
        self.assertIs(w._undo[0], first)                 # pile pleine : le plus ancien revient


if __name__ == '__main__':
    unittest.main()
