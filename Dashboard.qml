import QtQuick 2.15
import QtQuick.Window 2.15

Window {
    visible: true
    visibility: Window.FullScreen
    color: "black"

    // Rozdzielczość ekranu
    width: 1024
    height: 600

    Item {
        id: mainContainer
        anchors.fill: parent

        // ============================================================
        // NAWIGACJA: 3 STRONY (SWIPE PALCEM + PRZEŁĄCZNIK GPIO PIN A/B)
        // ============================================================
        Flickable {
            id: pager
            anchors.fill: parent
            contentWidth: width * 3
            contentHeight: height
            flickableDirection: Flickable.HorizontalFlick
            boundsBehavior: Flickable.StopAtBounds
            clip: true

            property int currentPage: 1

            Component.onCompleted: contentX = currentPage * width

            onMovementEnded: {
                var target = Math.round(contentX / width)
                target = Math.max(0, Math.min(2, target))
                currentPage = target
                snapAnimation.to = target * width
                snapAnimation.restart()
            }

            NumberAnimation {
                id: snapAnimation
                target: pager
                property: "contentX"
                duration: 200
                easing.type: Easing.OutCubic
            }

            Row {
                id: pageRow
                width: pager.contentWidth
                height: pager.height

                // STRONA 1: BARE BONES
                Item {
                    id: page1
                    width: pager.width
                    height: pager.height

                    Item {
                        id: shiftLight
                        anchors.fill: parent

                        property int segmentWidth: 100
                        property var segments: [
                            { threshold: 4000, color: "#33cc33" },
                            { threshold: 5500, color: "#ffcc00" },
                        ]

                        property int redFillThreshold: 6600
                        property color redFillColor: "#ff2222"

                        Repeater {
                            model: shiftLight.segments.length
                            Rectangle {
                                x: index * shiftLight.segmentWidth
                                y: 0
                                width: shiftLight.segmentWidth
                                height: parent.height
                                color: CarData.rpm >= shiftLight.segments[index].threshold
                                       ? shiftLight.segments[index].color
                                       : "transparent"
                                Behavior on color { ColorAnimation { duration: 120 } }
                            }
                        }

                        Repeater {
                            model: shiftLight.segments.length
                            Rectangle {
                                x: shiftLight.width - (index + 1) * shiftLight.segmentWidth
                                y: 0
                                width: shiftLight.segmentWidth
                                height: parent.height
                                color: CarData.rpm >= shiftLight.segments[index].threshold
                                       ? shiftLight.segments[index].color
                                       : "transparent"
                                Behavior on color { ColorAnimation { duration: 120 } }
                            }
                        }

                        Rectangle {
                            x: shiftLight.segments.length * shiftLight.segmentWidth
                            y: 0
                            width: shiftLight.width - 2 * shiftLight.segments.length * shiftLight.segmentWidth
                            height: parent.height
                            color: shiftLight.redFillColor
                            opacity: CarData.rpm > shiftLight.redFillThreshold ? 1.0 : 0.0
                            Behavior on opacity { NumberAnimation { duration: 100 } }
                        }
                    }

                    Text {
                        anchors.top: parent.top
                        anchors.topMargin: 30
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: CarData.rpm
                        color: "white"
                        font.pixelSize: 46
                        font.bold: true
                    }

                    Text {
                        anchors.centerIn: parent
                        text: CarData.speed
                        color: "white"
                        font.pixelSize: 200
                        font.bold: true
                    }

                    Row {
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: 112
                        anchors.horizontalCenter: parent.horizontalCenter
                        spacing: 16
                        z: 50

                        DashboardIcon {
                            source: "images/oil_press.png"
                            isActive: true
                            activeColor: "#ff3333"
                            visible: CarData.oilAlert && oilBlink.acknowledged
                            width: 30; height: 30
                        }
                        DashboardIcon {
                            source: "images/overheat.png"
                            isActive: true
                            activeColor: "#ff3333"
                            visible: CarData.overheatAlert && overheatBlink.acknowledged
                            width: 30; height: 30
                        }
                        DashboardIcon {
                            source: "images/battery.png"
                            isActive: true
                            activeColor: "#ffcc00"
                            visible: CarData.batteryAlert && batteryBlink.acknowledged
                            width: 30; height: 30
                        }
                        DashboardIcon {
                            source: "images/check_engine.png"
                            isActive: true
                            activeColor: "#ffcc00"
                            visible: CarData.checkAlert && checkBlink.acknowledged
                            width: 30; height: 30
                        }
                    }

                    Row {
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: 40
                        anchors.horizontalCenter: parent.horizontalCenter
                        spacing: 70

                        Column {
                            spacing: 4
                            Text { anchors.horizontalCenter: parent.horizontalCenter; text: "TRIP CZAS"; color: "#AAAAAA"; font.pixelSize: 15; font.bold: true }
                            Text { anchors.horizontalCenter: parent.horizontalCenter; text: CarData.tripTime; color: "white"; font.pixelSize: 32; font.bold: true }
                        }
                        Column {
                            spacing: 4
                            Text { anchors.horizontalCenter: parent.horizontalCenter; text: "TRIP DYSTANS"; color: "#AAAAAA"; font.pixelSize: 15; font.bold: true }
                            Text { anchors.horizontalCenter: parent.horizontalCenter; text: CarData.tripDist + " km"; color: "white"; font.pixelSize: 32; font.bold: true }
                        }
                        Column {
                            spacing: 4
                            Text { anchors.horizontalCenter: parent.horizontalCenter; text: "WODA"; color: "#AAAAAA"; font.pixelSize: 15; font.bold: true }
                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: CarData.waterTemp + " °C"
                                color: CarData.waterTemp > 105 ? "#ff3333" : "white"
                                font.pixelSize: 32; font.bold: true
                            }
                        }
                    }
                }

                // STRONA 2: DOJAZDÓWKA
                Item {
                    id: page2
                    width: pager.width
                    height: pager.height

                    Item {
                        x: 0; y: 20
                        width: 1024
                        height: 160
                        z: 0

                        RpmGauge {
                            anchors.fill: parent
                            value: CarData.rpm
                            max: 8000
                        }

                        Text {
                            text: CarData.rpm
                            color: "white"
                            font.pixelSize: 30
                            font.bold: true
                            x: 512 - (contentWidth / 2)
                            y: 130
                        }
                    }

                    Item {
                        x: 362; y: 150
                        width: 300; height: 200
                        z: 10

                        Column {
                            anchors.centerIn: parent
                            Text {
                                id: speedText
                                text: CarData.speed
                                color: "white"
                                font.pixelSize: 140
                                font.bold: true
                                anchors.horizontalCenter: parent.horizontalCenter
                            }
                        }
                    }

                    Item {
                        x: 24
                        y: 180
                        width: 300
                        height: 150

                        Text {
                            text: CarData.time
                            color: "white"
                            font.pixelSize: 60
                            font.bold: true
                            anchors.horizontalCenter: parent.horizontalCenter
                        }
                    }

                    Item {
                        x: 700
                        y: 180
                        width: 300
                        height: 150
                        z: 10

                        Column {
                            spacing: 10

                            Text {
                                text: CarData.tripTime
                                color: "white"
                                font.pixelSize: 50
                                font.bold: true
                                anchors.horizontalCenter: parent.horizontalCenter
                            }

                            Row {
                                spacing: 10
                                anchors.horizontalCenter: parent.horizontalCenter

                                Text {
                                    text: "DIST:"
                                    color: "#AAAAAA"
                                    font.pixelSize: 24
                                    font.bold: true
                                    anchors.verticalCenter: parent.verticalCenter
                                }

                                Text {
                                    text: CarData.dist + " km"
                                    color: "white"
                                    font.pixelSize: 32
                                    font.bold: true
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }
                        }
                    }

                    Text {
                        anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        anchors.rightMargin: 10
                        anchors.bottomMargin: 5

                        text: "CPU: " + CarData.cpuTemp.toFixed(1) + "°C"
                        color: "#666666"
                        font.pixelSize: 14
                        font.bold: true

                        states: State {
                            when: CarData.cpuTemp > 80
                            PropertyChanges { target: parent; color: "red"; font.pixelSize: 20 }
                        }
                    }

                    Item {
                        x: 362; y: 370
                        width: 300; height: 80

                        Row {
                            anchors.centerIn: parent
                            spacing: 30

                            DashboardIcon {
                                source: "images/turn_left.png"
                                isActive: CarData.leftTurn
                                activeColor: "#00FF00"
                                width: 50; height: 50
                            }

                            Item {
                                width: 50; height: 50

                                DashboardIcon {
                                    anchors.fill: parent
                                    source: "images/no_beams.png"
                                    isActive: true
                                    visible: !CarData.lightsOn && !CarData.highBeam
                                    activeColor: "white"
                                }

                                DashboardIcon {
                                    anchors.fill: parent
                                    source: "images/low_beam.png"
                                    isActive: CarData.lightsOn
                                    visible: CarData.lightsOn && !CarData.highBeam
                                    activeColor: "#00FF00"
                                }

                                DashboardIcon {
                                    anchors.fill: parent
                                    source: "images/high_beam.png"
                                    isActive: CarData.highBeam
                                    visible: CarData.highBeam
                                    activeColor: "#0066FF"
                                }
                            }

                            DashboardIcon {
                                source: "images/turn_right.png"
                                isActive: CarData.rightTurn
                                activeColor: "#00FF00"
                                width: 50; height: 50
                            }
                        }
                    }

                    Item {
                        x: 180; y: 360; width: 180; height: 100
                        SensorBox { anchors.fill: parent; label: "WATER TEMP"; unit: "°C"; value: CarData.waterTemp; maxLimit: 105 }
                    }
                    Item {
                        x: 664; y: 360; width: 180; height: 100
                        SensorBox { anchors.fill: parent; label: "FUEL"; unit: "%"; value: CarData.fuel }
                    }

                    Row {
                        anchors.horizontalCenter: parent.horizontalCenter
                        y: 470
                        spacing: 20
                        z: 50

                        DashboardIcon {
                            source: "images/oil_press.png"
                            isActive: true
                            activeColor: "#ff3333"
                            visible: CarData.oilAlert && oilBlink.acknowledged
                            width: 34; height: 34
                        }
                        DashboardIcon {
                            source: "images/overheat.png"
                            isActive: true
                            activeColor: "#ff3333"
                            visible: CarData.overheatAlert && overheatBlink.acknowledged
                            width: 34; height: 34
                        }
                        DashboardIcon {
                            source: "images/battery.png"
                            isActive: true
                            activeColor: "#ffcc00"
                            visible: CarData.batteryAlert && batteryBlink.acknowledged
                            width: 34; height: 34
                        }
                        DashboardIcon {
                            source: "images/check_engine.png"
                            isActive: true
                            activeColor: "#ffcc00"
                            visible: CarData.checkAlert && checkBlink.acknowledged
                            width: 34; height: 34
                        }
                    }
                }

                // STRONA 3: DEBUG / SUROWE DANE
                Item {
                    id: page3
                    width: pager.width
                    height: pager.height

                    Text {
                        text: "DEBUG / RAW DATA"
                        color: "#00FF00"
                        font.pixelSize: 22
                        font.bold: true
                        font.family: "monospace"
                        x: 24; y: 14
                    }

                    Row {
                        x: 24; y: 55
                        spacing: 50

                        Column {
                            spacing: 6
                            width: 470

                            Text { text: "Czas: " + CarData.time; color: "white"; font.pixelSize: 18; font.family: "monospace" }
                            Text { text: "CPU Temp: " + CarData.cpuTemp.toFixed(1) + " °C"; color: "white"; font.pixelSize: 18; font.family: "monospace" }

                            Item { width: 1; height: 6 }

                            Text { text: "-- CAN BUS --"; color: "#00AAFF"; font.pixelSize: 16; font.bold: true; font.family: "monospace" }
                            Text { text: "Status: " + (CarData.canConnected ? "OK" : "BRAK"); color: CarData.canConnected ? "#33cc33" : "#ff3333"; font.pixelSize: 16; font.family: "monospace" }
                            Text { text: "RPM: " + CarData.rpm; color: "white"; font.pixelSize: 16; font.family: "monospace" }
                            Text { text: "Prędkość: " + CarData.speed + " km/h"; color: "white"; font.pixelSize: 16; font.family: "monospace" }
                            Text { text: "Woda (CAN): " + CarData.waterTemp + " °C"; color: "white"; font.pixelSize: 16; font.family: "monospace" }
                            Text { text: "Paliwo: " + CarData.fuel + " %"; color: "white"; font.pixelSize: 16; font.family: "monospace" }
                            Text { text: "Przebieg: " + CarData.dist + " km"; color: "white"; font.pixelSize: 16; font.family: "monospace" }
                            Text { text: "Trip dystans: " + CarData.tripDist + " km"; color: "white"; font.pixelSize: 16; font.family: "monospace" }
                            Text { text: "Trip czas: " + CarData.tripTime; color: "white"; font.pixelSize: 16; font.family: "monospace" }

                            Item { width: 1; height: 6 }

                            Text { text: "Lewy kierunkowskaz: " + (CarData.leftTurn ? "TAK" : "nie"); color: "white"; font.pixelSize: 13; font.family: "monospace" }
                            Text { text: "Prawy kierunkowskaz: " + (CarData.rightTurn ? "TAK" : "nie"); color: "white"; font.pixelSize: 13; font.family: "monospace" }
                            Text { text: "Światła mijania: " + (CarData.lightsOn ? "TAK" : "nie"); color: "white"; font.pixelSize: 13; font.family: "monospace" }
                            Text { text: "Światła drogowe: " + (CarData.highBeam ? "TAK" : "nie"); color: "white"; font.pixelSize: 13; font.family: "monospace" }
                            Text { text: "Brak świateł: " + (CarData.noBeams ? "TAK" : "nie"); color: "white"; font.pixelSize: 13; font.family: "monospace" }

                            Item { width: 1; height: 6 }

                            Text { text: "Alarm oleju: " + (CarData.oilAlert ? "TAK" : "nie"); color: CarData.oilAlert ? "#ff3333" : "white"; font.pixelSize: 13; font.family: "monospace" }
                            Text { text: "Alarm przegrzania: " + (CarData.overheatAlert ? "TAK" : "nie"); color: CarData.overheatAlert ? "#ff3333" : "white"; font.pixelSize: 13; font.family: "monospace" }
                            Text { text: "Check Engine: " + (CarData.checkAlert ? "TAK" : "nie"); color: CarData.checkAlert ? "#ff3333" : "white"; font.pixelSize: 13; font.family: "monospace" }
                            Text { text: "Alarm akumulatora: " + (CarData.batteryAlert ? "TAK" : "nie"); color: CarData.batteryAlert ? "#ff3333" : "white"; font.pixelSize: 13; font.family: "monospace" }
                        }
                    }

                    // PRZYCISK BLUETOOTH
                    Rectangle {
                        id: btButton
                        x: 750
                        y: 50
                        width: 220
                        height: 80
                        radius: 12

                        color: CarData.btPairingActive ? "#00FF00" : (CarData.btActive ? "#00AAFF" : "#333333")
                        border.color: "#666666"
                        border.width: 2

                        Behavior on color {
                            ColorAnimation { duration: 100 }
                        }

                        Column {
                            anchors.centerIn: parent
                            spacing: 4
                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: CarData.btPairingActive ? "PAROWANIE..." : (CarData.btActive ? "BLUETOOTH ON" : "BLUETOOTH OFF")
                                color: CarData.btPairingActive ? "black" : (CarData.btActive ? "black" : "#aaaaaa")
                                font.pixelSize: 16
                                font.bold: true
                            }
                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: "(przytrzymaj = paruj)"
                                color: CarData.btPairingActive ? "#222222" : (CarData.btActive ? "#222222" : "#666666")
                                font.pixelSize: 11
                            }
                        }

                        MouseArea {
                            id: mouseArea
                            anchors.fill: parent

                            property bool heldFired: false

                            Timer {
                                id: holdTimer
                                interval: 800
                                repeat: false
                                onTriggered: {
                                    parent.heldFired = true
                                    CarData.startBtPairing()
                                }
                            }

                            onPressed: {
                                heldFired = false
                                holdTimer.start()
                            }

                            onReleased: {
                                holdTimer.stop()
                            }

                            onCanceled: {
                                holdTimer.stop()
                            }

                            onClicked: {
                                if (!heldFired) {
                                    CarData.toggleBluetooth()
                                }
                            }
                        }
                    }
                }
            }
        }

        Connections {
            target: CarData
            function onPageRequestChanged(page) {
                pager.currentPage = page
                snapAnimation.to = page * pager.width
                snapAnimation.restart()
            }
        }

        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 6
            spacing: 10
            z: 500

            Repeater {
                model: 3
                Rectangle {
                    width: 10; height: 10; radius: 5
                    color: pager.currentPage === index ? "white" : "#555555"
                }
            }
        }

        // POPUP PAROWANIA BLUETOOTH
        Rectangle {
            id: btPairingPopup
            anchors.fill: parent
            color: "#EE000000"
            visible: CarData.btPairingActive && CarData.btPinCode !== ""
            z: 1000

            Rectangle {
                width: 600
                height: 380
                color: "#1e1e1e"
                border.color: "#00AAFF"
                border.width: 3
                radius: 16
                anchors.centerIn: parent

                Column {
                    anchors.centerIn: parent
                    spacing: 20

                    Text {
                        text: "PAROWANIE BLUETOOTH"
                        color: "#00AAFF"
                        font.pixelSize: 26
                        font.bold: true
                        anchors.horizontalCenter: parent.horizontalCenter
                    }

                    Text {
                        text: "Urządzenie: " + CarData.btDeviceName
                        color: "white"
                        font.pixelSize: 18
                        anchors.horizontalCenter: parent.horizontalCenter
                    }

                    Text {
                        text: "KOD POTWIERDZENIA:"
                        color: "#AAAAAA"
                        font.pixelSize: 16
                        font.bold: true
                        anchors.horizontalCenter: parent.horizontalCenter
                    }

                    Rectangle {
                        width: 320
                        height: 70
                        color: "#111111"
                        border.color: "#333333"
                        radius: 10
                        anchors.horizontalCenter: parent.horizontalCenter

                        Text {
                            anchors.centerIn: parent
                            text: CarData.btPinCode
                            color: "#00FF00"
                            font.pixelSize: 42
                            font.bold: true
                            font.family: "monospace"
                        }
                    }

                    Item { width: 1; height: 10 }

                    Row {
                        spacing: 30
                        anchors.horizontalCenter: parent.horizontalCenter

                        Rectangle {
                            width: 200
                            height: 60
                            color: "#00aa00"
                            radius: 10

                            Text {
                                anchors.centerIn: parent
                                text: "ZATWIERDŹ"
                                color: "white"
                                font.pixelSize: 20
                                font.bold: true
                            }

                            MouseArea {
                                anchors.fill: parent
                                onClicked: {
                                    CarData.confirmPairing(true)
                                }
                            }
                        }

                        Rectangle {
                            width: 200
                            height: 60
                            color: "#aa0000"
                            radius: 10

                            Text {
                                anchors.centerIn: parent
                                text: "ODRZUĆ"
                                color: "white"
                                font.pixelSize: 20
                                font.bold: true
                            }

                            MouseArea {
                                anchors.fill: parent
                                onClicked: {
                                    CarData.confirmPairing(false)
                                }
                            }
                        }
                    }
                }
            }
        }

        Item {
            id: warningSystem
            anchors.fill: parent
            z: 100

            property int alertMaxBlinks: 5

            AlertBlinker { id: oilBlink;      active: CarData.oilAlert;               maxBlinks: warningSystem.alertMaxBlinks }
            AlertBlinker { id: overheatBlink; active: CarData.overheatAlert;          maxBlinks: warningSystem.alertMaxBlinks }
            AlertBlinker { id: batteryBlink;  active: CarData.batteryAlert;           maxBlinks: warningSystem.alertMaxBlinks }
            AlertBlinker { id: checkBlink;    active: CarData.checkAlert;             maxBlinks: warningSystem.alertMaxBlinks }

            property string message: {
                if (CarData.oilAlert && !oilBlink.acknowledged) return "CRITICAL: OIL PRESSURE!"
                if (CarData.overheatAlert && !overheatBlink.acknowledged) return "CRITICAL: ENGINE OVERHEAT!"
                if (CarData.batteryAlert && !batteryBlink.acknowledged) return "WARNING: BATTERY SYSTEM!"
                if (CarData.checkAlert && !checkBlink.acknowledged) return "WARNING: CHECK ENGINE!"
                return ""
            }

            property bool currentBlinkOn: {
                if (CarData.oilAlert && !oilBlink.acknowledged) return oilBlink.blinkOn
                if (CarData.overheatAlert && !overheatBlink.acknowledged) return overheatBlink.blinkOn
                if (CarData.batteryAlert && !batteryBlink.acknowledged) return batteryBlink.blinkOn
                if (CarData.checkAlert && !checkBlink.acknowledged) return checkBlink.blinkOn
                return true
            }

            visible: message !== ""

            Rectangle {
                width: parent.width; height: 120
                color: "#ccff0000"
                anchors.centerIn: parent
                radius: 10; border.color: "white"; border.width: 5

                opacity: warningSystem.currentBlinkOn ? 1.0 : 0.2
                Behavior on opacity { NumberAnimation { duration: 120 } }

                Text {
                    anchors.centerIn: parent
                    text: warningSystem.message
                    color: "white"
                    font.pixelSize: 45; font.bold: true
                }
            }
        }

        Rectangle {
            id: connectionWarning
            anchors.fill: parent
            color: "#CC000000"
            visible: !CarData.canConnected
            z: 999

            Column {
                anchors.centerIn: parent
                spacing: 20

                Text {
                    text: "INITIALIZING HARDWARE..."
                    color: "white"
                    font.pixelSize: 40
                    font.bold: true
                    anchors.horizontalCenter: parent.horizontalCenter
                }

                Text {
                    text: "CAN: " + (CarData.canConnected ? "OK" : "SEARCHING...")
                    color: CarData.canConnected ? "green" : "red"
                    font.pixelSize: 20
                    anchors.horizontalCenter: parent.horizontalCenter
                }
            }
        }
    }
}