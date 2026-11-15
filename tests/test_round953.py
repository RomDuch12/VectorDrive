"""Round 953 : disposition « TypeEdit 13 » du ruban — l'onglet FAO de TypeEdit porte lui aussi le groupe « Machine »
(fraiseuses puis lasers) et les commandes qu'un plugin réserve à une machine."""
import contextlib
import os
import tempfile
import types
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r953.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication, QToolButton  # noqa: E402

app = QApplication.instance() or QApplication([])

from tests import _posts  # noqa: E402
from vectordrive.plugins import REGISTRY, ActionSpec  # noqa: E402
from vectordrive.ui import typeedit_layout as TL  # noqa: E402

SCRIPT = """' onglet FAO de TypeEdit 13 (script synthétique, même syntaxe)
set categoryCAM = configProduct.AddCategoryFromID(310)
set panelPath = categoryCAM.AddPanelFromID(520)
cmd = "ID_LISTPATH"
panelPath.AddButton cmd,true,false
cmd = "ID_CREATEPATH"
panelPath.AddButton cmd,true,false
"""
STRINGS = {310: 'FAO', 520: 'Parcours'}


@contextlib.contextmanager
def declared():
    """Un laser et une fraiseuse d'essai (déclarés dans cet ordre), et une commande de plugin pour la fraiseuse."""
    old_machines, old_posts, old_actions = list(REGISTRY.machines), dict(REGISTRY.posts), list(REGISTRY.actions)
    REGISTRY.machines = [types.SimpleNamespace(key=k, label=label, kind=kind, posts=(f'poste_{k}',), doubles=(),
                                               tip='', plugin='essai')
                         for k, label, kind in (('c', 'Laser C', 'laser'), ('a', 'Fraiseuse A', 'fraiseuse'))]
    for k in 'ac':
        REGISTRY.posts[f'poste_{k}'] = (f'Poste {k}', _posts.write)
    REGISTRY.actions.append(ActionSpec('essai_pour_a', 'Essai pour A', lambda w: None, tab='FAO', group='Essai A',
                                       posts=('a',), plugin='essai'))
    try:
        yield
    finally:
        REGISTRY.posts.clear()
        REGISTRY.posts.update(old_posts)
        REGISTRY.actions[:] = old_actions
        REGISTRY.machines = old_machines


class TypeEditLayout(unittest.TestCase):

    def test_typeedit_fao_tab_has_the_machines(self):
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.ribbon import RibbonGroup
        with declared():
            w = MainWindow()
            try:
                w.settings.setValue('vue/disposition', 'typeedit13')
                with mock.patch.object(TL, 'installed', return_value=TL.parse(SCRIPT, STRINGS)):
                    self.assertTrue(w.apply_ribbon_layout())
                r = w.ribbon
                i = next(k for k in range(r.count()) if r.tabText(k) == 'FAO' and r.widget(k).property('te_layout'))
                page = r.page(i)
                titles = [g.title.text() for g in page.groups()]
                self.assertEqual(titles[0], 'Machine')                      # avant : pas de machines dans cet onglet
                self.assertIn('Essai A', titles)
                first = page.groups()[0]
                self.assertEqual([b.text() for b in first.buttons()], ['Fraiseuse A', 'Laser C'])
                extra = next(g for g in page.groups() if g.title.text() == 'Essai A')
                button = next(b for b in extra.findChildren(QToolButton) if b.defaultAction() is w.A['essai_pour_a'])
                self.assertTrue(w.set_machine('c'))                         # un laser : la commande de la fraiseuse part
                self.assertTrue(button.isHidden() and extra.isHidden())
                self.assertTrue(w.set_machine('a'))
                self.assertFalse(button.isHidden() or extra.isHidden())
                self.assertEqual([b.isChecked() for b in first.buttons()], [True, False])
            finally:
                w.settings.remove('vue/disposition')
                w.modified = False
                w.close()


if __name__ == '__main__':
    unittest.main()
