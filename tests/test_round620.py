"""Round 620 : simulation — contrôle des déplacements rapides dans la matière (outil et profil comptés, matière
à jour) : signalés avec leur position et leur profondeur, dans la fenêtre de simulation comme les collisions
du porte-outil ; une remontée verticale depuis le point d'usinage n'est pas contrôlée (elle sort de la
matière qu'elle vient de creuser) ; aucune fausse alerte sur les suites d'usinage 3D livrées."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from tests.test_round591 import pocket_stl
from vectordrive.cam import auto3d as A
from vectordrive.cam import model, simulate, strategies
from vectordrive.cam.model import Move, Toolpath
from vectordrive.core import solids as SO
from vectordrive.core.document import Document

app = QApplication.instance() or QApplication([])


def path(moves, kind='fraise', d=2.0):
    st = model.CamSetup(tools=[model.CamTool(name='F2', kind=kind, diameter=d)])
    tp = Toolpath(op_id='x', tool_id=st.tools[0].id, name='t')
    tp.moves = [Move(*m) for m in moves]
    return st, tp


class TestRapids(unittest.TestCase):
    def test_rapid_through_material(self):
        st, tp = path([('rapid', 0, 0, 5), ('rapid', 0, 0, 1), ('plunge', 0, 0, -2), ('feed', 5, 0, -2),
                       ('rapid', 5, 0, -1), ('rapid', 15, 0, -1), ('rapid', 15, 0, 5)])
        sim = simulate._simulate([tp], st, res=0.05)
        self.assertEqual(len(sim.rapid_hits), 1)
        h = sim.rapid_hits[0]
        self.assertAlmostEqual(h['depth'], 1.0, 6)                       # 1 mm sous le dessus
        self.assertLess(h['x'], 6.2)                                      # dès la sortie de la rainure
        self.assertTrue(any('déplacement rapide de « F2 »' in w for w in sim.warnings))
        self.assertEqual(simulate._sim_copy(sim).rapid_hits, sim.rapid_hits)

    def test_safe_moves(self):
        st, tp = path([('rapid', 0, 0, 5), ('rapid', 0, 0, 1), ('plunge', 0, 0, -2), ('feed', 10, 0, -2),
                       ('rapid', 10, 0, 5), ('rapid', 0, 0, 5), ('rapid', 0, 0, 1), ('plunge', 0, 0, -1.5),
                       ('rapid', 4, 0, -1.5), ('rapid', 4, 0, 5)])               # rapide dans la rainure déjà faite
        self.assertEqual(simulate._simulate([tp], st, res=0.05).rapid_hits, [])

    def test_ball_profile_counted(self):
        st, tp = path([('rapid', 0, 0, 5), ('rapid', 0, 0, 1), ('plunge', 0, 0, -2), ('feed', 10, 0, -2),
                       ('rapid', 10, 0, -1.2), ('rapid', 10, 3, -1.2), ('rapid', 10, 3, 5)], kind='boule', d=4.0)
        sim = simulate._simulate([tp], st, res=0.05)                      # sort de côté par le flanc de la boule
        self.assertEqual(len(sim.rapid_hits), 1)

    @unittest.skipUnless(SO.available(), 'manifold3d absent')
    def test_no_false_alarm_on_sequences(self):
        f = pocket_stl()
        for name in ('Ébauche, reprise, finition des pentes et des parois', 'Ébauche, finition, reprise des angles'):
            tools = [model.CamTool(kind='fraise', diameter=d, cut_length=60, step_down=2.0) for d in (2, 4, 6)] + \
                [model.CamTool(kind='boule', diameter=d, cut_length=60, step_down=1.0) for d in (1, 2, 4)]
            out = A.plan(A.builtin()[name], tools, [], A.PartInfo(40, 20, 10, 1.0, 20), model_path=f, depth=0)
            st = model.CamSetup(tools=list({id(p.tool): p.tool for p in out}.values()))
            tps = []
            for p in out:
                p.op.resolution = max(p.op.resolution, 0.2)
                tps.append(strategies.compute(Document(), st, p.op))
            self.assertEqual(simulate._simulate(tps, st, res=0.1).rapid_hits, [], name)

    def test_dialog_shows_rapids(self):
        from vectordrive.ui.sim_dialog import SimDialog
        st, tp = path([('rapid', 0, 0, 5), ('rapid', 0, 0, 1), ('plunge', 0, 0, -2), ('feed', 5, 0, -2),
                       ('rapid', 5, 0, -1), ('rapid', 15, 0, -1), ('rapid', 15, 0, 5)])
        simulate._SIM_CACHE.clear()
        dlg = SimDialog(None, [tp], st)
        self.assertIn('déplacement(s) rapide(s) dans la matière', dlg.info.text())
        dlg.done(0)


if __name__ == '__main__':
    unittest.main()
