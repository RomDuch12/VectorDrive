"""Round 669 : volumes du dessin usinés un par un — l'opération garde le
volume visé (objet du dessin) avec son numéro : un calque caché ne lui fait
plus usiner un autre volume ; volume caché ou supprimé : rien d'usiné, la
raison dite, trajectoires pas recomposées à faux ; numéro changé dans le
formulaire : le volume de ce numéro. Relecture : modèles d'usinage et
réglage importé sans volume d'un autre dessin ; booléen : le volume garde
son objet ; formulaire au numéro d'aujourd'hui ; prise du volume gardé ;
copie déplacée : nouveaux objets."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import mill3d, model, reassemble, strategies
from vectordrive.cam import templates as TPL
from vectordrive.core import solids as SO
from vectordrive.core import workspace as WS
from vectordrive.core.document import Document, Layer


def three_volumes():
    """A (x 0..10) sur le calque 1 ; B (x 30..40) et C (x 60..70) sur le calque 2."""
    d = Document(layers=[Layer(name='Un'), Layer(name='Deux')])
    d.layers[0].items.append(SO.make_shape(SO.box(0, 0, 0, 10, 10, 5)))
    d.layers[1].items.append(SO.make_shape(SO.box(30, 0, 0, 10, 10, 5)))
    d.layers[1].items.append(SO.make_shape(SO.box(60, 0, 0, 10, 10, 5)))
    return d


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestVolumeBody(unittest.TestCase):
    def setUp(self):
        self.d = three_volumes()
        self.st = model.CamSetup(tools=[model.CamTool(kind='boule', diameter=2, stepover=0.4, step_down=20)])
        self.op = model.Operation(kind='surface3d', tool_id=self.st.tools[0].id, depth=0, resolution=0.5, body3d=1)
        self.st.operations = [self.op]
        mill3d.bind_volumes(self.d, self.st)                                      # comme à l'enregistrement

    def xs(self):
        tp = strategies.compute(self.d, self.st, self.op)
        f = [m.x for m in tp.moves if m.kind == 'feed']
        return (min(f), max(f)) if f else None, tp.warnings

    def test_bound_to_its_volume(self):
        self.assertEqual(self.op.body3d_ref['n'], 1)
        (x0, x1), _w = self.xs()
        self.assertTrue(25 <= x0 and x1 <= 45, (x0, x1))                          # B
        self.d.layers[0].visible = False                                          # A caché : B devient le n° 0
        self.assertEqual(mill3d.op_body(self.d, self.op), 0)
        (x0, x1), _w = self.xs()
        self.assertTrue(25 <= x0 and x1 <= 45, (x0, x1))                          # toujours B, pas C

    def test_hidden_volume_not_machined(self):
        self.d.layers[1].visible = False                                          # B caché
        self.assertIsNone(mill3d.op_body(self.d, self.op))
        got, warnings = self.xs()
        self.assertIsNone(got)
        self.assertTrue(any('caché ou supprimé' in w for w in warnings), warnings)
        o = model.Operation(kind='surface3d', setup_face='-Z', body3d=1, body3d_ref=dict(self.op.body3d_ref))
        self.assertIsNone(reassemble.transform(self.d, o))                        # pas recomposée à faux

    def test_number_changed_in_form(self):
        self.op.body3d = 2                                                        # formulaire : C
        mill3d.bind_volumes(self.d, self.st)
        self.assertEqual(self.op.body3d_ref['n'], 2)
        (x0, x1), _w = self.xs()
        self.assertTrue(55 <= x0 and x1 <= 75, (x0, x1))
        self.op.body3d = -1                                                       # toute la pièce
        mill3d.bind_volumes(self.d, self.st)
        self.assertEqual(self.op.body3d_ref, {})

    def test_old_op_beyond_volumes(self):
        o = model.Operation(kind='surface3d', tool_id=self.st.tools[0].id, depth=0, resolution=0.5, body3d=5)
        self.assertIsNone(mill3d.op_body(self.d, o))                              # pas toute la pièce
        tp = strategies.compute(self.d, self.st, o)
        self.assertFalse([m for m in tp.moves if m.kind == 'feed'])

    def test_step_part_untouched(self):
        from tests.test_round596 import FakeDoc, two_boxes_stl
        path = two_boxes_stl()
        doc = FakeDoc(path)
        o = model.Operation(kind='surface3d', body3d=1, model_path=path)
        s = model.CamSetup(operations=[o])
        mill3d.bind_volumes(doc, s)
        self.assertEqual(o.body3d_ref, {})                                        # pièce STEP/STL : son numéro
        self.assertEqual(mill3d.op_body(doc, o), 1)

    def test_setup_key_follows_volume(self):
        self.d.layers[0].visible = False                                          # B devient le n° 0
        self.assertEqual(WS.op_setup(self.op, self.d), ('', 0))
        self.assertEqual(WS.op_setup(self.op), ('', 1))                           # sans dessin : le numéro écrit

    def test_malformed_ref(self):
        for bad in ({'item': 5, 'n': 1}, {'item': self.op.body3d_ref['item'], 'n': 'x'}, ['a']):
            self.op.body3d_ref = bad
            self.assertEqual(mill3d.op_body(self.d, self.op), 1, bad)              # le numéro
            mill3d.bind_volumes(self.d, self.st)
            self.assertEqual(self.op.body3d_ref['n'], 1)

    def test_templates_without_volume(self):
        item = self.op.body3d_ref['item']
        self.assertNotIn('body3d_ref', TPL.from_setup(self.st, 'm')['operations'][0])
        self.assertNotIn('body3d_ref', TPL.single(self.op, self.st.tools[0], 'm')['operations'][0])
        d = self.op.to_dict()
        tpl = {'tools': [t.to_dict() for t in self.st.tools], 'operations': [d]}
        s = model.CamSetup(tools=list(self.st.tools))
        s, _report = TPL.apply(s, tpl)
        self.assertEqual(s.operations[-1].body3d_ref, {})
        self.assertEqual(s.operations[-1].body3d, 1)
        self.assertEqual(self.op.body3d_ref['item'], item)


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestVolumeBodyUi(unittest.TestCase):
    def setUp(self):
        from PySide6.QtWidgets import QApplication
        self.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        d = self.w.canvas.doc
        d.layers.append(Layer(name='Deux'))
        self.a = SO.make_shape(SO.box(0, 0, 0, 10, 10, 5))
        self.b = SO.make_shape(SO.box(30, 0, 0, 10, 10, 5))
        self.c = SO.make_shape(SO.box(60, 0, 0, 10, 10, 5))
        d.layers[0].items.append(self.a)
        d.layers[-1].items += [self.b, self.c]
        cp = self.w.cam_panel
        s = cp.setup()
        s.tools = [model.CamTool(kind='boule', diameter=2)]
        s.operations = [model.Operation(kind='surface3d', tool_id=s.tools[0].id, body3d=1)]
        cp.save(s)
        self.assertEqual(cp.setup().operations[0].body3d_ref['item'], self.b.id)

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_boolean_keeps_volume(self):
        self.w.canvas.select([self.b, self.c])
        res = self.w.solid_boolean('union')
        self.assertEqual(res[0].id, self.b.id)
        self.assertEqual(mill3d.op_body(self.w.canvas.doc, self.w.cam_panel.setup().operations[0]), 1)

    def test_form_shows_current_number(self):
        cp = self.w.cam_panel
        self.w.canvas.doc.layers[0].visible = False                               # B devient le n° 0
        cp.refresh()
        cp.ops.selectRow(0)
        fd = cp.edit_op(exec_dialog=False)
        self.assertEqual(fd.widgets['body3d'].value(), 0)
        fd.reject()

    def test_import_setup_drops_volume(self):
        import json
        from unittest import mock
        from PySide6.QtWidgets import QFileDialog
        path = os.path.join(tempfile.mkdtemp(), 'fao.json')
        data = self.w.cam_panel.setup().to_dict()
        data['operations'][0]['body3d_ref'] = {'item': 'autre-dessin', 'n': 1}
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        with mock.patch.object(QFileDialog, 'getOpenFileName', return_value=(path, '')):
            self.w.cam_panel.import_setup()
        self.assertEqual(self.w.cam_panel.setup().operations[0].body3d_ref['item'], self.b.id)   # repris au numéro

    def test_moved_copy_new_objects(self):
        self.w.canvas.select([self.b])
        new = self.w.move_by(100, 0, copy_=True)
        self.assertNotEqual(new[0].id, self.b.id)


if __name__ == '__main__':
    unittest.main()
