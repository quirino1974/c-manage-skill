# c-manage-skill: catalogo, esportazione e sincronizzazione delle skill di Claude
# Copyright (C) 2026 Quirino Scaramastra
# SPDX-License-Identifier: GPL-3.0-or-later
"""Note personali sulle skill (dati/note.json): valgono per nome, quindi per tutte le copie della skill."""

from datetime import datetime

from .config import DATI, carica_json, salva_json

NOTE_FILE = DATI / "note.json"


def tutte() -> dict:
    return carica_json(NOTE_FILE, {})


def leggi(nome: str) -> str:
    return tutte().get(nome, {}).get("testo", "")


def scrivi(nome: str, testo: str) -> dict:
    """Salva la nota della skill; un testo vuoto la cancella."""
    note = tutte()
    testo = (testo or "").strip()
    if testo:
        note[nome] = {"testo": testo, "aggiornata": datetime.now().isoformat(timespec="seconds")}
    else:
        note.pop(nome, None)
    salva_json(NOTE_FILE, note)
    return note.get(nome, {})
