# c-manage-skill: catalogo, esportazione e sincronizzazione delle skill di Claude
# Copyright (C) 2026 Quirino Scaramastra
# SPDX-License-Identifier: GPL-3.0-or-later
"""Riga di comando di c-manage-skill (comando: ms). Esegui 'ms --help' o 'ms <comando> --help'."""

import argparse
import json
import sys
import webbrowser
from pathlib import Path

from . import COPYRIGHT, __version__, account, lingua, api_anthropic, catalogo, chiavi, cloud, note, pacchetti, sorgenti, terze
from . import skill as sk
from .config import impostazioni

FONTI = list(sorgenti.FONTI)
_print = print


def print(*valori, **opzioni):  # noqa: A001 - i messaggi passano dal dizionario della lingua scelta
    _print(*(lingua.t(v) if isinstance(v, str) else v for v in valori), **opzioni)


def _traduci_aiuto(p: argparse.ArgumentParser) -> None:
    """Traduce descrizioni e aiuti di tutti i comandi (C_MANAGE_SKILL_LINGUA=en)."""
    p.description = lingua.t(p.description)
    for azione in p._actions:
        if azione.help and azione.help != argparse.SUPPRESS:
            azione.help = lingua.t(azione.help)
        if isinstance(azione, argparse._SubParsersAction):
            for scelta in azione._choices_actions:
                scelta.help = lingua.t(scelta.help)
            for sotto in azione.choices.values():
                _traduci_aiuto(sotto)


def _stampa_tabella(righe, colonne):
    if not righe:
        print("(nessuna)")
        return
    # valori come categorie, stati e note predefinite nella lingua scelta (nomi e percorsi restano come sono)
    righe = [{c: lingua.t(r.get(c, "")) if isinstance(r.get(c, ""), str) else r.get(c, "") for c in colonne} for r in righe]
    larg = {c: min(max(len(c), *(len(str(r.get(c, ""))) for r in righe)), 60) for c in colonne}
    titoli = {c: lingua.intestazione(c) for c in colonne}
    larg = {c: max(larg[c], len(titoli[c])) for c in colonne}
    print("  ".join(titoli[c].upper().ljust(larg[c]) for c in colonne))
    for r in righe:
        print("  ".join(str(r.get(c, ""))[:larg[c]].ljust(larg[c]) for c in colonne))


# ---------------------------------------------------------------- catalogo e descrizione

def cmd_catalogo(a):
    righe = catalogo.costruisci(a.fonte)
    if a.json:
        print(json.dumps(righe, indent=2, ensure_ascii=False))
        return
    if a.categoria:
        righe = [r for r in righe if a.categoria.lower() in r["categoria"].lower()]
    if a.mie:
        righe = [r for r in righe if r["origine"] == "tua"]
    vista = [{**r, "fonti": ",".join(r["fonti"]), "stato": "ok" if r["allineata"] else "DIVERSE",
              "attiva": r["attivazione"]["stato"]} for r in righe]
    _stampa_tabella(vista, ["nome", "categoria", "attiva", "fonti", "file", "kb", "stato"])
    file = catalogo.salva(catalogo.costruisci(a.fonte))
    print(f"\n{len(righe)} skill. Catalogo salvato in {file['html']} e {file['json']}")
    if a.apri:
        webbrowser.open(file["html"].as_uri())


def cmd_descrivi(a):
    v = pacchetti.trova(a.nome, a.da)
    s = v.skill
    copie = [x for x in sorgenti.tutte() if x.skill.nome == a.nome]
    print(f"{s.nome}\n{'=' * len(s.nome)}")
    print(f"Categoria:   {catalogo.categoria(s.nome, s.descrizione)}")
    print(f"Origine:     {v.origine}")
    print(f"Cartella:    {v.percorso}" + (f"  (collegamento a {v.collegamento})" if v.collegamento else ""))
    print(f"Dimensione:  {len(s.file)} file, {s.kb} KB · impronta {s.impronta}")
    altri = {k: val for k, val in s.frontmatter.items() if k not in ("name", "description")}
    if altri:
        print("Frontmatter: " + ", ".join(f"{k}={val}" for k, val in altri.items()))
    print(f"\nDescrizione:\n  {s.descrizione}\n\nFile:")
    for f in s.file:
        print(f"  {f}  ({(s.cartella / f).stat().st_size} byte)")
    print("\nCopie:")
    for c in copie:
        nota = " (sola lettura)" if c.sola_lettura else ""
        print(f"  {c.fonte:12} {c.skill.impronta}  {c.percorso}{nota}")
    problemi = sk.valida(s, impostazioni()["limite_mb"])
    print("\nSkills API: " + ("pronta per l'importazione" if not problemi else "da sistemare:\n  - " + "\n  - ".join(problemi)))
    segreti = sk.cerca_segreti(s)
    print("Segreti:    " + ("nessuno trovato" if not segreti else f"{len(segreti)} da controllare (ms segreti {s.nome})"))


def cmd_confronta(a):
    risultati = catalogo.differenze(a.nome)
    if not risultati:
        print(f"'{a.nome}' ha una sola copia.")
    for x, y, agg, tolti, camb in risultati:
        print(f"{x}\n  vs {y}")
        if not (agg or tolti or camb):
            print("  identiche")
        for f in agg:
            print(f"  + {f}  (solo nella seconda)")
        for f in tolti:
            print(f"  - {f}  (solo nella prima)")
        for f in camb:
            print(f"  ~ {f}  (contenuto diverso)")


def cmd_valida(a):
    v = _voce(a.skill, a.da)
    problemi = sk.valida(v.skill, impostazioni()["limite_mb"])
    print(f"{v.skill.nome}: " + ("valida per la Skills API" if not problemi else "\n  - " + "\n  - ".join(problemi)))
    return 1 if problemi else 0


def cmd_segreti(a):
    if a.tutte:
        import os
        visti, voci = set(), []
        for v in sorgenti.tutte(["claude-code", "progetto"]):
            reale = os.path.realpath(v.percorso)
            if reale not in visti:
                visti.add(reale)
                voci.append(v)
    else:
        if not a.skill:
            raise SystemExit("Indica una skill oppure --tutte.")
        voci = [_voce(a.skill, a.da)]
    trovati = 0
    for v in voci:
        for f, tipo, riga in sk.cerca_segreti(v.skill):
            trovati += 1
            print(f"{v.skill.nome}: {f}:{riga}  {tipo}")
    print("Nessun segreto trovato." if not trovati else f"\n{trovati} punti da controllare (il valore non viene mai mostrato).")
    return 1 if trovati else 0


def _voce(nome_o_percorso, fonte=None):
    p = Path(nome_o_percorso).expanduser()
    if p.exists():
        return pacchetti.da_percorso(p)
    return pacchetti.trova(nome_o_percorso, fonte)


def _selezione(a):
    if getattr(a, "mie", False):
        voci = [v for v in sorgenti.tutte([a.da] if a.da else ["claude-code", "progetto", "claude-ai"]) if v.origine == "tua"]
        visti, scelte = set(), []
        for v in sorted(voci, key=lambda v: {"claude-code": 0, "progetto": 1, "claude-ai": 2}.get(v.fonte, 9)):
            if v.skill.nome not in visti:
                visti.add(v.skill.nome)
                scelte.append(v)
        return scelte
    if not a.skill:
        raise SystemExit("Indica una o più skill, oppure --mie.")
    return [_voce(n, a.da) for n in a.skill]


# ---------------------------------------------------------------- esportazione e importazione

def cmd_esporta(a):
    errori = 0
    for v in _selezione(a):
        try:
            base = pacchetti.esporta(v, forza_segreti=a.ignora_segreti)
            print(f"OK  {v.skill.nome:40} da {v.fonte:11} -> {base}")
        except pacchetti.Bloccato as e:
            errori += 1
            print(f"NO  {e}")
    return 1 if errori else 0


def cmd_importa(a):
    errori = 0
    for v in _selezione(a):
        try:
            esito = pacchetti.importa(v, a.verso, sovrascrivi=a.sovrascrivi, prova=a.prova, forza_segreti=a.ignora_segreti)
            dettagli = ", ".join(f"{k}={val}" for k, val in esito.items() if k not in ("account", "tipo"))
            print(f"{'PROVA' if a.prova else 'OK'}  {v.skill.nome:40} -> {a.verso}: {dettagli}")
        except pacchetti.Bloccato as e:
            errori += 1
            print(f"NO  {v.skill.nome}: {e}")
    return 1 if errori else 0


# ---------------------------------------------------------------- account e chiavi

def cmd_account_elenco(a):
    righe = []
    for nome, d in account.tutti().items():
        righe.append({"nome": nome, "tipo": d["tipo"], "dove": d.get("cartella") or d.get("workspace_id") or "",
                      "chiave": d.get("chiave", "") if d["tipo"] == "api" else "-", "nota": d.get("nota", "")})
    _stampa_tabella(righe, ["nome", "tipo", "dove", "chiave", "nota"])


def cmd_account_aggiungi(a):
    if a.nome in account.tutti() and not a.sostituisci:
        raise SystemExit(f"L'account '{a.nome}' esiste già: usa --sostituisci per ridefinirlo.")
    dati = {"tipo": a.tipo, "nota": a.nota or ""}
    if a.tipo == "api":
        dati["chiave"] = a.chiave
        if a.workspace:
            dati["workspace_id"] = a.workspace
        if a.base_url:
            dati["base_url"] = a.base_url
        if a.chiave in ("keyring", "file"):
            chiavi.salva(a.nome, a.chiave, chiavi.chiedi(a.nome))
    elif a.tipo in ("claude-code", "claude-ai"):
        if a.tipo == "claude-code" and not a.cartella:
            raise SystemExit("Per un account claude-code indica --cartella (es. ~/.claude/skills o <progetto>/.claude/skills).")
        if a.cartella:
            dati["cartella"] = str(Path(a.cartella).expanduser())
    account.aggiungi(a.nome, dati)
    print(f"Account '{a.nome}' ({a.tipo}) salvato." + (" Chiave salvata in " + a.chiave + "." if a.tipo == "api" and a.chiave in ("keyring", "file") else ""))


def cmd_account_console(a):
    from . import servizi
    try:
        esito = servizi.configura_console({"nome": a.nome, "valore_chiave": chiavi.chiedi(a.nome), "dove": a.dove,
                                            "workspace_id": a.workspace or "", "sostituisci": a.sostituisci})
    except servizi.Errore as e:
        print(f"NO: {e}")
        return 1
    print(esito["messaggio"])


def cmd_account_chiave(a):
    d = account.leggi(a.nome)
    if d["tipo"] != "api":
        raise SystemExit("Solo gli account di tipo api hanno una chiave.")
    dove = a.dove or d.get("chiave", "keyring")
    if dove not in ("keyring", "file"):
        raise SystemExit(f"La chiave di '{a.nome}' arriva da '{dove}': si cambia lì, non qui.")
    chiavi.salva(a.nome, dove, chiavi.chiedi(a.nome))
    if dove != d.get("chiave"):
        reg = {k: v for k, v in d.items() if k != "nome"}
        reg["chiave"] = dove
        account.aggiungi(a.nome, reg)
    print(f"Chiave di '{a.nome}' aggiornata ({dove}).")


def cmd_account_prova(a):
    d = account.leggi(a.nome)
    if d["tipo"] == "api":
        try:
            skill = api_anthropic.elenca(d)
            chiave = chiavi.leggi(a.nome, d.get("chiave", "keyring"))
            print(f"OK: chiave {chiavi.maschera(chiave) if chiave else '(profilo ant)'} valida, {len(skill)} skill custom nell'account.")
        except Exception as e:
            print(f"NO: {api_anthropic.errore_leggibile(e)}")
            return 1
    else:
        c = account.cartella(d) if d.get("cartella") else None
        print(f"Cartella {c}: " + ("esiste" if c and c.exists() else "non esiste ancora (verrà creata al primo import)") if c else "nessuna cartella: gli ZIP vanno in c_manage_skill/archivio/_da-caricare")


def cmd_account_rimuovi(a):
    d = account.rimuovi(a.nome)
    if d.get("tipo") == "api" and d.get("chiave") in ("keyring", "file"):
        chiavi.elimina(a.nome, d["chiave"])
        print("Chiave eliminata.")
    print(f"Account '{a.nome}' rimosso.")


# ---------------------------------------------------------------- skill negli account API

def cmd_remoto_elenco(a):
    try:
        _stampa_tabella(api_anthropic.elenca(account.leggi(a.account), tutte_le_fonti=a.tutte),
                        ["nome", "id", "fonte", "versione", "creata"])
    except Exception as e:
        print(f"NO: {api_anthropic.errore_leggibile(e)}")
        return 1


def cmd_remoto_versioni(a):
    d = account.leggi(a.account)
    s = api_anthropic.trova(d, a.nome)
    if not s:
        raise SystemExit(f"'{a.nome}' non c'è nell'account {a.account}.")
    _stampa_tabella(api_anthropic.versioni(d, s["id"]), ["id", "creata", "nome"])


def cmd_remoto_elimina(a):
    d = account.leggi(a.account)
    s = api_anthropic.trova(d, a.nome)
    if not s:
        raise SystemExit(f"'{a.nome}' non c'è nell'account {a.account}.")
    if not a.si:
        risposta = input(f"Eliminare '{a.nome}' ({s['id']}) e tutte le sue versioni da {a.account}? Scrivi SI: ")
        if risposta.strip() != "SI":
            print("Annullato.")
            return 1
    api_anthropic.elimina(d, s["id"])
    print(f"'{a.nome}' eliminata da {a.account}.")


# ---------------------------------------------------------------- skill del cloud (claude.ai)

def cmd_cloud_elenco(a):
    for c in cloud.conti():
        print(f"Account {c['nome']}: {c['skill']} skill, sincronizzate da Claude Code il {c['aggiornato']}")
    righe = cloud.elenca(sole_mie=a.mie)
    if a.json:
        print(json.dumps(righe, indent=2, ensure_ascii=False))
        return
    _stampa_tabella(righe, ["nome", "tipo", "categoria", "aggiornata", "file", "kb", "locale"])
    print(f"\n{len(righe)} skill nel cloud. 'locale' confronta con la copia di Claude Code (uguale, diversa, assente).")
    if a.api:
        print("\nAccount API (solo metadati, l'API non permette di scaricare i file):")
        _stampa_tabella(cloud.elenca_api(), ["account", "nome", "id", "versione", "creata", "errore"])


def cmd_cloud_esporta(a):
    if not (a.skill or a.mie):
        raise SystemExit("Indica una o più skill, oppure --mie.")
    risultati = cloud.esporta(nomi=a.skill or None, sole_mie=a.mie, forza_segreti=a.ignora_segreti)
    errori = 0
    for nome, r in risultati.items():
        if r["cartella"]:
            print(f"OK  {nome}: {len(r['esportate'])} skill in {r['cartella']}")
            if r["cambiate"]:
                print(f"    nuove o cambiate rispetto all'esportazione precedente: {', '.join(r['cambiate'])}")
        for s in r["saltate"]:
            errori += 1
            dove = ", ".join(f"{x['file']}:{x['riga']}" for x in s["segreti"])
            print(f"NO  {s['nome']}: {s['motivo']} ({dove}); usa --ignora-segreti se sono falsi allarmi")
    return 1 if errori else 0


def cmd_cloud_verso_api(a):
    esiti = cloud.verso_api(a.account, nomi=a.skill or None, prova=a.prova, forza=a.forza,
                            forza_segreti=a.ignora_segreti)
    errori = 0
    for e in esiti:
        if e["ok"]:
            dettagli = ", ".join(f"{k}={v}" for k, v in e.items() if k not in ("nome", "ok", "avviso"))
            print(f"{'PROVA' if a.prova else 'OK'}  {e['nome']:40} {dettagli}")
        else:
            errori += 1
            print(f"NO  {e['nome']:40} {e['errore']}")
        if e.get("avviso"):
            print(f"    attenzione: {e['avviso']}")
    return 1 if errori else 0


def cmd_cloud_storico(a):
    _stampa_tabella(cloud.esportazioni(), ["account", "data", "skill", "cambiate", "saltate", "sincronizzato", "cartella"])


# ---------------------------------------------------------------- prompt per ricreare una skill

def cmd_prompt(a):
    import shutil
    import subprocess
    from . import prompt
    v = _voce(a.skill, a.da)
    r = prompt.crea(v.skill, modalita="essenziale" if a.essenziale else "completo")
    if a.file:
        Path(a.file).expanduser().write_text(r["testo"], encoding="utf-8")
        print(f"Prompt salvato in {a.file} ({r['caratteri']} caratteri).")
    elif a.copia:
        programma = next(([p, *argomenti] for p, argomenti in (("wl-copy", []), ("xclip", ["-selection", "clipboard"]),
                                                                ("xsel", ["--clipboard", "--input"])) if shutil.which(p)), None)
        if not programma:
            raise SystemExit("Per copiare negli appunti serve wl-copy (wl-clipboard), xclip o xsel; usa --file in alternativa.")
        subprocess.run(programma, input=r["testo"].encode(), check=True)
        print(f"Prompt di '{r['nome']}' copiato negli appunti ({r['caratteri']} caratteri).")
    else:
        _print(r["testo"], end="")
    if r["oscurate"] and (a.file or a.copia):
        print(f"Attenzione: {r['oscurate']} righe oscurate per possibili segreti.")


# ---------------------------------------------------------------- note

def cmd_nota(a):
    if a.cancella:
        note.scrivi(a.nome, "")
        print(f"Nota di '{a.nome}' cancellata.")
    elif a.testo:
        note.scrivi(a.nome, " ".join(a.testo))
        print(f"Nota di '{a.nome}' salvata.")
    else:
        print(note.leggi(a.nome) or f"'{a.nome}' non ha note.")


# ---------------------------------------------------------------- terze parti

def _esiti(esiti, prova=False):
    errori = 0
    for e in esiti:
        dove = f" -> {e['account']}" if e.get("account") else ""
        if e["ok"]:
            dettagli = ", ".join(f"{k}={v}" for k, v in e.items() if k not in ("nome", "ok", "account", "avviso"))
            print(f"{'PROVA' if prova else 'OK'}  {e['nome']}{dove}: {dettagli}")
        else:
            errori += 1
            print(f"NO  {e['nome']}{dove}: {e['errore']}")
        if e.get("avviso"):
            print(f"    attenzione: {e['avviso']}")
    return 1 if errori else 0


def cmd_terze_elenco(a):
    righe = [{**r, "destinazioni": ",".join(r["destinazioni"]), "script": len(r["script"])} for r in terze.elenco()]
    _stampa_tabella(righe, ["nome", "stato", "commit", "aggiornata", "sincronizzata", "destinazioni", "script", "sorgente"])


def cmd_terze_anteprima(a):
    r = terze.anteprima(a.sorgente)
    print(f"{r['tipo']} {r['commit']}: {len(r['skill'])} skill")
    _stampa_tabella([{**s, "script": len(s["script"]), "installata": "sì" if s["gia_installata"] else ""} for s in r["skill"]],
                    ["percorso", "nome", "file", "kb", "script", "segreti", "installata"])


def cmd_terze_aggiungi(a):
    return _esiti(terze.aggiungi(a.sorgente, percorsi=a.percorso, destinazioni=a.verso, sostituisci=a.sostituisci))


def cmd_terze_aggiorna(a):
    return _esiti(terze.aggiorna(a.nomi or None, forza=a.forza))


def cmd_terze_destinazioni(a):
    info = terze.destinazioni(a.nome, a.account)
    print(f"Destinazioni di '{a.nome}': {', '.join(info['destinazioni']) or 'nessuna'}")


def cmd_terze_sincronizza(a):
    return _esiti(terze.sincronizza(a.nomi or None, verso=a.verso, prova=a.prova, forza=a.forza, forza_segreti=a.ignora_segreti), a.prova)


def cmd_terze_rimuovi(a):
    terze.rimuovi(a.nome)
    print(f"'{a.nome}' rimossa (copia in archivio). Le copie già negli account restano.")


# ---------------------------------------------------------------- parser

class _Versione(argparse.Action):
    """Stampa versione, copyright e licenza mantenendo gli a capo (l'azione 'version' li unisce)."""

    def __call__(self, parser, namespace, values, option_string=None):
        if lingua.attuale() == "en":
            testo = (f"c-manage-skill {__version__}\n{COPYRIGHT}\n"
                     "License GNU GPL v3 or later <https://www.gnu.org/licenses/gpl-3.0.html>.\n"
                     "This is free software, with no warranty. Details in the LICENSE and COPYRIGHT files.")
        else:
            testo = (f"c-manage-skill {__version__}\n{COPYRIGHT}\n"
                     "Licenza GNU GPL v3 o successiva <https://www.gnu.org/licenses/gpl-3.0.html>.\n"
                     "Questo è software libero, senza alcuna garanzia. Dettagli nei file LICENSE e COPYRIGHT.")
        _print(testo)
        parser.exit()


def parser():
    p = argparse.ArgumentParser(prog="ms", description="Esporta, cataloga, descrive e sposta le skill di Claude tra account.")
    p.add_argument("--versione", action=_Versione, nargs=0, help="versione, copyright e licenza")
    sub = p.add_subparsers(dest="comando", required=True)

    c = sub.add_parser("catalogo", help="elenca e cataloga tutte le skill trovate (salva HTML e JSON)")
    c.add_argument("--fonte", nargs="*", choices=FONTI, help="solo queste fonti")
    c.add_argument("--categoria", help="solo una categoria (anche parziale)")
    c.add_argument("--mie", action="store_true", help="solo le skill create da te")
    c.add_argument("--json", action="store_true", help="stampa il catalogo in JSON")
    c.add_argument("--apri", action="store_true", help="apre il catalogo HTML nel browser")
    c.set_defaults(f=cmd_catalogo)

    c = sub.add_parser("descrivi", help="scheda completa di una skill")
    c.add_argument("nome"); c.add_argument("--da", choices=FONTI); c.set_defaults(f=cmd_descrivi)

    c = sub.add_parser("confronta", help="differenze file per file tra le copie di una skill")
    c.add_argument("nome"); c.set_defaults(f=cmd_confronta)

    c = sub.add_parser("valida", help="controlla le regole della Skills API (nome, descrizione, dimensione)")
    c.add_argument("skill", help="nome, cartella o ZIP"); c.add_argument("--da", choices=FONTI); c.set_defaults(f=cmd_valida)

    c = sub.add_parser("segreti", help="cerca chiavi, token e password nei file di una skill")
    c.add_argument("skill", nargs="?"); c.add_argument("--da", choices=FONTI)
    c.add_argument("--tutte", action="store_true", help="tutte le skill di Claude Code e dei progetti"); c.set_defaults(f=cmd_segreti)

    for nome, aiuto, funzione in (("esporta", "esporta in c_manage_skill/archivio/ (cartella + ZIP + skill.json)", cmd_esporta),
                                  ("importa", "porta skill in un account (api, claude-code, claude-ai)", cmd_importa)):
        c = sub.add_parser(nome, help=aiuto)
        c.add_argument("skill", nargs="*", help="nomi, cartelle o ZIP")
        c.add_argument("--da", choices=FONTI, help="fonte da cui prendere la skill")
        c.add_argument("--mie", action="store_true", help="tutte le skill create da te")
        c.add_argument("--ignora-segreti", action="store_true", help="procede anche se il controllo segreti trova qualcosa")
        if nome == "importa":
            c.add_argument("--verso", required=True, help="account di destinazione (ms account elenco)")
            c.add_argument("--sovrascrivi", action="store_true", help="claude-code: sostituisce una copia diversa (salvata prima in archivio)")
            c.add_argument("--prova", action="store_true", help="mostra cosa farebbe, senza modificare nulla")
        c.set_defaults(f=funzione)

    ac = sub.add_parser("account", help="gestione degli account e delle chiavi").add_subparsers(dest="azione", required=True)
    c = ac.add_parser("elenco"); c.set_defaults(f=cmd_account_elenco)
    c = ac.add_parser("aggiungi")
    c.add_argument("nome"); c.add_argument("--tipo", required=True, choices=list(account.TIPI))
    c.add_argument("--chiave", default="keyring", help="api: keyring (predefinito), file, env:VARIABILE, ant")
    c.add_argument("--workspace", help="api: id del workspace (facoltativo)")
    c.add_argument("--base-url", help="api: endpoint alternativo (facoltativo)")
    c.add_argument("--cartella", help="claude-code: cartella delle skill; claude-ai: dove salvare gli ZIP")
    c.add_argument("--nota"); c.add_argument("--sostituisci", action="store_true"); c.set_defaults(f=cmd_account_aggiungi)
    c = ac.add_parser("console", help="account API della Claude Console: prova la chiave e la salva solo se funziona")
    c.add_argument("nome", nargs="?", default="console"); c.add_argument("--dove", choices=["keyring", "file"], default="keyring")
    c.add_argument("--workspace"); c.add_argument("--sostituisci", action="store_true"); c.set_defaults(f=cmd_account_console)
    c = ac.add_parser("chiave", help="inserisce o sostituisce la chiave di un account api")
    c.add_argument("nome"); c.add_argument("--dove", choices=["keyring", "file"]); c.set_defaults(f=cmd_account_chiave)
    c = ac.add_parser("prova", help="verifica che l'account sia raggiungibile")
    c.add_argument("nome"); c.set_defaults(f=cmd_account_prova)
    c = ac.add_parser("rimuovi", help="toglie l'account e la sua chiave salvata")
    c.add_argument("nome"); c.set_defaults(f=cmd_account_rimuovi)

    rc = sub.add_parser("remoto", help="skill presenti in un account API").add_subparsers(dest="azione", required=True)
    c = rc.add_parser("elenco"); c.add_argument("account"); c.add_argument("--tutte", action="store_true", help="anche quelle di Anthropic")
    c.set_defaults(f=cmd_remoto_elenco)
    c = rc.add_parser("versioni"); c.add_argument("account"); c.add_argument("nome"); c.set_defaults(f=cmd_remoto_versioni)
    c = rc.add_parser("elimina"); c.add_argument("account"); c.add_argument("nome")
    c.add_argument("--si", action="store_true", help="non chiede conferma"); c.set_defaults(f=cmd_remoto_elimina)

    c = sub.add_parser("prompt", help="crea il prompt per ricreare una skill con Claude (da copiare e incollare)")
    c.add_argument("skill", help="nome, cartella o ZIP"); c.add_argument("--da", choices=FONTI)
    c.add_argument("--essenziale", action="store_true", help="solo SKILL.md e l'elenco degli altri file")
    c.add_argument("--copia", action="store_true", help="copia il prompt negli appunti")
    c.add_argument("--file", help="salva il prompt in un file"); c.set_defaults(f=cmd_prompt)

    c = sub.add_parser("nota", help="legge, scrive o cancella la nota di una skill")
    c.add_argument("nome"); c.add_argument("testo", nargs="*"); c.add_argument("--cancella", action="store_true")
    c.set_defaults(f=cmd_nota)

    tc = sub.add_parser("terze", help="skill di terze parti: aggiunta da Git/ZIP/cartella, aggiornamento, sincronizzazione").add_subparsers(dest="azione", required=True)
    c = tc.add_parser("elenco"); c.set_defaults(f=cmd_terze_elenco)
    c = tc.add_parser("anteprima", help="skill presenti in una sorgente, senza installare"); c.add_argument("sorgente"); c.set_defaults(f=cmd_terze_anteprima)
    c = tc.add_parser("aggiungi", help="installa skill da un repository Git, uno ZIP o una cartella")
    c.add_argument("sorgente"); c.add_argument("--percorso", nargs="*", help="cartelle delle skill nella sorgente (vedi anteprima)")
    c.add_argument("--verso", nargs="*", help="account in cui sincronizzarle"); c.add_argument("--sostituisci", action="store_true")
    c.set_defaults(f=cmd_terze_aggiungi)
    c = tc.add_parser("aggiorna", help="riscarica dalla sorgente le skill cambiate"); c.add_argument("nomi", nargs="*")
    c.add_argument("--forza", action="store_true", help="sostituisce anche le copie modificate qui"); c.set_defaults(f=cmd_terze_aggiorna)
    c = tc.add_parser("destinazioni", help="account in cui sincronizzare una skill"); c.add_argument("nome"); c.add_argument("account", nargs="*")
    c.set_defaults(f=cmd_terze_destinazioni)
    c = tc.add_parser("sincronizza", help="porta le skill negli account di destinazione"); c.add_argument("nomi", nargs="*")
    c.add_argument("--verso", help="solo questo account"); c.add_argument("--prova", action="store_true")
    c.add_argument("--forza", action="store_true", help="sostituisce copie modificate a mano negli account")
    c.add_argument("--ignora-segreti", action="store_true"); c.set_defaults(f=cmd_terze_sincronizza)
    c = tc.add_parser("rimuovi"); c.add_argument("nome"); c.set_defaults(f=cmd_terze_rimuovi)

    cc = sub.add_parser("cloud", help="skill dell'account claude.ai: catalogo ed esportazione in c_manage_skill/archivio/cloud/").add_subparsers(dest="azione", required=True)
    c = cc.add_parser("elenco", help="catalogo delle skill claude.ai")
    c.add_argument("--mie", action="store_true", help="solo le tue"); c.add_argument("--json", action="store_true")
    c.add_argument("--api", action="store_true", help="anche i metadati delle skill negli account API"); c.set_defaults(f=cmd_cloud_elenco)
    c = cc.add_parser("esporta", help="fotografa le skill in c_manage_skill/archivio/cloud/<account>/<data-ora>/")
    c.add_argument("skill", nargs="*", help="nomi delle skill (vuoto con --mie)")
    c.add_argument("--mie", action="store_true", help="tutte le tue")
    c.add_argument("--ignora-segreti", action="store_true"); c.set_defaults(f=cmd_cloud_esporta)
    c = cc.add_parser("storico", help="esportazioni presenti in c_manage_skill/archivio/cloud/"); c.set_defaults(f=cmd_cloud_storico)
    c = cc.add_parser("verso-api", help="importa le skill di claude.ai in un account API (nuove o nuove versioni)")
    c.add_argument("account", help="account di tipo api (ms account elenco)")
    c.add_argument("skill", nargs="*", help="solo queste (predefinito: tutte le tue)")
    c.add_argument("--prova", action="store_true", help="mostra cosa farebbe, senza caricare nulla")
    c.add_argument("--forza", action="store_true", help="ricarica anche le skill già aggiornate")
    c.add_argument("--ignora-segreti", action="store_true"); c.set_defaults(f=cmd_cloud_verso_api)
    return p


def main(argv=None):
    p = parser()
    if lingua.attuale() != "it":
        _traduci_aiuto(p)
    args = p.parse_args(argv)
    try:
        codice = args.f(args)
    except pacchetti.Bloccato as e:
        print(f"NO: {e}")
        codice = 1
    except SystemExit as e:
        if isinstance(e.code, str):  # messaggi di errore delle funzioni: tradotti come gli altri
            print(e.code)
            codice = 1
        else:
            raise
    except KeyboardInterrupt:
        print("\nInterrotto.")
        codice = 130
    sys.exit(codice or 0)


if __name__ == "__main__":
    main()
