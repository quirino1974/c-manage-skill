# manage-skill: catalogo, esportazione e sincronizzazione delle skill di Claude
# Copyright (C) 2026 Quirino Scaramastra
# SPDX-License-Identifier: GPL-3.0-or-later
"""Gestione delle chiavi API degli account.

Le chiavi non stanno mai in account.json né negli archivi. Per ogni account si indica dove si trova la chiave:
  keyring     portachiavi di sistema (secret-tool / GNOME Keyring), consigliato
  file        file in ~/.config/manage-skill/chiavi/<account> con permessi 600
  env:VAR     variabile d'ambiente VAR (utile per CI o per chiavi già esportate)
  ant         credenziali del profilo attivo della CLI `ant` (ant auth login), nessuna chiave salvata qui
La chiave si inserisce solo da tastiera (getpass, senza eco) e non viene mai stampata.
"""

import getpass
import os
import shutil
import subprocess

from .config import CHIAVI_DIR

ATTRIBUTI = ("application", "manage-skill", "account")


def maschera(chiave: str) -> str:
    if not chiave:
        return "(nessuna)"
    return chiave[:7] + "…" + chiave[-4:] if len(chiave) > 16 else "…"


def keyring_disponibile() -> bool:
    return shutil.which("secret-tool") is not None


def salva(account: str, archivio: str, chiave: str) -> str:
    """Salva la chiave nel posto indicato. Ritorna la descrizione da mettere in account.json."""
    if archivio == "keyring":
        if not keyring_disponibile():
            raise RuntimeError("secret-tool non disponibile: usa --chiave file")
        subprocess.run(["secret-tool", "store", f"--label=manage-skill: {account}", *ATTRIBUTI, account],
                       input=chiave.encode(), check=True)
        return "keyring"
    if archivio == "file":
        CHIAVI_DIR.mkdir(parents=True, exist_ok=True)
        os.chmod(CHIAVI_DIR.parent, 0o700)
        os.chmod(CHIAVI_DIR, 0o700)
        p = CHIAVI_DIR / account
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(chiave.strip() + "\n")
        return "file"
    raise ValueError(f"archivio chiave sconosciuto: {archivio}")


def leggi(account: str, dove: str):
    """Ritorna la chiave dell'account, oppure None se la fonte è 'ant' (credenziali gestite dall'SDK)."""
    if dove == "keyring":
        r = subprocess.run(["secret-tool", "lookup", *ATTRIBUTI, account], capture_output=True, text=True)
        if r.returncode != 0 or not r.stdout.strip():
            raise RuntimeError(f"chiave di '{account}' non trovata nel portachiavi: usa 'ms account chiave {account}'")
        return r.stdout.strip()
    if dove == "file":
        p = CHIAVI_DIR / account
        if not p.exists():
            raise RuntimeError(f"chiave di '{account}' non trovata in {p}: usa 'ms account chiave {account}'")
        if p.stat().st_mode & 0o077:
            raise RuntimeError(f"{p} è leggibile da altri utenti: esegui chmod 600 {p}")
        return p.read_text().strip()
    if dove.startswith("env:"):
        var = dove[4:]
        if not os.environ.get(var):
            raise RuntimeError(f"variabile d'ambiente {var} non impostata")
        return os.environ[var]
    if dove == "ant":
        return None
    raise RuntimeError(f"fonte della chiave sconosciuta: {dove}")


def elimina(account: str, dove: str) -> None:
    if dove == "keyring" and keyring_disponibile():
        subprocess.run(["secret-tool", "clear", *ATTRIBUTI, account], check=False)
    elif dove == "file":
        p = CHIAVI_DIR / account
        if p.exists():
            p.unlink()


def chiedi(account: str) -> str:
    chiave = getpass.getpass(f"Chiave API per '{account}' (non viene mostrata): ").strip()
    if not chiave:
        raise SystemExit("Nessuna chiave inserita.")
    if not chiave.startswith("sk-ant-"):
        print("Attenzione: la chiave non inizia con 'sk-ant-'.")
    return chiave
