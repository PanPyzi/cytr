import QtQuick 2.15

// ============================================================
// AlertBlinker - pomocniczy komponent do ograniczonego mrugania
// ============================================================
// Gdy "active" staje się true, licznik mrugnięć startuje od zera
// i baner ma migać "maxBlinks" razy (jedno mrugnięcie = zapalone +
// zgaszone). Po osiągnięciu limitu ustawia "acknowledged: true" -
// od tego momentu ostrzeżenie uznajemy za "zobaczone" i można
// pokazać zamiast niego małą, stałą ikonkę.
//
// Gdy "active" wraca do false (usterka ustąpiła), stan resetuje się
// automatycznie - następnym razem alert znowu zamrugnie od nowa.
// ============================================================
Item {
    id: root

    property bool active: false        // czy dany alert jest aktualnie aktywny
    property int maxBlinks: 5          // <-- ZMIENNA: ile razy ma mrugnąć baner
    property int blinkIntervalMs: 400  // czas jednej "połówki" mrugnięcia

    property bool acknowledged: false  // true = baner już odmrugał swoje, pokaż ikonkę
    property bool blinkOn: true        // aktualny stan mrugania (do bindowania opacity)

    property int _blinksDone: 0

    onActiveChanged: {
        if (active) {
            // nowe wystąpienie usterki - zacznij mrugać od zera
            acknowledged = false
            _blinksDone = 0
            blinkOn = true
            blinkTimer.restart()
        } else {
            // usterka ustąpiła - zatrzymaj i wyzeruj
            blinkTimer.stop()
            blinkOn = true
            acknowledged = false
            _blinksDone = 0
        }
    }

    Timer {
        id: blinkTimer
        interval: root.blinkIntervalMs
        repeat: true
        running: false
        onTriggered: {
            root.blinkOn = !root.blinkOn
            if (!root.blinkOn) {
                root._blinksDone++
                if (root._blinksDone >= root.maxBlinks) {
                    root.acknowledged = true
                    running = false
                }
            }
        }
    }
}
