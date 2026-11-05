# c-manage-skill: catalogo, esportazione e sincronizzazione delle skill di Claude
# Copyright (C) 2026 Quirino Scaramastra
# SPDX-License-Identifier: GPL-3.0-or-later
"""Skill di terze parti: si aggiungono da un repository Git, da uno ZIP (file o https) o da una cartella,
si tengono in c_manage_skill/terze-parti/<nome>/ e si sincronizzano con gli account scelti.

Registro: dati/terze_parti.json
  {nome: {sorgente, tipo, percorso, commit, aggiunta, aggiornata, impronta,
          destinazioni: [account...], installata: {account: impronta caricata l'ultima volta}}}

Le skill di terze parti possono contenere script: c-manage-skill non li esegue mai, ma li elenca e li passa
al controllo dei segreti prima di ogni sincronizzazione.
"""

import os
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

from . import account as acc
from . import api_anthropic, pacchetti, sorgenti
from . import skill as sk
from .cloud import SINCRONIZZAZIONI
from .config import DATI, TERZE, carica_json, impostazioni, salva_json

REGISTRO = DATI / "terze_parti.json"
MAX_SCARICO = 50 * 1024 * 1024
ESEGUIBILI = {".sh", ".py", ".js", ".mjs", ".ts", ".rb", ".pl", ".ps1", ".bat", ".exe", ".bin"}


def registro() -> dict:
    return carica_json(REGISTRO, {})


def _salva(reg: dict) -> None:
    salva_json(REGISTRO, reg)


def _ora() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------- recupero dalla sorgente

def _tipo(sorgente: str) -> str:
    p = Path(sorgente).expanduser()
    if p.is_dir():
        return "cartella"
    if p.is_file() and p.suffix == ".zip":
        return "zip"
    if sorgente.startswith("https://") and sorgente.lower().split("?")[0].endswith(".zip"):
        return "zip-url"
    if sorgente.startswith(("https://", "git@")) or sorgente.endswith(".git"):
        return "git"
    raise SystemExit(f"Sorgente non riconosciuta: {sorgente}. Usa un repository Git (https://… o git@…), "
                     "uno ZIP (file o https://….zip) o una cartella.")


def _estrai_zip(zip_path: Path, dest: Path) -> None:
    with zipfile.ZipFile(zip_path) as z:
        totale = 0
        for info in z.infolist():
            if info.filename.startswith("/") or ".." in Path(info.filename).parts:
                raise SystemExit(f"ZIP non sicuro: percorso {info.filename}")
            totale += info.file_size
        if totale > MAX_SCARICO * 4:
            raise SystemExit("ZIP troppo grande una volta estratto.")
        z.extractall(dest)


def recupera(sorgente: str) -> tuple:
    """Scarica o copia la sorgente in una cartella temporanea. Ritorna (cartella, tipo, commit)."""
    tipo = _tipo(sorgente)
    tmp = Path(tempfile.mkdtemp(prefix="c-manage-skill-terze-"))
    commit = ""
    if tipo == "cartella":
        shutil.copytree(Path(sorgente).expanduser(), tmp / "src", symlinks=False,
                        ignore=shutil.ignore_patterns(".git", *sk.IGNORA))
    elif tipo == "zip":
        _estrai_zip(Path(sorgente).expanduser(), tmp / "src")
    elif tipo == "zip-url":
        file_zip = tmp / "scarico.zip"
        with urllib.request.urlopen(sorgente, timeout=60) as r, open(file_zip, "wb") as f:
            letti = 0
            while blocco := r.read(1 << 16):
                letti += len(blocco)
                if letti > MAX_SCARICO:
                    raise SystemExit("Download oltre 50 MB: interrotto.")
                f.write(blocco)
        _estrai_zip(file_zip, tmp / "src")
    else:
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        r = subprocess.run(["git", "clone", "--depth", "1", "--quiet", "--", sorgente, str(tmp / "src")],
                           capture_output=True, text=True, env=env, timeout=300)
        if r.returncode != 0:
            raise SystemExit(f"git clone non riuscito: {r.stderr.strip()[-400:]}")
        commit = subprocess.run(["git", "-C", str(tmp / "src"), "rev-parse", "--short", "HEAD"],
                                capture_output=True, text=True).stdout.strip()
    return tmp, tipo, commit


def _trova_skill(radice: Path) -> list:
    """Cartelle con SKILL.md dentro la sorgente: [(percorso relativo, Skill)]."""
    trovate = []
    for dirpath, dirnames, filenames in os.walk(radice):
        dirnames[:] = [d for d in dirnames if d not in (".git", *sk.IGNORA)]
        if "SKILL.md" in filenames:
            p = Path(dirpath)
            if sorgenti.di_anthropic(p):  # licenza proprietaria di Anthropic: non si installa
                continue
            try:
                trovate.append((p.relative_to(radice).as_posix() or ".", sk.carica(p)))
            except (OSError, FileNotFoundError):
                pass
    return sorted(trovate, key=lambda x: x[0])


def _script(s: sk.Skill) -> list:
    return [f for f in s.file if Path(f).suffix.lower() in ESEGUIBILI]


def anteprima(sorgente: str) -> dict:
    """Skill trovate nella sorgente, senza installare nulla."""
    tmp, tipo, commit = recupera(sorgente)
    try:
        installate = registro()
        return {"sorgente": sorgente, "tipo": tipo, "commit": commit, "skill": [
            {"percorso": rel, "nome": s.nome, "descrizione": s.descrizione, "file": len(s.file), "kb": s.kb,
             "script": _script(s), "segreti": len(sk.cerca_segreti(s)), "problemi_api": sk.valida(s, impostazioni()["limite_mb"]),
             "gia_installata": s.nome in installate}
            for rel, s in _trova_skill(tmp / "src")]}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------- aggiunta, aggiornamento, rimozione

def _nome_sicuro(nome: str) -> str:
    if not nome or not all(c.isalnum() or c in "-_." for c in nome) or nome.startswith("."):
        raise SystemExit(f"Nome di skill non utilizzabile come cartella: {nome!r}")
    return nome


def aggiungi(sorgente: str, percorsi=None, destinazioni=None, sostituisci=False) -> list:
    """Installa in terze-parti/ le skill scelte della sorgente (percorsi relativi; None = tutte se è una sola)."""
    tmp, tipo, commit = recupera(sorgente)
    try:
        trovate = _trova_skill(tmp / "src")
        if not trovate:
            raise SystemExit("Nella sorgente non c'è nessuna cartella con SKILL.md.")
        if percorsi:
            scelte = [x for x in trovate if x[0] in percorsi]
            mancanti = set(percorsi) - {x[0] for x in scelte}
            if mancanti:
                raise SystemExit(f"Percorsi non trovati nella sorgente: {', '.join(sorted(mancanti))}")
        elif len(trovate) == 1:
            scelte = trovate
        else:
            raise SystemExit(f"La sorgente contiene {len(trovate)} skill: scegli quali con --percorso "
                             f"({', '.join(x[0] for x in trovate[:10])}{'…' if len(trovate) > 10 else ''}).")
        reg = registro()
        esiti = []
        for rel, s in scelte:
            nome = _nome_sicuro(s.nome)
            if nome in reg and not sostituisci:
                esiti.append({"nome": nome, "ok": False, "errore": "già installata: usa Aggiorna, oppure sostituisci"})
                continue
            if not (nome in reg) and any(v.skill.nome == nome for v in sorgenti.tutte(["claude-code", "progetto"])):
                avviso = "esiste già una tua skill con lo stesso nome: alla sincronizzazione verso 'locale' verrà segnalato il conflitto"
            else:
                avviso = ""
            dest = TERZE / nome
            if dest.exists():
                pacchetti.esporta(sorgenti.Voce(sk.carica(dest), "backup", "terze parti", dest), forza_segreti=True)
                shutil.rmtree(dest)
            TERZE.mkdir(parents=True, exist_ok=True)
            shutil.copytree(s.cartella, dest, symlinks=False, ignore=shutil.ignore_patterns(".git", *sk.IGNORA))
            nuova = sk.carica(dest)
            prima = reg.get(nome, {})
            reg[nome] = {"sorgente": sorgente, "tipo": tipo, "percorso": rel, "commit": commit,
                         "aggiunta": prima.get("aggiunta", _ora()), "aggiornata": _ora(), "impronta": nuova.impronta,
                         "destinazioni": sorted(set(prima.get("destinazioni", [])) | set(destinazioni or [])),
                         "installata": prima.get("installata", {})}
            esiti.append({"nome": nome, "ok": True, "azione": "aggiunta", "cartella": str(dest), "script": _script(nuova),
                          **({"avviso": avviso} if avviso else {})})
        _salva(reg)
        return esiti
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def aggiorna(nomi=None, forza=False) -> list:
    """Riscarica dalla sorgente; se il contenuto è cambiato sostituisce la copia (la vecchia va in archivio).
    Se la copia è stata modificata qui dopo l'ultimo aggiornamento si ferma, a meno di forza=True."""
    reg = registro()
    nomi = nomi or sorted(reg)
    per_sorgente = {}
    for n in nomi:
        if n not in reg:
            raise SystemExit(f"'{n}' non è una skill di terze parti (ms terze elenco).")
        per_sorgente.setdefault(reg[n]["sorgente"], []).append(n)
    esiti = []
    for sorgente, gruppo in per_sorgente.items():
        try:
            tmp, _tipo_s, commit = recupera(sorgente)
        except SystemExit as e:
            esiti += [{"nome": n, "ok": False, "errore": str(e)} for n in gruppo]
            continue
        try:
            trovate = dict(_trova_skill(tmp / "src"))
            for n in gruppo:
                info = reg[n]
                s = trovate.get(info["percorso"])
                if not s:
                    esiti.append({"nome": n, "ok": False, "errore": f"nella sorgente non c'è più {info['percorso']}"})
                    continue
                if s.impronta == info["impronta"]:
                    info.update(commit=commit or info.get("commit", ""), controllata=_ora())
                    esiti.append({"nome": n, "ok": True, "azione": "invariata"})
                    continue
                dest = TERZE / n
                if dest.exists():
                    locale = sk.carica(dest)
                    if locale.impronta != info["impronta"] and not forza:
                        esiti.append({"nome": n, "ok": False, "errore": "c'è una nuova versione nella sorgente, ma la copia è stata "
                                      "modificata qui: usa forza per sostituirla (le modifiche vanno in archivio)"})
                        continue
                    pacchetti.esporta(sorgenti.Voce(locale, "backup", "terze parti", dest), forza_segreti=True)
                    shutil.rmtree(dest)
                shutil.copytree(s.cartella, dest, symlinks=False, ignore=shutil.ignore_patterns(".git", *sk.IGNORA))
                info.update(impronta=sk.carica(dest).impronta, commit=commit, aggiornata=_ora(), controllata=_ora())
                esiti.append({"nome": n, "ok": True, "azione": "aggiornata", "commit": commit})
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    _salva(reg)
    return esiti


def destinazioni(nome: str, account_scelti: list) -> dict:
    reg = registro()
    if nome not in reg:
        raise SystemExit(f"'{nome}' non è una skill di terze parti.")
    tutti = acc.tutti()
    sconosciuti = [a for a in account_scelti if a not in tutti]
    if sconosciuti:
        raise SystemExit(f"Account sconosciuti: {', '.join(sconosciuti)}")
    reg[nome]["destinazioni"] = sorted(set(account_scelti))
    _salva(reg)
    return reg[nome]


def rimuovi(nome: str) -> None:
    """Toglie la skill dal registro e da terze-parti/ (prima la salva in archivio). Non tocca gli account."""
    reg = registro()
    if nome not in reg:
        raise SystemExit(f"'{nome}' non è una skill di terze parti.")
    dest = TERZE / nome
    if dest.exists():
        pacchetti.esporta(sorgenti.Voce(sk.carica(dest), "backup", "terze parti", dest), forza_segreti=True)
        shutil.rmtree(dest)
    reg.pop(nome)
    _salva(reg)


# ---------------------------------------------------------------- sincronizzazione con gli account

def sincronizza(nomi=None, verso=None, prova=False, forza=False, forza_segreti=False) -> list:
    """Porta le skill di terze parti negli account di destinazione (quelli registrati, o `verso`).

    claude-code: copia; se la copia nell'account è stata modificata a mano dopo l'ultima sincronizzazione
                 si ferma (forza=True la sostituisce, salvandola prima in archivio).
    api:         nuova skill o nuova versione solo se il contenuto è cambiato.
    claude-ai:   prepara lo ZIP da caricare.
    """
    reg = registro()
    nomi = nomi or sorted(reg)
    sinc = carica_json(SINCRONIZZAZIONI, {})
    esiti = []
    remoti = {}
    for n in nomi:
        if n not in reg:
            raise SystemExit(f"'{n}' non è una skill di terze parti.")
        info = reg[n]
        conti = [verso] if verso else info.get("destinazioni", [])
        if not conti:
            esiti.append({"nome": n, "ok": False, "errore": "nessuna destinazione: scegli gli account in cui sincronizzarla"})
            continue
        s = sk.carica(TERZE / n)
        voce = sorgenti.Voce(s, "terze-parti", "terze parti", TERZE / n)
        for nome_acc in conti:
            base = {"nome": n, "account": nome_acc}
            try:
                a = acc.leggi(nome_acc)
                if a["tipo"] == "api":
                    if sk.cerca_segreti(s) and not forza_segreti:
                        raise pacchetti.Bloccato("possibili segreti: controlla con 'ms segreti' o usa ignora segreti")
                    problemi = sk.valida(s, impostazioni()["limite_mb"])
                    if problemi:
                        raise pacchetti.Bloccato("regole della Skills API: " + "; ".join(problemi))
                    if nome_acc not in remoti:
                        remoti[nome_acc] = {x["nome"]: x for x in api_anthropic.elenca(a)}
                    esistente = remoti[nome_acc].get(n)
                    fatto = sinc.get(nome_acc, {}).get(n, {})
                    if esistente and not forza and fatto.get("impronta") == s.impronta:
                        esiti.append({**base, "ok": True, "azione": "già aggiornata"})
                        continue
                    r = api_anthropic.carica(a, s.cartella, n, prova=prova, esistente=esistente)
                    if not prova:
                        sinc.setdefault(nome_acc, {})[n] = {"impronta": s.impronta, "skill_id": r["skill_id"], "versione": r["versione"],
                                                            "quando": _ora(), "da": "terze-parti"}
                        salva_json(SINCRONIZZAZIONI, sinc)
                    esiti.append({**base, "ok": True, **r})
                elif a["tipo"] == "claude-code":
                    dest = acc.cartella(a) / n
                    sovrascrivi = forza
                    if dest.exists() and not forza:
                        attuale = sk.carica(dest).impronta
                        sovrascrivi = attuale == info.get("installata", {}).get(nome_acc)
                        if attuale != s.impronta and not sovrascrivi:
                            raise pacchetti.Bloccato(f"in {dest} c'è una copia diversa, non installata da qui o modificata a mano: "
                                                     "usa forza per sostituirla (verrà salvata in archivio)")
                    r = pacchetti.importa(voce, nome_acc, sovrascrivi=sovrascrivi, prova=prova, forza_segreti=forza_segreti)
                    if not prova:
                        info.setdefault("installata", {})[nome_acc] = s.impronta
                    esiti.append({**base, "ok": True, **{k: v for k, v in r.items() if k not in ("account", "tipo")}})
                else:
                    r = pacchetti.importa(voce, nome_acc, prova=prova, forza_segreti=forza_segreti)
                    esiti.append({**base, "ok": True, **{k: v for k, v in r.items() if k not in ("account", "tipo")}})
            except pacchetti.Bloccato as e:
                esiti.append({**base, "ok": False, "errore": str(e)})
            except SystemExit as e:
                esiti.append({**base, "ok": False, "errore": str(e)})
            except Exception as e:
                esiti.append({**base, "ok": False, "errore": api_anthropic.errore_leggibile(e)})
        if not prova and not verso:
            info["sincronizzata"] = _ora()
    _salva(reg)
    return esiti


def elenco() -> list:
    reg = registro()
    righe = []
    for n, info in sorted(reg.items()):
        cartella = TERZE / n
        try:
            s = sk.carica(cartella)
            stato = "ok" if s.impronta == info["impronta"] else "modificata qui"
            script = _script(s)
        except (OSError, FileNotFoundError):
            stato, script = "cartella mancante", []
        righe.append({"nome": n, "sorgente": info["sorgente"], "tipo": info["tipo"], "percorso": info["percorso"],
                      "commit": info.get("commit", ""), "aggiornata": info.get("aggiornata", "")[:16].replace("T", " "),
                      "sincronizzata": info.get("sincronizzata", "")[:16].replace("T", " "),
                      "destinazioni": info.get("destinazioni", []), "stato": stato, "script": script, "cartella": str(cartella)})
    return righe
