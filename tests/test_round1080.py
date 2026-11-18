"""Round 1080 : l'assistant IA (et le serveur MCP) savent faire la courbe lisse et l'emporte-pièce (round 1079) —
outils `smooth_curve` et `punch`, un pas d'annulation chacun, refus sans pas."""
import json
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1080.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Group, Layer, Shape, Text  # noqa: E402
from vectordrive.core.geom import Path  # noqa: E402

BEFORE = 'avant : l\'assistant ne sait ni lisser un contour ni retirer un morceau à l\'emporte-pièce'


def length(path) -> float:
    return sum(s.length() for c in path.contours for s in c.segments)


class Assistant(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.agent.tools import ToolSet
        self.w = MainWindow()
        self.addCleanup(self.clean)
        self.tools = ToolSet(self.w)
        self.assertIn('punch', self.tools.names(), BEFORE)

    def clean(self):
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()

    def call(self, name, **args):
        return json.loads(self.tools.call(name, args)[0]['text'])

    def refused(self, name, **args):
        from vectordrive.agent.protocol import ToolError
        steps = len(self.w._undo)
        with self.assertRaises(ToolError) as cm:
            self.tools.call(name, args)
        self.assertEqual(len(self.w._undo), steps, 'un refus ne laisse pas de pas d\'annulation')
        return str(cm.exception)

    def add(self, contour, layer=None, **kw):
        s = Shape(path=Path([contour]), tool=0, **kw)
        self.w.canvas.doc.add(s, layer)
        return s

    def items(self):
        return [it for L in self.w.canvas.doc.layers for it in L.items]

    def test_listed_with_schemas(self):
        specs = {s['name']: s for s in self.tools.specs()}
        for name in ('smooth_curve', 'punch'):
            self.assertEqual(specs[name]['inputSchema']['type'], 'object')
            self.assertFalse(specs[name]['annotations']['readOnlyHint'])
            self.assertTrue(specs[name]['description'])
        self.assertEqual(specs['punch']['inputSchema']['properties']['shape']['enum'],
                         ['segment', 'rectangle', 'circle'])
        self.assertEqual(specs['smooth_curve']['inputSchema']['required'], ['ids', 'length'])

    def test_smooth_curve_one_undo_step_same_id(self):
        zig = geom.polyline([(k * 1.0, 0.2 if k % 2 else -0.2) for k in range(41)])
        s = self.add(zig)
        steps = len(self.w._undo)
        out = self.call('smooth_curve', ids=[s.id], length=8.0, tolerance=0.005)
        self.assertEqual(out['ids'], [s.id])                                 # le modèle garde son identifiant
        self.assertTrue(0.15 < out['max_deviation'] < 0.45, out)
        self.assertLess(out['segments'], 40)
        self.assertEqual(len(self.w._undo), steps + 1)
        self.assertIs(self.items()[-1], s)                                   # sur place
        self.assertEqual([x.id for x in self.w.canvas.selection], [s.id])
        self.w.undo()
        self.assertEqual(self.items()[-1].path.segment_count(), 40)

    def test_smooth_curve_refusals(self):
        s = self.add(geom.rect(0, 0, 10, 10))
        self.assertIn('greater than 0', self.refused('smooth_curve', ids=[s.id], length=0))
        self.assertIn('sharpness', self.refused('smooth_curve', ids=[s.id], length=2, sharpness=9))
        self.assertIn('tolerance', self.refused('smooth_curve', ids=[s.id], length=2, tolerance=5))
        t = Text(text='A')
        self.w.canvas.doc.add(t)
        self.assertIn('not a shape', self.refused('smooth_curve', ids=[t.id], length=2))
        self.assertIn('at least 0.05', self.refused('smooth_curve', ids=[s.id], length=0.01))
        big = self.add(geom.circle((0, 0), 500.0))
        self.assertIn('too small', self.refused('smooth_curve', ids=[big.id], length=0.1))
        two = self.add(geom.polyline([(0, 0), (5, 0)]))
        self.assertIn('nothing to smooth', self.refused('smooth_curve', ids=[two.id], length=2))
        s.locked = True
        self.assertIn('locked', self.refused('smooth_curve', ids=[s.id], length=2))

    def test_punch_segment_x_mm_one_undo_step(self):
        s = self.add(geom.polyline([(0, 0), (100, 0)]))
        steps = len(self.w._undo)
        out = self.call('punch', shape='segment', x=40, y=0.5, length=10)
        self.assertEqual(out, {'changed_ids': [s.id], 'removed_ids': []})
        self.assertEqual(len(self.w._undo), steps + 1)
        self.assertAlmostEqual(length(s.path), 90.0, places=6)
        self.assertEqual(len(s.path.contours), 2)
        self.assertIn('within reach', self.refused('punch', shape='segment', x=40, y=5, length=10))
        out = self.call('punch', shape='segment', x=80, y=5, length=4, reach=6)   # plus loin, avec reach
        self.assertAlmostEqual(length(s.path), 86.0, places=6)
        self.w.undo()
        self.w.undo()
        self.assertAlmostEqual(length(self.items()[-1].path), 100.0, places=6)

    def test_punch_circle_rectangle_ids_and_locks(self):
        a = self.add(geom.polyline([(0, 0), (100, 0)]))
        b = self.add(geom.polyline([(0, 2), (100, 2)]))
        self.call('punch', shape='circle', x=50, y=1, diameter=10, ids=[b.id])   # seulement b
        self.assertAlmostEqual(length(a.path), 100.0, places=6)
        self.assertLess(length(b.path), 100.0)
        out = self.call('punch', shape='rectangle', x=20, y=1, width=6, height=10)   # sans ids : tout
        self.assertEqual(sorted(out['changed_ids']), sorted([a.id, b.id]))
        self.assertIn('does not use: width', self.refused('punch', shape='circle', x=0, y=0, diameter=2, width=3))
        a.visible = False
        self.assertIn('none of these', self.refused('punch', shape='circle', x=20, y=0, diameter=4, ids=[a.id]))
        a.visible = True
        self.assertAlmostEqual(length(a.path), 94.0, places=5)
        self.assertIn('needs: diameter', self.refused('punch', shape='circle', x=0, y=0))
        self.assertIn('shape', self.refused('punch', shape='star', x=0, y=0))
        self.assertIn('nothing', self.refused('punch', shape='circle', x=50, y=80, diameter=4))
        L2 = Layer(name='verrou', locked=True)
        self.w.canvas.doc.layers.append(L2)
        c = self.add(geom.polyline([(0, 50), (100, 50)]), L2)
        self.assertIn('nothing', self.refused('punch', shape='circle', x=50, y=50, diameter=4))   # calque verrouillé
        self.assertIn('locked', self.refused('punch', shape='circle', x=50, y=50, diameter=4, ids=[c.id]))
        self.assertAlmostEqual(length(c.path), 100.0, places=6)

    def test_punch_inside_a_group(self):
        g = Group(children=[Shape(path=Path([geom.polyline([(0, 0), (4, 0)])]), tool=0),
                            Shape(path=Path([geom.polyline([(0, 30), (40, 30)])]), tool=0)])
        self.w.canvas.doc.add(g)
        first = g.children[0].id
        out = self.call('punch', shape='circle', x=2, y=0, diameter=10, ids=[g.id])
        self.assertEqual(out, {'changed_ids': [], 'removed_ids': [first]})
        self.assertEqual(len(g.children), 1)                                 # la feuille vidée quitte son groupe
        zig = Shape(path=Path([geom.polyline([(k * 1.0, 0.2 if k % 2 else -0.2) for k in range(41)])]), tool=0)
        g.children.append(zig)
        out = self.call('smooth_curve', ids=[g.id], length=8.0)             # un groupe : ses formes lissées
        self.assertEqual(out['ids'], [g.id])
        self.assertLess(zig.path.segment_count(), 40)

    def test_the_canvas_tool_still_uses_the_selection(self):
        a = self.add(geom.polyline([(0, 0), (100, 0)]))
        b = self.add(geom.polyline([(0, 1), (100, 1)]))
        self.w.canvas.selection = [b]
        spec = dict(self.w.PUNCHOUT_DEFAULT, kind='cercle', diameter=10.0)
        self.assertEqual(self.w.canvas.punch_at((50, 0.5), spec), 1)
        self.assertAlmostEqual(length(a.path), 100.0, places=6)

    def test_the_eraser_follows_the_same_rules(self):
        c = self.w.canvas
        c.selection = []
        g = Group(children=[Shape(path=Path([geom.polyline([(0, 0), (1, 0)])]), tool=0),
                            Shape(path=Path([geom.polyline([(0, 30), (40, 30)])]), tool=0)])
        c.doc.add(g)
        self.assertEqual(c.erase([(0.5, 0)], 3.0), 1)
        self.assertEqual(len(g.children), 1)                                 # gommée en entier : hors du groupe
        hidden = self.add(geom.polyline([(0, 60), (100, 60)]))
        hidden.visible = False
        self.assertEqual(c.erase([(50, 60)], 3.0), 0)                        # un objet caché : intact
        L2 = Layer(name='verrou', locked=True)
        c.doc.layers.append(L2)
        self.add(geom.polyline([(0, 90), (100, 90)]), L2)
        self.assertEqual(c.erase([(50, 90)], 3.0), 0)                        # un calque verrouillé : intact
        free = self.add(geom.polyline([(0, 120), (100, 120)]))
        self.assertEqual(c.erase([(50, 120)], 3.0), 1)
        self.assertLess(length(free.path), 100.0)


if __name__ == '__main__':
    unittest.main()
