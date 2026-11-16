"""Round 1055 : demande du 15/11, 20 h 55 (troisième partie) — la liste « générée par le postpro (parcours
sequences) » à côté du programme : le post donne les plages de ses séquences et de ses parcours ; la fenêtre du
programme en fait son plan, ses blocs repliables et ses surlignages, exacts."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1055.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from tests import _posts  # noqa: E402

app = QApplication.instance() or QApplication([])


def with_sections(toolpaths, setup, *, title: str = '', machine=None, stem: str = 'programme', box_mm=None):
    """Post d'essai : une séquence, un parcours par bloc — sans jamais écrire le nom des parcours ; il dit ses plages."""
    from vectordrive.cam.post import PostResult
    lines = ['module Essai', 'program Main', '; sequence 1']       # 0, 1, 2
    secs = []
    for k, _tp in enumerate(toolpaths):
        first = len(lines)
        lines.append(f'  ; bloc {k + 1}')
        lines += [f'  Line {j}' for j in range(3)]
        secs.append({'first': first, 'last': len(lines) - 1, 'kind': 'parcours', 'label': f'Bloc {k + 1}', 'path': k})
    secs.insert(0, {'first': 2, 'last': len(lines) - 1, 'kind': 'sequence', 'label': 'Séquence 1'})
    secs.append({'first': 'x', 'last': 3})                           # une plage mal formée : laissée de côté
    lines += ['endprogram', 'endmodule']
    res = PostResult('\n'.join(lines) + '\n', [], '.simpl', 'utf-8')
    res.sections = secs
    return res


def named(toolpaths, setup, *, title: str = '', machine=None, stem: str = 'programme', box_mm=None):
    from vectordrive.cam.post import PostResult
    lines = ['%']
    for k, tp in enumerate(toolpaths):
        lines += [f'N{10 * (k + 1)} ({tp.name})', 'G1 X1', 'G1 X2']
    lines.append('M30')
    return PostResult('\n'.join(lines) + '\n', [], '.nc', 'utf-8')


def spin(n=6):
    for _ in range(n):
        app.processEvents()


class Base(unittest.TestCase):
    post = staticmethod(with_sections)

    def setUp(self):
        from vectordrive.cam import model
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        from vectordrive.ui.main_window import MainWindow
        self.posts = _posts.registered('essai', self.post)
        self.posts.__enter__()
        self.addCleanup(self.posts.__exit__, None, None, None)
        self.w = MainWindow()
        self.w.resize(1500, 900)
        self.w.show()
        spin()
        self.addCleanup(self.close)
        self.p, self.prog = self.w.cam_panel, self.w.program_panel
        ids = []
        for r in ((0, 0, 20, 14), (30, 0, 12, 8)):
            sh = Shape(path=geom.Path([geom.rect(*r)]), tool=0)
            self.w.canvas.doc.add(sh)
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
        spin()
        self.prog.refresh()
        self.assertIsNotNone(getattr(self.prog, 'outline', None), 'avant : pas de plan du programme')

    def close(self):
        self.w.settings.remove('fao/programme_plan')
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()

    def tops(self):
        t = self.prog.outline
        return [t.topLevelItem(i) for i in range(t.topLevelItemCount())]


class GivenByThePost(Base):

    def test_the_post_can_give_its_ranges(self):
        from vectordrive.cam.post import PostResult
        self.assertIn('sections', PostResult.__dataclass_fields__)
        self.assertEqual(PostResult('x').sections, [])
        data = self.p.program_preview()
        got = [(d['file'], d['first'], d['last'], d['kind'], d['label']) for d in data['sections']]
        self.assertEqual(got, [(0, 2, 10, 'sequence', 'Séquence 1'), (0, 3, 6, 'parcours', 'Bloc 1'),
                               (0, 7, 10, 'parcours', 'Bloc 2')])            # la plage mal formée : écartée
        ops = self.p.setup().operations
        self.assertEqual([d['op_id'] for d in data['sections']], ['', ops[0].id, ops[1].id])

    def test_exact_ranges_without_the_names_in_the_text(self):
        self.assertNotIn('Plaque avant', self.prog.text.toPlainText())      # (la recherche par nom ne trouverait rien)
        ops = self.p.setup().operations
        self.assertEqual([(a, b, tp.op_id) for a, b, tp in self.prog.sections()],
                         [(3, 6, ops[0].id), (7, 10, ops[1].id)])
        for r in ((2, 10), (3, 6), (7, 10)):
            self.assertIn(r, self.prog.text.regions)                        # la séquence aussi se replie

    def test_the_outline_lists_sequences_and_toolpaths(self):
        tops = self.tops()
        self.assertEqual([t.text(0) for t in tops], ['Séquence 1'])
        kids = [tops[0].child(i) for i in range(tops[0].childCount())]
        self.assertEqual([(k.text(0), k.text(1)) for k in kids], [('Bloc 1', '4–7'), ('Bloc 2', '8–11')])
        self.assertEqual(tops[0].text(1), '3–11')

    def test_a_click_in_the_outline(self):
        tops = self.tops()
        self.prog.text.toggle_fold(7)                                        # le 2e bloc replié
        self.prog.outline.itemClicked.emit(tops[0].child(1), 0)
        spin()
        self.assertEqual(self.prog.text.bands, [(7, 10)])                   # surligné…
        self.assertFalse(self.prog.text.is_folded(7))                       # … déplié…
        rows = {i.row() for i in self.p.ops.selectedIndexes()}
        self.assertEqual(rows, {1})                                          # … et son opération choisie
        self.prog.outline.itemClicked.emit(tops[0], 0)                      # la séquence : toute sa plage
        self.assertEqual(self.prog.text.bands, [(2, 10)])

    def test_the_chosen_operation_is_found_by_its_range(self):
        self.p.ops.selectRow(0)
        spin()
        self.assertEqual(self.prog.follow_op(), 3)
        self.assertEqual(self.prog.text.bands, [(3, 6)])

    def test_the_outline_shown_or_hidden_is_kept(self):
        b = self.prog.buttons['outline']
        self.assertTrue(b.isChecked() and not self.prog.outline.isHidden())  # montré d'office
        b.click()
        self.assertTrue(self.prog.outline.isHidden())
        self.assertIn(self.w.settings.value('fao/programme_plan'), (False, 'false'))
        b.click()
        self.assertFalse(self.prog.outline.isHidden())


class WithoutRanges(Base):
    post = staticmethod(named)

    def test_the_outline_from_the_names(self):
        tops = self.tops()
        self.assertEqual([t.text(0) for t in tops], ['Plaque avant', 'Contour arriere'])
        self.assertEqual([t.text(1) for t in tops], ['2–4', '5–8'])
        self.assertEqual(tops[0].data(0, Qt.ItemDataRole.UserRole)[2], self.p.setup().operations[0].id)


if __name__ == '__main__':
    unittest.main()
