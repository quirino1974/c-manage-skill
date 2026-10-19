# manage-skill

Catalogo, backup, modifica e sincronizzazione delle skill di Claude.
*Catalog, back up, edit and sync your Claude skills.*

manage-skill trova le tue skill di Claude ovunque si trovino (Claude Code, progetti, copia sincronizzata di claude.ai, archivio), le confronta, indica quale copia è la più recente e dove sta, e le sposta tra account gestendo le chiavi API in modo sicuro.

- **Catalogo**: elenco con categorie, stato (attiva, solo manuale, disattivata), copie diverse e la più recente.
- **Backup**: esporta tutte le skill, anche quelle di claude.ai, in cartelle e ZIP con data.
- **Modifica**: editor integrato con copia di sicurezza prima di ogni salvataggio.
- **Prompt**: genera il testo da incollare in Claude per ricreare una skill, con i segreti oscurati.
- **Account**: importa le skill in Claude Code, in un account Claude Console (Skills API) o prepara lo ZIP per claude.ai; le chiavi stanno nel keyring di sistema, mai nei file del progetto.
- **Terze parti**: aggiunge skill da Git, ZIP o cartella e le tiene aggiornate.
- **Interfaccia**: riga di comando `ms` e finestra nativa C++/Qt 6, in italiano e in inglese. Nessun server.

Per proprietà, il programma mostra ed esporta solo le skill dell'utente, non quelle di Anthropic né dei plugin dei marketplace.

## Installazione / Installation

Requisiti: Linux, Python 3.10+, per la finestra `cmake` e `qt6-base-dev` (Qt SVG).

```bash
git clone <indirizzo del repository> manage-skill
cd manage-skill
./installa.sh          # ambiente .venv, SDK anthropic, comando ms in ~/.local/bin
gui-qt/compila.sh      # facoltativo: finestra manage-skill-qt, icona e voce di menu
ms catalogo
```

Interfaccia in inglese / English interface: `MANAGE_SKILL_LINGUA=en ms catalogo`, oppure il menu della lingua nella finestra / or the language menu in the window.

## Documentazione / Documentation

- [MANUALE.md](MANUALE.md) · [MANUAL.en.md](MANUAL.en.md)
- [RELEASENOTES.md](RELEASENOTES.md) · [RELEASENOTES.en.md](RELEASENOTES.en.md)

## Licenza / License

Copyright (C) 2026 Quirino Scaramastra.
Software libero secondo la GNU General Public License v3 o successiva / Free software under the GNU GPL v3 or later (GPL-3.0-or-later). Vedi / see [LICENSE](LICENSE) e / and [COPYRIGHT](COPYRIGHT).

"Claude" e "Anthropic" sono marchi di Anthropic PBC. manage-skill è un progetto indipendente, non affiliato ad Anthropic. / manage-skill is an independent project, not affiliated with Anthropic.
