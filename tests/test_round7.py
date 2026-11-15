"""Round 7 : cotations, marqueurs et axes TypeEdit ; objets d'origine
(textes, cotes) réécrits tels quels dans le VND s'ils sont intacts."""
import pathlib
import tempfile
import unittest

from vectordrive.core import geom
from vectordrive.core.document import Document, Group, Shape, Text
from vectordrive.core.geom import Affine
from vectordrive.io import registry, smb, vnd, vnd_write
from tests.corpus import corpus

SYM = corpus('symboles')
SAMPLES = {
    'laterale': corpus('smb_cote_laterale'),
    'verticale_angle_axes': corpus('smb_cotes_axes'),
    'marqueur': corpus('smb_marqueur'),
    'pdf': corpus('smb_pdf'),
}


def sample(key):
    p = SAMPLES[key]
    if not p.exists():
        raise unittest.SkipTest(f'{key} absent du corpus')
    return p


def classes(root):
    seen, out = set(), []

    def walk(o):
        if o is None or id(o) in seen or not hasattr(o, 'cls'):
            return
        seen.add(id(o))
        out.append(o.cls.name)
        for c in o.children:
            walk(c)
        for c in o.fields.get('slots', []) or []:
            walk(c)
    walk(root)
    return out


class TestDecoding(unittest.TestCase):
    def test_byte_identical(self):
        for key in ('laterale', 'verticale_angle_axes', 'marqueur'):
            with self.subTest(key):
                data = sample(key).read_bytes()
                self.assertEqual(smb.rewrite(data), data)

    def test_cotation_kinds(self):
        root, _fonts, _ar = smb.parse(sample('verticale_angle_axes').read_bytes())
        names = set(classes(root))
        self.assertTrue({'CCotationVerticale', 'CCotationAngle', 'CCenterLine'} <= names)

    def test_cotation_drawn_as_group(self):
        d = registry.open_document(sample('laterale'))
        top = d.layers[0].items[0]
        cotes = [g for g in top.children if isinstance(g, Group) and g.name == 'Cote']
        self.assertGreater(len(cotes), 5)
        labels = {g.extra['cotation']['texte'] for g in cotes}
        self.assertIn('5.90 mm', labels)
        # dessin complet : ligne de cote, texte, attaches, flèches
        g = cotes[0]
        self.assertTrue(any(isinstance(c, Text) for c in g.children))
        self.assertGreaterEqual(sum(1 for c in g.children if isinstance(c, Shape)), 3)
        # round 925 : ses textes sont dans une police de TypeEdit, lue seulement par un plugin (round 924) — sans
        # lui, la police est signalée absente, rien d'autre
        self.assertEqual([r for r in d.report if 'absente du poste' not in r], [])

    def test_construction_objects_reported(self):
        d = registry.open_document(sample('verticale_angle_axes'))
        # gardés (non affichés) pour la réécriture du VND depuis le round 89
        self.assertTrue(any(r.startswith('axe de construction non affiché') for r in d.report), d.report)

    def test_pdf_named_smb(self):
        d = registry.open_document(sample('pdf'))
        self.assertIn('PDF', d.report[0])
        self.assertGreater(d.stats()['contours'], 10)

    def test_summarize(self):
        self.assertEqual(vnd.summarize_report(['a', 'b', 'a', 'a']), ['a (× 3)', 'b'])


class TestSourceObjects(unittest.TestCase):
    def test_tracking(self):
        t = Text(text='A')
        t.extra['vnd_obj'] = object()
        self.assertFalse(t.transformed(Affine()).extra.get('vnd_moved'))
        moved = t.transformed(Affine.translation(1, 0))         # translation : cumulée (round 24)
        self.assertFalse(moved.extra.get('vnd_moved'))
        self.assertEqual(moved.extra['vnd_shift'], (1, 0))
        turned = t.transformed(Affine.rotation(90))
        self.assertTrue(turned.extra.get('vnd_moved'))
        self.assertFalse(t.extra.get('vnd_moved'))              # l'original n'est pas touché
        self.assertNotIn('vnd_obj', t.clone().extra)

    def test_placed_symbol_is_a_copy(self):
        g = smb.as_group(sample('laterale'))

        def any_source(it):
            return 'vnd_obj' in it.extra or any(any_source(c) for c in getattr(it, 'children', ()))
        self.assertFalse(any_source(g))

    def test_vnd_keeps_intact_cotation(self):
        top = registry.open_document(sample('laterale')).layers[0].items[0]
        cote = next(g for g in top.children if isinstance(g, Group) and g.name == 'Cote')
        # translation : la cote reste une cote (round 24) ; rotation : dessin
        for item, kept in ((cote, True), (cote.transformed(Affine.translation(5, 0)), True),
                           (cote.transformed(Affine.rotation(30)), False)):
            with self.subTest(kept=kept):
                doc = Document()
                doc.add(item)
                doc.add(Shape(path=geom.Path([geom.rect(0, 0, 20, 10)])))
                data, report = vnd_write.write_document(doc, allow_foreign=True)
                with tempfile.TemporaryDirectory() as t:
                    f = pathlib.Path(t) / 'c.vnd'
                    f.write_bytes(data)
                    root, _ar = vnd.parse(f.read_bytes())
                    back = vnd.read(f)
                names = classes(root)
                self.assertEqual('CCotationLaterale' in names, kept)
                self.assertEqual(any('tourné' in r for r in report), not kept)
                bb_in, bb_out = item.bbox(), back.bbox()
                self.assertLessEqual(bb_out[0], bb_in[0] + 1e-6)
                self.assertGreaterEqual(bb_out[2], bb_in[2] - 1e-6)


if __name__ == '__main__':
    unittest.main()
