// manage-skill: catalogo, esportazione e sincronizzazione delle skill di Claude
// Copyright (C) 2026 Quirino Scaramastra
// SPDX-License-Identifier: GPL-3.0-or-later
// Aspetto dell'applicazione: tavolozza e foglio di stile chiaro o scuro (segue il tema del sistema).
#pragma once

#include <QString>

class QApplication;
class QWidget;

namespace Stile {
void applica(QApplication &app);
// Colora i pulsanti principali e quelli che cancellano, cercandoli per testo dentro `radice`.
void ruoli(QWidget *radice);
bool scuro();
// Colori di stato leggibili sul tema attivo ("#rrggbb")
QString verde();
QString arancio();
QString rosso();
}
