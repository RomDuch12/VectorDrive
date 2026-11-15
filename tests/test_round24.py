"""Round 24 : textes, cotes et trous TypeEdit déplacés restent des objets
TypeEdit (translation comme leur `Deplace`), au lieu d'être écrits comme
dessin."""
import pathlib
import tempfile
import unittest

from vectordrive.core.document import Document, Group, Text
from vectordrive.core.geom import Affine
from vectordrive.io import registry, smb, vnd, vnd_write
from tests.corpus import corpus

SYMBOLS = corpus('symboles_bat')


def sample(path):
    if not path.exists():
        raise unittest.SkipTest(f'{path.name} absent')
    return path


def leaves_of(doc, pred):
    out = []

    def walk(xs):
        for x in xs:
            if pred(x):
                out.append(x)
            else:
                walk(getattr(x, 'children', []))
    for L in doc.layers:
        walk(L.items)
    return out


def is_cote(x):
    return isinstance(x, Group) and 'cotation' in x.extra


def vnd_of(symbol: pathlib.Path, tmp: str) -> pathlib.Path:
    """VND neuf contenant les objets TypeEdit d'un symbole (essai : en
    temps normal, ils seraient écrits comme dessin)."""
    d = smb.read(symbol)
    doc = Document()
    for it in [it for L in d.layers for it in L.items]:
        doc.add(it)
    data, _ = vnd_write.write_document(doc, allow_foreign=True)
    f = pathlib.Path(tmp) / f'{symbol.stem}.vnd'
    f.write_bytes(data)
    return f


def moved_copy(f: pathlib.Path, m: Affine, tmp: str):
    d = registry.open_document(f)
    for L in d.layers:
        L.items = [it.transformed(m) for it in L.items]
    data, rep = vnd_write.write_document(d)
    g = pathlib.Path(tmp) / ('m_' + f.name)
    g.write_bytes(data)
    return registry.open_document(f), registry.open_document(g), rep


class TestShiftTracking(unittest.TestCase):
    def test_translations_add_up(self):
        t = Text(text='A')
        t.extra['vnd_obj'] = object()
        t2 = t.transformed(Affine.translation(1, 2)).transformed(Affine.translation(0.5, -1))
        self.assertEqual(t2.extra['vnd_shift'], (1.5, 1))
        self.assertFalse(t2.extra.get('vnd_moved'))
        t3 = t2.transformed(Affine(2, 0, 0, 2, 0, 0))
        self.assertTrue(t3.extra.get('vnd_moved'))
        self.assertTrue(t3.transformed(Affine.translation(1, 0)).extra.get('vnd_moved'))
        self.assertNotIn('vnd_shift', t2.clone().extra)


class TestTranslatedObjects(unittest.TestCase):
    def test_paragraph_fields(self):
        f = sample(SYMBOLS / 'BAT.smb')
        root, fonts, _ = smb.parse(f.read_bytes())
        pars = []

        def walk(o):
            if o.cls.name == 'CParagraphe':
                pars.append(o)
            for c in o.fields.get('slots', o.children) or []:
                if c is not None:
                    walk(c)
        walk(root)
        p = pars[0]
        dx, dy = 0.0125, -0.003
        t = vnd_write.translated_object(p, dx, dy)
        self.assertIsNot(t, p)
        self.assertAlmostEqual(t.fields['origin'][0] - p.fields['origin'][0], dx, places=12)
        self.assertAlmostEqual(t.fields['bbox'][4] - p.fields['bbox'][4], dy, places=12)
        self.assertAlmostEqual(t.fields['cube'][3] - p.fields['cube'][3], dx, places=12)
        self.assertAlmostEqual(t.fields['boxes'][0][1] - p.fields['boxes'][0][1], dy, places=12)
        pts0 = p.fields['courbe1'].children[0].fields['points'][0]
        pts1 = t.fields['courbe1'].children[0].fields['points'][0]
        self.assertAlmostEqual(pts1[0] - pts0[0], dx * pts0[3], places=12)
        self.assertIs(t.fields['para1'], p.fields['para1'])          # attributs relatifs, partagés
        # l'original n'est pas touché
        self.assertEqual(p.fields['origin'], vnd_write.translated_object(p, 0, 0).fields['origin'])
        # mise en page identique, décalée
        _, _, _, a = vnd.layout_paragraph(p, fonts)
        _, _, _, b = vnd.layout_paragraph(t, fonts)
        ba, bb = a.bbox(), b.bbox()
        for i, d in enumerate((dx, dy, dx, dy)):
            self.assertAlmostEqual(bb[i] - ba[i], d * 1000, delta=2e-5)


class TestMovedInVnd(unittest.TestCase):
    def test_texts_stay_texts(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = vnd_of(sample(SYMBOLS / 'BAT.smb'), tmp)
            d1, d2, rep = moved_copy(f, Affine.translation(12.5, -3.25), tmp)
        self.assertEqual(rep, [])
        t1 = leaves_of(d1, lambda x: isinstance(x, Text))
        t2 = leaves_of(d2, lambda x: isinstance(x, Text))
        self.assertEqual(len(t1), len(t2))
        self.assertGreater(len(t1), 0)
        for a, b in zip(t1, t2):
            self.assertEqual(a.text, b.text)
            ba, bb = a.bbox(), b.bbox()
            self.assertAlmostEqual(bb[0] - ba[0], 12.5, delta=1e-5)
            self.assertAlmostEqual(bb[3] - ba[3], -3.25, delta=1e-5)

    def test_cotations_stay_cotations(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = vnd_of(sample(SYMBOLS / 'Char 10 x 15.smb'), tmp)
            d1, d2, rep = moved_copy(f, Affine.translation(7, 3), tmp)
        self.assertEqual(rep, [])
        c1, c2 = leaves_of(d1, is_cote), leaves_of(d2, is_cote)
        self.assertEqual(len(c1), 5)
        self.assertEqual(len(c2), 5)
        for a, b in zip(c1, c2):
            self.assertEqual(a.extra['cotation']['texte'], b.extra['cotation']['texte'])
            pa, pb = a.extra['cotation']['points_mm'], b.extra['cotation']['points_mm']
            self.assertEqual([round(y - x, 6) for x, y in zip(pa, pb)], [7, 3, 0, 7, 3, 0])

    def test_rotated_cotation_written_as_drawing(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = vnd_of(sample(SYMBOLS / 'Char 10 x 15.smb'), tmp)
            _d1, d2, rep = moved_copy(f, Affine.rotation(90), tmp)
        self.assertTrue(any('tourné' in r for r in rep), rep)
        self.assertEqual(leaves_of(d2, is_cote), [])


if __name__ == '__main__':
    unittest.main()
