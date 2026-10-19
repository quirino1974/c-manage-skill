# manage-skill: catalogo, esportazione e sincronizzazione delle skill di Claude
# Copyright (C) 2026 Quirino Scaramastra
# SPDX-License-Identifier: GPL-3.0-or-later
"""Prompt per ricreare una skill: un testo da incollare in Claude (claude.ai, Claude Code o un'altra chat)
che ricostruisce la skill con la stessa struttura e gli stessi file.

Due modalità:
  completo     tutti i file di testo, parola per parola (la skill torna identica);
  essenziale   solo SKILL.md e l'elenco degli altri file, che Claude riscrive dalle istruzioni.

Le righe in cui il controllo dei segreti trova chiavi, token o password vengono oscurate: il prompt è fatto
per essere incollato in una chat, e lì non devono finire credenziali.
"""

from pathlib import Path

from . import lingua
from . import skill as sk

LIMITE_FILE = 200_000      # oltre questa dimensione un file viene solo elencato
LIMITE_TOTALE = 600_000    # oltre questo totale gli altri file vengono solo elencati

LINGUAGGI = {".py": "python", ".sh": "bash", ".js": "javascript", ".mjs": "javascript", ".ts": "typescript",
             ".json": "json", ".yaml": "yaml", ".yml": "yaml", ".md": "markdown", ".html": "html", ".css": "css",
             ".toml": "toml", ".xml": "xml", ".sql": "sql", ".php": "php", ".txt": "text", ".csv": "csv"}

TESTI = {
    "it": {
        "titolo": "Ricrea la skill di Claude \"{nome}\"",
        "intro": ("Crea una skill di Claude chiamata `{nome}`, identica a quella descritta qui sotto. "
                  "Una skill è una cartella con un file `SKILL.md` (intestazione YAML con `name` e `description`, "
                  "poi le istruzioni) e gli eventuali file di supporto."),
        "come_completo": ("Ricrea **esattamente** la struttura e il contenuto di ogni file: non riassumere, non "
                          "tradurre e non migliorare il testo. Se puoi scrivere file (Claude Code o l'esecuzione di "
                          "codice), crea la cartella `{nome}/` con questi file; altrimenti restituisci ogni file in un "
                          "blocco separato con il suo percorso, e alla fine uno ZIP o le istruzioni per crearlo."),
        "come_essenziale": ("Usa il `SKILL.md` qui sotto così com'è. Gli altri file sono solo elencati: riscrivili tu "
                            "seguendo le istruzioni della skill, con lo stesso percorso e lo stesso scopo. Se puoi "
                            "scrivere file, crea la cartella `{nome}/`; altrimenti restituisci ogni file in un blocco "
                            "separato con il suo percorso."),
        "dove": ("Dove installarla: in Claude Code nella cartella `~/.claude/skills/{nome}/`; su claude.ai comprimi la "
                 "cartella `{nome}/` in uno ZIP e caricalo da Impostazioni > Capacità > Skill."),
        "struttura": "Struttura",
        "file": "File",
        "solo_elencati": "File solo elencati (da ricreare o da copiare a parte)",
        "binario": "file binario, {kb} KB: non incluso, va copiato a parte",
        "grande": "{kb} KB: troppo grande per il prompt, va copiato a parte",
        "da_scrivere": "da riscrivere seguendo le istruzioni della skill",
        "oscurato": "[OSCURATO da manage-skill: possibile segreto ({tipo}). Inserisci qui il valore corretto.]",
        "avviso_segreti": "Nota: {n} righe sono state oscurate perché sembravano contenere chiavi, token o password.",
        "fine": "Alla fine verifica che `SKILL.md` abbia `name: {nome}` e una `description` sotto i 1024 caratteri.",
    },
    "en": {
        "titolo": "Recreate the Claude skill \"{nome}\"",
        "intro": ("Create a Claude skill named `{nome}`, identical to the one described below. "
                  "A skill is a folder with a `SKILL.md` file (YAML header with `name` and `description`, then the "
                  "instructions) and any supporting files."),
        "come_completo": ("Recreate **exactly** the structure and the content of every file: do not summarize, "
                          "translate or improve the text. If you can write files (Claude Code or code execution), "
                          "create the folder `{nome}/` with these files; otherwise return each file in its own block "
                          "with its path, and at the end a ZIP or instructions to build it."),
        "come_essenziale": ("Use the `SKILL.md` below as it is. The other files are only listed: write them yourself "
                            "following the skill's instructions, with the same path and the same purpose. If you can "
                            "write files, create the folder `{nome}/`; otherwise return each file in its own block "
                            "with its path."),
        "dove": ("Where to install it: in Claude Code in the folder `~/.claude/skills/{nome}/`; on claude.ai zip the "
                 "`{nome}/` folder and upload it from Settings > Capabilities > Skills."),
        "struttura": "Structure",
        "file": "Files",
        "solo_elencati": "Files only listed (to recreate or copy separately)",
        "binario": "binary file, {kb} KB: not included, copy it separately",
        "grande": "{kb} KB: too large for the prompt, copy it separately",
        "da_scrivere": "to be written following the skill's instructions",
        "oscurato": "[REDACTED by manage-skill: possible secret ({tipo}). Put the correct value here.]",
        "avviso_segreti": "Note: {n} lines were redacted because they seemed to contain keys, tokens or passwords.",
        "fine": "At the end check that `SKILL.md` has `name: {nome}` and a `description` under 1024 characters.",
    },
}


def _recinto(testo: str) -> str:
    """Un recinto di backtick più lungo di quelli presenti nel testo (i file markdown ne contengono)."""
    lunghezza = 3
    for riga in testo.splitlines():
        s = riga.lstrip()
        if s.startswith("```"):
            lunghezza = max(lunghezza, len(s) - len(s.lstrip("`")) + 1)
    return "`" * lunghezza


def _albero(nome: str, file: list) -> str:
    """Albero delle cartelle: ogni cartella una volta, poi i suoi file, rientrati per livello."""
    righe, viste = [f"{nome}/"], set()
    for f in sorted(file, key=lambda x: (x.count("/") > 0, x)):
        parti = f.split("/")
        for i in range(1, len(parti)):
            cartella = "/".join(parti[:i])
            if cartella not in viste:
                viste.add(cartella)
                righe.append("  " * i + parti[i - 1] + "/")
        righe.append("  " * len(parti) + parti[-1])
    return "\n".join(righe)


def crea(s: sk.Skill, modalita: str = "completo", codice_lingua: str = None) -> dict:
    """Ritorna {testo, caratteri, file_inclusi, file_elencati, oscurate}."""
    T = TESTI["en" if (codice_lingua or lingua.attuale()) == "en" else "it"]
    nome = s.nome
    segreti = {}
    for f, tipo, riga in sk.cerca_segreti(s):
        segreti.setdefault(f, {})[riga] = tipo
    parti = [f"# {T['titolo'].format(nome=nome)}", "", T["intro"].format(nome=nome), "",
             T["come_completo" if modalita == "completo" else "come_essenziale"].format(nome=nome), "",
             T["dove"].format(nome=nome), "", f"## {T['struttura']}", "", "```", _albero(nome, s.file), "```", "",
             f"## {T['file']}", ""]
    elencati, inclusi, totale, oscurate = [], [], 0, 0
    ordine = sorted(s.file, key=lambda f: (f != "SKILL.md", f))
    for rel in ordine:
        p = s.cartella / rel
        dim = p.stat().st_size
        kb = round(dim / 1024, 1)
        if modalita != "completo" and rel != "SKILL.md":
            elencati.append(f"- `{rel}`: {T['da_scrivere']}")
            continue
        if rel in segreti and segreti[rel].get(0):  # file sensibile intero (.env, chiavi)
            elencati.append(f"- `{rel}`: {T['oscurato'].format(tipo=segreti[rel][0])}")
            oscurate += 1
            continue
        try:
            testo = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            elencati.append(f"- `{rel}`: {T['binario'].format(kb=kb)}")
            continue
        if dim > LIMITE_FILE or totale + dim > LIMITE_TOTALE:
            elencati.append(f"- `{rel}`: {T['grande'].format(kb=kb)}")
            continue
        if rel in segreti:
            righe = testo.split("\n")
            for n, tipo in segreti[rel].items():
                if 1 <= n <= len(righe):
                    rientro = righe[n - 1][:len(righe[n - 1]) - len(righe[n - 1].lstrip())]
                    righe[n - 1] = rientro + T["oscurato"].format(tipo=lingua.t(tipo))
                    oscurate += 1
            testo = "\n".join(righe)
        recinto = _recinto(testo)
        parti += [f"### `{nome}/{rel}`", "", f"{recinto}{LINGUAGGI.get(Path(rel).suffix.lower(), '')}",
                  testo.rstrip("\n"), recinto, ""]
        inclusi.append(rel)
        totale += dim
    if elencati:
        parti += [f"## {T['solo_elencati']}", "", *elencati, ""]
    if oscurate:
        parti += [T["avviso_segreti"].format(n=oscurate), ""]
    parti.append(T["fine"].format(nome=nome))
    testo = "\n".join(parti) + "\n"
    return {"testo": testo, "caratteri": len(testo), "file_inclusi": inclusi, "file_elencati": len(elencati),
            "oscurate": oscurate, "nome": nome}
