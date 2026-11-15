"""Opérations sur le contenu des textes : casse (majuscules, minuscules,
première lettre), rechercher et remplacer, ponctuation typographique."""
from __future__ import annotations

import re

CASES = ('majuscules', 'minuscules', 'mots', 'phrase')


def change_case(s: str, mode: str) -> str:
    """majuscules : TOUT ; minuscules : tout ; mots : Chaque Mot ; phrase :
    Première lettre de chaque ligne. Accents gardés (é → É)."""
    if mode == 'majuscules':
        return s.upper()
    if mode == 'minuscules':
        return s.lower()
    if mode == 'mots':
        return re.sub(r"[^\W\d_]+(?:['’][^\W\d_]+)*", lambda m: m.group(0)[:1].upper() + m.group(0)[1:].lower(), s)
    if mode == 'phrase':
        out = []
        for line in s.split('\n'):
            low = line.lower()
            m = re.search(r'[^\W\d_]', low)
            out.append(low if not m else low[:m.start()] + low[m.start()].upper() + low[m.start() + 1:])
        return '\n'.join(out)
    raise ValueError(f'casse inconnue : {mode}')


def find_replace(s: str, find: str, repl: str, *, case: bool = False, whole: bool = False) -> tuple[str, int]:
    """(texte remplacé, nombre de remplacements). `case` : respecter la
    casse ; `whole` : mots entiers seulement."""
    if not find:
        return s, 0
    pat = re.escape(find)
    if whole:
        pat = rf'(?<!\w){pat}(?!\w)'
    rx = re.compile(pat, 0 if case else re.IGNORECASE)
    return rx.subn(lambda m: repl, s)


#: espace insécable (présente dans toutes les polices, à la différence de la fine U+202F)
NBSP = '\u00a0'


def sizes_of(texts: list) -> list[float]:
    """Les tailles de ces textes, sans doublon, dans l'ordre où on les trouve."""
    out: list[float] = []
    for t in texts:
        v = round(float(t.size), 3)
        if v not in out:
            out.append(v)
    return out


def fonts_of(texts: list) -> list[str]:
    """Les polices de ces textes, sans doublon, dans l'ordre où on les trouve."""
    out: list[str] = []
    for t in texts:
        if t.font not in out:
            out.append(t.font)
    return out


def typographic(s: str) -> str:
    """Ponctuation typographique française : guillemets droits « … »
    (espaces insécables à l'intérieur), apostrophe ’, points de suspension
    …, tiret — pour « -- », espace insécable avant ; : ! ? et après « ,
    avant ». Déjà typographique : inchangé."""
    s = s.replace('...', '\u2026').replace('--', '\u2014')
    s = re.sub(r"(?<=\w)'(?=\w)|(?<=\w)'(?=\s|$)", '\u2019', s)          # apostrophe
    out, opened = [], False
    for ch in s:                                                       # guillemets droits par paires
        if ch == '"':
            out.append('\u00ab' + NBSP if not opened else NBSP + '\u00bb')
            opened = not opened
        else:
            out.append(ch)
    s = ''.join(out)
    s = re.sub(r'\u00ab[ \u00a0]*', '\u00ab' + NBSP, s)                 # une seule espace insécable
    s = re.sub(r'[ \u00a0]*\u00bb', NBSP + '\u00bb', s)
    # avant la ponctuation haute, quand elle termine un mot (pas « 10:30 », ni « !! » coupé)
    s = re.sub(r'(?<=[^\s;:!?])[ \u00a0]*([;:!?]+)(?=\s|$)', NBSP + r'\1', s)
    s = re.sub('(\u00ab' + NBSP + ')' + NBSP + '+', r'\1', s)
    return s
