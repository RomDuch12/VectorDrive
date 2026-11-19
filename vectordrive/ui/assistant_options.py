"""Options (F10) › Assistant (demande du 19/11 matin) : « Assistant a son onglet dans parametres dédié avec full
customization possible (scripts et templates de script, mémoire, affichage console, api gestion) ».

Les réglages simples (fournisseur, modèles, adresse, tours, outils permis, affichage de la discussion, dossier des
modèles de scripts) sont dans `options.SPEC` ; ici, le reste de l'onglet : les clés d'API (gestionnaire d'identifiants
de Windows, jamais les réglages), les consignes personnelles, la mémoire, les dossiers des scripts et des modèles."""
import html
import pathlib

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPlainTextEdit, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout)

from ..i18n import tr

KEY_INSTRUCTIONS = 'assistant/consignes'
KEY_TEMPLATES = 'assistant/dossier_modeles'
#: au plus tant de caractères de consignes personnelles
MAX_INSTRUCTIONS = 4000
#: les groupes d'outils qu'un réglage peut retirer : réglage → groupe de `agent.tools.ToolSet(without=…)`
TOOL_GROUPS = {'assistant/outils_memoire': 'memory', 'assistant/outils_scripts': 'scripts',
               'assistant/outils_commandes': 'commands'}


def instructions(settings) -> str:
    """Les consignes personnelles données à chaque discussion ('' : aucune)."""
    return str(settings.value(KEY_INSTRUCTIONS, '') or '').strip()[:MAX_INSTRUCTIONS]


def without(settings) -> tuple:
    """Les groupes d'outils retirés par les réglages."""
    from .options import value
    return tuple(sorted(g for k, g in TOOL_GROUPS.items() if not value(settings, k)))


def templates_dir(settings=None) -> pathlib.Path:
    """Les modèles de scripts : le dossier choisi dans les options, sinon « modeles » dans le dossier des scripts."""
    from ..core import shapescript as SS
    chosen = str(settings.value(KEY_TEMPLATES, '') or '').strip() if settings is not None else ''
    return pathlib.Path(chosen) if chosen else SS.user_dir() / 'modeles'


def system_text(settings) -> str:
    """Ce qui s'ajoute aux consignes de l'assistant : les consignes personnelles, puis sa mémoire (si permise)."""
    parts = []
    mine = instructions(settings)
    if mine:
        parts.append('Standing instructions from the user (set in the options of the application):\n' + mine)
    if 'memory' not in without(settings):
        from ..agent.tools import memory_prompt
        mem = memory_prompt()
        if mem:
            parts.append(mem)
    return '\n\n'.join(parts)


def seed_templates(folder: pathlib.Path) -> pathlib.Path | None:
    """Le dossier des modèles fait au besoin ; vide de scripts, il reçoit l'exemple de la fenêtre des scripts (jamais
    par-dessus un fichier). Rend le modèle écrit, sinon None."""
    from ..core import shapescript as SS
    from . import script_dialog as SD
    try:
        folder.mkdir(parents=True, exist_ok=True)
        if any(p.suffix.lower() in SS.EXTENSIONS for p in folder.iterdir() if p.is_file()):
            return None
    except OSError:                                      # lecteur absent, droits…
        return None
    example = getattr(SD, '_EXAMPLE', '')
    if not example.strip():
        return None
    path = folder / 'Exemple.vbs'
    try:
        with open(path, 'x', encoding='utf-8', newline='\r\n') as f:
            f.write(example.replace('\r\n', '\n'))
    except OSError:
        return None
    return path


def _open_folder(folder: pathlib.Path, say=None) -> bool:
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as ex:
        if say is not None:
            say(tr('Dossier inaccessible : {0}').format(ex))
        return False
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
    return True


class KeyEdit(QLineEdit):
    """Le champ d'une clé : Entrée la retient, sans valider la fenêtre des options."""

    def __init__(self, on_enter):
        super().__init__()
        self.on_enter = on_enter

    def keyPressEvent(self, ev):                         # noqa: N802 (API Qt)
        from PySide6.QtCore import Qt
        if ev.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.on_enter()
            ev.accept()
            return
        super().keyPressEvent(ev)


def _price_text(v: float) -> str:
    return f'{v:.12g}'


def same_prices(a: dict, b: dict) -> bool:
    return set(a) == set(b) and all(abs(x - y) < 1e-12 for k in a for x, y in zip(a[k], b[k]))


def read_prices(table: QTableWidget) -> dict:
    """Les prix du tableau des options : {"fournisseur:modèle": (entrée, sortie, cache)} ; les lignes sans nom (avec
    « : ») ou aux nombres illisibles sont laissées."""
    out = {}
    for r in range(table.rowCount()):
        cells = [table.item(r, c).text().strip() if table.item(r, c) is not None else '' for c in range(4)]
        if ':' not in cells[0] or not cells[0].split(':', 1)[1].strip():
            continue
        try:
            p = tuple(max(0.0, float((t or '0').replace(',', '.').replace(' ', ''))) for t in cells[1:])
        except ValueError:
            continue
        out[cells[0]] = p
    return out


def _panel(parent):
    """Le panneau de l'assistant de la fenêtre `parent`, s'il est fait."""
    dock = getattr(parent, 'dock_assistant', None)
    w = dock.widget() if dock is not None else None
    return w if hasattr(w, 'apply_settings') else None


def _searchable(dlg, form, box, *words) -> None:
    """La partie `box` trouvée par la recherche des options (mots en français et traduits)."""
    from .options import _fold
    rows = getattr(dlg, '_rows', None)
    if rows is not None:
        rows.append((dlg.tabs.count(), form, box, _fold(' '.join(words))))


def build(dlg, form, parent=None) -> None:
    """La fin de l'onglet Assistant de la fenêtre des options `dlg` (son formulaire `form`) ; ce qui se garde à OK
    passe par `dlg.on_accept`."""
    from ..agent import keys
    from ..agent import tools as AT
    from ..agent.chat import KEY_PAGES, PROVIDERS
    from ..core import shapescript as SS
    st = dlg.settings

    say = getattr(parent, 'statusBar', None)
    say = (lambda text: parent.statusBar().showMessage(text, 8000)) if callable(say) else None

    # --- les clés d'API -------------------------------------------------------------------------------------
    box = QGroupBox(tr('Clés d’API'))
    lay = QVBoxLayout(box)
    note = QLabel(tr('Gardées dans le gestionnaire d’identifiants de Windows, jamais dans les réglages ; retenues ou '
                     'oubliées aussitôt.'))
    note.setWordWrap(True)
    lay.addWidget(note)
    dlg.key_rows = {}
    for slug, (label, _default, _models, env) in PROVIDERS.items():
        row = QHBoxLayout()
        name = QLabel(label)
        name.setMinimumWidth(130)
        state = QLabel()
        keep = QPushButton(tr('Retenir'))
        forget = QPushButton(tr('Oublier la clé'))
        for b in (keep, forget):
            b.setAutoDefault(False)                      # Entrée ne les prend pas
        link = QLabel('<a href="{0}">{1}</a>'.format(html.escape(KEY_PAGES[slug]),
                                                     html.escape(tr('Obtenir une clé d’API'))))
        link.setOpenExternalLinks(False)
        link.linkActivated.connect(lambda url: QDesktopServices.openUrl(QUrl(url)))

        def refresh(slug=slug, state=state, forget=forget, env=env):
            if keys.stored(slug):
                state.setText(tr('Clé : retenue'))
            elif keys.load(slug):
                state.setText(tr('Clé : celle de la variable {0}').format(env))
            else:
                state.setText(tr('Aucune clé'))
            forget.setEnabled(keys.stored(slug))
            panel = _panel(parent)
            if panel is not None:                        # le panneau le dit aussitôt (même si on annule ensuite)
                panel._key_state()

        def save(_=False, slug=slug, refresh=refresh):
            e = dlg.key_rows[slug][1]
            k = e.text().strip()
            if k:
                keys.save(slug, k)
            e.clear()
            refresh()

        def drop(_=False, slug=slug, refresh=refresh):
            keys.forget(slug)
            refresh()
        edit = KeyEdit(save)
        edit.setEchoMode(QLineEdit.EchoMode.Password)
        edit.setPlaceholderText(tr('Clé d’API du fournisseur'))
        keep.clicked.connect(save)
        forget.clicked.connect(drop)
        for w in (name, state):
            row.addWidget(w)
        row.addWidget(edit, 1)
        for w in (keep, forget, link):
            row.addWidget(w)
        lay.addLayout(row)
        dlg.key_rows[slug] = (state, edit, keep, forget, refresh)
        refresh()
    form.addRow(box)
    _searchable(dlg, form, box, 'Clés d’API', tr('Clés d’API'), 'clé cle api key', *PROVIDERS)

    # --- les crédits : le prix des modèles ------------------------------------------------------------------
    from ..agent import credits as CR
    box = QGroupBox(tr('Crédits : prix des modèles'))
    lay = QVBoxLayout(box)
    note = QLabel(tr('Par million de jetons, dans la devise réglée plus haut. D’office, les prix publics relevés le '
                     '19/11/2026 (Mistral : le plus haut des prix trouvés) : à vérifier sur la page du fournisseur. '
                     'Un modèle sans prix compte ses jetons seulement. Les dépenses de la session et du dessin '
                     'affiché sont sous la discussion ; celles d’un dessin sont gardées dans son .vdz.'))
    note.setWordWrap(True)
    lay.addWidget(note)
    table = QTableWidget(0, 4)
    table.setHorizontalHeaderLabels([tr('Fournisseur:modèle'), tr('Prix en entrée'), tr('Prix en sortie'),
                                     tr('Prix en entrée lue en cache')])
    table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    table.verticalHeader().hide()
    table.setMinimumHeight(160)

    def add_row(key: str = '', p=(0.0, 0.0, 0.0)) -> int:
        r = table.rowCount()
        table.insertRow(r)
        table.setItem(r, 0, QTableWidgetItem(key))
        for c, v in enumerate(p, 1):
            table.setItem(r, c, QTableWidgetItem(_price_text(v)))
        return r

    def fill(prices: dict) -> None:
        table.setRowCount(0)
        for k, p in prices.items():
            add_row(k, p)

    def new_row(_=False) -> None:
        r = add_row(PROVIDERS and 'mistral:', (0.0, 0.0, 0.0))
        table.setCurrentCell(r, 0)
        table.editItem(table.item(r, 0))

    def drop_row(_=False) -> None:
        if table.currentRow() >= 0:
            table.removeRow(table.currentRow())
    fill(CR.prices(st))
    lay.addWidget(table)
    row = QHBoxLayout()
    for text, fn in ((tr('Ajouter un modèle'), new_row), (tr('Retirer la ligne'), drop_row),
                     (tr('Prix d’office'), lambda _=False: fill(dict(CR.PRICES)))):
        b = QPushButton(text)
        b.setAutoDefault(False)
        b.clicked.connect(fn)
        row.addWidget(b)
    row.addStretch(1)
    lay.addLayout(row)
    dlg.assistant_prices = table
    prices_before = CR.prices(st)
    form.addRow(box)
    _searchable(dlg, form, box, 'Crédits : prix des modèles', tr('Crédits : prix des modèles'),
                'credits crédits prix jetons tokens cout coût mistral')

    # --- les consignes personnelles -------------------------------------------------------------------------
    box = QGroupBox(tr('Consignes personnelles'))
    lay = QVBoxLayout(box)
    note = QLabel(tr('Données à chaque nouvelle discussion, en plus des siennes (par exemple : « réponds en peu de '
                     'mots », « mes plaques font 0,8 mm »).'))
    note.setWordWrap(True)
    lay.addWidget(note)
    dlg.assistant_instructions = QPlainTextEdit(instructions(st))
    dlg.assistant_instructions.setMinimumHeight(80)
    lay.addWidget(dlg.assistant_instructions)
    form.addRow(box)
    _searchable(dlg, form, box, 'Consignes personnelles', tr('Consignes personnelles'), 'assistant consignes')

    # --- la mémoire ---------------------------------------------------------------------------------------------
    box = QGroupBox(tr('Mémoire de l’assistant'))
    lay = QVBoxLayout(box)
    note = QLabel(tr('Ce qu’il retient d’une discussion à l’autre (il l’écrit quand vous le lui demandez) : {0}')
                  .format(AT.memory_path()))
    note.setWordWrap(True)
    lay.addWidget(note)
    before = AT.memory_text()
    dlg.assistant_memory = QPlainTextEdit(before)
    dlg.assistant_memory.setMinimumHeight(100)
    lay.addWidget(dlg.assistant_memory)
    clear = QPushButton(tr('Effacer la mémoire'))
    clear.setAutoDefault(False)
    clear.setToolTip(tr('Vide le texte ci-dessus ; effacée à OK'))
    clear.clicked.connect(lambda _=False: dlg.assistant_memory.setPlainText(''))
    row = QHBoxLayout()
    row.addWidget(clear)
    row.addStretch(1)
    lay.addLayout(row)
    form.addRow(box)
    _searchable(dlg, form, box, 'Mémoire de l’assistant', tr('Mémoire de l’assistant'), 'memoire')

    # --- les scripts et leurs modèles ---------------------------------------------------------------------------
    box = QGroupBox(tr('Scripts de forme et modèles'))
    lay = QVBoxLayout(box)
    note = QLabel(tr('L’assistant liste, lit et lance les scripts de forme, et en enregistre de nouveaux (jamais par-'
                     'dessus un script) ; les modèles lui servent d’exemples. Scripts : {0}').format(SS.user_dir()))
    note.setWordWrap(True)
    lay.addWidget(note)
    row = QHBoxLayout()
    b = QPushButton(tr('Ouvrir le dossier des scripts'))
    b.setAutoDefault(False)
    b.clicked.connect(lambda _=False: _open_folder(SS.user_dir(), say))
    row.addWidget(b)
    b = QPushButton(tr('Ouvrir le dossier des modèles'))
    b.setAutoDefault(False)
    b.setToolTip(tr('Fait au besoin, avec un premier modèle s’il est vide'))
    b.clicked.connect(lambda _=False: (seed_templates(templates_dir(st)), _open_folder(templates_dir(st), say)))
    row.addWidget(b)
    row.addStretch(1)
    lay.addLayout(row)
    form.addRow(box)
    _searchable(dlg, form, box, 'Scripts de forme et modèles', tr('Scripts de forme et modèles'), 'scripts modeles')

    if parent is not None and hasattr(parent, 'agent_dialog'):
        b = QPushButton(tr('Assistant (serveur MCP)…'))
        b.setAutoDefault(False)
        b.setToolTip(tr('Brancher un assistant (Claude Code…) sur le dessin ouvert : il le lit et peut y dessiner'))
        b.clicked.connect(lambda _=False: parent.agent_dialog())
        form.addRow(b)
        _searchable(dlg, form, b, 'Assistant (serveur MCP)', tr('Assistant (serveur MCP)…'), 'mcp')

    def keep():
        st.setValue(KEY_INSTRUCTIONS, dlg.assistant_instructions.toPlainText().strip()[:MAX_INSTRUCTIONS])
        now_prices = read_prices(dlg.assistant_prices)
        if not same_prices(now_prices, prices_before):   # inchangés : les réglages n'en gardent pas (prix d'office)
            CR.save_prices(st, now_prices)
        text = dlg.assistant_memory.toPlainText()
        if text == before:
            return
        now = AT.memory_text()
        if now != before:                                # l'assistant l'a écrite pendant ce temps
            if now.startswith(before):                   # il y a ajouté : son ajout gardé après le texte corrigé
                text = text.rstrip('\n') + '\n' + now[len(before):].lstrip('\n')
            else:                                        # il l'a réécrite : la sienne gardée, rien d'écrasé
                if say is not None:
                    say(tr('Mémoire non changée : l’assistant l’a réécrite pendant ce temps (rouvrez les options)'))
                return
        try:
            AT.write_memory(text[:AT.MAX_MEMORY])
        except OSError as ex:
            if say is not None:
                say(str(ex))
    dlg.on_accept.append(keep)
