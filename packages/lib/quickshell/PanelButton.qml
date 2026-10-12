import QtQuick
import qs.Commons
import qs.Commons as Commons
import "." as Plugin

Rectangle {
    id: root
    property string text: ""
    property string iconName: ""
    property string trailingIconName: ""
    property string prefixText: ""
    readonly property real prefixWidth: prefixText ? prefix.implicitWidth + Style.space(8) : 0
    property url logoSource: ""
    readonly property bool hasLogo: logoSource.toString() !== ""
    property string fontFamily: Style.font.family
    property color foreground: "white"
    property bool alignLeft: false
    property bool outlined: false
    property bool primary: false
    property bool multiline: false
    signal clicked()

    implicitWidth: (iconName ? Style.space(16) : label.implicitWidth) + Style.space(hasLogo ? 44 : 20) + prefixWidth
    implicitHeight: multiline ? Math.max(Style.space(30), label.implicitHeight + Style.space(16)) : Style.space(30)
    radius: Style.cornerRadius
    color: primary ? (mouse.containsMouse || activeFocus ? Qt.lighter(Commons.Color.accent, 1.12) : Commons.Color.accent)
                   : mouse.containsMouse || activeFocus ? Qt.rgba(foreground.r, foreground.g, foreground.b, 0.09) : "transparent"
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
        anchors.leftMargin: Style.space(root.hasLogo ? 34 : 10) + root.prefixWidth
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
    Text {
        id: prefix
        anchors.left: parent.left
        anchors.leftMargin: Style.space(10)
        anchors.verticalCenter: parent.verticalCenter
        text: root.prefixText
        textFormat: Text.PlainText
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
    }
    Item {
        anchors.left: parent.left
        anchors.leftMargin: Style.space(10) + root.prefixWidth
        anchors.verticalCenter: parent.verticalCenter
        width: Style.space(16)
        height: width
        visible: root.hasLogo
        Image {
            id: logo
            objectName: "provider-logo"
            anchors.fill: parent
            source: root.logoSource
            fillMode: Image.PreserveAspectFit
            asynchronous: true
        }
        Text {
            anchors.centerIn: parent
            visible: logo.status !== Image.Ready
            text: "◇"
            color: root.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
        }
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
        objectName: "trailing-icon"
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
