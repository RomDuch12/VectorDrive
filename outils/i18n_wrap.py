"""Enrobe les libellés visibles des modules d'interface dans `tr(...)`.

Heuristique (relue à la main après passage) : chaîne littérale simple
(pas f-string, pas docstring), qui commence par une majuscule ou contient
une espace ou un caractère accentué, hors raccourcis clavier, couleurs,
clés de réglages, noms de police et feuilles de style. Les chaînes
juxtaposées ('a' 'b') sont enrobées ensemble.

    python outils/i18n_wrap.py vectordrive/ui/main_window.py [...]
    python outils/i18n_wrap.py --extract   # liste les chaînes tr(...)
"""
from __future__ import annotations

import io
import json
import pathlib
import re
import sys
import tokenize

SKIP_CALLS = {'QKeySequence', 'setShortcut', 'setObjectName', 'QSettings', 'setStyleSheet',
              'QColor', 'QFont', 'value', 'setValue', 'startswith', 'endswith', 'tr', 'setData',
              'findData', 'get', 'replace', 'split', 'join', 'strftime', 'encode', 'decode',
              'QIcon', 'setFamily', 'icon', 'by_extension', 'pop', 'setdefault'}
SKIP_TEXT = re.compile(r'^(Ctrl|Shift|Alt|Meta|F\d+$|Del$|Esc$|Home$|End$|Return$|Ins$|PgUp|PgDown)|^#|'
                       r'^(Arial|Consolas|VectorDrive|Fusion|Segoe UI|O X Y Z|Plan \d+)$')
VISIBLE = re.compile(r'^[A-ZÀ-Ý]|[ À-ɏ…«»]')


def _literal(tok: str) -> str | None:
    m = re.match(r'^([rRuU]?)(\'\'\'|"""|\'|")', tok)
    if not m or m.group(1).lower() == 'r':
        return None
    try:
        return eval(tok)            # noqa: S307 - littéral issu de tokenize
    except Exception:
        return None


def wrap(src: str) -> tuple[str, int]:
    toks = [t for t in tokenize.generate_tokens(io.StringIO(src).readline)]
    sig = [t for t in toks if t.type not in (tokenize.NL, tokenize.COMMENT)]
    lines = src.splitlines(keepends=True)
    offs = [0]
    for ln in lines:
        offs.append(offs[-1] + len(ln))
    pos = lambda rc: offs[rc[0] - 1] + rc[1]
    edits = []
    i = 0
    while i < len(sig):
        t = sig[i]
        if t.type != tokenize.STRING:
            i += 1
            continue
        j = i
        while j + 1 < len(sig) and sig[j + 1].type == tokenize.STRING:
            j += 1
        group = sig[i:j + 1]
        prev = sig[i - 1] if i else None
        nxt = sig[j + 1] if j + 1 < len(sig) else None
        i = j + 1
        values = [_literal(g.string) for g in group]
        if any(v is None or not isinstance(v, str) for v in values):
            continue
        text = ''.join(values)
        if '\n' in text and len(text) > 200:
            continue
        # docstring / instruction isolée
        if prev is None or prev.type in (tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT):
            if nxt is None or nxt.type in (tokenize.NEWLINE, tokenize.ENDMARKER):
                continue
        if nxt is not None and nxt.string == ':' and prev is not None and prev.string in ('{', ','):
            continue                                    # clé de dictionnaire
        if nxt is not None and nxt.string in ('in', '==', '!=') or prev is not None and prev.string in ('==', '!=', 'in'):
            continue
        if prev is not None and prev.string == '[':
            continue                                    # indice
        # appel englobant
        depth, k, callee = 0, sig.index(group[0]) - 1, None
        while k >= 0:
            s = sig[k].string
            if s in (')', ']', '}'):
                depth += 1
            elif s in ('(', '[', '{'):
                if depth == 0:
                    if s == '(' and k > 0 and sig[k - 1].type == tokenize.NAME:
                        callee = sig[k - 1].string
                    break
                depth -= 1
            elif sig[k].type in (tokenize.NEWLINE,) and depth == 0:
                break
            k -= 1
        if callee in SKIP_CALLS:
            continue
        if not text.strip() or SKIP_TEXT.search(text) or not VISIBLE.search(text):
            continue
        if re.fullmatch(r'[\w./\\:*?-]+', text) and not re.match(r'^[A-ZÀ-Ý]', text):
            continue
        edits.append((pos(group[0].start), pos(group[-1].end)))
    out = src
    for a, b in reversed(edits):
        out = out[:a] + 'tr(' + out[a:b] + ')' + out[b:]
    return out, len(edits)


def extract(paths) -> list[str]:
    found = []
    for p in paths:
        src = pathlib.Path(p).read_text(encoding='utf-8')
        sig = [t for t in tokenize.generate_tokens(io.StringIO(src).readline)
               if t.type not in (tokenize.NL, tokenize.COMMENT)]
        for k in range(len(sig) - 2):
            if sig[k].string == 'tr' and sig[k + 1].string == '(' and sig[k + 2].type == tokenize.STRING:
                j = k + 2
                vals = []
                while sig[j].type == tokenize.STRING:
                    vals.append(_literal(sig[j].string))
                    j += 1
                if all(isinstance(v, str) for v in vals) and sig[j].string in (')', '.'):
                    s = ''.join(vals)
                    if s not in found:
                        found.append(s)
    return found


if __name__ == '__main__':
    root = pathlib.Path(__file__).resolve().parents[1]
    if sys.argv[1:2] == ['--extract']:
        files = sorted((root / 'vectordrive').rglob('*.py'))
        strings = extract(files)
        table = root / 'vectordrive' / 'ressources' / 'i18n' / 'en.json'
        have = json.loads(table.read_text(encoding='utf-8')) if table.exists() else {}
        missing = [s for s in strings if s not in have]
        print(json.dumps({'total': len(strings), 'manquantes': missing}, ensure_ascii=False, indent=1))
    else:
        for p in sys.argv[1:]:
            f = pathlib.Path(p)
            new, n = wrap(f.read_text(encoding='utf-8'))
            f.write_text(new, encoding='utf-8')
            print(f'{f.name}: {n} libellé(s)')
