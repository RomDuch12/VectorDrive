"""Round 1015 : réponse 20 du 14/11 — « aussi au calcul opés » : avec un brut du dessin 2D plus haut que la plaque,
la première passe part du haut du brut ; un surfaçage le retire sur toute son emprise, et les opérations d'après
repartent de Z 0."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1015.ini'))
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from vectordrive.cam import model, strategies  # noqa: E402
from vectordrive.core import geom, stock2d  # noqa: E402
from vectordrive.core.document import Document, Plate, Shape  # noqa: E402


def setup_for(top=1.0):
    doc = Document()
    doc.plate = Plate(width=60.0, height=40.0, thickness=5.0)
    sq = Shape(path=geom.Path([geom.rect(20.0, 10.0, 12.0, 12.0)]), tool=0)
    doc.add(sq)
    s = model.CamSetup()
    t = model.CamTool(name='F3', diameter=3.0, number=1, cut_length=10, step_down=0.5, stepover=0.4)
    s.tools = [t]
    s.operations = [model.Operation(name='P', kind='poche', tool_id=t.id, items=[sq.id], depth=0.5)]
    if top:
        s.stock2d = stock2d.to_dict(stock2d.Stock2D(kind='plaque', top=top, side=2.0))
    return doc, s, t


def cut_levels(tp):
    """Les cotes des passes : celles des mouvements d'usinage à plat (rampes et plongées exclues)."""
    out = set()
    for a, b in zip(tp.moves, tp.moves[1:]):
        if b.kind in ('feed', 'arc_cw', 'arc_ccw') and abs(a.z - b.z) < 1e-9:
            out.add(round(b.z, 6))
    return sorted(out)


class FromTheTopOfTheStock(unittest.TestCase):

    def test_first_pass_from_the_top(self):
        doc, s, _t = setup_for(0)
        flat = strategies.compute(doc, s, s.operations[0])
        self.assertEqual(cut_levels(flat), [-0.5])                            # sans brut : comme avant
        doc, s, _t = setup_for(1.0)
        op = s.operations[0]
        self.assertEqual(strategies.stock_rise(doc, s, op), 1.0)
        tp = strategies.compute(doc, s, op)
        self.assertEqual(cut_levels(tp), [-0.5, 0.0, 0.5])                    # depuis Z 1, le fond inchangé
        self.assertEqual(op.depth, 0.5)                                       # l'opération n'est pas touchée
        self.assertGreaterEqual(max(m.z for m in tp.moves), op.safe_z + 1.0)  # dégagement au-dessus du brut

    def test_facing_removes_it_first(self):
        doc, s, t = setup_for(1.0)
        face = model.Operation(name='S', kind='surfacage', tool_id=t.id, depth=0.0)
        s.operations.insert(0, face)
        tp = strategies.compute(doc, s, face)
        zs = cut_levels(tp)
        self.assertEqual((zs[0], zs[-1]), (0.0, 0.5))                         # du haut du brut à Z 0
        xs = [m.x for m in tp.moves if m.kind != 'rapid']
        self.assertLessEqual(min(xs), -2.0)                                   # toute l'emprise : plaque et marges
        self.assertGreaterEqual(max(xs), 62.0)
        self.assertEqual(strategies.stock_rise(doc, s, s.operations[1]), 0.0)  # la poche d'après : depuis Z 0
        self.assertEqual(cut_levels(strategies.compute(doc, s, s.operations[1])), [-0.5])
        face.enabled = False
        self.assertEqual(strategies.stock_rise(doc, s, s.operations[1]), 1.0)

    def test_partial_facing_other_setup_and_z_start(self):
        doc, s, t = setup_for(1.0)
        pocket = s.operations[0]
        face = model.Operation(name='S', kind='surfacage', tool_id=t.id, depth=0.0, items=list(pocket.items))
        s.operations.insert(0, face)
        self.assertEqual(strategies.stock_rise(doc, s, pocket), 1.0)          # surfaçage d'une zone : le brut reste
        face.items = []
        self.assertEqual(strategies.stock_rise(doc, s, pocket), 0.0)
        self.assertEqual(strategies.stock_rise(doc, s, face), 1.0)
        second = model.Operation(name='S2', kind='surfacage', tool_id=t.id, depth=0.0)
        s.operations.insert(1, second)
        self.assertEqual(strategies.stock_rise(doc, s, second), 0.0)          # le dessus est déjà fait
        doc, s, t = setup_for(1.0)
        pocket = s.operations[0]
        pocket.setup_face = '-Z'                                              # pièce retournée : autre repère
        self.assertEqual(strategies.stock_rise(doc, s, pocket), 0.0)
        pocket.setup_face = ''
        pocket.z_start = 0.4                                                  # Z de départ donné : il fait foi
        self.assertEqual(strategies.stock_rise(doc, s, pocket), 0.0)

    def test_rest_and_linked_pockets(self):
        doc, s, t = setup_for(1.0)
        small = model.CamTool(name='F1', diameter=1.0, number=2, cut_length=10, step_down=0.5, stepover=0.4)
        s.tools.append(small)
        first = s.operations[0]
        rest = model.Operation(name='R', kind='poche', tool_id=small.id, items=list(first.items), depth=0.5,
                               rest_previous=True)
        s.operations.append(rest)
        tp = strategies.compute(doc, s, rest)
        self.assertFalse([w for w in tp.warnings if 'aucune poche active' in w])  # la poche d'avant est vue
        rest.rest_previous = False
        rest.link_previous = True
        paths = strategies.compute_all(doc, s)
        linked = paths[1]
        self.assertTrue(linked.moves)
        self.assertTrue([z for z in cut_levels(linked) if z > 0.01])         # les coins repris aussi dans le brut
        self.assertEqual(min(cut_levels(linked)), -0.5)

    def test_other_kinds_and_cache(self):
        doc, s, t = setup_for(1.0)
        s.operations.append(model.Operation(name='V', kind='vcarve', tool_id=t.id, depth=0.3))
        v = s.operations[1]
        self.assertEqual(strategies.stock_rise(doc, s, v), 0.0)               # gravure 2,5D : Z 0…
        self.assertEqual(strategies.stock_top(doc, s, v), 1.0)
        tp = strategies.compute(doc, s, v)
        if tp.moves:                                                          # … dégagements au-dessus du brut
            self.assertGreaterEqual(max(m.z for m in tp.moves), v.safe_z + 1.0)
        self.assertTrue([w for w in tp.warnings if 'dégagements relevés' in w])
        self.assertEqual(v.safe_z, model.Operation().safe_z)                  # l'opération n'est pas touchée
        s.operations.pop()
        paths = strategies.compute_all(doc, s)
        self.assertIn(0.5, cut_levels(paths[0]))
        face = model.Operation(name='S', kind='surfacage', tool_id=t.id, depth=0.0)
        s.operations.insert(0, face)
        paths = strategies.compute_all(doc, s)                                 # la mémoire ne rend pas l'ancien
        self.assertEqual(cut_levels(paths[1]), [-0.5])


if __name__ == '__main__':
    unittest.main()
