// c-manage-skill: catalogo, esportazione e sincronizzazione delle skill di Claude
// Copyright (C) 2026 Quirino Scaramastra
// SPDX-License-Identifier: GPL-3.0-or-later
// Collegamento con il motore Python di c-manage-skill (python -m c_manage_skill.motore).
// Ogni richiesta avvia un processo che legge il JSON dallo standard input e risponde in JSON:
// nessun server, nessuna porta aperta. Le chiavi API passano solo dallo standard input.
#pragma once

#include <QJsonObject>
#include <QJsonValue>
#include <QObject>
#include <QString>
#include <functional>

class Motore : public QObject {
    Q_OBJECT
public:
    using Risposta = std::function<void(bool ok, const QJsonObject &risultato, const QString &errore)>;

    explicit Motore(QObject *genitore = nullptr);

    // Esegue un'azione del motore (vedi c_manage_skill/servizi.py, AZIONI) e chiama `risposta` alla fine.
    void chiedi(const QString &azione, const QJsonObject &dati, Risposta risposta);

    QString cartellaProgetto() const { return m_progetto; }
    bool pronto(QString *problema) const;

signals:
    void occupato(bool si);  // true quando almeno una richiesta è in corso

private:
    QString m_progetto;
    QString m_python;
    int m_inCorso = 0;
};
