#!/usr/bin/env bash
# Copyright (C) 2026 Quirino Scaramastra
# SPDX-License-Identifier: GPL-3.0-or-later
# Avvia c-manage-skill con il suo ambiente Python. Uso: ./ms --help
QUI=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)
if [ ! -x "$QUI/.venv/bin/python" ]; then
    echo "Ambiente non installato: esegui $QUI/installa.sh" >&2
    exit 1
fi
cd "$QUI" && exec "$QUI/.venv/bin/python" -m c_manage_skill.cli "$@"
