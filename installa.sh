#!/usr/bin/env bash
# Copyright (C) 2026 Quirino Scaramastra
# SPDX-License-Identifier: GPL-3.0-or-later
# Installa c-manage-skill: ambiente Python dedicato (.venv) con l'SDK ufficiale di Anthropic,
# e il comando 'ms' in ~/.local/bin.
set -euo pipefail
QUI=$(cd "$(dirname "$0")" && pwd)
cd "$QUI"
[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
chmod +x ms
mkdir -p "$HOME/.local/bin"
ln -sf "$QUI/ms" "$HOME/.local/bin/ms"
echo "Installato. SDK: $(.venv/bin/python -c 'import anthropic;print(anthropic.__version__)')"
echo "Comando disponibile: ms   (se non lo trova, aggiungi ~/.local/bin al PATH)"
