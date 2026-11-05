# c-manage-skill: catalogo, esportazione e sincronizzazione delle skill di Claude
# Copyright (C) 2026 Quirino Scaramastra
# SPDX-License-Identifier: GPL-3.0-or-later
"""Skill del cloud: catalogo ed esportazione su richiesta in c_manage_skill/archivio/cloud/.

Le skill dell'account claude.ai non si scaricano con un'API pubblica: Claude Code ne tiene una copia
sincronizzata in ~/.claude/skills/synced/<organizzazione>_<utente>/ con un manifest.json (id, tipo, data
di aggiornamento). Questo modulo legge quella copia e la fotografa in:

  c_manage_skill/archivio/cloud/<account>/<data-ora>/
    skill/<nome>/        la cartella di ogni skill
    zip/<nome>.zip       ZIP pronto da ricaricare su claude.ai o nella Skills API
    indice.json          catalogo dell'esportazione (id claude.ai, tipo, impronta, controlli)
    indice.html          lo stesso catalogo da aprire nel browser
  c_manage_skill/archivio/cloud/<account>/ultima collegamento all'esportazione più recente

Degli account API (Skills API) si possono elencare solo i metadati: l'API non permette di scaricare i file.
"""

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from . import account as acc
from . import api_anthropic, catalogo, sorgenti
from .pacchetti import _zip
from . import skill as sk
from .config import ARCHIVIO, DATI, HOME_CLAUDE, carica_json, impostazioni, salva_json

CLOUD = ARCHIVIO / "cloud"
# Cosa è già stato caricato negli account API: {account: {skill: {impronta, skill_id, versione, quando}}}
SINCRONIZZAZIONI = DATI / "sincronizzazioni.json"
SYNCED = HOME_CLAUDE / "skills" / "synced"
TIPI = {"plugin": "tua", "anthropic": "Anthropic", "anthropic-example": "esempio Anthropic"}


def nome_account(cartella_conto: str) -> str:
    """Nome breve e stabile per la copia di un account claude.ai (la cartella synced ha due UUID)."""
    org, _, utente = cartella_conto.partition("_")
    return f"claude-ai_{org[:8]}" + (f"_{utente[:8]}" if utente else "")


def conti() -> list:
    """Account claude.ai sincronizzati su questo PC: [{cartella, nome, aggiornato, skill}]."""
    risultato = []
    if not SYNCED.exists():
        return risultato
    for d in sorted(SYNCED.iterdir()):
        man = d / "manifest.json"
        if d.is_dir() and man.exists():
            dati = json.loads(man.read_text(encoding="utf-8"))
            risultato.append({"cartella": d.name, "nome": nome_account(d.name), "aggiornato": _data(dati.get("lastUpdated")),
                              "skill": len(dati.get("skills", []))})
    return risultato


def _data(valore) -> str:
    """Le date del manifest sono millisecondi o ISO: le rende leggibili in ora locale."""
    if valore in (None, ""):
        return ""
    try:
        if isinstance(valore, (int, float)) or str(valore).isdigit():
            return datetime.fromtimestamp(int(valore) / 1000).strftime("%Y-%m-%d %H:%M")
        return datetime.fromisoformat(str(valore).replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M")
    except (ValueError, OSError):
        return str(valore)


def elenca(sole_mie=False) -> list:
    """Catalogo delle skill claude.ai, con il confronto con la copia locale di Claude Code se esiste."""
    locali = {v.skill.nome: v for v in sorgenti.tutte(["claude-code", "progetto"])}
    regole = catalogo.categorie()
    righe = []
    for v in sorgenti.claude_ai():
        if sole_mie and v.origine != "tua":
            continue
        s, x = v.skill, v.extra
        locale = locali.get(s.nome)
        righe.append({
            "nome": s.nome, "descrizione": s.descrizione, "categoria": catalogo.categoria(s.nome, s.descrizione, regole),
            "origine": v.origine, "tipo": TIPI.get(x.get("tipo_claude_ai"), x.get("tipo_claude_ai", "")),
            "skill_id": x.get("skill_id", ""), "aggiornata": _data(x.get("aggiornata_claude_ai")),
            "account": nome_account(x.get("account", "")), "file": len(s.file), "kb": s.kb, "impronta": s.impronta,
            "locale": ("uguale" if locale.skill.impronta == s.impronta else "diversa") if locale else "assente",
            "percorso": str(v.percorso),
        })
    return righe


def elenca_api() -> list:
    """Metadati delle skill custom negli account API registrati (nessun file: l'API non li fornisce)."""
    pc = {v.skill.nome for v in sorgenti.tutte(["claude-code", "progetto"])}
    web = {v.skill.nome for v in sorgenti.claude_ai()}
    righe = []
    for nome, d in acc.tutti().items():
        if d["tipo"] != "api":
            continue
        try:
            for s in api_anthropic.elenca({"nome": nome, **d}):
                righe.append({"account": nome, **s, "sul_pc": "sì" if s["nome"] in pc else "no",
                              "su_claude_ai": "sì" if s["nome"] in web else "no"})
        except Exception as e:
            righe.append({"account": nome, "errore": api_anthropic.errore_leggibile(e)})
    return righe


def esporta(nomi=None, sole_mie=False, forza_segreti=False, account_cloud=None) -> dict:
    """Fotografa le skill claude.ai in c_manage_skill/archivio/cloud/<account>/<data-ora>/. Ritorna il riassunto dell'esportazione.

    nomi: solo queste skill; sole_mie: solo le tue (quelle di Anthropic non vengono mai lette). Una skill con possibili segreti
    viene saltata e segnalata, a meno di forza_segreti; le altre vengono esportate comunque.
    """
    voci = [v for v in sorgenti.claude_ai() if (not sole_mie or v.origine == "tua") and (not nomi or v.skill.nome in nomi)]
    if account_cloud:
        voci = [v for v in voci if nome_account(v.extra.get("account", "")) == account_cloud]
    if nomi:
        mancanti = sorted(set(nomi) - {v.skill.nome for v in voci})
        if mancanti:
            raise SystemExit(f"Non nel cloud: {', '.join(mancanti)}. Prova 'ms cloud elenco'.")
    if not voci:
        raise SystemExit("Nessuna skill claude.ai trovata: apri Claude Code collegato al tuo account per sincronizzarle.")

    quando = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    risultati = {}
    per_conto = {}
    for v in voci:
        per_conto.setdefault(v.extra.get("account", ""), []).append(v)
    for conto, gruppo in per_conto.items():
        nome = nome_account(conto)
        radice = CLOUD / nome
        precedente = _indice(radice / "ultima")
        base = radice / quando
        esportate, saltate = [], []
        regole = catalogo.categorie()
        for v in gruppo:
            s = v.skill
            segreti = sk.cerca_segreti(s)
            if segreti and not forza_segreti:
                saltate.append({"nome": s.nome, "motivo": "possibili segreti",
                                "segreti": [{"file": f, "tipo": t, "riga": r} for f, t, r in segreti]})
                continue
            shutil.copytree(s.cartella, base / "skill" / s.nome, ignore=shutil.ignore_patterns(*sk.IGNORA))
            (base / "zip").mkdir(parents=True, exist_ok=True)
            _zip(base / "skill" / s.nome, s.nome, base / "zip" / f"{s.nome}.zip")
            prima = precedente.get(s.nome)
            esportate.append({
                "nome": s.nome, "descrizione": s.descrizione, "categoria": catalogo.categoria(s.nome, s.descrizione, regole),
                "origine": v.origine, "tipo": TIPI.get(v.extra.get("tipo_claude_ai"), v.extra.get("tipo_claude_ai", "")),
                "skill_id": v.extra.get("skill_id", ""), "aggiornata": _data(v.extra.get("aggiornata_claude_ai")),
                "file": s.file, "byte": s.byte, "impronta": s.impronta,
                "rispetto_alla_precedente": "nuova" if not prima else ("uguale" if prima == s.impronta else "cambiata"),
                "problemi_api": sk.valida(s, impostazioni()["limite_mb"]),
                "segreti": [{"file": f, "tipo": t, "riga": r} for f, t, r in segreti],
            })
        if not esportate:
            risultati[nome] = {"cartella": None, "esportate": [], "saltate": saltate}
            continue
        man = json.loads((SYNCED / conto / "manifest.json").read_text(encoding="utf-8"))
        indice = {"account": nome, "cartella_synced": str(SYNCED / conto), "sincronizzato": _data(man.get("lastUpdated")),
                  "esportato": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                  "esportate": esportate, "saltate": saltate}
        (base / "indice.json").write_text(json.dumps(indice, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (base / "indice.html").write_text(_html(indice, base), encoding="utf-8")
        ultima = radice / "ultima"
        if ultima.is_symlink():
            ultima.unlink()
        if not ultima.exists():
            os.symlink(quando, ultima)
        risultati[nome] = {"cartella": str(base), "esportate": [e["nome"] for e in esportate], "saltate": saltate,
                           "cambiate": [e["nome"] for e in esportate if e["rispetto_alla_precedente"] != "uguale"]}
    return risultati


def _indice(cartella: Path) -> dict:
    """{nome: impronta} di un'esportazione precedente, per dire cosa è cambiato."""
    p = cartella / "indice.json"
    if not p.exists():
        return {}
    return {e["nome"]: e["impronta"] for e in json.loads(p.read_text(encoding="utf-8")).get("esportate", [])}


def esportazioni() -> list:
    """Le esportazioni presenti in c_manage_skill/archivio/cloud/, dalla più recente."""
    risultato = []
    if not CLOUD.exists():
        return risultato
    for p in sorted(CLOUD.glob("*/*/indice.json"), reverse=True):
        if p.parent.name == "ultima":
            continue
        dati = json.loads(p.read_text(encoding="utf-8"))
        risultato.append({"account": dati["account"], "data": p.parent.name, "cartella": str(p.parent),
                          "skill": len(dati["esportate"]), "saltate": len(dati.get("saltate", [])),
                          "cambiate": sum(e["rispetto_alla_precedente"] != "uguale" for e in dati["esportate"]),
                          "sincronizzato": dati.get("sincronizzato", "")})
    return risultato


def _html(indice: dict, base: Path) -> str:
    """Pagina dell'esportazione: stessa grafica del catalogo, con il link allo ZIP di ogni skill."""
    righe = [{"nome": e["nome"], "descrizione": e["descrizione"], "categoria": e["categoria"], "origine": e["origine"],
              "fonti": ["claude-ai"], "allineata": True, "file": len(e["file"]), "kb": round(e["byte"] / 1024, 1),
              "modificata": e["aggiornata"],
              "copie": [{"fonte": "zip", "percorso": f"zip/{e['nome']}.zip", "collegamento": "", "impronta": e["impronta"],
                         "modificata": e["rispetto_alla_precedente"], "sola_lettura": True}]} for e in indice["esportate"]]
    pagina = catalogo.html_catalogo(righe)
    pagina = pagina.replace("<title>Catalogo skill</title>", f"<title>Skill claude.ai {base.name}</title>")
    pagina = pagina.replace("<h1>Catalogo skill</h1>", f"<h1>Skill claude.ai</h1><p class=\"sub\">{indice['account']} · "
                            f"sincronizzate da Claude Code il {indice['sincronizzato']} · esportate il {base.name}</p>")
    return pagina


def verso_api(nome_account: str, nomi=None, prova=False, forza=False, forza_segreti=False) -> list:
    """Importa le skill di claude.ai in un account API (Claude Console).

    Una skill che nell'account manca viene creata; se c'è già ed è cambiata da quando c-manage-skill l'ha caricata
    l'ultima volta, diventa una nuova versione; se è uguale viene saltata (forza=True la ricarica comunque).
    Senza nomi prende tutte le tue skill. Quelle di Anthropic non ci sono mai: sorgenti non le legge.
    """
    a = acc.leggi(nome_account)
    if a["tipo"] != "api":
        raise SystemExit(f"'{nome_account}' non è un account api: scegline uno di tipo api (ms account elenco).")
    voci = [v for v in sorgenti.claude_ai() if v.origine == "tua" and (not nomi or v.skill.nome in nomi)]
    if nomi:
        mancanti = sorted(set(nomi) - {v.skill.nome for v in voci})
        if mancanti:
            raise SystemExit(f"Non su claude.ai: {', '.join(mancanti)}. Prova 'ms cloud elenco'.")
    if not voci:
        raise SystemExit("Nessuna skill claude.ai trovata: apri Claude Code collegato al tuo account per sincronizzarle.")
    try:
        remote = {s["nome"]: s for s in api_anthropic.elenca(a)}
    except SystemExit:
        raise
    except Exception as e:
        raise SystemExit(f"{nome_account}: {api_anthropic.errore_leggibile(e)}")
    registro = carica_json(SINCRONIZZAZIONI, {})
    fatti = registro.setdefault(nome_account, {})
    locali = {v.skill.nome: v for v in sorgenti.tutte(["claude-code", "progetto"])}
    limite = impostazioni()["limite_mb"]
    esiti = []
    for v in voci:
        s = v.skill
        esito = {"nome": s.nome}
        locale = locali.get(s.nome)
        if locale and locale.skill.impronta != s.impronta and sorgenti.data_modifica(locale) > sorgenti.data_modifica(v):
            esito["avviso"] = "sul PC c'è una versione più recente di quella su claude.ai"
        problemi = sk.valida(s, limite)
        if problemi:
            esiti.append({**esito, "ok": False, "errore": "non rispetta le regole della Skills API: " + "; ".join(problemi)})
            continue
        segreti = sk.cerca_segreti(s)
        if segreti and not forza_segreti:
            esiti.append({**esito, "ok": False, "errore": "possibili segreti: " + ", ".join(f"{f}:{r}" for f, _, r in segreti)})
            continue
        esistente = remote.get(s.nome)
        if esistente and not forza and fatti.get(s.nome, {}).get("impronta") == s.impronta:
            esiti.append({**esito, "ok": True, "azione": "già aggiornata", "skill_id": esistente["id"]})
            continue
        try:
            r = api_anthropic.carica(a, s.cartella, s.nome, prova=prova, esistente=esistente)
        except Exception as e:
            esiti.append({**esito, "ok": False, "errore": api_anthropic.errore_leggibile(e)})
            continue
        if not prova:
            fatti[s.nome] = {"impronta": s.impronta, "skill_id": r["skill_id"], "versione": r["versione"],
                             "quando": datetime.now().isoformat(timespec="seconds"), "da": "claude-ai"}
            salva_json(SINCRONIZZAZIONI, registro)
        esiti.append({**esito, "ok": True, **r})
    return esiti
