# manage-skill: catalogo, esportazione e sincronizzazione delle skill di Claude
# Copyright (C) 2026 Quirino Scaramastra
# SPDX-License-Identifier: GPL-3.0-or-later
"""Accesso alla Skills API di Anthropic con l'SDK ufficiale (anthropic >= 1.2.0, nessun header beta).

La Skills API permette di elencare, creare, aggiornare (nuova versione) ed eliminare le skill custom di un
account o workspace. Non espone un endpoint per scaricare i file di una skill: l'esportazione dei contenuti
avviene dalle copie locali (Claude Code, progetti, copia sincronizzata da claude.ai, archivio).
"""

from pathlib import Path

from . import chiavi


def client(account: dict, chiave: str = None):
    """Client per l'account; `chiave` serve solo a provare una chiave non ancora salvata."""
    try:
        import anthropic
    except ImportError:
        raise SystemExit("Manca l'SDK anthropic: esegui ./installa.sh")
    if chiave is None:
        chiave = chiavi.leggi(account["nome"], account.get("chiave", "keyring"))
    opzioni = {"max_retries": 3}
    if account.get("base_url"):
        opzioni["base_url"] = account["base_url"]
    return anthropic.Anthropic(api_key=chiave, **opzioni) if chiave else anthropic.Anthropic(**opzioni)


def _ws(account: dict) -> dict:
    return {"workspace_id": account["workspace_id"]} if account.get("workspace_id") else {}


def elenca(account: dict, tutte_le_fonti=False, chiave: str = None) -> list:
    c = client(account, chiave)
    risultato = []
    for s in c.skills.list(limit=100, **({} if tutte_le_fonti else {"source": "custom"}), **_ws(account)):
        risultato.append({"id": s.id, "nome": s.display_name, "fonte": getattr(s.source, "type", str(s.source)),
                          "versione": s.latest_version_id, "creata": str(getattr(s, "created_at", "")),
                          "aggiornata": str(getattr(s, "updated_at", ""))})
    return risultato


def versioni(account: dict, skill_id: str) -> list:
    c = client(account)
    return [{"id": v.id, "creata": str(getattr(v, "created_at", "")), "nome": getattr(v, "name", ""),
             "descrizione": getattr(v, "description", "")}
            for v in c.skills.versions.list(skill_id=skill_id, limit=100, **_ws(account))]


def trova(account: dict, nome: str):
    for s in elenca(account):
        if s["nome"] == nome:
            return s
    return None


_CERCA = object()


def carica(account: dict, cartella: Path, nome: str, prova=False, esistente=_CERCA) -> dict:
    """Crea la skill nell'account, o una nuova versione se esiste già una skill con lo stesso nome.
    `esistente` evita di rileggere l'elenco quando chi chiama lo conosce già (None = non c'è)."""
    if esistente is _CERCA:
        esistente = trova(account, nome)
    if prova:
        azione = f"nuova versione di {esistente['id']}" if esistente else "nuova skill"
        return {"azione": azione, "prova": True}
    from anthropic.lib import files_from_dir

    c = client(account)
    if esistente:
        v = c.skills.versions.create(skill_id=esistente["id"], files=files_from_dir(str(cartella)), **_ws(account))
        return {"azione": "nuova versione", "skill_id": esistente["id"], "versione": v.id}
    s = c.skills.create(files=files_from_dir(str(cartella)), display_name=nome, **_ws(account))
    return {"azione": "nuova skill", "skill_id": s.id, "versione": s.latest_version_id}


def elimina(account: dict, skill_id: str) -> None:
    client(account).skills.delete(skill_id=skill_id, **_ws(account))


def errore_leggibile(e: Exception) -> str:
    try:
        import anthropic
    except ImportError:
        return str(e)
    if isinstance(e, anthropic.AuthenticationError):
        return "chiave API non valida o revocata (401)"
    if isinstance(e, anthropic.PermissionDeniedError):
        return "la chiave non ha i permessi per la Skills API su questo workspace (403)"
    if isinstance(e, anthropic.NotFoundError):
        return "skill o workspace non trovati (404)"
    if isinstance(e, anthropic.RateLimitError):
        return "troppe richieste, riprova tra poco (429)"
    if isinstance(e, anthropic.BadRequestError) and "workspace" in str(getattr(e, "message", e)).lower():
        return ("la chiave non è legata a un workspace: indica il Workspace ID (wrkspc_…), che trovi nella Claude Console "
                "in Settings > Workspaces, oppure crea una chiave dentro il workspace da leggere")
    if isinstance(e, anthropic.BadRequestError):
        return f"richiesta rifiutata (400): {getattr(e, 'message', e)}"
    if isinstance(e, anthropic.APIStatusError):
        return f"errore dell'API ({e.status_code}): {getattr(e, 'message', e)}"
    if isinstance(e, anthropic.APIConnectionError):
        return "impossibile raggiungere l'API (rete o proxy)"
    return str(e)
