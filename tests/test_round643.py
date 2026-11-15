"""Round 643 : machine (table rainurée, portique) et broche dans l'espace de
travail ; table rainurée ; exemples livrés (machine et étau, petits étaux,
mandrins, table à brides) à reprendre et modifier ; export STEP (pavés et
cylindres en vraies faces) relu par le lecteur STEP ; exemples STEP."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from tests.test_round637 import BOX, path
from vectordrive.cam import model
from vectordrive.core import stock3d
from vectordrive.core import workspace as WS
from vectordrive.io import model3d as M
from vectordrive.io import step_solids as SS

app = QApplication.instance() or QApplication([])


def volume(m):
    t = np.asarray(m.triangles, np.float64).reshape(-1, 3, 3)
    return abs(np.einsum('ij,ij->i', t[:, 0], np.cross(t[:, 1], t[:, 2])).sum() / 6)


class TestKinds(unittest.TestCase):
    def test_slotted_table(self):
        flat = WS.parts(WS.Element('table'))
        self.assertEqual(len(flat), 1)
        t = WS.Element('table', params={'sx': 300, 'sy': 200, 'sz': 40, 'slots': 4, 'slot_w': 14, 'slot_d': 12})
        ps = WS.parts(t)
        self.assertEqual(len(ps), 1 + 5)                                       # semelle et cinq nervures
        self.assertEqual(max(q[7] for q in ps), 40)
        ribs = sum(2 * q[4] for q in ps[1:])
        self.assertAlmostEqual(ribs, 200 - 4 * 14)                              # quatre rainures de 14
        self.assertTrue(all(q[6] == 28 for q in ps[1:]))                       # profondes de 12

    def test_machine_frame_not_checked(self):
        m = WS.Element('machine')
        full, table = WS.triangles(m), WS.triangles(m, frame=False)
        self.assertGreater(len(full), len(table))
        self.assertAlmostEqual(float(table[:, :, 2].max()), m.p('sz'))          # sans portique : la table
        self.assertGreater(float(full[:, :, 2].max()), m.p('sz') + m.p('clearance'))
        m.params['frame'] = 0
        self.assertEqual(len(WS.triangles(m)), len(table))

    def test_spindle(self):
        b = WS.Element('broche', z=10)
        ps = WS.parts(b)
        self.assertEqual([q[0] for q in ps], ['cyl'] * 3)
        self.assertAlmostEqual(ps[-1][5], 25 + 40 + 260)
        tool = model.CamTool(kind='fraise', diameter=6, stickout=20, holder_diameter=40)
        rings = WS._rings(tool, (20.0, 40.0), b)
        self.assertEqual([r[0] for r in rings], ['outil', 'porte-outil', 'broche', 'broche', 'broche'])
        self.assertEqual(rings[2], ('broche', 25.0, 20.0))                       # écrou de pince (Ø 50)
        self.assertEqual(rings[3], ('broche', 40.0, 45.0))                       # nez au-dessus de l'écrou
        self.assertEqual(len(WS._rings(tool, (0.0, 0.0), b)), 1)                # dépassement inconnu : rien

    def test_spindle_collision_not_fixture(self):
        tool = model.CamTool(kind='fraise', diameter=4, stickout=20, holder_diameter=30)
        setup = model.CamSetup(tools=[tool])
        tps = [path([('rapid', 20, 10, 5), ('feed', 20, 10, -2), ('feed', 30, 10, -2)], tool)]
        far = WS.Element('bloc', x=80, y=10, z=-50, params={'sx': 40, 'sy': 40, 'sz': 130})  # haut à 80, dès X 60
        spindle = WS.Element('broche', x=20, y=10, z=-1)                        # posée sur la pièce : ignorée
        self.assertEqual(WS.collisions(tps, setup, WS.Workspace(elements=[spindle])), [])
        hits = WS.collisions(tps, setup, WS.Workspace(elements=[far, spindle]))
        self.assertEqual([h.what for h in hits], ['broche'])                    # le nez Ø 80 (Z 43) touche le bloc
        self.assertIn('la broche', WS.hit_text(hits[0]))

    def test_fixed_kinds_follow_without_turning(self):
        ws = WS.builtin()['Machine à portique et étau']
        box = stock3d.StockBox(0, 0, 20, 40, 1, -12)                            # étau tourné de 90°
        out = WS.fit_to_stock(ws, box, 5)
        vise, mach, spindle = out.elements
        self.assertEqual(vise.rot, 90.0)
        self.assertEqual((mach.rot, spindle.rot), (0.0, 0.0))
        self.assertEqual((mach.x, mach.y), (vise.x, vise.y))
        self.assertAlmostEqual(mach.z + mach.p('sz'), vise.z)                  # étau toujours sur la table

    def test_relative_to_stock(self):
        ws = WS.builtin()['Table rainurée et brides']
        self.assertEqual(ws.origin, 'brut')
        self.assertEqual(WS.Workspace.from_dict(ws.to_dict()).origin, 'brut')
        out = WS.fit_to_stock(ws, BOX, 5)
        self.assertEqual(out.origin, '')
        brides = [e for e in out.elements if e.kind == 'bride']
        self.assertTrue(all(e.z == BOX.top for e in brides))                   # sur le brut
        table = out.elements[0]
        self.assertEqual(table.z + table.p('sz'), BOX.bottom)                  # le brut posé sur la table
        hx = (BOX.x1 - BOX.x0) / 2
        self.assertEqual(sorted(e.x for e in brides), [BOX.center[0] - hx - 30, BOX.center[0] + hx + 30])
        self.assertTrue(all(e.y == BOX.center[1] for e in brides))
        for e in brides:                                                        # 10 mm sur le bord du brut
            xs = WS.triangles(e)[:, :, 0]
            inside = min(float(xs.max()), BOX.x1) - max(float(xs.min()), BOX.x0)
            self.assertAlmostEqual(inside, 10.0, places=6)

    def test_four_jaw_chuck(self):
        ch = WS.Element('mandrin', params={'jaws': 4})
        e = WS.clamp_stock(ch, stock3d.StockBox(0, 0, 40, 20, 0, -10), 5)
        self.assertEqual((e.p('clamp'), e.p('clamp2')), (20, 40))              # une paire par côté
        jaws = [q for q in WS.parts(e) if q[0] == 'box']
        reach = sorted(round(max(abs(q[1]), abs(q[2])) - q[3], 6) for q in jaws)
        self.assertEqual(reach, [10, 10, 20, 20])                               # faces des mors sur le brut
        three = WS.clamp_stock(WS.Element('mandrin'), stock3d.StockBox(0, 0, 40, 20, 0, -10), 5)
        self.assertEqual((three.p('clamp'), three.p('clamp2')), (20, 0))


class TestStep(unittest.TestCase):
    def test_round_trip(self):
        d = tempfile.mkdtemp()
        f = os.path.join(d, 'essai.step')
        SS.write(f, [{'kind': 'box', 'corners': [(0, 0), (40, 0), (40, 20), (0, 20)], 'z0': 0, 'z1': 10,
                      'name': 'bloc', 'color': (0.9, 0.1, 0.1)},
                     {'kind': 'box', 'corners': [(60, 0), (50, 10), (60, 20), (70, 10)], 'z0': 0, 'z1': 5,
                      'name': 'losange'},                                       # sens horaire : remis en direct
                     {'kind': 'cyl', 'cx': 100, 'cy': 10, 'r': 10, 'z0': -5, 'z1': 15, 'name': 'cylindre',
                      'color': (0.1, 0.2, 0.9)},
                     {'kind': 'box', 'corners': [(0, 0), (1, 0), (1, 1), (0, 1)], 'z0': 3, 'z1': 3}])   # plat : omis
        m = M.load(f)
        self.assertEqual(len(set(m.body_ids().tolist())), 3)
        lo, hi = np.asarray(m.triangles).reshape(-1, 3).min(axis=0), np.asarray(m.triangles).reshape(-1, 3).max(axis=0)
        self.assertTrue(np.allclose(lo, [0, 0, -5], atol=1e-4) and np.allclose(hi, [110, 20, 15], atol=1e-4))
        self.assertAlmostEqual(volume(m), 8000 + 1000 + np.pi * 100 * 20, delta=60)
        cols = {tuple(round(float(v), 2) for v in c) for c in np.asarray(m.colors).reshape(-1, 3)}
        self.assertEqual(cols, {(0.9, 0.1, 0.1), (0.62, 0.64, 0.68), (0.1, 0.2, 0.9)})   # un solide, une couleur
        with open(f, encoding='ascii') as fh:
            text = fh.read()
        self.assertIn('CYLINDRICAL_SURFACE', text)
        self.assertEqual(text.count('MANIFOLD_SOLID_BREP'), 3)

    def test_workspace_to_step(self):
        d = tempfile.mkdtemp()
        ws = WS.Workspace('Essai', '', [WS.Element('etau', x=10, rot=90), WS.Element('broche', visible=False)])
        n = WS.to_step(ws, os.path.join(d, 'e.step'))
        self.assertEqual(n, 3)                                                  # corps et deux mors ; broche cachée
        m = M.load(os.path.join(d, 'e.step'))
        t = WS.triangles(ws.elements[0])
        self.assertTrue(np.allclose(np.asarray(m.triangles).reshape(-1, 3).min(axis=0),
                                    t.reshape(-1, 3).min(axis=0), atol=1e-3))   # à sa place, tourné
        WS.to_step(ws, os.path.join(d, 'c.step'), centered=True)
        c = np.asarray(M.load(os.path.join(d, 'c.step')).triangles).reshape(-1, 3)
        self.assertAlmostEqual(float(c[:, 2].min()), 0.0, places=4)             # centré, base à 0
        self.assertAlmostEqual(float((c[:, 0].min() + c[:, 0].max()) / 2), 0.0, places=4)

    def test_examples(self):
        d = tempfile.mkdtemp()
        files = WS.write_examples(d)
        names = {f.name for f in files}
        self.assertTrue({'Machine_a_portique_et_etau.step', 'materiel_Broche.step', 'materiel_Mandrin_4_mors.step',
                         'Mandrin_3_mors_D160.step'} <= names, names)
        self.assertTrue(all(n.isascii() for n in names))
        for f in files:
            self.assertGreater(len(M.load(str(f)).triangles), 0, f.name)
        el = WS.Element('modele', path=str(files[0]))                          # réimporté comme modèle
        self.assertGreater(len(WS.triangles(el)), 0)

    def test_ascii_stem(self):
        self.assertEqual(WS.ascii_stem('Mandrin 3 mors Ø 160'), 'Mandrin_3_mors_D160')
        self.assertEqual(WS.ascii_stem('Étau de 125 mm'), 'Etau_de_125_mm')
        self.assertEqual(WS.ascii_stem('***'), 'espace')


class TestDialog(unittest.TestCase):
    def setUp(self):
        self.old = os.environ.get('VECTORDRIVE_WORKSPACES')
        os.environ['VECTORDRIVE_WORKSPACES'] = tempfile.mkdtemp()

    def tearDown(self):
        if self.old is None:
            os.environ.pop('VECTORDRIVE_WORKSPACES', None)
        else:
            os.environ['VECTORDRIVE_WORKSPACES'] = self.old

    def test_add_and_export(self):
        from vectordrive.ui.workspace_dialog import WorkspaceDialog
        d = WorkspaceDialog(None, WS.Workspace(), BOX)
        d.add_element('etau')
        m = d.add_element('machine')
        self.assertAlmostEqual(m.z + m.p('sz'), min(BOX.bottom, d.ws.elements[0].z))   # sous l'étau
        b = d.add_element('broche')
        self.assertGreater(b.z, BOX.top)
        self.assertEqual(d.spins[('machine', 'slots')].decimals(), 0)
        f = d.export_step(os.path.join(os.environ['VECTORDRIVE_WORKSPACES'], 'e.step'))
        self.assertTrue(os.path.isfile(f))
        self.assertIn('volume(s)', d.info.text())
        files = d.write_examples(open_folder=False)
        self.assertTrue(files and all(str(x).startswith(os.environ['VECTORDRIVE_WORKSPACES']) for x in files))
        self.assertTrue(d.load_library('Machine à portique et étau'))
        self.assertEqual([e.kind for e in d.value().elements], ['etau', 'machine', 'broche'])


if __name__ == '__main__':
    unittest.main()
