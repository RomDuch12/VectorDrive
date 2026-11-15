"""Round 446 : VND — l'origine du dessin devient le zéro de TypeEdit (même plaque, même origine) ;
BAT — une cote par gravure, prix du devis par gravure fourni par un plugin."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import geom
from vectordrive.core.document import Document, Group, Plate, Shape
from vectordrive.io import proof, registry, vnd_write


class TestVndOrigin(unittest.TestCase):
    def test_origin_written_as_zero(self):
        d = Document()
        d.plate = Plate(width=100, height=50)
        d.add(Shape(path=geom.Path([geom.rect(10, 10, 20, 5)])))
        d.extra['origine'] = [50.0, 25.0]                       # centre de la plaque
        data, report = vnd_write.write_document(d)
        self.assertTrue(any('origine' in r for r in report))
        p = pathlib.Path(tempfile.mkdtemp()) / 'a.vnd'
        p.write_bytes(data)
        e = registry.open_document(str(p))
        self.assertEqual((e.plate.x, e.plate.y, e.plate.width, e.plate.height), (-50.0, -25.0, 100.0, 50.0))
        self.assertEqual(tuple(round(v, 6) for v in e.bbox()), (-40.0, -15.0, -20.0, -10.0))
        self.assertEqual(d.extra['origine'], [50.0, 25.0])      # le document n'est pas touché
        self.assertEqual(d.plate.x, 0.0)
        d.extra.pop('origine')
        data2, report2 = vnd_write.write_document(d)
        self.assertFalse(any('origine' in r for r in report2))


class TestBatEngravings(unittest.TestCase):
    def doc(self):
        d = Document()
        d.plate = Plate(width=160, height=60)
        for x, w in ((10, 30), (60, 40), (115, 35)):
            d.add(Group(children=[Shape(path=geom.Path([geom.rect(x, 15, w, 30)])),
                                  Shape(path=geom.Path([geom.circle((x + w / 2, 30), 8)]))]))
        return d

    def labels(self, prims):
        return len(prims)

    def test_dims_and_prices(self):
        from vectordrive.plugins import REGISTRY
        d = self.doc()
        self.assertEqual(len(proof.engravings(d, proof.ProofInfo())), 3)
        base = proof.build(d, proof.ProofInfo(dims_each=False, prices=False))[0]
        each = proof.build(d, proof.ProofInfo(dims_each=True, prices=False))[0]
        # 3 gravures × 2 cotes × (traits, flèches, valeur), sans les 2 cotes d'ensemble (round 624)
        self.assertEqual(len(each) - len(base), 3 * 2 * 3 - 2 * 3)
        calls = []
        REGISTRY.bat_prices.append(lambda objs: calls.append(objs) or '50,00 € HT')
        try:
            priced = proof.build(d, proof.ProofInfo(dims_each=True, prices=True))[0]
        finally:
            REGISTRY.bat_prices.pop()
        self.assertEqual(len(calls), 3)
        self.assertEqual(len(priced) - len(each), 3)
        REGISTRY.bat_prices.append(lambda objs: 1 / 0)            # plugin en défaut : BAT sans prix
        try:
            self.assertEqual(len(proof.build(d, proof.ProofInfo(dims_each=True, prices=True))[0]), len(each))
        finally:
            REGISTRY.bat_prices.pop()


if __name__ == '__main__':
    unittest.main()
