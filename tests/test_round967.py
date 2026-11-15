"""Round 967 : la couleur des contours dans l'IGES lui-même — écrite (numéro de couleur ou définition 314), relue en
outils (une couleur = un outil), y compris celles d'un fichier reçu."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r967.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import OWN_COLOR, Document, Shape  # noqa: E402
from vectordrive.core.geom import Contour, Line  # noqa: E402
from vectordrive.io import colors, iges, iges_write  # noqa: E402


def rect(x, color=None, tool=0):
    s = Shape(path=geom.Path([geom.rect(x, 0, 10, 5)]), tool=tool)
    if color:
        s.extra[OWN_COLOR] = color
    return s


def drawing(*items):
    d = Document()
    d.layers[0].items += list(items)
    return d


def shown(doc, axis=0):
    """{bord gauche (ou bas) arrondi : couleur montrée} des objets du dessin."""
    return {round(it.bbox()[axis]): doc.item_color(it) for L in doc.layers for it in L.items}


class Ent:
    """Une entité d'un fichier écrit à la main ; `de` est connu après `build`."""

    def __init__(self, kind, params, color=0, status='00000000'):
        self.kind, self.params, self.color, self.status = kind, params, color, status
        self.de = 0


def build(ents):
    for i, e in enumerate(ents):
        e.de = 2 * i + 1
    d, p = [], []
    for e in ents:
        text = ','.join([str(e.kind), *[str(v.de if isinstance(v, Ent) else v) for v in e.params]]) + ';'
        chunks = [text[i:i + 64] for i in range(0, len(text), 64)]
        ptr = len(p) + 1
        for c in chunks:
            p.append(f'{c:<64}{e.de:>8}P{len(p) + 1:>7}')
        color = -e.color.de if isinstance(e.color, Ent) else e.color
        d.append(f'{e.kind:>8}{ptr:>8}{0:>8}{0:>8}{0:>8}{0:>8}{0:>8}{0:>8}{e.status:>8}D{e.de:>7}')
        d.append(f'{e.kind:>8}{0:>8}{color:>8}{len(chunks):>8}{0:>8}{0:>8}{0:>8}{"":>8}{0:>8}D{e.de + 1:>7}')
    g = ('1H,,1H;,3Hsrc,5Ha.igs,1Hx,1Hy,32,38,6,308,15,,1.,2,2HMM,1,1.,15H20260101.000000,0.001,100.,1Ha,1Hb,11,0,'
         '15H20260101.000000;')
    gl = [f'{g[i:i + 72]:<72}G{i // 72 + 1:>7}' for i in range(0, len(g), 72)]
    end = f'S{1:>7}G{len(gl):>7}D{len(d):>7}P{len(p):>7}'
    path = os.path.join(tempfile.mkdtemp(), 'recu.igs')
    with open(path, 'w', encoding='latin-1', newline='\n') as fh:
        fh.write('\n'.join([f'{"essai":<72}S{1:>7}'] + gl + d + p + [f'{end:<72}T{1:>7}']) + '\n')
    return path


def line(y, color=0, status='00000000', x=0.0):
    return Ent(110, [x, y, 0, x + 10.0, y, 0], color=color, status=status)


def patch_at(z):
    """Surface 128 plane de 20 × 10, à la hauteur z."""
    return Ent(128, [1, 1, 1, 1, 0, 0, 1, 0, 0, 0, 0, 1, 1, 0, 0, 1, 1, 1, 1, 1, 1,
                     0, 0, z, 20, 0, z, 0, 10, z, 20, 10, z, 0, 1, 0, 1])


class Written(unittest.TestCase):

    def test_colours_come_back_from_the_file_alone(self):
        d = drawing(rect(0), rect(20, '#ff0000'), rect(40, '#ff8800'), rect(60, '#ff8800'), rect(80, tool=3),
                    rect(100, '#123456'))
        path = os.path.join(tempfile.mkdtemp(), 'couleurs.igs')
        iges_write.write(d, path)
        back = iges.read(path)                           # sans compagnon : le fichier seul
        self.assertEqual(shown(back), {0: '#000000', 20: '#ff0000', 40: '#ff8800', 60: '#ff8800', 80: '#0000ff',
                                       100: '#123456'})                      # avant : tout en noir
        black = [it for L in back.layers for it in L.items if back.item_color(it) == '#000000']
        self.assertEqual([it.tool for it in black], [0])                     # le noir garde le premier outil
        r = iges._Reader(path)
        kinds = [e.kind for e in r.entries.values()]
        self.assertEqual(kinds.count(314), 2)            # une définition par couleur sans numéro, pas par contour
        told = [e.color for e in r.entries.values() if e.kind == 102]
        self.assertEqual(told[:2], [0, 2])               # noir : sans couleur ; rouge : le numéro de l'IGES
        self.assertEqual(told[2], told[3])
        self.assertEqual(told[4], 4)                     # le bleu de l'outil
        self.assertTrue(told[2] < 0 and told[5] < 0 and told[5] != told[2])
        for e in r.entries.values():                     # un morceau porte la couleur de sa courbe composite
            if e.kind == 102:
                first = r.entries[int(r.params(e.de)[1])]
                self.assertEqual(first.color, e.color)
        plain = iges_write.to_string(drawing(rect(0), rect(20)))[0]          # dessin noir : écrit comme avant
        entries = [ln for ln in plain.splitlines() if ln[72:73] == 'D']
        self.assertEqual({ln[:8].strip() for ln in entries}, {'110', '102'})
        self.assertEqual({ln[16:24].strip() for ln in entries if int(ln[73:]) % 2 == 0}, {'0'})


class Received(unittest.TestCase):

    def test_colours_of_a_received_file(self):
        a, b = line(10, color=4, status='00010000'), Ent(110, [10, 10, 0, 10, 15, 0], color=4, status='00010000')
        mixed = Ent(314, [100.0, 20.0, 0.0], status='00000200')
        c1, c2 = line(0, status='00010000'), line(5, color=7, status='00010000')
        fig = Ent(308, [0, '1HA', 2, c1, c2], status='00000200')
        ents = [line(0, color=3), a, b, Ent(102, [2, a, b]), mixed, line(30, color=mixed), line(40, color=8), line(50),
                c1, c2, fig, Ent(408, [fig, 0, 60, 0, 1.0], color=2)]
        path = build(ents)
        doc = iges.read(path)
        self.assertEqual(shown(doc, 1), {
            0: '#00ff00',                                # un numéro de couleur
            10: '#0000ff',                               # courbe composite sans couleur : celle de ses morceaux
            30: '#ff3300',                               # une définition 314, en pour cent
            40: '#000000',                               # le blanc des DAO : noir
            50: '#000000',                               # sans couleur
            60: '#ff0000',                               # sous-figure : la couleur de l'instance…
            65: '#00ffff',                               # … sauf pour qui a la sienne
        })
        self.assertEqual({it.tool for L in doc.layers for it in L.items if doc.item_color(it) == '#000000'}, {0})
        keep = colors.KEEP
        colors.KEEP = False                              # F10 › Fichiers : couleurs non reprises
        try:
            self.assertEqual({it.tool for L in iges.read(path).layers for it in L.items}, {0})
        finally:
            colors.KEEP = keep

    def test_levels_of_a_part_take_the_tools_after_the_colours(self):
        def tools(doc):
            return {L.name: (L.items[0].tool, L.tool) for L in doc.layers}
        doc = iges.read(build([patch_at(5.0), line(30, color=2)]))
        self.assertEqual(doc.item_color(doc.layers[0].items[0]), '#ff0000')
        self.assertEqual(tools(doc), {'IGES': (0, 0), 'IGES Pz 5': (1, 1), 'IGES Silhouette': (2, 2)})
        self.assertEqual(doc.tool_color(0), '#ff0000')
        plain = iges.read(build([patch_at(5.0), line(30)]))                 # sans couleur : comme avant
        self.assertEqual(tools(plain), {'IGES': (0, 0), 'IGES Pz 5': (0, 0), 'IGES Silhouette': (1, 1)})


class Chained(unittest.TestCase):

    def test_chain_keeps_the_tag_of_its_first_piece(self):
        from vectordrive.core.chain import chain, chain_tagged
        a = Contour([Line((0, 0), (10, 0))], False)
        b = Contour([Line((10, 0), (10, 10))], False)
        c = Contour([Line((50, 0), (60, 0))], False)
        box = geom.rect(100, 0, 5, 5)
        out, tags, joins, closings = chain_tagged([a, b, box, c], ['rouge', 'bleu', 'vert', None])
        self.assertEqual((tags, joins, closings), (['vert', 'rouge', None], 1, 0))
        self.assertEqual([len(k.segments) for k in out], [4, 2, 1])
        same, j, n = chain([a, b, box, c])
        self.assertEqual(([len(k.segments) for k in same], j, n), ([4, 2, 1], 1, 0))


if __name__ == '__main__':
    unittest.main()
