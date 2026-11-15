"""Round 1037 : demande du 15/11 ~10 h 35 — surfaçage : aller-retour, tout en avalant ou tout en opposition."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1037.ini'))

from vectordrive.cam import model, strategies as S  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Shape  # noqa: E402


def run(angle=0.0, **kw):
    d = Document()
    d.add(Shape(path=geom.Path([geom.rect(0, 0, 40, 20)]), tool=0))
    s = model.CamSetup()
    t = model.CamTool(name='F6', diameter=6, number=1, step_down=0.5, stepover=0.5, cut_length=10)
    s.tools = [t]
    op = model.Operation(kind='surfacage', tool_id=t.id, depth=0.5, face_angle=angle)
    for k, v in kw.items():                                                  # (avant : champ absent, sans effet)
        setattr(op, k, v)
    s.operations = [op]
    return S.compute(d, s, op)


def rows(tp):
    """Les passes au fond : [(départ, arrivée)] dans l'ordre, et s'il y a une remontée avant chacune."""
    out, prev, lifted = [], None, True
    for m in tp.moves:
        here = (m.x, m.y, m.z)
        if prev is not None:
            if m.kind == 'rapid' and m.z > 0:
                lifted = True
            elif m.kind == 'feed' and abs(m.z + 0.5) < 1e-6 and abs(prev[2] + 0.5) < 1e-6 \
                    and math.dist(prev[:2], here[:2]) > 10:
                out.append((prev[:2], here[:2], lifted))
                lifted = False
        prev = here
    return out


def sides(tp):
    """Pour chaque passe, + si la matière pas encore surfacée (côté des passes suivantes) est à sa droite."""
    rs = rows(tp)
    out = []
    for (a, b, _l), (c, _d, _l2) in zip(rs, rs[1:]):
        d = (b[0] - a[0], b[1] - a[1])
        p = (c[0] - a[0], c[1] - a[1])
        right = (d[1], -d[0])
        out.append(1 if right[0] * p[0] + right[1] * p[1] > 0 else -1)
    return out


class Directions(unittest.TestCase):

    def test_back_and_forth_by_default(self):
        self.assertEqual(getattr(model.Operation(), 'face_direction', None), 'aller_retour')
        tp = run()
        s = sides(tp)
        self.assertGreater(len(s), 3)
        self.assertTrue(all(a != b for a, b in zip(s, s[1:])))               # un coup en avalant, un coup en opposition
        self.assertFalse(any(lifted for _a, _b, lifted in rows(tp)[1:]))      # sans remonter entre les passes

    def test_all_climb(self):
        for angle in (0.0, 90.0, 30.0):
            tp = run(angle, face_direction='avalant')
            s = sides(tp)
            self.assertGreater(len(s), 3)
            self.assertEqual(set(s), {1}, angle)                             # matière à droite : broche horaire
            self.assertTrue(all(lifted for _a, _b, lifted in rows(tp)), angle)   # retour au départ par-dessus

    def test_all_conventional(self):
        for angle in (0.0, 90.0):
            tp = run(angle, face_direction='opposition')
            s = sides(tp)
            self.assertGreater(len(s), 3)
            self.assertEqual(set(s), {-1}, angle)
            self.assertTrue(all(lifted for _a, _b, lifted in rows(tp)), angle)

    def test_one_way_on_several_levels(self):
        safe = model.Operation().safe_z
        for d in ('avalant', 'opposition'):
            tp = run(face_direction=d, depth=1.0)                            # deux passes en Z de 0,5
            self.assertEqual(sorted({round(m.z, 6) for m in tp.moves if m.kind == 'feed'}), [-1.0, -0.5], d)
            plunges = [m for m in tp.moves if m.kind == 'plunge']
            self.assertGreater(len(plunges), 6, d)                           # une plongée par passe
            for m in plunges:                                                # hors de la zone, rayon de l'outil compris
                self.assertTrue(m.x < -2.9 or m.x > 42.9, (d, m.x, m.y))
            tops, top = [], None                                             # entre deux passes : remontée au
            for m in tp.moves:                                               # dégagement, par-dessus la pièce
                if m.kind == 'rapid':
                    top = m.z if top is None else max(top, m.z)
                elif m.kind == 'plunge':
                    tops.append(top)
                    top = None
            self.assertTrue(all(t is not None and abs(t - safe) < 1e-6 for t in tops), (d, tops))

    def test_same_area_and_cycle(self):
        both = [rows(run(face_direction=d)) for d in ('aller_retour', 'avalant', 'opposition')]
        span = [sorted(round(a[1], 6) for a, _b, _l in r) for r in both]
        self.assertEqual(span[0], span[1])                                  # les mêmes passes, seul le sens change
        self.assertEqual(span[0], span[2])
        self.assertEqual([c['kind'] for c in run().cycles], ['surfacage_rectangle'])
        for d in ('avalant', 'opposition'):                                 # le cycle de la machine va et vient :
            self.assertEqual(run(face_direction=d).cycles, [], d)           # les mouvements sont écrits


class Form(unittest.TestCase):

    def test_field_under_the_angle(self):
        from vectordrive.ui import cam_panel as CP
        self.assertIn('face_direction', CP.KIND_FIELDS['surfacage'])
        self.assertEqual(set(CP.FIELD_CHOICES.get('face_direction', ())), {'aller_retour', 'avalant', 'opposition'})
        fields = next(fs for _t, fs in CP.OP_SECTIONS if 'face_angle' in fs)
        self.assertEqual(fields[fields.index('face_angle') + 1], 'face_direction')
        self.assertEqual(CP.LABELS['face_direction'], 'Sens des passes')


if __name__ == '__main__':
    unittest.main()
