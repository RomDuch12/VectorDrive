"""Round 830 : Décaler sans perdre l'original, dictionnaire personnel, compression globale."""
import json
import os
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox

from vectordrive.core import geom
from vectordrive.core import spell as SP
from vectordrive.core import text as TX
from vectordrive.core.document import Layer, Plate, Shape, Text
from vectordrive.core.geom import Path
from vectordrive.ui import shortcuts as S
from vectordrive.ui.dialogs import OffsetDialog
from vectordrive.ui.main_window import MainWindow
from vectordrive.ui.spell_dialog import SpellDialog, SpellSession

app = QApplication.instance() or QApplication([])
DICT = 'orthographe/dictionnaire'
OFFSET_KEYS = ('decalage/distance', 'decalage/jonction', 'decalage/garder', 'decalage/dernier')


class FakeChecker:
    """Signale les mots de la liste."""

    def __init__(self, *bad):
        self.bad = bad

    def check(self, text):
        out = []
        for w in self.bad:
            at = text.find(w)
            if at >= 0:
                out.append(SP.Fault(at, len(w), w, ['corrigé']))
        return out


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


class Offset(Base):
    def tearDown(self):
        for k in OFFSET_KEYS:
            self.win.settings.remove(k)

    def shape(self, size=20.0):
        s = Shape(path=Path([geom.rect(0.0, 0.0, size, size)]))
        self.layer.items.append(s)
        return s

    def run_offset(self, *sel, distance=1.0, count=1, keep=False, last_only=False):
        self.win.canvas.select(list(sel))
        self.win.offset_selection({'distance': distance, 'join': 'miter', 'count': count, 'keep': keep, 'last_only': last_only})

    def test_all_the_offsets_by_default(self):
        s = self.shape()
        self.run_offset(s, count=3, keep=True)
        self.assertEqual(len(self.layer.items), 4)

    def test_only_the_farthest(self):
        s = self.shape()
        self.run_offset(s, count=3, keep=True, last_only=True)
        self.assertEqual(len(self.layer.items), 2)
        b = next(i for i in self.layer.items if i is not s).path.bbox()
        self.assertAlmostEqual(b[0], -3.0)
        self.assertAlmostEqual(b[2], 23.0)

    def test_setting_is_kept(self):
        s = self.shape()
        self.run_offset(s, last_only=True, keep=True)
        self.assertTrue(self.win.settings.value('decalage/dernier') in (True, 'true'))

    def test_nothing_computed_warns_and_keeps_the_shape(self):
        s = self.shape(2.0)
        n = len(self.win._undo)
        with mock.patch.object(QMessageBox, 'warning') as warn:
            self.run_offset(s, distance=-50.0)
        warn.assert_called_once()
        self.assertEqual(self.layer.items, [s])
        self.assertEqual(len(self.win._undo), n)

    def test_one_failure_among_others_stays(self):
        small, big = self.shape(2.0), self.shape(40.0)
        with mock.patch.object(QMessageBox, 'warning') as warn:
            self.run_offset(small, big, distance=-5.0)
        warn.assert_not_called()
        self.assertIn(small, self.layer.items)
        self.assertNotIn(big, self.layer.items)
        self.assertEqual(len(self.layer.items), 2)
        self.assertIn('1', self.win.statusBar().currentMessage())

    def test_dialog_values(self):
        d = OffsetDialog(None, 2.0, 'miter', True, True)
        self.assertTrue(d.values()['last_only'])
        d.last_only.setChecked(False)
        self.assertFalse(d.values()['last_only'])
        self.assertFalse(OffsetDialog(None).values()['last_only'])

    def test_dialog_path_uses_the_settings(self):
        s = self.shape()
        self.win.canvas.select([s])
        self.win.settings.setValue('decalage/dernier', True)
        with mock.patch.object(OffsetDialog, 'exec', return_value=False):
            self.win.offset_dialog()
        self.assertEqual(self.layer.items, [s])


class Dictionary(Base):
    def setUp(self):
        super().setUp()
        self.win.settings.remove(DICT)

    def tearDown(self):
        self.win.settings.remove(DICT)

    def text(self, s):
        t = Text(text=s, font='Arial', size=5.0)
        t.outline = TX.outline_for(t)
        self.layer.items.append(t)
        return t

    def test_add_stops_the_word_here_and_tells(self):
        added = []
        t1, t2 = self.text('un Mott ici'), self.text('encore Mott et Autre')
        s = SpellSession([t1, t2], FakeChecker('Mott', 'Autre'), lambda t, x: None, on_add=added.append)
        self.assertEqual(s.current_fault.word, 'Mott')
        s.add_word()
        self.assertEqual(added, ['Mott'])
        self.assertEqual(s.current_fault.word, 'Autre')

    def test_add_without_callback(self):
        t = self.text('un Mott ici')
        s = SpellSession([t], FakeChecker('Mott'), lambda t, x: None)
        s.add_word()
        self.assertTrue(s.finished())

    def test_words_are_kept_in_the_settings(self):
        self.assertEqual(self.win._spell_words(), set())
        self.win._spell_add_word('Mott')
        self.win._spell_add_word('Élan')
        self.win._spell_add_word('mott')
        self.assertEqual(self.win._spell_words(), {'mott', 'élan'})
        self.assertEqual(sorted(json.loads(self.win.settings.value(DICT))), ['mott', 'élan'])

    def test_broken_setting_is_empty(self):
        self.win.settings.setValue(DICT, '{pas du json')
        self.assertEqual(self.win._spell_words(), set())
        self.win.settings.setValue(DICT, '{"a": 1}')
        self.assertEqual(self.win._spell_words(), set())

    def test_a_kept_word_is_not_reported_next_time(self):
        t = self.text('un Mott ici')
        self.win._spell_add_word('Mott')
        s = SpellSession([t], FakeChecker('Mott'), lambda t, x: None, self.win._spell_words())
        self.assertTrue(s.finished())

    def test_button(self):
        added = []
        t1 = self.text('un Mott et Autre')
        s = SpellSession([t1], FakeChecker('Mott', 'Autre'), lambda t, x: None, on_add=added.append)
        d = SpellDialog(None, s)
        d.b_add.click()
        self.assertEqual(added, ['Mott'])
        self.assertEqual(s.current_fault.word, 'Autre')
        d.deleteLater()


class GlobalCompression(Base):
    def setUp(self):
        super().setUp()
        self.win.settings.remove('texte/compression_globale')
        self.t = Text(text='LONGUE LIGNE\nCOURT', font='Arial', size=5.0)
        self.t.outline = TX.outline_for(self.t)
        self.layer.items.append(self.t)
        self.win.canvas.select([self.t])
        self.width = TX.natural_width(self.t)

    def tearDown(self):
        self.win.settings.remove('texte/compression_globale')

    def test_natural_width_ignores_the_compression(self):
        self.assertGreater(self.width, 10.0)
        self.t.extra['max_length'] = {'length': 5.0, 'by': 'line'}
        self.assertAlmostEqual(TX.natural_width(self.t), self.width)

    def test_fits_in_the_percentage_with_the_same_factor(self):
        self.assertEqual(self.win.compress_global(50.0), 1)
        self.assertAlmostEqual(self.t.extra['max_length']['length'], self.width / 2)
        self.assertEqual(self.t.extra['max_length']['by'], 'paragraph')
        ratios = TX.compression(self.t)
        self.assertEqual(len(ratios), 2)
        self.assertAlmostEqual(ratios[0], ratios[1])
        self.assertLess(ratios[0], 1.0)
        w = self.t.outline.bbox()[2] - self.t.outline.bbox()[0]
        self.assertLess(w, self.width * 0.55)
        self.win.undo()

    def test_second_time_starts_from_the_full_length(self):
        self.win.compress_global(50.0)
        self.win.compress_global(80.0)
        self.assertAlmostEqual(self.t.extra['max_length']['length'], self.width * 0.8)

    def test_asks_and_remembers(self):
        with mock.patch.object(QInputDialog, 'getDouble', return_value=(70.0, True)):
            self.win.A['text_compress_global'].trigger()
        self.assertAlmostEqual(self.t.extra['max_length']['length'], self.width * 0.7)
        self.assertEqual(float(self.win.settings.value('texte/compression_globale')), 70.0)

    def test_cancel(self):
        with mock.patch.object(QInputDialog, 'getDouble', return_value=(70.0, False)):
            self.assertEqual(self.win.compress_global(), 0)
        self.assertNotIn('max_length', self.t.extra)

    def test_no_text(self):
        self.win.canvas.select([])
        with mock.patch.object(QInputDialog, 'getDouble') as ask:
            self.assertEqual(self.win.compress_global(), 0)
        ask.assert_not_called()

    def test_typeedit_command(self):
        self.assertEqual(S.TE_ACTIONS['ID_RAPIDO_LINE_BTNCOMPBYGLOBAL_DLL'], 'text_compress_global')
        self.assertEqual(S.TE_ACTIONS['ID_RAPIDO_LINE_BTNCOMPBYPARA_DLL'], 'text_compress_para')


if __name__ == '__main__':
    unittest.main()
