# c-manage-skill: catalogo, esportazione e sincronizzazione delle skill di Claude
# Copyright (C) 2026 Quirino Scaramastra
# SPDX-License-Identifier: GPL-3.0-or-later
"""Lettura di una skill da cartella: frontmatter, file, impronta, validazione e controllo dei segreti."""

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

IGNORA = {".git", "__pycache__", ".DS_Store", ".venv", "node_modules"}
NOME_VALIDO = re.compile(r"^[a-z0-9-]{1,64}$")
PAROLE_RISERVATE = ("anthropic", "claude")

# Segreti che non devono mai finire in un archivio o in un account
SEGRETI = [
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"), "chiave API Anthropic"),
    (re.compile(r"sk-[A-Za-z0-9]{32,}"), "chiave API (sk-...)"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "chiave AWS"),
    (re.compile(r"ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}"), "token GitHub"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"), "token Slack"),
    (re.compile(r"-----BEGIN (RSA |EC |OPENSSH |)PRIVATE KEY-----"), "chiave privata"),
    # Valore scritto tra virgolette, per esempio password = "abc123..." (non conta password = os.getenv(...))
    (re.compile(r"(?i)\b(password|passwd|pwd|secret|api_key|apikey|access_token|token)\b['\"]?\s*[=:]\s*['\"][^'\"\s]{8,}['\"]"), "password o token in chiaro"),
]
# Nei file di configurazione conta anche il valore senza virgolette (password: abc123...)
SEGRETO_CONFIG = re.compile(r"(?i)^\s*(password|passwd|pwd|secret|api_key|apikey|access_token|token)\s*[=:]\s*[^\s'\"{}$<>]{8,}\s*$")
ESTENSIONI_CONFIG = {".env", ".ini", ".cfg", ".conf", ".yaml", ".yml", ".toml", ".properties", ".txt"}
FILE_SEGRETI = {".env", ".netrc", "id_rsa", "id_ed25519", "credentials.json", "token.json"}


@dataclass
class Skill:
    nome: str
    descrizione: str
    cartella: Path
    file: list = field(default_factory=list)  # percorsi relativi
    byte: int = 0
    impronta: str = ""
    modificata: float = 0.0
    frontmatter: dict = field(default_factory=dict)

    @property
    def kb(self) -> float:
        return round(self.byte / 1024, 1)


def leggi_frontmatter(testo: str) -> dict:
    """Legge il frontmatter YAML semplice (chiave: valore su una riga) all'inizio di SKILL.md."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", testo, re.S)
    if not m:
        return {}
    dati, chiave = {}, None
    for riga in m.group(1).splitlines():
        r = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", riga)
        if r:
            chiave, valore = r.group(1), r.group(2).strip()
            if len(valore) >= 2 and valore[0] == valore[-1] and valore[0] in "\"'":
                valore = valore[1:-1]
            dati[chiave] = valore
        elif chiave and riga.startswith((" ", "\t")) and isinstance(dati.get(chiave), str):
            dati[chiave] = (dati[chiave] + " " + riga.strip()).strip()
    return dati


def elenca_file(cartella: Path) -> list:
    risultato = []
    for p in sorted(cartella.rglob("*")):
        if any(parte in IGNORA for parte in p.relative_to(cartella).parts):
            continue
        if p.is_file():
            risultato.append(p.relative_to(cartella).as_posix())
    return risultato


def carica(cartella: Path) -> Skill:
    cartella = Path(cartella)
    md = cartella / "SKILL.md"
    if not md.exists():
        raise FileNotFoundError(f"{cartella}: manca SKILL.md")
    fm = leggi_frontmatter(md.read_text(encoding="utf-8", errors="replace"))
    file = elenca_file(cartella)
    h = hashlib.sha256()
    byte, modificata = 0, 0.0
    for rel in file:
        p = cartella / rel
        dati = p.read_bytes()
        h.update(rel.encode() + b"\0" + dati + b"\0")
        byte += len(dati)
        modificata = max(modificata, p.stat().st_mtime)
    return Skill(nome=fm.get("name") or cartella.name, descrizione=fm.get("description", ""), cartella=cartella,
                 file=file, byte=byte, impronta=h.hexdigest()[:16], modificata=modificata, frontmatter=fm)


def valida(s: Skill, limite_mb: int = 30) -> list:
    """Regole della Skills API di Anthropic. Ritorna l'elenco dei problemi (vuoto = valida)."""
    problemi = []
    if "name" not in s.frontmatter:
        problemi.append("SKILL.md senza 'name' nel frontmatter")
    elif not NOME_VALIDO.match(s.nome):
        problemi.append(f"name '{s.nome}': solo lettere minuscole, numeri e trattini, massimo 64 caratteri")
    if any(p in s.nome for p in PAROLE_RISERVATE):
        problemi.append(f"name '{s.nome}': non può contenere le parole riservate {PAROLE_RISERVATE}")
    if not s.descrizione:
        problemi.append("description mancante")
    elif len(s.descrizione) > 1024:
        problemi.append(f"description di {len(s.descrizione)} caratteri (massimo 1024)")
    if re.search(r"<[a-zA-Z/][^>]*>", s.nome + s.descrizione):
        problemi.append("name o description contengono tag XML")
    if s.byte > limite_mb * 1024 * 1024:
        problemi.append(f"dimensione {s.byte / 1048576:.1f} MB (massimo {limite_mb} MB)")
    return problemi


def cerca_segreti(s: Skill) -> list:
    """Cerca chiavi, token e password nei file della skill. Ritorna [(file, tipo, riga)]."""
    trovati = []
    for rel in s.file:
        nome = Path(rel).name
        if nome in FILE_SEGRETI or nome.startswith(".env"):
            trovati.append((rel, f"file sensibile ({nome})", 0))
            continue
        p = s.cartella / rel
        if p.stat().st_size > 2 * 1024 * 1024:
            continue
        try:
            testo = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        config = Path(rel).suffix.lower() in ESTENSIONI_CONFIG
        for n, riga in enumerate(testo.splitlines(), 1):
            regole = SEGRETI + ([(SEGRETO_CONFIG, "password o token in un file di configurazione")] if config else [])
            for rx, tipo in regole:
                if rx.search(riga):
                    # Placeholder evidenti nella documentazione non contano
                    if re.search(r"(?i)(xxx|<[^>]+>|\.\.\.|esempio|example|your[_-]|tua[_-]|\$\{?[A-Z_]+\}?)", riga):
                        continue
                    trovati.append((rel, tipo, n))
    return trovati
