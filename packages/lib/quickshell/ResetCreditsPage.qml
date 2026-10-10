import QtQuick
import qs.Commons
import "." as Plugin
import "StableList.js" as StableList

Column {
    id: root
    property var provider: null
    property color foreground: "white"
    property string fontFamily: Style.font.family
    readonly property var inventory: provider && provider.resetCredits ? provider.resetCredits : ({available: 0, rows: [], undetailed: 0})
    signal backRequested()
    spacing: Style.space(18)
    function focusBack() { back.forceActiveFocus() }
    onInventoryChanged: StableList.sync(rows, inventory.rows, entry => entry.title + ":" + entry.expires + ":" + entry.count)
    Component.onCompleted: StableList.sync(rows, inventory.rows, entry => entry.title + ":" + entry.expires + ":" + entry.count)
    ListModel { id: rows; dynamicRoles: true }
    component Label: Text {
        textFormat: Text.PlainText
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
        wrapMode: Text.WordWrap
    }
    component Secondary: Label {
        opacity: 0.5
        font.pixelSize: Style.font.caption
    }
    Item {
        width: parent.width
        height: back.height
        Plugin.PanelButton {
            id: back
            objectName: "reset-back"
            width: parent.width
            Accessible.name: "Back to usage from " + (root.provider ? root.provider.name : "provider") + " resets"
            foreground: root.foreground
            fontFamily: root.fontFamily
            onClicked: root.backRequested()
        }
        Plugin.PanelIcon {
            anchors.left: parent.left
            anchors.leftMargin: Style.space(4)
            anchors.verticalCenter: parent.verticalCenter
            width: Style.space(16)
            height: width
            name: "arrow-left"
            foreground: root.foreground
        }
        Image {
            anchors.left: parent.left
            anchors.leftMargin: Style.space(28)
            anchors.verticalCenter: parent.verticalCenter
            width: Style.space(16)
            height: width
            source: root.provider && root.provider.logoPath ? "file://" + root.provider.logoPath : ""
            fillMode: Image.PreserveAspectFit
            asynchronous: true
        }
        Label {
            x: Style.space(52)
            width: Math.max(0, parent.width - x - Style.space(8))
            anchors.verticalCenter: parent.verticalCenter
            text: root.provider ? root.provider.name : "Back to usage"
        }
    }
    Secondary { width: parent.width; text: "Cached data"; visible: !!root.provider && root.provider.cached }
    Column {
        width: parent.width
        spacing: Style.space(8)
        Label { text: "Usage limit resets"; font.bold: true }
        Label {
            width: parent.width
            text: root.provider && root.provider.id === "codex"
                ? "Restore your 5-hour or weekly limit,\nor both, depending on the reset type."
                : "Restore eligible usage limits.\nCredits expire on the dates below."
        }
    }
    Rectangle {
        objectName: "reset-table"
        width: parent.width
        implicitHeight: table.implicitHeight + 2
        color: "transparent"
        border.width: 1
        border.color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.15)
        visible: root.inventory.available > 0
        Column {
            id: table
            x: 1
            y: 1
            width: parent.width - 2
            Rectangle {
                width: parent.width
                height: Style.space(42)
                color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.04)
                Label {
                    objectName: "reset-available"
                    anchors.fill: parent
                    anchors.margins: Style.space(12)
                    text: "Available " + root.inventory.available
                }
            }
            Row {
                x: Style.space(12)
                width: parent.width - x * 2
                topPadding: Style.space(10)
                bottomPadding: Style.space(8)
                spacing: Style.space(12)
                Secondary { width: (parent.width - parent.spacing) / 2; text: "Reset type" }
                Secondary { width: (parent.width - parent.spacing) / 2; text: "Expires" }
            }
            Repeater {
                model: rows
                delegate: Item {
                    required property var entry
                    width: table.width
                    implicitHeight: Math.max(typeCell.implicitHeight, expiryCell.implicitHeight) + Style.space(24)
                    Rectangle {
                        width: parent.width
                        height: 1
                        color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.09)
                    }
                    Column {
                        id: typeCell
                        x: Style.space(12)
                        y: Style.space(12)
                        width: (parent.width - Style.space(36)) / 2
                        spacing: Style.space(5)
                        Label { width: parent.width; text: entry.title }
                        Secondary { width: parent.width; text: entry.count + (entry.count === 1 ? " credit" : " credits") }
                    }
                    Column {
                        id: expiryCell
                        x: typeCell.x + typeCell.width + Style.space(12)
                        y: typeCell.y
                        width: typeCell.width
                        spacing: Style.space(5)
                        Label { width: parent.width; text: entry.expires }
                        Secondary { width: parent.width; text: entry.remaining + (entry.timezone ? "\n" + entry.timezone : "") }
                    }
                }
            }
        }
    }
    Label { width: parent.width; text: "No reset credits available."; visible: root.inventory.available === 0 }
    Secondary { width: parent.width; text: "Some reset details haven't been provided yet."; visible: root.inventory.undetailed > 0 }
}
