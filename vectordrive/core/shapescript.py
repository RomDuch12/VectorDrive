"""Scripts de forme : un sous-ensemble de VBScript qui dessine, comme les scripts de TypeEdit.

Le langage (Dim, If, For, While, Do, Select Case, Function, Sub, tableaux, opérateurs, fonctions
usuelles) est interprété ici, sans passer par Python ni par le système : un script ne peut ni lire
ni écrire de fichier, ni lancer quoi que ce soit, et un nombre de pas limite les boucles sans fin.

Les fonctions de dessin sont celles documentées dans le manuel de TypeEdit : NewCurve, MoveTo, LineTo,
ArcHTo, ArcTTo, ClosePath (coordonnées en mètres), InputScriptBox, ShowValue, DbApi (paramètres gardés
d'une fois à l'autre), WndScriptApi (boîte de paramètres), GetAppParameter, CreatUnicReeditableObject
(objet qu'on rouvre pour changer ses paramètres). `VbScriptInclude Nom` reprend un autre script du même dossier.
"""
from __future__ import annotations

import itertools
import json
import math
import os
import pathlib
import random
import re
import sys
from dataclasses import dataclass, field

from .geom import Contour, Line, arc as geom_arc

MAX_STEPS = 5_000_000
MAX_INCLUDES = 32
MAX_ARRAY = 2_000_000
MAX_TEXT = 1_000_000
MAX_SEGMENTS = 2_000_000
MAX_DEPTH = 4000
EXTENSIONS = ('.txt', '.sme', '.vbs')


class ScriptError(Exception):
    """Erreur dans un script : `line` est son numéro de ligne (0 : inconnu), `key` et `arg` le message."""

    def __init__(self, key: str, arg: str = '', line: int = 0):
        super().__init__(f'{key} {arg} (ligne {line})')
        self.key, self.arg, self.line = key, arg, line
        self.file = ''                                   # le script repris par VbScriptInclude où est l'erreur


# --- découpe en mots --------------------------------------------------------------------------
_TOKEN = re.compile(r"""
    (?P<space>[ \t\f]+)
  | (?P<cont>_[ \t]*\r?\n)
  | (?P<nl>\r?\n|:)
  | (?P<comment>'[^\n]*)
  | (?P<number>\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?|&[hH][0-9a-fA-F]+)
  | (?P<string>"(?:[^"\n]|"")*")
  | (?P<name>[A-Za-z_][A-Za-z_0-9]*)
  | (?P<op><>|<=|>=|=<|=>|[-+*/\\^&=<>(),.])
""", re.X)


@dataclass
class _Tok:
    kind: str
    value: object
    line: int


def _tokens(text: str) -> list[_Tok]:
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    out: list[_Tok] = []
    pos, line = 0, 1
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if m is None:
            raise ScriptError('syntax', text[pos:pos + 20].split('\n')[0], line)
        kind, s = m.lastgroup, m.group()
        pos = m.end()
        if kind == 'space':
            continue
        if kind == 'cont':
            line += 1
            continue
        if kind == 'comment':
            continue
        if kind == 'nl':
            out.append(_Tok('nl', s, line))
            if s != ':':
                line += 1
            continue
        if kind == 'number':
            value = float(int(s[2:], 16)) if s[0] == '&' else float(s)
            out.append(_Tok('number', value, line))
        elif kind == 'string':
            out.append(_Tok('string', s[1:-1].replace('""', '"'), line))
        elif kind == 'name':
            low = s.lower()
            if low == 'rem':                             # commentaire jusqu'au bout de la ligne
                end = text.find('\n', pos)
                pos = len(text) if end < 0 else end
                continue
            out.append(_Tok('name', low, line))
            out[-1].raw = s                              # le nom tel qu'écrit (messages)
        else:
            out.append(_Tok('op', {'=<': '<=', '=>': '>='}.get(s, s), line))
    out.append(_Tok('nl', '\n', line))
    out.append(_Tok('end', None, line))
    return out


# --- lecture : le texte devient un arbre (tuples) -------------------------------------------------
_BLOCK_END = {'end', 'else', 'elseif', 'next', 'wend', 'loop', 'case'}
_RESERVED = {'if', 'then', 'else', 'elseif', 'end', 'for', 'to', 'next', 'while', 'wend', 'do', 'loop', 'until',
             'dim', 'redim', 'const', 'set', 'function', 'sub', 'exit', 'call', 'select', 'case', 'and', 'or', 'not',
             'xor', 'mod', 'true', 'false', 'empty', 'null', 'nothing'}


class _Parser:
    def __init__(self, toks: list[_Tok]):
        self.t = toks
        self.i = 0

    @property
    def cur(self) -> _Tok:
        return self.t[self.i]

    def _next(self) -> _Tok:
        tok = self.t[self.i]
        self.i += 1
        return tok

    def _is(self, *words) -> bool:
        return self.cur.kind == 'name' and self.cur.value in words

    def _op(self, *ops) -> bool:
        return self.cur.kind == 'op' and self.cur.value in ops

    def _fail(self):
        tok = self.cur
        raise ScriptError('syntax', str(getattr(tok, 'raw', tok.value)), tok.line)

    def _expect_word(self, word: str) -> None:
        if not self._is(word):
            self._fail()
        self.i += 1

    def _expect_op(self, op: str) -> None:
        if not self._op(op):
            self._fail()
        self.i += 1

    def _skip_nl(self) -> None:
        while self.cur.kind == 'nl':
            self.i += 1

    def _end_of_statement(self) -> None:
        if self.cur.kind not in ('nl', 'end') and not self._is('else', 'elseif'):
            self._fail()

    def _name(self) -> str:
        if self.cur.kind != 'name':
            self._fail()
        return self._next().value

    def program(self) -> list:
        body = self.block()
        if self.cur.kind != 'end':
            self._fail()
        return body

    def block(self) -> list:
        out = []
        while True:
            self._skip_nl()
            if self.cur.kind == 'end' or (self.cur.kind == 'name' and self.cur.value in _BLOCK_END):
                return out
            st = self.statement()
            if st is not None:
                out.append(st)

    def statement(self):
        tok = self.cur
        line = tok.line
        if tok.kind != 'name':
            self._fail()
        w = tok.value
        if w in ('public', 'private') and self.t[self.i + 1].kind == 'name':
            self.i += 1
            return self.statement() if self.cur.value in ('function', 'sub', 'const', 'dim') else self._dim(line)
        if w == 'dim':
            self.i += 1
            return self._dim(line)
        if w == 'redim':
            self.i += 1
            keep = self._is('preserve') and self.t[self.i + 1].kind == 'name'
            if keep:
                self.i += 1
            return self._dim(line, redim='garde' if keep else 'vide')
        if w == 'const':
            self.i += 1
            pairs = []
            while True:
                n = self._name()
                self._expect_op('=')
                pairs.append((n, self.expr()))
                if not self._op(','):
                    break
                self.i += 1
            return ('const', line, pairs)
        if w == 'if':
            return self._if(line)
        if w == 'for':
            return self._for(line)
        if w == 'while':
            self.i += 1
            cond = self.expr()
            body = self.block()
            self._expect_word('wend')
            return ('while', line, cond, body)
        if w == 'do':
            return self._do(line)
        if w == 'select':
            return self._select(line)
        if w in ('function', 'sub'):
            return self._function(line)
        if w == 'exit':
            self.i += 1
            return ('exit', line, self._name())
        following = self.t[self.i + 1]
        if (w == 'on' and following.value == 'error') or (w == 'option' and following.value == 'explicit'):
            # On Error … : une erreur arrête toujours le script ; Option Explicit : rien à faire
            while self.cur.kind not in ('nl', 'end'):
                self.i += 1
            return None
        if w == 'call':
            self.i += 1
            target = self._postfix(self._primary())
            return ('call', line, target)
        if w == 'set':
            self.i += 1
        if w == 'vbscriptinclude':
            self.i += 1
            parts = []
            while self.cur.kind not in ('nl', 'end'):
                parts.append(str(getattr(self.cur, 'raw', self.cur.value)))
                self.i += 1
            return ('include', line, ''.join(parts).strip().strip('"'))
        return self._simple(line)

    def _dim(self, line: int, redim: str = ''):
        out = []
        while True:
            n = self._name()
            size = None
            if self._op('('):
                self.i += 1
                size = []
                while not self._op(')'):
                    size.append(self.expr())
                    if self._op(','):
                        self.i += 1
                self.i += 1
            out.append((n, size))
            if not self._op(','):
                break
            self.i += 1
        return ('dim', line, out, redim)

    def _simple(self, line: int):
        """Une affectation, ou l'appel d'une fonction sans parenthèses."""
        start = self.i
        target = self._postfix(self._primary(), stop_args=True)
        if self._op('='):
            self.i += 1
            return ('assign', line, target, self.expr())
        if self.cur.kind in ('nl', 'end') or self._is('else', 'elseif'):
            return ('call', line, target)
        # des arguments sans parenthèses : le nom seul, puis la liste
        self.i = start
        target = self._dotted()
        args = [None if self._op(',') else self.expr()]
        while self._op(','):
            self.i += 1
            args.append(self.expr())
        self._end_of_statement()
        return ('call', line, ('apply', target, args))

    def _dotted(self):
        tok = self.cur
        if tok.kind != 'name' or tok.value in _RESERVED:
            self._fail()
        self.i += 1
        node = ('var', tok.value, tok.line, getattr(tok, 'raw', tok.value))
        while self._op('.'):
            self.i += 1
            node = ('member', node, self._name(), tok.line)
        return node

    def _if(self, line: int):
        self._expect_word('if')
        cond = self.expr()
        self._expect_word('then')
        if self.cur.kind != 'nl':                        # sur une seule ligne
            then = self._inline()
            other = []
            if self._is('else'):
                self.i += 1
                other = self._inline()
            if self._is('end'):                          # « If a Then b End If » : toléré
                self.i += 1
                self._expect_word('if')
            return ('if', line, [(cond, then)], other)
        arms = [(cond, self.block())]
        other: list = []
        while True:
            if self._is('elseif'):
                self.i += 1
                c = self.expr()
                self._expect_word('then')
                arms.append((c, self.block()))
            elif self._is('else'):
                self.i += 1
                other = self.block()
            else:
                break
        self._expect_word('end')
        self._expect_word('if')
        return ('if', line, arms, other)

    def _inline(self) -> list:
        """Les instructions d'un If écrit sur une ligne, séparées par des deux-points."""
        out = []
        while True:
            st = self.statement()
            if st is not None:
                out.append(st)
            if self.cur.kind == 'nl' and self.cur.value == ':' and self.t[self.i + 1].kind not in ('nl', 'end'):
                self.i += 1
                continue
            return out

    def _for(self, line: int):
        self._expect_word('for')
        if self._is('each'):
            self._fail()
        var = self._name()
        self._expect_op('=')
        first = self.expr()
        self._expect_word('to')
        last = self.expr()
        step = None
        if self._is('step'):
            self.i += 1
            step = self.expr()
        body = self.block()
        self._expect_word('next')
        if self.cur.kind == 'name':
            self.i += 1
        return ('for', line, var, first, last, step, body)

    def _do(self, line: int):
        self._expect_word('do')
        pre = None
        if self._is('while', 'until'):
            pre = (self._next().value, self.expr())
        body = self.block()
        self._expect_word('loop')
        post = None
        if self._is('while', 'until'):
            post = (self._next().value, self.expr())
        return ('do', line, pre, post, body)

    def _select(self, line: int):
        self._expect_word('select')
        self._expect_word('case')
        subject = self.expr()
        self._skip_nl()
        arms, other = [], []
        while self._is('case'):
            self.i += 1
            if self._is('else'):
                self.i += 1
                other = self.block()
                continue
            values = [self.expr()]
            while self._op(','):
                self.i += 1
                values.append(self.expr())
            arms.append((values, self.block()))
        self._expect_word('end')
        self._expect_word('select')
        return ('select', line, subject, arms, other)

    def _function(self, line: int):
        kind = self._next().value
        name = self._name()
        params = []
        if self._op('('):
            self.i += 1
            while not self._op(')'):
                by_value = self._is('byval')
                if by_value or self._is('byref'):
                    self.i += 1
                params.append((self._name(), by_value))
                if self._op('('):                        # a()
                    self.i += 1
                    self._expect_op(')')
                if self._op(','):
                    self.i += 1
            self.i += 1
        body = self.block()
        self._expect_word('end')
        self._expect_word(kind)
        return ('function', line, name, params, body)

    # expressions, de la priorité la plus faible à la plus forte
    def expr(self):
        return self._or()

    def _or(self):
        node = self._or_only()
        while self._is('xor'):
            self.i += 1
            node = ('bin', 'xor', node, self._or_only(), self.cur.line)
        return node

    def _or_only(self):
        node = self._and()
        while self._is('or'):
            self.i += 1
            node = ('bin', 'or', node, self._and(), self.cur.line)
        return node

    def _and(self):
        node = self._not()
        while self._is('and'):
            self.i += 1
            node = ('bin', 'and', node, self._not(), self.cur.line)
        return node

    def _not(self):
        if self._is('not'):
            self.i += 1
            return ('not', self._not())
        return self._compare()

    def _compare(self):
        node = self._concat()
        while self._op('=', '<>', '<', '>', '<=', '>='):
            op = self._next().value
            node = ('bin', op, node, self._concat(), self.cur.line)
        return node

    def _concat(self):
        node = self._add()
        while self._op('&'):
            self.i += 1
            node = ('bin', '&', node, self._add(), self.cur.line)
        return node

    def _add(self):
        node = self._mod()
        while self._op('+', '-'):
            op = self._next().value
            node = ('bin', op, node, self._mod(), self.cur.line)
        return node

    def _mod(self):
        node = self._int_div()
        while self._is('mod'):
            self.i += 1
            node = ('bin', 'mod', node, self._int_div(), self.cur.line)
        return node

    def _int_div(self):
        node = self._mul()
        while self._op('\\'):
            self.i += 1
            node = ('bin', '\\', node, self._mul(), self.cur.line)
        return node

    def _mul(self):
        node = self._unary()
        while self._op('*', '/'):
            op = self._next().value
            node = ('bin', op, node, self._unary(), self.cur.line)
        return node

    def _unary(self):
        if self._op('-'):
            self.i += 1
            return ('neg', self._unary())
        if self._op('+'):
            self.i += 1
            return self._unary()
        return self._power()

    def _power(self):
        node = self._postfix(self._primary())
        while self._op('^'):                             # de gauche à droite : 2^3^2 = 64
            self.i += 1
            negative = False
            while self._op('-', '+'):
                negative ^= self._next().value == '-'
            right = self._postfix(self._primary())
            node = ('bin', '^', node, ('neg', right) if negative else right, self.cur.line)
        return node

    def _primary(self):
        tok = self.cur
        if tok.kind == 'number' or tok.kind == 'string':
            self.i += 1
            return ('lit', tok.value)
        if self._op('('):
            self.i += 1
            node = self.expr()
            self._expect_op(')')
            return node
        if tok.kind == 'name':
            if tok.value == 'true':
                self.i += 1
                return ('lit', -1.0)
            if tok.value == 'false':
                self.i += 1
                return ('lit', 0.0)
            if tok.value in ('empty', 'null', 'nothing'):
                self.i += 1
                return ('lit', None)
            if tok.value in _RESERVED:
                self._fail()
            self.i += 1
            return ('var', tok.value, tok.line, getattr(tok, 'raw', tok.value))
        self._fail()

    def _postfix(self, node, stop_args: bool = False):
        while True:
            if self._op('.'):
                self.i += 1
                node = ('member', node, self._name(), self.cur.line)
            elif self._op('(') and node[0] in ('var', 'member', 'apply'):
                self.i += 1
                args = []
                while not self._op(')'):
                    args.append(self.expr())
                    if self._op(','):
                        self.i += 1
                    elif not self._op(')'):
                        self._fail()
                self.i += 1
                node = ('apply', node, args)
            else:
                return node


# --- ce que produit un script ----------------------------------------------------------------------
@dataclass
class Host:
    """Ce qu'un script voit de l'application. Sans interface : boîtes de réponse d'avance (essais)."""
    params: list = field(default_factory=list)                 # GetAppParameter
    profile: dict = field(default_factory=dict)                # DbApi : {'SECTION/clé': valeur}
    ask: object = None                                         # ask(titre, défaut) -> texte ou None
    dialog: object = None                                      # dialog(titre, [(id, libellé, défaut)]) -> {id: texte} ou None
    show: object = None                                        # show(texte)
    folder: pathlib.Path | None = None                         # VbScriptInclude
    notes: list = field(default_factory=list)
    reedit: dict | None = None                                 # paramètres de l'objet rouvert (double-clic)


@dataclass
class Result:
    contours: list                                             # Contour, en mm
    reedit: dict | None = None                                 # le script a créé un objet à paramètres
    notes: list = field(default_factory=list)                  # 'html' : boîte HTML remplacée par les valeurs gardées


class _Pen:
    """Les contours dessinés, en mm (le script parle en mètres)."""

    def __init__(self):
        self.contours: list[Contour] = []
        self.segs: list = []
        self.at = None
        self.count = 0

    def flush(self, closed: bool = False) -> None:
        if self.segs:
            self.contours.append(Contour(self.segs, closed))
        self.segs = []

    def _add(self, *segs) -> None:
        self.count += len(segs)
        if self.count > MAX_SEGMENTS:
            raise ScriptError('segments')
        self.segs.extend(segs)

    @staticmethod
    def _mm(x, y) -> tuple[float, float]:
        p = (x * 1000.0, y * 1000.0)
        if not (math.isfinite(p[0]) and math.isfinite(p[1])):
            raise ScriptError('value', 'x, y')
        return p

    def new_curve(self) -> float:
        self.flush()
        return -1.0

    def move(self, x, y) -> None:
        self.flush()
        self.at = self._mm(x, y)

    def line(self, x, y) -> None:
        p = self._mm(x, y)
        if self.at is None:
            self.at = p
            return
        if math.dist(p, self.at) > 1e-9:
            self._add(Line(self.at, p))
            self.at = p

    def arc(self, x, y, cx, cy, clockwise: bool) -> None:
        p, c = self._mm(x, y), self._mm(cx, cy)
        if self.at is None:
            self.at = p
            return
        r = math.dist(self.at, c)
        if r < 1e-9:
            self.line(x, y)
            return
        a0 = math.atan2(self.at[1] - c[1], self.at[0] - c[0])
        a1 = math.atan2(p[1] - c[1], p[0] - c[0])
        sweep = a1 - a0
        if abs(sweep) < 1e-9:                            # revient à son départ : le cercle entier
            sweep = 0.0
        if clockwise:
            while sweep >= 0:
                sweep -= 2 * math.pi
        else:
            while sweep <= 0:
                sweep += 2 * math.pi
        segs = geom_arc(c, r, math.degrees(a0), math.degrees(sweep)).segments
        self._add(*segs)
        self.at = segs[-1].end
        if math.dist(p, self.at) > 1e-9:                 # arrivée hors du cercle : on la rejoint
            self._add(Line(self.at, p))
            self.at = p

    def close(self) -> None:
        if self.segs:
            first = self.segs[0].start
            if math.dist(first, self.at) > 1e-9:
                self._add(Line(self.at, first))
            self.flush(True)
            self.at = first


class _Return(Exception):
    pass


class _ExitLoop(Exception):
    def __init__(self, kind: str):
        super().__init__(kind)
        self.kind = kind


class _Array:
    def __init__(self, sizes: list[int]):
        total = 1
        for n in sizes:
            total *= n + 1
        if total > MAX_ARRAY:
            raise ScriptError('array')
        self.sizes = sizes
        self.items: list = [None] * total

    def index(self, idx: list[int]) -> int:
        if len(idx) != len(self.sizes):
            raise ScriptError('index')
        k = 0
        for i, n in zip(idx, self.sizes):
            if i < 0 or i > n:
                raise ScriptError('index')
            k = k * (n + 1) + i
        return k


def _number(v, line: int = 0) -> float:
    if v is None or v == '':
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            x = float(v.strip().replace(',', '.'))
        except ValueError:
            raise ScriptError('number', v[:30], line) from None
        if not math.isfinite(x):
            raise ScriptError('number', v[:30], line)
        return x
    raise ScriptError('number', '?', line)


def _text(v) -> str:
    if v is None:
        return ''
    if isinstance(v, str):
        return v
    if float(v) == int(v) and abs(v) < 1e15:
        return str(int(v))
    return f'{v:.15g}'


def _truth(v, line: int = 0) -> bool:
    return _number(v, line) != 0.0


def _vb_round(x: float) -> float:
    return float(round(x))


def _split(text, sep=' '):
    parts = _text(text).split(_text(sep)) if _text(sep) else [_text(text)]
    out = _Array([len(parts) - 1])
    out.items[:] = parts
    return out


def _format_number(v, digits=2):
    return f'{_number(v):.{int(_number(digits))}f}'


def _substr(s, start, length=None):
    s, i = _text(s), max(0, int(_number(start)) - 1)
    return s[i:] if length is None else s[i:i + max(0, int(_number(length)))]


_FUNCS = {
    'sin': lambda x: math.sin(_number(x)), 'cos': lambda x: math.cos(_number(x)), 'tan': lambda x: math.tan(_number(x)),
    'atn': lambda x: math.atan(_number(x)), 'exp': lambda x: math.exp(_number(x)), 'log': lambda x: math.log(_number(x)),
    'sqr': lambda x: math.sqrt(_number(x)), 'abs': lambda x: abs(_number(x)),
    'int': lambda x: float(math.floor(_number(x))), 'fix': lambda x: float(math.trunc(_number(x))),
    'sgn': lambda x: float((_number(x) > 0) - (_number(x) < 0)),
    'round': lambda x, n=0: round(_number(x), int(_number(n))),
    'cdbl': _number, 'csng': _number, 'cint': lambda x: _vb_round(_number(x)), 'clng': lambda x: _vb_round(_number(x)),
    'cbool': lambda x: -1.0 if _truth(x) else 0.0, 'cstr': _text,
    'len': lambda s: float(len(_text(s))), 'left': lambda s, n: _text(s)[:max(0, int(_number(n)))],
    'right': lambda s, n: _text(s)[-int(_number(n)):] if int(_number(n)) > 0 else '',
    'mid': _substr, 'trim': lambda s: _text(s).strip(), 'ltrim': lambda s: _text(s).lstrip(),
    'rtrim': lambda s: _text(s).rstrip(), 'ucase': lambda s: _text(s).upper(), 'lcase': lambda s: _text(s).lower(),
    'instr': lambda a, b=None: float(_text(a).find(_text(b)) + 1), 'replace': lambda s, a, b: _text(s).replace(_text(a), _text(b)),
    'isnumeric': lambda v: -1.0 if _is_numeric(v) else 0.0, 'isempty': lambda v: -1.0 if v is None else 0.0,
    'isnull': lambda v: -1.0 if v is None else 0.0, 'isobject': lambda v: -1.0 if isinstance(v, _Api) else 0.0,
    'isarray': lambda v: -1.0 if isinstance(v, _Array) else 0.0, 'split': _split,
    'join': lambda a, sep=' ': _text(sep).join(_text(v) for v in a.items),
    'formatnumber': _format_number, 'chr': lambda n: chr(int(_number(n))), 'asc': lambda s: float(ord(_text(s)[0])),
    'ubound': lambda a, d=1: float(a.sizes[int(_number(d)) - 1]), 'lbound': lambda _a, _d=1: 0.0,
    'convertstringtodouble': _number, 'arccos': lambda x: math.acos(_number(x)), 'arcsin': lambda x: math.asin(_number(x)),
    'atan2': lambda y, x: math.atan2(_number(y), _number(x)),
}
#: objets et fonctions de TypeEdit qui agissent sur son document : refusés avec leur nom, pas ignorés
_UNSUPPORTED = {'createobject', 'getobject', 'execute', 'executeglobal', 'eval', 'getdocument', 'getselection', 'matrice',
                'lnsegment', 'gmangle'}


def _is_numeric(v) -> bool:
    if isinstance(v, (int, float)):
        return True
    try:
        _number(v)
        return v not in (None, '')
    except ScriptError:
        return False


class _Api:
    """Un objet exposé au script (DbApi, WndScriptApi, objet rééditable) : méthodes en minuscules."""

    def __init__(self, methods: dict):
        self.methods = methods


class Interp:
    def __init__(self, host: Host | None = None, max_steps: int = MAX_STEPS):
        self.host = host or Host()
        self.pen = _Pen()
        self.max_steps = max_steps
        self.steps = 0
        self.funcs: dict = {}
        self.globals: dict = {}
        self.frames: list[dict] = []
        self.current: list = []                          # (nom de la fonction, ) pendant un appel
        self.edits: list = []                            # WndScriptApi : champs de la prochaine boîte
        self.values: dict = {}
        self.includes = 0
        self.reedit: dict | None = None                  # paramètres de l'objet créé par le script
        self.random = random.Random()
        self.globals.update({'vbcrlf': '\r\n', 'vbnewline': '\r\n', 'vbcr': '\r', 'vblf': '\n', 'vbtab': '\t'})
        self.apis = {'dbapi': _Api(self._db_methods()), 'wndscriptapi': _Api(self._wnd_methods())}
        self.drawing = {
            'newcurve': lambda: self.pen.new_curve(),
            'moveto': lambda x, y, _z=0: self.pen.move(_number(x), _number(y)),
            'lineto': lambda x, y, _z=0: self.pen.line(_number(x), _number(y)),
            'archto': lambda x, y, _z, cx, cy, _cz=0: self.pen.arc(_number(x), _number(y), _number(cx), _number(cy), True),
            'arctto': lambda x, y, _z, cx, cy, _cz=0: self.pen.arc(_number(x), _number(y), _number(cx), _number(cy), False),
            'closepath': lambda: self.pen.close(),
            'inputscriptbox': self._input_box, 'inputbox': self._input_box, 'showvalue': self._show, 'msgbox': self._show,
            'getnbparameters': lambda: float(len(self.host.params)),
            'getappparameter': self._app_param,
            'creatunicreeditableobject': self._new_object, 'addcurvetoreeditableobject': lambda: -1.0,
            'rnd': lambda _x=None: self.random.random(), 'randomize': lambda seed=None: self.random.seed(seed),
        }

    # --- API ---
    def _input_box(self, title, default=''):
        if self.host.ask is None:
            return _text(default)
        got = self.host.ask(_text(title), _text(default))
        return 'IDCANCEL' if got is None else got

    def _show(self, text):
        if self.host.show is not None:
            self.host.show(_text(text))
        return None

    def _app_param(self, i):
        k = int(_number(i))
        return self.host.params[k] if 0 <= k < len(self.host.params) else ''

    def _new_object(self):
        """L'objet qu'on rouvrira : ce qu'il garde (AddParam…) est relu à la réouverture (GetParam…)."""
        stored = dict(self.host.reedit or {})
        self.reedit = {}

        def add(name, value):
            self.reedit[_text(name).lower()] = value if isinstance(value, str) else float(_number(value))
            return -1.0

        def read(name):
            return stored.get(_text(name).lower(), 0.0)

        return _Api({'isparamexist': lambda n: -1.0 if _text(n).lower() in stored else 0.0,
                     'getparamdouble': lambda n: _number(read(n)), 'getparamint': lambda n: _vb_round(_number(read(n))),
                     'getparamstring': lambda n: _text(read(n)), 'addparamdouble': add, 'addparamint': add,
                     'addparamstring': add, 'setresizable': lambda _b=None: None})

    def _db_methods(self) -> dict:
        def get(key, section, default=''):
            return self.host.profile.get(f'{_text(section)}/{_text(key)}', default)

        def get_number(key, section, default=0.0):
            return _number(get(key, section, default))

        def put(key, section, value):
            self.host.profile[f'{_text(section)}/{_text(key)}'] = value if isinstance(value, str) else float(_number(value))
            return None

        return {'getprofilestring': lambda k, s, d='': _text(get(k, s, d)), 'getprofilelong': lambda k, s, d=0: _vb_round(get_number(k, s, d)),
                'getprofiledbl': get_number, 'writeprofilestring': put, 'writeprofilelong': put, 'writeprofiledbl': put}

    def _wnd_methods(self) -> dict:
        def add(ident, title, default=''):
            self.edits.append((_text(ident), _text(title), _text(default)))
            return -1.0

        def modal(title):
            if self.host.dialog is None:
                self.values = {i: d for i, _t, d in self.edits}
                return 'IDOK'
            got = self.host.dialog(_text(title), list(self.edits))
            if got is None:
                return 'IDCancel'
            self.values = dict(got)
            return 'IDOK'

        def html(_url, _w=0, _h=0):
            self.host.notes.append('html')
            return 'IDOK'

        def clean():
            self.edits = []
            return -1.0

        return {'addedit': add, 'domodaldynamic': modal, 'domodalhtml': html,
                'setboxsize': lambda _w, _h: None, 'getvalueedit': lambda i: self.values.get(_text(i), ''), 'cleanlistedit': clean}

    # --- exécution ---
    def run(self, text: str) -> list[Contour]:
        limit = sys.getrecursionlimit()
        sys.setrecursionlimit(max(limit, MAX_DEPTH))
        try:
            self._exec_block(self._hoist(_Parser(_tokens(text)).program()))
        except _Return:                                  # Exit Sub hors de toute fonction : le script s'arrête là
            pass
        except _ExitLoop as ex:
            raise ScriptError('syntax', 'Exit ' + ex.kind) from None
        finally:
            sys.setrecursionlimit(limit)
        self.pen.flush()
        return self.pen.contours

    def _hoist(self, body: list) -> list:
        """Les fonctions existent dès le début du script, où qu'elles soient écrites."""
        rest = []
        for st in body:
            if st[0] == 'function':
                self.funcs[st[2]] = st
            else:
                rest.append(st)
        return rest

    def _tick(self, line: int) -> None:
        self.steps += 1
        if self.steps > self.max_steps:
            raise ScriptError('steps', '', line)

    def _exec_block(self, body: list) -> None:
        for st in body:
            self._exec(st)

    def _exec(self, st) -> None:
        kind, line = st[0], st[1]
        self._tick(line)
        try:
            getattr(self, '_st_' + kind)(st)
        except ScriptError as ex:
            if not ex.line:
                ex.line = line
            raise
        except ZeroDivisionError:
            raise ScriptError('zero', '', line) from None
        except (ValueError, OverflowError, TypeError, IndexError, AttributeError) as ex:
            raise ScriptError('value', str(ex)[:60], line) from None
        except RecursionError:
            raise ScriptError('depth', '', line) from None

    def _scope(self) -> dict:
        return self.frames[-1] if self.frames else self.globals

    def _set(self, name: str, value) -> None:
        if self.frames and name in self.frames[-1]:
            self.frames[-1][name] = value
        elif name in self.globals:
            self.globals[name] = value
        else:
            self._scope()[name] = value

    def _lookup(self, name: str):
        if self.frames and name in self.frames[-1]:
            return True, self.frames[-1][name]
        if name in self.globals:
            return True, self.globals[name]
        return False, None

    def _st_dim(self, st) -> None:
        redim = st[3]
        for n, size in st[2]:
            if redim:
                old = self._lookup(n)[1]
                new = _Array([int(_number(self._eval(e))) for e in size or []] or [0])
                if redim == 'garde' and isinstance(old, _Array) and len(old.sizes) == len(new.sizes):
                    for idx in itertools.product(*(range(min(a, b) + 1) for a, b in zip(old.sizes, new.sizes))):
                        new.items[new.index(list(idx))] = old.items[old.index(list(idx))]
                self._set(n, new)
            elif size:
                self._scope()[n] = _Array([int(_number(self._eval(e))) for e in size])
            elif n not in self._scope():                  # un Dim dans une boucle garde la valeur, comme VBScript
                self._scope()[n] = None

    def _st_const(self, st) -> None:
        for n, e in st[2]:
            self._scope()[n] = self._eval(e)

    def _st_assign(self, st) -> None:
        target, value = st[2], self._eval(st[3])
        if target[0] == 'var':
            self._set(target[1], value)
            return
        if target[0] == 'apply' and target[1][0] == 'var':
            ok, arr = self._lookup(target[1][1])
            if ok and isinstance(arr, _Array):
                arr.items[arr.index([int(_number(self._eval(e))) for e in target[2]])] = value
                return
        if target[0] == 'member':                        # une propriété d'un objet de TypeEdit
            raise ScriptError('unsupported', target[2], st[1])
        raise ScriptError('syntax', '=', st[1])

    def _st_call(self, st) -> None:
        self._eval(st[2], statement=True)

    def _st_if(self, st) -> None:
        for cond, body in st[2]:
            if _truth(self._eval(cond), st[1]):
                self._exec_block(body)
                return
        self._exec_block(st[3])

    def _st_for(self, st) -> None:
        _k, line, var, first, last, step, body = st
        i, hi = _number(self._eval(first), line), _number(self._eval(last), line)
        d = _number(self._eval(step), line) if step is not None else 1.0
        if d == 0:
            raise ScriptError('value', 'Step 0', line)
        try:
            while (i <= hi + 1e-12) if d > 0 else (i >= hi - 1e-12):
                self._set(var, i)
                self._tick(line)
                self._exec_block(body)
                i = _number(self._lookup(var)[1], line) + d
        except _ExitLoop as ex:
            if ex.kind != 'for':
                raise

    def _st_while(self, st) -> None:
        while _truth(self._eval(st[2]), st[1]):
            self._tick(st[1])
            self._exec_block(st[3])

    def _st_do(self, st) -> None:
        _k, line, pre, post, body = st
        def go_on(test):
            return test is None or _truth(self._eval(test[1]), line) == (test[0] == 'while')
        try:
            while go_on(pre):
                self._tick(line)
                self._exec_block(body)
                if not go_on(post):
                    break
        except _ExitLoop as ex:
            if ex.kind != 'do':
                raise

    def _st_select(self, st) -> None:
        subject = self._eval(st[2])
        for values, body in st[3]:
            if any(self._equal(subject, self._eval(v)) for v in values):
                self._exec_block(body)
                return
        self._exec_block(st[4])

    def _st_exit(self, st) -> None:
        if st[2] in ('function', 'sub'):
            raise _Return()
        raise _ExitLoop(st[2])

    def _st_function(self, st) -> None:                  # fonction écrite dans un bloc
        self.funcs[st[2]] = st

    def _st_include(self, st) -> None:
        self.includes += 1
        if self.includes > MAX_INCLUDES or self.host.folder is None:
            raise ScriptError('include', st[2], st[1])
        text = read_include(self.host.folder, st[2])
        if text is None:
            raise ScriptError('include', st[2], st[1])
        try:
            self._exec_block(self._hoist(_Parser(_tokens(text)).program()))
        except ScriptError as ex:
            ex.file = ex.file or st[2]
            raise

    def _call_function(self, fn, args: list, line: int, nodes=()):
        """Les arguments passent par référence, sauf ByVal : un paramètre modifié change la variable de l'appelant."""
        _k, _l, name, params, body = fn
        if len(args) > len(params):
            raise ScriptError('args', name, line)
        frame = {p: v for (p, _b), v in zip(params, args)}
        for p, _b in params[len(args):]:
            frame[p] = None
        frame[name] = None
        self.frames.append(frame)
        try:
            self._exec_block(body)
        except _Return:
            pass
        finally:
            self.frames.pop()
        for (p, by_value), node in zip(params, nodes):
            if not by_value and node[0] == 'var' and self._lookup(node[1])[0]:
                self._set(node[1], frame[p])
        return frame[name]

    def _call_name(self, name: str, raw: str, args: list, line: int, nodes=()):
        fn = self.funcs.get(name)
        if fn is not None:
            return self._call_function(fn, args, line, nodes)
        native = self.drawing.get(name) or _FUNCS.get(name)
        if native is not None:
            try:
                return native(*args)
            except TypeError:
                raise ScriptError('args', raw, line) from None
        if name in _UNSUPPORTED:
            raise ScriptError('unsupported', raw, line)
        raise ScriptError('unknown', raw, line)

    def _eval(self, node, statement: bool = False):
        kind = node[0]
        if kind == 'lit':
            return node[1]
        if kind == 'var':
            name = node[1]
            ok, v = self._lookup(name)
            if ok:
                return v
            if name in self.apis:
                return self.apis[name]
            if name in self.funcs or name in self.drawing or name in _FUNCS:
                self._tick(node[2])
                return self._call_name(name, node[3], [], node[2])
            if name in _UNSUPPORTED or statement:
                raise ScriptError('unsupported' if name in _UNSUPPORTED else 'unknown', node[3], node[2])
            return None                                  # variable jamais écrite : vide, comme VBScript
        if kind == 'bin':
            return self._binary(node)
        if kind == 'neg':
            return -_number(self._eval(node[1]))
        if kind == 'not':
            return 0.0 if _truth(self._eval(node[1])) else -1.0
        if kind == 'member':
            obj = self._eval(node[1])
            if isinstance(obj, _Api) and node[2] in obj.methods:
                return obj.methods[node[2]]()
            raise ScriptError('unsupported', node[2], node[3])
        if kind == 'apply':
            return self._apply(node)
        raise ScriptError('syntax', str(kind))

    def _apply(self, node):
        target, args = node[1], node[2]
        if target[0] == 'member':
            obj = self._eval(target[1])
            method = obj.methods.get(target[2]) if isinstance(obj, _Api) else None
            if method is None:
                raise ScriptError('unsupported', target[2], target[3])
            values = [self._eval(a) for a in args]
            try:
                return method(*values)
            except TypeError:
                raise ScriptError('args', target[2], target[3]) from None
        if target[0] != 'var':
            raise ScriptError('syntax', '(')
        name = target[1]
        ok, v = self._lookup(name)
        if ok and isinstance(v, _Array):
            return v.items[v.index([int(_number(self._eval(a))) for a in args])]
        self._tick(target[2])
        return self._call_name(name, target[3], [self._eval(a) for a in args], target[2], args)

    def _equal(self, a, b) -> bool:
        if a is None or b is None:                       # vide : égal à 0 et à la chaîne vide
            other = b if a is None else a
            return other is None or other == '' or other == 0
        if isinstance(a, str) and isinstance(b, str):
            return a == b
        if _is_numeric(a) and _is_numeric(b):
            return _number(a) == _number(b)
        return _text(a) == _text(b)

    def _binary(self, node):
        _k, op, left, right, line = node
        a = self._eval(left)
        b = self._eval(right)
        if op == '&' or (op == '+' and (isinstance(a, str) or isinstance(b, str)) and
                         all(isinstance(v, str) or v is None for v in (a, b))):
            out = _text(a) + _text(b)                    # « + » de deux chaînes : elles se suivent, même si ce sont des chiffres
            if len(out) > MAX_TEXT:
                raise ScriptError('value', 'texte', line)
            return out
        if op == '=':
            return -1.0 if self._equal(a, b) else 0.0
        if op == '<>':
            return 0.0 if self._equal(a, b) else -1.0
        if op in ('<', '>', '<=', '>='):
            if isinstance(a, str) and isinstance(b, str):
                x, y = a, b
            else:
                x, y = _number(a, line), _number(b, line)
            r = {'<': x < y, '>': x > y, '<=': x <= y, '>=': x >= y}[op]
            return -1.0 if r else 0.0
        x, y = _number(a, line), _number(b, line)
        if op == '+':
            return x + y
        if op == '-':
            return x - y
        if op == '*':
            return x * y
        if op == '/':
            if y == 0:
                raise ScriptError('zero', '', line)
            return x / y
        if op == '\\':
            d = _vb_round(y)
            if d == 0:
                raise ScriptError('zero', '', line)
            return float(math.trunc(_vb_round(x) / d))
        if op == 'mod':
            d = _vb_round(y)
            if d == 0:
                raise ScriptError('zero', '', line)
            return float(math.fmod(_vb_round(x), d))
        if op == '^':
            if x < 0 and y != int(y):
                raise ScriptError('value', f'{x:g} ^ {y:g}', line)
            return x ** y
        ix, iy = int(_vb_round(x)), int(_vb_round(y))
        return float({'and': ix & iy, 'or': ix | iy, 'xor': ix ^ iy}[op])


def read_text(path: pathlib.Path) -> str:
    """Un script en UTF-8, sinon en Windows-1252 (ceux de TypeEdit)."""
    raw = path.read_bytes()
    try:
        return raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        return raw.decode('cp1252', errors='replace')


def read_include(folder: pathlib.Path, name: str) -> str | None:
    """Le texte d'un script du même dossier, sans jamais en sortir."""
    if any(c in name for c in '/\\:') or '..' in name:
        return None
    for ext in ('.sli', '.txt', '.vbs', ''):
        p = pathlib.Path(folder) / (name + ext)
        if p.is_file():
            return read_text(p)
    return None


def run(text: str, host: Host | None = None, max_steps: int = MAX_STEPS) -> Result:
    """Ce que dessine le script, les contours qui se touchent raccordés. ScriptError s'il y a une erreur."""
    from .chain import chain
    interp = Interp(host, max_steps)
    contours = interp.run(text)
    closed = [c for c in contours if c.closed]
    opened = [c for c in contours if not c.closed]
    return Result(closed + (chain(opened, 1e-6)[0] if opened else []), interp.reedit, interp.host.notes)


# --- dossiers -------------------------------------------------------------------------------------
def user_dir() -> pathlib.Path:
    """Les scripts de l'utilisateur."""
    env = os.environ.get('VECTORDRIVE_SCRIPTS')
    if env:
        return pathlib.Path(env)
    from ..portable import data_dir
    return data_dir() / 'scripts'


def find_script(name: str, *folders) -> pathlib.Path | None:
    """Le fichier d'un script nommé sur la ligne de commande : le chemin tel quel, ou le nom dans « Mes scripts »
    puis dans `folders`. TypeEdit écrit « ShapeScript\\X.txt », relatif à son installation."""
    p = pathlib.Path(str(name).replace('\\', '/'))
    tries = [p, user_dir() / p, user_dir() / p.name]
    tries += [pathlib.Path(f) / p.name for f in folders if f]
    for t in tries:
        for f in (t, t.with_name(t.name + '.txt')):
            if f.is_file():
                return f
    return None


def scripts_in(folder: pathlib.Path) -> list[pathlib.Path]:
    """Les scripts qu'on lance d'un dossier ; les .sli ne servent qu'à être repris par les autres."""
    try:
        return sorted((f for f in pathlib.Path(folder).iterdir() if f.is_file() and f.suffix.lower() in EXTENSIONS),
                      key=lambda f: f.name.lower())
    except OSError:
        return []


def _values_file(script: pathlib.Path) -> pathlib.Path:
    return user_dir() / '_valeurs' / (pathlib.Path(script).stem + '.json')


def load_values(script: pathlib.Path) -> dict:
    """Ce que le script a gardé par DbApi la dernière fois. Jamais à côté du script : le dossier de TypeEdit reste intact."""
    try:
        got = json.loads(_values_file(script).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return got if isinstance(got, dict) else {}


def save_values(script: pathlib.Path, values: dict) -> None:
    f = _values_file(script)
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix('.tmp')
        tmp.write_text(json.dumps(values, ensure_ascii=False, indent=1), encoding='utf-8')
        tmp.replace(f)
    except OSError:
        pass
