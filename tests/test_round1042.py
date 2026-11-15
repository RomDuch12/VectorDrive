"""Round 1042 : demande du 15/11 « Outils : … Classement outils Cylindriques (dossier parent de Cyl 3, Cyl 4, Cyl 6,
Cyl 8 etc), Conique (con 90, Con 45, Con 30, Con 20 etc), Boule, Chamfer, Thread, Ext-Rad, T-slot, Drill ; … des étoiles
devant chacun pour les remonter en tête de liste Favoris (pliable dépliable), les outils sont réarrangeables à la
souris ; … Filtres repartir largeur avec barre recherche qui prend trop de longueur, champs sans flèches avec croix
pour effacer » (1re partie : classement, filtres, favoris de « Choisir un outil »)."""
import json
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1042.ini'))
os.environ.setdefault('VECTORDRIVE_TOOLS', os.path.join(tempfile.mkdtemp(), 'tools.json'))

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QLineEdit  # noqa: E402

from vectordrive.cam import model, toollib  # noqa: E402

app = QApplication.instance() or QApplication([])
ROLE = Qt.ItemDataRole.UserRole


class Settings(dict):
    def value(self, k, d=None):
        return self.get(k, d)

    def setValue(self, k, v):                                         # noqa: N802
        self[k] = v


def tool(name, kind='fraise', d=3.0, angle=0.0, ref='', **extra):
    t = model.CamTool(name=name, kind=kind, diameter=d, angle=angle, ref=ref)
    for k, v in extra.items():
        setattr(t, k, v)
    return t


def api(tools, name='Lib 1042'):
    from vectordrive import plugins
    plugins.reset()
    a = plugins.Api(plugins.REGISTRY, plugins.PluginInfo('essai1042', name='Essai'))
    a.add_tool_library(name, lambda: [model.CamTool.from_dict(t.to_dict()) for t in tools])
    return plugins


def func(name):
    f = getattr(toollib, name, None)
    if f is None:
        raise AssertionError(f'toollib.{name} absent')
    return f


class Families(unittest.TestCase):

    def test_family_paths(self):
        path = func('family_path')
        cases = [(tool('C3', d=3.0), ['Cylindriques', 'Cyl 3']),
                 (tool('C6', d=6.0), ['Cylindriques', 'Cyl 6']),
                 (tool('V90', 'conique', 3.0, 90.0), ['Coniques', 'Con 90']),
                 (tool('V20', 'conique', 3.175, 20.0), ['Coniques', 'Con 20']),
                 (tool('B2', 'boule', 2.0), ['Boules']),
                 (tool('Ch', 'conique', 6.0, 90.0, catalog={'famille': 'chanfrein'}), ['Chamfer']),
                 (tool('M4', geometry={'famille': 'filetage'}), ['Thread']),
                 (tool('R1', geometry={'famille': 'rayon'}), ['Ext-Rad']),
                 (tool('T8', d=8.0, catalog={'famille': 'tslot'}), ['T-slot']),
                 (tool('D3', 'foret', 3.0, 118.0), ['Drill'])]
        self.assertEqual([path(t) for t, _p in cases], [p for _t, p in cases])

    def test_folder_order(self):
        key = func('folder_sort_key')
        names = ['Datron/Drill', 'Datron/Coniques/Con 30', 'Datron/Cylindriques/Cyl 10', 'Datron/Coniques/Con 90',
                 'Datron/Cylindriques/Cyl 3', 'Datron/Boules', 'Datron/Chamfer', 'Datron/T-slot', 'Datron/Ext-Rad',
                 'Datron/Thread', 'Datron/Coniques/Con 45', 'Datron/Cylindriques/Cyl 4']
        self.assertEqual(sorted(names, key=key),
                         ['Datron/Cylindriques/Cyl 3', 'Datron/Cylindriques/Cyl 4', 'Datron/Cylindriques/Cyl 10',
                          'Datron/Coniques/Con 90', 'Datron/Coniques/Con 45', 'Datron/Coniques/Con 30',
                          'Datron/Boules', 'Datron/Chamfer', 'Datron/Thread', 'Datron/Ext-Rad', 'Datron/T-slot',
                          'Datron/Drill'])

    def test_plugin_tools_filed_by_family(self):
        plugins = api([tool('P4', d=4.0, folder='Fraises'), tool('P45', 'conique', 3.0, 45.0, folder='Coniques'),
                       tool('PB', 'boule', 2.0)])
        try:
            got = {t.name: t.folder for t in toollib.with_plugins([])}
        finally:
            plugins.reset()
        self.assertEqual(got, {'P4': 'Lib 1042/Cylindriques/Cyl 4', 'P45': 'Lib 1042/Coniques/Con 45',
                               'PB': 'Lib 1042/Boules'})

    def test_old_folder_rules_still_match_plugin_tools(self):
        """Relecture : une règle « dossier » (Outils par opération) qui visait le dossier d'un outil dans son plugin
        vaut encore, comme celle qui vise sa famille."""
        from vectordrive.cam import toolprefs
        plugins = api([tool('L3', d=3.0, folder='Fraises')])
        try:
            got = [t for t in toollib.with_plugins([]) if t.name == 'L3']
        finally:
            plugins.reset()
        self.assertEqual(len(got), 1)
        self.assertEqual(toollib.folder_of(got[0]), 'Lib 1042/Cylindriques/Cyl 3')
        self.assertTrue(toolprefs.matches({'type': 'dossier', 'value': 'Lib 1042/Fraises'}, got[0]))
        self.assertTrue(toolprefs.matches({'type': 'dossier', 'value': 'Lib 1042/Cylindriques'}, got[0]))
        self.assertFalse(toolprefs.matches({'type': 'dossier', 'value': 'Lib 1042/Forets'}, got[0]))

    def test_library_window_by_family(self):
        from vectordrive.ui.toollib_dialog import ToolLibraryDialog
        plugins = api([tool('L6', d=6.0), tool('L3', d=3.0), tool('L90', 'conique', 3.0, 90.0), tool('LB', 'boule')])
        try:
            dlg = ToolLibraryDialog(None, None, pathlib.Path(tempfile.mkdtemp()) / 'tools.json')
            self.addCleanup(dlg.deleteLater)
            dlg.source.setCurrentIndex(dlg.source.findData('Lib 1042'))
        finally:
            plugins.reset()
        node = dlg.tree.topLevelItem(0)                  # 1043 : un seul arbre, la bibliothèque en dossier
        self.assertTrue(node.text(0).startswith('📚 Lib 1042'), node.text(0))
        tops = [node.child(i) for i in range(node.childCount())]
        self.assertEqual([t.text(0) for t in tops], ['📁 Cylindriques', '📁 Coniques', '📁 Boules'])
        cyl = tops[0]
        self.assertEqual([cyl.child(i).text(0) for i in range(cyl.childCount())], ['📁 Cyl 3', '📁 Cyl 6'])
        self.assertEqual(cyl.child(0).child(0).text(0).split(' — ')[0].strip(), 'L3')


class Filters(unittest.TestCase):

    def bar(self):
        from vectordrive.ui.tool_filters import FilterBar
        bar = FilterBar(Settings())
        self.addCleanup(bar.deleteLater)
        return bar

    def test_diameters_without_arrows_and_with_a_cross(self):
        bar = self.bar()
        seen = []
        bar.changed.connect(lambda: seen.append(bar.dmin.value()))
        for f in (bar.dmin, bar.dmax):
            self.assertIsInstance(f, QLineEdit)                              # pas de flèches
            self.assertTrue(f.isClearButtonEnabled())                        # une croix pour l'effacer
        bar.dmin.setValue(1.5)
        self.assertEqual((bar.dmin.text(), bar.dmin.value()), ('1.5', 1.5))
        bar.dmin.setText('2,5')                                              # virgule ou point
        self.assertEqual(bar.dmin.value(), 2.5)
        self.assertTrue(bar.active())
        bar.dmin.clear()                                                     # la croix : sans borne
        self.assertEqual(bar.dmin.value(), 0.0)
        self.assertFalse(bar.active())
        self.assertEqual(seen, [1.5, 2.5, 0.0])
        bar.dmax.setValue(4)
        bar.reset()
        self.assertEqual((bar.dmax.text(), bar.dmax.value()), ('', 0.0))

    def test_filters_share_the_width(self):
        bar = self.bar()
        bar.resize(1800, 40)
        bar.show()
        app.processEvents()
        bar.layout().activate()
        w = bar.width()
        self.assertLess(bar.text.width(), 0.35 * w)                          # la recherche ne prend plus tout
        for c in (bar.kind, bar.vendor, bar.op):
            self.assertGreater(c.width(), 0.12 * w, c.currentText())


class Picker(unittest.TestCase):

    def setUp(self):
        self.s = Settings()
        self.a = tool('Fav A', d=3.0, folder='Atelier')
        self.b = tool('Fav B', 'conique', 3.0, 60.0, ref='REF-B', folder='Atelier')
        self.c = tool('Fav C', 'boule', 2.0, folder='Gravure')
        self.lib = {t.id: t for t in (self.a, self.b, self.c)}

    def picker(self, show=False):
        from vectordrive.ui.tool_picker import ToolPickerDialog
        dlg = ToolPickerDialog(None, [], self.lib, settings=self.s)
        self.addCleanup(dlg.deleteLater)
        if show:
            dlg.show()
            app.processEvents()
        return dlg

    def favs(self, *tools):
        key = func('favorite_key')
        self.s['outils/favoris'] = json.dumps([key(t) for t in tools])

    def names(self, group):
        return [group.child(i).text(0).split(' — ')[0].strip() for i in range(group.childCount())]

    def row(self, dlg, t, in_favs=False):
        for it in dlg._items():
            fav = it.parent() is not None and it.parent().data(0, ROLE + 2) == 'favoris'
            if it.data(0, ROLE) == 'lib:' + t.id and fav == in_favs:
                return it
        raise AssertionError(f'{t.name} absent')

    def test_favourites_on_top_in_their_order(self):
        self.favs(self.c, self.a)
        dlg = self.picker()
        top = dlg.tree.topLevelItem(0)
        self.assertTrue(top.text(0).startswith('★ Favoris'), top.text(0))
        self.assertEqual(self.names(top), ['Fav C', 'Fav A'])
        self.assertTrue(top.isExpanded())
        self.row(dlg, self.a)                                                 # toujours dans son dossier aussi

    def test_a_click_on_the_star(self):
        dlg = self.picker(show=True)
        it = self.row(dlg, self.b)
        dlg.tree.scrollToItem(it)
        r = dlg.tree.visualItemRect(it)
        QTest.mouseClick(dlg.tree.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                         QPoint(r.left() + 8, r.center().y()))
        for _ in range(3):
            app.processEvents()
        self.assertIn('ref:ref-b', self.s.get('outils/favoris', ''))
        top = dlg.tree.topLevelItem(0)
        self.assertTrue(top.text(0).startswith('★ Favoris'), top.text(0))
        self.assertEqual(self.names(top), ['Fav B'])
        self.assertTrue(self.row(dlg, self.b).data(0, ROLE + 20))            # ★ aussi dans son dossier
        fav = self.row(dlg, self.b, in_favs=True)
        dlg.tree.scrollToItem(fav)
        r = dlg.tree.visualItemRect(fav)
        QTest.mouseClick(dlg.tree.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                         QPoint(r.left() + 8, r.center().y()))
        for _ in range(3):
            app.processEvents()
        self.assertEqual(json.loads(self.s['outils/favoris']), [])
        self.assertFalse(dlg.tree.topLevelItem(0).text(0).startswith('★'))

    def test_the_mouse_reorders_the_favourites(self):
        self.favs(self.a, self.b, self.c)
        dlg = self.picker()
        g = dlg.tree.topLevelItem(0)
        rows = [g.child(i) for i in range(g.childCount())]
        self.assertTrue(all(r.flags() & Qt.ItemFlag.ItemIsDragEnabled for r in rows))
        self.assertTrue(g.flags() & Qt.ItemFlag.ItemIsDropEnabled)
        others = [it for it in dlg._items() if it.parent() is not g and it is not g]
        self.assertFalse(any(it.flags() & Qt.ItemFlag.ItemIsDragEnabled for it in others))
        self.assertFalse(any(it.flags() & Qt.ItemFlag.ItemIsDropEnabled for it in others))
        self.assertFalse(dlg.tree.invisibleRootItem().flags() & Qt.ItemFlag.ItemIsDropEnabled)
        g.insertChild(0, g.takeChild(2))                                     # ce que fait un glisser-déposer
        moved = getattr(dlg, '_favorites_moved', None)
        self.assertIsNotNone(moved, 'pas de rangement des favoris')
        moved()
        for _ in range(3):
            app.processEvents()
        key = func('favorite_key')
        self.assertEqual(json.loads(self.s['outils/favoris']), [key(self.c), key(self.a), key(self.b)])
        self.assertEqual(self.names(dlg.tree.topLevelItem(0)), ['Fav C', 'Fav A', 'Fav B'])

    def test_sorted_by_a_column_the_order_is_kept(self):
        """Relecture : triée par une colonne, la liste ne laisse rien glisser, et un dépôt ne change pas l'ordre."""
        self.favs(self.a, self.b, self.c)
        dlg = self.picker()
        grp = getattr(dlg, 'favorites_group', None)
        self.assertIsNotNone(grp, 'pas de favoris')
        dlg.tree.sortByColumn(0, Qt.SortOrder.DescendingOrder)
        g = grp()
        self.assertFalse(any(g.child(i).flags() & Qt.ItemFlag.ItemIsDragEnabled for i in range(g.childCount())))
        g.insertChild(0, g.takeChild(2))
        dlg._favorites_moved()
        for _ in range(3):
            app.processEvents()
        key = func('favorite_key')
        self.assertEqual(json.loads(self.s['outils/favoris']), [key(self.a), key(self.b), key(self.c)])

    def test_a_folded_group_stays_folded(self):
        """Relecture : favoris pliés, la ligne choisie dedans ; une autre étoile basculée ne les déplie pas."""
        self.favs(self.a)
        dlg = self.picker(show=True)
        dlg.tree.setCurrentItem(self.row(dlg, self.a, in_favs=True))
        dlg.tree.topLevelItem(0).setExpanded(False)
        self.assertIs(self.s.get('outils/favoris_ouvert'), False)
        dlg.toggle_favorite('lib:' + self.c.id)
        for _ in range(3):
            app.processEvents()
        self.assertFalse(dlg.tree.topLevelItem(0).isExpanded())
        self.assertIs(self.s.get('outils/favoris_ouvert'), False)

    def test_a_renamed_favourite_stays_one(self):
        """Relecture : un favori renommé depuis sa fiche reste favori, à sa place."""
        from vectordrive.ui import tool_sheet as TS
        self.favs(self.c, self.a)
        sheet = TS.ToolSheet(None, None, self.s)
        self.addCleanup(sheet.deleteLater)
        sheet.show_tool(self.a, TS.DOC)
        sheet.w['name'].setText('Fav A bis')
        self.assertTrue(sheet.save(emit=False))
        self.assertEqual(self.a.name, 'Fav A bis')
        key = func('favorite_key')
        self.assertEqual(json.loads(self.s['outils/favoris']), [key(self.c), key(self.a)])

    def test_a_renamed_copy_leaves_the_original_starred(self):
        """Relecture : la copie d'un favori (dans le document) renommée : l'original reste favori, la copie aussi."""
        from vectordrive.ui import tool_sheet as TS
        from vectordrive.ui.tool_picker import ToolPickerDialog
        copy = model.CamTool.from_dict(self.a.to_dict())
        copy.id = model.new_id()
        self.favs(self.a)
        dlg = ToolPickerDialog(None, [copy], self.lib, settings=self.s)
        self.addCleanup(dlg.deleteLater)
        self.assertIsNotNone(getattr(dlg.sheet, 'shared_key', None), 'avant : la copie emportait l’étoile')
        dlg.sheet.show_tool(copy, TS.DOC)
        dlg.sheet.w['name'].setText('Fav A copie')
        self.assertTrue(dlg.sheet.save(emit=False))
        key = func('favorite_key')
        self.assertEqual(json.loads(self.s['outils/favoris']), [key(self.a), key(copy)])

    def test_folding_is_remembered(self):
        self.favs(self.a)
        dlg = self.picker()
        top = dlg.tree.topLevelItem(0)
        self.assertTrue(top.text(0).startswith('★ Favoris'), top.text(0))
        top.setExpanded(False)
        dlg2 = self.picker()
        self.assertFalse(dlg2.tree.topLevelItem(0).isExpanded())
        dlg2.tree.topLevelItem(0).setExpanded(True)
        self.assertTrue(self.picker().tree.topLevelItem(0).isExpanded())

    def test_folders_in_family_order(self):
        lib = [tool('X4', d=4.0, folder='Datron/Cylindriques/Cyl 4'),
               tool('X10', d=10.0, folder='Datron/Cylindriques/Cyl 10'),
               tool('X30', 'conique', 3.0, 30.0, folder='Datron/Coniques/Con 30'),
               tool('X90', 'conique', 3.0, 90.0, folder='Datron/Coniques/Con 90'),
               tool('XB', 'boule', 2.0, folder='Datron/Boules')]
        self.lib = {t.id: t for t in lib}
        dlg = self.picker()
        datron = dlg.tree.topLevelItem(0)
        self.assertTrue(datron.text(0).startswith('📁 Datron'), datron.text(0))
        kids = [datron.child(i) for i in range(datron.childCount())]
        self.assertEqual([k.text(0).split('  (')[0] for k in kids], ['📁 Cylindriques', '📁 Coniques', '📁 Boules'])
        self.assertEqual([kids[0].child(i).text(0).split('  (')[0] for i in range(kids[0].childCount())],
                         ['📁 Cyl 4', '📁 Cyl 10'])
        self.assertEqual([kids[1].child(i).text(0).split('  (')[0] for i in range(kids[1].childCount())],
                         ['📁 Con 90', '📁 Con 30'])


class DxfDrawing(unittest.TestCase):
    """« le dxf n'affiche pas les lignes de cotation » : un trait seul horizontal ou vertical (ligne de cote, axe) était
    écarté au dessin (rectangle plat), un texte lu d'un DXF n'avait jamais de tracé."""

    def drawn(self, doc):
        """Canevas hors écran sur `doc` : les tracés passés à drawPath pendant un rendu (id des QPainterPath)."""
        from PySide6.QtGui import QPainter
        from vectordrive.ui import canvas as C
        seen = []

        class Recorder(QPainter):
            def drawPath(self, path):                                 # noqa: N802
                seen.append(id(path))
                super().drawPath(path)

        c = C.Canvas()
        c.resize(640, 480)
        doc.plate = None
        c.set_document(doc)
        old = C.QPainter
        C.QPainter = Recorder
        try:
            c.grab()
        finally:
            C.QPainter = old
        return c, set(seen)

    def line(self, a, b, tool=3):
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        return Shape(path=geom.Path([geom.Contour([geom.Line(a, b)], False)]), tool=tool)

    def test_lone_horizontal_and_vertical_lines_drawn(self):
        from vectordrive.core.document import Document
        doc = Document()
        diag, flat, upright = (self.line((100, 30), (110, 40)), self.line((100, 50), (140, 50)),
                               self.line((160, 30), (160, 70)))
        for it in (diag, flat, upright):
            doc.add(it)
        c, seen = self.drawn(doc)
        self.assertIn(id(c._entry(diag)[1]), seen)                   # oblique : dessiné avant comme après
        self.assertIn(id(c._entry(flat)[1]), seen, 'trait horizontal seul non dessiné')
        self.assertIn(id(c._entry(upright)[1]), seen, 'trait vertical seul non dessiné')

    def test_text_read_without_outline_is_drawn(self):
        from vectordrive.core.document import Document, Text
        from vectordrive.core.geom import Affine
        from vectordrive.ui.canvas import item_path
        doc = Document()
        t = Text(text='AB', font='VD Géo', size=5.0, matrix=Affine.translation(20, 20))
        lost = Text(text='CD', font='Police absente 1042', size=5.0, matrix=Affine.translation(20, 40))
        doc.add(t)
        doc.add(lost)
        self.assertIsNone(t.outline)
        p = item_path(t)
        self.assertIsNotNone(p, 'texte sans tracé : rien à dessiner')
        self.assertTrue(p.contours)
        self.assertIs(t.outline, p)                                   # gardé : calculé une seule fois
        self.assertIsNone(item_path(lost))                           # police absente : pas de police de remplacement
        self.assertIsNone(lost.outline)
        c, seen = self.drawn(doc)
        self.assertIn(id(c._entry(t)[1]), seen)

    def test_tool_drawing_dimensions_all_drawn(self):
        from vectordrive.cam import tooldraw
        from vectordrive.io import dxf
        from vectordrive.ui.canvas import _leaves
        t = model.CamTool(name='Essai', kind='fraise', diameter=3.0, cut_length=8.0)
        t.geometry = {'D1': 3.0, 'D2': 6.0, 'L1': 50.0, 'L2': 8.0}
        out = tooldraw.write_drawings(t, tempfile.mkdtemp())
        doc = dxf.read(out['dxf'])
        cotes = [L for L in doc.layers if L.name == 'COTES']
        self.assertEqual(len(cotes), 1)
        leaves = list(_leaves(cotes[0].items))
        self.assertGreaterEqual(len(leaves), 10)
        c, seen = self.drawn(doc)
        missing = [type(it).__name__ for it in leaves if c._entry(it) is None or id(c._entry(it)[1]) not in seen]
        self.assertEqual(missing, [], 'cotes du dessin d’outil non dessinées')


if __name__ == '__main__':
    unittest.main()
