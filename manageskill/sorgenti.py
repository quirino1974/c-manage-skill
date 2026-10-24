# manage-skill: catalogo, esportazione e sincronizzazione delle skill di Claude
# Copyright (C) 2026 Quirino Scaramastra
# SPDX-License-Identifier: GPL-3.0-or-later
"""Ricerca delle skill nelle varie fonti: Claude Code, progetti, plugin, copia sincronizzata da claude.ai."""

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import skill as sk
from .config import ARCHIVIO, HOME_CLAUDE, TERZE, impostazioni


@dataclass
class Voce:
    """Una skill trovata in una fonte."""
    skill: sk.Skill
    fonte: str            # claude-code | progetto | plugin | claude-ai | archivio | <account>
    origine: str          # tua | anthropic | plugin
    percorso: Path
    collegamento: str = ""  # destinazione se la cartella è un collegamento simbolico
    sola_lettura: bool = False
    extra: dict = None


def di_anthropic(cartella: Path) -> bool:
    """Skill di Anthropic con licenza proprietaria ("Anthropic, PBC. All rights reserved." nel file di licenza).
    Non è dell'utente e non si può ridistribuire: manage-skill non la legge, da nessuna fonte."""
    for nome in ("LICENSE.txt", "LICENSE", "LICENSE.md"):
        try:
            testo = (cartella / nome).read_text(encoding="utf-8", errors="ignore")[:4000]
        except OSError:
            continue
        if "Anthropic, PBC" in testo and "all rights reserved" in testo.lower():
            return True
    return False


def _carica(cartella: Path, fonte: str, origine: str, sola_lettura=False, extra=None):
    if di_anthropic(cartella):
        return None
    try:
        s = sk.carica(cartella)
    except (FileNotFoundError, OSError):
        return None
    link = str(Path(os.path.realpath(cartella))) if cartella.is_symlink() else ""
    return Voce(s, fonte, origine, cartella, link, sola_lettura, extra or {})


def claude_code(cartella: Path = HOME_CLAUDE / "skills"):
    """Skill personali di Claude Code (~/.claude/skills), anche se sono collegamenti ai progetti."""
    voci = []
    if not cartella.exists():
        return voci
    for d in sorted(cartella.iterdir()):
        if d.name == "synced" or not d.is_dir():
            continue
        v = _carica(d, "claude-code", "tua")
        if v:
            voci.append(v)
    return voci


def progetti(radici=None):
    """Skill di progetto: <progetto>/.claude/skills/<nome>/SKILL.md sotto le radici configurate."""
    cfg = impostazioni()
    radici = radici or cfg["radici_progetti"]
    escludi = set(cfg["escludi"])
    voci, visti = [], set()
    for radice in radici:
        for dirpath, dirnames, _ in os.walk(radice):
            dirnames[:] = [d for d in dirnames if d not in escludi and not (d.startswith(".") and d != ".claude")]
            p = Path(dirpath)
            if p.name == "skills" and p.parent.name == ".claude":
                for d in sorted(p.iterdir()):
                    reale = os.path.realpath(d)
                    if d.is_dir() and reale not in visti:
                        visti.add(reale)
                        v = _carica(d, "progetto", "tua", extra={"progetto": str(p.parent.parent)})
                        if v:
                            voci.append(v)
                dirnames[:] = []
    return voci


def plugin(cartella: Path = HOME_CLAUDE / "plugins"):
    """Skill dei plugin dei marketplace (anche quelli di Anthropic): non sono dell'utente, quindi non si leggono.
    La fonte resta nell'elenco per compatibilità con i comandi che la nominano."""
    return []


def claude_ai(cartella: Path = HOME_CLAUDE / "skills" / "synced"):
    """Copia locale delle skill del tuo account claude.ai, sincronizzata da Claude Code (sola lettura)."""
    voci = []
    if not cartella.exists():
        return voci
    for conto in sorted(cartella.iterdir()):
        man = conto / "manifest.json"
        if not conto.is_dir() or not man.exists():
            continue
        manifest = {x["name"]: x for x in json.loads(man.read_text(encoding="utf-8")).get("skills", [])}
        for d in sorted(conto.iterdir()):
            if not d.is_dir():
                continue
            info = manifest.get(d.name, {})
            src = info.get("source", "")
            if src.startswith("anthropic"):  # skill di Anthropic su claude.ai: non si esportano
                continue
            origine = "tua"
            v = _carica(d, "claude-ai", origine, sola_lettura=True,
                        extra={"skill_id": info.get("skillId", ""), "aggiornata_claude_ai": info.get("updatedAt", ""),
                               "account": conto.name, "tipo_claude_ai": src})
            if v:
                voci.append(v)
    return voci


def archivio(cartella: Path = ARCHIVIO):
    """Pacchetti esportati da manage-skill (manageskill/archivio/<nome>/<data>/<nome>/SKILL.md)."""
    voci = []
    if not cartella.exists():
        return voci
    for md in sorted(cartella.glob("*/*/*/SKILL.md")):
        v = _carica(md.parent, "archivio", "tua", sola_lettura=True, extra={"esportata": md.parent.parent.name})
        if v:
            voci.append(v)
    return voci


def terze_parti(cartella: Path = TERZE):
    """Skill di terze parti installate con manage-skill (si aggiornano dalla loro sorgente)."""
    voci = []
    if not cartella.exists():
        return voci
    for d in sorted(cartella.iterdir()):
        if d.is_dir():
            v = _carica(d, "terze-parti", "terze parti")
            if v:
                voci.append(v)
    return voci


def _overrides(cartelle) -> dict:
    """skillOverrides dai settings di Claude Code: utente, poi progetto e locale (l'ultimo vince)."""
    risultato = {}
    for c in cartelle:
        for nome in ("settings.json", "settings.local.json"):
            p = c / nome
            try:
                risultato.update(json.loads(p.read_text(encoding="utf-8")).get("skillOverrides") or {})
            except (OSError, ValueError, AttributeError):
                pass
    return risultato


STATI = {"off": "disattivata", "user-invocable-only": "solo manuale", "name-only": "attiva (compatta)"}


def stato(v: Voce) -> dict:
    """Se la skill è attiva per Claude.

    claude-code / progetto: skillOverrides nei settings ("off", "user-invocable-only", "name-only") e
    disable-model-invocation nel frontmatter. claude.ai: l'interruttore sta solo sul sito (Impostazioni >
    Capacità), la copia sincronizzata non lo riporta. Archivio e terze parti non sono caricati da Claude."""
    if v.fonte in ("claude-code", "progetto"):
        cartelle = [HOME_CLAUDE]
        if v.fonte == "progetto" and v.extra.get("progetto"):
            cartelle.append(Path(v.extra["progetto"]) / ".claude")
        valore = _overrides(cartelle).get(v.skill.nome)
        if valore in STATI:
            return {"stato": STATI[valore], "attiva": valore != "off", "perche": f"skillOverrides: {valore}"}
        if str(v.skill.frontmatter.get("disable-model-invocation", "")).lower() == "true":
            return {"stato": "solo manuale", "attiva": True, "perche": "disable-model-invocation: true nel frontmatter"}
        return {"stato": "attiva", "attiva": True, "perche": "caricata da Claude Code"}
    if v.fonte == "claude-ai":
        return {"stato": "su claude.ai", "attiva": None,
                "perche": "lo stato attiva/disattiva si vede solo su claude.ai (Impostazioni > Capacità > Skill)"}
    if v.fonte == "plugin":
        return {"stato": "plugin", "attiva": None, "perche": "dipende dal plugin"}
    return {"stato": "non caricata", "attiva": False, "perche": "copia di manage-skill, Claude non la usa da qui"}


def data_modifica(v: Voce) -> float:
    """Quando è stata modificata davvero la copia. Per claude.ai conta la data del manifest (aggiornamento sul cloud):
    i file locali hanno la data della sincronizzazione, non quella della modifica."""
    if v.fonte == "claude-ai" and v.extra.get("aggiornata_claude_ai"):
        valore = v.extra["aggiornata_claude_ai"]
        try:
            if isinstance(valore, (int, float)) or str(valore).isdigit():
                return int(valore) / 1000
            return datetime.fromisoformat(str(valore).replace("Z", "+00:00")).timestamp()
        except ValueError:
            pass
    return v.skill.modificata


FONTI = {"claude-code": claude_code, "progetto": progetti, "plugin": plugin, "claude-ai": claude_ai, "terze-parti": terze_parti, "archivio": archivio}


def tutte(fonti=None):
    voci = []
    for nome, funzione in FONTI.items():
        if fonti and nome not in fonti:
            continue
        voci.extend(funzione())
    return voci
