"""Round 926 : l'onglet Mise en forme tient sur un écran de 1920 px — les petits boutons du formulaire suivent le mode
« icônes seules » du ruban, et chaque commande du formulaire a son icône."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r926.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

ROOT = pathlib.Path(__file__).resolve().parents[1]
#: l'onglet Mise en forme déborde-t-il, la fenêtre à la largeur donnée (processus à part, vraies polices) ;
#: depuis le round 1094, plus de groupe replié : il défilerait
MEASURE = r'''
import json, sys
sys.path.insert(0, sys.argv[1])
from PySide6.QtWidgets import QApplication
app = QApplication([])
from PySide6.QtGui import QFont
app.setFont(QFont('Segoe UI', 9))
from vectordrive.ui.main_window import MainWindow
w = MainWindow()
w.resize(int(sys.argv[2]), 1000)
w.show()
w.new_text(10.0, 10.0)
r = w.ribbon
i = [i for i in range(r.count()) if r.tabText(i) == w.text_tab_title][0]
r.setCurrentIndex(i)
for _ in range(5):
    app.processEvents()
r.fit_current()
app.processEvents()
folded = [] if r.page(i).sizeHint().width() <= r.widget(i).width() else ['déborde']
w.typing_tool().finish()
w.modified = False
w.close()
print(json.dumps(folded))
'''

NEW = ('case_upper', 'case_lower', 'case_words', 'case_small', 'case_initial', 'text_rtl', 'text_on_baseline',
       'text_under_baseline', 'line_fixed', 'line_prop', 'line_typo', 'text_compress_line', 'text_compress_para',
       'text_compress_global', 'find_replace', 'text_copy_format', 'text_styles', 'text_preset_save')


class TextTabFits(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.dialog = mock.patch('vectordrive.ui.dialogs.TextDialog.exec', return_value=0)
        self.dialog.start()
        self.w = MainWindow()

    def tearDown(self):
        tool = self.w.typing_tool() if hasattr(self.w, 'typing_tool') else None
        if tool is not None:
            tool.finish()
        self.w.modified = False
        self.w.close()
        self.dialog.stop()

    def show_at(self, width):
        w = self.w
        w.resize(width, 1000)
        w.show()
        w.new_text(10.0, 10.0)
        r = w.ribbon
        i = next(i for i in range(r.count()) if r.tabText(i) == w.text_tab_title)
        r.setCurrentIndex(i)
        for _ in range(5):
            app.processEvents()
        r.fit_current()
        app.processEvents()
        return r.page(i)

    def group(self, page, title):
        return next(g for g in page.groups() if g.title.text() == title)

    def test_whole_tab_on_a_1920_screen(self):
        """Mesuré dans un processus à part, avec les polices de Windows et celle de l'interface (Segoe UI 9) : le
        rendu hors écran des essais n'a pas de police, ses largeurs de libellés ne disent rien de l'écran."""
        fontdir = pathlib.Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
        if not (fontdir / 'segoeui.ttf').exists():
            self.skipTest('police de l\'interface de Windows absente')
        tmp = tempfile.mkdtemp()
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QPA_FONTDIR=str(fontdir), PYTHONIOENCODING='utf-8',
                   VECTORDRIVE_SETTINGS=os.path.join(tmp, 's.ini'), VECTORDRIVE_SESSION=os.path.join(tmp, 'se'),
                   VECTORDRIVE_CACHE=os.path.join(tmp, 'c'), VECTORDRIVE_NO_TYPEEDIT='1', VECTORDRIVE_NO_PLUGINS='1')
        for width in (1920, 1600):
            out = subprocess.run([sys.executable, '-c', MEASURE, str(ROOT), str(width)], env=env, capture_output=True,
                                 text=True, encoding='utf-8', timeout=240)
            self.assertEqual(out.returncode, 0, out.stderr[-800:])
            folded = json.loads(out.stdout.strip().splitlines()[-1])
            self.assertEqual(folded, [], width)

    def test_form_rows_follow_the_iconic_mode(self):
        page = self.show_at(1920)
        g = self.group(page, 'Position du texte')
        self.assertGreaterEqual(g.small_count(), 12)
        g.set_iconic(True)
        self.assertEqual({b.toolButtonStyle() for b in g.buttons()}, {Qt.ToolButtonStyle.ToolButtonIconOnly})
        narrow = g.expanded_width()
        g.set_iconic(False)
        self.assertEqual({b.toolButtonStyle() for b in g.buttons()}, {Qt.ToolButtonStyle.ToolButtonTextBesideIcon})
        self.assertGreater(g.expanded_width(), narrow + 200)                    # les libellés rendus

    def test_one_icon_per_command(self):
        page = self.show_at(1920)
        keys = [b.defaultAction().property('vd_icon') for g in page.groups() for b in g.buttons()]
        self.assertEqual(sorted({k for k in keys if keys.count(k) > 1}), [])
        self.assertTrue(set(NEW) <= set(keys))
        from vectordrive.ui import icons
        imgs = [icons.icon(k).pixmap(32, 32).toImage() for k in NEW]
        for k, im in zip(NEW, imgs):
            inked = sum(1 for x in range(32) for y in range(32) if im.pixelColor(x, y).alpha() > 128)
            self.assertGreater(inked, 40, k)
        for i in range(len(NEW)):
            for j in range(i + 1, len(NEW)):
                self.assertFalse(imgs[i] == imgs[j], (NEW[i], NEW[j]))


if __name__ == '__main__':
    unittest.main()
