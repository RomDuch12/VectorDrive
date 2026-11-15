"""Round 637 : espace de travail (core.workspace) — table, étaux, mandrins,
brides, cales, blocs et modèles importés autour de la pièce ; étau ou
mandrin placé pour serrer le brut, prise dans les mors ; collisions de
l'outil (un cône s'élargit avec la hauteur) et du porte-outil ;
vérification avant l'écriture du programme ; espaces gardés sous un nom."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np

from vectordrive.cam import model, preflight
from vectordrive.core import stock3d
from vectordrive.core import workspace as WS
from vectordrive.core.document import Document

BOX = stock3d.StockBox(0, 0, 40, 20, 1, -12)            # brut 40 × 20 × 13, haut à +1


def path(moves, tool, name='essai', op_id='op'):
    return model.Toolpath(op_id, tool.id, [model.Move(k, x, y, z) for k, x, y, z in moves], name=name)


def vise(grip=5.0, **params):
    return WS.clamp_stock(WS.Element('etau', 'Étau', params=params), BOX, grip)


class TestElements(unittest.TestCase):
    def test_dict(self):
        e = WS.Element('etau', 'Mon étau', 10, 5, -50, 90, {'opening': 70}, visible=False)
        ws = WS.Workspace('Atelier', 'essai', [e, WS.Element('modele', path='x.stl')])
        back = WS.Workspace.from_dict(ws.to_dict())
        self.assertEqual(back, ws)
        self.assertEqual(WS.Element.from_dict({'kind': 'soucoupe', 'x': 'a', 'params': {'sx': 'b', 'sy': 3}}),
                         WS.Element('bloc', params={'sy': 3.0}))
        self.assertEqual(WS.Element('etau').p('jaw_h'), 40.0)                   # défaut
        self.assertEqual(WS.Element('etau', params={'jaw_h': 'x'}).p('jaw_h'), 40.0)
        doc = Document()
        WS.store(doc, ws)
        self.assertEqual(WS.of(doc), ws)
        WS.store(doc, WS.Workspace())
        self.assertNotIn(WS.KEY, doc.extra)

    def test_geometry(self):
        e = WS.Element('etau', x=10, y=5, z=-50, rot=90, params={'opening': 60, 'jaw_t': 20, 'jaw_w': 100})
        t = WS.triangles(e)
        lo, hi = t.reshape(-1, 3).min(axis=0), t.reshape(-1, 3).max(axis=0)
        self.assertAlmostEqual(hi[2], -50 + 120)                               # haut des mors
        self.assertEqual(WS.jaw_top(e), 70)
        self.assertAlmostEqual(lo[1], 5 - 50)                                  # tourné : largeur suivant Y
        self.assertAlmostEqual(hi[0], 10 + 200)                                # corps de 400 suivant X
        pts = np.array([[1.0, 2.0, 3.0], [-4.0, 0.5, 0.0]])
        self.assertTrue(np.allclose(WS.local(e, WS.place(e, pts)), pts))
        c = WS.triangles(WS.Element('mandrin', params={'jaws': 4}))
        self.assertEqual(len(c), 4 * WS.SEGMENTS + 4 * 12)                     # corps et quatre mors
        self.assertAlmostEqual(float(c[:, :, 2].max()), 90.0)
        self.assertEqual(len(WS.triangles(WS.Element('modele', path='absent.stl'))), 0)

    def test_imported_model(self):
        from vectordrive.io import stl_write
        f = pathlib.Path(tempfile.mkdtemp()) / 'montage.stl'
        stl_write.write_stl(str(f), WS._box_tris(100, 100, 10, 5, 0, 7, 9))  # pavé 20 × 10 × 2 loin de 0
        t = WS.triangles(WS.Element('modele', x=1, y=2, z=-3, path=str(f), params={'scale': 2}))
        lo, hi = t.reshape(-1, 3).min(axis=0), t.reshape(-1, 3).max(axis=0)
        self.assertTrue(np.allclose(lo, (1 - 20, 2 - 10, -3), atol=1e-4))     # centré, posé sur sa base, × 2
        self.assertTrue(np.allclose(hi, (1 + 20, 2 + 10, 1), atol=1e-4))


class TestClamp(unittest.TestCase):
    def test_vise_on_stock(self):
        e = vise()
        self.assertEqual((e.x, e.y, e.rot, e.p('opening')), (20, 10, 0.0, 20))  # mors sur les grands côtés
        self.assertAlmostEqual(WS.jaw_top(e), -12 + 5)
        self.assertAlmostEqual(e.p('parallel'), 35)                             # les cales portent le brut
        self.assertAlmostEqual(float(WS.triangles(e)[:, :, 2].max()), -7)
        tall = WS.clamp_stock(WS.Element('etau'), stock3d.StockBox(0, 0, 20, 50, 0, -10), 4)
        self.assertEqual((tall.rot, tall.p('opening')), (90.0, 20))
        ch = WS.clamp_stock(WS.Element('mandrin'), stock3d.StockBox(-15, -15, 15, 15, 0, -20, True), 8)
        self.assertEqual((ch.p('clamp'), ch.x, WS.jaw_top(ch)), (30, 0, -12))

    def test_grip(self):
        self.assertEqual(WS.grip_for(BOX, None, 40), (13, []))                  # tout le brut
        self.assertEqual(WS.grip_for(BOX, None, 8), (8, []))                    # au plus la hauteur des mors
        self.assertEqual(WS.grip_for(BOX, -3, 40), (8, []))                     # 1 mm sous la coupe
        g, w = WS.grip_for(BOX, -10, 40)
        self.assertEqual(g, 1)
        self.assertTrue(w and 'prise minimale de 3 mm' in w[0], w)

    def test_deepest_near_jaws(self):
        tool = model.CamTool(kind='fraise', diameter=4)
        setup = model.CamSetup(tools=[tool])
        e = vise()
        tps = [path([('rapid', 20, 10, 5), ('feed', 20, 10, -9), ('feed', 30, 10, -9)], tool),     # au milieu
               path([('rapid', 5, 1, 5), ('feed', 5, 1, -4), ('feed', 35, 1, -4)], tool)]           # contre un mors
        self.assertEqual(WS.deepest_near_jaws(e, tps, setup), -4)
        self.assertIsNone(WS.deepest_near_jaws(e, tps[:1], setup))
        self.assertIsNone(WS.deepest_near_jaws(WS.Element('bloc'), tps, setup))


class TestCollisions(unittest.TestCase):
    def setUp(self):
        self.mill = model.CamTool(kind='fraise', diameter=6, name='Fraise 6')
        self.cone = model.CamTool(kind='conique', diameter=1, angle=30, tip=0.2, geometry={'D2': 6}, name='Cône')
        self.held = model.CamTool(kind='fraise', diameter=4, stickout=15, holder_diameter=30, name='F4')
        self.setup = model.CamSetup(tools=[self.mill, self.cone, self.held])
        self.ws = WS.Workspace(elements=[vise()])

    def hits(self, *tps):
        return WS.collisions(list(tps), self.setup, self.ws)

    def test_tool_in_jaw(self):
        tp = path([('rapid', -10, 10, 5), ('feed', -10, 10, -2), ('feed', 50, 10, -2),
                   ('feed', 50, -5, -2), ('feed', 20, -5, -9)], self.mill, 'Détourage')
        h = self.hits(tp)
        self.assertEqual(len(h), 1, h)
        self.assertEqual((h[0].path, h[0].what, h[0].element), ('Détourage', 'outil', 'Étau'))
        self.assertLess(h[0].z, -7 + 0.1)
        self.assertIn('touche « Étau »', WS.hit_text(h[0]))
        ok = path([('rapid', -10, 10, 5), ('feed', -10, 10, -6), ('feed', 50, 10, -6)], self.mill)
        self.assertEqual(self.hits(ok), [])                                     # au-dessus des mors
        inside = path([('rapid', 20, 10, 5), ('feed', 10, 10, -11), ('feed', 30, 10, -11)], self.mill)
        self.assertEqual(self.hits(inside), [])                                 # entre les cales, au-dessus d'elles

    def test_holder(self):
        tp = path([('rapid', 20, 10, 5), ('feed', 20, 10, -25)], self.held, 'Perçage')
        h = self.hits(tp)
        self.assertEqual([x.what for x in h], ['porte-outil'])                  # Ø 30 à -10, les mors à -7
        self.assertIn('le porte-outil', WS.hit_text(h[0]))
        self.assertEqual(self.hits(path([('rapid', 20, 10, 5), ('feed', 20, 10, -15)], self.held)), [])

    def test_cone_widens(self):
        self.ws = WS.Workspace(elements=[WS.Element('bloc', 'Cale', 5, 0, -10, params={'sx': 10, 'sy': 40, 'sz': 10})])
        near = [('rapid', -2, -5, 5), ('feed', -2, -5, -0.3), ('feed', -2, 5, -0.3)]   # à 2 mm du bloc, 0,3 dessous
        self.assertEqual(self.hits(path(near, self.cone)), [])                 # le cône n'a que 0,2 mm de rayon là
        self.assertEqual(len(self.hits(path(near, self.mill))), 1)             # une fraise de 6 le touche
        deep = [('rapid', -2, -5, 5), ('feed', -2, -5, -8), ('feed', -2, 5, -8)]
        self.assertEqual(len(self.hits(path(deep, self.cone))), 1)             # 8 mm plus bas : le cône s'est élargi

    def test_skips(self):
        tp = path([('rapid', -10, -5, 5), ('feed', 50, -5, -9)], self.mill)     # dans le mors à Y -5
        self.assertEqual(len(self.hits(tp)), 1)
        self.setup.operations = [model.Operation(id='op', setup_face='-Z')]
        self.assertEqual(self.hits(tp), [])                                     # autre prise : pas vérifiée
        self.setup.operations = []
        self.ws.elements[0].visible = False
        self.assertEqual(self.hits(tp), [])
        self.assertEqual(WS.collisions([], self.setup, WS.Workspace()), [])

    def test_preflight(self):
        doc = Document()
        WS.store(doc, self.ws)
        tp = path([('rapid', -10, -5, 5), ('feed', -10, -5, -9), ('feed', 50, -5, -9)], self.mill, 'Détourage')
        r = preflight.inspect(doc, self.setup, [tp])
        self.assertTrue(any('Espace de travail' in t and 'Détourage' in t for t in r.blocking()), r.notes)
        WS.store(doc, WS.Workspace())
        self.assertFalse([t for t in preflight.inspect(doc, self.setup, [tp]).blocking() if 'Espace' in t])


class TestLibrary(unittest.TestCase):
    def setUp(self):
        self.old = os.environ.get('VECTORDRIVE_WORKSPACES')
        os.environ['VECTORDRIVE_WORKSPACES'] = tempfile.mkdtemp()

    def tearDown(self):
        if self.old is None:
            os.environ.pop('VECTORDRIVE_WORKSPACES', None)
        else:
            os.environ['VECTORDRIVE_WORKSPACES'] = self.old

    def test_save_load(self):
        from vectordrive.plugins import REGISTRY
        self.assertIn('Étau de 125 mm', WS.builtin())
        ws = WS.Workspace('Ma machine / étau', 'essai', [WS.Element('table'), vise()])
        f = WS.save_user(ws)
        self.assertEqual(f.parent, pathlib.Path(os.environ['VECTORDRIVE_WORKSPACES']))
        self.assertEqual(WS.user_workspaces()['Ma machine / étau'], ws)
        saved = dict(REGISTRY.templates.get(WS.KIND) or {})
        try:
            REGISTRY.templates[WS.KIND] = {'Montage': {'elements': [{'kind': 'bride'}]}}
            every = WS.all_workspaces()
            self.assertEqual(every['Montage'][0], 'plugin')
            self.assertEqual(every['Ma machine / étau'][0], 'utilisateur')
            self.assertEqual(every['Mandrin 3 mors Ø 160'][0], 'cœur')
        finally:
            if saved:
                REGISTRY.templates[WS.KIND] = saved
            else:
                REGISTRY.templates.pop(WS.KIND, None)
        self.assertTrue(WS.delete_user('Ma machine / étau'))
        self.assertFalse(WS.delete_user('Ma machine / étau'))
        with self.assertRaises(ValueError):
            WS.save_user(WS.Workspace())


if __name__ == '__main__':
    unittest.main()
