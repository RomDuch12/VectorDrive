"""Plugins : ce qui est propre à un atelier vit hors du cœur.

Voir `docs/ARCHITECTURE.md`. Un plugin est un paquet Python qui expose
`PLUGIN` (métadonnées) et `register(api)` ; `api` est une `Api`, la seule
porte d'entrée vers le cœur. Ce qu'il apporte est rangé dans `REGISTRY`,
que le cœur consulte (raccourcis, actions, post-processeurs, stratégies…).

Recherche (`load`) : dossiers `plugins/` à côté de l'application et dans
les données de l'utilisateur, puis `VECTORDRIVE_PLUGINS` (chemins séparés
par `;`). `VECTORDRIVE_NO_PLUGINS=1` désactive tout. Un plugin en erreur
est noté (`PluginInfo.error`) et n'empêche jamais le démarrage.

Ajout (`install`, Options › Plugins › « Ajouter un plugin… ») : l'archive
.zip d'un plugin — ses paquets à la racine, les bibliothèques Python qu'il
apporte dans `_lib/` — est décompressée dans le dossier des plugins de
l'utilisateur (`user_dir`) ; le plugin est chargé au démarrage suivant.
Le dossier `_lib` d'un dossier de plugins (ou d'une archive qui y est
rangée) est ajouté à la fin de `sys.path` avant le chargement.

Fabrication (`build_archive`, `outils/plugin_zip.py`) : l'archive ajoutable
d'un plugin, son paquet et ses bibliothèques Python pures.
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
    short: str = ''                 # libellé court, pour l'onglet du panneau (vide : le début du titre)
    host: str = ''                  # 'programme' : une partie repliable de l'onglet Programme, pas un panneau à part


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
    #: page des prix du BAT (question 29) : fonction(dessin, gravures, réglage du BAT) → (titre, [lignes]) ou None
    bat_pages: list = field(default_factory=list)
    nc_readers: list = field(default_factory=list)           # (libellé, extensions, lecture, reconnaissance)
    #: catalogues d'opérations machine : (libellé, fonction() → [cam.catalog.Entry ou dict])
    instruction_catalogs: list = field(default_factory=list)
    panels: list = field(default_factory=list)               # PanelSpec
    post_hooks: list = field(default_factory=list)           # fonction(window, clé de la machine) : machine changée
    #: export propre à une machine : clé de post → fonction(panneau FAO, parcours, réglage) → vrai si fait
    post_exports: dict = field(default_factory=dict)
    machines: list = field(default_factory=list)             # MachineSpec : fraiseuses et lasers du ruban FAO
    #: opérations d'un plugin dans la liste des opérations FAO : clé → fournisseur (`cam.external`)
    op_providers: dict = field(default_factory=dict)


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
                        clear: Callable | None = None, dirs=(), clonable: bool = False,
                        filter_label: str = '') -> None:
        """Un format de polices propriétaire, lu sur le poste (jamais redistribué) : `extensions` ('.xyz', …) ;
        `label` : l'infobulle de ses polices dans les listes ; `filter_label` : le libellé court (« TypeEdit ») de
        leur filtre et de leur section dans la liste des polices — les formats d'un même libellé se partagent le
        filtre ; sans lui, elles vont avec « Plugins » ; `font_name(chemin)` → nom ou None ;
        `glyph(chemin, caractère)` → (Path, avance) ; `metrics(chemin)` → {'upem', 'ascent', 'descent', 'cap'} ;
        `kerning(chemin, gauche, droite)` ; `characters(chemin)` → codes ; `clear()` : oublier ce qui est lu ;
        `dirs` : ses dossiers ; `clonable` : l'éditeur de polices peut partir de ses polices."""
        from .core import fontformats
        exts = tuple(str(e).lower() for e in extensions)
        self._r.font_formats.append((label, exts))
        fontformats.register(fontformats.FontFormat(
            label=label, extensions=exts, font_name=font_name, glyph=glyph, metrics=metrics, kerning=kerning,
            characters=characters, clear=clear, dirs=tuple(pathlib.Path(d) for d in dirs), clonable=clonable,
            reader=f'{self.info.module} {self.info.version}', filter_label=str(filter_label or '').strip()))

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

    def add_panel(self, key: str, title: str, factory: Callable, *, posts=(), area: str = 'droite',
                  short: str = '', host: str = '') -> None:
        """Panneau ancré (`factory(window)` → QWidget), montré seulement pour
        les machines `posts` (vide : toujours) — les fonctions d'une machine
        qui apparaissent quand on la choisit. `short` : son libellé court, écrit
        sur son onglet quand il partage une colonne (sinon : le début du titre).
        `host` 'programme' : pas de panneau à part, une partie repliable de
        l'onglet Programme (au-dessus du texte du programme), montrée pour ses
        machines seulement (atelier SimPL, 17/11)."""
        self._r.panels.append(PanelSpec(key, title, factory, tuple(posts or ()), area, self.info.name,
                                        str(short or ''), str(host or '')))

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

    def add_bat_page(self, fn: Callable) -> None:
        """Page des prix du BAT (réponse du 15/11 à la question 29 : « BaT + devis devient un pdf de 2 pages
        (technique séparé prix) ») : `fn(dessin, gravures, réglage du BAT)` → (titre, [lignes]) ou None (pas de
        devis réglé). Quand elle en donne une, le BAT a deux pages et la page technique n'a plus de prix. Une ligne
        qui commence par des espaces est décalée d'autant."""
        self._r.bat_pages.append(fn)

    def add_translations(self, lang: str, table: dict) -> None:
        self._r.translations.setdefault(lang, {}).update(table)
        from . import i18n
        i18n.refresh_plugins()

    # --- FAO -------------------------------------------------------------------------
    def add_post(self, key: str, label: str, write: Callable) -> None:
        """Post-processeur : write(toolpaths, setup, *, title, machine, stem, box_mm) → PostResult."""
        self._r.posts[key] = (label, write)

    def add_operation_provider(self, key: str, provider) -> None:
        """Opérations du plugin dans la liste des opérations du panneau FAO, à leur place dans le programme (une liste
        unique : réponse du 17/11 à la question 48 ; `cam.external`). `provider.rows(dessin)` → [{'ref' (unique, gardé
        dans le dessin), 'label', 'tool', 'tip', 'enabled'}] ; facultatifs : `provider.label` (colonne Stratégie),
        `provider.posts` (clés des post-processeurs qui les écrivent ; vide : tous), `set_enabled(dessin, ref, oui)`,
        `edit(fenêtre, ref)` (double clic, Modifier), `reload(fenêtre, ref, identifiants des formes)` → vrai si fait
        (⟳), `remove(fenêtre, ref)` → vrai si retirée (Suppr), `rename(dessin, ref, nom)` → vrai si renommée (double
        clic sur le nom, Renommer… ; avec `renamable(dessin, ref)` → faux : la ligne ne se renomme pas et son double
        clic l'ouvre ; `name_of(dessin, ref)` : le nom proposé ; `undo_keys` : les clés de `doc.extra` que Ctrl+Z
        rend). Une ligne neuve s'ajoute en fin de liste ; ↑ / ↓ la
        placent entre les parcours ; le post-processeur reçoit, à son rang, un parcours dont le cycle est
        `{'kind': 'instruction', 'name': 'externe', 'params': {'provider', 'ref', …}}`. Le plugin rafraîchit la liste
        (`fenêtre.cam_panel.refresh()`) quand ses opérations changent."""
        self._r.op_providers[key] = provider

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

    def add_work_folder(self, key: str, label: str, *, last_key: str = '', tip: str = '') -> None:
        """Une ligne de F10 › Dossiers de travail (dossiers clients…) : le dernier utilisé ou toujours ce dossier.
        Le plugin prend son dossier de départ par `vectordrive.ui.workdirs.start_folder(settings, key, …)` et retient
        son dernier dossier dans `last_key` (vide : « dossier/<key> »)."""
        from .ui import workdirs
        workdirs.register(key, label, last_key=last_key, tip=tip)

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
        if c.is_dir() and c.name != LIB and (c / '__init__.py').is_file():
            out.append((d, c.name))
        elif c.suffix.lower() == '.zip':
            import zipfile
            try:
                with zipfile.ZipFile(c) as z:
                    names = {n.split('/')[0] for n in z.namelist() if n.count('/') == 1 and n.endswith('/__init__.py')
                             and not n.startswith(LIB + '/')}
            except (OSError, *_zip_errors()):                # une archive abîmée n'empêche pas le démarrage
                continue
            out += [(c, n) for n in sorted(names)]
    return out


#: dossier des bibliothèques Python (paquets purs : openpyxl…) qu'un plugin apporte avec lui, à la racine de son
#: archive ou d'un dossier de plugins ; jamais pris pour un plugin
LIB = '_lib'


def _zip_names(archive) -> list[str]:
    import zipfile
    try:
        with zipfile.ZipFile(archive) as z:
            return z.namelist()
    except (OSError, *_zip_errors()):
        return []


def _add_libs(d: pathlib.Path) -> None:
    """Ajoute à la fin de sys.path (les bibliothèques du cœur restent prioritaires) le dossier `_lib` de `d` et celui
    de chaque archive .zip de `d` qui en a un."""
    if not d.is_dir():
        return
    libs = [d / LIB] if (d / LIB).is_dir() else []
    for c in _zips(d):
        if any(n.replace(chr(92), '/').startswith(LIB + '/') for n in _zip_names(c)):
            libs.append(c / LIB)
    for lib in libs:
        if str(lib) not in sys.path:
            sys.path.append(str(lib))


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
        _add_libs(pathlib.Path(d))
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


# --- ajout d'un plugin (« Ajouter un plugin… ») ---------------------------------------------------------------------

class ArchiveError(ValueError):
    """Archive de plugin refusée ; `kind` : 'illisible' (archive abîmée, chiffrée…), 'vide' (aucun plugin), 'reserve'
    (nom du cœur), 'chemin' (un chemin sortirait du dossier), 'paquet' (un paquet de la racine qui n'est pas un plugin :
    sa place est dans `_lib`) ; `detail` : le fichier ou le nom en cause."""

    def __init__(self, kind: str, detail: str = ''):
        super().__init__(f'{kind} : {detail}' if detail else kind)
        self.kind = kind
        self.detail = detail


def user_dir() -> pathlib.Path:
    """Le dossier où « Ajouter un plugin… » range les plugins : `plugins` des données de l'utilisateur."""
    from .portable import data_dir
    return data_dir() / 'plugins'


def _zip_errors() -> tuple:
    """Erreurs de lecture d'une archive (abîmée, chiffrée, compression inconnue, nom de membre mal encodé)."""
    import zipfile
    import zlib
    return (zipfile.BadZipFile, RuntimeError, NotImplementedError, EOFError, zlib.error, UnicodeDecodeError)


def _zips(d: pathlib.Path) -> list[pathlib.Path]:
    """Archives .zip de `d` (« .ZIP » compris, comme `_candidates`, sous macOS aussi)."""
    if not d.is_dir():
        return []
    return sorted(c for c in d.iterdir() if c.suffix.lower() == '.zip' and c.is_file())


def _entries(z) -> list:
    """(membre, nom) de l'archive, le nom écrit avec « / » sur tous les systèmes (une archive faite sous Windows peut
    avoir des « \\ » : zipfile ne les change que sous Windows)."""
    return [(info, info.filename.replace(chr(92), '/')) for info in z.infolist()]


def _root_packages(z) -> dict:
    """{paquet de la racine de l'archive : est un plugin (son __init__.py nomme register)}, sans `_lib`."""
    import re
    out = {}
    for info, name in _entries(z):
        parts = name.split('/')
        if len(parts) == 2 and parts[1] == '__init__.py' and parts[0] not in ('', LIB):
            out[parts[0]] = re.search(r'\bregister\b', z.read(info).decode('utf-8', 'replace')) is not None
    return out


def archive_plugins(archive) -> list[str]:
    """Paquets de plugin d'une archive .zip : les dossiers de sa racine dont le `__init__.py` nomme `register` (pas
    `_lib`)."""
    import zipfile
    try:
        with zipfile.ZipFile(archive) as z:
            return sorted(n for n, plugin in _root_packages(z).items() if plugin)
    except (OSError, *_zip_errors()) as ex:
        raise ArchiveError('illisible', str(ex)) from ex


def archives_with(dest, pkgs) -> list[pathlib.Path]:
    """Archives .zip de `dest` qui apportent un des paquets `pkgs` (gardées par `install` quand elles apportent aussi
    un autre plugin)."""
    out = []
    for c in _zips(pathlib.Path(dest)):
        try:
            if set(archive_plugins(c)) & set(pkgs):
                out.append(c)
        except ArchiveError:
            continue
    return out


def _set_aside_name(c: pathlib.Path) -> pathlib.Path:
    """« X.zip.ancien », ou « X.zip.ancien2 »… si une copie est déjà gardée sous ce nom."""
    p, k = c.with_name(c.name + '.ancien'), 2
    while p.exists():
        p, k = c.with_name(f'{c.name}.ancien{k}'), k + 1
    return p


def _place(tmp: pathlib.Path, dest: pathlib.Path, pkgs: list[str]) -> None:
    """Les paquets et `_lib` décompressés dans `tmp` prennent leur place dans `dest`, d'un bloc : chaque entrée de la
    racine de `_lib` remplace la même (une bibliothèque, aussi ses anciens « .dist-info »), chaque paquet le même.
    Ce qui est remplacé est d'abord mis de côté dans un dossier « .anciens_… » de `dest` (sans __init__.py : jamais pris
    pour un plugin) ; si une pose échoue (fichier en service, antivirus…), tout est remis comme avant, et si même cela
    échoue, rien n'est effacé : l'ancienne version reste dans ce dossier, dit par l'erreur. Lève `OSError`."""
    import shutil
    import tempfile
    pairs = []                                       # (nouveau, sa place, ce qu'il remplace)
    lib = tmp / LIB
    if lib.is_dir():
        (dest / LIB).mkdir(exist_ok=True)
        for item in sorted(lib.iterdir()):
            old = [dest / LIB / item.name]
            if item.name.endswith('.dist-info'):
                old += sorted((dest / LIB).glob(item.name.split('-')[0] + '-*.dist-info'))
            pairs.append((item, dest / LIB / item.name, old))
    pairs += [(tmp / name, dest / name, [dest / name]) for name in pkgs]
    aside = pathlib.Path(tempfile.mkdtemp(prefix='.anciens_', dir=dest))
    moved, placed = [], []
    try:
        for src, target, old in pairs:
            for p in dict.fromkeys(old):
                if p.exists() or p.is_symlink():
                    keep = aside / str(len(moved))
                    p.replace(keep)
                    moved.append((p, keep))
            src.replace(target)
            placed.append((target, src))
    except OSError as ex:
        lost = []
        for target, src in reversed(placed):
            try:
                target.replace(src)
            except OSError:
                lost.append(target)
        for p, keep in reversed(moved):
            try:
                keep.replace(p)
            except OSError:
                lost.append(p)
        if lost:
            raise OSError(f'{ex} ; remise en place impossible ({", ".join(p.name for p in lost)}) : l’ancienne '
                          f'version est gardée dans {aside}') from ex
        shutil.rmtree(aside, ignore_errors=True)
        raise
    shutil.rmtree(aside, ignore_errors=True)


def install(archive, dest=None) -> list[str]:
    """Ajoute le plugin de l'archive .zip `archive` au dossier `dest` (d'office `user_dir()`) et rend les noms de ses
    paquets. Ses paquets et son dossier `_lib` sont décompressés (rien d'autre de l'archive), puis prennent la place de
    ceux du même nom (`_place`) ; une archive rangée dans `dest` qui n'apporte que ces paquets — celle choisie
    comprise — est renommée en « .zip.ancien » (sinon elle serait chargée à la place ; celle qui apporte aussi un
    autre plugin est gardée : `archives_with`). Le plugin est chargé au prochain démarrage. Lève `ArchiveError`
    (archive refusée, rien de changé) ou `OSError` (écriture impossible, voir `_place`)."""
    import shutil
    import tempfile
    import zipfile
    archive = pathlib.Path(archive)
    dest = pathlib.Path(dest) if dest is not None else user_dir()
    try:
        z = zipfile.ZipFile(archive)
    except (OSError, *_zip_errors()) as ex:
        raise ArchiveError('illisible', str(ex)) from ex
    with z:
        try:
            roots = _root_packages(z)
            pkgs = sorted(n for n, plugin in roots.items() if plugin)
            if not pkgs:
                raise ArchiveError('vide', archive.name)
            if 'vectordrive' in roots:
                raise ArchiveError('reserve', 'vectordrive')
            others = sorted(n for n, plugin in roots.items() if not plugin)
            if others:
                raise ArchiveError('paquet', ', '.join(others))
            keep = set(pkgs) | {LIB}
            members = []
            for info, name in _entries(z):
                parts = pathlib.PurePosixPath(name).parts
                if not parts or parts[0] not in keep:
                    continue
                if name.startswith('/') or '..' in parts or ':' in name:
                    raise ArchiveError('chemin', info.filename)
                members.append((info, parts, name.endswith('/')))
            dest.mkdir(parents=True, exist_ok=True)
            tmp = pathlib.Path(tempfile.mkdtemp(prefix='.ajout_', dir=dest))
            try:
                for info, parts, is_dir in members:      # un à un, sous le nom en « / » (pas z.extract)
                    target = tmp.joinpath(*parts)
                    if is_dir:
                        target.mkdir(parents=True, exist_ok=True)
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(info) as src, open(target, 'wb') as out:
                        shutil.copyfileobj(src, out)
                _place(tmp, dest, pkgs)
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
        except _zip_errors() as ex:
            raise ArchiveError('illisible', str(ex)) from ex
    for c in archives_with(dest, pkgs):                  # après la fermeture de l'archive (Windows)
        try:
            if set(archive_plugins(c)) <= set(pkgs):
                c.replace(_set_aside_name(c))
        except (ArchiveError, OSError):
            continue
    return pkgs


# --- fabrication de l'archive d'un plugin (outils/plugin_zip.py) -----------------------------------------------------

#: extensions des fichiers compilés : propres à un système (Windows, macOS…), une bibliothèque qui en a ne marcherait pas
#: partout
COMPILED = ('.pyd', '.so', '.dylib', '.dll')


def _skipped(rel: pathlib.PurePath) -> bool:
    """Fichier laissé hors de l'archive : un « .pyc », un fichier caché (.DS_Store…) ou ce qui est dans `__pycache__`
    ou un dossier caché (.git…)."""
    return (rel.suffix.lower() in ('.pyc', '.pyo')
            or any(part == '__pycache__' or part.startswith('.') for part in rel.parts))


def _tree(top: pathlib.Path, arc: str) -> list:
    """(fichier, nom dans l'archive) des fichiers du dossier `top`, rangés sous `arc`, dans l'ordre."""
    out = []
    for f in sorted(top.rglob('*')):
        rel = f.relative_to(top)
        if f.is_file() and not _skipped(rel):
            out.append((f, f'{arc}/{rel.as_posix()}'))
    return out


#: noms que Windows réserve (avec ou sans extension) : un fichier de ce nom ne s'y écrit pas
_RESERVED = {'con', 'prn', 'aux', 'nul', *(f'{d}{i}' for d in ('com', 'lpt') for i in (*range(1, 10), '¹', '²', '³'))}


def _unportable(name: str) -> str:
    """Pourquoi le nom `name` (chemin en « / » de l'archive) ne se décompresserait pas partout — « Ajouter un
    plugin… » le refuserait, ou Windows ne pourrait pas l'écrire (une archive faite sous macOS ou Linux) ; '' s'il
    le peut."""
    for part in name.split('/'):
        if part in ('', '.', '..'):
            return 'chemin vide ou relatif'
        if any(c in '<>:"|?*' + chr(92) or ord(c) < 32 for c in part):
            return 'caractère interdit sous Windows'
        if part[-1] in ' .':
            return 'nom fini par un point ou une espace'
        if part.split('.')[0].rstrip(' ').lower() in _RESERVED:      # « con .txt » aussi (l'espace est ôtée)
            return 'nom réservé par Windows'
    return ''


def _case_clash(names) -> tuple:
    """Deux chemins de `names` (fichiers, ou leurs dossiers) qui ne diffèrent que par la casse — un seul sous Windows
    et macOS (`pkg/a` et `pkg/A/b.py` aussi) ; () s'il n'y en a pas."""
    seen = {}
    for name in names:
        parts = name.split('/')
        for k in range(1, len(parts) + 1):
            prefix = '/'.join(parts[:k])
            if seen.setdefault(prefix.lower(), prefix) != prefix:
                return seen[prefix.lower()], prefix
    return ()


def _true_name(folder: pathlib.Path) -> str:
    """Le nom du dossier tel qu'il est sur le disque, pas tel qu'il est tapé (Windows et macOS ignorent la casse) ;
    un lien symbolique garde son propre nom (pas celui de sa cible)."""
    p = pathlib.Path(os.path.abspath(folder))
    try:
        same = [c.name for c in p.parent.iterdir() if c.name.lower() == p.name.lower() and os.path.samefile(c, p)]
    except OSError:
        same = []
    return p.name if p.name in same or not same else same[0]


def _inside(path: pathlib.Path, folder: pathlib.Path) -> bool:
    """`path` est rangé dans `folder` (ou un de ses sous-dossiers) — liens et casse compris (le chemin tel qu'il est
    donné et tel que les liens le résolvent)."""
    given = pathlib.Path(os.path.abspath(path))
    for d in (*given.parents, *pathlib.Path(os.path.realpath(given)).parents):
        try:
            if d.exists() and os.path.samefile(d, folder):
                return True
        except OSError:
            continue
    return False


def _lib_files(name: str, memo: dict | None = None) -> list:
    """(fichier, nom dans l'archive) de la bibliothèque pure `name` (un module de premier niveau importable sur ce
    poste : openpyxl…) et de ses « .dist-info », rangés dans `_lib`. `memo` garde, le temps d'une archive, la table
    des distributions du poste (longue à lire). Lève `ValueError` : nom invalide, introuvable, bibliothèque standard,
    nom du cœur, bibliothèque compilée."""
    import importlib.metadata as md
    import importlib.util
    if not name.isidentifier():
        raise ValueError(f'{name} : nom de module attendu (openpyxl…)')
    if name.lower() in ('vectordrive', LIB):
        raise ValueError(f'{name} : nom réservé au cœur')
    if name in sys.stdlib_module_names or name in sys.builtin_module_names:
        raise ValueError(f'{name} : bibliothèque standard de Python, déjà dans VectorDrive')
    try:
        spec = importlib.util.find_spec(name)
    except (ImportError, ValueError):
        spec = None
    if spec is None:
        raise ValueError(f'{name} : bibliothèque introuvable sur ce poste')

    def refuse(f: pathlib.Path):
        raise ValueError(f'{name} : bibliothèque compilée ({f.name}) — propre à un système, elle ne marcherait pas '
                         f'partout')

    if spec.submodule_search_locations:                      # un paquet (ou un paquet d'espace de noms)
        tops = [pathlib.Path(loc) for loc in spec.submodule_search_locations]
        for top in tops:
            if not top.is_dir():
                raise ValueError(f'{name} : bibliothèque hors d’un dossier ({top})')
            hit = next((f for f in top.rglob('*') if f.suffix.lower() in COMPILED), None)   # dès le premier
            if hit is not None:
                refuse(hit)
        out = [item for top in tops for item in _tree(top, f'{LIB}/{name}')]
        parent = tops[0].parent
    elif spec.origin and pathlib.Path(spec.origin).is_file():
        f = pathlib.Path(spec.origin)
        if f.suffix.lower() in COMPILED:
            refuse(f)
        out, parent = [(f, f'{LIB}/{f.name}')], f.parent
    else:
        raise ValueError(f'{name} : bibliothèque intégrée à Python, déjà dans VectorDrive')
    # ses « .dist-info » : celui à son nom à côté d'elle (openpyxl-3.1.5.dist-info), sinon ceux que lui attribue
    # importlib.metadata (PyYAML pour yaml… : plus long, toutes les bibliothèques du poste sont lues)
    dists = [md.PathDistribution(d) for d in sorted(parent.glob('*.dist-info'))
             if d.is_dir() and d.name.split('-')[0].lower() == name.lower()]
    if not dists:
        memo = {} if memo is None else memo
        if 'distributions' not in memo:
            memo['distributions'] = md.packages_distributions()
        for dist_name in dict.fromkeys(memo['distributions'].get(name, [])):
            try:
                dists.append(md.distribution(dist_name))
            except md.PackageNotFoundError:
                continue
    for dist in dists:
        for f in dist.files or []:
            rel = pathlib.PurePosixPath(str(f).replace(chr(92), '/'))     # RECORD aux barres inverses (certains pip)
            if len(rel.parts) > 1 and rel.parts[0].endswith('.dist-info'):
                p = pathlib.Path(dist.locate_file(rel.as_posix()))
                if p.is_file():
                    out.append((p, f'{LIB}/{rel.as_posix()}'))
    return out


def build_archive(package, out, libs=()) -> pathlib.Path:
    """Écrit `out`, l'archive .zip du plugin `package` à ajouter par « Ajouter un plugin… » (`install`), sous Windows
    comme sous macOS, et rend son chemin : le paquet (le dossier, dont le __init__.py nomme `register`) à la racine,
    sans `__pycache__`, « .pyc » ni fichiers cachés ; dans `_lib`, chaque bibliothèque de `libs` (modules de premier
    niveau importables sur ce poste, pures : openpyxl…) avec ses « .dist-info ». Le paquet prend le nom de son
    dossier sur le disque ; chaque nom de l'archive y est une fois (le premier) et doit pouvoir s'écrire partout
    (`_unportable`, casse comprise). L'archive est écrite à côté puis relue (`archive_plugins`) avant de prendre la
    place de `out`. Lève `ValueError` (rien d'écrit) : pas un plugin, nom réservé, bibliothèque introuvable, standard
    ou compilée (`COMPILED`), nom de fichier impossible ailleurs, sortie dans le paquet ; `OSError`."""
    import re
    import zipfile
    package, out = pathlib.Path(package), pathlib.Path(out)
    init = package / '__init__.py'
    if not init.is_file():
        raise ValueError(f'{package} : pas un paquet Python (pas de __init__.py)')
    name = _true_name(package)
    if not name.isidentifier() or name.lower() in ('vectordrive', LIB):     # « _Lib » : le même dossier ailleurs
        raise ValueError(f'{name} : nom de paquet invalide ou réservé au cœur')
    if re.search(r'\bregister\b', init.read_text(encoding='utf-8', errors='replace')) is None:
        raise ValueError(f'{name} : pas un plugin (son __init__.py ne définit pas register)')
    if _inside(out, package):
        raise ValueError(f'{out} : l’archive ne peut pas être rangée dans le paquet')
    files, memo = _tree(package, name), {}
    for lib in dict.fromkeys(libs):
        if lib == name:
            raise ValueError(f'{lib} : c’est le plugin lui-même')
        files += _lib_files(lib, memo)
    first = {}
    for f, arc in files:                                     # un nom une fois : le premier (deux bibliothèques d'une
        first.setdefault(arc, (f, arc))                      # même distribution ont les mêmes « .dist-info »)
    files = list(first.values())
    for f, arc in files:
        why = _unportable(arc)
        if why:
            raise ValueError(f'{arc} : {why} — l’archive ne s’ajouterait pas partout')
    clash = _case_clash(arc for _, arc in files)
    if clash:
        raise ValueError(f'{clash[1]} et {clash[0]} ne diffèrent que par la casse — un seul sous Windows et macOS')
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + '.tmp')
    try:
        # strict_timestamps=False : un fichier daté d'avant 1980 (copié d'une archive…) prend le 1/1/1980
        with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED, strict_timestamps=False) as z:
            for f, arc in files:
                z.write(f, arc)
        got = archive_plugins(tmp)
        if got != [name]:
            raise ValueError(f'{out.name} : l’archive relue apporte {got or "aucun plugin"} au lieu de {name}')
        tmp.replace(out)
    finally:
        tmp.unlink(missing_ok=True)
    return out


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
