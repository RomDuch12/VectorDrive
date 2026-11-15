"""Plugins : ce qui est propre à un atelier vit hors du cœur.

Voir `docs/ARCHITECTURE.md`. Un plugin est un paquet Python qui expose
`PLUGIN` (métadonnées) et `register(api)` ; `api` est une `Api`, la seule
porte d'entrée vers le cœur. Ce qu'il apporte est rangé dans `REGISTRY`,
que le cœur consulte (raccourcis, actions, post-processeurs, stratégies…).

Recherche (`load`) : dossiers `plugins/` à côté de l'application et dans
les données de l'utilisateur, puis `VECTORDRIVE_PLUGINS` (chemins séparés
par `;`). `VECTORDRIVE_NO_PLUGINS=1` désactive tout. Un plugin en erreur
est noté (`PluginInfo.error`) et n'empêche jamais le démarrage.
"""
from __future__ import annotations

import importlib
import os
import pathlib
import sys
import traceback
from dataclasses import dataclass, field
from typing import Callable

#: version de l'API ; un plugin qui en demande une autre n'est pas chargé
API_VERSION = 1
ENV_PATHS = 'VECTORDRIVE_PLUGINS'
ENV_OFF = 'VECTORDRIVE_NO_PLUGINS'


@dataclass
class PluginInfo:
    module: str
    name: str = ''
    version: str = ''
    licence: str = ''
    description: str = ''
    path: str = ''
    error: str = ''

    @property
    def ok(self) -> bool:
        return not self.error


@dataclass
class ActionSpec:
    key: str
    label: str
    slot: Callable                  # slot(window)
    tab: str = ''                   # onglet du ruban (créé au besoin) ; vide = aucun
    group: str = ''
    icon: str = ''
    tip: str = ''
    shortcut: str = ''
    big: bool = True
    plugin: str = ''
    after: str = ''                 # clé d'une action du ruban : le bouton se place juste après
    posts: tuple = ()               # machines (clés de post-processeur ou de machine) où l'action se montre ; vide : toujours


@dataclass
class PanelSpec:
    """Panneau ancré apporté par un plugin, montré seulement pour certaines
    machines (clés de post-processeur ; vide : toujours)."""
    key: str
    title: str
    factory: Callable               # factory(window) → QWidget
    posts: tuple = ()
    area: str = 'droite'            # 'droite' ou 'gauche'
    plugin: str = ''


@dataclass
class MachineSpec:
    """Machine de la FAO déclarée par un plugin (voir `cam.machines`) : une fraiseuse ou un laser, les clés de
    post-processeur qui la pilotent (motifs à la fnmatch, de la meilleure à la moins bonne) et celles qui font
    double emploi."""
    key: str
    label: str
    kind: str = 'fraiseuse'         # 'fraiseuse' ou 'laser'
    posts: tuple = ()
    doubles: tuple = ()
    tip: str = ''
    plugin: str = ''


@dataclass
class FormatSpec:
    """Format de fichier apporté par un plugin (programme machine…)."""
    key: str
    label: str
    extensions: tuple
    read: Callable | None = None            # read(chemin) → Document
    write: Callable | None = None           # write(Document, chemin)
    export: Callable | None = None          # export(fenêtre, chemin) : réglages demandés puis écriture
    machine: bool = False                   # programme machine : le dessin est vérifié avant l'écriture
    plugin: str = ''


@dataclass
class Registry:
    """Contributions des plugins chargés."""
    plugins: list = field(default_factory=list)
    shortcut_schemes: dict = field(default_factory=dict)     # clé → (libellé, [(commande TypeEdit, touches)])
    default_scheme: str = ''
    cam_favorites: list = field(default_factory=list)       # clés d'actions de la palette FAO
    font_dirs: list = field(default_factory=list)
    font_formats: list = field(default_factory=list)         # (libellé, extensions) des formats de polices
    symbol_roots: list = field(default_factory=list)
    actions: list = field(default_factory=list)              # ActionSpec
    posts: dict = field(default_factory=dict)                # clé → (libellé, fonction d'écriture)
    #: fournisseurs de post-processeurs tirés de fichiers machine : posts(dossier) → {clé: libellé},
    #: resolve(clé) → (clé du post-processeur, fiche machine) ou None
    post_providers: list = field(default_factory=list)
    formats: list = field(default_factory=list)              # FormatSpec
    strategies: dict = field(default_factory=dict)           # nature → (libellé, fonction)
    cam_presets: dict = field(default_factory=dict)          # clé → (libellé, nature, réglages, nature d'outil)
    tool_libraries: dict = field(default_factory=dict)       # nom → fonction() → [CamTool]
    templates: dict = field(default_factory=dict)            # genre → {nom: données}
    vnd_template: str = ''
    translations: dict = field(default_factory=dict)         # langue → {français: traduction}
    autotests: list = field(default_factory=list)            # (nom, fonction)
    about: list = field(default_factory=list)
    update_manifest: str = ''                                # nom du manifeste de mise à jour
    window_hooks: list = field(default_factory=list)         # fonction(window), une fois la fenêtre bâtie
    defaults: dict = field(default_factory=dict)             # « famille » → {réglage: valeur}
    themes: list = field(default_factory=list)               # thèmes de l'interface (dict JSON)
    bat_prices: list = field(default_factory=list)           # fonction(objets) → prix écrit (BAT), ou None
    nc_readers: list = field(default_factory=list)           # (libellé, extensions, lecture, reconnaissance)
    #: catalogues d'opérations machine : (libellé, fonction() → [cam.catalog.Entry ou dict])
    instruction_catalogs: list = field(default_factory=list)
    panels: list = field(default_factory=list)               # PanelSpec
    post_hooks: list = field(default_factory=list)           # fonction(window, clé de la machine) : machine changée
    #: export propre à une machine : clé de post → fonction(panneau FAO, parcours, réglage) → vrai si fait
    post_exports: dict = field(default_factory=dict)
    machines: list = field(default_factory=list)             # MachineSpec : fraiseuses et lasers du ruban FAO


REGISTRY = Registry()
_loaded = False


class Api:
    """Ce qu'un plugin peut faire. Toutes les méthodes sont sans effet sur
    les fichiers : elles déclarent des contributions."""

    version = API_VERSION

    def __init__(self, registry: Registry, info: PluginInfo):
        self._r = registry
        self.info = info

    # --- interface ------------------------------------------------------------------
    def add_shortcut_scheme(self, key: str, label: str, entries: list, default: bool = False) -> None:
        """Jeu de raccourcis : accélérateurs au format TypeEdit (commande, « Ctrl+R »)."""
        self._r.shortcut_schemes[key] = (label, [tuple(e) for e in entries])
        if default:
            self._r.default_scheme = key

    def link_typeedit_command(self, command: str, action_key: str) -> None:
        """Commande TypeEdit (« ID_FILE_COST »…) reliée à une action du plugin :
        son bouton dans la disposition TypeEdit et son raccourci TeTurboKey.
        Une commande déjà reliée par VectorDrive le reste."""
        from .ui.shortcuts import TE_ACTIONS
        TE_ACTIONS.setdefault(command, action_key)

    def set_cam_favorites(self, keys: list[str]) -> None:
        """Commandes en tête de la palette FAO quand TypeEdit n'est pas sur le poste."""
        self._r.cam_favorites = list(keys)

    def add_font_dir(self, path) -> None:
        self._r.font_dirs.append(pathlib.Path(path))
        from .core import fonts
        fonts.add_dirs([path])

    def add_font_format(self, label: str, extensions, *, font_name: Callable, glyph: Callable, metrics: Callable,
                        kerning: Callable | None = None, characters: Callable | None = None,
                        clear: Callable | None = None, dirs=(), clonable: bool = False) -> None:
        """Un format de polices propriétaire, lu sur le poste (jamais redistribué) : `extensions` ('.xyz', …) ;
        `label` : l'infobulle de ses polices dans les listes ; `font_name(chemin)` → nom ou None ;
        `glyph(chemin, caractère)` → (Path, avance) ; `metrics(chemin)` → {'upem', 'ascent', 'descent', 'cap'} ;
        `kerning(chemin, gauche, droite)` ; `characters(chemin)` → codes ; `clear()` : oublier ce qui est lu ;
        `dirs` : ses dossiers ; `clonable` : l'éditeur de polices peut partir de ses polices."""
        from .core import fontformats
        exts = tuple(str(e).lower() for e in extensions)
        self._r.font_formats.append((label, exts))
        fontformats.register(fontformats.FontFormat(
            label=label, extensions=exts, font_name=font_name, glyph=glyph, metrics=metrics, kerning=kerning,
            characters=characters, clear=clear, dirs=tuple(pathlib.Path(d) for d in dirs), clonable=clonable,
            reader=f'{self.info.module} {self.info.version}'))

    def add_symbol_root(self, path) -> None:
        self._r.symbol_roots.append(pathlib.Path(path))

    def add_action(self, key: str, label: str, slot: Callable, *, tab: str = '', group: str = '',
                   icon: str = '', tip: str = '', shortcut: str = '', big: bool = True, after: str = '',
                   posts=()) -> None:
        """Commande de la fenêtre (`slot(window)`), dans le ruban si `tab` ;
        `after` : clé d'une action déjà dans le ruban (ex. 'proof', le BAT) —
        le bouton se met juste après elle, dans son groupe (sinon dans
        `tab` / `group`) ; `posts` : montrée seulement quand la machine du
        dessin est l'une de celles-ci (clés de post-processeur)."""
        self._r.actions.append(ActionSpec(key, label, slot, tab, group, icon, tip, shortcut, big,
                                          self.info.name, after, tuple(posts or ())))

    def add_panel(self, key: str, title: str, factory: Callable, *, posts=(), area: str = 'droite') -> None:
        """Panneau ancré (`factory(window)` → QWidget), montré seulement pour
        les machines `posts` (vide : toujours) — les fonctions d'une machine
        qui apparaissent quand on la choisit."""
        self._r.panels.append(PanelSpec(key, title, factory, tuple(posts or ()), area, self.info.name))

    def add_machine(self, key: str, label: str, *, kind: str = 'fraiseuse', posts=(), doubles=(),
                    tip: str = '') -> None:
        """Machine du ruban FAO : `kind` 'fraiseuse' (rubans FAO 2D et 3D) ou 'laser' (ruban FAO laser) ; `posts`,
        les clés de post-processeur qui la pilotent, de la meilleure à la moins bonne (motifs à la fnmatch :
        « mah:*/Haas/* ») ; `doubles`, celles qui font double emploi et ne sont plus proposées. Sans `posts`
        disponible, la machine est montrée « à configurer ». Les actions et panneaux déclarés avec
        `posts=(clé de la machine,)` ne se montrent que pour elle."""
        self._r.machines = [m for m in self._r.machines if m.key != key]
        self._r.machines.append(MachineSpec(key, label, kind if kind in ('fraiseuse', 'laser') else 'fraiseuse',
                                            tuple(posts or ()), tuple(doubles or ()), tip, self.info.name))

    def on_post_changed(self, fn: Callable) -> None:
        """`fn(window, clé)` quand la machine du dessin change (choix dans les
        Options, autre dessin, modèle d'usinage) ; la clé est celle du
        post-processeur (une fiche machine : celui qu'elle désigne)."""
        self._r.post_hooks.append(fn)

    def add_post_export(self, key: str, fn: Callable) -> None:
        """Export propre à une machine : « Post-traitement » appelle
        `fn(panneau FAO, parcours, réglage)` au lieu de la boîte « Enregistrer »
        ordinaire (nom du travail, dossier, quantité…) ; elle rend vrai si elle
        a écrit (ou annulé), faux pour laisser faire l'export ordinaire."""
        self._r.post_exports[key] = fn

    def on_window(self, fn: Callable) -> None:
        """`fn(window)` une fois la fenêtre principale construite."""
        self._r.window_hooks.append(fn)

    def add_about(self, line: str) -> None:
        self._r.about.append(line)

    def add_nc_reader(self, label: str, extensions, read: Callable, sniff: Callable | None = None) -> None:
        """Lecteur de programmes machine pour le visualiseur : `read(texte, nom)`
        → Toolpath ; `sniff(texte)` → vrai si le texte est de ce langage (sinon :
        reconnu à l'extension seulement)."""
        self._r.nc_readers.append((label, tuple(e.lower() for e in extensions), read, sniff))

    def add_instruction_catalog(self, label: str, provider: Callable) -> None:
        """Catalogue d'opérations machine (FAO › Ajouter depuis un catalogue) :
        provider() → [cam.catalog.Entry, ou dict de ses champs], appelé à
        l'ouverture de la fenêtre."""
        self._r.instruction_catalogs.append((label, provider))

    def add_bat_price(self, fn: Callable) -> None:
        """Prix d'une gravure sur le BAT : `fn(objets)` → texte (« 72,00 € HT »)
        ou None (pas de devis réglé) ; appelée pour chaque gravure."""
        self._r.bat_prices.append(fn)

    def add_translations(self, lang: str, table: dict) -> None:
        self._r.translations.setdefault(lang, {}).update(table)
        from . import i18n
        i18n.refresh_plugins()

    # --- FAO -------------------------------------------------------------------------
    def add_post(self, key: str, label: str, write: Callable) -> None:
        """Post-processeur : write(toolpaths, setup, *, title, machine, stem, box_mm) → PostResult."""
        self._r.posts[key] = (label, write)

    def add_post_provider(self, provider) -> None:
        """Post-processeurs tirés de fichiers machine (fiches d'un dossier) :
        `provider.posts(dossier)` → {clé: libellé} ; `provider.resolve(clé)` →
        (clé d'un post-processeur, fiche machine) ou None ; facultatif :
        `provider.default_machines()` → dossier de fiches livré avec le plugin,
        pris quand l'utilisateur n'en a choisi aucun ; `provider.default_zero(clé)`
        → zéro des programmes qu'attend la machine de la fiche ('plaque_hg'…,
        `cam.post.ZEROS`), pris quand le dessin laisse le choix à la machine. Un
        post-processeur dit le sien par l'attribut `program_zero` de sa fonction."""
        self._r.post_providers.append(provider)

    def add_format(self, key: str, label: str, extensions, read: Callable | None = None,
                   write: Callable | None = None, *, export: Callable | None = None, machine: bool = False) -> None:
        """Format de fichier (lecture, écriture ; `export(fenêtre, chemin)` :
        réglages demandés puis écriture ; `machine` : programme machine)."""
        exts = tuple(e.lower() if e.startswith('.') else '.' + e.lower() for e in extensions)
        self._r.formats.append(FormatSpec(key, label, exts, read, write, export, machine, self.info.name))

    def add_strategy(self, kind: str, label: str, fn: Callable) -> None:
        """Stratégie : fn(doc, setup, op, tool, toolpath, emitter, here)."""
        self._r.strategies[kind] = (label, fn)

    def add_cam_preset(self, key: str, label: str, kind: str, settings: dict | None = None,
                       tool_kind: str = 'fraise') -> None:
        """Bouton de la palette « Créer un parcours »."""
        self._r.cam_presets[key] = (label, kind, dict(settings or {}), tool_kind)

    def add_theme(self, theme: dict) -> None:
        """Thème de l'interface (format des fichiers de thème : key, name,
        dark, colors, canvas ; les couleurs absentes sont calculées)."""
        self._r.themes.append(dict(theme))

    def add_tool_library(self, name: str, loader: Callable) -> None:
        """Bibliothèque d'outils : loader() → [CamTool]."""
        self._r.tool_libraries[name] = loader

    def add_templates(self, kind: str, templates: dict) -> None:
        """Gabarits nommés (montages, gammes…) : genre → {nom: données JSON}."""
        self._r.templates.setdefault(kind, {}).update(templates)

    def set_defaults(self, family: str, values: dict) -> None:
        """Réglages par défaut d'une famille (« cljob », « datron »…)."""
        self._r.defaults.setdefault(family, {}).update(values)

    # --- fichiers, distribution ----------------------------------------------------------
    def set_vnd_template(self, path) -> None:
        """VND de départ des dessins neufs enregistrés en VND."""
        self._r.vnd_template = str(path)

    def set_update_manifest(self, name: str) -> None:
        self._r.update_manifest = name

    def add_autotest(self, name: str, fn: Callable) -> None:
        """Vérification de `--autotest` : fn() → texte du résultat (lève en cas d'échec)."""
        self._r.autotests.append((name, fn))


# --- recherche et chargement ---------------------------------------------------------------

def search_dirs() -> list[pathlib.Path]:
    out = []
    try:
        from .portable import app_dir, data_dir
        a = app_dir()
        if a is not None:
            out.append(a / 'plugins')
        out.append(data_dir() / 'plugins')
    except Exception:                               # pragma: no cover - sans Qt
        pass
    for p in (os.environ.get(ENV_PATHS) or '').split(os.pathsep):
        if p.strip():
            out.append(pathlib.Path(p.strip()))
    try:                                            # dossiers choisis dans les options (F10)
        from .portable import settings
        for p in str(settings().value('plugins/dossiers', '') or '').split(';'):
            if p.strip():
                out.append(pathlib.Path(p.strip()))
    except Exception:                               # pragma: no cover - sans Qt
        pass
    return out


def _candidates(d: pathlib.Path) -> list[tuple[pathlib.Path, str]]:
    """(dossier à mettre dans sys.path, nom du module) des plugins d'un
    dossier : `d` lui-même s'il est un paquet, sinon ses sous-paquets et
    ses archives .zip (un paquet à la racine)."""
    if not d.is_dir():
        return []
    if (d / '__init__.py').is_file():
        return [(d.parent, d.name)]
    out = []
    for c in sorted(d.iterdir()):
        if c.is_dir() and (c / '__init__.py').is_file():
            out.append((d, c.name))
        elif c.suffix.lower() == '.zip':
            import zipfile
            try:
                with zipfile.ZipFile(c) as z:
                    names = {n.split('/')[0] for n in z.namelist() if n.count('/') == 1 and n.endswith('/__init__.py')}
            except (OSError, zipfile.BadZipFile):
                continue
            out += [(c, n) for n in sorted(names)]
    return out


def load(dirs: list | None = None, *, force: bool = False) -> list[PluginInfo]:
    """Charge les plugins (une fois). Rend la liste des plugins vus."""
    global _loaded
    if _loaded and not force:
        return REGISTRY.plugins
    _loaded = True
    if os.environ.get(ENV_OFF) == '1':
        return REGISTRY.plugins
    seen = {p.module for p in REGISTRY.plugins}
    for d in (dirs if dirs is not None else search_dirs()):
        for root, name in _candidates(pathlib.Path(d)):
            if name in seen:
                continue
            seen.add(name)
            REGISTRY.plugins.append(load_module(name, root))
    return REGISTRY.plugins


def load_module(name: str, root=None) -> PluginInfo:
    info = PluginInfo(module=name, path=str(root or ''))
    try:
        if root is not None and str(root) not in sys.path:
            sys.path.insert(0, str(root))
        mod = importlib.import_module(name)
        meta = getattr(mod, 'PLUGIN', {}) or {}
        info.name = str(meta.get('nom') or meta.get('name') or name)
        info.version = str(meta.get('version', ''))
        info.licence = str(meta.get('licence') or meta.get('license') or '')
        info.description = str(meta.get('description', ''))
        need = int(meta.get('api', API_VERSION))
        if need != API_VERSION:
            info.error = f'API {need} demandée, VectorDrive fournit l\'API {API_VERSION}'
            return info
        reg = getattr(mod, 'register', None)
        if not callable(reg):
            info.error = 'pas de fonction register(api)'
            return info
        reg(Api(REGISTRY, info))
    except Exception as ex:                         # un plugin ne casse jamais le démarrage
        info.error = f'{type(ex).__name__} : {ex}'
        info.description = info.description or traceback.format_exc(limit=3)
    return info


def reset() -> None:
    """Oublie les plugins chargés (tests)."""
    global _loaded
    REGISTRY.__init__()
    _loaded = False
    from . import i18n
    i18n.refresh_plugins()


def default(family: str, key: str, value):
    """Réglage par défaut d'une famille, éventuellement fourni par un plugin."""
    return REGISTRY.defaults.get(family, {}).get(key, value)
