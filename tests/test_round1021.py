"""Round 1021 : demande du 14/11, 19 h 45 — « Prise en charge, si existante, de la vitesse avance finition de l'outil
lors des passes de finition »."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1021.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from vectordrive.cam import arcfit, edit, model, strategies, timing  # noqa: E402
from vectordrive.cam import post  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Shape  # noqa: E402

SQUARE = [(0, 0), (20, 0), (20, 20), (0, 20)]


def doc_of(points):
    d = Document()
    d.layers[0].items.append(Shape(path=geom.Path([geom.polyline(points, closed=True)])))
    return d


def compute(kind='contour', finish=True, **kw):
    tool = model.CamTool(name='F', kind='fraise', diameter=2.0, step_down=0.5, feed=1000.0, finish_feed=400.0)
    s = model.CamSetup(tools=[tool])
    op = model.Operation(name='op', kind=kind, tool_id=tool.id, depth=1.5, stock=0.3, finish=finish, **kw)
    if kind == 'contour':
        op.side = 'exterieur'
    s.operations = [op]
    return strategies.compute(doc_of(SQUARE), s, op), s, op, tool


def fins(tp):
    return [m for m in tp.moves if getattr(m, 'fin', False)]


def circle(z, fin, n=72, r=5.0):
    return [model.Move('feed', r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n), z, fin=fin)
            for k in range(1, n + 1)]


class Marked(unittest.TestCase):

    def test_contour_finish_pass_marked(self):
        tp, *_ = compute('contour')
        f = fins(tp)
        self.assertTrue(f)                                                    # avant : rien de marqué
        self.assertTrue(all(m.kind == 'feed' for m in f))
        self.assertTrue(all(abs(m.z + 1.5) < 1e-6 for m in f))               # au fond seulement
        self.assertTrue(any(m.kind == 'feed' and not m.fin for m in tp.moves))   # l'ébauche, non marquée
        last_rough = max(i for i, m in enumerate(tp.moves) if m.kind == 'feed' and not m.fin)
        self.assertLess(last_rough, tp.moves.index(f[0]))                     # la finition après l'ébauche

    def test_pocket_finish_pass_marked(self):
        tp, *_ = compute('poche')
        self.assertTrue(fins(tp))
        self.assertTrue(any(m.kind == 'feed' and not m.fin for m in tp.moves))

    def test_rest_pocket_finish_marked(self):
        big = model.CamTool(name='F3', kind='fraise', diameter=3.0, step_down=0.5, feed=1000.0)
        small = model.CamTool(name='F1', kind='fraise', diameter=1.0, step_down=0.5, feed=800.0, finish_feed=300.0,
                              number=2)
        s = model.CamSetup(tools=[big, small])
        first = model.Operation(name='E', kind='poche', tool_id=big.id, depth=1.0)
        rest = model.Operation(name='R', kind='poche', tool_id=small.id, depth=1.0, rest_previous=True, finish=True,
                               stock=0.2)
        s.operations = [first, rest]
        tp = strategies.compute(doc_of([(0, 0), (20, 0), (20, 20), (0, 20)]), s, rest)
        self.assertTrue(fins(tp))                                             # avant : non marquée

    def test_without_finishing_nothing_marked(self):
        tp, *_ = compute('contour', finish=False)
        self.assertFalse(fins(tp))
        tp, *_ = compute('poche', finish=False)
        self.assertFalse(fins(tp))


class Feeds(unittest.TestCase):

    def test_move_feed(self):
        tool = model.CamTool(feed=1000.0, finish_feed=400.0)
        op = model.Operation()
        rough, fin = model.Move('feed', 1, 0, 0), model.Move('feed', 2, 0, 0, fin=True)
        self.assertEqual(model.move_feed(rough, op, tool), 1000.0)
        self.assertEqual(model.move_feed(fin, op, tool), 400.0)              # l'avance de finition de l'outil
        op.finish_feed = 300.0
        self.assertEqual(model.move_feed(fin, op, tool), 300.0)              # celle de l'opération d'abord
        self.assertEqual(model.finish_feed_of(op, tool), 300.0)
        op.finish_feed, op.feed = 0.0, 250.0                                  # l'opération impose son avance :
        self.assertEqual(model.move_feed(fin, op, tool), 250.0)              # l'outil plus vif ne la dépasse pas
        op.feed = 0.0
        op.finish_feed, tool.finish_feed = 0.0, 0.0
        self.assertEqual(model.move_feed(fin, op, tool), 1000.0)             # aucune : l'avance d'ébauche
        self.assertEqual(model.finish_feed_of(op, tool), 0.0)
        self.assertEqual(rough, model.Move('feed', 1, 0, 0, fin=True))       # hors des comparaisons

    def test_time_counts_finish_feed(self):
        tp, s, op, tool = compute('contour')
        slow = timing.path_seconds(tp, s)
        tool.finish_feed = 0.0
        same = timing.path_seconds(tp, s)
        self.assertGreater(slow, same + 0.5)                                 # la finition à 400 au lieu de 1000


class Follows(unittest.TestCase):

    def test_arc_fit_keeps_finishing_apart(self):
        start = [model.Move('rapid', 5.0, 0.0, 5.0), model.Move('plunge', 5.0, 0.0, -1.0)]
        out = arcfit.fit_moves(start + circle(-1.0, False) + circle(-1.0, True), 0.01)
        arcs = [m for m in out if m.is_arc]
        self.assertTrue(any(m.fin for m in arcs))                            # avant : les arcs perdaient la marque
        self.assertTrue(any(not m.fin for m in arcs))
        self.assertLess(len(out), 40)                                        # toujours ajustés en arcs
        k = next(i for i, m in enumerate(out) if m.fin)
        self.assertTrue(all(m.fin for m in out[k:]))                         # rien de mêlé

    def test_copies_keep_the_mark(self):
        tp, *_ = compute('contour')
        n = len(fins(tp))
        self.assertGreater(n, 0)
        self.assertEqual(len(fins(edit.translated_toolpath(tp, 1.0, 2.0))), n)
        self.assertEqual(len(fins(edit.reversed_toolpath(tp))), n)
        self.assertEqual(len(fins(post.shifted([tp], (3.0, 4.0))[0])), n)
        self.assertEqual(len(fins(post.oriented([tp], 'miroir_x', (0, 0, 30, 30))[0][0])), n)

    def test_panels_keep_the_mark(self):
        from vectordrive.cam import panels
        tp, *_ = compute('contour')
        whole = panels.Panel(0, 0, 0, -50.0, -50.0, 80.0, 80.0)
        got = [m for _start, ms in panels.chains(tp.moves, whole) for m in ms]
        self.assertTrue(any(m.fin for m in got))                              # avant : perdue au découpage
        self.assertTrue(any(m.kind == 'feed' and not m.fin for m in got))

    def test_session_keeps_the_mark(self):
        from vectordrive.ui import session
        tp, *_ = compute('contour')
        back = session.paths_from_bytes(session.paths_bytes([tp]))[0]
        self.assertEqual([m.fin for m in back.moves], [m.fin for m in tp.moves])
        self.assertTrue(any(m.fin for m in back.moves))


if __name__ == '__main__':
    unittest.main()
