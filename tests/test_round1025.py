"""Round 1025 : demande du 14/11 — plaques de reprise : les bruts posés sur le dessin de la plaque, percés et taraudés
aux trous de la plaque qu'ils couvrent, pour y être vissés (« programmes auto de taraudage bruts personnalisable une
fois les pièces placées sur le dessin »)."""
import json
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1025.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication, QMenu  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Group, Layer, Shape  # noqa: E402

CORNERS = [(10.0, 10.0), (50.0, 10.0), (10.0, 30.0), (50.0, 30.0)]


def circle(x, y, d):
    return Shape(path=geom.Path([geom.circle((x, y), d / 2)]), tool=0)


def drawing():
    """Une plaque d'essai percée Ø 3,2 tous les 20 mm (10 × 10), un trou Ø 14 et un trou dessiné deux fois ; deux bruts
    (50 × 30 sur six trous, 8 × 8 entre les trous), une gravure dans le premier et un cercle à part."""
    plate = Layer(name='Plaque')
    grid = [circle(10.0 + 20 * i, 10.0 + 20 * j, 3.2) for i in range(10) for j in range(10)]
    plate.items = [Group(children=grid + [circle(100.0, 100.0, 14.0)]), circle(10.0, 10.0, 3.2)]
    blanks = Layer(name='Bruts')
    a = Shape(path=geom.Path([geom.rect(5.0, 5.0, 50.0, 30.0)]), tool=1)
    b = Shape(path=geom.Path([geom.rect(120.0, 120.0, 8.0, 8.0)]), tool=1)
    engraving = Shape(path=geom.Path([geom.rect(20.0, 15.0, 10.0, 5.0)]), tool=2)
    blanks.items = [a, b, engraving, circle(160.0, 20.0, 6.0)]
    doc = Document(layers=[plate, blanks])
    return doc, plate, blanks, a, b, engraving


def at(holes):
    return [(round(h.x, 3), round(h.y, 3)) for h in holes]


class Model(unittest.TestCase):

    def test_thread_through_the_plate_holes(self):
        from vectordrive.cam import fixture as FX
        # depuis 0.915.0 : ajustement juste (une M4 passe dans un Ø 4, une M2 dans un Ø 2)
        self.assertEqual([FX.thread_for(d) for d in (3.2, 4.0, 4.3, 6.4, 9.0, 2.0, 1.5)],
                         ['M3', 'M4', 'M4', 'M6', 'M8', 'M2', ''])

    def test_plate_holes_and_blanks(self):
        from vectordrive.cam import fixture as FX
        doc, plate, blanks, a, b, _eng = drawing()
        self.assertEqual(len(FX.plate_holes(plate.items, 2.5, 9.0)), 100)   # Ø 14 à part, le doublon une fois
        self.assertEqual(len(FX.plate_holes(plate.items, 2.5, 20.0)), 101)
        self.assertEqual(FX.blanks_of(blanks.items), [a, b])                 # ni la gravure du brut, ni le cercle

    def test_four_screws_far_apart_with_margin(self):
        from vectordrive.cam import fixture as FX
        doc, plate, blanks, a, b, _eng = drawing()
        pl = FX.layout([a, b], plate.items, FX.Spec())
        self.assertEqual(pl.thread, 'M3')
        (ba, ha), (bb, hb) = pl.blanks
        self.assertIs(ba, a)
        self.assertEqual(sorted(at(ha)), sorted(CORNERS))                    # les quatre coins des six trous couverts
        self.assertEqual((hb, pl.empty(), pl.count()), ([], [b], 4))
        self.assertEqual(len(FX.layout([a], plate.items, FX.Spec(per_blank=0)).blanks[0][1]), 6)
        self.assertEqual(FX.layout([a], plate.items, FX.Spec(margin=6.0)).count(), 0)   # trop près du bord
        self.assertEqual(at(FX.layout([a], plate.items, FX.Spec(per_blank=1)).blanks[0][1]), [(10.0, 10.0)])

    def test_blank_turned_over_for_tapping(self):
        from vectordrive.cam import fixture as FX
        doc, plate, blanks, a, b, _eng = drawing()
        got = FX.layout([a], plate.items, FX.Spec(per_blank=1, mirror='x')).blanks[0][1]
        self.assertEqual(at(got), [(50.0, 10.0)])                            # miroir autour du centre du brut (x 30)
        got = FX.layout([a], plate.items, FX.Spec(per_blank=1, mirror='y')).blanks[0][1]
        self.assertEqual(at(got), [(10.0, 30.0)])

    def test_spec_kept_whatever_was_stored(self):
        from vectordrive.cam import fixture as FX
        s = FX.Spec.from_dict({'per_blank': -2, 'mirror': 'z', 'margin': 'abc', 'depth': 8, 'inconnu': 1})
        self.assertEqual((s.per_blank, s.mirror, s.margin, s.depth), (0, '', 3.0, 8.0))
        self.assertEqual(FX.Spec.from_dict(FX.Spec(thread='M4').to_dict()).thread, 'M4')
        self.assertEqual(FX.Spec.from_dict({'thread': None}).thread, '')     # ni « None » ni filetage inconnu
        self.assertEqual(FX.thread_for(2.7), 'M2.5')

    def test_round_blanks_frames_and_blanks_drawn_together(self):
        from vectordrive.cam import fixture as FX
        doc, plate, blanks, a, b, eng = drawing()
        disc = circle(150.0, 150.0, 60.0)                                    # un brut rond (médaille)
        outline = Shape(path=geom.Path([geom.rect(0.0, 0.0, 200.0, 200.0)]), tool=0)
        self.assertEqual(FX.blanks_of([a, disc, circle(1.0, 1.0, 6.0)]), [a, disc])
        self.assertEqual(FX.blanks_of([outline, a, b]), [outline])            # sans le cadre des trous : la plaque
        frame = FX.frame_of(FX.plate_holes(plate.items, 2.5, 9.0))
        self.assertEqual(FX.blanks_of([outline, a, b, eng], frame=frame), [a, b])
        self.assertEqual(FX.blanks_of([outline], frame=frame), [outline])     # seul : un grand brut sur tous les trous
        everything = plate.items + [outline, a, b, eng]                      # tout choisi (Ctrl+A)
        self.assertEqual(FX.find_blanks(everything, plate.items, 2.5, 9.0), [a, b])
        self.assertEqual(FX.skip_for(everything, [a, b]), set())             # la plaque garde ses trous
        part = Group(children=[a, circle(30.0, 20.0, 6.0)])                  # un brut et son alésage, groupés
        self.assertEqual(FX.skip_for([part], [a]), {part.children[1].id})
        bores = Group(children=[b] + [circle(121.0 + 2 * k, 124.0, 1.0) for k in range(3)])
        on_plate = plate.items + [bores]                                     # brut groupé avec ses perçages, sur la plaque
        self.assertNotIn(b.id, FX.plate_parts(on_plate, 0.5, 9.0))
        self.assertIn(b, FX.find_blanks(on_plate + [a], on_plate, 0.5, 9.0))
        logo = Shape(path=geom.Path([geom.rect(90.0, 95.0, 20.0, 10.0)]), tool=2)   # entre les trous
        self.assertEqual(FX.find_blanks([outline, logo], plate.items, 2.5, 9.0), [outline])   # un grand brut gravé
        twin = Shape(path=geom.Path([geom.rect(5.0, 5.0, 50.0, 30.0), geom.rect(5.0, 45.0, 50.0, 30.0)]), tool=1)
        pl = FX.layout([twin], plate.items, FX.Spec())
        self.assertEqual([len(h) for _b, h in pl.blanks], [4, 4])            # deux contours : deux bruts
        self.assertEqual(FX.layout([disc], plate.items, FX.Spec()).count(), 4)

    def test_hidden_holes_and_the_blanks_own_circles_left_out(self):
        from vectordrive.cam import fixture as FX
        doc, plate, blanks, a, b, eng = drawing()
        plate.items[0].visible = False                                       # la grille cachée
        self.assertEqual(len(FX.plate_holes(plate.items, 2.5, 9.0)), 1)
        plate.items[0].visible = True
        bore = circle(30.0, 20.0, 6.0)                                       # l'alésage du brut, sur le calque de la plaque
        plate.items.append(bore)
        got = FX.layout([a], plate.items, FX.Spec(per_blank=0), skip={bore.id})
        self.assertNotIn((30.0, 20.0), at(got.blanks[0][1]))
        got = FX.layout([a], plate.items, FX.Spec(per_blank=0, common_only=False))   # 0.915.0 : tous les Ø
        self.assertIn((30.0, 20.0), at(got.blanks[0][1]))


class Panel(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()

        def close():
            self.w.modified = False
            for t in getattr(self.w, 'docs', []):
                t.modified = False
            self.w.settings.remove('fao/plaque_reprise')
            self.w.close()
            app.processEvents()
        self.addCleanup(close)

    def test_holes_and_operations_added(self):
        from vectordrive.cam import fixture as FX
        from vectordrive.cam import model
        from vectordrive.core import holes
        p = self.w.cam_panel
        doc, plate, blanks, a, b, _eng = drawing()
        p.doc.layers.extend([plate, blanks])
        before = len(p.setup().operations)
        pl = p.fixture_holes(exec_dialog=False, spec=FX.Spec(depth=5.0, auto_depth=False), plate_layer=plate,
                             blanks=[a, b])
        self.assertEqual(pl.count(), 4)
        layer = p.doc.layers[-1]
        self.assertEqual(layer.name, 'Fixation des bruts M3')
        self.assertEqual(len(layer.items), 4)
        self.assertTrue(all(holes.is_hole(it) for it in layer.items))       # trous TypeEdit, au foret de la M3
        self.assertEqual(sorted(at([FX.Hole(*holes.circle_of(it)[:2], 0) for it in layer.items])), sorted(CORNERS))
        self.assertAlmostEqual(holes.circle_of(layer.items[0])[2] * 2, model.THREADS['M3'][2], places=3)
        ops = p.setup().operations[before:]
        self.assertEqual(len(ops), 1)                                        # 0.915.0 : sous M6, une seule opération
        self.assertEqual((ops[0].kind, ops[0].thread, ops[0].depth), ('taraudage', 'M3', 5.0))
        self.assertEqual(sorted(ops[0].items), sorted(it.id for it in layer.items))
        self.assertEqual(json.loads(self.w.settings.value('fao/plaque_reprise'))['depth'], 5.0)
        self.assertIsNone(p.fixture_holes(exec_dialog=False, spec=FX.Spec(), plate_layer=plate, blanks=[b]))
        self.assertTrue(layer.extra.get(FX.MADE_KEY))                        # la fois suivante : jamais la plaque
        from vectordrive.ui.fixture_dialog import FixtureDialog
        layer.items += [circle(500.0 + 10 * k, 0.0, 3.3) for k in range(200)]   # plus de trous que la plaque
        dlg = FixtureDialog(None, p.doc, FX.Spec())
        self.addCleanup(dlg.deleteLater)
        self.assertIs(dlg.plate_layer(), plate)

    def test_dialog_counts_follow_the_settings(self):
        from vectordrive.cam import fixture as FX
        from vectordrive.ui.fixture_dialog import FixtureDialog
        doc, plate, blanks, a, b, eng = drawing()
        dlg = FixtureDialog(None, doc, FX.Spec(), selection=[a, b, eng])
        self.addCleanup(dlg.deleteLater)
        self.assertIs(dlg.plate_layer(), plate)                               # le calque qui a le plus de trous
        self.assertEqual(dlg.blank_src.currentData(), '')                     # les formes choisies : deux bruts
        self.assertEqual(dlg.blanks(), [a, b])
        self.assertIn('4', dlg.info.text())
        self.assertTrue(dlg.ok.isEnabled())
        dlg.per_blank.setValue(0)
        self.assertEqual(dlg.placement.count(), 6)
        dlg.margin.setValue(6.0)
        self.assertFalse(dlg.ok.isEnabled())                                  # plus aucun trou : rien à faire
        dlg.blank_src.setCurrentIndex(dlg.blank_src.findData(blanks.id))
        self.assertEqual(dlg.blanks(), [a, b])
        self.assertEqual(dlg.spec().margin, 6.0)

    def test_in_the_setup_menu(self):
        seen = []

        class Menu(QMenu):                                                    # le menu montré : ses commandes lues
            def exec(self, *_a):
                seen.extend(x.text() for x in self.actions())
        with mock.patch('PySide6.QtWidgets.QMenu', Menu):
            self.w.cam_panel.setup_menu()
        self.assertIn('Plaque de reprise : trous de fixation des bruts…', seen)


if __name__ == '__main__':
    unittest.main()
