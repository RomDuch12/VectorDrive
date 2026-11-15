"""Round 990 : Décaler, retour de l'atelier — « Décalage : intersections => union auto ». Les contours décalés qui se
croisent sont réunis d'office (à chaque distance, pour un même outil) ; l'un dans l'autre, ils restent séparés ; la case
de la fenêtre est retenue."""
import os
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication  # noqa: E402

from vectordrive.core import geom, pathops  # noqa: E402
from vectordrive.core.document import Layer, Plate, Shape  # noqa: E402
from vectordrive.core.geom import Path  # noqa: E402
from vectordrive.ui.dialogs import OffsetDialog  # noqa: E402
from vectordrive.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])
KEYS = ('decalage/distance', 'decalage/jonction', 'decalage/garder', 'decalage/dernier', 'decalage/reunir')


def square(x, y, size, tool=0):
    return Shape(path=Path([geom.rect(x, y, size, size)]), tool=tool)


class Groups(unittest.TestCase):

    def test_crossing_touching_inside(self):
        a = Path([geom.rect(0, 0, 10, 10)])
        b = Path([geom.rect(9, 0, 10, 10)])                  # chevauche a
        c = Path([geom.rect(18, 0, 10, 10)])                 # chevauche b : même groupe, de proche en proche
        touching = Path([geom.rect(0, 10, 10, 10)])          # bord commun avec a : rien en commun
        frame = Path([geom.rect(100, 0, 50, 50)])
        letter = Path([geom.circle((125, 25), 5)])            # dans le cadre : séparés
        far = Path([geom.rect(300, 0, 5, 5)])
        self.assertEqual(pathops.crossing_groups([a, touching, b, frame, letter, c, far]), [[0, 2, 5]])

    def test_hole_counts(self):
        ring = pathops.normalize(Path([geom.rect(0, 0, 40, 40), geom.rect(10, 10, 20, 20)]))   # un trou au milieu
        in_hole = Path([geom.rect(15, 15, 10, 10)])
        across = Path([geom.rect(5, 15, 10, 10)])            # à cheval sur le bord du trou
        self.assertEqual(pathops.crossing_groups([ring, in_hole]), [])
        self.assertEqual(pathops.crossing_groups([ring, across]), [[0, 1]])
        self.assertEqual(pathops.crossing_groups([]), [])

    def test_inside_member_leaves_its_group(self):
        frame = Path([geom.rect(-1, -1, 102, 102)])
        letter = Path([geom.rect(-0.5, 39, 12, 12)])         # dans le cadre, tout près du bord
        logo = Path([geom.rect(-12.2, 39, 12, 12)])          # dehors : croise le cadre et la lettre
        self.assertEqual(pathops.crossing_groups([frame, letter, logo]), [[0, 2]])   # la réunion effacerait la lettre
        a, b = Path([geom.rect(0, 0, 10, 10)]), Path([geom.rect(5, 0, 10, 10)])
        self.assertEqual(pathops.crossing_groups([a, b], owners=['x', 'x']), [])    # deux morceaux d'un même tracé

    def test_regions_keep_the_contours(self):
        p = Path([geom.rect(0, 0, 40, 40), geom.rect(10, 10, 20, 20), geom.rect(15, 15, 10, 10), geom.rect(50, 0, 10, 10)])
        rs = pathops.regions(p)
        self.assertEqual([len(r.contours) for r in rs], [2, 1, 1])                 # le cadre et son trou, l'île, l'autre
        self.assertIs(rs[0].contours[0], p.contours[0])
        self.assertIs(rs[0].contours[1], p.contours[1])


class Offset(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.close()
        cls.win.deleteLater()

    def setUp(self):
        self.doc = self.win.canvas.doc
        self.layer = Layer(name='Plan 1')
        self.doc.layers[:] = [self.layer]
        self.doc.active = self.layer.id
        self.doc.plate = Plate(width=300.0, height=200.0)
        self.win._undo.clear()

    def tearDown(self):
        for k in KEYS:
            self.win.settings.remove(k)

    def run_offset(self, *items, distance=1.0, count=1, **more):
        self.layer.items[:] = list(items)
        self.win.canvas.select(list(items))
        v = {'distance': distance, 'join': 'round', 'count': count, 'keep': False, 'last_only': False}
        v.update(more)
        self.win.offset_selection(v)
        return list(self.layer.items)

    def test_neighbours_become_one_letter_in_frame_stays(self):
        frame = square(0, 0, 100)
        left, right = square(20, 20, 10), square(31, 20, 10)   # 1 mm d'écart : les décalages de 1 se croisent
        alone = square(70, 70, 10)
        out = self.run_offset(frame, left, right, alone)
        self.assertEqual(len(out), 3)
        boxes = sorted(tuple(round(v, 6) for v in it.path.bbox()) for it in out)
        self.assertEqual(boxes, [(-1, -1, 101, 101), (19, 19, 42, 31), (69, 69, 81, 81)])
        joined = next(it for it in out if round(it.path.bbox()[0]) == 19)
        self.assertEqual(len(joined.path.contours), 1)
        self.assertAlmostEqual(pathops.area(joined.path), pathops.area(pathops.union_all(
            [pathops.offset(left.path, 1.0), pathops.offset(right.path, 1.0)])), delta=0.01)   # arrondis : < 0,01 mm²
        self.assertIn('réunis en 1', self.win.statusBar().currentMessage())
        self.assertEqual(self.win.settings.value('decalage/reunir') in (True, 'true'), True)

    def test_unticked_keeps_each_offset(self):
        out = self.run_offset(square(20, 20, 10), square(31, 20, 10), union=False)
        self.assertEqual(len(out), 2)
        self.assertEqual(self.win.settings.value('decalage/reunir') in (False, 'false'), True)

    def test_each_distance_and_each_tool(self):
        out = self.run_offset(square(0, 0, 10), square(13, 0, 10), count=2)   # 3 mm : seuls les décalages de 2 se croisent
        self.assertEqual(len(out), 3)
        self.assertEqual(sorted(len(it.path.contours) for it in out), [1, 1, 1])
        self.assertEqual(sorted(round(it.path.bbox()[2] - it.path.bbox()[0], 6) for it in out), [12, 12, 27])
        out = self.run_offset(square(0, 0, 10, tool=1), square(11, 0, 10, tool=2))
        self.assertEqual(sorted(it.tool for it in out), [1, 2])               # deux outils : deux usinages

    def test_nothing_inside_the_frame_disappears(self):
        box = lambda it: tuple(round(v, 6) for v in it.path.bbox())                # noqa: E731
        out = self.run_offset(square(0, 0, 100), square(0.5, 40, 10), square(-11.2, 40, 10))
        self.assertEqual(sorted(box(it) for it in out), [(-12.2, -1, 101, 101), (-0.5, 39, 11.5, 51)])   # la lettre reste
        text = Shape(path=Path([geom.rect(-11.2, 60, 10, 10), geom.rect(40, 40, 10, 10)]))   # un texte : deux lettres
        out = self.run_offset(square(0, 0, 100), text)
        self.assertEqual(sorted(box(it) for it in out), [(-12.2, -1, 101, 101), (39, 39, 51, 51)])   # l'autre lettre reste
        self.assertIn('réunis en 1', self.win.statusBar().currentMessage())

    def test_inward_offsets_of_overlapping_shapes(self):
        out = self.run_offset(square(0, 0, 20), square(10, 0, 20), distance=-1.0)
        self.assertEqual(len(out), 1)
        self.assertEqual(tuple(round(v, 6) for v in out[0].path.bbox()), (1, 1, 29, 19))


class Dialog(unittest.TestCase):

    def test_box_and_values(self):
        d = OffsetDialog(None, 2.0, 'round', True, False)
        self.assertTrue(d.union.isChecked())
        self.assertTrue(d.values()['union'])
        d.union.setChecked(False)
        self.assertFalse(d.values()['union'])
        self.assertFalse(OffsetDialog(None, union=False).values()['union'])

    def test_window_passes_the_saved_choice(self):
        w = MainWindow()
        seen = {}
        try:
            sh = square(0, 0, 10)
            w.canvas.doc.add(sh)
            w.canvas.select([sh])
            w.settings.setValue('decalage/reunir', False)

            def fake_exec(dlg):
                seen['union'] = dlg.union.isChecked()
                return False
            with mock.patch.object(OffsetDialog, 'exec', fake_exec):
                w.offset_dialog()
            self.assertIs(seen['union'], False)
        finally:
            w.settings.remove('decalage/reunir')
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
