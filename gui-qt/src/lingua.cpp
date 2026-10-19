// manage-skill: catalogo, esportazione e sincronizzazione delle skill di Claude
// Copyright (C) 2026 Quirino Scaramastra
// SPDX-License-Identifier: GPL-3.0-or-later
#include "lingua.h"

#include <QFile>
#include <QHash>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QList>
#include <QPair>
#include <QRegularExpression>
#include <QSettings>

namespace {
QString g_codice = "it";
QHash<QString, QString> g_esatti;
QList<QPair<QRegularExpression, QString>> g_modelli;

QString unaRiga(const QString &riga) {
    if (riga.trimmed().isEmpty()) return riga;
    const auto it = g_esatti.constFind(riga);
    if (it != g_esatti.constEnd()) return it.value();
    // spazi iniziali e finali restano dove sono
    const qsizetype inizio = riga.size() - QString(riga).remove(QRegularExpression("^\\s+")).size();
    const qsizetype fine = riga.size() - QString(riga).remove(QRegularExpression("\\s+$")).size();
    const QString nucleo = riga.mid(inizio, riga.size() - inizio - fine);
    const auto it2 = g_esatti.constFind(nucleo);
    if (it2 != g_esatti.constEnd()) return riga.left(inizio) + it2.value() + riga.right(fine);
    for (const auto &[rx, sostituto] : g_modelli) {
        const auto m = rx.match(nucleo);
        if (m.hasMatch()) {
            QString r = sostituto;
            for (int g = m.lastCapturedIndex(); g >= 1; --g) r.replace("\\" + QString::number(g), unaRiga(m.captured(g)));
            return riga.left(inizio) + r + riga.right(fine);
        }
    }
    return riga;
}
}  // namespace

namespace Lingua {

void imposta(const QString &codice, const QString &cartellaProgetto) {
    g_codice = codice == "en" ? "en" : "it";
    g_esatti.clear();
    g_modelli.clear();
    if (g_codice == "it") return;
    QFile f(cartellaProgetto + "/manageskill/lingue/" + g_codice + ".json");
    if (!f.open(QIODevice::ReadOnly)) return;
    const QJsonObject d = QJsonDocument::fromJson(f.readAll()).object();
    const QJsonObject esatti = d["esatti"].toObject();
    for (auto it = esatti.begin(); it != esatti.end(); ++it) g_esatti.insert(it.key(), it.value().toString());
    for (const auto &x : d["modelli"].toArray()) {
        const QJsonArray coppia = x.toArray();
        QRegularExpression rx("^(?:" + coppia[0].toString() + ")$", QRegularExpression::DotMatchesEverythingOption);
        if (rx.isValid()) g_modelli.append({rx, coppia[1].toString()});
    }
}

QString codice() { return g_codice; }

QString salvata() { return QSettings("manage-skill", "manage-skill").value("lingua", "it").toString(); }

void salva(const QString &codice) { QSettings("manage-skill", "manage-skill").setValue("lingua", codice); }

QString traduci(const QString &testo) {
    if (g_codice == "it" || testo.isEmpty()) return testo;
    const auto it = g_esatti.constFind(testo);
    if (it != g_esatti.constEnd()) return it.value();
    if (!testo.contains('\n')) return unaRiga(testo);
    QStringList righe = testo.split('\n');
    for (auto &r : righe) r = unaRiga(r);
    return righe.join('\n');
}

}  // namespace Lingua
