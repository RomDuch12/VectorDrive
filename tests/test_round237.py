"""Round 237 : modèles de parcours de TypeEdit — chaînes Unicode
(TypeEdit 15), fiches d'outils lues (numéro, nom, référence ; gammes à
plusieurs outils), import rangé dans le dossier de sa source, mémo de
l'outil dans la palette, dossiers de modèles gérés (ranger, renommer,
supprimer)."""
import os
import struct
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


# --- TPP synthétique (structure de TypeEdit, valeurs inventées) -------------------------------
def ansi(s: str) -> bytes:
    b = s.encode('cp1252')
    return bytes([len(b)]) + b


def uni(s: str) -> bytes:
    return b'\xff\xfe\xff' + bytes([len(s)]) + s.encode('utf-16-le')


def preset(name, kind, sections, tools=(), enc=ansi) -> bytes:
    out = enc(name) + struct.pack('<III', 7, len(name), 7) + enc(kind) + b'\x01\x01\x00\x00\x00'
    out += enc('TEMP') + b'\x01' + struct.pack('<I', len(sections))
    for sec, kv in sections.items():
        out += enc(sec) + struct.pack('<I', len(kv))
        for k, v in kv.items():
            out += enc(k) + enc(v)
    out += enc('ADMINISTRATOR') + b'\0' * 40
    from vectordrive.cam import tooldb
    for i, t in enumerate(tools):
        out += struct.pack('<ii', 1 if i == 0 else 0, 2) + ansi(t.name) + tooldb._tool_block(t) + b'\0' * 30
    return out


def folder(name, enc=ansi, v15=False) -> bytes:
    mark = b'\xfd\xff\xff\xff\xfe\xff\xff\xff' if v15 else b'\xff' * 8
    return mark + struct.pack('<I', 2) + enc(name) + struct.pack('<IIII', 0, 1, 7, 7) + b'\xff' * 4


def tools():
    from vectordrive.cam.model import CamTool
    a = CamTool(name='Ø3 Z1 L13', kind='fraise', diameter=3.0, number=248, ref='REF-0003', vendor='FOURNISSEUR')
    b = CamTool(name='30° 0.2', kind='conique', diameter=4.0, angle=30.0, tip=0.2, number=61, ref='REF-0030')
    return a, b


SEC = {'PARAMPCR': {'MODE': 'CREATION'}, 'PROFONDEUR': {'NBSLICES': '2', 'ZBOTTOM': '3.e-003'}}


def tpp13() -> bytes:
    a, b = tools()
    return (struct.pack('<IIII', 0xCF0B, 2, 1, 1) + folder('Atelier')
            + preset('Détour Pz3', 'CP_Cutting_3D', SEC, [a])
            + preset('Gamme Ø3 30°', 'CP_Sequence_MultiTool', SEC, [a, b])
            + folder('Laiton') + preset('Tracé fin', 'CP_Plotting', SEC, [b]))


def tpp15() -> bytes:
    return (struct.pack('<IIII', 0xCF0B, 2, 0, 1) + folder('Disponible', uni, v15=True)
            + preset('Tracé', 'CP_Plotting', SEC, enc=uni) + preset('Balayage', 'CP_Sweeping', SEC, enc=uni))


class TestTpp(unittest.TestCase):
    def test_tools_of_presets(self):
        from vectordrive.cam import tpp
        ps = tpp.parse(tpp13())
        self.assertEqual([(p.folder, p.name) for p in ps],
                         [('Atelier', 'Détour Pz3'), ('Atelier', 'Gamme Ø3 30°'), ('Laiton', 'Tracé fin')])
        self.assertEqual([(t.number, t.name, t.ref) for t in ps[0].tools], [(248, 'Ø3 Z1 L13', 'REF-0003')])
        self.assertEqual([t.number for t in ps[1].tools], [248, 61])
        self.assertEqual((ps[2].tools[0].kind, ps[2].tools[0].angle, ps[2].tools[0].tip), ('conique', 30.0, 0.2))
        self.assertEqual(tpp.tool_memo(ps[0].tools[0]), 'T248 Ø3 Z1 L13 — réf. REF-0003 (FOURNISSEUR)')

    def test_unicode_v15(self):
        from vectordrive.cam import tpp
        ps = tpp.parse(tpp15())
        self.assertEqual([(p.folder, p.name, p.kind) for p in ps],
                         [('Disponible', 'Tracé', 'CP_Plotting'), ('Disponible', 'Balayage', 'CP_Sweeping')])
        self.assertEqual(ps[0].value('PROFONDEUR', 'ZBOTTOM'), 0.003)

    def test_template_keeps_tools_and_source_folder(self):
        from vectordrive.cam import tpp
        ps = tpp.parse(tpp13())
        t = tpp.to_template(ps[1], 'TypeEdit 13 — Meca3')
        self.assertEqual(t['dossier'], 'TypeEdit 13 — Meca3/Atelier')
        self.assertEqual(t['name'], 'TypeEdit 13 — Meca3/Atelier / Gamme Ø3 30°')
        o = t['operations'][-1]                                                     # gamme : ébauche puis finition (279)
        ids = [d['id'] for d in t['tools']]
        self.assertEqual((o['tool_id'], o['ref_tool_id']), (ids[1], ids[0]))      # finition, ébauche avant
        self.assertEqual(t['operations'][0]['tool_id'], ids[0])
        self.assertEqual(len(t['outils_memo']), 2)
        self.assertIn('REF-0003', t['description'])
        self.assertEqual(tpp.source_name('C:/TypeEdit_V13-LaserType_V13/CONFIG/PathParam_Meca3.TPP'),
                         'TypeEdit 13 — Meca3')


class TestFolders(unittest.TestCase):
    def setUp(self):
        self._old = os.environ.get('VECTORDRIVE_CAM_TEMPLATES')
        os.environ['VECTORDRIVE_CAM_TEMPLATES'] = tempfile.mkdtemp()

    def tearDown(self):
        if self._old is None:
            os.environ.pop('VECTORDRIVE_CAM_TEMPLATES', None)
        else:
            os.environ['VECTORDRIVE_CAM_TEMPLATES'] = self._old

    def _import(self):
        from vectordrive.cam import templates as TPL, tpp
        for p in tpp.parse(tpp13()):
            TPL.save_user(tpp.to_template(p, 'TypeEdit 13 — Meca3'))
        return TPL

    def test_move_rename_delete(self):
        TPL = self._import()
        self.assertEqual(TPL.user_folders(), ['TypeEdit 13 — Meca3', 'TypeEdit 13 — Meca3/Atelier',
                                              'TypeEdit 13 — Meca3/Laiton'])
        new = TPL.set_folder('TypeEdit 13 — Meca3/Laiton / Tracé fin', 'Mes modèles')
        self.assertEqual(new, 'Mes modèles / Tracé fin')
        self.assertEqual(TPL.user_templates()[new]['dossier'], 'Mes modèles')
        self.assertEqual(TPL.rename_folder('TypeEdit 13 — Meca3', 'Rangement/TE13'), 2)
        self.assertIn('Rangement/TE13/Atelier / Détour Pz3', TPL.user_templates())
        self.assertEqual(TPL.delete_folder('Rangement'), 2)
        self.assertEqual(list(TPL.user_templates()), ['Mes modèles / Tracé fin'])

    def test_palette_import_and_memo(self):
        from vectordrive.ui.main_window import MainWindow
        path = os.path.join(tempfile.mkdtemp(), 'PathParam_Essai.TPP')
        with open(path, 'wb') as f:
            f.write(tpp13())
        w = MainWindow()
        try:
            pal = w.cam_palette if hasattr(w, 'cam_palette') else None
            if pal is None:
                from vectordrive.ui.cam_palette import CamPalette
                pal = CamPalette(w)
            n = pal.import_typeedit([path], quiet=True)
            self.assertEqual(n, 3)
            from vectordrive.cam import templates as TPL
            self.assertTrue(all(t['dossier'].startswith('TypeEdit — Essai') for t in TPL.user_templates().values()))
            texts = []

            def walk(it):
                texts.append(it.text(0))
                for i in range(it.childCount()):
                    walk(it.child(i))
            for i in range(pal.tree.topLevelItemCount()):
                walk(pal.tree.topLevelItem(i))
            self.assertIn('📁 TypeEdit — Essai', texts)
            self.assertIn('📄 Détour Pz3  — T248 Ø3 Z1 L13', texts)
            self.assertIn('📄 Gamme Ø3 30°  — T248 Ø3 Z1 L13 (+1)', texts)
            # le formulaire ouvert d'après le modèle reprend les deux outils de la gamme
            from vectordrive.cam import model
            s = model.CamSetup()
            o = model.Operation(kind='gamme')
            self.assertTrue(w.cam_panel._apply_op_template(o, s, 'TypeEdit — Essai/Atelier / Gamme Ø3 30°'))
            got = {t.id: t.number for t in s.tools}
            self.assertEqual((o.kind, got[o.tool_id]), ('poche', 248))               # 1re étape : l'ébauche (279)
        finally:
            w.close()


if __name__ == '__main__':
    unittest.main()
