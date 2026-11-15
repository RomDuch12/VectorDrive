"""Round 950 : machines de la FAO déclarées par les plugins — un bouton par machine dans les rubans FAO, un ruban
« FAO laser », la palette qui suit le genre de la machine, les post-processeurs en double qui ne sont plus proposés."""
import contextlib
import os
import tempfile
import types
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r950.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from tests import _posts  # noqa: E402
from vectordrive.cam import post  # noqa: E402
from vectordrive.plugins import REGISTRY, ActionSpec  # noqa: E402


def machine(key, label, kind, posts=(), doubles=()):
    return types.SimpleNamespace(key=key, label=label, kind=kind, posts=tuple(posts), doubles=tuple(doubles), tip='',
                                 plugin='essai')


@contextlib.contextmanager
def declared():
    """Quatre machines d'essai et cinq post-processeurs, le temps du bloc : la fraiseuse A a deux post-processeurs
    possibles (le meilleur, « poste_a2 », n'est pas installé) et un double ; le laser D n'en a pas encore."""
    had = hasattr(REGISTRY, 'machines')
    old_machines = list(getattr(REGISTRY, 'machines', []))
    old_posts, old_actions = dict(REGISTRY.posts), list(REGISTRY.actions)
    REGISTRY.machines = [machine('fraise_a', 'Fraiseuse A', 'fraiseuse', ('poste_a2', 'poste_a'), ('vieux_*',)),
                         machine('fraise_b', 'Fraiseuse B', 'fraiseuse', ('poste_b',)),
                         machine('laser_c', 'Laser C', 'laser', ('poste_c',)),
                         machine('laser_d', 'Laser D', 'laser')]
    for key, label in (('poste_a', 'Poste A'), ('vieux_a', 'Vieux poste A'), ('poste_b', 'Poste B'),
                       ('poste_c', 'Poste C'), ('libre', 'Poste libre')):
        REGISTRY.posts[key] = (label, _posts.write)
    REGISTRY.actions.append(ActionSpec('essai_pour_a', 'Essai pour A', lambda w: None, tab='FAO', group='Essai',
                                       posts=('fraise_a',), plugin='essai'))
    try:
        yield
    finally:
        REGISTRY.posts.clear()
        REGISTRY.posts.update(old_posts)
        REGISTRY.actions[:] = old_actions
        if had:
            REGISTRY.machines = old_machines
        else:
            del REGISTRY.machines


class Machines(unittest.TestCase):

    def test_each_machine_is_offered_once(self):
        import importlib
        try:
            MC = importlib.import_module('vectordrive.cam.machines')
        except ImportError:
            self.fail('pas de machines dans la FAO')                        # avant
        with declared():
            got = [(k, label, m.key if m is not None else None) for k, label, m in MC.choices(post.posts(''))]
            self.assertEqual(got, [('poste_a', 'Fraiseuse A', 'fraise_a'), ('poste_b', 'Fraiseuse B', 'fraise_b'),
                                   ('poste_c', 'Laser C', 'laser_c'), ('libre', 'Poste libre', None)])
            self.assertEqual(MC.of_post('vieux_a').key, 'fraise_a')         # le double : même machine, plus proposé
            self.assertEqual(MC.kind_of('poste_c'), 'laser')
            self.assertEqual(MC.resolve(MC.by_key('laser_d'), post.posts('')), '')     # à configurer
            self.assertIsNone(MC.of_post('libre'))
        self.assertEqual(MC.choices({'x': 'X'}), [('x', 'X', None)])        # sans machine déclarée : la liste telle quelle


class Ribbon(unittest.TestCase):

    def window(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()

        def close():
            w.modified = False
            w.close()
        self.addCleanup(close)
        return w

    def test_fao_ribbons_follow_the_machine(self):
        with declared():
            w = self.window()
            self.assertIn('machine_fraise_a', w.A)                          # avant : aucun bouton de machine
            r = w.ribbon
            titles = [r.tabText(i) for i in range(r.count())]
            self.assertIn('FAO laser', titles)
            self.assertLess(titles.index('FAO 3D'), titles.index('FAO laser'))
            cp = w.cam_panel
            # la liste des post-processeurs : chaque machine une fois, le double retiré
            self.assertEqual([cp.post.itemData(i) for i in range(cp.post.count())],
                             ['poste_a', 'poste_b', 'poste_c', 'libre'])
            self.assertEqual(cp.post.itemText(0), 'Fraiseuse A')
            # un clic sur une machine : son post-processeur devient celui du dessin, son bouton est enfoncé
            w.A['machine_fraise_b'].trigger()
            self.assertEqual(cp.setup().post, 'poste_b')
            self.assertEqual([k for k in ('fraise_a', 'fraise_b', 'laser_c', 'laser_d')
                              if w.A[f'machine_{k}'].isChecked()], ['fraise_b'])
            self.assertFalse(w.A['essai_pour_a'].isVisible())
            self.assertIn('cam_new_decoupe', w.cam_palette.items)
            self.assertNotIn('cam_new_laser', w.cam_palette.items)          # une fraiseuse : plus de parcours laser
            self.assertTrue(cp.laser_row.isHidden())
            self.assertTrue(w.set_machine('fraise_a'))
            self.assertEqual(cp.setup().post, 'poste_a')                    # « poste_a2 » n'est pas installé : le suivant
            self.assertTrue(w.A['essai_pour_a'].isVisible())                # l'action du plugin, pour cette machine seule
            # un laser : sa palette, sa rangée « champ de marquage »
            w.A['machine_laser_c'].trigger()
            self.assertEqual(cp.setup().post, 'poste_c')
            self.assertIn('cam_new_laser', w.cam_palette.items)
            self.assertNotIn('cam_new_decoupe', w.cam_palette.items)
            self.assertIn('cam_new_instruction', w.cam_palette.items)       # l'instruction machine : pour toutes
            self.assertFalse(cp.laser_row.isHidden())
            # une machine pas encore configurée : le dessin garde la sienne
            w.A['machine_laser_d'].trigger()
            self.assertEqual(cp.setup().post, 'poste_c')
            self.assertEqual([k for k in ('fraise_a', 'fraise_b', 'laser_c', 'laser_d')
                              if w.A[f'machine_{k}'].isChecked()], ['laser_c'])
            # un dessin réglé sur le double : c'est la machine A, et F10 propose son meilleur post-processeur
            s = cp.setup()
            s.post = 'vieux_a'
            cp.save(s)
            cp.refresh()
            self.assertTrue(w.A['machine_fraise_a'].isChecked())
            self.assertIn('Fraiseuse A', cp.post_label.text())
            dlg = w.options_dialog(exec_dialog=False)
            box = dlg.widgets['fao/post']
            self.assertEqual([box.itemData(i) for i in range(box.count())], ['poste_a', 'poste_b', 'poste_c', 'libre'])
            self.assertEqual(box.currentData(), 'poste_a')
            dlg.close()

    def test_nothing_changes_without_machines(self):
        w = self.window()                                                   # cœur seul : aucune machine déclarée
        r = w.ribbon
        self.assertNotIn('FAO laser', [r.tabText(i) for i in range(r.count())])
        self.assertFalse([k for k in w.A if k.startswith('machine_')])
        self.assertIn('cam_new_laser', w.cam_palette.items)
        self.assertIn('cam_new_decoupe', w.cam_palette.items)
        self.assertIn('laser_coupon', w.A)                                  # avant : le coupon n'avait pas de commande


if __name__ == '__main__':
    unittest.main()
