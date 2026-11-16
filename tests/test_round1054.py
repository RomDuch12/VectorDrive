"""Round 1054 : demande du 15/11, 20 h 55 (deuxième partie) — le programme machine « fenetre centrale à la place du
dessin, rempli l'espace entre les 2 colonnes gauche et droite »."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1054.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QItemSelectionModel  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from tests import _posts  # noqa: E402

app = QApplication.instance() or QApplication([])


def named(toolpaths, setup, *, title: str = '', machine=None, stem: str = 'programme', box_mm=None):
    from vectordrive.cam.post import PostResult
    lines = ['%']
    for k, tp in enumerate(toolpaths):
        lines.append(f'N{10 * (k + 1)} T{k + 1} M6 ({tp.name})')
        for m in tp.moves:
            lines.append(f'G1 X{m.x:.3f} Y{m.y:.3f} Z{m.z:.3f}')
    lines.append('M30')
    return PostResult('\n'.join(lines) + '\n', [], '.nc', 'utf-8')


def spin(n=6):
    for _ in range(n):
        app.processEvents()


class InTheCentre(unittest.TestCase):

    def setUp(self):
        from vectordrive.cam import model
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        from vectordrive.ui.main_window import MainWindow
        self.posts = _posts.registered('essai', named)
        self.posts.__enter__()
        self.addCleanup(self.posts.__exit__, None, None, None)
        self.w = MainWindow()
        self.w.resize(1500, 900)
        self.w.show()
        spin()
        self.addCleanup(self.close)
        self.p, self.prog = self.w.cam_panel, self.w.program_panel
        doc = self.w.canvas.doc
        ids = []
        for r in ((0, 0, 20, 14), (30, 0, 12, 8)):
            sh = Shape(path=geom.Path([geom.rect(*r)]), tool=0)
            doc.add(sh)
            ids.append(sh.id)
        s = self.p.setup()
        tool = model.CamTool(name='Cyl 2', diameter=2.0, number=1, cut_length=7, step_down=1.0, spindle=20000)
        s.tools = [tool]
        s.post = 'essai'
        s.operations = [model.Operation(name=n, kind='gravure', tool_id=tool.id, items=[i], depth=0.2)
                        for n, i in zip(('Plaque avant', 'Contour arriere'), ids)]
        self.p._fill_posts()
        self.p.save(s)
        self.p.compute()
        self.center = getattr(self.w, 'program_center', None)
        self.assertIsNotNone(self.center, 'avant : le programme ne se met pas à la place du dessin')

    def close(self):
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()

    def test_takes_the_place_of_the_drawing(self):
        w = self.w
        w.show_program()
        spin()
        dock = w.dock_program
        self.assertFalse(dock.isHidden())
        self.assertTrue(self.center(True))
        spin()
        self.assertTrue(w.program_centered())
        self.assertIs(w.stage.currentWidget(), self.prog.parentWidget())    # dans le plan de travail
        self.assertTrue(dock.isHidden())                                     # sa fenêtre : fermée pendant ce temps
        self.assertFalse(w.canvas.isVisible())                               # à la place du dessin
        self.assertTrue(self.prog.isVisible())
        self.assertGreater(self.prog.width(), w.stage.width() - 20)         # tout l'espace entre les colonnes
        self.assertIn('(Plaque avant)', self.prog.text.toPlainText())
        self.assertTrue(self.prog.buttons['center'].isChecked())

    def test_back_in_its_window(self):
        w = self.w
        w.show_program()
        spin()
        self.center(True)
        spin()
        self.assertFalse(self.center(False))
        spin()
        self.assertFalse(w.program_centered())
        self.assertEqual(w.stage.currentIndex(), 0)                         # le dessin revenu
        self.assertTrue(w.canvas.isVisible())
        self.assertIs(w.dock_program.widget(), self.prog)
        self.assertFalse(w.dock_program.isHidden())                         # comme avant
        self.assertFalse(self.prog.buttons['center'].isChecked())

    def test_the_button_and_the_view_switch(self):
        w = self.w
        self.prog.buttons['center'].click()                                  # ▣, sans l'avoir ouvert avant
        spin()
        self.assertTrue(w.program_centered())
        self.assertTrue(w.dock_program.isHidden())
        w.show_program()                                                     # « Programme » : il y est déjà
        spin()
        self.assertTrue(w.program_centered())
        w.set_view_mode('2d')                                                # revenir au dessin : il rentre chez lui
        spin()
        self.assertFalse(w.program_centered())
        self.assertTrue(w.canvas.isVisible())
        self.assertTrue(w.dock_program.isHidden())                          # il n'était pas ouvert avant : refermé

    def test_never_an_empty_window(self):
        w = self.w
        self.center(True)
        spin()
        w.dock_program.setVisible(True)                                      # montrée d'ailleurs (fenêtre de colonne…)
        spin()
        self.assertFalse(w.program_centered())                               # le programme y est retourné
        self.assertIs(w.dock_program.widget(), self.prog)
        self.assertTrue(w.canvas.isVisible())

    def test_the_cad_tab_gives_the_drawing_back(self):
        w = self.w
        self.center(True)
        spin()
        self.assertEqual(w.view_mode(), '2d')
        r = w.ribbon
        cad = next(k for k in range(r.count()) if r.page(k) is not None and r.page(k).property('vd_cad') == '2d')
        w._ribbon_tab_clicked(cad)
        spin()
        self.assertFalse(w.program_centered())
        self.assertTrue(w.canvas.isVisible())

    def test_follows_the_chosen_operation_there_too(self):
        self.center(True)
        spin()
        m = self.p.ops.selectionModel()
        m.select(self.p.ops.model().index(1, 0),
                 QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
        spin()
        line = self.prog.follow_op()
        self.assertGreaterEqual(line, 0)
        self.assertIn('(Contour arriere)', self.prog.text.toPlainText().split('\n')[line])


if __name__ == '__main__':
    unittest.main()
