// c-manage-skill: catalogo, esportazione e sincronizzazione delle skill di Claude
// Copyright (C) 2026 Quirino Scaramastra
// SPDX-License-Identifier: GPL-3.0-or-later
// c-manage-skill-qt: interfaccia locale (Qt 6) per c-manage-skill. Nessun server: ogni operazione avvia il motore
// Python con la richiesta sullo standard input e legge la risposta JSON.
#include "finestra.h"
#include "motore.h"
#include "stile.h"
#include "lingua.h"

#include <QApplication>
#include <QIcon>

#include <functional>

int main(int argc, char *argv[]) {
    QApplication app(argc, argv);
    QApplication::setApplicationName("c-manage-skill");
    QApplication::setApplicationVersion(VERSIONE_GUI);
    QApplication::setOrganizationName("c-manage-skill");
    QGuiApplication::setDesktopFileName("c-manage-skill");  // collega la finestra all'icona del menu (Wayland)
    QApplication::setWindowIcon(QIcon(":/c-manage-skill.svg"));
    Stile::applica(app);
    Motore motore;
    Lingua::imposta(Lingua::salvata(), motore.cartellaProgetto());
    // Cambiando lingua la finestra viene ricreata, così tutti i testi passano dal dizionario
    std::function<void()> apri = [&] {
        auto *f = new Finestra(&motore);
        f->setAttribute(Qt::WA_DeleteOnClose);
        QObject::connect(f, &Finestra::linguaCambiata, f, [&, f](const QString &codice) {
            const QByteArray stato = f->saveGeometry();
            Lingua::imposta(codice, motore.cartellaProgetto());
            f->hide();
            f->deleteLater();
            apri();
            for (auto *w : QApplication::topLevelWidgets())
                if (auto *nuova = qobject_cast<Finestra *>(w); nuova && nuova != f) nuova->restoreGeometry(stato);
        });
        f->show();
    };
    apri();
    return app.exec();
}
