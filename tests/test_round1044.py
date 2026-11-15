"""Round 1044 : demande du 15/11 (20 h 35) « opération_form boutons OK Annuler colorés plus grands et en bas au centre
de la fenetre »."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1044.ini'))

from PySide6.QtWidgets import QApplication, QDialogButtonBox  # noqa: E402

from vectordrive.cam import model  # noqa: E402

app = QApplication.instance() or QApplication([])
OK, CANCEL = QDialogButtonBox.StandardButton.Ok, QDialogButtonBox.StandardButton.Cancel


class OpForm(unittest.TestCase):

    def form(self, obj=None, with_doc=True):
        from vectordrive.core.document import Document
        from vectordrive.ui.cam_panel import FieldsDialog
        obj = obj if obj is not None else model.Operation(kind='contour', sources=[0])
        dlg = FieldsDialog(None, 'Essai 1044', obj, Document() if with_doc else None, [])
        self.addCleanup(dlg.deleteLater)
        return dlg

    def box(self, dlg):
        box = getattr(dlg, 'ok_box', None)
        self.assertIsNotNone(box, 'avant : OK et Annuler mêlés aux autres boutons, à droite')
        return box

    def test_ok_and_cancel_alone_at_the_bottom_centre(self):
        dlg = self.form()
        box = self.box(dlg)
        lay = dlg.layout()
        self.assertIs(lay.itemAt(lay.count() - 1).widget(), box)            # tout en bas
        self.assertTrue(box.centerButtons())                                 # au centre
        self.assertEqual(sorted(int(box.standardButton(b).value) for b in box.buttons()),
                         sorted([int(OK.value), int(CANCEL.value)]))         # seuls
        self.assertIs(dlg.findChild(QDialogButtonBox), box)

    def test_the_other_buttons_on_the_row_above(self):
        dlg = self.form()
        acts = getattr(dlg, 'actions_box', None)
        self.assertIsNotNone(acts)
        lay = dlg.layout()
        self.assertEqual(lay.indexOf(acts), lay.indexOf(self.box(dlg)) - 1)
        for b in (dlg.full_button, dlg.fit_button, dlg.advise_button, dlg.rest_button):
            self.assertIsNotNone(b)
            self.assertIn(b, acts.buttons())
            self.assertNotIn(b, dlg.ok_box.buttons())

    def test_bigger_and_coloured(self):
        import importlib.util
        spec = importlib.util.find_spec("vectordrive.ui.okcancel")
        self.assertIsNotNone(spec, "avant : pas de module okcancel")
        from vectordrive.ui import okcancel
        dlg = self.form()
        box = self.box(dlg)
        dlg.resize(900, 700)
        dlg.show()
        app.processEvents()
        for which, colour in ((OK, okcancel.GREEN[0]), (CANCEL, okcancel.RED[0])):
            b = box.button(which)
            self.assertGreaterEqual(b.minimumWidth(), 150)
            self.assertGreaterEqual(b.minimumHeight(), 40)
            self.assertGreaterEqual(b.height(), 40)
            self.assertIn(colour, b.styleSheet())
            img = b.grab().toImage()
            c = img.pixelColor(8, img.height() // 2)                          # fond du bouton, hors du texte
            if which == OK:
                self.assertGreater(c.green(), c.red() + 40, c.name())        # vert
            else:
                self.assertGreater(c.red(), c.green() + 60, c.name())        # rouge
        mid = box.mapTo(dlg, box.rect().center()).x()                       # la boîte au centre de la fenêtre
        self.assertLess(abs(mid - dlg.width() // 2), dlg.width() // 10)
        ok, cancel = box.button(OK), box.button(CANCEL)
        pair = (min(ok.mapTo(dlg, ok.rect().topLeft()).x(), cancel.mapTo(dlg, cancel.rect().topLeft()).x()),
                max(ok.mapTo(dlg, ok.rect().topRight()).x(), cancel.mapTo(dlg, cancel.rect().topRight()).x()))
        self.assertLess(abs((pair[0] + pair[1]) // 2 - dlg.width() // 2), 40)   # les deux boutons centrés
        dlg.reject()

    def test_ok_and_cancel_still_work(self):
        tool_form = self.form(model.CamTool(name='F 1044'), with_doc=False)
        done = []
        tool_form.finished.connect(done.append)
        self.box(tool_form).button(OK).click()                              # fiche d'un outil : même fenêtre
        self.assertEqual(done, [1])
        op = self.form()
        shut = []
        op.finished.connect(shut.append)
        op.ok_box.button(OK).click()                                         # opération sans outil : refusée
        self.assertEqual(shut, [])
        op.ok_box.button(CANCEL).click()
        self.assertEqual(shut, [0])


if __name__ == '__main__':
    unittest.main()
