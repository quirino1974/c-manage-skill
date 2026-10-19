# manage-skill: catalogo, esportazione e sincronizzazione delle skill di Claude
# Copyright (C) 2026 Quirino Scaramastra
# SPDX-License-Identifier: GPL-3.0-or-later
"""Percorsi e impostazioni di manage-skill."""

import json
import os
from pathlib import Path

PROGETTO = Path(__file__).resolve().parent.parent
DATI = PROGETTO / "dati"
# Esportazioni dentro la cartella del programma: manageskill/archivio (skill singole, ZIP da caricare, cloud/)
ARCHIVIO = PROGETTO / "manageskill" / "archivio"
# Skill di terze parti installate da manage-skill (vedi terze.py)
TERZE = PROGETTO / "manageskill" / "terze-parti"
CATALOGO = PROGETTO / "catalogo"
CONFIG_FILE = DATI / "config.json"
ACCOUNT_FILE = DATI / "account.json"
CATEGORIE_FILE = DATI / "categorie.json"
# Le chiavi non stanno mai nella cartella del progetto
CHIAVI_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "manage-skill" / "chiavi"

HOME_CLAUDE = Path.home() / ".claude"

PREDEFINITA = {
    # Cartelle in cui cercare skill di progetto (.claude/skills/<nome>/SKILL.md)
    "radici_progetti": [str(Path.home() / "claudeworkspace")],
    # Cartelle da non esplorare durante la ricerca
    "escludi": ["node_modules", ".git", ".venv", "venv", "__pycache__", "data", "archivio"],
    # Limiti della Skills API di Anthropic
    "limite_mb": 30,
    # Proprietà: mostra solo le skill dell'utente (niente skill di Anthropic né plugin dei marketplace)
    "solo_utente": True,
}


def carica_json(percorso: Path, default):
    if percorso.exists():
        with open(percorso, encoding="utf-8") as f:
            return json.load(f)
    return default


def salva_json(percorso: Path, dati) -> None:
    percorso.parent.mkdir(parents=True, exist_ok=True)
    tmp = percorso.with_suffix(percorso.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dati, f, indent=2, ensure_ascii=False)
        f.write("\n")
    tmp.replace(percorso)


def impostazioni() -> dict:
    return {**PREDEFINITA, **carica_json(CONFIG_FILE, {})}
