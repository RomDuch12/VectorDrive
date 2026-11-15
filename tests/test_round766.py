"""Round 766 : Orthographe : le correcteur de Windows sur les textes du dessin."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', os.path.join(tempfile.mkdtemp(), 'session'))
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')

from PySide6.QtWidgets import QApplication

from vectordrive.core import spell as SP
from vectordrive.core.document import Text
from vectordrive.core.geom import Affine
from vectordrive.ui.main_window import MainWindow
from vectordrive.ui.spell_dialog import SpellDialog, SpellSession

app = QApplication.instance() or QApplication([])

WORDS = {'bonjor': ['bonjour'], 'tensoin': ['tension'], 'etiquette': ['étiquette'], 'erreurr': ['erreur', 'erreurs']}


class FakeChecker:
    """Un correcteur qui connaît quelques fautes, comme celui de Windows : les majuscules ne sont pas relues."""

    def __init__(self):
        self.closed = False

    def check(self, text):
        import re
        out = []
        for m in re.finditer(r'[^\W\d_]+', text):
            w = m.group(0)
            if not w.isupper() and w.lower() in WORDS:
                out.append(SP.Fault(m.start(), len(w), w, list(WORDS[w.lower()])))
        return out

    def close(self):
        self.closed = True


class TestFaults(unittest.TestCase):
    def setUp(self):
        self.c = FakeChecker()

    def test_plain(self):
        f, = SP.faults_of(self.c, 'dit bonjor à tous')
        self.assertEqual((f.start, f.length, f.word), (4, 6, 'bonjor'))
        self.assertEqual(f.suggestions, ['bonjour'])

    def test_capitals_are_checked_too(self):
        f, = SP.faults_of(self.c, 'DANGER HAUTE TENSOIN')
        self.assertEqual(f.word, 'TENSOIN')
        self.assertEqual(f.suggestions, ['TENSION'])                # dans la casse du texte

    def test_capitals_without_accents_are_no_fault(self):
        self.assertEqual(SP.faults_of(self.c, 'ETIQUETTE'), [])
        self.assertEqual(len(SP.faults_of(self.c, 'etiquette')), 1)  # en minuscules, l'accent manque vraiment

    def test_variables_not_checked(self):
        self.assertEqual(SP.faults_of(self.c, 'n° {bonjor}'), [])

    def test_with_digits_not_checked(self):
        self.assertEqual(SP.faults_of(self.c, 'réf bonjor2'), [])

    def test_ignored(self):
        self.assertEqual(SP.faults_of(self.c, 'bonjor Bonjor', ignore={'bonjor'}), [])

    def test_lower_capitals_keeps_positions(self):
        for s in ('É ÉTÉ été', 'STRAẞE ok', 'ß', 'A😀BC'):
            self.assertEqual(len(SP._lower_capitals(s)), len(s), s)

    def test_single_capital_left_alone(self):
        self.assertEqual(SP._lower_capitals('A B c'), 'A B c')


class TestReplaced(unittest.TestCase):
    def test_word(self):
        self.assertEqual(SP.replaced('dit bonjor !', SP.Fault(4, 6, 'bonjor'), 'bonjour'), 'dit bonjour !')

    def test_repeated_word_removed_with_its_space(self):
        self.assertEqual(SP.replaced('le le chat', SP.Fault(3, 2, 'le'), ''), 'le chat')

    def test_at_the_start(self):
        self.assertEqual(SP.replaced('le chat', SP.Fault(0, 2, 'le'), ''), ' chat')


class TestCharIndex(unittest.TestCase):
    def test_ascii(self):
        self.assertEqual(SP._char_index('abc', 2), 2)

    def test_after_an_emoji(self):
        self.assertEqual(SP._char_index('é😀 abc', 4), 3)            # é = 1, 😀 = 2 unités, espace = 1

    def test_past_the_end(self):
        self.assertEqual(SP._char_index('é', 5), 1)


class TestSession(unittest.TestCase):
    def make(self, *texts):
        self.items = [Text(text=s) for s in texts]
        self.applied = []

        def apply(t, s):
            self.applied.append((t, s))
            t.text = s
        return SpellSession(self.items, FakeChecker(), apply)

    def test_nothing_to_see(self):
        self.assertTrue(self.make('tout va bien', 'ici aussi').finished())

    def test_goes_through_every_text(self):
        s = self.make('bonjor', 'rien', 'erreurr')
        self.assertEqual(s.current_fault.word, 'bonjor')
        self.assertIs(s.text, self.items[0])
        s.ignore()
        self.assertEqual(s.current_fault.word, 'erreurr')
        self.assertIs(s.text, self.items[2])
        s.ignore()
        self.assertTrue(s.finished())

    def test_replace(self):
        s = self.make('dit bonjor et erreurr')
        s.replace('bonjour')
        self.assertEqual(self.items[0].text, 'dit bonjour et erreurr')
        self.assertEqual(s.current_fault.word, 'erreurr')
        self.assertEqual(s.current_fault.start, 15)                  # la position suit le texte modifié
        s.replace('erreur')
        self.assertEqual(self.items[0].text, 'dit bonjour et erreur')
        self.assertTrue(s.finished())
        self.assertEqual(s.replacements, 2)

    def test_bad_replacement_is_asked_again(self):
        s = self.make('bonjor')
        s.replace('erreurr')                                         # encore une faute : à revoir
        self.assertEqual(s.current_fault.word, 'erreurr')

    def test_replacing_by_the_same_does_nothing(self):
        s = self.make('bonjor')
        s.replace('bonjor')
        self.assertEqual(self.applied, [])
        self.assertTrue(s.finished())

    def test_ignore_only_that_one(self):
        s = self.make('bonjor bonjor')
        s.ignore()
        self.assertEqual(s.current_fault.start, 7)
        s.ignore()
        self.assertTrue(s.finished())

    def test_ignore_all(self):
        s = self.make('bonjor erreurr', 'Bonjor')
        s.ignore_all()
        self.assertEqual(s.current_fault.word, 'erreurr')
        s.ignore()
        self.assertTrue(s.finished())

    def test_fixed_earlier_word_with_later_ignored_one(self):
        s = self.make('erreurr bonjor erreurr')
        s.ignore()
        s.replace('bonjour')
        self.assertEqual(s.current_fault.start, 16)
        self.assertEqual(s.current_fault.word, 'erreurr')


class TestDialog(unittest.TestCase):
    def setUp(self):
        self.items = [Text(text='dit <bonjor> & co'), Text(text='erreurr')]

        def apply(t, s):
            t.text = s
        self.shown = []
        self.dlg = SpellDialog(None, SpellSession(self.items, FakeChecker(), apply), self.shown.append)

    def tearDown(self):
        self.dlg.deleteLater()

    def test_shows_the_word_in_its_text(self):
        self.assertIn('<u>bonjor</u>', self.dlg.context.text())
        self.assertIn('&lt;', self.dlg.context.text())              # le texte du client n'est pas du HTML
        self.assertIn('&amp;', self.dlg.context.text())
        self.assertEqual(self.dlg.edit.text(), 'bonjour')
        self.assertEqual(self.dlg.list.count(), 1)
        self.assertIs(self.shown[-1], self.items[0])

    def test_replace_button(self):
        self.dlg.b_replace.click()
        self.assertEqual(self.items[0].text, 'dit <bonjour> & co')
        self.assertIn('<u>erreurr</u>', self.dlg.context.text())
        self.assertEqual(self.dlg.list.count(), 2)
        self.assertIs(self.shown[-1], self.items[1])

    def test_pick_a_suggestion(self):
        self.dlg.b_ignore.click()
        self.dlg.list.setCurrentRow(1)
        self.assertEqual(self.dlg.edit.text(), 'erreurs')
        self.dlg.b_replace.click()
        self.assertEqual(self.items[1].text, 'erreurs')

    def test_typed_correction(self):
        self.dlg.edit.setText('salut')
        self.dlg.do_replace()
        self.assertEqual(self.items[0].text, 'dit <salut> & co')

    def test_closes_at_the_end(self):
        closed = []
        self.dlg.accepted.connect(lambda: closed.append(1))
        self.dlg.b_ignore.click()
        self.dlg.b_all.click()
        self.assertEqual(closed, [1])

    def test_no_suggestion(self):
        WORDS['zzz'] = []
        try:
            d = SpellDialog(None, SpellSession([Text(text='zzz')], FakeChecker(), lambda t, s: None))
            self.assertEqual(d.edit.text(), 'zzz')
            self.assertEqual(d.list.count(), 0)
            d.deleteLater()
        finally:
            del WORDS['zzz']

    def test_repeated_word_offers_removal(self):
        WORDS['xx'] = ['']
        try:
            items = [Text(text='a xx')]

            def apply(t, s):
                t.text = s
            d = SpellDialog(None, SpellSession(items, FakeChecker(), apply))
            self.assertEqual(d.list.count(), 1)
            self.assertEqual(d.edit.text(), '')
            d.do_replace()
            self.assertEqual(items[0].text, 'a')
            d.deleteLater()
        finally:
            del WORDS['xx']


class TestWindow(unittest.TestCase):
    def setUp(self):
        self.w = MainWindow()
        self.t = Text(text='dit bonjor', font='Arial', size=8.0, matrix=Affine.translation(10, 20))
        self.w.canvas.doc.layers[0].items[:] = [self.t, Text(text='autre texte', font='Arial', size=8.0)]
        self.w.canvas.invalidate()
        self.w.canvas.select([])
        self.p = mock.patch.object(SP, 'open_checker', side_effect=lambda lang: FakeChecker())
        self.p.start()

    def tearDown(self):
        self.p.stop()
        self.w.modified = False
        self.w.close()

    def test_replace_changes_the_drawing_and_undoes(self):
        d = self.w.spell_check(exec_dialog=False)
        self.assertIs(self.w.canvas.selection[0], self.t)            # le texte en cours se voit dans le plan de travail
        before = self.t.outline
        d.do_replace()
        items = self.w.canvas.doc.layers[0].items
        self.assertEqual(items[0].text, 'dit bonjour')
        self.assertIsNot(items[0].outline, before)                   # contour refait
        self.w.undo()
        self.assertEqual(self.w.canvas.doc.layers[0].items[0].text, 'dit bonjor')

    def test_selection_limits_it(self):
        other = self.w.canvas.doc.layers[0].items[1]
        self.w.canvas.select([other])
        self.assertIsNone(self.w.spell_check(exec_dialog=False))     # pas de faute dans ce qui est sélectionné

    def test_no_text(self):
        self.w.canvas.doc.layers[0].items[:] = []
        self.w.canvas.invalidate()
        self.assertIsNone(self.w.spell_check(exec_dialog=False))

    def test_no_checker_says_so(self):
        self.p.stop()
        try:
            with mock.patch.object(SP, 'open_checker', return_value=None):
                with mock.patch('vectordrive.ui.main_window.QMessageBox.information') as info:
                    self.assertIsNone(self.w.spell_check())
            self.assertIn('fr-FR', info.call_args[0][2].replace(self.w.spell_language(), 'fr-FR'))
        finally:
            self.p.start()

    def test_language_setting(self):
        self.w.settings.setValue('texte/langue_orthographe', 'en-GB')
        try:
            self.assertEqual(self.w.spell_language(), 'en-GB')
        finally:
            self.w.settings.remove('texte/langue_orthographe')

    def test_in_the_ribbon(self):
        a = self.w.A['spell_check']
        self.assertFalse(a.icon().isNull())
        self.assertTrue(a.toolTip())
        pages = [self.w.ribbon.page(i) for i in range(self.w.ribbon.count())]
        n = sum(1 for page in pages if page for g in page.groups() for b in g.buttons() if b.defaultAction() is a)
        self.assertEqual(n, 1)


@unittest.skipUnless(SP.available('fr-FR'), 'pas de correcteur français sur ce poste')
class TestForReal(unittest.TestCase):
    """Le vrai correcteur de Windows."""

    def setUp(self):
        self.c = SP.open_checker('fr-FR')

    def tearDown(self):
        self.c.close()

    def test_finds_a_fault_with_suggestion(self):
        f, = SP.faults_of(self.c, 'Bonjor le monde')
        self.assertEqual((f.start, f.word), (0, 'Bonjor'))
        self.assertIn('Bonjour', f.suggestions)

    def test_good_french(self):
        self.assertEqual(SP.faults_of(self.c, 'Plaque de sécurité'), [])

    def test_capitals(self):
        f, = SP.faults_of(self.c, 'DANGER HAUTE TENSOIN')
        self.assertEqual(f.word, 'TENSOIN')
        self.assertIn('TENSION', f.suggestions)

    def test_capitals_without_accents(self):
        self.assertEqual(SP.faults_of(self.c, 'SECURITE ETIQUETTE'), [])

    def test_repeated_word(self):
        f, = SP.faults_of(self.c, 'attention attention danger')
        self.assertEqual(f.start, 10)
        self.assertEqual(f.suggestions, [''])

    def test_after_an_emoji(self):
        f, = SP.faults_of(self.c, 'é😀 erreurr fin')
        self.assertEqual(f.word, 'erreurr')
        self.assertEqual(f.start, 3)

    def test_empty(self):
        self.assertEqual(self.c.check('   '), [])

    def test_unknown_language(self):
        self.assertIsNone(SP.open_checker('xx-YY'))


if __name__ == '__main__':
    unittest.main()
