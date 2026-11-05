# c-manage-skill: catalogo, esportazione e sincronizzazione delle skill di Claude
# Copyright (C) 2026 Quirino Scaramastra
# SPDX-License-Identifier: GPL-3.0-or-later
"""Esportazione e importazione delle skill.

Un'esportazione crea in c_manage_skill/archivio/<nome>/<data-ora>/:
  <nome>/               la cartella della skill, così com'è
  <nome>.zip            ZIP con la cartella <nome>/SKILL.md, pronto per claude.ai o per la Skills API
  skill.json            metadati: fonte, impronta, file, data, controllo dei segreti
"""

import json
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from . import account as acc
from . import api_anthropic, sorgenti
from . import skill as sk
from .config import ARCHIVIO, impostazioni


class Bloccato(Exception):
    """Operazione fermata da un controllo (segreti, validazione, conflitto)."""


def trova(nome: str, fonte: str = None) -> sorgenti.Voce:
    """La skill con quel nome; se è in più fonti senza --da, preferisce la copia modificabile più recente."""
    candidati = [v for v in sorgenti.tutte([fonte] if fonte else None) if v.skill.nome == nome]
    if not candidati:
        raise SystemExit(f"Skill '{nome}' non trovata" + (f" nella fonte {fonte}" if fonte else "") + ". Prova 'ms catalogo'.")
    ordine = {"claude-code": 0, "progetto": 1, "claude-ai": 2, "terze-parti": 3, "archivio": 4, "plugin": 5}
    candidati.sort(key=lambda v: (ordine.get(v.fonte, 9), -v.skill.modificata))
    return candidati[0]


def _controlla(s: sk.Skill, forza_segreti: bool) -> dict:
    segreti = sk.cerca_segreti(s)
    if segreti and not forza_segreti:
        elenco = "\n".join(f"  {f}:{r} {t}" for f, t, r in segreti)
        raise Bloccato(f"Possibili segreti in '{s.nome}', esportazione fermata:\n{elenco}\n"
                       "Toglili dalla skill, oppure usa --ignora-segreti se sono falsi allarmi.")
    return {"segreti": [{"file": f, "tipo": t, "riga": r} for f, t, r in segreti]}


def _zip(cartella: Path, nome: str, destinazione: Path) -> Path:
    with zipfile.ZipFile(destinazione, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in sk.elenca_file(cartella):
            z.write(cartella / rel, f"{nome}/{rel}")
    return destinazione


def esporta(voce: sorgenti.Voce, forza_segreti=False, destinazione: Path = ARCHIVIO) -> Path:
    s = voce.skill
    controllo = _controlla(s, forza_segreti)
    quando = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    base = destinazione / s.nome / quando
    n = 2
    while base.exists():  # due esportazioni nello stesso secondo (per esempio due copie di sicurezza di fila)
        base = destinazione / s.nome / f"{quando}-{n}"
        n += 1
    shutil.copytree(s.cartella, base / s.nome, symlinks=False, ignore=shutil.ignore_patterns(*sk.IGNORA))
    _zip(base / s.nome, s.nome, base / f"{s.nome}.zip")
    meta = {"nome": s.nome, "descrizione": s.descrizione, "impronta": s.impronta, "file": s.file, "byte": s.byte,
            "fonte": voce.fonte, "origine": voce.origine, "percorso": str(voce.percorso),
            "collegamento": voce.collegamento, "esportata": quando, "problemi_api": sk.valida(s, impostazioni()["limite_mb"]),
            **controllo, **({"extra": voce.extra} if voce.extra else {})}
    (base / "skill.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return base


def da_percorso(p: Path) -> sorgenti.Voce:
    """Una skill da cartella, da ZIP o da una cartella di archivio (quella con skill.json)."""
    p = Path(p).expanduser()
    if p.is_file() and p.suffix == ".zip":
        tmp = Path(tempfile.mkdtemp(prefix="c-manage-skill-"))
        with zipfile.ZipFile(p) as z:
            for n in z.namelist():
                if n.startswith("/") or ".." in Path(n).parts:
                    raise Bloccato(f"ZIP non sicuro: percorso {n}")
            z.extractall(tmp)
        trovate = list(tmp.glob("SKILL.md")) + list(tmp.glob("*/SKILL.md"))
        if len(trovate) != 1:
            raise Bloccato(f"{p}: lo ZIP deve contenere un solo SKILL.md (alla radice o in una cartella)")
        if sorgenti.di_anthropic(trovate[0].parent):
            raise Bloccato(f"{p}: skill di Anthropic con licenza proprietaria: c-manage-skill non la esporta né la importa")
        return sorgenti.Voce(sk.carica(trovate[0].parent), "file", "tua", trovate[0].parent)
    if (p / "skill.json").exists():
        meta = json.loads((p / "skill.json").read_text(encoding="utf-8"))
        p = p / meta["nome"]
    if sorgenti.di_anthropic(p):
        raise Bloccato(f"{p}: skill di Anthropic con licenza proprietaria: c-manage-skill non la esporta né la importa")
    return sorgenti.Voce(sk.carica(p), "file", "tua", p)


def importa(voce: sorgenti.Voce, nome_account: str, sovrascrivi=False, prova=False, forza_segreti=False) -> dict:
    """Porta la skill nell'account indicato. Ritorna un riassunto dell'operazione."""
    s = voce.skill
    a = acc.leggi(nome_account)
    _controlla(s, forza_segreti)
    if a["tipo"] == "api":
        problemi = sk.valida(s, impostazioni()["limite_mb"])
        if problemi:
            raise Bloccato(f"'{s.nome}' non rispetta le regole della Skills API:\n  " + "\n  ".join(problemi))
        try:
            esito = api_anthropic.carica(a, s.cartella, s.nome, prova=prova)
        except Exception as e:  # errori dell'SDK resi leggibili
            raise Bloccato(f"{nome_account}: {api_anthropic.errore_leggibile(e)}") from e
        return {"account": nome_account, "tipo": "api", **esito}

    if a["tipo"] == "claude-code":
        dest = acc.cartella(a) / s.nome
        if dest.exists() or dest.is_symlink():
            esistente = sk.carica(dest)
            if esistente.impronta == s.impronta:
                return {"account": nome_account, "tipo": "claude-code", "azione": "già identica", "cartella": str(dest)}
            if not sovrascrivi:
                raise Bloccato(f"'{s.nome}' esiste già in {dest} con contenuto diverso: usa --sovrascrivi "
                               "(la copia attuale viene salvata in archivio prima).")
            if dest.is_symlink():
                raise Bloccato(f"{dest} è un collegamento a {dest.resolve()}: aggiorna la skill nella cartella del progetto.")
        if prova:
            return {"account": nome_account, "tipo": "claude-code", "azione": "sostituzione" if dest.exists() else "nuova", "prova": True}
        if dest.exists():
            esporta(sorgenti.Voce(sk.carica(dest), "backup", "tua", dest), forza_segreti=True)
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(s.cartella, dest, ignore=shutil.ignore_patterns(*sk.IGNORA))
        return {"account": nome_account, "tipo": "claude-code", "azione": "copiata", "cartella": str(dest)}

    if a["tipo"] == "claude-ai":
        problemi = sk.valida(s, impostazioni()["limite_mb"])
        base = acc.cartella(a) if a.get("cartella") else ARCHIVIO / "_da-caricare" / nome_account
        if prova:
            return {"account": nome_account, "tipo": "claude-ai", "azione": "ZIP da caricare", "prova": True, "avvisi": problemi}
        base.mkdir(parents=True, exist_ok=True)
        z = _zip(s.cartella, s.nome, base / f"{s.nome}.zip")
        return {"account": nome_account, "tipo": "claude-ai", "azione": "ZIP pronto", "zip": str(z), "avvisi": problemi,
                "istruzioni": "Su claude.ai: Impostazioni > Capacità > Skill > Carica skill, scegli questo ZIP."}

    raise SystemExit(f"Tipo di account non gestito: {a['tipo']}")
