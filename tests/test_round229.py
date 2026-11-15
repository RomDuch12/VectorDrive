"""Round 229 : un texte vivant jamais affiché (sans contour calculé) était
sauté par tous les écrivains — DXF, SVG, PDF, EPS, VND — donc perdu par
`--convert`, le traitement par lots et un import suivi d'un export. Les
contours manquants sont calculés avant d'écrire."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import geom
from vectordrive.core.document import Document, Group, Shape, Text
from vectordrive.io import registry


def contours(doc) -> int:
    return sum(len((getattr(it, 'path', None) or getattr(it, 'outline', None) or geom.Path([])).contours)
               for it in doc.iter_leaves())


class TestExportTexts(unittest.TestCase):
    def doc(self):
        d = Document()
        d.plate = None
        d.add(Text(text='Essai', font='Arial', size=8.0, matrix=geom.Affine.translation(10, 10)))
        d.add(Group(children=[Text(text='Groupe', font='Police Absente', size=5.0,
                                   matrix=geom.Affine.translation(10, 30))]))
        d.add(Shape(path=geom.Path([geom.rect(0, 0, 60, 40)])))
        return d

    def test_every_writer_keeps_texts(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        for ext in ('dxf', 'svg', 'pdf', 'eps', 'vnd', 'vdz'):
            d = self.doc()
            self.assertEqual(contours(d), 1)                                 # jamais affiché : pas de contours
            f = tmp / f'x.{ext}'
            registry.save_document(d, f)
            back = registry.open_document(f)
            self.assertGreater(contours(back), 1 + 5 + 5, ext)              # « Essai » et « Groupe » (≥ 11 lettres… de contours)

    def test_ensure_outlines(self):
        from vectordrive.core import text as TX
        d = self.doc()
        self.assertEqual(TX.ensure_outlines(d), 2)
        kept = [it.outline for it in d.iter_leaves() if isinstance(it, Text)]
        self.assertTrue(all(o is not None and o.contours for o in kept))
        self.assertEqual(TX.ensure_outlines(d), 0)                          # déjà faits : rien recalculé
        self.assertEqual([it.outline for it in d.iter_leaves() if isinstance(it, Text)], kept)


if __name__ == '__main__':
    unittest.main()
