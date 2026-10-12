import QtQuick
import QtQuick.Templates as T
import qs.Commons

T.Switch {
    id: root
    property color foreground: "white"
    property string fontFamily: Style.font.family
    implicitWidth: 180
    implicitHeight: Math.max(Style.space(32), label.implicitHeight + Style.space(8))
    activeFocusOnTab: true
    opacity: enabled ? 1 : 0.35
    Accessible.name: text
    contentItem: Text {
        id: label
        leftPadding: Style.space(2)
        rightPadding: Style.space(48)
        text: root.text
        textFormat: Text.PlainText
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
        verticalAlignment: Text.AlignVCenter
        wrapMode: Text.WordWrap
    }
    indicator: Rectangle {
        width: Style.space(34)
        height: Style.space(18)
        x: root.width - width - Style.space(2)
        y: (root.height - height) / 2
        radius: height / 2
        color: root.checked ? Color.accent : "transparent"
        border.width: 1
        border.color: root.activeFocus ? root.foreground : Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.2)
        Rectangle {
            width: Style.space(12)
            height: width
            radius: width / 2
            x: root.checked ? parent.width - width - Style.space(3) : Style.space(3)
            anchors.verticalCenter: parent.verticalCenter
            color: root.checked ? Color.popups.background : root.foreground
        }
    }
    background: Rectangle {
        color: "transparent"
        radius: Style.cornerRadius
        border.width: root.activeFocus ? 1 : 0
        border.color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.2)
    }
}
