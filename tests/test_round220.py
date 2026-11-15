"""Round 220 : les fenêtres de dialogue sont libérées une fois finies (elles
restaient en vie avec tous leurs widgets, des milliers en une journée) ;
une fenêtre réemployée (vérification du dessin) est gardée."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

app = QApplication.instance() or QApplication([])


def dialogs():
    return [d for d in app.allWidgets() if isinstance(d, QDialog)]


class TestRelease(unittest.TestCase):
    def test_dialogs_freed_after_use(self):
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        w.show()
        sh = Shape(path=geom.Path([geom.rect(0, 0, 20, 10)]), tool=0)
        w.canvas.doc.add(sh)
        w.canvas.select([sh])
        before = len(app.allWidgets())
        from vectordrive.cam import model
        from vectordrive.ui.cam_panel import FieldsDialog
        for _ in range(3):                                                   # formulaires montrés puis finis (sans boucle modale)
            p = w.cam_panel
            s = p.setup()
            o = model.Operation(name='Gravure', kind='gravure', tool_id=p._tool_for(s, 'conique').id)
            d = FieldsDialog(p, 'Nouveau parcours', o, w.canvas.doc, s.tools, library=p.library_tools(), selection=[])
            d.show()
            d.accept()
            d2 = w.options_dialog(exec_dialog=False)
            d2.show()
            d2.reject()
        QTest.qWait(20)
        self.assertEqual(dialogs(), [])                                      # toutes détruites
        self.assertLess(len(app.allWidgets()), before + 200)                 # pas d'accumulation
        d = w.options_dialog(exec_dialog=False)                              # montrée sans exec : idem à la fermeture
        d.show()
        self.assertIn(d, dialogs())
        d.close()
        QTest.qWait(20)
        self.assertEqual(dialogs(), [])
        w.check_drawing()                                                    # réemployée : gardée
        dlg = w._check_dlg
        dlg.close()
        QTest.qWait(20)
        self.assertIs(w._check_dlg, dlg)
        w.check_drawing()                                                    # rouverte sans erreur
        self.assertTrue(dlg.isVisible())
        dlg.close()
        w.modified = False
        w.close()

    def test_release_opt_out(self):
        from vectordrive.ui.fit import release

        class Kept(QDialog):
            vd_keep = True
        k = Kept()
        release(k)
        k.show()
        k.accept()
        QTest.qWait(20)
        self.assertIn(k, dialogs())
        k.deleteLater()
        d = QDialog()
        release(d)
        d.show()
        d.reject()
        QTest.qWait(20)
        self.assertNotIn(d, dialogs())


if __name__ == '__main__':
    unittest.main()
