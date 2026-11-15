"""Round 715 : cadres de tolérancement (GD&T, d'après CADCraft) — chaîne
du cadre (lecture, composition, chaînes hostiles), mise en page, groupe qui
suit les similitudes, lecture DXF de TOLERANCE, dialogue et double-clic."""
import math
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import gdt
from vectordrive.core.geom import Affine

FRAME = '{\\Fgdt;j}%%v{\\Fgdt;n}0.1{\\Fgdt;m}%%vA%%vB^J2.5{\\Fgdt;p}'


class TestFrame(unittest.TestCase):
    def test_parse(self):
        rows = gdt.parse_frame(FRAME)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]), 4)
        self.assertEqual(rows[0][0], [('s', 'position')])
        self.assertEqual(rows[0][1], [('s', 'diameter'), ('t', '0.1'), ('s', 'mmc')])
        self.assertEqual(rows[0][3], [('t', 'B')])
        self.assertEqual(rows[1][0], [('t', '2.5'), ('s', 'projected')])
        self.assertEqual(gdt.parse_frame('%%c5\\PA\\{x\\}'), [[[('s', 'diameter'), ('t', '5')]],
                                                                [[('t', 'A{x}')]]])

    def test_compose(self):
        s = gdt.compose_frame([{'symbol': 'flatness', 'tol1': {'value': '0.05'}, 'tol2': None,
                                'datums': [{'letter': 'A', 'material': 'L'}]}], datum_id='B')
        self.assertEqual(s, '{\\Fgdt;c}%%v0.05%%v%%vA{\\Fgdt;l}^JB')
        rows = gdt.parse_frame(s)
        self.assertEqual(rows[0][3], [('t', 'A'), ('s', 'lmc')])
        self.assertEqual(rows[1][0], [('t', 'B')])
        self.assertEqual(gdt.parse_frame(gdt.compose_frame([{'tol1': {'value': '5%{}'}}]))[0][1],
                         [('t', '5%{}')])                                          # caractères spéciaux échappés

    def test_fields(self):
        f = {'symbol': 'position', 'diameter': True, 'value': '0.2', 'material': 'M', 'datum1': 'A',
             'datum2': 'B(M)', 'datum3': '', 'datum_id': 'C'}
        t = gdt.compose_fields(f)
        self.assertEqual(t, '{\\Fgdt;j}%%v{\\Fgdt;n}0.2{\\Fgdt;m}%%v%%vA%%vB{\\Fgdt;m}^JC')
        self.assertEqual(gdt.fields_of(t), f)
        self.assertNotEqual(gdt.compose_fields(gdt.fields_of(FRAME)), FRAME)      # deux lignes : pas un seul jeu de champs

    def test_hostile(self):
        huge = '%%v{\\Fgdt;j}' * 100000
        for s in ('{\\Fgdt;', '{\\Fgdt', '\\', '%%', '%', '{{{{', '}}}}', '^', '\\P\\P\\P', '{\\H', huge,
                  '\x00%%v￿', None):
            rows = gdt.parse_frame(s)
            self.assertTrue(len(rows) <= gdt.MAX_FRAME_ROWS and all(len(r) <= gdt.MAX_FRAME_CELLS for r in rows))
            lay = gdt.layout(s, float('nan'), float('inf'), lambda t, h: len(t) * h)
            self.assertTrue(all(math.isfinite(v) for p in lay['frame'] for q in p for v in q))

    def test_layout(self):
        lay = gdt.layout('{\\Fgdt;j}%%v0.1%%vA', 1.0, 0.5, lambda t, h: len(t) * h)
        self.assertEqual(len(lay['frame']), 6)                                     # 4 séparations, haut et bas
        self.assertEqual(len(lay['texts']), 2)
        ys = [q[1] for p in lay['frame'] for q in p]
        self.assertEqual((min(ys), max(ys)), (-1.0, 1.0))
        self.assertEqual(lay['width'], 2.0 + 4.0 + 2.0)                            # cases d'au moins une hauteur de ligne
        two = gdt.layout('{\\Fgdt;c}%%v0.05^J{\\Fgdt;j}%%v0.1%%vABC', 1.0, 0.5, lambda t, h: len(t) * h)
        tops = [p for p in two['frame'] if p[0][1] == p[1][1] == -1.0]
        self.assertEqual(len(tops), 2)                                             # bas de la 1re ligne + haut qui dépasse
        self.assertTrue(all(gdt.symbol_prims(k) for k in gdt.CODES))


class TestGroup(unittest.TestCase):
    spec = {'text': FRAME, 'insert': [10.0, 20.0], 'rotation': 0.0, 'height': 3.5, 'gap': None, 'font': 'Arial'}

    def test_group_follows(self):
        g = gdt.group(self.spec, tool=2)
        self.assertEqual(len(g.children), 3)
        self.assertTrue(g.children[0].path.contours and g.children[1].filled and g.children[2].filled)
        self.assertEqual({c.tool for c in g.children}, {2})
        x0, y0, x1, y1 = g.bbox()
        self.assertAlmostEqual(x0, 10.0, places=6)
        self.assertAlmostEqual(y1, 20.0 + 3.5, places=6)
        self.assertAlmostEqual(y0, 20.0 - 3 * 3.5, places=6)                     # deux lignes
        r = g.transformed(Affine.rotation(90.0) @ Affine.scaling(2.0))
        d = gdt.spec_of(r)
        self.assertAlmostEqual(d['rotation'], 90.0)
        self.assertAlmostEqual(d['height'], 7.0)
        self.assertAlmostEqual(d['insert'][0], -40.0)
        self.assertAlmostEqual(d['insert'][1], 20.0)
        b = gdt.group(d).bbox()
        for u, v in zip(b, r.bbox()):
            self.assertAlmostEqual(u, v, places=6)                                 # même dessin, recalculé
        self.assertIsNone(gdt.spec_of(g.transformed(Affine.scaling(-1.0, 1.0))))  # miroir : un dessin
        self.assertIsNone(gdt.spec_of(g.transformed(Affine.scaling(1.0, 2.0))))
        gdt.rebuild(g, {**self.spec, 'text': '{\\Fgdt;c}%%v0.05'})
        self.assertEqual(gdt.spec_of(g)['text'], '{\\Fgdt;c}%%v0.05')
        self.assertAlmostEqual(g.bbox()[1], 20.0 - 3.5, places=6)                 # une seule ligne


class TestDxf(unittest.TestCase):
    def test_read(self):
        import ezdxf
        from vectordrive.core.document import Group
        from vectordrive.io import dxf as VD
        doc = ezdxf.new('R2018', setup=True)
        doc.header['$INSUNITS'] = 5                                                # cm
        st = doc.dimstyles.get('Standard')
        st.dxf.dimtxt, st.dxf.dimgap, st.dxf.dimscale = 0.25, 0.1, 2.0
        msp = doc.modelspace()
        msp.add_line((0, 0), (10, 0))
        msp.new_entity('TOLERANCE', dxfattribs={'insert': (1, 2), 'content': FRAME, 'x_axis_vector': (0, 1, 0),
                                                'layer': 'cotes'})
        msp.new_entity('TOLERANCE', dxfattribs={'insert': (0, 0), 'content': '%%v'})
        doc.layers.add('cache').off()
        msp.new_entity('TOLERANCE', dxfattribs={'insert': (0, 0), 'content': FRAME, 'layer': 'cache'})
        p = os.path.join(tempfile.mkdtemp(), 'gdt.dxf')
        doc.saveas(p)
        r = VD.read(p)
        frames = [it for L in r.layers for it in L.items if isinstance(it, Group) and gdt.spec_of(it)]
        self.assertEqual(len(frames), 1)
        d = gdt.spec_of(frames[0])
        self.assertEqual(d['text'], FRAME)
        self.assertAlmostEqual(d['height'], 5.0)                                  # 0,25 × 2 cm
        self.assertAlmostEqual(d['gap'], 2.0)
        self.assertAlmostEqual(d['rotation'], 90.0)
        self.assertAlmostEqual(d['insert'][0], 10.0)
        self.assertAlmostEqual(d['insert'][1], 20.0)
        self.assertIn('1 cadre(s) de tolérancement (TOLERANCE) repris', r.report)
        self.assertFalse([m for m in r.report if m.startswith('TOLERANCE')])


class TestDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def test_create_edit_undo(self):
        w, c = self.w, self.w.canvas
        n = len(c.doc.active_layer.items)
        g = w.gdt_frame(params={'symbol': 'perpendicularity', 'value': '0.02', 'datum1': 'A', 'height': 3.5})
        self.assertEqual(len(c.doc.active_layer.items), n + 1)
        self.assertEqual(gdt.spec_of(g)['text'], '{\\Fgdt;b}%%v0.02%%v%%vA')
        bb = g.bbox()
        cx, cy = w._view_center()
        self.assertAlmostEqual((bb[0] + bb[2]) / 2, cx, places=6)                # au centre de la vue
        self.assertAlmostEqual((bb[1] + bb[3]) / 2, cy, places=6)
        ins = gdt.spec_of(g)['insert']
        w.gdt_frame(g, params={'symbol': 'position', 'diameter': True, 'value': '0.1', 'material': 'M',
                               'datum1': 'A', 'datum2': 'B', 'height': 5.0})
        d = gdt.spec_of(g)
        self.assertEqual(d['text'], '{\\Fgdt;j}%%v{\\Fgdt;n}0.1{\\Fgdt;m}%%v%%vA%%vB')
        self.assertEqual((d['insert'], d['height']), (ins, 5.0))                  # même place, nouvelle hauteur
        w.undo()
        g = next(it for it in c.doc.active_layer.items if gdt.spec_of(it))
        self.assertEqual(gdt.spec_of(g)['text'], '{\\Fgdt;b}%%v0.02%%v%%vA')
        two = gdt.group({'text': FRAME, 'insert': [0, 0], 'rotation': 0, 'height': 2.5, 'gap': None,
                         'font': 'Arial'})
        c.doc.add(two)
        w.gdt_frame(two, params={'text': FRAME + '^JD', 'height': 2.5})           # plusieurs lignes : par la chaîne
        self.assertEqual(gdt.spec_of(two)['text'], FRAME + '^JD')
        with mock.patch.object(w, 'gdt_frame') as ed:
            w._item_double_clicked(two)
            ed.assert_called_once_with(two)

    def test_ribbon_icon(self):
        from vectordrive.ui import icons
        self.assertIn('gdt', icons.ICONS)
        a = self.w.A['gdt_frame']
        self.assertFalse(a.icon().isNull())
        self.assertTrue(a.toolTip())


if __name__ == '__main__':
    unittest.main()
