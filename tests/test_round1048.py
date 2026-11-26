"""Round 1048 : demande du 15/11, 22 h 30 — « fao parcours : colonne est polluée par commentaires avec panneaux
attention, possibilité de les replier » : le compte rendu du bas du panneau FAO se replie en une ligne ; le repli est
retenu."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1048.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

app = QApplication.instance() or QApplication([])

LONG = ('Gravure : 1200 mm en avance, 300 mm en rapide, ~4 min\n'
        '  ⚠ Outil trop court pour cette profondeur, la passe est limitée à la longueur de coupe\n'
        'Détourage : 800 mm en avance, 200 mm en rapide, ~3 min\n'
        '  ⚠ Rien à usiner\n'
        'Temps estimé : ~7 min, dont 1 changement(s) d’outil (~10 s)')


class Folding(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.p = self.w.cam_panel
        self.w.resize(1200, 800)
        self.w.show()
        app.processEvents()

    def tearDown(self):
        self.w.settings.remove('fao/compte_rendu_replie')
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()

    def fold(self):
        fold = getattr(self.p, 'set_info_folded', None)
        self.assertIsNotNone(fold, 'avant : le compte rendu du panneau FAO ne se replie pas')
        return fold

    def shown(self):
        return QLabel.text(self.p.info)

    def test_folds_to_one_line_with_the_warnings_counted(self):
        fold = self.fold()
        self.p.info.setText(LONG)
        app.processEvents()
        tall = self.p.info.sizeHint().height()
        fold(True)
        app.processEvents()
        self.assertNotIn('\n', self.shown())
        self.assertEqual(self.p.info.summary(), '⚠ 2 · Gravure : 1200 mm en avance, 300 mm en rapide, ~4 min')
        self.assertLess(self.p.info.sizeHint().height(), tall / 2)          # la colonne rendue aux opérations
        self.assertEqual(self.p.info.text(), LONG)                          # le texte entier reste là
        self.assertEqual(self.p.info.toolTip(), LONG)                       # et en bulle
        fold(False)
        app.processEvents()
        self.assertEqual(self.shown(), LONG)
        self.assertEqual(self.p.info.toolTip(), '')

    def test_unfolded_it_scrolls_past_six_lines(self):
        self.fold()
        area = getattr(self.p, 'info_area', None)
        self.assertIsNotNone(area, 'avant : le compte rendu prend toute sa hauteur sur la liste des opérations')
        self.p.info.setText('\n'.join(f'Parcours {i} : 100 mm en avance' for i in range(30)))
        app.processEvents()
        line = self.p.info.fontMetrics().lineSpacing()
        self.assertLessEqual(area.sizeHint().height(), 6 * line + 6)          # six lignes au plus : le reste défile
        self.assertGreater(self.p.info.sizeHint().height(), 20 * line)       # (le texte, lui, est entier)
        self.p.info.setText('Calcul annulé')
        app.processEvents()
        self.assertLessEqual(area.sizeHint().height(), 2 * line)             # un message court : sa seule hauteur

    def test_the_button(self):
        self.fold()
        b = self.p.info_fold
        self.p.info.setText('Calcul annulé')
        self.assertTrue(b.isHidden(), 'une seule ligne : rien à replier')
        self.p.info.setText(LONG)
        self.assertFalse(b.isHidden())
        self.assertEqual(b.text(), '▾')
        b.click()
        self.assertTrue(self.p.info.folded())
        self.assertEqual(b.text(), '▸')
        b.click()
        self.assertFalse(self.p.info.folded())

    def test_one_line_is_never_cut(self):
        fold = self.fold()
        fold(True)
        self.p.info.setText('Modèle « Plaque » enregistré')
        self.assertEqual(self.shown(), 'Modèle « Plaque » enregistré')

    def test_folded_never_widens_the_column(self):
        fold = self.fold()
        self.p.info.setText(LONG + '\n' + 'x' * 400)
        fold(True)
        app.processEvents()
        self.assertLessEqual(self.p.info.minimumSizeHint().width(), 60)
        self.assertLessEqual(self.p.info.sizeHint().width(), 60)
        self.assertLessEqual(self.p.info.fontMetrics().horizontalAdvance(self.shown()),
                             max(40, self.p.info.width()) + 2)              # coupé à la largeur de la colonne

    def test_the_report_shows_the_estimated_time(self):
        from vectordrive.cam import model
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        fold = self.fold()
        sh = Shape(path=geom.Path([geom.rect(0, 0, 20, 14)]), tool=0)
        self.w.canvas.doc.add(sh)
        s = self.p.setup()
        tool = model.CamTool(name='Cyl 2', diameter=2.0, number=1, cut_length=7, step_down=1.0)
        s.tools = [tool]
        s.operations = [model.Operation(name='Gravure', kind='gravure', tool_id=tool.id, items=[sh.id], depth=0.2)]
        self.p.save(s)
        self.p.compute()
        self.assertTrue(self.p.toolpaths)
        self.p.toolpaths[0].warnings = ['Essai 1048']
        self.p._report()
        fold(True)
        app.processEvents()
        last = self.p.info.text().split('\n')[-1]
        self.assertEqual(self.p.info.summary(), '⚠ 1 · ' + last)            # « Temps estimé… », pas la 1re ligne

    def test_the_help_of_the_palette_folds_too(self):
        pal = self.w.cam_palette
        fold = getattr(pal, 'set_hint_folded', None)
        self.assertIsNotNone(fold, 'avant : le texte d’aide de la palette ne se replie pas')
        self.addCleanup(self.w.settings.remove, 'fao/palette/aide_repliee')
        full = pal.hint.text()
        self.assertIn('Un double clic sur un parcours', full)               # round 1163
        tall = pal.hint.heightForWidth(250)
        self.assertEqual(pal.hint_fold.text(), '▾')
        pal.hint_fold.click()
        self.assertTrue(pal.hint.folded())
        self.assertEqual(pal.hint_fold.text(), '▸')
        self.assertLess(pal.hint.sizeHint().height(), tall / 2)
        self.assertEqual(pal.hint.text(), full)
        tip = pal.hint.toolTip()                                             # entier, en bulle, sur plusieurs lignes
        self.assertEqual(' '.join(tip.split()), ' '.join(full.split()))
        self.assertLessEqual(max(len(line) for line in tip.split('\n')), 90)
        self.assertIn(self.w.settings.value('fao/palette/aide_repliee'), (True, 'true'))

    def test_kept_for_the_next_time(self):
        from vectordrive.ui.main_window import MainWindow
        fold = self.fold()
        fold(True)
        again = MainWindow()
        self.addCleanup(again.deleteLater)
        self.addCleanup(again.close)
        self.assertTrue(again.cam_panel.info.folded(), 'le repli de la dernière fois est perdu')
        again.modified = False


class Settings(dict):
    def value(self, k, d=None):
        return self.get(k, d)

    def setValue(self, k, v):                                         # noqa: N802
        self[k] = v


def tree_of(shape):
    """Un arbre d'après `shape` : {nom: {enfants}}."""
    from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem
    tree = QTreeWidget()

    def add(parent, sub):
        for name, kids in sub.items():
            it = QTreeWidgetItem([name])
            (parent.addChild if isinstance(parent, QTreeWidgetItem) else parent.addTopLevelItem)(it)
            add(it, kids)
    add(tree, shape)
    return tree


SHAPE = {'A': {'A1': {'A1a': {}, 'A1b': {}}, 'A2': {}}, 'B': {}, 'C': {'C1': {}}}
ORDER = ['A', 'A1', 'A1a', 'A1b', 'A2', 'B', 'C', 'C1']


class NoQtIterator(unittest.TestCase):
    """Plantage (violation d'accès dans `QTreeWidget.clear()`, une fois sur vingt environ) dans la bibliothèque
    d'outils depuis 0.903.0, dans la palette FAO depuis 0.893.0 : PySide attache chaque `QTreeWidgetItemIterator` à
    son arbre, pour toute la vie de l'arbre ; arrêté au milieu, il garde l'adresse d'une ligne que `clear()` détruit.
    Plus aucun itérateur de Qt dans le code : `tree_memory.items`."""

    def test_no_tree_iterator_left_in_the_code(self):
        import ast
        import pathlib
        root = pathlib.Path(__file__).resolve().parent.parent
        found = []
        for path in sorted((root / 'vectordrive').rglob('*.py')) + sorted((root / 'tests').glob('*.py')):
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                names = [a.name for a in node.names] if isinstance(node, ast.ImportFrom) else \
                    [node.id] if isinstance(node, ast.Name) else [node.attr] if isinstance(node, ast.Attribute) else []
                if 'QTreeWidgetItemIterator' in names:
                    found.append(f'{path.relative_to(root).as_posix()}:{node.lineno}')
        self.assertEqual(found, [], 'un QTreeWidgetItemIterator reste attaché à son arbre : plantage au clear()')

    def walk(self):
        from vectordrive.ui import tree_memory as TM
        items = getattr(TM, 'items', None)
        self.assertIsNotNone(items, 'avant : pas de parcours sans itérateur de Qt')
        return items

    def test_every_row_parents_first_in_order(self):
        from PySide6.QtWidgets import QTreeWidget
        items = self.walk()
        tree = tree_of(SHAPE)
        self.addCleanup(tree.deleteLater)
        self.assertEqual([it.text(0) for it in items(tree)], ORDER)
        tree.topLevelItem(0).child(0).setHidden(True)                       # une ligne cachée : comptée aussi
        self.assertEqual([it.text(0) for it in items(tree)], ORDER)
        self.assertEqual(list(items(QTreeWidget())), [])

    def test_a_search_stopped_halfway_then_the_tree_refilled(self):
        from PySide6.QtWidgets import QTreeWidgetItem
        items = self.walk()
        tree = tree_of(SHAPE)
        self.addCleanup(tree.deleteLater)
        for _ in range(50):                                                 # trouver, vider, remplir : sans fin
            hit = next((it for it in items(tree) if it.text(0) == 'A1b'), None)
            self.assertIsNotNone(hit)
            del hit
            tree.clear()
            for name in ('A', 'B', 'C'):
                top = QTreeWidgetItem([name])
                tree.addTopLevelItem(top)
                for k in ('1', '1b'):
                    top.addChild(QTreeWidgetItem([name + k]))
        self.assertEqual(tree.topLevelItemCount(), 3)

    def test_the_tool_trees_still_find_their_rows(self):
        self.walk()
        from vectordrive.cam import model
        from vectordrive.ui.tool_picker import ToolPickerDialog
        a = model.CamTool(name='A6', kind='fraise', diameter=6.0)
        a.folder = 'Fraises'
        g = model.CamTool(name='G1', kind='conique', diameter=1.0, angle=30.0)
        g.folder = 'Gravure'
        dlg = ToolPickerDialog(None, [], {a.id: a, g.id: g}, current='lib:' + g.id, settings=Settings())
        self.addCleanup(dlg.deleteLater)
        rows = [it.data(0, 0x0100) for it in dlg._items() if it.data(0, 0x0100)]
        self.assertEqual(sorted(rows), sorted(['lib:' + a.id, 'lib:' + g.id]))
        dlg.search.setText('G1')
        app.processEvents()
        dlg.search.clear()
        app.processEvents()
        self.assertEqual(dlg.tree.currentItem().data(0, 0x0100), 'lib:' + g.id)


if __name__ == '__main__':
    unittest.main()
