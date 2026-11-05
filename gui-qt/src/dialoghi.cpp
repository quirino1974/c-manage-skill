// c-manage-skill: catalogo, esportazione e sincronizzazione delle skill di Claude
// Copyright (C) 2026 Quirino Scaramastra
// SPDX-License-Identifier: GPL-3.0-or-later
#include "dialoghi.h"

#include "motore.h"
#include "lingua.h"
#include "stile.h"

#include <QCheckBox>
#include <QComboBox>
#include <QDialogButtonBox>
#include <QFileDialog>
#include <QFormLayout>
#include <QHBoxLayout>
#include <QJsonArray>
#include <QLabel>
#include <QLineEdit>
#include <QListWidget>
#include <QMessageBox>
#include <QInputDialog>
#include <QPlainTextEdit>
#include <QShortcut>
#include <QSplitter>
#include <QTableWidget>
#include <QHeaderView>
#include <QFontDatabase>
#include <QClipboard>
#include <QGuiApplication>
#include <QSaveFile>
#include <QTimer>
#include <QDir>
#include <QPushButton>
#include <QTextBrowser>
#include <QUrl>
#include <QVBoxLayout>

namespace {
QString h(const QString &s) { return s.toHtmlEscaped(); }
QString h(const QJsonValue &v) { return v.toVariant().toString().toHtmlEscaped(); }
}

// ---------------------------------------------------------------- scheda della skill

DialogoSkill::DialogoSkill(Motore *motore, const QString &nome, const QString &fonte, QWidget *genitore)
    : QDialog(genitore), m_motore(motore), m_nome(nome) {
    setWindowTitle(L("Skill ") + nome);
    resize(860, 760);
    auto *v = new QVBoxLayout(this);
    m_testo = new QTextBrowser;
    m_testo->setOpenLinks(false);  // i link "da:<fonte>" mostrano un'altra copia
    connect(m_testo, &QTextBrowser::anchorClicked, this, [this](const QUrl &u) {
        if (u.scheme() == "da") carica(u.path());
    });
    v->addWidget(m_testo);
    auto *riga = new QHBoxLayout;
    m_confronta = new QPushButton(L("Confronta le copie file per file"));
    m_confronta->setEnabled(false);
    connect(m_confronta, &QPushButton::clicked, this, &DialogoSkill::confronta);
    auto *chiudi = new QPushButton(L("Chiudi"));
    connect(chiudi, &QPushButton::clicked, this, &QDialog::accept);
    auto *bottonePrompt = new QPushButton(L("Prompt per ricreare la skill"));
    bottonePrompt->setToolTip(L("Crea il prompt da incollare in Claude per ricreare questa skill"));
    connect(bottonePrompt, &QPushButton::clicked, this, [this] {
        auto *d = new DialogoPrompt(m_motore, m_nome, QString(), this);
        d->setAttribute(Qt::WA_DeleteOnClose);
        d->show();
    });
    riga->addWidget(bottonePrompt);
    riga->addWidget(m_confronta);
    riga->addStretch();
    riga->addWidget(chiudi);
    v->addLayout(riga);
    carica(fonte);
    Stile::ruoli(this);
}

void DialogoSkill::carica(const QString &fonte) {
    m_testo->setHtml(L("<p>Caricamento…</p>"));
    QJsonObject dati{{"nome", m_nome}};
    if (!fonte.isEmpty()) dati["da"] = fonte;
    m_motore->chiedi("skill", dati, [this](bool ok, const QJsonObject &s, const QString &errore) {
        if (!ok) { m_testo->setHtml("<p style='color:" + Stile::rosso() + "'>" + h(errore) + "</p>"); return; }
        QString html = "<h2>" + h(s["nome"]) + "</h2><p style='color:gray'>" + h(s["categoria"]) + " · " + h(s["origine"]) + " · "
            + QString::number(s["file"].toArray().size()) + L(" file · ") + h(s["kb"]) + L(" KB · impronta ") + h(s["impronta"]) + "</p>"
            + "<p>" + h(s["descrizione"]) + "</p><table cellpadding='3'>"
            + L("<tr><td><b>Copia mostrata</b></td><td>") + h(s["fonte"]) + ": " + h(s["percorso"])
            + (s["collegamento"].toString().isEmpty() ? QString() : " → " + h(s["collegamento"])) + "</td></tr>";
        const QJsonObject fm = s["frontmatter"].toObject();
        for (auto it = fm.begin(); it != fm.end(); ++it)
            if (it.key() != "name" && it.key() != "description")
                html += "<tr><td><b>" + h(it.key()) + "</b></td><td>" + h(it.value()) + "</td></tr>";
        const QJsonArray problemi = s["problemi_api"].toArray();
        QStringList p;
        for (const auto &x : problemi) p << h(x);
        html += L("<tr><td><b>Skills API</b></td><td>") + (p.isEmpty() ? QString("<span style='color:" + Stile::verde() + L("'>pronta per l'importazione</span>"))
                                                                    : "<span style='color:" + Stile::arancio() + "'>" + p.join("<br>") + "</span>") + "</td></tr>";
        QStringList seg;
        for (const auto &x : s["segreti"].toArray()) {
            const QJsonObject o = x.toObject();
            seg << h(o["file"]) + ":" + h(o["riga"]) + " " + h(o["tipo"]);
        }
        html += "<tr><td><b>Segreti</b></td><td>" + (seg.isEmpty() ? QString("<span style='color:" + Stile::verde() + L("'>nessuno trovato</span>"))
                                                               : "<span style='color:" + Stile::rosso() + "'>" + seg.join("<br>") + "</span>") + "</td></tr></table>";
        const QJsonArray copie = s["copie"].toArray();
        QString impRecente;
        for (const auto &x : copie)
            if (x.toObject()["piu_recente"].toBool()) { impRecente = x.toObject()["impronta"].toString(); break; }
        html += L("<h3>Copie, dalla più recente</h3>");
        if (!impRecente.isEmpty())
            html += "<p style='color:" + Stile::arancio() + L("'>Le copie hanno contenuti diversi. ★ indica la versione più recente.</p>");
        html += L("<table cellpadding='4'><tr><th></th><th align='left'>Fonte</th><th align='left'>Modificata</th><th align='left'>Impronta</th><th align='left'>Dove sta</th></tr>");
        for (const auto &x : copie) {
            const QJsonObject c = x.toObject();
            const bool recente = c["piu_recente"].toBool();
            const QString colore = impRecente.isEmpty() ? QString() : recente ? "color:" + Stile::verde() + ";font-weight:bold" : c["fonte"] == "archivio" ? QString("color:gray") : "color:" + Stile::arancio();
            html += "<tr style='" + colore + "'><td>" + (recente ? "★" : "") + "</td><td><a href='da:" + h(c["fonte"]) + "'>" + h(c["fonte"]) + "</a></td><td>"
                + h(c["modificata"]) + "</td><td><code>" + h(c["impronta"]) + "</code></td><td>"
                + h(c["percorso"]) + (c["sola_lettura"].toBool() ? L(" <i>(sola lettura)</i>") : "") + "</td></tr>";
        }
        html += "</table><h3>File</h3><p>";
        QStringList f;
        for (const auto &x : s["file"].toArray()) f << h(x.toObject()["nome"]) + " (" + h(x.toObject()["byte"]) + " B)";
        html += f.join(" · ") + "</p><h3>SKILL.md</h3><pre style='white-space:pre-wrap'>" + h(s["skill_md"]) + "</pre>";
        m_htmlScheda = html;
        m_testo->setHtml(html);
        m_confronta->setEnabled(copie.size() > 1);
    });
}

void DialogoSkill::confronta() {
    m_confronta->setEnabled(false);
    m_motore->chiedi("confronta", {{"nome", m_nome}}, [this](bool ok, const QJsonObject &r, const QString &errore) {
        m_confronta->setEnabled(true);
        QString html = L("<h3>Confronto tra le copie</h3>");
        if (!ok) html += "<p style='color:" + Stile::rosso() + "'>" + h(errore) + "</p>";
        for (const auto &x : r["confronti"].toArray()) {
            const QJsonObject c = x.toObject();
            html += "<p><b>" + h(c["a"]) + "</b><br>vs <b>" + h(c["b"]) + "</b><br>";
            const auto agg = c["aggiunti"].toArray(), tolti = c["tolti"].toArray(), camb = c["cambiati"].toArray();
            if (agg.isEmpty() && tolti.isEmpty() && camb.isEmpty()) html += "<span style='color:" + Stile::verde() + "'>identiche</span>";
            for (const auto &f : agg) html += "<span style='color:" + Stile::verde() + "'>+ " + h(f) + L(" (solo nella seconda)</span><br>");
            for (const auto &f : tolti) html += "<span style='color:" + Stile::rosso() + "'>− " + h(f) + L(" (solo nella prima)</span><br>");
            for (const auto &f : camb) html += "<span style='color:" + Stile::arancio() + "'>~ " + h(f) + L(" (contenuto diverso)</span><br>");
            html += "</p>";
        }
        m_testo->setHtml(html + "<hr>" + m_htmlScheda);
    });
}

// ---------------------------------------------------------------- nuovo account

DialogoAccount::DialogoAccount(const QJsonObject &tipi, bool keyring, QWidget *genitore) : QDialog(genitore) {
    setWindowTitle(L("Nuovo account"));
    auto *v = new QVBoxLayout(this);
    m_form = new QFormLayout;
    m_nome = new QLineEdit;
    m_tipo = new QComboBox;
    for (auto it = tipi.begin(); it != tipi.end(); ++it) {
        m_tipo->addItem(it.key(), it.key());
        m_tipo->setItemData(m_tipo->count() - 1, it.value().toString(), Qt::ToolTipRole);
    }
    m_dove = new QComboBox;
    m_dove->addItem(L("portachiavi di sistema"), "keyring");
    m_dove->addItem(L("file protetto (600)"), "file");
    m_dove->addItem(L("profilo della CLI ant"), "ant");
    m_dove->addItem(L("variabile d'ambiente"), "env");
    if (!keyring) m_dove->setCurrentIndex(1);
    m_env = new QLineEdit;
    m_env->setPlaceholderText(L("ANTHROPIC_API_KEY"));
    m_chiave = new QLineEdit;
    m_chiave->setEchoMode(QLineEdit::Password);
    m_chiave->setInputMethodHints(Qt::ImhHiddenText | Qt::ImhNoPredictiveText | Qt::ImhSensitiveData);
    m_workspace = new QLineEdit;
    m_baseUrl = new QLineEdit;
    m_baseUrl->setPlaceholderText("https://api.anthropic.com");
    m_cartella = new QLineEdit;
    m_cartella->setPlaceholderText("~/.claude/skills");
    auto *sfoglia = new QPushButton(L("Sfoglia…"));
    connect(sfoglia, &QPushButton::clicked, this, [this] {
        const QString d = QFileDialog::getExistingDirectory(this, L("Cartella delle skill"));
        if (!d.isEmpty()) m_cartella->setText(d);
    });
    m_rigaCartella = new QWidget;
    auto *hc = new QHBoxLayout(m_rigaCartella);
    hc->setContentsMargins(0, 0, 0, 0);
    hc->addWidget(m_cartella);
    hc->addWidget(sfoglia);
    m_nota = new QLineEdit;
    m_sostituisci = new QCheckBox(L("sostituisci se esiste già"));

    m_form->addRow(L("Nome"), m_nome);
    m_form->addRow(L("Tipo"), m_tipo);
    m_form->addRow(L("Chiave in"), m_dove);
    m_form->addRow(L("Variabile"), m_env);
    m_form->addRow(L("Chiave API"), m_chiave);
    m_form->addRow(L("Workspace"), m_workspace);
    m_form->addRow(L("Endpoint"), m_baseUrl);
    m_form->addRow(L("Cartella"), m_rigaCartella);
    m_form->addRow(L("Nota"), m_nota);
    m_form->addRow("", m_sostituisci);
    v->addLayout(m_form);
    auto *nota = new QLabel(L("La chiave va nel portachiavi o in ~/.config/c-manage-skill/chiavi:\nnon compare mai nella finestra né in dati/account.json."));
    nota->setStyleSheet("color: gray");
    v->addWidget(nota);
    auto *bottoni = new QDialogButtonBox(QDialogButtonBox::Save | QDialogButtonBox::Cancel);
    bottoni->button(QDialogButtonBox::Save)->setText(L("Salva account"));
    bottoni->button(QDialogButtonBox::Cancel)->setText(L("Annulla"));
    connect(bottoni, &QDialogButtonBox::accepted, this, &QDialog::accept);
    connect(bottoni, &QDialogButtonBox::rejected, this, &QDialog::reject);
    v->addWidget(bottoni);

    connect(m_tipo, &QComboBox::currentIndexChanged, this, &DialogoAccount::aggiornaCampi);
    connect(m_dove, &QComboBox::currentIndexChanged, this, &DialogoAccount::aggiornaCampi);
    aggiornaCampi();
    Stile::ruoli(this);
}

void DialogoAccount::aggiornaCampi() {
    const bool api = m_tipo->currentData().toString() == "api";
    const QString dove = m_dove->currentData().toString();
    m_form->setRowVisible(m_dove, api);
    m_form->setRowVisible(m_env, api && dove == "env");
    m_form->setRowVisible(m_chiave, api && (dove == "keyring" || dove == "file"));
    m_form->setRowVisible(m_workspace, api);
    m_form->setRowVisible(m_baseUrl, api);
    m_form->setRowVisible(m_rigaCartella, !api);
    adjustSize();
}

QJsonObject DialogoAccount::dati() const {
    QJsonObject d{{"nome", m_nome->text().trimmed()}, {"tipo", m_tipo->currentData().toString()},
                  {"nota", m_nota->text()}, {"sostituisci", m_sostituisci->isChecked()}};
    if (d["tipo"] == "api") {
        const QString dove = m_dove->currentData().toString();
        d["chiave"] = dove == "env" ? "env:" + m_env->text().trimmed() : dove;
        if (dove == "keyring" || dove == "file") d["valore_chiave"] = m_chiave->text();
        if (!m_workspace->text().trimmed().isEmpty()) d["workspace_id"] = m_workspace->text().trimmed();
        if (!m_baseUrl->text().trimmed().isEmpty()) d["base_url"] = m_baseUrl->text().trimmed();
    } else if (!m_cartella->text().trimmed().isEmpty()) {
        d["cartella"] = m_cartella->text().trimmed();
    }
    return d;
}

void DialogoAccount::pulisciChiave() { m_chiave->clear(); }

// ---------------------------------------------------------------- account della Claude Console

DialogoConsole::DialogoConsole(Motore *motore, bool keyring, QWidget *genitore) : QDialog(genitore), m_motore(motore) {
    setWindowTitle(L("Account API della Claude Console"));
    resize(620, 0);
    auto *v = new QVBoxLayout(this);
    auto *spiega = new QLabel(
        L("<p>Serve una <b>chiave API</b> della Claude Console (platform.claude.com):<br>Settings &gt; API keys &gt; Create key, nel workspace che vuoi leggere. Non usare una chiave Admin.</p><p>La chiave viene provata subito sulla Skills API e <b>salvata solo se funziona</b>, nel portachiavi di sistema o in un file con permessi 600. Non compare mai nella finestra, nei registri o in dati/account.json.</p><p style='color:gray'>Le skill della Console (API) e quelle di claude.ai sono archivi separati: la scansione mostra le skill dell'organizzazione o del workspace della chiave.</p>"));
    spiega->setWordWrap(true);
    spiega->setTextFormat(Qt::RichText);
    v->addWidget(spiega);

    auto *form = new QFormLayout;
    m_nome = new QLineEdit("console");
    m_chiave = new QLineEdit;
    m_chiave->setEchoMode(QLineEdit::Password);
    m_chiave->setInputMethodHints(Qt::ImhHiddenText | Qt::ImhNoPredictiveText | Qt::ImhSensitiveData);
    m_chiave->setPlaceholderText(L("sk-ant-api03-…"));
    m_workspace = new QLineEdit;
    m_workspace->setPlaceholderText(L("wrkspc_… (obbligatorio se la chiave non è di un solo workspace)"));
    m_dove = new QComboBox;
    m_dove->addItem(L("portachiavi di sistema (consigliato)"), "keyring");
    m_dove->addItem(L("file protetto ~/.config/c-manage-skill/chiavi (600)"), "file");
    if (!keyring) m_dove->setCurrentIndex(1);
    m_sostituisci = new QCheckBox(L("sostituisci se l'account esiste già"));
    form->addRow(L("Nome dell'account"), m_nome);
    form->addRow(L("Chiave API"), m_chiave);
    form->addRow(L("Workspace"), m_workspace);
    form->addRow(L("Salva la chiave nel"), m_dove);
    form->addRow("", m_sostituisci);
    v->addLayout(form);

    m_esito = new QTextBrowser;
    m_esito->setMaximumHeight(80);
    m_esito->hide();
    v->addWidget(m_esito);

    auto *riga = new QHBoxLayout;
    m_salva = new QPushButton(L("Verifica e salva"));
    m_salva->setDefault(true);
    auto *annulla = new QPushButton(L("Chiudi"));
    riga->addStretch();
    riga->addWidget(annulla);
    riga->addWidget(m_salva);
    v->addLayout(riga);
    connect(annulla, &QPushButton::clicked, this, &QDialog::reject);
    connect(m_salva, &QPushButton::clicked, this, &DialogoConsole::verificaESalva);
    Stile::ruoli(this);
}

void DialogoConsole::verificaESalva() {
    QJsonObject dati{{"nome", m_nome->text().trimmed()}, {"valore_chiave", m_chiave->text().trimmed()},
                     {"dove", m_dove->currentData().toString()}, {"sostituisci", m_sostituisci->isChecked()}};
    if (!m_workspace->text().trimmed().isEmpty()) dati["workspace_id"] = m_workspace->text().trimmed();
    m_salva->setEnabled(false);
    m_esito->show();
    m_esito->setHtml(L("Verifica della chiave sulla Skills API…"));
    m_motore->chiedi("account_console", dati, [this](bool ok, const QJsonObject &r, const QString &errore) {
        m_salva->setEnabled(true);
        if (!ok) {
            m_esito->setHtml("<span style='color:" + Stile::rosso() + "'>" + errore.toHtmlEscaped() + "</span>");
            if (errore.contains("workspace", Qt::CaseInsensitive)) {
                m_workspace->setStyleSheet("border: 2px solid #B42318");
                m_workspace->setFocus();
            }
            return;  // la chiave resta nel campo: basta aggiungere il workspace e riprovare
        }
        m_chiave->clear();
        emit salvato(r["messaggio"].toString());
        accept();
    });
    dati = {};
}

// ---------------------------------------------------------------- editor della skill

EditorSkill::EditorSkill(Motore *motore, const QString &nome, const QString &fonte, QWidget *genitore)
    : QDialog(genitore), m_motore(motore), m_nome(nome), m_fonte(fonte) {
    setWindowTitle(L("Modifica ") + nome);
    resize(1050, 760);
    auto *v = new QVBoxLayout(this);
    m_info = new QLabel;
    m_info->setWordWrap(true);
    m_info->setTextFormat(Qt::RichText);
    v->addWidget(m_info);
    auto *div = new QSplitter;
    auto *sinistra = new QWidget;
    auto *sv = new QVBoxLayout(sinistra);
    sv->setContentsMargins(0, 0, 0, 0);
    m_elenco = new QListWidget;
    auto *nuovo = new QPushButton(L("Nuovo file…"));
    sv->addWidget(m_elenco);
    sv->addWidget(nuovo);
    m_testo = new QPlainTextEdit;
    m_testo->setFont(QFontDatabase::systemFont(QFontDatabase::FixedFont));
    m_testo->setLineWrapMode(QPlainTextEdit::WidgetWidth);
    div->addWidget(sinistra);
    div->addWidget(m_testo);
    div->setStretchFactor(1, 4);
    v->addWidget(div, 1);
    auto *riga = new QHBoxLayout;
    m_salva = new QPushButton(L("Salva (Ctrl+S)"));
    m_salva->setEnabled(false);
    auto *chiudi = new QPushButton(L("Chiudi"));
    riga->addStretch();
    riga->addWidget(chiudi);
    riga->addWidget(m_salva);
    v->addLayout(riga);

    connect(m_testo, &QPlainTextEdit::modificationChanged, this, [this](bool cambiato) {
        m_salva->setEnabled(cambiato && !m_solaLettura);
        setWindowTitle((cambiato ? "● " : "") + QString(L("Modifica ")) + m_nome + " · " + m_file);
    });
    connect(m_elenco, &QListWidget::itemActivated, this, [this](QListWidgetItem *i) {
        if (i->text() != m_file && chiediSeScartare()) apri(i->text());
    });
    connect(m_elenco, &QListWidget::itemClicked, this, [this](QListWidgetItem *i) {
        if (i->text() != m_file && chiediSeScartare()) apri(i->text());
    });
    connect(m_salva, &QPushButton::clicked, this, &EditorSkill::salva);
    connect(new QShortcut(QKeySequence::Save, this), &QShortcut::activated, this, &EditorSkill::salva);
    connect(nuovo, &QPushButton::clicked, this, &EditorSkill::nuovoFile);
    connect(chiudi, &QPushButton::clicked, this, &EditorSkill::reject);
    apri(L("SKILL.md"));
    Stile::ruoli(this);
}

bool EditorSkill::chiediSeScartare() {
    if (!m_testo->document()->isModified()) return true;
    return QMessageBox::question(this, L("Modifiche non salvate"), L("Ci sono modifiche non salvate in ") + m_file + L(". Scartarle?"))
           == QMessageBox::Yes;
}

void EditorSkill::reject() {
    if (chiediSeScartare()) QDialog::reject();
}

void EditorSkill::apri(const QString &file) {
    QJsonObject dati{{"nome", m_nome}, {"file", file}};
    if (!m_fonte.isEmpty()) dati["da"] = m_fonte;
    m_motore->chiedi("file_leggi", dati, [this, file](bool ok, const QJsonObject &r, const QString &errore) {
        if (!ok) { QMessageBox::warning(this, L("Modifica"), errore); return; }
        m_file = file;
        m_sha = r["sha"].toString();
        m_nuovo = false;
        m_solaLettura = r["sola_lettura"].toBool();
        m_fonte = r["fonte"].toString();
        m_testo->setPlainText(r["testo"].toString());
        m_testo->setReadOnly(m_solaLettura);
        m_testo->document()->setModified(false);
        m_elenco->clear();
        for (const auto &f : r["file_skill"].toArray()) m_elenco->addItem(f.toString());
        const auto trovati = m_elenco->findItems(file, Qt::MatchExactly);
        if (!trovati.isEmpty()) m_elenco->setCurrentItem(trovati.first());
        QString info = "<b>" + m_nome.toHtmlEscaped() + L("</b> · copia in <b>") + m_fonte.toHtmlEscaped() + "</b>: "
                       + r["percorso"].toString().toHtmlEscaped();
        if (!r["collegamento"].toString().isEmpty()) info += " → " + r["collegamento"].toString().toHtmlEscaped();
        info += m_solaLettura ? "<br><span style='color:" + Stile::arancio() + L("'>Sola lettura: per modificarla apri la copia di claude-code, del progetto o delle terze parti.</span>")
                              : QString(L("<br><span style='color:gray'>Prima di ogni salvataggio la skill viene copiata in archivio.</span>"));
        m_info->setText(info);
        setWindowTitle(L("Modifica ") + m_nome + " · " + m_file);
    });
}

void EditorSkill::nuovoFile() {
    if (m_solaLettura) return;
    if (!chiediSeScartare()) return;
    bool ok = false;
    const QString nome = QInputDialog::getText(this, L("Nuovo file"), L("Percorso del file nella skill (es. references/note.md):"),
                                               QLineEdit::Normal, {}, &ok).trimmed();
    if (!ok || nome.isEmpty()) return;
    m_file = nome;
    m_sha.clear();
    m_nuovo = true;
    m_testo->clear();
    m_testo->document()->setModified(true);
    m_elenco->clearSelection();
    setWindowTitle(L("● Modifica ") + m_nome + " · " + m_file + L(" (nuovo)"));
}

void EditorSkill::salva() {
    if (m_solaLettura || !m_testo->document()->isModified()) return;
    QJsonObject dati{{"nome", m_nome}, {"da", m_fonte}, {"file", m_file}, {"testo", m_testo->toPlainText()}, {"sha", m_sha}};
    if (m_nuovo) dati["nuovo"] = true;
    m_salva->setEnabled(false);
    m_motore->chiedi("file_salva", dati, [this](bool ok, const QJsonObject &r, const QString &errore) {
        if (!ok) {
            m_salva->setEnabled(true);
            QMessageBox::warning(this, L("Salvataggio non riuscito"), errore);
            return;
        }
        m_sha = r["sha"].toString();
        const bool eraNuovo = m_nuovo;
        m_nuovo = false;
        m_testo->document()->setModified(false);
        QStringList avvisi;
        for (const auto &a : r["avvisi"].toArray()) avvisi << "• " + a.toString();
        for (const auto &s : r["segreti"].toArray())
            avvisi << L("• possibile segreto in ") + s.toObject()["file"].toString() + ":" + s.toObject()["riga"].toVariant().toString();
        if (!avvisi.isEmpty()) QMessageBox::warning(this, L("Salvato, con avvisi"), r["messaggio"].toString() + "\n\n" + avvisi.join("\n"));
        emit salvata();
        if (eraNuovo) apri(m_file);
    });
}

// ---------------------------------------------------------------- terze parti

bool scegliAccount(QWidget *genitore, const QString &titolo, const QJsonArray &account, QStringList &scelti) {
    QDialog d(genitore);
    d.setWindowTitle(titolo);
    auto *v = new QVBoxLayout(&d);
    v->addWidget(new QLabel(L("Account in cui sincronizzare:")));
    auto *elenco = new QListWidget;
    for (const auto &x : account) {
        const QJsonObject a = x.toObject();
        auto *i = new QListWidgetItem(a["nome"].toString() + "  (" + a["tipo"].toString() + ")");
        i->setData(Qt::UserRole, a["nome"].toString());
        i->setFlags(i->flags() | Qt::ItemIsUserCheckable);
        i->setCheckState(scelti.contains(a["nome"].toString()) ? Qt::Checked : Qt::Unchecked);
        elenco->addItem(i);
    }
    v->addWidget(elenco);
    auto *b = new QDialogButtonBox(QDialogButtonBox::Ok | QDialogButtonBox::Cancel);
    QObject::connect(b, &QDialogButtonBox::accepted, &d, &QDialog::accept);
    QObject::connect(b, &QDialogButtonBox::rejected, &d, &QDialog::reject);
    v->addWidget(b);
    if (d.exec() != QDialog::Accepted) return false;
    scelti.clear();
    for (int r = 0; r < elenco->count(); ++r)
        if (elenco->item(r)->checkState() == Qt::Checked) scelti << elenco->item(r)->data(Qt::UserRole).toString();
    return true;
}

DialogoTerze::DialogoTerze(Motore *motore, const QJsonArray &account, QWidget *genitore) : QDialog(genitore), m_motore(motore) {
    setWindowTitle(L("Aggiungi skill di terze parti"));
    resize(900, 640);
    auto *v = new QVBoxLayout(this);
    auto *spiega = new QLabel(L("Sorgente: repository Git (https://github.com/… o git@…), ZIP (file o https://….zip) o cartella. Le skill di terze parti possono contenere script: c-manage-skill non li esegue, ma controllali prima di usarle."));
    spiega->setWordWrap(true);
    v->addWidget(spiega);
    auto *riga = new QHBoxLayout;
    m_sorgente = new QLineEdit;
    m_sorgente->setPlaceholderText("https://github.com/anthropics/skills");
    auto *cartella = new QPushButton(L("Cartella…"));
    auto *zip = new QPushButton(L("ZIP…"));
    auto *bottoneCerca = new QPushButton(L("Cerca skill"));
    bottoneCerca->setDefault(true);
    riga->addWidget(m_sorgente, 1);
    riga->addWidget(cartella);
    riga->addWidget(zip);
    riga->addWidget(bottoneCerca);
    v->addLayout(riga);
    m_stato = new QLabel;
    v->addWidget(m_stato);
    m_trovate = new QTableWidget(0, 6);
    m_trovate->setHorizontalHeaderLabels({L("Percorso"), L("Nome"), L("File"), L("Script"), L("Segreti"), L("Note")});
    m_trovate->setEditTriggers(QAbstractItemView::NoEditTriggers);
    m_trovate->verticalHeader()->hide();
    m_trovate->horizontalHeader()->setStretchLastSection(true);
    v->addWidget(m_trovate, 3);
    v->addWidget(new QLabel(L("Sincronizza poi in questi account (si può cambiare dopo):")));
    m_account = new QListWidget;
    m_account->setMaximumHeight(110);
    for (const auto &x : account) {
        const QJsonObject a = x.toObject();
        auto *i = new QListWidgetItem(a["nome"].toString() + "  (" + a["tipo"].toString() + ")");
        i->setData(Qt::UserRole, a["nome"].toString());
        i->setFlags(i->flags() | Qt::ItemIsUserCheckable);
        i->setCheckState(Qt::Unchecked);
        m_account->addItem(i);
    }
    v->addWidget(m_account, 1);
    auto *bottoni = new QHBoxLayout;
    m_installa = new QPushButton(L("Aggiungi le selezionate"));
    m_installa->setEnabled(false);
    auto *chiudi = new QPushButton(L("Chiudi"));
    bottoni->addStretch();
    bottoni->addWidget(chiudi);
    bottoni->addWidget(m_installa);
    v->addLayout(bottoni);

    connect(cartella, &QPushButton::clicked, this, [this] {
        const QString d = QFileDialog::getExistingDirectory(this, L("Cartella con le skill"));
        if (!d.isEmpty()) { m_sorgente->setText(d); cerca(); }
    });
    connect(zip, &QPushButton::clicked, this, [this] {
        const QString f = QFileDialog::getOpenFileName(this, L("ZIP con le skill"), {}, L("ZIP (*.zip)"));
        if (!f.isEmpty()) { m_sorgente->setText(f); cerca(); }
    });
    connect(bottoneCerca, &QPushButton::clicked, this, &DialogoTerze::cerca);
    connect(m_sorgente, &QLineEdit::returnPressed, this, &DialogoTerze::cerca);
    connect(m_installa, &QPushButton::clicked, this, &DialogoTerze::installa);
    connect(chiudi, &QPushButton::clicked, this, &QDialog::reject);
    Stile::ruoli(this);
}

void DialogoTerze::cerca() {
    const QString s = m_sorgente->text().trimmed();
    if (s.isEmpty()) return;
    m_stato->setText(L("Recupero della sorgente…"));
    m_installa->setEnabled(false);
    m_trovate->setRowCount(0);
    m_motore->chiedi("terze_anteprima", {{"sorgente", s}}, [this, s](bool ok, const QJsonObject &r, const QString &errore) {
        if (!ok) { m_stato->setText("<span style='color:" + Stile::rosso() + "'>" + errore.toHtmlEscaped() + "</span>"); return; }
        m_sorgenteCercata = s;
        const QJsonArray skill = r["skill"].toArray();
        m_stato->setText(L("%1%2: %3 skill trovate. Spunta quelle da aggiungere.")
                             .arg(r["tipo"].toString(), r["commit"].toString().isEmpty() ? "" : " " + r["commit"].toString())
                             .arg(skill.size()));
        for (const auto &x : skill) {
            const QJsonObject k = x.toObject();
            const int n = m_trovate->rowCount();
            m_trovate->insertRow(n);
            auto *p = new QTableWidgetItem(k["percorso"].toString());
            p->setFlags(p->flags() | Qt::ItemIsUserCheckable);
            p->setCheckState(skill.size() == 1 ? Qt::Checked : Qt::Unchecked);
            p->setToolTip(k["descrizione"].toString());
            m_trovate->setItem(n, 0, p);
            m_trovate->setItem(n, 1, new QTableWidgetItem(k["nome"].toString()));
            m_trovate->setItem(n, 2, new QTableWidgetItem(QString::number(k["file"].toInt())));
            auto *script = new QTableWidgetItem(QString::number(k["script"].toArray().size()));
            if (!k["script"].toArray().isEmpty()) {
                QStringList l;
                for (const auto &f : k["script"].toArray()) l << f.toString();
                script->setToolTip(l.join("\n"));
                script->setForeground(QColor(Stile::arancio()));
            }
            m_trovate->setItem(n, 3, script);
            auto *seg = new QTableWidgetItem(QString::number(k["segreti"].toInt()));
            if (k["segreti"].toInt()) seg->setForeground(QColor(Stile::rosso()));
            m_trovate->setItem(n, 4, seg);
            QStringList note;
            if (k["gia_installata"].toBool()) note << L("già installata");
            for (const auto &pr : k["problemi_api"].toArray()) note << pr.toString();
            m_trovate->setItem(n, 5, new QTableWidgetItem(note.join("; ")));
        }
        m_trovate->resizeColumnsToContents();
        m_installa->setEnabled(!skill.isEmpty());
    });
}

void DialogoTerze::installa() {
    QJsonArray percorsi, dest;
    for (int r = 0; r < m_trovate->rowCount(); ++r)
        if (m_trovate->item(r, 0)->checkState() == Qt::Checked) percorsi.append(m_trovate->item(r, 0)->text());
    if (percorsi.isEmpty()) { QMessageBox::warning(this, L("Terze parti"), L("Spunta almeno una skill.")); return; }
    for (int r = 0; r < m_account->count(); ++r)
        if (m_account->item(r)->checkState() == Qt::Checked) dest.append(m_account->item(r)->data(Qt::UserRole).toString());
    m_installa->setEnabled(false);
    m_stato->setText(L("Installazione…"));
    m_motore->chiedi("terze_aggiungi", {{"sorgente", m_sorgenteCercata}, {"percorsi", percorsi}, {"destinazioni", dest}},
                     [this](bool ok, const QJsonObject &r, const QString &errore) {
                         m_installa->setEnabled(true);
                         if (!ok) { m_stato->setText("<span style='color:" + Stile::rosso() + "'>" + errore.toHtmlEscaped() + "</span>"); return; }
                         emit aggiunte(r["esiti"].toArray());
                         accept();
                     });
}

// ---------------------------------------------------------------- prompt per ricreare la skill

DialogoPrompt::DialogoPrompt(Motore *motore, const QString &nome, const QString &fonte, QWidget *genitore)
    : QDialog(genitore), m_motore(motore), m_nome(nome), m_fonte(fonte) {
    setWindowTitle(L("Prompt per ricreare la skill") + " · " + nome);
    resize(980, 760);
    auto *v = new QVBoxLayout(this);
    auto *spiega = new QLabel(L("Incollalo in una nuova chat di Claude (claude.ai o Claude Code). Puoi modificarlo qui prima di copiarlo."));
    spiega->setWordWrap(true);
    v->addWidget(spiega);
    auto *riga = new QHBoxLayout;
    riga->addWidget(new QLabel(L("Modalità")));
    m_modalita = new QComboBox;
    m_modalita->addItem(L("completo: tutti i file, parola per parola"), "completo");
    m_modalita->addItem(L("essenziale: SKILL.md e l'elenco degli altri file"), "essenziale");
    riga->addWidget(m_modalita);
    riga->addStretch();
    v->addLayout(riga);
    m_testo = new QPlainTextEdit;
    m_testo->setFont(QFontDatabase::systemFont(QFontDatabase::FixedFont));
    m_testo->setLineWrapMode(QPlainTextEdit::WidgetWidth);
    v->addWidget(m_testo, 1);
    m_info = new QLabel;
    m_info->setWordWrap(true);
    m_info->setTextFormat(Qt::RichText);
    v->addWidget(m_info);
    auto *bottoni = new QHBoxLayout;
    auto *copia = new QPushButton(L("Copia negli appunti"));
    copia->setDefault(true);
    auto *salva = new QPushButton(L("Salva come file…"));
    auto *chiudi = new QPushButton(L("Chiudi"));
    bottoni->addStretch();
    bottoni->addWidget(chiudi);
    bottoni->addWidget(salva);
    bottoni->addWidget(copia);
    v->addLayout(bottoni);

    connect(m_modalita, &QComboBox::currentIndexChanged, this, &DialogoPrompt::genera);
    connect(copia, &QPushButton::clicked, this, [this, copia] {
        QGuiApplication::clipboard()->setText(m_testo->toPlainText());
        copia->setText(L("Copiato negli appunti."));
        QTimer::singleShot(2500, copia, [copia] { copia->setText(L("Copia negli appunti")); });
    });
    connect(salva, &QPushButton::clicked, this, [this] {
        const QString f = QFileDialog::getSaveFileName(this, L("Salva come file…"), QDir::homePath() + "/prompt-" + m_nome + ".md",
                                                       L("Prompt (*.md *.txt)"));
        if (f.isEmpty()) return;
        QSaveFile out(f);
        if (out.open(QIODevice::WriteOnly) && out.write(m_testo->toPlainText().toUtf8()) >= 0 && out.commit())
            m_info->setText(L("Salvato in ") + f.toHtmlEscaped());
        else
            QMessageBox::warning(this, L("Salvataggio non riuscito"), out.errorString());
    });
    connect(chiudi, &QPushButton::clicked, this, &QDialog::accept);
    Stile::ruoli(this);
    genera();
}

void DialogoPrompt::genera() {
    m_testo->setPlainText(L("Generazione del prompt…"));
    QJsonObject dati{{"nome", m_nome}, {"modalita", m_modalita->currentData().toString()}};
    if (!m_fonte.isEmpty()) dati["da"] = m_fonte;
    m_motore->chiedi("prompt", dati, [this](bool ok, const QJsonObject &r, const QString &errore) {
        if (!ok) {
            m_testo->clear();
            m_info->setText("<span style='color:" + Stile::rosso() + "'>" + errore.toHtmlEscaped() + "</span>");
            return;
        }
        m_testo->setPlainText(r["testo"].toString());
        QString info = L("%1 caratteri · %2 file inclusi · %3 solo elencati")
                           .arg(r["caratteri"].toInt()).arg(r["file_inclusi"].toArray().size()).arg(r["file_elencati"].toInt())
                       + " · " + r["fonte"].toString().toHtmlEscaped();
        if (r["oscurate"].toInt())
            info += "<br><span style='color:" + Stile::arancio() + "'>" +
                    L("%1 righe oscurate perché sembravano contenere chiavi, token o password.").arg(r["oscurate"].toInt()) + "</span>";
        m_info->setText(info);
    });
}
