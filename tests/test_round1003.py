"""Round 1003 : le programme machine dans sa fenêtre (demande du 14/11) — le bouton « Programme » du panneau FAO, à
l'icône de machine colorée, ouvre un panneau détaché : le programme coloré, en direct ou à la demande, la machine au
choix, l'opération choisie retrouvée ; il s'ancre dans une colonne ou couvre le dessin en plein écran translucide."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1003.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QItemSelectionModel  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QAbstractButton, QApplication  # noqa: E402

from tests import _posts  # noqa: E402
from vectordrive.i18n import tr  # noqa: E402

app = QApplication.instance() or QApplication([])


def named(toolpaths, setup, *, title: str = '', machine=None, stem: str = 'programme', box_mm=None):
    """Post-processeur d'essai : le nom de chaque parcours en commentaire, puis ses mouvements."""
    from vectordrive.cam.post import PostResult
    lines = ['%', f'(ESSAI {title})']
    for k, tp in enumerate(toolpaths):
        lines.append(f'N{10 * (k + 1)} T{k + 1} M6 ({tp.name})')
        for m in tp.moves:
            lines.append(f'{"G0" if m.kind == "rapid" else "G1"} X{m.x:.3f} Y{m.y:.3f} Z{m.z:.3f} F1200')
    lines.append('M30 ; fin')
    return PostResult('\n'.join(lines) + '\n', ['essai : un avertissement'], '.nc', 'utf-8')


def ascii_post(toolpaths, setup, *, title: str = '', machine=None, stem: str = 'programme', box_mm=None):
    from vectordrive.cam.post import PostResult
    return PostResult(''.join(f'({tp.name})\n' for tp in toolpaths), [], '.nc', 'ascii')


def two_files(toolpaths, setup, *, title: str = '', machine=None, stem: str = 'programme', box_mm=None):
    from vectordrive.cam.post import PostResult
    names = [tp.name for tp in toolpaths]
    return PostResult('A\n', [], '.nc', 'utf-8', files=[(f'{stem}_1.nc', f'({names[0]})\nM30\n'),
                                                        (f'{stem}_2.nc', '\n'.join(f'({n})' for n in names[1:]) + '\nM30\n')])


class Base(unittest.TestCase):

    def setUp(self):
        from vectordrive.cam import model
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        from vectordrive.portable import settings
        from vectordrive.ui.main_window import MainWindow
        self.forget()
        self.addCleanup(self.forget)
        self.posts = _posts.registered('essai', named)
        self.posts.__enter__()
        self.addCleanup(self.posts.__exit__, None, None, None)
        self.w = MainWindow()
        self.w.resize(1400, 900)
        self.w.show()
        app.processEvents()
        self.p, self.prog = self.w.cam_panel, self.w.program_panel
        doc = self.w.canvas.doc
        ids = []
        for r in ((0, 0, 20, 14), (30, 0, 12, 8)):
            sh = Shape(path=geom.Path([geom.rect(*r)]), tool=0)
            doc.add(sh)
            ids.append(sh.id)
        s = self.p.setup()
        self.tool = model.CamTool(name='Cyl 2', diameter=2.0, number=1, cut_length=7, step_down=1.0, spindle=20000)
        s.tools = [self.tool]
        s.post = 'essai'
        s.operations = [model.Operation(name=n, kind='gravure', tool_id=self.tool.id, items=[i], depth=0.2)
                        for n, i in zip(('Plaque avant', 'Détourage été'), ids)]
        self.p._fill_posts()
        self.p.save(s)
        self.addCleanup(self.close)
        assert settings() is not None

    @staticmethod
    def forget():
        from vectordrive.portable import settings
        st = settings()
        for k in list(st.allKeys()):
            if k.startswith('panneaux_colonnes/') or k in ('fao/programme_direct', 'fenetre/geometrie',
                                                           'fenetre/plein_ecran', 'vue/panneau_fao'):
                st.remove(k)
        st.sync()

    def close(self):
        self.w.modified = False
        self.w.close()
        app.processEvents()

    def select(self, *rows):
        t = self.p.ops
        f = QItemSelectionModel.SelectionFlag
        t.clearSelection()
        for r in rows:
            t.selectionModel().select(t.model().index(r, 0), f.Select | f.Rows)
        app.processEvents()

    def wait(self):
        from vectordrive.ui import program_window as PW
        QTest.qWait(PW.LIVE_MS + 200)

    def text(self):
        return self.prog.text.toPlainText()


class Button(Base):

    def test_the_program_button_opens_the_window(self):
        p = self.p
        self.assertFalse([b for b in p.findChildren(QAbstractButton) if b.text() == tr('Post-traiter…')])
        b = p.program_button
        self.assertEqual(b.text(), tr('Programme'))
        self.assertFalse(b.icon().isNull())
        img = b.icon().pixmap(40, 40).toImage()
        hues = {img.pixelColor(x, y).name() for x in range(0, 40, 2) for y in range(0, 40, 2)
                if img.pixelColor(x, y).alpha() > 200}
        self.assertTrue({'#1c7ed6', '#f76707'} <= hues, hues)       # colorée : le bâti bleu, la broche orange
        d = self.w.dock_program
        self.assertTrue(d.isHidden())
        b.click()
        app.processEvents()
        self.assertFalse(d.isHidden())
        self.assertTrue(d.isFloating())                             # une fenêtre à part, d'office
        self.assertGreaterEqual(d.width(), 400)
        self.assertIn('cam_program', self.w.A)
        d.setGeometry(120, 90, 500, 480)                            # placée ailleurs, fermée, rouverte : elle y reste
        app.processEvents()
        size = d.size()
        d.close()
        b.click()
        app.processEvents()
        self.assertEqual(d.size(), size)

    def test_a_panel_like_the_others(self):
        from vectordrive.ui.overlay import _keeps_wheel
        d = self.w.dock_program
        cols = self.w.columns
        self.w.show_program()
        app.processEvents()
        bar = d.titleBarWidget()
        self.assertEqual(list(bar.buttons), ['plein', 'detacher', 'fermer'])
        bar.buttons['plein'].click()                                # sur le dessin, opacité réglable
        app.processEvents()
        ov = cols.overlay(d)
        self.assertTrue(ov.active)
        ov.set_opacity(1.0)
        self.assertEqual(d.windowOpacity(), 1.0)                    # opaque : à la place du dessin
        self.assertEqual(d.geometry().size(), self.w.stage.size())
        self.assertTrue(_keeps_wheel(self.prog.text.viewport()))    # la molette fait défiler le programme, pas le dessin
        ov.set_active(False)
        app.processEvents()
        self.assertTrue(d.isFloating())                             # il était détaché : il le reste
        cols.move(d, 'gauche')                                      # ou rangé dans une colonne
        app.processEvents()
        self.assertEqual(cols.side(d), 'gauche')
        self.assertIn(d, cols.fao_docks())


class Text(Base):

    def test_the_program_of_the_shown_paths(self):
        self.p.compute()
        self.w.show_program()
        text = self.text()
        self.assertIn('(Plaque avant)', text)
        self.assertIn('(Détourage été)', text)
        self.assertTrue(text.startswith('%'))
        self.assertIn(tr('{0} avertissement(s)').format(1), self.prog.status.text())
        self.assertIn('essai : un avertissement', self.prog.status.toolTip())
        self.assertFalse(self.prog.file.isVisibleTo(self.prog))
        self.prog.copy()
        self.assertEqual(QApplication.clipboard().text(), text)

    def test_as_the_file_will_be_written(self):
        with _posts.registered('essai', ascii_post):
            self.p.compute()
            self.w.show_program()
            self.assertIn('(D?tourage ?t?)', self.text())           # l'encodage du fichier : pas d'accent en ASCII
        with mock.patch.object(self.p, 'current_paths', wraps=self.p.current_paths) as cur:
            self.prog.buttons['update'].click()
        self.assertEqual(cur.call_args.kwargs, {'dates': False})    # un aperçu ne touche pas aux dates du dessin

    def test_colours(self):
        from vectordrive.ui import program_window as PW
        h = self.prog.highlighter
        line = 'N10 T1 M6 (Plaque G1) G1 X12.5 Y-3 F1200 ; fin'
        want = {'N10': 'line', 'T1': 'tool', 'M6': 'm', '(Plaque': 'comment', ' G1 X': 'g', 'X12': 'axis',
                '12.5': 'number', '2.5': 'number', '.5': 'number', '-3': 'number', 'F1200': 'feed', '1200': 'number',
                '; fin': 'comment'}
        for piece, role in want.items():
            i = line.index(piece) + (1 if piece.startswith(' ') else 0)
            self.assertEqual(h.role_at(line, i), role, piece)
        self.assertEqual(h.role_at(line, line.index('G1)')), 'comment')     # le commentaire l'emporte sur ce qu'il contient
        compact = 'N10G1X12.5Y3F300'                                # code collé : pas de limite de mot
        self.assertEqual([h.role_at(compact, compact.index(c)) for c in ('G', 'X', '1', 'Y', 'F')],
                         ['g', 'axis', 'line', 'axis', 'feed'])
        self.assertEqual(h.role_at(compact, compact.index('12.5')), 'number')
        self.assertEqual(h.role_at('#100=5', 0), '')                # une variable ISO n'est pas un commentaire
        self.assertEqual(h.role_at('  # commentaire SimPL', 4), 'comment')
        self.assertEqual(h.role_at('export program Main', 8), 'keyword')
        self.assertEqual(h.role_at('Tool type="0068443G"', 12), 'string')
        hp = 'PU0,0;PD10,0;'
        self.assertEqual(h.role_at(hp, hp.index('PD')), 'comment')  # en ISO, après « ; » : un commentaire
        h.set_kind('.plt')
        self.assertEqual(h.role_at(hp, hp.index('PD')), '')         # en HPGL, « ; » termine l'ordre
        self.assertEqual(h.role_at(hp, hp.index('10')), 'number')
        h.set_kind('.nc')
        self.assertNotEqual(PW.COLORS['g'][0], PW.COLORS['comment'][0])

    def test_long_programs_stay_plain(self):
        from vectordrive.ui import program_window as PW
        self.p.compute()
        self.w.show_program()
        self.assertIs(self.prog.highlighter.document(), self.prog.text.document())
        with mock.patch.object(PW, 'MAX_LINE', 10):                 # une très longue ligne : pas de coloration
            self.prog.files = [('a.nc', 'G1 X' + '1' * 50)]
            self.prog._show_file(0)
            self.assertIsNone(self.prog.highlighter.document())
        self.prog.refresh()
        self.assertIs(self.prog.highlighter.document(), self.prog.text.document())

    def test_several_files(self):
        with _posts.registered('essai', two_files):
            self.p.compute()
            self.w.show_program()
            self.assertTrue(self.prog.file.isVisibleTo(self.prog))
            self.assertEqual(self.prog.file.count(), 2)
            self.assertIn('(Plaque avant)', self.text())
            self.select(1)                                          # l'opération du 2e fichier : il est montré
            self.assertEqual(self.prog.file.currentIndex(), 1)
            self.assertIn('(Détourage été)', self.text())
            self.assertEqual(len(self.prog.text.extraSelections()), 1)

    def test_without_paths_or_without_a_post(self):
        self.w.show_program()
        self.assertEqual(self.text(), '')
        self.assertIn(tr('Aucun parcours montré : « Mettre à jour » les calcule'), self.prog.status.text())
        self.prog.buttons['update'].click()                         # à la demande : les parcours sont calculés
        self.assertIn('(Plaque avant)', self.text())
        from vectordrive.plugins import REGISTRY
        with mock.patch.dict(REGISTRY.posts, clear=True):
            data = self.p.program_preview()
        self.assertEqual(data['files'], [])
        self.assertIn('plugins', data['note'])


class Live(Base):

    def test_it_follows_the_cam_panel(self):
        from vectordrive.ui import program_window as PW
        self.p.compute()
        self.w.show_program()
        app.processEvents()
        self.assertTrue(self.prog.live.isChecked())
        self.assertEqual(self.prog.timer.interval(), PW.LIVE_MS)    # les changements à la suite n'en font qu'un
        self.assertIn('(Détourage été)', self.text())
        with mock.patch.object(self.p, 'program_preview', wraps=self.p.program_preview) as made:
            self.p.toggle_op_paths(1, False)                        # un parcours caché : hors du programme
            app.processEvents()
            self.assertIn('(Détourage été)', self.text())           # pas dans l'instant…
            self.wait()
            self.assertEqual(made.call_count, 1)                    # … mais sous peu, une seule fois
        self.assertNotIn('(Détourage été)', self.text())
        self.assertIn('(Plaque avant)', self.text())
        self.assertIn('⚠', self.prog.status.text())                 # une opération active cachée : c'est dit
        self.assertTrue(self.prog.buttons['all'].isVisibleTo(self.prog))
        self.prog.buttons['all'].click()                            # « Tout montrer » : le programme entier
        self.assertIn('(Détourage été)', self.text())
        self.assertNotIn('⚠', self.prog.status.text())
        self.assertFalse(self.prog.buttons['all'].isVisibleTo(self.prog))

    def test_it_follows_the_drawing(self):
        from vectordrive.core import geom
        self.p.compute()
        self.w.show_program()
        app.processEvents()
        note = tr('Le dessin a changé depuis le calcul : « Mettre à jour » refait les parcours')
        self.assertNotIn(note, self.prog.status.text())
        sh = self.w.canvas.doc.layers[0].items[0]
        sh.path = geom.Path([geom.rect(0, 0, 40, 28)])
        self.w._on_doc_changed()                                    # un objet retouché
        self.wait()
        self.assertIn(note, self.prog.status.text())
        before = self.text()
        self.prog.refresh(recompute=True)
        self.assertNotEqual(self.text(), before)
        self.assertNotIn(note, self.prog.status.text())

    def test_or_waits_to_be_asked(self):
        self.p.compute()
        self.w.show_program()
        app.processEvents()
        self.prog.live.setChecked(False)
        self.assertEqual(str(self.w.settings.value('fao/programme_direct')).lower(), 'false')
        self.p.toggle_op_paths(1, False)
        self.wait()
        self.assertIn('(Détourage été)', self.text())               # à la demande : rien n'a bougé
        self.prog.buttons['update'].click()
        self.assertNotIn('(Détourage été)', self.text())

    def test_not_for_nothing(self):
        from vectordrive.ui import program_window as PW
        self.p.compute()
        with mock.patch.object(self.p, 'program_preview', wraps=self.p.program_preview) as made:
            self.p.toggle_op_paths(1, False)
            self.wait()
            made.assert_not_called()                                # fenêtre fermée : rien n'est écrit pour rien
            self.w.show_program()
            app.processEvents()
            made.reset_mock()
            self.p._computing = True                                # pendant un calcul : après lui
            self.p.toggle_op_paths(1, True)
            self.wait()
            made.assert_not_called()
            self.p._computing = False
            self.wait()
            self.assertEqual(made.call_count, 1)
            made.reset_mock()
            with mock.patch.object(PW, 'LIVE_MAX_MOVES', 1):        # un très long programme : à la demande
                self.p.toggle_op_paths(1, False)
                self.wait()
                made.assert_not_called()
                self.assertIn('Mettre à jour', self.prog.status.text())


class Links(Base):

    def test_the_chosen_operation_is_found(self):
        self.p.compute()
        self.w.show_program()
        app.processEvents()
        lines = self.text().split('\n')
        self.select(1)
        sels = self.prog.text.extraSelections()
        self.assertEqual(len(sels), 1)
        line = sels[0].cursor.blockNumber()
        self.assertIn('(Détourage été)', lines[line])
        self.assertEqual(self.prog.find_lines('DETOURAGE ETE'), [(0, line)])    # sans casse ni accents
        self.assertEqual(self.prog.text.textCursor().blockNumber(), line)      # amenée à l'écran
        self.prog.text.verticalScrollBar().setValue(0)
        cur = self.prog.text.textCursor()
        cur.setPosition(0)
        self.prog.text.setTextCursor(cur)
        self.prog.refresh()                                         # une mise à jour ne déplace ni la vue ni le curseur
        self.assertEqual(self.prog.text.textCursor().blockNumber(), 0)
        self.assertEqual(len(self.prog.text.extraSelections()), 1)  # … mais l'opération reste surlignée
        self.p.toggle_op_paths(1, False)
        self.prog.refresh()
        self.assertEqual(self.prog.text.extraSelections(), [])      # cachée : rien à surligner, pas une autre ligne
        self.select()
        self.assertEqual(self.prog.text.extraSelections(), [])
        self.assertEqual(self.prog.find_lines('absent du programme'), [])

    def test_two_operations_of_the_same_name(self):
        s = self.p.setup()
        s.operations[1].name = 'Plaque avant'
        self.p.save(s)
        self.p.compute()
        self.w.show_program()
        app.processEvents()
        self.select(0)
        sels = self.prog.text.extraSelections()
        first = sels[0].cursor.blockNumber()
        self.select(1)
        sels = self.prog.text.extraSelections()
        second = sels[0].cursor.blockNumber()
        self.assertGreater(second, first)                           # la 2e du même nom : sa ligne à elle

    def test_the_machine_is_chosen_there(self):
        with _posts.registered('autre', ascii_post):
            self.p._fill_posts()
            self.p.refresh()
            self.p.compute()
            self.w.show_program()
            keys = [self.prog.machine.itemData(i) for i in range(self.prog.machine.count())]
            self.assertEqual(sorted(keys), ['autre', 'essai'])
            self.assertEqual(self.prog.machine.currentData(), 'essai')
            self.prog.machine.setCurrentIndex(keys.index('autre'))
            self.assertEqual(self.p.setup().post, 'autre')          # enregistrée dans le dessin
            self.assertIn('(D?tourage ?t?)', self.text())
            self.assertEqual(self.prog.machine.currentData(), 'autre')

    def test_save_writes_through_the_usual_post_processing(self):
        self.p.compute()
        self.w.show_program()
        with mock.patch.object(self.p, 'post_process') as post:
            self.prog.buttons['save'].click()
        post.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
