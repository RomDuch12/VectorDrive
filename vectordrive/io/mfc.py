"""Lecture d'une archive MFC (`CArchive`) — le conteneur des fichiers
TypeEdit (.vnd, .smb…).

Rappel du format MFC (documenté par Microsoft, `afx.h` / `arcobj.cpp`) :

* les objets sont précédés d'une **étiquette** de 16 bits :
  `0xFFFF` = nouvelle classe (suivie du schéma, de la longueur du nom et du
  nom), `0x8000 | n` = classe déjà vue (n = indice), `0x7FFF` = étiquette
  longue sur 32 bits, autre valeur = **référence** à un objet déjà lu
  (0 = pointeur nul) ;
* classes et objets partagent une seule table d'indices, qui commence à 1 ;
* les `CString` sont précédées d'une longueur à taille variable, et d'un
  marqueur `FF FE FF` quand elles sont en UTF-16.

Ce module ne connaît aucune classe TypeEdit : il fournit la mécanique, et
`vnd.py` enregistre une fonction de lecture par nom de classe.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Callable

NEW_CLASS_TAG = 0xFFFF
CLASS_TAG = 0x8000
BIG_OBJECT_TAG = 0x7FFF
BIG_CLASS_TAG = 0x80000000


_U8, _U16, _U32, _I32, _U64, _F64 = (struct.Struct(f) for f in ('<B', '<H', '<I', '<i', '<Q', '<d'))
_STRUCTS: dict = {}


class ArchiveError(ValueError):
    pass


@dataclass
class MfcClass:
    name: str
    schema: int


@dataclass
class MfcObject:
    """Objet lu : nom de classe, schéma, champs décodés, et position dans
    le fichier (début de l'étiquette, fin des données)."""
    cls: MfcClass
    fields: dict = field(default_factory=dict)
    children: list['MfcObject'] = field(default_factory=list)
    start: int = 0
    end: int = 0

    @property
    def name(self) -> str:
        return self.cls.name

    def __repr__(self) -> str:
        return f'<{self.cls.name} v{self.cls.schema} @{self.start} {len(self.children)} enfants>'


Reader = Callable[['Archive', MfcObject], None]


class WideStr(str):
    """Chaîne lue en UTF-16 dans l'archive : réécrite en UTF-16."""
    __slots__ = ()


class Archive:
    """Curseur de lecture sur un tampon d'octets, petit-boutiste."""

    def __init__(self, data: bytes, pos: int = 0,
                 readers: dict[str, Reader] | None = None):
        self.data = data
        self.pos = pos
        self.readers = readers or {}
        self.table: list = [None]          # indice 0 = pointeur nul
        self.trace: list[str] = []
        #: objets en cours de lecture (racine d'abord) : après une erreur,
        #: ce qui a été lu reste accessible (lecture partielle)
        self.stack: list[MfcObject] = []

    # --- types de base ------------------------------------------------------
    # formats précompilés : ces lectures se comptent par centaines de
    # milliers dans un gros VND
    def _unpack(self, fmt: str):
        st = _STRUCTS.get(fmt)
        if st is None:
            st = _STRUCTS[fmt] = struct.Struct(fmt)
        return self._take(st)

    def _take(self, st: struct.Struct):
        p = self.pos
        if p + st.size > len(self.data):
            raise ArchiveError(f'fin de fichier à {p} (lecture {st.format})')
        self.pos = p + st.size
        return st.unpack_from(self.data, p)

    def u8(self) -> int:
        return self._take(_U8)[0]

    def u16(self) -> int:
        return self._take(_U16)[0]

    def u32(self) -> int:
        return self._take(_U32)[0]

    def i32(self) -> int:
        return self._take(_I32)[0]

    def u64(self) -> int:
        return self._take(_U64)[0]

    def f64(self) -> float:
        return self._take(_F64)[0]

    def f64s(self, n: int) -> tuple[float, ...]:
        return self._unpack(f'<{n}d')

    def raw(self, n: int) -> bytes:
        if n < 0 or self.pos + n > len(self.data):
            raise ArchiveError(f'longueur invalide {n} à {self.pos}')
        b = self.data[self.pos:self.pos + n]
        self.pos += n
        return b

    def std_string(self) -> str:
        """Chaîne « maison » : longueur u32 puis octets (ANSI)."""
        n = self.u32()
        if n > 1 << 24:
            raise ArchiveError(f'chaîne trop longue ({n}) à {self.pos - 4}')
        return self.raw(n).decode('cp1252', 'replace')

    def cstring(self) -> str:
        """`CString` MFC (opérateur >>), ANSI ou UTF-16 (rendue en
        `WideStr` pour être réécrite à l'identique)."""
        unicode = False
        n = self.u8()
        if n == 0xFF:
            n = self.u16()
            if n == 0xFFFE:                 # marqueur Unicode
                unicode = True
                n = self.u8()
                if n == 0xFF:
                    n = self.u16()
                    if n == 0xFFFF:
                        n = self.u32()
            elif n == 0xFFFF:
                n = self.u32()
        if unicode:
            return WideStr(self.raw(2 * n).decode('utf-16-le', 'replace'))
        return self.raw(n).decode('cp1252', 'replace')

    # --- objets -------------------------------------------------------------
    def read_object(self) -> MfcObject | None:
        """`CArchive::ReadObject` : étiquette, classe, puis données."""
        start = self.pos
        tag = self.u16()
        if tag == BIG_OBJECT_TAG:
            ob_tag = self.u32()
        else:
            ob_tag = ((tag & CLASS_TAG) << 16) | (tag & ~CLASS_TAG & 0xFFFF)
        if tag == NEW_CLASS_TAG:
            schema = self.u16()
            n = self.u16()
            name = self.raw(n).decode('ascii', 'replace')
            cls = MfcClass(name, schema)
            self.table.append(cls)
        elif ob_tag & BIG_CLASS_TAG:
            idx = ob_tag & ~BIG_CLASS_TAG
            if idx >= len(self.table) or not isinstance(self.table[idx], MfcClass):
                raise ArchiveError(f'référence de classe invalide {idx} à {start}')
            cls = self.table[idx]
        else:
            # référence à un objet déjà lu (0 = NULL)
            if ob_tag >= len(self.table):
                raise ArchiveError(f'référence d\'objet invalide {ob_tag} à {start}')
            return self.table[ob_tag]
        obj = MfcObject(cls, start=start)
        self.table.append(obj)
        self.stack.append(obj)
        self.serialize(obj)                 # en cas d'erreur, la pile reste en l'état
        self.stack.pop()
        obj.end = self.pos
        return obj

    def serialize(self, obj: MfcObject) -> None:
        """Lit les données d'un objet dont la classe est connue (appel
        direct de `Serialize`, sans étiquette)."""
        reader = self.readers.get(obj.cls.name)
        if reader is None:
            raise ArchiveError(
                f'classe inconnue « {obj.cls.name} » (schéma {obj.cls.schema}) '
                f'à l\'octet {obj.start}')
        reader(self, obj)

    def embedded(self, name: str, schema: int = 0) -> MfcObject:
        """Objet sérialisé directement par son parent (sans étiquette)."""
        obj = MfcObject(MfcClass(name, schema), start=self.pos)
        self.serialize(obj)
        obj.end = self.pos
        return obj
