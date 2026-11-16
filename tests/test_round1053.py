"""Round 1053 : demande du 15/11, 20 h 55 (première partie) — dans la fenêtre du programme machine : « numérotation
lignes, repliage blocs et sequences, et surlignage (plutot discret) de la partie concernée par ce que fait user dans
les autres colonnes »."""
import importlib.util
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1053.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QItemSelectionModel  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from tests import _posts  # noqa: E402

app = QApplication.instance() or QApplication([])

PROGRAM = '\n'.join([
    'module Essai',                 # 0
    'program Main',                 # 1
    '  ; Gravure',                  # 2
    '  Line 1',                     # 3
    '  Line 2',                     # 4
    '  ; Detourage',                # 5
    '  if Fini',                    # 6
    '    Line 3',                   # 7
    '    Line 4',                   # 8
    '  endif',                      # 9
    'endprogram',                   # 10
    'endmodule',                    # 11
])


def view_module():
    spec = importlib.util.find_spec('vectordrive.ui.code_view')
    return spec


def shown_lines(view):
    doc = view.document()
    return [b for b in range(doc.blockCount()) if doc.findBlockByNumber(b).isVisible()]


class Folding(unittest.TestCase):

    def view(self, text=PROGRAM, sections=()):
        self.assertIsNotNone(view_module(), 'avant : le programme est un simple texte, sans marge ni blocs')
        from vectordrive.ui.code_view import CodeView
        v = CodeView()
        v.resize(500, 400)
        v.set_program(text, sections)
        v.show()
        app.processEvents()
        self.addCleanup(v.deleteLater)
        return v

    def test_blocks_of_the_language_and_given_ranges(self):
        self.assertIsNotNone(view_module(), 'avant : pas de blocs repliables')
        from vectordrive.ui.code_view import fold_regions
        self.assertEqual(fold_regions(PROGRAM), [(0, 10), (1, 9), (6, 8)])
        self.assertEqual(fold_regions(PROGRAM, [(2, 4), (5, 9)]), [(0, 10), (1, 9), (2, 4), (5, 9), (6, 8)])
        self.assertEqual(fold_regions('G0 X1\nG1 X2\nM30'), [])              # un programme ISO : rien de lui-même
        self.assertEqual(fold_regions('if A\nendif\nif B\n  x'), [])         # une seule ligne, ou jamais fermé
        self.assertEqual(fold_regions('module M\nendif\nx\ny\nendmodule'), [(0, 3)])   # un mot de fin sans bloc ouvert

    def test_line_numbers_in_a_margin(self):
        v = self.view()
        self.assertGreater(v.gutter_width(), 20)
        self.assertEqual(v.viewportMargins().left(), v.gutter_width())
        self.assertEqual(v.gutter.width(), v.gutter_width())
        self.assertFalse(v.gutter.grab().toImage().isNull())                # la marge se dessine
        self.assertEqual(v.toPlainText(), PROGRAM)

    def test_fold_and_unfold(self):
        v = self.view(sections=[(2, 4), (5, 9)])
        self.assertEqual(shown_lines(v), list(range(12)))
        self.assertTrue(v.toggle_fold(2))                                   # le parcours « Gravure »
        self.assertEqual(shown_lines(v), [0, 1, 2, 5, 6, 7, 8, 9, 10, 11])
        self.assertTrue(v.is_folded(2))
        self.assertFalse(v.toggle_fold(2))
        self.assertEqual(shown_lines(v), list(range(12)))
        self.assertFalse(v.toggle_fold(3))                                  # pas le début d'un bloc : rien
        self.assertEqual(v.toPlainText(), PROGRAM)                          # le texte, lui, ne change jamais

    def test_nested_blocks(self):
        v = self.view(sections=[(2, 4), (5, 9)])
        v.toggle_fold(6)                                                     # le « if », dans le 2e parcours
        v.toggle_fold(1)                                                     # puis tout le programme
        self.assertEqual(shown_lines(v), [0, 1, 10, 11])
        v.toggle_fold(1)                                                     # déplié : le « if » reste replié
        self.assertEqual(shown_lines(v), [0, 1, 2, 3, 4, 5, 6, 9, 10, 11])
        v.reveal(8)                                                          # une ligne cachée demandée : son bloc déplié
        self.assertEqual(shown_lines(v), list(range(12)))
        v.fold_all(True)
        self.assertEqual(shown_lines(v), [0, 11])
        v.fold_all(False)
        self.assertEqual(shown_lines(v), list(range(12)))

    def test_a_click_in_the_margin(self):
        v = self.view(sections=[(2, 4), (5, 9)])
        y = int(v.blockBoundingGeometry(v.document().findBlockByNumber(5)).translated(v.contentOffset()).center().y())
        self.assertEqual(v.line_at(y), 5)
        v.gutter_clicked(y)
        self.assertTrue(v.is_folded(5))
        self.assertEqual(shown_lines(v), [0, 1, 2, 3, 4, 5, 10, 11])

    def test_folds_kept_when_the_program_is_rewritten(self):
        v = self.view(sections=[(2, 4), (5, 9)])
        v.toggle_fold(5)
        longer = PROGRAM.replace('  Line 2', '  Line 2\n  Line 2b')         # le 1er parcours a une ligne de plus
        v.set_program(longer, [(2, 5), (6, 10)])
        self.assertTrue(v.is_folded(6), 'le bloc replié est redéplié quand le programme est réécrit')
        self.assertFalse(v.is_folded(2))

    def test_discreet_bands(self):
        v = self.view()
        v.set_bands([(5, 9)])
        self.assertEqual(v.bands, [(5, 9)])
        img = v.viewport().grab().toImage()                                  # se dessine, le texte par-dessus
        self.assertFalse(img.isNull())
        from vectordrive.ui import code_view
        self.assertLess(code_view.BAND.alpha(), 80)                         # discret : on lit au travers
        v.set_bands([])
        self.assertEqual(v.bands, [])


def named(toolpaths, setup, *, title: str = '', machine=None, stem: str = 'programme', box_mm=None):
    """Post-processeur d'essai : le nom de chaque parcours en commentaire, puis ses mouvements."""
    from vectordrive.cam.post import PostResult
    lines = ['%', f'(ESSAI {title})']
    for k, tp in enumerate(toolpaths):
        lines.append(f'N{10 * (k + 1)} T{k + 1} M6 ({tp.name})')
        for m in tp.moves:
            lines.append(f'{"G0" if m.kind == "rapid" else "G1"} X{m.x:.3f} Y{m.y:.3f} Z{m.z:.3f} F1200')
    lines.append('M30 ; fin')
    return PostResult('\n'.join(lines) + '\n', [], '.nc', 'utf-8')


class InTheProgramWindow(unittest.TestCase):

    def setUp(self):
        from vectordrive.cam import model
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        from vectordrive.ui.main_window import MainWindow
        self.posts = _posts.registered('essai', named)
        self.posts.__enter__()
        self.addCleanup(self.posts.__exit__, None, None, None)
        self.w = MainWindow()
        self.w.resize(1400, 900)
        self.w.show()
        app.processEvents()
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
        self.w.show_program()
        app.processEvents()
        self.prog.refresh()
        self.assertTrue(hasattr(self.prog.text, 'set_bands'), 'avant : le programme est un simple texte')

    def close(self):
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()

    def lines(self):
        return self.prog.text.toPlainText().split('\n')

    def select(self, row):
        m = self.p.ops.selectionModel()
        m.select(self.p.ops.model().index(row, 0),
                 QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
        app.processEvents()

    def test_one_range_per_toolpath(self):
        lines = self.lines()
        a = next(k for k, t in enumerate(lines) if '(Plaque avant)' in t)
        b = next(k for k, t in enumerate(lines) if '(Contour arriere)' in t)
        last = max(k for k, t in enumerate(lines) if t.strip())
        got = [(x, y) for x, y, _tp in self.prog.sections()]
        self.assertEqual(got, [(a, b - 1), (b, last)])
        self.assertIn((a, b - 1), self.prog.text.regions)                   # chacun est un bloc repliable

    def test_the_chosen_operation_is_highlighted_whole(self):
        self.select(1)
        self.prog.follow_op()
        (b, last), = [(x, y) for x, y, tp in self.prog.sections() if tp.op_id == self.p.setup().operations[1].id]
        self.assertEqual(self.prog.text.bands, [(b, last)])
        self.select(0)
        self.prog.follow_op()
        self.assertEqual(self.prog.text.bands[0][0], next(k for k, t in enumerate(self.lines()) if '(Plaque avant)' in t))

    def test_fold_and_unfold_buttons(self):
        fold, unfold = self.prog.buttons.get('fold'), self.prog.buttons.get('unfold')
        self.assertIsNotNone(fold)
        fold.click()
        heads = sorted(a for a, _b, _tp in self.prog.sections())
        self.assertEqual(sorted(self.prog.text.folded), heads)
        self.assertEqual(len(shown_lines(self.prog.text)), len(self.lines()) - sum(b - a for a, b, _t in self.prog.sections()))
        self.select(1)                                                       # l'opération choisie : dépliée
        self.prog.follow_op()
        self.assertNotIn(heads[1], self.prog.text.folded)
        unfold.click()
        self.assertEqual(self.prog.text.folded, set())
        fold.click()                                                         # replié de nouveau, l'opération 2 choisie
        self.prog.refresh()                                                  # un rafraîchissement (en direct…)
        app.processEvents()
        self.assertEqual(sorted(self.prog.text.folded), heads)              # … ne redéplie rien


if __name__ == '__main__':
    unittest.main()
