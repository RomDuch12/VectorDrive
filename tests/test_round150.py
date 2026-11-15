"""Round 150 : opérations de NeoDrive, trous — taraudage (fraise à
fileter), perçage à la fraise (hélice), ébavurage (outil conique) :
parcours réels et cycles notés pour les machines qui en ont."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def holes_doc(*circles):
    d = Document()
    d.plate = None
    for (x, y, r) in circles:
        d.add(Shape(path=geom.Path([geom.circle((x, y), r)]), tool=0))
    return d


def run(doc, kind, tool, **kw):
    s = model.CamSetup()
    s.tools = [tool]
    op = model.Operation(kind=kind, tool_id=tool.id, **kw)
    s.operations = [op]
    return S.compute(doc, s, op)


def winding(moves, cx, cy) -> float:
    """Somme des angles balayés (rad) par les avances autour de (cx, cy)."""
    total, prev = 0.0, None
    for m in moves:
        if m.kind != 'feed':
            continue
        a = math.atan2(m.y - cy, m.x - cx)
        if prev is not None and math.hypot(m.x - cx, m.y - cy) > 1e-6:
            total += (a - prev + math.pi) % (2 * math.pi) - math.pi
        prev = a
    return total


class TestThreads(unittest.TestCase):
    def test_table(self):
        self.assertEqual(model.THREADS['M4'], (4.0, 0.7, 3.3))
        self.assertEqual(model.THREADS['M6'][1], 1.0)

    def test_thread_milling_right_hand_climb(self):
        doc = holes_doc((10, 10, 1.65))                                   # avant-trou M4
        tool = model.CamTool(name='Fraise à fileter', diameter=2.5, number=3, cut_length=8)
        tp = run(doc, 'taraudage', tool, depth=6, thread='M4', climb=True)
        feeds = [m for m in tp.moves if m.kind == 'feed']
        radii = [math.hypot(m.x - 10, m.y - 10) for m in feeds]
        self.assertAlmostEqual(max(radii), 2.0 - 1.25, places=6)
        zs = [m.z for m in feeds]
        self.assertAlmostEqual(min(zs), -6.0)
        self.assertAlmostEqual(max(zs), 0.0)
        turns = winding(tp.moves, 10, 10) / (2 * math.pi)
        self.assertAlmostEqual(turns, 6 / 0.7, delta=0.05)                # sens trigo, pas 0,7
        self.assertEqual(tp.cycles, [{'kind': 'taraudage', 'x': 10, 'y': 10, 'depth': 6.0, 'thread': 'M4',
                                      'pitch': 0.7, 'left': False, 'climb': True}])
        self.assertFalse(tp.warnings)

    def test_left_and_conventional(self):
        doc = holes_doc((0, 0, 1.65))
        tool = model.CamTool(diameter=2.5)
        left = run(doc, 'taraudage', tool, depth=3, thread='M4', thread_left=True, climb=True)
        self.assertLess(winding(left.moves, 0, 0), 0)                     # filet à gauche : horaire en remontant
        conv = run(doc, 'taraudage', tool, depth=3, thread='M4', climb=False)
        feeds = [m for m in conv.moves if m.kind == 'feed']
        self.assertGreater(feeds[1].z, feeds[-2].z)                       # de haut en bas
        self.assertLess(winding(conv.moves, 0, 0), 0)                     # filet à droite descendant : horaire

    def test_tool_too_big(self):
        tp = run(holes_doc((0, 0, 1.25)), 'taraudage', model.CamTool(diameter=4), depth=3, thread='M3')
        self.assertTrue(any('trop grosse' in w for w in tp.warnings))
        self.assertFalse(tp.moves)


class TestBore(unittest.TestCase):
    def test_helix_bore(self):
        tool = model.CamTool(diameter=2, step_down=0.5)
        tp = run(holes_doc((5, 5, 3)), 'percage_fraise', tool, depth=2)
        feeds = [m for m in tp.moves if m.kind == 'feed']
        self.assertAlmostEqual(max(math.hypot(m.x - 5, m.y - 5) for m in feeds), 2.0, places=6)
        self.assertAlmostEqual(min(m.z for m in feeds), -2.0)
        self.assertGreater(winding(tp.moves, 5, 5) / (2 * math.pi), 2 / 0.5 + 0.9)   # hélice + tour au fond
        self.assertEqual(tp.cycles[0]['diameter'], 6)
        tp2 = run(holes_doc((5, 5, 3)), 'percage_fraise', tool, depth=2, hole_diameter=8)
        self.assertAlmostEqual(max(math.hypot(m.x - 5, m.y - 5) for m in tp2.moves if m.kind == 'feed'), 3.0,
                               places=6)

    def test_chamfer_depth(self):
        tool = model.CamTool(name='Chanfrein 90°', kind='conique', diameter=6, angle=90, tip=0)
        tp = run(holes_doc((0, 0, 1.65), (10, 0, 1.65)), 'chanfrein', tool, stock=0.2)
        self.assertEqual(len(tp.cycles), 2)
        self.assertAlmostEqual(tp.cycles[0]['depth'], 1.85, places=9)
        self.assertAlmostEqual(min(m.z for m in tp.moves), -1.85, places=9)
        bad = run(holes_doc((0, 0, 1.65)), 'chanfrein', model.CamTool(diameter=3), stock=0.2)
        self.assertTrue(bad.warnings)


class TestForm(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_thread_field(self):
        from vectordrive.ui.cam_panel import FieldsDialog, PRESETS
        self.assertIn('taraudage', PRESETS)
        o = model.Operation(kind='taraudage', thread='M6')
        d = FieldsDialog(None, 'Opération', o)
        d.show()
        combo = d.widgets['thread']
        self.assertEqual(combo.currentData(), 'M6')
        self.assertTrue(combo.isVisible())
        d.widgets['kind'].setCurrentIndex(d.widgets['kind'].findData('poche'))
        self.assertFalse(combo.isVisible())
        d.widgets['kind'].setCurrentIndex(d.widgets['kind'].findData('taraudage'))
        combo.setCurrentIndex(combo.findData('M8'))
        d.apply()
        self.assertEqual((o.kind, o.thread), ('taraudage', 'M8'))
        d.close()


if __name__ == '__main__':
    unittest.main()
