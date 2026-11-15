"""Round 716 : cotes d'inspection (comme DIMINSPECT : cadre à bouts ronds
ou pointus, libellé, taux) et Espacer les cotes (comme DIMSPACE), d'après
CADCraft."""
import copy
import json
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import dims as D
from vectordrive.core.geom import bbox_union


def _dim(kind='libre', pts=((0, 0), (60, 0)), offset=8.0, **style):
    st = D.DimStyle()
    for k, v in style.items():
        setattr(st, k, v)
    return D.Dim(kind, list(pts), offset, st)


def _inside(inner, outer, tol=1e-9):
    return (outer[0] - tol <= inner[0] and outer[1] - tol <= inner[1] and inner[2] <= outer[2] + tol
            and inner[3] <= outer[3] + tol)


class TestInspection(unittest.TestCase):
    def test_frames(self):
        plain = D.build(_dim())
        for shape in ('ronde', 'angulaire'):
            lines, _f, txt = D.build(_dim(inspect=shape, inspect_label='A', inspect_rate='100%'))
            extra = lines.contours[len(plain[0].contours):]
            self.assertEqual(len(extra), 3)                                          # deux séparations et le cadre
            frame = extra[-1]
            self.assertTrue(frame.closed)
            self.assertTrue(_inside(txt.bbox(), frame.bbox()))
            self.assertGreater(frame.bbox()[1], 0.0)                                # au-dessus de la ligne de cote
            self.assertGreater(len(txt.contours), len(plain[2].contours))           # libellé et taux écrits
        lines, _f, txt = D.build(_dim(inspect='ronde'))
        self.assertEqual(len(lines.contours), len(plain[0].contours) + 1)           # valeur seule : le cadre
        lines, _f, txt = D.build(_dim(inspect='sans', inspect_label='B', inspect_rate='50%'))
        self.assertEqual(len(lines.contours), len(plain[0].contours))               # sans cadre
        self.assertGreater(len(txt.contours), len(plain[2].contours))
        lines, _f, _t = D.build(_dim(inspect='inconnue'))
        self.assertEqual(len(lines.contours), len(plain[0].contours))

    def test_in_line_angular_radial(self):
        d = _dim(inspect='ronde', inspect_rate='100%', text_offset=0.0)
        lines = D.build(d)[0]
        frame = lines.contours[-1]
        fx0, _y0, fx1, _y1 = frame.bbox()
        on_line = [c for c in lines.contours if c.bbox()[1] == c.bbox()[3] == 8.0]
        self.assertEqual(len(on_line), 2)                                           # ligne coupée par le cadre
        self.assertTrue(all(c.bbox()[2] < fx0 or c.bbox()[0] > fx1 for c in on_line))
        for kind, pts, off in (('angulaire', ((20, 0), (0, 0), (15, 15)), 18.0), ('radiale', ((0, 0), (8, 6)), 10.0)):
            lines, _f, txt = D.build(_dim(kind, pts, off, inspect='angulaire', inspect_rate='10%'))
            self.assertTrue(_inside(txt.bbox(), lines.contours[-1].bbox(), 1e-6))
        self.assertEqual(D.build(_dim('ordonnee', ((0, 0), (10, 5), (10, 20)), inspect='ronde'))[0].contours,
                         D.build(_dim('ordonnee', ((0, 0), (10, 5), (10, 20))))[0].contours)

    def test_kept(self):
        d = _dim(inspect='angulaire', inspect_label='A', inspect_rate='25%')
        back = D.from_dict(json.loads(json.dumps(D.to_dict(d))))
        self.assertEqual((back.style.inspect, back.style.inspect_label, back.style.inspect_rate),
                         ('angulaire', 'A', '25%'))
        from vectordrive.core.geom import Affine
        g = D.group(d).transformed(Affine.rotation(30.0))
        self.assertEqual(D.dim_of(g).style.inspect, 'angulaire')


class TestSpace(unittest.TestCase):
    def test_space(self):
        ds = [D.Dim('horizontale', [(0, 0), (70, 3)], 9.0), D.Dim('horizontale', [(0, 0), (40, 3)], 6.0),
              D.Dim('libre', [(120, 0), (0, 0)], -30.0), D.Dim('horizontale', [(0, 0), (100, 3)], 10.5),
              D.Dim('verticale', [(0, 0), (0, 50)], 5.0)]
        self.assertEqual(D.space(ds, 7.0), 3)
        self.assertEqual([d.offset for d in ds], [13.0, 6.0, -27.0, 20.0, 5.0])     # verticale : laissée
        self.assertEqual(D.space(ds, 0.0), 3)
        self.assertEqual([d.offset for d in ds], [6.0, 6.0, -6.0, 6.0, 5.0])        # toutes sur la ligne de base
        below = [D.Dim('horizontale', [(0, 10), (30, 10)], -4.0), D.Dim('horizontale', [(0, 12), (60, 12)], -5.0)]
        D.space(below, 5.0)
        self.assertEqual([d.offset for d in below], [-4.0, -11.0])                  # du côté de la base
        self.assertEqual(D.space(below[:1], 5.0), 0)
        self.assertEqual(D.space([below[0], D.Dim('angulaire', [(1, 0), (0, 0), (0, 1)], 5.0)], 5.0), 0)


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

    def put(self, *dims):
        gs = [D.group(d) for d in dims]
        for g in gs:
            self.w.canvas.doc.add(g)
        return gs

    def test_inspect_and_space(self):
        w, c = self.w, self.w.canvas
        g1, g2 = self.put(_dim(pts=((0, 0), (40, 0)), offset=6.0), _dim(pts=((0, 0), (80, 0)), offset=7.0))
        c.select([g1, g2])
        self.assertEqual(w.dim_inspect({'inspect': 'ronde', 'inspect_label': 'A', 'inspect_rate': '100%'}), 2)
        self.assertEqual({D.dim_of(g).style.inspect_rate for g in (g1, g2)}, {'100%'})
        self.assertEqual(w.dim_space({'spacing': 8.0}), 1)
        self.assertEqual(D.dim_of(g2).offset, 14.0)
        w.undo()
        g2 = next(it for it in c.doc.active_layer.items if D.dim_of(it) and D.dim_of(it).points[1][0] == 80)
        self.assertEqual(D.dim_of(g2).offset, 7.0)
        self.assertEqual(D.dim_of(g2).style.inspect, 'ronde')
        c.select([g2])
        w.dim_inspect({'inspect': ''})
        self.assertEqual((D.dim_of(g2).style.inspect, D.dim_of(g2).style.inspect_rate), ('', ''))   # retirée
        with mock.patch('vectordrive.ui.main_window.QMessageBox.information') as mb:
            c.select([g2])
            self.assertEqual(w.dim_space({'spacing': 8.0}), 0)                       # une seule cote
            c.select([])
            self.assertEqual(w.dim_inspect({'inspect': 'ronde'}), 0)
            self.assertEqual(mb.call_count, 2)

    def test_dialog_and_style(self):
        from vectordrive.ui import dim_dialog as DD
        d = _dim(inspect='ronde', inspect_rate='100%')
        dlg = DD.DimDialog(self.w, d.style, dim=d)
        self.assertIn('inspect', dlg.widgets)
        dlg.set_field('inspect_label', 'Z')
        self.assertEqual(dlg.value().style.inspect_label, 'Z')
        dlg.set_field('inspect', '')
        self.assertFalse(dlg.widgets['inspect_rate'].isEnabled())
        self.assertNotIn('inspect', DD.DimDialog(self.w, D.DimStyle()).widgets)    # options des prochaines cotes
        self.assertNotIn('inspect', DD.DimDialog(self.w, D.DimStyle(), dim=_dim('repere', ((0, 0), (5, 5)))).widgets)
        DD.save_style(self.w.settings, copy.deepcopy(d.style))
        self.assertEqual(DD.default_style(self.w.settings).inspect, '')            # propre à la cote

    def test_ribbon_icons(self):
        from vectordrive.ui import icons
        for k in ('dim_inspect', 'dim_space'):
            self.assertIn(k, icons.ICONS)
            self.assertFalse(self.w.A[k].icon().isNull())
            self.assertTrue(self.w.A[k].toolTip())


if __name__ == '__main__':
    unittest.main()
