# manage-skill: catalogo, esportazione e sincronizzazione delle skill di Claude
# Copyright (C) 2026 Quirino Scaramastra
# SPDX-License-Identifier: GPL-3.0-or-later
"""Funzioni di gestione usate dalle interfacce (finestra Qt, tramite motore.py): ricevono e restituiscono dati JSON."""

import hashlib
import os
from pathlib import Path

from . import COPYRIGHT, LICENZA, __version__, account, api_anthropic, catalogo, chiavi, cloud, lingua, note, pacchetti, prompt, sorgenti, terze
from . import skill as sk
from .config import ARCHIVIO, CATALOGO, impostazioni


class Errore(Exception):
    def __init__(self, messaggio, codice=400):
        super().__init__(messaggio)
        self.codice = codice


def stato(_):
    return {"versione": __version__, "copyright": COPYRIGHT, "licenza": LICENZA, "conti_cloud": cloud.conti(), "keyring": chiavi.keyring_disponibile(),
            "cartelle": {"archivio": str(ARCHIVIO), "cloud": str(cloud.CLOUD), "catalogo": str(CATALOGO), "terze": str(terze.TERZE)},
            "fonti": list(sorgenti.FONTI), "tipi_account": account.TIPI}


def elenco_catalogo(q):
    fonti = [f for f in q.get("fonti", "").split(",") if f] or None
    righe = catalogo.costruisci(fonti)
    catalogo.salva(righe)
    return {"skill": righe}


def scheda(q):
    v = pacchetti.trova(q["nome"], q.get("da") or None)
    s = v.skill
    testo = (s.cartella / "SKILL.md").read_text(encoding="utf-8", errors="replace")
    return {"nome": s.nome, "descrizione": s.descrizione, "categoria": catalogo.categoria(s.nome, s.descrizione),
            "origine": v.origine, "fonte": v.fonte, "percorso": str(v.percorso), "collegamento": v.collegamento,
            "frontmatter": s.frontmatter, "impronta": s.impronta, "kb": s.kb,
            "file": [{"nome": f, "byte": (s.cartella / f).stat().st_size} for f in s.file],
            "copie": _copie(s.nome),
            "problemi_api": sk.valida(s, impostazioni()["limite_mb"]),
            "segreti": [{"file": f, "tipo": t, "riga": r} for f, t, r in sk.cerca_segreti(s)],
            "skill_md": testo[:200_000], "nota": note.leggi(s.nome), "modificabile": not v.sola_lettura}


def _copie(nome):
    """Copie della skill dalla più recente, con la data di modifica e il segno sulla più recente se sono diverse."""
    riga = next((r for r in catalogo.costruisci() if r["nome"] == nome), None)
    return [{k: c[k] for k in ("fonte", "percorso", "impronta", "modificata", "sola_lettura", "piu_recente", "attivazione", "perche")}
            for c in (riga["copie"] if riga else [])]


def configura_console(d):
    """Account API della Claude Console: prova la chiave e la salva solo se funziona."""
    nome = (d.get("nome") or "console").strip()
    dove = d.get("dove") or "keyring"
    chiave = (d.get("valore_chiave") or "").strip()
    if dove not in ("keyring", "file"):
        raise Errore("La chiave va nel portachiavi (keyring) o nel file protetto (file).")
    if not chiave:
        raise Errore("Incolla la chiave API creata nella Claude Console.")
    if not chiave.startswith("sk-ant-"):
        raise Errore("Non sembra una chiave API di Anthropic: deve iniziare con sk-ant-.")
    if chiave.startswith("sk-ant-admin"):
        raise Errore("Questa è una chiave Admin: serve una chiave API normale (Console > Settings > API keys).")
    if nome in account.tutti() and not d.get("sostituisci"):
        raise Errore(f"L'account '{nome}' esiste già: spunta 'sostituisci' per ridefinirlo.")
    workspace = (d.get("workspace_id") or "").strip()
    if workspace and not workspace.startswith("wrkspc_"):
        raise Errore("Il Workspace ID inizia con wrkspc_ (Claude Console > Settings > Workspaces).")
    dati = {"tipo": "api", "chiave": dove, "nota": d.get("nota") or "Claude Console"}
    for k in ("workspace_id", "base_url"):
        if (d.get(k) or "").strip():
            dati[k] = d[k].strip()
    try:
        skill = api_anthropic.elenca({"nome": nome, **dati}, chiave=chiave)
    except SystemExit:
        raise
    except Exception as e:
        raise Errore(f"Chiave non salvata: {api_anthropic.errore_leggibile(e)}")
    chiavi.salva(nome, dove, chiave)
    account.aggiungi(nome, dati)
    return {"messaggio": f"Account '{nome}' salvato: chiave {chiavi.maschera(chiave)} valida, {len(skill)} skill custom. "
                         f"Chiave nel {'portachiavi di sistema' if dove == 'keyring' else 'file protetto'}."}


def crea_prompt(d):
    """Prompt per ricreare la skill (dalla copia indicata, o dalla migliore)."""
    v = pacchetti.trova(d["nome"], d.get("da") or None)
    r = prompt.crea(v.skill, modalita=d.get("modalita") or "completo", codice_lingua=lingua.attuale())
    return {**r, "fonte": v.fonte, "percorso": str(v.percorso)}


def salva_nota(d):
    nota = note.scrivi(d["nome"], d.get("testo", ""))
    return {"messaggio": f"Nota di '{d['nome']}' " + ("salvata." if nota else "cancellata."), "nota": nota.get("testo", "")}


# ---------------------------------------------------------------- modifica dei file di una skill

LIMITE_TESTO = 1_000_000


def _copia_modificabile(d):
    v = pacchetti.trova(d["nome"], d.get("da") or None)
    if v.sola_lettura:
        raise Errore(f"La copia in '{v.fonte}' è di sola lettura: si modifica la copia di claude-code, del progetto "
                     "o delle terze parti (per claude.ai: modifica la copia locale e poi ricaricala).")
    return v


def _percorso_file(v, rel):
    rel = (rel or "").strip().replace("\\", "/")
    if not rel or rel.startswith("/") or ".." in Path(rel).parts or any(p in sk.IGNORA for p in Path(rel).parts):
        raise Errore(f"Nome di file non ammesso: {rel!r}")
    base = Path(os.path.realpath(v.skill.cartella))
    p = Path(os.path.realpath(base / rel))
    if base not in p.parents:
        raise Errore(f"Il file {rel} è fuori dalla cartella della skill.")
    return p


def _sha(dati: bytes) -> str:
    return hashlib.sha256(dati).hexdigest()


def leggi_file(d):
    v = pacchetti.trova(d["nome"], d.get("da") or None)
    p = _percorso_file(v, d.get("file") or "SKILL.md")
    if not p.is_file():
        raise Errore(f"{d.get('file')} non esiste.")
    dati = p.read_bytes()
    if len(dati) > LIMITE_TESTO:
        raise Errore("File troppo grande per l'editor (oltre 1 MB).")
    try:
        testo = dati.decode("utf-8")
    except UnicodeDecodeError:
        raise Errore("Non è un file di testo (UTF-8): non si modifica dall'editor.")
    return {"file": d.get("file") or "SKILL.md", "testo": testo, "sha": _sha(dati), "sola_lettura": v.sola_lettura,
            "fonte": v.fonte, "percorso": str(v.percorso), "collegamento": v.collegamento,
            "file_skill": v.skill.file}


def salva_file(d):
    """Salva un file della skill. Prima fa una copia di sicurezza della skill in archivio; rifiuta se il file
    è cambiato su disco dopo l'apertura (sha diverso)."""
    v = _copia_modificabile(d)
    p = _percorso_file(v, d.get("file"))
    testo = d.get("testo", "")
    if len(testo.encode("utf-8")) > LIMITE_TESTO:
        raise Errore("Testo oltre 1 MB.")
    if p.exists():
        if d.get("nuovo"):
            raise Errore(f"{d['file']} esiste già.")
        if d.get("sha") and _sha(p.read_bytes()) != d["sha"]:
            raise Errore("Il file è stato modificato da un altro programma dopo l'apertura: riaprilo prima di salvare.")
    elif not d.get("nuovo"):
        raise Errore(f"{d['file']} non esiste più.")
    copia = pacchetti.esporta(sorgenti.Voce(v.skill, "backup", v.origine, v.percorso), forza_segreti=True)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".manage-skill.tmp")
    tmp.write_text(testo, encoding="utf-8")
    if p.exists():
        os.chmod(tmp, p.stat().st_mode & 0o777)
    tmp.replace(p)
    s = sk.carica(v.skill.cartella)
    avvisi = sk.valida(s, impostazioni()["limite_mb"])
    if s.nome != Path(v.percorso).name:
        avvisi.append(f"il name nel frontmatter ('{s.nome}') non coincide con la cartella ('{Path(v.percorso).name}')")
    return {"messaggio": f"{d['file']} salvato in {v.fonte}. Copia di sicurezza: {copia}", "sha": _sha(p.read_bytes()),
            "avvisi": avvisi, "segreti": [{"file": f, "tipo": t_, "riga": r} for f, t_, r in sk.cerca_segreti(s)],
            "impronta": s.impronta}


# ---------------------------------------------------------------- terze parti

def terze_elenco(_):
    return {"skill": terze.elenco()}


def terze_anteprima(d):
    if not (d.get("sorgente") or "").strip():
        raise Errore("Indica un repository Git, uno ZIP o una cartella.")
    return terze.anteprima(d["sorgente"].strip())


def terze_aggiungi(d):
    return {"esiti": terze.aggiungi(d["sorgente"].strip(), percorsi=d.get("percorsi") or None,
                                    destinazioni=d.get("destinazioni") or None, sostituisci=bool(d.get("sostituisci")))}


def terze_aggiorna(d):
    return {"esiti": terze.aggiorna(d.get("nomi") or None, forza=bool(d.get("forza")))}


def terze_destinazioni(d):
    terze.destinazioni(d["nome"], d.get("destinazioni") or [])
    return {"messaggio": f"Destinazioni di '{d['nome']}': {', '.join(d.get('destinazioni') or []) or 'nessuna'}."}


def terze_sincronizza(d):
    return {"esiti": terze.sincronizza(d.get("nomi") or None, verso=d.get("verso") or None, prova=bool(d.get("prova")),
                                       forza=bool(d.get("forza")), forza_segreti=bool(d.get("ignora_segreti")))}


def terze_rimuovi(d):
    terze.rimuovi(d["nome"])
    return {"messaggio": f"'{d['nome']}' rimossa dalle terze parti (copia salvata in archivio). Le copie già sincronizzate negli account restano."}


def confronta(q):
    return {"confronti": [{"a": a, "b": b, "aggiunti": agg, "tolti": tolti, "cambiati": camb}
                          for a, b, agg, tolti, camb in catalogo.differenze(q["nome"])]}


def _voci(d):
    nomi = d.get("nomi") or []
    if not nomi:
        raise Errore("Nessuna skill selezionata.")
    return [pacchetti.trova(n, d.get("da") or None) for n in nomi]


def esporta(d):
    esiti = []
    for v in _voci(d):
        try:
            esiti.append({"nome": v.skill.nome, "ok": True, "cartella": str(pacchetti.esporta(v, forza_segreti=bool(d.get("ignora_segreti"))))})
        except pacchetti.Bloccato as e:
            esiti.append({"nome": v.skill.nome, "ok": False, "errore": str(e)})
    return {"esiti": esiti}


def importa(d):
    if not d.get("verso"):
        raise Errore("Scegli l'account di destinazione.")
    esiti = []
    for v in _voci(d):
        try:
            r = pacchetti.importa(v, d["verso"], sovrascrivi=bool(d.get("sovrascrivi")), prova=bool(d.get("prova")),
                                  forza_segreti=bool(d.get("ignora_segreti")))
            esiti.append({"nome": v.skill.nome, "ok": True, **r})
        except pacchetti.Bloccato as e:
            esiti.append({"nome": v.skill.nome, "ok": False, "errore": str(e)})
    return {"esiti": esiti}


def cloud_elenco(q):
    return {"conti": cloud.conti(), "skill": cloud.elenca(sole_mie=q.get("mie") == "1")}


def cloud_api(_):
    return {"skill": cloud.elenca_api()}


def cloud_esporta(d):
    return {"risultati": cloud.esporta(nomi=d.get("nomi") or None, sole_mie=bool(d.get("mie")),
                                       forza_segreti=bool(d.get("ignora_segreti")))}


def cloud_verso_api(d):
    if not d.get("account"):
        raise Errore("Scegli l'account API di destinazione.")
    return {"esiti": cloud.verso_api(d["account"], nomi=d.get("nomi") or None, prova=bool(d.get("prova")),
                                     forza=bool(d.get("forza")), forza_segreti=bool(d.get("ignora_segreti")))}


def esportazioni(_):
    archivio = [{"nome": v.skill.nome, "data": v.extra.get("esportata", ""), "cartella": str(v.percorso.parent),
                 "zip": str(v.percorso.parent / f"{v.skill.nome}.zip")}
                for v in sorgenti.archivio()]
    return {"cloud": cloud.esportazioni(), "archivio": sorted(archivio, key=lambda x: x["data"], reverse=True)}


def elenco_account(_):
    return {"account": [{"nome": n, "tipo": a["tipo"], "cartella": a.get("cartella", ""), "workspace_id": a.get("workspace_id", ""),
                         "base_url": a.get("base_url", ""), "chiave": a.get("chiave", "") if a["tipo"] == "api" else "",
                         "nota": a.get("nota", ""), "predefinito": n in account.PREDEFINITI}
                        for n, a in account.tutti().items()]}


def salva_account(d):
    nome, tipo = (d.get("nome") or "").strip(), d.get("tipo")
    if not nome or tipo not in account.TIPI:
        raise Errore("Servono un nome e un tipo validi.")
    if nome in account.tutti() and not d.get("sostituisci"):
        raise Errore(f"L'account '{nome}' esiste già: spunta 'sostituisci' per ridefinirlo.")
    dati = {"tipo": tipo, "nota": d.get("nota", "")}
    if tipo == "api":
        dove = d.get("chiave") or "keyring"
        if not (dove in ("keyring", "file", "ant") or dove.startswith("env:")):
            raise Errore("Chiave: keyring, file, env:VARIABILE oppure ant.")
        dati["chiave"] = dove
        for k in ("workspace_id", "base_url"):
            if d.get(k):
                dati[k] = d[k].strip()
        if dove in ("keyring", "file"):
            # Stessa verifica della Claude Console: la chiave si salva solo se funziona
            return configura_console({**d, "dove": dove, "nota": d.get("nota") or "Account API"})
    elif d.get("cartella"):
        dati["cartella"] = str(Path(d["cartella"]).expanduser())
    elif tipo == "claude-code":
        raise Errore("Per un account claude-code serve la cartella delle skill.")
    account.aggiungi(nome, dati)
    return {"messaggio": f"Account '{nome}' salvato."}


def cambia_chiave(d):
    a = account.leggi(d["nome"])
    dove = d.get("dove") or a.get("chiave", "keyring")
    if a["tipo"] != "api" or dove not in ("keyring", "file"):
        raise Errore("Si può inserire la chiave solo per account api con chiave in keyring o file.")
    valore = (d.get("valore_chiave") or "").strip()
    if not valore:
        raise Errore("Inserisci la chiave API.")
    chiavi.salva(a["nome"], dove, valore)
    if dove != a.get("chiave"):
        account.aggiungi(a["nome"], {**{k: v for k, v in a.items() if k != "nome"}, "chiave": dove})
    return {"messaggio": f"Chiave di '{a['nome']}' aggiornata ({dove})."}


def prova_account(d):
    a = account.leggi(d["nome"])
    if a["tipo"] != "api":
        c = account.cartella(a) if a.get("cartella") else None
        return {"ok": True, "messaggio": f"Cartella {c}: {'esiste' if c.exists() else 'verrà creata al primo import'}" if c
                else "Nessuna cartella: gli ZIP vanno in manageskill/archivio/_da-caricare"}
    try:
        n = len(api_anthropic.elenca(a))
        chiave = chiavi.leggi(a["nome"], a.get("chiave", "keyring"))
        return {"ok": True, "messaggio": f"Chiave {chiavi.maschera(chiave) if chiave else '(profilo ant)'} valida, {n} skill custom."}
    except Exception as e:
        return {"ok": False, "messaggio": api_anthropic.errore_leggibile(e)}


def rimuovi_account(d):
    a = account.rimuovi(d["nome"])
    if a.get("tipo") == "api" and a.get("chiave") in ("keyring", "file"):
        chiavi.elimina(d["nome"], a["chiave"])
    return {"messaggio": f"Account '{d['nome']}' rimosso" + (" con la sua chiave." if a.get("tipo") == "api" else ".")}


def remoto(q):
    try:
        return {"skill": api_anthropic.elenca(account.leggi(q["account"]), tutte_le_fonti=q.get("tutte") == "1")}
    except SystemExit:
        raise
    except Exception as e:
        raise Errore(api_anthropic.errore_leggibile(e))


def remoto_elimina(d):
    if d.get("conferma") != d.get("nome"):
        raise Errore("Per eliminare scrivi esattamente il nome della skill nel campo di conferma.")
    a = account.leggi(d["account"])
    s = api_anthropic.trova(a, d["nome"])
    if not s:
        raise Errore(f"'{d['nome']}' non c'è nell'account {d['account']}.")
    api_anthropic.elimina(a, s["id"])
    return {"messaggio": f"'{d['nome']}' eliminata da {d['account']} con tutte le sue versioni."}


AZIONI = {"stato": stato, "catalogo": elenco_catalogo, "skill": scheda, "confronta": confronta,
          "cloud": cloud_elenco, "cloud_api": cloud_api, "esportazioni": esportazioni, "account": elenco_account,
          "remoto": remoto, "esporta": esporta, "importa": importa, "cloud_esporta": cloud_esporta, "cloud_verso_api": cloud_verso_api,
          "account_salva": salva_account, "account_chiave": cambia_chiave, "account_prova": prova_account,
          "account_rimuovi": rimuovi_account, "account_console": configura_console, "remoto_elimina": remoto_elimina,
          "nota": salva_nota, "prompt": crea_prompt, "file_leggi": leggi_file, "file_salva": salva_file,
          "terze_elenco": terze_elenco, "terze_anteprima": terze_anteprima, "terze_aggiungi": terze_aggiungi,
          "terze_aggiorna": terze_aggiorna, "terze_destinazioni": terze_destinazioni,
          "terze_sincronizza": terze_sincronizza, "terze_rimuovi": terze_rimuovi}
