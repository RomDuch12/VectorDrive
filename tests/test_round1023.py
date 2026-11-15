"""Round 1023 : demande du 15/11 — « tous les formulaires fao et autres : les champs ne fonctionnent pas avec fleches
incrémentales ». Une case plus large que sa colonne était coupée à droite : les flèches de ses champs ne recevaient
plus le clic."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1023.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import (QAbstractSpinBox, QApplication, QDoubleSpinBox, QFormLayout, QGroupBox,  # noqa: E402
                               QHBoxLayout, QLabel, QStyle, QStyleOptionSpinBox, QWidget)

app = QApplication.instance() or QApplication([])

from vectordrive.cam import model  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Shape  # noqa: E402
from vectordrive.ui import cam_panel as CP  # noqa: E402
from vectordrive.ui import fit, tiles  # noqa: E402

WIDE_SCREEN = mock.patch.object(tiles, 'screen_width', lambda _w: 1920, create=True)


def up_rect(sb):
    opt = QStyleOptionSpinBox()
    sb.initStyleOption(opt)
    return sb.style().subControlRect(QStyle.ComplexControl.CC_SpinBox, opt, QStyle.SubControl.SC_SpinBoxUp, sb)


def arrow_in_its_column(sb, board) -> bool:
    """La flèche du haut entière tient-elle dans la largeur visible de sa colonne ?"""
    r = up_rect(sb)
    sa = next(s for s in board.scrolls if s.isAncestorOf(sb))
    vp = sa.viewport()
    left = sb.mapTo(vp, r.topLeft()).x()
    right = sb.mapTo(vp, r.topRight()).x()
    return r.isValid() and r.width() > 0 and left >= 0 and right < vp.width()


def case(name, width):
    g = QGroupBox(name)
    f = QFormLayout(g)
    sb = QDoubleSpinBox()
    sb.setMinimumWidth(width)
    f.addRow(QLabel(name), sb)
    return g, sb


def form(a_width, b_width):
    a, sa = case('A', a_width)
    b, sb = case('B', b_width)
    host = QWidget()
    lay = QHBoxLayout(host)
    board = tiles.TileBoard({'A': a, 'B': b}, columns=2)
    lay.addWidget(board, 1)
    cover = QLabel('schéma')
    cover.setMinimumWidth(260)
    lay.addWidget(cover)                                                      # comme le schéma du formulaire
    host.resize(500, 400)
    return host, board, sa, sb


class ColumnsKeepTheirCases(unittest.TestCase):

    def test_a_wide_case_is_not_cut(self):
        with WIDE_SCREEN:
            host, board, sa, sb = form(120, 520)                              # B plus large que sa part
            self.addCleanup(host.deleteLater)
            host.show()
            QTest.qWait(30)
            self.assertGreaterEqual(board.scrolls[1].minimumSizeHint().width(), 520)
            self.assertGreaterEqual(host.width(), 120 + 520 + 260)           # avant : la fenêtre gardait 500 px
            for s in (sa, sb):
                self.assertTrue(arrow_in_its_column(s, board), s.minimumWidth())   # avant : la flèche de B coupée
            self.assertFalse(board.scrolls[1].horizontalScrollBar().isVisible())

    def test_small_screen_scrolls_instead_of_cutting(self):
        with mock.patch.object(tiles, 'screen_width', lambda _w: 900, create=True):
            host, board, sa, sb = form(120, 700)
            self.addCleanup(host.deleteLater)
            host.show()
            QTest.qWait(30)
            col = board.scrolls[1]
            self.assertLessEqual(col.minimumSizeHint().width(), (900 - 360) // 2)   # sa part de l'écran
            self.assertLess(host.width(), 900 + 120)
            bar = col.horizontalScrollBar()
            self.assertTrue(bar.isVisible() and bar.maximum() > 0)            # avant : coupé, sans barre
            bar.setValue(bar.maximum())
            QTest.qWait(10)
            self.assertTrue(arrow_in_its_column(sb, board))                   # la flèche s'atteint en défilant

    def test_follows_a_case_that_grows(self):
        with WIDE_SCREEN:
            a, sa = case('A', 120)
            board = tiles.TileBoard({'A': a}, columns=1)
            board.show()
            self.addCleanup(board.deleteLater)
            QTest.qWait(20)
            sa.setMinimumWidth(480)                                           # un champ élargi (texte plus long)
            QTest.qWait(30)
            self.assertGreaterEqual(board.width(), 480)                       # la colonne a suivi
            self.assertTrue(arrow_in_its_column(sa, board))

    def test_vscroll_follows_its_content(self):
        inner = QWidget()
        lay = QFormLayout(inner)
        sb = QDoubleSpinBox()
        lay.addRow('x', sb)
        host = QWidget()
        h = QHBoxLayout(host)
        v = fit.VScroll(inner)
        h.addWidget(v)
        host.show()
        self.addCleanup(host.deleteLater)
        QTest.qWait(20)
        sb.setMinimumWidth(600)                                               # le contenu s'élargit après coup
        QTest.qWait(30)
        self.assertGreaterEqual(v.viewport().width(), 600)                    # avant : coupé à droite


class OperationForm(unittest.TestCase):

    def test_arrows_of_both_feed_frames_reachable(self):
        d = Document()
        d.add(Shape(path=geom.Path([geom.rect(0, 0, 30, 20)]), tool=0))
        lib = [model.CamTool(name='F3', kind='fraise', diameter=3.0, number=1, feed=800.0, finish_feed=400.0)]
        op = model.Operation(kind=CP.presets()['gravure'][1], sources=[0], depth=1.0, tool_id=lib[0].id)
        with mock.patch.object(tiles, 'screen_width', lambda _w: 4000, create=True):   # hors écran, les libellés
            dlg = CP.FieldsDialog(None, 'Op', op, d, list(lib), library=lib, preset='gravure')   # sont plus larges
            self.addCleanup(dlg.deleteLater)
            for n in ('finish_feed', 'feed'):
                dlg.widgets[n].setMinimumWidth(330)                           # Ébauche et Finition côte à côte, larges
            dlg.resize(700, 600)
            dlg.show()
            QTest.qWait(50)
            cut = [n for n, w in dlg.widgets.items()
                   if isinstance(w, QAbstractSpinBox) and w.isVisibleTo(dlg) and dlg.board.isAncestorOf(w)
                   and w.buttonSymbols() != QAbstractSpinBox.ButtonSymbols.NoButtons
                   and not arrow_in_its_column(w, dlg.board)]
            self.assertEqual(cut, [])                                         # avant : les vitesses coupées


if __name__ == '__main__':
    unittest.main()
