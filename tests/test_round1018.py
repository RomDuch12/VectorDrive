"""Round 1018 : demande du 14/11, 19 h 45 — « Prise en charge, si existante, de la vitesse avance finition de l'outil
lors des passes de finition ; pour toute opé : à côté du cadre avances roughing, cadre Finishing (modifiable aussi
avec sauve possible dans la fiche outil et historique changements dans fiche outil) ; user clique sur un cadre ou
l'autre (ce qui l'active avec surbrillance) »."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1018.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QFocusEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.cam import model, timing, toollib  # noqa: E402
from vectordrive.i18n import tr  # noqa: E402


class Settings(dict):
    def value(self, k, d=None):
        return self.get(k, d)

    def setValue(self, k, v):                                                # noqa: N802
        self[k] = v


class Feeds(unittest.TestCase):

    def test_feed_of_the_active_frame(self):
        tool = model.CamTool(name='F 1018', feed=1000.0, finish_feed=400.0)
        op = model.Operation(kind='contour', tool_id=tool.id)
        self.assertEqual(op.feed_frame, 'ebauche')                            # avant : pas de cadre
        self.assertEqual(model.op_feed(op, tool), 1000.0)
        op.feed_frame = 'finition'
        self.assertEqual(model.op_feed(op, tool), 400.0)                      # l'avance de finition de l'outil
        op.finish_feed = 300.0
        self.assertEqual(model.op_feed(op, tool), 300.0)                      # celle de l'opération
        op.finish_feed, tool.finish_feed, op.feed = 0.0, 0.0, 800.0
        self.assertEqual(model.op_feed(op, tool), 800.0)                      # sans finition : celle d'ébauche
        from vectordrive.cam import strategies
        tool.finish_feed = 400.0
        self.assertEqual(strategies._feeds(op, tool)[0], 400.0)
        again = model.Operation.from_dict(op.to_dict())
        self.assertEqual((again.feed_frame, again.finish_feed), ('finition', 0.0))
        model.note_change(tool, 'feed', 1000.0, 1100.0, 'essai')
        t2 = model.CamTool.from_dict(tool.to_dict())
        self.assertEqual((t2.finish_feed, t2.history[-1]['champ'], t2.history[-1]['apres']), (400.0, 'feed', 1100.0))

    def test_duration_follows_the_frame(self):
        tool = model.CamTool(name='F 1018', feed=1000.0, finish_feed=400.0)
        op = model.Operation(kind='contour', tool_id=tool.id)
        setup = model.CamSetup(tools=[tool], operations=[op])
        tp = model.Toolpath(op.id, tool.id, moves=[model.Move('rapid', 0.0, 0.0, -1.0),
                                                   model.Move('feed', 100.0, 0.0, -1.0)])
        spec = timing.TimingSpec(accel=0.0)
        self.assertAlmostEqual(timing.path_seconds(tp, setup, spec), 6.0)     # 100 mm à 1000 mm/min
        op.feed_frame = 'finition'
        self.assertAlmostEqual(timing.path_seconds(tp, setup, spec), 15.0)    # à 400 mm/min

    def test_history_kept_and_listed(self):
        tool = model.CamTool(name='F 1018')
        for k in range(60):
            model.note_change(tool, 'spindle', k, k + 1, 'essai')
        self.assertEqual(len(tool.history), 50)                               # les 50 derniers
        self.assertEqual(tool.history[-1]['apres'], 60.0)
        lines = model.history_lines(tool, {'spindle': 'Broche'})
        self.assertIn('Broche : 59 → 60 (essai)', lines[0])                   # le plus récent d'abord
        from vectordrive.cam import templates as TPL
        op = model.Operation(kind='contour', tool_id=tool.id)
        self.assertNotIn('history', TPL.single(op, tool, 'M 1018')['tools'][0])   # propre au poste : pas aux modèles
        setup = model.CamSetup(tools=[tool], operations=[op])
        self.assertNotIn('history', TPL.from_setup(setup, 'M 1018')['tools'][0])


class Form(unittest.TestCase):

    def setUp(self):
        self.tool = model.CamTool(name='F 1018', feed=900.0, number=3)

    def open(self, **kw):
        from vectordrive.ui import cam_panel as CP
        op = model.Operation(kind=kw.pop('kind', 'contour'), tool_id=self.tool.id, name='Op 1018', **kw)
        d = CP.FieldsDialog(None, 'essai', op, tools=[self.tool])
        self.addCleanup(d.deleteLater)
        return d

    def test_two_frames_one_click_activates(self):
        d = self.open(feed_frame='finition')
        fr = d.feed_frames                                                    # avant : pas de cadres
        self.assertEqual((fr['ebauche'].objectName(), fr['finition'].objectName()), ('cadre_ebauche', 'cadre_finition'))
        self.assertIs(d.widgets['feed'].parentWidget(), fr['ebauche'])
        self.assertIs(d.widgets['finish_feed'].parentWidget(), fr['finition'])
        self.assertEqual(d.feed_frame(), 'finition')
        self.assertTrue(fr['finition'].property('vd_active'))
        self.assertIn('highlight', fr['finition'].styleSheet())               # en surbrillance
        self.assertNotIn('highlight', fr['ebauche'].styleSheet())
        d.show()
        app.processEvents()
        QTest.mouseClick(fr['ebauche'], Qt.MouseButton.LeftButton)            # un clic sur le cadre Ébauche
        self.assertEqual(d.feed_frame(), 'ebauche')
        self.assertTrue(fr['ebauche'].property('vd_active'))
        w = d.widgets['finish_feed']
        QApplication.sendEvent(w, QFocusEvent(QEvent.Type.FocusIn, Qt.FocusReason.OtherFocusReason))
        self.assertEqual(d.feed_frame(), 'ebauche')                           # le focus d'ouverture : rien
        QApplication.sendEvent(w, QFocusEvent(QEvent.Type.FocusIn, Qt.FocusReason.TabFocusReason))
        self.assertEqual(d.feed_frame(), 'ebauche')                           # Tab vers le champ suivant : rien
        QTest.mouseClick(w.lineEdit(), Qt.MouseButton.LeftButton)             # un clic dans le texte du champ
        self.assertEqual(d.feed_frame(), 'finition')
        d.apply()
        self.assertEqual(d.obj.feed_frame, 'finition')
        d.close()

    def test_saved_in_the_tool_sheet_with_history(self):
        d = self.open()
        w = d.widgets['finish_feed']
        self.assertIn('900 mm/min', w.specialValueText())                     # l'outil n'en a pas : celle d'ébauche
        d.widgets['feed'].setValue(700.0)
        self.assertIn('700 mm/min', w.specialValueText())                     # celle d'ébauche de l'opération
        d.widgets['feed'].setValue(0.0)
        self.assertTrue(d.feed_save_buttons['finition'].isEnabled())          # outil du document
        d._sync_feed_buttons(model.CamTool(name='Mes outils 1018'))
        self.assertFalse(d.feed_save_buttons['finition'].isEnabled())         # Mes outils : Choisir un outil
        d._sync_feed_buttons(self.tool)
        w.setValue(450.0)
        self.assertEqual(d.save_feeds_to_tool('finition'), ['finish_feed'])
        self.assertEqual(self.tool.finish_feed, 450.0)                        # dans la fiche de l'outil
        self.assertEqual(w.value(), 0.0)                                      # l'opération suit l'outil
        self.assertIn('450', w.specialValueText())
        h = self.tool.history[-1]
        self.assertEqual((h['champ'], h['avant'], h['apres'], h['source']), ('finish_feed', 0.0, 450.0, 'Op 1018'))
        d.widgets['feed'].setValue(1200.0)
        d.save_feeds_to_tool('ebauche')
        self.assertEqual(self.tool.feed, 1200.0)
        dlg = d.feed_history(exec_dialog=False)
        self.addCleanup(dlg.deleteLater)
        text = dlg.history_text.toPlainText().splitlines()
        self.assertEqual(len(text), 2)
        self.assertIn('900 → 1200', text[0])                                  # le plus récent d'abord
        self.assertIn('0 → 450', text[1])

    def test_instruction_has_no_frames(self):
        d = self.open(kind='instruction')
        self.assertTrue(d.feed_box.isHidden())

    def test_tool_form_records_history(self):
        from vectordrive.ui import cam_panel as CP
        d = CP.FieldsDialog(None, 'outil', self.tool)
        self.addCleanup(d.deleteLater)
        self.assertIn('finish_feed', d.widgets)
        d.widgets['feed'].setValue(1300.0)
        d.widgets['finish_feed'].setValue(500.0)
        d.apply()
        self.assertEqual((self.tool.feed, self.tool.finish_feed), (1300.0, 500.0))
        got = {h['champ']: (h['avant'], h['apres'], h['source']) for h in self.tool.history}
        self.assertEqual(got, {'feed': (900.0, 1300.0, tr('formulaire de l’outil')),
                               'finish_feed': (0.0, 500.0, tr('formulaire de l’outil'))})


class Sheet(unittest.TestCase):

    def setUp(self):
        self._env = os.environ.get('VECTORDRIVE_TOOLS')
        self.path = os.path.join(tempfile.mkdtemp(), 'tools.json')
        os.environ['VECTORDRIVE_TOOLS'] = self.path
        self.mine = model.CamTool(name='Mine 1018', diameter=2.0, number=8, feed=500.0)
        toollib.save([self.mine], self.path)
        self.doc_tool = model.CamTool(name='Doc 1018', diameter=1.0, number=6, feed=700.0)

    def tearDown(self):
        if self._env is None:
            os.environ.pop('VECTORDRIVE_TOOLS', None)
        else:
            os.environ['VECTORDRIVE_TOOLS'] = self._env

    def test_finishing_feed_in_sheet_column_and_library(self):
        from vectordrive.ui import tool_columns as TC
        from vectordrive.ui.tool_picker import ToolPickerDialog
        from vectordrive.ui.toollib_dialog import ToolLibraryDialog
        self.assertIn('finish_feed', TC.KEYS)                                 # une colonne
        self.assertIn('finish_feed', dict(ToolLibraryDialog.NUM))             # la bibliothèque d'outils
        lib = {self.mine.id: model.CamTool.from_dict(self.mine.to_dict())}
        dlg = ToolPickerDialog(None, [self.doc_tool], lib, settings=Settings())
        self.addCleanup(dlg.deleteLater)
        it = next(i for i in dlg._items() if i.data(0, Qt.ItemDataRole.UserRole) and 'Doc 1018' in i.text(0))
        dlg.tree.setCurrentItem(it)
        sheet = dlg.sheet
        self.assertFalse(sheet.history_btn.isEnabled())                       # pas encore d'historique
        sheet.w['finish_feed'].setValue(350.0)
        sheet.w['feed'].setValue(750.0)
        self.assertTrue(sheet.save())
        self.assertEqual((self.doc_tool.feed, self.doc_tool.finish_feed), (750.0, 350.0))
        self.assertEqual(sorted(h['champ'] for h in self.doc_tool.history), ['feed', 'finish_feed'])
        self.assertEqual(self.doc_tool.history[0]['source'], tr('fiche de l’outil'))
        self.assertTrue(sheet.history_btn.isEnabled())


if __name__ == '__main__':
    unittest.main()
