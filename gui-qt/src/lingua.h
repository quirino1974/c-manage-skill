// c-manage-skill: catalogo, esportazione e sincronizzazione delle skill di Claude
// Copyright (C) 2026 Quirino Scaramastra
// SPDX-License-Identifier: GPL-3.0-or-later
// Lingua dell'interfaccia. I testi sono scritti in italiano nel codice; per l'inglese vengono cercati nel
// dizionario c_manage_skill/lingue/en.json, lo stesso usato dal motore Python e dalla riga di comando.
#pragma once

#include <QString>

namespace Lingua {
// Imposta la lingua ("it" o "en") e carica il dizionario dalla cartella del programma.
void imposta(const QString &codice, const QString &cartellaProgetto);
QString codice();
// Lingua salvata nelle preferenze (predefinita: italiano).
QString salvata();
void salva(const QString &codice);
QString traduci(const QString &testo);
}

// Testo dell'interfaccia nella lingua scelta.
inline QString L(const char *testo) { return Lingua::traduci(QString::fromUtf8(testo)); }
inline QString L(const QString &testo) { return Lingua::traduci(testo); }
