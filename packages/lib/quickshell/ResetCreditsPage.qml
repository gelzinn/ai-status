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
    spacing: Style.space(18)
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
        objectName: "reset-provider-heading"
        width: parent.width
        height: Math.max(Style.space(24), providerLabel.implicitHeight)
        Image {
            objectName: "reset-provider-logo"
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            width: Style.space(16)
            height: width
            source: root.provider ? root.provider.logoPath ? "file://" + root.provider.logoPath : Qt.resolvedUrl("../assets/providers/" + root.provider.id + ".png") : ""
            fillMode: Image.PreserveAspectFit
            asynchronous: true
        }
        Label {
            id: providerLabel
            x: Style.space(24)
            width: Math.max(0, parent.width - x)
            anchors.verticalCenter: parent.verticalCenter
            text: root.provider ? root.provider.name : ""
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
        id: resetTable
        objectName: "reset-table"
        width: parent.width
        implicitHeight: table.implicitHeight + 2
        color: "transparent"
        border.width: 1
        radius: Style.space(3)
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
                radius: Math.max(0, resetTable.radius - 1)
                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: parent.height / 2
                    color: parent.color
                }
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
