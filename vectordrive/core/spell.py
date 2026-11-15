"""Orthographe : le correcteur de Windows (API Spell Checking, Windows 8 et suivants). Aucun dictionnaire à fournir : ceux de
la langue du poste servent, et les mots ajoutés dans Windows sont connus. Ailleurs, ou sans dictionnaire pour la langue,
`available` rend False et la commande le dit.

Interfaces COM appelées à la main (ctypes), pour ne dépendre de rien :
ISpellCheckerFactory, ISpellChecker, IEnumSpellingError, ISpellingError, IEnumString."""
from __future__ import annotations

import ctypes
import re
import sys
import unicodedata
from dataclasses import dataclass, field

_CLSID_FACTORY = '{7AB36653-1796-484B-BDFA-E74F1DB7C1DC}'
_IID_FACTORY = '{8E018A9D-2415-4677-BF08-794EA61F94BB}'
_S_OK = 0
_MAX_SUGGESTIONS = 8
#: Actions correctives de ISpellingError
_ACT_GET_SUGGESTIONS, _ACT_REPLACE, _ACT_DELETE = 1, 2, 3


@dataclass
class Fault:
    """Un mot à revoir dans un texte."""
    start: int
    length: int
    word: str
    suggestions: list[str] = field(default_factory=list)


class _GUID(ctypes.Structure):
    _fields_ = [('a', ctypes.c_ulong), ('b', ctypes.c_ushort), ('c', ctypes.c_ushort), ('d', ctypes.c_ubyte * 8)]

    @classmethod
    def parse(cls, text: str) -> '_GUID':
        h = text.strip('{}').replace('-', '')
        return cls(int(h[:8], 16), int(h[8:12], 16), int(h[12:16], 16), (ctypes.c_ubyte * 8)(*bytes.fromhex(h[16:])))


def _method(obj, index: int, restype, *argtypes):
    """Méthode n° `index` de la table de l'objet COM `obj`, prête à appeler."""
    vtable = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    proto = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)
    fn = proto(vtable[index])
    return lambda *a: fn(obj, *a)


def _release(obj) -> None:
    if obj:
        _method(obj, 2, ctypes.c_ulong)()


def _take_wstr(p: int | None) -> str:
    """Chaîne allouée par COM : lue, puis rendue."""
    if not p:
        return ''
    try:
        return ctypes.wstring_at(p)
    finally:
        ctypes.WINFUNCTYPE(None, ctypes.c_void_p)(('CoTaskMemFree', ctypes.windll.ole32))(p)


class Checker:
    """Un correcteur pour une langue ('fr-FR'). Utiliser `open_checker`."""

    def __init__(self, ptr, lang: str):
        self._ptr = ptr
        self.lang = lang

    def close(self) -> None:
        _release(self._ptr)
        self._ptr = None

    def suggest(self, word: str) -> list[str]:
        en = ctypes.c_void_p()
        hr = _method(self._ptr, 5, ctypes.c_long, ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_void_p))(word, ctypes.byref(en))
        if hr < 0 or not en:
            return []
        out = []
        try:
            nxt = _method(en, 3, ctypes.c_long, ctypes.c_ulong, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_ulong))
            while len(out) < _MAX_SUGGESTIONS:
                item, got = ctypes.c_void_p(), ctypes.c_ulong(0)
                if nxt(1, ctypes.byref(item), ctypes.byref(got)) != _S_OK or not got.value:
                    break
                s = _take_wstr(item.value)
                if s and s != word:
                    out.append(s)
        finally:
            _release(en)
        return out

    def check(self, text: str) -> list[Fault]:
        """Mots à revoir de `text` ; les positions comptent en unités UTF-16, comme l'API."""
        if not text.strip():
            return []
        en = ctypes.c_void_p()
        hr = _method(self._ptr, 4, ctypes.c_long, ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_void_p))(text, ctypes.byref(en))
        if hr < 0 or not en:
            return []
        wide = text.encode('utf-16-le', 'surrogatepass')
        faults = []
        try:
            nxt = _method(en, 3, ctypes.c_long, ctypes.POINTER(ctypes.c_void_p))
            while True:
                err = ctypes.c_void_p()
                if nxt(ctypes.byref(err)) != _S_OK or not err:
                    break
                try:
                    start, length, action = ctypes.c_ulong(), ctypes.c_ulong(), ctypes.c_int()
                    _method(err, 3, ctypes.c_long, ctypes.POINTER(ctypes.c_ulong))(ctypes.byref(start))
                    _method(err, 4, ctypes.c_long, ctypes.POINTER(ctypes.c_ulong))(ctypes.byref(length))
                    _method(err, 5, ctypes.c_long, ctypes.POINTER(ctypes.c_int))(ctypes.byref(action))
                    word = wide[2 * start.value:2 * (start.value + length.value)].decode('utf-16-le', 'replace')
                    if action.value == _ACT_REPLACE:
                        rep = ctypes.c_void_p()
                        _method(err, 6, ctypes.c_long, ctypes.POINTER(ctypes.c_void_p))(ctypes.byref(rep))
                        sug = [_take_wstr(rep.value)]
                    elif action.value == _ACT_DELETE:
                        sug = ['']                         # mot répété : à retirer
                    else:
                        sug = self.suggest(word)
                    faults.append(Fault(_char_index(text, start.value), len(word), word, [s for s in sug if s != word]))
                finally:
                    _release(err)
        finally:
            _release(en)
        return faults


def _char_index(text: str, unit: int) -> int:
    """Position en caractères d'une position en unités UTF-16."""
    if text.isascii():
        return unit
    n = 0
    for i, ch in enumerate(text):
        if n >= unit:
            return i
        n += 2 if ord(ch) > 0xFFFF else 1
    return len(text)


def _factory():
    if sys.platform != 'win32':
        return None
    ole32 = ctypes.windll.ole32
    ole32.CoInitializeEx(None, 2)                        # COINIT_APARTMENTTHREADED ; déjà fait par Qt : sans effet
    clsid, iid = _GUID.parse(_CLSID_FACTORY), _GUID.parse(_IID_FACTORY)
    ptr = ctypes.c_void_p()
    hr = ole32.CoCreateInstance(ctypes.byref(clsid), None, 1 | 4, ctypes.byref(iid), ctypes.byref(ptr))
    return ptr.value if hr >= 0 and ptr else None


def open_checker(lang: str) -> Checker | None:
    """Correcteur pour la langue, None s'il n'y en a pas sur ce poste."""
    try:
        f = _factory()
    except OSError:
        return None
    if not f:
        return None
    try:
        ok = ctypes.c_int(0)
        hr = _method(f, 4, ctypes.c_long, ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int))(lang, ctypes.byref(ok))
        if hr < 0 or not ok.value:
            return None
        c = ctypes.c_void_p()
        hr = _method(f, 5, ctypes.c_long, ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_void_p))(lang, ctypes.byref(c))
        return Checker(c.value, lang) if hr >= 0 and c else None
    finally:
        _release(f)


def available(lang: str = 'fr-FR') -> bool:
    c = open_checker(lang)
    if c is None:
        return False
    c.close()
    return True


#: `{variable}`, codes et numéros de série : rien à corriger là-dedans
_SKIP = re.compile(r'\{[^{}]*\}|\b[\w.+-]*\d[\w.+-]*\b')


def _bare(word: str) -> str:
    """Le mot sans accents, en majuscules : ce qu'on grave souvent sur une plaque."""
    return ''.join(ch for ch in unicodedata.normalize('NFD', word) if not unicodedata.combining(ch)).upper()


def _lower_capitals(text: str) -> str:
    """Les mots tout en majuscules, en minuscules : Windows ne relit pas les majuscules. Même longueur, ou rien."""
    def low(m):
        w = m.group(0)
        return w.lower() if w.isupper() and len(w) > 1 and len(w.lower()) == len(w) else w
    return re.sub(r'[^\W\d_]+', low, text)


def faults_of(checker: Checker, text: str, *, ignore: set | None = None) -> list[Fault]:
    """Mots à revoir d'un texte gravé : ni les variables, ni ce qui porte un chiffre, ni les mots écartés. Les majuscules
    sont relues aussi ; un mot qui n'a que ses accents en moins n'est pas une faute."""
    protected = [m.span() for m in _SKIP.finditer(text)]
    out = []
    for f in checker.check(_lower_capitals(text)):
        word = text[f.start:f.start + f.length]
        if ignore and word.casefold() in ignore:
            continue
        if any(a < f.start + f.length and f.start < b for a, b in protected):
            continue
        sug = f.suggestions
        if word.isupper():
            if any(s and _bare(s) == word for s in sug):
                continue
            sug = [s.upper() for s in sug]
        out.append(Fault(f.start, f.length, word, sug))
    return out


def replaced(text: str, fault: Fault, by: str) -> str:
    """Le texte, le mot remplacé. Un mot répété retiré emporte l'espace qui le précède."""
    start = fault.start
    if not by and start > 0 and text[start - 1] == ' ':
        start -= 1
    return text[:start] + by + text[fault.start + fault.length:]
