"""Carte graphique de la vue 3D (OpenGL), pour les postes à deux cartes
(intégrée + dédiée) : le choix de Windows, l'économie d'énergie, les
hautes performances, ou le rendu logiciel (sans carte, Mesa de Qt).

Au démarrage, avant Qt (`before_qt`) : variable SHIM_MCCOMPAT du processus
(NVIDIA Optimus : vérifié Intel UHD → Quadro RTX 5000), QT_OPENGL=software
pour le rendu logiciel. L'exécutable installé reçoit aussi la préférence
de Paramètres › Système › Affichage › Graphismes (HKEY_CURRENT_USER\\
Software\\Microsoft\\DirectX\\UserGpuPreferences, « GpuPreference=N; »),
pour les autres cartes doubles (AMD…). Prend effet au prochain démarrage.
"""
from __future__ import annotations

import os
import sys

KEY = r'Software\Microsoft\DirectX\UserGpuPreferences'
SETTING = 'affichage/gpu'
#: choix → GpuPreference de Windows (None : la valeur du programme retirée, Windows décide)
PREFERENCE = {'auto': None, 'economie': 1, 'performance': 2, 'logiciel': None}
CHOICES = [('auto', 'Choix de Windows'), ('economie', 'Économie d\'énergie (carte intégrée)'),
           ('performance', 'Hautes performances (carte dédiée)'), ('logiciel', 'Rendu logiciel (sans carte graphique)')]
#: carte qui a rendu la vue 3D pendant la séance (GL_RENDERER), '' : vue pas encore ouverte
RENDERER = ''
_ADAPTERS: list | None = None


def adapters() -> list[str]:
    """Noms des cartes graphiques du poste (Windows ; [] ailleurs ou en cas d'échec), lus une fois."""
    global _ADAPTERS
    if _ADAPTERS is not None:
        return list(_ADAPTERS)
    out = []
    if os.name == 'nt':
        import subprocess
        try:
            r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command',
                                '[Console]::OutputEncoding = [Text.Encoding]::UTF8; '
                                '(Get-CimInstance Win32_VideoController).Name'],
                               capture_output=True, timeout=8, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            out = [s.strip() for s in r.stdout.decode('utf-8', 'replace').splitlines() if s.strip()]
        except (OSError, subprocess.SubprocessError):
            out = []
    _ADAPTERS = out
    return list(out)


def programs() -> list[str]:
    """Programmes dont la préférence de Windows est posée : l'exécutable de
    VectorDrive seul ([] lancé par Python : la préférence vaudrait pour tous
    les programmes Python ; la variable de `before_qt` suffit alors)."""
    return [os.path.abspath(sys.executable)] if getattr(sys, 'frozen', False) else []


def _reg_write(name: str, data: str | None) -> None:
    import winreg
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, KEY, 0, winreg.KEY_SET_VALUE) as k:
        if data is None:
            try:
                winreg.DeleteValue(k, name)
            except FileNotFoundError:
                pass
        else:
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, data)


def _reg_read(name: str) -> str | None:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY) as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return None


def apply(choice: str, write=None, progs=None) -> list[str]:
    """Préférence de Windows posée (ou retirée) pour les programmes de
    VectorDrive ; rend les programmes touchés. Rien hors de Windows."""
    if choice not in PREFERENCE:
        raise ValueError(choice)
    if write is None:
        if os.name != 'nt':
            return []
        write = _reg_write
    pref = PREFERENCE[choice]
    progs = programs() if progs is None else progs
    for p in progs:
        write(p, None if pref is None else f'GpuPreference={pref};')
    return list(progs)


def current(read=None, progs=None) -> str:
    """Choix lu dans Windows pour le premier programme ('auto' sans préférence)."""
    if read is None:
        if os.name != 'nt':
            return 'auto'
        read = _reg_read
    progs = programs() if progs is None else progs
    v = read(progs[0]) if progs else None
    for part in (v or '').split(';'):
        if part.strip().startswith('GpuPreference='):
            n = part.split('=', 1)[1].strip()
            return {'1': 'economie', '2': 'performance'}.get(n, 'auto')
    return 'auto'


#: NVIDIA Optimus : carte du processus choisie par cette variable, lue à la création du contexte OpenGL
SHIM = 'SHIM_MCCOMPAT'
SHIM_VALUE = {'economie': '0x800000000', 'performance': '0x800000001'}


def before_qt(choice: str) -> None:
    """À appeler avant de créer l'application Qt (variables du processus,
    rien d'écrit sur le poste) : carte intégrée ou dédiée des postes NVIDIA
    Optimus ; rendu logiciel → OpenGL de Qt sans carte (opengl32sw). Une
    variable déjà posée par l'utilisateur est gardée."""
    if choice in SHIM_VALUE and not os.environ.get(SHIM):
        os.environ[SHIM] = SHIM_VALUE[choice]
    if choice == 'logiciel' and not os.environ.get('QT_OPENGL'):
        os.environ['QT_OPENGL'] = 'software'


def note_renderer(name: str) -> None:
    global RENDERER
    RENDERER = str(name or '')
