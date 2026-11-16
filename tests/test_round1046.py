"""Round 1046 : demande du 15/11, 23 h 45 — « prio bibli tools garde le dernier affichage » : la bibliothèque
d'outils, et « Choisir un outil », rouvrent comme on les a laissées (dossiers ouverts ou fermés, outil choisi, tri,
part de l'arbre et de la fiche) ; l'affichage reste le même quand l'arbre se refait, et revient après une
recherche."""
import importlib.util
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1046.ini'))
os.environ.setdefault('VECTORDRIVE_TOOLS', os.path.join(tempfile.mkdtemp(), 'tools.json'))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from vectordrive.cam import model, toollib  # noqa: E402

app = QApplication.instance() or QApplication([])
ROLE = Qt.ItemDataRole.UserRole
LIB = 'Lib 1046'


class Settings(dict):
    def value(self, k, d=None):
        return self.get(k, d)

    def setValue(self, k, v):                                         # noqa: N802
        self[k] = v


class Parent(QWidget):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings


def tool(name, kind='fraise', d=3.0, angle=0.0, folder='', ref=''):
    t = model.CamTool(name=name, kind=kind, diameter=d, angle=angle, ref=ref)
    t.folder = folder
    return t


def label(it):
    return it.text(0).split('  (')[0].split('  —  ')[0]


def child(node, name):
    for i in range(node.childCount()):
        if label(node.child(i)) == name:
            return node.child(i)
    raise AssertionError(f'pas de « {name} » sous « {label(node)} »')


def top(tree, name):
    for i in range(tree.topLevelItemCount()):
        if label(tree.topLevelItem(i)) == name:
            return tree.topLevelItem(i)
    raise AssertionError(f'pas de « {name} » dans l’arbre')


def module():
    spec = importlib.util.find_spec('vectordrive.ui.tree_memory')
    return spec


class Library(unittest.TestCase):

    def setUp(self):
        from vectordrive import plugins
        self.s = Settings()
        self.parent = Parent(self.s)
        self.addCleanup(self.parent.deleteLater)
        self.path = pathlib.Path(tempfile.mkdtemp()) / 'tools.json'
        self.m1, self.m2 = tool('Mine 1', d=2.0, folder='Atelier'), tool('Mine 2', 'boule', 1.0, folder='Gravure')
        self.m3 = tool('Mine 3', d=4.0, folder='Gravure')
        toollib.save([self.m1, self.m2, self.m3], self.path)
        self.lib = [tool('Plug 6', d=6.0, ref='P-6'), tool('Plug 3', d=3.0, ref='P-3'),
                    tool('Plug V90', 'conique', 3.0, 90.0, ref='P-V90')]
        plugins.reset()
        api = plugins.Api(plugins.REGISTRY, plugins.PluginInfo('essai1046', name='Essai'))
        api.add_tool_library(LIB, lambda: [model.CamTool.from_dict(t.to_dict()) for t in self.lib])
        self.addCleanup(plugins.reset)

    def dialog(self):
        from vectordrive.ui.toollib_dialog import ToolLibraryDialog
        dlg = ToolLibraryDialog(self.parent, None, self.path)
        self.addCleanup(dlg.deleteLater)
        dlg.show()
        app.processEvents()
        return dlg

    def arrange(self, dlg):
        """Un plugin choisi (Plug 3), Mes outils ouvert en entier sauf Gravure, le plugin plié sauf Cylindriques."""
        tree = dlg.tree
        plug = top(tree, '📚 ' + LIB)
        cyl = child(plug, '📁 Cylindriques')
        plug.setExpanded(True)
        cyl.setExpanded(True)
        cyl3 = child(cyl, '📁 Cyl 3')                                     # Cylindriques › Cyl 3 › Plug 3
        cyl3.setExpanded(True)
        row = next(cyl3.child(i) for i in range(cyl3.childCount()) if cyl3.child(i).data(0, ROLE) == self.lib[1].id)
        tree.setCurrentItem(row)
        child(plug, '📁 Coniques').setExpanded(False)
        mine = top(tree, '📚 Mes outils')
        mine.setExpanded(True)
        child(mine, '📁 Atelier').setExpanded(True)
        child(mine, '📁 Gravure').setExpanded(False)
        app.processEvents()

    def check(self, dlg, current=True):
        tree = dlg.tree
        plug = top(tree, '📚 ' + LIB)
        mine = top(tree, '📚 Mes outils')
        self.assertTrue(mine.isExpanded(), 'Mes outils, ouvert la dernière fois, est replié')
        self.assertTrue(child(mine, '📁 Atelier').isExpanded())
        self.assertFalse(child(mine, '📁 Gravure').isExpanded(), 'Gravure, plié la dernière fois, est ouvert')
        self.assertTrue(plug.isExpanded())
        self.assertTrue(child(plug, '📁 Cylindriques').isExpanded())
        self.assertTrue(child(child(plug, '📁 Cylindriques'), '📁 Cyl 3').isExpanded())
        self.assertFalse(child(plug, '📁 Coniques').isExpanded(), 'Coniques, plié la dernière fois, est ouvert')
        if current:
            cur = tree.currentItem()
            self.assertIsNotNone(cur, 'plus d’outil choisi à la réouverture')
            self.assertEqual(cur.data(0, ROLE), self.lib[1].id)
            self.assertEqual(dlg.w['name'].text(), 'Plug 3')            # sa fiche montrée

    def test_reopens_as_it_was_left(self):
        self.assertIsNotNone(module(), 'avant : pas de module tree_memory')
        dlg = self.dialog()
        self.arrange(dlg)
        dlg.reject()
        again = self.dialog()
        self.check(again)

    def test_view_kept_when_the_tree_refills(self):
        dlg = self.dialog()
        self.arrange(dlg)
        dlg.fill()                                                         # une commande, une étoile : l'arbre refait
        app.processEvents()
        self.check(dlg, current=False)

    def test_search_cleared_gives_back_the_view(self):
        dlg = self.dialog()
        self.arrange(dlg)
        dlg.filters.text.setText('P-V90')                                  # la recherche ouvre tout
        app.processEvents()
        self.assertTrue(child(top(dlg.tree, '📚 ' + LIB), '📁 Coniques').isExpanded())
        dlg.filters.text.clear()
        app.processEvents()
        self.check(dlg, current=False)

    def test_closed_during_a_search_keeps_the_view_before_it(self):
        dlg = self.dialog()
        self.arrange(dlg)
        dlg.filters.text.setText('P-V90')
        app.processEvents()
        dlg.reject()
        again = self.dialog()
        self.assertEqual(again.filters.text.text(), '')                    # la recherche repart vide
        self.check(again, current=False)

    def test_sort_and_split_kept(self):
        dlg = self.dialog()
        dlg.tree.header().setSortIndicator(1, Qt.SortOrder.DescendingOrder)
        split = getattr(dlg, 'split', None)
        self.assertIsNotNone(split, 'avant : la part de l’arbre et de la fiche n’est pas retenue')
        total = sum(split.sizes())
        split.setSizes([total // 4, total - total // 4])
        app.processEvents()
        want = split.sizes()[0]
        dlg.reject()
        again = self.dialog()
        self.assertEqual(again.tree.sortColumn(), 1, 'le tri de la dernière fois est perdu')
        self.assertEqual(again.tree.header().sortIndicatorOrder(), Qt.SortOrder.DescendingOrder)
        self.assertLessEqual(abs(again.split.sizes()[0] - want), 30)

    def test_first_time_unchanged(self):
        dlg = self.dialog()                                                # rien de retenu : comme avant
        self.assertTrue(top(dlg.tree, '📚 ' + LIB).isExpanded() or top(dlg.tree, '📚 Mes outils').isExpanded())


class Picker(unittest.TestCase):

    def setUp(self):
        self.s = Settings()
        self.a6, self.a3 = tool('A6', d=6.0, folder='Fraises/Cyl'), tool('A3', d=3.0, folder='Fraises/Cyl')
        self.g1 = tool('G1', 'conique', 1.0, 30.0, folder='Gravure')
        self.lib = {t.id: t for t in (self.a6, self.a3, self.g1)}

    def picker(self, current=None):
        from vectordrive.ui.tool_picker import ToolPickerDialog
        dlg = ToolPickerDialog(None, [], self.lib, current=current, settings=self.s)
        self.addCleanup(dlg.deleteLater)
        dlg.show()
        app.processEvents()
        return dlg

    def test_picker_reopens_as_it_was_left(self):
        self.assertIsNotNone(module(), 'avant : pas de module tree_memory')
        dlg = self.picker()
        top(dlg.tree, '📁 Gravure').setExpanded(False)
        fr = top(dlg.tree, '📁 Fraises')
        fr.setExpanded(True)
        cyl = child(fr, '📁 Cyl')
        cyl.setExpanded(True)
        row = next(cyl.child(i) for i in range(cyl.childCount()) if cyl.child(i).data(0, ROLE) == 'lib:' + self.a3.id)
        dlg.tree.setCurrentItem(row)
        app.processEvents()
        dlg.reject()
        again = self.picker()
        self.assertFalse(top(again.tree, '📁 Gravure').isExpanded(), 'Gravure, plié la dernière fois, est ouvert')
        self.assertTrue(child(top(again.tree, '📁 Fraises'), '📁 Cyl').isExpanded())
        cur = again.tree.currentItem()
        self.assertIsNotNone(cur, 'plus d’outil choisi à la réouverture')
        self.assertEqual(cur.data(0, ROLE), 'lib:' + self.a3.id)

    def test_tool_of_the_operation_stays_chosen_and_in_view(self):
        dlg = self.picker()
        top(dlg.tree, '📁 Gravure').setExpanded(False)
        child(top(dlg.tree, '📁 Fraises'), '📁 Cyl').setExpanded(False)
        app.processEvents()
        dlg.reject()
        again = self.picker(current='lib:' + self.a6.id)                   # l'outil de l'opération ouverte
        self.assertEqual(again.tree.currentItem().data(0, ROLE), 'lib:' + self.a6.id)
        self.assertTrue(child(top(again.tree, '📁 Fraises'), '📁 Cyl').isExpanded())     # ses dossiers ouverts
        self.assertFalse(top(again.tree, '📁 Gravure').isExpanded(), 'Gravure, plié la dernière fois, est ouvert')

    def test_tool_of_the_operation_not_scrolled_away(self):
        many = [tool(f'Lot {i:02d}', d=1.0 + i / 10, folder='Lot') for i in range(80)]
        self.lib.update({t.id: t for t in many})
        dlg = self.picker()
        dlg.tree.scrollToTop()
        app.processEvents()
        dlg.reject()
        again = self.picker(current='lib:' + many[-1].id)                  # tout en bas de la liste
        for _ in range(3):
            app.processEvents()
        cur = again.tree.currentItem()
        self.assertEqual(cur.data(0, ROLE), 'lib:' + many[-1].id)
        self.assertTrue(again.tree.visualItemRect(cur).intersects(again.tree.viewport().rect()),
                        'l’outil de l’opération est hors de la vue')

    def test_picker_search_cleared_gives_back_the_view(self):
        dlg = self.picker()
        top(dlg.tree, '📁 Gravure').setExpanded(False)
        app.processEvents()
        dlg.search.setText('G1')
        app.processEvents()
        self.assertTrue(top(dlg.tree, '📁 Gravure').isExpanded())          # la recherche ouvre le dossier
        dlg.search.clear()
        app.processEvents()
        self.assertFalse(top(dlg.tree, '📁 Gravure').isExpanded(), 'recherche effacée : Gravure reste ouvert')


if __name__ == '__main__':
    unittest.main()
