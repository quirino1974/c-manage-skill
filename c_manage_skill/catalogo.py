# c-manage-skill: catalogo, esportazione e sincronizzazione delle skill di Claude
# Copyright (C) 2026 Quirino Scaramastra
# SPDX-License-Identifier: GPL-3.0-or-later
"""Catalogo: raggruppa per nome le skill di tutte le fonti, assegna una categoria e confronta le copie."""

import html
import re
from collections import defaultdict
from datetime import datetime

from . import note, sorgenti
from .config import CATALOGO, CATEGORIE_FILE, carica_json, salva_json

# Categoria = regola con il punteggio più alto: ogni parola trovata nel nome vale 3, nella descrizione 1.
# Le parole sono intere ("post" non trova "posta"); con l'asterisco finale sono radici ("certificaz*").
# In dati/categorie.json si possono cambiare le regole e fissare a mano la categoria di una skill ("assegnate").
CATEGORIE_PREDEFINITE = {
    "regole": [
        {"categoria": "Social e post", "parole": ["linkedin", "facebook", "substack", "bluesky", "mastodon", "threads", "post", "tweet", "newsletter", "social"]},
        {"categoria": "Posta e messaggi", "parole": ["gmail", "posta", "casella", "telegram", "slack", "smista*"]},
        {"categoria": "Finanza", "parole": ["etf", "portafoglio", "borsa", "azioni", "titoli azionari"]},
        {"categoria": "Carriera e formazione", "parole": ["sviluppo professionale", "carriera", "certificaz*", "competenze", "skill gap"]},
        {"categoria": "Riunioni e lavoro", "parole": ["riunione", "riunioni", "meeting", "team"]},
        {"categoria": "Sito e SEO", "parole": ["sito", "seo", "geo"]},
        {"categoria": "Documenti", "parole": ["docx", "pdf", "pptx", "xlsx", "word", "excel", "powerpoint", "spreadsheet*", "slide*", "docs", "google-workspace", "document*"]},
        {"categoria": "Browser e computer", "parole": ["browser", "chrome", "computer-use", "computer use", "desktop"]},
        {"categoria": "Ricerca", "parole": ["research", "ricerca approfondita", "deep-research"]},
        {"categoria": "Sviluppo software", "parole": ["code", "hook*", "plugin*", "git", "sdk", "commit", "frontend", "mcp", "command*", "security", "repository"]},
        {"categoria": "Strumenti di Claude", "parole": ["skill-creator", "memory", "memoria", "morning", "claude-md", "session"]},
    ],
    "assegnate": {},
}


def categorie():
    dati = carica_json(CATEGORIE_FILE, CATEGORIE_PREDEFINITE)
    if isinstance(dati, list):  # formato vecchio: solo l'elenco delle regole
        dati = {"regole": dati, "assegnate": {}}
    return dati


def _conta(parola: str, testo: str) -> int:
    p = parola.lower()
    if p.endswith("*"):
        rx = r"(?<![a-z0-9])" + re.escape(p[:-1])
    else:
        rx = r"(?<![a-z0-9])" + re.escape(p) + r"(?![a-z0-9])"
    return len(re.findall(rx, testo))


def categoria(nome: str, descrizione: str, regole=None) -> str:
    regole = regole or categorie()
    if nome in regole.get("assegnate", {}):
        return regole["assegnate"][nome]
    n, d = nome.lower().replace("_", "-"), descrizione.lower()
    migliore, punteggio = "Altro", 0
    for r in regole["regole"]:
        punti = sum(3 * _conta(p, n) + min(_conta(p, d), 3) for p in r["parole"])
        if punti > punteggio:
            migliore, punteggio = r["categoria"], punti
    return migliore


def costruisci(fonti=None) -> list:
    voci = sorgenti.tutte(fonti)
    regole = categorie()
    tutte_note = note.tutte()
    per_nome = defaultdict(list)
    for v in voci:
        per_nome[v.skill.nome].append(v)
    righe = []
    for nome, copie in sorted(per_nome.items()):
        principale = max(copie, key=lambda v: (v.fonte in ("claude-code", "progetto"), v.skill.modificata))
        vive = [v for v in copie if v.fonte != "archivio"]
        impronte = {v.skill.impronta for v in vive}
        quando = {id(v): sorgenti.data_modifica(v) for v in copie}
        # La copia più recente conta solo se le copie sono diverse; le copie identiche alla più recente sono segnate anche loro
        recente = max(vive, key=lambda v: quando[id(v)]) if len(impronte) > 1 else None
        stati = {id(v): sorgenti.stato(v) for v in copie}
        in_uso = next((stati[id(v)] for v in copie if v.fonte == "claude-code"), None) or \
            next((stati[id(v)] for v in copie if v.fonte == "progetto"), None) or \
            next((stati[id(v)] for v in copie if v.fonte == "claude-ai"), None) or {"stato": "non caricata", "attiva": False, "perche": ""}
        righe.append({
            "nome": nome,
            "descrizione": principale.skill.descrizione,
            "nota": tutte_note.get(nome, {}).get("testo", ""),
            "categoria": categoria(nome, principale.skill.descrizione, regole),
            "origine": principale.origine,
            "fonti": sorted({v.fonte for v in copie}),
            "allineata": len(impronte) <= 1,
            "attivazione": in_uso,
            "file": len(principale.skill.file),
            "kb": principale.skill.kb,
            "modificata": _quando(max(quando.values(), default=0)),
            "piu_recente": {"fonte": recente.fonte, "percorso": str(recente.percorso), "modificata": _quando(quando[id(recente)]),
                            "impronta": recente.skill.impronta} if recente else None,
            "copie": [{"fonte": v.fonte, "percorso": str(v.percorso), "collegamento": v.collegamento, "impronta": v.skill.impronta,
                       "modificata": _quando(quando[id(v)]), "sola_lettura": v.sola_lettura,
                       "attivazione": stati[id(v)]["stato"], "perche": stati[id(v)]["perche"],
                       "piu_recente": bool(recente) and v.fonte != "archivio" and v.skill.impronta == recente.skill.impronta,
                       **(v.extra or {})} for v in sorted(copie, key=lambda v: -quando[id(v)])],
        })
    return righe


def _quando(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else ""


def salva(righe: list) -> dict:
    CATALOGO.mkdir(parents=True, exist_ok=True)
    salva_json(CATALOGO / "catalogo.json", {"creato": datetime.now().isoformat(timespec="seconds"), "skill": righe})
    (CATALOGO / "catalogo.html").write_text(html_catalogo(righe), encoding="utf-8")
    return {"json": CATALOGO / "catalogo.json", "html": CATALOGO / "catalogo.html"}


def html_catalogo(righe: list) -> str:
    e = html.escape
    per_cat = defaultdict(list)
    for r in righe:
        per_cat[r["categoria"]].append(r)
    sezioni = []
    for cat in sorted(per_cat, key=lambda c: (c == "Altro", c)):
        carte = []
        for r in per_cat[cat]:
            copie = "".join(f"<li><b>{e(c['fonte'])}</b> <code>{e(c['percorso'])}</code>"
                            f"{' → ' + e(c['collegamento']) if c['collegamento'] else ''} · {e(c['modificata'])} · {e(c['impronta'])}</li>"
                            for c in r["copie"])
            stato = "allineata" if r["allineata"] else "copie diverse"
            carte.append(f"""<article class="card {'diversa' if not r['allineata'] else ''}" data-testo="{e((r['nome'] + ' ' + r['descrizione']).lower())}">
<h3>{e(r['nome'])}</h3><p class="meta">{e(r['origine'])} · {r['file']} file · {r['kb']} KB · {e(stato)}</p>
<p>{e(r['descrizione'][:400])}{'…' if len(r['descrizione']) > 400 else ''}</p>
<details><summary>{len(r['copie'])} copie</summary><ul>{copie}</ul></details></article>""")
        sezioni.append(f"<section><h2>{e(cat)} <small>{len(per_cat[cat])}</small></h2><div class=\"grid\">{''.join(carte)}</div></section>")
    tue = sum(r["origine"] == "tua" for r in righe)
    return f"""<!DOCTYPE html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Catalogo skill</title><style>
:root{{--bg:#F5F6FA;--card:#fff;--ink:#101830;--muted:#5A6480;--line:#DDE1EC;--acc:#2a78d6;--warn:#B45309}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0B1330;--card:#121C40;--ink:#EEF1FB;--muted:#A3AED3;--line:#24315E;--acc:#7D96FF;--warn:#FBBF24}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,sans-serif}}main{{max-width:1180px;margin:0 auto;padding:24px 16px}}
h1{{margin:0 0 4px}}h2{{margin:28px 0 10px}}h2 small{{color:var(--muted);font-weight:400}}
.sub{{color:var(--muted)}}input{{font:inherit;width:100%;max-width:420px;padding:.5rem .7rem;border:1px solid var(--line);border-radius:10px;background:var(--card);color:var(--ink)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px;min-width:0}}.card.diversa{{border-color:var(--warn)}}
.card h3{{margin:0 0 2px;font-size:1.05rem;overflow-wrap:anywhere}}.meta{{color:var(--acc);font-size:.82rem;margin:0 0 6px}}
.card p{{margin:0 0 8px;font-size:.92rem}}details{{font-size:.82rem;color:var(--muted)}}code{{overflow-wrap:anywhere}}
</style></head><body><main><h1>Catalogo skill</h1>
<p class="sub">{len(righe)} skill · {tue} tue · creato il {datetime.now().strftime('%d/%m/%Y %H:%M')} con c-manage-skill. Le schede con il bordo arancione hanno copie con contenuto diverso.</p>
<input id="q" type="search" placeholder="Cerca per nome o descrizione" aria-label="Cerca">
{''.join(sezioni)}</main><script>
document.getElementById('q').addEventListener('input',function(){{var t=this.value.toLowerCase();
document.querySelectorAll('.card').forEach(function(c){{c.style.display=c.dataset.testo.indexOf(t)>-1?'':'none'}});
document.querySelectorAll('section').forEach(function(s){{s.style.display=[...s.querySelectorAll('.card')].some(c=>c.style.display!=='none')?'':'none'}})}});
</script></body></html>"""


def differenze(nome: str) -> list:
    """Confronta file per file le copie di una skill. Ritorna [(fonte_a, fonte_b, aggiunti, tolti, cambiati)]."""
    import hashlib
    voci = [v for v in sorgenti.tutte() if v.skill.nome == nome and v.fonte != "archivio"]
    def mappa(v):
        return {f: hashlib.sha256((v.skill.cartella / f).read_bytes()).hexdigest() for f in v.skill.file}
    risultati = []
    for i in range(len(voci)):
        for j in range(i + 1, len(voci)):
            a, b = mappa(voci[i]), mappa(voci[j])
            agg = sorted(set(b) - set(a)); tolti = sorted(set(a) - set(b))
            camb = sorted(f for f in set(a) & set(b) if a[f] != b[f])
            risultati.append((f"{voci[i].fonte}:{voci[i].percorso}", f"{voci[j].fonte}:{voci[j].percorso}", agg, tolti, camb))
    return risultati
