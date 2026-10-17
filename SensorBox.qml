import QtQuick 2.15

Rectangle {
    id: root
    width: 180
    height: 100
    color: "transparent"

    // Właściwości
    property string label: "TEMP"
    property string unit: "°C"
    property var value: 0

    // --- NOWA LOGIKA LIMITÓW ---
    // Ustawiamy domyślne wartości tak, aby alarm się nie włączał, jeśli ich nie podasz.
    property double minLimit: -9999 // Alarm, jeśli spadnie poniżej tego
    property double maxLimit: 9999  // Alarm, jeśli wzrośnie powyżej tego

    // Alarm włącza się, gdy wartość jest POZA zakresem (za mała LUB za duża)
    property bool isAlarmState: (value < minLimit) || (value > maxLimit)

    // --- NOWA LOGIKA: OGRANICZONE MRUGANIE ---
    // Zamiast od razu i na stałe świecić na czerwono, box najpierw mruga
    // "maxBlinks" razy (ta sama logika co reszta alertów w Dashboard.qml,
    // patrz AlertBlinker.qml), a dopiero potem zostaje na stałe czerwony.
    property int maxBlinks: 5   // <-- ZMIENNA: ile razy ma mrugnąć box

    AlertBlinker {
        id: blinker
        active: root.isAlarmState
        maxBlinks: root.maxBlinks
    }

    property color boxColor: {
        if (!isAlarmState) return "#eec200"           // norma - żółty
        if (!blinker.acknowledged) return blinker.blinkOn ? "#ff0000" : "#eec200" // mruganie
        return "#ff0000"                              // po odmruganiu - na stałe czerwony
    }

    // --- RESZTA WYGLĄDU BEZ ZMIAN ---
    border.color: root.boxColor
    border.width: 4
    radius: 8
    Behavior on border.color { ColorAnimation { duration: 100 } }

    Rectangle {
        id: headerBar
        width: parent.width
        height: 22
        color: root.boxColor
        anchors.top: parent.top
        radius: 8
        Rectangle {
            anchors.bottom: parent.bottom; width: parent.width; height: 6
            color: root.boxColor; anchors.bottomMargin: 0; z: -1
        }
        Text {
            anchors.centerIn: parent
            text: root.label
            color: "black"
            font.bold: true
            font.pixelSize: 12
        }
    }

    Text {
        text: typeof(root.value) === "number" ? root.value.toFixed(root.value % 1 === 0 ? 0 : 1) : root.value
        anchors.centerIn: parent
        anchors.verticalCenterOffset: 10
        color: "white"
        font.pixelSize: 32
        font.family: "Arial"
        font.bold: true
    }

    Text {
        text: root.unit
        anchors.right: parent.right
        anchors.rightMargin: 6
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 4
        color: root.boxColor
        font.pixelSize: 12
        font.bold: true
    }
}