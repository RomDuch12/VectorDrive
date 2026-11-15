"""Round 80 : les objets masqués (sources gardées dans un tampon, des
hachures…) ne partent dans aucun export."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import geom, hatch, stamp
from vectordrive.core import text as TX
from vectordrive.core.document import Document, Plate, Text
from vectordrive.io import registry


def contours_of(doc):
    n = 0
    for leaf in doc.iter_leaves():
        p = getattr(leaf, 'path', None) or getattr(leaf, 'outline', None)
        if p:
            n += len(p.contours)
    return n


class TestHiddenNotExported(unittest.TestCase):
    def test_stamp_and_hatch(self):
        t = Text(text='F', font='Arial', size=10)
        t.outline = TX.outline_for(t)
        st = stamp.build([t], stamp.StampSpec(margin=1, border=0.5))
        ring = geom.Path([geom.circle((40, 10), 5), geom.circle((40, 10), 2)])
        from vectordrive.core.document import Shape
        ht = hatch.build([Shape(path=ring)], hatch.HatchSpec(spacing=1, outline=False))
        visible = sum(len(c.path.contours) for g in (st, ht) for c in g.children if c.visible)
        d = Document()
        d.plate = Plate(width=60, height=30)
        d.layers[0].items += [st, ht]
        with tempfile.TemporaryDirectory() as tmp:
            for ext in ('vnd', 'dxf', 'svg', 'eps'):                  # SimPl, CLJOB : plugin (round 218)
                f = os.path.join(tmp, f'x.{ext}')
                registry.save_document(d, f)
                back = registry.open_document(f)
                n = contours_of(back)
                self.assertEqual(n, visible, ext)

    def test_vdz_keeps_hidden(self):
        t = Text(text='F', font='Arial', size=10)
        t.outline = TX.outline_for(t)
        d = Document()
        d.layers[0].items.append(stamp.build([t], stamp.StampSpec()))
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'x.vdz')
            registry.save_document(d, f)
            back = registry.open_document(f)
            g = next(back.iter_items())
            self.assertEqual([c.visible for c in g.children], [False, True, True])   # re-modifiable


if __name__ == '__main__':
    unittest.main()
