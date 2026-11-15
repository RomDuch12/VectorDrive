"""Round 129 : textes TypeEdit modifiables dans les VND (expérimental,
validé dans TypeEdit 13 pour une ligne en police TrueType) ; gabarit des
attributs de caractère corrigé (4 octets décalés : TypeEdit 13 ne chargeait
pas le dessin)."""
import os
import struct
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import fonts as F
from vectordrive.core import geom
from vectordrive.core import text as TX
from vectordrive.core.document import Document, Shape, Text
from vectordrive.core.geom import Affine
from vectordrive.io import paragraph as PG
from vectordrive.io import vnd
from vectordrive.io import vnd_write as W


def text(s, font='Arial', **kw):
    t = Text(text=s, font=font, size=8, matrix=Affine.translation(20, 50), **kw)
    t.outline = TX.outline_for(t)
    return t


def classes_under_calque(data):
    root, _ = vnd.parse(data)
    out = []

    def walk(o, trail):
        if o.cls.name == 'CParagraphe':
            out.append('>'.join(trail + ['CParagraphe']))
        for c in o.children:
            walk(c, trail + [o.cls.name])
    walk(root, [])
    return root, out


class TestCharTemplate(unittest.TestCase):
    def test_layout_like_typeedit(self):
        r = PG.char_record(ord('A'), 3, 0.008, 0.9)
        self.assertEqual(len(r), 204)
        self.assertEqual(struct.unpack_from('<IIdd', r, 4), (65, 3, 0.008, 0.9))
        self.assertEqual(struct.unpack_from('<d', r, 56)[0], -0.4)        # et non à 60
        self.assertEqual(r[44:48], bytes(4))
        self.assertEqual(struct.unpack_from('<I', r, 92)[0], 5)
        self.assertEqual(r[136], 4)


@unittest.skipUnless(F.find_font('Arial'), 'Arial absente')
class TestLiveTextsInVnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QApplication.instance() or QApplication([])

    def doc(self, *texts):
        d = Document()
        d.add(Shape(path=geom.Path([geom.rect(10, 10, 100, 60)])))
        for t in texts:
            d.add(t)
        return d

    def test_single_line_truetype_is_live(self):
        data, rep = W.write_document(self.doc(text('Plaque 12')), live_texts=True)
        root, paths = classes_under_calque(data)
        self.assertEqual(paths, ['CTravail>CCalque>CZone>CParagraphe'])   # une zone, comme TypeEdit
        self.assertEqual(vnd.font_table(data)[1], ['Arial'])
        self.assertTrue(any('modifiable' in r for r in rep))
        self.assertEqual(W.v13_issues(root), [])
        tmp = os.path.join(tempfile.mkdtemp(), 't.vnd')
        with open(tmp, 'wb') as fh:
            fh.write(data)
        back = [it for it in vnd.read(tmp).iter_leaves() if isinstance(it, Text)]
        self.assertEqual([t.text for t in back], ['Plaque 12'])
        self.assertIn('vnd_obj', back[0].extra)

    def test_multiline_and_off_are_curves(self):
        # round 134 : plusieurs lignes vivantes (une ligne de base par ligne)
        data, _rep = W.write_document(self.doc(text('Deux\nlignes')), live_texts=True)
        self.assertEqual(len(classes_under_calque(data)[1]), 1)
        data, _rep = W.write_document(self.doc(text('Plaque 12')))           # option désactivée
        self.assertEqual(classes_under_calque(data)[1], [])
        self.assertEqual(vnd.font_table(data)[1], [])

    def test_option_from_document(self):
        d = self.doc(text('Plaque 12'))
        d.extra['vnd_textes_vivants'] = True
        self.assertEqual(len(classes_under_calque(W.write_document(d)[0])[1]), 1)

    def test_missing_font_is_curves(self):
        # round 924 : les polices de TypeEdit, lues par le plugin de l'atelier, y sont essayées
        data, _rep = W.write_document(self.doc(text('Plaque', font='Police Inexistante XYZ')), live_texts=True)
        self.assertEqual(classes_under_calque(data)[1], [])                # introuvable : en courbes


if __name__ == '__main__':
    unittest.main()
