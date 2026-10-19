#!/usr/bin/env bash
# Copyright (C) 2026 Quirino Scaramastra
# SPDX-License-Identifier: GPL-3.0-or-later
# Compila l'interfaccia Qt di manage-skill e crea il comando manage-skill-qt in ~/.local/bin.
# Serve una volta: sudo apt install qt6-base-dev cmake
set -euo pipefail
QUI="$(cd "$(dirname "$0")" && pwd)"

if ! command -v cmake >/dev/null || ! pkg-config --exists Qt6Widgets 2>/dev/null; then
    echo "Mancano Qt 6 o cmake. Installa con: sudo apt install qt6-base-dev cmake" >&2
    exit 1
fi

cmake -S "$QUI" -B "$QUI/build" -DCMAKE_BUILD_TYPE=Release
cmake --build "$QUI/build" -j"$(nproc)"

mkdir -p "$HOME/.local/bin"
ln -sf "$QUI/build/manage-skill-qt" "$HOME/.local/bin/manage-skill-qt"

# Icona e voce nel menu delle applicazioni (solo per questo utente)
ICONE="$HOME/.local/share/icons/hicolor/scalable/apps"
APPS="$HOME/.local/share/applications"
mkdir -p "$ICONE" "$APPS"
cp "$QUI/risorse/manage-skill.svg" "$ICONE/manage-skill.svg"
sed "s|@ESEGUIBILE@|$QUI/build/manage-skill-qt|" "$QUI/risorse/manage-skill.desktop.in" > "$APPS/manage-skill.desktop"
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" 2>/dev/null || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
echo "Fatto: avvia con  manage-skill-qt  (oppure $QUI/build/manage-skill-qt)"
