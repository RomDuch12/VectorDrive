"""Round 160 : vérification avant l'écriture du programme (TauDrive)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.cam import model, preflight as PF, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Plate, Shape, Text


def setup_doc(rects=((5, 5, 10, 10),), plate=True):
    d = Document()
    d.plate = Plate(50, 30) if plate else None
    for r in rects:
        d.add(Shape(path=geom.Path([geom.rect(*r)])))
    s = model.CamSetup()
    t = model.CamTool(name='F2', diameter=2, number=1, cut_length=10)
    s.tools = [t]
    s.operations = [model.Operation(name='Détourage', kind='contour', tool_id=t.id, depth=1.0)]
    return d, s


class TestInspect(unittest.TestCase):
    def test_clean(self):
        d, s = setup_doc()
        r = PF.inspect(d, s, S.compute_all(d, s))
        self.assertEqual(r.paths, 1)
        self.assertGreater(r.feed_mm, 40)
        self.assertGreater(r.duration_s, 0)
        self.assertEqual(r.tools, [(1, 'F2', 'fraise')])
        self.assertEqual(r.notes, [])
        self.assertIn('Rien de particulier', PF.summary_html(r))

    def test_notes(self):
        d, s = setup_doc(rects=((5, 5, 10, 10), (45, 5, 20, 10)))           # le second déborde de la plaque
        hidden = d.add(Shape(path=geom.Path([geom.rect(0, 0, 1, 1)])))
        hidden.visible = False
        d.add(Text(text='A', font='Police absente'))
        t2 = model.CamTool(name='V30', kind='conique', diameter=3, angle=30, number=1)
        s.tools.append(t2)
        s.operations.append(model.Operation(name='Gravure', kind='gravure', tool_id=t2.id, depth=0.1))
        s.operations.append(model.Operation(name='Vide', kind='gravure', tool_id=t2.id, depth=0.1,
                                            items=['inexistant']))
        s.operations.append(model.Operation(name='Off', kind='gravure', tool_id=t2.id, enabled=False))
        tps = S.compute_all(d, s)
        r = PF.inspect(d, s, tps, post_warnings=['export refusé — x'])
        texts = ' | '.join(t for _lv, t in r.notes)
        for frag in ('sort de la plaque', 'objet(s) masqué(s)', 'sans contour', 'T1 est appelé pour 2',
                     '« Vide » ne produit aucun parcours', 'désactivée', 'export refusé'):
            self.assertIn(frag, texts)
        self.assertEqual(r.notes[0][0], PF.BLOQUANT)                         # le plus grave d'abord
        self.assertEqual(r.disabled, 1)

    def test_empty_and_overflow_tolerance(self):
        d, s = setup_doc(rects=())
        r = PF.inspect(d, s, S.compute_all(d, s))
        self.assertEqual(r.blocking(), ['Aucun parcours à usiner : le programme serait vide.'])
        d, s = setup_doc(rects=((0, 0, 50, 30),))                             # détourage extérieur de la plaque
        r = PF.inspect(d, s, S.compute_all(d, s))
        self.assertFalse([t for _lv, t in r.notes if 'plaque' in t])          # dans le rayon de l'outil


class TestPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_dialog_and_setting(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            panel = w.cam_panel
            doc = w.canvas.doc
            _d, s = setup_doc()
            doc.add(Shape(path=geom.Path([geom.rect(5, 5, 10, 10)])))
            model.store(doc, s)
            w.settings.setValue('fao/verifier', True)
            self.assertTrue(panel.preflight(S.compute_all(doc, panel.setup()), exec_dialog=False))
            dlg = panel.last_preflight
            self.assertIn('Parcours', dlg.text.toPlainText())
            self.assertFalse(dlg.skip_next_time())
            w.settings.setValue('fao/verifier', False)
            panel.last_preflight = None
            self.assertTrue(panel.preflight([], exec_dialog=False))
            self.assertIsNone(panel.last_preflight)                           # désactivée : pas de fenêtre
            w.settings.setValue('fao/verifier', True)
        finally:
            w.modified = False
            w.close()

    def test_blocking_button(self):
        from vectordrive.ui.preflight_dialog import PreflightDialog
        from PySide6.QtWidgets import QDialogButtonBox
        r = PF.Report(notes=[(PF.BLOQUANT, 'x')])
        dlg = PreflightDialog(None, r)
        ok = dlg.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok)
        self.assertEqual(ok.text(), 'Écrire quand même')


if __name__ == '__main__':
    unittest.main()
