"""Round 916 : préréglages de texte sûrs. Un préréglage importé (ou déjà enregistré) aux valeurs illisibles ne bloque
plus ni le gestionnaire ni le démarrage, et ne garde que les champs de mise en forme (il ne change jamais le contenu
d'un texte) ; l'interligne donné remplace le mode d'interligne ; un préréglage qui ne change rien ne fait pas d'étape
d'annulation ; un nouveau texte garde les valeurs du préréglage hors des bornes de la fenêtre Texte ; importer le
préréglage des nouveaux textes les met à jour ; exporter là où c'est impossible le dit."""
import json
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r916.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from vectordrive.core.document import Text  # noqa: E402
from vectordrive.ui import text_presets as TP  # noqa: E402

KEYS = ('texte/styles', 'texte/format', 'texte/preset', 'texte/style_courant', 'texte/hauteur', 'texte/police')
BAD = {'A': {'attrs': {'size': None, 'font': 5, 'text': 'PIRATE', 'align': 'diagonale', 'line_spacing': 'deux'},
             'extra': {'italic': 'abc', 'line_mode': 'x', 'underline': 'oui', 'max_length': {'length': 'long'}}},
       'B': {'attrs': {'size': '5 mm', 'width_ratio': float('nan'), 'spacing': True}}}


class Base(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.new_document()
        for k in KEYS:
            self.w.settings.remove(k)

    def tearDown(self):
        for k in KEYS:
            self.w.settings.remove(k)
        self.w.modified = False
        self.w.close()

    def put(self, text='Abc', size=5.0, font='VD Trait'):
        from vectordrive.core import text as TX
        t = Text(text=text, font=font, size=size)
        t.outline = TX.outline_for(t)
        self.w.canvas.doc.layers[0].items.append(t)
        self.w.canvas.select([t])
        self.w._on_selection()
        return t

    def import_presets(self, presets: dict) -> int:
        path = os.path.join(tempfile.mkdtemp(), 'p.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({'prereglages': presets}, f)
        dlg = TP.PresetsDialog(self.w)
        try:
            return dlg.import_file(path)
        finally:
            dlg.close()


class Robust(Base):

    def test_bad_import_neither_breaks_the_manager_nor_the_start(self):
        self.assertEqual(self.import_presets(BAD), 2)
        got = TP.load(self.w.settings)
        self.assertEqual(got['A'], {'attrs': {}, 'extra': {}})                 # valeurs illisibles écartées
        self.assertEqual(got['B'], {'attrs': {}, 'extra': {}})
        self.assertEqual(TP.values(got['B'])['size'], 5.0)
        dlg = TP.PresetsDialog(self.w)                                          # le gestionnaire s'ouvre
        dlg.close()
        from vectordrive.ui.main_window import MainWindow
        w2 = MainWindow()                                                       # et VectorDrive démarre
        w2.modified = False
        w2.close()

    def test_a_bad_preset_already_saved_is_read_safely(self):
        self.w.settings.setValue(TP.KEY, json.dumps({'A': {'attrs': {'size': None, 'font': 'VD Trait'}}}))
        self.assertEqual(TP.load(self.w.settings)['A'], {'attrs': {'font': 'VD Trait'}, 'extra': {}})
        self.w.settings.setValue(TP.FORMAT_KEY, json.dumps({'attrs': {'size': 'x', 'text': 'PIRATE'}}))
        fmt = TP.new_text_format(self.w.settings)
        self.assertNotIn('text', fmt['attrs'])
        self.assertEqual(fmt['attrs']['size'], TP.base_format(self.w.settings)['attrs']['size'])
        self.w.refresh_text_bars()

    def test_a_preset_never_changes_the_content_of_a_text(self):
        t = self.put()
        TP.save(self.w.settings, {'P': {'attrs': {'font': 'VD Trait', 'size': 7.0, 'text': 'PIRATE'}, 'extra': {}}})
        self.assertEqual(self.w.use_text_preset('P'), 1)
        self.assertEqual((t.text, t.size), ('Abc', 7.0))

    def test_formatting_fields_kept_as_they_are_the_rest_dropped(self):
        fmt = {'attrs': {'font': 'VD Trait', 'size': 4.5, 'width_ratio': 0.9, 'spacing': -0.2, 'line_spacing': 1.5,
                         'align': 'center'},
               'extra': {'italic': 12.0, 'spacing_mode': 'tight', 'underline': {'pos': 10.0, 'thick': 5.0},
                         'small_caps': True, 'rtl': True, 'baseline': {'side': 'under', 'offset': 5.0},
                         'max_length': {'length': 40.0, 'by': 'line'}, 'line_mode': {'mode': 'fixed', 'value': 8.0}}}
        junk = {'attrs': dict(fmt['attrs'], matrix=[1, 0, 0, 1, 50, 50], text='PIRATE'),
                'extra': dict(fmt['extra'], fit={'width': 3.0}, box=[0, 0, 1, 1])}
        self.assertEqual(TP.norm(fmt), fmt)
        self.assertEqual(TP.norm(junk), fmt)
        self.assertEqual(self.import_presets({'P': junk}), 1)
        self.assertEqual(TP.load(self.w.settings)['P'], fmt)


class Behaviour(Base):

    def test_line_spacing_replaces_the_line_mode(self):
        fmt = {'attrs': {'line_spacing': 2.0}, 'extra': {'line_mode': {'mode': 'fixed', 'value': 10.0}}}
        new = TP.with_value(fmt, 'line_spacing', 3.0)
        self.assertNotIn('line_mode', new['extra'])
        self.assertEqual(new['attrs']['line_spacing'], 3.0)

    def test_a_preset_that_changes_nothing_records_no_undo(self):
        self.put()
        self.w.modified = False
        TP.save(self.w.settings, {'P': {'attrs': {'font': 'VD Trait'}, 'extra': {}}})
        undo = len(self.w._undo)
        self.assertEqual(self.w.use_text_preset('P'), 0)
        self.assertEqual(len(self.w._undo), undo)
        self.assertFalse(self.w.modified)

    def test_new_text_keeps_preset_values_the_text_window_cannot_show(self):
        fmt = {'attrs': {'font': 'VD Trait', 'size': 4.0, 'line_spacing': 6.0}, 'extra': {}}
        TP.save(self.w.settings, {'P': fmt})
        TP.set_new_text_format(self.w.settings, fmt, 'P')

        self.w.new_text(0.0, 0.0)                        # round 922 : le texte s'écrit dans le dessin
        self.w.canvas.tool_obj.insert('AB\nCD')
        self.w.canvas.tool_obj.finish()
        t = self.w.canvas.doc.layers[0].items[-1]
        self.assertEqual((t.text, t.font, t.line_spacing), ('AB\nCD', 'VD Trait', 6.0))   # pas 5 (borne de la fenêtre)
        self.assertEqual(str(self.w.settings.value(TP.CURRENT, '')), 'P')                 # toujours le préréglage P
        self.assertEqual(TP.new_text_format(self.w.settings)['attrs']['line_spacing'], 6.0)

    def test_importing_the_preset_of_new_texts_updates_them(self):
        TP.save(self.w.settings, {'P': {'attrs': {'font': 'VD Trait', 'size': 5.0}, 'extra': {}}})
        TP.set_new_text_format(self.w.settings, TP.load(self.w.settings)['P'], 'P')
        self.assertEqual(self.import_presets({'P': {'attrs': {'font': 'VD Trait', 'size': 8.0}}}), 1)
        self.assertEqual(TP.new_text_format(self.w.settings)['attrs']['size'], 8.0)

    def test_export_where_it_is_impossible_says_so(self):
        dlg = TP.PresetsDialog(self.w)
        bad = os.path.join(tempfile.mkdtemp(), 'absent', 'p.json')
        with mock.patch.object(TP.QMessageBox, 'warning') as warn:
            self.assertEqual(dlg.export_file(bad), 0)
        warn.assert_called_once()
        dlg.close()


if __name__ == '__main__':
    unittest.main()
