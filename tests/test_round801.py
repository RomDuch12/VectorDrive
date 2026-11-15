"""Round 801 : HPGL lu en entier."""
import math
import pathlib
import tempfile
import unittest

from vectordrive.core import geom
from vectordrive.core.document import Text
from vectordrive.io import hpgl, registry


def contours(text, pen=1):
    return hpgl.read_text(text)[0].get(pen, [])


def box(cs):
    return geom.Path(list(cs)).bbox()


def state(text):
    return hpgl._parse(hpgl._unwrap(text) or '')


def encode_number(v, seven=False):
    """Un nombre de PE, comme le font les pilotes."""
    n = (abs(v) << 1) | (1 if v < 0 else 0)
    base = 32 if seven else 64
    out = []
    while True:
        d, n = n % base, n // base
        if n == 0:
            out.append(chr(d + (95 if seven else 191)))
            return ''.join(out)
        out.append(chr(d + 63))


def encode(points, seven=False):
    return ''.join(encode_number(x, seven) + encode_number(y, seven) for x, y in points)


class Scale(unittest.TestCase):
    def assertBox(self, got, want, places=6):
        for a, b in zip(got, want):
            self.assertAlmostEqual(a, b, places=places)

    def test_anisotropic(self):
        # P1 P2 = 400 x 800 unités = 10 x 20 mm, pour 100 x 100 unités du fichier
        c = contours('IP0,0,400,800;SC0,100,0,100;PU0,0;PD100,0,100,100;PU;')
        self.assertBox(box(c), (0, 0, 10, 20))

    def test_origin_of_the_user_units(self):
        c = contours('IP400,400,800,800;SC-50,50,-50,50;PU0,0;PD50,50;PU;')
        self.assertBox(box(c), (15, 15, 20, 20))

    def test_isotropic_centres_by_default(self):
        c = contours('IP0,0,800,400;SC0,100,0,100,1;PU0,0;PD100,100;PU;')
        self.assertBox(box(c), (5, 0, 15, 10))

    def test_isotropic_left_bottom(self):
        c = contours('IP0,0,800,400;SC0,100,0,100,1,0,0;PU0,0;PD100,100;PU;')
        self.assertBox(box(c), (0, 0, 10, 10))
        c = contours('IP0,0,800,400;SC0,100,0,100,1,100,100;PU0,0;PD100,100;PU;')
        self.assertBox(box(c), (10, 0, 20, 10))

    def test_point_factor_needs_no_window(self):
        st = state('SC0,4,0,8,2;PU0,0;PD100,100;PU;')
        self.assertBox(box(st.by_pen[1]), (0, 0, 10, 20))
        self.assertFalse(st.guessed)

    def test_without_window_the_size_is_a_guess(self):
        st = state('SC0,100,0,100;PU0,0;PD400,400;PU;')
        self.assertTrue(st.guessed)
        self.assertBox(box(st.by_pen[1]), (0, 0, 10, 10))

    def test_mirror(self):
        c = contours('IP0,0,400,400;SC100,0,0,100;PU0,0;PD100,100;PU;')
        self.assertBox(box(c), (0, 0, 10, 10))
        self.assertEqual(c[0].segments[0].start, (10.0, 0.0))

    def test_scale_off(self):
        c = contours('IP0,0,400,400;SC0,1,0,1;PU0,0;PD1,1;PU;SC;PU800,800;PD840,840;PU;')
        self.assertBox(box(c[:1]), (0, 0, 10, 10))
        self.assertBox(box(c[1:]), (20, 20, 21, 21))

    def test_impossible_scale_is_ignored(self):
        c = contours('IP0,0,400,400;SC5,5,0,1;PU0,0;PD40,40;PU;')
        self.assertBox(box(c), (0, 0, 1, 1))
        c = contours('SC0,0,0,4,2;PU0,0;PD40,40;PU;')
        self.assertBox(box(c), (0, 0, 1, 1))

    def test_the_pen_stays_on_the_paper_when_the_scale_changes(self):
        c = contours('PU400,400;IP0,0,400,400;SC0,1,0,1;PD0,0;PU;')
        self.assertEqual(len(c), 1)
        self.assertBox(c[0].segments[0].start, (10, 10))

    def test_ip_with_one_point_moves_p2(self):
        st = state('IP0,0,400,400;IP100,100;')
        self.assertEqual(st.p1, (100, 100))
        self.assertEqual(st.p2, (500, 500))
        st = state('IP0,0,400,400;IP;')
        self.assertIsNone(st.p1)

    def test_in_resets(self):
        c = contours('IP0,0,400,400;SC0,1,0,1;RO90;IN;PU0,0;PD40,40;PU;')
        self.assertBox(box(c), (0, 0, 1, 1))

    def test_df_turns_the_scale_off(self):
        c = contours('IP0,0,400,400;SC0,1,0,1;DF;PU0,0;PD40,40;PU;')
        self.assertBox(box(c), (0, 0, 1, 1))

    def test_rotation(self):
        c = contours('RO90;PU0,0;PD400,0;PU;')
        self.assertEqual(c[0].segments[0].end, (0.0, 10.0))
        c = contours('RO180;PU0,0;PD400,0;PU;')
        self.assertEqual(c[0].segments[0].end, (-10.0, 0.0))
        c = contours('RO270;PU0,0;PD400,0;PU;')
        self.assertEqual(c[0].segments[0].end, (0.0, -10.0))
        c = contours('RO;PU0,0;PD400,0;PU;')
        self.assertEqual(c[0].segments[0].end, (10.0, 0.0))

    def test_rectangle_turned(self):
        c = contours('RO90;PU0,0;EA400,200;')
        self.assertBox(box(c), (-5, 0, 0, 10))
        self.assertEqual(len(c[0].segments), 4)
        self.assertTrue(c[0].closed)


class Curves(unittest.TestCase):
    def test_arc_and_line_are_one_contour(self):
        c = contours('PU0,0;PD400,0;AA400,400,90;PD0,400,0,0;PU;')
        self.assertEqual(len(c), 1)
        self.assertTrue(c[0].closed)
        kinds = {type(s) for s in c[0].segments}
        self.assertIn(geom.Conic, kinds)
        self.assertIn(geom.Line, kinds)

    def test_arc_with_the_scale(self):
        c = contours('IP0,0,400,400;SC0,1,0,1;PU1,0;PD;AA0,0,90;PU;')
        b = box(c)
        self.assertAlmostEqual(b[2], 10.0)
        self.assertAlmostEqual(b[3], 10.0)

    def test_anisotropic_arc_is_an_ellipse(self):
        c = contours('IP0,0,400,800;SC0,1,0,1;PU1,0;PD;AA0,0,90;PU;')
        b = box(c)
        self.assertAlmostEqual(b[2], 10.0)
        self.assertAlmostEqual(b[3], 20.0)

    def test_circle_with_the_scale(self):
        c = contours('IP0,0,400,800;SC0,1,0,1;PA1,1;CI1;')
        b = box(c)
        self.assertAlmostEqual(b[0], 0.0)
        self.assertAlmostEqual(b[2], 20.0)
        self.assertAlmostEqual(b[1], 0.0)
        self.assertAlmostEqual(b[3], 40.0)

    def test_mirrored_arc_turns_the_other_way(self):
        st = state('IP0,0,400,400;SC1,-1,-1,1;PU1,0;PD;AA0,0,90;PU;')
        c = st.by_pen[1][0]
        self.assertAlmostEqual(c.end[0], 5.0 + 0.0)
        self.assertAlmostEqual(c.end[1], 10.0)

    def test_arc_with_a_rotation_ends_where_it_says(self):
        st = state('RO90;PU400,0;PD;AA0,0,90;')
        self.assertAlmostEqual(st.x, 0.0, places=9)
        self.assertAlmostEqual(st.y, 400.0, places=9)
        st.flush()
        self.assertAlmostEqual(st.by_pen[1][0].end[0], -10.0, places=9)

    def test_relative_arc(self):
        c = contours('PU400,0;PD;AR-400,0,90;PU;')
        self.assertAlmostEqual(box(c)[3], 10.0)

    def test_three_point_arc(self):
        for text in ('PU400,0;PD;AT0,400,-400,0;PU;', 'PU400,0;PD;RT-400,400,-800,0;PU;'):
            c = contours(text)
            b = box(c)
            self.assertAlmostEqual(b[3], 10.0, places=6)
            self.assertAlmostEqual(b[1], 0.0, places=6)
            self.assertAlmostEqual(c[0].end[0], -10.0, places=6)

    def test_three_point_arc_other_side(self):
        c = contours('PU400,0;PD;AT0,-400,-400,0;PU;')
        b = box(c)
        self.assertAlmostEqual(b[1], -10.0, places=6)
        self.assertAlmostEqual(b[3], 0.0, places=6)

    def test_three_points_in_line(self):
        c = contours('PU0,0;PD;AT200,0,400,0;PU;')
        self.assertEqual(c[0].segments[0].end, (10.0, 0.0))
        self.assertIsInstance(c[0].segments[0], geom.Line)

    def test_wedge(self):
        c = contours('PA400,400;EW200,0,90;')
        self.assertTrue(c[0].closed)
        self.assertEqual(c[0].segments[0].start, (10.0, 10.0))
        b = box(c)
        self.assertAlmostEqual(b[2], 15.0)
        self.assertAlmostEqual(b[3], 15.0)

    def test_whole_wedge_is_a_circle(self):
        c = contours('PA400,400;WG200,0,360;')
        self.assertTrue(c[0].closed)
        self.assertTrue(all(isinstance(s, geom.Conic) for s in c[0].segments))

    def test_beziers(self):
        c = contours('PU0,0;PD;BZ0,400,400,400,400,0;BR0,-400,400,-400,400,0;PU;')
        self.assertEqual(len(c), 1)
        self.assertEqual(len(c[0].segments), 2)
        self.assertIsInstance(c[0].segments[0], geom.Cubic)
        self.assertEqual(c[0].end, (20.0, 0.0))

    def test_polygon_closes(self):
        c = contours('PA0,0;PM0;PD400,0,400,400;PM2;FP;')
        self.assertTrue(c[0].closed)
        self.assertEqual(len(c[0].segments), 3)

    def test_polygon_with_two_rings(self):
        c = contours('PA0,0;PM0;PD400,0,400,400;PM1;PU100,100;PD200,100,200,200;PM2;')
        self.assertEqual(len(c), 2)
        self.assertTrue(all(k.closed for k in c))

    def test_pm0_does_not_close(self):
        c = contours('PA0,0;PD400,0,400,400;PM0;')
        self.assertFalse(c[0].closed)


class Encoded(unittest.TestCase):
    def test_number_codes(self):
        self.assertEqual(encode_number(0), chr(191))
        self.assertEqual(encode_number(1), chr(193))
        self.assertEqual(encode_number(-1), chr(194))
        self.assertEqual(encode_number(32, seven=True), chr(63) + chr(95 + 2))

    def test_relative_pen_down(self):
        c = contours('PA400,400;PE' + encode([(400, 0), (0, 400), (-400, 0), (0, -400)]) + ';')
        self.assertEqual(len(c), 1)
        self.assertTrue(c[0].closed)
        self.assertEqual(box(c), (10.0, 10.0, 20.0, 20.0))

    def test_big_numbers(self):
        c = contours('PE' + encode([(123456, -654321)]) + ';')
        self.assertAlmostEqual(c[0].end[0], 123456 / 40)
        self.assertAlmostEqual(c[0].end[1], -654321 / 40)

    def test_seven_bits(self):
        c = contours('PE7' + encode([(4000, 0), (0, 4000)], seven=True) + ';')
        self.assertEqual(c[0].end, (100.0, 100.0))

    def test_pen_up_flag(self):
        c = contours('PE<' + encode([(400, 400)]) + encode([(400, 0)]) + '<' + encode([(0, 400)]) + encode([(400, 0)]) + ';')
        self.assertEqual(len(c), 2)
        self.assertEqual(c[0].segments[0].start, (10.0, 10.0))
        self.assertEqual(c[1].segments[0].start, (20.0, 20.0))

    def test_absolute_flag(self):
        c = contours('PA4000,4000;PE<=' + encode([(400, 400)]) + encode([(40, 0)]) + ';')
        self.assertEqual(c[0].segments[0].start, (10.0, 10.0))
        self.assertEqual(c[0].segments[0].end, (11.0, 10.0))

    def test_fraction(self):
        c = contours('PE>' + encode_number(2) + encode([(400, 0)]) + ';')
        self.assertEqual(c[0].end, (2.5, 0.0))

    def test_pen_select(self):
        by = hpgl.read_text('PE:' + encode_number(3) + encode([(40, 0)]) + ';')[0]
        self.assertEqual(sorted(by), [3])

    def test_letters_are_data(self):
        c = contours('PE' + encode([(40 * 64, 0)]) + ';PU;')
        self.assertEqual(len(c), 1)
        # les caractères de PE ne sont pas pris pour PD, IN, etc.
        self.assertTrue(all(ord(x) >= 63 for x in encode([(1000, 2000)])))

    def test_mode_comes_back(self):
        c = contours('PA0,0;PU;PE' + encode([(40, 0)]) + ';PU400,400;PD440,400;PU;')
        self.assertEqual(c[1].segments[0].start, (10.0, 10.0))
        self.assertEqual(c[1].segments[0].end, (11.0, 10.0))

    def test_cut_short(self):
        self.assertEqual(contours('PE' + chr(70)), [])
        self.assertEqual(contours('PE:'), [])
        self.assertEqual(contours('PE<'), [])


class Labels(unittest.TestCase):
    def only(self, text):
        return [t for _p, t in state(text).texts]

    def at(self, t):
        return t.matrix.apply((0.0, 0.0))

    def test_a_text_at_its_place(self):
        t = self.only('PA400,800;LBHello\x03')
        self.assertEqual(len(t), 1)
        self.assertIsInstance(t[0], Text)
        self.assertEqual(t[0].text, 'Hello')
        self.assertEqual(self.at(t[0]), (10.0, 20.0))
        self.assertEqual(t[0].size, hpgl.CELL_H)

    def test_size_and_width(self):
        t = self.only('SI0.2,0.5;LBABCD\x03')[0]
        self.assertEqual(t.size, 5.0)
        self.assertAlmostEqual(t.extra['fit']['width'], 2.0 * 1.5 * 3 + 2.0)

    def test_relative_size(self):
        t = self.only('IP0,0,4000,8000;SR1,2;LBA\x03')[0]
        self.assertAlmostEqual(t.size, 4.0)

    def test_direction(self):
        t = self.only('DI0,1;LBA\x03')[0]
        self.assertAlmostEqual(t.matrix.b, 1.0)
        self.assertAlmostEqual(t.matrix.a, 0.0)
        t = self.only('DI1,1;LBA\x03')[0]
        self.assertAlmostEqual(math.degrees(math.atan2(t.matrix.b, t.matrix.a)), 45.0)
        t = self.only('DI0,1;DI;LBA\x03')[0]
        self.assertAlmostEqual(t.matrix.b, 0.0)

    def test_rotation_turns_texts(self):
        t = self.only('RO90;PA400,0;LBA\x03')[0]
        self.assertAlmostEqual(self.at(t)[1], 10.0)
        self.assertAlmostEqual(t.matrix.b, 1.0)

    def test_the_scale_does_not_change_the_size(self):
        t = self.only('IP0,0,400,400;SC0,1,0,1;PA1,1;LBA\x03')[0]
        self.assertEqual(t.size, hpgl.CELL_H)
        self.assertAlmostEqual(self.at(t)[0], 10.0)

    def test_origin(self):
        t = self.only('SI0.2,0.4;PA0,0;LO5;LBABC\x03')[0]
        w = 2.0 * 1.5 * 2 + 2.0
        self.assertAlmostEqual(self.at(t)[0], -w / 2)
        self.assertAlmostEqual(self.at(t)[1], -2.0)
        t = self.only('SI0.2,0.4;PA0,0;LO9;LBABC\x03')[0]
        self.assertAlmostEqual(self.at(t)[0], -w)
        self.assertAlmostEqual(self.at(t)[1], -4.0)
        t = self.only('SI0.2,0.4;PA0,0;LO11;LBABC\x03')[0]
        self.assertAlmostEqual(self.at(t)[0], 0.5)
        self.assertAlmostEqual(self.at(t)[1], 1.0)

    def test_pen_goes_on_after_a_label(self):
        t = self.only('SI0.2,0.4;PA0,0;LBAB\x03LBCD\x03')
        self.assertAlmostEqual(self.at(t[1])[0], 2.0 * 1.5 * 2)

    def test_line_breaks(self):
        t = self.only('SI0.2,0.4;PA400,4000;LBfirst\r\nsecond\x03')
        self.assertEqual([k.text for k in t], ['first', 'second'])
        self.assertEqual(self.at(t[1]), (10.0, 100.0 - 8.0))

    def test_lf_alone_stays_on_the_column(self):
        t = self.only('SI0.2,0.4;PA0,0;LBAB\nCD\x03')
        self.assertAlmostEqual(self.at(t[1])[0], 6.0)
        self.assertAlmostEqual(self.at(t[1])[1], -8.0)

    def test_backspace(self):
        t = self.only('SI0.2,0.4;PA0,0;LBA\bB\x03')
        self.assertAlmostEqual(self.at(t[1])[0], 0.0)

    def test_carriage(self):
        t = self.only('SI0.2,0.4;PA0,0;CP2,1;LBA\x03')[0]
        self.assertAlmostEqual(self.at(t)[0], 6.0)
        self.assertAlmostEqual(self.at(t)[1], 8.0)
        t = self.only('SI0.2,0.4;PA0,0;LBAB\x03CP;LBC\x03')[1]
        self.assertAlmostEqual(self.at(t)[0], 0.0)
        self.assertAlmostEqual(self.at(t)[1], -8.0)

    def test_spacing(self):
        t = self.only('SI0.2,0.4;ES0.5,0;PA0,0;LBAB\x03LBC\x03')[1]
        self.assertAlmostEqual(self.at(t)[0], 2.0 * 1.5 * 1.5 * 2)

    def test_slant(self):
        t = self.only('SL1;LBA\x03')[0]
        self.assertAlmostEqual(t.extra['italic'], 45.0)
        self.assertNotIn('italic', self.only('SL1;SL;LBA\x03')[0].extra)

    def test_font_definition(self):
        t = self.only('SD3,10,4,20;LBA\x03')[0]
        self.assertAlmostEqual(t.size, 20 * 25.4 / 72 * 0.7)
        self.assertAlmostEqual(t.extra['fit']['width'], 25.4 / 10 / 1.5)

    def test_pen_of_the_text(self):
        pen, t = state('SP4;LBA\x03').texts[0]
        self.assertEqual(pen, 4)
        self.assertEqual(t.tool, 3)

    def test_blank_labels_only_move(self):
        t = self.only('SI0.2,0.4;LB   \x03LBA\x03')
        self.assertEqual(len(t), 1)
        self.assertAlmostEqual(self.at(t[0])[0], 9.0)

    def test_other_terminator(self):
        st = state('DT*;PA0,0;LBabc*PD400,0;PU;')
        self.assertEqual([t.text for _p, t in st.texts], ['abc'])
        self.assertEqual(len(st.by_pen[1]), 1)
        st = state('DT*,1;LBabc*;DT;LBdef\x03')
        self.assertEqual([t.text for _p, t in st.texts], ['abc', 'def'])

    def test_terminator_never_swallows_everything(self):
        st = state('DT*;IN;LBabc\x03PU0,0;PD400,0;PU;')
        self.assertEqual([t.text for _p, t in st.texts], ['abc'])
        self.assertEqual(len(st.by_pen[1]), 1)

    def test_buffered_label_is_not_read_as_commands(self):
        st = state('BLPD400,400\x03PU0,0;PD40,0;PU;')
        self.assertEqual(st.texts, [])
        self.assertEqual(box(st.by_pen[1]), (0.0, 0.0, 1.0, 0.0))

    def test_quoted_strings_are_not_read_as_commands(self):
        c = contours('BP1,"Plan PD 400,400";CO"PU0,0";PU0,0;PD40,0;PU;')
        self.assertEqual(box(c), (0.0, 0.0, 1.0, 0.0))

    def test_symbol_letter_is_not_a_command(self):
        c = contours('SMP;PU0,0;PD40,0;PU;')
        self.assertEqual(box(c), (0.0, 0.0, 1.0, 0.0))


class Files(unittest.TestCase):
    def setUp(self):
        self.dir = pathlib.Path(tempfile.mkdtemp())

    def file(self, data, name='x.plt'):
        p = self.dir / name
        p.write_bytes(data if isinstance(data, bytes) else data.encode('latin-1'))
        return p

    def test_pcl_envelope(self):
        p = self.file(b'\x1b%-12345X@PJL ENTER LANGUAGE=PCL\r\n\x1bE\x1b%0BIN;PU0,0;PD400,0;PU;\x1b%0A\x1bE\x1b%-12345X')
        d = hpgl.read(p)
        self.assertEqual(d.bbox(), (0.0, 0.0, 10.0, 0.0))

    def test_several_blocks(self):
        p = self.file(b'\x1b%0BIN;PU0,0;PD400,0;PU;\x1b%0A\x1b*r1A\x1b%0BPU0,400;PD400,400;PU;\x1b%0A')
        self.assertEqual(hpgl.read(p).bbox(), (0.0, 0.0, 10.0, 10.0))

    def test_block_without_an_end(self):
        p = self.file(b'\x1b%-1BIN;PU0,0;PD400,0;PU;')
        self.assertEqual(hpgl.read(p).bbox(), (0.0, 0.0, 10.0, 0.0))

    def test_pcl_alone_is_refused(self):
        p = self.file(b'\x1b%-12345X@PJL\r\n\x1bE\x1b*r1A\x1b%-12345X')
        with self.assertRaises(ValueError):
            hpgl.read(p)

    def test_device_sequences_are_taken_out(self):
        self.assertEqual(hpgl._unwrap('\x1b.YIN;\x1b.@10;2:PU;\x1b.)'), 'IN;PU;')

    def test_in_right_after_a_device_sequence(self):
        p = self.file(b'\x1b.(\x1b.I81;;17:IN;PU0,0;PD400,0;PU;\x1b.)')
        self.assertEqual(hpgl.read(p).bbox(), (0.0, 0.0, 10.0, 0.0))

    def test_text_only_file(self):
        d = hpgl.read(self.file('IN;SP2;LBabc\x03'))
        self.assertEqual(len(d.layers), 1)
        self.assertEqual(d.layers[0].name, 'Plume 2')
        self.assertIsInstance(d.layers[0].items[0], Text)

    def test_shapes_and_texts_by_pen(self):
        d = hpgl.read(self.file('SP1;PU0,0;PD40,0;PU;SP2;LBb\x03SP1;LBa\x03'))
        self.assertEqual([L.name for L in d.layers], ['Plume 1', 'Plume 2'])
        self.assertEqual(len(d.layers[0].items), 2)
        self.assertEqual(len(d.layers[1].items), 1)

    def test_the_guess_is_told(self):
        d = hpgl.read(self.file('SC0,100,0,100;PU0,0;PD40,40;PU;'))
        self.assertTrue(any('SC' in r for r in d.report))
        d = hpgl.read(self.file('IP0,0,400,400;SC0,100,0,100;PU0,0;PD40,40;PU;'))
        self.assertFalse(any('SC' in r for r in d.report))

    def test_pages_are_told(self):
        d = hpgl.read(self.file('PU0,0;PD40,0;PU;PG;PU0,0;PD40,0;PU;'))
        self.assertTrue(any('2 pages' in r for r in d.report))
        d = hpgl.read(self.file('PU0,0;PD40,0;PU;PG;'))
        self.assertFalse(any('pages' in r for r in d.report))

    def test_extensions(self):
        for ext in ('.hgl', '.gl2'):
            p = self.file('IN;PU0,0;PD400,0;PU;', 'x' + ext)
            self.assertEqual(registry.open_document(p).bbox(), (0.0, 0.0, 10.0, 0.0))

    def test_text_outline_fits_its_width(self):
        from vectordrive.core import fonts as F
        from vectordrive.core import text as TX
        if not F.is_available(hpgl.LABEL_FONT):
            self.skipTest('pas de police ici')
        d = hpgl.read(self.file('SI0.2,0.4;PA10,0;LBABCD\x03'))
        b = TX.outline_for(d.layers[0].items[0]).bbox()
        self.assertAlmostEqual(b[2] - b[0], 2.0 * 1.5 * 3 + 2.0, delta=1.0)
        self.assertAlmostEqual(b[3] - b[1], 4.0, delta=0.5)

    def test_writing_still_gives_what_is_read(self):
        from vectordrive.core.document import Document, Layer, Shape
        d = Document()
        d.layers = [Layer(name='a', items=[Shape(path=geom.Path([geom.rect(0, 0, 10, 5)]))])]
        text, _images = hpgl.write_text(d)
        self.assertEqual(box(hpgl.read_text(text)[0][1]), (0.0, 0.0, 10.0, 5.0))


if __name__ == '__main__':
    unittest.main()
