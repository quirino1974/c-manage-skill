// manage-skill: catalogo, esportazione e sincronizzazione delle skill di Claude
// Copyright (C) 2026 Quirino Scaramastra
// SPDX-License-Identifier: GPL-3.0-or-later
#include "motore.h"

#include "lingua.h"

#include <QDir>
#include <QFileInfo>
#include <QJsonDocument>
#include <QProcess>

Motore::Motore(QObject *genitore) : QObject(genitore) {
    const QString daAmbiente = qEnvironmentVariable("MANAGE_SKILL_DIR");
    m_progetto = QDir(daAmbiente.isEmpty() ? QStringLiteral(PROGETTO_DIR) : daAmbiente).absolutePath();
    m_python = m_progetto + "/.venv/bin/python";
}

bool Motore::pronto(QString *problema) const {
    if (!QFileInfo::exists(m_progetto + "/manageskill/motore.py")) {
        *problema = "Non trovo manage-skill in " + m_progetto + ".\nImposta MANAGE_SKILL_DIR con la cartella del programma.";
        return false;
    }
    if (!QFileInfo(m_python).isExecutable()) {
        *problema = "Manca l'ambiente Python in " + m_python + ".\nEsegui ./installa.sh nella cartella del programma.";
        return false;
    }
    return true;
}

void Motore::chiedi(const QString &azione, const QJsonObject &dati, Risposta risposta) {
    auto *p = new QProcess(this);
    p->setWorkingDirectory(m_progetto);
    p->setProgram(m_python);
    // Con -m Python cerca il pacchetto nella cartella di lavoro, cioè la cartella del programma
    p->setArguments({"-m", "manageskill.motore"});

    if (++m_inCorso == 1) emit occupato(true);

    connect(p, &QProcess::finished, this, [this, p, risposta](int codice, QProcess::ExitStatus stato) {
        const QByteArray uscita = p->readAllStandardOutput();
        const QString erroreProcesso = QString::fromUtf8(p->readAllStandardError()).trimmed();
        p->deleteLater();
        if (--m_inCorso == 0) emit occupato(false);

        QJsonParseError e;
        const QJsonDocument doc = QJsonDocument::fromJson(uscita, &e);
        if (stato != QProcess::NormalExit || e.error != QJsonParseError::NoError || !doc.isObject()) {
            QString msg = "Il motore Python non ha risposto correttamente (codice " + QString::number(codice) + ").";
            if (!erroreProcesso.isEmpty()) msg += "\n\n" + erroreProcesso.right(1500);
            risposta(false, {}, msg);
            return;
        }
        const QJsonObject r = doc.object();
        if (r.value("ok").toBool())
            risposta(true, r.value("risultato").toObject(), {});
        else
            risposta(false, {}, r.value("errore").toString("errore sconosciuto"));
    });
    connect(p, &QProcess::errorOccurred, this, [this, p, risposta](QProcess::ProcessError err) {
        if (err != QProcess::FailedToStart) return;  // gli altri casi arrivano anche a finished
        p->deleteLater();
        if (--m_inCorso == 0) emit occupato(false);
        risposta(false, {}, "Impossibile avviare " + m_python + ": " + p->errorString());
    });

    p->start();
    QJsonObject richiesta{{"azione", azione}, {"dati", dati}, {"lingua", Lingua::codice()}};
    p->write(QJsonDocument(richiesta).toJson(QJsonDocument::Compact));
    p->closeWriteChannel();
}
