"""Texte de droite à gauche : l'ordre d'affichage et les formes liées de l'arabe.

Le texte reste gardé dans l'ordre de la frappe ; on en tire une chaîne « visuelle », posée de gauche à droite comme
une autre. Les formes viennent des blocs de présentation d'Unicode, que portent les polices TrueType courantes :
isolée, initiale, médiane, finale (TypeEdit fait de même). Ce n'est pas un moteur de composition complet :
pas de ligatures autres que lam-alef, et l'ordre d'affichage suit une version réduite de l'algorithme d'Unicode
(paragraphe de droite à gauche, sans caractères de contrôle ni imbrications).
"""
from __future__ import annotations

import functools
import unicodedata

_LAM = 0x0644
_TATWEEL = 0x0640
_MIRROR = dict(zip('()[]{}<>«»‹›', ')(][}{><»«›‹'))


@functools.lru_cache(maxsize=1)
def _tables() -> tuple[dict, dict]:
    """Les formes, lues dans la base Unicode : {lettre : {forme : caractère}}, {(lam, alef) : {forme : caractère}}."""
    letters: dict[int, dict[str, str]] = {}
    ligatures: dict[int, dict[str, str]] = {}
    for code in [*range(0xFB50, 0xFE00), *range(0xFE70, 0xFEFD)]:
        d = unicodedata.decomposition(chr(code))
        if not d.startswith('<'):
            continue
        kind, _, rest = d[1:].partition('> ')
        parts = [int(x, 16) for x in rest.split()]
        if kind not in ('isolated', 'final', 'initial', 'medial'):
            continue
        if len(parts) == 1:
            letters.setdefault(parts[0], {}).setdefault(kind, chr(code))
        elif len(parts) == 2 and parts[0] == _LAM and kind in ('isolated', 'final'):
            ligatures.setdefault(parts[1], {}).setdefault(kind, chr(code))
    return letters, ligatures


def _is_mark(ch: str) -> bool:
    return unicodedata.category(ch) in ('Mn', 'Me')


def _joins_after(ch: str, letters: dict) -> bool:
    """La lettre peut se lier à la suivante."""
    return ord(ch) == _TATWEEL or 'initial' in letters.get(ord(ch), {})


def _joins_before(ch: str, letters: dict) -> bool:
    """La lettre peut se lier à la précédente."""
    return ord(ch) == _TATWEEL or 'final' in letters.get(ord(ch), {})


def shape(text: str, has=None) -> str:
    """Les lettres arabes de `text` (ordre de frappe) dans leurs formes liées. `has(c)` : la police a ce caractère ;
    sans la forme voulue, la lettre reste telle quelle."""
    letters, ligatures = _tables()
    ok = has or (lambda _c: True)
    n = len(text)

    def neighbour(i: int, step: int) -> str | None:
        i += step
        while 0 <= i < n and _is_mark(text[i]):
            i += step
        return text[i] if 0 <= i < n else None

    out = []
    i = 0
    while i < n:
        ch = text[i]
        forms = letters.get(ord(ch))
        if forms is None:
            out.append(ch)
            i += 1
            continue
        before = neighbour(i, -1)
        joined = before is not None and _joins_after(before, letters)
        after = neighbour(i, 1)
        if ord(ch) == _LAM and after is not None and ord(after) in ligatures:
            lig = ligatures[ord(after)].get('final' if joined else 'isolated')
            if lig and ok(lig):
                out.append(lig)
                j = i + 1
                while text[j] != after:                  # les signes posés sur le lam suivent la ligature
                    out.append(text[j])
                    j += 1
                i = j + 1
                continue
        linked = after is not None and _joins_before(after, letters) and _joins_after(ch, letters)
        if joined and linked:
            kind = 'medial'
        elif joined:
            kind = 'final'
        elif linked:
            kind = 'initial'
        else:
            kind = 'isolated'
        form = forms.get(kind)
        if form is None and kind == 'medial':
            form = forms.get('final')
        out.append(form if form and ok(form) else ch)
        i += 1
    return ''.join(out)


def _levels(line: str) -> list[int]:
    """1 pour ce qui se lit de droite à gauche, 2 pour le reste (latin, chiffres, et ce qui les relie)."""
    kinds = [unicodedata.bidirectional(c) for c in line]
    n = len(kinds)
    # séparateurs et terminateurs de nombres : pris dans le nombre
    for i, k in enumerate(kinds):
        if k in ('ES', 'CS') and 0 < i < n - 1 and kinds[i - 1] in ('EN', 'AN') and kinds[i + 1] == kinds[i - 1]:
            kinds[i] = kinds[i - 1]
    for i, k in enumerate(kinds):
        if k == 'ET' and ((i > 0 and kinds[i - 1] == 'EN') or (i < n - 1 and kinds[i + 1] == 'EN')):
            kinds[i] = 'EN'
    for i in range(n - 2, -1, -1):
        if kinds[i] == 'ET' and kinds[i + 1] == 'EN':
            kinds[i] = 'EN'
    levels = [0] * n
    for i, k in enumerate(kinds):
        if k in ('R', 'AL'):
            levels[i] = 1
        elif k in ('L', 'EN', 'AN'):
            levels[i] = 2
    # le reste : le sens de ses deux voisins s'ils s'accordent, sinon celui du paragraphe
    i = 0
    while i < n:
        if levels[i]:
            i += 1
            continue
        j = i
        while j < n and not levels[j]:
            j += 1
        left = levels[i - 1] if i > 0 else 1
        right = levels[j] if j < n else 1
        level = left if left == right else 1
        for k in range(i, j):
            levels[k] = level
        i = j
    return levels


def _clusters(line: str, levels: list[int]) -> list[tuple[str, int]]:
    """Une lettre et ses signes : ils restent ensemble, le signe après sa lettre, quel que soit le sens."""
    out: list[list] = []
    for ch, level in zip(line, levels):
        if _is_mark(ch) and out:
            out[-1][0] += ch
        else:
            out.append([ch, level])
    return [(a, b) for a, b in out]


def visual_line(line: str) -> str:
    """L'ordre d'affichage d'une ligne de droite à gauche, sans les formes."""
    if not line:
        return line
    parts = _clusters(line, _levels(line))
    # l'algorithme d'Unicode : du niveau le plus haut au plus bas, chaque suite est retournée
    runs = list(parts)
    for floor in (2, 1):
        i = 0
        while i < len(runs):
            if runs[i][1] < floor:
                i += 1
                continue
            j = i
            while j < len(runs) and runs[j][1] >= floor:
                j += 1
            runs[i:j] = runs[i:j][::-1]
            i = j
    return ''.join(_MIRROR.get(c, c) if level % 2 else c for c, level in runs)


def visual(text: str, has=None) -> str:
    """Le texte tel qu'il se pose de gauche à droite : formes liées, puis ordre d'affichage, ligne par ligne."""
    return '\n'.join(visual_line(shape(line, has)) for line in text.split('\n'))
