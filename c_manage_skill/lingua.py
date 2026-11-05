# c-manage-skill: catalogo, esportazione e sincronizzazione delle skill di Claude
# Copyright (C) 2026 Quirino Scaramastra
# SPDX-License-Identifier: GPL-3.0-or-later
"""Lingua dei messaggi. Il programma è scritto in italiano; per l'inglese i testi vengono cercati nel dizionario
c_manage_skill/lingue/en.json (lo stesso della finestra Qt), generato da strumenti/crea_dizionario_en.py.

La lingua si sceglie con C_MANAGE_SKILL_LINGUA=en|it, con "lingua" in dati/config.json, oppure, per la finestra,
con il menu della lingua (che la passa al motore a ogni richiesta).
"""

import json
import os
import re
from functools import lru_cache
from pathlib import Path

CARTELLA = Path(__file__).resolve().parent / "lingue"
# Campi delle risposte del motore che contengono messaggi da tradurre
MESSAGGI = {"errore", "messaggio", "avviso", "motivo", "perche", "istruzioni", "azione"}

_lingua = None


def attuale() -> str:
    global _lingua
    if _lingua is None:
        from .config import impostazioni
        _lingua = (os.environ.get("C_MANAGE_SKILL_LINGUA") or impostazioni().get("lingua") or "it").lower()[:2]
    return _lingua


def imposta(codice: str) -> None:
    global _lingua
    _lingua = "en" if (codice or "").lower().startswith("en") else "it"


@lru_cache(maxsize=4)
def _dizionario(codice: str) -> dict:
    p = CARTELLA / f"{codice}.json"
    if not p.exists():
        return {"esatti": {}, "intestazioni": {}, "modelli": []}
    d = json.loads(p.read_text(encoding="utf-8"))
    d["modelli"] = [(re.compile(f"(?:{m})", re.S), s) for m, s in d.get("modelli", [])]
    return d


def _riga(riga: str, d: dict) -> str:
    nucleo = riga.strip()
    if not nucleo:
        return riga
    if riga in d["esatti"]:
        return d["esatti"][riga]
    inizio = riga[:len(riga) - len(riga.lstrip())]
    fine = riga[len(riga.rstrip()):]
    if nucleo in d["esatti"]:
        return inizio + d["esatti"][nucleo] + fine
    for rx, sostituto in d["modelli"]:
        m = rx.fullmatch(nucleo)
        if m:
            risultato = sostituto
            for i in range(len(m.groups()), 0, -1):
                risultato = risultato.replace(f"\\{i}", _riga(m.group(i), d))
            return inizio + risultato + fine
    return riga


def t(testo):
    """Il testo nella lingua scelta (invariato se non c'è traduzione)."""
    if not isinstance(testo, str) or attuale() == "it" or not testo:
        return testo
    d = _dizionario(attuale())
    if testo in d["esatti"]:
        return d["esatti"][testo]
    if "\n" not in testo:
        return _riga(testo, d)
    intero = _riga(testo, d)
    if intero != testo:
        return intero
    return "\n".join(_riga(r, d) for r in testo.split("\n"))


def intestazione(colonna: str) -> str:
    if attuale() == "it":
        return colonna
    return _dizionario(attuale())["intestazioni"].get(colonna, colonna)


def traduci_risultato(dati):
    """Traduce i messaggi dentro una risposta del motore (solo i campi di MESSAGGI e gli elenchi di avvisi)."""
    if attuale() == "it":
        return dati
    if isinstance(dati, dict):
        return {k: (t(v) if k in MESSAGGI and isinstance(v, str)
                    else [t(x) for x in v] if k in ("avvisi", "problemi_api") and isinstance(v, list)
                    else traduci_risultato(v)) for k, v in dati.items()}
    if isinstance(dati, list):
        return [traduci_risultato(x) for x in dati]
    return dati
