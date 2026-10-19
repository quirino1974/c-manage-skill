// manage-skill: catalogo, esportazione e sincronizzazione delle skill di Claude
// Copyright (C) 2026 Quirino Scaramastra
// SPDX-License-Identifier: GPL-3.0-or-later
// Finestra principale: schede Catalogo, Cloud claude.ai, Account e chiavi, Esportazioni, più il registro.
#pragma once

#include <QJsonArray>
#include <QJsonObject>
#include <QMainWindow>

class Motore;
class QTableWidget;
class QLineEdit;
class QComboBox;
class QCheckBox;
class QLabel;
class QPlainTextEdit;
class QPushButton;

class Finestra : public QMainWindow {
    Q_OBJECT
public:
    explicit Finestra(Motore *motore, QWidget *genitore = nullptr);

signals:
    void linguaCambiata(const QString &codice);  // la finestra va ricreata nella nuova lingua

private:
    QWidget *creaCatalogo();
    QWidget *creaCloud();
    QWidget *creaAccount();
    QWidget *creaEsportazioni();
    QWidget *creaTerze();

    void avvio();
    QWidget *creaIntestazione();
    void informazioni();
    void aggiornaContatori();
    void caricaCatalogo();
    void filtraCatalogo();
    void mostraCopie();
    void salvaNota();
    void modifica(const QString &nome, const QString &fonte);
    void caricaTerze();
    void aggiungiTerze();
    void aggiornaTerze(bool forza);
    void sincronizzaTerze();
    void destinazioniTerze();
    void rimuoviTerze();
    QStringList terzeSelezionate() const;
    void configuraConsole();
    void esportaCatalogo();
    void importaCatalogo();
    void caricaCloud();
    void esportaCloud(const QJsonObject &dati);
    void caricaApiCloud();
    void cloudVersoApi();
    void caricaAccount();
    void nuovoAccount();
    void provaAccount();
    void cambiaChiave();
    void rimuoviAccount();
    void elencaRemoto();
    void eliminaRemoto();
    void caricaEsportazioni();

    QStringList selezionate(QTableWidget *t) const;
    QString accountSelezionato() const;
    void registra(const QString &testo, bool errore = false);
    void mostraEsiti(const QJsonArray &esiti, const QString &titolo);
    void errore(const QString &testo);

    Motore *m_motore;
    QJsonObject m_stato;
    QJsonArray m_catalogo, m_account;

    // catalogo
    QTableWidget *m_tabCat;
    QLineEdit *m_cerca;
    QComboBox *m_fCategoria, *m_fFonte, *m_daFonte, *m_verso;
    QCheckBox *m_fMie, *m_fDiverse, *m_prova, *m_sovrascrivi, *m_ignora;
    QLabel *m_contaCat, *m_titoloCopie;
    QTableWidget *m_tabCopie;
    QPlainTextEdit *m_nota;
    QPushButton *m_salvaNota;
    QString m_notaNome;
    // terze parti
    QTableWidget *m_tabTerze;
    QCheckBox *m_tProva, *m_tForza;
    // cloud
    QTableWidget *m_tabCloud, *m_tabApiCloud;
    QLabel *m_infoCloud;
    QCheckBox *m_cMie, *m_cIgnora, *m_cProvaApi;
    QComboBox *m_cApiAcc;
    // account
    QTableWidget *m_tabAcc, *m_tabRemoto;
    QComboBox *m_remAcc;
    QCheckBox *m_remTutte;
    // esportazioni
    QTableWidget *m_tabEspCloud, *m_tabEspArch;
    QLabel *m_cartelle;
    // intestazione
    QLabel *m_cTot, *m_cTue, *m_cDiverse, *m_cTerze, *m_versione;
    // registro
    QPlainTextEdit *m_registro;
};
