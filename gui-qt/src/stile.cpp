// manage-skill: catalogo, esportazione e sincronizzazione delle skill di Claude
// Copyright (C) 2026 Quirino Scaramastra
// SPDX-License-Identifier: GPL-3.0-or-later
#include "stile.h"

#include "lingua.h"

#include <QApplication>
#include <QPalette>
#include <QPushButton>
#include <QSet>
#include <QStyle>
#include <QStyleFactory>
#include <QStyleHints>

namespace {

struct Colori {
    const char *fondo, *carta, *campo, *riga, *alterna, *testo, *tenue, *accento, *accentoChiaro, *selezione, *rosso;
};

const Colori CHIARO{"#F3F5FB", "#FFFFFF", "#FFFFFF", "#DCE1EE", "#F7F9FD", "#141B33", "#5B6582", "#3B6FE0", "#5584EA", "#E3EBFD", "#B42318"};
const Colori SCURO{"#10152A", "#181F3B", "#141A33", "#2A3460", "#1C2446", "#E8ECF8", "#9AA5C4", "#6C8CFF", "#86A0FF", "#26336A", "#FF8A80"};

bool g_scuro = false;

QString foglio(const Colori &c) {
    return QString(R"(
QMainWindow, QDialog { background: %1; }
QWidget { color: %6; }
QToolTip { color: %6; background: %2; border: 1px solid %4; padding: 4px; }

#intestazione { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3B6FE0, stop:1 #6A3FD1); }
#intestazione QLabel { color: white; background: transparent; }
#titolo { font-size: 17pt; font-weight: 700; }
#sottotitolo { color: rgba(255,255,255,0.82); }
#contatore { background: rgba(255,255,255,0.16); border-radius: 11px; padding: 4px 11px; font-weight: 600; }
#contatore[avviso="true"] { background: rgba(255,170,60,0.35); }
#intestazione QPushButton { background: rgba(255,255,255,0.14); color: white; border: 1px solid rgba(255,255,255,0.35); }
#intestazione QPushButton:hover { background: rgba(255,255,255,0.26); }

QTabWidget::pane { border: 1px solid %4; border-radius: 12px; background: %2; top: -1px; }
QTabBar::tab { padding: 9px 18px; margin-right: 3px; color: %7; background: transparent;
               border-top-left-radius: 9px; border-top-right-radius: 9px; }
QTabBar::tab:hover { color: %6; }
QTabBar::tab:selected { color: %8; background: %2; border: 1px solid %4; border-bottom: 3px solid %8; font-weight: 600; }

QPushButton { background: %2; border: 1px solid %4; border-radius: 8px; padding: 6px 14px; }
QPushButton:hover { border-color: %8; }
QPushButton:pressed { background: %10; }
QPushButton:disabled { color: %7; border-color: %4; }
QPushButton[ruolo="primario"] { background: %8; color: white; border-color: %8; font-weight: 600; }
QPushButton[ruolo="primario"]:hover { background: %9; border-color: %9; }
QPushButton[ruolo="primario"]:disabled { background: %4; border-color: %4; color: %7; }
QPushButton[ruolo="pericolo"] { color: %11; }
QPushButton[ruolo="pericolo"]:hover { border-color: %11; }

QLineEdit, QComboBox, QPlainTextEdit, QTextBrowser, QListWidget {
    background: %3; border: 1px solid %4; border-radius: 8px; padding: 5px 8px; selection-background-color: %8; selection-color: white; }
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QListWidget:focus { border-color: %8; }
QComboBox::drop-down { border: 0; width: 22px; }
QComboBox QAbstractItemView { background: %2; border: 1px solid %4; selection-background-color: %10; selection-color: %6; }

QTableWidget { background: %2; alternate-background-color: %5; border: 1px solid %4; border-radius: 10px;
               gridline-color: transparent; selection-background-color: %10; selection-color: %6; }
QTableWidget::item { padding: 3px 6px; }
QHeaderView::section { background: %2; color: %7; border: 0; border-bottom: 1px solid %4; padding: 7px 8px; font-weight: 600; }
QTableCornerButton::section { background: %2; border: 0; }

QGroupBox { border: 1px solid %4; border-radius: 12px; margin-top: 16px; padding: 12px 8px 8px 8px; background: %2; }
QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 6px; color: %7; font-weight: 600; }

QStatusBar { color: %7; }
QSplitter::handle { background: transparent; }
QSplitter::handle:vertical { height: 8px; }
QScrollBar:vertical { background: transparent; width: 11px; margin: 2px; }
QScrollBar::handle:vertical { background: %4; border-radius: 4px; min-height: 30px; }
QScrollBar:horizontal { background: transparent; height: 11px; margin: 2px; }
QScrollBar::handle:horizontal { background: %4; border-radius: 4px; min-width: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
#registro { font-family: monospace; font-size: 9pt; }
QCheckBox::indicator, QTableWidget::indicator, QListWidget::indicator { width: 15px; height: 15px; border: 1px solid %7; border-radius: 4px; background: %3; }
QCheckBox::indicator:checked, QTableWidget::indicator:checked, QListWidget::indicator:checked { background: %8; border-color: %8; image: none; }
QCheckBox::indicator:hover, QTableWidget::indicator:hover { border-color: %8; }
)")
        .arg(c.fondo, c.carta, c.campo, c.riga, c.alterna, c.testo, c.tenue, c.accento, c.accentoChiaro)
        .arg(c.selezione, c.rosso);
}

}  // namespace

namespace Stile {

bool scuro() { return g_scuro; }
QString verde() { return g_scuro ? "#4CC38A" : "#1B7F4B"; }
QString arancio() { return g_scuro ? "#F0B44C" : "#A85A00"; }
QString rosso() { return g_scuro ? "#FF8A80" : "#B42318"; }

void applica(QApplication &app) {
    // MANAGE_SKILL_TEMA=chiaro|scuro forza il tema; altrimenti segue quello del sistema
    const QString tema = qEnvironmentVariable("MANAGE_SKILL_TEMA").toLower();
    const auto schema = QGuiApplication::styleHints()->colorScheme();
    if (tema == "scuro" || tema == "chiaro")
        g_scuro = tema == "scuro";
    else
        g_scuro = schema == Qt::ColorScheme::Dark ||
                  (schema == Qt::ColorScheme::Unknown && app.palette().color(QPalette::Window).lightness() < 128);
    app.setStyle(QStyleFactory::create("Fusion"));
    const Colori &c = g_scuro ? SCURO : CHIARO;
    QPalette p;
    p.setColor(QPalette::Window, QColor(c.fondo));
    p.setColor(QPalette::WindowText, QColor(c.testo));
    p.setColor(QPalette::Base, QColor(c.campo));
    p.setColor(QPalette::AlternateBase, QColor(c.alterna));
    p.setColor(QPalette::Text, QColor(c.testo));
    p.setColor(QPalette::Button, QColor(c.carta));
    p.setColor(QPalette::ButtonText, QColor(c.testo));
    p.setColor(QPalette::Highlight, QColor(c.accento));
    p.setColor(QPalette::HighlightedText, Qt::white);
    p.setColor(QPalette::ToolTipBase, QColor(c.carta));
    p.setColor(QPalette::ToolTipText, QColor(c.testo));
    p.setColor(QPalette::PlaceholderText, QColor(c.tenue));
    p.setColor(QPalette::Link, QColor(c.accento));
    p.setColor(QPalette::Disabled, QPalette::Text, QColor(c.tenue));
    p.setColor(QPalette::Disabled, QPalette::ButtonText, QColor(c.tenue));
    p.setColor(QPalette::Disabled, QPalette::WindowText, QColor(c.tenue));
    app.setPalette(p);
    app.setStyleSheet(foglio(c));
}

void ruoli(QWidget *radice) {
    static const QSet<QString> primari{"Importa", "Esporta tutte le mie", "Importa in account API", "Sincronizza con gli account",
                                       "Aggiungi…", "Nuovo account…", "Salva nota", "Verifica e salva", "Aggiungi le selezionate",
                                       "Salva account", "Cerca skill", "Salva (Ctrl+S)", "Copia negli appunti"};
    static const QSet<QString> pericolo{"Rimuovi", "Elimina la selezionata…"};
    for (auto *b : radice->findChildren<QPushButton *>()) {
        auto contiene = [b](const QSet<QString> &insieme) {
            for (const auto &x : insieme)
                if (b->text() == x || b->text() == L(x)) return true;
            return false;
        };
        const char *ruolo = contiene(primari) ? "primario" : contiene(pericolo) ? "pericolo" : nullptr;
        if (!ruolo) continue;
        b->setProperty("ruolo", ruolo);
        b->style()->unpolish(b);  // il foglio di stile rilegge la proprietà
        b->style()->polish(b);
    }
}

}  // namespace Stile
