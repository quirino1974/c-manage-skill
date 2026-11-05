// c-manage-skill: catalogo, esportazione e sincronizzazione delle skill di Claude
// Copyright (C) 2026 Quirino Scaramastra
// SPDX-License-Identifier: GPL-3.0-or-later
// Finestre secondarie: scheda di una skill e nuovo account.
#pragma once

#include <QDialog>
#include <QJsonObject>

class Motore;
class QTextBrowser;
class QPushButton;
class QLineEdit;
class QComboBox;
class QCheckBox;
class QFormLayout;
class QListWidget;
class QPlainTextEdit;
class QLabel;
class QTableWidget;
#include <QJsonArray>
#include <QStringList>

// Scheda completa di una skill: descrizione, copie, file, controlli, SKILL.md e confronto tra le copie.
class DialogoSkill : public QDialog {
    Q_OBJECT
public:
    DialogoSkill(Motore *motore, const QString &nome, const QString &fonte, QWidget *genitore = nullptr);

private:
    void carica(const QString &fonte);
    void confronta();

    Motore *m_motore;
    QString m_nome;
    QTextBrowser *m_testo;
    QPushButton *m_confronta;
    QString m_htmlScheda;
};

// Nuovo account (api, claude-code, claude-ai). La chiave si scrive in un campo password e va subito al motore.
class DialogoAccount : public QDialog {
    Q_OBJECT
public:
    DialogoAccount(const QJsonObject &tipi, bool keyring, QWidget *genitore = nullptr);
    QJsonObject dati() const;   // pronto per l'azione account_salva
    void pulisciChiave();        // svuota il campo della chiave appena usata

private:
    void aggiornaCampi();

    QFormLayout *m_form;
    QLineEdit *m_nome, *m_env, *m_chiave, *m_workspace, *m_baseUrl, *m_cartella, *m_nota;
    QComboBox *m_tipo, *m_dove;
    QCheckBox *m_sostituisci;
    QWidget *m_rigaCartella;
};

// Account API della Claude Console: la chiave viene provata sulla Skills API e salvata solo se funziona.
class DialogoConsole : public QDialog {
    Q_OBJECT
public:
    DialogoConsole(Motore *motore, bool keyring, QWidget *genitore = nullptr);

signals:
    void salvato(const QString &messaggio);

private:
    void verificaESalva();

    Motore *m_motore;
    QLineEdit *m_nome, *m_chiave, *m_workspace;
    QComboBox *m_dove;
    QCheckBox *m_sostituisci;
    QPushButton *m_salva;
    QTextBrowser *m_esito;
};

// Editor dei file di una skill (SKILL.md, riferimenti, script). Salva solo copie modificabili, dopo una copia
// di sicurezza in archivio; rifiuta il salvataggio se il file è cambiato su disco nel frattempo.
class EditorSkill : public QDialog {
    Q_OBJECT
public:
    EditorSkill(Motore *motore, const QString &nome, const QString &fonte, QWidget *genitore = nullptr);

signals:
    void salvata();

protected:
    void reject() override;

private:
    void apri(const QString &file);
    void salva();
    void nuovoFile();
    bool chiediSeScartare();

    Motore *m_motore;
    QString m_nome, m_fonte, m_file, m_sha;
    bool m_solaLettura = false, m_nuovo = false;
    QListWidget *m_elenco;
    QPlainTextEdit *m_testo;
    QLabel *m_info;
    QPushButton *m_salva;
};

// Aggiunta di skill di terze parti: sorgente (Git, ZIP o cartella), anteprima, scelta delle skill e degli account.
class DialogoTerze : public QDialog {
    Q_OBJECT
public:
    DialogoTerze(Motore *motore, const QJsonArray &account, QWidget *genitore = nullptr);

signals:
    void aggiunte(const QJsonArray &esiti);

private:
    void cerca();
    void installa();

    Motore *m_motore;
    QLineEdit *m_sorgente;
    QTableWidget *m_trovate;
    QListWidget *m_account;
    QPushButton *m_installa;
    QLabel *m_stato;
    QString m_sorgenteCercata;
};

// Prompt per ricreare la skill: anteprima modificabile, copia negli appunti, salvataggio su file.
class DialogoPrompt : public QDialog {
    Q_OBJECT
public:
    DialogoPrompt(Motore *motore, const QString &nome, const QString &fonte, QWidget *genitore = nullptr);

private:
    void genera();

    Motore *m_motore;
    QString m_nome, m_fonte;
    QComboBox *m_modalita;
    QPlainTextEdit *m_testo;
    QLabel *m_info;
};

// Scelta di più account (caselle). Ritorna false se l'utente annulla.
bool scegliAccount(QWidget *genitore, const QString &titolo, const QJsonArray &account, QStringList &scelti);
