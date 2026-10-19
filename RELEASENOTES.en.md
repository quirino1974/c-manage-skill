# manage-skill: release notes

## 1.1.0, 18 October 2026

### Prompt to recreate a skill
- `ms prompt <skill>` and the **Prompt…** button create the text to paste into Claude to recreate the skill: instructions, folder tree and the content of every file. Complete or essential mode, copy to clipboard or save to file. Lines with possible secrets are redacted.

### Only your skills, activation state, language
- For ownership reasons the program shows and exports only the user's skills: Anthropic's skills on claude.ai and the skills of marketplace plugins are no longer read (`"solo_utente": true`). The 13 copies of Anthropic skills were removed from the existing cloud export.
- New **Active** column: active, manual only, active (compact), disabled (from `skillOverrides` in the Claude Code settings and from the frontmatter), or "on claude.ai" when the state is visible only on the website.
- **Language**: Italian and English. Menu in the window, `MANAGE_SKILL_LINGUA=en` for the command line, a single dictionary `manageskill/lingue/en.json`. English documents: `MANUAL.en.md`, `RELEASENOTES.en.md`, bilingual `COPYRIGHT`.

### License and copyright
- manage-skill is distributed under the **GNU GPL v3 or later** (GPL-3.0-or-later): `LICENSE` file, `COPYRIGHT` file with the third-party components, SPDX header in every source file.
- `ms --versione` and the window's **About** button show version, copyright and license.

### Icon and look
- New application icon (`gui-qt/risorse/manage-skill.svg`), used by the window and installed by `compila.sh` together with the applications menu entry.
- Redesigned interface:
  - header bar with logo and counters (skills, yours, to align, third-party);
  - more polished tabs, tables, fields and buttons, with main and destructive buttons highlighted;
  - light and dark theme following the system, or chosen with `MANAGE_SKILL_TEMA`;
  - status colors readable in both themes.
- The features described below (notes, editor, third parties, Claude Console, most recent copies, claude.ai to API) are part of this release.

## 1.0.0, 18 October 2026

First release. The sections below also describe the additions that came with 1.1.0.

### Catalog
- Finds skills in five sources:
  - Claude Code (`~/.claude/skills`, also when the skill is a link to a project);
  - project skills (`<project>/.claude/skills`);
  - installed plugins;
  - the synced copy of the claude.ai account;
  - the export archive.
- Groups copies by name, assigns a category and flags when copies differ (SHA-256 fingerprint of the files).
- Categories are assigned by whole words, scoring name and description. Rules and manual assignments are in `dati/categorie.json`.
- Produces `catalogo/catalogo.html` (cards with search) and `catalogo/catalogo.json`.
- Other commands: `descrivi` (full details), `confronta` (file-by-file differences), `valida` (Skills API rules) and `segreti` (check for keys, tokens and passwords).

### Cloud skills
- `ms cloud elenco` shows the claude.ai account skills with:
  - the type (yours, Anthropic, Anthropic example);
  - the claude.ai id;
  - the update date;
  - the comparison with the local copy.
- `ms cloud esporta` snapshots the skills on request into `manageskill/archivio/cloud/<account>/<date-time>/`. Each export creates:
  - the skill folders;
  - the ZIPs;
  - `indice.json` and `indice.html`;
  - the `ultima` link.
- Each export reports which skills are new or changed since the previous one.
- `ms cloud storico` lists the exports.
- `--api` adds the metadata of the skills in API accounts.

### Export and import
- `esporta` saves the folder, the ZIP and `skill.json` in `manageskill/archivio/<name>/<date-time>/`.
- `importa` brings a skill into an account:
  - **api**: creates the skill with the Skills API, or a new version if it already exists, and accepts `--prova`;
  - **claude-code**: copies into the folder. If the skill is already there and identical it does nothing; if it differs it stops, unless `--sovrascrivi` is given, which archives the current copy first;
  - **claude-ai**: prepares the ZIP to upload to claude.ai by hand.
- Accepts as input a name, a folder, a ZIP or an archive folder.
- The secret check blocks export and import, unless `--ignora-segreti` is given.

### Accounts and keys
- Three account types: `api`, `claude-code` and `claude-ai`. The `dati/account.json` registry contains no keys.
- The key can be kept in:
  - the system keyring (secret-tool);
  - a protected file in `~/.config/manage-skill/chiavi` (600/700);
  - an environment variable;
  - the `ant` CLI profile.
- The key is typed without echo and never printed.
- `remoto elenco`, `remoto versioni` and `remoto elimina` manage the skills in API accounts. Deletion asks you to type SI.

### Management interface
- `manage-skill-qt` is a native C++ window with Qt 6, with tabs for Catalog, claude.ai cloud, Accounts and keys, Exports, and an activity log at the bottom.
- There is no server and no port: each operation starts the Python engine (`manageskill/motore.py`) and exchanges JSON on standard input and output.
- The key is typed in a password field, travels only through standard input and never returns to the window.
- Built with `gui-qt/compila.sh` (needs `qt6-base-dev` and `cmake`).

### Copies and most recent versions
- When a skill's copies differ, the catalog shows the most recent one (★) and where it is. For claude.ai copies the date is the cloud update date.
- The Qt window shows under the catalog all copies of the selected skill, with date, status and folder.

### Claude Console accounts
- `ms account console` and the "Set up API account (Claude Console)" button test the key against the Skills API and save it, in the keyring or the protected file, only if it works. Admin keys are rejected.
- "Scan API account skills" lists the Console skills and says whether they also exist on this PC or on claude.ai.

### From claude.ai to the Claude API
- `ms cloud verso-api <account>` and the "Import into API account" button bring claude.ai skills into an API account: they create new ones, add a version to changed ones and skip identical ones (registry in `dati/sincronizzazioni.json`). They accept `--prova` and warn when the PC has a more recent version.

### Notes, editing and third parties
- **Skill notes** (`dati/note.json`), from the window or with `ms nota`.
- **Skill editor** in the window: edits and creates files in claude-code, project and third-party copies. Before every save it archives a copy, refuses to save if the file changed on disk, and checks the skill again after saving. Other copies open read-only.
- **Third-party skills** from Git, ZIP or folder (`ms terze`, Third parties tab):
  - preview with the number of scripts and possible secrets;
  - update from the source, protecting changes made here;
  - per-skill destinations and sync to claude-code, api and claude-ai, protecting changes made by hand in the accounts.
- Exports are in `manageskill/archivio/`, third parties in `manageskill/terze-parti/`.

### Known limitations
- **claude.ai cloud:**
  - there is no public API to download or upload claude.ai skills. The export uses the copy that Claude Code syncs, updated the last time Claude Code was opened (date shown in the catalog);
  - the on/off state of claude.ai skills is not in the synced copy: it can only be seen on the website;
  - importing to claude.ai prepares the ZIP, which must be uploaded by hand.
- **Skills API:** it does not allow downloading a skill's files. For API accounts only name, id and versions are visible.
- **Language:** command and option names stay in Italian; the generated HTML catalogs (`catalogo.html`, `indice.html`) are in Italian.
