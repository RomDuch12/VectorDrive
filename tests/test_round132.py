"""Round 132 : disposition du ruban de TypeEdit 13 (le thème TypeEdit 13 est
un « mod ») — script de ruban et libellés lus dans le TypeEdit du poste,
onglets, groupes et commandes dans l'ordre de TypeEdit, onglets
contextuels ouverts par les boutons Mode / Opérations."""
import os
import pathlib
import struct
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.ui import typeedit_layout as TL

SCRIPT = """' script de ruban synthétique (même syntaxe que TypeEdit)
set mainPanel = configProduct.AddMainPanelFromID(702)
cmd = "ID_FILE_NEW"
mainPanel.AddButton cmd,true,true
set categoryEdit = configProduct.AddCategoryFromID(303)
set panelAction = categoryEdit.AddPanelFromID(560)
cmd = "ID_EDIT_UNDO"
panelAction.AddButton cmd,true,false
cmd = "ID_EDIT_REDO"
panelAction.AddButton cmd,true,false   ' commentaire
panelAction.AddSeparator(FALSE)
set categoryCAD = configProduct.AddCategoryFromID(307)
set panelMode = categoryCAD.AddPanelFromID(506)
cmd = "ID_COMPO_SHOWPALSHAPE"
set buttonShape = panelMode.AddButton(cmd,true,false)
buttonShape.SetContextID(1001)
set categoryShape = configProduct.AddContextCategoryFromID(316,-1,1001)
set panelSel = categoryShape.AddPanelFromID(599)
cmd = "ID_BACKTO"
set buttonBack = panelSel.AddButton(cmd,true,false)
buttonBack.SetTypeExitContextCategory(true)
set panelShape = categoryShape.AddPanelFromID(316)
cmd = "ID_COMPO_RECTANGLE"
panelShape.AddButton cmd,true,false
cmd = "ID_COMPO_ELLIPSE"
panelShape.AddRadioButton cmd
"""
STRINGS = {303: 'Edition', 307: 'TypeEdit', 316: 'Formes géométriques', 506: 'Mode', 560: 'Action',
           599: 'Retour', 702: 'Menu déroulant'}


def string_dll(path, strings):
    """DLL minimale (32 bits) dont la section .rsrc porte une table de
    chaînes RT_STRING (répertoires : racine → type 6 → blocs → langue)."""
    blocks = {}
    for k, v in strings.items():
        blocks.setdefault(k // 16 + 1, {})[k % 16] = v
    ids = sorted(blocks)
    n = len(ids)
    blobs = [b''.join(struct.pack('<H', len(blocks[b].get(i, ''))) + blocks[b].get(i, '').encode('utf-16-le')
                      for i in range(16)) for b in ids]
    rva0 = 0x1000
    type_dir = 24
    lang0 = type_dir + 16 + 8 * n
    data0 = lang0 + 24 * n
    blob0 = data0 + 16 * n
    rsrc = bytearray(struct.pack('<IIHHHH', 0, 0, 0, 0, 0, 1) + struct.pack('<II', 6, 0x80000000 | type_dir))
    rsrc += struct.pack('<IIHHHH', 0, 0, 0, 0, 0, n)
    for k, b in enumerate(ids):
        rsrc += struct.pack('<II', b, 0x80000000 | (lang0 + 24 * k))
    for k in range(n):
        rsrc += struct.pack('<IIHHHH', 0, 0, 0, 0, 0, 1) + struct.pack('<II', 0x40C, data0 + 16 * k)
    pos = blob0
    for blob in blobs:
        rsrc += struct.pack('<IIII', rva0 + pos, len(blob), 0, 0)
        pos += len(blob)
    for blob in blobs:
        rsrc += blob
    pe_off, opt_size = 0x40, 224
    hdr = bytearray(0x200)
    hdr[0:2] = b'MZ'
    struct.pack_into('<I', hdr, 0x3C, pe_off)
    hdr[pe_off:pe_off + 4] = b'PE\0\0'
    struct.pack_into('<HHIIIHH', hdr, pe_off + 4, 0x14C, 1, 0, 0, 0, opt_size, 0x2102)
    opt = pe_off + 24
    struct.pack_into('<H', hdr, opt, 0x10B)
    struct.pack_into('<II', hdr, opt + 96 + 2 * 8, rva0, len(rsrc))
    sec = opt + opt_size
    hdr[sec:sec + 8] = b'.rsrc\0\0\0'
    struct.pack_into('<IIII', hdr, sec + 8, len(rsrc), rva0, len(rsrc), 0x200)
    pathlib.Path(path).write_bytes(bytes(hdr) + bytes(rsrc))


class TestParse(unittest.TestCase):
    def test_structure(self):
        lay = TL.parse(SCRIPT, STRINGS)
        self.assertEqual(lay.main_menu, ['ID_FILE_NEW'])
        self.assertEqual([t.title for t in lay.tabs], ['Edition', 'TypeEdit'])
        self.assertEqual([(p.title, p.commands) for p in lay.tabs[0].panels],
                         [('Action', [('ID_EDIT_UNDO', True), ('ID_EDIT_REDO', True)])])
        self.assertEqual(lay.modes, {'ID_COMPO_SHOWPALSHAPE': '1001'})
        ctx = lay.contexts['1001']
        self.assertEqual(ctx.title, 'Formes géométriques')
        self.assertEqual(ctx.exit_command, 'ID_BACKTO')
        self.assertEqual([c for p in ctx.panels for c, _b in p.commands],
                         ['ID_BACKTO', 'ID_COMPO_RECTANGLE', 'ID_COMPO_ELLIPSE'])

    def test_string_table(self):
        tmp = pathlib.Path(tempfile.mkdtemp()) / 'TypeEditDLLFR.dll'
        string_dll(tmp, STRINGS)
        self.assertEqual(TL.string_table(tmp), STRINGS)
        other = tmp.with_name('pas_une_dll.dll')
        other.write_bytes(b'rien')
        self.assertEqual(TL.string_table(other), {})

    def test_installed_from_a_fake_typeedit(self):
        root = pathlib.Path(tempfile.mkdtemp()) / 'Gravotech' / 'TypeEdit_V13-LaserType_V13'
        (root / 'res' / 'RIBBON').mkdir(parents=True)
        (root / 'res' / 'RIBBON' / 'ScriptRibbonUI_TE.txt').write_bytes(SCRIPT.encode('latin-1', 'replace'))
        (root / 'LANGUAGE' / 'FR').mkdir(parents=True)
        string_dll(root / 'LANGUAGE' / 'FR' / 'TypeEditDLLFR.dll', STRINGS)
        TL._cache.clear()
        with mock.patch.dict(os.environ, {'PROGRAMDATA': str(root.parents[1]), 'VECTORDRIVE_NO_TYPEEDIT': '0'}), \
                mock.patch('vectordrive.ui.themes.ribbon_script_files',
                           return_value=[str(root / 'res' / 'RIBBON' / 'ScriptRibbonUI_TE.txt')]):
            lay = TL.installed(13, 'fr')
        TL._cache.clear()
        self.assertEqual([t.title for t in lay.tabs], ['Edition', 'TypeEdit'])


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_layout_follows_theme(self):
        from vectordrive.ui.main_window import MainWindow
        TL._cache.clear()
        fake = TL.parse(SCRIPT, STRINGS)
        with mock.patch.object(TL, 'installed', return_value=fake):
            w = MainWindow()
            try:
                r = w.ribbon
                vd_tabs = [r.tabText(i) for i in range(r.count()) if r.isTabVisible(i)]
                self.assertFalse(w.layout_active)
                w.set_theme('typeedit13')
                self.assertTrue(w.layout_active)
                visible = [r.tabText(i) for i in range(r.count()) if r.isTabVisible(i)]
                self.assertEqual(visible, ['Fichier', 'Edition', 'CAD', 'VectorDrive', 'Aide'])   # Fichier complet (441)   # Aide à droite (213), TypeEdit → 2.5D (242) → CAD (903)
                self.assertEqual(r.tabText(r.currentIndex()), 'CAD')
                # bouton Mode → onglet contextuel
                mode = next(a for a in w._te_actions if a.text() == 'Formes géométriques')
                mode.trigger()
                self.assertEqual(r.tabText(r.currentIndex()), 'Formes géométriques')
                w.close_te_contexts()
                self.assertEqual(r.tabText(r.currentIndex()), 'CAD')
                self.assertFalse(any(r.isTabVisible(i) for i in range(r.count())
                                     if r.widget(i).property('te_context')))
                # l'onglet VectorDrive donne accès aux onglets d'origine
                i = next(i for i in range(r.count()) if r.tabText(i) == 'VectorDrive' and r.isTabVisible(i))
                from PySide6.QtWidgets import QToolButton
                menus = [b for b in r.widget(i).findChildren(QToolButton) if b.defaultAction()
                         and b.defaultAction().menu() is not None]
                self.assertGreaterEqual(len(menus), 5)
                # retour au ruban de VectorDrive
                w.set_theme('clair')
                self.assertFalse(w.layout_active)
                self.assertEqual([r.tabText(i) for i in range(r.count()) if r.isTabVisible(i)], vd_tabs)
                # option : TypeEdit 13 quel que soit le thème
                w.settings.setValue('vue/disposition', 'typeedit13')
                self.assertTrue(w.apply_ribbon_layout())
                w.settings.setValue('vue/disposition', 'theme')
                self.assertFalse(w.apply_ribbon_layout())
            finally:
                w.settings.remove('vue/disposition')
                w.set_theme('clair')
                w.modified = False
                w.close()

    def test_without_typeedit(self):
        from vectordrive.ui.main_window import MainWindow
        with mock.patch.object(TL, 'installed', return_value=None):
            w = MainWindow()
            try:
                w.set_theme('typeedit13')
                self.assertFalse(w.layout_active)                      # pas de TypeEdit 13 : ruban normal
            finally:
                w.set_theme('clair')
                w.modified = False
                w.close()


if __name__ == '__main__':
    unittest.main()
