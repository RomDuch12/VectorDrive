"""Traduction de l'interface (FR d'origine → EN).

Les libellés sont écrits en français dans le code et passés à `tr()` ;
la table `ressources/i18n/<langue>.json` donne leur traduction (texte
français → texte traduit). Une chaîne absente de la table reste en
français. Les gabarits utilisent `str.format` : `tr('{n} copie(s)').format(n=3)`.

La langue est choisie dans les options (F10) et prend effet au
redémarrage ; par défaut, celle du système (français sinon anglais).
"""
from __future__ import annotations

import json
import locale
import pathlib

LANGUAGES = {'fr': 'Français', 'en': 'English'}
_DIR = pathlib.Path(__file__).resolve().parent / 'ressources' / 'i18n'
_table: dict[str, str] = {}
_core: dict[str, str] = {}                  # table du cœur ; `_table` y ajoute celles des plugins
_lang = 'fr'


def system_language() -> str:
    try:
        from PySide6.QtCore import QLocale
        name = QLocale.system().name()
    except Exception:                       # pragma: no cover - sans Qt
        name = locale.getlocale()[0] or ''
    return 'fr' if name.lower().startswith('fr') else 'en'


def set_language(lang: str | None) -> str:
    """Charge la table de `lang` ('fr', 'en' ; None = langue du système)."""
    global _core, _lang
    lang = lang if lang in LANGUAGES else system_language()
    _lang = lang
    _core = {}
    if lang != 'fr':
        f = _DIR / f'{lang}.json'
        if f.exists():
            _core = json.loads(f.read_text(encoding='utf-8'))
    refresh_plugins()
    return lang


def refresh_plugins() -> None:
    """Table active = celle du cœur + celles des plugins chargés (le cœur
    a le dernier mot)."""
    global _table
    if _lang == 'fr':
        _table = {}
        return
    from .plugins import REGISTRY
    _table = {**REGISTRY.translations.get(_lang, {}), **_core}


def language() -> str:
    return _lang


def install_qt_translations(app) -> bool:
    """Traductions de Qt lui-même (boutons standard « Annuler », menus des
    champs de saisie…) dans la langue de l'interface. True si chargées."""
    if _lang == 'en':
        return False
    import pathlib as _pl

    import PySide6
    from PySide6.QtCore import QLibraryInfo, QTranslator
    t = QTranslator(app)
    for d in (QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath),
              str(_pl.Path(PySide6.__file__).resolve().parent / 'translations')):
        if t.load(f'qtbase_{_lang}', d):
            app.installTranslator(t)
            app._vd_qt_translator = t              # garder une référence
            return True
    return False


def tr(text: str) -> str:
    return _table.get(text, text) if _table else text


def decimal_sep() -> str:
    """Séparateur décimal des documents produits (BAT) : virgule en français."""
    return ',' if _lang == 'fr' else '.'
