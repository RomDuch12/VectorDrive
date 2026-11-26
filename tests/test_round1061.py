"""Round 1061 : demande du 15/11 — « Z de sécurité doit etre réglable soit au dessus de zones non usinées (plus haut)
soit où tout a été usiné sous le parcours rapide » : le dégagement bas, qui valait au-dessus d'une zone surfacée, vaut
aussi au-dessus du fond d'une poche faite avant à la fraise."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1061.ini'))

from PySide6.QtWidgets import QApplication  # noqa: E402

from vectordrive.cam import strategies as S  # noqa: E402
from vectordrive.cam.model import CamSetup, CamTool, Operation  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Layer, Plate, Shape  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : le dégagement bas ne vaut qu’au-dessus d’un surfaçage'


def square(x, y, w=5.0):
    return Shape(path=geom.Path([geom.rect(x, y, w, w)]), tool=0)


class Pocketed(unittest.TestCase):
    """Plaque 100 × 100 : une poche de 60 × 60 à la fraise de 10, puis des gravures dedans (a, b) et dehors (c)."""

    def setUp(self):
        self.assertTrue(hasattr(S, 'flat_floor'), BEFORE)
        self.zone = square(0, 0, 60)
        self.a, self.b, self.c = square(10, 10), square(40, 40), square(85, 85)
        doc = Document()
        doc.plate = Plate(100, 100)
        doc.layers = [Layer(name='A', items=[self.zone, self.a, self.b, self.c])]
        self.doc = doc
        self.setup = CamSetup(tools=[CamTool(id='p', name='P', kind='fraise', diameter=10.0, step_down=1.0),
                                     CamTool(id='g', name='G', kind='fraise', diameter=2.0),
                                     CamTool(id='v', name='V', kind='conique', diameter=10.0, tip=0.2, angle=60.0)])
        self.pocket = Operation(name='poche', kind='poche', tool_id='p', depth=2.0, items=[self.zone.id])

    def engrave(self, items, **k):
        k = {'safe_z': 3.0, 'safe_z_faced': 0.2, 'z_start': -2.0, **k}       # au fond de la poche
        return Operation(name='g', kind='gravure', tool_id='g', depth=0.2, items=[i.id for i in items], **k)

    def laterals(self, tp):
        out, prev = [], None
        for m in tp.moves:
            if prev is not None and m.kind == 'rapid' and (abs(m.x - prev.x) > 1e-9 or abs(m.y - prev.y) > 1e-9):
                out.append((round(prev.x, 3), round(prev.y, 3), round(m.x, 3), round(m.y, 3), round(m.z, 3)))
            prev = m
        return out

    def run_ops(self, *ops):
        self.setup.operations = list(ops)
        return S.compute_all(self.doc, self.setup)

    def test_low_over_the_floor_of_the_pocket_high_elsewhere(self):
        _p, tp = self.run_ops(self.pocket, self.engrave([self.a, self.b, self.c]))
        lat = self.laterals(tp)
        self.assertEqual((tp.moves[0].kind, tp.moves[0].z), ('rapid', 1.0))    # l'arrivée : haute (3 mm au-dessus de son Z de départ)
        heights = [z for *_xy, z in lat]
        self.assertIn(0.2, heights)                                          # a → b : au-dessus du fond de la poche
        self.assertIn(1.0, heights)                                          # vers c : hors de la poche
        for x0, _y0, x1, _y1, z in lat:
            if z == 0.2:
                self.assertLess(max(x0, x1), 60)
            if max(x0, x1) > 60:
                self.assertEqual(z, 1.0)
        self.assertTrue(any('zone déjà usinée' in w for w in tp.warnings), tp.warnings)

    def test_never_without_a_flat_floor_or_when_asked_not_to(self):
        cone = Operation(name='cône', kind='poche', tool_id='v', depth=2.0, items=[self.zone.id])
        _p, tp = self.run_ops(cone, self.engrave([self.a, self.b]))          # un cône : fond plus étroit que l'outil
        self.assertEqual({z for *_xy, z in self.laterals(tp)}, {1.0})
        self.assertFalse(S.flat_floor(cone, self.setup.tool('v')))
        self.assertTrue(S.flat_floor(self.pocket, self.setup.tool('p')))
        self.assertTrue(S.flat_floor(Operation(kind='surfacage'), None))
        self.assertFalse(S.flat_floor(Operation(kind='contour', tool_id='p'), self.setup.tool('p')))
        _p, tp = self.run_ops(self.pocket, self.engrave([self.a, self.b], safe_z_faced=0.0))   # 0 : sans
        self.assertEqual({z for *_xy, z in self.laterals(tp)}, {1.0})
        _p, tp = self.run_ops(self.engrave([self.a, self.b]), self.pocket)   # la poche vient après : rien n'est vidé
        self.assertEqual({z for *_xy, z in self.laterals(_p)}, {1.0})

    def test_a_cut_above_the_low_height_keeps_the_high_one(self):
        # une gravure qui part du dessus de la plaque (Z 0), à côté du trou de la poche : ses passes sont plus hautes
        # que le fond — le dégagement bas (0,2 mm au-dessus de Z 0) reste au-dessus d'elles, il vaut encore
        top = self.engrave([self.a, self.b], z_start=0.0)
        _p, tp = self.run_ops(self.pocket, top)
        self.assertIn(0.2, {z for *_xy, z in self.laterals(tp)})
        high = self.engrave([self.a, self.b], z_start=1.0)                    # coupe au-dessus du dégagement bas
        _p, tp = self.run_ops(self.pocket, high)
        self.assertNotIn(0.2, {z for *_xy, z in self.laterals(tp)})

    def test_faced_zones_keep_their_own_words(self):
        face = Operation(name='surf', kind='surfacage', tool_id='p', depth=0.3, items=[self.zone.id])
        _f, tp = self.run_ops(face, self.engrave([self.a, self.b], z_start=-0.3))
        self.assertTrue(any('zone surfacée' in w for w in tp.warnings), tp.warnings)
        again = S.compute_all(self.doc, self.setup)[1]
        self.assertEqual(sum(w.startswith(S.LOW_NOTES) for w in again.warnings), 1)   # jamais deux fois

    def low(self, tp) -> bool:
        return 0.2 in {z for *_xy, z in self.laterals(tp)}

    def test_a_low_link_never_outlives_what_allowed_it(self):
        tps = list(self.run_ops(self.pocket, self.engrave([self.a, self.b])))
        eng = tps[1]
        self.assertTrue(self.low(eng))
        self.pocket.enabled = False                                          # la poche décochée : plus au programme
        S.apply_faced_all(self.setup, tps)
        self.assertFalse(self.low(eng))
        self.assertFalse(any(w.startswith(S.LOW_NOTES) for w in eng.warnings))
        self.pocket.enabled = True
        S.apply_faced_all(self.setup, tps)
        self.assertTrue(self.low(eng))
        tps[0].on = False                                                    # à l'arrêt (round 1163)
        S.apply_faced_all(self.setup, tps)
        self.assertFalse(self.low(eng))
        tps[0].on = True
        S.apply_faced_all(self.setup, tps)
        self.assertTrue(self.low(eng))
        S.apply_faced_all(self.setup, tps[::-1])                             # la poche passée après : rien n'est vidé
        self.assertFalse(self.low(eng))
        S.apply_faced_all(self.setup, tps)
        S.apply_faced_all(self.setup, tps)                                   # deux fois de suite : une seule note
        self.assertEqual(sum(w.startswith(S.LOW_NOTES) for w in eng.warnings), 1)
        self.assertIn('0.2 mm, 1 mm ailleurs', eng.warnings[-1])             # les hauteurs telles qu'elles sont
        S.apply_faced_all(self.setup, [eng])                                 # la poche retirée de la liste
        self.assertFalse(self.low(eng))
        self.assertEqual({z for *_xy, z in self.laterals(eng)}, {1.0})

    def test_a_machine_instruction_or_another_setup_resets(self):
        stop = Operation(name='i', kind='instruction', instruction='message')
        tps = self.run_ops(self.pocket, stop, self.engrave([self.a, self.b]))
        self.assertEqual(len(tps), 3)
        self.assertFalse(self.low(tps[2]))                                   # palpage, repère, retournement… : plus sûr
        stop.enabled = False                                                 # l'instruction décochée ne compte pas
        S.apply_faced_all(self.setup, tps)
        self.assertTrue(self.low(tps[2]))
        other = self.engrave([self.a, self.b], setup_face='dessous')         # une autre prise : rien n'y est usiné
        _p, tp = self.run_ops(self.pocket, other)
        self.assertFalse(self.low(tp))

    def test_only_where_the_whole_tool_stays_over_the_floor(self):
        near = square(0.2, 30, 0.5)                                          # tout entier à moins de 1 mm du bord
        self.doc.layers[0].items.append(near)
        _p, tp = self.run_ops(self.pocket, self.engrave([near, self.b]))
        self.assertFalse(self.low(tp))                                       # l'outil ne tient pas entier au-dessus du fond
        self.zone.path = geom.Path([geom.rect(0, 0, 60, 60), geom.rect(25, 25, 10, 10)])   # un îlot au milieu
        far = square(45, 45)
        self.doc.layers[0].items.append(far)
        _p, tp = self.run_ops(self.pocket, self.engrave([self.a, far]))
        self.assertFalse(self.low(tp))                                       # la liaison passerait au-dessus de l'îlot
        _p, tp = self.run_ops(self.pocket, self.engrave([self.a, square(10, 45)]))
        self.assertFalse(self.low(tp))                                       # (forme hors du dessin : pas usinée)
        left = square(10, 45)
        self.doc.layers[0].items.append(left)
        _p, tp = self.run_ops(self.pocket, self.engrave([self.a, left]))
        self.assertTrue(self.low(tp))                                        # à côté de l'îlot : bas


class Program(unittest.TestCase):

    def test_what_is_written_never_keeps_a_stale_low_link(self):
        self.assertTrue(hasattr(S, 'flat_floor'), BEFORE)
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()

        def close():
            w.modified = False
            w.close()
            w.deleteLater()
        self.addCleanup(close)
        p = w.cam_panel
        zone, a, b = square(0, 0, 60), square(10, 10), square(40, 40)
        p.doc.layers[0].items.extend([zone, a, b])
        s = p.setup()
        s.tools = [CamTool(id='p', name='P', kind='fraise', diameter=10.0, step_down=1.0),
                   CamTool(id='g', name='G', kind='fraise', diameter=2.0)]
        s.operations = [Operation(name='poche', kind='poche', tool_id='p', depth=2.0, items=[zone.id]),
                        Operation(name='g', kind='gravure', tool_id='g', depth=0.2, items=[a.id, b.id],
                                  safe_z=3.0, safe_z_faced=0.2)]
        p.save(s)
        tps = p.compute()

        def low(tp):
            prev, out = None, False
            for m in tp.moves:
                if prev is not None and m.kind == 'rapid' and (m.x != prev.x or m.y != prev.y) and abs(m.z - 0.2) < 1e-9:
                    out = True
                prev = m
            return out
        eng = next(t for t in tps if t.op_id == s.operations[1].id)
        self.assertTrue(low(eng))
        s = p.setup()
        s.operations[0].enabled = False                                      # la poche décochée dans la liste
        p.save(s)
        written = p._writable(p.toolpaths)
        self.assertEqual([t.op_id for t in written], [s.operations[1].id])
        self.assertFalse(low(written[0]))                                    # écrit au dégagement haut

    def test_the_labels_say_machined(self):
        from vectordrive.ui import cam_panel as CP
        from vectordrive.ui import options
        self.assertIn('usinée', CP.LABELS['safe_z_faced'])
        self.assertIn('usinée', options.BY_KEY['fao/z_surface'].label)


if __name__ == '__main__':
    unittest.main()
