"""Brancher un assistant (Claude, par le protocole MCP) sur le dessin ouvert.

- `protocol` : les messages MCP (JSON-RPC 2.0), sans transport ;
- `tools` : les outils offerts à l'assistant (lire le dessin, dessiner, déplacer, réunir, capturer, annuler) ;
- `server` : le serveur HTTP local (127.0.0.1) de la fenêtre.

Rien n'est lancé à l'import ; le serveur ne tourne que si l'option « Serveur MCP local » est cochée (Options, F10).
"""
