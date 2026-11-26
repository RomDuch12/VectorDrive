"""Round 1179+1 (suite de l'électroérosion à fil, demande du 26/11) : l'interface — la stratégie dans la liste des
opérations, son formulaire sans outil (réglages du fil, contours haut et bas pris sur la sélection), la fenêtre des
chutes à risque et ses propositions (incliner le fil, laisser une attache)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1179.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

from vectordrive.cam import model  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Plate, Shape  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : pas d\'électroérosion à fil dans la liste des opérations'


def square(x, y, w, h):
    return Shape(path=geom.Path([geom.polyline([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], closed=True)]))


class Window(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def setUp(self):
        self.assertIn('fil_edm', model.op_kinds(), BEFORE)
        doc = self.w.canvas.doc
        doc.plate = Plate(width=100.0, height=50.0, thickness=10.0)
        for L in doc.layers:
            L.items.clear()
        self.items = [square(40, 15, 20, 20), square(41, 16, 18, 18)]
        doc.layers[0].items.append(self.items[0])
        self.cp = self.w.cam_panel
        box = getattr(self.cp, 'chutes_box', None)
        if box is not None:
            from shiboken6 import isValid
            if isValid(box):
                box.close()
        self.cp.chutes_box = None

    def form(self, op, selection=()):
        from vectordrive.ui.cam_panel import FieldsDialog
        return FieldsDialog(self.cp, None, op, self.w.canvas.doc, [], selection=list(selection), kind_choice=True)

    def test_form_without_tool_with_the_wire_settings(self):
        from vectordrive.cam import wire_edm as W
        op = model.Operation(kind='fil_edm', tool_id='')
        dlg = self.form(op)
        try:
            for n in ('tool_id', 'depth', 'feed'):
                if n in dlg.rows:
                    self.assertTrue(dlg.rows[n][1].isHidden(), n)
            self.assertFalse(dlg.rows['side'][1].isHidden())
            self.assertEqual(set(dlg.param_widgets), {f[0] for f in W.FORM_FIELDS})
            dlg.param_widgets['fil'].setValue(0.2)
            self.assertTrue(dlg.accept_checked())                      # pas d'outil demandé
            dlg.apply()
            self.assertEqual(W.params_of(op)['fil'], 0.2)
            self.assertEqual(op.params['compensation'], W.CHOICE_LABELS['compensation']['g41'])
        finally:
            dlg.close()

    def test_upper_and_lower_contours_taken_from_the_selection(self):
        from vectordrive.cam import wire_edm as W
        op = model.Operation(kind='fil_edm')
        dlg = self.form(op, self.items)
        try:
            self.assertTrue(dlg.pick_button.isEnabled())
            dlg.pick_button.click()
            dlg.apply()
            p = W.params_of(op)
            self.assertEqual((p['bas'], p['haut'], p['inclinaison']), (self.items[0].id, self.items[1].id, 'haut_bas'))
        finally:
            dlg.close()

    def test_upper_and_lower_sorted_by_their_names(self):
        from vectordrive.cam import wire_edm as W
        top, bottom = self.items[1], self.items[0]
        top.name, bottom.name = 'Contour dessus', 'Contour dessous'
        op = model.Operation(kind='fil_edm')
        dlg = self.form(op, [top, bottom])                             # cadre : l'ordre du dessin, inversé
        try:
            dlg.pick_button.click()
            dlg.apply()
            p = W.params_of(op)
            self.assertEqual((p['bas'], p['haut']), (bottom.id, top.id))
        finally:
            dlg.close()
            top.name = bottom.name = ''
        self.assertIn('ordre du dessin', W.FORM_NOTE)                  # sans nom parlant : le dire

    def compute(self, **params):
        op = model.Operation(name='Fil', kind='fil_edm', side='interieur', params=params)
        model.store(self.w.canvas.doc, model.CamSetup(operations=[op]))
        self.cp.compute()
        return op

    def test_risky_slug_told_once_with_both_proposals(self):
        self.compute()
        box = self.cp.chutes_box
        self.assertIsNotNone(box)
        self.assertTrue(box.isVisible())
        self.assertFalse(box.isModal())
        self.assertEqual(sorted(b[0] for b in box.buttons), ['tab', 'taper'])
        self.assertIn('G52', next(b[3].text() for b in box.buttons if b[0] == 'taper'))
        self.assertIsNone(self.cp.announce_chutes())                    # une fois par calcul
        self.assertIsNone(getattr(self.cp, 'zones_box', None))          # pas « Îles gardées »

    def test_tab_proposal_applied_and_recomputed(self):
        from vectordrive.cam import wire_edm as W
        op = self.compute()
        box = self.cp.chutes_box
        btn = next(b[3] for b in box.buttons if b[0] == 'tab')
        btn.click()
        s = self.cp.setup()
        done = next(o for o in s.operations if o.id == op.id)
        self.assertEqual(len(W.params_of(done)['attaches']), 1)
        tp = next(t for t in self.cp.toolpaths if t.op_id == op.id)
        ch = next(c for c in tp.cycles if c.get('kind') == 'fil_edm')['chutes']
        self.assertEqual([(c['attache'], c['risque']) for c in ch], [(True, 'faible')])

    def test_taper_proposal_applied_and_recomputed(self):
        from vectordrive.cam import wire_edm as W
        op = self.compute()
        btn = next(b[3] for b in self.cp.chutes_box.buttons if b[0] == 'taper')
        btn.click()
        done = next(o for o in self.cp.setup().operations if o.id == op.id)
        p = W.params_of(done)
        self.assertEqual(p['inclinaison'], 'constante')
        self.assertLess(p['angle'], 0)
        tp = next(t for t in self.cp.toolpaths if t.op_id == op.id)
        self.assertEqual(tp.zones, [])


if __name__ == '__main__':
    unittest.main()
