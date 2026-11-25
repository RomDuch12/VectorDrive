"""Round 1156 (demande du 24/11) : « Bibliothèque : une interne est en place, les favoris dépliables arborescence,
peut contenir les logos utilisés pour les BaT + favoris fichiers; BaT enregistrer logos utilisés pour les prochaines
fois; »."""
import os
import pathlib
import tempfile
import threading
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1156.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ.setdefault('VECTORDRIVE_KEYS_MEMORY', '1')

from PySide6.QtCore import QSettings, Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Shape  # noqa: E402
from vectordrive.i18n import tr  # noqa: E402
from vectordrive.io import proof  # noqa: E402

app = QApplication.instance() or QApplication([])
UR = Qt.ItemDataRole.UserRole
BEFORE = 'avant : les logos d’un BAT n’étaient retenus que par leur chemin, et « Favoris » ne se dépliait pas'
DXF = "0\nSECTION\n2\nENTITIES\n0\nLINE\n8\n0\n10\n0\n20\n0\n11\n10\n21\n5\n0\nENDSEC\n0\nEOF\n"
SHARE = '\\\\poste-absent\\partage\\Clients'


def png(path, color='#c02010', w=40, h=20) -> str:
    """Un petit logo PNG d'une couleur (deux couleurs : deux contenus)."""
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(QColor(color))
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    assert img.save(str(path))
    DATES.append(1_700_000_000 + 60 * len(DATES))        # chaque logo a sa date (même taille, autre contenu)
    os.utime(path, (DATES[-1], DATES[-1]))
    return str(path)


DATES: list = []


def doc_of():
    d = Document()
    d.add(Shape(path=geom.Path([geom.rect(0, 0, 40, 40)]), tool=1))
    return d


def names(folder) -> list:
    return sorted(os.listdir(folder)) if os.path.isdir(folder) else []


def children(item) -> list:
    return [item.child(k).text(0) for k in range(item.childCount())]


class Base(unittest.TestCase):
    """Chaque essai a sa bibliothèque interne (dossier temporaire) et ses réglages (fichier temporaire)."""

    def setUp(self):
        self.dir = pathlib.Path(tempfile.mkdtemp())
        self.lib = self.dir / 'bibliotheque'
        self.lib.mkdir()
        env = mock.patch.dict(os.environ, {'VECTORDRIVE_BIBLIOTHEQUE': str(self.lib)})
        env.start()
        self.addCleanup(env.stop)
        self.st = QSettings(str(self.dir / 'reglages.ini'), QSettings.Format.IniFormat)
        from vectordrive.ui import symbols
        self.S = symbols
        self.logos = self.lib / 'Logos BAT'

    def panel(self, roots=None):
        self.st.setValue('symboles/dossiers', [str(r) for r in (roots or [self.lib])])
        p = self.S.SymbolPanel(self.st)
        self.addCleanup(self.drop, p)
        return p

    @staticmethod
    def drop(p):
        p._timer.stop()
        p._prev_timer.stop()
        p.list.clear()
        p.deleteLater()

    def favorites(self, p):
        node = p.tree.topLevelItem(1)
        self.assertEqual(node.data(0, UR), self.S.FAVORITES)
        return node


class KeepCopy(Base):
    def test_once_same_name_then_suffix(self):
        keep = getattr(self.S, 'keep_copy', None)
        self.assertIsNotNone(keep, BEFORE)
        a = png(self.dir / 'a' / 'logo.png', '#c02010')
        made = []
        first = keep(a, self.logos, made)
        self.assertEqual(first, self.logos / 'logo.png')                     # même nom, dossier créé
        self.assertEqual(first.read_bytes(), pathlib.Path(a).read_bytes())
        self.assertEqual(keep(a, self.logos, made), first)                   # même contenu : pas de doublon
        self.assertEqual((names(self.logos), made), (['logo.png'], [first]))
        b = png(self.dir / 'b' / 'logo.png', '#1040c0')                      # même nom, autre contenu
        second = keep(b, self.logos)
        self.assertEqual(second.name, 'logo (2).png')
        self.assertEqual(second.read_bytes(), pathlib.Path(b).read_bytes())
        self.assertEqual(keep(b, self.logos), second)                        # … reconnu ensuite
        self.assertEqual(keep(a, self.logos), first)
        self.assertEqual(keep(first, self.logos), first)                     # déjà dans le dossier : pas recopié
        self.assertEqual(names(self.logos), ['logo (2).png', 'logo.png'])
        self.assertIsNone(keep(self.dir / 'absent.png', self.logos))         # pas un fichier : rien, sans erreur

    def test_where_the_logos_go(self):
        folder = getattr(self.S, 'logo_library', lambda: None)()
        self.assertEqual(folder, self.lib / 'Logos BAT', BEFORE)             # dans la bibliothèque interne
        self.assertEqual(self.S.internal_favorites(), self.lib / 'Favoris')
        self.assertFalse(folder.exists())                                    # créé à la première copie seulement


class Bat(Base):
    """La fenêtre du BAT : ses listes de logos et ce qu'elle retient à la validation."""

    def setUp(self):
        super().setUp()
        self.parent = QWidget()
        self.parent.settings = self.st
        self.addCleanup(self.parent.deleteLater)

    def dialog(self, **k):
        from vectordrive.ui.batdialog import BatDialog
        dlg = BatDialog(self.parent, doc_of(), proof.ProofInfo(**k))
        self.addCleanup(dlg.deleteLater)
        return dlg

    def validate(self, **logos):
        """Un BAT validé avec ces logos (logo, logo2, watermark_logo) ; rend les erreurs de copie."""
        dlg = self.dialog()
        for key, path in logos.items():
            dlg.set_logo(getattr(dlg, key), path)
        dlg.result_info()
        return dlg.remember_logos()

    @staticmethod
    def choices(box) -> list:
        return [box.itemData(k) for k in range(1, box.count() - 1)]         # sans « Aucun » ni « Choisir… »

    def test_each_logo_copied_once(self):
        a, b = png(self.dir / 'a' / 'logo.png'), png(self.dir / 'b' / 'client.png', '#1040c0')
        self.assertEqual(self.validate(logo=a, logo2=b, watermark_logo=a), [], BEFORE)
        self.assertEqual(names(self.logos), ['client.png', 'logo.png'], BEFORE)
        self.assertEqual(self.validate(logo=a, logo2=b), [])                 # second BAT : pas de doublon
        self.assertEqual(names(self.logos), ['client.png', 'logo.png'])
        box = self.dialog().logo
        self.assertEqual(self.choices(box), [a, b])                          # les originaux, pas en plus leur copie
        self.assertEqual(box.itemData(1, Qt.ItemDataRole.ToolTipRole), a)    # (la bulle : le chemin entier)

    def test_original_gone_copy_offered(self):
        a = png(self.dir / 'a' / 'logo.png')
        self.validate(logo=a)
        os.remove(a)                                                         # l'original a bougé
        kept = str(self.logos / 'logo.png')
        dlg = self.dialog(logo=a)                                            # le BAT suivant le nommait encore
        self.assertEqual(self.choices(dlg.logo), [kept], BEFORE)
        self.assertEqual(dlg.logo.currentData(), kept)
        self.assertEqual(dlg.result_info().logo, kept)                       # le BAT emploie la copie
        self.assertEqual(self.choices(dlg.watermark_logo), [kept])
        self.assertEqual(dlg.remember_logos(), [])                           # validé avec la copie : rien de plus
        self.assertEqual(names(self.logos), ['logo.png'])
        self.assertEqual(self.choices(self.dialog().logo2), [kept])

    def test_same_name_other_content(self):
        a = png(self.dir / 'a' / 'logo.png', '#c02010')
        b = png(self.dir / 'b' / 'logo.png', '#1040c0')
        self.validate(logo=a)
        self.validate(logo=b)
        self.assertEqual(names(self.logos), ['logo (2).png', 'logo.png'], BEFORE)
        self.assertEqual((self.logos / 'logo (2).png').read_bytes(), pathlib.Path(b).read_bytes())
        self.assertEqual(self.choices(self.dialog().logo), [b, a])           # les deux originaux, sans leurs copies
        os.remove(b)
        self.assertEqual(self.choices(self.dialog().logo), [str(self.logos / 'logo (2).png'), a])
        os.remove(a)
        self.assertEqual(self.choices(self.dialog().logo),
                         [str(self.logos / 'logo (2).png'), str(self.logos / 'logo.png')])

    def test_kept_logos_offered_beyond_the_recent_ones(self):
        a = png(self.dir / 'a' / 'logo.png')
        self.validate(logo=a)
        old = png(self.logos / 'ancien.png', '#208040')                      # gardé là, plus parmi les derniers
        (self.logos / 'notes.zzz').write_text('pas un logo', encoding='utf-8')
        self.assertEqual(self.choices(self.dialog().logo), [a, old], BEFORE)

    def test_copy_error_is_told_never_raised(self):
        a = png(self.dir / 'a' / 'logo.png')
        self.assertTrue(hasattr(self.S, 'keep_copy'), BEFORE)
        with mock.patch.object(self.S, 'keep_copy', side_effect=OSError('disque plein')):
            errors = self.validate(logo=a)
        self.assertEqual(len(errors), 1)
        self.assertIn('logo.png', errors[0])
        self.assertIn('disque plein', errors[0])
        self.assertEqual(self.choices(self.dialog().logo), [a])              # retenu quand même, par son chemin


class Window(Base):
    """De bout en bout : Fichier › BAT validé dans la fenêtre principale."""

    def setUp(self):
        super().setUp()
        from vectordrive.ui.main_window import MainWindow
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
        for t in self.w.docs:
            t.modified = False
        self.w.modified = False
        self.w.close()

    def bat(self, logo=None):
        """Le BAT validé (fenêtre jamais montrée) ; rend (le cartouche, les logos proposés, le logo en cours)."""
        from vectordrive.ui.batdialog import BatDialog
        seen = {}

        def fake_exec(dlg):
            if logo is not None:
                dlg.set_logo(dlg.logo, logo)
            seen['choices'] = [dlg.logo.itemData(k) for k in range(1, dlg.logo.count() - 1)]
            seen['current'] = dlg.logo.currentData()
            return 1
        with mock.patch.object(BatDialog, 'exec', fake_exec):
            return self.w._proof_info(), seen['choices'], seen['current']

    def test_valid_bat_keeps_its_logo_in_the_library(self):
        a = png(self.dir / 'a' / 'logo.png')
        info, _c, _cur = self.bat(a)
        self.assertEqual(info.logo, a)                                       # ce BAT : l'original
        self.assertEqual(names(self.logos), ['logo.png'], BEFORE)            # … copié pour les fois suivantes
        app.processEvents()                                                  # (la Bibliothèque suit, après le BAT)
        top = next(self.w.symbols.tree.topLevelItem(i) for i in range(self.w.symbols.tree.topLevelItemCount())
                   if self.w.symbols.tree.topLevelItem(i).data(0, UR) == str(self.lib))
        top.setExpanded(True)
        self.assertIn('Logos BAT', children(top))                            # vu dans la Bibliothèque, comme les autres
        info, choices, cur = self.bat()                                      # second BAT : pas de doublon
        self.assertEqual((names(self.logos), choices, cur, info.logo), (['logo.png'], [a], a, a))
        os.remove(a)                                                         # l'original supprimé : la copie
        kept = str(self.logos / 'logo.png')
        info, choices, cur = self.bat()
        self.assertEqual((choices, cur, info.logo), ([kept], kept, kept))
        self.assertTrue(proof.build(doc_of(), info)[0])                      # et le BAT se fait avec elle

    def test_copy_error_goes_to_the_status_bar(self):
        a = png(self.dir / 'a' / 'logo.png')
        self.assertTrue(hasattr(self.S, 'keep_copy'), BEFORE)
        with mock.patch.object(self.S, 'keep_copy', side_effect=OSError('disque plein')):
            info, _c, _cur = self.bat(a)
        self.assertEqual(info.logo, a)                                       # le BAT se fait quand même
        self.assertIn('disque plein', self.w.statusBar().currentMessage())
        self.assertIn('logo.png', self.w.statusBar().currentMessage())


class Tree(Base):
    """L'arbre de la Bibliothèque : « Favoris » déplié en dossiers favoris, puis en sous-dossiers."""

    def setUp(self):
        super().setUp()
        self.out = self.dir / 'ailleurs'                 # des dossiers hors de la bibliothèque
        (self.out / 'Clients' / 'Dupont' / '2026').mkdir(parents=True)
        (self.out / 'Clients' / 'Martin').mkdir()
        (self.out / 'Plaques').mkdir()
        self.file = self.out / 'plaque.dxf'
        self.file.write_text(DXF, encoding='ascii')
        (self.out / 'Clients' / 'Dupont' / 'enseigne.dxf').write_text(DXF, encoding='ascii')

    def rows(self, p) -> list:
        return [(p.list.item(i).text(), p.list.item(i).data(self.S.ROLE_KIND)) for i in range(p.list.count())]

    def test_one_child_per_favorite_folder_unfolding(self):
        for f in (self.out / 'Clients', self.file, self.out / 'Plaques'):
            self.S.toggle_favorite(self.st, f)
        p = self.panel()
        node = self.favorites(p)
        self.assertEqual(children(node), ['Clients', 'Plaques'], BEFORE)     # un enfant par DOSSIER favori
        clients = node.child(0)
        self.assertEqual(clients.data(0, UR), str(self.out / 'Clients'))
        self.assertEqual(children(clients), ['…'])                           # ses sous-dossiers : à la demande
        self.assertEqual(children(node.child(1)), [])                        # (dossier sans sous-dossier)
        clients.setExpanded(True)
        self.assertEqual(children(clients), ['Dupont', 'Martin'])
        dupont = clients.child(0)
        dupont.setExpanded(True)
        self.assertEqual(children(dupont), ['2026'])
        p._folder_clicked(node)                                              # « Favoris » : comme avant
        self.assertEqual(self.rows(p), [('Clients', 'dir'), ('Plaques', 'dir'), ('plaque', None)])
        self.assertTrue(dupont.isExpanded())                                 # … sans replier ce qui est déplié
        p.tree.setCurrentItem(dupont)
        p._folder_clicked(dupont)                                            # un sous-dossier : son contenu
        self.assertEqual(self.rows(p), [('2026', 'dir'), ('enseigne', None)])
        self.assertEqual(p.tree.currentItem().data(0, UR), str(self.out / 'Clients' / 'Dupont'))
        p.show_folder(self.out / 'Clients' / 'Dupont' / '2026')              # double-clic dans la liste
        cur = p.tree.currentItem()                                           # … suivi dans la branche des favoris
        self.assertEqual((cur.text(0), cur.parent().text(0), cur.parent().parent().text(0)),
                         ('2026', 'Dupont', 'Clients'))
        self.assertIs(cur.parent().parent().parent(), node)

    def test_favorite_added_or_removed_shows_in_the_tree(self):
        p = self.panel()
        node = self.favorites(p)
        self.assertEqual(children(node), [])
        p.toggle_favorites([self.out / 'Clients'])
        self.assertEqual(children(node), ['Clients'], BEFORE)
        self.assertTrue(node.isExpanded())                                   # ajouté : montré
        p.show_folder(self.out / 'Clients' / 'Martin')                       # (aucune ligne choisie dans l'arbre)
        self.assertEqual(p.tree.currentItem().data(0, UR), str(self.out / 'Clients' / 'Martin'))
        p.toggle_favorites([self.file])                                      # un fichier : pas dans l'arbre
        self.assertEqual(children(node), ['Clients'])
        p._fill_tree()                                                       # l'arbre refait : toujours déplié
        node = self.favorites(p)
        self.assertEqual((children(node), node.isExpanded()), (['Clients'], True))
        martin = self.out / 'Clients' / 'Martin'
        p.show_folder(martin)                                                # déplié jusqu'à Martin, choisi
        p.toggle_favorites([self.out / 'Plaques'])                           # un autre favori ajouté, puis retiré :
        self.assertEqual(children(node), ['Clients', 'Plaques'])
        p.toggle_favorites([self.out / 'Plaques'])                           # rien n'est replié, la ligne reste
        self.assertEqual((children(node), children(node.child(0))), (['Clients'], ['Dupont', 'Martin']))
        self.assertTrue(node.child(0).isExpanded())
        self.assertEqual(p.tree.currentItem().data(0, UR), str(martin))
        p.toggle_favorites([self.out / 'Clients'])
        self.assertEqual(children(node), [])

    def test_favorite_gone_is_no_error(self):
        gone, never = self.out / 'Plaques', self.out / 'Jamais'
        self.S.toggle_favorite(self.st, gone)
        self.st.setValue('symboles/favoris', [str(gone), str(never)])        # (un favori déjà absent à l'ouverture)
        p = self.panel()
        node = self.favorites(p)
        self.assertEqual(children(node), ['Plaques'], BEFORE)
        (gone / 'Sous').mkdir()
        p._fill_tree()
        child = self.favorites(p).child(0)
        self.assertEqual(children(child), ['…'])
        (gone / 'Sous').rmdir()
        gone.rmdir()                                                         # clé débranchée, dossier renommé…
        child.setExpanded(True)                                              # déplié : rien, sans erreur
        self.assertEqual(children(child), [])
        p.tree.setCurrentItem(child)
        p._folder_clicked(child)                                             # cliqué : liste vide, sans erreur
        self.assertEqual(p.list.count(), 0)
        p.show_favorites()                                                   # « Favoris » : il n'y est plus
        self.assertEqual((children(self.favorites(p)), p.list.count()), ([], 0))

    def test_unreachable_share_is_never_read_in_the_interface(self):
        touched = []                                     # tout accès disque au partage : (fonction, fil)

        def guard(name, real, absent):
            def call(*a, **k):
                if a and str(a[0]).startswith(('\\\\', '//')):
                    touched.append((name, threading.current_thread() is threading.main_thread()))
                    if absent is OSError:
                        raise OSError('partage hors d’atteinte')
                    return absent
                return real(*a, **k)
            return call
        for owner, name, absent in ((pathlib.Path, 'is_dir', False), (pathlib.Path, 'is_file', False),
                                    (pathlib.Path, 'exists', False), (pathlib.Path, 'iterdir', OSError),
                                    (pathlib.Path, 'stat', OSError), (pathlib.Path, 'resolve', OSError),
                                    (os, 'scandir', OSError), (os.path, 'isdir', False),
                                    (os.path, 'isfile', False), (os.path, 'exists', False)):
            patcher = mock.patch.object(owner, name, guard(name, getattr(owner, name), absent))
            patcher.start()
            self.addCleanup(patcher.stop)
        self.st.setValue('symboles/favoris', [SHARE, SHARE + '\\plaque.dxf'])
        p = self.panel()
        node = self.favorites(p)
        self.assertEqual(children(node), ['Clients'], BEFORE)                # le dossier du partage, sans le lire
        child = node.child(0)
        self.assertEqual(children(child), ['…'])
        p._folder_clicked(node)
        self.assertEqual(self.rows(p), [('Clients', 'dir'), ('plaque', None)])
        asked = []                                       # vignette et fiche : confiées à un fil (ici : notées)
        for name, got in (('_timed_preview', None), ('_details', (None, None))):
            patcher = mock.patch.object(self.S, name, lambda *a, _n=name, _g=got: asked.append(_n) or _g)
            patcher.start()
            self.addCleanup(patcher.stop)
        p._timer.stop()
        p._load_some()                                                       # un tour de vignettes
        p._timer.stop()
        for row in (0, 1):                                                   # l'aperçu du dossier, puis du fichier
            p.list.setCurrentRow(row)
            p.update_preview()
        self.assertEqual(p.file_info.text().splitlines()[0], 'plaque.dxf')
        p._dtimer.stop()
        p._prev_timer.stop()
        p.list.item(0).setSelected(True)
        p.list.item(1).setSelected(True)
        texts = [a.text() for a in p.menu(p.list, None, exec_menu=False).actions()]      # le clic droit
        self.assertIn(tr('Insérer dans le dessin'), texts)                   # (le fichier, reconnu à son extension)
        self.assertEqual(touched, [])                                        # rien lu : rien ne peut figer
        child.setExpanded(True)                                              # déplié : lu dans le fil de calcul
        self.assertEqual(children(child), [])
        self.assertTrue(touched)
        self.assertFalse(any(main for _name, main in touched))               # … jamais dans celui de l'interface


class Internal(Base):
    """La bibliothèque interne : fichiers gardés (clic droit), logos visibles."""

    def test_copy_into_the_internal_library(self):
        out = self.dir / 'ailleurs'
        out.mkdir()
        f = out / 'plaque.dxf'
        f.write_text(DXF, encoding='ascii')
        p = self.panel([self.lib, out])
        p.show_folder(out)
        self.assertTrue(p.select_file(f))
        texts = [a.text() for a in p.menu(p.list, None, exec_menu=False).actions()]
        self.assertIn(tr('Copier dans la bibliothèque interne'), texts, BEFORE)
        kept = self.lib / 'Favoris' / 'plaque.dxf'
        self.assertEqual(p.copy_to_library([f]), [kept])
        self.assertEqual(kept.read_text(encoding='ascii'), DXF)
        self.assertTrue(f.is_file())                                         # une copie : l'original reste
        self.assertEqual(p.copy_to_library([f]), [kept])                     # déjà gardé : pas de doublon
        self.assertEqual(names(self.lib / 'Favoris'), ['plaque.dxf'])
        top = next(p.tree.topLevelItem(i) for i in range(p.tree.topLevelItemCount())
                   if p.tree.topLevelItem(i).data(0, UR) == str(self.lib))
        top.setExpanded(True)
        self.assertIn('Favoris', children(top))                              # le dossier se voit dans l'arbre
        p.show_folder(self.lib / 'Favoris')
        self.assertTrue(p.select_file(kept))
        texts = [a.text() for a in p.menu(p.list, None, exec_menu=False).actions()]
        self.assertNotIn(tr('Copier dans la bibliothèque interne'), texts)   # déjà dedans : pas proposé
        g = out / 'autre.dxf'
        g.write_text(DXF + ' ', encoding='ascii')
        with mock.patch.object(self.S, 'keep_copy', side_effect=OSError('disque plein')), \
                mock.patch.object(self.S.QMessageBox, 'warning') as box:
            self.assertEqual(p.copy_to_library([f, g]), [])
        self.assertEqual(box.call_count, 1)                                  # une seule boîte pour la sélection
        self.assertEqual(box.call_args[0][2].count('disque plein'), 2)

    def test_logos_are_seen_in_their_folder(self):
        png(self.logos / 'logo.png')
        png(self.lib / 'Symboles' / 'photo.png')
        (self.lib / 'Symboles' / 'plaque.dxf').write_text(DXF, encoding='ascii')
        p = self.panel()

        def files():
            rows = [p.list.item(i) for i in range(p.list.count())]
            return [it.text() for it in rows if it.data(self.S.ROLE_KIND) is None]
        p.show_folder(self.logos)
        self.assertEqual(files(), ['logo'], BEFORE)                          # les images des logos s'y voient
        p.show_folder(self.lib / 'Symboles')                                 # ailleurs : comme avant
        self.assertEqual(files(), ['plaque'])
        from vectordrive.ui.file_browser import FileBrowserPanel
        self.assertFalse(FileBrowserPanel.LOGOS_SHOWN)                       # Ouvrir : son filtre des formats décide


class Browser(Base):
    """La fenêtre Ouvrir hérite de l'arbre : ses favoris (`navigateur/favoris`) se déplient aussi."""

    def test_open_window_favorites_unfold(self):
        from vectordrive.ui import file_browser as FB
        out = self.dir / 'ailleurs'
        (out / 'Clients' / 'Dupont').mkdir(parents=True)
        self.st.setValue(FB.FileBrowserPanel.FAV, [str(out / 'Clients'), SHARE])
        for name, value in (('system_roots', lambda: [self.dir]), ('_QUICK', [])):   # ni vrais dossiers ni PowerShell
            patcher = mock.patch.object(FB, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        p = FB.FileBrowserPanel(self.st)
        self.addCleanup(self.drop, p)
        tops = [p.tree.topLevelItem(i).data(0, UR) for i in range(4)]
        self.assertEqual(tops, [self.S.RECENTS, self.S.FAVORITES, FB.BIBLI, FB.QUICK])     # l'ordre d'avant
        node = self.favorites(p)
        self.assertEqual([node.child(k).data(0, UR) for k in range(node.childCount())],
                         [str(out / 'Clients'), SHARE], BEFORE)
        self.assertEqual(children(node.child(1)), ['…'])                     # le partage : pas lu, dépliable
        local = node.child(0)
        local.setExpanded(True)
        self.assertEqual(children(local), ['Dupont'])
        p.tree.setCurrentItem(local)
        p._folder_clicked(local)                                             # son contenu, la ligne reste choisie
        self.assertEqual([p.list.item(i).text() for i in range(p.list.count())][-1], 'Dupont')
        self.assertEqual(p.tree.currentItem().parent().data(0, UR), self.S.FAVORITES)
        p.show_folder(out / 'Clients' / 'Dupont')                            # double-clic : suivi sous « Favoris »
        cur = p.tree.currentItem()
        self.assertEqual((cur.text(0), cur.parent().text(0)), ('Dupont', 'Clients'))
        self.assertEqual(cur.parent().parent().data(0, UR), self.S.FAVORITES)


if __name__ == '__main__':
    unittest.main()
