"""Volumes Windows indisponibles : lecteur verrouillé par BitLocker, volume non reconnu, lecteur sans support.

Python 3.13 (celui de l'exécutable) ne prend pour « absent », dans `Path.exists`, `is_dir` et `is_file`, que trois
erreurs Windows et lève une exception pour les autres : un lecteur verrouillé faisait échouer « Ouvrir ». Ces erreurs
sont ajoutées à sa liste à l'import de ce module (Python 3.14 prend toute erreur pour « absent »). Les erreurs réseau
passagères (connexion perdue, partage injoignable) n'y sont pas : prises pour « absent », un fichier partagé lu
« absent » pendant une coupure serait recréé vide et écraserait l'original au retour du réseau (bibliothèque
d'outils…) ; ce qui doit les tolérer (liste des lecteurs du navigateur) le fait sur place."""
from __future__ import annotations

import sys

#: FVE_E_LOCKED_VOLUME (BitLocker, valeur signée telle que Python la rend), ERROR_UNRECOGNIZED_VOLUME,
#: ERROR_NO_MEDIA_IN_DRIVE
UNREACHABLE_WINERRORS = (-2144272384, 1005, 1112)


def tolerant() -> bool:
    """Ajoute les erreurs à la liste de `pathlib` ; False si rien à faire (autre système, autre Python)."""
    if sys.platform != 'win32':
        return False
    try:
        from pathlib import _abc
        known = tuple(_abc._IGNORED_WINERRORS)
    except (ImportError, AttributeError):
        return False
    _abc._IGNORED_WINERRORS = known + tuple(e for e in UNREACHABLE_WINERRORS if e not in known)
    return True


tolerant()
