"""Round 875 : ce que l'import des réglages de TypeEdit perdait, relevé en comparant TE13 et VD sur un même dessin : le nombre de passes, l'ordre
des passes, le départ, les passes de la Gravure 3D, et l'outil dans l'en-tête des parcours."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from shapely.geometry import Point, Polygon

from vectordrive.cam import model as M
from vectordrive.cam import strategies as S
from vectordrive.cam import tpp, typeedit
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape

TEE = [(10, 10), (50, 10), (50, 20), (35, 20), (35, 40), (25, 40), (25, 20), (10, 20)]
TRI = [(70, 15), (90, 15), (80, 40)]


def drawing():
    doc = Document()
    doc.plate = Plate(width=100.0, height=50.0)
    doc.layers = [Layer(name='A', items=[Shape(path=geom.Path([geom.polyline(TEE, closed=True)])),
                                         Shape(path=geom.Path([geom.polyline(TRI, closed=True)]))])]
    return doc


def path_of(tool, **kw):
    doc = drawing()
    setup = M.setup_of(doc)
    setup.tools.append(tool)
    op = M.Operation(tool_id=tool.id, **kw)
    setup.operations.append(op)
    M.store(doc, setup)
    return S.compute(doc, setup, op, (0.0, 0.0))


def flats(tp):
    """Longueur à plat par cote."""
    out, q = {}, None
    for m in tp.moves:
        if q is not None and m.kind != 'rapid' and abs(m.z - q.z) < 1e-6:
            out[round(m.z, 3)] = out.get(round(m.z, 3), 0.0) + math.hypot(m.x - q.x, m.y - q.y)
        q = m
    return out


def shape_at(m):
    p = Point(m.x, m.y)
    return 'T' if Polygon(TEE).distance(p) < Polygon(TRI).distance(p) else 'Y'


class TestPassCount(unittest.TestCase):

    def test_a_rounded_step_does_not_add_a_pass(self):
        # 2 mm en 6 passes, pas arrondi à 0,3333 : TE13 en fait 6, VD en faisait 7
        self.assertEqual(len(S.levels(2.0, 0.3333)), 6)
        self.assertEqual(len(S.levels(0.1, 0.0333)), 3)
        self.assertAlmostEqual(S.levels(2.0, 0.3333)[0], -2.0 / 6, places=9)

    def test_other_steps_do_not_change(self):
        self.assertEqual(len(S.levels(1.0, 0.3)), 4)
        self.assertEqual(len(S.levels(2.0, 0.4)), 5)
        self.assertEqual(len(S.levels(10.0, 3.0)), 4)
        self.assertEqual(S.levels(1.0, 2.0), [-1.0])

    def test_the_import_keeps_the_count(self):
        p = tpp.Preset(name='d', kind='CP_Cutting_3D', sections={'PROFONDEUR': {'ZBOTTOM': '2.e-003', 'NBSLICES': '6'}})
        o = tpp.to_template(p)['operations'][0]
        self.assertEqual(len(S.levels(o['depth'], o['step_down'])), 6)


class TestPassOrder(unittest.TestCase):

    def op(self, mode=None):
        sections = {'PROFONDEUR': {'ZBOTTOM': '2.e-003', 'NBSLICES': '2'}}
        if mode is not None:
            sections['FAO_NEWPARAMGLOB'] = {'MODE_MULTIPASSE': mode}
        return tpp.to_template(tpp.Preset(name='d', kind='CP_Cutting_3D', sections=sections))['operations'][0]

    def test_the_setting_is_read(self):
        self.assertEqual(self.op('0')['pass_order'], 'global')
        self.assertEqual(self.op('1')['pass_order'], 'poche')
        self.assertEqual(self.op()['pass_order'], 'poche')

    def test_the_start_is_the_drawings(self):
        self.assertEqual(self.op()['start_policy'], 'dessin')


class TestStart(unittest.TestCase):

    def test_after_the_corner_both_ways(self):
        # relevé dans TE13 : Ø2, surépaisseur 0,2 : (8,8 ; 10) en avalant, (10 ; 8,8) en opposition
        for climb, want in ((True, (8.8, 10.0)), (False, (10.0, 8.8))):
            tp = path_of(M.CamTool(name='F', diameter=2.0), kind='contour', side='exterieur', climb=climb, depth=1.0, step_down=1.0,
                         stock=0.2, start_policy='dessin')
            self.assertAlmostEqual(tp.moves[0].x, want[0], delta=1e-3, msg=str(climb))
            self.assertAlmostEqual(tp.moves[0].y, want[1], delta=1e-3, msg=str(climb))


class TestEngraving(unittest.TestCase):

    def tool(self):
        return M.CamTool(name='V', kind='conique', diameter=6.0, angle=90.0, tip=0.1)

    def engrave(self, **kw):
        args = dict(kind='vcarve', depth=0.35, resolution=0.2, stepover_mm=0.2, vcarve_walls=False)
        args.update(kw)
        return path_of(self.tool(), **args)

    def test_the_import_asks_for_it(self):
        p = tpp.Preset(name='g', kind='CP_Engraving_3D', sections={'PROFONDEUR': {'ZBOTTOM': '3.5e-004', 'NBSLICES': '3'},
                                                                   'SPECIALGRAVURE': {'Stepover': '5.e-005'}})
        o = tpp.to_template(p)['operations'][0]
        self.assertIs(o['vcarve_walls'], False)
        self.assertAlmostEqual(o['vcarve_step'], 0.35 / 3, places=5)

    def test_no_walls_one_pass(self):
        # TE13 : le fond à la profondeur finale, rien aux cotes intermédiaires
        cotes = flats(self.engrave())
        self.assertEqual([z for z, v in cotes.items() if v > 1.0], [-0.35])

    def test_with_walls_as_before(self):
        cotes = flats(self.engrave(vcarve_walls=True, resolution=0.05))
        self.assertGreater(len([z for z, v in cotes.items() if v > 1.0]), 3)

    def test_each_pass_has_its_own_inset(self):
        # la pointe de 0,1 et le cône à 90° : le bord de chaque passe à 0,05 + la profondeur de cette passe
        tp = self.engrave(vcarve_step=0.35 / 3)
        for z in (-0.117, -0.233, -0.35):
            ins = [Polygon(TEE).boundary.distance(Point(m.x, m.y)) for m in tp.moves if abs(m.z - z) < 5e-4 and m.kind != 'rapid' and shape_at(m) == 'T']
            self.assertAlmostEqual(min(ins), 0.05 + abs(z), delta=2e-3, msg=str(z))

    def order(self, tp):
        seq = []
        for m in tp.moves:
            if m.kind != 'rapid' and m.z < -0.05:
                key = (shape_at(m), round(m.z, 2))
                if not seq or seq[-1] != key:
                    if key not in seq:
                        seq.append(key)
        return seq

    def test_global_order(self):
        # relevé dans TE13 : le T et le triangle à la première passe, puis les deux à la deuxième…
        seq = self.order(self.engrave(vcarve_step=0.35 / 3, pass_order='global'))
        shapes = [s for s, z in seq if z in (-0.12, -0.23, -0.35)]
        self.assertEqual(shapes, ['T', 'Y', 'T', 'Y', 'T', 'Y'])

    def test_shape_by_shape_order(self):
        seq = self.order(self.engrave(vcarve_step=0.35 / 3, pass_order='poche'))
        shapes = [s for s, z in seq if z in (-0.12, -0.23, -0.35)]
        self.assertEqual(shapes, ['T', 'T', 'T', 'Y', 'Y', 'Y'])

    def test_the_form_offers_it(self):
        from vectordrive.ui import cam_panel as P
        self.assertIn('vcarve_walls', P.KIND_FIELDS['vcarve'])
        self.assertIn('vcarve_walls', P.LABELS)

    def test_a_saved_op_keeps_its_walls(self):
        d = M.Operation(kind='vcarve').to_dict()
        d.pop('vcarve_walls', None)
        self.assertIs(M.Operation.from_dict(d).vcarve_walls, True)


class TestHeader(unittest.TestCase):

    def test_te13_values(self):
        # relevé sur les parcours de TE13 : rayon, demi-angle, diamètre de la pointe
        self.assertEqual(typeedit._tool_of_header(249, 3.0, 0.0, 6.0), {'number': 249, 'diameter': 6.0, 'angle': 0.0, 'tip': 6.0})
        self.assertEqual(typeedit._tool_of_header(49, 2.0, 15.0, 0.2), {'number': 49, 'diameter': 4.0, 'angle': 30.0, 'tip': 0.2})
        got = typeedit._tool_of_header(49, 2.0, math.radians(15.0), 0.2)
        self.assertAlmostEqual(got['angle'], 30.0, places=4)
        self.assertEqual(got['diameter'], 4.0)

    def test_files_written_before(self):
        # VectorDrive écrivait des mètres
        self.assertEqual(typeedit._tool_of_header(3, 0.006, math.radians(15.0), 0.0006)['diameter'], 6.0)
        self.assertEqual(typeedit._tool_of_header(3, 0.006, math.radians(15.0), 0.0006)['tip'], 0.6)
        self.assertEqual(typeedit._tool_of_header(3, 0.006, 0.0, 0.006)['diameter'], 6.0)

    def test_written_like_te13(self):
        import struct
        data = typeedit.write_bytes(M.Toolpath(op_id='', tool_id='', moves=[M.Move('rapid', 0, 0, 1), M.Move('feed', 1, 0, 0)]), tool_number=5, tool_diameter=6.0)
        n, rad, half, tip, _v = struct.unpack_from('<H4d', data, 0x144)
        self.assertEqual((n, rad, half, tip), (5, 3.0, 0.0, 6.0))
        self.assertEqual(typeedit.read_bytes(data).header['tool']['diameter'], 6.0)


if __name__ == '__main__':
    unittest.main()
