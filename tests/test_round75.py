"""Round 75 : Aide > Nouveautés."""
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.ui import news

SAMPLE = """# Journal

## Rounds

### Round 1 (16/10) — v0.1.0 : début
- premier

### Round 2 (16/10) — v0.2.0 : suite
- deuxième
  sur deux lignes

### Round 3 (16/10) — v0.10.0 : plus tard
- troisième
"""


class TestNews(unittest.TestCase):
    def test_parse_and_filter(self):
        es = news.entries(SAMPLE)
        self.assertEqual([e[1] for e in es], [(0, 1, 0), (0, 2, 0), (0, 10, 0)])
        self.assertIn('sur deux lignes', es[1][2])
        self.assertEqual([e[1] for e in news.news_since('0.2.0', SAMPLE)], [(0, 10, 0)])   # 10 > 2 (numérique)
        self.assertEqual(len(news.news_since(None, SAMPLE, limit=2)), 2)
        md = news.markdown(news.news_since('0.1.0', SAMPLE))
        self.assertLess(md.index('Round 3'), md.index('Round 2'))                          # le plus récent d'abord

    def test_real_journal(self):
        jp = news.journal_path()
        self.assertIsNotNone(jp)
        from vectordrive import __version__
        es = news.entries(jp.read_text(encoding='utf-8'))
        self.assertEqual(max(e[1] for e in es), news.version_tuple(__version__))         # journal à jour


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_dialog_and_no_auto_popup(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w._auto_news()                                       # hors écran / tests : rien
            self.assertEqual(w.settings.value('nouveautes/vu', ''), '')
            w.show_news('0.60.0')
            dlgs = [c for c in w.children() if isinstance(c, news.NewsDialog)]
            self.assertEqual(len(dlgs), 1)
            dlgs[0].close()
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
