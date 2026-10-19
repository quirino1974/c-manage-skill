// manage-skill: catalogo, esportazione e sincronizzazione delle skill di Claude
// Copyright (C) 2026 Quirino Scaramastra
// SPDX-License-Identifier: GPL-3.0-or-later
#include "finestra.h"

#include "dialoghi.h"
#include "motore.h"
#include "lingua.h"
#include "stile.h"

#include <QApplication>
#include <QCheckBox>
#include <QComboBox>
#include <QDateTime>
#include <QDesktopServices>
#include <QDialogButtonBox>
#include <QFile>
#include <QIcon>
#include <QTextBrowser>
#include <QGroupBox>
#include <QHBoxLayout>
#include <QHeaderView>
#include <QInputDialog>
#include <QLabel>
#include <QLineEdit>
#include <QMessageBox>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QSet>
#include <QSplitter>
#include <QStatusBar>
#include <QTabWidget>
#include <QTableWidget>
#include <QUrl>
#include <QVBoxLayout>

namespace {

// Colori di stato: dipendono dal tema, quindi si leggono quando servono
#define OK QColor(Stile::verde())
#define AVVISO QColor(Stile::arancio())
#define ERRORE QColor(Stile::rosso())

QTableWidget *tabella(const QStringList &intestazioni) {
    auto *t = new QTableWidget(0, intestazioni.size());
    t->setHorizontalHeaderLabels(intestazioni);
    t->setEditTriggers(QAbstractItemView::NoEditTriggers);
    t->setSelectionBehavior(QAbstractItemView::SelectRows);
    t->setAlternatingRowColors(true);
    t->verticalHeader()->hide();
    t->horizontalHeader()->setStretchLastSection(true);
    t->setWordWrap(false);
    return t;
}

QTableWidgetItem *cella(const QJsonValue &v) {
    auto *i = new QTableWidgetItem;
    if (v.isDouble()) i->setData(Qt::DisplayRole, v.toDouble());  // ordina come numero
    else i->setText(L(v.toVariant().toString()));  // valori come "uguale", "tua", le categorie
    return i;
}

// Prima colonna con la casella di selezione e il nome della skill
QTableWidgetItem *cellaNome(const QString &nome, const QString &suggerimento, bool selezionata = false) {
    auto *i = new QTableWidgetItem(nome);
    i->setFlags(i->flags() | Qt::ItemIsUserCheckable);
    i->setCheckState(selezionata ? Qt::Checked : Qt::Unchecked);
    i->setToolTip(suggerimento);
    QFont f = i->font();
    f.setBold(true);
    i->setFont(f);
    return i;
}

void riempi(QTableWidget *t, const QJsonArray &righe, const QStringList &chiavi) {
    t->setSortingEnabled(false);
    t->setRowCount(0);
    for (const auto &x : righe) {
        const QJsonObject r = x.toObject();
        const int n = t->rowCount();
        t->insertRow(n);
        for (int c = 0; c < chiavi.size(); ++c) {
            auto *i = cella(r[chiavi[c]]);
            if (chiavi[c] == "errore" && !i->text().isEmpty()) i->setForeground(ERRORE);
            t->setItem(n, c, i);
        }
    }
    t->setSortingEnabled(true);
    t->resizeColumnsToContents();
}

QString unisci(const QJsonArray &a, const QString &sep = ", ") {
    QStringList l;
    for (const auto &x : a) l << x.toVariant().toString();
    return l.join(sep);
}

}  // namespace

Finestra::Finestra(Motore *motore, QWidget *genitore) : QMainWindow(genitore), m_motore(motore) {
    setWindowTitle("manage-skill");
    resize(1240, 820);

    auto *schede = new QTabWidget;
    schede->setDocumentMode(false);
    auto icona = [](const char *nome) { return QIcon::fromTheme(nome); };
    schede->addTab(creaCatalogo(), icona("view-list-details"), L("Catalogo"));
    schede->addTab(creaCloud(), icona("folder-cloud"), L("Cloud claude.ai"));
    schede->addTab(creaTerze(), icona("package-x-generic"), L("Terze parti"));
    schede->addTab(creaAccount(), icona("dialog-password"), L("Account e chiavi"));
    schede->addTab(creaEsportazioni(), icona("document-save-as"), L("Esportazioni"));
    connect(schede, &QTabWidget::currentChanged, this, [this](int i) {
        if (i == 1 && m_tabCloud->rowCount() == 0) caricaCloud();
        if (i == 2) caricaTerze();
        if (i == 3) caricaAccount();
        if (i == 4) caricaEsportazioni();
    });

    m_registro = new QPlainTextEdit;
    m_registro->setObjectName("registro");
    m_registro->setReadOnly(true);
    m_registro->setPlaceholderText(L("Registro delle operazioni"));
    m_registro->setMaximumBlockCount(2000);

    auto *divisore = new QSplitter(Qt::Vertical);
    divisore->addWidget(schede);
    divisore->addWidget(m_registro);
    divisore->setStretchFactor(0, 5);
    divisore->setStretchFactor(1, 1);
    auto *centro = new QWidget;
    auto *cv = new QVBoxLayout(centro);
    cv->setContentsMargins(0, 0, 0, 0);
    cv->setSpacing(0);
    cv->addWidget(creaIntestazione());
    auto *corpo = new QWidget;
    auto *bv = new QVBoxLayout(corpo);
    bv->setContentsMargins(12, 12, 12, 8);
    bv->addWidget(divisore);
    cv->addWidget(corpo, 1);
    setCentralWidget(centro);
    for (auto *c : findChildren<QComboBox *>()) c->setSizeAdjustPolicy(QComboBox::AdjustToContents);
    Stile::ruoli(this);

    connect(m_motore, &Motore::occupato, this, [this](bool si) {
        if (si) {
            QApplication::setOverrideCursor(Qt::BusyCursor);
            statusBar()->showMessage(L("Lavoro in corso…"));
        } else {
            QApplication::restoreOverrideCursor();
            statusBar()->showMessage(L("Pronto"), 3000);
        }
    });
    avvio();
}

// ---------------------------------------------------------------- intestazione e informazioni

QWidget *Finestra::creaIntestazione() {
    auto *w = new QWidget;
    w->setObjectName("intestazione");
    w->setAttribute(Qt::WA_StyledBackground, true);
    auto *h = new QHBoxLayout(w);
    h->setContentsMargins(18, 12, 18, 12);
    h->setSpacing(14);
    auto *logo = new QLabel;
    logo->setPixmap(QIcon(":/manage-skill.svg").pixmap(52, 52));
    h->addWidget(logo);
    auto *testi = new QVBoxLayout;
    testi->setSpacing(0);
    auto *titolo = new QLabel("manage-skill");
    titolo->setObjectName("titolo");
    auto *sotto = new QLabel(L("Catalogo, cloud, terze parti e account delle tue skill di Claude"));
    sotto->setObjectName("sottotitolo");
    testi->addWidget(titolo);
    testi->addWidget(sotto);
    h->addLayout(testi);
    h->addStretch();
    auto contatore = [h](const QString &suggerimento) {
        auto *l = new QLabel("–");
        l->setObjectName("contatore");
        l->setToolTip(suggerimento);
        h->addWidget(l);
        return l;
    };
    m_cTot = contatore(L("Skill trovate in tutte le fonti"));
    m_cTue = contatore(L("Skill create da te"));
    m_cDiverse = contatore(L("Skill con copie dal contenuto diverso"));
    m_cTerze = contatore(L("Skill di terze parti installate"));
    m_versione = new QLabel;
    m_versione->setObjectName("sottotitolo");
    h->addSpacing(8);
    h->addWidget(m_versione);
    auto *lingua = new QComboBox;
    lingua->addItem("🇮🇹  Italiano", "it");
    lingua->addItem("🇬🇧  English", "en");
    lingua->setCurrentIndex(Lingua::codice() == "en" ? 1 : 0);
    lingua->setToolTip(L("Lingua dell'interfaccia"));
    lingua->setMinimumWidth(130);
    connect(lingua, &QComboBox::currentIndexChanged, this, [this, lingua] {
        const QString c = lingua->currentData().toString();
        if (c == Lingua::codice()) return;
        Lingua::salva(c);
        emit linguaCambiata(c);
    });
    h->addWidget(lingua);
    auto *info = new QPushButton(L("Informazioni"));
    info->setIcon(QIcon::fromTheme("help-about"));
    connect(info, &QPushButton::clicked, this, &Finestra::informazioni);
    h->addWidget(info);
    return w;
}

void Finestra::aggiornaContatori() {
    int tue = 0, diverse = 0, terze = 0;
    for (const auto &x : m_catalogo) {
        const QJsonObject s = x.toObject();
        tue += s["origine"] == "tua";
        diverse += !s["allineata"].toBool();
        terze += s["origine"] == "terze parti";
    }
    m_cTot->setText(L("%1 skill").arg(m_catalogo.size()));
    m_cTue->setText(L("%1 tue").arg(tue));
    m_cDiverse->setText(L("%1 da allineare").arg(diverse));
    m_cDiverse->setProperty("avviso", diverse > 0);
    m_cDiverse->style()->unpolish(m_cDiverse);
    m_cDiverse->style()->polish(m_cDiverse);
    m_cTerze->setText(L("%1 terze parti").arg(terze));
}

void Finestra::informazioni() {
    QDialog d(this);
    d.setWindowTitle(L("Informazioni su manage-skill"));
    d.resize(560, 520);
    auto *v = new QVBoxLayout(&d);
    auto *riga = new QHBoxLayout;
    auto *logo = new QLabel;
    logo->setPixmap(QIcon(":/manage-skill.svg").pixmap(96, 96));
    riga->addWidget(logo, 0, Qt::AlignTop);
    auto *testa = new QLabel(QString(L("<h2 style='margin:0'>manage-skill</h2><p style='margin:2px 0'>Versione %1 · interfaccia Qt %2</p><p style='margin:6px 0'>Catalogo, esportazione e sincronizzazione delle skill di Claude.</p><p style='margin:6px 0'><b>%3</b></p>"))
                                 .arg(m_stato["versione"].toString(), QStringLiteral(VERSIONE_GUI),
                                      m_stato["copyright"].toString(L("Copyright (C) 2026 Quirino Scaramastra")).toHtmlEscaped()));
    testa->setWordWrap(true);
    riga->addWidget(testa, 1);
    v->addLayout(riga);
    auto *testo = new QTextBrowser;
    testo->setOpenExternalLinks(true);
    testo->setHtml(
        L("<p>Questo programma è <b>software libero</b>: puoi ridistribuirlo e/o modificarlo secondo i termini della <b>GNU General Public License</b> pubblicata dalla Free Software Foundation, nella versione 3 della licenza o (a tua scelta) in una qualsiasi versione successiva.</p><p>Questo programma è distribuito nella speranza che sia utile, ma <b>SENZA ALCUNA GARANZIA</b>, nemmeno la garanzia implicita di COMMERCIABILITÀ o di IDONEITÀ A UNO SCOPO PARTICOLARE. Per i dettagli vedi la <a href='https://www.gnu.org/licenses/gpl-3.0.html'>GNU General Public License</a>.</p><p><b>Componenti di terze parti</b><br>Anthropic Python SDK (MIT) · Qt 6 (LGPL v3) · Python (PSF).</p><p>Le skill gestite restano sotto la licenza dei rispettivi autori. \"Claude\" e \"Anthropic\" sono marchi di Anthropic PBC: manage-skill è un progetto indipendente, non affiliato ad Anthropic.</p><p style='color:gray'>SPDX: GPL-3.0-or-later · file LICENSE e COPYRIGHT nella cartella del programma.</p>"));
    v->addWidget(testo, 1);
    auto *bottoni = new QDialogButtonBox(QDialogButtonBox::Close);
    auto *licenza = bottoni->addButton(L("Licenza completa"), QDialogButtonBox::ActionRole);
    auto *qt = bottoni->addButton(L("Informazioni su Qt"), QDialogButtonBox::ActionRole);
    connect(licenza, &QPushButton::clicked, this, [this] {
        const QString f = m_motore->cartellaProgetto() + "/LICENSE";
        if (QFile::exists(f)) QDesktopServices::openUrl(QUrl::fromLocalFile(f));
        else QDesktopServices::openUrl(QUrl("https://www.gnu.org/licenses/gpl-3.0.html"));
    });
    connect(qt, &QPushButton::clicked, this, [] { QApplication::aboutQt(); });
    connect(bottoni, &QDialogButtonBox::rejected, &d, &QDialog::reject);
    v->addWidget(bottoni);
    d.exec();
}

// ---------------------------------------------------------------- utilità

void Finestra::registra(const QString &testoOriginale, bool errore) {
    const QString testo = L(testoOriginale);
    const QString ora = QDateTime::currentDateTime().toString("HH:mm:ss");
    m_registro->appendHtml("<span style='color:gray'>" + ora + "</span> " +
                           (errore ? "<span style='color:" + Stile::rosso() + "'>" : QString("<span>")) + testo.toHtmlEscaped().replace("\n", "<br>") + "</span>");
}

void Finestra::errore(const QString &testo) {
    registra(testo, true);
    QMessageBox::warning(this, "manage-skill", testo);
}

QStringList Finestra::selezionate(QTableWidget *t) const {
    QStringList nomi;
    for (int r = 0; r < t->rowCount(); ++r)
        if (t->item(r, 0) && t->item(r, 0)->checkState() == Qt::Checked && !t->isRowHidden(r)) nomi << t->item(r, 0)->text();
    return nomi;
}

void Finestra::mostraEsiti(const QJsonArray &esiti, const QString &titolo) {
    int ok = 0, no = 0;
    for (const auto &x : esiti) {
        const QJsonObject e = x.toObject();
        if (e["ok"].toBool()) {
            ++ok;
            QStringList dettagli;
            for (auto it = e.begin(); it != e.end(); ++it)
                if (!QStringList{"nome", "ok", "account", "tipo"}.contains(it.key()))
                    dettagli << it.key() + "=" + (it.value().isArray() ? unisci(it.value().toArray(), "; ") : it.value().toVariant().toString());
            registra("✓ " + e["nome"].toString() + ": " + dettagli.join(", "));
        } else {
            ++no;
            registra("✗ " + e["nome"].toString() + ": " + e["errore"].toString(), true);
        }
    }
    statusBar()->showMessage(L("%1: %2 riuscite, %3 non riuscite").arg(titolo).arg(ok).arg(no), 8000);
    if (no) QMessageBox::warning(this, titolo, L("%1 operazioni non riuscite: i motivi sono nel registro.").arg(no));
}

void Finestra::avvio() {
    QString problema;
    if (!m_motore->pronto(&problema)) {
        errore(problema);
        return;
    }
    m_motore->chiedi("stato", {}, [this](bool ok, const QJsonObject &r, const QString &e) {
        if (!ok) return errore(e);
        m_stato = r;
        setWindowTitle(L("manage-skill ") + r["versione"].toString());
        m_versione->setText("v" + r["versione"].toString());
        for (const auto &f : r["fonti"].toArray()) {
            m_fFonte->addItem(f.toString(), f.toString());
            m_daFonte->addItem(L("da: ") + f.toString(), f.toString());
        }
        registra(L("Motore pronto in ") + m_motore->cartellaProgetto());
        caricaCatalogo();
        caricaAccount();
    });
}

// ---------------------------------------------------------------- catalogo

QWidget *Finestra::creaCatalogo() {
    auto *w = new QWidget;
    auto *v = new QVBoxLayout(w);
    auto *filtri = new QHBoxLayout;
    m_cerca = new QLineEdit;
    m_cerca->setPlaceholderText(L("Cerca per nome o descrizione"));
    m_cerca->setClearButtonEnabled(true);
    m_fCategoria = new QComboBox;
    m_fCategoria->addItem(L("Tutte le categorie"), "");
    m_fFonte = new QComboBox;
    m_fFonte->addItem(L("Tutte le fonti"), "");
    m_fMie = new QCheckBox(L("solo le mie"));
    m_fDiverse = new QCheckBox(L("solo copie diverse"));
    auto *aggiorna = new QPushButton(L("Aggiorna"));
    auto *apriHtml = new QPushButton(L("Catalogo HTML"));
    filtri->addWidget(m_cerca, 1);
    filtri->addWidget(m_fCategoria);
    filtri->addWidget(m_fFonte);
    filtri->addWidget(m_fMie);
    filtri->addWidget(m_fDiverse);
    filtri->addWidget(aggiorna);
    filtri->addWidget(apriHtml);
    v->addLayout(filtri);

    m_tabCat = tabella({L("Nome"), L("Categoria"), L("Attiva"), L("Origine"), L("Fonti"), L("File"), "KB", L("Stato"), L("Più recente"), L("Note")});

    // Pannello sotto la tabella: tutte le copie della skill selezionata, dalla più recente
    auto *pannello = new QWidget;
    auto *pv = new QVBoxLayout(pannello);
    pv->setContentsMargins(0, 0, 0, 0);
    auto *pr = new QHBoxLayout;
    m_titoloCopie = new QLabel(L("Seleziona una skill per vedere dove stanno le sue copie."));
    m_titoloCopie->setTextFormat(Qt::RichText);
    auto *apriCopia = new QPushButton(L("Apri la cartella della copia"));
    auto *promptCopia = new QPushButton(L("Prompt…"));
    promptCopia->setToolTip(L("Crea il prompt da incollare in Claude per ricreare questa skill"));
    connect(promptCopia, &QPushButton::clicked, this, [this] {
        if (m_notaNome.isEmpty()) return errore("Seleziona una skill nel catalogo.");
        const auto r = m_tabCopie->selectionModel()->selectedRows();
        auto *d = new DialogoPrompt(m_motore, m_notaNome, r.isEmpty() ? QString() : m_tabCopie->item(r.first().row(), 1)->text(), this);
        d->setAttribute(Qt::WA_DeleteOnClose);
        d->show();
    });
    auto *modificaCopia = new QPushButton(L("Modifica…"));
    modificaCopia->setToolTip(L("Apre l'editor sulla copia selezionata (o sulla copia modificabile principale)"));
    pr->addWidget(m_titoloCopie, 1);
    pr->addWidget(promptCopia);
    pr->addWidget(modificaCopia);
    pr->addWidget(apriCopia);
    pv->addLayout(pr);
    auto *rigaCopie = new QHBoxLayout;
    m_tabCopie = tabella({"", L("Fonte"), L("Modificata"), L("Stato"), L("Attivazione"), L("Impronta"), L("Dove sta")});
    m_tabCopie->setSelectionMode(QAbstractItemView::SingleSelection);
    rigaCopie->addWidget(m_tabCopie, 3);
    auto *colNota = new QVBoxLayout;
    colNota->addWidget(new QLabel(L("Note sulla skill")));
    m_nota = new QPlainTextEdit;
    m_nota->setPlaceholderText(L("Annotazioni tue: a cosa serve, da dove viene, cosa ricordare…"));
    m_nota->setEnabled(false);
    m_salvaNota = new QPushButton(L("Salva nota"));
    m_salvaNota->setEnabled(false);
    colNota->addWidget(m_nota, 1);
    colNota->addWidget(m_salvaNota, 0, Qt::AlignRight);
    rigaCopie->addLayout(colNota, 2);
    pv->addLayout(rigaCopie);
    connect(m_salvaNota, &QPushButton::clicked, this, &Finestra::salvaNota);
    connect(m_nota, &QPlainTextEdit::modificationChanged, m_salvaNota, &QPushButton::setEnabled);
    connect(modificaCopia, &QPushButton::clicked, this, [this] {
        if (m_notaNome.isEmpty()) return errore(L("Seleziona una skill nel catalogo."));
        const auto r = m_tabCopie->selectionModel()->selectedRows();
        modifica(m_notaNome, r.isEmpty() ? QString() : m_tabCopie->item(r.first().row(), 1)->text());
    });
    connect(m_tabCopie, &QTableWidget::cellDoubleClicked, this, [this](int r, int) {
        modifica(m_notaNome, m_tabCopie->item(r, 1)->text());
    });
    auto *divisore = new QSplitter(Qt::Vertical);
    divisore->addWidget(m_tabCat);
    divisore->addWidget(pannello);
    divisore->setStretchFactor(0, 3);
    divisore->setStretchFactor(1, 1);
    v->addWidget(divisore, 1);
    connect(m_tabCat, &QTableWidget::currentCellChanged, this, &Finestra::mostraCopie);
    connect(apriCopia, &QPushButton::clicked, this, [this] {
        const auto r = m_tabCopie->selectionModel()->selectedRows();
        if (r.isEmpty()) return errore(L("Seleziona una copia nella tabella delle copie."));
        QDesktopServices::openUrl(QUrl::fromLocalFile(m_tabCopie->item(r.first().row(), 6)->text()));
    });

    auto *azioni = new QHBoxLayout;
    m_contaCat = new QLabel;
    m_daFonte = new QComboBox;
    m_daFonte->addItem(L("da: copia migliore"), "");
    auto *esporta = new QPushButton(L("Esporta in archivio"));
    m_verso = new QComboBox;
    m_prova = new QCheckBox(L("solo prova"));
    m_prova->setChecked(true);
    m_prova->setToolTip(L("Mostra cosa farebbe l'importazione senza modificare nulla"));
    m_sovrascrivi = new QCheckBox(L("sovrascrivi"));
    m_sovrascrivi->setToolTip(L("claude-code: sostituisce una copia diversa (salvata prima in archivio)"));
    m_ignora = new QCheckBox(L("ignora segreti"));
    auto *importa = new QPushButton(L("Importa"));
    importa->setDefault(true);
    azioni->addWidget(m_contaCat);
    azioni->addStretch();
    azioni->addWidget(m_daFonte);
    azioni->addWidget(esporta);
    azioni->addSpacing(16);
    azioni->addWidget(m_verso);
    azioni->addWidget(m_prova);
    azioni->addWidget(m_sovrascrivi);
    azioni->addWidget(m_ignora);
    azioni->addWidget(importa);
    v->addLayout(azioni);

    connect(m_cerca, &QLineEdit::textChanged, this, &Finestra::filtraCatalogo);
    connect(m_fCategoria, &QComboBox::currentIndexChanged, this, &Finestra::filtraCatalogo);
    connect(m_fFonte, &QComboBox::currentIndexChanged, this, &Finestra::filtraCatalogo);
    connect(m_fMie, &QCheckBox::toggled, this, &Finestra::filtraCatalogo);
    connect(m_fDiverse, &QCheckBox::toggled, this, &Finestra::filtraCatalogo);
    connect(m_tabCat, &QTableWidget::itemChanged, this, [this](QTableWidgetItem *i) { if (i->column() == 0) filtraCatalogo(); });
    connect(aggiorna, &QPushButton::clicked, this, &Finestra::caricaCatalogo);
    connect(apriHtml, &QPushButton::clicked, this, [this] {
        QDesktopServices::openUrl(QUrl::fromLocalFile(m_motore->cartellaProgetto() + "/catalogo/catalogo.html"));
    });
    connect(m_tabCat, &QTableWidget::cellDoubleClicked, this, [this](int r, int) {
        auto *d = new DialogoSkill(m_motore, m_tabCat->item(r, 0)->text(), m_daFonte->currentData().toString(), this);
        d->setAttribute(Qt::WA_DeleteOnClose);
        d->show();
    });
    connect(esporta, &QPushButton::clicked, this, &Finestra::esportaCatalogo);
    connect(importa, &QPushButton::clicked, this, &Finestra::importaCatalogo);
    return w;
}

void Finestra::caricaCatalogo() {
    registra(L("Ricerca delle skill…"));
    m_motore->chiedi("catalogo", {}, [this](bool ok, const QJsonObject &r, const QString &e) {
        if (!ok) return errore(e);
        const QStringList giaScelte = selezionate(m_tabCat);
        const QSet<QString> prima(giaScelte.begin(), giaScelte.end());
        m_catalogo = r["skill"].toArray();
        QSet<QString> categorie;
        m_tabCat->blockSignals(true);
        m_tabCat->setSortingEnabled(false);
        m_tabCat->setRowCount(0);
        for (const auto &x : m_catalogo) {
            const QJsonObject s = x.toObject();
            categorie << s["categoria"].toString();
            const int n = m_tabCat->rowCount();
            m_tabCat->insertRow(n);
            m_tabCat->setItem(n, 0, cellaNome(s["nome"].toString(), s["descrizione"].toString(), prima.contains(s["nome"].toString())));
            m_tabCat->setItem(n, 1, cella(s["categoria"]));
            const QJsonObject att = s["attivazione"].toObject();
            auto *attiva = new QTableWidgetItem(L(att["stato"].toString()));
            attiva->setToolTip(L(att["perche"].toString()));
            attiva->setForeground(att["attiva"].isNull() ? QColor(Qt::gray) : att["attiva"].toBool() ? OK : ERRORE);
            m_tabCat->setItem(n, 2, attiva);
            m_tabCat->setItem(n, 3, cella(s["origine"]));
            m_tabCat->setItem(n, 4, new QTableWidgetItem(unisci(s["fonti"].toArray())));
            m_tabCat->setItem(n, 5, cella(s["file"]));
            m_tabCat->setItem(n, 6, cella(s["kb"]));
            const bool allineata = s["allineata"].toBool();
            auto *stato = new QTableWidgetItem(allineata ? L("allineata") : QString(L("copie diverse (%1)")).arg(s["copie"].toArray().size()));
            stato->setForeground(allineata ? OK : AVVISO);
            auto *recente = new QTableWidgetItem;
            if (!allineata) {
                QFont f = stato->font();
                f.setBold(true);
                stato->setFont(f);
                const QJsonObject p = s["piu_recente"].toObject();
                recente->setText("★ " + p["fonte"].toString() + " · " + p["modificata"].toString());
                recente->setToolTip(L("Versione più recente: ") + p["percorso"].toString());
                recente->setForeground(OK);
                recente->setFont(f);
            }
            m_tabCat->setItem(n, 7, stato);
            m_tabCat->setItem(n, 8, recente);
            auto *nota = new QTableWidgetItem(s["nota"].toString().section('\n', 0, 0).left(80));
            nota->setToolTip(s["nota"].toString());
            m_tabCat->setItem(n, 9, nota);
        }
        m_tabCat->setSortingEnabled(true);
        m_tabCat->sortByColumn(0, Qt::AscendingOrder);
        m_tabCat->resizeColumnsToContents();
        m_tabCat->blockSignals(false);

        const QString scelta = m_fCategoria->currentData().toString();
        m_fCategoria->blockSignals(true);
        m_fCategoria->clear();
        m_fCategoria->addItem(L("Tutte le categorie"), "");
        QStringList ordinate(categorie.begin(), categorie.end());
        ordinate.sort();
        for (const auto &c : ordinate) m_fCategoria->addItem(c, c);
        m_fCategoria->setCurrentIndex(qMax(0, m_fCategoria->findData(scelta)));
        m_fCategoria->blockSignals(false);
        filtraCatalogo();
        mostraCopie();
        aggiornaContatori();
        registra(L("%1 skill nel catalogo (salvato anche in catalogo/catalogo.html)").arg(m_catalogo.size()));
    });
}

void Finestra::mostraCopie() {
    m_tabCopie->setRowCount(0);
    const int r = m_tabCat->currentRow();
    if (r < 0 || !m_tabCat->item(r, 0)) return;
    const QString nome = m_tabCat->item(r, 0)->text();
    QJsonObject s;
    for (const auto &x : m_catalogo)
        if (x.toObject()["nome"].toString() == nome) s = x.toObject();
    const bool allineata = s["allineata"].toBool();
    const QJsonObject p = s["piu_recente"].toObject();
    m_notaNome = nome;
    m_nota->setEnabled(true);
    m_nota->setPlainText(s["nota"].toString());
    m_nota->document()->setModified(false);
    m_titoloCopie->setText(allineata
        ? QString(L("<b>%1</b>: %2 copie, tutte uguali.")).arg(nome.toHtmlEscaped()).arg(s["copie"].toArray().size())
        : QString(L("<b>%1</b>: copie diverse. <span style='color:") + Stile::verde() + L("'>★ La più recente è in <b>%2</b> (%3)</span>"))
              .arg(nome.toHtmlEscaped(), p["fonte"].toString().toHtmlEscaped(), p["modificata"].toString()));
    for (const auto &x : s["copie"].toArray()) {
        const QJsonObject c = x.toObject();
        const int n = m_tabCopie->rowCount();
        m_tabCopie->insertRow(n);
        const bool piuRecente = c["piu_recente"].toBool();
        QString stato = L("uguale");
        QColor colore = OK;
        if (!allineata) {
            if (piuRecente) stato = L("★ più recente");
            else if (c["fonte"] == "archivio") { stato = L("esportazione"); colore = Qt::gray; }
            else { stato = L("più vecchia, diversa"); colore = AVVISO; }
        }
        const QStringList valori{piuRecente ? "★" : "", c["fonte"].toString(), c["modificata"].toString(), stato,
                                 L(c["attivazione"].toString()), c["impronta"].toString(), c["percorso"].toString()};
        for (int k = 0; k < valori.size(); ++k) {
            auto *i = new QTableWidgetItem(valori[k]);
            if (k == 3 || k == 0) i->setForeground(colore);
            if (piuRecente) { QFont f = i->font(); f.setBold(true); i->setFont(f); }
            if (k == 4) i->setToolTip(L(c["perche"].toString()));
            if (k == 6 && !c["collegamento"].toString().isEmpty()) i->setToolTip(L("collegamento a ") + c["collegamento"].toString());
            m_tabCopie->setItem(n, k, i);
        }
    }
    m_tabCopie->resizeColumnsToContents();
}

void Finestra::salvaNota() {
    if (m_notaNome.isEmpty()) return;
    const QString nome = m_notaNome, testo = m_nota->toPlainText();
    m_motore->chiedi("nota", {{"nome", nome}, {"testo", testo}}, [this, nome](bool ok, const QJsonObject &r, const QString &e) {
        if (!ok) return errore(e);
        registra(r["messaggio"].toString());
        m_nota->document()->setModified(false);
        for (int i = 0; i < m_catalogo.size(); ++i) {
            QJsonObject s = m_catalogo[i].toObject();
            if (s["nome"].toString() == nome) { s["nota"] = r["nota"]; m_catalogo[i] = s; }
        }
        for (int row = 0; row < m_tabCat->rowCount(); ++row)
            if (m_tabCat->item(row, 0)->text() == nome) {
                m_tabCat->item(row, 9)->setText(r["nota"].toString().section('\n', 0, 0).left(80));
                m_tabCat->item(row, 9)->setToolTip(r["nota"].toString());
            }
    });
}

void Finestra::modifica(const QString &nome, const QString &fonte) {
    auto *e = new EditorSkill(m_motore, nome, fonte, this);
    e->setAttribute(Qt::WA_DeleteOnClose);
    connect(e, &EditorSkill::salvata, this, [this, nome] { registra(L("Modificata ") + nome); caricaCatalogo(); });
    e->show();
}

void Finestra::filtraCatalogo() {
    QHash<QString, QJsonObject> perNome;
    for (const auto &x : m_catalogo) perNome[x.toObject()["nome"].toString()] = x.toObject();
    const QString q = m_cerca->text().toLower(), cat = m_fCategoria->currentData().toString(), fonte = m_fFonte->currentData().toString();
    int visibili = 0;
    for (int r = 0; r < m_tabCat->rowCount(); ++r) {
        const QJsonObject s = perNome.value(m_tabCat->item(r, 0)->text());
        const bool mostra = (q.isEmpty() || (s["nome"].toString() + " " + s["descrizione"].toString()).toLower().contains(q))
            && (cat.isEmpty() || s["categoria"].toString() == cat)
            && (fonte.isEmpty() || s["fonti"].toArray().contains(fonte))
            && (!m_fMie->isChecked() || s["origine"].toString() == "tua")
            && (!m_fDiverse->isChecked() || !s["allineata"].toBool());
        m_tabCat->setRowHidden(r, !mostra);
        visibili += mostra;
    }
    m_contaCat->setText(L("%1 selezionate · %2 di %3 mostrate").arg(selezionate(m_tabCat).size()).arg(visibili).arg(m_catalogo.size()));
}

void Finestra::esportaCatalogo() {
    const QStringList nomi = selezionate(m_tabCat);
    if (nomi.isEmpty()) return errore(L("Seleziona almeno una skill (casella nella colonna Nome)."));
    m_motore->chiedi("esporta", {{"nomi", QJsonArray::fromStringList(nomi)}, {"da", m_daFonte->currentData().toString()},
                                 {"ignora_segreti", m_ignora->isChecked()}},
                     [this](bool ok, const QJsonObject &r, const QString &e) {
                         if (!ok) return errore(e);
                         mostraEsiti(r["esiti"].toArray(), L("Esportazione in archivio"));
                     });
}

void Finestra::importaCatalogo() {
    const QStringList nomi = selezionate(m_tabCat);
    if (nomi.isEmpty()) return errore(L("Seleziona almeno una skill (casella nella colonna Nome)."));
    const QString verso = m_verso->currentData().toString();
    if (verso.isEmpty()) return errore(L("Scegli l'account di destinazione."));
    const bool prova = m_prova->isChecked();
    if (!prova && QMessageBox::question(this, L("Importa"), QString(L("Importare %1 skill in '%2'?%3")).arg(nomi.size()).arg(verso)
                                            .arg(m_sovrascrivi->isChecked() ? L("\nLe copie diverse verranno sostituite (prima salvate in archivio).") : ""))
                      != QMessageBox::Yes)
        return;
    m_motore->chiedi("importa", {{"nomi", QJsonArray::fromStringList(nomi)}, {"da", m_daFonte->currentData().toString()}, {"verso", verso},
                                 {"prova", prova}, {"sovrascrivi", m_sovrascrivi->isChecked()}, {"ignora_segreti", m_ignora->isChecked()}},
                     [this, prova, verso](bool ok, const QJsonObject &r, const QString &e) {
                         if (!ok) return errore(e);
                         mostraEsiti(r["esiti"].toArray(), prova ? L("Prova di importazione (nessuna modifica)") : L("Importazione in ") + verso);
                         if (!prova) caricaCatalogo();
                     });
}

// ---------------------------------------------------------------- cloud

QWidget *Finestra::creaCloud() {
    auto *w = new QWidget;
    auto *v = new QVBoxLayout(w);
    m_infoCloud = new QLabel(L("Caricamento…"));
    m_infoCloud->setWordWrap(true);
    v->addWidget(m_infoCloud);
    auto *riga = new QHBoxLayout;
    m_cMie = new QCheckBox(L("solo le mie"));
    auto *aggiorna = new QPushButton(L("Aggiorna"));
    auto *espSel = new QPushButton(L("Esporta selezionate"));
    auto *espMie = new QPushButton(L("Esporta tutte le mie"));
    auto *espTutte = new QPushButton(L("Esporta tutte"));
    m_cIgnora = new QCheckBox(L("ignora segreti"));
    riga->addWidget(m_cMie);
    riga->addWidget(aggiorna);
    riga->addStretch();
    riga->addWidget(espSel);
    riga->addWidget(espMie);
    riga->addWidget(espTutte);
    riga->addWidget(m_cIgnora);
    v->addLayout(riga);
    auto *rigaApi = new QHBoxLayout;
    auto *etichetta = new QLabel(L("Importa in un account API (selezionate, o tutte le tue se non ne selezioni):"));
    m_cApiAcc = new QComboBox;
    m_cProvaApi = new QCheckBox(L("solo prova"));
    m_cProvaApi->setChecked(true);
    auto *versoApi = new QPushButton(L("Importa in account API"));
    rigaApi->addWidget(etichetta);
    rigaApi->addWidget(m_cApiAcc);
    rigaApi->addWidget(m_cProvaApi);
    rigaApi->addWidget(versoApi);
    rigaApi->addStretch();
    v->addLayout(rigaApi);
    connect(versoApi, &QPushButton::clicked, this, &Finestra::cloudVersoApi);
    m_tabCloud = tabella({L("Nome"), L("Tipo"), L("Categoria"), L("Aggiornata"), L("File"), "KB", L("Copia locale"), L("Id claude.ai")});
    v->addWidget(m_tabCloud, 3);

    auto *gruppo = new QGroupBox(L("Skill negli account API della Claude Console"));
    auto *g = new QVBoxLayout(gruppo);
    auto *nota = new QLabel(L("La Skills API mostra nome, id e versioni; i file non si scaricano. Le skill della Console e quelle di claude.ai sono archivi separati: le colonne a destra dicono dove esiste una skill con lo stesso nome."));
    nota->setWordWrap(true);
    nota->setStyleSheet("color: gray");
    g->addWidget(nota);
    auto *ra = new QHBoxLayout;
    auto *console = new QPushButton(L("Configura account API (Claude Console)…"));
    auto *caricaApi = new QPushButton(L("Scansiona le skill degli account API"));
    ra->addWidget(console);
    ra->addWidget(caricaApi);
    ra->addStretch();
    g->addLayout(ra);
    connect(console, &QPushButton::clicked, this, &Finestra::configuraConsole);
    m_tabApiCloud = tabella({L("Account"), L("Nome"), "Id", L("Versione"), L("Creata"), L("Aggiornata"), L("Sul PC"), L("Su claude.ai"), L("Errore")});
    g->addWidget(m_tabApiCloud);
    v->addWidget(gruppo, 1);

    connect(m_cMie, &QCheckBox::toggled, this, &Finestra::caricaCloud);
    connect(aggiorna, &QPushButton::clicked, this, &Finestra::caricaCloud);
    connect(espSel, &QPushButton::clicked, this, [this] {
        const QStringList nomi = selezionate(m_tabCloud);
        if (nomi.isEmpty()) return errore(L("Seleziona almeno una skill."));
        esportaCloud({{"nomi", QJsonArray::fromStringList(nomi)}});
    });
    connect(espMie, &QPushButton::clicked, this, [this] { esportaCloud({{"mie", true}}); });
    connect(espTutte, &QPushButton::clicked, this, [this] { esportaCloud({}); });
    connect(caricaApi, &QPushButton::clicked, this, &Finestra::caricaApiCloud);
    connect(m_tabCloud, &QTableWidget::cellDoubleClicked, this, [this](int r, int) {
        auto *d = new DialogoSkill(m_motore, m_tabCloud->item(r, 0)->text(), "claude-ai", this);
        d->setAttribute(Qt::WA_DeleteOnClose);
        d->show();
    });
    return w;
}

void Finestra::caricaCloud() {
    QJsonObject dati;
    if (m_cMie->isChecked()) dati["mie"] = "1";
    m_motore->chiedi("cloud", dati, [this](bool ok, const QJsonObject &r, const QString &e) {
        if (!ok) return errore(e);
        QStringList info;
        for (const auto &x : r["conti"].toArray()) {
            const QJsonObject c = x.toObject();
            info << QString(L("Account <b>%1</b>: %2 skill, copia sincronizzata da Claude Code il %3."))
                        .arg(c["nome"].toString().toHtmlEscaped()).arg(c["skill"].toInt()).arg(c["aggiornato"].toString());
        }
        m_infoCloud->setText(info.isEmpty() ? L("Nessuna copia sincronizzata: apri Claude Code collegato al tuo account claude.ai.")
                                            : info.join("<br>") + L("<br>Le esportazioni vanno in <code>manageskill/archivio/cloud/&lt;account&gt;/&lt;data-ora&gt;/</code> con le cartelle, gli ZIP e l'indice. Per avere l'ultima versione apri Claude Code prima di esportare."));
        const QStringList giaScelte = selezionate(m_tabCloud);
        const QSet<QString> prima(giaScelte.begin(), giaScelte.end());
        m_tabCloud->setSortingEnabled(false);
        m_tabCloud->setRowCount(0);
        for (const auto &x : r["skill"].toArray()) {
            const QJsonObject s = x.toObject();
            const int n = m_tabCloud->rowCount();
            m_tabCloud->insertRow(n);
            m_tabCloud->setItem(n, 0, cellaNome(s["nome"].toString(), s["descrizione"].toString(), prima.contains(s["nome"].toString())));
            int c = 1;
            for (const char *k : {"tipo", "categoria", "aggiornata", "file", "kb"}) m_tabCloud->setItem(n, c++, cella(s[k]));
            auto *locale = new QTableWidgetItem(L(s["locale"].toString()));
            locale->setForeground(s["locale"] == "uguale" ? OK : s["locale"] == "diversa" ? AVVISO : QColor(Qt::gray));
            m_tabCloud->setItem(n, c++, locale);
            m_tabCloud->setItem(n, c, cella(s["skill_id"]));
        }
        m_tabCloud->setSortingEnabled(true);
        m_tabCloud->sortByColumn(0, Qt::AscendingOrder);
        m_tabCloud->resizeColumnsToContents();
    });
}

void Finestra::esportaCloud(const QJsonObject &dati) {
    QJsonObject d = dati;
    d["ignora_segreti"] = m_cIgnora->isChecked();
    registra(L("Esportazione delle skill del cloud…"));
    m_motore->chiedi("cloud_esporta", d, [this](bool ok, const QJsonObject &r, const QString &e) {
        if (!ok) return errore(e);
        const QJsonObject ris = r["risultati"].toObject();
        QString ultimaCartella;
        int saltate = 0;
        for (auto it = ris.begin(); it != ris.end(); ++it) {
            const QJsonObject x = it.value().toObject();
            if (!x["cartella"].isNull()) {
                ultimaCartella = x["cartella"].toString();
                registra(QString(L("✓ %1: %2 skill esportate in %3")).arg(it.key()).arg(x["esportate"].toArray().size()).arg(ultimaCartella));
                const QJsonArray cambiate = x["cambiate"].toArray();
                registra(cambiate.isEmpty() ? L("   nessuna cambiata rispetto all'esportazione precedente")
                                            : L("   nuove o cambiate: ") + unisci(cambiate));
            }
            for (const auto &s : x["saltate"].toArray()) {
                ++saltate;
                QStringList dove;
                for (const auto &g : s.toObject()["segreti"].toArray())
                    dove << g.toObject()["file"].toString() + ":" + g.toObject()["riga"].toVariant().toString();
                registra("✗ " + s.toObject()["nome"].toString() + ": " + s.toObject()["motivo"].toString() + " (" + dove.join(", ") + ")", true);
            }
        }
        if (saltate) QMessageBox::warning(this, L("Esportazione"), L("%1 skill saltate per possibili segreti: dettagli nel registro.").arg(saltate));
        if (!ultimaCartella.isEmpty() &&
            QMessageBox::question(this, L("Esportazione completata"), L("Esportazione salvata in\n") + ultimaCartella + L("\n\nAprire l'indice?")) == QMessageBox::Yes)
            QDesktopServices::openUrl(QUrl::fromLocalFile(ultimaCartella + "/indice.html"));
    });
}

void Finestra::caricaApiCloud() {
    m_motore->chiedi("cloud_api", {}, [this](bool ok, const QJsonObject &r, const QString &e) {
        if (!ok) return errore(e);
        riempi(m_tabApiCloud, r["skill"].toArray(), {"account", "nome", "id", "versione", "creata", "aggiornata", "sul_pc", "su_claude_ai", "errore"});
        if (r["skill"].toArray().isEmpty())
            registra(L("Nessuna skill trovata: configura un account con \"Configura account API (Claude Console)\" oppure l'account non ha skill custom."));
        else
            registra(QString(L("Scansione API: %1 righe")).arg(r["skill"].toArray().size()));
    });
}

void Finestra::cloudVersoApi() {
    const QString acc = m_cApiAcc->currentData().toString();
    if (acc.isEmpty()) return errore(L("Configura prima un account API (pulsante \"Configura account API (Claude Console)\")."));
    const QStringList nomi = selezionate(m_tabCloud);
    const bool prova = m_cProvaApi->isChecked();
    if (!prova && QMessageBox::question(this, L("Importa in account API"),
            QString(L("Caricare in '%1' %2?\nLe skill nuove vengono create, quelle cambiate diventano una nuova versione."))
                .arg(acc, nomi.isEmpty() ? L("tutte le tue skill di claude.ai") : L("%1 skill").arg(nomi.size()))) != QMessageBox::Yes)
        return;
    registra(prova ? L("Prova di importazione in ") + acc + "…" : L("Importazione in ") + acc + "…");
    m_motore->chiedi("cloud_verso_api", {{"account", acc}, {"nomi", QJsonArray::fromStringList(nomi)}, {"prova", prova},
                                         {"ignora_segreti", m_cIgnora->isChecked()}},
                     [this, prova, acc](bool ok, const QJsonObject &r, const QString &e) {
                         if (!ok) return errore(e);
                         const QJsonArray esiti = r["esiti"].toArray();
                         for (const auto &x : esiti)
                             if (x.toObject().contains("avviso"))
                                 registra(L("   attenzione, ") + x.toObject()["nome"].toString() + ": " + x.toObject()["avviso"].toString(), true);
                         mostraEsiti(esiti, prova ? L("Prova di importazione in ") + acc + L(" (nessuna modifica)") : L("Importazione in ") + acc);
                         if (!prova) caricaApiCloud();
                     });
}

void Finestra::configuraConsole() {
    auto *d = new DialogoConsole(m_motore, m_stato["keyring"].toBool(), this);
    d->setAttribute(Qt::WA_DeleteOnClose);
    connect(d, &DialogoConsole::salvato, this, [this](const QString &msg) {
        registra(msg);
        QMessageBox::information(this, L("Account API"), msg);
        caricaAccount();
        caricaApiCloud();
    });
    d->open();
}

// ---------------------------------------------------------------- account

QWidget *Finestra::creaAccount() {
    auto *w = new QWidget;
    auto *v = new QVBoxLayout(w);
    m_tabAcc = tabella({L("Nome"), L("Tipo"), L("Dove"), L("Chiave"), L("Nota")});
    m_tabAcc->setSelectionMode(QAbstractItemView::SingleSelection);
    v->addWidget(m_tabAcc, 1);
    auto *riga = new QHBoxLayout;
    auto *nuovo = new QPushButton(L("Nuovo account…"));
    auto *prova = new QPushButton(L("Prova"));
    auto *chiave = new QPushButton(L("Cambia chiave…"));
    auto *rimuovi = new QPushButton(L("Rimuovi"));
    riga->addWidget(nuovo);
    riga->addStretch();
    riga->addWidget(prova);
    riga->addWidget(chiave);
    riga->addWidget(rimuovi);
    v->addLayout(riga);
    auto *nota = new QLabel(L("Le chiavi stanno nel portachiavi di sistema o in ~/.config/manage-skill/chiavi (permessi 600): non compaiono mai qui né in dati/account.json."));
    nota->setWordWrap(true);
    nota->setStyleSheet("color: gray");
    v->addWidget(nota);

    auto *gruppo = new QGroupBox(L("Skill in un account API"));
    auto *g = new QVBoxLayout(gruppo);
    auto *rr = new QHBoxLayout;
    m_remAcc = new QComboBox;
    m_remTutte = new QCheckBox(L("anche quelle di Anthropic"));
    auto *elenca = new QPushButton(L("Elenca"));
    auto *elimina = new QPushButton(L("Elimina la selezionata…"));
    rr->addWidget(m_remAcc);
    rr->addWidget(m_remTutte);
    rr->addWidget(elenca);
    rr->addStretch();
    rr->addWidget(elimina);
    g->addLayout(rr);
    m_tabRemoto = tabella({L("Nome"), "Id", L("Fonte"), L("Versione"), L("Creata")});
    m_tabRemoto->setSelectionMode(QAbstractItemView::SingleSelection);
    g->addWidget(m_tabRemoto);
    v->addWidget(gruppo, 1);

    connect(nuovo, &QPushButton::clicked, this, &Finestra::nuovoAccount);
    connect(prova, &QPushButton::clicked, this, &Finestra::provaAccount);
    connect(chiave, &QPushButton::clicked, this, &Finestra::cambiaChiave);
    connect(rimuovi, &QPushButton::clicked, this, &Finestra::rimuoviAccount);
    connect(elenca, &QPushButton::clicked, this, &Finestra::elencaRemoto);
    connect(elimina, &QPushButton::clicked, this, &Finestra::eliminaRemoto);
    return w;
}

void Finestra::caricaAccount() {
    m_motore->chiedi("account", {}, [this](bool ok, const QJsonObject &r, const QString &e) {
        if (!ok) return errore(e);
        m_account = r["account"].toArray();
        QJsonArray righe;
        const QString versoPrima = m_verso->currentData().toString();
        m_verso->clear();
        m_remAcc->clear();
        const QString apiPrima = m_cApiAcc->currentData().toString();
        m_cApiAcc->clear();
        for (const auto &x : m_account) {
            QJsonObject a = x.toObject();
            QString dove = a["cartella"].toString();
            if (dove.isEmpty()) dove = a["workspace_id"].toString();
            if (dove.isEmpty()) dove = a["base_url"].toString();
            if (dove.isEmpty() && a["tipo"] == "claude-ai") dove = "manageskill/archivio/_da-caricare";
            a["dove"] = dove;
            if (a["chiave"].toString().isEmpty()) a["chiave"] = "–";
            righe.append(a);
            m_verso->addItem(L("verso: ") + a["nome"].toString() + " (" + a["tipo"].toString() + ")", a["nome"].toString());
            if (a["tipo"] == "api") {
                m_remAcc->addItem(a["nome"].toString());
                m_cApiAcc->addItem(a["nome"].toString(), a["nome"].toString());
            }
        }
        m_verso->setCurrentIndex(qMax(0, m_verso->findData(versoPrima)));
        if (m_remAcc->count() == 0) m_remAcc->addItem("nessun account api", "");
        if (m_cApiAcc->count() == 0) m_cApiAcc->addItem("nessun account api", "");
        m_cApiAcc->setCurrentIndex(qMax(0, m_cApiAcc->findData(apiPrima)));
        riempi(m_tabAcc, righe, {"nome", "tipo", "dove", "chiave", "nota"});
    });
}

QString Finestra::accountSelezionato() const {
    const auto righe = m_tabAcc->selectionModel()->selectedRows();
    return righe.isEmpty() ? QString() : m_tabAcc->item(righe.first().row(), 0)->text();
}

void Finestra::nuovoAccount() {
    DialogoAccount d(m_stato["tipi_account"].toObject(), m_stato["keyring"].toBool(), this);
    if (d.exec() != QDialog::Accepted) return;
    QJsonObject dati = d.dati();
    d.pulisciChiave();
    m_motore->chiedi("account_salva", dati, [this](bool ok, const QJsonObject &r, const QString &e) {
        if (!ok) return errore(e);
        registra(r["messaggio"].toString());
        caricaAccount();
    });
    dati = {};  // la copia della chiave non resta in memoria più del necessario
}

void Finestra::provaAccount() {
    const QString nome = accountSelezionato();
    if (nome.isEmpty()) return errore(L("Seleziona un account nella tabella."));
    m_motore->chiedi("account_prova", {{"nome", nome}}, [this, nome](bool ok, const QJsonObject &r, const QString &e) {
        if (!ok) return errore(e);
        const QString msg = nome + ": " + r["messaggio"].toString();
        registra(msg, !r["ok"].toBool());
        if (r["ok"].toBool())
            QMessageBox::information(this, L("Prova account"), msg);
        else
            QMessageBox::warning(this, L("Prova account"), msg);
    });
}

void Finestra::cambiaChiave() {
    const QString nome = accountSelezionato();
    if (nome.isEmpty()) return errore(L("Seleziona un account api nella tabella."));
    bool ok = false;
    QString chiave = QInputDialog::getText(this, L("Cambia chiave"), L("Nuova chiave API per '") + nome + L("' (non viene mostrata):"),
                                           QLineEdit::Password, {}, &ok);
    if (!ok || chiave.trimmed().isEmpty()) return;
    m_motore->chiedi("account_chiave", {{"nome", nome}, {"valore_chiave", chiave.trimmed()}},
                     [this](bool ok2, const QJsonObject &r, const QString &e) {
                         if (!ok2) return errore(e);
                         registra(r["messaggio"].toString());
                         caricaAccount();
                     });
    chiave.fill(QChar(' '));
    chiave.clear();
}

void Finestra::rimuoviAccount() {
    const QString nome = accountSelezionato();
    if (nome.isEmpty()) return errore(L("Seleziona un account nella tabella."));
    if (QMessageBox::question(this, L("Rimuovi account"), L("Rimuovere l'account '") + nome + L("' e la sua chiave salvata?")) != QMessageBox::Yes) return;
    m_motore->chiedi("account_rimuovi", {{"nome", nome}}, [this](bool ok, const QJsonObject &r, const QString &e) {
        if (!ok) return errore(e);
        registra(r["messaggio"].toString());
        caricaAccount();
    });
}

void Finestra::elencaRemoto() {
    const QString acc = m_remAcc->currentText();
    if (acc.isEmpty() || acc == "nessun account api") return errore(L("Aggiungi prima un account di tipo api."));
    QJsonObject dati{{"account", acc}};
    if (m_remTutte->isChecked()) dati["tutte"] = "1";
    m_motore->chiedi("remoto", dati, [this](bool ok, const QJsonObject &r, const QString &e) {
        if (!ok) return errore(e);
        riempi(m_tabRemoto, r["skill"].toArray(), {"nome", "id", "fonte", "versione", "creata"});
        registra(L("%1 skill nell'account %2").arg(r["skill"].toArray().size()).arg(m_remAcc->currentText()));
    });
}

void Finestra::eliminaRemoto() {
    const auto righe = m_tabRemoto->selectionModel()->selectedRows();
    if (righe.isEmpty()) return errore(L("Seleziona una skill nella tabella dell'account API."));
    const int r = righe.first().row();
    const QString nome = m_tabRemoto->item(r, 0)->text(), acc = m_remAcc->currentText();
    if (m_tabRemoto->item(r, 2)->text() != "custom") return errore(L("Si possono eliminare solo le skill custom."));
    bool ok = false;
    const QString conferma = QInputDialog::getText(this, L("Elimina skill"),
        L("Eliminare '") + nome + L("' dall'account ") + acc + L(" con TUTTE le sue versioni?\nNon si può annullare.\n\nScrivi il nome della skill per confermare:"),
        QLineEdit::Normal, {}, &ok);
    if (!ok) return;
    m_motore->chiedi("remoto_elimina", {{"account", acc}, {"nome", nome}, {"conferma", conferma.trimmed()}},
                     [this](bool ok2, const QJsonObject &res, const QString &e) {
                         if (!ok2) return errore(e);
                         registra(res["messaggio"].toString());
                         elencaRemoto();
                     });
}

// ---------------------------------------------------------------- terze parti

QWidget *Finestra::creaTerze() {
    auto *w = new QWidget;
    auto *v = new QVBoxLayout(w);
    auto *nota = new QLabel(L("Skill prese da altri (repository Git, ZIP, cartelle). Restano in manageskill/terze-parti/: \"Aggiorna dalla sorgente\" scarica le nuove versioni, \"Sincronizza\" le porta negli account scelti. Gli script non vengono mai eseguiti da manage-skill: controllali prima di usare la skill."));
    nota->setWordWrap(true);
    nota->setStyleSheet("color: gray");
    v->addWidget(nota);
    auto *r1 = new QHBoxLayout;
    auto *aggiungi = new QPushButton(L("Aggiungi…"));
    auto *aggiorna = new QPushButton(L("Aggiorna dalla sorgente"));
    auto *destinazioni = new QPushButton(L("Destinazioni…"));
    auto *sincronizza = new QPushButton(L("Sincronizza con gli account"));
    m_tProva = new QCheckBox(L("solo prova"));
    m_tProva->setChecked(true);
    m_tForza = new QCheckBox(L("forza"));
    m_tForza->setToolTip(L("Aggiorna: sostituisce anche le copie modificate qui.\nSincronizza: sostituisce le copie modificate a mano negli account.\nLe copie sostituite vanno sempre in archivio."));
    r1->addWidget(aggiungi);
    r1->addWidget(aggiorna);
    r1->addWidget(destinazioni);
    r1->addWidget(sincronizza);
    r1->addWidget(m_tProva);
    r1->addWidget(m_tForza);
    r1->addStretch();
    auto *modificaT = new QPushButton(L("Modifica…"));
    auto *apri = new QPushButton(L("Apri la cartella"));
    auto *rimuovi = new QPushButton(L("Rimuovi"));
    r1->addWidget(modificaT);
    r1->addWidget(apri);
    r1->addWidget(rimuovi);
    v->addLayout(r1);
    m_tabTerze = tabella({L("Nome"), L("Stato"), L("Commit"), L("Aggiornata"), L("Sincronizzata"), L("Destinazioni"), L("Script"), L("Sorgente")});
    v->addWidget(m_tabTerze, 1);

    connect(aggiungi, &QPushButton::clicked, this, &Finestra::aggiungiTerze);
    connect(aggiorna, &QPushButton::clicked, this, [this] { aggiornaTerze(m_tForza->isChecked()); });
    connect(destinazioni, &QPushButton::clicked, this, &Finestra::destinazioniTerze);
    connect(sincronizza, &QPushButton::clicked, this, &Finestra::sincronizzaTerze);
    connect(rimuovi, &QPushButton::clicked, this, &Finestra::rimuoviTerze);
    connect(modificaT, &QPushButton::clicked, this, [this] {
        const QStringList n = terzeSelezionate();
        if (n.size() != 1) return errore(L("Seleziona una sola skill di terze parti."));
        modifica(n.first(), "terze-parti");
    });
    connect(apri, &QPushButton::clicked, this, [this] {
        const QStringList n = terzeSelezionate();
        if (n.size() != 1) return errore(L("Seleziona una sola skill di terze parti."));
        QDesktopServices::openUrl(QUrl::fromLocalFile(m_stato["cartelle"].toObject()["terze"].toString() + "/" + n.first()));
    });
    connect(m_tabTerze, &QTableWidget::cellDoubleClicked, this, [this](int r, int) {
        auto *d = new DialogoSkill(m_motore, m_tabTerze->item(r, 0)->text(), "terze-parti", this);
        d->setAttribute(Qt::WA_DeleteOnClose);
        d->show();
    });
    return w;
}

QStringList Finestra::terzeSelezionate() const {
    QStringList nomi = selezionate(m_tabTerze);
    if (nomi.isEmpty())
        for (const auto &r : m_tabTerze->selectionModel()->selectedRows()) nomi << m_tabTerze->item(r.row(), 0)->text();
    return nomi;
}

void Finestra::caricaTerze() {
    m_motore->chiedi("terze_elenco", {}, [this](bool ok, const QJsonObject &r, const QString &e) {
        if (!ok) return errore(e);
        const QStringList giaScelte = selezionate(m_tabTerze);
        m_tabTerze->setSortingEnabled(false);
        m_tabTerze->setRowCount(0);
        for (const auto &x : r["skill"].toArray()) {
            const QJsonObject s = x.toObject();
            const int n = m_tabTerze->rowCount();
            m_tabTerze->insertRow(n);
            m_tabTerze->setItem(n, 0, cellaNome(s["nome"].toString(), s["cartella"].toString(), giaScelte.contains(s["nome"].toString())));
            auto *stato = new QTableWidgetItem(L(s["stato"].toString()));
            stato->setForeground(s["stato"] == "ok" ? OK : AVVISO);
            m_tabTerze->setItem(n, 1, stato);
            int c = 2;
            for (const char *k : {"commit", "aggiornata", "sincronizzata"}) m_tabTerze->setItem(n, c++, cella(s[k]));
            const QString dest = unisci(s["destinazioni"].toArray());
            auto *d = new QTableWidgetItem(dest.isEmpty() ? L("nessuna") : dest);
            if (dest.isEmpty()) d->setForeground(Qt::gray);
            m_tabTerze->setItem(n, 5, d);
            auto *sc = new QTableWidgetItem(QString::number(s["script"].toArray().size()));
            sc->setToolTip(unisci(s["script"].toArray(), "\n"));
            if (!s["script"].toArray().isEmpty()) sc->setForeground(AVVISO);
            m_tabTerze->setItem(n, 6, sc);
            m_tabTerze->setItem(n, 7, cella(s["sorgente"]));
        }
        m_tabTerze->setSortingEnabled(true);
        m_tabTerze->sortByColumn(0, Qt::AscendingOrder);
        m_tabTerze->resizeColumnsToContents();
    });
}

void Finestra::aggiungiTerze() {
    auto *d = new DialogoTerze(m_motore, m_account, this);
    d->setAttribute(Qt::WA_DeleteOnClose);
    connect(d, &DialogoTerze::aggiunte, this, [this](const QJsonArray &esiti) {
        for (const auto &x : esiti)
            if (x.toObject().contains("avviso")) registra(L("   attenzione, ") + x.toObject()["nome"].toString() + ": " + x.toObject()["avviso"].toString(), true);
        mostraEsiti(esiti, L("Skill di terze parti aggiunte"));
        caricaTerze();
        caricaCatalogo();
    });
    d->open();
}

void Finestra::aggiornaTerze(bool forza) {
    const QStringList nomi = terzeSelezionate();
    registra(L("Controllo delle sorgenti") + (nomi.isEmpty() ? QString(L(" di tutte le skill di terze parti…")) : ": " + nomi.join(", ")));
    m_motore->chiedi("terze_aggiorna", {{"nomi", QJsonArray::fromStringList(nomi)}, {"forza", forza}},
                     [this](bool ok, const QJsonObject &r, const QString &e) {
                         if (!ok) return errore(e);
                         mostraEsiti(r["esiti"].toArray(), L("Aggiornamento dalle sorgenti"));
                         caricaTerze();
                         caricaCatalogo();
                     });
}

void Finestra::destinazioniTerze() {
    const QStringList nomi = terzeSelezionate();
    if (nomi.size() != 1) return errore(L("Seleziona una sola skill di terze parti."));
    QStringList scelti;
    for (int r = 0; r < m_tabTerze->rowCount(); ++r)
        if (m_tabTerze->item(r, 0)->text() == nomi.first() && m_tabTerze->item(r, 5)->text() != L("nessuna"))
            scelti = m_tabTerze->item(r, 5)->text().split(", ");
    if (!scegliAccount(this, L("Destinazioni di ") + nomi.first(), m_account, scelti)) return;
    m_motore->chiedi("terze_destinazioni", {{"nome", nomi.first()}, {"destinazioni", QJsonArray::fromStringList(scelti)}},
                     [this](bool ok, const QJsonObject &r, const QString &e) {
                         if (!ok) return errore(e);
                         registra(r["messaggio"].toString());
                         caricaTerze();
                     });
}

void Finestra::sincronizzaTerze() {
    const QStringList nomi = terzeSelezionate();
    const bool prova = m_tProva->isChecked(), forza = m_tForza->isChecked();
    if (!prova && QMessageBox::question(this, L("Sincronizza"), QString(L("Sincronizzare %1 con i loro account di destinazione?%2"))
            .arg(nomi.isEmpty() ? L("tutte le skill di terze parti") : nomi.join(", "),
                 forza ? L("\nLe copie modificate a mano negli account verranno sostituite (prima salvate in archivio).") : "")) != QMessageBox::Yes)
        return;
    m_motore->chiedi("terze_sincronizza", {{"nomi", QJsonArray::fromStringList(nomi)}, {"prova", prova}, {"forza", forza}},
                     [this, prova](bool ok, const QJsonObject &r, const QString &e) {
                         if (!ok) return errore(e);
                         QJsonArray esiti;
                         for (const auto &x : r["esiti"].toArray()) {  // nel registro: L("nome -> account")
                             QJsonObject o = x.toObject();
                             if (o.contains("account")) o["nome"] = o["nome"].toString() + " → " + o["account"].toString();
                             esiti.append(o);
                         }
                         mostraEsiti(esiti, prova ? L("Prova di sincronizzazione (nessuna modifica)") : L("Sincronizzazione"));
                         if (!prova) { caricaTerze(); caricaCatalogo(); }
                     });
}

void Finestra::rimuoviTerze() {
    const QStringList nomi = terzeSelezionate();
    if (nomi.size() != 1) return errore(L("Seleziona una sola skill di terze parti."));
    if (QMessageBox::question(this, L("Rimuovi"), L("Rimuovere '") + nomi.first() + L("' dalle terze parti?\nLa cartella viene salvata in archivio; le copie già sincronizzate negli account restano.")) != QMessageBox::Yes)
        return;
    m_motore->chiedi("terze_rimuovi", {{"nome", nomi.first()}}, [this](bool ok, const QJsonObject &r, const QString &e) {
        if (!ok) return errore(e);
        registra(r["messaggio"].toString());
        caricaTerze();
        caricaCatalogo();
    });
}

// ---------------------------------------------------------------- esportazioni

QWidget *Finestra::creaEsportazioni() {
    auto *w = new QWidget;
    auto *v = new QVBoxLayout(w);
    auto *rc = new QHBoxLayout;
    m_cartelle = new QLabel;
    m_cartelle->setTextInteractionFlags(Qt::TextSelectableByMouse);
    auto *apriArchivio = new QPushButton(L("Apri l'archivio"));
    rc->addWidget(m_cartelle, 1);
    rc->addWidget(apriArchivio);
    v->addLayout(rc);
    connect(apriArchivio, &QPushButton::clicked, this, [this] {
        QDesktopServices::openUrl(QUrl::fromLocalFile(m_stato["cartelle"].toObject()["archivio"].toString()));
    });
    auto *g1 = new QGroupBox(L("Esportazioni del cloud (manageskill/archivio/cloud/)"));
    auto *l1 = new QVBoxLayout(g1);
    m_tabEspCloud = tabella({L("Account"), L("Data"), L("Skill"), L("Cambiate"), L("Saltate"), L("Sincronizzate il"), L("Cartella")});
    l1->addWidget(m_tabEspCloud);
    auto *r1 = new QHBoxLayout;
    auto *indice = new QPushButton(L("Apri l'indice"));
    auto *cartella1 = new QPushButton(L("Apri la cartella"));
    r1->addWidget(indice);
    r1->addWidget(cartella1);
    r1->addStretch();
    l1->addLayout(r1);
    v->addWidget(g1, 1);

    auto *g2 = new QGroupBox(L("Archivio (manageskill/archivio/)"));
    auto *l2 = new QVBoxLayout(g2);
    m_tabEspArch = tabella({L("Skill"), L("Data"), L("Cartella")});
    l2->addWidget(m_tabEspArch);
    auto *cartella2 = new QPushButton(L("Apri la cartella"));
    l2->addWidget(cartella2, 0, Qt::AlignLeft);
    v->addWidget(g2, 1);

    auto cartellaDi = [](QTableWidget *t, int colonna) {
        const auto r = t->selectionModel()->selectedRows();
        return r.isEmpty() ? QString() : t->item(r.first().row(), colonna)->text();
    };
    connect(indice, &QPushButton::clicked, this, [this, cartellaDi] {
        const QString c = cartellaDi(m_tabEspCloud, 6);
        if (c.isEmpty()) return errore(L("Seleziona un'esportazione."));
        QDesktopServices::openUrl(QUrl::fromLocalFile(c + "/indice.html"));
    });
    connect(cartella1, &QPushButton::clicked, this, [this, cartellaDi] {
        const QString c = cartellaDi(m_tabEspCloud, 6);
        if (c.isEmpty()) return errore(L("Seleziona un'esportazione."));
        QDesktopServices::openUrl(QUrl::fromLocalFile(c));
    });
    connect(cartella2, &QPushButton::clicked, this, [this, cartellaDi] {
        const QString c = cartellaDi(m_tabEspArch, 2);
        if (c.isEmpty()) return errore(L("Seleziona un'esportazione."));
        QDesktopServices::openUrl(QUrl::fromLocalFile(c));
    });
    connect(m_tabEspCloud, &QTableWidget::cellDoubleClicked, this, [this](int r, int) {
        QDesktopServices::openUrl(QUrl::fromLocalFile(m_tabEspCloud->item(r, 6)->text() + "/indice.html"));
    });
    return w;
}

void Finestra::caricaEsportazioni() {
    m_motore->chiedi("esportazioni", {}, [this](bool ok, const QJsonObject &r, const QString &e) {
        if (!ok) return errore(e);
        riempi(m_tabEspCloud, r["cloud"].toArray(), {"account", "data", "skill", "cambiate", "saltate", "sincronizzato", "cartella"});
        riempi(m_tabEspArch, r["archivio"].toArray(), {"nome", "data", "cartella"});
        const QJsonObject c = m_stato["cartelle"].toObject();
        m_cartelle->setText(L("Archivio: ") + c["archivio"].toString() + L("\nCloud: ") + c["cloud"].toString());
    });
}
