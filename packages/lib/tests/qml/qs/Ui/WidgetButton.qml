import QtQuick
Item {
    property bool labelVisible: true
    property bool hasVisualContent: true
    property color foreground: "#eeeeee"
    property var bar
    property string text
    property string tooltipText
    property real fixedWidth
    property real fixedHeight
    signal pressed(int button)
    width: fixedWidth
    height: fixedHeight
    Text { anchors.centerIn: parent; text: parent.text; color: "#eeeeee"; font.family: "monospace"; font.pixelSize: 13 }
    MouseArea { anchors.fill: parent; onClicked: parent.pressed(Qt.LeftButton) }
}
