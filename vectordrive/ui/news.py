"""Aide > Nouveautés : les entrées de CHANGELOG.md (nouveautés publiques,
version par version) depuis la dernière version vue, montrées une fois
après une mise à jour. Le journal de développement (JOURNAL.md) reste privé."""
from __future__ import annotations

import pathlib
import re
import sys

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout

from .. import __version__
from ..i18n import tr

_HEAD = re.compile(r'^### ((?:Round \d+|v\d+\.\d+\.\d+).*)$')
_VER = re.compile(r'v(\d+)\.(\d+)\.(\d+)')


def journal_path() -> pathlib.Path | None:
    """CHANGELOG.md : à côté du paquet (sources) ou dans les ressources (exe)."""
    here = pathlib.Path(__file__).resolve().parents[1]
    for p in (here / 'ressources' / 'CHANGELOG.md', here.parent / 'CHANGELOG.md',
              pathlib.Path(getattr(sys, '_MEIPASS', here)) / 'vectordrive' / 'ressources' / 'CHANGELOG.md'):
        if p.is_file():
            return p
    return None


def version_tuple(v: str) -> tuple[int, int, int]:
    m = _VER.search(v if v.startswith('v') else 'v' + v)
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


def entries(text: str) -> list[tuple[str, tuple[int, int, int], str]]:
    """[(titre, version, corps markdown)] dans l'ordre du journal."""
    out = []
    cur = None
    for line in text.splitlines():
        m = _HEAD.match(line)
        if m:
            if cur:
                out.append(cur)
            title = m.group(1)
            cur = [title, version_tuple(title), []]
        elif line.startswith('## ') or line.startswith('# '):
            if cur:
                out.append(cur)
            cur = None
        elif cur is not None:
            cur[2].append(line)
    if cur:
        out.append(cur)
    return [(t, v, '\n'.join(body).strip()) for t, v, body in out]


def news_since(seen: str | None, text: str, limit: int = 25) -> list[tuple[str, tuple, str]]:
    """Entrées de version > `seen` (les `limit` dernières si rien n'a été vu)."""
    es = [e for e in entries(text) if e[1] > (0, 0, 0)]
    if not seen:
        return es[-limit:]
    s = version_tuple(seen)
    return [e for e in es if e[1] > s]


def markdown(es) -> str:
    return '\n\n'.join(f'### {t}\n\n{body}' for t, _v, body in reversed(es))


class NewsDialog(QDialog):
    def __init__(self, parent, es):
        super().__init__(parent)
        from .fit import no_hscroll
        no_hscroll(self)                                 # pas de défilement horizontal à l'ouverture
        self.setWindowTitle(tr('Nouveautés de VectorDrive {0}').format(__version__))
        lay = QVBoxLayout(self)
        view = QTextBrowser()
        view.setOpenExternalLinks(False)
        view.setMarkdown(markdown(es) or tr('Rien de nouveau.'))
        lay.addWidget(view)
        bb = QDialogButtonBox()
        bb.addButton(tr('Fermer'), QDialogButtonBox.ButtonRole.RejectRole)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.resize(760, 640)
