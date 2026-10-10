import QtQuick
import qs.Commons
import "." as Plugin

Rectangle {
    id: root
    property string text: ""
    property string iconName: ""
    property string trailingIconName: ""
    property string fontFamily: Style.font.family
    property color foreground: "white"
    property bool alignLeft: false
    property bool outlined: false
    property bool multiline: false
    signal clicked()

    implicitWidth: (iconName ? Style.space(16) : label.implicitWidth) + Style.space(20)
    implicitHeight: multiline ? Math.max(Style.space(30), label.implicitHeight + Style.space(16)) : Style.space(30)
    radius: Style.space(3)
    color: mouse.containsMouse || activeFocus ? Qt.rgba(foreground.r, foreground.g, foreground.b, 0.09) : "transparent"
    border.width: outlined || activeFocus ? 1 : 0
    border.color: Qt.rgba(foreground.r, foreground.g, foreground.b, 0.2)
    opacity: enabled ? 1 : 0.35
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: text
    Accessible.onPressAction: if (enabled) clicked()
    Keys.onReturnPressed: if (enabled) clicked()
    Keys.onEnterPressed: if (enabled) clicked()
    Keys.onSpacePressed: if (enabled) clicked()
    Keys.onTabPressed: nextItemInFocusChain(true).forceActiveFocus(Qt.TabFocusReason)
    Keys.onBacktabPressed: nextItemInFocusChain(false).forceActiveFocus(Qt.BacktabFocusReason)

    Text {
        id: label
        visible: root.iconName === ""
        anchors.fill: parent
        anchors.leftMargin: Style.space(10)
        anchors.rightMargin: Style.space(root.trailingIconName ? 34 : 10)
        text: root.text
        textFormat: Text.PlainText
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
        horizontalAlignment: root.alignLeft ? Text.AlignLeft : Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        wrapMode: root.multiline ? Text.WordWrap : Text.NoWrap
        elide: root.multiline ? Text.ElideNone : Text.ElideRight
    }
    Plugin.PanelIcon {
        anchors.centerIn: parent
        width: Style.space(16)
        height: Style.space(16)
        visible: root.iconName !== ""
        name: root.iconName
        foreground: root.foreground
    }
    Plugin.PanelIcon {
        anchors.right: parent.right
        anchors.rightMargin: Style.space(8)
        anchors.verticalCenter: parent.verticalCenter
        width: Style.space(16)
        height: Style.space(16)
        visible: root.trailingIconName !== ""
        name: root.trailingIconName
        foreground: root.foreground
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: {
            root.forceActiveFocus()
            root.clicked()
        }
    }
}
