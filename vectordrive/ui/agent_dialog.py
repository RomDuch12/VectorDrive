"""« Assistant (serveur MCP) » — demande du 15/11 : « Possibilité de connecter un agent claude ou chatgpt pour créer
des dessins 2d et 3d ? », puis « queue serveur MCP ». Ouverte depuis Options (F10) › Général.

Une case lance le serveur MCP local de la fenêtre (`agent.server`) ; la fenêtre donne ce qu'il faut pour y brancher un
assistant : la commande de Claude Code, l'adresse et l'en-tête pour un autre client MCP. Le jeton se renouvelle d'un
bouton (les assistants déjà branchés doivent alors être rebranchés)."""
from __future__ import annotations

from PySide6.QtWidgets import (QApplication, QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget)

from ..agent import server as AS
from ..i18n import tr

#: le nom du serveur chez le client
CLIENT_NAME = 'vectordrive'


class AgentDialog(QDialog):
    """Le serveur MCP local : le lancer, et de quoi y brancher un assistant."""

    def __init__(self, win, parent=None):
        super().__init__(parent or win)
        self.win = win
        self.setWindowTitle(tr('Assistant (serveur MCP)'))
        self.setSizeGripEnabled(True)
        self.setMinimumWidth(680)
        lay = QVBoxLayout(self)
        note_text = tr('Un assistant branché ici (Claude Code, par exemple) lit le dessin ouvert et peut le modifier : formes, textes, déplacements, réunions. Chaque modification est un pas d’annulation (Ctrl+Z). Ce que l’assistant lit du dessin part chez son fournisseur. Le serveur n’écoute que sur cette machine (127.0.0.1), jamais sur le réseau, et demande le jeton ci-dessous.')
        note = QLabel(note_text)
        note.setWordWrap(True)
        lay.addWidget(note)
        self.on = QCheckBox(tr('Lancer le serveur MCP local avec VectorDrive'))
        self.on.toggled.connect(self.set_on)
        lay.addWidget(self.on)
        form = QFormLayout()
        self.port_box = QSpinBox()
        self.port_box.setRange(1024, 65535)
        self.port_box.setToolTip(tr('Port du serveur sur cette machine ; à changer s’il est pris par un autre logiciel'))
        self.port_box.editingFinished.connect(lambda: self.set_port(self.port_box.value()))
        form.addRow(tr('Port'), self.port_box)
        self.state = QLabel()
        self.state.setWordWrap(True)
        form.addRow(tr('État'), self.state)
        self.command = self._line(form, 'Claude Code',
                                  tr('À coller dans un terminal : Claude Code retient le serveur pour tous les projets'))
        self.url = self._line(form, tr('Adresse'), tr('Pour un autre client MCP (transport HTTP)'))
        self.header = self._line(form, tr('En-tête'), tr('À envoyer avec chaque demande'))
        desktop_tip = tr('À fusionner dans claude_desktop_config.json (Claude Desktop : Réglages › Développeur › Modifier la configuration), puis relancer Claude Desktop : il lance le pont de VectorDrive, qui joint le serveur ci-dessus.')
        self.desktop = self._line(form, 'Claude Desktop', desktop_tip)
        lay.addLayout(form)
        row = QHBoxLayout()
        self.renew = QPushButton(tr('Nouveau jeton'))
        self.renew.setToolTip(tr('L’ancien jeton ne marche plus : les assistants déjà branchés sont à rebrancher'))
        self.renew.clicked.connect(lambda _=False: self.renew_token())
        row.addWidget(self.renew)
        row.addStretch(1)
        lay.addLayout(row)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(self.reject)
        bb.accepted.connect(self.accept)
        lay.addWidget(bb)
        self.refresh()

    def _line(self, form: QFormLayout, label: str, tip: str) -> QLineEdit:
        box = QWidget()
        h = QHBoxLayout(box)
        h.setContentsMargins(0, 0, 0, 0)
        line = QLineEdit()
        line.setReadOnly(True)
        line.setToolTip(tip)
        copy = QPushButton(tr('Copier'))
        copy.clicked.connect(lambda _=False, w=line: QApplication.clipboard().setText(w.text()))
        h.addWidget(line, 1)
        h.addWidget(copy)
        form.addRow(label, box)
        return line

    # --- l'état --------------------------------------------------------------------------------------
    def is_on(self) -> bool:
        return self.win.settings.value(AS.KEY_ON, False) in (True, 'true', 1, '1')

    def token(self) -> str:
        return AS.token_of(self.win.settings)

    def address(self) -> str:
        """L'adresse du serveur : celle qu'il sert, sinon celle qu'il servirait."""
        srv = getattr(self.win, '_agent_server', None)
        port = srv.port if srv is not None and srv.running else AS.port_of(self.win.settings)
        return f'http://{AS.HOST}:{port}{AS.PATH}'

    def header_text(self) -> str:
        return 'Authorization: Bearer ' + self.token()

    def claude_code_command(self) -> str:
        return (f'claude mcp add --transport http --scope user {CLIENT_NAME} {self.address()} '
                f'--header "{self.header_text()}"')

    def bridge_command(self) -> tuple:
        """(commande, arguments) du pont `--mcp` : l'exécutable de VectorDrive, ou Python et le lanceur."""
        import sys
        if getattr(sys, 'frozen', False):
            return sys.executable, ['--mcp']
        import pathlib
        return sys.executable, [str(pathlib.Path(__file__).resolve().parents[2] / 'VectorDrive.py'), '--mcp']

    def desktop_config(self) -> str:
        """La configuration de Claude Desktop pour ce VectorDrive : un serveur lancé par lui, le pont `--mcp`."""
        import json
        command, args = self.bridge_command()
        return json.dumps({'mcpServers': {CLIENT_NAME: {'command': command, 'args': args}}}, ensure_ascii=False)

    def refresh(self) -> None:
        srv = getattr(self.win, '_agent_server', None)
        running = srv is not None and srv.running
        self.on.blockSignals(True)
        self.on.setChecked(self.is_on())
        self.on.blockSignals(False)
        self.port_box.blockSignals(True)
        self.port_box.setValue(AS.port_of(self.win.settings))
        self.port_box.blockSignals(False)
        problem = str(getattr(self.win, '_agent_error', '') or '')
        if running:
            self.state.setText(tr('Lancé : {0}').format(srv.url))
        else:
            self.state.setText(problem or tr('Arrêté'))
        self.command.setText(self.claude_code_command())
        self.url.setText(self.address())
        self.header.setText(self.header_text())
        self.desktop.setText(self.desktop_config())

    # --- les commandes ---------------------------------------------------------------------------------
    def set_on(self, on: bool) -> None:
        self.win.agent_sync(bool(on))
        self.refresh()

    def set_port(self, port: int) -> None:
        port = int(port)
        if port == AS.port_of(self.win.settings):
            return
        self.win.settings.setValue(AS.KEY_PORT, port)
        self.win.agent_sync()
        self.refresh()

    def renew_token(self) -> str:
        """Un jeton neuf, retenu ; le serveur lancé le demande aussitôt (l'ancien ne vaut plus)."""
        self.win.settings.setValue(AS.KEY_TOKEN, '')
        tok = self.token()                               # un neuf, retenu
        self.win.agent_sync()                            # le serveur lancé repart avec lui
        self.refresh()
        return tok
