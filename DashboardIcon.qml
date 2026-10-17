import QtQuick 2.15

Item {
    id: root

    // --- TEGO BRAKOWAŁO (Przyczyny błędu) ---
    // Definiujemy właściwości, które Dashboard.qml próbuje ustawić
    property string source: ""
    property string name: ""
    property bool isActive: false
    property color activeColor: "white"

    // Główny obrazek ikony
    Image {
        id: iconImage
        anchors.fill: parent
        fillMode: Image.PreserveAspectFit
        source: root.source

        // --- LOGIKA ŚWIECENIA ---
        // Jeśli isActive == true (np. włączony kierunkowskaz), to opacity = 1.0 (widoczny)
        // Jeśli false, to opacity = 0.1 (lekko widoczny, "zgaszony")
        opacity: root.isActive ? 1.0 : 0.1

        // Płynna animacja mrugania (opcjonalnie)
        Behavior on opacity { NumberAnimation { duration: 150 } }
    }
}