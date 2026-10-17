import QtQuick 2.15

Item {
    id: root

    // --- DANE ---
    property int value: 0
    property int max: 8000

    // --- KALIBRACJA ---
    property double startOffset: 0.04
    property double endOffset: 0.075

    // 1. TŁO
    Image {
        id: bg
        source: "images/rpm_dark.png"
        anchors.fill: parent
        fillMode: Image.PreserveAspectFit
        anchors.horizontalCenter: parent.horizontalCenter
    }

    // 2. CLIPPER (Maska)
    Rectangle {
        id: clipper
        color: "transparent"
        clip: true

        anchors.top: bg.top
        anchors.bottom: bg.bottom
        anchors.left: bg.left

        // --- MATEMATYKA (Twoja kalibracja) ---
        width: {
            if (root.max > 0) {
                var percent = root.value / root.max;
                if (percent > 1.0) percent = 1.0;

                var activeWidth = bg.width * (1.0 - root.startOffset - root.endOffset);
                var startPx = bg.width * root.startOffset;

                return startPx + (activeWidth * percent);
            } else {
                return 0;
            }
        }

        // 3. WYPEŁNIENIE
        Image {
            id: fill
            source: "images/rpm_fill.png"
            width: bg.width
            height: bg.height
            fillMode: Image.PreserveAspectFit
            anchors.left: parent.left
            anchors.top: parent.top
        }
    }
}