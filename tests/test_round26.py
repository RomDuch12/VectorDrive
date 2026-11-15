"""Round 26 : table des polices des GVT ; les textes et cotes TypeEdit ne
sont réécrits tels quels que dans leur propre VND."""
import pathlib
import tempfile
import unittest

from vectordrive.core.document import Document, Group, Text
from vectordrive.io import registry, smb, vnd, vnd_write
from tests.corpus import corpus

DRAWS = pathlib.Path('C:/ProgramData/Gravotech/TypeEdit_V15-LaserType_V15/DRAWS')
SYMBOLS = corpus('symboles_bat')
PERLIM = corpus('vnd_verite')


def sample(path):
    if not path.exists():
        raise unittest.SkipTest(f'{path.name} absent')
    return path


class TestFontTable(unittest.TestCase):
    def test_gvt_table(self):
        data = sample(DRAWS / 'Cameleon.gvt').read_bytes()
        pos, names = vnd.font_table(data)
        self.assertEqual(names, ['Arial', 'Segoe UI'])
        self.assertEqual(pos + 4 + 64 * 2, vnd.archive_start(data))
        d = registry.open_document(DRAWS / 'Cameleon.gvt')
        fonts = {t.font for t in d.iter_leaves() if isinstance(t, Text)}
        self.assertEqual(fonts, {'Segoe UI'})                # 2e police de la table, plus Arial par défaut

    def test_gvt_empty_table_and_vnd(self):
        data = sample(DRAWS / 'watch.gvt').read_bytes()
        self.assertEqual(vnd.font_table(data)[1], [])
        data = sample(PERLIM).read_bytes()
        # VND sans texte : compteur nul juste avant l'archive (round 88)
        self.assertEqual(vnd.font_table(data), (vnd.archive_start(data) - 4, []))


class TestForeignObjects(unittest.TestCase):
    def test_symbol_saved_as_vnd_writes_drawings(self):
        d = smb.read(sample(SYMBOLS / 'BAT.smb'))
        doc = Document()
        for it in [it for L in d.layers for it in L.items]:
            doc.add(it)
        data, rep = vnd_write.write_document(doc)
        self.assertTrue(any("venu(s) d'un autre fichier" in r for r in rep), rep)
        root, _ = vnd.parse(data)
        self.assertNotIn('CParagraphe', vnd.structure_signature(root))
        # le document d'origine n'est pas modifié
        self.assertTrue(any('vnd_obj' in t.extra for t in doc.iter_leaves() if isinstance(t, Text)))
        with tempfile.TemporaryDirectory() as tmp:
            f = pathlib.Path(tmp) / 'b.vnd'
            f.write_bytes(data)
            back = registry.open_document(f)
        self.assertAlmostEqual(back.bbox()[0], doc.bbox()[0], places=4)

    def test_own_vnd_objects_kept(self):
        d = smb.read(sample(SYMBOLS / 'Char 10 x 15.smb'))
        doc = Document()
        for it in [it for L in d.layers for it in L.items]:
            doc.add(it)
        data, _ = vnd_write.write_document(doc, allow_foreign=True)
        with tempfile.TemporaryDirectory() as tmp:
            f = pathlib.Path(tmp) / 'a.vnd'
            f.write_bytes(data)
            d1 = registry.open_document(f)
        data2, rep = vnd_write.write_document(d1)              # son propre VND : gardés
        self.assertEqual(rep, [])
        root, _ = vnd.parse(data2)
        self.assertEqual(vnd.structure_signature(root).count('CCotationLaterale'), 5)
        cotes = []

        def walk(xs):
            for x in xs:
                if isinstance(x, Group) and 'cotation' in x.extra:
                    cotes.append(x)
                else:
                    walk(getattr(x, 'children', []))
        for L in d1.layers:
            walk(L.items)
        self.assertEqual(len(cotes), 5)


if __name__ == '__main__':
    unittest.main()
