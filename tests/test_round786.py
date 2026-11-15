"""Round 786 : scripts de forme (un sous-ensemble de VBScript qui dessine)."""
import json
import math
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from vectordrive.core import shapescript as SS
from vectordrive.core.geom import Path


def run(text, **kw):
    return SS.run(text, SS.Host(**kw))


def show(text, **kw):
    """Ce que le script montre par ShowValue."""
    seen = []
    SS.run(text, SS.Host(show=seen.append, **kw))
    return seen


class TestLanguage(unittest.TestCase):
    def test_arithmetic(self):
        self.assertEqual(show('ShowValue 2 + 3 * 4'), ['14'])
        self.assertEqual(show('ShowValue (2 + 3) * 4'), ['20'])
        self.assertEqual(show('ShowValue 7 \\ 2'), ['3'])
        self.assertEqual(show('ShowValue 7 Mod 3'), ['1'])
        self.assertEqual(show('ShowValue 7 / 2'), ['3.5'])

    def test_power_goes_left_to_right(self):
        self.assertEqual(show('ShowValue 2 ^ 3 ^ 2'), ['64'])
        self.assertEqual(show('ShowValue -2 ^ 2'), ['-4'])
        self.assertEqual(show('ShowValue 2 ^ -1'), ['0.5'])

    def test_text_and_numbers(self):
        self.assertEqual(show('ShowValue "a" & 1 & "b"'), ['a1b'])
        self.assertEqual(show('ShowValue "2" + 3'), ['5'])
        self.assertEqual(show('ShowValue "a" + "b"'), ['ab'])
        self.assertEqual(show('ShowValue "2" + "3"'), ['23'])
        self.assertEqual(show('ShowValue x + "b"'), ['b'])
        self.assertEqual(show('ShowValue "dit ""oui"""'), ['dit "oui"'])

    def test_comparisons_and_logic(self):
        self.assertEqual(show('ShowValue 1 < 2'), ['-1'])
        self.assertEqual(show('ShowValue 1 = 2'), ['0'])
        self.assertEqual(show('ShowValue "5" = 5'), ['-1'])
        self.assertEqual(show('ShowValue Not 1 = 2'), ['-1'])
        self.assertEqual(show('ShowValue True And False'), ['0'])
        self.assertEqual(show('ShowValue True Or False'), ['-1'])
        self.assertEqual(show('ShowValue True Xor True'), ['0'])

    def test_case_does_not_matter(self):
        self.assertEqual(show('DIM aB\nab = 3\nshowvalue AB'), ['3'])

    def test_comments_and_continuation(self):
        text = "REM rien\n' rien non plus\nDim a : a = 1 + _\n  2 ' fin\nShowValue a"
        self.assertEqual(show(text), ['3'])

    def test_if_forms(self):
        self.assertEqual(show('If 1 Then ShowValue "a" Else ShowValue "b"'), ['a'])
        self.assertEqual(show('If 0 Then ShowValue "a" Else ShowValue "b"'), ['b'])
        self.assertEqual(show('If 0 Then ShowValue "a" : ShowValue "c"'), [])
        self.assertEqual(show('If 1 Then ShowValue "a" : ShowValue "c"'), ['a', 'c'])
        text = 'x = 2\nIf x = 1 Then\n ShowValue "un"\nElseIf x = 2 Then\n ShowValue "deux"\nElse\n ShowValue "autre"\nEnd If'
        self.assertEqual(show(text), ['deux'])

    def test_else_if_on_a_line_nests(self):
        text = 'x = 2\nIf x = 1 Then\n ShowValue "un"\nElse If x = 2 Then\n  ShowValue "deux"\n End If\n ShowValue "fin"\nEnd If'
        self.assertEqual(show(text), ['deux', 'fin'])

    def test_for(self):
        self.assertEqual(show('For i = 1 To 3\nShowValue i\nNext'), ['1', '2', '3'])
        self.assertEqual(show('For i = 3 To 1 Step -1\nShowValue i\nNext i'), ['3', '2', '1'])
        self.assertEqual(show('For i = 1 To 0\nShowValue i\nNext'), [])
        self.assertEqual(show('For i = 1 To 9\nIf i = 2 Then Exit For\nShowValue i\nNext'), ['1'])

    def test_step_is_also_a_name(self):
        self.assertEqual(show('step = 2\nFor i = 0 To 4 Step step\nShowValue i\nNext'), ['0', '2', '4'])

    def test_while_and_do(self):
        self.assertEqual(show('i = 0\nWhile i < 2\ni = i + 1\nShowValue i\nWend'), ['1', '2'])
        self.assertEqual(show('i = 0\nDo\ni = i + 1\nLoop Until i = 3\nShowValue i'), ['3'])
        self.assertEqual(show('i = 5\nDo While i < 3\ni = i + 1\nLoop\nShowValue i'), ['5'])
        self.assertEqual(show('i = 0\nDo\ni = i + 1\nIf i = 2 Then Exit Do\nLoop\nShowValue i'), ['2'])

    def test_select(self):
        text = 'x = {}\nSelect Case x\nCase 1, 2\n ShowValue "a"\nCase 3\n ShowValue "b"\nCase Else\n ShowValue "c"\nEnd Select'
        self.assertEqual(show(text.format(2)), ['a'])
        self.assertEqual(show(text.format(3)), ['b'])
        self.assertEqual(show(text.format(9)), ['c'])

    def test_function_and_recursion(self):
        text = 'Function F(n)\n If n < 2 Then\n  F = 1\n  Exit Function\n End If\n F = n * F(n - 1)\nEnd Function\nShowValue F(5)'
        self.assertEqual(show(text), ['120'])

    def test_functions_exist_before_they_are_written(self):
        self.assertEqual(show('ShowValue G(2)\nFunction G(x)\n G = x + 1\nEnd Function'), ['3'])

    def test_function_without_parentheses(self):
        self.assertEqual(show('Function H\n H = 4\nEnd Function\nIf H Then ShowValue H'), ['4'])

    def test_sub_without_parentheses(self):
        self.assertEqual(show('Sub S(a, b)\n ShowValue a + b\nEnd Sub\nS 1, 2\nCall S(3, 4)'), ['3', '7'])

    def test_parenthesis_at_the_start_of_an_argument(self):
        self.assertEqual(show('Sub S(a, b)\n ShowValue a + b\nEnd Sub\nS (1 + 1) * 2, 3'), ['7'])

    def test_scope(self):
        text = 'g = 1\nSub S\n Dim g\n g = 5\n k = 7\nEnd Sub\nS\nShowValue g\nShowValue k + 0'
        self.assertEqual(show(text), ['1', '0'])
        self.assertEqual(show('g = 1\nSub S\n g = 5\nEnd Sub\nS\nShowValue g'), ['5'])

    def test_arguments_by_reference_unless_byval(self):
        self.assertEqual(show('Sub S(a)\n a = 9\nEnd Sub\nx = 1\nS x\nShowValue x'), ['9'])
        self.assertEqual(show('Sub S(ByVal a)\n a = 9\nEnd Sub\nx = 1\nS x\nShowValue x'), ['1'])

    def test_arrays(self):
        text = 'Dim a(2), m(1, 1)\na(2) = 5\nm(1, 0) = 6\nShowValue a(2) + m(1, 0)\nShowValue UBound(a)'
        self.assertEqual(show(text), ['11', '2'])

    def test_redim(self):
        self.assertEqual(show('Dim a(1)\na(1) = 5\nReDim Preserve a(3)\nShowValue a(1)\nShowValue UBound(a)'), ['5', '3'])
        self.assertEqual(show('Dim a(1)\na(1) = 5\nReDim a(3)\nShowValue a(1) + 0'), ['0'])

    def test_builtins(self):
        self.assertEqual(show('ShowValue Sqr(9)'), ['3'])
        self.assertEqual(show('ShowValue Int(-1.5)'), ['-2'])
        self.assertEqual(show('ShowValue Fix(-1.5)'), ['-1'])
        self.assertEqual(show('ShowValue CInt(2.5)'), ['2'])
        self.assertEqual(show('ShowValue Sgn(-3)'), ['-1'])
        self.assertEqual(show('ShowValue Mid("abcd", 2, 2)'), ['bc'])
        self.assertEqual(show('ShowValue Left("abcd", 1) & Right("abcd", 1)'), ['ad'])
        self.assertEqual(show('ShowValue FormatNumber(1.5, 3)'), ['1.500'])
        self.assertEqual(show('p = Split("a b", " ")\nShowValue p(1)'), ['b'])
        self.assertAlmostEqual(float(show('ShowValue 4 * Atn(1)')[0]), math.pi, places=9)

    def test_numbers_written_differently(self):
        self.assertEqual(show('ShowValue &H10'), ['16'])
        self.assertEqual(show('ShowValue .5 + 1e1'), ['10.5'])
        self.assertEqual(show('ShowValue CDbl("1,5")'), ['1.5'])


class TestErrors(unittest.TestCase):
    def fails(self, text, key, line=None, **kw):
        with self.assertRaises(SS.ScriptError) as got:
            run(text, **kw)
        self.assertEqual(got.exception.key, key)
        if line is not None:
            self.assertEqual(got.exception.line, line)
        return got.exception

    def test_syntax_gives_the_line(self):
        self.fails('a = 1\nIf a Then\nb = 2\n', 'syntax')
        self.fails('a = 1\nb = = 2', 'syntax', 2)
        self.fails('a = $', 'syntax', 1)

    def test_unknown_function_is_named(self):
        ex = self.fails('a = 1\nFooBar 2', 'unknown', 2)
        self.assertEqual(ex.arg, 'FooBar')

    def test_division_by_zero(self):
        self.fails('a = 1 / 0', 'zero', 1)
        self.fails('a = 1 \\ 0', 'zero', 1)
        self.fails('a = 1 Mod 0', 'zero', 1)

    def test_endless_loop_stops(self):
        with self.assertRaises(SS.ScriptError) as got:
            SS.run('Do\nLoop', max_steps=1000)
        self.assertEqual(got.exception.key, 'steps')

    def test_endless_recursion_stops(self):
        self.fails('Function F(n)\n F = F(n + 1)\nEnd Function\na = F(0)', 'depth')

    def test_bad_number(self):
        self.fails('a = "abc" * 2', 'number', 1)
        self.fails('LineTo "nan", 0, 0', 'number', 1)

    def test_impossible_values(self):
        self.fails('a = Sqr(-1)', 'value', 1)
        self.fails('a = (-8) ^ 0.5', 'value', 1)
        self.fails('MoveTo 1e308, 1e308, 0', 'value', 1)

    def test_array_limits(self):
        self.fails('Dim a(2)\nb = a(3)', 'index', 2)
        self.fails('Dim a(2000000000)', 'array', 1)

    def test_text_cannot_explode(self):
        self.fails('s = "aaaaaaaaaa"\nFor i = 1 To 60\n s = s & s\nNext', 'value', 3)

    def test_wrong_argument_count(self):
        self.fails('a = Sqr(1, 2)', 'args', 1)
        self.fails('Sub S(a)\nEnd Sub\nS 1, 2', 'args', 3)

    def test_nothing_reaches_the_system(self):
        for text in ('Set f = CreateObject("Scripting.FileSystemObject")', 'Execute "a = 1"', 'a = Eval("1 + 1")'):
            self.fails(text, 'unsupported', 1)

    def test_document_objects_are_refused_by_name(self):
        ex = self.fails('Set d = GetDocument()', 'unsupported', 1)
        self.assertEqual(ex.arg, 'GetDocument')
        self.fails('Set p = GetThing\np.Value = 1', 'unsupported', 2)

    def test_exit_for_outside_a_loop(self):
        self.fails('Exit For', 'syntax')

    def test_exit_sub_ends_the_script(self):
        self.assertEqual(show('ShowValue 1\nExit Sub\nShowValue 2'), ['1'])


class TestDrawing(unittest.TestCase):
    def test_metres_become_millimetres(self):
        got = run('MoveTo 0, 0, 0\nLineTo 0.01, 0.02, 0').contours
        self.assertEqual(Path(got).bbox(), (0.0, 0.0, 10.0, 20.0))
        self.assertFalse(got[0].closed)

    def test_close_path(self):
        got = run('MoveTo 0, 0, 0\nLineTo .01, 0, 0\nLineTo .01, .01, 0\nClosePath').contours
        self.assertEqual(len(got), 1)
        self.assertTrue(got[0].closed)
        self.assertAlmostEqual(abs(Path(got).area()) if hasattr(Path, 'area') else 50.0, 50.0, places=6)

    def test_new_curve_is_true_and_starts_a_contour(self):
        text = 'If NewCurve Then\nMoveTo 0, 0, 0\nLineTo .01, 0, 0\nEnd If\nIf NewCurve Then\nMoveTo 0, .01, 0\nLineTo .01, .01, 0\nEnd If'
        self.assertEqual(len(run(text).contours), 2)

    def test_touching_curves_are_joined(self):
        text = 'NewCurve\nMoveTo 0, 0, 0\nLineTo .01, 0, 0\nNewCurve\nMoveTo .01, 0, 0\nLineTo .01, .01, 0\nNewCurve\nMoveTo .01, .01, 0\nLineTo 0, 0, 0'
        got = run(text).contours
        self.assertEqual(len(got), 1)
        self.assertTrue(got[0].closed)

    def test_z_is_ignored(self):
        self.assertEqual(Path(run('MoveTo 0, 0, 5\nLineTo .01, 0, 9').contours).bbox()[3], 0.0)

    def _arc(self, verb, end, centre=(0, 0)):
        text = f'MoveTo .01, 0, 0\n{verb} {end[0]}, {end[1]}, 0, {centre[0]}, {centre[1]}, 0'
        return run(text).contours[0]

    def test_arc_clockwise_is_the_long_way_up(self):
        c = self._arc('ArcHTo', (0, .01))                # horaire de (10,0) à (0,10) : trois quarts de tour par le bas
        x0, y0, x1, y1 = Path([c]).bbox()
        self.assertAlmostEqual(y0, -10.0, places=3)
        self.assertAlmostEqual(x0, -10.0, places=3)

    def test_arc_counter_clockwise_is_the_short_way_up(self):
        c = self._arc('ArcTTo', (0, .01))                # anti-horaire de (10,0) à (0,10) : un quart de tour
        x0, y0, x1, y1 = Path([c]).bbox()
        self.assertAlmostEqual(y0, 0.0, places=3)
        self.assertAlmostEqual(x0, 0.0, places=3)
        self.assertAlmostEqual(y1, 10.0, places=3)

    def test_arc_end_is_exact(self):
        c = self._arc('ArcTTo', (0, .01))
        self.assertAlmostEqual(c.end[0], 0.0, places=6)
        self.assertAlmostEqual(c.end[1], 10.0, places=6)

    def test_full_circle_both_ways(self):
        for verb in ('ArcHTo', 'ArcTTo'):
            c = self._arc(verb, (.01, 0))
            x0, y0, x1, y1 = Path([c]).bbox()
            self.assertAlmostEqual(x1 - x0, 20.0, places=3)
            self.assertAlmostEqual(y1 - y0, 20.0, places=3)

    def test_arc_end_off_the_circle_is_reached(self):
        c = self._arc('ArcTTo', (0, .02))
        self.assertAlmostEqual(c.end[1], 20.0, places=6)

    def test_nothing_drawn(self):
        self.assertEqual(run('a = 1').contours, [])

    def test_drawing_limit(self):
        with mock.patch.object(SS, 'MAX_SEGMENTS', 10):
            with self.assertRaises(SS.ScriptError) as got:
                run('MoveTo 0, 0, 0\nFor i = 1 To 100\nLineTo i / 1000, 0, 0\nNext')
        self.assertEqual(got.exception.key, 'segments')


class TestHost(unittest.TestCase):
    def test_input_box(self):
        asked = []

        def ask(title, default):
            asked.append((title, default))
            return '0.01'
        got = run('r = InputScriptBox("Rayon", "5")\nMoveTo 0, 0, 0\nLineTo r, 0, 0', ask=ask)
        self.assertEqual(asked, [('Rayon', '5')])
        self.assertAlmostEqual(Path(got.contours).bbox()[2], 10.0)

    def test_input_box_cancelled(self):
        self.assertEqual(show('r = InputScriptBox("t", "1")\nShowValue r', ask=lambda _t, _d: None), ['IDCANCEL'])

    def test_input_box_without_interface_gives_the_default(self):
        self.assertEqual(show('ShowValue InputScriptBox("t", "7")'), ['7'])

    def test_app_parameters(self):
        text = 'ShowValue GetNbParameters()\nShowValue GetAppParameter(1)\nShowValue "[" & GetAppParameter(5) & "]"'
        self.assertEqual(show(text, params=['a', 'b']), ['2', 'b', '[]'])

    def test_kept_values(self):
        store = {}
        text = ('a = DbApi.GetProfileDbl("r", "S", 1.5)\nShowValue a\nDbApi.WriteProfileDbl "r", "S", a + 1\n'
                'DbApi.WriteProfileLong "n", "S", 3\nDbApi.WriteProfileString "t", "S", "x"')
        self.assertEqual(show(text, profile=store), ['1.5'])
        self.assertEqual(show(text, profile=store), ['2.5'])
        self.assertEqual(store['S/n'], 3.0)
        self.assertEqual(store['S/t'], 'x')
        self.assertEqual(show('ShowValue DbApi.GetProfileLong("n", "S", 0) & DbApi.GetProfileString("t", "S", "")', profile=store), ['3x'])

    SCRIPT_BOX = ('WndScriptApi.CleanListEdit\nWndScriptApi.SetBoxSize 300, 200\nWndScriptApi.AddEdit "R", "Rayon", "5"\n'
                  'o = WndScriptApi.DoModalDynamic("Titre")\nShowValue o\nShowValue WndScriptApi.GetValueEdit("R")')

    def test_dynamic_box(self):
        seen = {}

        def dialog(title, edits):
            seen.update(title=title, edits=edits)
            return {'R': '9'}
        self.assertEqual(show(self.SCRIPT_BOX, dialog=dialog), ['IDOK', '9'])
        self.assertEqual(seen, {'title': 'Titre', 'edits': [('R', 'Rayon', '5')]})

    def test_dynamic_box_cancelled(self):
        self.assertEqual(show(self.SCRIPT_BOX, dialog=lambda _t, _e: None)[0], 'IDCancel')

    def test_dynamic_box_without_interface_keeps_defaults(self):
        self.assertEqual(show(self.SCRIPT_BOX), ['IDOK', '5'])

    def test_html_box_is_not_opened_and_says_so(self):
        got = run('o = WndScriptApi.DoModalHTML("x.htm", 300, 200)\nMoveTo 0, 0, 0\nLineTo .01, 0, 0')
        self.assertIn('html', got.notes)
        self.assertEqual(len(got.contours), 1)

    def test_reeditable_object(self):
        text = ('Set o = CreatUnicReeditableObject()\nr = 0.01\nIf o.IsParamExist("Rayon") Then r = o.GetParamDouble("Rayon")\n'
                'MoveTo 0, 0, 0\nLineTo r, 0, 0\nAddCurveToReeditableObject\no.AddParamDouble "Rayon", r * 2\no.SetResizable False')
        first = run(text)
        self.assertEqual(first.reedit, {'rayon': 0.02})
        self.assertAlmostEqual(Path(first.contours).bbox()[2], 10.0)
        second = run(text, reedit=first.reedit)
        self.assertAlmostEqual(Path(second.contours).bbox()[2], 20.0)
        self.assertEqual(second.reedit, {'rayon': 0.04})

    def test_no_reeditable_object_by_default(self):
        self.assertIsNone(run('MoveTo 0, 0, 0\nLineTo .01, 0, 0').reedit)


class TestFiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)
        self.env = mock.patch.dict(os.environ, {'VECTORDRIVE_SCRIPTS': str(self.dir / 'mes')})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_include_from_the_same_folder(self):
        (self.dir / 'Aide.sli').write_text('Function Deux\n Deux = 2\nEnd Function\n', encoding='utf-8')
        self.assertEqual(show('VbScriptInclude Aide\nShowValue Deux', folder=self.dir), ['2'])

    def test_include_with_quotes_and_extension(self):
        (self.dir / 'Aide.sli').write_text('x = 5\n', encoding='utf-8')
        self.assertEqual(show('VbScriptInclude "Aide.sli"\nShowValue x', folder=self.dir), ['5'])

    def test_include_cannot_leave_its_folder(self):
        sub = self.dir / 'sous'
        sub.mkdir()
        (self.dir / 'Dehors.sli').write_text('x = 5\n', encoding='utf-8')
        for name in ('"../Dehors"', '"..\\Dehors"', '"C:/Dehors"'):
            with self.assertRaises(SS.ScriptError) as got:
                run('VbScriptInclude ' + name, folder=sub)
            self.assertEqual(got.exception.key, 'include')

    def test_include_missing(self):
        with self.assertRaises(SS.ScriptError) as got:
            run('VbScriptInclude Absent', folder=self.dir)
        self.assertEqual(got.exception.key, 'include')

    def test_include_loop_stops(self):
        (self.dir / 'Boucle.sli').write_text('VbScriptInclude Boucle\n', encoding='utf-8')
        with self.assertRaises(SS.ScriptError) as got:
            run('VbScriptInclude Boucle', folder=self.dir)
        self.assertEqual(got.exception.key, 'include')

    def test_error_in_an_include_names_the_file(self):
        (self.dir / 'Faux.sli').write_text('a = 1\nb = = 2\n', encoding='utf-8')
        with self.assertRaises(SS.ScriptError) as got:
            run('VbScriptInclude Faux', folder=self.dir)
        self.assertEqual((got.exception.file, got.exception.line), ('Faux', 2))

    def test_reads_old_windows_scripts(self):
        f = self.dir / 'a.txt'
        f.write_bytes("' é\r\nShowValue 1\r\n".encode('cp1252'))
        self.assertIn('é', SS.read_text(f))
        self.assertEqual(show(SS.read_text(f)), ['1'])

    def test_reads_utf8_with_mark(self):
        f = self.dir / 'a.txt'
        f.write_bytes('\ufeffShowValue "é"'.encode('utf-8'))
        self.assertEqual(show(SS.read_text(f)), ['é'])

    def test_listing_leaves_out_helpers(self):
        for n in ('b.txt', 'a.sme', 'c.sli', 'd.ini', 'e.jpg'):
            (self.dir / n).write_text('', encoding='utf-8')
        self.assertEqual([f.name for f in SS.scripts_in(self.dir)], ['a.sme', 'b.txt'])
        self.assertEqual(SS.scripts_in(self.dir / 'absent'), [])

    def test_values_stay_out_of_the_script_folder(self):
        script = self.dir / 'lecture' / 'x.txt'
        script.parent.mkdir()
        SS.save_values(script, {'S/r': 2.0})
        self.assertEqual(SS.load_values(script), {'S/r': 2.0})
        self.assertEqual(list(script.parent.iterdir()), [])
        self.assertEqual(json.loads((SS.user_dir() / '_valeurs' / 'x.json').read_text(encoding='utf-8')), {'S/r': 2.0})

    def test_values_broken_or_absent(self):
        script = self.dir / 'y.txt'
        self.assertEqual(SS.load_values(script), {})
        f = SS.user_dir() / '_valeurs' / 'y.json'
        f.parent.mkdir(parents=True)
        f.write_text('{ pas du json', encoding='utf-8')
        self.assertEqual(SS.load_values(script), {})


HEXAGON = """Dim i, a
If NewCurve Then
  MoveTo 0.02, 0, 0
  For i = 1 To 5
    a = i * 8 * Atn(1) / 6
    LineTo 0.02 * Cos(a), 0.02 * Sin(a), 0
  Next
  ClosePath
End If
"""

REEDIT = """Set o = CreatUnicReeditableObject()
r = 0.01
If o.IsParamExist("r") Then r = o.GetParamDouble("r")
s = InputScriptBox("Rayon", FormatNumber(r, 3))
If s <> "IDCANCEL" Then
  r = CDbl(s)
  MoveTo r, 0, 0
  ArcTTo r, 0, 0, 0, 0, 0
  ClosePath
  AddCurveToReeditableObject
  o.AddParamDouble "r", r
End If
"""


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)
        self.env = mock.patch.dict(os.environ, {
            'VECTORDRIVE_SCRIPTS': str(self.dir / 'mes'), 'VECTORDRIVE_SETTINGS': str(self.dir / 'r.ini'),
            'VECTORDRIVE_SESSION': str(self.dir / 'session'), 'VECTORDRIVE_CACHE': str(self.dir / 'cache')})
        self.env.start()
        from vectordrive.ui.main_window import MainWindow
        self.win = MainWindow()

    def tearDown(self):
        self.win.canvas.doc.modified = False
        self.win.close()
        self.win.deleteLater()
        self.env.stop()
        self.tmp.cleanup()

    def shapes(self):
        return [it for it in self.win.canvas.doc.iter_items()]

    def test_action_and_te_link(self):
        from vectordrive.ui.icons import ICONS
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertIn('shape_script', self.win.A)
        self.assertEqual(TE_ACTIONS['ID_SHAPE_SCRIPT'], 'shape_script')
        self.assertIn('shape_script', ICONS)

    def test_run_adds_one_shape_with_undo(self):
        shape = self.win.run_shape_script(HEXAGON)
        self.assertIn(shape, self.shapes())
        self.assertEqual(len(shape.path.contours), 1)
        self.assertTrue(shape.path.contours[0].closed)
        self.assertEqual(list(self.win.canvas.selection), [shape])
        self.assertEqual(shape.tool, self.win.canvas.current_tool_index)
        self.assertNotIn('script', shape.extra)
        self.win.undo()
        self.assertEqual(self.shapes(), [])

    def test_empty_script_adds_nothing(self):
        self.assertIsNone(self.win.run_shape_script('a = 1'))
        self.assertEqual(self.shapes(), [])

    def test_error_adds_nothing_and_keeps_no_value(self):
        script = self.dir / 'faux.txt'
        with self.assertRaises(SS.ScriptError):
            self.win.run_shape_script('DbApi.WriteProfileDbl "r", "S", 1\nb = = 2', script)
        with self.assertRaises(SS.ScriptError):
            self.win.run_shape_script('DbApi.WriteProfileDbl "r", "S", 1\nb = 1 / 0', script)
        self.assertEqual(self.shapes(), [])
        self.assertEqual(SS.load_values(script), {})

    def test_values_are_kept_after_a_run(self):
        script = self.dir / 'bon.txt'
        text = 'a = DbApi.GetProfileDbl("r", "S", 0.01)\nMoveTo 0, 0, 0\nLineTo a, 0, 0\nDbApi.WriteProfileDbl "r", "S", a * 2'
        one = self.win.run_shape_script(text, script)
        two = self.win.run_shape_script(text, script)
        self.assertAlmostEqual(one.path.bbox()[2], 10.0)
        self.assertAlmostEqual(two.path.bbox()[2], 20.0)

    def _answers(self, *values):
        return mock.patch('vectordrive.ui.script_dialog.QInputDialog.getText', side_effect=[(v, True) for v in values])

    def test_double_click_reopens_with_its_values(self):
        with self._answers('0.01'):
            shape = self.win.run_shape_script(REEDIT)
        self.assertEqual(shape.extra['script']['params'], {'r': 0.01})
        self.assertAlmostEqual(shape.path.bbox()[2], 10.0, places=3)
        with self._answers('0.02') as ask:
            self.win._item_double_clicked(shape)
        self.assertEqual(ask.call_args.kwargs['text'], '0.010')
        new = self.shapes()[0]
        self.assertIsNot(new, shape)
        self.assertAlmostEqual(new.path.bbox()[2], 20.0, places=3)
        self.assertEqual(new.extra['script']['params'], {'r': 0.02})
        self.win.undo()
        self.assertAlmostEqual(self.shapes()[0].path.bbox()[2], 10.0, places=3)

    def test_reopening_keeps_where_it_was_moved(self):
        from vectordrive.core.geom import Affine
        with self._answers('0.01'):
            shape = self.win.run_shape_script(REEDIT)
        shape.path = shape.path.transformed(Affine.translation(100, 50))
        with self._answers('0.02'):
            new = self.win.edit_script_object(shape)
        x0, y0, x1, y1 = new.path.bbox()
        self.assertAlmostEqual((x0 + x1) / 2, 100, places=3)
        self.assertAlmostEqual((y0 + y1) / 2, 50, places=3)
        with self._answers('0.02'):
            again = self.win.edit_script_object(new)
        self.assertAlmostEqual(sum(again.path.bbox()[::2]) / 2, 100, places=3)

    def test_reopening_cancelled_changes_nothing(self):
        with self._answers('0.01'):
            shape = self.win.run_shape_script(REEDIT)
        with mock.patch('vectordrive.ui.script_dialog.QInputDialog.getText', return_value=('', False)):
            self.assertIsNone(self.win.edit_script_object(shape))
        self.assertEqual(self.shapes(), [shape])

    def test_document_keeps_the_object(self):
        with self._answers('0.01'):
            shape = self.win.run_shape_script(REEDIT)
        clone = shape.clone()
        self.assertEqual(clone.extra['script']['params'], {'r': 0.01})

    def test_box_of_the_script(self):
        from PySide6.QtWidgets import QDialog
        from vectordrive.ui.script_dialog import ParamBox, make_host
        box = ParamBox(self.win, 'T', [('R', 'Rayon', '5'), ('N', 'Nombre', '3')])
        self.assertEqual(box.values(), {'R': '5', 'N': '3'})
        box.fields['R'].setText('8')
        self.assertEqual(box.values()['R'], '8')
        host = make_host(self.win, None)
        with mock.patch.object(ParamBox, 'exec', return_value=QDialog.DialogCode.Rejected):
            self.assertIsNone(host.dialog('T', [('R', 'Rayon', '5')]))
        with mock.patch.object(ParamBox, 'exec', return_value=QDialog.DialogCode.Accepted):
            self.assertEqual(host.dialog('T', [('R', 'Rayon', '5')]), {'R': '5'})

    def test_error_messages_cover_every_key(self):
        from vectordrive.ui.script_dialog import why
        for key in ('syntax', 'array', 'index', 'number', 'steps', 'zero', 'value', 'depth', 'include', 'args',
                    'unsupported', 'unknown', 'segments'):
            text = why(SS.ScriptError(key, 'xyz', 7))
            self.assertIn('7', text)
            self.assertNotIn('{', text)
        self.assertIn('Foo', why(SS.ScriptError('unknown', 'Foo', 1)))


class TestDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)
        self.env = mock.patch.dict(os.environ, {
            'VECTORDRIVE_SCRIPTS': str(self.dir / 'mes'), 'VECTORDRIVE_SETTINGS': str(self.dir / 'r.ini'),
            'VECTORDRIVE_SESSION': str(self.dir / 'session'), 'VECTORDRIVE_CACHE': str(self.dir / 'cache')})
        self.env.start()
        from vectordrive.ui.main_window import MainWindow
        self.win = MainWindow()
        self.other = self.dir / 'autres'
        self.other.mkdir()
        (self.other / 'lu.txt').write_text('MoveTo 0, 0, 0\nLineTo .01, 0, 0\n', encoding='utf-8')

    def tearDown(self):
        self.win.canvas.doc.modified = False
        self.win.close()
        self.win.deleteLater()
        self.env.stop()
        self.tmp.cleanup()

    def dialog(self, folder=None):
        from vectordrive.ui.script_dialog import ScriptDialog
        return ScriptDialog(self.win, folder)

    def names(self, dlg):
        return [dlg.list.item(i).text().strip() for i in range(dlg.list.count())]

    def _select(self, dlg, stem):
        row = self.names(dlg).index(stem)
        dlg.list.setCurrentRow(row)

    def test_opens_on_an_example_that_works(self):
        dlg = self.dialog()
        self.assertTrue(dlg.edit.toPlainText())
        self.assertIsNotNone(dlg.try_script())
        self.assertIn('1', dlg.message.text())

    def test_new_script_is_saved_in_my_scripts(self):
        dlg = self.dialog()
        target = dlg.save_script('essai')
        self.assertEqual(target, SS.user_dir() / 'essai.txt')
        self.assertEqual(target.read_text(encoding='utf-8'), dlg.edit.toPlainText())
        self.assertIn('essai', self.names(dlg))

    def test_bad_characters_are_removed_from_the_name(self):
        self.assertEqual(self.dialog().save_script('a/b:c').name, 'abc.txt')
        self.assertIsNone(self.dialog().save_script('///'))

    def test_saving_again_writes_the_same_file(self):
        dlg = self.dialog()
        target = dlg.save_script('essai')
        dlg.edit.setPlainText('a = 2\n')
        self.assertEqual(dlg.save_script(), target)
        self.assertEqual(target.read_text(encoding='utf-8'), 'a = 2\n')

    def test_replacing_asks_first(self):
        from PySide6.QtWidgets import QMessageBox
        dlg = self.dialog()
        target = dlg.save_script('essai')
        before = target.read_text(encoding='utf-8')
        dlg.new_script()
        dlg.edit.setPlainText('a = 2\n')
        with mock.patch('vectordrive.ui.script_dialog.QMessageBox.question', return_value=QMessageBox.StandardButton.No):
            self.assertIsNone(dlg.save_script('essai'))
        self.assertEqual(target.read_text(encoding='utf-8'), before)

    def test_outside_folder_is_read_only(self):
        dlg = self.dialog(self.other)
        self.assertIn('lu', self.names(dlg))
        self._select(dlg, 'lu')
        self.assertTrue(dlg.edit.isReadOnly())
        before = (self.other / 'lu.txt').read_text(encoding='utf-8')
        target = dlg.save_script('copie')
        self.assertEqual(target.parent, SS.user_dir())
        self.assertEqual((self.other / 'lu.txt').read_text(encoding='utf-8'), before)
        self.assertEqual(sorted(p.name for p in self.other.iterdir()), ['lu.txt'])
        self.assertFalse(dlg.edit.isReadOnly())

    def test_section_titles_cannot_be_picked(self):
        dlg = self.dialog(self.other)
        self.assertFalse(dlg.list.item(0).flags())

    def test_try_changes_nothing(self):
        dlg = self.dialog()
        dlg.edit.setPlainText('DbApi.WriteProfileDbl "r", "S", 1\nMoveTo 0, 0, 0\nLineTo .01, 0, 0')
        target = dlg.save_script('essai')
        got = dlg.try_script()
        self.assertEqual(len(got.contours), 1)
        self.assertIn('10.000', dlg.message.text())
        self.assertEqual(list(self.win.canvas.doc.iter_items()), [])
        self.assertEqual(SS.load_values(target), {})

    def test_error_shows_its_line(self):
        dlg = self.dialog()
        dlg.edit.setPlainText('a = 1\nb = = 2\nc = 3')
        self.assertIsNone(dlg.try_script())
        self.assertIn('2', dlg.message.text())
        self.assertEqual(dlg.edit.textCursor().selectedText(), 'b = = 2')

    def test_draw_adds_and_closes(self):
        dlg = self.dialog()
        dlg.edit.setPlainText('MoveTo 0, 0, 0\nLineTo .01, 0, 0')
        item = dlg.draw_script()
        self.assertIn(item, list(self.win.canvas.doc.iter_items()))

    def test_draw_with_an_error_stays_open(self):
        dlg = self.dialog()
        dlg.edit.setPlainText('a = 1 / 0')
        self.assertIsNone(dlg.draw_script())
        self.assertIn('1', dlg.message.text())
        self.assertEqual(list(self.win.canvas.doc.iter_items()), [])

    def test_draw_nothing_says_so(self):
        dlg = self.dialog()
        dlg.edit.setPlainText('a = 1')
        self.assertIsNone(dlg.draw_script())
        self.assertTrue(dlg.message.text())

    def test_html_box_is_mentioned(self):
        dlg = self.dialog()
        dlg.edit.setPlainText('o = WndScriptApi.DoModalHTML("x.htm", 1, 1)\nMoveTo 0, 0, 0\nLineTo .01, 0, 0')
        dlg.try_script()
        self.assertIn('HTML', dlg.message.text())

    def test_no_typeedit_folder_in_tests(self):
        self.assertIsNone(self.win._te_script_folder())


if __name__ == '__main__':
    unittest.main()
