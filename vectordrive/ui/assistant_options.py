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
               'assistant/outils_commandes': 'commands', 'assistant/outils_fao': 'cam',
               'assistant/outils_copies': 'copies', 'assistant/outils_step': 'step'}


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


def system_text(settings, removed=None) -> str:
    """Ce qui s'ajoute aux consignes de l'assistant : les consignes personnelles, puis sa mémoire (si permise) ;
    `removed` : les groupes d'outils retirés, s'ils ne sont pas ceux des options (un bouton IA)."""
    parts = []
    mine = instructions(settings)
    if mine:
        parts.append('Standing instructions from the user (set in the options of the application):\n' + mine)
    if 'memory' not in (without(settings) if removed is None else removed):
        from ..agent.tools import memory_prompt
        mem = memory_prompt()
        if mem:
            parts.append(mem)
        from ..agent.memories import prompt as topics_prompt
        topics = topics_prompt()                         # les mémoires thématiques : titres et descriptions
        if topics:
            parts.append(topics)
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


#: le réglage de la mémoire de carte graphique trouvée (Go ; 0 : inconnue) par « Détecter la carte graphique »
KEY_GPU = 'assistant/gpu_local'


def _tier_notes() -> dict:
    """Ce qu'il faut savoir de chaque palier (traduit)."""
    return {'ministral-3:3b': tr('rapide ; outils et images ; demandes simples'),
            'ministral-3:8b': tr('bon équilibre ; outils et images'),
            'ministral-3:14b': tr('plus sûr sur les demandes en plusieurs étapes'),
            'mistral-small3.2:24b': tr('le plus capable ; juste sur 16 Go (une partie passe par la mémoire du poste, '
                                       'plus lent)')}


def _local_box(dlg, form, parent=None) -> None:
    """« Mistral en local (Ollama) » (demande du 22/11) : le palier de la carte graphique (4, 8, 12, 16 Go), l'état
    d'Ollama, Démarrer, Télécharger le modèle (une console que l'utilisateur voit), Utiliser ce modèle (fournisseur
    et modèle des options, gardés à OK)."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QComboBox
    from ..agent import local_models as LM
    from ..i18n import decimal_sep
    st = dlg.settings
    box = QGroupBox(tr('Mistral en local (Ollama)'))
    lay = QVBoxLayout(box)
    note = QLabel(tr('Un modèle Mistral sur ce poste, par Ollama : sans clé ni crédit, et le dessin reste à '
                     'l’atelier. Choisissez le palier de votre carte graphique, téléchargez le modèle une fois, puis '
                     '« Utiliser ce modèle ».'))
    note.setWordWrap(True)
    lay.addWidget(note)
    row = QHBoxLayout()
    dlg.local_gpu = QLabel('')
    dlg.local_gpu.setWordWrap(True)
    detect = QPushButton(tr('Détecter la carte graphique'))
    row.addWidget(dlg.local_gpu, 1)
    row.addWidget(detect)
    lay.addLayout(row)
    dlg.local_tier = QComboBox()
    notes = _tier_notes()
    for t in LM.TIERS:
        size = ('%g' % t.size_gb).replace('.', decimal_sep())
        dlg.local_tier.addItem(tr('{0} Go : {1} ({2}, {3} Go) — {4}').format(t.gpu_gb, t.label, t.model, size,
                                                                             notes.get(t.model, '')), t.model)
    lay.addWidget(dlg.local_tier)
    dlg.local_state = QLabel(tr('Ollama : pas encore vérifié'))
    dlg.local_state.setWordWrap(True)
    dlg.local_state.setTextFormat(Qt.TextFormat.PlainText)
    lay.addWidget(dlg.local_state)
    row = QHBoxLayout()
    check = QPushButton(tr('Vérifier Ollama'))
    start = QPushButton(tr('Démarrer Ollama'))
    pull = QPushButton(tr('Télécharger le modèle'))
    pull.setToolTip(tr('Une console « ollama pull » : l’avancement s’y affiche ; une fois par modèle'))
    use = QPushButton(tr('Utiliser ce modèle'))
    use.setToolTip(tr('Le fournisseur « Mistral en local » et ce modèle, gardés à OK'))
    link = QLabel('<a href="{0}">{1}</a>'.format(html.escape(LM.DOWNLOAD_PAGE), html.escape(tr('Installer Ollama'))))
    link.linkActivated.connect(lambda url: QDesktopServices.openUrl(QUrl(url)))
    for b in (detect, check, start, pull, use):
        b.setAutoDefault(False)
    for w in (check, start, pull, use, link):
        row.addWidget(w)
    row.addStretch(1)
    lay.addLayout(row)

    def model() -> str:
        return str(dlg.local_tier.currentData() or LM.TIERS[1].model)

    def address() -> str:
        w = getattr(dlg, 'widgets', {}).get('assistant/adresse_local')
        return w.text().strip() if w is not None else str(st.value('assistant/adresse_local', '') or '')

    def show_gpu(gb) -> None:
        if gb:
            best = LM.recommend(gb)
            dlg.local_gpu.setText(tr('Carte graphique : {0} Go → palier conseillé : {1}').format(
                ('%g' % gb).replace('.', decimal_sep()), best.label))
        else:
            dlg.local_gpu.setText(tr('Carte graphique : mémoire inconnue — « Détecter » ; sans carte NVIDIA, le plus '
                                     'petit palier tourne aussi sur le processeur, lentement'))

    def do_detect(_=False) -> float | None:
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            gb = LM.gpu_memory_gb()
        finally:
            QApplication.restoreOverrideCursor()
        st.setValue(KEY_GPU, gb or 0)
        show_gpu(gb)
        i = dlg.local_tier.findData(LM.recommend(gb).model)
        if i >= 0:
            dlg.local_tier.setCurrentIndex(i)
        return gb

    def do_check(_=False, sync: bool = False):
        """L'état d'Ollama ; demandé dans un fil de travail (`sync` : tout de suite, pour les essais) : la fenêtre
        reste vive pendant l'attente d'une adresse absente."""
        url = address()
        if sync:
            return show_status(LM.status(url))
        import threading
        from PySide6.QtCore import QTimer
        holder = {}
        check.setEnabled(False)
        dlg.local_state.setText(tr('Vérification d’Ollama…'))
        def work():
            try:
                got = LM.status(url)
            except Exception as ex:                      # noqa: BLE001 — jamais un bouton figé
                got = {'running': False, 'version': '', 'models': [], 'error': str(ex)}
            holder['got'] = got
        threading.Thread(target=work, daemon=True, name='vectordrive-ollama-status').start()
        timer = QTimer(dlg)

        def poll():
            if 'got' in holder:
                timer.stop()
                timer.deleteLater()
                check.setEnabled(True)
                show_status(holder['got'])
        timer.timeout.connect(poll)
        timer.start(100)
        return None

    def show_status(got: dict) -> dict:
        m = model()
        if got['running']:
            st.setValue(LM.KEY_SEEN, '|'.join(got['models']))
            text = tr('Ollama {0} en marche ; modèles : {1}').format(got['version'] or '?',
                                                                    ', '.join(got['models']) or tr('aucun'))
            text += ' — ' + (tr('« {0} » prêt').format(m) if LM.has_model(got['models'], m)
                             else tr('« {0} » à télécharger').format(m))
            if m.startswith('ministral-3') and not LM.version_ok(got['version']):
                text += ' — ' + tr('Ministral 3 demande Ollama 0.13.1 ou plus récent : mettez Ollama à jour')
        elif got['error'] == 'adresse refusée':
            text = tr('Adresse refusée : https://, ou http:// vers ce poste ou le réseau de l’atelier')
        elif LM.exe():
            text = tr('Ollama est installé mais ne répond pas : « Démarrer Ollama »')
        else:
            text = tr('Ollama n’est pas installé : « Installer Ollama » (ollama.com), puis « Vérifier Ollama »')
        dlg.local_state.setText(text)
        return got

    def do_start(_=False) -> bool:
        try:
            ok = LM.start()
        except OSError:
            ok = False
        if ok:
            dlg.local_state.setText(tr('Ollama démarre… « Vérifier Ollama » dans quelques secondes'))
        elif LM.exe():
            dlg.local_state.setText(tr('Ollama ne s’est pas lancé : démarrez-le depuis le menu Démarrer de Windows'))
        else:
            dlg.local_state.setText(tr('Ollama n’est pas installé : « Installer Ollama » (ollama.com), puis '
                                       '« Vérifier Ollama »'))
        return ok

    def do_pull(_=False) -> bool:
        m = model()
        t = LM.tier_of(m)
        ok = LM.pull(m)
        if ok:
            size = ('%g' % t.size_gb).replace('.', decimal_sep()) if t is not None else '?'
            dlg.local_state.setText(tr('Téléchargement de « {0} » dans une console (environ {1} Go) ; à la fin, '
                                       '« Vérifier Ollama »').format(m, size))
        else:
            dlg.local_state.setText(tr('Ollama n’est pas installé : « Installer Ollama » (ollama.com), puis '
                                       '« Vérifier Ollama »'))
        return ok

    def do_use(_=False) -> None:
        m = model()
        w = getattr(dlg, 'widgets', {})
        if 'assistant/fournisseur' in w:
            box_ = w['assistant/fournisseur']
            box_.setCurrentIndex(max(0, box_.findData('local')))
        if 'assistant/modele_local' in w:
            w['assistant/modele_local'].setText(m)
        dlg.local_state.setText(tr('« {0} » sera l’assistant à la fermeture par OK').format(m))

    detect.clicked.connect(do_detect)
    check.clicked.connect(do_check)
    start.clicked.connect(do_start)
    pull.clicked.connect(do_pull)
    use.clicked.connect(do_use)
    dlg.local_actions = {'detect': do_detect, 'check': do_check, 'start': do_start, 'pull': do_pull, 'use': do_use}
    gb = float(st.value(KEY_GPU, 0) or 0)
    show_gpu(gb)
    current = str(st.value('assistant/modele_local', '') or '')
    i = dlg.local_tier.findData(current if LM.tier_of(current) else LM.recommend(gb).model)
    dlg.local_tier.setCurrentIndex(max(0, i))
    form.addRow(box)
    _searchable(dlg, form, box, 'Mistral en local (Ollama)', tr('Mistral en local (Ollama)'),
                'ollama local gpu carte graphique ministral mistral small hors ligne')


def build(dlg, form, parent=None) -> None:
    """La fin de l'onglet Assistant de la fenêtre des options `dlg` (son formulaire `form`) ; ce qui se garde à OK
    passe par `dlg.on_accept`."""
    note = QLabel(tr('Mode Débutant : les réglages courants seulement. Les autres (modèles, outils permis, '
                     'dossiers, couleurs…) : mode Avancé, ou la recherche ci-dessus.'))
    note.setWordWrap(True)
    form.insertRow(1, note)                              # sous « Mode de l’assistant »
    dlg.assistant_note = note
    from ..agent import keys
    from ..agent import tools as AT
    from ..agent.chat import KEY_PAGES, NO_KEY, PROVIDERS
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
        if slug in NO_KEY:                               # Mistral en local : sans clé (sa partie plus bas)
            continue
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
    _local_box(dlg, form, parent)

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
