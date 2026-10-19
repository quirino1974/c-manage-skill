# manage-skill: catalogo, esportazione e sincronizzazione delle skill di Claude
# Copyright (C) 2026 Quirino Scaramastra
# SPDX-License-Identifier: GPL-3.0-or-later
"""Motore per la finestra Qt: legge una richiesta JSON dallo standard input e scrive la risposta JSON.

    echo '{"azione": "catalogo", "dati": {}}' | .venv/bin/python -m manageskill.motore

Risposta: {"ok": true, "risultato": {...}} oppure {"ok": false, "errore": "..."}.
I dati (comprese le chiavi API inserite nella finestra) passano solo dallo standard input: non compaiono
tra gli argomenti del processo, quindi non sono visibili con ps. Nessun server e nessuna porta.
"""

import contextlib
import io
import json
import sys

from . import lingua, pacchetti
from .servizi import AZIONI, Errore


def esegui(richiesta: dict) -> dict:
    if richiesta.get("lingua"):
        lingua.imposta(richiesta["lingua"])
    return lingua.traduci_risultato(_esegui(richiesta))


def _esegui(richiesta: dict) -> dict:
    azione = richiesta.get("azione")
    if azione not in AZIONI:
        return {"ok": False, "errore": f"azione sconosciuta: {azione}"}
    try:
        # Le funzioni non devono stampare: qualunque testo finisce nel registro, non nella risposta JSON
        with contextlib.redirect_stdout(io.StringIO()):
            return {"ok": True, "risultato": AZIONI[azione](richiesta.get("dati") or {})}
    except (Errore, SystemExit, pacchetti.Bloccato, RuntimeError, ValueError) as e:
        return {"ok": False, "errore": str(e)}
    except KeyError as e:
        return {"ok": False, "errore": f"manca il parametro {e}"}
    except Exception as e:
        return {"ok": False, "errore": f"{type(e).__name__}: {e}"}


def main():
    try:
        richiesta = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        risposta = {"ok": False, "errore": "richiesta JSON non valida"}
    else:
        risposta = esegui(richiesta)
    sys.stdout.write(json.dumps(risposta, ensure_ascii=False, default=str))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
