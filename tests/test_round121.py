"""Round 121 : modèles TypeEdit (.vnm) — lus comme des VND, proposés dans
« Nouveau d'après un modèle » ; codes-barres TypeEdit (CObBCode) lus,
affichés et réécrits tels quels."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ['VECTORDRIVE_DOC_TEMPLATES'] = os.path.join(tempfile.mkdtemp(), 'modeles')

from PySide6.QtWidgets import QApplication

from tests.corpus import corpus
from vectordrive.core import geom
from vectordrive.core.document import Document, Group, Shape
from vectordrive.io import doc_templates as DT
from vectordrive.io import registry, vnd
from vectordrive.io.mfc import Archive, MfcClass, MfcObject
from vectordrive.io.vnd_write import MfcWriter, w_bcode
from vectordrive.io.vnd_write import write as write_vnd


def fake_typeedit():
    """Un faux dossier ProgramData/Gravotech/TypeEdit_V15/Models avec un .vnm."""
    pd = pathlib.Path(tempfile.mkdtemp())
    models = pd / 'Gravotech' / 'TypeEdit_V15-Essai' / 'Models' / 'Trotec'
    models.mkdir(parents=True)
    d = Document()
    d.add(Shape(path=geom.Path([geom.rect(0, 0, 30, 10)])))
    write_vnd(d, str(models / 'plaque.vnm'))
    return pd


class TestVnm(unittest.TestCase):
    def test_vnm_is_readable(self):
        f = registry.by_extension('x.VNM')
        self.assertEqual(f.key, 'vnm')
        pd = fake_typeedit()
        doc = registry.open_document(next(pd.rglob('*.vnm')))
        self.assertEqual(len(list(doc.iter_leaves())), 1)

    def test_typeedit_models_listed(self):
        pd = fake_typeedit()
        with mock.patch.dict(os.environ, {'PROGRAMDATA': str(pd), 'VECTORDRIVE_NO_TYPEEDIT': '0'}):
            models = DT.typeedit_models()
            self.assertEqual(list(models), ['TypeEdit : Trotec / plaque'])
            self.assertEqual(DT.templates()['TypeEdit : Trotec / plaque'][0], 'TypeEdit')
        with mock.patch.dict(os.environ, {'PROGRAMDATA': str(pd), 'VECTORDRIVE_NO_TYPEEDIT': '1'}):
            self.assertEqual(DT.typeedit_models(), {})

    def test_new_from_vnm(self):
        QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        pd = fake_typeedit()
        w = MainWindow()
        try:
            self.assertTrue(w.new_from_template(str(next(pd.rglob('*.vnm')))))
            self.assertIsNone(w.path)
            self.assertEqual(len(list(w.canvas.doc.iter_leaves())), 1)
        finally:
            w.modified = False
            w.close()


class TestBarcode(unittest.TestCase):
    def roundtrip(self, schema, data, var=None):
        from vectordrive.io.vnd_write import _obdao_fields
        o = MfcObject(MfcClass('CObBCode', schema))
        o.fields = _obdao_fields((0.0, 0.0, 0.0, 0.01, 0.005, 0.0))
        o.fields.update(has_zone=0, zone=None, norme_len=4 + 16, norme=b'\x06\x00\x00\x00*DLSOFT*1D*1',
                        data=data, var_flag=1 if var else 0, i124=7, var=var, d138=0.5)
        w = MfcWriter()
        w_bcode(w, o)
        ar = Archive(bytes(w.buf), 0, vnd.READERS)
        back = MfcObject(MfcClass('CObBCode', schema))
        vnd.read_bcode(ar, back)
        self.assertEqual(ar.pos, len(w.buf))
        return back

    def test_roundtrip_schema3_and_4(self):
        b = self.roundtrip(3, b'1234567890')
        self.assertEqual(b.fields['data'], b'1234567890')
        self.assertEqual(vnd.bcode_norm(b), '*DLSOFT*1D*1')
        self.assertEqual(b.fields['d138'], 0.5)
        b4 = self.roundtrip(4, 'REF-É42', var='serie')
        self.assertEqual(vnd.bcode_text(b4.fields['data']), 'REF-É42')
        self.assertEqual(vnd.bcode_text(b4.fields['var']), 'serie')

    @unittest.skipUnless(corpus('vnm_codebarre').is_file(), 'modèle TypeEdit avec code-barres absent')
    def test_typeedit_model_with_barcode(self):
        d = vnd.read(corpus('vnm_codebarre'))
        codes = [it for it in d.iter_items() if isinstance(it, Group) and 'typeedit_barcode' in it.extra]
        self.assertEqual(len(codes), 1)
        info = codes[0].extra['typeedit_barcode']
        self.assertEqual(info['donnee'], '1234567890')
        self.assertTrue(info['norme'].startswith('*DLSOFT*'))
        self.assertTrue(codes[0].children)                                # le dessin du code (image)


if __name__ == '__main__':
    unittest.main()
