# c-manage-skill: catalogo, esportazione e sincronizzazione delle skill di Claude
# Copyright (C) 2026 Quirino Scaramastra
# SPDX-License-Identifier: GPL-3.0-or-later
"""Registro degli account di destinazione e di provenienza (dati/account.json, senza chiavi)."""

from pathlib import Path

from .config import ACCOUNT_FILE, HOME_CLAUDE, carica_json, salva_json

TIPI = {
    "api": "Account o workspace della Claude API (Skills API, chiave API)",
    "claude-code": "Cartella di skill di Claude Code (~/.claude/skills o <progetto>/.claude/skills)",
    "claude-ai": "Account claude.ai: prepara gli ZIP da caricare da Impostazioni > Capacità > Skill",
}

PREDEFINITI = {
    "locale": {"tipo": "claude-code", "cartella": str(HOME_CLAUDE / "skills"),
               "nota": "Skill personali di Claude Code su questo PC"},
}


def tutti() -> dict:
    return {**PREDEFINITI, **carica_json(ACCOUNT_FILE, {})}


def leggi(nome: str) -> dict:
    a = tutti().get(nome)
    if not a:
        raise SystemExit(f"Account '{nome}' sconosciuto. Account disponibili: {', '.join(tutti())}")
    return {"nome": nome, **a}


def aggiungi(nome: str, dati: dict) -> None:
    if not nome.replace("-", "").replace("_", "").isalnum():
        raise SystemExit("Il nome dell'account può contenere solo lettere, numeri, trattini e trattini bassi.")
    reg = carica_json(ACCOUNT_FILE, {})
    reg[nome] = dati
    salva_json(ACCOUNT_FILE, reg)


def rimuovi(nome: str) -> dict:
    reg = carica_json(ACCOUNT_FILE, {})
    if nome not in reg:
        raise SystemExit(f"Account '{nome}' non presente (gli account predefiniti non si rimuovono).")
    dati = reg.pop(nome)
    salva_json(ACCOUNT_FILE, reg)
    return dati


def cartella(a: dict) -> Path:
    return Path(a["cartella"]).expanduser()
