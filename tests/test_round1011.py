"""Round 1011 : réponse 7 du 14/11 — poche entière, en option : la passe de finition à toutes les cotes le long de la
matière que l'ébauche n'a pas ouverte (zone étroite où seule la finition entre), au fond ailleurs."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1011.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from vectordrive.cam import model, strategies  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Shape  # noqa: E402

#: un carré de 10 et une rainure de 1,3 × 20 : la fraise de 1 à 0,3 de surépaisseur n'y entre qu'à la finition
KEYHOLE = [(0, 0), (10, 0), (10, 4.35), (30, 4.35), (30, 5.65), (10, 5.65), (10, 10), (0, 10)]


def doc_of(points):
    d = Document()
    d.layers[0].items.append(Shape(path=geom.Path([geom.polyline(points, closed=True)])))
    return d


def compute(points, shut, kind='fraise', diameter=1.0, **kw):
    tool = model.CamTool(name='F', kind=kind, diameter=diameter, step_down=0.5, angle=60.0 if kind == 'conique' else 0.0)
    s = model.CamSetup(tools=[tool])
    op = model.Operation(name='poche', kind='poche', tool_id=tool.id, depth=2.0, stock=0.3, finish=True,
                         finish_shut_levels=shut, **kw)
    s.operations = [op]
    return strategies.compute(doc_of(points), s, op)


def levels_in_slot(tp, x_min=12.0):
    """Cotes où l'outil coupe dans la rainure (x > x_min)."""
    out, prev = set(), None
    for m in tp.moves:
        if prev is not None and m.kind != 'rapid' and min(prev.x, m.x) > x_min and m.z < -1e-6 \
                and abs(m.z - prev.z) < 1e-9 and math.dist((prev.x, prev.y), (m.x, m.y)) > 1e-9:
            out.add(round(m.z, 3))
        prev = m
    return sorted(out)


def first_cut_in_slot(tp, x_min=12.0) -> float:
    """Cote du premier mouvement de coupe dans la rainure : l'outil y entre-t-il de côté, à pleine profondeur ?"""
    return next(m.z for m in tp.moves if m.kind != 'rapid' and m.x > x_min and m.z < -1e-6)


def doc_of_many(*polys):
    d = Document()
    d.layers[0].items.append(Shape(path=geom.Path([geom.polyline(p, closed=True) for p in polys])))
    return d


class WholePocket(unittest.TestCase):

    def test_the_narrow_slot_level_by_level_with_the_option(self):
        before = compute(KEYHOLE, False)
        self.assertEqual(levels_in_slot(before), [-2.0])                     # d'office : au fond seulement
        tp = compute(KEYHOLE, True)
        self.assertEqual(levels_in_slot(tp), [-2.0, -1.5, -1.0, -0.5])        # l'option : à toutes les cotes
        self.assertEqual(first_cut_in_slot(before), -2.0)                   # de côté, à 2 mm d'un coup
        self.assertEqual(first_cut_in_slot(tp), -0.5)                       # une passe après l'autre
        self.assertTrue(any('ébauche n\'a pas ouverte' in w for w in tp.warnings), tp.warnings)
        self.assertFalse(any('ébauche n\'a pas ouverte' in w for w in before.warnings))

    def test_review_what_the_roughing_really_opened(self):
        """Relecture : un balayage sans tour du contour laisse des dents le long d'un bord presque parallèle aux
        rangées ; l'ouvert se lit dans les mouvements de l'ébauche, pas dans la forme."""
        slope = [(0, 0), (30, 0), (30, 10), (0, 11.5)]
        tp = compute(slope, True, pocket_mode='balayage', sweep_contour='sans', sweep_angle=0.0,
                     sweep_angle_mode='fixe')
        self.assertTrue(any('ébauche n\'a pas ouverte' in w for w in tp.warnings), tp.warnings)
        tp = compute(slope, True, pocket_mode='balayage', sweep_angle=0.0, sweep_angle_mode='fixe')   # avec le tour
        self.assertFalse(any('ébauche n\'a pas ouverte' in w for w in tp.warnings), tp.warnings)

    def test_review_legacy_sweep_by_zone_finishes_once(self):
        """Relecture : le balayage d'avant 876, zone par zone, refaisait la finition de toute la poche par zone."""
        tool = model.CamTool(name='F', diameter=1.0, step_down=0.5)
        s = model.CamSetup(tools=[tool])
        counts = []
        for by_zone in (False, True):
            op = model.Operation(name='poche', kind='poche', tool_id=tool.id, depth=1.0, stock=0.3, finish=True,
                                 finish_shut_levels=False, pocket_mode='balayage', sweep_rule=0, sweep_by_zone=by_zone)
            s.operations = [op]
            tp = strategies.compute(doc_of_many([(0, 0), (10, 0), (10, 8), (0, 8)],
                                                [(20, 0), (30, 0), (30, 8), (20, 8)]), s, op)
            counts.append(sum(1 for p, m in zip(tp.moves, tp.moves[1:]) if m.kind == 'feed' and abs(m.z + 1.0) < 1e-6
                              and abs(p.x - 0.5) < 1e-6 and abs(m.x - 0.5) < 1e-6 and abs(p.y - m.y) > 1.0))
        self.assertEqual(counts[0], counts[1])                              # avant : deux fois le tour de finition
        self.assertGreater(counts[0], 0)

    def test_sweep_pockets_too(self):
        for extra in ({'pocket_mode': 'balayage'}, {'pocket_mode': 'balayage', 'sweep_rule': 0}):
            self.assertEqual(levels_in_slot(compute(KEYHOLE, False, **extra)), [-2.0], extra)
            self.assertEqual(levels_in_slot(compute(KEYHOLE, True, **extra)), [-2.0, -1.5, -1.0, -0.5], extra)

    def test_nothing_changes_where_the_roughing_opened_everything(self):
        square = [(0, 0), (20, 0), (20, 10), (0, 10)]
        a, b = compute(square, False), compute(square, True)
        self.assertEqual([(m.kind, round(m.x, 6), round(m.y, 6), round(m.z, 6)) for m in a.moves],
                         [(m.kind, round(m.x, 6), round(m.y, 6), round(m.z, 6)) for m in b.moves])
        self.assertFalse(any('ébauche n\'a pas ouverte' in w for w in b.warnings))

    def test_cone_and_ball_stay_at_the_bottom(self):
        for kind in ('conique', 'boule'):
            a = compute(KEYHOLE, False, kind=kind)
            b = compute(KEYHOLE, True, kind=kind)
            self.assertEqual(len(a.moves), len(b.moves), kind)
            self.assertFalse(any('ébauche n\'a pas ouverte' in w for w in b.warnings), kind)

    def test_in_the_pocket_form(self):
        from vectordrive.ui import cam_panel as CP
        self.assertFalse(model.Operation().finish_shut_levels)
        self.assertIn('finish_shut_levels', CP.KIND_FIELDS['poche'])
        self.assertNotIn('finish_shut_levels', CP.KIND_FIELDS['contour'])
        self.assertIn('finish_shut_levels', dict(CP.OP_SECTIONS)['Profondeurs'])
        self.assertIn('ébauche', CP.LABELS['finish_shut_levels'])
        op = model.Operation.from_dict(dict(model.Operation(kind='poche', finish_shut_levels=True).to_dict()))
        self.assertTrue(op.finish_shut_levels)


if __name__ == '__main__':
    unittest.main()
