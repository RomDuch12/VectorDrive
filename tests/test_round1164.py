"""Round 1164 (demande : « Invest debug improve in autonomy ») : limites connues des rounds 1155 et 1156 levées.
Favori d'un bouton Mode de TypeEdit 13 = le bouton même (il ouvre son onglet) ; pas de doublon dans la barre d'accès
rapide ; identifiants stables des boutons de l'onglet « VectorDrive » (anciens relus) ; logo d'un BAT pris sur un
partage copié hors du fil de l'interface. La disposition TypeEdit est celle, synthétique, de test_round1155 ; le
partage est un dossier temporaire tenu pour tel (aucun réseau), sa lenteur simulée."""
import json
import os
import pathlib
import tempfile
import threading
import time
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1164.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ.setdefault('VECTORDRIVE_KEYS_MEMORY', '1')

from PySide6.QtGui import QColor, QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from tests import test_round1155 as T  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE_MODE = 'avant : le favori d’un bouton Mode était la commande de sa famille (la palette), pas son onglet'
BEFORE_TWIN = 'avant : la même commande pouvait paraître deux fois dans la barre d’accès rapide'
BEFORE_IDS = 'avant : l’identifiant suivait la première commande de l’onglet, qui change si on le range autrement'
BEFORE_LOGO = 'avant : le logo d’un partage était copié dans le fil de l’interface (fenêtre gelée)'
BEFORE_RACE = 'avant : deux copies du même logo en même temps écrivaient le même fichier temporaire'
DUP = 'te_mode:ID_COMPO_SHOWPALDUPLICATION'                       # un bouton Mode de famille (son onglet)
POINT = 'te_mode:ID_COMPO_SHOWPALPOINT'                           # un bouton Mode d'outil (l'outil Point aussi)


class Favorites(T.Base):
    def test_mode_family_favorite_opens_its_tab(self):
        w = self.w
        dup = T.mode_action(w, 'Duplication')
        m = self.right_click(T.te_button(w, dup))
        next(a for a in m.actions() if a.text() == T.FAV).trigger()
        self.assertEqual(w.favorite_keys(), [DUP], BEFORE_MODE)
        self.assertIn(dup, w.te_quickbar.actions())                   # le bouton Mode même, au bout de la barre
        self.assertNotIn(w.A['duplicate'], w.te_quickbar.actions())
        b = w.te_quickbar.widgetForAction(dup)
        self.assertTrue(w._is_favorite_button(b))
        self.assertIn(T.UNFAV, T.texts(self.right_click(b)))
        dup.trigger()                                                 # il ouvre son onglet, comme dans le ruban
        r = w.ribbon
        self.assertEqual(r.widget(r.currentIndex()).property('te_context'), '1006')
        self.assertIn(T.UNFAV, T.texts(self.right_click(T.te_button(w, dup))))
        w.set_theme('clair')                                          # disposition VectorDrive : sa commande
        self.assertFalse(w.layout_active)
        self.assertEqual(w.favorite_keys(), [DUP])
        self.assertIn(w.A['duplicate'], w.fav_bar.actions())
        w.set_theme('typeedit13')                                     # et de retour : le bouton Mode
        self.assertIn(T.mode_action(w, 'Duplication'), w.te_quickbar.actions())
        self.assertTrue(w.remove_favorite(DUP))
        self.assertEqual(w.favorite_keys(), [])

    def test_no_twin_in_the_quick_bar(self):
        w = self.w
        text_mode = T.mode_action(w, 'Texte')                         # dans la barre d'accès rapide de TypeEdit
        self.assertIn(text_mode, w.te_quickbar.actions())
        self.assertFalse(w.add_favorite('tool_text'), BEFORE_TWIN)    # sa commande : déjà là par le bouton Mode
        self.assertNotIn(w.A['tool_text'], w.te_quickbar.actions())
        self.assertIn('déjà dans la barre', w.statusBar().currentMessage())
        self.assertEqual(w.favorite_keys(), [])
        w.settings.setValue('ruban/favoris', ['tool_text', 'tool_rect'])     # retenus avant : pas deux fois
        w.refresh_favorites()
        self.assertNotIn(w.A['tool_text'], w.te_quickbar.actions())
        self.assertIn(w.A['tool_rect'], w.te_quickbar.actions())
        m = self.right_click(w.te_quickbar.widgetForAction(text_mode))       # le bouton Mode : la retirer
        next(a for a in m.actions() if a.text() == T.UNFAV).trigger()
        self.assertEqual(w.favorite_keys(), ['tool_rect'])
        self.assertTrue(w.add_favorite(POINT))                        # un bouton Mode d'outil favori, puis l'outil
        self.assertFalse(w.add_favorite('tool_node'))
        self.assertEqual(sum(1 for a in w.te_quickbar.actions()
                             if a is T.mode_action(w, 'Point') or a is w.A['tool_node']), 1)
        self.assertTrue(w.add_favorite('tool_star'))                  # déjà là telle quelle : comme avant
        self.assertEqual(w.favorite_keys(), ['tool_rect', POINT, 'tool_star'])

    def test_family_mode_and_its_command_live_together(self):
        w = self.w
        self.assertTrue(w.add_favorite(DUP), BEFORE_MODE)
        self.assertTrue(w.add_favorite('duplicate'))                  # lui ouvre son onglet, elle se lance
        acts = w.te_quickbar.actions()
        self.assertIn(T.mode_action(w, 'Duplication'), acts)
        self.assertIn(w.A['duplicate'], acts)
        m = self.right_click(T.te_button(w, T.mode_action(w, 'Duplication')))
        next(a for a in m.actions() if a.text() == T.UNFAV).trigger()
        self.assertEqual(w.favorite_keys(), ['duplicate'])            # le bouton Mode retiré, pas la commande

    def test_menu_of_a_mode_favorite_in_the_vectordrive_layout(self):
        w = self.w
        self.assertTrue(w.add_favorite(DUP), BEFORE_MODE)
        w.set_theme('clair')                                          # il y est la commande « Dupliquer »
        t = T.texts(self.right_click(w.fav_bar.widgetForAction(w.A['duplicate'])))
        self.assertIn(T.UNFAV, t)
        self.assertNotIn(T.FAV, t)
        m = self.right_click(w.fav_bar.widgetForAction(w.A['duplicate']))
        next(a for a in m.actions() if a.text() == T.UNFAV).trigger()
        self.assertEqual(w.favorite_keys(), [])

    def test_mode_favorite_can_be_dragged(self):
        from PySide6.QtCore import Qt
        from vectordrive.ui import fav_bar
        w = self.w
        self.assertTrue(w.add_favorite('tool_rect'))
        self.assertTrue(w.add_favorite(DUP), BEFORE_MODE)
        w.arrange_favorites(True)
        self.addCleanup(w.arrange_favorites, False)
        dragged = []

        class FakeDrag:                                  # (le vrai glisser attendrait la souris)
            def __init__(self, _src):
                pass

            def setMimeData(self, mime):                 # noqa: N802
                dragged.append(bytes(mime.data(fav_bar.MIME)).decode('utf-8'))

            def setPixmap(self, _p):                     # noqa: N802
                pass

            def setHotSpot(self, _p):                    # noqa: N802
                pass

            def exec(self, *_a):
                return Qt.DropAction.MoveAction
        b = w.te_quickbar.widgetForAction(T.mode_action(w, 'Duplication'))
        with mock.patch.object(fav_bar, 'QDrag', FakeDrag):
            w._fav_arranger.drag(b)
        self.assertEqual(dragged, [DUP])
        w._fav_arranger.apply(DUP, 'tool_rect')                       # déposé devant Rectangle
        app.processEvents()
        self.assertEqual(w.favorite_keys(), [DUP, 'tool_rect'])

    def test_renamed_button_of_an_own_tab(self):
        from PySide6.QtCore import QPoint
        from PySide6.QtWidgets import QToolButton
        from vectordrive.ui import ribbon_editor as RE
        w = self.w
        self.addCleanup(lambda: (w.settings.remove(RE.KEY), w.settings.remove(RE.MORE)))
        RE.save_all(w.settings, [{'titre': 'Atelier 1164', 'position': 'debut', 'groupes': [
            {'titre': 'G', 'commandes': [{'key': 'duplicate', 'big': True, 'texte': 'Dup'}]}]}])
        w._build_custom_tab()
        b = next(x for x in w.ribbon.findChildren(QToolButton) if isinstance(x.defaultAction(), RE.RelayAction)
                 and x.defaultAction().src is w.A['duplicate'])
        self.assertTrue(w.add_favorite('duplicate'))
        m = w._ribbon_button_menu(b, QPoint(0, 0), exec_menu=False)
        self.addCleanup(m.deleteLater)
        self.assertIn(T.UNFAV, T.texts(m), 'un relais (bouton renommé) : sa commande d’origine est favorite')
        next(a for a in m.actions() if a.text() == T.UNFAV).trigger()
        self.assertEqual(w.favorite_keys(), [])

    def test_favorites_window_refuses_the_same_twins(self):
        w = self.w
        dlg = w.favorites_dialog(exec_dialog=False)
        self.addCleanup(dlg.deleteLater)
        self.assertFalse(dlg.add('tool_text'), BEFORE_TWIN)           # Texte (bouton Mode d'outil) déjà là
        self.assertTrue(dlg.add('tool_rect'))
        self.assertFalse(dlg.add('tool_rect'))
        self.assertTrue(dlg.add('duplicate'))                         # commande d'une famille : acceptée
        self.assertEqual(dlg.keys(), ['tool_rect', 'duplicate'])

    def test_same_command_under_two_keys(self):
        w = self.w
        w.A['essai_alias_1164'] = w.A['tool_rect']                    # une commande sous deux clés
        self.addCleanup(w.A.pop, 'essai_alias_1164', None)
        self.assertTrue(w.add_favorite('tool_rect'))
        self.assertFalse(w.add_favorite('essai_alias_1164'), BEFORE_TWIN)
        self.assertEqual(w.favorite_keys(), ['tool_rect'])


class TabIds(T.Base):
    def vd_page(self, w, title):
        r = w.ribbon
        return next(r.page(i) for i in range(r.count())
                    if r.tabText(i) == title and not r.widget(i).property('te_layout'))

    def test_ids_survive_a_rearranged_tab(self):
        w = self.w
        g = T.vd_group(w)
        ids = [w._button_id(b) for b in g.buttons()]
        self.assertIn('te_onglet:@edition', ids, BEFORE_IDS)          # le nom interne de l'onglet
        self.assertEqual(len(set(ids)), len(ids))
        self.assertTrue(w.ribbon_button_op(g.buttons()[0], 'small'))
        w.set_theme('clair')                                          # disposition VectorDrive : Edition rangé
        title, groups = w._vd_tab_menus()[0]
        first = w._action_key(groups[0][1][0])
        btn = next(b for b in self.vd_page(w, title).groups()[0].buttons() if w._action_key(b.defaultAction()) == first)
        self.assertTrue(w.ribbon_button_op(btn, 'last'))
        self.assertNotEqual(w._action_key(w._vd_tab_menus()[0][1][0][1][0]), first)    # sa 1re commande a changé
        w.set_theme('typeedit13')
        g = T.vd_group(w)
        self.assertEqual([w._button_id(b) for b in g.buttons()], ids)                  # mêmes identifiants…
        self.assertIs(g.entry_big(g.buttons()[0]), False)                              # … taille retenue
        self.assertTrue(all(x.startswith('te_onglet:@') for x in ids))               # (« @ » : jamais une commande)
        self.assertGreater(len(ids), 5)

    def test_old_ids_are_read_again(self):
        from vectordrive.ui.main_window import MainWindow
        w = self.w
        firsts = [next(w._action_key(a) for _g, acts in gs for a in acts if w._action_key(a))
                  for _t, gs in w._vd_tab_menus()]
        old = [f'te_onglet:{f}' for f in firsts]                      # ceux du round 1155
        self.assertEqual(len(set(old)), len(old))
        conf = {'te:' + old[0]: [[k, True] for k in old[1:]] + [[old[0], False]]}
        w.settings.setValue('ruban/boutons', json.dumps(conf))        # retenu avant : Edition petit, au bout
        T.close(w)
        self.open.remove(w)
        w2 = MainWindow()
        self.open.append(w2)
        self.assertTrue(w2.layout_active)
        g = T.vd_group(w2)
        ids = [w2._button_id(b) for b in g.buttons()]
        self.assertEqual(ids[-1], 'te_onglet:@edition', BEFORE_IDS)   # relu sous le nouvel identifiant
        self.assertIs(g.entry_big(g.buttons()[-1]), False)
        self.assertTrue(all(x.startswith('te_onglet:@') for x in ids))
        self.assertTrue(w2.ribbon_button_op(g.buttons()[-1], 'first'))           # retenu ensuite sous le nouveau
        saved = json.loads(w2.settings.value('ruban/boutons'))
        self.assertNotIn('te:' + old[0], saved)
        self.assertIn('te:te_onglet:@edition', saved)
        self.assertTrue(all(k.startswith('te_onglet:@') for k, _b in saved['te:te_onglet:@edition']))


def png(path, color='#c02010') -> str:
    img = QImage(40, 20, QImage.Format.Format_RGB32)
    img.fill(QColor(color))
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    assert img.save(str(path))
    return str(path)


def names(folder) -> list:
    return sorted(os.listdir(folder)) if os.path.isdir(folder) else []


class ShareLogos(unittest.TestCase):
    """Fichier › BAT validé avec un logo d'un partage (dossier temporaire tenu pour un partage, copie ralentie)."""

    def setUp(self):
        from vectordrive.ui import symbols
        from vectordrive.ui.main_window import MainWindow
        self.dir = pathlib.Path(tempfile.mkdtemp())
        self.lib = self.dir / 'bibliotheque'
        self.lib.mkdir()
        self.logos = self.lib / 'Logos BAT'
        self.share = self.dir / 'partage'
        env = mock.patch.dict(os.environ, {'VECTORDRIVE_BIBLIOTHEQUE': str(self.lib)})
        env.start()
        self.addCleanup(env.stop)
        self.gate = threading.Event()                    # le partage « répond » quand on l'ouvre
        self.calls, self.broken = [], None
        real = symbols.keep_copy

        def slow(src, folder, made=None):
            self.calls.append((str(src), threading.current_thread() is threading.main_thread()))
            self.gate.wait(3)                            # un partage lent (simulé)
            if self.broken is not None:
                raise self.broken
            return real(src, folder, made)
        share = os.path.normcase(str(self.share))
        for name, fake in (('keep_copy', slow), ('is_remote', lambda p: os.path.normcase(str(p)).startswith(share))):
            p = mock.patch.object(symbols, name, side_effect=fake)
            p.start()
            self.addCleanup(p.stop)
        self.w = w = MainWindow()
        self.addCleanup(self.close)
        s = w.settings                                   # les réglages partagés : remis comme avant
        s.beginGroup('bat')
        old = {k: s.value(k) for k in s.allKeys()}
        s.endGroup()
        self.addCleanup(self.restore, old)
        for k in ('bat/logos', 'bat/logos_copies', 'bat/logo', 'bat/logo2', 'bat/watermark_logo'):
            s.remove(k)

    def restore(self, old):
        s = self.w.settings
        s.remove('bat')
        for k, v in old.items():
            s.setValue(f'bat/{k}', v)

    def close(self):
        self.gate.set()
        th = getattr(self.w, '_logos_thread', None)
        if th is not None:
            th.join(5)
        app.processEvents()
        for t in self.w.docs:
            t.modified = False
        self.w.modified = False
        self.w.close()

    def bat(self, logo=None):
        """Le BAT validé (fenêtre jamais montrée) ; rend (le cartouche, le logo proposé en cours)."""
        from vectordrive.ui.batdialog import BatDialog
        seen = {}

        def fake_exec(dlg):
            if logo is not None:
                dlg.set_logo(dlg.logo, logo)
            seen['current'] = dlg.logo.currentData()
            return 1
        with mock.patch.object(BatDialog, 'exec', fake_exec):
            return self.w._proof_info(), seen['current']

    def finish(self):
        """La copie en cours finie, et son retour reçu par l'interface."""
        th = getattr(self.w, '_logos_thread', None)
        self.assertIsNotNone(th, BEFORE_LOGO)
        th.join(5)
        self.assertFalse(th.is_alive())
        for _ in range(100):
            app.processEvents()
            if not getattr(self.w, '_logos_busy', None):
                break
            time.sleep(0.01)

    def test_share_logo_copied_without_freezing(self):
        a = png(self.share / 'Clients' / 'logo.png')
        t0 = time.monotonic()
        info, _cur = self.bat(a)
        took = time.monotonic() - t0
        self.assertEqual(info.logo, a)                                       # ce BAT : l'original
        self.assertLess(took, 2.5, BEFORE_LOGO)                              # sans attendre le partage
        self.assertEqual(names(self.logos), [])                              # copie pas encore faite
        self.gate.set()
        self.finish()
        self.assertEqual(names(self.logos), ['logo.png'])
        self.assertEqual(self.calls, [(a, False)])                           # hors du fil de l'interface
        copies = json.loads(self.w.settings.value('bat/logos_copies'))
        self.assertEqual(copies, {os.path.normcase(a): 'logo.png'})
        kept = str(self.logos / 'logo.png')
        info, cur = self.bat()                                               # le BAT suivant : sa copie
        self.assertEqual((cur, info.logo), (kept, kept))

    def test_one_copy_at_a_time_and_errors_told(self):
        a = png(self.share / 'logo.png')
        self.bat(a)
        self.bat(a)                                                          # la première copie pas finie
        self.assertEqual(len(self.calls), 1, BEFORE_LOGO)
        self.gate.set()
        self.finish()
        self.assertEqual(names(self.logos), ['logo.png'])
        self.broken = OSError('partage coupé')
        b = png(self.share / 'autre.png', '#1040c0')
        info, _cur = self.bat(b)
        self.assertEqual(info.logo, b)                                       # le BAT se fait quand même
        self.finish()
        msg = self.w.statusBar().currentMessage()
        self.assertIn('partage coupé', msg)
        self.assertIn('autre.png', msg)
        self.assertFalse(any(main for _p, main in self.calls))

    def test_same_logo_written_otherwise_copied_once(self):
        a = png(self.share / 'logo.png')
        if os.path.normcase(a) != os.path.normcase(a.upper()):
            self.skipTest('système de fichiers sensible à la casse')
        self.bat(a)
        self.bat(a.upper())                                                  # le même fichier, écrit autrement
        self.assertEqual(len(self.calls), 1, BEFORE_LOGO)
        self.gate.set()
        self.finish()
        self.assertEqual(names(self.logos), ['logo.png'])

    def test_thread_that_cannot_start(self):
        a = png(self.share / 'logo.png')
        self.assertTrue(hasattr(self.w, '_keep_logos_later'), BEFORE_LOGO)
        with mock.patch.object(threading.Thread, 'start', side_effect=RuntimeError('plus de fil')):
            got = self.w._keep_logos_later([a])
        self.assertIsNone(got)
        self.assertFalse(self.w._logos_busy)                                 # pas tenu pour « en cours »
        self.assertIn('plus de fil', self.w.statusBar().currentMessage())
        self.assertIsNone(getattr(self.w, '_logos_thread', None))

    def test_relay_gone_before_the_end(self):
        from shiboken6 import delete
        a = png(self.share / 'logo.png')
        self.bat(a)
        th = getattr(self.w, '_logos_thread', None)
        self.assertIsNotNone(th, BEFORE_LOGO)
        errors = []
        hook = threading.excepthook
        threading.excepthook = errors.append
        self.addCleanup(setattr, threading, 'excepthook', hook)
        delete(self.w._logo_sig)                         # comme une fenêtre détruite pendant la copie
        self.gate.set()
        th.join(5)
        self.assertEqual(errors, [])                     # rien de levé dans le fil
        self.assertEqual(names(self.logos), ['logo.png'])


class KeepCopyRace(unittest.TestCase):
    def test_two_copies_at_once_of_the_same_logo(self):
        import shutil
        from vectordrive.ui import symbols
        d = pathlib.Path(tempfile.mkdtemp())
        src, folder = png(d / 'source' / 'logo.png'), d / 'Logos BAT'
        real, tmps, out, errors = shutil.copy2, [], [], []
        both = threading.Barrier(2, timeout=3)           # les deux copies en cours au même moment

        def copy2(a, b, **k):
            tmps.append(str(b))
            try:
                both.wait()
            except threading.BrokenBarrierError:
                pass
            return real(a, b, **k)

        def run():
            try:
                out.append(symbols.keep_copy(src, folder))
            except Exception as ex:                      # noqa: BLE001 — rendue à l'essai
                errors.append(ex)
        with mock.patch.object(shutil, 'copy2', copy2):
            ths = [threading.Thread(target=run) for _k in range(2)]
            for th in ths:
                th.start()
            for th in ths:
                th.join(10)
        self.assertEqual(len(set(tmps)), 2, BEFORE_RACE)                     # chacune son fichier temporaire
        self.assertEqual(errors, [])
        self.assertEqual(out, [folder / 'logo.png'] * 2)                     # une seule copie, la même pour les deux
        self.assertEqual(names(folder), ['logo.png'])                        # sans reste

    def test_read_only_logo_leaves_no_temporary(self):
        import stat
        from vectordrive.ui import symbols
        d = pathlib.Path(tempfile.mkdtemp())
        src, folder = png(d / 'source' / 'logo.png'), d / 'Logos BAT'
        os.chmod(src, stat.S_IREAD)                      # en lecture seule sur le partage
        self.addCleanup(os.chmod, src, stat.S_IREAD | stat.S_IWRITE)
        with mock.patch.object(os, 'rename', side_effect=OSError('disque plein')):
            with self.assertRaises(OSError) as cm:
                symbols.keep_copy(src, folder)
        self.assertIn('disque plein', str(cm.exception))                     # l'erreur de la copie, pas celle du ménage
        self.assertEqual(names(folder), [])                                  # le fichier temporaire retiré
        kept = symbols.keep_copy(src, folder)
        self.assertTrue(os.access(kept, os.W_OK))                            # la copie gardée : modifiable

    @staticmethod
    def files_in(folder, names_, age=2 * 86400):
        """Des fichiers de `names_`, dont le contenu a la date d'il y a `age` secondes (comme `copy2` la reporte)."""
        folder.mkdir(parents=True, exist_ok=True)
        old = time.time() - age
        for n in names_:
            (folder / n).write_bytes(b'x')
            os.utime(folder / n, (old, old))

    def test_stale_temporaries_purged(self):
        from vectordrive.ui import symbols
        d = pathlib.Path(tempfile.mkdtemp())
        src, folder = png(d / 'source' / 'logo.png'), d / 'Logos BAT'
        ours = ['.vdkeep.logo.png.ab12cd34.tmp', '.vdkeep.autre.svg.zz99yy88.tmp']
        others = ['.logo.png.ab12cd34.tmp', 'notes.tmp', '.x.tmp', '.vdkeep.x.tmp']
        self.files_in(folder, ours + others)
        symbols.keep_copy(src, folder)                   # créés à l'instant : pas encore des restes
        self.assertEqual(names(folder), sorted(ours + others + ['logo.png']))
        later = time.time() + 2 * 86400
        with mock.patch('time.time', return_value=later):           # deux jours plus tard
            symbols.keep_copy(src, folder)
        self.assertEqual(names(folder), sorted(others + ['logo.png']))      # les nôtres seulement

    def test_user_file_with_a_close_name_is_kept_in_the_favorites(self):
        from vectordrive.ui import symbols
        d = pathlib.Path(tempfile.mkdtemp())
        env = mock.patch.dict(os.environ, {'VECTORDRIVE_BIBLIOTHEQUE': str(d / 'bibliotheque')})
        env.start()
        self.addCleanup(env.stop)
        favs = symbols.internal_favorites()              # « Copier dans la bibliothèque interne » y passe aussi
        user = '.plan.dxf.ab12cd34.tmp'                  # un fichier de l'utilisateur, au nom proche
        self.files_in(favs, [user])
        src = png(d / 'source' / 'logo.png')
        with mock.patch('time.time', return_value=time.time() + 2 * 86400):
            symbols.keep_copy(src, favs)
        self.assertEqual(names(favs), [user, 'logo.png'], 'un fichier de l’utilisateur n’est jamais purgé')

    def test_temporary_of_a_copy_in_progress_is_not_purged(self):
        import shutil
        from vectordrive.ui import symbols
        d = pathlib.Path(tempfile.mkdtemp())
        src, folder = png(d / 'source' / 'logo.png'), d / 'Logos BAT'
        real, copied, go, out, errors = shutil.copy2, threading.Event(), threading.Event(), [], []

        def copy2(a, b, **k):
            r = real(a, b, **k)                          # (le temporaire : la date de l'original)
            copied.set()
            go.wait(5)
            return r

        def run():
            try:
                out.append(symbols.keep_copy(src, folder))
            except Exception as ex:                      # noqa: BLE001 — rendue à l'essai
                errors.append(ex)
        with mock.patch.object(shutil, 'copy2', copy2):
            th = threading.Thread(target=run)
            th.start()
            self.assertTrue(copied.wait(5))
            tmps = [n for n in names(folder) if n.endswith('.tmp')]
            self.assertEqual(len(tmps), 1)
            with mock.patch.object(symbols, 'KEEP_TMP_AGE', -60.0):     # tout serait « vieux »
                symbols._purge_tmp(folder)
            self.assertEqual([n for n in names(folder) if n.endswith('.tmp')], tmps, 'copie en cours : gardé')
            go.set()
            th.join(10)
        self.assertEqual(errors, [])
        self.assertEqual(out, [folder / 'logo.png'])
        self.assertEqual(names(folder), ['logo.png'])


class Place(unittest.TestCase):
    """La pose de la copie : jamais par-dessus un fichier pris entre-temps."""

    def setUp(self):
        d = pathlib.Path(tempfile.mkdtemp())
        self.src, self.folder = png(d / 'source' / 'logo.png'), d / 'Logos BAT'

    def test_name_taken_at_the_last_moment_gives_the_next_one(self):
        from vectordrive.ui import symbols
        real, calls = os.rename, []

        def rename(a, b):
            calls.append(b)
            if len(calls) == 1:
                raise FileExistsError(b)                 # pris par un autre programme, juste avant
            return real(a, b)
        with mock.patch.object(symbols, '_KEEP_LINK', False), mock.patch.object(os, 'rename', rename):
            kept = symbols.keep_copy(self.src, self.folder)
        self.assertEqual(kept, self.folder / 'logo (2).png')                 # le nom suivant, sans boucler
        self.assertEqual(names(self.folder), ['logo (2).png'])

    def test_hard_link_outside_windows(self):
        from vectordrive.ui import symbols
        real, links = os.link, []

        def link(a, b):
            links.append(b)
            if len(links) == 1:
                raise FileExistsError(b)
            return real(a, b)
        with mock.patch.object(symbols, '_KEEP_LINK', True), mock.patch.object(os, 'link', link), \
                mock.patch.object(os, 'rename', side_effect=AssertionError('rename écraserait')):
            kept = symbols.keep_copy(self.src, self.folder)
        self.assertEqual(kept, self.folder / 'logo (2).png')
        self.assertEqual(names(self.folder), ['logo (2).png'])                # le temporaire retiré
        self.assertEqual(kept.read_bytes(), pathlib.Path(self.src).read_bytes())

    def test_no_hard_links_on_this_disk(self):
        from vectordrive.ui import symbols
        with mock.patch.object(symbols, '_KEEP_LINK', True), \
                mock.patch.object(os, 'link', side_effect=PermissionError('pas de liens')):
            kept = symbols.keep_copy(self.src, self.folder)
        self.assertEqual(kept, self.folder / 'logo.png')                      # posée autrement
        self.assertEqual(names(self.folder), ['logo.png'])


class Names(unittest.TestCase):
    def test_favorite_name_on_one_line(self):
        from PySide6.QtGui import QAction
        from vectordrive.ui import fav_dialog
        self.assertEqual(fav_dialog.name(QAction('Texte\nvertical')), 'Texte vertical')


if __name__ == '__main__':
    unittest.main()
