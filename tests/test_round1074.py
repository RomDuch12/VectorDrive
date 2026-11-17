"""Round 1074 : réponses du 17/11 — question 46 (« la palette ») : le panneau de colonne « Couleur », la palette des
couleurs du dessin, un clic colore la sélection et choisit la couleur courante ; Q31 : les deux avances d'un outil
NeoDrive ; question 45 : les vis hors de la découpe de chaque gravure, dans le squelette ou dans les gravures."""
import importlib.util
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1074.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication, QDockWidget  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Group, Shape  # noqa: E402

BEFORE = 'avant : pas de panneau Couleur (seulement Édition › Couleur…, la couleur propre des objets)'


def forget():
    from vectordrive import portable
    s = portable.settings()
    s.remove('panneaux_colonnes')
    s.sync()


class Palette(unittest.TestCase):

    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('vectordrive.ui.color_panel'), BEFORE)
        forget()
        self.addCleanup(forget)
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.show()
        app.processEvents()
        self.addCleanup(self.close)
        doc = self.w.canvas.doc
        self.a = Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]), tool=0)
        self.b = Shape(path=geom.Path([geom.rect(20, 0, 10, 10)]), tool=0)
        self.g = Group(children=[Shape(path=geom.Path([geom.rect(40, 0, 5, 5)]), tool=1)], tool=1)
        for it in (self.a, self.b, self.g):
            doc.add(it)
        self.p = self.w.color_panel

    def close(self):
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()

    def rows(self):
        return [self.p.list.item(k).text() for k in range(self.p.list.count())]

    def test_a_column_panel_on_the_left_hidden_until_asked(self):
        d = self.w.findChild(QDockWidget, 'couleur')
        self.assertIs(d, self.w.dock_color)
        self.assertTrue(d.isHidden())
        self.assertEqual(self.w.columns.side(d), 'gauche')
        from vectordrive.ui import columns as C
        table = C.PanelRows(self.w.columns)
        self.addCleanup(table.deleteLater)
        self.assertIn('couleur', table.choices)                              # dans le tableau Gauche / Masqué / Droite
        table.choices['couleur']['gauche'].click()
        app.processEvents()
        self.assertFalse(d.isHidden())
        self.assertEqual(len(self.rows()), len(self.w.canvas.doc.tools))     # une ligne par couleur du dessin
        self.assertIn('(2)', self.rows()[0])                                 # ses objets comptés
        self.assertIn('(1)', self.rows()[1])

    def test_a_click_colours_the_selection_and_makes_the_current_colour(self):
        w = self.w
        w.canvas.selection = [self.a, self.g]
        w._on_selection()
        n = self.p.apply(3)
        self.assertEqual(n, 2)                                               # a et la forme du groupe
        self.assertEqual((self.a.tool, self.g.tool, self.g.children[0].tool, self.b.tool), (3, 3, 3, 0))
        self.assertEqual(w.canvas.current_tool_index, 3)                     # les objets dessinés ensuite
        self.assertEqual(w.canvas.doc.active_layer.tool, 0)                  # le calque n'est pas recoloré
        self.w.layers_panel.refresh()
        self.assertEqual(w.canvas.current_tool_index, 3)                     # gardée
        self.p.sync(force=True)
        self.assertTrue(self.rows()[3].startswith('✓'))                      # la couleur de la sélection
        self.assertTrue(self.p.list.item(3).font().bold())                   # la couleur courante
        w.undo()                                                             # un seul pas
        self.assertEqual((w.canvas.doc.layers[0].items[0].tool, w.canvas.doc.active_layer.tool), (0, 0))

    def test_without_selection_only_the_current_colour(self):
        w = self.w
        w.canvas.selection = []
        w.modified = False
        steps = len(w._undo)
        self.p.apply(2)
        self.assertEqual((self.a.tool, self.b.tool, w.canvas.doc.active_layer.tool), (0, 0, 0))
        self.assertEqual((len(w._undo), w.modified), (steps, False))       # le dessin ne change pas
        self.assertEqual(w.canvas.current_tool_index, 2)
        self.w.layers_panel.refresh()                                        # gardée
        self.assertEqual(w.canvas.current_tool_index, 2)
        from vectordrive.core.document import Layer
        L2 = Layer(name='B', tool=5)
        w.canvas.doc.layers.append(L2)
        w.canvas.doc.active = L2.id                                          # un autre calque : sa couleur
        self.w.layers_panel.refresh()
        self.assertEqual(w.canvas.current_tool_index, 5)

    def test_change_the_colour_of_a_tool(self):
        self.assertTrue(self.p.set_tool_color(1, '#123456'))
        self.assertEqual(self.w.canvas.doc.tools[1].color, '#123456')
        self.assertFalse(self.p.set_tool_color(1, '#123456'))
        self.assertFalse(self.p.set_tool_color(1, '#123456'.upper()))       # même couleur, autre casse
        self.w.undo()
        self.assertNotEqual(self.w.canvas.doc.tools[1].color, '#123456')


class NeoDriveFeeds(unittest.TestCase):
    """Q31 (réponse du 17/11 : oui) : le cadre Ébauche prend `feed_roughing`, le cadre Finition `feed_finishing`."""

    def test_both_feeds_kept(self):
        from vectordrive.cam import toollib
        t = toollib.from_neodrive('f3', {'name': 'Fraise 3', 'diameter': 3.0, 'feed_roughing': 1800,
                                         'feed_finishing': 900})
        self.assertEqual((t.feed, t.finish_feed), (1800, 900), 'avant : 900 partout (feed_finishing seule)')
        key, d = toollib.to_neodrive(t)
        self.assertEqual((d['feed_roughing'], d['feed_finishing']), (1800, 900))

    def test_one_feed_or_the_same_no_finish_feed(self):
        from vectordrive.cam import toollib
        for d, want in (({'feed_finishing': 1200}, 1200), ({'feed_roughing': 700}, 700),
                        ({'feed_roughing': 500, 'feed_finishing': 500}, 500), ({}, 600)):
            t = toollib.from_neodrive('x', dict(d, name='Fraise', diameter=2.0))
            self.assertEqual((t.feed, t.finish_feed), (want, 0.0), d)
            self.assertEqual(toollib.to_neodrive(t)[1]['feed_finishing'], want)


def circle(x, y, d):
    return Shape(path=geom.Path([geom.circle((x, y), d / 2)]), tool=0)


def plate_drawing():
    """Une plaque percée Ø 4,05 tous les 10 mm (de 5 à 95 × de 5 à 55) ; un brut 100 × 60 ; deux gravures (20 × 20 et
    30 × 25) ; une troisième, à 1 mm de la deuxième (leurs découpes se touchent)."""
    from vectordrive.core.document import Document, Layer
    plate = Layer(name='Plaque')
    plate.items = [Group(children=[circle(5.0 + 10 * i, 5.0 + 10 * j, 4.05) for i in range(10) for j in range(6)])]
    work = Layer(name='Bruts')
    blank = Shape(path=geom.Path([geom.rect(0.0, 0.0, 100.0, 60.0)]), tool=1)
    logo1 = Group(children=[Shape(path=geom.Path([geom.rect(10.0, 10.0, 8.0, 20.0)]), tool=2),
                            Shape(path=geom.Path([geom.rect(22.0, 10.0, 8.0, 20.0)]), tool=2)])   # un logo groupé
    logo2 = Shape(path=geom.Path([geom.rect(55.0, 15.0, 30.0, 25.0)]), tool=2)
    work.items = [blank, logo1, logo2]
    return Document(layers=[plate, work]), plate, work, blank, logo1, logo2


class ScrewsAndEngravingCut(unittest.TestCase):
    """Question 45 (réponse du 17/11) : la forme découpée est le cadre englobant de chaque logo ; les vis vont au
    choix dans le squelette ou dans les gravures (selon le cahier des charges du client)."""

    def spec(self, where, **kw):
        from vectordrive.cam import fixture as FX
        self.assertIn('screws_in', FX.Spec.__dataclass_fields__, 'avant : les vis partout sous le brut')
        return FX.Spec(per_blank=0, margin=1.0, screws_in=where, cut_width=2.0, **kw)

    def test_frames_of_the_logos(self):
        from vectordrive.cam import fixture as FX
        doc, plate, work, blank, logo1, logo2 = plate_drawing()
        poly = FX.blank_polygon(blank)
        frames = FX.logo_frames(poly, work.items, {blank.id}, 2.0)
        self.assertEqual(frames, [(10.0, 10.0, 30.0, 30.0), (55.0, 15.0, 85.0, 40.0)])   # le groupe : un seul cadre
        near = Shape(path=geom.Path([geom.rect(86.0, 15.0, 5.0, 5.0)]), tool=2)
        self.assertEqual(len(FX.logo_frames(poly, work.items + [near], {blank.id}, 2.0)), 2)   # découpés ensemble
        self.assertEqual(len(FX.logo_frames(poly, work.items + [near], {blank.id}, 0.0)), 3)

    def test_as_before_without_choice(self):
        from vectordrive.cam import fixture as FX
        doc, plate, work, blank, logo1, logo2 = plate_drawing()
        before = FX.layout([blank], plate.items, FX.Spec(per_blank=0, margin=1.0))
        pl = FX.layout([blank], plate.items, self.spec(''), logos=FX.engraving_items(doc))
        self.assertEqual(pl.count(), before.count())
        self.assertEqual(pl.count(), 60)
        self.assertEqual(pl.frames, [])

    def test_screws_in_the_skeleton_out_of_the_cut(self):
        from shapely.geometry import Point, box
        from vectordrive.cam import fixture as FX
        doc, plate, work, blank, logo1, logo2 = plate_drawing()
        pl = FX.layout([blank], plate.items, self.spec('squelette'), logos=FX.engraving_items(doc))
        holes = pl.blanks[0][1]
        cuts = [box(*f).buffer(2.0, join_style=2) for f, _n in pl.frames]
        self.assertEqual(len(cuts), 2)
        self.assertTrue(0 < len(holes) < 60)
        for h in holes:                                  # ni sous la gravure ni sous sa découpe, à la marge près
            self.assertFalse(any(c.distance(Point(h.x, h.y)) < 1.0 + h.diameter / 2 - 1e-9 for c in cuts), (h.x, h.y))
        self.assertIn((45.0, 25.0), {(h.x, h.y) for h in holes})            # entre les deux gravures

    def test_screws_in_each_engraving(self):
        from vectordrive.cam import fixture as FX
        doc, plate, work, blank, logo1, logo2 = plate_drawing()
        pl = FX.layout([blank], plate.items, self.spec('gravures'), logos=FX.engraving_items(doc))
        self.assertEqual([f for f, _n in pl.frames], [(10.0, 10.0, 30.0, 30.0), (55.0, 15.0, 85.0, 40.0)])
        (b1, h1), (b2, h2) = pl.blanks
        self.assertIs(b1, blank)
        self.assertTrue(all(10 < h.x < 30 and 10 < h.y < 30 for h in h1) and h1)
        self.assertTrue(all(55 < h.x < 85 and 15 < h.y < 40 for h in h2) and h2)
        pl2 = FX.layout([blank], plate.items, FX.Spec(
            per_blank=2, margin=1.0, screws_in='gravures'), logos=FX.engraving_items(doc))
        self.assertEqual([len(h) for _b, h in pl2.blanks], [2, 2])          # les vis par gravure
        self.assertEqual(pl2.bare(), [])

    def test_spec_kept_and_checked(self):
        from vectordrive.cam import fixture as FX
        s = FX.Spec.from_dict(dict(self.spec('gravures').to_dict(), cut_width=3.0))
        self.assertEqual((s.screws_in, s.cut_width), ('gravures', 3.0))
        self.assertEqual(FX.Spec.from_dict({'screws_in': 'ailleurs', 'cut_width': -1}).screws_in, '')
        self.assertEqual(FX.Spec.from_dict({'cut_width': -1}).cut_width, 0.0)

    def test_the_window_offers_the_choice(self):
        from vectordrive.cam import fixture as FX
        from vectordrive.ui.fixture_dialog import FixtureDialog
        doc, plate, work, blank, logo1, logo2 = plate_drawing()
        dlg = FixtureDialog(None, doc, FX.Spec(per_blank=0, margin=1.0), selection=[blank])
        self.addCleanup(dlg.deleteLater)
        self.assertEqual(dlg.placement.count(), 60)
        self.assertFalse(dlg.cut_width.isEnabled())
        dlg.screws_in.setCurrentIndex(dlg.screws_in.findData('gravures'))
        self.assertEqual(len(dlg.placement.frames), 2)
        self.assertIn('2 gravures', dlg.info.text())
        self.assertTrue(dlg.cut_width.isEnabled())
        self.assertEqual(dlg.spec().screws_in, 'gravures')
        dlg.screws_in.setCurrentIndex(dlg.screws_in.findData('squelette'))
        self.assertLess(dlg.placement.count(), 60)


if __name__ == '__main__':
    unittest.main()
